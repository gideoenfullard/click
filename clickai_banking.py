# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - BANKING MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Banking page, Bank import, Categorize, Zane suggest, Delete all
# ==============================================================================

import os
import re
import io
import csv
import json
import logging
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def _bank_fingerprint(date, description, amount=0.0, debit=0.0, credit=0.0, balance=None):
    """Dedup fingerprint for a bank transaction: (date, description, SIGNED amount, balance).

    The amount is SIGNED (never abs) so a deposit (+) can NEVER collide with a
    payment (-) of the same magnitude — the bug that silently dropped real income
    and corrupted the bank balance. If 'amount' is 0 it is derived from
    credit - debit.

    The running BALANCE is included because it is unique per statement line: two
    genuinely different transactions on the same day with the same description and
    amount (e.g. two R4.90 card-purchase fees) have different running balances, so
    they no longer collide and get one silently dropped. A re-import of the same
    statement has identical balances, so it is still deduped. When no balance is
    available it normalises to 0 on both sides (falls back to old behaviour).

    Used by BOTH the existing-transaction load and the per-row dedup check, so the
    two can never drift apart again.
    """
    d = str(date or "")[:10]
    desc = (description or "").strip().upper()[:80]
    amt = round(float(amount or 0), 2)
    if not amt:
        amt = round(round(float(credit or 0), 2) - round(float(debit or 0), 2), 2)
    bal = round(float(balance or 0), 2)
    return (d, desc, amt, bal)


# Income-side categories the bank importer can assign. A money-IN (credit) line may
# only ever carry one of these (or a neutral one); a money-OUT (debit) line may never.
_BANK_INCOME_CATEGORIES = frozenset({
    "CUSTOMER PAYMENT", "CUSTOMER PAYMENT?", "CUSTOMER PAYMENT (MULTI-INVOICE)",
    "POS DEPOSIT", "CARD SETTLEMENT", "SALES", "OTHER INCOME", "INTEREST RECEIVED",
})


def _category_is_expense(category, extra_expense_cats=()):
    """True if a category represents an expense. Wage/salary/payroll labels always
    count as expenses (so 'Staff Wages' is caught even if it isn't in the configured
    expense list); income categories never do."""
    cat_u = (category or "").upper().strip()
    if not cat_u or cat_u in _BANK_INCOME_CATEGORIES:
        return False
    if any(tok in cat_u for tok in ("WAGE", "SALAR", "PAYROLL")):
        return True
    return cat_u in {str(c).upper().strip() for c in extra_expense_cats}


def _direction_safe_pattern_category(category, desc_upper, is_credit, extra_expense_cats=()):
    """Stop income and expense crossing on a learned-pattern match.

    Returns (category_to_use, was_redirected). category_to_use is None when the match
    must be dropped (left for manual review).
      - credit (money IN) may never carry an expense label -> redirect to a sensible
        income suggestion: Interest Received / Refund / else 'Customer Payment?'.
      - debit (money OUT) may never carry an income label -> drop (manual review).
    Neutral categories (Refund, Transfer, Loan, Supplier Payment, etc.) pass through.
    """
    cat_u = (category or "").upper().strip()
    if is_credit:
        if _category_is_expense(category, extra_expense_cats):
            d = desc_upper or ""
            if "INTEREST" in d:
                return "Interest Received", True
            if "REFUND" in d or "REVERSAL" in d:
                return "Refund", True
            return "Customer Payment?", True
        return category, False
    if cat_u in _BANK_INCOME_CATEGORIES:
        return None, False
    return category, False


# Module-level holders for the reconciliation engine, registered when the banking
# routes load. This lets other modules (e.g. Zane in clickai.py) ask for the
# reconciliation difference + plain-language explanation using the exact same
# deterministic engine, without duplicating any logic.
_RECON_COMPUTE = None
_RECON_EXPLAIN = None


