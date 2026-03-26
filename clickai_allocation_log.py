"""
ClickAI Allocation Log Module
===============================
"Follow the Money" - Full audit trail ledger.

Every transaction in the business is logged here:
- POS sales (who, what, GL accounts, stock movement, payment method)
- Scanned invoices (AI decisions, stock matching, category)
- Scanned expenses (AI category, GL code, reasoning)
- Bank statement imports (auto-categorization, matching)
- Manual expenses, payments, credit notes
- Journal entries, payroll, GRVs

The /ledger page shows accordion bundles that open to reveal:
  Layer 1: Transaction summary (date, type, amount, who)
  Layer 2: Full detail (items, customer/supplier, payment, GL journals)
  Layer 3: Linked documents and stock movements

Grouping: Per Transaction (default), Per Day, Per Customer, Per Cashier
Search: Any field - customer, supplier, amount, reference, cashier, date

Import in clickai.py with try/except:
    try:
        from clickai_allocation_log import register_ledger_routes, log_allocation
        ALLOCATION_LOG_LOADED = True
    except ImportError:
        log_allocation = None
        ALLOCATION_LOG_LOADED = False
"""

import json
import logging
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

# Module-level reference to db — set during register
_db = None
_generate_id = None
_now = None
_today = None


def log_allocation(
    business_id: str,
    allocation_type: str,
    source_table: str,
    source_id: str,
    description: str,
    amount: float = 0,
    gl_entries: list = None,
    stock_movements: list = None,
    ai_reasoning: str = "",
    ai_confidence: str = "",
    ai_worker: str = "",
    category: str = "",
    category_code: str = "",
    customer_name: str = "",
    supplier_name: str = "",
    payment_method: str = "",
    reference: str = "",
    created_by: str = "",
    created_by_name: str = "",
    transaction_date: str = "",
    match_key: str = "",
    extra: dict = None
):
    """
    Log a transaction allocation to the place of safety.
    
    Args:
        business_id:     Business ID
        allocation_type: pos_sale | scan_supplier_invoice | scan_expense | bank_import | 
                        bank_categorize | manual_expense | payment | credit_note | 
                        journal_entry | supplier_payment | grv
        source_table:    The table where the source record lives (sales, supplier_invoices, expenses, etc)
        source_id:       The ID of the source record
        description:     Human-readable description
        amount:          Total amount
        gl_entries:      List of GL postings [{account_code, debit, credit, account_name}]
        stock_movements: List of stock changes [{stock_id, code, description, qty_change, old_qty, new_qty}]
        ai_reasoning:    Why the AI made this decision (category, matching, etc)
        ai_confidence:   HIGH, MEDIUM, LOW
        ai_worker:       Which AI worker (Jacqo, Zane, Diane, auto)
        category:        Expense/income category assigned
        category_code:   GL code assigned
        customer_name:   Customer if applicable
        supplier_name:   Supplier if applicable
        payment_method:  cash, card, eft, account
        reference:       Invoice/PO/receipt number
        created_by:      User ID who did this
        created_by_name: User display name
        transaction_date: The actual business date of the transaction (invoice date, bank date etc)
        match_key:       Key for linking related entries — e.g. "supplier:Acme:1500.00" or "ref:INV-001"
                        Used to pair scanned invoices with bank statement entries in the ledger
        extra:           Any additional data to store
    """
    global _db, _generate_id, _now, _today
    
    if not _db or not _generate_id:
        logger.warning("[ALLOC LOG] Module not initialized — call register_ledger_routes first")
        return False
    
    try:
        # Build match_key automatically if not provided
        auto_match_key = match_key
        if not auto_match_key:
            amt_str = f"{abs(round(float(amount), 2)):.2f}"
            if supplier_name:
                s_norm = supplier_name.strip().lower().split()[0] if supplier_name.strip() else ""
                auto_match_key = f"sup:{s_norm}:{amt_str}"
            elif reference:
                auto_match_key = f"ref:{reference.strip().upper()}"
        
        # Use transaction_date if provided, else today
        txn_date = transaction_date or (_today() if _today else "")
        
        # Store link/date info in extra as well (guaranteed to work even if columns don't exist yet)
        extra_data = extra or {}
        extra_data["transaction_date"] = txn_date
        extra_data["match_key"] = auto_match_key
        
        record = {
            "id": _generate_id(),
            "business_id": business_id,
            "allocation_type": allocation_type,
            "source_table": source_table,
            "source_id": source_id,
            "description": description[:500] if description else "",
            "amount": round(float(amount), 2),
            "gl_entries": json.dumps(gl_entries) if gl_entries else "[]",
            "stock_movements": json.dumps(stock_movements) if stock_movements else "[]",
            "ai_reasoning": ai_reasoning[:1000] if ai_reasoning else "",
            "ai_confidence": ai_confidence,
            "ai_worker": ai_worker,
            "category": category,
            "category_code": category_code,
            "customer_name": customer_name,
            "supplier_name": supplier_name,
            "payment_method": payment_method,
            "reference": reference,
            "created_by": created_by,
            "created_by_name": created_by_name,
            "transaction_date": txn_date,
            "match_key": auto_match_key,
            "linked_id": "",
            "extra": json.dumps(extra_data),
            "status": "active",
            "created_at": _now()
        }
        
        success, err = _db.save("allocation_log", record)
        
        # If save failed (likely missing columns), retry without new fields
        if not success:
            logger.warning(f"[ALLOC LOG] First save failed ({err}), retrying without new columns...")
            for col in ["transaction_date", "match_key", "linked_id"]:
                record.pop(col, None)
            success, err = _db.save("allocation_log", record)
            if not success:
                logger.error(f"[ALLOC LOG] Retry also failed: {err}")
                return False
        
        alloc_id = record["id"]
        
        # ── AUTO-LINK: Try find a matching partner entry ──
        if auto_match_key:
            try:
                _try_auto_link(business_id, alloc_id, auto_match_key, allocation_type, round(float(amount), 2))
            except Exception as link_err:
                logger.warning(f"[ALLOC LOG] Auto-link failed (non-critical): {link_err}")
        
        logger.info(f"[ALLOC LOG] {allocation_type} | {reference or source_id[:8]} | R{amount:,.2f} | {ai_worker or created_by_name or 'system'} | key={auto_match_key}")
        return True
        
    except Exception as e:
        logger.error(f"[ALLOC LOG] Error: {e}")
        return False


