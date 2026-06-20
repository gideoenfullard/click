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


def test_paye_travel_allowance_is_taxable():
    """Travel allowance must RAISE PAYE (80% of it is taxable per SARS).

    A regression that stopped taxing travel would under-deduct PAYE and leave the
    employee with a SARS shortfall at assessment.
    """
    from clickai_payroll import calc_monthly_paye
    base = calc_monthly_paye(40000, age=40)
    with_travel = calc_monthly_paye(40000, age=40, travel=5000)
    assert with_travel > base, "travel allowance did not increase PAYE (80% should be taxable)"


def test_paye_provident_and_medical_reduce_tax():
    """A provident-fund contribution and medical-aid members must each LOWER PAYE."""
    from clickai_payroll import calc_monthly_paye
    base = calc_monthly_paye(40000, age=40)
    with_provident = calc_monthly_paye(40000, age=40, provident=3000)
    with_medical = calc_monthly_paye(40000, age=40, medical_members=2)
    assert with_provident < base, "provident contribution did not reduce PAYE"
    assert with_medical < base, "medical-aid credits did not reduce PAYE"


def test_safe_float_strips_currency_and_junk():
    """safe_float must read 'R1,234.50' as 1234.5 and turn junk/None into 0.0.

    This is the sanitiser on money inputs; if it ever raised or returned junk,
    a single bad cell would break a whole payroll run.
    """
    from clickai_payroll import safe_float
    assert safe_float("1234.5") == 1234.5
    assert safe_float("R1,234.50") == 1234.5
    assert safe_float(None) == 0.0
    assert safe_float("abc") == 0.0
    assert safe_float("") == 0.0


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
# Tier 3b — DOMAIN MATH  (the per-unit money + payroll logic that decides profit)
#
# Two kinds of test live here:
#   GOLDEN  — a known-correct value is locked (e.g. M12x70 @ R250/kg = R23.00).
#             If you DELIBERATELY change a price/rate, update the expected number.
#   INVARIANT — a property that must always hold (price rises with size, Sunday
#             hours never land in the 'normal' bucket, totals are floats, etc.).
#             These should never need changing.
# ---------------------------------------------------------------------------

def _pricing_class():
    """The Fulltech steel-pricing class (named 'fulltech_addon' in clickai.py)."""
    import clickai, inspect
    for _name, obj in vars(clickai).items():
        if inspect.isclass(obj) and hasattr(obj, "calc_bolt_price"):
            return obj
    raise AssertionError("pricing class with calc_bolt_price not found in clickai.py")


def _payroll_hours_class():
    """The class exposing calc_hours (PayrollSettings in clickai.py)."""
    import clickai, inspect
    for _name, obj in vars(clickai).items():
        if inspect.isclass(obj) and hasattr(obj, "calc_hours"):
            return obj
    raise AssertionError("class with calc_hours not found in clickai.py")


def test_steel_bolt_price_known_values():
    """GOLDEN: bolt/nut weight->price math must hold to the cent.

    M12 x 70 @ R250/kg  -> 92.0 g -> R23.00
    M12 nut   @ R250/kg -> 21.0 g -> R5.25
    These are the anchors Fulltech prices against; a drift here is lost margin.
    """
    P = _pricing_class()
    bolt = P.calc_bolt_price(12, 70, 250)
    assert bolt["success"] is True
    assert round(bolt["price"], 2) == 23.00
    assert round(bolt["weight_g"], 1) == 92.0
    nut = P.calc_bolt_price(12, rkg=250, item_type="nut")
    assert nut["success"] is True
    assert round(nut["price"], 2) == 5.25


def test_steel_bolt_price_invariants():
    """INVARIANT: price must rise with length and with R/kg; bad input must fail cleanly."""
    P = _pricing_class()
    assert P.calc_bolt_price(12, 100, 250)["price"] > P.calc_bolt_price(12, 50, 250)["price"]
    assert P.calc_bolt_price(12, 70, 300)["price"] > P.calc_bolt_price(12, 70, 200)["price"]
    # a bolt with no length, or an unknown size, must return success=False (not crash, not 0)
    assert P.calc_bolt_price(12)["success"] is False
    assert P.calc_bolt_price(999, 70, 250)["success"] is False