def register_banking_routes(app, db, login_required, Auth, render_page,
                            generate_id, money, safe_string, now, today,
                            gl, create_journal_entry, log_allocation,
                            has_reactor_hud, jarvis_hud_header, jarvis_techline,
                            extract_json_from_text,
                            BankLearning, IndustryKnowledge, InvoiceMatch, RecordFactory,
                            JARVIS_HUD_CSS, THEME_REACTOR_SKINS,
                            BANKING_KNOWLEDGE_LOADED,
                            get_relevant_banking_knowledge, format_banking_knowledge,
                            ensure_gl_account=None):
    """Register all Banking routes with the Flask app."""

    @app.route("/banking")
    @login_required
    def banking_page():
        """Bank Reconciliation - Smart Dashboard"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get ALL transactions, not just unmatched
        all_transactions = db.get("bank_transactions", {"business_id": biz_id}) if biz_id else []
        # Two-pass stable sort to match the EXACT bank statement order:
        #   1. Sort by created_at ASC (preserves the order AI read them from the statement)
        #   2. Sort by date ASC (stable sort keeps insertion order within same day)
        # Result: oldest day at top, newest day at bottom — exactly like the bank statement.
        all_transactions.sort(key=lambda x: str(x.get("created_at", "")))
        all_transactions.sort(key=lambda x: str(x.get("date", ""))[:10])
        
        # NOTE: InvoiceMatch.match_all_transactions removed from page load — was causing 6+ second delays
        # Matching now happens at IMPORT time (see api_banking_import) and on-demand via Zane
        
        # ═══════════════════════════════════════════════════════════════
        # AUTO-ALLOCATE DISABLED (Deon's request 2026-05-06):
        # Auto-Matched tab keeps showing legacy transactions imported BEFORE
        # this change (they have auto_matched=True). New imports never set
        # auto_matched=True, so they all flow into "Suggested" or "Needs You".
        # ═══════════════════════════════════════════════════════════════
        auto_matched = [t for t in all_transactions if (t.get("auto_matched") or t.get("invoice_matched")) and not t.get("matched")]
        # Suggested = has a category suggestion AND not yet matched AND not in legacy auto_matched bucket
        suggested = [t for t in all_transactions if t.get("suggested_category") and not t.get("matched") and not t.get("auto_matched") and not t.get("invoice_matched")]
        needs_attention = [t for t in all_transactions if not t.get("matched") and not t.get("suggested_category") and not t.get("auto_matched") and not t.get("invoice_matched")]
        already_done = [t for t in all_transactions if t.get("matched")]
        
        # ── Group transactions into import batches (keyed by created_at minute) so a single
        #    import can be deleted without touching other imports. Allocated txns are counted
        #    separately and are never deleted by the per-import delete (see /api/banking/delete-import).
        _import_batches = {}
        for _t in all_transactions:
            _bkey = str(_t.get("created_at", "") or "")[:16]  # minute precision = one import
            if not _bkey:
                continue
            _bb = _import_batches.setdefault(_bkey, {"count": 0, "allocated": 0, "dates": []})
            _bb["count"] += 1
            if _t.get("matched"):
                _bb["allocated"] += 1
            _bd = _t.get("date")
            if _bd:
                _bb["dates"].append(str(_bd))
        import_options_html = ""
        for _bkey in sorted(_import_batches.keys(), reverse=True):
            _bb = _import_batches[_bkey]
            _unalloc = _bb["count"] - _bb["allocated"]
            _disp = _bkey.replace("T", " ")
            _drange = ""
            if _bb["dates"]:
                _dmin, _dmax = min(_bb["dates"]), max(_bb["dates"])
                _drange = f" | {_dmin}" + (f" to {_dmax}" if _dmax != _dmin else "")
            _akept = f", {_bb['allocated']} allocated kept" if _bb["allocated"] else ""
            import_options_html += f'<option value="{_bkey}">{_disp} UTC: {_bb["count"]} txns ({_unalloc} to delete{_akept}){_drange}</option>'
        
        # Get expense categories
        expense_categories = IndustryKnowledge.get_expense_categories(biz_id) if biz_id else ["Sundry Expenses"]
        category_options = "".join([f'<option value="{c}">{c}</option>' for c in expense_categories])
        
        # Add common categories
        extra_cats = ["Customer Payment", "Supplier Payment", "POS Deposit", "Card Settlement", "Owner Drawings", "Owner Capital Introduced", "Loan", "Loan Repayment", "Refund", "Transfer", "Ignore"]
        for cat in extra_cats:
            if cat not in expense_categories:
                category_options += f'<option value="{cat}">{cat}</option>'
        
        # JSON list for split modal JS
        all_cats_for_split = list(expense_categories)
        for cat in extra_cats:
            if cat not in all_cats_for_split:
                all_cats_for_split.append(cat)
        json_cat_list = json.dumps(all_cats_for_split)
        
        # Customer + Supplier lists for entity picker (when allocating payments)
        _all_customers = db.get("customers", {"business_id": biz_id}) if biz_id else []
        _all_suppliers = db.get("suppliers", {"business_id": biz_id}) if biz_id else []
        _cust_list = [{"id": c.get("id",""), "name": c.get("name","")} for c in (_all_customers or []) if c.get("name")]
        _supp_list = [{"id": s.get("id",""), "name": s.get("name","")} for s in (_all_suppliers or []) if s.get("name")]
        _cust_list.sort(key=lambda x: x["name"].upper())
        _supp_list.sort(key=lambda x: x["name"].upper())
        _entity_json_customers = json.dumps(_cust_list).replace("'", "&#39;")
        _entity_json_suppliers = json.dumps(_supp_list).replace("'", "&#39;")
        
        # Stats
        total_count = len(all_transactions)
        auto_count = len(auto_matched)
        suggested_count = len(suggested)
        needs_count = len(needs_attention)
        done_count = len(already_done)
        
        # Calculate totals for unmatched
        unmatched = [t for t in all_transactions if not t.get("matched")]
        total_debit = sum(float(t.get("debit", 0)) for t in unmatched)
        total_credit = sum(float(t.get("credit", 0)) for t in unmatched)
        
        # Build rows for each section
        def build_row(txn, show_approve=False, show_suggestion=True):
            txn_id = txn.get("id", "")
            debit = float(txn.get("debit", 0))
            credit = float(txn.get("credit", 0))
            desc = safe_string(txn.get("description", "-"))
            suggested_cat = txn.get("suggested_category", "")
            confidence = txn.get("suggestion_confidence", 0)
            match_ref = txn.get("match_reference", "")
            match_type = txn.get("match_type", "")
            
            # Suggestion display
            suggestion_html = ""
            if show_suggestion and suggested_cat:
                conf_pct = int(confidence * 100)
                if match_type == "invoice":
                    suggestion_html = f'<div style="font-size:11px;color:#22d3ee;margin-top:3px;">Invoice match: {suggested_cat}</div>'
                    if match_ref:
                        suggestion_html += f'<div style="font-size:10px;color:var(--text-muted);">{match_ref}</div>'
                elif match_type in ("customer_payment", "possible_payment", "customer_payment_combo"):
                    # Show customer name prominently
                    _cust_display = match_ref.split(" - ", 1)[1].strip() if " - " in match_ref else match_ref.replace("Maybe ", "").replace("?", "").strip()
                    _inv_display = match_ref.split(" - ", 1)[0].strip() if " - " in match_ref else ""
                    # For combo matches, prefix the customer name with a multi-invoice indicator
                    _cust_prefix = "👤📑" if match_type == "customer_payment_combo" else "👤"
                    suggestion_html = f'<div style="font-size:12px;color:#22d3ee;margin-top:3px;font-weight:600;">{_cust_prefix} {_cust_display}</div>'
                    if _inv_display:
                        suggestion_html += f'<div style="font-size:11px;color:var(--green);">{suggested_cat} — {_inv_display} ({conf_pct}%)</div>'
                    else:
                        suggestion_html += f'<div style="font-size:11px;color:var(--yellow);">{suggested_cat}? ({conf_pct}%)</div>'
                elif match_type == "payroll":
                    # Show employee name prominently
                    _emp_name = match_ref.replace("Salary — ", "").replace("Maybe ", "").replace("?", "").strip()
                    if "(" in _emp_name:
                        _emp_name = _emp_name.split("(")[0].strip()
                    suggestion_html = f'<div style="font-size:12px;color:#22d3ee;margin-top:3px;font-weight:600;">👷 {_emp_name}</div>'
                    suggestion_html += f'<div style="font-size:11px;color:var(--green);">{suggested_cat} ({conf_pct}%)</div>'
                elif match_type == "expense_match" and match_ref:
                    # Show supplier from scanned expense
                    _sup_name = match_ref.replace("Scanned: ", "").strip()
                    suggestion_html = f'<div style="font-size:12px;color:#22d3ee;margin-top:3px;font-weight:600;">🏢 {_sup_name}</div>'
                    suggestion_html += f'<div style="font-size:11px;color:var(--green);">{suggested_cat} ({conf_pct}%)</div>'
                elif confidence >= 0.85:
                    suggestion_html = f'<div style="font-size:11px;color:var(--green);margin-top:3px;">{suggested_cat} ({conf_pct}%)</div>'
                elif confidence >= 0.6:
                    suggestion_html = f'<div style="font-size:11px;color:var(--yellow);margin-top:3px;">{suggested_cat}? ({conf_pct}%)</div>'
                else:
                    suggestion_html = f'<div style="font-size:11px;color:var(--text-muted);margin-top:3px;">Maybe {suggested_cat}?</div>'
                
                if match_ref and match_type != "invoice":
                    suggestion_html += f'<div style="font-size:10px;color:var(--text-muted);">{match_ref}</div>'
            # Action buttons
            txn_date = txn.get("date", "")
            safe_desc = desc.replace("'", "\\'").replace('"', '&quot;')
            if show_approve and suggested_cat and confidence >= 0.6:
                action_html = f'''
                <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center;">
                    <button onclick="approveMatch('{txn_id}', '{suggested_cat}')" class="btn" style="padding:5px 10px;font-size:11px;background:var(--green);border:none;color:white;border-radius:6px;">GOOD: {suggested_cat}</button>
                    <button onclick="askZaneBank('{txn_id}', '{safe_desc}', {debit}, {credit}, '{txn_date}')" class="btn" style="padding:5px 10px;font-size:11px;background:var(--primary);border:none;color:white;border-radius:6px;">Ask Zane</button>
                    <button onclick="openSplitModal('{txn_id}', '{safe_desc}', {debit}, {credit}, '{txn_date}')" class="btn" style="padding:5px 10px;font-size:11px;background:rgba(245,158,11,0.2);border:1px solid #f59e0b;color:#f59e0b;border-radius:6px;" title="Split into multiple categories">Split</button>
                    <select class="form-input" style="width:120px;padding:4px;font-size:11px;" onchange="categorizeTransaction('{txn_id}', this.value, '{safe_desc}')">
                        <option value="">Manual...</option>
                        {category_options}
                    </select>
                </div>
                '''
            else:
                action_html = f'''
                <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center;">
                    <button onclick="askZaneBank('{txn_id}', '{safe_desc}', {debit}, {credit}, '{txn_date}')" class="btn" style="padding:7px 14px;font-size:12px;background:var(--primary);border:none;color:white;border-radius:6px;font-weight:600;">Ask Zane</button>
                    <button onclick="openSplitModal('{txn_id}', '{safe_desc}', {debit}, {credit}, '{txn_date}')" class="btn" style="padding:7px 14px;font-size:12px;background:rgba(245,158,11,0.2);border:1px solid #f59e0b;color:#f59e0b;border-radius:6px;" title="Split into multiple categories">Split</button>
                    <select class="form-input" style="width:120px;padding:4px;font-size:11px;" onchange="categorizeTransaction('{txn_id}', this.value, '{safe_desc}')">
                        <option value="">Manual...</option>
                        {category_options}
                    </select>
                </div>
                '''
            
            # Combo-match hint attributes (only present when match was a multi-invoice combo)
            combo_attrs = ""
            if txn.get("match_type") == "customer_payment_combo":
                _combo_ids = txn.get("combo_invoice_ids") or []
                _combo_cust = txn.get("combo_customer_id") or ""
                if _combo_ids:
                    combo_attrs = f' data-combo-invoices="{",".join(_combo_ids)}" data-combo-customer="{_combo_cust}"'
            
            # Settlement-discount hint attributes (present when ClickAI matched the credit to a
            # single invoice LESS the customer's discount %) — used to pre-select + pre-tick on confirm.
            disc_attrs = ""
            if txn.get("disc_invoice_id"):
                _disc_inv = txn.get("disc_invoice_id") or ""
                _disc_cust = txn.get("disc_customer_id") or ""
                if _disc_inv and _disc_cust:
                    disc_attrs = f' data-disc-invoice="{_disc_inv}" data-disc-customer="{_disc_cust}"'
            
            # Statement (full-account) hint attributes — present when ClickAI matched the credit to a
            # customer's whole statement balance (optionally less their discount %).
            stmt_attrs = ""
            if txn.get("stmt_invoice_ids"):
                _stmt_ids = [i for i in (txn.get("stmt_invoice_ids") or []) if i]
                _stmt_cust = txn.get("stmt_customer_id") or ""
                if _stmt_ids and _stmt_cust:
                    _stmt_short = txn.get("stmt_shortfall") or 0
                    stmt_attrs = f' data-stmt-invoices="{",".join(_stmt_ids)}" data-stmt-customer="{_stmt_cust}" data-stmt-shortfall="{_stmt_short}"'
            
            # Running balance (from bank statement) — show in dim color so it doesn't compete with debit/credit
            running_bal = txn.get("balance")
            if running_bal is None:
                running_bal = txn.get("running_balance")  # fallback for legacy field name
            if running_bal is not None:
                try:
                    rb = float(running_bal)
                    bal_color = "var(--red)" if rb < 0 else "var(--text-muted)"
                    balance_html = f'<span style="color:{bal_color};">{money(rb)}</span>'
                except (ValueError, TypeError):
                    balance_html = '<span style="color:var(--text-muted);">-</span>'
            else:
                balance_html = '<span style="color:var(--text-muted);">-</span>'
            
            return f'''
            <tr data-id="{txn_id}" data-debit="{debit}" data-credit="{credit}"{combo_attrs}{disc_attrs}{stmt_attrs}>
                <td style="white-space:nowrap;">{txn.get("date", "-")}</td>
                <td>
                    <div style="max-width:300px;">{desc}</div>
                    {suggestion_html}
                </td>
                <td style="text-align:right;color:var(--red);white-space:nowrap;">{money(debit) if debit > 0 else "-"}</td>
                <td style="text-align:right;color:var(--green);white-space:nowrap;">{money(credit) if credit > 0 else "-"}</td>
                <td style="text-align:right;white-space:nowrap;font-size:12px;">{balance_html}</td>
                <td>{action_html}</td>
            </tr>
            '''
        
        # Build sections
        auto_rows = "".join([build_row(t, show_approve=True) for t in auto_matched[:100]])
        suggested_rows = "".join([build_row(t, show_approve=True) for t in suggested[:100]])
        needs_rows = "".join([build_row(t, show_approve=False, show_suggestion=False) for t in needs_attention[:100]])
        
        # Build done rows - show allocated transactions so they're traceable
        done_rows_html = ""
        for t in already_done[:200]:
            txn_id = t.get("id", "")
            debit = float(t.get("debit", 0))
            credit = float(t.get("credit", 0))
            desc = safe_string(t.get("description", "-"))
            cat = t.get("category", t.get("suggested_category", ""))
            matched_at = str(t.get("matched_at", ""))[:10]
            is_split = t.get("is_split", False)
            split_cats = t.get("split_categories", [])
            matched_name = t.get("matched_name", "")
            matched_entity_type = t.get("matched_entity_type", "")
            matched_invoice_num = t.get("matched_invoice_number", "")
            matched_invoice_id = t.get("matched_invoice_id", "")
            match_ref = t.get("match_reference", "")
            
            # Build category display with entity name
            if is_split and split_cats:
                cat_html = '<div style="display:flex;flex-wrap:wrap;gap:3px;">'
                cat_html += '<span style="background:#f59e0b;color:black;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:700;">SPLIT</span>'
                for sc in split_cats[:4]:
                    sc_cat = sc.get("category", "")[:20]
                    sc_amt = sc.get("amount", 0)
                    cat_html += f'<span style="background:rgba(99,102,241,0.2);color:var(--text);padding:3px 6px;border-radius:4px;font-size:10px;">{sc_cat} R{sc_amt:,.2f}</span>'
                cat_html += '</div>'
            else:
                cat_html = f'<span style="background:var(--green);color:white;padding:4px 10px;border-radius:4px;font-size:12px;">{cat}</span>'
            
            # Entity name line (customer or supplier)
            entity_html = ""
            if matched_name:
                _entity_icon = "👤" if matched_entity_type == "customer" else "🏢"
                entity_html = f'<div style="font-size:12px;color:#22d3ee;margin-top:4px;font-weight:600;">{_entity_icon} {safe_string(matched_name)}</div>'
            elif match_ref and cat in ("Customer Payment", "Customer Payment?", "Supplier Payment"):
                # Fallback: extract name from match_reference
                _ref_name = match_ref.replace("Maybe ", "").replace("?", "").strip()
                if " - " in _ref_name:
                    _ref_name = _ref_name.split(" - ", 1)[1].strip()
                if _ref_name and not _ref_name.startswith("INV"):
                    _entity_icon = "👤" if "Customer" in cat else "🏢"
                    entity_html = f'<div style="font-size:12px;color:#22d3ee;margin-top:4px;font-weight:600;">{_entity_icon} {safe_string(_ref_name)}</div>'
            
            # Invoice link (clickable)
            inv_link_html = ""
            if matched_invoice_num:
                inv_link_html = f'<a href="/invoices/{matched_invoice_id}" style="font-size:11px;color:var(--primary);text-decoration:none;margin-top:2px;display:inline-block;" title="View invoice">{matched_invoice_num} →</a>'
            
            # Running balance for done row
            running_bal_done = t.get("balance")
            if running_bal_done is None:
                running_bal_done = t.get("running_balance")  # fallback for legacy field name
            if running_bal_done is not None:
                try:
                    rb_done = float(running_bal_done)
                    bal_done_color = "var(--red)" if rb_done < 0 else "var(--text-muted)"
                    balance_done_html = f'<span style="color:{bal_done_color};">{money(rb_done)}</span>'
                except (ValueError, TypeError):
                    balance_done_html = '<span style="color:var(--text-muted);">-</span>'
            else:
                balance_done_html = '<span style="color:var(--text-muted);">-</span>'
            
            done_rows_html += f'''
            <tr data-id="{txn_id}">
                <td style="white-space:nowrap;">{t.get("date", "-")}</td>
                <td><div style="max-width:300px;">{desc}</div></td>
                <td style="text-align:right;color:var(--red);white-space:nowrap;">{money(debit) if debit > 0 else "-"}</td>
                <td style="text-align:right;color:var(--green);white-space:nowrap;">{money(credit) if credit > 0 else "-"}</td>
                <td style="text-align:right;white-space:nowrap;font-size:12px;">{balance_done_html}</td>
                <td>{cat_html}
                    {entity_html}
                    {inv_link_html}
                    <div style="font-size:10px;color:var(--text-muted);margin-top:3px;">{matched_at}</div></td>
            </tr>
            '''
        
        content = f'''
        <style>
        .recon-tabs {{ display: flex; gap: 5px; margin-bottom: 20px; flex-wrap: wrap; }}
        .recon-tab {{ padding: 12px 20px; border-radius: 8px; cursor: pointer; background: var(--card); border: 1px solid var(--border); transition: all 0.2s; }}
        .recon-tab:hover {{ background: rgba(139,92,246,0.1); }}
        .recon-tab.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
        .recon-tab .count {{ background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 10px; margin-left: 8px; font-size: 12px; }}
        .recon-section {{ display: none; }}
        .recon-section.active {{ display: block; }}
        .bulk-bar {{ background: linear-gradient(135deg, rgba(16,185,129,0.2), rgba(16,185,129,0.1)); padding: 15px; border-radius: 8px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
        /* Split Modal */
        .split-overlay {{ position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9998;display:none;justify-content:center;align-items:center; }}
        .split-overlay.active {{ display:flex; }}
        .split-modal {{ background:var(--card);border-radius:16px;padding:24px;width:95%;max-width:560px;max-height:85vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.4);border:1px solid var(--border); }}
        .split-modal h3 {{ margin:0 0 6px 0;font-size:18px; }}
        .split-line {{ display:grid;grid-template-columns:2fr 100px 40px;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06); }}
        .split-line select, .split-line input {{ padding:8px 10px;border-radius:6px;border:1px solid var(--border);background:var(--input-bg,var(--bg));color:var(--text);font-size:13px; }}
        .split-line input[type=number] {{ text-align:right; }}
        .split-line .remove-split {{ background:none;border:none;color:var(--red);cursor:pointer;font-size:18px;padding:4px 8px;border-radius:4px; }}
        .split-line .remove-split:hover {{ background:rgba(239,68,68,0.15); }}
        .split-balance {{ padding:10px 0;font-size:14px;font-weight:600;display:flex;justify-content:space-between;align-items:center; }}
        .split-balance.balanced {{ color:var(--green); }}
        .split-balance.unbalanced {{ color:var(--red); }}
        .split-matched-badge {{ background:linear-gradient(135deg,#6366f1,#8b5cf6);color:white;padding:6px 12px;border-radius:8px;font-size:12px;margin-bottom:12px;display:flex;align-items:center;gap:6px; }}
        </style>
        
        <!-- HEADER -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <h2 style="margin:0;">🏦 Bank Reconciliation</h2>
            <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <a href="/banking/reconcile" class="btn btn-primary">Reconcile vs GL</a>
                <a href="/subscriptions" class="btn btn-secondary">📦 Recurring Expenses</a>
                <button class="btn btn-secondary" style="background:rgba(245,158,11,0.15);border-color:#f59e0b;color:#f59e0b;" onclick="resetPatterns()">Reset Learned Patterns</button>
                <button class="btn btn-secondary" style="background:rgba(239,68,68,0.15);border-color:#ef4444;color:#ef4444;" onclick="deleteAllTransactions()">🗑️ Delete All</button>
                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:8px;padding:6px 10px;">
                    <select id="importBatchSelect" style="padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:12px;max-width:340px;">
                        <option value="">Delete a single import…</option>
                        {import_options_html}
                    </select>
                    <button class="btn btn-secondary" style="background:rgba(239,68,68,0.12);border-color:#ef4444;color:#ef4444;" onclick="deleteImport()">Delete unallocated</button>
                </div>
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:8px;padding:6px 10px;">
                    <span style="font-size:11px;color:var(--text-muted);">Import range (optional):</span>
                    <input type="date" id="importDateFrom" title="From date" style="padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:12px;">
                    <span style="font-size:11px;color:var(--text-muted);">to</span>
                    <input type="date" id="importDateTo" title="To date" style="padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:12px;">
                    <label class="btn btn-primary" style="cursor:pointer;margin:0;">
                        📥 Import Statement
                        <input type="file" accept=".csv,.pdf,.txt,text/plain" style="display:none;" onchange="uploadStatement(this.files[0])">
                    </label>
                </div>
            </div>
        </div>
        
        <!-- SUMMARY CARDS -->
        <div class="stats-grid" style="margin-bottom:20px;">
            <div class="stat-card" style="background:rgba(16,185,129,0.1);border-color:var(--green);cursor:pointer;" onclick="showTab('auto')">
                <div class="stat-value" id="statAuto" style="color:var(--green);">{auto_count}</div>
                <div class="stat-label">✅ Auto-Matched</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">High confidence - just approve</div>
            </div>
            <div class="stat-card" style="background:rgba(245,158,11,0.1);border-color:var(--yellow);cursor:pointer;" onclick="showTab('suggested')">
                <div class="stat-value" id="statSuggested" style="color:var(--yellow);">{suggested_count}</div>
                <div class="stat-label">🤖 AI Suggested</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">Review suggestions</div>
            </div>
            <div class="stat-card" style="background:rgba(239,68,68,0.1);border-color:var(--red);cursor:pointer;" onclick="showTab('needs')">
                <div class="stat-value" id="statNeeds" style="color:var(--red);">{needs_count}</div>
                <div class="stat-label">❓ Needs You</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">No suggestion - you decide</div>
            </div>
            <div class="stat-card" style="cursor:pointer;" onclick="showTab('done')">
                <div class="stat-value" id="statDone">{done_count}</div>
                <div class="stat-label">GOOD: Done</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">Already categorized</div>
            </div>
        </div>
        
        <!-- SEARCH -->
        <div style="margin-bottom:15px;">
            <input type="text" id="bankSearch" placeholder="Search transactions... (description, amount, date)" 
                   oninput="filterBankTransactions(this.value)"
                   style="width:100%;padding:12px 16px;border:1px solid var(--border);border-radius:8px;background:var(--card);color:var(--text);font-size:14px;">
        </div>
        
        <!-- TABS -->
        <div class="recon-tabs">
            <div class="recon-tab active" onclick="showTab('auto')">✅ Auto-Matched <span class="count" id="tabAuto">{auto_count}</span></div>
            <div class="recon-tab" onclick="showTab('suggested')">🤖 Suggested <span class="count" id="tabSuggested">{suggested_count}</span></div>
            <div class="recon-tab" onclick="showTab('needs')">❓ Needs You <span class="count" id="tabNeeds">{needs_count}</span></div>
            <div class="recon-tab" onclick="showTab('done')">✅ Done <span class="count" id="tabDone">{done_count}</span></div>
        </div>
        
        <!-- AUTO-MATCHED SECTION -->
        <div id="section-auto" class="recon-section active">
            {f"""
            <div class="bulk-bar">
                <div>
                    <strong>🎉 Zane matched {auto_count} transactions automatically!</strong><br>
                    <span style="font-size:13px;color:var(--text-muted);">These are high-confidence matches. Approve all or review individually.</span>
                </div>
                <button onclick="bulkApprove()" class="btn btn-primary" style="background:var(--green);">GOOD: Approve All ({auto_count})</button>
            </div>
            """ if auto_count > 0 else ""}
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="text-align:right;width:120px;">Balance</th>
                            <th style="width:180px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {auto_rows or "<tr><td colspan='6' style='text-align:center;padding:40px;color:var(--text-muted);'>🎉 No auto-matched transactions waiting for approval!</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- SUGGESTED SECTION -->
        <div id="section-suggested" class="recon-section">
            <div class="card" style="margin-bottom:15px;background:rgba(245,158,11,0.1);">
                <p style="margin:0;"><strong>🤖 AI Suggestions</strong> - Zane thinks these might be correct, but confidence is lower. Please verify.</p>
            </div>
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="text-align:right;width:120px;">Balance</th>
                            <th style="width:180px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {suggested_rows or "<tr><td colspan='6' style='text-align:center;padding:40px;color:var(--text-muted);'>No suggestions pending</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- NEEDS ATTENTION SECTION -->
        <div id="section-needs" class="recon-section">
            <div class="card" style="margin-bottom:15px;background:rgba(239,68,68,0.1);">
                <p style="margin:0;"><strong>❓ These need your help</strong> - Zane couldn't figure these out. Select a category to teach him!</p>
            </div>
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="text-align:right;width:120px;">Balance</th>
                            <th style="width:180px;">Category</th>
                        </tr>
                    </thead>
                    <tbody>
                        {needs_rows or "<tr><td colspan='6' style='text-align:center;padding:40px;color:var(--green);'>🎉 Nothing needs your attention!</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- DONE / HISTORY SECTION -->
        <div id="section-done" class="recon-section">
            <div class="card" style="margin-bottom:15px;background:rgba(16,185,129,0.1);">
                <p style="margin:0;"><strong>Allocated Transactions</strong> - These have been categorized and recorded in your books.</p>
            </div>
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="text-align:right;width:120px;">Balance</th>
                            <th style="width:150px;">Category</th>
                        </tr>
                    </thead>
                    <tbody>
                        {done_rows_html or "<tr><td colspan='6' style='text-align:center;padding:40px;color:var(--text-muted);'>No allocated transactions yet. Categorize transactions above and they will appear here.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- TIPS -->
        <div class="card" style="margin-top:20px;background:linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.05));">
            <h4 style="margin-top:0;">💡 How Zane Learns</h4>
            <p style="color:var(--text-muted);margin:0;">
                Every time you categorize a transaction, Zane remembers the pattern. Next time he sees "TELKOM", he'll know it's Telephone. 
                The more you teach him, the faster reconciliation becomes!
            </p>
        </div>
        
        <script>
        function showTab(tab) {{
            // Hide all sections
            document.querySelectorAll('.recon-section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.recon-tab').forEach(t => t.classList.remove('active'));
            
            // Show selected
            document.getElementById('section-' + tab).classList.add('active');
            event.target.closest('.recon-tab')?.classList.add('active');
        }}
        
        async function categorizeTransaction(id, category, description, entityId, entityName, invoiceIds, invoiceNums, discountAllowed) {{
            if (!category) return;
            
            // If Customer Payment or Supplier Payment and no entity chosen, prompt to pick one
            if ((category === 'Customer Payment' || category === 'Supplier Payment') && !entityId) {{
                showEntityPicker(id, category, description);
                return;
            }}
            
            // For all OTHER categories (except Ignore/Transfer), prompt for optional supplier/customer link.
            // Skip if entityId already provided (avoids recursion when picker calls back into this function).
            if (!entityId 
                && category !== 'Ignore' 
                && category !== 'Transfer Between Accounts' 
                && category !== 'Customer Payment' 
                && category !== 'Supplier Payment') {{
                showAllocationPicker(id, category, description);
                return;
            }}
            
            // Counter-sale guard: POS books every counter sale automatically, so recording
            // a bank payment against a "Counter Sale" customer doubles the money (it inflates
            // the bank and creates a credit on Debtors Control). Soft warning — still allowed.
            if (category === 'Customer Payment' && entityName
                && entityName.toUpperCase().split(' ').join('') === 'COUNTERSALE') {{
                if (!confirm('POS already books counter sales automatically. Recording this as a Counter Sale customer payment will double the money — it inflates the bank and creates a credit on Debtors Control. Continue anyway?')) {{
                    return;
                }}
            }}
            
            try {{
                const payload = {{id, category, description}};
                if (entityId && entityId !== '__skip__') {{ payload.entity_id = entityId; payload.entity_name = entityName || ''; }}
                if (invoiceIds && invoiceIds.length > 0) {{ payload.invoice_ids = invoiceIds; payload.invoice_nums = invoiceNums || []; }}
                if (discountAllowed) {{ payload.discount_allowed = true; }}
                
                const response = await fetch('/api/banking/categorize', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(payload)
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    const row = document.querySelector(`tr[data-id="${{id}}"]`);
                    if (row) {{
                        // Mark as allocated IMMEDIATELY so updateCounts excludes it from totals
                        row.dataset.allocated = '1';
                        const cells = row.querySelectorAll('td');
                        const lastCell = cells[cells.length - 1];
                        lastCell.innerHTML = `<span style="background:var(--green);color:white;padding:4px 10px;border-radius:4px;font-size:12px;font-weight:bold;">GOOD: ${{category}}</span>`;
                        row.style.background = 'rgba(16,185,129,0.15)';
                        row.style.transition = 'opacity 0.5s';
                        setTimeout(() => {{ row.style.opacity = '0.4'; }}, 2000);
                        setTimeout(() => row.remove(), 3000);
                    }}
                    updateCounts();
                }} else {{
                    alert('Error: ' + data.error);
                }}
            }} catch (err) {{
                alert('Failed to categorize');
            }}
        }}
        
        async function approveMatch(id, category) {{
            // Extract description from the row so showAllocationPicker can pre-match a supplier/customer
            const row = document.querySelector(`tr[data-id="${{id}}"]`);
            let desc = '';
            if (row) {{
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {{
                    // Description cell is index 1; grab the first text/div content
                    const descDiv = cells[1].querySelector('div');
                    desc = (descDiv ? descDiv.textContent : cells[1].textContent || '').trim();
                }}
            }}
            await categorizeTransaction(id, category, desc);
        }}
        
        // Entity picker for Customer Payment / Supplier Payment
        function showEntityPicker(txnId, category, description) {{
            const isCustomer = category === 'Customer Payment';
            const entities = isCustomer ? _entityCustomers : _entitySuppliers;
            const label = isCustomer ? 'Customer' : 'Supplier';
            
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            // Read combo hints from row data attributes (set when ClickAI auto-matched a multi-invoice combo)
            const comboCustomer = row ? row.getAttribute('data-combo-customer') || '' : '';
            const comboInvoicesStr = row ? row.getAttribute('data-combo-invoices') || '' : '';
            const comboInvoiceIds = comboInvoicesStr ? comboInvoicesStr.split(',').filter(Boolean) : [];
            const hasCombo = comboCustomer && comboInvoiceIds.length > 0;
            
            // Read settlement-discount hint (single invoice matched LESS the customer's discount %)
            const discCustomer = row ? row.getAttribute('data-disc-customer') || '' : '';
            const discInvoice = row ? row.getAttribute('data-disc-invoice') || '' : '';
            const hasDisc = !!(discCustomer && discInvoice);
            // Read statement (full-account) hint — whole balance matched, optionally less discount %
            const stmtCustomer = row ? row.getAttribute('data-stmt-customer') || '' : '';
            const stmtInvoicesStr = row ? row.getAttribute('data-stmt-invoices') || '' : '';
            const stmtInvoiceIds = stmtInvoicesStr ? stmtInvoicesStr.split(',').filter(Boolean) : [];
            const stmtShortfall = row ? parseFloat(row.getAttribute('data-stmt-shortfall') || '0') : 0;
            const hasStmt = !!(stmtCustomer && stmtInvoiceIds.length > 0);
            // Customer to pre-select: combo wins, then statement, then single-invoice discount.
            const preCustomer = hasCombo ? comboCustomer : (hasStmt ? stmtCustomer : (hasDisc ? discCustomer : ''));
            
            let optionsHtml = entities.map(e => {{
                const selected = (preCustomer && e.id === preCustomer) ? ' selected' : '';
                return `<option value="${{e.id}}" data-name="${{(e.name||'').replace(/"/g,'&quot;')}}"${{selected}}>${{e.name}}</option>`;
            }}).join('');
            
            const safeDesc = (description || '').replace(/'/g, "\\\\'");
            
            // Combo banner — shown only when ClickAI pre-selected based on multi-invoice match
            const comboBanner = hasCombo ? `
                <div style="background:rgba(34,211,238,0.10);border:1px solid rgba(34,211,238,0.4);border-radius:6px;padding:8px 10px;margin-bottom:8px;font-size:11px;color:#22d3ee;">
                    🔗 ClickAI matched this to ${{comboInvoiceIds.length}} invoices that sum to the payment amount.
                    Verify the ticks below and click Allocate.
                </div>` : '';
            
            // Settlement-discount banner — shown when the amount matched an invoice less the customer's discount %
            const discBanner = (hasDisc && !hasCombo && !hasStmt) ? `
                <div style="background:rgba(245,158,11,0.10);border:1px solid rgba(245,158,11,0.4);border-radius:6px;padding:8px 10px;margin-bottom:8px;font-size:11px;color:#f59e0b;">
                    Matched to this customer's invoice less their settlement discount. The shortfall is pre-ticked as Discount Allowed below — review and change if needed.
                </div>` : '';
            
            // Statement banner — shown when the whole statement balance was matched (optionally less discount)
            const stmtBanner = (hasStmt && !hasCombo) ? `
                <div style="background:rgba(34,211,238,0.10);border:1px solid rgba(34,211,238,0.4);border-radius:6px;padding:8px 10px;margin-bottom:8px;font-size:11px;color:#22d3ee;">
                    Matched to this customer's full statement (${{stmtInvoiceIds.length}} invoices). ${{stmtShortfall > 0.01 ? 'The settlement discount is pre-ticked as Discount Allowed below. ' : ''}}Review the ticks and click Allocate.
                </div>` : '';
            
            actionCell.innerHTML = `
                <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:320px;">
                    <div style="font-size:13px;font-weight:700;color:#8b5cf6;margin-bottom:8px;">${{category}} — Select ${{label}}</div>
                    ${{comboBanner}}${{discBanner}}${{stmtBanner}}
                    <select id="entityPick_${{txnId}}" onchange="loadEntityInvoices('${{txnId}}','${{category}}')" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px;margin-bottom:8px;">
                        <option value="">-- Select ${{label}} --</option>
                        ${{optionsHtml}}
                    </select>
                    <div id="invList_${{txnId}}" style="max-height:200px;overflow-y:auto;margin-bottom:8px;"></div>
                    <div style="display:flex;gap:6px;">
                        <button onclick="confirmEntityPick('${{txnId}}','${{category}}','${{safeDesc}}')" 
                                style="flex:1;padding:8px;background:var(--green);color:white;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:13px;">
                            Allocate
                        </button>
                        <button onclick="categorizeTransaction('${{txnId}}','${{category}}','${{safeDesc}}','__skip__','')" 
                                style="padding:8px 12px;background:var(--card);border:1px solid var(--border);color:var(--text-muted);border-radius:6px;cursor:pointer;font-size:12px;">
                            Skip
                        </button>
                    </div>
                </div>`;
            
            // If we have combo, statement or settlement-discount hints, the customer is already
            // selected — auto-load their invoices (with a small delay so the DOM has settled)
            if (hasCombo || hasStmt || hasDisc) {{
                setTimeout(() => loadEntityInvoices(txnId, category), 50);
            }}
        }}
        
        async function loadEntityInvoices(txnId, category) {{
            const sel = document.getElementById('entityPick_' + txnId);
            const container = document.getElementById('invList_' + txnId);
            if (!sel || !container) return;
            const entityId = sel.value;
            if (!entityId) {{ container.innerHTML = ''; return; }}
            
            // Read combo hints from the row (if any) — used to auto-tick the right invoices
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const comboCustomer = row ? row.getAttribute('data-combo-customer') || '' : '';
            const comboInvoicesStr = row ? row.getAttribute('data-combo-invoices') || '' : '';
            const comboInvoiceIds = (comboInvoicesStr && entityId === comboCustomer)
                ? comboInvoicesStr.split(',').filter(Boolean)
                : [];
            // Read settlement-discount hint — auto-tick the matched invoice + pre-tick Discount Allowed.
            const discCustomer = row ? row.getAttribute('data-disc-customer') || '' : '';
            const discInvoiceId = (entityId && entityId === discCustomer) ? (row ? row.getAttribute('data-disc-invoice') || '' : '') : '';
            const hasDiscMatch = !!discInvoiceId;
            // Read statement (full-account) hint — auto-tick ALL the customer's invoices + pre-tick discount.
            const stmtCustomer = row ? row.getAttribute('data-stmt-customer') || '' : '';
            const stmtInvoiceIds = (entityId && entityId === stmtCustomer)
                ? ((row ? row.getAttribute('data-stmt-invoices') || '' : '').split(',').filter(Boolean))
                : [];
            const stmtShortfall = row ? parseFloat(row.getAttribute('data-stmt-shortfall') || '0') : 0;
            const hasStmtMatch = stmtInvoiceIds.length > 0;
            
            container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:6px;">Loading invoices...</div>';
            
            try {{
                const resp = await fetch('/api/banking/entity-invoices', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        entity_id: entityId,
                        entity_type: category === 'Customer Payment' ? 'customer' : 'supplier'
                    }})
                }});
                const data = await resp.json();
                
                if (!data.success || !data.invoices || data.invoices.length === 0) {{
                    container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:6px;background:rgba(255,255,255,0.03);border-radius:6px;">No outstanding invoices</div>';
                    return;
                }}
                
                let html = '<div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;font-weight:600;">Allocate against invoices:</div>';
                // Statement match: render smallest-outstanding first so the LARGEST invoice is last.
                // On confirm the payment is applied in order and the last (largest) invoice cleanly
                // absorbs the settlement-discount shortfall (keeps it within the per-invoice guard).
                if (hasStmtMatch) {{
                    data.invoices.sort((a, b) => (((a.total||0) - (a.paid_amount||0)) - ((b.total||0) - (b.paid_amount||0))));
                }}
                for (const inv of data.invoices) {{
                    // If invoice is part of the combo match (or the settlement-discount match), pre-tick + highlight it
                    const isComboInv = comboInvoiceIds.includes(inv.id);
                    const isDiscInv = (inv.id === discInvoiceId);
                    const isStmtInv = stmtInvoiceIds.includes(inv.id);
                    const checked = (isComboInv || isDiscInv || isStmtInv) ? ' checked' : '';
                    const rowStyle = (isComboInv || isDiscInv || isStmtInv)
                        ? 'background:rgba(34,211,238,0.10);border:1px solid rgba(34,211,238,0.35);'
                        : 'background:rgba(255,255,255,0.03);';
                    // Outstanding = total minus any partial payment already recorded
                    const outstanding = Math.round((inv.total - (inv.paid_amount || 0)) * 100) / 100;
                    // Age note — shown so the user can decide; never enforced.
                    let ageNote = '';
                    if (inv.days_old !== null && inv.days_old !== undefined) {{
                        if (inv.days_old <= 30) {{
                            ageNote = `<span style="color:var(--green);font-size:10px;">${{inv.days_old}}d · within terms</span>`;
                        }} else {{
                            ageNote = `<span style="color:var(--orange);font-size:10px;">${{inv.days_old}}d · over 30 days</span>`;
                        }}
                    }}
                    html += `<label style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:6px;cursor:pointer;font-size:12px;${{rowStyle}}margin-bottom:3px;">
                        <input type="checkbox" class="invCheck_${{txnId}}" value="${{inv.id}}" data-num="${{inv.number}}" data-amount="${{outstanding}}" onchange="srUpdateShortfall('${{txnId}}')" style="accent-color:var(--green);"${{checked}}>
                        <span style="flex:1;">${{inv.number}} <span style="color:var(--text-muted);">(${{inv.date}})</span> ${{ageNote}}</span>
                        <span style="font-weight:700;">R${{outstanding.toLocaleString('en-ZA', {{minimumFractionDigits:2}})}}</span>
                    </label>`;
                }}
                // Live shortfall panel — appears when ticked invoices exceed the payment.
                html += `<div id="shortfallBox_${{txnId}}" style="display:none;margin-top:6px;padding:8px 10px;border-radius:6px;background:rgba(245,158,11,0.10);border:1px solid rgba(245,158,11,0.4);font-size:11px;">
                    <div id="shortfallText_${{txnId}}" style="color:var(--orange);font-weight:600;margin-bottom:5px;"></div>
                    <label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--text);">
                        <input type="checkbox" id="discAllowed_${{txnId}}" style="accent-color:var(--orange);">
                        <span>Credit the shortfall as Discount Allowed (customer will be credited, closes the invoice)</span>
                    </label>
                </div>`;
                container.innerHTML = html;
                srUpdateShortfall(txnId);
                // Settlement-discount match (single invoice OR full statement) — pre-tick Discount Allowed
                // so the shortfall closes the invoice(s). srUpdateShortfall has revealed the box;
                // Daphne can untick to override.
                if (hasDiscMatch || (hasStmtMatch && stmtShortfall > 0.01)) {{
                    const da = document.getElementById('discAllowed_' + txnId);
                    const box = document.getElementById('shortfallBox_' + txnId);
                    if (da && box && box.style.display !== 'none') {{ da.checked = true; }}
                }}
            }} catch (err) {{
                container.innerHTML = '<div style="color:var(--red);font-size:12px;padding:6px;">Failed to load invoices</div>';
            }}
        }}
        
        // Recompute the shortfall whenever invoice ticks change. The shortfall
        // is the payment amount minus the outstanding total of ticked invoices.
        // Only shown when the payment is SHORT (paid less than invoiced).
        function srUpdateShortfall(txnId) {{
            const box = document.getElementById('shortfallBox_' + txnId);
            if (!box) return;
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const payAmount = row ? parseFloat(row.getAttribute('data-credit') || '0') : 0;
            const checks = document.querySelectorAll('.invCheck_' + txnId + ':checked');
            let invTotal = 0;
            checks.forEach(c => {{ invTotal += parseFloat(c.getAttribute('data-amount') || '0'); }});
            const shortfall = Math.round((invTotal - payAmount) * 100) / 100;
            // Show only for a genuine shortfall (1c..50% of invoice total) — a
            // larger gap is probably a wrong invoice selection, not a discount.
            if (checks.length > 0 && shortfall > 0.01 && shortfall <= invTotal * 0.5) {{
                document.getElementById('shortfallText_' + txnId).textContent =
                    'Payment is R' + shortfall.toFixed(2) + ' short of the selected invoice total (R' + invTotal.toFixed(2) + ').';
                box.style.display = 'block';
            }} else {{
                const da = document.getElementById('discAllowed_' + txnId);
                if (da) da.checked = false;
                box.style.display = 'none';
            }}
        }}
        
        function confirmEntityPick(txnId, category, description) {{
            const sel = document.getElementById('entityPick_' + txnId);
            if (!sel) return;
            const entityId = sel.value;
            const entityName = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].getAttribute('data-name') || sel.options[sel.selectedIndex].text : '';
            if (!entityId) {{
                alert('Please select a ' + (category === 'Customer Payment' ? 'customer' : 'supplier'));
                return;
            }}
            
            // Collect selected invoice IDs
            const checks = document.querySelectorAll('.invCheck_' + txnId + ':checked');
            const invoiceIds = Array.from(checks).map(c => c.value);
            const invoiceNums = Array.from(checks).map(c => c.getAttribute('data-num'));
            // Discount Allowed — only when the shortfall box is visible and ticked
            const daBox = document.getElementById('shortfallBox_' + txnId);
            const daCheck = document.getElementById('discAllowed_' + txnId);
            const discountAllowed = !!(daBox && daBox.style.display !== 'none' && daCheck && daCheck.checked);
            
            categorizeTransaction(txnId, category, description, entityId, entityName, invoiceIds, invoiceNums, discountAllowed);
        }}
        
        // ═══════════════════════════════════════════════════════════
        // GENERIC ALLOCATION PICKER — for any category (e.g. Telephone, Bank Charges, Sales)
        // Lets user optionally link the transaction to a supplier or customer.
        // Auto-pre-selects entity matching the description (e.g. "VODACOM" → VODACOM supplier).
        // ═══════════════════════════════════════════════════════════
        function showAllocationPicker(txnId, category, description) {{
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            // Decide income vs expense based on row's debit/credit data attrs
            const debit = parseFloat(row.getAttribute('data-debit') || '0');
            const credit = parseFloat(row.getAttribute('data-credit') || '0');
            const isExpense = debit > 0;
            
            // Income categories (money in) → show Customers; Expense (money out) → show Suppliers
            const isCustomer = !isExpense;
            const entities = isCustomer ? _entityCustomers : _entitySuppliers;
            const label = isCustomer ? 'Customer' : 'Supplier';
            const colorAccent = isCustomer ? '#10b981' : '#f59e0b';
            
            // Auto-pre-select entity whose name appears in the description
            const descUpper = (description || '').toUpperCase();
            let preSelectedId = '';
            const genericWords = ['PTY','LTD','THE','AND','FOR','BANK','ELECT','ELECTRONIC',
                                  'PAYMENT','TRANSFER','CREDIT','DEBIT','BUSINESS','ACCOUNT',
                                  'SERVICE','FEE','CHARGE','CHARGES','CASH','DEPOSIT','FROM','BANKING'];
            for (const e of entities) {{
                const ename = (e.name || '').toUpperCase().trim();
                if (ename.length < 3) continue;
                const words = ename.split(/\\s+/).filter(w => w.length >= 3 && genericWords.indexOf(w) === -1);
                for (const w of words) {{
                    if (descUpper.indexOf(w) !== -1) {{
                        preSelectedId = e.id;
                        break;
                    }}
                }}
                if (preSelectedId) break;
            }}
            
            const optionsHtml = entities.map(e => {{
                const sel = (e.id === preSelectedId) ? ' selected' : '';
                const safeName = (e.name || '').replace(/"/g, '&quot;');
                return `<option value="${{e.id}}" data-name="${{safeName}}"${{sel}}>${{e.name}}</option>`;
            }}).join('');
            
            const safeDesc = (description || '').replace(/'/g, "\\\\'");
            const safeCat = (category || '').replace(/'/g, "\\\\'");
            
            const matchBanner = preSelectedId ? `
                <div style="background:rgba(34,211,238,0.10);border:1px solid rgba(34,211,238,0.4);border-radius:6px;padding:6px 9px;margin-bottom:8px;font-size:11px;color:#22d3ee;">
                    🔗 Auto-matched to ${{label.toLowerCase()}} based on description. Verify or change below.
                </div>` : '';
            
            actionCell.innerHTML = `
                <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:300px;">
                    <div style="font-size:13px;font-weight:700;color:${{colorAccent}};margin-bottom:6px;">
                        ${{category}} — Allocate to ${{label}}?
                    </div>
                    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
                        Optional: link this transaction to a specific ${{label.toLowerCase()}}.
                    </div>
                    ${{matchBanner}}
                    <select id="allocPick_${{txnId}}" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:13px;margin-bottom:8px;">
                        <option value="">-- None / Skip ${{label}} --</option>
                        ${{optionsHtml}}
                    </select>
                    <div style="display:flex;gap:6px;">
                        <button onclick="confirmAllocationPick('${{txnId}}','${{safeCat}}','${{safeDesc}}')" 
                                style="flex:1;padding:8px;background:var(--green);color:white;border:none;border-radius:6px;cursor:pointer;font-weight:700;font-size:13px;">
                            Allocate
                        </button>
                        <button onclick="categorizeTransaction('${{txnId}}','${{safeCat}}','${{safeDesc}}','__skip__','')" 
                                style="padding:8px 12px;background:var(--card);border:1px solid var(--border);color:var(--text-muted);border-radius:6px;cursor:pointer;font-size:12px;">
                            Skip
                        </button>
                    </div>
                </div>`;
        }}
        
        function confirmAllocationPick(txnId, category, description) {{
            const sel = document.getElementById('allocPick_' + txnId);
            if (!sel) return;
            const entityId = sel.value;
            const entityName = (entityId && sel.options[sel.selectedIndex]) 
                ? (sel.options[sel.selectedIndex].getAttribute('data-name') || sel.options[sel.selectedIndex].text) 
                : '';
            
            // If user left "None / Skip" selected, treat as skip (no entity link)
            const finalEntityId = entityId || '__skip__';
            categorizeTransaction(txnId, category, description, finalEntityId, entityName, [], []);
        }}
        
        // ═══════════════════════════════════════════════════════════
        // ASK ZANE - Collaborative bank transaction allocation
        // Uses dedicated lightweight AI endpoint (not full Zane brain)
        // ═══════════════════════════════════════════════════════════
        async function askZaneBank(txnId, description, debit, credit, date, clarificationAnswer) {{
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            // User chose "let me pick" — show dropdown
            if (clarificationAnswer === 'manual') {{
                showAllCategories(txnId, description, window._allCategories || [], 'No problem — pick the category:');
                return;
            }}
            
            // Show thinking state
            actionCell.innerHTML = `
                <div style="padding:8px;text-align:center;">
                    <div style="color:var(--primary);font-size:13px;font-weight:600;">Zane is checking...</div>
                </div>`;
            
            try {{
                const payload = {{ description, debit, credit, date }};
                if (clarificationAnswer) payload.clarification_answer = clarificationAnswer;
                
                const response = await fetch('/api/banking/zane-suggest', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(payload)
                }});
                
                const data = await response.json();
                
                // Store categories globally
                if (data.all_categories) window._allCategories = data.all_categories;
                
                // Zane asks with clickable plain-language options
                if (data.success && data.needs_clarification && data.options) {{
                    let optionsHtml = '';
                    const safeDesc = description.replace(/'/g, "\\\\'");
                    data.options.forEach(opt => {{
                        if (opt.value === 'manual') {{
                            // "None of these" -> show full dropdown
                            optionsHtml += `
                                <button onclick="showAllCategories('${{txnId}}','${{safeDesc}}',window._allCategories||[],'Pick the category:')"
                                        style="padding:8px 14px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;cursor:pointer;font-size:12px;margin:3px;">
                                    ${{opt.label}}
                                </button>`;
                        }} else {{
                            // Plain language option -> send back to Zane to map to GL category
                            optionsHtml += `
                                <button onclick="askZaneBank('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}', '${{opt.label}}')"
                                        style="padding:8px 14px;background:var(--primary);color:white;border:none;border-radius:6px;cursor:pointer;font-size:12px;margin:3px;">
                                    ${{opt.label}}
                                </button>`;
                        }}
                    }});
                    
                    actionCell.innerHTML = `
                        <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:260px;position:relative;">
                            <button onclick="resetAskZane('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                                    style="position:absolute;top:6px;right:8px;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:4px;line-height:1;" 
                                    title="Close">✕</button>
                            <div style="font-size:14px;font-weight:600;color:#8b5cf6;margin-bottom:10px;padding-right:20px;">
                                ${{data.question}}
                            </div>
                            <div style="display:flex;gap:4px;flex-wrap:wrap;">
                                ${{optionsHtml}}
                            </div>
                        </div>`;
                    return;
                }}
                
                // Safety: if clarification but no options came through, show dropdown
                if (data.success && data.needs_clarification) {{
                    showAllCategories(txnId, description, data.all_categories || [], data.question || 'Pick the category:');
                    return;
                }}
                
                // CASE 3: Zane knows the answer — show confirm
                if (data.success && data.category) {{
                    const confText = data.confidence >= 0.85 ? 'High confidence' : data.confidence >= 0.6 ? 'Medium' : 'Low';
                    const learnedBadge = data.source === 'learned' ? ' <span style="background:var(--green);color:white;padding:2px 6px;border-radius:3px;font-size:10px;">Learned</span>' : data.source === 'invoice_match' ? ' <span style="background:#22d3ee;color:black;padding:2px 6px;border-radius:3px;font-size:10px;">Invoice Match</span>' : data.source === 'expense_split_match' ? ' <span style="background:#f59e0b;color:black;padding:2px 6px;border-radius:3px;font-size:10px;">Scan Split Match</span>' : '';
                    const vatWarning = data.vat_warning ? `<div style="background:#fef3c7;border-left:3px solid #f59e0b;padding:6px 8px;border-radius:4px;font-size:11px;color:#000;margin-top:8px;">${{data.vat_warning}}</div>` : '';
                    
                    // If this is a split match, show Split button as primary action
                    let actionButtons = '';
                    if (data.has_split_match && data.matched_splits) {{
                        // Store matched data for the split modal
                        window._pendingSplitMatch = {{
                            expense_id: data.matched_expense_id || '',
                            splits: data.matched_splits || []
                        }};
                        actionButtons = `
                            <button onclick="openSplitWithMatch('${{txnId}}', '${{description.replace(/'/g, "\\\\'")}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                                    style="padding:7px 16px;font-size:12px;background:#f59e0b;border:none;color:black;border-radius:6px;cursor:pointer;font-weight:600;">
                                ✂️ Gebruik Split
                            </button>
                            <button onclick="categorizeTransaction('${{txnId}}', '${{data.category}}', '${{description.replace(/'/g, "\\\\'")}}')" 
                                    style="padding:7px 16px;font-size:12px;background:var(--green);border:none;color:white;border-radius:6px;cursor:pointer;font-weight:600;">
                                As een boek
                            </button>
                            <button onclick="showAllCategories('${{txnId}}', '${{description.replace(/'/g, "\\\\'")}}')" 
                                    style="padding:7px 16px;font-size:12px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;cursor:pointer;">
                                Ander
                            </button>`;
                    }} else {{
                        actionButtons = `
                            <button onclick="categorizeTransaction('${{txnId}}', '${{data.category}}', '${{description.replace(/'/g, "\\\\'")}}')" 
                                    style="padding:7px 16px;font-size:12px;background:var(--green);border:none;color:white;border-radius:6px;cursor:pointer;font-weight:600;">
                                Yes, Allocate
                            </button>
                            <button onclick="openSplitModal('${{txnId}}', '${{description.replace(/'/g, "\\\\'")}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                                    style="padding:7px 16px;font-size:12px;background:rgba(245,158,11,0.2);border:1px solid #f59e0b;color:#f59e0b;border-radius:6px;cursor:pointer;">
                                Split
                            </button>
                            <button onclick="showAllCategories('${{txnId}}', '${{description.replace(/'/g, "\\\\'")}}')" 
                                    style="padding:7px 16px;font-size:12px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;cursor:pointer;">
                                Different category
                            </button>`;
                    }}
                    
                    actionCell.innerHTML = `
                        <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:260px;position:relative;">
                            <button onclick="resetAskZane('${{txnId}}', '${{description.replace(/'/g, "\\\\'")}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                                    style="position:absolute;top:6px;right:8px;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:4px;line-height:1;" 
                                    title="Close">✕</button>
                            <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px;">${{confText}}${{learnedBadge}}</div>
                            <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:4px;">${{data.category}}</div>
                            <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;line-height:1.4;">${{data.reason}}</div>
                            ${{vatWarning}}
                            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
                                ${{actionButtons}}
                            </div>
                        </div>`;
                    row.dataset.categories = JSON.stringify(data.all_categories || []);
                }} else {{
                    showAllCategories(txnId, description, data.all_categories, data.reason || 'Not sure — please pick from the list.');
                }}
                
            }} catch (err) {{
                const safeDesc = description.replace(/'/g, "\\'");
                actionCell.innerHTML = `<div style="color:var(--red);font-size:12px;position:relative;padding-right:22px;">
                    <button onclick="resetAskZane('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                            style="position:absolute;top:-2px;right:0;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:14px;line-height:1;" title="Close">✕</button>
                    Could not analyze — <a href="#" onclick="askZaneBank('${{txnId}}','${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}');return false;" style="color:var(--primary);">try again</a></div>`;
            }}
        }}
        
        // Reset Ask Zane popup back to original buttons
        function resetAskZane(txnId, description, debit, credit, date) {{
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            const safeDesc = description.replace(/'/g, "\\'");
            const catOptions = (window._allCategories || []).map(c => `<option value="${{c}}">${{c}}</option>`).join('');
            actionCell.innerHTML = `
                <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center;">
                    <button onclick="askZaneBank('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}')" class="btn" style="padding:7px 14px;font-size:12px;background:var(--primary);border:none;color:white;border-radius:6px;font-weight:600;">Ask Zane</button>
                    <select class="form-input" style="width:120px;padding:4px;font-size:11px;" onchange="categorizeTransaction('${{txnId}}', this.value, '${{safeDesc}}')">
                        <option value="">Manual...</option>
                        ${{catOptions}}
                    </select>
                </div>`;
        }}
        
        function showSearchableCategories(txnId, description, cats, hint) {{
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            if (!cats || !cats.length) cats = window._allCategories || [];
            const safeDesc = description.replace(/'/g, "\\\\'");
            const uid = 'sc_' + txnId;
            
            // Get debit/credit from the row for resetAskZane
            const tds = row.querySelectorAll('td');
            const debitText = tds[2]?.textContent?.replace(/[^0-9.]/g, '') || '0';
            const creditText = tds[3]?.textContent?.replace(/[^0-9.]/g, '') || '0';
            const dateText = tds[0]?.textContent?.trim() || '';
            
            actionCell.innerHTML = `
                <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:220px;max-width:350px;position:relative;">
                    <button onclick="resetAskZane('${{txnId}}', '${{safeDesc}}', ${{debitText}}, ${{creditText}}, '${{dateText}}')" 
                            style="position:absolute;top:6px;right:8px;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:4px;line-height:1;z-index:1;" 
                            title="Close">✕</button>
                    ${{hint ? `<div style="font-size:12px;color:#8b5cf6;margin-bottom:8px;line-height:1.4;padding-right:20px;">${{hint}}</div>` : ''}}
                    <input type="text" id="${{uid}}_search" placeholder="Type to search categories..." 
                        style="width:100%;padding:8px 12px;border-radius:6px;border:2px solid rgba(139,92,246,0.3);background:var(--input-bg);color:var(--text);font-size:13px;box-sizing:border-box;margin-bottom:6px;"
                        oninput="filterCats('${{uid}}')">
                    <div id="${{uid}}_list" style="max-height:200px;overflow-y:auto;border:1px solid var(--border);border-radius:6px;background:var(--card);">
                    </div>
                </div>`;
            
            // Populate list
            const listEl = document.getElementById(uid + '_list');
            window['_cats_' + uid] = cats;
            renderCatList(uid, cats, txnId, safeDesc);
            
            setTimeout(() => document.getElementById(uid + '_search')?.focus(), 100);
        }}
        
        function renderCatList(uid, cats, txnId, safeDesc) {{
            const listEl = document.getElementById(uid + '_list');
            if (!listEl) return;
            listEl.innerHTML = cats.map(c => 
                `<div onclick="categorizeTransaction('${{txnId}}', '${{c.replace(/'/g, "\\\\'")}}', '${{safeDesc}}')" 
                      style="padding:8px 12px;cursor:pointer;font-size:13px;border-bottom:1px solid var(--border);color:var(--text);transition:background 0.15s;"
                      onmouseover="this.style.background='rgba(139,92,246,0.15)'" 
                      onmouseout="this.style.background='transparent'">${{c}}</div>`
            ).join('');
            if (!cats.length) listEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);font-size:12px;text-align:center;">No matching categories</div>';
        }}
        
        function filterCats(uid) {{
            const search = document.getElementById(uid + '_search')?.value.toLowerCase() || '';
            const allCats = window['_cats_' + uid] || [];
            const filtered = search ? allCats.filter(c => c.toLowerCase().includes(search)) : allCats;
            const txnId = uid.replace('sc_', '');
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const desc = row?.querySelector('td:nth-child(2)')?.textContent?.trim() || '';
            renderCatList(uid, filtered, txnId, desc.replace(/'/g, "\\\\'"));
        }}
        
        function showAllCategories(txnId, description, categoriesFromApi, message) {{
            let cats = categoriesFromApi;
            if (!cats || !cats.length) {{
                const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
                if (row && row.dataset.categories) {{
                    try {{ cats = JSON.parse(row.dataset.categories); }} catch(e) {{}}
                }}
            }}
            if (!cats || !cats.length) cats = window._allCategories || [];
            showSearchableCategories(txnId, description, cats, message || '');
        }}
        
        async function bulkApprove() {{
            if (!confirm('Approve all {auto_count} auto-matched transactions?')) return;
            
            const rows = document.querySelectorAll('#section-auto tbody tr[data-id]');
            let approved = 0;
            
            for (const row of rows) {{
                const id = row.dataset.id;
                const btn = row.querySelector('button');
                if (btn) {{
                    const category = btn.onclick.toString().match(/approveMatch\\('.*?',\\s*'(.*?)'\\)/)?.[1];
                    if (category) {{
                        try {{
                            await fetch('/api/banking/categorize', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify({{id, category, description: ''}})
                            }});
                            approved++;
                            row.style.display = 'none';
                        }} catch(e) {{}}
                    }}
                }}
            }}
            
            alert(`✅ Approved ${{approved}} transactions!`);
            location.reload();
        }}
        
        function updateCounts() {{
            // Live-update the HUD counters at the top of the page when a transaction is allocated.
            // Counts only rows that are NOT yet allocated in this session (data-allocated attr unset).
            try {{
                const total = {total_count};
                
                function liveRows(secId) {{
                    return document.querySelectorAll('#' + secId + ' tbody tr[data-id]:not([data-allocated])');
                }}
                
                const autoRows = liveRows('section-auto');
                const sugRows = liveRows('section-suggested');
                const needsRows = liveRows('section-needs');
                
                const autoCount = autoRows.length;
                const sugCount = sugRows.length;
                const needsCount = needsRows.length;
                const doneCount = total - (autoCount + sugCount + needsCount);
                
                // Sum unmatched debit/credit only on still-open rows (auto + suggested + needs)
                let unmatchedDr = 0, unmatchedCr = 0;
                [autoRows, sugRows, needsRows].forEach(set => {{
                    set.forEach(r => {{
                        unmatchedDr += parseFloat(r.dataset.debit || 0) || 0;
                        unmatchedCr += parseFloat(r.dataset.credit || 0) || 0;
                    }});
                }});
                
                const matchPct = Math.round((doneCount / Math.max(total, 1)) * 100);
                
                // Update stat-cards (the 4 big number cards above the tabs)
                const sAuto = document.getElementById('statAuto');
                const sSug = document.getElementById('statSuggested');
                const sNeeds = document.getElementById('statNeeds');
                const sDone = document.getElementById('statDone');
                if (sAuto) sAuto.textContent = String(autoCount);
                if (sSug) sSug.textContent = String(sugCount);
                if (sNeeds) sNeeds.textContent = String(needsCount);
                if (sDone) sDone.textContent = String(doneCount);
                
                // Update tab counters (the small pill counters inside the tabs)
                const tAuto = document.getElementById('tabAuto');
                const tSug = document.getElementById('tabSuggested');
                const tNeeds = document.getElementById('tabNeeds');
                const tDone = document.getElementById('tabDone');
                if (tAuto) tAuto.textContent = String(autoCount);
                if (tSug) tSug.textContent = String(sugCount);
                if (tNeeds) tNeeds.textContent = String(needsCount);
                if (tDone) tDone.textContent = String(doneCount);
                
                function fmtMoney(v) {{
                    return 'R ' + Number(v).toLocaleString('en-ZA', {{minimumFractionDigits:2, maximumFractionDigits:2}});
                }}
                
                // Update each HUD flank item by matching its label text
                const hudItems = document.querySelectorAll('.j-hud-wrap .j-fi');
                hudItems.forEach(item => {{
                    const lbl = item.querySelector('.j-fl');
                    const val = item.querySelector('.j-fv');
                    if (!lbl || !val) return;
                    const t = (lbl.textContent || '').trim().toUpperCase();
                    if (t === 'TRANSACTIONS') val.textContent = String(total);
                    else if (t === 'RECONCILED') val.textContent = String(doneCount);
                    else if (t === 'AUTO MATCHED') val.textContent = String(autoCount);
                    else if (t === 'SUGGESTED') val.textContent = String(sugCount);
                    else if (t === 'NEEDS REVIEW') val.textContent = String(needsCount);
                    else if (t === 'UNMATCHED DR') val.textContent = fmtMoney(unmatchedDr);
                    else if (t === 'UNMATCHED CR') val.textContent = fmtMoney(unmatchedCr);
                    else if (t === 'MATCH RATE') val.textContent = matchPct + '%';
                }});
                
                // Update the alert ticker (needs review banner) — hide it if everything done
                const ticker = document.querySelector('.j-hud-wrap .j-ticker');
                if (ticker) {{
                    if (needsCount === 0) {{
                        ticker.style.display = 'none';
                    }} else {{
                        const msg = ticker.querySelector('.jt-msg');
                        if (msg) msg.innerHTML = needsCount + ' transactions need attention &mdash; ' + fmtMoney(unmatchedDr) + ' debits, ' + fmtMoney(unmatchedCr) + ' credits unmatched';
                    }}
                }}
            }} catch(e) {{
                // Silent fail — counter is cosmetic, never break the page
                console.warn('updateCounts failed', e);
            }}
        }}
        
        async function deleteImport() {{
            const sel = document.getElementById('importBatchSelect');
            const batch = sel ? sel.value : '';
            if (!batch) {{ alert('Please select an import to delete first.'); return; }}
            const label = sel.options[sel.selectedIndex].text;
            if (!confirm(`Delete the UNALLOCATED transactions from this import?\\n\\n${{label}}\\n\\nAllocated transactions are kept and not touched. This cannot be undone.`)) return;
            try {{
                const response = await fetch('/api/banking/delete-import', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ batch: batch }})
                }});
                const data = await response.json();
                if (data.success) {{
                    alert(`✅ ${{data.message}}`);
                    location.reload();
                }} else {{
                    alert('❌ ' + data.error);
                }}
            }} catch (err) {{
                alert('❌ Delete failed: ' + err.message);
            }}
        }}
        
        async function deleteAllTransactions() {{
            const count = {len(all_transactions)};
            if (!confirm(`⚠️ Delete ALL ${{count}} bank transactions?\\n\\nThis cannot be undone. You can re-import after.`)) return;
            if (!confirm(`Are you sure? This will delete ${{count}} transactions permanently.`)) return;
            
            try {{
                const response = await fetch('/api/banking/delete-all', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }});
                const data = await response.json();
                if (data.success) {{
                    alert(`✅ ${{data.message}}`);
                    location.reload();
                }} else {{
                    alert('❌ ' + data.error);
                }}
            }} catch (err) {{
                alert('❌ Delete failed: ' + err.message);
            }}
        }}
        
        async function resetPatterns() {{
            if (!confirm('Reset all learned bank patterns?\\n\\nZane will forget all previously learned categorizations and re-learn from your next actions.')) return;
            try {{
                const response = await fetch('/api/banking/reset-patterns', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }});
                const data = await response.json();
                if (data.success) {{
                    alert('✅ ' + data.message);
                }} else {{
                    alert('❌ ' + data.error);
                }}
            }} catch (err) {{
                alert('❌ Reset failed: ' + err.message);
            }}
        }}
        
        function filterBankTransactions(query) {{
            const q = query.toLowerCase().trim();
            const sections = ['section-auto', 'section-suggested', 'section-needs', 'section-done'];
            sections.forEach(secId => {{
                const rows = document.querySelectorAll('#' + secId + ' tbody tr[data-id]');
                rows.forEach(row => {{
                    if (!q) {{ row.style.display = ''; return; }}
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(q) ? '' : 'none';
                }});
            }});
        }}
    
        async function uploadStatement(file) {{
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            const dFrom = document.getElementById('importDateFrom');
            const dTo = document.getElementById('importDateTo');
            if (dFrom && dFrom.value) formData.append('date_from', dFrom.value);
            if (dTo && dTo.value) formData.append('date_to', dTo.value);
            
            // Show loading
            const btn = event.target.closest('label');
            const originalText = btn.innerHTML;
            const isPDF = file.name.toLowerCase().endsWith('.pdf');
            btn.innerHTML = isPDF ? '🤖 AI Reading PDF... (1-3 min)' : '⏳ Importing...';
            
            try {{
                const response = await fetch('/api/banking/import', {{
                    method: 'POST',
                    body: formData
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    const stats = data.stats || {{}};
                    let msg = `✅ Imported ${{stats.total || 0}} transactions!\\n\\n` +
                          `🤖 Auto-matched: ${{stats.auto_matched || 0}}\\n` +
                          `💡 Suggested: ${{stats.suggested || 0}}\\n` +
                          `❓ Needs you: ${{stats.needs_attention || 0}}`;
                    if (stats.out_of_range_skipped) {{
                        msg += `\\n📅 Skipped (outside date range): ${{stats.out_of_range_skipped}}`;
                    }}
                    if ((stats.total || 0) === 0) {{
                        msg += `\\n\\n🔎 Diagnostics: ${{stats.rows_parsed || 0}} rows parsed`;
                        if (stats.duplicates_skipped) msg += `, ${{stats.duplicates_skipped}} duplicates`;
                        if (stats.row_errors) msg += `, ${{stats.row_errors}} row errors`;
                        msg += `\\nFile: ${{stats.filename || '?'}} | Standard Bank format: ${{stats.sb_prov_detected ? 'yes' : 'no'}}`;
                        if (stats.row_error_sample) msg += `\\nFirst error: ${{stats.row_error_sample}}`;
                    }}
                    alert(msg);
                    location.reload();
                }} else {{
                    alert('❌ ' + data.error);
                }}
            }} catch (err) {{
                alert('❌ Upload failed');
            }} finally {{
                btn.innerHTML = originalText;
            }}
        }}
        </script>
        
        <!-- ═══ SPLIT TRANSACTION MODAL ═══ -->
        <div id="splitOverlay" class="split-overlay" onclick="if(event.target===this)closeSplitModal()">
            <div class="split-modal">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                    <h3>✂️ Split Transaction</h3>
                    <button onclick="closeSplitModal()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:22px;padding:2px 8px;">✕</button>
                </div>
                <div id="splitTxnInfo" style="background:rgba(99,102,241,0.08);border-radius:8px;padding:12px;margin-bottom:15px;">
                    <div id="splitDesc" style="font-size:14px;font-weight:600;color:var(--text);"></div>
                    <div style="display:flex;gap:15px;margin-top:6px;">
                        <span id="splitDate" style="font-size:12px;color:var(--text-muted);"></span>
                        <span id="splitAmount" style="font-size:14px;font-weight:700;"></span>
                    </div>
                </div>
                
                <!-- Matched expense from scan -->
                <div id="splitMatchedExpense" style="display:none;"></div>
                
                <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;font-weight:600;">VERDEEL NA KATEGORIEË:</div>
                <div id="splitLines"></div>
                
                <button onclick="addSplitLine()" style="padding:6px 14px;font-size:12px;background:rgba(99,102,241,0.15);border:1px solid rgba(99,102,241,0.3);color:var(--primary);border-radius:6px;cursor:pointer;margin:8px 0;">+ Voeg lyn by</button>
                
                <div id="splitBalanceInfo" class="split-balance"></div>
                
                <div style="display:flex;gap:10px;margin-top:15px;">
                    <button id="splitSaveBtn" onclick="saveSplitAllocation()" class="btn btn-primary" style="flex:1;padding:12px;font-size:14px;font-weight:700;" disabled>💾 Save Split</button>
                    <button onclick="closeSplitModal()" class="btn btn-secondary" style="padding:12px 20px;">Kanselleer</button>
                </div>
            </div>
        </div>
        
        <script>
        // ═══════════════════════════════════════════════════════════
        // SPLIT TRANSACTION LOGIC
        // ═══════════════════════════════════════════════════════════
        let _splitTxnId = '';
        let _splitTotalAmount = 0;
        let _splitIsDebit = true;
        let _splitLineCount = 0;
        let _splitMatchedExpenseId = '';
        let _splitAllCategories = {json_cat_list};
        let _entityCustomers = {_entity_json_customers};
        let _entitySuppliers = {_entity_json_suppliers};
        
        function openSplitModal(txnId, desc, debit, credit, date) {{
            _splitTxnId = txnId;
            _splitIsDebit = debit > 0;
            _splitTotalAmount = _splitIsDebit ? debit : credit;
            _splitLineCount = 0;
            _splitMatchedExpenseId = '';
            
            document.getElementById('splitDesc').textContent = desc;
            document.getElementById('splitDate').textContent = date;
            document.getElementById('splitAmount').textContent = 'R ' + _splitTotalAmount.toFixed(2);
            document.getElementById('splitAmount').style.color = _splitIsDebit ? 'var(--red)' : 'var(--green)';
            document.getElementById('splitLines').innerHTML = '';
            document.getElementById('splitMatchedExpense').style.display = 'none';
            document.getElementById('splitMatchedExpense').innerHTML = '';
            
            // Start with 2 empty lines
            addSplitLine();
            addSplitLine();
            updateSplitBalance();
            
            document.getElementById('splitOverlay').classList.add('active');
            
            // Check for matching scanned expenses
            checkSplitExpenseMatch(txnId, _splitTotalAmount, date);
        }}
        
        function closeSplitModal() {{
            document.getElementById('splitOverlay').classList.remove('active');
        }}
        
        function buildCategoryOptions() {{
            return _splitAllCategories.map(c => `<option value="${{c}}">${{c}}</option>`).join('');
        }}
        
        function addSplitLine(category, amount) {{
            _splitLineCount++;
            const idx = _splitLineCount;
            const catVal = category || '';
            const amtVal = amount || '';
            const catOptions = buildCategoryOptions();
            const selectedAttr = catVal ? '' : '';
            
            const html = `
                <div class="split-line" id="splitLine_${{idx}}">
                    <select id="splitCat_${{idx}}" onchange="updateSplitBalance()">
                        <option value="">-- Kies kategorie --</option>
                        ${{catOptions}}
                    </select>
                    <input type="number" id="splitAmt_${{idx}}" step="0.01" min="0" placeholder="0.00" value="${{amtVal}}" oninput="updateSplitBalance()">
                    <button class="remove-split" onclick="removeSplitLine(${{idx}})" title="Verwyder">✕</button>
                </div>
            `;
            document.getElementById('splitLines').insertAdjacentHTML('beforeend', html);
            
            // Set selected category if provided
            if (catVal) {{
                const sel = document.getElementById('splitCat_' + idx);
                if (sel) {{
                    for (let opt of sel.options) {{
                        if (opt.value === catVal) {{ opt.selected = true; break; }}
                    }}
                    // Fuzzy match if exact didn't work
                    if (!sel.value) {{
                        const lower = catVal.toLowerCase();
                        for (let opt of sel.options) {{
                            if (opt.value.toLowerCase().includes(lower) || lower.includes(opt.value.toLowerCase())) {{
                                opt.selected = true; break;
                            }}
                        }}
                    }}
                }}
            }}
            
            updateSplitBalance();
        }}
        
        function removeSplitLine(idx) {{
            const el = document.getElementById('splitLine_' + idx);
            if (el) el.remove();
            updateSplitBalance();
        }}
        
        function getSplitLines() {{
            const lines = [];
            document.querySelectorAll('.split-line').forEach(row => {{
                const selects = row.querySelectorAll('select');
                const inputs = row.querySelectorAll('input[type=number]');
                if (selects.length && inputs.length) {{
                    const cat = selects[0].value;
                    const amt = parseFloat(inputs[0].value) || 0;
                    if (cat && amt > 0) {{
                        lines.push({{ category: cat, amount: amt }});
                    }}
                }}
            }});
            return lines;
        }}
        
        function updateSplitBalance() {{
            const lines = getSplitLines();
            const total = lines.reduce((s, l) => s + l.amount, 0);
            const diff = _splitTotalAmount - total;
            const el = document.getElementById('splitBalanceInfo');
            const btn = document.getElementById('splitSaveBtn');
            
            if (Math.abs(diff) < 0.01 && lines.length >= 2) {{
                el.className = 'split-balance balanced';
                el.innerHTML = `✅ Gebalanseer — R${{total.toFixed(2)}} van R${{_splitTotalAmount.toFixed(2)}}`;
                btn.disabled = false;
                btn.style.opacity = '1';
            }} else {{
                el.className = 'split-balance unbalanced';
                const diffAbs = Math.abs(diff).toFixed(2);
                if (lines.length < 2) {{
                    el.innerHTML = `⚠️ Minimum 2 lyne nodig`;
                }} else if (diff > 0) {{
                    el.innerHTML = `⚠️ Nog R${{diffAbs}} oor om te verdeel (totaal: R${{_splitTotalAmount.toFixed(2)}})`;
                }} else {{
                    el.innerHTML = `❌ R${{diffAbs}} te veel — verminder bedrae (totaal: R${{_splitTotalAmount.toFixed(2)}})`;
                }}
                btn.disabled = true;
                btn.style.opacity = '0.5';
            }}
        }}
        
        async function checkSplitExpenseMatch(txnId, amount, date) {{
            // Ask server if there's a matching scanned expense
            try {{
                const resp = await fetch('/api/banking/find-matching-expense', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ amount, date, txn_id: txnId }})
                }});
                const data = await resp.json();
                if (data.success && data.match) {{
                    const m = data.match;
                    _splitMatchedExpenseId = m.expense_id || '';
                    
                    const container = document.getElementById('splitMatchedExpense');
                    let html = `<div class="split-matched-badge">🔗 Scanned receipt found: ${{m.supplier || 'Unknown'}} — R${{parseFloat(m.amount||0).toFixed(2)}} (${{m.date || ''}})</div>`;
                    
                    if (m.splits && m.splits.length > 1) {{
                        html += `<div style="background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);border-radius:8px;padding:10px;margin-bottom:12px;">`;
                        html += `<div style="font-size:12px;color:var(--green);font-weight:600;margin-bottom:6px;">📋 Hierdie slip was al gesplit — wil jy dieselfde splits gebruik?</div>`;
                        m.splits.forEach(sp => {{
                            html += `<div style="display:flex;justify-content:space-between;padding:3px 0;font-size:13px;"><span>${{sp.category}}</span><span style="font-weight:600;">R${{parseFloat(sp.amount).toFixed(2)}}</span></div>`;
                        }});
                        html += `<button onclick="useScanSplits()" style="margin-top:8px;padding:8px 16px;background:var(--green);color:white;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:600;width:100%;">✅ Gebruik hierdie splits</button>`;
                        html += `</div>`;
                    }} else {{
                        html += `<div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">Hierdie expense was nie gesplit nie — jy kan dit nou hier split.</div>`;
                    }}
                    
                    container.innerHTML = html;
                    container.style.display = 'block';
                    
                    // Store splits for reuse
                    window._matchedSplits = m.splits || [];
                }}
            }} catch(e) {{
                // No match found, that's fine
            }}
        }}
        
        function useScanSplits() {{
            if (!window._matchedSplits || !window._matchedSplits.length) return;
            
            // Clear existing lines
            document.getElementById('splitLines').innerHTML = '';
            _splitLineCount = 0;
            
            // Add lines from matched scan
            window._matchedSplits.forEach(sp => {{
                addSplitLine(sp.category, sp.amount);
            }});
            
            updateSplitBalance();
        }}
        
        // Open split modal with pre-populated data from a scan match (called by Zane suggest)
        function openSplitWithMatch(txnId, desc, debit, credit, date) {{
            // Open the modal first
            openSplitModal(txnId, desc, debit, credit, date);
            
            // Then pre-populate from matched splits if available
            if (window._pendingSplitMatch && window._pendingSplitMatch.splits) {{
                _splitMatchedExpenseId = window._pendingSplitMatch.expense_id || '';
                
                // Small delay to ensure modal is rendered
                setTimeout(() => {{
                    // Clear default empty lines
                    document.getElementById('splitLines').innerHTML = '';
                    _splitLineCount = 0;
                    
                    // Add matched splits
                    window._pendingSplitMatch.splits.forEach(sp => {{
                        addSplitLine(sp.category, sp.amount);
                    }});
                    
                    // Show matched badge
                    const container = document.getElementById('splitMatchedExpense');
                    container.innerHTML = `<div class="split-matched-badge">🔗 Splits van gescande slip gebruik</div>`;
                    container.style.display = 'block';
                    
                    updateSplitBalance();
                    window._pendingSplitMatch = null;
                }}, 200);
            }}
        }}
        
        async function saveSplitAllocation() {{
            const lines = getSplitLines();
            if (lines.length < 2) {{ alert('Minimum 2 lyne nodig'); return; }}
            
            const total = lines.reduce((s, l) => s + l.amount, 0);
            if (Math.abs(total - _splitTotalAmount) > 0.01) {{
                alert('Bedrae balanseer nie. Totaal moet R' + _splitTotalAmount.toFixed(2) + ' wees.');
                return;
            }}
            
            const btn = document.getElementById('splitSaveBtn');
            btn.disabled = true;
            btn.innerHTML = '⏳ Saving...';
            
            try {{
                const resp = await fetch('/api/banking/split-categorize', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        id: _splitTxnId,
                        splits: lines,
                        is_debit: _splitIsDebit,
                        matched_expense_id: _splitMatchedExpenseId || null
                    }})
                }});
                const data = await resp.json();
                
                if (data.success) {{
                    closeSplitModal();
                    
                    // Update the row in the table
                    const row = document.querySelector(`tr[data-id="${{_splitTxnId}}"]`);
                    if (row) {{
                        const cells = row.querySelectorAll('td');
                        const lastCell = cells[cells.length - 1];
                        let badges = '<span style="background:#f59e0b;color:black;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:700;">SPLIT</span> ';
                        lines.forEach(l => {{
                            badges += `<span style="background:rgba(99,102,241,0.2);color:var(--text);padding:3px 6px;border-radius:4px;font-size:10px;margin:2px;">${{l.category.substring(0,20)}} R${{l.amount.toFixed(2)}}</span> `;
                        }});
                        lastCell.innerHTML = badges;
                        row.style.background = 'rgba(16,185,129,0.15)';
                        row.style.transition = 'opacity 0.5s';
                        setTimeout(() => {{ row.style.opacity = '0.4'; }}, 2000);
                        setTimeout(() => row.remove(), 3000);
                    }}
                }} else {{
                    alert('❌ ' + (data.error || 'Split save failed'));
                }}
            }} catch(e) {{
                alert('❌ Split failed: ' + e.message);
            }} finally {{
                btn.disabled = false;
                btn.innerHTML = '💾 Save Split';
            }}
        }}
        </script>
        '''
        
        # -- JARVIS: Banking HUD header --
        if has_reactor_hud():
            _match_pct = int((done_count / max(total_count, 1)) * 100)
            _j_alert = ""
            if needs_count > 0:
                _j_alert = f'<div class="j-ticker"><b>&#9888; RECONCILE</b><span class="jt-msg">{needs_count} transactions need attention &mdash; {money(total_debit)} debits, {money(total_credit)} credits unmatched</span><a href="#needsSection" class="jt-act">REVIEW NOW &rarr;</a></div>'
            
            _hud = jarvis_hud_header(
                page_name="BANKING",
                page_count=f"{total_count} TRANSACTIONS",
                left_items=[
                    ("TRANSACTIONS", str(total_count), "c", "", ""),
                    ("RECONCILED", str(done_count), "g", "g", "g"),
                    ("AUTO MATCHED", str(auto_count), "c", "", ""),
                    ("SUGGESTED", str(suggested_count), "o", "o", ""),
                ],
                right_items=[
                    ("NEEDS REVIEW", str(needs_count), "r", "r", "r"),
                    ("UNMATCHED DR", money(total_debit), "o", "o", "o"),
                    ("UNMATCHED CR", money(total_credit), "g", "g", "g"),
                    ("MATCH RATE", f"{_match_pct}%", "c", "", ""),
                ],
                reactor_size="page",
                alert_html=_j_alert
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline(f"BANKING <b>{total_count} TXN</b>")
        
        return render_page("Banking", content, user, "banking")
    
    
    def _compute_recon(biz_id, stmt_open=None, stmt_close=None):
        """Engine for the bank reconciliation. Returns the two-sided figures plus the
        reconciling item lists. Used by BOTH the recon screen and the 'Ask Zane to
        explain' route, so the numbers Zane explains are exactly the numbers on screen.
        stmt_open/stmt_close are the statement's real balances entered by the user;
        they take priority over the imported running balance (some bank formats carry
        no per-line running balance)."""
        try:
            bank_code = str(gl(biz_id, "bank") or "1000")
        except Exception:
            bank_code = "1000"

        def _f(v):
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        # Statement side: imported bank transactions (movement + any running balance)
        txns = db.get("bank_transactions", {"business_id": biz_id}) or []
        txns.sort(key=lambda x: str(x.get("date", ""))[:10])
        bank_credits = sum(_f(t.get("credit")) for t in txns)
        bank_debits = sum(_f(t.get("debit")) for t in txns)
        bank_movement = bank_credits - bank_debits
        _with_bal = [t for t in txns if t.get("balance") not in (None, "")]

        # GL side: chart-of-accounts opening + journals on the bank account.
        # Opening-balance journals are folded into the OPENING (not the movement), so
        # they don't masquerade as "postings not on the statement", and the opening
        # reads correctly whether it lives in the COA field or in a journal.
        coa = db.get("chart_of_accounts", {"business_id": biz_id}) or []
        bank_acc = None
        for _a in coa:
            if str(_a.get("account_code", "")) == bank_code:
                bank_acc = _a
                break
        gl_opening = _f(bank_acc.get("opening_balance")) if bank_acc else 0.0
        journals = db.get("journals", {"business_id": biz_id}) or []
        bank_journals = [j for j in journals if str(j.get("account_code", "")) == bank_code]

        def _is_opening(j):
            _r = str(j.get("reference", "") or "").upper()
            _d = str(j.get("description", "") or "").lower()
            return _r.startswith("OPENING") or "opening balance" in _d
        opening_journals = [j for j in bank_journals if _is_opening(j)]
        move_journals = [j for j in bank_journals if not _is_opening(j)]
        gl_opening += sum(_f(j.get("debit")) - _f(j.get("credit")) for j in opening_journals)
        gl_dr = sum(_f(j.get("debit")) for j in move_journals)
        gl_cr = sum(_f(j.get("credit")) for j in move_journals)
        gl_movement = gl_dr - gl_cr
        gl_balance = gl_opening + gl_movement

        # Bank opening/closing: prefer the statement's real balances (entered by the
        # user), because some bank formats carry no per-line running balance. Fall back
        # to the imported running balance, then to the GL opening + movement.
        if stmt_close is not None:
            bank_closing = stmt_close
            bank_opening = stmt_open if stmt_open is not None else gl_opening
            have_bank_balance = True
        elif _with_bal:
            _first, _last = _with_bal[0], _with_bal[-1]
            bank_opening = _f(_first.get("balance")) - (_f(_first.get("credit")) - _f(_first.get("debit")))
            bank_closing = _f(_last.get("balance"))
            have_bank_balance = True
        else:
            bank_opening = gl_opening
            bank_closing = bank_opening + bank_movement
            have_bank_balance = False

        # Difference, decomposed so the arithmetic always ties
        difference = round(bank_closing - gl_balance, 2)
        opening_gap = round(bank_opening - gl_opening, 2)
        unalloc = [t for t in txns if not t.get("matched")]
        unalloc_net = round(sum(_f(t.get("credit")) - _f(t.get("debit")) for t in unalloc), 2)
        residual = round(difference - opening_gap - unalloc_net, 2)

        # Possible misplaced opening balance (Sage namespace e.g. 8400/000)
        misplaced = []
        for _a in coa:
            _c = str(_a.get("account_code", ""))
            _ob = _f(_a.get("opening_balance"))
            if _ob and _c != bank_code and ("8400" in _c or "/000" in _c or _c.endswith("/000")):
                misplaced.append((_a, _ob))

        # GL bank postings with no matching statement line (by amount + direction).
        # Opening-balance journals are excluded — they ARE the opening, not a missing line.
        from collections import Counter as _Counter
        _stmt_in = _Counter(round(_f(t.get("credit")), 2) for t in txns if _f(t.get("credit")) > 0)
        _stmt_out = _Counter(round(_f(t.get("debit")), 2) for t in txns if _f(t.get("debit")) > 0)
        gl_only = []
        for j in move_journals:
            _jd, _jc = _f(j.get("debit")), _f(j.get("credit"))
            if _jd > 0:
                _amt = round(_jd, 2)
                if _stmt_in.get(_amt, 0) > 0:
                    _stmt_in[_amt] -= 1
                else:
                    gl_only.append(j)
            elif _jc > 0:
                _amt = round(_jc, 2)
                if _stmt_out.get(_amt, 0) > 0:
                    _stmt_out[_amt] -= 1
                else:
                    gl_only.append(j)

        # Possible duplicate bank postings: the SAME reference booked more than once on
        # the bank account with the same amount (e.g. BNK-xxxx booked several times).
        # References are unique transaction ids, so a repeat is almost always a double-up.
        # Listed for review — the user decides what to reverse.
        from collections import defaultdict as _dd_dup
        _by_ref = _dd_dup(list)
        for j in move_journals:
            _ref = str(j.get("reference", "") or "").strip()
            if _ref:
                _ramt = round(_f(j.get("debit")) - _f(j.get("credit")), 2)
                _by_ref[(_ref, _ramt)].append(j)
        duplicates = []
        for (_ref, _ramt), _grp in _by_ref.items():
            if len(_grp) >= 2:
                duplicates.append({
                    "reference": _ref,
                    "description": str(_grp[0].get("description", "") or ""),
                    "date": str(_grp[0].get("date", "") or "")[:10],
                    "count": len(_grp),
                    "amount": _ramt,
                    "excess": round(_ramt * (len(_grp) - 1), 2),
                })
        duplicates.sort(key=lambda d: abs(d["excess"]), reverse=True)
        dup_excess_total = round(sum(abs(d["excess"]) for d in duplicates), 2)

        # Possible over-reversals: the SAME original posting reversed more than once.
        # The duplicate check above only catches an identical reference repeated; it misses
        # the case where one original (e.g. BNK-xxxx) was reversed twice under DIFFERENT
        # REV- references (REV-...-2f48a9 and REV-...-e63b9e). Resolve each REV- journal back
        # to the real original it reverses (anchored to a known reference, so suffixes
        # collapse to the same original), then flag any original carrying 2+ reversals.
        _known_refs = set()
        for _t in txns:
            _kr = str(_t.get("reference", "") or "").strip()
            if _kr:
                _known_refs.add(_kr)
        for _j in move_journals:
            _kr = str(_j.get("reference", "") or "").strip()
            if _kr and not _kr.upper().startswith("REV-"):
                _known_refs.add(_kr)

        def _reversal_target(_ref):
            _base = _ref[4:] if _ref[:4].upper() == "REV-" else _ref
            if _base in _known_refs:
                return _base
            _parts = _base.split("-")
            while len(_parts) > 1:
                _parts = _parts[:-1]
                _cand = "-".join(_parts)
                if _cand in _known_refs:
                    return _cand
            return _base

        _rev_by_target = _dd_dup(list)
        for _j in move_journals:
            _ref = str(_j.get("reference", "") or "").strip()
            if _ref and _ref.upper().startswith("REV-"):
                _tgt = _reversal_target(_ref)
                _ramt = round(abs(_f(_j.get("debit")) - _f(_j.get("credit"))), 2)
                _rev_by_target[(_tgt, _ramt)].append(_j)
        over_reversals = []
        for (_tgt, _ramt), _grp in _rev_by_target.items():
            if len(_grp) >= 2:
                over_reversals.append({
                    "reference": _tgt,
                    "description": str(_grp[0].get("description", "") or ""),
                    "date": str(_grp[0].get("date", "") or "")[:10],
                    "count": len(_grp),
                    "amount": _ramt,
                    "excess": round(_ramt * (len(_grp) - 1), 2),
                })
        over_reversals.sort(key=lambda d: abs(d["excess"]), reverse=True)
        over_rev_total = round(sum(abs(d["excess"]) for d in over_reversals), 2)

        return {
            "bank_code": bank_code, "have_bank_balance": have_bank_balance,
            "stmt_entered": stmt_close is not None,
            "bank_opening": bank_opening, "bank_closing": bank_closing,
            "gl_opening": gl_opening, "gl_balance": gl_balance,
            "difference": difference, "opening_gap": opening_gap,
            "unalloc_net": unalloc_net, "residual": residual,
            "unalloc": unalloc, "gl_only": gl_only, "misplaced": misplaced,
            "duplicates": duplicates, "dup_excess_total": dup_excess_total,
            "over_reversals": over_reversals, "over_rev_total": over_rev_total,
            "txns": txns,
        }

    def _find_orphaned_bank_allocations(biz_id):
        """Find bank-allocation records (references BNK-<id[:8]> or REV-BNK-<id[:8]>)
        whose source bank_transaction no longer exists — e.g. left behind when a
        statement was deleted and re-imported. Deterministic: a record is orphaned
        only when no bank_transaction id starts with the reference's prefix, never by
        amount. Returns the ids to delete per table plus the customer/supplier invoices
        whose paid status must be reset (their backing receipt/payment is being removed)."""
        txns = db.get("bank_transactions", {"business_id": biz_id}) or []
        live_prefixes = {str(t.get("id", ""))[:8] for t in txns if t.get("id")}

        def _prefix(ref):
            r = str(ref or "").strip()
            up = r.upper()
            if up.startswith("REV-BNK-"):
                rest = r[8:]
            elif up.startswith("BNK-"):
                rest = r[4:]
            else:
                return None
            return rest.split("-")[0][:8] if rest else None

        def _is_orphan_ref(ref):
            p = _prefix(ref)
            return bool(p) and p not in live_prefixes

        journals = db.get("journals", {"business_id": biz_id}) or []
        receipts = db.get("receipts", {"business_id": biz_id}) or []
        supplier_payments = db.get("supplier_payments", {"business_id": biz_id}) or []
        alloc_log = db.get("allocation_log", {"business_id": biz_id}) or []

        orphan_journal_ids = [j["id"] for j in journals if j.get("id") and _is_orphan_ref(j.get("reference"))]
        orphan_receipt_ids = [r["id"] for r in receipts if r.get("id") and _is_orphan_ref(r.get("reference"))]
        orphan_sp_ids = [s["id"] for s in supplier_payments if s.get("id") and _is_orphan_ref(s.get("reference"))]
        orphan_log_ids = [a["id"] for a in alloc_log if a.get("id") and _is_orphan_ref(a.get("reference"))]

        # Supplier invoices carry the BNK- ref in payment_reference — a precise link.
        supplier_invoices = db.get("supplier_invoices", {"business_id": biz_id}) or []
        reset_sinv = [s for s in supplier_invoices
                      if s.get("id") and str(s.get("status", "")).lower() == "paid"
                      and _is_orphan_ref(s.get("payment_reference"))]

        # Customer invoices have no BNK- ref — link via paid_via + a backing receipt
        # (customer_id + amount). Reset a banking-paid invoice only when NO surviving
        # (non-orphaned) receipt still backs it. Precise, and safe for partial repairs.
        live_receipt_keys = set()
        for r in receipts:
            if r.get("id") and not _is_orphan_ref(r.get("reference")):
                try:
                    live_receipt_keys.add((str(r.get("customer_id", "")), round(float(r.get("amount", 0) or 0), 2)))
                except Exception:
                    pass
        reset_inv = []
        for inv in (db.get("invoices", {"business_id": biz_id}) or []):
            if str(inv.get("paid_via", "")) != "banking_recon":
                continue
            if str(inv.get("status", "")).lower() != "paid":
                continue
            try:
                key = (str(inv.get("customer_id", "")), round(float(inv.get("paid_amount", 0) or 0), 2))
            except Exception:
                key = (str(inv.get("customer_id", "")), 0.0)
            if key not in live_receipt_keys:
                reset_inv.append(inv)

        return {
            "journal_ids": orphan_journal_ids,
            "receipt_ids": orphan_receipt_ids,
            "supplier_payment_ids": orphan_sp_ids,
            "log_ids": orphan_log_ids,
            "reset_invoices": reset_inv,
            "reset_supplier_invoices": reset_sinv,
        }

    @app.route("/api/banking/repair-orphaned-allocations", methods=["POST"])
    @login_required
    def banking_repair_orphaned():
        """Preview or execute removal of orphaned bank-allocation records (references whose
        source bank_transaction was deleted, e.g. after a re-import). Deletes the
        journals/receipts/supplier_payments/allocation_log and resets the paid status on the
        invoices those allocations had marked paid. Re-allocating the clean bank lines
        afterwards rebuilds everything correctly. mode='preview' only reports counts;
        mode='execute' (with confirm=true) performs the change."""
        try:
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            data = request.get_json(silent=True) or {}
            mode = (data.get("mode") or "preview").strip()
            found = _find_orphaned_bank_allocations(biz_id)
            counts = {
                "journals": len(found["journal_ids"]),
                "receipts": len(found["receipt_ids"]),
                "supplier_payments": len(found["supplier_payment_ids"]),
                "allocation_log": len(found["log_ids"]),
                "invoices_reset": len(found["reset_invoices"]),
                "supplier_invoices_reset": len(found["reset_supplier_invoices"]),
            }
            total = sum(counts.values())
            if mode != "execute":
                return jsonify({"success": True, "mode": "preview", "counts": counts, "total": total})
            if not data.get("confirm"):
                return jsonify({"success": False, "error": "Confirmation required"})

            deleted = {}
            for _tbl, _ids in (("journals", found["journal_ids"]),
                               ("receipts", found["receipt_ids"]),
                               ("supplier_payments", found["supplier_payment_ids"]),
                               ("allocation_log", found["log_ids"])):
                if _ids:
                    _s, _f = db.delete_many(_tbl, _ids, business_id=biz_id)
                    deleted[_tbl] = _s

            inv_reset = 0
            for inv in found["reset_invoices"]:
                try:
                    db.update("invoices", inv["id"],
                              {"status": "outstanding", "paid_date": "", "paid_amount": 0, "paid_via": ""}, biz_id)
                    inv_reset += 1
                except Exception as _e:
                    logger.warning(f"[REPAIR] invoice reset failed {inv.get('id')}: {_e}")
            sinv_reset = 0
            for sinv in found["reset_supplier_invoices"]:
                try:
                    db.update("supplier_invoices", sinv["id"],
                              {"status": "outstanding", "paid_date": "", "paid_amount": 0, "payment_reference": ""}, biz_id)
                    sinv_reset += 1
                except Exception as _e:
                    logger.warning(f"[REPAIR] supplier invoice reset failed {sinv.get('id')}: {_e}")

            logger.info(f"[REPAIR] biz {biz_id}: deleted {deleted}, reset {inv_reset} invoices, {sinv_reset} supplier invoices")
            return jsonify({"success": True, "mode": "execute",
                            "deleted": deleted, "invoices_reset": inv_reset,
                            "supplier_invoices_reset": sinv_reset})
        except Exception as e:
            logger.error(f"[REPAIR] failed: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/banking/reconcile")
    @login_required
    def banking_reconcile():
        """Direct two-sided bank reconciliation: the bank statement balance against the
        GL bank account balance, with every cent of the difference broken into the
        reconciling items that explain it (opening balance, unallocated statement lines,
        and GL bank postings that never came off the statement)."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return redirect("/banking")

        def _parg(name):
            _v = (request.args.get(name) or "").strip()
            if not _v:
                return None
            try:
                return float(_v.replace(",", ""))
            except Exception:
                return None
        _stmt_open_in = _parg("stmt_open")
        _stmt_close_in = _parg("stmt_close")
        R = _compute_recon(biz_id, _stmt_open_in, _stmt_close_in)
        bank_code = R["bank_code"]
        have_bank_balance = R["have_bank_balance"]
        stmt_entered = R["stmt_entered"]
        bank_opening = R["bank_opening"]
        bank_closing = R["bank_closing"]
        gl_opening = R["gl_opening"]
        gl_balance = R["gl_balance"]
        difference = R["difference"]
        opening_gap = R["opening_gap"]
        unalloc_net = R["unalloc_net"]
        residual = R["residual"]
        unalloc = R["unalloc"]
        gl_only = R["gl_only"]
        misplaced = R["misplaced"]
        duplicates = R["duplicates"]
        dup_excess_total = R["dup_excess_total"]
        over_reversals = R["over_reversals"]
        over_rev_total = R["over_rev_total"]
        bank_txns = R["txns"]

        def _f(v):
            try:
                return float(v or 0)
            except Exception:
                return 0.0

        # ── Build the page (inline styles only; English UI) ────────────────────────
        _reconciled = abs(difference) < 0.01
        _diff_color = "var(--green)" if _reconciled else "var(--red)"
        _bal_color = "var(--green)" if bank_closing >= 0 else "var(--red)"
        _gl_color = "var(--green)" if gl_balance >= 0 else "var(--red)"
        _og_color = "var(--green)" if abs(opening_gap) < 0.01 else "var(--red)"

        def _card(label, value, color, sub=""):
            _s = f'<div style="font-size:12px;color:var(--text-muted);margin-top:4px;">{sub}</div>' if sub else ""
            return ('<div class="card" style="flex:1;min-width:210px;">'
                    f'<div style="font-size:13px;color:var(--text-muted);">{label}</div>'
                    f'<div style="font-size:26px;font-weight:700;color:{color};font-variant-numeric:tabular-nums;">{money(value)}</div>'
                    f'{_s}</div>')

        cards = ('<div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px;">'
                 + _card("Bank statement balance", bank_closing, _bal_color,
                         ("From your entered statement closing balance" if stmt_entered else ("From the bank's running balance" if have_bank_balance else "Opening + movement (no running balance imported)")))
                 + _card("GL bank balance (code " + bank_code + ")", gl_balance, _gl_color, "Opening balance + journals on the bank account")
                 + _card("Difference", difference, _diff_color,
                         "Reconciled — the books match the bank" if _reconciled else "Bank minus books — accounted for below")
                 + '</div>')

        breakdown = ('<div class="card" style="margin-bottom:18px;">'
                     '<h3 style="margin:0 0 8px 0;">What makes up the difference</h3>'
                     '<p style="margin:0;color:var(--text-muted);font-size:13px;">'
                     f'Difference of <b style="color:{_diff_color};">{money(difference)}</b> = '
                     f'opening balance gap <b>{money(opening_gap)}</b> '
                     f'+ unallocated statement lines <b>{money(unalloc_net)}</b> ({len(unalloc)}) '
                     f'+ other GL bank postings <b>{money(residual)}</b>.</p></div>')

        # 1. Opening balance
        ob_rows = (f'<tr><td>Bank statement opening</td><td style="text-align:right;font-variant-numeric:tabular-nums;">{money(bank_opening)}</td></tr>'
                   f'<tr><td>GL opening on code {bank_code}</td><td style="text-align:right;font-variant-numeric:tabular-nums;">{money(gl_opening)}</td></tr>'
                   f'<tr><td><b>Opening gap</b></td><td style="text-align:right;font-variant-numeric:tabular-nums;color:{_og_color};"><b>{money(opening_gap)}</b></td></tr>')
        misplaced_html = ""
        if misplaced:
            _mr = "".join(
                f'<tr><td>Code {safe_string(str(_a.get("account_code","")))} — {safe_string(_a.get("account_name",""))}</td>'
                f'<td style="text-align:right;color:#f59e0b;font-variant-numeric:tabular-nums;">{money(_ob)}</td></tr>'
                for _a, _ob in misplaced)
            misplaced_html = ('<p style="margin:12px 0 4px 0;font-size:13px;color:#f59e0b;">Opening balances sit on Sage-style codes. '
                              'If the bank\'s opening balance was loaded here instead of code ' + bank_code + ', this is your gap:</p>'
                              '<table style="width:100%;font-size:13px;">' + _mr + '</table>')
        opening_section = (f'<details class="card" style="margin-bottom:14px;" {"open" if abs(opening_gap) >= 0.01 else ""}>'
                           f'<summary style="cursor:pointer;font-weight:600;">1. Opening balance &mdash; gap {money(opening_gap)}</summary>'
                           f'<table style="width:100%;font-size:13px;margin-top:8px;">{ob_rows}</table>{misplaced_html}</details>')

        # 2. Unallocated statement lines
        if unalloc:
            _ur = "".join(
                f'<tr><td style="white-space:nowrap;">{safe_string(str(t.get("date","-"))[:10])}</td>'
                f'<td>{safe_string(t.get("description","-"))}</td>'
                f'<td style="text-align:right;color:var(--red);font-variant-numeric:tabular-nums;">{money(_f(t.get("debit"))) if _f(t.get("debit")) > 0 else ""}</td>'
                f'<td style="text-align:right;color:var(--green);font-variant-numeric:tabular-nums;">{money(_f(t.get("credit"))) if _f(t.get("credit")) > 0 else ""}</td></tr>'
                for t in unalloc[:200])
            _umore = f'<p style="font-size:12px;color:var(--text-muted);">Showing first 200 of {len(unalloc)}.</p>' if len(unalloc) > 200 else ""
            unalloc_body = ('<table style="width:100%;font-size:13px;margin-top:8px;"><thead><tr>'
                            '<th style="text-align:left;">Date</th><th style="text-align:left;">Description</th>'
                            '<th style="text-align:right;">Out</th><th style="text-align:right;">In</th></tr></thead>'
                            f'<tbody>{_ur}</tbody></table>{_umore}'
                            '<p style="margin-top:8px;"><a href="/banking" class="btn btn-primary">Allocate these on the Banking page</a></p>')
        else:
            unalloc_body = '<p style="color:var(--text-muted);font-size:13px;margin-top:8px;">All statement lines are allocated to the GL.</p>'
        unalloc_section = (f'<details class="card" style="margin-bottom:14px;" {"open" if unalloc else ""}>'
                           f'<summary style="cursor:pointer;font-weight:600;">2. Unallocated statement lines &mdash; {len(unalloc)} ({money(unalloc_net)})</summary>'
                           '<p style="margin:8px 0 0 0;color:var(--text-muted);font-size:13px;">On the bank statement but not yet posted to the GL. '
                           'Allocate them (Ask Zane) to close this part of the gap.</p>'
                           f'{unalloc_body}</details>')

        # 3. GL bank postings with no statement line
        if gl_only:
            _gr = "".join(
                f'<tr><td style="white-space:nowrap;">{safe_string(str(j.get("date","-"))[:10])}</td>'
                f'<td>{safe_string(j.get("description","-"))}</td>'
                f'<td>{safe_string(j.get("reference","-"))}</td>'
                f'<td style="text-align:right;color:var(--green);font-variant-numeric:tabular-nums;">{money(_f(j.get("debit"))) if _f(j.get("debit")) > 0 else ""}</td>'
                f'<td style="text-align:right;color:var(--red);font-variant-numeric:tabular-nums;">{money(_f(j.get("credit"))) if _f(j.get("credit")) > 0 else ""}</td></tr>'
                for j in gl_only[:200])
            _gmore = f'<p style="font-size:12px;color:var(--text-muted);">Showing first 200 of {len(gl_only)}.</p>' if len(gl_only) > 200 else ""
            gl_only_body = ('<table style="width:100%;font-size:13px;margin-top:8px;"><thead><tr>'
                            '<th style="text-align:left;">Date</th><th style="text-align:left;">Description</th><th style="text-align:left;">Ref</th>'
                            '<th style="text-align:right;">Into bank</th><th style="text-align:right;">Out of bank</th></tr></thead>'
                            f'<tbody>{_gr}</tbody></table>{_gmore}')
        else:
            gl_only_body = '<p style="color:var(--text-muted);font-size:13px;margin-top:8px;">Every GL bank posting has a matching statement line.</p>'
        gl_only_section = (f'<details class="card" style="margin-bottom:14px;" {"open" if gl_only else ""}>'
                           f'<summary style="cursor:pointer;font-weight:600;">3. GL bank postings with no statement line &mdash; {len(gl_only)}</summary>'
                           '<p style="margin:8px 0 0 0;color:var(--text-muted);font-size:13px;">Posted to the bank account in the GL but not found on the statement (matched by amount). '
                           'Usually payments booked in Invoicing/Purchases, manual journals, or duplicates &mdash; check these for double-ups.</p>'
                           f'{gl_only_body}</details>')

        # 4. Possible duplicate postings (same reference booked more than once)
        if duplicates:
            _dr = "".join(
                f'<tr><td style="white-space:nowrap;">{safe_string(d.get("date","-"))}</td>'
                f'<td>{safe_string(d.get("description","-"))}</td>'
                f'<td>{safe_string(d.get("reference","-"))}</td>'
                f'<td style="text-align:center;font-variant-numeric:tabular-nums;">{d.get("count",0)}&times;</td>'
                f'<td style="text-align:right;font-variant-numeric:tabular-nums;">{money(abs(_f(d.get("amount"))))}</td>'
                f'<td style="text-align:right;color:var(--red);font-variant-numeric:tabular-nums;">{money(abs(_f(d.get("excess"))))}</td></tr>'
                for d in duplicates[:200])
            _dmore = f'<p style="font-size:12px;color:var(--text-muted);">Showing first 200 of {len(duplicates)}.</p>' if len(duplicates) > 200 else ""
            dup_body = ('<table style="width:100%;font-size:13px;margin-top:8px;"><thead><tr>'
                        '<th style="text-align:left;">Date</th><th style="text-align:left;">Description</th><th style="text-align:left;">Ref</th>'
                        '<th style="text-align:center;">Times</th><th style="text-align:right;">Each</th><th style="text-align:right;">Excess</th></tr></thead>'
                        f'<tbody>{_dr}</tbody></table>{_dmore}')
        else:
            dup_body = '<p style="color:var(--text-muted);font-size:13px;margin-top:8px;">No reference is booked more than once on the bank account.</p>'
        dup_section = (f'<details class="card" style="margin-bottom:14px;" {"open" if duplicates else ""}>'
                       f'<summary style="cursor:pointer;font-weight:600;">4. Possible duplicate postings &mdash; {len(duplicates)} (excess {money(dup_excess_total)})</summary>'
                       '<p style="margin:8px 0 0 0;color:var(--text-muted);font-size:13px;">The same reference is booked more than once on the bank account. '
                       'Each extra copy is likely a double-up &mdash; review and reverse the duplicates. "Excess" is the doubled-up value (each &times; extra copies).</p>'
                       f'{dup_body}</details>')

        # 5. Possible over-reversals (the same original reversed more than once)
        if over_reversals:
            _or = "".join(
                f'<tr><td style="white-space:nowrap;">{safe_string(d.get("date","-"))}</td>'
                f'<td>{safe_string(d.get("description","-"))}</td>'
                f'<td>{safe_string(d.get("reference","-"))}</td>'
                f'<td style="text-align:center;font-variant-numeric:tabular-nums;">{d.get("count",0)}&times;</td>'
                f'<td style="text-align:right;font-variant-numeric:tabular-nums;">{money(abs(_f(d.get("amount"))))}</td>'
                f'<td style="text-align:right;color:var(--red);font-variant-numeric:tabular-nums;">{money(abs(_f(d.get("excess"))))}</td></tr>'
                for d in over_reversals[:200])
            _omore = f'<p style="font-size:12px;color:var(--text-muted);">Showing first 200 of {len(over_reversals)}.</p>' if len(over_reversals) > 200 else ""
            over_rev_body = ('<table style="width:100%;font-size:13px;margin-top:8px;"><thead><tr>'
                             '<th style="text-align:left;">Date</th><th style="text-align:left;">Description</th><th style="text-align:left;">Original ref</th>'
                             '<th style="text-align:center;">Reversals</th><th style="text-align:right;">Each</th><th style="text-align:right;">Excess</th></tr></thead>'
                             f'<tbody>{_or}</tbody></table>{_omore}')
        else:
            over_rev_body = '<p style="color:var(--text-muted);font-size:13px;margin-top:8px;">No original is reversed more than once on the bank account.</p>'
        over_rev_section = (f'<details class="card" style="margin-bottom:14px;" {"open" if over_reversals else ""}>'
                            f'<summary style="cursor:pointer;font-weight:600;">5. Possible over-reversals &mdash; {len(over_reversals)} (excess {money(over_rev_total)})</summary>'
                            '<p style="margin:8px 0 0 0;color:var(--text-muted);font-size:13px;">The same original posting was reversed more than once (including via different REV- references that section 4 cannot see). '
                            'The first reversal cancels the original; each extra reversal over-corrects. "Excess" is the over-reversed value (each &times; extra reversals).</p>'
                            f'{over_rev_body}</details>')

        # Imported bank statement with running balance (the source data, for verification)
        if bank_txns:
            # Per-line running balance. Use the bank's own balance when a line carries
            # one; otherwise reconstruct it forward from the opening so formats without a
            # per-line balance (e.g. Standard Bank) still show a running balance, not "—".
            _eff_bals = []
            _run = bank_opening
            for _t in bank_txns:
                _stored = _t.get("balance")
                if _stored not in (None, ""):
                    _run = _f(_stored)
                else:
                    _run = _run + _f(_t.get("credit")) - _f(_t.get("debit"))
                _eff_bals.append(_run)
            _sr = "".join(
                f'<tr><td style="white-space:nowrap;">{safe_string(str(t.get("date","-"))[:10])}</td>'
                f'<td>{safe_string(t.get("description","-"))}</td>'
                f'<td style="text-align:right;color:var(--red);font-variant-numeric:tabular-nums;">{money(_f(t.get("debit"))) if _f(t.get("debit")) > 0 else ""}</td>'
                f'<td style="text-align:right;color:var(--green);font-variant-numeric:tabular-nums;">{money(_f(t.get("credit"))) if _f(t.get("credit")) > 0 else ""}</td>'
                f'<td style="text-align:right;font-variant-numeric:tabular-nums;">{money(_eb)}</td></tr>'
                for t, _eb in zip(bank_txns[:500], _eff_bals[:500]))
            _smore = f'<p style="font-size:12px;color:var(--text-muted);">Showing first 500 of {len(bank_txns)}.</p>' if len(bank_txns) > 500 else ""
            stmt_body = ('<table style="width:100%;font-size:13px;margin-top:8px;"><thead><tr>'
                         '<th style="text-align:left;">Date</th><th style="text-align:left;">Description</th>'
                         '<th style="text-align:right;">Out</th><th style="text-align:right;">In</th>'
                         '<th style="text-align:right;">Balance</th></tr></thead>'
                         f'<tbody>{_sr}</tbody></table>{_smore}')
            _has_rb = any(t.get("balance") not in (None, "") for t in bank_txns)
            _recon_close = _eff_bals[-1] if _eff_bals else bank_opening
            _rb_note = (f'Running balance from the imported statement — opening {money(bank_opening)}, closing {money(bank_closing)}.'
                        if _has_rb else
                        f'No per-line balance was imported, so the running balance is reconstructed forward from the opening {money(bank_opening)} (closing {money(_recon_close)}). Enter the statement opening/closing balance above to anchor it to your real statement.')
        else:
            stmt_body = '<p style="color:var(--text-muted);font-size:13px;margin-top:8px;">No bank transactions imported yet.</p>'
            _rb_note = ""
        stmt_section = ('<details class="card" style="margin-bottom:14px;">'
                        f'<summary style="cursor:pointer;font-weight:600;">Imported bank statement (running balance) &mdash; {len(bank_txns)} lines &middot; closing {money(bank_closing)}</summary>'
                        f'<p style="margin:8px 0 0 0;color:var(--text-muted);font-size:13px;">{_rb_note}</p>'
                        f'{stmt_body}</details>')

        header = ('<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:8px;">'
                  '<h2 style="margin:0;">Bank Reconciliation &mdash; Statement vs GL</h2>'
                  '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
                  '<button id="zaneReconBtn" class="btn btn-primary" onclick="askZaneRecon()">Ask Zane to explain</button>'
                  '<a href="/banking" class="btn btn-secondary">Back to Banking</a></div></div>'
                  '<p style="color:var(--text-muted);margin:0 0 16px 0;font-size:13px;">A direct two-sided check: the bank statement balance against the GL bank account, '
                  'with every rand of the difference accounted for.</p>')

        _zane_box = '<div id="zaneReconBox" style="display:none;margin-bottom:18px;"></div>'
        _zane_script = """<script>
async function askZaneRecon(){
  var box=document.getElementById('zaneReconBox');
  var btn=document.getElementById('zaneReconBtn');
  box.style.display='block';
  box.innerHTML='<div class="card"><em style="color:var(--text-muted);">Zane is reviewing the reconciliation...</em></div>';
  if(btn){btn.disabled=true;btn.textContent='Asking Zane...';}
  try{
    var _sj=window.RECON_STMT||{open:null,close:null};
    var r=await fetch('/api/banking/reconcile-explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stmt_open:_sj.open,stmt_close:_sj.close})});
    var d=await r.json();
    if(d.success){box.innerHTML='<div class="card"><h3 style="margin:0 0 8px 0;">Zane explains</h3><p style="margin:0;white-space:pre-wrap;line-height:1.5;">'+escapeHtmlRecon(d.explanation)+'</p></div>';}
    else{box.innerHTML='<div class="card"><em style="color:var(--red);">Zane could not explain right now: '+escapeHtmlRecon(d.error||'unavailable')+'</em></div>';}
  }catch(e){box.innerHTML='<div class="card"><em style="color:var(--red);">Could not reach Zane.</em></div>';}
  if(btn){btn.disabled=false;btn.textContent='Ask Zane to explain';}
}
function escapeHtmlRecon(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
</script>"""
        _so_val = ("%.2f" % _stmt_open_in) if _stmt_open_in is not None else ""
        _sc_val = ("%.2f" % _stmt_close_in) if _stmt_close_in is not None else ""
        _stmt_form = (
            '<div class="card" style="margin-bottom:16px;">'
            '<form method="GET" action="/banking/reconcile" style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;">'
            '<div><label style="display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px;">Statement opening balance</label>'
            '<input type="text" name="stmt_open" value="' + _so_val + '" placeholder="optional" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);width:170px;"></div>'
            '<div><label style="display:block;font-size:12px;color:var(--text-muted);margin-bottom:4px;">Statement closing balance</label>'
            '<input type="text" name="stmt_close" value="' + _sc_val + '" placeholder="e.g. -825523.81" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);width:180px;"></div>'
            '<button type="submit" class="btn btn-primary">Apply</button>'
            '<a href="/banking/reconcile" class="btn btn-secondary">Clear</a>'
            '</form>'
            '<p style="margin:8px 0 0 0;font-size:12px;color:var(--text-muted);">For bank formats without a per-line running balance, enter the closing balance from your statement (use a minus sign for an overdraft). Leave blank to use the imported balance.</p>'
            '</div>')
        _stmt_js = ('<script>window.RECON_STMT={open:%s,close:%s};</script>'
                    % (("%.2f" % _stmt_open_in) if _stmt_open_in is not None else "null",
                       ("%.2f" % _stmt_close_in) if _stmt_close_in is not None else "null"))
        repair_section = (
            '<details class="card" style="margin-bottom:14px;">'
            '<summary style="cursor:pointer;font-weight:600;">Reconciliation repair &mdash; remove orphaned allocations</summary>'
            '<p style="margin:8px 0 0 0;color:var(--text-muted);font-size:13px;">'
            'If a statement was re-imported, the earlier allocations can be left orphaned in the GL '
            '(postings with no matching bank line). Scan to find them, review the counts, then repair. '
            'This removes the orphaned postings and resets the invoices they had marked paid, so you can '
            're-allocate the clean statement cleanly. Nothing changes until you confirm.</p>'
            '<div style="margin-top:10px;"><button id="orphanScanBtn" class="btn btn-secondary" onclick="scanOrphans()">Scan for orphaned allocations</button></div>'
            '<div id="orphanResult" style="margin-top:10px;"></div>'
            '</details>')
        _repair_script = """<script>
async function scanOrphans(){
  var btn=document.getElementById('orphanScanBtn');
  var box=document.getElementById('orphanResult');
  if(btn){btn.disabled=true;btn.textContent='Scanning...';}
  box.innerHTML='<em style="color:var(--text-muted);">Scanning...</em>';
  try{
    var r=await fetch('/api/banking/repair-orphaned-allocations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'preview'})});
    var d=await r.json();
    if(!d.success){box.innerHTML='<em style="color:var(--red);">'+(d.error||'Scan failed')+'</em>';}
    else if(d.total===0){box.innerHTML='<p style="color:var(--green);font-size:13px;margin:0;">No orphaned allocations found &mdash; nothing to repair.</p>';}
    else{
      var c=d.counts;
      box.innerHTML='<table style="width:100%;font-size:13px;"><tbody>'+
        '<tr><td>Journal postings</td><td style="text-align:right;">'+c.journals+'</td></tr>'+
        '<tr><td>Customer receipts</td><td style="text-align:right;">'+c.receipts+'</td></tr>'+
        '<tr><td>Supplier payments</td><td style="text-align:right;">'+c.supplier_payments+'</td></tr>'+
        '<tr><td>Allocation-log entries</td><td style="text-align:right;">'+c.allocation_log+'</td></tr>'+
        '<tr><td>Invoices reset to outstanding</td><td style="text-align:right;">'+c.invoices_reset+'</td></tr>'+
        '<tr><td>Supplier invoices reset</td><td style="text-align:right;">'+c.supplier_invoices_reset+'</td></tr>'+
        '</tbody></table>'+
        '<button class="btn btn-primary" style="margin-top:10px;" onclick="repairOrphans()">Repair now</button>';
    }
  }catch(e){box.innerHTML='<em style="color:var(--red);">Could not scan.</em>';}
  if(btn){btn.disabled=false;btn.textContent='Scan for orphaned allocations';}
}
async function repairOrphans(){
  if(!confirm('Remove the orphaned allocations and reset the affected invoices? This cannot be undone. Re-allocate the clean statement afterwards.'))return;
  var box=document.getElementById('orphanResult');
  box.innerHTML='<em style="color:var(--text-muted);">Repairing...</em>';
  try{
    var r=await fetch('/api/banking/repair-orphaned-allocations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'execute',confirm:true})});
    var d=await r.json();
    if(!d.success){box.innerHTML='<em style="color:var(--red);">'+(d.error||'Repair failed')+'</em>';}
    else{
      var del=d.deleted||{};
      box.innerHTML='<p style="color:var(--green);font-size:13px;">Repair done. Deleted: journals '+(del.journals||0)+', receipts '+(del.receipts||0)+', supplier payments '+(del.supplier_payments||0)+', log '+(del.allocation_log||0)+'. Reset '+(d.invoices_reset||0)+' invoices, '+(d.supplier_invoices_reset||0)+' supplier invoices. Re-allocate the clean statement, then reload this page.</p>';
    }
  }catch(e){box.innerHTML='<em style="color:var(--red);">Could not complete the repair.</em>';}
}
</script>"""
        content = header + _stmt_form + cards + breakdown + repair_section + _zane_box + opening_section + unalloc_section + gl_only_section + dup_section + over_rev_section + stmt_section + _stmt_js + _zane_script + _repair_script
        return render_page("Bank Reconciliation", content, user, "banking")

    def _recon_plain_explanation(R, _m):
        """Fully deterministic plain-language explanation of the reconciliation
        difference and the single most important fix, built only from the engine's
        computed figures. Always available, even with no AI — the reliable answer
        behind 'Ask Zane to explain'."""
        comps = []  # (kind, label, amount)
        if abs(R["opening_gap"]) >= 1:
            comps.append(("opening", "the opening balance gap", R["opening_gap"]))
        if R["unalloc"]:
            comps.append(("unalloc", f"{len(R['unalloc'])} unallocated statement line(s)", R["unalloc_net"]))
        if abs(R["residual"]) >= 1:
            comps.append(("residual", "an unexplained remainder still to be traced to specific items", R["residual"]))
        if R["duplicates"]:
            comps.append(("dup", f"{len(R['duplicates'])} duplicate posting(s)", R["dup_excess_total"]))
        if R.get("over_reversals"):
            comps.append(("over_rev", f"{len(R['over_reversals'])} over-reversal(s)", R["over_rev_total"]))

        head = (f"The bank statement shows {_m(R['bank_closing'])} and the books (GL code {R['bank_code']}) "
                f"show {_m(R['gl_balance'])} — a difference of {_m(R['difference'])}.")
        if not comps:
            return head + " Every rand is accounted for; there is nothing outstanding to fix."

        breakdown = " It is made up of " + "; ".join(f"{label} ({_m(amt)})" for (_k, label, amt) in comps) + "."
        biggest = max(comps, key=lambda c: abs(c[2]))
        fixes = {
            "opening": f"move {_m(biggest[2])} so the GL opening on code {R['bank_code']} matches the bank — the opening must sit in only one place",
            "unalloc": "allocate those statement lines on the Banking page (Ask Zane)",
            "residual": "trace the remainder to specific items — list the unmatched GL postings on the bank code and any statement lines not yet booked, then allocate or correct them",
            "dup": "reverse the extra duplicate copies",
            "over_rev": "reverse the extra over-reversals",
        }
        fix = fixes.get(biggest[0], "allocate or correct the items above")
        return head + breakdown + f" The biggest part is {biggest[1]} ({_m(biggest[2])}); to close the gap, {fix}."

    # Expose the deterministic engine to other modules (e.g. Zane chat in clickai.py).
    global _RECON_COMPUTE, _RECON_EXPLAIN
    _RECON_COMPUTE = _compute_recon
    _RECON_EXPLAIN = _recon_plain_explanation

    @app.route("/api/banking/reconcile-explain", methods=["POST"])
    @login_required
    def api_banking_reconcile_explain():
        """Zane explains the reconciliation in plain English and suggests ONE fix.
        Grounded entirely on the engine's computed figures — Zane cannot invent items."""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("name", "the business") if business else "the business"
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})

        _det = None
        try:
            _body = request.get_json(silent=True) or {}
            def _pf(v):
                try:
                    return float(v) if v is not None and str(v).strip() != "" else None
                except Exception:
                    return None
            R = _compute_recon(biz_id, _pf(_body.get("stmt_open")), _pf(_body.get("stmt_close")))
            cur = business.get("currency", "R") if business else "R"

            def _m(v):
                try:
                    return money(v)
                except Exception:
                    return f"{cur}{float(v or 0):,.2f}"

            # Deterministic answer — always available, even if the AI is down.
            _det = _recon_plain_explanation(R, _m)

            misplaced_txt = ""
            for _a, _ob in R["misplaced"]:
                misplaced_txt += (f"\n- Possible misplaced opening balance: {_m(_ob)} sits on code "
                                  f"{_a.get('account_code','')} ({_a.get('account_name','')}), not on the bank code {R['bank_code']}.")

            dup_txt = ""
            for _d in R["duplicates"][:3]:
                dup_txt += (f"\n  - {_d['reference']} ({_d['description'][:40]}) booked {_d['count']} times, "
                            f"doubled-up {_m(abs(_d['excess']))}.")

            prompt = (
                "You are Zane, the bookkeeping assistant in ClickAI. A bank reconciliation has been run for "
                + biz_name + ". The figures below were computed by the system — trust them exactly and do NOT invent "
                "any numbers or items.\n\n"
                f"Bank statement balance: {_m(R['bank_closing'])}\n"
                f"GL bank balance (code {R['bank_code']}): {_m(R['gl_balance'])}\n"
                f"Difference (bank minus books): {_m(R['difference'])}\n\n"
                "The difference is made up of exactly these parts:\n"
                f"- Opening balance gap: {_m(R['opening_gap'])} (bank opening {_m(R['bank_opening'])} vs GL opening {_m(R['gl_opening'])} on code {R['bank_code']})."
                + misplaced_txt + "\n"
                f"- Unallocated statement lines (on the bank, not yet posted to the GL): {len(R['unalloc'])} transactions, net {_m(R['unalloc_net'])}.\n"
                f"- Other GL bank postings with no statement line (possible duplicates or payments booked in Invoicing/Purchases): {len(R['gl_only'])} entries, residual {_m(R['residual'])}.\n"
                f"- Possible duplicate postings (same reference booked more than once on the bank): {len(R['duplicates'])} references, doubled-up value {_m(R['dup_excess_total'])}.{dup_txt}\n"
                f"- Possible over-reversals (an original reversed more than once): {len(R['over_reversals'])} originals, over-reversed value {_m(R['over_rev_total'])}.\n\n"
                "Write a reply in plain English (UK/SA business English), no markdown, no headings, no bullet symbols, under 130 words, in two short paragraphs:\n"
                "1) What the difference is made of, in money terms, naming the biggest contributor.\n"
                "2) The single most important fix to do first, concrete and specific. If a misplaced opening balance explains most of it, say to move that amount from its code to code "
                + str(R['bank_code']) + " with a journal. If unallocated lines are the biggest part, say to allocate those on the Banking page. "
                "If the residual/duplicates are biggest, say to check those GL postings for double-ups."
            )

            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return jsonify({"success": True, "explanation": _det})
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 350,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=20
            )
            if resp.status_code != 200:
                logger.error(f"[BANK RECON EXPLAIN] API error: {resp.status_code} — {resp.text[:300]}")
                return jsonify({"success": True, "explanation": _det})
            ai_text = (resp.json().get("content", [{}])[0].get("text", "") or "").strip()
            if not ai_text:
                return jsonify({"success": True, "explanation": _det})
            return jsonify({"success": True, "explanation": ai_text})
        except Exception as e:
            logger.error(f"[BANK RECON EXPLAIN] {e}")
            if _det:
                return jsonify({"success": True, "explanation": _det})
            return jsonify({"success": False, "error": "Could not build explanation"})


    @app.route("/api/banking/import", methods=["POST"])
    @login_required
    def api_banking_import():
        """Import bank statement CSV or PDF with SMART AUTO-MATCHING"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            file = request.files.get("file")
            if not file:
                return jsonify({"success": False, "error": "No file uploaded"})
            
            # ═══ OPTIONAL DATE RANGE FILTER ═══
            # If supplied, only transactions within [import_date_from, import_date_to]
            # are imported. Blank = import everything (original behaviour).
            import_date_from = (request.form.get("date_from") or "").strip()
            import_date_to = (request.form.get("date_to") or "").strip()
            if import_date_from or import_date_to:
                logger.info(f"[BANK IMPORT] Date range filter: from='{import_date_from or 'any'}' to='{import_date_to or 'any'}'")
            
            filename = file.filename.lower()
            logger.info(f"[BANK IMPORT] === START === File: {filename}, Size: {request.content_length or 'unknown'} bytes")
            
            # ═══════════════════════════════════════════════════════════════
            # PDF PARSING - Standard Bank, ABSA, FNB, Nedbank, Capitec
            # ═══════════════════════════════════════════════════════════════
            if filename.endswith('.pdf'):
                try:
                    import subprocess, tempfile, os
                    
                    # Save PDF to temp file
                    pdf_bytes = file.read()
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        tmp.write(pdf_bytes)
                        tmp_path = tmp.name
                    
                    # First try text extraction
                    pdf_text = ""
                    try:
                        result = subprocess.run(['pdftotext', '-layout', tmp_path, '-'], capture_output=True, text=True, timeout=30)
                        pdf_text = result.stdout.strip()
                        logger.info(f"[BANK IMPORT] pdftotext extracted {len(pdf_text)} chars")
                    except Exception as pdftotext_err:
                        logger.warning(f"[BANK IMPORT] pdftotext failed: {pdftotext_err}")
                    
                    if not pdf_text:
                        try:
                            import pdfplumber
                            with pdfplumber.open(tmp_path) as pdf_doc:
                                for page in pdf_doc.pages:
                                    page_text = page.extract_text()
                                    if page_text:
                                        pdf_text += page_text + "\n"
                            logger.info(f"[BANK IMPORT] pdfplumber extracted {len(pdf_text)} chars")
                        except Exception as plumber_err:
                            logger.warning(f"[BANK IMPORT] pdfplumber failed: {plumber_err}")
                    
                    # If text extraction failed (scanned PDF), use Claude AI via page-by-page processing
                    if not pdf_text or len(pdf_text) < 50:
                        logger.info(f"[BANK IMPORT] Scanned PDF detected (text={len(pdf_text) if pdf_text else 0} chars) - processing page by page")
                        
                        try:
                            import base64
                            from concurrent.futures import ThreadPoolExecutor, as_completed
                            all_transactions = []
                            
                            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                            if not api_key:
                                os.unlink(tmp_path)
                                return jsonify({"success": False, "error": "AI API key not configured"})
                            
                            # Split PDF into individual pages using pdfseparate
                            import glob
                            page_dir = tmp_path + "_pages"
                            os.makedirs(page_dir, exist_ok=True)
                            
                            try:
                                split_result = subprocess.run(
                                    ['pdfseparate', tmp_path, os.path.join(page_dir, 'page_%d.pdf')],
                                    capture_output=True, text=True, timeout=30
                                )
                                page_files = sorted(glob.glob(os.path.join(page_dir, 'page_*.pdf')))
                                logger.info(f"[BANK IMPORT] Split PDF into {len(page_files)} pages")
                            except Exception as split_err:
                                # Fallback: send whole PDF if splitting fails
                                logger.warning(f"[BANK IMPORT] pdfseparate failed ({split_err}), sending whole PDF")
                                page_files = [tmp_path]
                            
                            if not page_files:
                                page_files = [tmp_path]
                            
                            prompt = """Extract ALL bank transactions from this bank statement page.

