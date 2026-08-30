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

import json
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
        select="id,date,description,reference,account_code,debit,credit,segment,created_by,created_at"
    ) or []

    by_ref = defaultdict(list)
    for j in journals:
        ref = str(j.get("reference", "") or "").strip()
        if ref:
            by_ref[ref].append(j)

    coa = db.get(
        "chart_of_accounts", {"business_id": biz_id}, limit=10000,
        select="id,account_code,account_name,account_type,category,is_active,debit,credit,opening_balance"
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
    for role in ("bank", "debtors", "creditors", "vat_input", "vat_output", "sales", "stock", "general"):
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
        select="id,invoice_number,vat,total,date,customer_name,items"
    ) or []
    expenses = db.get(
        "expenses", {"business_id": biz_id}, limit=100000,
        select="id,vat_amount,amount,date,description"
    ) or []
    bank_txns = db.get(
        "bank_transactions", {"business_id": biz_id}, limit=100000,
        select="id,date,description,amount,matched"
    ) or []

    sales = db.get(
        "sales", {"business_id": biz_id}, limit=100000,
        select="id,sale_number,date,total,payment_method,customer_name"
    ) or []

    # Refunded status lives ONLY in allocation_log — the sales table has no
    # status column (same rule as clickai_pos.py). Checks read ctx, never the DB.
    refunded_sale_ids = set()
    for al in (db.get("allocation_log", {"business_id": biz_id}, limit=100000,
                      select="source_id,source_table,extra") or []):
        if al.get("source_table") != "sales" or not al.get("source_id"):
            continue
        extra = al.get("extra", {})
        if isinstance(extra, str):
            try:
                extra = json.loads(extra) if extra else {}
            except Exception:
                extra = {}
        if isinstance(extra, dict) and extra.get("action") == "pos_refund":
            refunded_sale_ids.add(al.get("source_id"))

    suppliers = db.get(
        "suppliers", {"business_id": biz_id}, limit=100000,
        select="id,name,segment,direct_cost"
    ) or []
    grvs = db.get(
        "goods_received", {"business_id": biz_id}, limit=100000,
        select="id,grv_number,supplier_id,supplier_name,date"
    ) or []

    return {
        "biz_id": biz_id,
        "today": today(),
        "suppliers": suppliers,
        "grvs": grvs,
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
        "sales": sales,
        "refunded_sale_ids": refunded_sale_ids,
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
            suggested_action={"type": "create_gl_accounts"},
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
# CHK-011 — POS SALE NOT POSTED TO THE GL
# The sale saved but its journal did not — a dropped Supabase connection
# loses the journal silently while the till still prints the slip. The money
# is in the drawer and on the Z-Read, but nowhere in the ledger.
# ==============================================================================

def chk_pos_unposted(ctx):
    cid, cname = "CHK-011", "POS sales not posted to the GL"
    money = _DEPS["money"]
    findings = []
    for sale in ctx["sales"]:
        if sale.get("id") in ctx["refunded_sale_ids"]:
            continue
        total = _f(sale.get("total"))
        if total <= TOLERANCE:
            continue
        ref = str(sale.get("sale_number", "") or "").strip()
        if not ref:
            continue
        if ctx["by_ref"].get(ref):
            continue
        findings.append(_finding(
            cid, cname, "critical",
            f"POS sale {ref} was never posted to the GL",
            f"The sale of {money(total)} on {sale.get('date', '')} "
            f"({sale.get('payment_method', '')}) is in the sales table but no journal "
            f"with reference {ref} exists. The money was taken at the till and counted "
            f"on the Z-Read, but the ledger does not show it.",
            refs=[{"table": "sales", "id": str(sale.get("id", "")), "label": ref}],
            amounts={"total": round(total, 2)},
        ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            findings.append(_finding(
                cid, cname, "info", "More unposted POS sales exist",
                f"Only the first {MAX_FINDINGS_PER_CHECK} are shown. Fix these and run again."))
            break
    return findings


# ==============================================================================
# REGISTER THE v1 CHECKS
# ==============================================================================
# CHK-012 — TRIAL BALANCE vs INCOME STATEMENT
# The reports must read one ledger the same way. Profit computed the TB way
# (chart balances + every journal line) must equal the Income Statement's
# "All Time" net profit to the cent.
# ==============================================================================

def _pl_sections():
    from clickai_reports import _gl_section, _coa_base_balance
    return _gl_section, _coa_base_balance


def chk_tb_vs_pnl(ctx):
    cid, cname = "CHK-012", "Trial balance vs Income Statement"
    money = _DEPS["money"]
    findings = []
    try:
        _gl_section, _coa_base_balance = _pl_sections()
        from clickai_reports import build_pnl_summary
    except Exception as e:
        return [_finding(cid, cname, "info", "Check could not run",
                         f"Report helpers unavailable: {e}")]
    acc = {str(a.get("account_code", "") or "").strip(): a for a in ctx["coa"]}
    tb_net = 0.0
    for code, a in acc.items():
        sec = _gl_section(code, a)
        if sec in ("income", "cost_of_sales", "expense"):
            d, c = _coa_base_balance(a)
            tb_net += (c - d)
    for j in ctx["journals"]:
        code = str(j.get("account_code", "") or "").strip()
        sec = _gl_section(code, acc.get(code))
        if sec in ("income", "cost_of_sales", "expense"):
            tb_net += _f(j.get("credit")) - _f(j.get("debit"))
    pnl = build_pnl_summary(_DEPS["db"], ctx["biz_id"], "2000-01-01", "2099-12-31")
    gap = round(tb_net - pnl["net_profit"], 2)
    if abs(gap) > TOLERANCE:
        findings.append(_finding(
            cid, cname, "critical",
            f"Trial balance profit differs from the Income Statement by {money(abs(gap))}",
            f"Trial balance net profit {money(tb_net)} vs Income Statement (All Time) "
            f"{money(pnl['net_profit'])}. The two reports must read the same ledger with "
            f"the same account classification — a difference means one of them is "
            f"reading a different source or rule.",
            amounts={"trial_balance": round(tb_net, 2), "income_statement": round(pnl["net_profit"], 2),
                     "difference": gap},
            suggested_action={"type": "open_page", "params": {"url": "/reports/pnl?period=all"}},
        ))
    return findings


# ==============================================================================
# CHK-013 — BALANCE SHEET BALANCES
# Assets = Liabilities + Equity + profit to date, from the same ledger.
# Accounts with a balance but no type on the chart are reported separately:
# they are the usual reason a balance sheet does not balance.
# ==============================================================================

def chk_balance_sheet(ctx):
    cid, cname = "CHK-013", "Balance sheet balances"
    money = _DEPS["money"]
    findings = []
    try:
        _gl_section, _coa_base_balance = _pl_sections()
    except Exception as e:
        return [_finding(cid, cname, "info", "Check could not run", f"Report helpers unavailable: {e}")]
    acc = {str(a.get("account_code", "") or "").strip(): a for a in ctx["coa"]}
    bal = defaultdict(float)
    for code, a in acc.items():
        d, c = _coa_base_balance(a)
        if d or c:
            bal[code] += d - c
    for j in ctx["journals"]:
        code = str(j.get("account_code", "") or "").strip()
        if code:
            bal[code] += _f(j.get("debit")) - _f(j.get("credit"))
    assets = liabs = equity = profit = 0.0
    unclassified = []
    for code, v in bal.items():
        v = round(v, 2)
        if v == 0:
            continue
        sec = _gl_section(code, acc.get(code))
        if sec == "asset":
            assets += v
        elif sec == "liability":
            liabs += -v
        elif sec == "equity":
            equity += -v
        elif sec in ("income", "cost_of_sales", "expense"):
            profit += -v
        else:
            unclassified.append((code, v))
    if unclassified:
        findings.append(_finding(
            cid, cname, "warning",
            f"{len(unclassified)} account(s) with a balance have no type on the chart of accounts",
            "These accounts cannot be placed on the balance sheet or income statement: "
            + ", ".join(f"{c} ({money(v)})" for c, v in sorted(unclassified)[:10])
            + (" ..." if len(unclassified) > 10 else "")
            + ". Set account_type (asset/liability/equity/income/expense) on each.",
            refs=[{"table": "chart_of_accounts", "id": str((acc.get(c) or {}).get("id", "")),
                   "label": c} for c, _ in unclassified[:10]],
            amounts={"unclassified_total": round(sum(v for _, v in unclassified), 2)},
            suggested_action={"type": "open_page", "params": {"url": "/settings/chart-of-accounts"}},
        ))
    gap = round(assets - (liabs + equity + profit + sum(v for _, v in unclassified)), 2)
    if abs(gap) > TOLERANCE:
        findings.append(_finding(
            cid, cname, "critical",
            f"Balance sheet is out by {money(abs(gap))}",
            f"Assets {money(assets)} vs liabilities {money(liabs)} + equity {money(equity)} "
            f"+ profit to date {money(profit)}. A ledger that balances per journal cannot "
            f"produce this unless an account is misclassified or a journal is unbalanced "
            f"(see CHK-002).",
            amounts={"assets": round(assets, 2), "liabilities": round(liabs, 2),
                     "equity": round(equity, 2), "profit_to_date": round(profit, 2), "difference": gap},
            suggested_action={"type": "open_page", "params": {"url": "/reports/balance-sheet"}},
        ))
    return findings


# ==============================================================================
# CHK-014 — SUNDRY EXPENSES USED AS A CATCH-ALL
# The fallback account must stay near zero. Anything that lands there is an
# allocation nobody finished.
# ==============================================================================

SUNDRY_MONTH_LIMIT = 2000.0
SUNDRY_LINE_LIMIT = 5


def chk_sundry_catch_all(ctx):
    cid, cname = "CHK-014", "Sundry expenses used as catch-all"
    money = _DEPS["money"]
    findings = []
    code = ""
    for a in ctx["coa"]:
        if "sundry" in str(a.get("account_name", "") or "").lower():
            code = str(a.get("account_code", "") or "").strip()
            break
    if not code:
        code = ctx["roles"].get("general") or ""
    if not code:
        return findings
    month = ctx["today"][:7]
    lines = [j for j in ctx["journals"]
             if str(j.get("account_code", "") or "").strip() == code
             and str(j.get("date", "") or "")[:7] == month]
    total = sum(_f(l.get("debit")) - _f(l.get("credit")) for l in lines)
    if total > SUNDRY_MONTH_LIMIT or len(lines) > SUNDRY_LINE_LIMIT:
        findings.append(_finding(
            cid, cname, "warning",
            f"{len(lines)} posting(s) totalling {money(total)} on {code} this month",
            f"Account {code} ({ctx['name_of'].get(code, 'Sundry Expenses')}) is the fallback "
            f"when nobody chose a specific account. Every line here is an allocation still "
            f"to be finished: " + "; ".join(
                f"{str(l.get('description', '') or '')[:35]} {money(_f(l.get('debit')) - _f(l.get('credit')))}"
                for l in sorted(lines, key=lambda x: -abs(_f(x.get('debit')) - _f(x.get('credit'))))[:6]),
            refs=[{"table": "journals", "id": str(l.get("id", "")),
                   "label": str(l.get("reference", "") or "")} for l in lines[:10]],
            amounts={"month_total": round(total, 2), "lines": len(lines)},
            suggested_action={"type": "open_page", "params": {"url": f"/reports/gl?account={quote(code)}"}},
        ))
    return findings


# ==============================================================================
# CHK-015 — VAT CLAIMED ON EXEMPT OR NON-SUPPLY COSTS
# Input VAT debited in a journal whose other leg is wages, interest, SARS,
# loans, drawings or a members' loan. SA VAT Act: no input VAT on these.
# ==============================================================================

VAT_EXEMPT_WORDS = ("salar", "wage", "payroll", "paye", "uif", "sdl", "sars", "interest",
                    "loan", "drawing", "members", "member's", "dividend", "tax payable",
                    "income tax", "provisional tax")


def chk_vat_on_exempt(ctx):
    cid, cname = "CHK-015", "VAT claimed on exempt costs"
    money = _DEPS["money"]
    findings = []
    vat_codes = {c for c in (ctx["roles"].get("vat_input"), ctx["roles"].get("vat_output")) if c}
    bank = ctx["roles"].get("bank") or ""
    if not vat_codes:
        return findings
    for ref, lines in ctx["by_ref"].items():
        vat_dr = sum(_f(l.get("debit")) for l in lines
                     if str(l.get("account_code", "") or "").strip() in vat_codes)
        if vat_dr <= TOLERANCE:
            continue
        legs = []
        for l in lines:
            code = str(l.get("account_code", "") or "").strip()
            if code in vat_codes or code == bank or _f(l.get("debit")) <= 0:
                continue
            nm = (ctx["name_of"].get(code, "") + " " + str(l.get("description", "") or "")).lower()
            if any(w in nm for w in VAT_EXEMPT_WORDS):
                legs.append((code, ctx["name_of"].get(code, ""), _f(l.get("debit"))))
        if not legs:
            continue
        findings.append(_finding(
            cid, cname, "critical",
            f"Input VAT {money(vat_dr)} claimed on exempt cost — {ref}",
            f"Journal {ref} ({lines[0].get('date', '-')}) claims input VAT while its cost leg is "
            + ", ".join(f"{c} {n} {money(a)}" for c, n, a in legs[:3])
            + ". Wages, interest, SARS payments, loans and drawings carry no input VAT; the "
            f"VAT line should be part of the cost.",
            refs=[{"table": "journals", "id": str(l.get("id", "")), "label": ref} for l in lines[:10]],
            amounts={"vat_claimed": round(vat_dr, 2)},
        ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            findings.append(_finding(cid, cname, "info", "More findings exist",
                                     f"Only the first {MAX_FINDINGS_PER_CHECK} are shown."))
            break
    return findings


# ==============================================================================
# CHK-016 — INVOICE WITH STOCK LINES BUT NO COST OF SALES
# An invoice whose lines are linked to stock items must have a COS-<number>
# journal (DR cost of sales / CR stock), like a POS sale.
# ==============================================================================

INVOICE_COS_DAYS = 90


def _invoice_lines(inv):
    items = inv.get("items")
    if isinstance(items, str):
        try:
            items = json.loads(items) if items else []
        except Exception:
            items = []
    return items if isinstance(items, list) else []


def chk_invoice_without_cos(ctx):
    cid, cname = "CHK-016", "Invoice without cost of sales"
    money = _DEPS["money"]
    findings = []
    cutoff = (datetime.strptime(ctx["today"], "%Y-%m-%d") - timedelta(days=INVOICE_COS_DAYS)).strftime("%Y-%m-%d")
    for inv in ctx["invoices"]:
        d = str(inv.get("date", "") or "")[:10]
        if not d or d < cutoff:
            continue
        num = str(inv.get("invoice_number", "") or "")
        if not num or ("COS-" + num) in ctx["by_ref"]:
            continue
        linked = [li for li in _invoice_lines(inv) if isinstance(li, dict) and li.get("stock_id")]
        if not linked:
            continue
        findings.append(_finding(
            cid, cname, "warning",
            f"Invoice {num} has {len(linked)} stock line(s) but no cost of sales journal",
            f"Dated {d} for {str(inv.get('customer_name', '') or '')[:30]}, total {money(_f(inv.get('total')))}. "
            f"Stock-linked lines must post DR cost of sales / CR stock at cost price, "
            f"otherwise gross margin is overstated and stock is not reduced.",
            refs=[{"table": "invoices", "id": str(inv.get("id", "")), "label": num}],
            amounts={"invoice_total": round(_f(inv.get("total")), 2), "stock_lines": len(linked)},
            suggested_action={"type": "open_page", "params": {"url": f"/invoice/{inv.get('id', '')}"}},
        ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            break
    return findings


# ==============================================================================
# CHK-017 — FREE-TEXT INVOICE LINES (no stock item)
# Lines typed without picking a stock item post no cost of sales and never
# reduce stock. Informational: the trend should fall over time.
# ==============================================================================

FREE_TEXT_DAYS = 30


def chk_free_text_lines(ctx):
    cid, cname = "CHK-017", "Invoice lines not linked to stock"
    findings = []
    cutoff = (datetime.strptime(ctx["today"], "%Y-%m-%d") - timedelta(days=FREE_TEXT_DAYS)).strftime("%Y-%m-%d")
    total = linked = 0
    for inv in ctx["invoices"]:
        d = str(inv.get("date", "") or "")[:10]
        if not d or d < cutoff:
            continue
        for li in _invoice_lines(inv):
            if not isinstance(li, dict) or not str(li.get("description", "") or "").strip():
                continue
            total += 1
            if li.get("stock_id"):
                linked += 1
    if total and (total - linked) > 0:
        pct = (total - linked) / total * 100
        findings.append(_finding(
            cid, cname, "info",
            f"{pct:.0f}% of invoice lines in the last {FREE_TEXT_DAYS} days are not linked to a stock item",
            f"{total - linked} of {total} lines were typed as free text. These post no cost of "
            f"sales and do not reduce stock, so gross margin and stock value drift until a "
            f"stock count. Pick the stock item on the invoice line where the goods are stock.",
            amounts={"lines": total, "unlinked": total - linked, "pct_unlinked": round(pct, 1)},
        ))
    return findings


# ==============================================================================
# CHK-018 / CHK-019 — GOODS RECEIVED vs SUPPLIER SETTINGS
# ==============================================================================

def _grv_journals(ctx):
    """[(grv, supplier, lines)] for GRVs that have a GL journal."""
    sup = {str(s.get("id", "") or ""): s for s in ctx["suppliers"]}
    out = []
    for g in ctx["grvs"]:
        ref = "GRV " + str(g.get("grv_number", "") or "")
        lines = ctx["by_ref"].get(ref)
        if not lines:
            continue
        out.append((g, sup.get(str(g.get("supplier_id", "") or "")), lines))
    return out


def chk_grv_segment(ctx):
    cid, cname = "CHK-018", "Goods received stamped to the wrong segment"
    findings = []
    for g, s, lines in _grv_journals(ctx):
        seg = str((s or {}).get("segment", "") or "").strip()
        if not seg:
            continue
        wrong = [l for l in lines if str(l.get("segment", "") or "").strip() != seg]
        if not wrong:
            continue
        ref = "GRV " + str(g.get("grv_number", "") or "")
        findings.append(_finding(
            cid, cname, "warning",
            f"{ref} is stamped {wrong[0].get('segment') or 'unassigned'}, supplier is {seg}",
            f"Goods received from {str(g.get('supplier_name', '') or '')[:30]} carry the segment "
            f"'{wrong[0].get('segment') or ''}' on {len(wrong)} journal line(s); the supplier "
            f"belongs to {seg}. The segment P&L moves the cost to the wrong division.",
            refs=[{"table": "journals", "id": str(l.get("id", "")), "label": ref} for l in wrong[:10]],
        ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            break
    return findings


def chk_grv_direct_cost(ctx):
    cid, cname = "CHK-019", "Direct-cost supplier received into stock"
    money = _DEPS["money"]
    findings = []
    stock = ctx["roles"].get("stock") or ""
    for g, s, lines in _grv_journals(ctx):
        if not s or not s.get("direct_cost"):
            continue
        to_stock = sum(_f(l.get("debit")) for l in lines
                       if str(l.get("account_code", "") or "").strip() == stock)
        if to_stock <= TOLERANCE:
            continue
        ref = "GRV " + str(g.get("grv_number", "") or "")
        findings.append(_finding(
            cid, cname, "warning",
            f"{ref} moved {money(to_stock)} into stock for a direct-cost supplier",
            f"{str(s.get('name', '') or '')[:30]} is marked 'Direct cost (not stock)': its goods "
            f"are expensed on purchase and never sold as stock items, so this journal parks the "
            f"cost in stock where it will never come out.",
            refs=[{"table": "journals", "id": str(l.get("id", "")), "label": ref} for l in lines[:10]],
            amounts={"moved_to_stock": round(to_stock, 2)},
        ))
        if len(findings) >= MAX_FINDINGS_PER_CHECK:
            break
    return findings


# ==============================================================================
# CHK-020 — ESTIMATE JOURNALS OUTSTANDING
# EST-* journals are explicit estimates (e.g. cost of sales pending a stock
# count). They must be replaced by real figures, not forgotten.
# ==============================================================================

def chk_estimates(ctx):
    cid, cname = "CHK-020", "Estimate journals outstanding"
    money = _DEPS["money"]
    ests = {ref: lines for ref, lines in ctx["by_ref"].items() if ref.startswith("EST-")}
    if not ests:
        return []
    total = sum(_f(l.get("debit")) for lines in ests.values() for l in lines)
    first = min(str(l.get("date", "") or "") for lines in ests.values() for l in lines)
    return [_finding(
        cid, cname, "info",
        f"{len(ests)} estimate journal(s) totalling {money(total)} still in the ledger",
        f"References {', '.join(sorted(ests)[:6])}{' ...' if len(ests) > 6 else ''} (oldest {first}). "
        f"These are marked estimates and must be reversed and replaced with actual figures "
        f"(e.g. after the stock count) before year-end.",
        refs=[{"table": "journals", "id": str(lines[0].get("id", "")), "label": ref}
              for ref, lines in sorted(ests.items())[:10]],
        amounts={"estimated_total": round(total, 2)},
    )]


# ==============================================================================
# CHK-021 — JOURNALS WITHOUT AN OWNER
# Postings made by a logged-in user must carry created_by; otherwise Pulse
# cannot show who did what. System jobs (schedulers, imports) legitimately
# post without one — this only flags document-type references.
# ==============================================================================

OWNER_DAYS = 7
SYSTEM_PREFIXES = ("COS-", "REVCOS-", "EST-", "REVEDIT-", "REFCOS-", "OPENING-", "OB", "CORR-", "JNL-")


def chk_journals_without_owner(ctx):
    cid, cname = "CHK-021", "Journals without an owner"
    cutoff = (datetime.strptime(ctx["today"], "%Y-%m-%d") - timedelta(days=OWNER_DAYS)).strftime("%Y-%m-%d")
    by_prefix = defaultdict(int)
    refs = []
    seen = set()
    for j in ctx["journals"]:
        ca = str(j.get("created_at", "") or "")[:10]
        if not ca or ca < cutoff or j.get("created_by"):
            continue
        ref = str(j.get("reference", "") or "")
        if not ref or ref.startswith(SYSTEM_PREFIXES) or ref in seen:
            continue
        seen.add(ref)
        by_prefix[ref.split("-")[0][:8]] += 1
        if len(refs) < 10:
            refs.append({"table": "journals", "id": str(j.get("id", "")), "label": ref})
    if not seen:
        return []
    return [_finding(
        cid, cname, "info",
        f"{len(seen)} journal(s) in the last {OWNER_DAYS} days have no owner",
        "Postings without created_by cannot be shown per person on Pulse. By reference type: "
        + ", ".join(f"{p} ({n})" for p, n in sorted(by_prefix.items(), key=lambda x: -x[1])[:8])
        + ". If these were captured by a user, the capture path is not passing the session "
        "through create_journal_entry.",
        refs=refs,
        amounts={"journals": len(seen)},
    )]


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
register_check("CHK-011", "POS sales not posted to the GL", chk_pos_unposted)
register_check("CHK-012", "Trial balance vs Income Statement", chk_tb_vs_pnl)
register_check("CHK-013", "Balance sheet balances", chk_balance_sheet)
register_check("CHK-014", "Sundry expenses used as catch-all", chk_sundry_catch_all)
register_check("CHK-015", "VAT claimed on exempt costs", chk_vat_on_exempt)
register_check("CHK-016", "Invoice without cost of sales", chk_invoice_without_cos)
register_check("CHK-017", "Invoice lines not linked to stock", chk_free_text_lines)
register_check("CHK-018", "Goods received stamped to the wrong segment", chk_grv_segment)
register_check("CHK-019", "Direct-cost supplier received into stock", chk_grv_direct_cost)
register_check("CHK-020", "Estimate journals outstanding", chk_estimates)
register_check("CHK-021", "Journals without an owner", chk_journals_without_owner)


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
            elif sa.get("type") == "create_gl_accounts":
                action_html = (f'<div style="margin-top:10px;">'
                               f'<a href="/system-health/create-gl-accounts" '
                               f'class="btn btn-secondary" style="padding:6px 14px;font-size:12px;">'
                               f'Review &amp; create missing accounts</a></div>')
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

        return render_page("System Health", content, user, "system-health")

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
        return render_page("Reverse Duplicate", content, user, "system-health")

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

    # --------------------------------------------------------------------------
    # PHASE 4 — guarded fix action: create missing GL accounts (CHK-005).
    # Codes used in journals but absent from the chart of accounts are invisible
    # to every report. This creates a COA row for each, with type inferred from the
    # code's leading digit, so the amounts become visible. It never moves money and
    # never renames an existing account — it only adds the missing rows. Two steps,
    # never automatic: a confirmation page lists exactly what will be created.
    # --------------------------------------------------------------------------

    @app.route("/system-health/create-gl-accounts")
    @login_required
    def system_health_create_gl_accounts_confirm():
        from flask import redirect, flash
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            flash("Please select a business first", "error")
            return redirect("/")
        user = Auth.get_current_user()
        try:
            import clickai as _main
            preview = _main.backfill_missing_coa_codes(biz_id, dry_run=True)
        except Exception as e:
            logger.error(f"[HEALTH] COA preview failed: {e}")
            flash("Could not read the missing accounts.", "error")
            return redirect("/system-health")
        orphans = preview.get("orphans", [])
        if not orphans:
            flash("There are no missing GL accounts to create.", "success")
            return redirect("/system-health")

        rows = "".join(
            f'<tr>'
            f'<td style="padding:6px 10px;">{safe_string(o["code"])}</td>'
            f'<td style="padding:6px 10px;">{safe_string(o["account_type"])}</td>'
            f'<td style="padding:6px 10px;">{safe_string(o["name"])}</td>'
            f'<td style="padding:6px 10px;text-align:right;">{o["lines"]}</td>'
            f'<td style="padding:6px 10px;text-align:right;">{money(o["debit"])}</td>'
            f'<td style="padding:6px 10px;text-align:right;">{money(o["credit"])}</td>'
            f'</tr>'
            for o in orphans)

        content = f'''
        <div class="card">
            <h3 class="card-title" style="margin:0 0 4px;">Create missing GL accounts</h3>
            <p style="color:var(--text-muted);font-size:13px;margin:0 0 14px;">
                {len(orphans)} account code(s) are used in journals but do not exist in the
                chart of accounts, so their amounts are invisible to reports. Confirming
                creates one account for each, with the type inferred from the code number.
                Nothing is moved and no existing account is renamed — review and rename the
                new accounts afterwards if needed.
            </p>
            <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px;">
                <thead><tr style="border-bottom:1px solid var(--border);">
                    <th style="padding:6px 10px;text-align:left;">Code</th>
                    <th style="padding:6px 10px;text-align:left;">Type</th>
                    <th style="padding:6px 10px;text-align:left;">Name</th>
                    <th style="padding:6px 10px;text-align:right;">Lines</th>
                    <th style="padding:6px 10px;text-align:right;">Debits</th>
                    <th style="padding:6px 10px;text-align:right;">Credits</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <form method="POST" action="/system-health/create-gl-accounts" style="display:flex;gap:10px;align-items:center;">
                <button type="submit" class="btn btn-primary">Create {len(orphans)} account(s)</button>
                <a href="/system-health" class="btn btn-secondary">Cancel</a>
            </form>
        </div>
        '''
        return render_page("Create GL Accounts", content, user, "system-health")

    @app.route("/system-health/create-gl-accounts", methods=["POST"])
    @login_required
    def system_health_create_gl_accounts_post():
        from flask import redirect, flash
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
            flash("You don't have permission to change the chart of accounts.", "error")
            return redirect("/system-health")

        try:
            result = _main.backfill_missing_coa_codes(biz_id)
        except Exception as e:
            logger.error(f"[HEALTH] COA backfill failed: {e}")
            flash(f"Could not create the accounts: {e}", "error")
            return redirect("/system-health")

        created = result.get("created", 0)
        try:
            from clickai_allocation_log import log_allocation
        except Exception:
            log_allocation = None
        try:
            if log_allocation and created:
                _uid, _uname = _main.get_acting_user()
                codes = ", ".join(o["code"] for o in result.get("orphans", []))
                log_allocation(
                    business_id=biz_id, allocation_type="coa_repair",
                    source_table="chart_of_accounts", source_id="health",
                    description=f"System Health created {created} missing GL account(s): {codes}"[:480],
                    amount=0, gl_entries=[],
                    transaction_date=today(),
                    created_by=_uid, created_by_name=_uname)
        except Exception as _le:
            logger.warning(f"[HEALTH] COA repair allocation_log failed: {_le}")

        logger.info(f"[HEALTH] Created {created} missing GL account(s) for {biz_id}")
        if created:
            flash(f"Created {created} missing GL account(s). Review their names and types "
                  f"on the chart of accounts.", "success")
        else:
            flash("No missing GL accounts to create.", "success")
        return redirect("/system-health")

    logger.info("[HEALTH] System Health routes registered")