def _try_auto_link(business_id: str, new_id: str, match_key: str, new_type: str, new_amount: float):
    """
    Try to find and link a partner allocation entry.
    """
    global _db
    if not _db:
        return
    
    pair_types = {
        "scan_supplier_invoice": ["bank_categorize", "bank_import", "supplier_payment"],
        "scan_expense":          ["bank_categorize", "bank_import"],
        "bank_categorize":       ["scan_supplier_invoice", "scan_expense", "manual_expense", "invoice"],
        "bank_import":           ["scan_supplier_invoice", "scan_expense", "manual_expense"],
        "supplier_payment":      ["scan_supplier_invoice"],
        "manual_expense":        ["bank_categorize", "bank_import"],
        "invoice":               ["bank_categorize", "bank_import", "payment"],
        "payment":               ["invoice"],
    }
    
    valid_partners = pair_types.get(new_type, [])
    if not valid_partners:
        return
    
    all_allocs = _db.get("allocation_log", {"business_id": business_id}) or []
    
    best_match = None
    best_score = 0
    
    for a in all_allocs:
        if a.get("id") == new_id:
            continue
        if a.get("linked_id"):
            continue
        if a.get("allocation_type") not in valid_partners:
            continue
        
        score = 0
        
        if match_key and a.get("match_key") == match_key:
            score += 10
        
        a_ref = (a.get("reference") or "").strip().upper()
        if a_ref and match_key and a_ref in match_key.upper():
            score += 5
        
        a_amt = abs(float(a.get("amount", 0)))
        if a_amt > 0 and new_amount > 0:
            diff = abs(a_amt - new_amount)
            pct = diff / max(a_amt, new_amount) if max(a_amt, new_amount) > 0 else 1
            if diff < 0.02:
                score += 8
            elif pct < 0.02:
                score += 5
            elif diff <= 10:
                score += 3
        
        if score > best_score:
            best_score = score
            best_match = a
    
    if best_match and best_score >= 10:
        try:
            _db.save("allocation_log", {"id": new_id, "linked_id": best_match["id"]})
            _db.save("allocation_log", {"id": best_match["id"], "linked_id": new_id})
            logger.info(f"[ALLOC LOG] AUTO-LINKED: {new_type} <-> {best_match.get('allocation_type')} | key={match_key} | score={best_score}")
        except Exception as e:
            logger.warning(f"[ALLOC LOG] Auto-link save failed (column may not exist): {e}")


# URL mapping: source_table → actual Flask route prefix
_SOURCE_URL_MAP = {
    "goods_received": "grv",
    "purchase_orders": "purchase",
    "sales": "sale",
    "invoices": "invoice",
    "supplier_invoices": "supplier-invoice",
    "credit_notes": "credit-note",
    "delivery_notes": "delivery-note",
}

def _source_url(a):
    """Build correct URL path from allocation record's source_table + source_id"""
    table = a.get("source_table", "")
    sid = a.get("source_id", "")
    prefix = _SOURCE_URL_MAP.get(table, table.replace("_", "-"))
    return f"{prefix}/{sid}"


# ═══════════════════════════════════════════════════════════════════════════════
# TYPE CONFIG - Icons, Colors, Labels for each transaction type
# ═══════════════════════════════════════════════════════════════════════════════

TYPE_CONFIG = {
    "pos_sale":               ("POS",    "#10b981", "POS Sale"),
    "scan_supplier_invoice":  ("SCAN",   "#3b82f6", "Scanned Invoice"),
    "scan_expense":           ("SCAN",   "#f59e0b", "Scanned Expense"),
    "bank_import":            ("BANK",   "#8b5cf6", "Bank Import"),
    "bank_categorize":        ("BANK",   "#6366f1", "Bank Categorize"),
    "manual_expense":         ("EXP",    "#f97316", "Manual Expense"),
    "payment":                ("PAY",    "#10b981", "Payment"),
    "credit_note":            ("CN",     "#ef4444", "Credit Note"),
    "journal_entry":          ("JNL",    "#64748b", "Journal Entry"),
    "supplier_payment":       ("PAY",    "#0ea5e9", "Supplier Payment"),
    "grv":                    ("GRV",    "#0f766e", "GRV"),
    "grv_to_invoice":         ("GRV",    "#065f46", "GRV to Invoice"),
    "invoice":                ("INV",    "#10b981", "Invoice"),
    "payroll":                ("PAY",    "#7c3aed", "Payroll"),
}

# Payment method badges
PAY_BADGES = {
    "cash":    ("CASH",    "#10b981"),
    "card":    ("CARD",    "#3b82f6"),
    "eft":     ("EFT",     "#8b5cf6"),
    "account": ("ACC",     "#f59e0b"),
}


