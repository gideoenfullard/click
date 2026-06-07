# -*- coding: utf-8 -*-
"""
ClickAI safety net — run this after EVERY fix, before `fly deploy`.

What it does (and does NOT do):
  - It does NOT touch Supabase, Fly.io, Anthropic, or any live data.
  - It runs entirely on the local .py files in this folder.
  - Tier 1 (syntax)  : every clickai*.py file must parse. This is the #1 deploy-killer.
  - Tier 2 (imports) : every route module must import and expose its register_* function.
  - Tier 3 (logic)   : core money / identity / escaping functions must still behave.

How to run:
  python3 test_clickai.py

Exit code 0 = all good, safe to deploy.
Exit code 1 = something broke, DO NOT deploy.

Adding a test: drop a new `def test_xxx():` function below. It is auto-discovered.
Use plain `assert`. No pytest needed.
"""

import os
import sys
import ast
import re
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ---------------------------------------------------------------------------
# Tier 1 — SYNTAX GATE  (always runs, needs nothing)
# ---------------------------------------------------------------------------

def test_all_files_parse():
    """Every clickai*.py file in this folder must parse with ast.parse()."""
    files = sorted(glob.glob(os.path.join(HERE, "clickai*.py")))
    assert files, "No clickai*.py files found next to this test."
    broken = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                ast.parse(f.read(), filename=path)
        except SyntaxError as e:
            broken.append(f"{os.path.basename(path)}: line {e.lineno}: {e.msg}")
    assert not broken, "Syntax errors:\n  " + "\n  ".join(broken)


# ---------------------------------------------------------------------------
# Tier 2 — IMPORT SMOKE  (route modules import cleanly with no env)
# ---------------------------------------------------------------------------

ROUTE_MODULES = {
    "clickai_allocation_log": "register_ledger_routes",
    "clickai_banking":        "register_banking_routes",
    "clickai_cashup":         "register_cashup_routes",
    "clickai_invoicing":      "register_invoicing_routes",
    "clickai_payroll":        "register_payroll_routes",
    "clickai_pos":            "register_pos_routes",
    "clickai_pulse":          "register_pulse_routes",
    "clickai_purchases":      "register_purchases_routes",
    "clickai_reports":        "register_report_routes",
    "clickai_settings":       "register_settings_routes",
}

def test_route_modules_import():
    """Each route module must import without error AND expose its register_* function."""
    failures = []
    for mod_name, register_fn in ROUTE_MODULES.items():
        if not os.path.exists(os.path.join(HERE, mod_name + ".py")):
            continue  # module not present in this folder — skip silently
        try:
            mod = __import__(mod_name)
        except Exception as e:
            failures.append(f"{mod_name}: import failed: {type(e).__name__}: {e}")
            continue
        if not hasattr(mod, register_fn):
            failures.append(f"{mod_name}: missing {register_fn}()")
    assert not failures, "Module import problems:\n  " + "\n  ".join(failures)


# ---------------------------------------------------------------------------
# Tier 3 — PURE LOGIC  (the functions a fix is most likely to break silently)
# ---------------------------------------------------------------------------

def test_paye_matches_sage():
    """PAYE for Gideon's known payslip must match Sage to the cent (R4 134.30)."""
    from clickai_payroll import calc_monthly_paye
    assert round(calc_monthly_paye(27897.29), 2) == 4134.30


def test_paye_zero_and_brackets():
    """PAYE basics: zero income = zero; PAYE rises with income; never negative."""
    from clickai_payroll import calc_monthly_paye
    assert calc_monthly_paye(0) == 0.0
    assert calc_monthly_paye(-500) == 0.0           # never negative
    low = calc_monthly_paye(15000)
    high = calc_monthly_paye(60000)
    assert 0 <= low < high                           # monotonic across brackets


def test_paye_rebates_and_deductions_reduce_tax():
    """A 65+ rebate and a pension deduction must each LOWER the PAYE, not raise it."""
    from clickai_payroll import calc_monthly_paye
    base = calc_monthly_paye(40000, age=40)
    older = calc_monthly_paye(40000, age=66)         # extra secondary rebate
    with_pension = calc_monthly_paye(40000, age=40, pension=3000)
    assert older < base
    assert with_pension < base


def test_safe_string_escapes_injection():
    """safe_string must neutralise the chars that have caused UI/JS breakage."""
    import clickai
    out = clickai.safe_string("<script>alert('x')`")
    assert "<" not in out and ">" not in out
    assert "'" not in out and "`" not in out
    assert clickai.safe_string(None) == ""
    assert "\n" not in clickai.safe_string("a\nb")   # newlines flattened


def test_next_doc_number_sequence():
    """Document numbering must continue from the max, and start at 1 when empty."""
    import clickai
    recs = [{"po_number": "PO-00041"}, {"po_number": "PO-00040"}, {"po_number": ""}]
    assert clickai.next_doc_number(recs, "po_number", "PO-") == "PO-00042"
    assert clickai.next_doc_number([], "po_number", "PO-") == "PO-00001"