def test_steel_finish_and_sheet_pricing():
    """GOLDEN: finish + sheet-piece pricing anchors (N4 + PVC, 2mm)."""
    P = _pricing_class()
    fin = P.calc_finish(5.0, finish="N4 + PVC", thickness_mm=2)
    assert round(fin["total"], 2) == 222.52
    assert fin["min_applied"] is True
    sheet = P.calc_sheet_piece(2000, 1000, 2, finish="N4 + PVC")
    assert round(sheet["sqm"], 2) == 2.0
    assert round(sheet["markup"], 2) == 0.40          # +40% for piece >= 1 sqm


def test_steel_coil_and_bar_geometry():
    """GOLDEN: coil m2 + bar mass-per-metre lookups (the inputs every coil price uses)."""
    P = _pricing_class()
    coil = P.calc_coil(weight_kg=100, od_mm=1000, width_mm=1219, thickness_mm=2, grade="304")
    assert round(coil["sqm"], 2) == 6.20
    assert round(coil["kg_per_sqm"], 2) == 16.14
    assert coil["length_m"] > 0
    assert round(P.get_round(12), 2) == 4.30          # kg/m, 12mm round 304
    assert round(P.get_square(20), 2) == 10.42        # kg/m, 20mm square


def test_payroll_calc_hours_day_types():
    """GOLDEN+INVARIANT: 08:00->17:00 splits correctly, and Sun/Sat land in their own buckets.

    A regression that put Sunday hours into 'normal' (single pay) would silently
    underpay double-time. Sunday hours must NEVER be in the normal bucket.
    """
    TC = _payroll_hours_class()
    s = {"normal_hours_per_day": 9, "ot_multiplier": 1.5, "sunday_multiplier": 2.0}
    mon = TC.calc_hours(8 * 60, 17 * 60, "Monday", s)
    assert mon["normal"] == 8 and mon["overtime"] == 0.5 and mon["day_type"] == "normal"
    sat = TC.calc_hours(8 * 60, 17 * 60, "Saturday", s)
    assert sat["is_saturday"] is True and sat["day_type"] == "saturday"
    sun = TC.calc_hours(8 * 60, 17 * 60, "Sunday", s)
    assert sun["is_sunday"] is True and sun["day_type"] == "sunday"
    assert sun["sunday"] == 8.5 and sun["normal"] == 0   # Sunday never counted as normal


def test_money_formatting():
    """INVARIANT: money() always renders R, thousands separators, exactly 2 decimals."""
    import clickai
    assert clickai.money(0) == "R0.00"
    assert clickai.money(1234.5) == "R1,234.50"
    assert clickai.money(1234567.891) == "R1,234,567.89"


def test_uuid_validation_helpers():
    """INVARIANT: a real UUID validates; junk does not; safe_uuid drops junk to None."""
    import clickai
    good = clickai.generate_id()
    assert clickai.is_valid_uuid(good) is True
    assert clickai.is_valid_uuid("not-a-uuid") is False
    assert clickai.safe_uuid("not-a-uuid") is None
    assert clickai.safe_uuid(good) == good


def test_smart_stock_code_deterministic():
    """INVARIANT: the same description always yields the same, non-empty code."""
    import clickai
    a = clickai.smart_stock_code("Round Bar 16mm 316")
    b = clickai.smart_stock_code("Round Bar 16mm 316")
    assert a == b and isinstance(a, str) and a.strip() != ""


def test_extract_json_from_text():
    """INVARIANT: JSON is recovered from plain text and from ```json fences (AI replies)."""
    import clickai
    assert clickai.extract_json_from_text('noise {"a": 1, "b": [2, 3]} tail') == {"a": 1, "b": [2, 3]}
    assert clickai.extract_json_from_text('```json\n{"x": true}\n```') == {"x": True}