def register_ledger_routes(app, db, login_required, Auth, generate_id, now_fn, today_fn):
    """Register the /ledger page and API routes"""
    
    global _db, _generate_id, _now, _today
    _db = db
    _generate_id = generate_id
    _now = now_fn
    _today = today_fn
    
    
    def _build_gl_detail(a, money_fn):
        """Build the GL journal entries detail HTML for an allocation"""
        try:
            gl = json.loads(a.get("gl_entries", "[]"))
            if not gl:
                return ""
            
            total_dr = sum(float(g.get("debit", 0)) for g in gl)
            total_cr = sum(float(g.get("credit", 0)) for g in gl)
            balanced = abs(total_dr - total_cr) < 0.02
            bal_icon = "BALANCED" if balanced else "UNBALANCED"
            bal_color = "#10b981" if balanced else "#ef4444"
            
            rows = ""
            for g in gl:
                code = g.get("account_code", "?")
                name = g.get("account_name", "")
                dr = float(g.get("debit", 0))
                cr = float(g.get("credit", 0))
                
                dr_display = money_fn(dr) if dr > 0 else ""
                cr_display = money_fn(cr) if cr > 0 else ""
                
                rows += f'''<tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:5px 8px;font-family:monospace;font-size:12px;font-weight:600;">{code}</td>
                    <td style="padding:5px 8px;font-size:12px;color:var(--text-muted);">{name}</td>
                    <td style="padding:5px 8px;text-align:right;font-family:monospace;font-size:12px;color:#10b981;font-weight:600;">{dr_display}</td>
                    <td style="padding:5px 8px;text-align:right;font-family:monospace;font-size:12px;color:#ef4444;font-weight:600;">{cr_display}</td>
                </tr>'''
            
            return f'''
            <div style="margin-top:10px;border:1px solid var(--border);border-radius:8px;overflow:hidden;">
                <div style="background:rgba(99,102,241,0.08);padding:8px 12px;display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);">GL Journal Entries</span>
                    <span style="font-size:10px;font-weight:700;color:{bal_color};background:{bal_color}18;padding:2px 8px;border-radius:4px;">{bal_icon}</span>
                </div>
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="border-bottom:2px solid var(--border);">
                            <th style="padding:6px 8px;text-align:left;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Account</th>
                            <th style="padding:6px 8px;text-align:left;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Name</th>
                            <th style="padding:6px 8px;text-align:right;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Debit</th>
                            <th style="padding:6px 8px;text-align:right;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Credit</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                        <tr style="background:rgba(99,102,241,0.05);border-top:2px solid var(--border);">
                            <td colspan="2" style="padding:6px 8px;font-size:11px;font-weight:700;">TOTALS</td>
                            <td style="padding:6px 8px;text-align:right;font-family:monospace;font-size:12px;font-weight:700;color:#10b981;">{money_fn(total_dr)}</td>
                            <td style="padding:6px 8px;text-align:right;font-family:monospace;font-size:12px;font-weight:700;color:#ef4444;">{money_fn(total_cr)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>'''
        except:
            return ""
    
    
    def _build_stock_detail(a):
        """Build stock movement detail HTML"""
        try:
            sm = json.loads(a.get("stock_movements", "[]"))
            if not sm:
                return ""
            
            rows = ""
            for s in sm:
                code = s.get("code", "?")
                desc = s.get("description", "")
                qty = s.get("qty_change", 0)
                old_q = s.get("old_qty", "?")
                new_q = s.get("new_qty", "?")
                direction = "OUT" if qty < 0 else "IN"
                dir_color = "#ef4444" if qty < 0 else "#10b981"
                
                rows += f'''<tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:4px 8px;font-family:monospace;font-size:12px;font-weight:600;">{code}</td>
                    <td style="padding:4px 8px;font-size:12px;">{desc[:40]}</td>
                    <td style="padding:4px 8px;text-align:center;">
                        <span style="color:{dir_color};font-weight:700;font-size:11px;">{direction} {abs(qty)}</span>
                    </td>
                    <td style="padding:4px 8px;text-align:right;font-size:11px;color:var(--text-muted);">{old_q} &rarr; {new_q}</td>
                </tr>'''
            
            return f'''
            <div style="margin-top:10px;border:1px solid var(--border);border-radius:8px;overflow:hidden;">
                <div style="background:rgba(15,118,110,0.08);padding:8px 12px;">
                    <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted);">Stock Movements ({len(sm)} items)</span>
                </div>
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="border-bottom:2px solid var(--border);">
                            <th style="padding:5px 8px;text-align:left;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Code</th>
                            <th style="padding:5px 8px;text-align:left;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Description</th>
                            <th style="padding:5px 8px;text-align:center;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Qty</th>
                            <th style="padding:5px 8px;text-align:right;font-size:10px;color:var(--text-muted);text-transform:uppercase;">Old &rarr; New</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>'''
        except:
            return ""
    
    
    def _build_linked_detail(a, alloc_by_id, money_fn, safe_string_fn):
        """Build linked transaction detail HTML"""
        linked_id = a.get("linked_id", "")
        if not linked_id or linked_id not in alloc_by_id:
            return ""
        
        partner = alloc_by_id[linked_id]
        p_type = partner.get("allocation_type", "")
        p_short, p_color, p_label = TYPE_CONFIG.get(p_type, ("?", "#888", p_type.replace("_", " ").title()))
        p_date = (partner.get("transaction_date") or partner.get("created_at", ""))[:10]
        p_ref = safe_string_fn(partner.get("reference", ""))
        p_desc = safe_string_fn(partner.get("description", "")[:80])
        p_amt = abs(float(partner.get("amount", 0)))
        p_src_url = _source_url(partner)
        
        return f'''
        <div style="margin-top:10px;border:1px solid #10b98144;border-radius:8px;overflow:hidden;">
            <div style="background:rgba(16,185,129,0.08);padding:8px 12px;display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#10b981;">Linked Transaction</span>
                <a href="/{p_src_url}" style="font-size:11px;color:var(--primary);text-decoration:none;">View Document &rarr;</a>
            </div>
            <div style="padding:10px 12px;display:flex;gap:20px;flex-wrap:wrap;align-items:center;">
                <span style="background:{p_color}18;color:{p_color};padding:3px 10px;border-radius:6px;font-size:11px;font-weight:700;">{p_short} {p_label}</span>
                <span style="font-size:12px;font-weight:600;">{p_date}</span>
                <span style="font-size:12px;">{p_ref}</span>
                <span style="font-size:12px;color:var(--text-muted);">{p_desc}</span>
                <span style="font-size:13px;font-weight:700;">{money_fn(p_amt)}</span>
            </div>
        </div>'''
    
    
    def _build_ai_detail(a, safe_string_fn):
        """Build AI decision detail HTML"""
        if not a.get("ai_reasoning"):
            return ""
        
        conf = a.get("ai_confidence", "")
        conf_color = {"HIGH": "#10b981", "MEDIUM": "#f59e0b", "LOW": "#ef4444"}.get(conf, "#888")
        worker = safe_string_fn(a.get("ai_worker", ""))
        reasoning = safe_string_fn(a.get("ai_reasoning", ""))
        
        return f'''
        <div style="margin-top:10px;border:1px solid #8b5cf644;border-radius:8px;overflow:hidden;">
            <div style="background:rgba(139,92,246,0.08);padding:8px 12px;display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#8b5cf6;">AI Decision — {worker}</span>
                <span style="font-size:10px;font-weight:700;color:{conf_color};background:{conf_color}18;padding:2px 8px;border-radius:4px;">{conf}</span>
            </div>
            <div style="padding:10px 12px;font-size:12px;line-height:1.6;color:var(--text);">{reasoning}</div>
        </div>'''
    
    
    def _build_single_accordion(a, alloc_by_id, money_fn, safe_string_fn, idx):
        """Build a single transaction accordion row"""
        atype = a.get("allocation_type", "unknown")
        short, color, label = TYPE_CONFIG.get(atype, ("?", "#888", atype.replace("_", " ").title()))
        
        amt = abs(float(a.get("amount", 0)))
        
        # Payment method badge
        pm = (a.get("payment_method") or "").lower()
        pm_label, pm_color = PAY_BADGES.get(pm, ("", "#888"))
        pm_badge = f'<span style="background:{pm_color}18;color:{pm_color};padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;margin-left:6px;">{pm_label}</span>' if pm_label else ""
        
        # AI badge
        ai_badge = ""
        if a.get("ai_worker"):
            ai_badge = f'<span style="background:rgba(139,92,246,0.15);color:#8b5cf6;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:6px;">AI {safe_string_fn(a.get("ai_worker", ""))}</span>'
        
        # Linked badge
        linked_badge = ""
        if a.get("linked_id") and a.get("linked_id") in alloc_by_id:
            linked_badge = '<span style="background:rgba(16,185,129,0.15);color:#10b981;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:4px;">LINKED</span>'
        
        # Date + Time
        txn_date = (a.get("transaction_date") or "")[:10]
        created = a.get("created_at", "")
        created_date = created[:10] if len(created) >= 10 else ""
        time_str = created[11:16] if len(created) > 16 else ""
        date_display = txn_date or created_date
        
        # Who
        who = safe_string_fn(a.get("created_by_name") or a.get("ai_worker") or "System")
        
        # Customer / supplier
        entity = ""
        if a.get("customer_name"):
            entity = safe_string_fn(a.get("customer_name"))
        elif a.get("supplier_name"):
            entity = safe_string_fn(a.get("supplier_name"))
        
        # Reference
        ref = safe_string_fn(a.get("reference", ""))
        
        # Description
        desc = safe_string_fn(a.get("description", "-")[:80])
        
        # Category
        cat = safe_string_fn(a.get("category", ""))
        cat_code = safe_string_fn(a.get("category_code", ""))
        
        # Source URL
        src_url = _source_url(a)
        
        # Extra data for PO links etc
        extra_data = {}
        try:
            _ex = a.get("extra", "{}")
            extra_data = json.loads(_ex) if isinstance(_ex, str) else (_ex or {})
        except:
            pass
        
        po_id = extra_data.get("po_id", "")
        po_link = f'<a href="/purchase/{po_id}" style="font-size:11px;color:var(--primary);text-decoration:none;padding:4px 10px;border:1px solid var(--border);border-radius:6px;">View PO</a>' if po_id else ""
        
        # Build inner detail sections
        gl_detail = _build_gl_detail(a, money_fn)
        stock_detail = _build_stock_detail(a)
        linked_detail = _build_linked_detail(a, alloc_by_id, money_fn, safe_string_fn)
        ai_detail = _build_ai_detail(a, safe_string_fn)
        
        # Income or expense indicator
        is_income = atype in ("pos_sale", "payment", "invoice", "bank_import")
        amt_color = "#10b981" if is_income else "#ef4444"
        amt_prefix = "+" if is_income else "-"
        
        aid = a.get("id", f"alloc_{idx}")
        
        return f'''
        <div class="ledger-entry" style="border:1px solid var(--border);border-radius:10px;margin-bottom:6px;overflow:hidden;border-left:4px solid {color};">
            <!-- ACCORDION HEADER - Layer 1 -->
            <div onclick="toggleLedger('{aid}')" style="cursor:pointer;padding:12px 16px;display:grid;grid-template-columns:90px 1fr 130px 100px 40px;align-items:center;gap:10px;transition:background 0.15s;" 
                 onmouseover="this.style.background='rgba(99,102,241,0.04)'" onmouseout="this.style.background='transparent'">
                <!-- Date -->
                <div>
                    <div style="font-size:13px;font-weight:700;color:var(--text);">{date_display}</div>
                    <div style="font-size:10px;color:var(--text-muted);">{time_str}</div>
                </div>
                <!-- Type + Description -->
                <div style="min-width:0;">
                    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                        <span style="background:{color}18;color:{color};padding:2px 8px;border-radius:5px;font-size:10px;font-weight:800;letter-spacing:0.5px;">{short}</span>
                        <span style="font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{desc}</span>
                        {pm_badge}{ai_badge}{linked_badge}
                    </div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">
                        {ref}{f' &bull; {entity}' if entity else ''}{f' &bull; {who}' if who != 'System' else ''}
                    </div>
                </div>
                <!-- Amount -->
                <div style="text-align:right;">
                    <div style="font-size:15px;font-weight:800;color:{amt_color};font-family:monospace;">{amt_prefix}{money_fn(amt)}</div>
                </div>
                <!-- Running Balance placeholder -->
                <div style="text-align:right;">
                    <div style="font-size:11px;color:var(--text-muted);font-family:monospace;">&nbsp;</div>
                </div>
                <!-- Chevron -->
                <div style="text-align:center;">
                    <span id="chev_{aid}" style="color:var(--text-muted);font-size:14px;transition:transform 0.2s;display:inline-block;">&#9654;</span>
                </div>
            </div>
            
            <!-- ACCORDION BODY - Layer 2 & 3 -->
            <div id="body_{aid}" style="display:none;border-top:1px solid var(--border);background:rgba(99,102,241,0.02);">
                <div style="padding:16px;">
                    
                    <!-- Transaction Info Grid -->
                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:10px;">
                        <div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Type</div>
                            <div style="font-weight:600;font-size:13px;">{label}</div>
                        </div>
                        <div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Amount</div>
                            <div style="font-weight:700;font-size:14px;color:{amt_color};font-family:monospace;">{money_fn(amt)}</div>
                        </div>
                        {f"""<div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Payment</div>
                            <div style="font-weight:600;font-size:13px;">{pm.upper() if pm else '-'}</div>
                        </div>""" if pm else ""}
                        {f"""<div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Customer</div>
                            <div style="font-weight:600;font-size:13px;">{entity}</div>
                        </div>""" if a.get("customer_name") else ""}
                        {f"""<div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Supplier</div>
                            <div style="font-weight:600;font-size:13px;">{safe_string_fn(a.get('supplier_name', ''))}</div>
                        </div>""" if a.get("supplier_name") else ""}
                        {f"""<div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Category</div>
                            <div style="font-weight:600;font-size:13px;">{cat} {f'({cat_code})' if cat_code else ''}</div>
                        </div>""" if cat else ""}
                        <div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Reference</div>
                            <div style="font-weight:600;font-size:13px;">{ref or '-'}</div>
                        </div>
                        <div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Created By</div>
                            <div style="font-weight:600;font-size:13px;">{who}</div>
                        </div>
                    </div>
                    
                    <!-- Source Document Link -->
                    <div style="display:flex;gap:8px;margin-bottom:4px;flex-wrap:wrap;">
                        <a href="/{src_url}" style="font-size:11px;color:var(--primary);text-decoration:none;padding:4px 10px;border:1px solid var(--border);border-radius:6px;">View Source Document</a>
                        {po_link}
                    </div>
                    
                    <!-- AI Decision (if applicable) -->
                    {ai_detail}
                    
                    <!-- GL Journal Entries -->
                    {gl_detail}
                    
                    <!-- Stock Movements -->
                    {stock_detail}
                    
                    <!-- Linked Transaction -->
                    {linked_detail}
                    
                </div>
            </div>
        </div>'''
    
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LEDGER PAGE - "Follow the Money"
    # ═══════════════════════════════════════════════════════════════════════════
    
    @app.route("/ledger")
    @login_required
    def ledger_page():
        """Follow the Money - Full Audit Trail Ledger"""
        
        import clickai as _ck
        render_page = _ck.render_page
        money = _ck.money
        safe_string = _ck.safe_string
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return render_page("Ledger", "<div class='card'><p>No business selected</p></div>", user, "ledger")
        
        from flask import request as req
        
        # ── FILTERS ──
        date_from = req.args.get("from", "")
        date_to = req.args.get("to", "")
        type_filter = req.args.get("type", "all")
        pay_filter = req.args.get("pay", "all")
        search_q = req.args.get("q", "").strip()
        group_by = req.args.get("group", "transaction")  # transaction | day | customer | cashier
        page = int(req.args.get("page", 1))
        per_page = 50
        
        # ── LOAD ALL ALLOCATIONS ──
        all_allocs = db.get("allocation_log", {"business_id": biz_id}) or []
        
        # Hydrate: read from extra if top-level fields missing
        for a in all_allocs:
            if not a.get("transaction_date") and a.get("extra"):
                try:
                    ex = json.loads(a["extra"]) if isinstance(a["extra"], str) else a["extra"]
                    if ex.get("transaction_date"):
                        a["transaction_date"] = ex["transaction_date"]
                    if ex.get("match_key") and not a.get("match_key"):
                        a["match_key"] = ex["match_key"]
                except:
                    pass
        
        # ── APPLY FILTERS ──
        filtered = all_allocs
        
        # Date range
        if date_from:
            filtered = [a for a in filtered if (a.get("transaction_date") or a.get("created_at", ""))[:10] >= date_from]
        if date_to:
            filtered = [a for a in filtered if (a.get("transaction_date") or a.get("created_at", ""))[:10] <= date_to]
        
        # Type
        if type_filter and type_filter != "all":
            filtered = [a for a in filtered if a.get("allocation_type") == type_filter]
        
        # Payment method
        if pay_filter and pay_filter != "all":
            filtered = [a for a in filtered if (a.get("payment_method") or "").lower() == pay_filter]
        
        # Search — search EVERYTHING
        if search_q:
            sq = search_q.lower()
            # Also search by amount (e.g. user types "1500" or "R1500")
            sq_amt = sq.replace("r", "").replace(",", "").replace(" ", "").strip()
            
            def _matches(a):
                # Text fields
                for field in ("description", "supplier_name", "customer_name", "reference", 
                              "category", "ai_worker", "created_by_name", "payment_method",
                              "allocation_type", "category_code", "ai_reasoning"):
                    if sq in (a.get(field) or "").lower():
                        return True
                # Amount match
                try:
                    if sq_amt and abs(float(a.get("amount", 0)) - float(sq_amt)) < 0.50:
                        return True
                except:
                    pass
                return False
            
            filtered = [a for a in filtered if _matches(a)]
        
        # ── SORT newest first ──
        filtered = sorted(filtered, key=lambda x: x.get("transaction_date") or x.get("created_at", ""), reverse=True)
        
        # ── STATS ──
        total_count = len(filtered)
        income_total = sum(abs(float(a.get("amount", 0))) for a in filtered 
                          if a.get("allocation_type") in ("pos_sale", "payment", "invoice", "bank_import"))
        expense_total = sum(abs(float(a.get("amount", 0))) for a in filtered 
                           if a.get("allocation_type") in ("scan_supplier_invoice", "scan_expense", "manual_expense", 
                                                           "supplier_payment", "grv", "credit_note"))
        ai_count = sum(1 for a in filtered if a.get("ai_worker"))
        linked_count = sum(1 for a in filtered if a.get("linked_id"))
        
        # ── PAGINATION (for transaction view) ──
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        start_idx = (page - 1) * per_page
        
        # ── BUILD ALLOC LOOKUP ──
        alloc_by_id = {a.get("id"): a for a in all_allocs}
        
        # ── BUILD CONTENT BASED ON GROUPING ──
        entries_html = ""
        
        if group_by == "transaction":
            # Simple list of accordions — each transaction is its own accordion
            page_allocs = filtered[start_idx:start_idx + per_page]
            for idx, a in enumerate(page_allocs):
                entries_html += _build_single_accordion(a, alloc_by_id, money, safe_string, start_idx + idx)
        
        elif group_by == "day":
            # Group by date, each date is an outer accordion
            by_day = defaultdict(list)
            for a in filtered:
                d = (a.get("transaction_date") or a.get("created_at", ""))[:10]
                by_day[d].append(a)
            
            days = sorted(by_day.keys(), reverse=True)
            # Paginate by days
            page_days = days[start_idx:start_idx + per_page]
            total_pages = max(1, (len(days) + per_page - 1) // per_page)
            
            for day in page_days:
                day_allocs = by_day[day]
                day_total = sum(abs(float(a.get("amount", 0))) for a in day_allocs)
                day_income = sum(abs(float(a.get("amount", 0))) for a in day_allocs 
                                if a.get("allocation_type") in ("pos_sale", "payment", "invoice", "bank_import"))
                day_expense = sum(abs(float(a.get("amount", 0))) for a in day_allocs 
                                 if a.get("allocation_type") not in ("pos_sale", "payment", "invoice", "bank_import"))
                
                inner_html = ""
                for idx, a in enumerate(day_allocs):
                    inner_html += _build_single_accordion(a, alloc_by_id, money, safe_string, idx)
                
                day_id = day.replace("-", "")
                entries_html += f'''
                <div style="border:2px solid var(--border);border-radius:12px;margin-bottom:10px;overflow:hidden;">
                    <div onclick="toggleGroup('{day_id}')" style="cursor:pointer;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;background:rgba(99,102,241,0.06);"
                         onmouseover="this.style.background='rgba(99,102,241,0.10)'" onmouseout="this.style.background='rgba(99,102,241,0.06)'">
                        <div style="display:flex;align-items:center;gap:12px;">
                            <span id="gchev_{day_id}" style="font-size:14px;transition:transform 0.2s;display:inline-block;color:var(--text-muted);">&#9654;</span>
                            <span style="font-size:16px;font-weight:800;">{day}</span>
                            <span style="font-size:12px;color:var(--text-muted);">{len(day_allocs)} transactions</span>
                        </div>
                        <div style="display:flex;gap:15px;align-items:center;">
                            <span style="font-size:13px;color:#10b981;font-weight:700;font-family:monospace;">+{money(day_income)}</span>
                            <span style="font-size:13px;color:#ef4444;font-weight:700;font-family:monospace;">-{money(day_expense)}</span>
                        </div>
                    </div>
                    <div id="gbody_{day_id}" style="display:none;padding:10px;">
                        {inner_html}
                    </div>
                </div>'''
        
        elif group_by in ("customer", "cashier"):
            # Group by customer_name or created_by_name
            field = "customer_name" if group_by == "customer" else "created_by_name"
            by_entity = defaultdict(list)
            for a in filtered:
                key = a.get(field) or a.get("supplier_name") or "Unknown"
                by_entity[key].append(a)
            
            entities = sorted(by_entity.keys())
            page_entities = entities[start_idx:start_idx + per_page]
            total_pages = max(1, (len(entities) + per_page - 1) // per_page)
            
            for entity in page_entities:
                ent_allocs = by_entity[entity]
                ent_total = sum(abs(float(a.get("amount", 0))) for a in ent_allocs)
                
                inner_html = ""
                for idx, a in enumerate(ent_allocs):
                    inner_html += _build_single_accordion(a, alloc_by_id, money, safe_string, idx)
                
                ent_id = "".join(c for c in entity if c.isalnum())[:20]
                entries_html += f'''
                <div style="border:2px solid var(--border);border-radius:12px;margin-bottom:10px;overflow:hidden;">
                    <div onclick="toggleGroup('{ent_id}')" style="cursor:pointer;padding:14px 18px;display:flex;justify-content:space-between;align-items:center;background:rgba(99,102,241,0.06);"
                         onmouseover="this.style.background='rgba(99,102,241,0.10)'" onmouseout="this.style.background='rgba(99,102,241,0.06)'">
                        <div style="display:flex;align-items:center;gap:12px;">
                            <span id="gchev_{ent_id}" style="font-size:14px;transition:transform 0.2s;display:inline-block;color:var(--text-muted);">&#9654;</span>
                            <span style="font-size:16px;font-weight:800;">{safe_string(entity)}</span>
                            <span style="font-size:12px;color:var(--text-muted);">{len(ent_allocs)} transactions</span>
                        </div>
                        <div style="font-size:15px;font-weight:800;font-family:monospace;">{money(ent_total)}</div>
                    </div>
                    <div id="gbody_{ent_id}" style="display:none;padding:10px;">
                        {inner_html}
                    </div>
                </div>'''
        
        if not entries_html:
            entries_html = f'''
            <div style="text-align:center;padding:60px 20px;color:var(--text-muted);">
                <div style="font-size:48px;margin-bottom:15px;">&#128214;</div>
                <div style="font-size:16px;font-weight:600;margin-bottom:8px;">No transactions found</div>
                <div style="font-size:13px;">{'Try adjusting your filters or search terms.' if search_q or date_from or type_filter != 'all' else 'Transactions are logged automatically as they happen in POS, Invoices, Expenses, and more.'}</div>
            </div>'''
        
        # ── PAGINATION HTML ──
        pagination_html = ""
        if total_pages > 1:
            base_url = f"/ledger?from={date_from}&to={date_to}&type={type_filter}&pay={pay_filter}&q={search_q}&group={group_by}"
            prev_btn = f'<a href="{base_url}&page={page-1}" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">&larr; Prev</a>' if page > 1 else ''
            next_btn = f'<a href="{base_url}&page={page+1}" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">Next &rarr;</a>' if page < total_pages else ''
            pagination_html = f'''
            <div style="display:flex;justify-content:center;gap:8px;margin-top:15px;align-items:center;">
                {prev_btn}
                <span style="color:var(--text-muted);font-size:13px;">Page {page} of {total_pages}</span>
                {next_btn}
            </div>'''
        
        # ── TYPE FILTER OPTIONS ──
        type_options = '<option value="all">All Types</option>'
        for tkey, (tshort, tcolor, tlabel) in TYPE_CONFIG.items():
            selected = "selected" if type_filter == tkey else ""
            type_options += f'<option value="{tkey}" {selected}>{tshort} {tlabel}</option>'
        
        # ── GROUP BY BUTTONS ──
        def _grp_btn(val, lbl):
            active = "background:var(--primary);color:white;font-weight:700;" if group_by == val else "background:var(--card);color:var(--text);"
            return f'<a href="/ledger?from={date_from}&to={date_to}&type={type_filter}&pay={pay_filter}&q={search_q}&group={val}" style="padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none;border:1px solid var(--border);{active}">{lbl}</a>'
        
        group_btns = f'''
            {_grp_btn("transaction", "Per Transaction")}
            {_grp_btn("day", "Per Day")}
            {_grp_btn("customer", "Per Customer")}
            {_grp_btn("cashier", "Per Cashier")}
        '''
        
        # ── MAIN PAGE ──
        content = f'''
        <!-- HEADER -->
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <div>
                <h2 style="margin:0;font-size:22px;">Follow the Money</h2>
                <p style="color:var(--text-muted);margin:4px 0 0 0;font-size:13px;">Full audit trail — every transaction, every rand, forever.</p>
            </div>
        </div>
        
        <!-- STATS BAR -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px;">
            <div class="card" style="padding:12px 16px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Transactions</div>
                <div style="font-size:22px;font-weight:800;color:var(--text);">{total_count:,}</div>
            </div>
            <div class="card" style="padding:12px 16px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Income</div>
                <div style="font-size:18px;font-weight:800;color:#10b981;font-family:monospace;">{money(income_total)}</div>
            </div>
            <div class="card" style="padding:12px 16px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Expenses</div>
                <div style="font-size:18px;font-weight:800;color:#ef4444;font-family:monospace;">{money(expense_total)}</div>
            </div>
            <div class="card" style="padding:12px 16px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">AI Processed</div>
                <div style="font-size:22px;font-weight:800;color:#8b5cf6;">{ai_count}</div>
            </div>
            <div class="card" style="padding:12px 16px;text-align:center;">
                <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Linked Pairs</div>
                <div style="font-size:22px;font-weight:800;color:#10b981;">{linked_count // 2}</div>
            </div>
        </div>
        
        <!-- SEARCH & FILTERS -->
        <div class="card" style="padding:14px;margin-bottom:16px;">
            <form method="GET" action="/ledger" id="ledgerForm">
                <input type="hidden" name="group" value="{group_by}">
                
                <!-- Search Bar -->
                <div style="position:relative;margin-bottom:12px;">
                    <input type="text" name="q" value="{safe_string(search_q)}" 
                           placeholder="Search anything — customer, supplier, amount, reference, cashier, invoice number..." 
                           class="form-input" 
                           style="width:100%;padding:12px 16px 12px 40px;font-size:14px;border-radius:10px;">
                    <span style="position:absolute;left:14px;top:50%;transform:translateY(-50%);color:var(--text-muted);font-size:16px;">&#128269;</span>
                </div>
                
                <!-- Filter Row -->
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                    <input type="date" name="from" value="{date_from}" class="form-input" style="width:auto;font-size:12px;" title="From date">
                    <span style="color:var(--text-muted);font-size:12px;">to</span>
                    <input type="date" name="to" value="{date_to}" class="form-input" style="width:auto;font-size:12px;" title="To date">
                    
                    <select name="type" class="form-input" style="width:auto;font-size:12px;">
                        {type_options}
                    </select>
                    
                    <select name="pay" class="form-input" style="width:auto;font-size:12px;">
                        <option value="all" {"selected" if pay_filter == "all" else ""}>All Payments</option>
                        <option value="cash" {"selected" if pay_filter == "cash" else ""}>Cash</option>
                        <option value="card" {"selected" if pay_filter == "card" else ""}>Card</option>
                        <option value="eft" {"selected" if pay_filter == "eft" else ""}>EFT</option>
                        <option value="account" {"selected" if pay_filter == "account" else ""}>Account</option>
                    </select>
                    
                    <button type="submit" class="btn btn-primary" style="padding:8px 20px;font-size:13px;">Search</button>
                    <a href="/ledger" style="color:var(--text-muted);font-size:12px;padding:6px;">Clear All</a>
                </div>
            </form>
        </div>
        
        <!-- GROUP BY BAR -->
        <div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap;align-items:center;">
            <span style="font-size:11px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-right:6px;">Group by:</span>
            {group_btns}
        </div>
        
        <!-- LEDGER ENTRIES -->
        <div id="ledgerEntries">
            {entries_html}
        </div>
        
        {pagination_html}
        
        <!-- JAVASCRIPT -->
        <script>
        // Toggle individual transaction accordion
        function toggleLedger(id) {{
            const body = document.getElementById('body_' + id);
            const chev = document.getElementById('chev_' + id);
            if (!body) return;
            
            if (body.style.display === 'none') {{
                body.style.display = '';
                if (chev) chev.style.transform = 'rotate(90deg)';
            }} else {{
                body.style.display = 'none';
                if (chev) chev.style.transform = 'rotate(0deg)';
            }}
        }}
        
        // Toggle group accordion (day/customer/cashier)
        function toggleGroup(id) {{
            const body = document.getElementById('gbody_' + id);
            const chev = document.getElementById('gchev_' + id);
            if (!body) return;
            
            if (body.style.display === 'none') {{
                body.style.display = '';
                if (chev) chev.style.transform = 'rotate(90deg)';
            }} else {{
                body.style.display = 'none';
                if (chev) chev.style.transform = 'rotate(0deg)';
            }}
        }}
        
        // Expand all / Collapse all
        function expandAll() {{
            document.querySelectorAll('[id^="body_"]').forEach(el => el.style.display = '');
            document.querySelectorAll('[id^="chev_"]').forEach(el => el.style.transform = 'rotate(90deg)');
            document.querySelectorAll('[id^="gbody_"]').forEach(el => el.style.display = '');
            document.querySelectorAll('[id^="gchev_"]').forEach(el => el.style.transform = 'rotate(90deg)');
        }}
        function collapseAll() {{
            document.querySelectorAll('[id^="body_"]').forEach(el => el.style.display = 'none');
            document.querySelectorAll('[id^="chev_"]').forEach(el => el.style.transform = 'rotate(0deg)');
            document.querySelectorAll('[id^="gbody_"]').forEach(el => el.style.display = 'none');
            document.querySelectorAll('[id^="gchev_"]').forEach(el => el.style.transform = 'rotate(0deg)');
        }}
        
        // Keyboard shortcut: Enter in search to submit
        document.querySelector('input[name="q"]').addEventListener('keydown', function(e) {{
            if (e.key === 'Enter') {{
                e.preventDefault();
                document.getElementById('ledgerForm').submit();
            }}
        }});
        </script>
        
        <style>
            .ledger-entry {{ transition: box-shadow 0.15s; }}
            .ledger-entry:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
            @media (max-width: 768px) {{
                .ledger-entry > div:first-child {{
                    grid-template-columns: 70px 1fr 90px !important;
                }}
                .ledger-entry > div:first-child > div:nth-child(4),
                .ledger-entry > div:first-child > div:nth-child(5) {{
                    display: none !important;
                }}
            }}
        </style>
        '''
        
        return render_page("Follow the Money", content, user, "ledger")
    
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LEDGER STATS API (for dashboard widget)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @app.route("/api/ledger/stats")
    @login_required
    def api_ledger_stats():
        """Get ledger stats for dashboard widget"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return {"today": 0, "ai": 0, "manual": 0}
        
        try:
            allocs = db.get("allocation_log", {"business_id": biz_id}) or []
            today_allocs = [a for a in allocs if (a.get("created_at") or "")[:10] == today_fn()]
            
            ai = sum(1 for a in today_allocs if a.get("ai_worker"))
            manual = len(today_allocs) - ai
            total_amt = sum(abs(float(a.get("amount", 0))) for a in today_allocs)
            
            return {
                "today": len(today_allocs),
                "ai": ai,
                "manual": manual,
                "total_amount": round(total_amt, 2)
            }
        except Exception as e:
            logger.error(f"[ALLOC LOG] Stats error: {e}")
            return {"today": 0, "ai": 0, "manual": 0}
    
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LEDGER SEARCH API (for AJAX / Zane)
    # ═══════════════════════════════════════════════════════════════════════════
    
    @app.route("/api/ledger/search")
    @login_required
    def api_ledger_search():
        """Search ledger entries via API - returns JSON"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return {"results": [], "total": 0}
        
        from flask import request as req
        q = req.args.get("q", "").strip().lower()
        limit = min(int(req.args.get("limit", 20)), 100)
        
        if not q:
            return {"results": [], "total": 0}
        
        try:
            allocs = db.get("allocation_log", {"business_id": biz_id}) or []
            
            # Search amount too
            q_amt = q.replace("r", "").replace(",", "").replace(" ", "").strip()
            
            results = []
            for a in allocs:
                matched = False
                for field in ("description", "supplier_name", "customer_name", "reference", 
                              "category", "created_by_name", "payment_method", "allocation_type"):
                    if q in (a.get(field) or "").lower():
                        matched = True
                        break
                
                if not matched:
                    try:
                        if q_amt and abs(float(a.get("amount", 0)) - float(q_amt)) < 0.50:
                            matched = True
                    except:
                        pass
                
                if matched:
                    results.append({
                        "id": a.get("id"),
                        "date": (a.get("transaction_date") or a.get("created_at", ""))[:10],
                        "type": a.get("allocation_type"),
                        "description": (a.get("description") or "")[:80],
                        "amount": float(a.get("amount", 0)),
                        "payment_method": a.get("payment_method", ""),
                        "customer": a.get("customer_name", ""),
                        "supplier": a.get("supplier_name", ""),
                        "reference": a.get("reference", ""),
                        "created_by": a.get("created_by_name", ""),
                    })
                    
                    if len(results) >= limit:
                        break
            
            # Sort newest first
            results.sort(key=lambda x: x.get("date", ""), reverse=True)
            
            return {"results": results, "total": len(results)}
        
        except Exception as e:
            logger.error(f"[ALLOC LOG] Search error: {e}")
            return {"results": [], "total": 0, "error": str(e)}
    
    
    logger.info("[ALLOC LOG] Ledger routes registered — Follow the Money ✓")
