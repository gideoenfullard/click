# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - SYSTEM HEALTH MODULE
# ==============================================================================
# Deterministic, read-only accounting health checks. Every check is a plain
# function that returns Findings in ONE fixed format (the contract below).
# Consumers (the /health page, the Zane tool, future fix actions) only ever
# read that format — adding a check never changes a consumer and vice versa.
#
# THE FINDING CONTRACT (fields may be ADDED later, never renamed or removed):
# {
#     "check_id":   "CHK-002",
#     "check_name": "Unbalanced journals",
#     "severity":   "critical" | "warning" | "info",
#     "title":      "...",                # English — shown in the UI
#     "detail":     "...",                # English — shown in the UI
#     "refs":       [{"table": "...", "id": "...", "label": "..."}],
#     "amounts":    {...},                # deterministic numbers only
#     "suggested_action": None            # Phase 4: {"type": ..., "params": ...}
# }
#
# RULES:
# - Checks read ONLY from the ctx snapshot. They never write to the database.
# - Every number comes from a deterministic calculation — never from an AI.
# - A check that finds nothing returns []. A check that crashes is reported
#   as an "info" finding; the runner always completes.
# ==============================================================================

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import quote

logger = logging.getLogger(__name__)

TOLERANCE = 0.02          # cents tolerance, same as create_journal_entry
MAX_FINDINGS_PER_CHECK = 100
STALE_BANK_DAYS = 30

HEALTH_CHECKS = []        # [(check_id, check_name, fn)]

# Dependencies injected by register_health_routes; module-level so the
# runner can be exported (same pattern as clickai_banking._RECON_COMPUTE)
_DEPS = {}


def register_check(check_id, check_name, fn):
    """Add a check to the registry. Adding a check is the ONLY thing a new
    rule ever requires — no consumer changes."""
    HEALTH_CHECKS.append((check_id, check_name, fn))


def _finding(check_id, check_name, severity, title, detail,
             refs=None, amounts=None, suggested_action=None):
    """Build one Finding in the fixed contract format."""
    return {
        "check_id": check_id,
        "check_name": check_name,
        "severity": severity,
        "title": title,
        "detail": detail,
        "refs": refs or [],
        "amounts": amounts or {},
        "suggested_action": suggested_action,
    }