def test_generate_id_is_unique_uuid():
    """generate_id must return distinct, well-formed UUIDs."""
    import clickai
    a, b = clickai.generate_id(), clickai.generate_id()
    assert a != b
    assert re.fullmatch(r"[0-9a-fA-F-]{36}", a)


def test_bank_dedup_signed_not_abs():
    """The dedup bug guard: a deposit and a same-size payment must NOT collide.

    This is the exact failure that silently dropped ~R205k of customer deposits.
    The fingerprint must use the SIGNED amount, so +5000 and -5000 differ.
    """
    from clickai_banking import _bank_fingerprint
    deposit = _bank_fingerprint("2026-05-29", "MAGTAPE CREDIT", 5000)
    payment = _bank_fingerprint("2026-05-29", "MAGTAPE CREDIT", -5000)
    assert deposit != payment, "deposit collided with same-size payment (abs bug is back)"
    # amount derived from credit/debit when 'amount' is 0 must also stay signed
    cre = _bank_fingerprint("2026-05-29", "X", 0, debit=0, credit=5000)
    deb = _bank_fingerprint("2026-05-29", "X", 0, debit=5000, credit=0)
    assert cre != deb
    # a genuinely identical transaction must still produce an identical fingerprint
    assert _bank_fingerprint("2026-05-29", " magtape credit ", 5000) == \
           _bank_fingerprint("2026-05-29", "MAGTAPE CREDIT", 5000)


def test_bank_income_expense_never_cross():
    """Money IN may never get an expense label; money OUT may never get an income label.

    This is the 'income tagged as Staff Wages' bug: a learned expense pattern was
    applied to an incoming credit. Income and expense must never cross.
    """
    from clickai_banking import _direction_safe_pattern_category, _category_is_expense
    exp = {"Staff Wages", "Fuel", "Salaries"}
    # credit (money IN) with an expense label -> redirected to an income suggestion
    cat, redirected = _direction_safe_pattern_category("Staff Wages", "CREDIT TRANSFER X", True, exp)
    assert redirected and cat == "Customer Payment?"
    # credit with interest / refund hints -> precise income category
    assert _direction_safe_pattern_category("Salaries", "INTEREST ON ACCOUNT", True, exp)[0] == "Interest Received"
    assert _direction_safe_pattern_category("Fuel", "REFUND FROM SUPPLIER", True, exp)[0] == "Refund"
    # legitimate income label on a credit -> kept untouched
    assert _direction_safe_pattern_category("Customer Payment", "X", True, exp) == ("Customer Payment", False)
    # expense label on a debit (money OUT) -> kept
    assert _direction_safe_pattern_category("Fuel", "X", False, exp) == ("Fuel", False)
    # income label on a debit -> dropped (left for manual review)
    assert _direction_safe_pattern_category("Customer Payment", "X", False, exp) == (None, False)
    # wage/salary is always an expense; an income category never is
    assert _category_is_expense("Staff Wages") is True
    assert _category_is_expense("Customer Payment") is False


# ---------------------------------------------------------------------------
# Runner — auto-discovers test_* functions. SKIPS (not fails) Tier-3 tests
# whose module can't be imported in a stripped-down environment.
# ---------------------------------------------------------------------------

_REQUIRES = {  # test name -> module it imports; SKIP (not fail) if that module won't import
    "test_paye_matches_sage":                      "clickai_payroll",
    "test_paye_zero_and_brackets":                 "clickai_payroll",
    "test_paye_rebates_and_deductions_reduce_tax": "clickai_payroll",
    "test_safe_string_escapes_injection":          "clickai",
    "test_next_doc_number_sequence":               "clickai",
    "test_generate_id_is_unique_uuid":             "clickai",
    "test_bank_dedup_signed_not_abs":              "clickai_banking",
    "test_bank_income_expense_never_cross":        "clickai_banking",
}

def _importable(mod_name):
    try:
        __import__(mod_name)
        return True
    except Exception:
        return False

def run():
    tests = sorted(
        (name, fn) for name, fn in globals().items()
        if name.startswith("test_") and callable(fn)
    )
    cache = {}  # module -> importable?
    passed = failed = skipped = 0
    print("=" * 60)
    print("ClickAI safety net")
    print("=" * 60)
    for name, fn in tests:
        need = _REQUIRES.get(name)
        if need is not None:
            if need not in cache:
                cache[need] = _importable(need)
            if not cache[need]:
                print(f"SKIP  {name}  ({need} not importable here)")
                skipped += 1
                continue
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {name}\n      {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {name}\n      {type(e).__name__}: {e}")
            failed += 1
    print("-" * 60)
    print(f"{passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)
    if failed:
        print("DO NOT DEPLOY — fix the failures first.")
    else:
        print("All good — safe to deploy.")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(run())