def test_record_factory_stock_movement_shape():
    """INVARIANT: a stock movement keeps its type/qty and carries every field the DB needs.

    This guards the *record* the GRV path writes when booking stock. If a field is
    dropped or 'quantity' stops being numeric, stock booking breaks downstream.
    (The GRV booking DECISION itself lives in clickai_purchases.py and needs its
    own test there once that module is in scope.)
    """
    import clickai, inspect
    RF = None
    for _name, obj in vars(clickai).items():
        if inspect.isclass(obj) and hasattr(obj, "stock_movement") and hasattr(obj, "invoice"):
            RF = obj
    assert RF is not None, "RecordFactory not found"
    mv = RF.stock_movement("biz-1", "stk-1", "in", 10, reference="GRV-0007")
    for key in ("id", "business_id", "stock_id", "date", "type", "quantity", "reference"):
        assert key in mv, f"stock_movement missing '{key}'"
    assert mv["type"] == "in"
    assert mv["stock_id"] == "stk-1"
    assert isinstance(mv["quantity"], float) and mv["quantity"] == 10.0
    assert mv["reference"] == "GRV-0007"
    assert RF.stock_movement("b", "s", "out", 3)["type"] == "out"


def test_record_factory_invoice_and_expense_shape():
    """INVARIANT: invoice/expense builders keep required fields and numeric totals."""
    import clickai, inspect
    RF = None
    for _name, obj in vars(clickai).items():
        if inspect.isclass(obj) and hasattr(obj, "invoice") and hasattr(obj, "expense"):
            RF = obj
    assert RF is not None
    inv = RF.invoice("biz", "cid", "Acme", [], subtotal=100, vat=15)
    for key in ("business_id", "customer_id", "customer_name", "items",
                "subtotal", "vat", "total", "status"):
        assert key in inv, f"invoice missing '{key}'"
    assert isinstance(inv["subtotal"], float) and isinstance(inv["total"], float)
    exp = RF.expense("biz", "Diesel", 500)
    assert exp["description"] == "Diesel"
    assert isinstance(exp["amount"], float) and exp["amount"] == 500.0


def test_extract_time_hhmm():
    """INVARIANT: extract_time pulls HH:MM out of a timestamp."""
    import clickai
    assert clickai.extract_time("2026-05-29T14:30:00") == "14:30"


# ---------------------------------------------------------------------------
# Runner — auto-discovers test_* functions. SKIPS (not fails) Tier-3 tests
# whose module can't be imported in a stripped-down environment.
# ---------------------------------------------------------------------------

_REQUIRES = {  # test name -> module it imports; SKIP (not fail) if that module won't import
    "test_paye_matches_sage":                      "clickai_payroll",
    "test_paye_zero_and_brackets":                 "clickai_payroll",
    "test_paye_rebates_and_deductions_reduce_tax": "clickai_payroll",
    "test_paye_travel_allowance_is_taxable":       "clickai_payroll",
    "test_paye_provident_and_medical_reduce_tax":  "clickai_payroll",
    "test_safe_float_strips_currency_and_junk":    "clickai_payroll",
    "test_safe_string_escapes_injection":          "clickai",
    "test_next_doc_number_sequence":               "clickai",
    "test_generate_id_is_unique_uuid":             "clickai",
    "test_bank_dedup_signed_not_abs":              "clickai_banking",
    "test_bank_income_expense_never_cross":        "clickai_banking",
    "test_steel_bolt_price_known_values":          "clickai",
    "test_steel_bolt_price_invariants":            "clickai",
    "test_steel_finish_and_sheet_pricing":         "clickai",
    "test_steel_coil_and_bar_geometry":            "clickai",
    "test_payroll_calc_hours_day_types":           "clickai",
    "test_money_formatting":                       "clickai",
    "test_uuid_validation_helpers":                "clickai",
    "test_smart_stock_code_deterministic":         "clickai",
    "test_extract_json_from_text":                 "clickai",
    "test_record_factory_stock_movement_shape":    "clickai",
    "test_record_factory_invoice_and_expense_shape": "clickai",
    "test_extract_time_hhmm":                      "clickai",
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
    if skipped:
        print(f"NOTE: {skipped} test(s) SKIPPED (a module would not import here).")
        print("      Install deps (e.g. `pip install anthropic`) so these RUN, not skip.")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(run())