def _f(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


# ==============================================================================
# CTX SNAPSHOT — one set of reads per run, shared by all checks.
# Supabase sits in Ireland (~150ms per round trip); ten checks fetching their
# own tables would make the page unusable. Checks read ctx, never the DB.
# ==============================================================================

def build_ctx(biz_id):
    db = _DEPS["db"]
    gl = _DEPS["gl"]
    today = _DEPS["today"]

    journals = db.get(
        "journals", {"business_id": biz_id}, limit=100000,
        select="id,date,description,reference,account_code,debit,credit"
    ) or []

    by_ref = defaultdict(list)
    for j in journals:
        ref = str(j.get("reference", "") or "").strip()
        if ref:
            by_ref[ref].append(j)

    coa = db.get(
        "chart_of_accounts", {"business_id": biz_id}, limit=10000,
        select="id,account_code,account_name,account_type,category"
    ) or []
    coa_codes = {str(a.get("account_code", "") or "").strip()
                 for a in coa if a.get("account_code")}
    type_of = {}
    name_of = {}
    for a in coa:
        code = str(a.get("account_code", "") or "").strip()
        if code:
            type_of[code] = str(a.get("account_type", "") or "").strip().lower()
            name_of[code] = str(a.get("account_name", "") or "").strip()

    roles = {}
    for role in ("bank", "debtors", "creditors", "vat_input", "vat_output", "sales"):
        try:
            roles[role] = str(gl(biz_id, role) or "").strip()
        except Exception:
            roles[role] = ""

    # Sub-ledger balances — always calculated from source documents
    try:
        customer_balances = _DEPS["calc_all_customer_balances"](biz_id) or {}
    except Exception as e:
        logger.error(f"[HEALTH] customer balances failed: {e}")
        customer_balances = None
    try:
        supplier_balances = _DEPS["calc_all_supplier_balances"](biz_id) or {}
    except Exception as e:
        logger.error(f"[HEALTH] supplier balances failed: {e}")
        supplier_balances = None

    invoices = db.get(
        "invoices", {"business_id": biz_id}, limit=100000,
        select="id,invoice_number,vat,total,date,customer_name"
    ) or []
    expenses = db.get(
        "expenses", {"business_id": biz_id}, limit=100000,
        select="id,vat_amount,amount,date,description"
    ) or []
    bank_txns = db.get(
        "bank_transactions", {"business_id": biz_id}, limit=100000,
        select="id,date,description,amount,matched"
    ) or []

    return {
        "biz_id": biz_id,
        "today": today(),
        "journals": journals,
        "by_ref": by_ref,
        "coa": coa,
        "coa_codes": coa_codes,
        "type_of": type_of,
        "name_of": name_of,
        "roles": roles,
        "customer_balances": customer_balances,
        "supplier_balances": supplier_balances,
        "invoices": invoices,
        "expenses": expenses,
        "bank_txns": bank_txns,
    }


# ==============================================================================
# CHK-001 — BANK RECONCILIATION
# Thin wrapper around the existing deterministic recon engine in
# clickai_banking (_RECON_COMPUTE). No logic is duplicated here.
# ==============================================================================

def chk_bank_recon(ctx):
    cid, cname = "CHK-001", "Bank reconciliation"
    money = _DEPS["money"]
    try:
        import clickai_banking as _bank
    except Exception:
        return [_finding(cid, cname, "info", "Bank reconciliation check could not run",
                         "The banking module is not loaded.")]
    compute = getattr(_bank, "_RECON_COMPUTE", None)
    if not compute:
        return [_finding(cid, cname, "info", "Bank reconciliation check could not run",
                         "The reconciliation engine is not registered yet — deploy clickai_banking.py.")]
    try:
        R = compute(ctx["biz_id"], None, None)
    except Exception as e:
        return [_finding(cid, cname, "info", "Bank reconciliation check could not run",
                         f"The reconciliation engine raised an error: {e}")]

    diff = _f(R.get("difference"))
    if abs(diff) <= TOLERANCE:
        return []
    unalloc = R.get("unalloc") or []
    gl_only = R.get("gl_only") or []
    dups = R.get("duplicates") or []
    detail = (
        f"Bank statement balance {money(_f(R.get('bank_closing')))} vs GL bank account "
        f"{R.get('bank_code', '')} balance {money(_f(R.get('gl_balance')))} — "
        f"difference {money(diff)}. Breakdown: {len(unalloc)} unallocated statement "
        f"line(s) net {money(_f(R.get('unalloc_net')))}, {len(gl_only)} GL-only posting(s), "
        f"{len(dups)} duplicate reference(s) excess {money(_f(R.get('dup_excess_total')))}, "
        f"opening gap {money(_f(R.get('opening_gap')))}, residual {money(_f(R.get('residual')))}."
    )
    return [_finding(
        cid, cname, "critical",
        f"Bank does not reconcile — difference {money(diff)}",
        detail,
        refs=[{"table": "bank_transactions", "id": str(t.get("id", "")),
               "label": f"{t.get('date', '')} {str(t.get('description', ''))[:40]}"}
              for t in unalloc[:20]],
        amounts={
            "bank_closing": _f(R.get("bank_closing")),
            "gl_balance": _f(R.get("gl_balance")),
            "difference": diff,
            "unallocated_count": len(unalloc),
            "unallocated_net": _f(R.get("unalloc_net")),
            "gl_only_count": len(gl_only),
            "duplicate_count": len(dups),
        },
        suggested_action={"type": "open_page", "params": {"url": "/banking"}},
    )]


# ==============================================================================
# CHK-002 — UNBALANCED JOURNALS
# ==============================================================================

def chk_unbalanced_journals(ctx):
    cid, cname = "CHK-002", "Unbalanced journals"
    money = _DEPS["money"]
    findings = []
    for ref, lines in ctx["by_ref"].items():
        debits = sum(_f(l.get("debit")) for l in lines)
        credits = sum(_f(l.get("credit")) for l in lines)
        gap = debits - credits
        if abs(gap) > TOLERANCE:
            findings.append(_finding(
                cid, cname, "critical",
                f"Journal {ref} does not balance",
                f"Debits {money(debits)} vs credits {money(credits)} — "
                f"{'short on the credit side' if gap > 0 else 'short on the debit side'} "
                f"by {money(abs(gap))}. ({len(lines)} line(s), date {lines[0].get('date', '-')})",
                refs=[{"table": "journals", "id": str(l.get("id", "")),
                       "label": f"{ref} line {l.get('account_code', '')}"} for l in lines[:10]],
                amounts={"debits": round(debits, 2), "credits": round(credits, 2),
                         "difference": round(gap, 2)},
            ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            findings.append(_finding(
                cid, cname, "info",
                "More unbalanced journals exist",
                f"Only the first {MAX_FINDINGS_PER_CHECK} are shown. Fix these and run again."))
            break
    return findings


# ==============================================================================
# CHK-003 / CHK-004 — CONTROL ACCOUNTS vs CALCULATED SUB-LEDGERS
# The R50,000 class: the GL control account must equal the sum of the
# balances calculated from source documents. Compared as at today (v1).
# ==============================================================================

def _gl_balance_for_code(ctx, code, credit_side=False):
    bal = 0.0
    for j in ctx["journals"]:
        if str(j.get("account_code", "") or "").strip() == code:
            bal += (_f(j.get("credit")) - _f(j.get("debit"))) if credit_side \
                else (_f(j.get("debit")) - _f(j.get("credit")))
    return bal


def chk_debtors_control(ctx):
    cid, cname = "CHK-003", "Debtors control vs sub-ledger"
    money = _DEPS["money"]
    if ctx["customer_balances"] is None:
        return [_finding(cid, cname, "info", "Debtors check could not run",
                         "Customer balances could not be calculated.")]
    code = ctx["roles"].get("debtors", "")
    if not code:
        return [_finding(cid, cname, "info", "Debtors check could not run",
                         "No debtors control account could be resolved from the chart of accounts.")]
    gl_bal = _gl_balance_for_code(ctx, code, credit_side=False)
    sub = sum(_f(v) for v in ctx["customer_balances"].values())
    gap = gl_bal - sub
    if abs(gap) <= TOLERANCE:
        return []
    return [_finding(
        cid, cname, "critical",
        f"Debtors control does not match the customer ledger — difference {money(gap)}",
        f"GL control account {code} ({ctx['name_of'].get(code, 'Debtors Control')}) shows "
        f"{money(gl_bal)}, but the sum of all customer balances calculated from invoices, "
        f"receipts and credit notes is {money(sub)}. Difference {money(gap)}. "
        f"Causes are usually journals posted to {code} without a customer document, "
        f"or documents that never reached the GL.",
        refs=[{"table": "chart_of_accounts", "id": code, "label": f"Control account {code}"}],
        amounts={"gl_control": round(gl_bal, 2), "sub_ledger": round(sub, 2),
                 "difference": round(gap, 2),
                 "customers": len(ctx["customer_balances"])},
    )]


def chk_creditors_control(ctx):
    cid, cname = "CHK-004", "Creditors control vs sub-ledger"
    money = _DEPS["money"]
    if ctx["supplier_balances"] is None:
        return [_finding(cid, cname, "info", "Creditors check could not run",
                         "Supplier balances could not be calculated.")]
    code = ctx["roles"].get("creditors", "")
    if not code:
        return [_finding(cid, cname, "info", "Creditors check could not run",
                         "No creditors control account could be resolved from the chart of accounts.")]
    gl_bal = _gl_balance_for_code(ctx, code, credit_side=True)
    sub = sum(_f(v) for v in ctx["supplier_balances"].values())
    gap = gl_bal - sub
    if abs(gap) <= TOLERANCE:
        return []
    return [_finding(
        cid, cname, "critical",
        f"Creditors control does not match the supplier ledger — difference {money(gap)}",
        f"GL control account {code} ({ctx['name_of'].get(code, 'Creditors Control')}) shows "
        f"{money(gl_bal)}, but the sum of all supplier balances calculated from supplier "
        f"invoices and payments is {money(sub)}. Difference {money(gap)}.",
        refs=[{"table": "chart_of_accounts", "id": code, "label": f"Control account {code}"}],
        amounts={"gl_control": round(gl_bal, 2), "sub_ledger": round(sub, 2),
                 "difference": round(gap, 2),
                 "suppliers": len(ctx["supplier_balances"])},
    )]


# ==============================================================================
# CHK-005 — UNKNOWN ACCOUNT CODES
# ==============================================================================

def chk_unknown_codes(ctx):
    cid, cname = "CHK-005", "Unknown account codes"
    money = _DEPS["money"]
    if not ctx["coa_codes"]:
        return [_finding(cid, cname, "info", "Unknown-codes check could not run",
                         "This business has no chart of accounts imported.")]
    grouped = defaultdict(lambda: {"count": 0, "debit": 0.0, "credit": 0.0, "ids": []})
    blank = {"count": 0, "debit": 0.0, "credit": 0.0, "ids": []}
    for j in ctx["journals"]:
        code = str(j.get("account_code", "") or "").strip()
        if not code:
            blank["count"] += 1
            blank["debit"] += _f(j.get("debit"))
            blank["credit"] += _f(j.get("credit"))
            if len(blank["ids"]) < 10:
                blank["ids"].append(str(j.get("id", "")))
        elif code not in ctx["coa_codes"]:
            g = grouped[code]
            g["count"] += 1
            g["debit"] += _f(j.get("debit"))
            g["credit"] += _f(j.get("credit"))
            if len(g["ids"]) < 10:
                g["ids"].append(str(j.get("id", "")))
    findings = []
    if blank["count"]:
        findings.append(_finding(
            cid, cname, "warning",
            f"{blank['count']} journal line(s) have no account code at all",
            f"These lines carry debits {money(blank['debit'])} and credits "
            f"{money(blank['credit'])} but were never mapped to any GL account — "
            f"typically unmapped opening entries from a migration import. They are "
            f"invisible to every report until they are assigned a real account.",
            refs=[{"table": "journals", "id": i, "label": "Journal line with no code"}
                  for i in blank["ids"]],
            amounts={"lines": blank["count"], "debits": round(blank["debit"], 2),
                     "credits": round(blank["credit"], 2),
                     "net": round(blank["debit"] - blank["credit"], 2)},
        ))
    for code, g in sorted(grouped.items()):
        findings.append(_finding(
            cid, cname, "warning",
            f"Account code {code} is not in the chart of accounts",
            f"{g['count']} journal line(s) are posted to {code}, but that code does not "
            f"exist in this business's chart of accounts — debits {money(g['debit'])}, "
            f"credits {money(g['credit'])}. These amounts are invisible to reports that "
            f"read the chart of accounts.",
            refs=[{"table": "journals", "id": i, "label": f"Journal line on {code}"}
                  for i in g["ids"]],
            amounts={"lines": g["count"], "debits": round(g["debit"], 2),
                     "credits": round(g["credit"], 2)},
            suggested_action={"type": "ensure_gl_account", "params": {"account_code": code}},
        ))
    return findings


# ==============================================================================
# CHK-006 — VAT MISSING FROM JOURNAL
# A source document carries VAT, but its journal has no line on the VAT
# control account (or the document was never posted at all).
# ==============================================================================

def _vat_check_docs(ctx, docs, ref_fn, vat_fn, label_fn, vat_code, doc_table, cid, cname):
    money = _DEPS["money"]
    findings = []
    for doc in docs:
        vat = vat_fn(doc)
        if vat <= TOLERANCE:
            continue
        ref = ref_fn(doc)
        if not ref:
            continue
        lines = ctx["by_ref"].get(ref)
        if not lines:
            findings.append(_finding(
                cid, cname, "critical",
                f"{label_fn(doc)} was never posted to the GL",
                f"The document carries VAT of {money(vat)} but no journal with reference "
                f"{ref} exists. The whole document is missing from the ledger.",
                refs=[{"table": doc_table, "id": str(doc.get("id", "")), "label": ref}],
                amounts={"vat": round(vat, 2)},
            ))
        elif vat_code and not any(
                str(l.get("account_code", "") or "").strip() == vat_code for l in lines):
            findings.append(_finding(
                cid, cname, "critical",
                f"{label_fn(doc)} has VAT but no VAT line in the GL",
                f"The document carries VAT of {money(vat)}, but journal {ref} has no line "
                f"on the VAT control account {vat_code}. The VAT sits inside another "
                f"account instead of {vat_code}.",
                refs=[{"table": doc_table, "id": str(doc.get("id", "")), "label": ref}] +
                     [{"table": "journals", "id": str(l.get("id", "")),
                       "label": f"{ref} line {l.get('account_code', '')}"} for l in lines[:6]],
                amounts={"vat": round(vat, 2)},
            ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            findings.append(_finding(
                cid, cname, "info", "More VAT findings exist",
                f"Only the first {MAX_FINDINGS_PER_CHECK} are shown. Fix these and run again."))
            break
    return findings


def chk_vat_missing(ctx):
    cid, cname = "CHK-006", "VAT missing from journal"
    out = []
    out += _vat_check_docs(
        ctx, ctx["invoices"],
        ref_fn=lambda d: str(d.get("invoice_number", "") or "").strip(),
        vat_fn=lambda d: _f(d.get("vat")),
        label_fn=lambda d: f"Invoice {d.get('invoice_number', '')}",
        vat_code=ctx["roles"].get("vat_output", ""),
        doc_table="invoices", cid=cid, cname=cname)
    out += _vat_check_docs(
        ctx, ctx["expenses"],
        ref_fn=lambda d: f"EXP-{str(d.get('id', ''))[:8]}" if d.get("id") else "",
        vat_fn=lambda d: _f(d.get("vat_amount")),
        label_fn=lambda d: f"Expense {str(d.get('description', ''))[:30]}",
        vat_code=ctx["roles"].get("vat_input", ""),
        doc_table="expenses", cid=cid, cname=cname)
    return out


# ==============================================================================
# CHK-007 — DOCUMENT POSTED TO THE WRONG SIDE OF THE LEDGER
# A sales document whose journal touches no income-type account (the
# "sales in 5500 Brushing Expenses" case), or an expense whose journal
# touches no expense/asset-type account. Account types come from the
# business's own imported chart of accounts; lines whose type is unknown
# are skipped — the check never guesses.
# ==============================================================================

def _wrong_side(ctx, docs, ref_fn, label_fn, expected_types, expected_word,
                control_codes, cid, cname):
    findings = []
    for doc in docs:
        ref = ref_fn(doc)
        if not ref:
            continue
        lines = ctx["by_ref"].get(ref)
        if not lines:
            continue  # CHK-006 already reports unposted documents
        known_types = []
        landed = []
        for l in lines:
            code = str(l.get("account_code", "") or "").strip()
            if code in control_codes:
                continue  # control/VAT/bank legs are expected on every journal
            t = ctx["type_of"].get(code, "")
            if t:
                known_types.append(t)
                landed.append((code, t))
        if not known_types:
            continue  # all types unknown — no guessing
        if not any(t in expected_types for t in known_types):
            where = ", ".join(
                f"{c} ({ctx['name_of'].get(c, t)})" for c, t in landed[:4])
            findings.append(_finding(
                cid, cname, "critical",
                f"{label_fn(doc)} touches no {expected_word} account",
                f"Journal {ref} posts to {where}, but none of these is "
                f"a {expected_word}-type account in the chart of accounts. "
                f"The amount is sitting on the wrong side of the ledger.",
                refs=[{"table": "journals", "id": str(l.get("id", "")),
                       "label": f"{ref} line {l.get('account_code', '')}"} for l in lines[:6]],
                amounts={"lines": len(lines)},
            ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            break
    return findings


def chk_wrong_side(ctx):
    cid, cname = "CHK-007", "Posted to wrong account type"
    control_codes = {c for c in ctx["roles"].values() if c}
    out = []
    out += _wrong_side(
        ctx, ctx["invoices"],
        ref_fn=lambda d: str(d.get("invoice_number", "") or "").strip(),
        label_fn=lambda d: f"Invoice {d.get('invoice_number', '')}",
        expected_types=("income", "revenue", "sales"),
        expected_word="income",
        control_codes=control_codes, cid=cid, cname=cname)
    out += _wrong_side(
        ctx, ctx["expenses"],
        ref_fn=lambda d: f"EXP-{str(d.get('id', ''))[:8]}" if d.get("id") else "",
        label_fn=lambda d: f"Expense {str(d.get('description', ''))[:30]}",
        expected_types=("expense", "asset", "cost_of_sales", "cost"),
        expected_word="expense or asset",
        control_codes=control_codes, cid=cid, cname=cname)
    return out


# ==============================================================================
# CHK-008 — DUPLICATE JOURNAL POSTINGS
# A reference whose lines are an exact even multiple of one line-set —
# the signature of the same document posted twice.
# ==============================================================================

def chk_duplicate_journals(ctx):
    cid, cname = "CHK-008", "Duplicate journal postings"
    money = _DEPS["money"]
    findings = []
    for ref, lines in ctx["by_ref"].items():
        if len(lines) < 4:
            continue  # a double posting of a 2-line journal has at least 4 lines
        counts = defaultdict(int)
        for l in lines:
            key = (str(l.get("account_code", "") or "").strip(),
                   round(_f(l.get("debit")), 2), round(_f(l.get("credit")), 2))
            counts[key] += 1
        if all(c >= 2 and c % 2 == 0 for c in counts.values()):
            total_debits = sum(_f(l.get("debit")) for l in lines)
            # Offer a one-click reversal ONLY for the unambiguous "posted exactly
            # twice" case (every unique line appears 2×). Higher even multiples are
            # ambiguous about the intended count and are left for manual review.
            clean_double = len(lines) >= 4 and all(c == 2 for c in counts.values())
            action = ({"type": "reverse_duplicate", "params": {"reference": ref}}
                      if clean_double else None)
            findings.append(_finding(
                cid, cname, "warning",
                f"Journal {ref} appears to be posted twice",
                f"Every line under reference {ref} appears an even number of times — "
                f"{len(lines)} lines where {len(counts)} unique lines are expected. "
                f"Total debits {money(total_debits)}; roughly half of that "
                f"({money(total_debits / 2)}) is likely a duplicate posting. "
                f"Review before removing anything.",
                refs=[{"table": "journals", "id": str(l.get("id", "")),
                       "label": f"{ref} line {l.get('account_code', '')}"} for l in lines[:12]],
                amounts={"lines": len(lines), "unique_lines": len(counts),
                         "total_debits": round(total_debits, 2),
                         "likely_excess": round(total_debits / 2, 2)},
                suggested_action=action,
            ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            break
    return findings


# ==============================================================================
# CHK-009 — OPENING BALANCE SUSPENSE NOT ZERO
# ==============================================================================

def chk_suspense(ctx):
    cid, cname = "CHK-009", "Opening balance suspense"
    money = _DEPS["money"]
    findings = []
    for a in ctx["coa"]:
        name = str(a.get("account_name", "") or "")
        if "suspense" not in name.lower():
            continue
        code = str(a.get("account_code", "") or "").strip()
        if not code:
            continue
        bal = _gl_balance_for_code(ctx, code, credit_side=False)
        if abs(bal) > TOLERANCE:
            findings.append(_finding(
                cid, cname, "warning",
                f"Suspense account {code} is not zero — {money(bal)}",
                f"Account {code} ({name}) carries a balance of {money(bal)}. A suspense "
                f"account should clear to zero once opening balances and migration "
                f"differences are resolved by bookkeeper review.",
                refs=[{"table": "chart_of_accounts", "id": str(a.get("id", "")),
                       "label": f"{code} {name}"}],
                amounts={"balance": round(bal, 2)},
                suggested_action={"type": "open_page",
                                  "params": {"url": "/settings/opening-balances"}},
            ))
    return findings


# ==============================================================================
# CHK-010 — STALE UNALLOCATED BANK LINES
# ==============================================================================

def chk_stale_bank_lines(ctx):
    cid, cname = "CHK-010", "Stale unallocated bank lines"
    money = _DEPS["money"]
    try:
        cutoff = (datetime.strptime(ctx["today"], "%Y-%m-%d")
                  - timedelta(days=STALE_BANK_DAYS)).strftime("%Y-%m-%d")
    except Exception:
        return [_finding(cid, cname, "info", "Stale-bank check could not run",
                         "Today's date could not be parsed.")]
    stale = [t for t in ctx["bank_txns"]
             if not t.get("matched") and str(t.get("date", "") or "") < cutoff
             and str(t.get("date", "") or "")]
    if not stale:
        return []
    net = sum(_f(t.get("amount")) for t in stale)
    return [_finding(
        cid, cname, "info",
        f"{len(stale)} bank line(s) older than {STALE_BANK_DAYS} days are still unallocated",
        f"These statement lines (net {money(net)}) have waited more than "
        f"{STALE_BANK_DAYS} days for allocation. They are the backlog that quietly "
        f"breaks the bank reconciliation — allocate them on the Banking page.",
        refs=[{"table": "bank_transactions", "id": str(t.get("id", "")),
               "label": f"{t.get('date', '')} {str(t.get('description', ''))[:40]}"}
              for t in sorted(stale, key=lambda x: str(x.get("date", "")))[:20]],
        amounts={"count": len(stale), "net": round(net, 2)},
        suggested_action={"type": "open_page", "params": {"url": "/banking"}},
    )]


# ==============================================================================
# REGISTER THE v1 CHECKS
# ==============================================================================

register_check("CHK-001", "Bank reconciliation", chk_bank_recon)
register_check("CHK-002", "Unbalanced journals", chk_unbalanced_journals)
register_check("CHK-003", "Debtors control vs sub-ledger", chk_debtors_control)
register_check("CHK-004", "Creditors control vs sub-ledger", chk_creditors_control)
register_check("CHK-005", "Unknown account codes", chk_unknown_codes)
register_check("CHK-006", "VAT missing from journal", chk_vat_missing)
register_check("CHK-007", "Posted to wrong account type", chk_wrong_side)
register_check("CHK-008", "Duplicate journal postings", chk_duplicate_journals)
register_check("CHK-009", "Opening balance suspense", chk_suspense)
register_check("CHK-010", "Stale unallocated bank lines", chk_stale_bank_lines)


# ==============================================================================
# THE RUNNER — builds one ctx, runs every registered check, never dies.
# ==============================================================================

def run_health_checks(biz_id, only=None):
    """Run all (or selected) checks for one business. Returns
    {"findings": [...], "summary": {...}} in the fixed contract."""
    now = _DEPS["now"]
    findings = []
    ctx = build_ctx(biz_id)
    checks_run = 0
    for check_id, check_name, fn in HEALTH_CHECKS:
        if only and check_id not in only:
            continue
        checks_run += 1
        try:
            findings.extend(fn(ctx) or [])
        except Exception as e:
            logger.error(f"[HEALTH] {check_id} crashed: {e}")
            findings.append(_finding(
                check_id, check_name, "info",
                f"{check_name} could not run",
                f"The check raised an error and was skipped: {e}"))
    order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 3), f["check_id"]))
    summary = {
        "checks_run": checks_run,
        "critical": sum(1 for f in findings if f["severity"] == "critical"),
        "warning": sum(1 for f in findings if f["severity"] == "warning"),
        "info": sum(1 for f in findings if f["severity"] == "info"),
        "journals_scanned": len(ctx["journals"]),
        "generated_at": now(),
    }
    return {"findings": findings, "summary": summary}


# Exported for the Zane tool (Phase 3) — same pattern as _RECON_COMPUTE
_HEALTH_RUN = run_health_checks


# ==============================================================================
# ROUTES — the /health page is a pure consumer: it runs the checks and
# renders findings. Zero logic of its own.
# ==============================================================================

def register_health_routes(app, db, login_required, Auth, render_page,
                           money, safe_string, now, today, gl,
                           calc_all_customer_balances, calc_all_supplier_balances):
    """Register the System Health routes with the Flask app."""

    _DEPS.update({
        "db": db, "gl": gl, "money": money, "now": now, "today": today,
        "calc_all_customer_balances": calc_all_customer_balances,
        "calc_all_supplier_balances": calc_all_supplier_balances,
    })

    SEV_STYLE = {
        "critical": ("CRITICAL", "#ef4444", "rgba(239,68,68,0.08)"),
        "warning": ("WARNING", "#f59e0b", "rgba(245,158,11,0.08)"),
        "info": ("INFO", "#6366f1", "rgba(99,102,241,0.08)"),
    }

    @app.route("/system-health")
    @login_required
    def system_health_page():
        """System Health — run all checks and show the findings."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            from flask import redirect, flash
            flash("Please select a business first", "error")
            return redirect("/")

        result = run_health_checks(biz_id)
        findings = result["findings"]
        summary = result["summary"]

        finding_cards = ""
        for f in findings:
            label, color, bg = SEV_STYLE.get(f["severity"], SEV_STYLE["info"])
            refs_html = ""
            if f["refs"]:
                ref_items = ", ".join(safe_string(r.get("label", "")) for r in f["refs"][:8])
                more = f" and {len(f['refs']) - 8} more" if len(f["refs"]) > 8 else ""
                refs_html = (f'<div style="margin-top:8px;font-size:11px;color:var(--text-muted);">'
                             f'Records: {ref_items}{more}</div>')
            action_html = ""
            sa = f.get("suggested_action") or {}
            if sa.get("type") == "open_page":
                action_html = (f'<div style="margin-top:10px;"><a href="{sa["params"]["url"]}" '
                               f'class="btn btn-secondary" style="padding:6px 14px;font-size:12px;">'
                               f'Open page</a></div>')
            elif sa.get("type") == "reverse_duplicate":
                _ref_q = quote(str(sa.get("params", {}).get("reference", "")))
                action_html = (f'<div style="margin-top:10px;">'
                               f'<a href="/system-health/reverse-duplicate?ref={_ref_q}" '
                               f'class="btn btn-secondary" style="padding:6px 14px;font-size:12px;">'
                               f'Review &amp; reverse duplicate</a></div>')
            finding_cards += f'''
            <div class="card" style="border-left:4px solid {color};background:{bg};margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap;">
                    <div style="font-weight:600;">{safe_string(f["title"])}</div>
                    <div style="display:flex;gap:8px;align-items:center;">
                        <span style="font-size:10px;color:var(--text-muted);">{f["check_id"]}</span>
                        <span style="background:{color};color:white;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600;">{label}</span>
                    </div>
                </div>
                <p style="margin:8px 0 0;font-size:13px;color:var(--text);">{safe_string(f["detail"])}</p>
                {refs_html}
                {action_html}
            </div>
            '''

        if not findings:
            finding_cards = ('<div class="card" style="border-left:4px solid #10b981;">'
                             '<div style="font-weight:600;">All checks passed</div>'
                             '<p style="margin:8px 0 0;font-size:13px;color:var(--text-muted);">'
                             f'{summary["checks_run"]} checks ran across '
                             f'{summary["journals_scanned"]} journal lines and found nothing '
                             'to report.</p></div>')

        content = f'''
        <div class="stats-grid">
            <div class="stat-card" style="{'background:rgba(239,68,68,0.1);' if summary["critical"] else ''}">
                <div class="stat-value" style="color:{'#ef4444' if summary["critical"] else 'var(--text)'};">{summary["critical"]}</div>
                <div class="stat-label">Critical</div>
            </div>
            <div class="stat-card" style="{'background:rgba(245,158,11,0.1);' if summary["warning"] else ''}">
                <div class="stat-value" style="color:{'#f59e0b' if summary["warning"] else 'var(--text)'};">{summary["warning"]}</div>
                <div class="stat-label">Warnings</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary["info"]}</div>
                <div class="stat-label">Info</div>
            </div>
            <div class="stat-card green">
                <div class="stat-value">{summary["checks_run"]}</div>
                <div class="stat-label">Checks Run</div>
            </div>
        </div>

        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                <h3 class="card-title" style="margin:0;">System Health</h3>
                <a href="/system-health" class="btn btn-primary">Run Again</a>
            </div>
            <p style="color:var(--text-muted);font-size:12px;margin:8px 0 0;">
                Deterministic, read-only accounting checks — {summary["journals_scanned"]} journal
                lines scanned at {summary["generated_at"]}. Nothing on this page changes your data.
            </p>
        </div>

        {finding_cards}
        '''

        return render_page("System Health", content, user, "reports")

    # --------------------------------------------------------------------------
    # PHASE 4 — guarded fix action: reverse a duplicate journal (CHK-008).
    # Two steps, never automatic: the finding links to a confirmation page that
    # shows the exact reversal, and only an explicit POST posts it. Every step
    # re-reads the journal fresh and re-verifies it is still a clean duplicate,
    # so a stale link or an already-fixed entry safely does nothing.
    # --------------------------------------------------------------------------

    def _load_clean_duplicate(biz_id, ref):
        """Fresh re-read of one reference's journal lines. Returns a reversal plan
        ONLY if it is still an unambiguous 'posted exactly twice' duplicate (every
        unique line appears exactly 2x). Otherwise returns None."""
        if not ref:
            return None
        lines = db.get(
            "journals", {"business_id": biz_id, "reference": ref}, limit=10000,
            select="id,date,description,reference,account_code,debit,credit") or []
        if len(lines) < 4:
            return None
        counts = defaultdict(int)
        for l in lines:
            key = (str(l.get("account_code", "") or "").strip(),
                   round(_f(l.get("debit")), 2), round(_f(l.get("credit")), 2))
            counts[key] += 1
        if len(counts) < 2 or not all(c == 2 for c in counts.values()):
            return None
        reversal = [{"account_code": acc, "debit": cr, "credit": dr}
                    for (acc, dr, cr) in counts.keys()]
        amount = round(sum(e["debit"] for e in reversal), 2)
        return {"lines": lines, "reversal": reversal, "amount": amount,
                "date": lines[0].get("date", "")}

    @app.route("/system-health/reverse-duplicate")
    @login_required
    def system_health_reverse_duplicate_confirm():
        from flask import request, redirect, flash
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            flash("Please select a business first", "error")
            return redirect("/")
        user = Auth.get_current_user()
        ref = (request.args.get("ref", "") or "").strip()
        plan = _load_clean_duplicate(biz_id, ref)
        if not plan:
            flash("That journal is no longer a clean duplicate — nothing to reverse.", "error")
            return redirect("/system-health")

        rows = "".join(
            f'<tr><td style="padding:6px 10px;">{safe_string(e["account_code"])}</td>'
            f'<td style="padding:6px 10px;text-align:right;">{money(e["debit"]) if e["debit"] else ""}</td>'
            f'<td style="padding:6px 10px;text-align:right;">{money(e["credit"]) if e["credit"] else ""}</td></tr>'
            for e in plan["reversal"])

        content = f'''
        <div class="card">
            <h3 class="card-title" style="margin:0 0 4px;">Reverse duplicate journal</h3>
            <p style="color:var(--text-muted);font-size:13px;margin:0 0 14px;">
                Reference <strong>{safe_string(ref)}</strong> was posted twice. Confirming posts a
                single balancing reversal dated today ({safe_string(today())}), under the same
                reference, so the net posting returns to its correct single value. The original
                lines are kept for the audit trail — nothing is deleted.
            </p>
            <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:6px;">
                <thead><tr style="border-bottom:1px solid var(--border);">
                    <th style="padding:6px 10px;text-align:left;">Account</th>
                    <th style="padding:6px 10px;text-align:right;">Debit</th>
                    <th style="padding:6px 10px;text-align:right;">Credit</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="font-size:12px;color:var(--text-muted);margin:0 0 16px;">
                Reversal total: {money(plan["amount"])}.
            </p>
            <form method="POST" action="/system-health/reverse-duplicate" style="display:flex;gap:10px;align-items:center;">
                <input type="hidden" name="ref" value="{safe_string(ref)}">
                <button type="submit" class="btn btn-primary">Confirm reversal</button>
                <a href="/system-health" class="btn btn-secondary">Cancel</a>
            </form>
        </div>
        '''
        return render_page("Reverse Duplicate", content, user, "reports")

    @app.route("/system-health/reverse-duplicate", methods=["POST"])
    @login_required
    def system_health_reverse_duplicate_post():
        from flask import request, redirect, flash
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            flash("Please select a business first", "error")
            return redirect("/")

        try:
            import clickai as _main
            role = _main.get_user_role()
        except Exception:
            _main, role = None, ""
        if role not in ("owner", "admin", "manager", "bookkeeper", "accountant"):
            flash("You don't have permission to post corrections.", "error")
            return redirect("/system-health")

        ref = (request.form.get("ref", "") or "").strip()
        plan = _load_clean_duplicate(biz_id, ref)
        if not plan:
            flash("That journal is no longer a clean duplicate — nothing was changed.", "error")
            return redirect("/system-health")

        try:
            _main.create_journal_entry(
                biz_id, today(),
                f"System Health: reversal of duplicate posting ({ref})",
                ref, plan["reversal"])
        except Exception as e:
            logger.error(f"[HEALTH] Duplicate reversal failed for {ref}: {e}")
            flash(f"Could not post the reversal: {e}", "error")
            return redirect("/system-health")

        try:
            from clickai_allocation_log import log_allocation
        except Exception:
            log_allocation = None
        try:
            if log_allocation:
                _uid, _uname = _main.get_acting_user()
                log_allocation(
                    business_id=biz_id, allocation_type="reversal",
                    source_table="journals", source_id=ref,
                    description=f"System Health reversal of duplicate journal {ref} - {money(plan['amount'])}",
                    amount=plan["amount"], gl_entries=plan["reversal"],
                    reference=ref, transaction_date=today(),
                    created_by=_uid, created_by_name=_uname)
        except Exception as _le:
            logger.warning(f"[HEALTH] Reversal allocation_log failed: {_le}")

        logger.info(f"[HEALTH] Reversed duplicate journal {ref} for {biz_id} — {plan['amount']}")
        flash(f"Reversed duplicate posting {ref} ({money(plan['amount'])}). "
              f"The original lines are kept for audit.", "success")
        return redirect("/system-health")

    logger.info("[HEALTH] System Health routes registered")