Return ONLY a valid JSON array, no other text. Each transaction must have:
- "date": "YYYY-MM-DD" format
- "description": the FULL transaction description including ALL detail lines
- "debit": amount as number (money going OUT, positive number) or 0
- "credit": amount as number (money coming IN, positive number) or 0
- "balance": the running balance after this transaction

CRITICAL - DESCRIPTIONS:
- Each transaction may span MULTIPLE LINES. The first line has the transaction type (e.g. "ELECTRONIC BANKING PAYMENT TO") and the next line(s) have the beneficiary/reference details (e.g. "MAR20 M FULLARD ERY5310:21")
- You MUST combine ALL lines of a transaction into ONE description string
- Example: if you see "CREDIT TRANSFER" on one line and "KHUPHUKANI" on the next, the description must be "CREDIT TRANSFER KHUPHUKANI"
- NEVER use generic text like "Transaction" — always use the actual text from the statement

RULES:
- Payments OUT (debits, purchases, fees) go in "debit" field as POSITIVE numbers
- Payments IN (credits, deposits) go in "credit" field as POSITIVE numbers
- Never use negative numbers
- Include ALL transactions on this page, not just a sample
- Skip "BALANCE BROUGHT FORWARD" lines, page headers, and column headers
- If this page has NO transactions (only headers/summary), return an empty array: []

Return ONLY the JSON array. No markdown, no explanation."""
                            
                            import requests as _req
                            
                            def process_page(page_path, page_num):
                                """Process a single PDF page through Claude"""
                                try:
                                    with open(page_path, 'rb') as f:
                                        page_bytes = f.read()
                                    page_b64 = base64.standard_b64encode(page_bytes).decode("utf-8")
                                    
                                    resp = _req.post(
                                        "https://api.anthropic.com/v1/messages",
                                        headers={
                                            "x-api-key": api_key,
                                            "anthropic-version": "2023-06-01",
                                            "content-type": "application/json"
                                        },
                                        json={
                                            "model": "claude-haiku-4-5-20251001",
                                            "max_tokens": 8000,
                                            "messages": [{
                                                "role": "user",
                                                "content": [
                                                    {
                                                        "type": "document",
                                                        "source": {
                                                            "type": "base64",
                                                            "media_type": "application/pdf",
                                                            "data": page_b64
                                                        }
                                                    },
                                                    {"type": "text", "text": prompt}
                                                ]
                                            }]
                                        },
                                        timeout=90
                                    )
                                    
                                    if resp.status_code != 200:
                                        logger.error(f"[BANK IMPORT] Page {page_num} Claude error: {resp.status_code}")
                                        return []
                                    
                                    ai_result = resp.json()
                                    ai_text = ""
                                    for block in ai_result.get("content", []):
                                        if block.get("type") == "text":
                                            ai_text += block["text"]
                                    
                                    ai_text = ai_text.strip()
                                    if ai_text.startswith("```"):
                                        ai_text = ai_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                                    
                                    try:
                                        page_txns = json.loads(ai_text)
                                        logger.info(f"[BANK IMPORT] Page {page_num}: {len(page_txns)} transactions")
                                        return page_txns if isinstance(page_txns, list) else []
                                    except json.JSONDecodeError as je:
                                        # Try truncation recovery
                                        recovered = ai_text[:je.pos].rstrip().rstrip(",")
                                        if not recovered.endswith("]"):
                                            last_brace = recovered.rfind("}")
                                            if last_brace > 0:
                                                recovered = recovered[:last_brace + 1] + "]"
                                        try:
                                            page_txns = json.loads(recovered)
                                            logger.info(f"[BANK IMPORT] Page {page_num}: recovered {len(page_txns)} transactions")
                                            return page_txns if isinstance(page_txns, list) else []
                                        except json.JSONDecodeError:
                                            logger.error(f"[BANK IMPORT] Page {page_num}: JSON parse failed")
                                            return []
                                except Exception as page_err:
                                    logger.error(f"[BANK IMPORT] Page {page_num} error: {page_err}")
                                    return []
                            
                            # Process pages in parallel (max 3 concurrent to avoid rate limits)
                            max_workers = min(3, len(page_files))
                            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                                futures = {
                                    executor.submit(process_page, pf, idx + 1): idx
                                    for idx, pf in enumerate(page_files)
                                }
                                page_results = [None] * len(page_files)
                                for future in as_completed(futures):
                                    idx = futures[future]
                                    page_results[idx] = future.result()
                            
                            # Merge results in page order
                            for page_txns in page_results:
                                if page_txns:
                                    all_transactions.extend(page_txns)
                            
                            logger.info(f"[BANK IMPORT] Total from all pages: {len(all_transactions)} transactions")
                            
                            # Cleanup page files
                            import shutil
                            if os.path.exists(page_dir):
                                shutil.rmtree(page_dir, ignore_errors=True)
                            os.unlink(tmp_path)
                            
                            if not all_transactions:
                                return jsonify({"success": False, "error": "AI could not read any transactions from the PDF. Try a clearer scan or CSV export."})
                            
                            # Convert to standard format
                            data_rows = []
                            for tx in all_transactions:
                                data_rows.append([
                                    str(tx.get("date", "")),
                                    str(tx.get("description", "")),
                                    str(tx.get("debit", 0)),
                                    str(tx.get("credit", 0)),
                                    str(tx.get("balance", 0))
                                ])
                            
                            date_col = 0
                            desc_col = 1
                            debit_col = 2
                            credit_col = 3
                            balance_col = 4
                            amount_col = None
                            
                            logger.info(f"[BANK IMPORT] AI extracted {len(data_rows)} total transactions from PDF")
                            
                        except Exception as ai_err:
                            # Cleanup on error
                            import shutil
                            page_dir = tmp_path + "_pages"
                            if os.path.exists(page_dir):
                                shutil.rmtree(page_dir, ignore_errors=True)
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                            logger.error(f"[BANK IMPORT] AI PDF error: {ai_err}")
                            return jsonify({"success": False, "error": f"Failed to read scanned PDF: {str(ai_err)}"})
                    
                    else:
                        os.unlink(tmp_path)
                        # Text-based PDF parsing
                        import re
                        
                        transactions = []
                        lines = pdf_text.split('\n')
                        
                        logger.info(f"[BANK IMPORT] Text PDF: {len(lines)} lines")
                        
                        date_pattern = re.compile(r'(20\d{6})')
                        amount_pattern = re.compile(r'-?[\d,]+\.\d{2}')
                        
                        i = 0
                        while i < len(lines):
                            line = lines[i].strip()
                            if not line:
                                i += 1
                                continue
                            
                            if any(skip in line.upper() for skip in ['PAGE', 'DETAILS', 'SERVICE FEE', 'CURRENT ACCOUNT', 'STATEMENT', 'STANDARD BANK', 'COMPUTER GENERATED', 'END OF REPORT', 'BRANCH', 'VAT REGISTRATION', 'CLOSING BALANCE', 'BALANCE BROUGHT']):
                                i += 1
                                continue
                            
                            date_match = date_pattern.search(line)
                            if date_match:
                                raw_date = date_match.group(1)
                                tx_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                                
                                # Validate date is real (e.g. reject 2026-02-29)
                                try:
                                    datetime.strptime(tx_date, "%Y-%m-%d")
                                except ValueError:
                                    i += 1
                                    continue
                                
                                # Validate date is real (e.g. reject 2026-02-29)
                                try:
                                    datetime.strptime(tx_date, "%Y-%m-%d")
                                except ValueError:
                                    i += 1
                                    continue
                                
                                numbers = amount_pattern.findall(line)
                                
                                if len(numbers) >= 2:
                                    first_num_pos = line.find(numbers[0])
                                    description = line[:first_num_pos].strip()
                                    description = re.sub(r'^\d+\s+', '', description).strip()
                                    
                                    if not description:
                                        i += 1
                                        continue
                                    
                                    clean_nums = [float(n.replace(',', '')) for n in numbers]
                                    balance = clean_nums[-1]
                                    debit = 0.0
                                    credit = 0.0
                                    for n in clean_nums[:-1]:
                                        if n < 0:
                                            debit = abs(n)
                                        elif n > 0:
                                            credit = n
                                    
                                    if debit == 0 and credit == 0:
                                        i += 1
                                        continue
                                    
                                    transactions.append({
                                        "date": tx_date,
                                        "description": description,
                                        "debit": round(debit, 2),
                                        "credit": round(credit, 2),
                                        "balance": round(balance, 2)
                                    })
                            i += 1
                        
                        data_rows = []
                        for tx in transactions:
                            # Stringify all fields so the downstream loop can safely call .replace()
                            # without crashing on float values (consistent with AI-path)
                            data_rows.append([
                                str(tx["date"]),
                                str(tx["description"]),
                                str(tx["debit"]),
                                str(tx["credit"]),
                                str(tx["balance"])
                            ])
                        
                        date_col = 0
                        desc_col = 1
                        debit_col = 2
                        credit_col = 3
                        balance_col = 4
                        amount_col = None
                        
                        if not data_rows:
                            return jsonify({"success": False, "error": "Could not parse transactions from PDF text"})
                    
                except Exception as pdf_err:
                    logger.error(f"[BANK IMPORT] PDF parse error: {pdf_err}")
                    return jsonify({"success": False, "error": f"PDF parse error: {str(pdf_err)}"})
            
            else:
                # CSV PARSING (existing logic)
                content = file.read().decode('utf-8', errors='ignore')
                # newline='' lets the csv module do its own universal newline handling,
                # avoiding "new-line character seen in unquoted field" on CRLF/stray-CR files.
                reader = csv.reader(io.StringIO(content, newline=''))
                rows = list(reader)
            
                if len(rows) < 2:
                    return jsonify({"success": False, "error": "File is empty"})
                
                # ═══════════════════════════════════════════════════════════════
                # STANDARD BANK "PROV" / MAGTAPE CSV FORMAT
                # No headers, ~8 cols, col 0 = "ALL"/"PROV", col 1 = date code
                # (000DDMMx), col 2 = type (PAY/EFTPOS/FEE/ACB/SF/OPEN/CLOSE),
                # col 3 = signed amount with leading zeros, cols 4+5 = description.
                # ═══════════════════════════════════════════════════════════════
                def _is_sb_prov(_rows):
                    if not _rows:
                        return False
                    sample = _rows[0] if len(_rows[0]) >= 6 else (_rows[1] if len(_rows) > 1 and len(_rows[1]) >= 6 else None)
                    if not sample or len(sample) < 6:
                        return False
                    c0 = str(sample[0]).strip().upper()
                    if c0 not in ("ALL", "PROV"):
                        return False
                    c3 = str(sample[3]).strip()
                    if not (c3.startswith("+") or c3.startswith("-") or c3.lstrip().startswith("0")):
                        return False
                    return True
                
                def _parse_sb_prov_date(_field):
                    """Decode '000DDMMx' format -> YYYY-MM-DD using current year + rollover guard."""
                    raw = str(_field).strip()
                    if len(raw) != 7 or not raw.isdigit():
                        return None
                    ddmm = raw[3:7]
                    try:
                        day = int(ddmm[:2])
                        month = int(ddmm[2:4])
                        if not (1 <= day <= 31 and 1 <= month <= 12):
                            return None
                        year = datetime.now().year
                        try:
                            dt = datetime(year, month, day)
                        except ValueError:
                            return None
                        # Rollover guard: if parsed date is more than 30 days in the future,
                        # the statement is for the previous calendar year
                        if dt > datetime.now() + timedelta(days=30):
                            try:
                                dt = datetime(year - 1, month, day)
                            except ValueError:
                                return None
                        return dt.strftime("%Y-%m-%d")
                    except (ValueError, IndexError):
                        return None
                
                def _parse_sb_prov_amount(_field):
                    """Parse signed leading-zero amount. Returns (debit, credit)."""
                    raw = str(_field).strip()
                    sign = 1
                    if raw.startswith('-'):
                        sign = -1
                        raw = raw[1:]
                    elif raw.startswith('+'):
                        raw = raw[1:]
                    raw = raw.lstrip('0') or '0'
                    try:
                        val = float(raw) * sign
                    except ValueError:
                        return (0.0, 0.0)
                    if val < 0:
                        return (round(abs(val), 2), 0.0)
                    return (0.0, round(val, 2))
                
                if _is_sb_prov(rows):
                    logger.info(f"[BANK IMPORT] Detected Standard Bank PROV/magtape format")

                    def _parse_sb_prov_signed(_field):
                        """Parse a signed leading-zero balance field, keeping the sign."""
                        raw = str(_field).strip()
                        sign = 1
                        if raw.startswith('-'):
                            sign = -1
                            raw = raw[1:]
                        elif raw.startswith('+'):
                            raw = raw[1:]
                        raw = raw.lstrip('0') or '0'
                        try:
                            return round(float(raw) * sign, 2)
                        except ValueError:
                            return None

                    _prov_data = []
                    _prov_meta_skipped = 0
                    _prov_unparseable = 0
                    _prov_open_balance = None
                    _prov_close_balance = None
                    for _r in rows:
                        if len(_r) < 6:
                            continue
                        _type = str(_r[2]).strip().upper()
                        # Capture the opening/closing balance rows so the per-line running
                        # balance can be reconstructed (Standard Bank PROV carries none).
                        if _type == "OPEN":
                            _prov_open_balance = _parse_sb_prov_signed(_r[3])
                            _prov_meta_skipped += 1
                            continue
                        if _type == "CLOSE":
                            _prov_close_balance = _parse_sb_prov_signed(_r[3])
                            _prov_meta_skipped += 1
                            continue
                        # Skip remaining non-transaction rows: header rows.
                        if _type in ("BRANCH", "ACC NO", "ACCNO"):
                            _prov_meta_skipped += 1
                            continue
                        _d = _parse_sb_prov_date(_r[1])
                        if not _d:
                            _prov_unparseable += 1
                            continue
                        _deb, _cre = _parse_sb_prov_amount(_r[3])
                        _desc1 = str(_r[4]).strip() if len(_r) > 4 else ""
                        _desc2 = str(_r[5]).strip() if len(_r) > 5 else ""
                        _description = f"{_desc1} {_desc2}".strip() if _desc1 else _desc2
                        if not _description and _type:
                            _description = _type
                        _prov_data.append([_d, _description, str(_deb), str(_cre), "0"])

                    # Reconstruct the per-transaction running balance from the opening
                    # balance row, in date order, so the bank reconciliation has a reliable
                    # closing balance without the user typing it in. Fully additive: with no
                    # OPEN row the balances stay "0" and behaviour is unchanged.
                    if _prov_open_balance is not None and _prov_data:
                        _prov_data.sort(key=lambda _x: str(_x[0])[:10])
                        _run = _prov_open_balance
                        for _row in _prov_data:
                            try:
                                _rb_deb = float(_row[2] or 0)
                                _rb_cre = float(_row[3] or 0)
                            except (ValueError, TypeError):
                                _rb_deb = _rb_cre = 0.0
                            _run = round(_run + _rb_cre - _rb_deb, 2)
                            _row[4] = str(_run)
                        if _prov_close_balance is not None and abs(_run - _prov_close_balance) > 0.05:
                            logger.warning(f"[BANK IMPORT] PROV running balance {_run} != statement CLOSE {_prov_close_balance} (diff {round(_run - _prov_close_balance, 2)})")
                        else:
                            logger.info(f"[BANK IMPORT] PROV running balance reconstructed: open {_prov_open_balance} -> close {_run}")

                    logger.info(f"[BANK IMPORT] PROV: {len(_prov_data)} txns parsed, {_prov_meta_skipped} meta rows skipped, {_prov_unparseable} unparseable")
                    
                    if not _prov_data:
                        return jsonify({"success": False, "error": "Standard Bank PROV format detected but no transactions could be parsed."})
                    
                    # Set up data_rows in standard format and predefine column indices
                    # so the downstream loop can process them like any other CSV.
                    data_rows = _prov_data
                    headers = []  # bypass header-based column detection
                    _sb_prov_active = True
                else:
                    headers = [str(h).lower() if not isinstance(h, list) else str(h[0]).lower() for h in rows[0]]
                    data_rows = rows[1:]
                    _sb_prov_active = False
            
            def cell_str(cell):
                if cell is None:
                    return ""
                if isinstance(cell, (list, tuple)):
                    while isinstance(cell, (list, tuple)) and cell:
                        cell = cell[0]
                    return str(cell).strip() if cell is not None else ""
                return str(cell).strip()
            
            # For CSV: clean data and find columns
            if not filename.endswith('.pdf'):
                data_rows = [[cell_str(cell) for cell in row] for row in data_rows]
                
                # SB PROV format already pre-built data_rows in [date, desc, debit, credit, balance]
                # order with explicit column indices. Skip header-based column detection.
                if locals().get('_sb_prov_active'):
                    date_col = 0
                    desc_col = 1
                    debit_col = 2
                    credit_col = 3
                    balance_col = 4
                    amount_col = None
                else:
                    # Find columns
                    date_col = desc_col = amount_col = debit_col = credit_col = balance_col = None
                    
                    for i, h in enumerate(headers):
                        if "date" in h:
                            date_col = i
                        elif "desc" in h or "narr" in h or "particular" in h:
                            desc_col = i
                        elif "amount" in h:
                            amount_col = i
                        elif "debit" in h:
                            debit_col = i
                        elif "credit" in h:
                            credit_col = i
                        elif "balance" in h:
                            balance_col = i
            
            # ═══════════════════════════════════════════════════════════════
            # GET DATA FOR SMART MATCHING
            # ═══════════════════════════════════════════════════════════════
            
            # POS daily totals for matching deposits
            sales = db.get("sales", {"business_id": biz_id}) or []
            pos_daily = {}
            for s in sales:
                d = str(s.get("date", ""))[:10]
                if d not in pos_daily:
                    pos_daily[d] = 0
                pos_daily[d] += float(s.get("total", 0))
            
            # Outstanding invoices for matching customer payments
            invoices = db.get("invoices", {"business_id": biz_id}) or []
            outstanding = [i for i in invoices if i.get("status") != "paid"]
            
            # Customers for name matching
            customers = db.get("customers", {"business_id": biz_id}) or []
            customer_names = {c.get("name", "").upper(): c for c in customers if c.get("name")}
            customers_by_id = {c.get("id"): c for c in customers if c.get("id")}
            
            # Known expense keywords
            expense_keywords = {
                "SARS": "Tax",
                "TELKOM": "Telephone",
                "VODACOM": "Telephone",
                "MTN": "Telephone",
                "CELL C": "Telephone",
                "ESKOM": "Electricity",
                "CITY POWER": "Electricity",
                "MUNICIPAL": "Municipal Charges",
                "ENGEN": "Fuel",
                "SHELL": "Fuel",
                "SASOL": "Fuel",
                "CALTEX": "Fuel",
                "BP ": "Fuel",
                "TOTAL ": "Fuel",
                "MAKRO": "Stock Purchase",
                "BUILDERS": "Stock Purchase",
                "CASHBUILD": "Stock Purchase",
                "TAKEALOT": "Online Purchases",
                "AMAZON": "Online Purchases",
                "PAYROLL": "Salaries",
                "SALARY": "Salaries",
                "WAGES": "Salaries",
                "INSURANCE": "Insurance",
                "OUTSURANCE": "Insurance",
                "SANTAM": "Insurance",
                "DISCOVERY": "Insurance",
                "RENT": "Rent",
                "LEASE": "Rent",
                "BANK CHARGE": "Bank Charges",
                "SERVICE FEE": "Bank Charges",
                "INTEREST": "Interest",
            }

            # Expense categories used to keep income and expense from crossing during
            # learned-pattern matching (the business COA expense list + the keyword map).
            try:
                _import_expense_cats = set(IndustryKnowledge.get_expense_categories(biz_id) or [])
            except Exception:
                _import_expense_cats = set()
            _import_expense_cats |= set(expense_keywords.values())
            
            # Payslips for matching salary EFT payments
            payslips = db.get("payslips", {"business_id": biz_id}) or []
            payslip_lookup = []
            for ps in payslips:
                ps_net = float(ps.get("net", 0) or 0)
                ps_name = (ps.get("employee_name") or "").upper().strip()
                ps_date = str(ps.get("date", ""))[:10]
                if ps_net > 0 and ps_name and ps_date:
                    # Build name parts for flexible matching (first name, surname, initials)
                    name_parts = [p for p in ps_name.split() if len(p) > 1]
                    payslip_lookup.append({
                        "net": ps_net,
                        "name": ps_name,
                        "name_parts": name_parts,
                        "date": ps_date,
                        "employee_name": ps.get("employee_name", ""),
                        "id": ps.get("id", ""),
                        "matched": ps.get("bank_matched", False)
                    })
            
            # Scanned expenses for matching (amount + date + carry splits)
            all_expenses = db.get("expenses", {"business_id": biz_id}) or []
            _matched_expense_splits = {}  # temp store for split data during import
            
            imported = 0
            auto_matched = 0
            suggested = 0
            skipped_dupes = 0
            skipped_out_of_range = 0
            
            # ═══════════════════════════════════════════════════════════════
            # DEDUP: Build fingerprint set of existing transactions
            # Prevents re-importing the same statement twice
            # Uses TWO layers: exact match + fuzzy match (date+amount only)
            # ═══════════════════════════════════════════════════════════════
            existing_txns = db.get("bank_transactions", {"business_id": biz_id}) or []
            existing_fingerprints = set()
            for et in existing_txns:
                existing_fingerprints.add(_bank_fingerprint(
                    et.get("date", ""), et.get("description"),
                    et.get("amount", 0), et.get("debit", 0), et.get("credit", 0),
                    et.get("balance", 0)))
            
            logger.info(f"[BANK IMPORT] Dedup: {len(existing_fingerprints)} signed fingerprints loaded")
            
            # ═══════════════════════════════════════════════════════════════
            # PRE-CACHE: Load all bank patterns ONCE instead of per-transaction
            # ═══════════════════════════════════════════════════════════════
            _cached_patterns = []
            try:
                _cached_patterns = db.get("bank_patterns", {"business_id": biz_id}) or []
                logger.info(f"[BANK IMPORT] Cached {len(_cached_patterns)} bank patterns for matching")
            except Exception:
                pass
            
            def _fast_pattern_match(description):
                """Match against cached patterns — NO DB calls"""
                normalized = description.upper().strip()
                # Remove common prefixes
                for prefix in ['ELECTRONIC BANKING PAYMENT TO ', 'ELECTRONIC BANKING PAYMENT FR ', 
                              'CREDIT TRANSFER ', 'DEBIT TRANSFER ', 'CREDIT CARD EFTPOS SETTLEMENT ',
                              'IB PAYMENT FROM ', 'MAGTAPE CREDIT ', 'INTERBANK CREDIT TRANSFER ']:
                    if normalized.startswith(prefix):
                        normalized = normalized[len(prefix):]
                        break
                import re as _re
                normalized = _re.sub(r'\b(ERY|CR EFTPOS|DR EFTPOS)\s*\d+[:\s]*\d*', '', normalized).strip()
                normalized = _re.sub(r'\s+', ' ', normalized).strip()[:80]
                
                if not normalized:
                    return {"category": None, "confidence": 0}
                
                # Exact match
                for p in _cached_patterns:
                    if p.get("pattern", "") == normalized:
                        return {
                            "category": p.get("category"),
                            "confidence": p.get("confidence", 0.5),
                        }
                
                # Partial match (80%+ word overlap)
                norm_words = set(normalized.split())
                if len(norm_words) >= 3:
                    for p in _cached_patterns:
                        known = p.get("pattern", "")
                        known_words = set(known.split())
                        if len(known_words) < 3:
                            continue
                        common = norm_words & known_words
                        ratio = len(common) / max(len(known_words), len(norm_words))
                        if ratio >= 0.8:
                            return {
                                "category": p.get("category"),
                                "confidence": p.get("confidence", 0.5) * 0.8,
                            }
                
                return {"category": None, "confidence": 0}
            
            # ═══════════════════════════════════════════════════════════════
            # PROCESS ROWS — build list first, then batch save
            # ═══════════════════════════════════════════════════════════════
            txns_to_save = []
            _row_errors = 0
            _row_error_sample = ""
            
            # Anchor a base timestamp so each txn's created_at = base + idx microseconds.
            # Guarantees statement-reading order is preserved exactly in created_at.
            from datetime import timedelta as _td_seq
            _seq_base = datetime.utcnow()
            
            for idx, row in enumerate(data_rows):
                try:
                    txn_date = row[date_col] if date_col is not None else today()
                    description = row[desc_col] if desc_col is not None else ""
                    
                    # ═══ FLEXIBLE DATE PARSING ═══
                    # Bank statements come in many formats: 2026-04-30, 30/04/2026,
                    # 30-04-2026, 30 Apr 2026, 30 April 2026, 20260430, etc.
                    # Try direct parse first, then slice fallbacks for time-suffixed values.
                    _raw_date = str(txn_date).strip()
                    _parsed_date = None
                    if _raw_date:
                        # Direct parse — handles full strings without trailing data
                        for _fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y",
                                     "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%Y%m%d",
                                     "%d/%m/%y", "%d-%m-%y"):
                            try:
                                _parsed_date = datetime.strptime(_raw_date, _fmt)
                                break
                            except (ValueError, TypeError):
                                continue
                        # Slice fallback for ISO with time appended (e.g. "2026-04-30 00:00:00")
                        if _parsed_date is None:
                            try:
                                _parsed_date = datetime.strptime(_raw_date[:10], "%Y-%m-%d")
                            except (ValueError, TypeError):
                                pass
                    
                    if _parsed_date is None:
                        logger.warning(f"[BANK IMPORT] Unparseable date '{_raw_date}', defaulting to today")
                        txn_date = today()
                    else:
                        txn_date = _parsed_date.strftime("%Y-%m-%d")
                    
                    # ═══ DATE RANGE FILTER ═══
                    # txn_date is now a clean YYYY-MM-DD string — ISO strings compare
                    # correctly as plain text. Skip anything outside the chosen range.
                    _txn_ymd = str(txn_date)[:10]
                    if import_date_from and _txn_ymd < import_date_from:
                        skipped_out_of_range += 1
                        continue
                    if import_date_to and _txn_ymd > import_date_to:
                        skipped_out_of_range += 1
                        continue
                    
                    if amount_col is not None:
                        amt_str = str(row[amount_col] or "").replace(",", "").replace("R", "").replace(" ", "").strip()
                        amount = float(amt_str or 0)
                        debit = abs(amount) if amount < 0 else 0
                        credit = amount if amount > 0 else 0
                    elif debit_col is not None and credit_col is not None:
                        deb_str = str(row[debit_col] or "").replace(",", "").replace("R", "").replace(" ", "").strip()
                        cred_str = str(row[credit_col] or "").replace(",", "").replace("R", "").replace(" ", "").strip()
                        debit = float(deb_str or 0)
                        credit = float(cred_str or 0)
                        amount = credit - debit
                    else:
                        continue
                    
                    # Extract running balance if available (from PDF/AI scan or CSV with balance column)
                    running_balance = None
                    if balance_col is not None and balance_col < len(row):
                        try:
                            bal_str = str(row[balance_col]).replace(",", "").replace("R", "").replace(" ", "").strip()
                            if bal_str and bal_str != "0" and bal_str != "0.0":
                                running_balance = round(float(bal_str), 2)
                        except (ValueError, TypeError):
                            running_balance = None
                    
                    if not description:
                        continue
                    
                    desc_upper = description.upper()
                    
                    # Skip non-transaction rows (balance lines, headers, etc)
                    skip_phrases = ['BALANCE BROUGHT', 'BROUGHT FORWARD', 'OPENING BALANCE', 
                                   'CLOSING BALANCE', 'BALANCE CARRIED', 'CARRIED FORWARD',
                                   'B/F', 'C/F', 'STATEMENT BALANCE']
                    if any(skip in desc_upper for skip in skip_phrases):
                        logger.info(f"[BANK] Skipping non-transaction row: {description[:60]}")
                        continue
                    
                    # Also skip rows with zero amount (just balance lines)
                    if debit == 0 and credit == 0 and amount == 0:
                        continue
                    
                    # ═══════════════════════════════════════════════════════════════
                    # DEDUP CHECK: Skip if this transaction already exists.
                    # Fingerprint = date + full description + signed amount + running
                    # balance. The balance makes two genuinely different transactions
                    # on the same day with the same description+amount (e.g. two R4.90
                    # card fees with different running balances) distinct, so neither
                    # is silently dropped. A re-import of the same statement has
                    # identical balances and is still deduped.
                    # ═══════════════════════════════════════════════════════════════
                    fingerprint = _bank_fingerprint(txn_date, description, amount, debit, credit, running_balance)
                    if fingerprint in existing_fingerprints:
                        skipped_dupes += 1
                        continue
                    
                    # A transaction is only a duplicate when its date, full description
                    # AND signed amount all match an existing one (the exact check above).
                    # The previous "fuzzy" date+amount+prefix matching is removed: it
                    # dropped legitimate distinct deposits that shared a generic prefix
                    # (e.g. "MAGTAPE CREDIT ...", "CREDIT CARD EFTPOS SETTLEMENT ...") and
                    # happened to have the same amount on a busy day. Erring toward keeping
                    # a transaction is safe (visible, removable); silently dropping income
                    # is not (invisible, and it corrupts the bank balance).
                    
                    # Add this new one to prevent exact dupes within the same import file
                    existing_fingerprints.add(fingerprint)
                    
                    # ═══════════════════════════════════════════════════════════════
                    # SMART MATCHING LOGIC
                    # ═══════════════════════════════════════════════════════════════
                    
                    match_type = None
                    match_category = None
                    match_confidence = 0
                    match_reference = None
                    combo_invoice_ids = None
                    combo_invoice_nums = None
                    combo_customer_id = None
                    disc_invoice_id = None
                    disc_invoice_num = None
                    disc_customer_id = None
                    disc_shortfall = None
                    disc_pct = None
                    stmt_invoice_ids = None
                    stmt_customer_id = None
                    stmt_shortfall = None
                    stmt_pct = None
                    
                    # 1. TRY: Match credit to POS daily total
                    if credit > 0:
                        # Normalize date for comparison
                        txn_date_str = str(txn_date)[:10]
                        if txn_date_str in pos_daily:
                            pos_total = pos_daily[txn_date_str]
                            # Allow 1% tolerance for bank fees
                            if abs(credit - pos_total) < (pos_total * 0.01 + 1):
                                match_type = "pos_deposit"
                                match_category = "POS Deposit"
                                match_confidence = 0.95
                                match_reference = f"POS {txn_date_str}"
                                auto_matched += 1
                    
                    # 2. TRY: Match credit to outstanding invoice
                    if credit > 0 and not match_type:
                        for inv in outstanding:
                            inv_total = float(inv.get("total", 0))
                            cust_name = (inv.get("customer_name") or "").upper()
                            
                            # Exact amount match + customer name in description
                            if abs(credit - inv_total) < 1 and cust_name and cust_name[:5] in desc_upper:
                                match_type = "customer_payment"
                                match_category = "Customer Payment"
                                match_confidence = 0.9
                                match_reference = f"{inv.get('invoice_number')} - {inv.get('customer_name')}"
                                auto_matched += 1
                                break
                            # Just amount match
                            elif abs(credit - inv_total) < 1:
                                match_type = "possible_payment"
                                match_category = "Customer Payment?"
                                match_confidence = 0.6
                                match_reference = f"Maybe {inv.get('invoice_number')}?"
                    
                    # 2-STMT. TRY: Full-account / statement payment. Account customers (e.g. NDE)
                    # reconcile against their STATEMENT and pay the whole balance — usually less
                    # their settlement discount. The statement (= sum of their outstanding invoices)
                    # is the truth, not any single invoice. Match the credit against each customer's
                    # outstanding-invoice total (full) or that total LESS their discount %.
                    # Conservative — no guessing:
                    #   - target is the sum of THAT customer's own outstanding invoices
                    #   - matches the SPECIFIC figure to the cent (full preferred over discounted)
                    #   - fires ONLY for 2+ invoices and ONLY if EXACTLY ONE customer matches;
                    #     otherwise no auto-match (falls through to single-invoice / review).
                    if credit > 0 and not match_type:
                        _stmt_groups = {}
                        for inv in outstanding:
                            _icid = inv.get("customer_id")
                            if not _icid:
                                continue
                            _ioz = round(float(inv.get("total", 0)) - float(inv.get("paid_amount", 0) or 0), 2)
                            if _ioz <= 0:
                                continue
                            _g = _stmt_groups.setdefault(_icid, {"sum": 0.0, "ids": []})
                            _g["sum"] = round(_g["sum"] + _ioz, 2)
                            _g["ids"].append(inv.get("id"))
                        _stmt_candidates = []
                        for _icid, _g in _stmt_groups.items():
                            if len(_g["ids"]) < 2:
                                continue  # single invoice is handled by step 2 / 2a, not "statement"
                            _bal = round(_g["sum"], 2)
                            if _bal <= 0:
                                continue
                            _c = customers_by_id.get(_icid)
                            # Full statement payment
                            if abs(credit - _bal) <= 0.02:
                                _stmt_candidates.append((_icid, _c, _g["ids"], _bal, 0.0, 0.0))
                                continue
                            # Statement payment less settlement discount
                            _cdp = 0.0
                            if _c:
                                try:
                                    _cdp = float(_c.get("discount_percentage", 0) or 0)
                                except (TypeError, ValueError):
                                    _cdp = 0.0
                            if 0 < _cdp <= 50:
                                _bt = round(_bal * (1 - _cdp / 100.0), 2)
                                if abs(credit - _bt) <= 0.02:
                                    _stmt_candidates.append((_icid, _c, _g["ids"], _bal, _cdp, round(_bal - credit, 2)))
                        if len(_stmt_candidates) == 1:
                            _s_cid, _s_cust, _s_ids, _s_bal, _s_pct, _s_short = _stmt_candidates[0]
                            _s_cname = (_s_cust.get("name", "") if _s_cust else "") or ""
                            match_type = "customer_payment_statement"
                            match_category = "Customer Payment"
                            match_confidence = 0.9 if (_s_cname[:5].upper() in desc_upper) else 0.8
                            match_reference = (f"Statement - {_s_cname} (less {_s_pct:g}% settlement discount)"
                                               if _s_pct > 0 else f"Statement - {_s_cname}")
                            stmt_invoice_ids = [i for i in _s_ids if i]
                            stmt_customer_id = _s_cid
                            stmt_shortfall = _s_short
                            stmt_pct = _s_pct
                            auto_matched += 1
                    
                    # 2a. TRY: Single invoice where the credit matches the invoice total LESS
                    # the customer's own settlement discount %. Only fires when no full-amount
                    # match was found above (a full-amount match always wins). Conservative —
                    # no guessing:
                    #   - uses each customer's OWN stored discount_percentage on their OWN invoice
                    #   - matches the SPECIFIC discounted figure to the cent (never widens tolerance)
                    #   - fires ONLY if EXACTLY ONE invoice's discounted target matches; zero or
                    #     2+ candidates means no auto-match (falls through to review).
                    if credit > 0 and not match_type:
                        _disc_candidates = []
                        for inv in outstanding:
                            inv_total = float(inv.get("total", 0))
                            if inv_total <= 0:
                                continue
                            _cust_rec = customer_names.get((inv.get("customer_name") or "").upper().strip())
                            if not _cust_rec:
                                continue
                            try:
                                _dpct = float(_cust_rec.get("discount_percentage", 0) or 0)
                            except (TypeError, ValueError):
                                _dpct = 0
                            # Sane settlement-discount range only — a large % is not a settlement discount.
                            if _dpct <= 0 or _dpct > 50:
                                continue
                            _target = round(inv_total * (1 - _dpct / 100.0), 2)
                            if abs(credit - _target) <= 0.02:
                                _disc_candidates.append((inv, _cust_rec, _dpct, round(inv_total - credit, 2)))
                        if len(_disc_candidates) == 1:
                            _d_inv, _d_cust, _d_pct, _d_short = _disc_candidates[0]
                            _d_cname = _d_cust.get("name", "") or _d_inv.get("customer_name", "")
                            match_type = "customer_payment"
                            match_category = "Customer Payment"
                            # Higher confidence when the name corroborates; the exact discounted
                            # amount alone is still a strong, precise signal.
                            match_confidence = 0.85 if (_d_cname[:5].upper() in desc_upper) else 0.7
                            match_reference = f"{_d_inv.get('invoice_number')} - {_d_cname} (less {_d_pct:g}% settlement discount)"
                            disc_invoice_id = _d_inv.get("id")
                            disc_invoice_num = _d_inv.get("invoice_number", "")
                            disc_customer_id = _d_cust.get("id") or _d_inv.get("customer_id", "")
                            disc_shortfall = _d_short
                            disc_pct = _d_pct
                            auto_matched += 1
                    
                    # 2b. TRY: Match credit to SUM of multiple invoices for same customer
                    # Only attempts this if the customer name appears in the description —
                    # we don't want wild combination guesses without that anchor.
                    # Combinations of 2 or 3 invoices only (4+ becomes guesswork).
                    if credit > 0 and not match_type:
                        # Group outstanding invoices by customer (only those whose name is in description)
                        cust_invoice_groups = {}
                        for inv in outstanding:
                            cust_name = (inv.get("customer_name") or "").upper().strip()
                            if not cust_name or len(cust_name) < 5:
                                continue
                            if cust_name[:5] not in desc_upper:
                                continue
                            cid = inv.get("customer_id") or cust_name
                            if cid not in cust_invoice_groups:
                                cust_invoice_groups[cid] = []
                            cust_invoice_groups[cid].append(inv)
                        
                        # For each customer with 2+ outstanding invoices, try combinations
                        combo_match = None
                        for cid, cust_invs in cust_invoice_groups.items():
                            if len(cust_invs) < 2:
                                continue
                            # Try pairs first (most common case)
                            for i in range(len(cust_invs)):
                                if combo_match:
                                    break
                                for j in range(i + 1, len(cust_invs)):
                                    pair_total = float(cust_invs[i].get("total", 0)) + float(cust_invs[j].get("total", 0))
                                    if abs(credit - pair_total) < 1:
                                        combo_match = [cust_invs[i], cust_invs[j]]
                                        break
                            # Try triples only if no pair found and there are 3+ invoices
                            if not combo_match and len(cust_invs) >= 3:
                                for i in range(len(cust_invs)):
                                    if combo_match:
                                        break
                                    for j in range(i + 1, len(cust_invs)):
                                        if combo_match:
                                            break
                                        for k in range(j + 1, len(cust_invs)):
                                            triple_total = (
                                                float(cust_invs[i].get("total", 0))
                                                + float(cust_invs[j].get("total", 0))
                                                + float(cust_invs[k].get("total", 0))
                                            )
                                            if abs(credit - triple_total) < 1:
                                                combo_match = [cust_invs[i], cust_invs[j], cust_invs[k]]
                                                break
                            if combo_match:
                                break
                        
                        if combo_match:
                            inv_numbers = " + ".join(inv.get("invoice_number", "") for inv in combo_match)
                            cust_label = combo_match[0].get("customer_name", "")
                            match_type = "customer_payment_combo"
                            match_category = "Customer Payment (multi-invoice)"
                            match_confidence = 0.85  # Slightly below single-match — Daphne reviews
                            match_reference = f"{inv_numbers} - {cust_label}"
                            # Store IDs for later — when Daphne confirms, backend will mark all paid
                            combo_invoice_ids = [inv.get("id") for inv in combo_match if inv.get("id")]
                            combo_invoice_nums = [inv.get("invoice_number", "") for inv in combo_match]
                            combo_customer_id = combo_match[0].get("customer_id", "")
                            suggested += 1
                            logger.info(f"[BANK IMPORT] Combo match: {credit:.2f} → {inv_numbers} ({cust_label})")
                    
                    # 3. TRY: Match debit to known expense keywords
                    if debit > 0 and not match_type:
                        for keyword, category in expense_keywords.items():
                            if keyword in desc_upper:
                                match_type = "expense_keyword"
                                match_category = category
                                match_confidence = 0.85
                                suggested += 1
                                break
                    
                    # 4. TRY: Match debit to payroll EFT (employee name + net amount + date)
                    if debit > 0 and not match_type:
                        txn_date_str = str(txn_date)[:10]
                        for ps in payslip_lookup:
                            if ps["matched"]:
                                continue
                            # Amount match: within R2
                            if abs(debit - ps["net"]) > 2.0:
                                continue
                            # Date match: within 5 days
                            try:
                                from datetime import datetime as _dt
                                _txn_d = _dt.strptime(txn_date_str, "%Y-%m-%d")
                                _ps_d = _dt.strptime(ps["date"], "%Y-%m-%d")
                                if abs((_txn_d - _ps_d).days) > 5:
                                    continue
                            except (ValueError, TypeError):
                                continue
                            # Name match: any name part (first name or surname) in bank description
                            name_found = any(part in desc_upper for part in ps["name_parts"])
                            if name_found:
                                match_type = "payroll"
                                match_category = "Salaries & Wages"
                                match_confidence = 0.92
                                match_reference = f"Salary — {ps['employee_name']} ({ps['date']})"
                                ps["matched"] = True
                                auto_matched += 1
                                break
                            # Fallback: amount + date match without name (lower confidence)
                            elif abs(debit - ps["net"]) < 0.50:
                                match_type = "payroll"
                                match_category = "Salaries & Wages?"
                                match_confidence = 0.6
                                match_reference = f"Maybe {ps['employee_name']}? ({ps['date']})"
                                suggested += 1
                                break
                    
                    # 5. TRY: Match debit to scanned expense (with split data carry-over)
                    if debit > 0 and not match_type:
                        txn_date_str = str(txn_date)[:10]
                        for _exp in all_expenses:
                            if _exp.get("bank_transaction_id") or _exp.get("bank_matched"):
                                continue
                            _exp_amt = float(_exp.get("amount", 0) or _exp.get("total", 0) or 0)
                            if _exp_amt <= 0 or abs(_exp_amt - debit) > 2.0:
                                continue
                            try:
                                from datetime import datetime as _dt
                                _txn_d = _dt.strptime(txn_date_str, "%Y-%m-%d")
                                _exp_d = _dt.strptime(str(_exp.get("date", ""))[:10], "%Y-%m-%d")
                                if abs((_txn_d - _exp_d).days) > 5:
                                    continue
                            except (ValueError, TypeError):
                                continue
                            # Match found — check for splits
                            _splits = _exp.get("splits")
                            _supplier = _exp.get("supplier_name", "") or _exp.get("supplier", "")
                            if _splits and len(_splits) > 1:
                                match_type = "expense_split"
                                _split_summary = " + ".join([s.get("category", "")[:20] for s in _splits[:3]])
                                match_category = f"Split: {_split_summary}"
                                match_confidence = 0.88
                                match_reference = f"Scanned: {_supplier}" if _supplier else "Scanned expense (split)"
                                _matched_expense_splits[generate_id()] = {"expense_id": _exp.get("id", ""), "splits": _splits}
                                suggested += 1
                            else:
                                match_type = "expense_match"
                                match_category = _exp.get("category", "Expense")
                                match_confidence = 0.88
                                match_reference = f"Scanned: {_supplier}" if _supplier else "Scanned expense"
                                suggested += 1
                            break
                    
                    # 6. TRY: Check learned patterns (CACHED — no DB calls)
                    if not match_type:
                        pattern_match = _fast_pattern_match(description)
                        if pattern_match.get("confidence", 0) > 0.5:
                            _pm_cat = pattern_match.get("category")
                            _safe_cat, _redirected = _direction_safe_pattern_category(
                                _pm_cat, desc_upper, credit > 0, _import_expense_cats)
                            if _safe_cat is None:
                                # income label on a money-out line — leave for manual review
                                pass
                            elif _redirected:
                                # expense label on a money-in line — never allowed
                                match_type = "income_redirect"
                                match_category = _safe_cat
                                match_confidence = 0.5
                                suggested += 1
                            else:
                                match_type = "learned_pattern"
                                match_category = _safe_cat
                                match_confidence = pattern_match.get("confidence", 0)
                                if match_confidence >= 0.8:
                                    auto_matched += 1
                                else:
                                    suggested += 1
                    
                    txn = {
                        "id": generate_id(),
                        "business_id": biz_id,
                        "date": txn_date,
                        "description": description,
                        "amount": amount,
                        "debit": debit,
                        "credit": credit,
                        "balance": running_balance,
                        "match_type": match_type,
                        "suggested_category": match_category,
                        "suggestion_confidence": match_confidence,
                        "match_reference": match_reference,
                        # ═══════════════════════════════════════════════════════════
                        # AUTO-ALLOCATE DISABLED — Deon's request 2026-05-06
                        # Smart match still produces suggestions (visible in UI),
                        # but NOTHING posts to GL until the user clicks Approve.
                        # Previously: matched/auto_matched = True at >= 0.85 confidence
                        # Now: ALL transactions go to "Suggested" (>= 0.85) or
                        # "Needs You" (< 0.85). User must approve every one.
                        # ═══════════════════════════════════════════════════════════
                        "matched": False,
                        "auto_matched": False,
                        "created_at": (_seq_base + _td_seq(microseconds=idx)).isoformat() + 'Z'
                    }
                    # Persist combo-match invoice IDs so UI can pre-select them on confirm
                    if combo_invoice_ids:
                        txn["combo_invoice_ids"] = combo_invoice_ids
                        txn["combo_invoice_nums"] = combo_invoice_nums
                        if combo_customer_id:
                            txn["combo_customer_id"] = combo_customer_id
                    # Persist settlement-discount match so UI can pre-select the customer,
                    # pre-tick the invoice and pre-tick the Discount Allowed box on confirm.
                    if disc_invoice_id:
                        txn["disc_invoice_id"] = disc_invoice_id
                        txn["disc_invoice_num"] = disc_invoice_num
                        txn["disc_customer_id"] = disc_customer_id
                        txn["disc_shortfall"] = disc_shortfall
                        txn["disc_pct"] = disc_pct
                    # Persist statement (full-account) match so UI can pre-select the customer,
                    # pre-tick ALL their invoices and pre-tick the Discount Allowed box on confirm.
                    if stmt_invoice_ids:
                        txn["stmt_invoice_ids"] = stmt_invoice_ids
                        txn["stmt_customer_id"] = stmt_customer_id
                        txn["stmt_shortfall"] = stmt_shortfall
                        txn["stmt_pct"] = stmt_pct
                    
                    txns_to_save.append(txn)
                    imported += 1
                    
                except Exception as row_err:
                    _row_errors += 1
                    if not _row_error_sample:
                        _row_error_sample = f"{type(row_err).__name__}: {row_err}"
                    logger.warning(f"[BANK] Row error: {row_err}")
                    continue
            
            # ═══════════════════════════════════════════════════════════════
            # BATCH SAVE — save all transactions at once
            # ═══════════════════════════════════════════════════════════════
            logger.info(f"[BANK IMPORT] Saving {len(txns_to_save)} transactions...")
            save_errors = 0
            for txn in txns_to_save:
                try:
                    db.save("bank_transactions", txn)
                except Exception as save_err:
                    save_errors += 1
                    if save_errors <= 3:
                        logger.warning(f"[BANK] Save error: {save_err}")
            if save_errors > 0:
                logger.warning(f"[BANK IMPORT] {save_errors} save errors out of {len(txns_to_save)}")
            
            # ═══════════════════════════════════════════════════════════════
            # POST-IMPORT: Balance chain validation
            # If the PDF included running balances, verify the chain is
            # consistent. Duplicate OCR entries break the balance sequence.
            # Remove any transaction that breaks the chain.
            # ═══════════════════════════════════════════════════════════════
            balance_removed = 0
            try:
                if imported > 0:
                    fresh_txns = db.get("bank_transactions", {"business_id": biz_id}) or []
                    # Sort by date, then by balance (to establish order)
                    fresh_txns.sort(key=lambda x: (str(x.get("date", ""))[:10], float(x.get("balance", 0) or 0)))
                    
                    # Group by date+amount to find remaining duplicates
                    from collections import defaultdict
                    da_groups = defaultdict(list)
                    for t in fresh_txns:
                        _d = str(t.get("date", ""))[:10]
                        _amt = round(float(t.get("amount", 0) or 0), 2)
                        da_groups[(_d, _amt)].append(t)
                    
                    # For any group with 2+ entries, check if descriptions are similar
                    import re as _re_bc
                    for key, group in da_groups.items():
                        if len(group) <= 1:
                            continue
                        # Compare each pair - if core text matches, delete the duplicate
                        seen_cores = {}
                        for t in group:
                            desc = (t.get("description") or "").upper()
                            core = _re_bc.sub(r'[0-9#:@%\-\.\s]+', '', desc)[:20]
                            if core in seen_cores:
                                # This is a duplicate — delete it
                                try:
                                    db.delete("bank_transactions", t["id"])
                                    balance_removed += 1
                                    logger.info(f"[BANK IMPORT] Balance chain removed dupe: {key[0]} {key[1]} {desc[:40]}")
                                except Exception:
                                    pass
                            else:
                                seen_cores[core] = t
                    
                    if balance_removed > 0:
                        imported -= balance_removed
                        skipped_dupes += balance_removed
                        logger.info(f"[BANK IMPORT] Balance chain validation removed {balance_removed} duplicates")
            except Exception as bc_err:
                logger.warning(f"[BANK IMPORT] Balance chain check error (non-fatal): {bc_err}")
            
            # Invoice matching skipped during import for speed — runs on-demand via Zane
            logger.info(f"[BANK IMPORT] Skipping invoice matching during import (will run on-demand)")
            
            needs_attention = imported - auto_matched - suggested
            
            dupe_msg = f" ({skipped_dupes} duplicates skipped)" if skipped_dupes > 0 else ""
            range_msg = f" ({skipped_out_of_range} outside date range)" if skipped_out_of_range > 0 else ""
            logger.info(f"[BANK IMPORT] Done: {imported} imported, {skipped_dupes} dupes skipped, {skipped_out_of_range} out-of-range skipped, {auto_matched} auto-matched, {suggested} suggested")
            
            return jsonify({
                "success": True, 
                "message": f"Imported {imported} transactions{dupe_msg}{range_msg}",
                "stats": {
                    "total": imported,
                    "auto_matched": auto_matched,
                    "suggested": suggested,
                    "needs_attention": max(0, needs_attention),
                    "duplicates_skipped": skipped_dupes,
                    "out_of_range_skipped": skipped_out_of_range,
                    "rows_parsed": len(data_rows),
                    "row_errors": _row_errors,
                    "row_error_sample": _row_error_sample,
                    "filename": filename,
                    "sb_prov_detected": bool(locals().get('_sb_prov_active'))
                }
            })
            
        except Exception as e:
            logger.error(f"[BANK] Import error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/banking/categorize", methods=["POST"])
    @login_required
    def api_banking_categorize():
        """Categorize a bank transaction and learn from it"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        try:
            data = request.get_json()
            txn_id = data.get("id")
            category = data.get("category")
            description = data.get("description", "")
            _picked_entity_id = data.get("entity_id", "") or ""
            _picked_entity_name = data.get("entity_name", "") or ""
            _picked_invoice_ids = data.get("invoice_ids", []) or []
            _picked_invoice_nums = data.get("invoice_nums", []) or []
            _discount_allowed = bool(data.get("discount_allowed", False))
            
            if not txn_id or not category:
                return jsonify({"success": False, "error": "Missing data"})
            
            # Get transaction
            txn = db.get_one("bank_transactions", txn_id)
            if not txn:
                return jsonify({"success": False, "error": "Transaction not found"})
            
            # Use transaction description if none provided
            if not description:
                description = txn.get("description", "")
            
            # Mark as matched and save category
            txn["matched"] = True
            txn["category"] = category
            txn["matched_at"] = now()
            db.save("bank_transactions", txn)
            
            # LEARN from this categorization!
            if description:
                BankLearning.learn_from_categorization(biz_id, description, category)
            
            # Handle based on category type
            debit = float(txn.get("debit", 0))
            credit = float(txn.get("credit", 0))
            amount = float(txn.get("amount", 0))
            
            # Get GL code from comprehensive lookup
            gl_code = IndustryKnowledge.get_gl_code(category, business_id=biz_id)
            
            # SARS: No VAT claim on fuel or entertainment
            no_vat_cats = ["fuel", "entertainment", "meals", "membership"]
            is_no_vat = any(nv in category.lower() for nv in no_vat_cats)
            
            # === SPECIAL CATEGORIES with custom GL logic ===
            # These need specific double-entry treatment, not generic expense/income
            
            special_categories = {
                # Money IN specials
                "Customer Payment",      # Debit Bank, Credit Debtors (1200)
                "POS Deposit",           # Debit Bank, Credit Petty Cash (1100)
                "Card Settlement",       # Debit Bank, Credit Card Clearing (1010)
                "Supplier Payment",      # Money OUT: Debit Creditors (2000), Credit Bank
                "VAT Payment to SARS",   # Debit VAT Output (2100), Credit Bank - paying liability
                "Owner Drawings",        # Debit Drawings (3200), Credit Bank
                "Owner Capital Introduced",  # Debit Bank, Credit Capital (3000)
                "Loan",                  # IN: Debit Bank, Credit Loan (2300). OUT: Debit Loan (2300), Credit Bank
                "Loan Repayment",        # Debit Loan (2300), Credit Bank
                "Transfer Between Accounts",  # No journal - need both accounts
                "Ignore",               # No journal
            }
            
            txn_date = txn.get("date", today())
            ref = f"BNK-{txn_id[:8]}"
            desc_short = description[:50]

            # Capture the actual GL journal lines posted during this categorization
            # so the ledger can show where the transaction was allocated in the GL.
            _alloc_gl_lines = []
            _orig_create_journal_entry = create_journal_entry
            def _cje(_b, _d, _ds, _r, _lines):
                try:
                    if _lines:
                        _alloc_gl_lines.extend(_lines)
                except Exception:
                    pass
                return _orig_create_journal_entry(_b, _d, _ds, _r, _lines)
            
            # Determine if money out (expense) or money in (income/payment)
            if debit > 0 or amount < 0:
                expense_amount = debit if debit > 0 else abs(amount)
                expense_rounded = round(expense_amount, 2)
                
                if category in special_categories:
                    # --- SPECIAL MONEY OUT HANDLING ---
                    if category == "Owner Drawings":
                        _cje(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "drawings"), "debit": expense_rounded, "credit": 0},  # Drawings
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "Loan Repayment":
                        _cje(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "uif"), "debit": expense_rounded, "credit": 0},  # Loan liability down
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "Loan":
                        # Money OUT as Loan = repaying loan principal
                        _cje(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "uif"), "debit": expense_rounded, "credit": 0},  # Loan liability down
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "Customer Payment":
                        # Money OUT to customer = refund from bank
                        _cje(biz_id, txn_date, f"Customer refund: {desc_short}", ref, [
                            {"account_code": gl(biz_id, "sales"), "debit": expense_rounded, "credit": 0},   # Sales reversed
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},    # Bank out
                        ])
                    elif category == "Supplier Payment":
                        logger.info(f"[BANK] === Supplier Payment R{expense_amount} — starting processing ===")
                        _cje(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "creditors"), "debit": expense_rounded, "credit": 0},
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},
                        ])
                        
                        _matched_supplier = None
                        try:
                            # Priority 0: User explicitly picked supplier invoices from the picker
                            # Allocate payment amount across invoices in order — only mark paid if fully covered
                            if _picked_invoice_ids:
                                _remaining_pay = expense_amount
                                for _inv_id in _picked_invoice_ids:
                                    _picked_sinv = db.get_one("supplier_invoices", _inv_id)
                                    if _picked_sinv and _picked_sinv.get("status") not in ("paid", "credited"):
                                        _inv_total = float(_picked_sinv.get("total", 0))
                                        if _remaining_pay >= _inv_total - 0.01:
                                            # Fully paid
                                            _picked_sinv["status"] = "paid"
                                            _picked_sinv["paid_date"] = txn_date
                                            _picked_sinv["paid_amount"] = _inv_total
                                            _picked_sinv["payment_reference"] = ref
                                            db.save("supplier_invoices", _picked_sinv)
                                            _remaining_pay -= _inv_total
                                            logger.info(f"[BANK] Marked supplier inv {_picked_sinv.get('invoice_number','?')} as PAID (R{_inv_total})")
                                        else:
                                            # Partial — record partial payment but keep outstanding
                                            _picked_sinv["paid_amount"] = round(float(_picked_sinv.get("paid_amount", 0)) + _remaining_pay, 2)
                                            _picked_sinv["payment_reference"] = ref
                                            db.save("supplier_invoices", _picked_sinv)
                                            logger.info(f"[BANK] Partial payment R{_remaining_pay:.2f} on {_picked_sinv.get('invoice_number','?')} (total R{_inv_total})")
                                            _remaining_pay = 0
                                        if not _matched_supplier and _picked_sinv.get("supplier_id"):
                                            _matched_supplier = db.get_one("suppliers", _picked_sinv["supplier_id"])
                                        if _remaining_pay <= 0.01:
                                            break
                            
                            # Priority 1: User explicitly picked a supplier
                            if _picked_entity_id and not _matched_supplier:
                                _matched_supplier = db.get_one("suppliers", _picked_entity_id)
                                if _matched_supplier:
                                    logger.info(f"[BANK] Supplier matched via entity picker: {_matched_supplier.get('name')}")
                            # Priority 2: match_reference from auto-matching
                            if not _matched_supplier:
                                match_ref = txn.get("match_reference", "")
                                if match_ref:
                                    inv_num = match_ref.split(" - ")[0] if " - " in match_ref else match_ref
                                    if inv_num:
                                        s_invoices = db.get("supplier_invoices", {"business_id": biz_id, "invoice_number": inv_num})
                                        if s_invoices:
                                            s_inv = s_invoices[0]
                                            s_inv["status"] = "paid"
                                            s_inv["paid_date"] = txn_date
                                            db.save("supplier_invoices", s_inv)
                                            if s_inv.get("supplier_id"):
                                                _matched_supplier = db.get_one("suppliers", s_inv["supplier_id"])
                            # Priority 3: name match in description
                            if not _matched_supplier:
                                _desc_upper = (txn.get("description") or "").upper()
                                _all_suppliers = db.get("suppliers", {"business_id": biz_id}) or []
                                # Generic words that appear in many bank descriptions — NEVER match on these
                                _generic_words = {'PTY', 'LTD', 'THE', 'AND', 'FOR', 'BANK', 'ELECT',
                                                  'ELECTRONIC', 'PAYMENT', 'TRANSFER', 'CREDIT', 'DEBIT',
                                                  'BUSINESS', 'ACCOUNT', 'SERVICE', 'FEE', 'CHARGE',
                                                  'CHARGES', 'CASH', 'DEPOSIT', 'FROM', 'BANKING'}
                                for _s in _all_suppliers:
                                    _sname = (_s.get("name") or "").upper().strip()
                                    if _sname and len(_sname) >= 3:
                                        _swords = [w for w in _sname.split() if len(w) >= 3 and w not in _generic_words]
                                        if _swords and any(w in _desc_upper for w in _swords):
                                            _matched_supplier = _s
                                            break
                            if _matched_supplier:
                                # Supplier balance is now calculated dynamically — no manual update needed
                                pass
                        except Exception as e:
                            logger.error(f"[BANK] Supplier matching error (payment still created): {e}")
                        
                        # === UPDATE TXN WITH SUPPLIER NAME ===
                        _sup_name = _matched_supplier.get("name", "") if _matched_supplier else ""
                        if _sup_name:
                            txn["matched_name"] = _sup_name
                            txn["matched_entity_type"] = "supplier"
                            txn["matched_entity_id"] = _matched_supplier.get("id", "") if _matched_supplier else ""
                            db.save("bank_transactions", txn)
                        
                        # === SUPPLIER PAYMENT — ALWAYS RUNS ===
                        try:
                            logger.info(f"[BANK] Creating supplier payment...")
                            _sp = {
                                "id": generate_id(),
                                "business_id": biz_id,
                                "supplier_id": _matched_supplier.get("id", "") if _matched_supplier else "",
                                "supplier_name": _matched_supplier.get("name", description[:60]) if _matched_supplier else (_picked_entity_name or description[:60]),
                                "amount": float(expense_amount),
                                "date": txn_date,
                                "method": "eft",
                                "reference": ref,
                                "source": "banking_recon",
                                "created_at": now()
                            }
                            _sps, _spe = db.save("supplier_payments", _sp)
                            logger.info(f"[BANK] Supplier payment save result: success={_sps}")
                        except Exception as e:
                            logger.error(f"[BANK] Supplier payment CRASHED: {e}")
                    elif category == "VAT Payment to SARS":
                        # Paying VAT liability - NOT an expense!
                        _cje(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "vat_output"), "debit": expense_rounded, "credit": 0},  # VAT Output liability down
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "POS Deposit":
                        # POS Deposit as money OUT doesn't apply - skip
                        pass
                    # Transfer/Ignore = no journal entry
                    
                else:
                    # --- REGULAR EXPENSE ---
                    # Try to link expense to a supplier
                    _exp_supplier_id = ""
                    _exp_supplier_name = ""
                    if _picked_entity_id and _picked_entity_id != "__skip__":
                        _exp_supplier_id = _picked_entity_id
                        _exp_supplier_name = _picked_entity_name or ""
                    if not _exp_supplier_id:
                        try:
                            _desc_upper = (description or "").upper()
                            _all_sups = db.get("suppliers", {"business_id": biz_id}) or []
                            # Generic words that appear in many bank descriptions — NEVER match on these
                            _generic_words = {'PTY', 'LTD', 'THE', 'AND', 'FOR', 'BANK', 'ELECT',
                                              'ELECTRONIC', 'PAYMENT', 'TRANSFER', 'CREDIT', 'DEBIT',
                                              'BUSINESS', 'ACCOUNT', 'SERVICE', 'FEE', 'CHARGE',
                                              'CHARGES', 'CASH', 'DEPOSIT', 'FROM', 'BANKING'}
                            for _s in _all_sups:
                                _sn = (_s.get("name") or "").upper().strip()
                                if _sn and len(_sn) >= 3:
                                    _sw = [w for w in _sn.split() if len(w) >= 3 and w not in _generic_words]
                                    if _sw and any(w in _desc_upper for w in _sw):
                                        _exp_supplier_id = _s.get("id", "")
                                        _exp_supplier_name = _s.get("name", "")
                                        break
                        except Exception:
                            pass
                    expense = RecordFactory.expense(
                        business_id=biz_id,
                        description=description,
                        amount=expense_amount,
                        date=txn_date,
                        category=category,
                        category_code=gl_code,
                        reference=f"Bank: {txn_id[:8]}",
                        payment_method="eft"
                    )
                    if _exp_supplier_id:
                        expense["supplier_id"] = _exp_supplier_id
                        expense["supplier_name"] = _exp_supplier_name
                        expense["supplier"] = _exp_supplier_name
                    db.save("expenses", expense)
                    
                    # Create journal entry with proper GL code
                    vat_amount = round(expense_amount * 15 / 115, 2) if not is_no_vat else 0
                    net_amount = round(expense_amount - vat_amount, 2)
                    
                    journal_entries = [
                        {"account_code": gl_code, "debit": net_amount, "credit": 0},
                    ]
                    if vat_amount > 0:
                        journal_entries.append({"account_code": gl(biz_id, "vat_input"), "debit": vat_amount, "credit": 0})
                    journal_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(expense_amount, 2)})
                    
                    _cje(biz_id, txn_date, desc_short, ref, journal_entries)
                    logger.info(f"[BANK] Created expense: {category} GL={gl_code} R{expense_amount}")
            
            elif credit > 0 or amount > 0:
                income_amount = credit if credit > 0 else amount
                income_rounded = round(income_amount, 2)
                
                if category == "Customer Payment":
                    logger.info(f"[BANK] === Customer Payment R{income_amount} — starting processing ===")
                    # Customer paying their account - reduce debtors
                    _cje(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "debtors"), "debit": 0, "credit": income_rounded},    # Debtors down
                    ])
                    
                    # Try to mark invoice as paid — in its own try/except so receipt ALWAYS runs
                    matched_invoice = None
                    matched_customer = None
                    _total_discount_allowed = 0.0  # sum of shortfalls written off as Discount Allowed
                    try:
                        # Priority 0: User explicitly picked invoices from the picker
                        # Allocate payment amount across invoices in order — only mark paid if fully covered
                        if _picked_invoice_ids:
                            _remaining_pay = income_amount
                            for _inv_id in _picked_invoice_ids:
                                _picked_inv = db.get_one("invoices", _inv_id)
                                if _picked_inv and _picked_inv.get("status") not in ("paid", "credited"):
                                    _inv_total = float(_picked_inv.get("total", 0))
                                    _inv_outstanding = round(_inv_total - float(_picked_inv.get("paid_amount", 0) or 0), 2)
                                    if _remaining_pay >= _inv_outstanding - 0.01:
                                        # Fully paid
                                        _picked_inv["status"] = "paid"
                                        _picked_inv["paid_date"] = txn_date
                                        _picked_inv["paid_amount"] = _inv_total
                                        _picked_inv["paid_via"] = "banking_recon"
                                        _picked_inv["payment_reference"] = ref
                                        db.save("invoices", _picked_inv)
                                        _remaining_pay -= _inv_outstanding
                                        logger.info(f"[BANK] Marked {_picked_inv.get('invoice_number','?')} as PAID (R{_inv_total})")
                                    elif _discount_allowed and (_inv_outstanding - _remaining_pay) <= _inv_outstanding * 0.5:
                                        # Shortfall written off as Discount Allowed — invoice CLOSED.
                                        # The remaining payment covers part; the gap becomes discount.
                                        _shortfall = round(_inv_outstanding - _remaining_pay, 2)
                                        _picked_inv["status"] = "paid"
                                        _picked_inv["paid_date"] = txn_date
                                        _picked_inv["paid_amount"] = _inv_total
                                        _picked_inv["paid_via"] = "banking_recon"
                                        _picked_inv["payment_reference"] = ref
                                        _picked_inv["discount_allowed"] = _shortfall
                                        db.save("invoices", _picked_inv)
                                        _total_discount_allowed = round(_total_discount_allowed + _shortfall, 2)
                                        _remaining_pay = 0
                                        logger.info(f"[BANK] {_picked_inv.get('invoice_number','?')} CLOSED with Discount Allowed R{_shortfall:.2f}")
                                        # Create a Discount Allowed credit-note record (DA-) so the
                                        # shortfall shows as a CREDIT on the customer statement and
                                        # reduces the calculated balance. The GL journal is posted
                                        # below; this record only affects the customer sub-ledger
                                        # (no double-posting). Number generated inline (next_document_number
                                        # is not available in this module).
                                        try:
                                            _da_sub = round(_shortfall / 1.15, 2)
                                            _da_v = round(_shortfall - _da_sub, 2)
                                            _da_existing = db.get("credit_notes", {"business_id": biz_id}) or []
                                            _da_max = 0
                                            for _dc in _da_existing:
                                                _dn = str(_dc.get("credit_note_number", "") or "")
                                                if _dn.startswith("DA-"):
                                                    _digits = "".join(ch for ch in _dn[3:] if ch.isdigit())
                                                    if _digits:
                                                        _da_max = max(_da_max, int(_digits))
                                            _da_num = f"DA-{_da_max + 1:05d}"
                                            db.save("credit_notes", {
                                                "id": generate_id(), "business_id": biz_id,
                                                "credit_note_number": _da_num, "date": txn_date,
                                                "invoice_id": _picked_inv.get("id", ""),
                                                "invoice_number": _picked_inv.get("invoice_number", ""),
                                                "customer_id": _picked_inv.get("customer_id", ""),
                                                "customer_name": _picked_inv.get("customer_name", ""),
                                                "reason": "Settlement discount on payment",
                                                "items": json.dumps([{"description": "Discount Allowed", "quantity": 1, "price": _da_sub, "total": _da_sub}]),
                                                "subtotal": _da_sub, "vat": _da_v, "total": _shortfall,
                                                "kind": "discount_allowed", "credit_type": "discount_allowed",
                                                "created_by": None, "created_at": now()
                                            })
                                            logger.info(f"[BANK] Discount Allowed credit-note {_da_num} created (R{_shortfall:.2f})")
                                        except Exception as _da_cn_err:
                                            logger.error(f"[BANK] DA credit-note record failed: {_da_cn_err}")
                                    else:
                                        # Partial — record partial payment but keep outstanding
                                        _picked_inv["paid_amount"] = round(float(_picked_inv.get("paid_amount", 0)) + _remaining_pay, 2)
                                        _picked_inv["paid_via"] = "banking_recon"
                                        _picked_inv["payment_reference"] = ref
                                        db.save("invoices", _picked_inv)
                                        logger.info(f"[BANK] Partial payment R{_remaining_pay:.2f} on {_picked_inv.get('invoice_number','?')} (total R{_inv_total})")
                                        _remaining_pay = 0
                                    if not matched_invoice:
                                        matched_invoice = _picked_inv
                                    if not matched_customer and _picked_inv.get("customer_id"):
                                        matched_customer = db.get_one("customers", _picked_inv["customer_id"])
                                    if _remaining_pay <= 0.01:
                                        break
                        
                        # Discount Allowed journal — post the written-off shortfall.
                        # The VAT portion is split out automatically (the original
                        # invoice charged VAT on the full amount, so a proportional
                        # part of the discount is VAT recoverable):
                        #   DR Discount Allowed (net)  DR VAT Output (vat)  CR Debtors (total)
                        if _total_discount_allowed > 0.01:
                            _da_vat = round(_total_discount_allowed * 15 / 115, 2)
                            _da_net = round(_total_discount_allowed - _da_vat, 2)
                            # Ensure the Discount Allowed account exists for this
                            # business (auto-creates it if missing — platform-wide,
                            # no manual SQL needed). Falls back to gl() if the
                            # helper wasn't supplied.
                            if ensure_gl_account:
                                _da_code = ensure_gl_account(biz_id, "discount_allowed", "Discount Allowed", "expense", "Expenses")
                            else:
                                _da_code = gl(biz_id, "discount_allowed")
                            _da_lines = [
                                {"account_code": _da_code, "debit": _da_net, "credit": 0},
                            ]
                            if _da_vat > 0:
                                _da_lines.append({"account_code": gl(biz_id, "vat_output"), "debit": _da_vat, "credit": 0})
                            _da_lines.append({"account_code": gl(biz_id, "debtors"), "debit": 0, "credit": _total_discount_allowed})
                            _cje(biz_id, txn_date, f"Discount Allowed: {desc_short}", ref, _da_lines)
                            logger.info(f"[BANK] Discount Allowed journal posted: net R{_da_net} vat R{_da_vat} total R{_total_discount_allowed}")
                        
                        # Priority 1: User explicitly picked a customer
                        if _picked_entity_id and not matched_customer:
                            matched_customer = db.get_one("customers", _picked_entity_id)
                            if matched_customer:
                                logger.info(f"[BANK] Customer matched via entity picker: {matched_customer.get('name')}")
                                # Customer balance is now calculated dynamically — no manual update needed
                        
                        # Priority 2: match_reference
                        match_ref = txn.get("match_reference", "")
                        if match_ref and not matched_invoice:
                            inv_num = match_ref.split(" - ")[0] if " - " in match_ref else match_ref
                            inv_num = inv_num.replace("Maybe ", "").replace("?", "").strip()
                            if inv_num.startswith("INV"):
                                invoices = db.get("invoices", {"business_id": biz_id, "invoice_number": inv_num})
                                if invoices:
                                    matched_invoice = invoices[0]
                        
                        outstanding_inv = []
                        if not matched_invoice:
                            outstanding_inv = db.get("invoices", {"business_id": biz_id}) or []
                            outstanding_inv = [i for i in outstanding_inv if i.get("status") not in ("paid", "credited")]
                            desc_upper = (txn.get("description") or "").upper()
                            for inv in outstanding_inv:
                                inv_total = float(inv.get("total", 0))
                                cust_name = (inv.get("customer_name") or "").upper().strip()
                                if abs(income_amount - inv_total) < 1 and cust_name and len(cust_name) >= 3 and cust_name[:6] in desc_upper:
                                    matched_invoice = inv
                                    break
                        
                        if not matched_invoice and outstanding_inv:
                            amount_matches = [i for i in outstanding_inv if abs(income_amount - float(i.get("total", 0))) < 1]
                            if len(amount_matches) == 1:
                                matched_invoice = amount_matches[0]
                        
                        if matched_invoice:
                            matched_invoice["status"] = "paid"
                            matched_invoice["paid_date"] = txn_date
                            matched_invoice["paid_amount"] = income_amount
                            matched_invoice["paid_via"] = "banking_recon"
                            db.save("invoices", matched_invoice)
                            logger.info(f"[BANK] Marked {matched_invoice.get('invoice_number','?')} as PAID")
                            cust_id = matched_invoice.get("customer_id")
                            if cust_id and not _picked_entity_id:
                                # Customer balance is now calculated dynamically — no manual update needed
                                pass
                            if not matched_customer and cust_id:
                                matched_customer = db.get_one("customers", cust_id)
                        elif not matched_customer:
                            # Priority 3: name match in description
                            desc_upper = (txn.get("description") or "").upper()
                            all_customers = db.get("customers", {"business_id": biz_id}) or []
                            for c in all_customers:
                                cname = (c.get("name") or "").upper().strip()
                                if cname and len(cname) >= 3:
                                    # Match any significant word (3+ chars) of customer name in description
                                    _cwords = [w for w in cname.split() if len(w) >= 3]
                                    if _cwords and any(w in desc_upper for w in _cwords):
                                        matched_customer = c
                                        break
                            # Customer balance is now calculated dynamically — no manual update needed
                    except Exception as e:
                        logger.error(f"[BANK] Invoice matching error (receipt still created): {e}")
                    
                    # === UPDATE TXN WITH CUSTOMER NAME + INVOICE REF ===
                    try:
                        _cust_name = ""
                        _inv_num = ""
                        _inv_id = ""
                        if matched_invoice:
                            _cust_name = matched_invoice.get("customer_name", "")
                            _inv_num = matched_invoice.get("invoice_number", "")
                            _inv_id = matched_invoice.get("id", "")
                            txn["matched_entity_id"] = matched_invoice.get("customer_id", "")
                        elif matched_customer:
                            _cust_name = matched_customer.get("name", "")
                            txn["matched_entity_id"] = matched_customer.get("id", "")
                        if _cust_name:
                            txn["matched_name"] = _cust_name
                            txn["matched_entity_type"] = "customer"
                            txn["matched_invoice_number"] = _inv_num
                            txn["matched_invoice_id"] = _inv_id
                            db.save("bank_transactions", txn)
                    except Exception:
                        pass
                    
                    # === RECEIPT — ALWAYS RUNS ===
                    try:
                        logger.info(f"[BANK] Creating receipt...")
                        _rcid = ""
                        _rcname = description[:60]
                        if matched_invoice:
                            _rcid = matched_invoice.get("customer_id", "")
                            _rcname = matched_invoice.get("customer_name", description[:60])
                        elif matched_customer:
                            _rcid = matched_customer.get("id", "")
                            _rcname = matched_customer.get("name", description[:60])
                        _receipt = {
                            "id": generate_id(),
                            "business_id": biz_id,
                            "customer_id": _rcid,
                            "customer_name": _rcname,
                            "amount": float(income_amount),
                            "date": txn_date,
                            "method": "eft",
                            "reference": ref,
                            "source": "banking_recon",
                            "created_at": now()
                        }
                        _rs, _re = db.save("receipts", _receipt)
                        logger.info(f"[BANK] Receipt save result: success={_rs}")
                    except Exception as e:
                        logger.error(f"[BANK] Receipt CRASHED: {e}")
                                
                elif category == "POS Deposit":
                    # POS cash deposited into bank
                    _cje(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "cash"), "debit": 0, "credit": income_rounded},    # Cash On Hand down
                    ])
                    
                elif category == "Card Settlement":
                    # Card-machine settlement deposited into the bank — clears Card Clearing (1010).
                    # Net effect: bank up by the actual deposit, Card Clearing reduced by the same.
                    _cje(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up (actual deposit)
                        {"account_code": "1010", "debit": 0, "credit": income_rounded},               # Card Clearing down
                    ])
                    
                elif category == "Owner Capital Introduced":
                    _cje(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "capital"), "debit": 0, "credit": income_rounded},    # Capital up
                    ])
                    
                elif category == "Loan":
                    # Receiving loan funds
                    _cje(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "uif"), "debit": 0, "credit": income_rounded},    # Loan liability up
                    ])
                    
                elif category == "Refund":
                    # Refund received - credit original expense
                    _cje(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": "7900", "debit": 0, "credit": income_rounded},    # Sundry expenses reversed
                    ])
                    
                elif category in ["Transfer Between Accounts", "Ignore"]:
                    pass  # No journal entry
                    
                else:
                    # Regular income
                    _cje(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},
                        {"account_code": gl_code, "debit": 0, "credit": income_rounded},
                    ])
            
            # === ALLOCATION LOG ===
            try:
                # Ignore / Transfer have no GL impact — do NOT log them as allocations,
                # otherwise they clutter the ledger and show up as false duplicates.
                if log_allocation and category not in ("Ignore", "Transfer Between Accounts", "Transfer"):
                    _is_expense = debit > 0 or amount < 0
                    log_allocation(
                        business_id=biz_id, allocation_type="bank_categorize", source_table="bank_transactions", source_id=txn_id,
                        description=f"Bank: {description[:100]} → {category}",
                        amount=float(debit if debit > 0 else credit if credit > 0 else abs(amount)),
                        category=category, category_code=gl_code,
                        ai_reasoning=f"Bank transaction categorized as '{category}' (GL {gl_code}). {'Auto-matched' if txn.get('auto_categorized') else 'Manual review'}. Original desc: {description[:100]}",
                        ai_confidence="HIGH" if txn.get("auto_categorized") else "",
                        ai_worker="BankLearning" if txn.get("auto_categorized") else "",
                        supplier_name=txn.get("supplier_name", "") or description.split()[0][:30] if description else "",
                        payment_method="eft", reference=f"BNK-{txn_id[:8]}",
                        gl_entries=(_alloc_gl_lines or None),
                        transaction_date=txn_date,
                        created_by=session.get("user_id", ""), created_by_name=(Auth.get_current_user() or {}).get("name", "")
                    )
            except Exception:
                pass
            
            return jsonify({"success": True, "message": f"Categorized as {category}"})
            
        except Exception as e:
            logger.error(f"[BANK] Categorize failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/banking/zane-suggest", methods=["POST"])
    @login_required
    def api_banking_zane_suggest():
        """
        Zane analyzes a bank transaction and suggests allocation.
        NOW WITH CLARIFICATION — Zane asks smart follow-up questions when needed!
        Returns: suggested category, reason, confidence, clarification if needed.
        """
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("name", "Business") if business else "Business"
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        try:
            data = request.get_json()
            description = data.get("description", "")
            debit = float(data.get("debit", 0))
            credit = float(data.get("credit", 0))
            date = data.get("date", "")
            user_answer = data.get("clarification_answer", "")
            
            if not description:
                return jsonify({"success": False, "error": "No description"})
            
            # Get all available categories — comprehensive list
            all_category_names = IndustryKnowledge.get_all_category_names()
            
            # ═══ PRIORITY 1: SCANNED INVOICE MATCH — user already scanned this, trust it ═══
            if not user_answer:
                amount = debit if debit > 0 else credit
                direction = "out" if debit > 0 else "in"
                inv_match = InvoiceMatch.find_match(biz_id, description, amount, date, direction)
                if inv_match and inv_match.get("confidence", 0) >= 0.5:
                    logger.info(f"[BANK ZANE] Invoice match: '{description[:30]}' → {inv_match.get('category', '')}")
                    return jsonify({
                        "success": True,
                        "category": inv_match.get("category", ""),
                        "reason": inv_match.get("reason", "Matched to scanned invoice"),
                        "confidence": inv_match.get("confidence", 0.8),
                        "source": "invoice_match",
                        "needs_clarification": False,
                        "vat_warning": "",
                        "match_reference": inv_match.get("reference", ""),
                        "all_categories": all_category_names
                    })
            
            # ═══ PRIORITY 1b: SCANNED EXPENSE MATCH — check if a matching expense exists with splits ═══
            if not user_answer and debit > 0:
                try:
                    _match_amount = debit if debit > 0 else credit
                    _all_expenses = db.get("expenses", {"business_id": biz_id}) or []
                    for _exp in _all_expenses:
                        if _exp.get("bank_transaction_id") or _exp.get("bank_matched"):
                            continue
                        _exp_amt = float(_exp.get("amount", 0) or _exp.get("total", 0) or 0)
                        if abs(_exp_amt - _match_amount) <= 2.0:
                            # Check date within 5 days
                            try:
                                from datetime import datetime as _dt
                                _txn_d = _dt.strptime(str(date)[:10], "%Y-%m-%d")
                                _exp_d = _dt.strptime(str(_exp.get("date", ""))[:10], "%Y-%m-%d")
                                if abs((_txn_d - _exp_d).days) <= 5:
                                    _splits = _exp.get("splits")
                                    if _splits and len(_splits) > 1:
                                        # Found a split expense match — tell user about the split
                                        _split_desc = ", ".join([s.get("category", "") + " R" + str(s.get("amount", 0)) for s in _splits])
                                        logger.info(f"[BANK ZANE] Split expense match: '{description[:30]}' → {_split_desc}")
                                        return jsonify({
                                            "success": True,
                                            "category": "Split: " + " + ".join([s.get("category", "")[:20] for s in _splits[:3]]),
                                            "reason": f"Hierdie lyk soos die slip wat jy gescanned het ({_exp.get('supplier_name', '')}) — dit was gesplit: {_split_desc}. Klik Split om dieselfde verdeling te gebruik.",
                                            "confidence": 0.85,
                                            "source": "expense_split_match",
                                            "needs_clarification": False,
                                            "vat_warning": "",
                                            "has_split_match": True,
                                            "matched_expense_id": _exp.get("id", ""),
                                            "matched_splits": _splits,
                                            "all_categories": all_category_names
                                        })
                            except (ValueError, TypeError):
                                pass
                except Exception as _e:
                    logger.error(f"[BANK ZANE] Expense match check error: {_e}")
            
            # ═══ PRIORITY 2: BANKLEARNING — user already categorized this type before ═══
            existing = BankLearning.suggest_category(biz_id, description)
            if existing and existing.get("confidence", 0) >= 0.85 and not user_answer:
                return jsonify({
                    "success": True,
                    "category": existing.get("category", ""),
                    "reason": f"I've seen this type of transaction {existing.get('times_seen', 1)} times before — always {existing.get('category')}.",
                    "confidence": existing.get("confidence", 0.85),
                    "source": "learned",
                    "needs_clarification": False,
                    "all_categories": all_category_names
                })
            
            # ═══ PRIORITY 3: KNOWN PATTERNS — obvious matches, still go through AI drill-down ═══
            if not user_answer:
                desc_upper = description.upper()
                
                # EFTPOS card settlements: use the money DIRECTION (bank column), NOT the
                # DR/CR in the description — on Standard Bank "DR EFTPOS"/"CR EFTPOS" means
                # debit-card vs credit-card, not money out vs in. Money IN clears the Card
                # Clearing account (1010) since income was already booked at POS; money OUT
                # is a card-machine fee.
                if "EFTPOS" in desc_upper or "SETTLEMENT" in desc_upper:
                    if credit > 0:
                        logger.info(f"[BANK ZANE] EFTPOS settlement IN: '{description[:40]}' → Card Settlement")
                        return jsonify({
                            "success": True, "category": "Card Settlement",
                            "reason": "Card machine settlement deposited — clears the Card Clearing account (income already booked at POS).",
                            "confidence": 0.9, "source": "known_pattern",
                            "needs_clarification": False, "all_categories": all_category_names
                        })
                    else:
                        logger.info(f"[BANK ZANE] EFTPOS settlement OUT: '{description[:40]}' → Card Machine Fees")
                        return jsonify({
                            "success": True, "category": "Card Machine Fees",
                            "reason": "EFTPOS settlement fee charged by the bank.",
                            "confidence": 0.9, "source": "known_pattern",
                            "needs_clarification": False, "all_categories": all_category_names
                        })
                
                is_income = credit > 0
                
                # Map obvious descriptions to exact category names
                KNOWN_EXPENSE = {
                    "TELKOM": ("Telephone — Landline", "Telkom is your landline provider."),
                    "VODACOM": ("Cellphone / Mobile", "Vodacom mobile account."),
                    "MTN": ("Cellphone / Mobile", "MTN mobile account."),
                    "CELL C": ("Cellphone / Mobile", "Cell C mobile account."),
                    "RAIN ": ("Internet / WiFi", "Rain internet/data provider."),
                    "ESKOM": ("Electricity", "Eskom electricity account."),
                    "PREPAID ELEC": ("Electricity", "Prepaid electricity purchase."),
                    "BANK CHARGES": ("Bank Charges", "Monthly bank service fees."),
                    "SERVICE FEE": ("Bank Charges", "Bank service fee."),
                    "MONTHLY FEE": ("Bank Charges", "Monthly bank fee."),
                    "CASH DEPOSIT FEE": ("Bank Charges", "Bank cash deposit fee."),
                    "SARS": ("VAT Payment to SARS", "SARS tax payment."),
                    "SANTAM": ("Insurance — Business / Contents", "Santam insurance premium."),
                    "OUTSURANCE": ("Insurance — Business / Contents", "OUTsurance premium."),
                    "DISCOVERY": ("Insurance — Life / Key Person", "Discovery insurance/medical."),
                    "ENGEN": ("Fuel — Business Vehicle", "Fuel purchase at Engen."),
                    "SASOL ": ("Fuel — Business Vehicle", "Fuel purchase at Sasol."),
                    "SHELL ": ("Fuel — Business Vehicle", "Fuel purchase at Shell."),
                    "BP ": ("Fuel — Business Vehicle", "Fuel purchase at BP."),
                    "CALTEX": ("Fuel — Business Vehicle", "Fuel purchase at Caltex."),
                    "TOTAL GARAGE": ("Fuel — Business Vehicle", "Fuel purchase."),
                    "TAKEALOT": ("Office Supplies", "Online purchase from Takealot."),
                    "MAKRO": ("Stock Purchases — General", "Makro bulk purchase."),
                    "BUILDERS": ("Stock Purchases — Hardware", "Builders Warehouse hardware."),
                    "CASHBUILD": ("Stock Purchases — Hardware", "Cashbuild building materials."),
                    "GAME ": ("Office Supplies", "Game store purchase."),
                    "DSTV": ("DSTV / Streaming", "DStv subscription."),
                    "MULTICHOICE": ("DSTV / Streaming", "MultiChoice subscription."),
                    "NETFLIX": ("DSTV / Streaming", "Netflix streaming subscription."),
                    "UBER": ("Travel — Local", "Uber transport."),
                }
                
                KNOWN_INCOME = {
                    "SPEEDPOINT": ("Sales — Card Machine", "Speedpoint card machine settlement."),
                    "YOCO": ("Sales — Card Machine", "Yoco card payment settlement."),
                    "IKHOKHA": ("Sales — Card Machine", "iKhokha card payment settlement."),
                    "POS DEP": ("POS Deposit", "Point of sale deposit."),
                }
                
                # Check expense patterns (also catch credits/refunds from known expense providers)
                for keyword, (cat, reason) in KNOWN_EXPENSE.items():
                    if keyword in desc_upper:
                        if is_income:
                            reason = f"Credit/refund from {keyword.strip()} — verify if this should be {cat}."
                        logger.info(f"[BANK ZANE] Instant match: '{description[:30]}' → {cat}")
                        return jsonify({
                            "success": True, "category": cat, "reason": reason,
                            "confidence": 0.85 if is_income else 0.9, "source": "known_pattern",
                            "needs_clarification": False, "all_categories": all_category_names
                        })
                
                # Check income patterns  
                if is_income:
                    for keyword, (cat, reason) in KNOWN_INCOME.items():
                        if re.search(keyword, desc_upper):
                            logger.info(f"[BANK ZANE] Instant match: '{description[:30]}' → {cat}")
                            return jsonify({
                                "success": True, "category": cat, "reason": reason,
                                "confidence": 0.9, "source": "known_pattern",
                                "needs_clarification": False, "all_categories": all_category_names
                            })
            
            # ═══ PRIORITY 4: AI (Haiku) — smart drill-down for everything else ═══
            # Get recent learned patterns for context
            patterns = db.get("bank_patterns", {"business_id": biz_id}) or []
            pattern_examples = ""
            if patterns:
                recent = sorted(patterns, key=lambda p: p.get("times_seen", 0), reverse=True)[:10]
                pattern_examples = "\n".join([f"- {p.get('original_description', p.get('pattern', ''))} → {p.get('category', '')}" for p in recent])
            
            # Build focused AI prompt with comprehensive categories
            direction = "Payment out (expense)" if debit > 0 else "Payment in (income)"
            amount = debit if debit > 0 else credit
            all_categories_for_ai = IndustryKnowledge.build_category_list_for_ai()
            
            # Get SA-specific context for this transaction
            banking_context = ""
            if BANKING_KNOWLEDGE_LOADED:
                try:
                    bk_chunks = get_relevant_banking_knowledge(description, max_chunks=1)
                    if bk_chunks:
                        banking_context = format_banking_knowledge(bk_chunks)
                        logger.info(f"[BANK ZANE] Knowledge hit for '{description[:30]}'")
                except Exception:
                    pass
            
            prompt = f"""You are Zane, a bookkeeper. Pick a category for this bank transaction. Be direct — no filler, no emojis.
    {banking_context}
    
    DIRECTION: {"MONEY IN — this is income/deposit/payment received" if credit > 0 else "MONEY OUT — this is an expense/payment made"}
    Transaction: "{description}", {date}, R{amount:,.2f}
    {"THE USER SAYS THIS IS FOR: " + user_answer if user_answer else ""}
    
    Categories:
    {all_categories_for_ai}
    
    {f"Learned patterns from this business:{chr(10)}{pattern_examples}" if pattern_examples else ""}
    
    Two paths:
    1. You KNOW (Telkom=Telephone, Engen=Fuel, bank fees, etc): say it directly
    2. You DON'T KNOW: give 3-5 plain-language options. User clicks one, you map to the right category.
    
    {"If their answer '" + user_answer + "' is specific enough to pick ONE exact category, give the final answer. If still ambiguous, drill deeper with more options. Example: user says 'Fuel' — ask 'Business vehicle, garden equipment, or generator?'" if user_answer else ""}
    
    Example: "ACCOUNT PAYMENT CARTRACK" options: "Vehicle tracking subscription", "Fleet management fee", "Refund from Cartrack"
    ALWAYS include "None of these" as the last option.
    Fuel: warn no VAT claim on own use. Never use "General Expenses".
    
    JSON only — pick ONE:
    Know it: {{"needs_clarification":false,"category":"[exact]","reason":"[1 sentence]","confidence":"high","vat_warning":""}}
    Need more info: {{"needs_clarification":true,"question":"[plain question]","options":[{{"label":"[plain language]","value":"[short]"}},{{"label":"None of these","value":"manual"}}],"confidence":"medium","reason":""}}"""
    
            # Haiku — fast, cheap, smart enough for category matching
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=15
            )
            
            if resp.status_code != 200:
                logger.error(f"[BANK ZANE] API error: {resp.status_code} — {resp.text[:300]}")
                return jsonify({"success": False, "error": "AI unavailable", "all_categories": all_category_names})
            
            ai_text = resp.json().get("content", [{}])[0].get("text", "")
            logger.info(f"[BANK ZANE] Raw AI response for '{description[:30]}': {ai_text[:200]}")
            
            # Try to parse as JSON first (new format)
            suggestion = extract_json_from_text(ai_text)
            
            if suggestion and suggestion.get("needs_clarification"):
                # Zane needs to ask a question
                logger.info(f"[BANK ZANE] Asking clarification for '{description[:30]}'")
                return jsonify({
                    "success": True,
                    "needs_clarification": True,
                    "question": suggestion.get("question", ""),
                    "options": suggestion.get("options", []),
                    "reason": suggestion.get("reason", ""),
                    "confidence": {"hoog": 0.9, "high": 0.9, "medium": 0.7, "laag": 0.4, "low": 0.4}.get(str(suggestion.get("confidence", "medium")), 0.7),
                    "source": "ai",
                    "all_categories": all_category_names
                })
            
            if suggestion and suggestion.get("category"):
                category = suggestion["category"]
                reason = suggestion.get("reason", "")
                confidence = str(suggestion.get("confidence", "medium"))
                vat_warning = suggestion.get("vat_warning", "")
            else:
                # Fallback: parse old text format
                category = ""
                reason = ""
                confidence = "medium"
                vat_warning = ""
                
                for line in ai_text.strip().split("\n"):
                    line = line.strip()
                    if line.upper().startswith("CATEGORY:"):
                        category = line.split(":", 1)[1].strip()
                    elif line.upper().startswith("REASON:"):
                        reason = line.split(":", 1)[1].strip()
                    elif line.upper().startswith("CONFIDENCE:"):
                        confidence = line.split(":", 1)[1].strip().lower()
            
            # Validate category against available list — with SMART fuzzy matching
            valid = False
            
            # Try 1: Exact match
            for c in all_category_names:
                if c.lower() == category.lower():
                    category = c
                    valid = True
                    break
            
            # Try 2: Partial/contains match
            if not valid and category:
                for c in all_category_names:
                    if category.lower() in c.lower() or c.lower() in category.lower():
                        category = c
                        valid = True
                        break
            
            # Try 3: Word overlap match (e.g. "Telephone" matches "Telephone — Landline")
            if not valid and category:
                cat_words = set(category.lower().replace("—", "").replace("-", "").split())
                best_match = None
                best_overlap = 0
                for c in all_category_names:
                    c_words = set(c.lower().replace("—", "").replace("-", "").split())
                    overlap = len(cat_words & c_words)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = c
                if best_match and best_overlap >= 1:
                    category = best_match
                    valid = True
                    logger.info(f"[BANK ZANE] Fuzzy matched '{suggestion.get('category', category)}' → {category}")
            
            if not valid:
                logger.warning(f"[BANK ZANE] No valid category match for AI response: '{category}' from '{ai_text[:100]}'")
            
            conf_score = {"hoog": 0.9, "high": 0.9, "medium": 0.7, "laag": 0.4, "low": 0.4}.get(confidence, 0.7)
            
            logger.info(f"[BANK ZANE] '{description[:30]}' → {category} ({confidence})")
            
            return jsonify({
                "success": True,
                "category": category if valid else "",
                "reason": reason or "Not sure about this one — pick from the dropdown and I'll learn for next time.",
                "confidence": conf_score,
                "source": "ai",
                "needs_clarification": False,
                "vat_warning": vat_warning,
                "all_categories": all_category_names
            })
            
        except Exception as e:
            logger.error(f"[BANK ZANE] Error: {e}")
            try:
                cats = IndustryKnowledge.get_all_category_names()
            except:
                cats = ["Sundry Expenses"]
            return jsonify({"success": False, "error": str(e), "all_categories": cats})
    
    
    # ═══════════════════════════════════════════════════════════════════════
    # SPLIT CATEGORIZE — Split one bank transaction into multiple GL codes
    # ═══════════════════════════════════════════════════════════════════════
    @app.route("/api/banking/split-categorize", methods=["POST"])
    @login_required
    def api_banking_split_categorize():
        """
        Split a single bank transaction into multiple expense categories.
        Each split line gets its own GL debit/credit entry.
        Optionally links to a previously scanned expense.
        """
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        try:
            data = request.get_json()
            txn_id = data.get("id")
            splits = data.get("splits", [])  # [{category, amount}, ...]
            is_debit = data.get("is_debit", True)
            matched_expense_id = data.get("matched_expense_id")
            
            if not txn_id:
                return jsonify({"success": False, "error": "No transaction ID"})
            if not splits or len(splits) < 2:
                return jsonify({"success": False, "error": "Need at least 2 split lines"})
            
            # Get transaction
            txn = db.get_one("bank_transactions", txn_id)
            if not txn:
                return jsonify({"success": False, "error": "Transaction not found"})
            
            # Validate amounts balance
            txn_amount = float(txn.get("debit", 0)) if is_debit else float(txn.get("credit", 0))
            if txn_amount == 0:
                txn_amount = abs(float(txn.get("amount", 0)))
            
            split_total = sum(float(sp.get("amount", 0)) for sp in splits)
            if abs(split_total - txn_amount) > 0.02:
                return jsonify({"success": False, "error": f"Split total R{split_total:.2f} does not match transaction R{txn_amount:.2f}"})
            
            description = txn.get("description", "")
            txn_date = txn.get("date", today())
            ref = f"BNK-SPLIT-{txn_id[:8]}"
            user = Auth.get_current_user()
            
            # Build category summary for the transaction record
            split_categories = []
            for sp in splits:
                split_categories.append({
                    "category": sp.get("category", ""),
                    "amount": round(float(sp.get("amount", 0)), 2)
                })
            
            # Mark transaction as matched with split info
            txn["matched"] = True
            txn["category"] = "Split: " + " + ".join([sp.get("category", "")[:20] for sp in splits[:3]])
            txn["is_split"] = True
            txn["split_categories"] = split_categories
            txn["matched_at"] = now()
            if matched_expense_id:
                txn["linked_expense_id"] = matched_expense_id
            db.save("bank_transactions", txn)
            
            # SARS: No VAT claim categories
            no_vat_cats = ["fuel", "entertainment", "meals", "membership"]
            
            if is_debit:
                # ═══ MONEY OUT — Split expense across multiple GL codes ═══
                journal_entries = []
                
                for sp in splits:
                    sp_amount = round(float(sp.get("amount", 0)), 2)
                    sp_category = sp.get("category", "Sundry Expenses")
                    sp_gl = IndustryKnowledge.get_gl_code(sp_category, business_id=biz_id)
                    
                    is_no_vat = any(nv in sp_category.lower() for nv in no_vat_cats)
                    
                    if is_no_vat:
                        # No VAT claim — full amount to expense
                        journal_entries.append({"account_code": sp_gl, "debit": sp_amount, "credit": 0})
                    else:
                        # VAT inclusive — split out VAT
                        vat = round(sp_amount * 15 / 115, 2)
                        net = round(sp_amount - vat, 2)
                        journal_entries.append({"account_code": sp_gl, "debit": net, "credit": 0})
                        if vat > 0:
                            journal_entries.append({"account_code": gl(biz_id, "vat_input"), "debit": vat, "credit": 0})
                    
                    # Create individual expense record for each split line
                    exp = RecordFactory.expense(
                        business_id=biz_id,
                        description=f"{description[:40]} [{sp_category[:25]}]",
                        amount=sp_amount,
                        date=txn_date,
                        category=sp_category,
                        category_code=sp_gl,
                        reference=ref,
                        payment_method="eft",
                        status="paid",
                        created_by=user.get("id") if user else None
                    )
                    # Add split metadata
                    exp["bank_transaction_id"] = txn_id
                    exp["is_split_line"] = True
                    exp["split_parent_amount"] = txn_amount
                    db.save("expenses", exp)
                    
                    # Learn from each split category
                    BankLearning.learn_from_categorization(biz_id, description, sp_category)
                
                # Credit Bank for the full amount
                journal_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(txn_amount, 2)})
                
                create_journal_entry(biz_id, txn_date, f"SPLIT: {description[:40]}", ref, journal_entries)
                logger.info(f"[BANK SPLIT] Debit split: {len(splits)} categories, R{txn_amount:.2f} for {biz_id}")
            
            else:
                # ═══ MONEY IN — Split income across multiple GL codes ═══
                journal_entries = []
                
                # Debit Bank for the full amount
                journal_entries.append({"account_code": gl(biz_id, "bank"), "debit": round(txn_amount, 2), "credit": 0})
                
                for sp in splits:
                    sp_amount = round(float(sp.get("amount", 0)), 2)
                    sp_category = sp.get("category", "Sales")
                    sp_gl = IndustryKnowledge.get_gl_code(sp_category, business_id=biz_id)
                    
                    # VAT on income
                    vat = round(sp_amount * 15 / 115, 2)
                    net = round(sp_amount - vat, 2)
                    
                    journal_entries.append({"account_code": sp_gl, "debit": 0, "credit": net})
                    if vat > 0:
                        journal_entries.append({"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": vat})
                
                create_journal_entry(biz_id, txn_date, f"SPLIT: {description[:40]}", ref, journal_entries)
                logger.info(f"[BANK SPLIT] Credit split: {len(splits)} categories, R{txn_amount:.2f} for {biz_id}")
            
            # Link back to matched scanned expense if provided
            if matched_expense_id:
                try:
                    db.update("expenses", matched_expense_id, {
                        "bank_transaction_id": txn_id,
                        "bank_matched": True,
                        "bank_matched_at": now()
                    })
                    logger.info(f"[BANK SPLIT] Linked to scanned expense {matched_expense_id}")
                except Exception:
                    pass
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="bank_split", source_table="bank_transactions", source_id=txn_id,
                        description=f"SPLIT: {description[:80]} → {len(splits)} categories",
                        amount=txn_amount,
                        gl_entries=journal_entries,
                        category="Split",
                        category_code="SPLIT",
                        ai_reasoning="Manual split allocation: " + ", ".join([sp.get("category", "") + " R" + str(round(sp.get("amount", 0), 2)) for sp in splits]) + ". " + ("Linked to scanned expense " + str(matched_expense_id) if matched_expense_id else "No scan match."),
                        ai_confidence="HIGH",
                        payment_method="eft",
                        reference=ref,
                        transaction_date=txn_date,
                        created_by=session.get("user_id", ""),
                        created_by_name=(user or {}).get("name", "")
                    )
            except Exception:
                pass
            
            return jsonify({
                "success": True, 
                "message": f"Split into {len(splits)} categories",
                "splits": split_categories
            })
        
        except Exception as e:
            logger.error(f"[BANK SPLIT] Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)})
    
    
    # ═══════════════════════════════════════════════════════════════════════
    # FIND MATCHING EXPENSE — Check if a scanned expense matches this bank txn
    # ═══════════════════════════════════════════════════════════════════════
    @app.route("/api/banking/find-matching-expense", methods=["POST"])
    @login_required
    def api_banking_find_matching_expense():
        """
        Find a previously scanned/saved expense that matches this bank transaction.
        Matches on amount (±R2) and date (±5 days).
        Returns the expense with its split data if available.
        """
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False})
        
        try:
            data = request.get_json()
            amount = float(data.get("amount", 0))
            date_str = data.get("date", "")
            txn_id = data.get("txn_id", "")
            
            if amount <= 0 or not date_str:
                return jsonify({"success": False})
            
            # Get all expenses for this business (not already bank-matched)
            all_expenses = db.get("expenses", {"business_id": biz_id}) or []
            
            # Parse transaction date
            try:
                txn_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            except (ValueError, TypeError):
                return jsonify({"success": False})
            
            best_match = None
            best_score = 0
            
            for exp in all_expenses:
                # Skip if already linked to a bank transaction
                if exp.get("bank_transaction_id") or exp.get("bank_matched"):
                    continue
                
                exp_amount = float(exp.get("amount", 0) or exp.get("total", 0) or 0)
                if exp_amount <= 0:
                    continue
                
                # Amount match: within R2
                amount_diff = abs(exp_amount - amount)
                if amount_diff > 2.0:
                    continue
                
                # Date match: within 5 days
                try:
                    exp_date_str = str(exp.get("date", ""))[:10]
                    exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                    date_diff = abs((txn_date - exp_date).days)
                    if date_diff > 5:
                        continue
                except (ValueError, TypeError):
                    continue
                
                # Score: closer amount + closer date = better match
                score = 100 - (amount_diff * 10) - (date_diff * 5)
                
                # Bonus for split transactions (more useful to show)
                if exp.get("splits"):
                    score += 20
                
                if score > best_score:
                    best_score = score
                    best_match = exp
            
            if best_match:
                # Try to get splits from journal entries if not stored on expense
                splits_data = best_match.get("splits")
                if not splits_data:
                    # Check allocation log for split info
                    try:
                        exp_id = best_match.get("id", "")
                        alloc_logs = db.get("allocation_log", {"business_id": biz_id, "source_id": exp_id}) or []
                        for al in alloc_logs:
                            reasoning = al.get("ai_reasoning", "")
                            if "Multi-GL split applied" in reasoning:
                                # Has split but data not stored — indicate it
                                gl_entries = al.get("gl_entries", [])
                                if gl_entries and len(gl_entries) > 2:
                                    splits_data = []
                                    for ge in gl_entries:
                                        if ge.get("debit", 0) > 0 and ge.get("account_code") != gl(biz_id, "vat_input"):
                                            splits_data.append({
                                                "category": ge.get("account_code", ""),
                                                "amount": ge.get("debit", 0)
                                            })
                    except Exception:
                        pass
                
                return jsonify({
                    "success": True,
                    "match": {
                        "expense_id": best_match.get("id", ""),
                        "supplier": best_match.get("supplier_name", "") or best_match.get("supplier", ""),
                        "description": best_match.get("description", ""),
                        "amount": float(best_match.get("amount", 0)),
                        "date": str(best_match.get("date", ""))[:10],
                        "category": best_match.get("category", ""),
                        "splits": splits_data or [],
                        "score": best_score
                    }
                })
            
            return jsonify({"success": False, "match": None})
        
        except Exception as e:
            logger.error(f"[BANK MATCH] Error finding matching expense: {e}")
            return jsonify({"success": False})
    
    
    @app.route("/api/banking/delete-import", methods=["POST"])
    @login_required
    def api_banking_delete_import():
        """Delete the UNALLOCATED transactions of a single import batch (identified by the
        created_at minute). Allocated (matched) transactions are skipped so their GL journals
        and customer/supplier payments are never orphaned — re-check happens at delete time."""
        try:
            user = Auth.get_current_user()
            if not user:
                return jsonify({"success": False, "error": "Not logged in"})
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            data = request.get_json(silent=True) or {}
            batch = (data.get("batch") or "").strip()
            if not batch:
                return jsonify({"success": False, "error": "No import selected"})
            
            all_txns = db.get("bank_transactions", {"business_id": biz_id}) or []
            # Match this import by created_at minute; NEVER delete an allocated (matched) txn.
            to_delete = [t["id"] for t in all_txns
                         if "id" in t
                         and str(t.get("created_at", "") or "")[:16] == batch
                         and not t.get("matched")]
            kept_allocated = len([t for t in all_txns
                                  if str(t.get("created_at", "") or "")[:16] == batch
                                  and t.get("matched")])
            if not to_delete:
                _msg = ("Nothing to delete — every transaction in this import is allocated."
                        if kept_allocated else "No matching transactions found for this import.")
                return jsonify({"success": True, "deleted": 0, "kept": kept_allocated, "message": _msg})
            
            success_count, failed_count = db.delete_many("bank_transactions", to_delete, business_id=biz_id)
            logger.info(f"[BANK DELETE IMPORT] Deleted {success_count} unallocated txns from import {batch} for business {biz_id} ({failed_count} failed, {kept_allocated} allocated kept)")
            _kept_note = f" {kept_allocated} allocated transaction(s) kept." if kept_allocated else ""
            return jsonify({
                "success": True,
                "deleted": success_count,
                "failed": failed_count,
                "kept": kept_allocated,
                "message": f"Deleted {success_count} unallocated transactions from this import.{_kept_note}"
            })
        except Exception as e:
            logger.error(f"[BANK DELETE IMPORT] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/banking/delete-all", methods=["POST"])
    @login_required
    def api_banking_delete_all():
        """Delete ALL bank transactions for current business — for re-import"""
        try:
            user = Auth.get_current_user()
            if not user:
                return jsonify({"success": False, "error": "Not logged in"})
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            
            # Get all transaction IDs
            all_txns = db.get("bank_transactions", {"business_id": biz_id}) or []
            if not all_txns:
                return jsonify({"success": True, "deleted": 0, "message": "No transactions to delete"})
            
            ids = [t["id"] for t in all_txns if "id" in t]
            success_count, failed_count = db.delete_many("bank_transactions", ids, business_id=biz_id)
            
            logger.info(f"[BANK DELETE ALL] Deleted {success_count} transactions for business {biz_id} ({failed_count} failed)")
            
            return jsonify({
                "success": True, 
                "deleted": success_count, 
                "failed": failed_count,
                "message": f"Deleted {success_count} bank transactions"
            })
        except Exception as e:
            logger.error(f"[BANK DELETE ALL] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/banking/reset-patterns", methods=["POST"])
    @login_required
    def api_banking_reset_patterns():
        """Delete ALL learned bank patterns for current business — forces re-learning with correct normalization"""
        try:
            user = Auth.get_current_user()
            if not user:
                return jsonify({"success": False, "error": "Not logged in"})
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            
            all_patterns = db.get("bank_patterns", {"business_id": biz_id}) or []
            if not all_patterns:
                return jsonify({"success": True, "deleted": 0, "message": "No learned patterns to reset"})
            
            ids = [p["id"] for p in all_patterns if "id" in p]
            success_count, failed_count = db.delete_many("bank_patterns", ids, business_id=biz_id)
            
            logger.info(f"[BANK RESET PATTERNS] Deleted {success_count} patterns for business {biz_id}")
            
            return jsonify({
                "success": True, 
                "deleted": success_count,
                "message": f"Reset {success_count} learned patterns. Zane will re-learn from your next categorizations."
            })
        except Exception as e:
            logger.error(f"[BANK RESET PATTERNS] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    

    @app.route("/api/banking/entity-invoices", methods=["POST"])
    @login_required
    def api_banking_entity_invoices():
        """Fetch outstanding invoices for a customer or supplier — used by invoice picker in banking allocation"""
        try:
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "invoices": []})
            
            data = request.get_json()
            entity_id = data.get("entity_id", "")
            entity_type = data.get("entity_type", "customer")  # "customer" or "supplier"
            
            if not entity_id:
                return jsonify({"success": False, "invoices": []})
            
            result = []
            if entity_type == "customer":
                from datetime import datetime as _dt
                _today = _dt.now()
                invoices = db.get("invoices", {"business_id": biz_id, "customer_id": entity_id}) or []
                for inv in invoices:
                    if inv.get("status") in ("paid", "credited"):
                        continue
                    _inv_date_str = str(inv.get("date", ""))[:10]
                    _days_old = None
                    try:
                        if _inv_date_str:
                            _days_old = (_today - _dt.strptime(_inv_date_str, "%Y-%m-%d")).days
                    except Exception:
                        _days_old = None
                    result.append({
                        "id": inv.get("id", ""),
                        "number": inv.get("invoice_number", "-"),
                        "date": _inv_date_str,
                        "total": round(float(inv.get("total", 0)), 2),
                        "paid_amount": round(float(inv.get("paid_amount", 0) or 0), 2),
                        "days_old": _days_old,
                        "status": inv.get("status", "outstanding")
                    })
            else:
                s_invoices = db.get("supplier_invoices", {"business_id": biz_id, "supplier_id": entity_id}) or []
                for inv in s_invoices:
                    if inv.get("status") in ("paid", "credited"):
                        continue
                    result.append({
                        "id": inv.get("id", ""),
                        "number": inv.get("invoice_number", "-"),
                        "date": str(inv.get("date", ""))[:10],
                        "total": round(float(inv.get("total", 0)), 2),
                        "status": inv.get("status", "outstanding")
                    })
            
            result.sort(key=lambda x: x["date"])
            return jsonify({"success": True, "invoices": result})
        except Exception as e:
            logger.error(f"[BANK ENTITY-INV] Error: {e}")
            return jsonify({"success": False, "invoices": []})


    logger.info("[BANKING] All banking routes registered ✓")
