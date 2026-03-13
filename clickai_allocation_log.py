"""
ClickAI Allocation Log Module
===============================
"Place of Safety" - Every transaction allocation logged and viewable.

Tracks:
- POS sales (who, what, GL accounts, stock movement)
- Scanned invoices (AI decisions, stock matching, category)
- Scanned expenses (AI category, GL code, reasoning)
- Bank statement imports (auto-categorization, matching)
- Manual expenses, payments, credit notes
- Journal entries

Each allocation can be reviewed and edited from /ledger

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
                # Normalize: lowercase, strip spaces, just first word for matching
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
    
    Logic:
    - A scanned invoice (scan_supplier_invoice) should link to a bank entry (bank_categorize) and vice versa
    - Matching is by match_key (supplier+amount) OR by reference (invoice number)
    - Only links if not already linked
    """
    global _db
    if not _db:
        return
    
    # Define which types can pair with each other
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
            continue  # Already linked to something else
        if a.get("allocation_type") not in valid_partners:
            continue
        
        score = 0
        
        # Match by match_key (supplier+amount)
        if match_key and a.get("match_key") == match_key:
            score += 10
        
        # Match by reference (invoice number)
        a_ref = (a.get("reference") or "").strip().upper()
        # Check if new entry's reference appears in the other entry's description or reference
        if a_ref and match_key and a_ref in match_key.upper():
            score += 5
        
        # Amount proximity (within 2% or R10)
        a_amt = abs(float(a.get("amount", 0)))
        if a_amt > 0 and new_amount > 0:
            diff = abs(a_amt - new_amount)
            pct = diff / max(a_amt, new_amount) if max(a_amt, new_amount) > 0 else 1
            if diff < 0.02:  # Exact match
                score += 8
            elif pct < 0.02:  # Within 2%
                score += 5
            elif diff <= 10:  # Within R10
                score += 3
        
        if score > best_score:
            best_score = score
            best_match = a
    
    # Need at least score 10 (match_key match) or 13 (ref + amount) to auto-link
    if best_match and best_score >= 10:
        # Link both entries to each other (ignore errors if linked_id column doesn't exist yet)
        try:
            _db.save("allocation_log", {"id": new_id, "linked_id": best_match["id"]})
            _db.save("allocation_log", {"id": best_match["id"], "linked_id": new_id})
            logger.info(f"[ALLOC LOG] AUTO-LINKED: {new_type} <-> {best_match.get('allocation_type')} | key={match_key} | score={best_score}")
        except Exception as e:
            logger.warning(f"[ALLOC LOG] Auto-link save failed (column may not exist): {e}")


def register_ledger_routes(app, db, login_required, Auth, generate_id, now_fn, today_fn):
    """Register the /ledger page and API routes"""
    
    global _db, _generate_id, _now, _today
    _db = db
    _generate_id = generate_id
    _now = now_fn
    _today = today_fn
    
    @app.route("/ledger")
    @login_required
    def ledger_page():
        """Allocation Ledger - Place of Safety"""
        
        # Import these at call time (they're defined after module registration in clickai.py)
        import clickai as _ck
        render_page = _ck.render_page
        money = _ck.money
        safe_string = _ck.safe_string
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return render_page("Ledger", "<div class='card'><p>No business selected</p></div>", user, "ledger")
        
        # Get filter params
        from flask import request as req
        date_filter = req.args.get("date", "")  # Empty = show ALL (never hide data)
        type_filter = req.args.get("type", "all")
        search_q = req.args.get("q", "").strip()
        page = int(req.args.get("page", 1))
        per_page = 100
        
        # Load allocations — ALWAYS load all, never discard
        all_allocs = db.get("allocation_log", {"business_id": biz_id}) or []
        
        # Hydrate: if transaction_date/match_key/linked_id missing at top level, read from extra
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
        
        # Filter by date ONLY if explicitly chosen (data never disappears)
        if date_filter:
            all_allocs = [a for a in all_allocs if 
                (a.get("transaction_date") or "")[:10] == date_filter or
                (a.get("created_at") or "")[:10] == date_filter
            ]
        
        # Filter by type
        if type_filter and type_filter != "all":
            all_allocs = [a for a in all_allocs if a.get("allocation_type") == type_filter]
        
        # Search
        if search_q:
            sq = search_q.lower()
            all_allocs = [a for a in all_allocs if 
                sq in (a.get("description") or "").lower() or
                sq in (a.get("supplier_name") or "").lower() or
                sq in (a.get("customer_name") or "").lower() or
                sq in (a.get("reference") or "").lower() or
                sq in (a.get("category") or "").lower() or
                sq in (a.get("ai_worker") or "").lower() or
                sq in (a.get("created_by_name") or "").lower()
            ]
        
        # Sort newest first — prefer transaction_date, fallback to created_at
        all_allocs = sorted(all_allocs, key=lambda x: x.get("transaction_date") or x.get("created_at", ""), reverse=True)
        
        # Stats (on filtered set)
        total_count = len(all_allocs)
        total_amount = sum(abs(float(a.get("amount", 0))) for a in all_allocs)
        ai_count = sum(1 for a in all_allocs if a.get("ai_worker"))
        manual_count = total_count - ai_count
        linked_count = sum(1 for a in all_allocs if a.get("linked_id"))
        
        # Pagination
        start_idx = (page - 1) * per_page
        page_allocs = all_allocs[start_idx:start_idx + per_page]
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        
        # Build a quick ID lookup for linked entries
        alloc_by_id = {a.get("id"): a for a in all_allocs}
        
        # Build pagination HTML outside the f-string (Python 3.11 can't handle nested f-string comparisons)
        pagination_html = ""
        if total_pages > 1:
            prev_btn = f'<a href="/ledger?page={page-1}&date={date_filter}&type={type_filter}&q={search_q}" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">&larr; Prev</a>' if page > 1 else ''
            next_btn = f'<a href="/ledger?page={page+1}&date={date_filter}&type={type_filter}&q={search_q}" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">Next &rarr;</a>' if page < total_pages else ''
            pagination_html = f'''
            <div style="display:flex;justify-content:center;gap:8px;margin-top:15px;align-items:center;">
                {prev_btn}
                <span style="color:var(--text-muted);font-size:13px;">Page {page} of {total_pages} ({total_count} entries)</span>
                {next_btn}
            </div>'''
        
        # Build date clear link
        date_clear_html = f'<a href="/ledger" style="font-size:11px;color:var(--primary);text-decoration:none;">✕ Clear date</a>' if date_filter else '<span style="font-size:11px;color:var(--text-muted);">Showing all</span>'
        
        # Build no-results message
        no_results_msg = f"No allocations found for {date_filter}" if date_filter else "No allocations found"
        
        # Build linked pairs badge
        linked_pairs = linked_count // 2
        linked_badge_html = f'<span style="background:rgba(16,185,129,0.15);color:#10b981;padding:6px 12px;border-radius:8px;font-size:13px;font-weight:600;">🔗 {linked_pairs} linked pairs</span>' if linked_count > 0 else ''
        
        # Type icons and colors
        type_config = {
            "pos_sale": ("🛒", "#10b981", "POS Sale"),
            "scan_supplier_invoice": ("📸", "#3b82f6", "Scanned Invoice"),
            "scan_expense": ("📸", "#f59e0b", "Scanned Expense"),
            "bank_import": ("🏦", "#8b5cf6", "Bank Import"),
            "bank_categorize": ("🏦", "#6366f1", "Bank Categorize"),
            "manual_expense": ("✏️", "#f97316", "Manual Expense"),
            "payment": ("💰", "#10b981", "Payment"),
            "credit_note": ("🔴", "#ef4444", "Credit Note"),
            "journal_entry": ("📒", "#64748b", "Journal Entry"),
            "supplier_payment": ("💳", "#0ea5e9", "Supplier Payment"),
            "grv": ("📦", "#0f766e", "GRV"),
            "invoice": ("📄", "#10b981", "Invoice"),
        }
        
        # Build rows
        rows = ""
        for a in page_allocs:
            atype = a.get("allocation_type", "unknown")
            icon, color, label = type_config.get(atype, ("📋", "#888", atype.replace("_", " ").title()))
            
            amt = float(a.get("amount", 0))
            
            # AI badge
            ai_badge = ""
            if a.get("ai_worker"):
                conf = a.get("ai_confidence", "")
                conf_color = {"HIGH": "#10b981", "MEDIUM": "#f59e0b", "LOW": "#ef4444"}.get(conf, "#888")
                ai_badge = f'<span style="background:rgba(139,92,246,0.15);color:#8b5cf6;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:6px;">🤖 {safe_string(a.get("ai_worker", ""))}</span>'
            
            # Linked badge — show if this entry has a partner
            linked_badge = ""
            linked_detail = ""
            linked_id = a.get("linked_id", "")
            if linked_id and linked_id in alloc_by_id:
                partner = alloc_by_id[linked_id]
                p_type = partner.get("allocation_type", "")
                p_icon, p_color, p_label = type_config.get(p_type, ("📋", "#888", p_type.replace("_", " ").title()))
                p_date = (partner.get("transaction_date") or partner.get("created_at", ""))[:10]
                linked_badge = f'<span style="background:rgba(16,185,129,0.15);color:#10b981;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:4px;" title="Linked to {p_label} from {p_date}">🔗</span>'
                linked_detail = f"""<div style="margin-bottom:12px;padding:10px;background:rgba(16,185,129,0.08);border-radius:6px;border-left:3px solid #10b981;">
                    <span style="font-size:10px;color:#10b981;text-transform:uppercase;letter-spacing:1px;font-weight:700;">🔗 Linked Transaction</span>
                    <div style="margin-top:6px;font-size:12px;display:flex;gap:15px;flex-wrap:wrap;">
                        <span><b>{p_icon} {p_label}</b></span>
                        <span>{p_date}</span>
                        <span>{money(abs(float(partner.get('amount', 0))))}</span>
                        <span style="color:var(--text-muted);">{safe_string(partner.get('description', '')[:60])}</span>
                        <a href="#" onclick="toggleDetail('{linked_id}');return false;" style="color:var(--primary);font-size:11px;">View partner →</a>
                    </div>
                </div>"""
            
            # Who
            who = safe_string(a.get("created_by_name") or a.get("ai_worker") or "System")
            
            # Date + Time — show transaction_date prominently, created_at as secondary
            txn_date = (a.get("transaction_date") or "")[:10]
            created = a.get("created_at", "")
            created_date = created[:10] if len(created) >= 10 else ""
            time_str = created[11:16] if len(created) > 16 else ""
            date_display = txn_date or created_date
            # Show both if they differ
            date_note = ""
            if txn_date and created_date and txn_date != created_date:
                date_note = f'<br><span style="font-size:9px;color:var(--text-muted);">logged {created_date}</span>'
            
            # GL summary
            gl_summary = ""
            try:
                gl = json.loads(a.get("gl_entries", "[]"))
                if gl:
                    parts = []
                    for g in gl:
                        code = g.get("account_code", "?")
                        dr = float(g.get("debit", 0))
                        cr = float(g.get("credit", 0))
                        if dr > 0:
                            parts.append(f"DR {code} R{dr:,.2f}")
                        if cr > 0:
                            parts.append(f"CR {code} R{cr:,.2f}")
                    gl_summary = " | ".join(parts[:4])
                    if len(parts) > 4:
                        gl_summary += f" +{len(parts)-4} more"
            except:
                pass
            
            # Stock summary
            stock_summary = ""
            try:
                sm = json.loads(a.get("stock_movements", "[]"))
                if sm:
                    stock_summary = f"{len(sm)} item(s) affected"
            except:
                pass
            
            rows += f'''
            <tr class="alloc-row" onclick="toggleDetail('{a.get("id")}')" style="cursor:pointer;{'border-left:3px solid #10b981;' if linked_id else ''}">
                <td style="padding:10px 8px;white-space:nowrap;">
                    <span style="font-size:12px;font-weight:600;">{date_display}</span>
                    <br><span style="font-size:10px;color:var(--text-muted);">{time_str}</span>
                    {date_note}
                </td>
                <td style="padding:10px 8px;">
                    <span style="background:{color}22;color:{color};padding:3px 8px;border-radius:6px;font-size:11px;font-weight:600;">{icon} {label}</span>
                    {linked_badge}
                </td>
                <td style="padding:10px 8px;">
                    <div style="font-weight:600;font-size:13px;">{safe_string(a.get("description", "-")[:60])}</div>
                    <div style="font-size:11px;color:var(--text-muted);">
                        {safe_string(a.get("reference", ""))}
                        {f' • {safe_string(a.get("customer_name"))}' if a.get("customer_name") else ""}
                        {f' • {safe_string(a.get("supplier_name"))}' if a.get("supplier_name") else ""}
                    </div>
                </td>
                <td style="padding:10px 8px;text-align:right;font-weight:700;font-size:14px;">
                    {money(amt)}
                </td>
                <td style="padding:10px 8px;">
                    <span style="font-size:12px;">{safe_string(who)}</span>{ai_badge}
                </td>
                <td style="padding:10px 8px;text-align:center;">
                    <span style="color:var(--text-muted);font-size:16px;">▸</span>
                </td>
            </tr>
            <tr id="detail_{a.get("id")}" style="display:none;">
                <td colspan="6" style="padding:0 8px 15px 8px;background:rgba(99,102,241,0.03);">
                    <div style="padding:15px;border-radius:8px;border:1px solid var(--border);margin-top:2px;">
                        
                        {linked_detail}
                        
                        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px;">
                            <div>
                                <span style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Category</span>
                                <div style="font-weight:600;font-size:13px;">{safe_string(a.get("category", "-"))} {f'({safe_string(a.get("category_code"))})' if a.get("category_code") else ""}</div>
                            </div>
                            <div>
                                <span style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Payment</span>
                                <div style="font-weight:600;font-size:13px;">{safe_string(a.get("payment_method", "-")).title()}</div>
                            </div>
                            <div>
                                <span style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Source</span>
                                <div style="font-weight:600;font-size:13px;">{safe_string(a.get("source_table", "-"))}/{safe_string(a.get("source_id", "-")[:8])}</div>
                            </div>
                        </div>
                        
                        {f"""<div style="margin-bottom:12px;padding:10px;background:rgba(139,92,246,0.08);border-radius:6px;border-left:3px solid #8b5cf6;">
                            <span style="font-size:10px;color:#8b5cf6;text-transform:uppercase;letter-spacing:1px;font-weight:700;">🤖 AI Decision — {safe_string(a.get('ai_worker', ''))}</span>
                            {f'<span style="margin-left:8px;background:{conf_color}22;color:{conf_color};padding:1px 6px;border-radius:3px;font-size:10px;">{a.get("ai_confidence", "")}</span>' if a.get("ai_confidence") else ""}
                            <div style="margin-top:6px;font-size:12px;color:var(--text);line-height:1.6;">{safe_string(a.get('ai_reasoning', ''))}</div>
                        </div>""" if a.get("ai_reasoning") else ""}
                        
                        {f"""<div style="margin-bottom:12px;">
                            <span style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">GL Postings</span>
                            <div style="font-family:monospace;font-size:11px;margin-top:4px;color:var(--text);line-height:1.8;">{gl_summary}</div>
                        </div>""" if gl_summary else ""}
                        
                        {f"""<div style="margin-bottom:12px;">
                            <span style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;">Stock Movement</span>
                            <div style="font-size:12px;margin-top:4px;">{stock_summary}</div>
                        </div>""" if stock_summary else ""}
                        
                        <div style="display:flex;gap:8px;margin-top:10px;">
                            <a href="/{a.get('source_table','').replace('_','-')}/{a.get('source_id','')}" 
                               style="font-size:11px;color:var(--primary);text-decoration:none;">📄 View Source Document</a>
                        </div>
                    </div>
                </td>
            </tr>
            '''
        
        # Type filter options
        type_options = '<option value="all">All Types</option>'
        for tkey, (ticon, tcolor, tlabel) in type_config.items():
            selected = "selected" if type_filter == tkey else ""
            type_options += f'<option value="{tkey}" {selected}>{ticon} {tlabel}</option>'
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <div>
                <h2 style="margin:0;">📒 Allocation Ledger</h2>
                <p style="color:var(--text-muted);margin:4px 0 0 0;font-size:13px;">Place of Safety — every allocation, forever. Nothing gets deleted.</p>
            </div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <span style="background:rgba(16,185,129,0.15);color:#10b981;padding:6px 12px;border-radius:8px;font-size:13px;font-weight:600;">
                    {total_count} entries
                </span>
                <span style="background:rgba(139,92,246,0.15);color:#8b5cf6;padding:6px 12px;border-radius:8px;font-size:13px;font-weight:600;">
                    🤖 {ai_count} AI
                </span>
                {linked_badge_html}
                <span style="font-weight:700;font-size:15px;">
                    {money(total_amount)}
                </span>
            </div>
        </div>
        
        <div class="card" style="margin-bottom:15px;padding:15px;">
            <form method="GET" action="/ledger" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                <input type="date" name="date" value="{date_filter}" class="form-input" style="width:auto;" onchange="this.form.submit()">
                {date_clear_html}
                <select name="type" class="form-input" style="width:auto;" onchange="this.form.submit()">
                    {type_options}
                </select>
                <input type="text" name="q" value="{safe_string(search_q)}" placeholder="Search supplier, ref, category..." class="form-input" style="width:200px;">
                <button type="submit" class="btn btn-secondary" style="padding:8px 16px;">🔍</button>
                <a href="/ledger" style="color:var(--text-muted);font-size:12px;margin-left:5px;">Clear all</a>
            </form>
        </div>
        
        <div class="card" style="padding:0;overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr style="border-bottom:2px solid var(--border);">
                        <th style="padding:10px 8px;text-align:left;font-size:11px;color:var(--text-muted);text-transform:uppercase;width:90px;">Date</th>
                        <th style="padding:10px 8px;text-align:left;font-size:11px;color:var(--text-muted);text-transform:uppercase;width:150px;">Type</th>
                        <th style="padding:10px 8px;text-align:left;font-size:11px;color:var(--text-muted);text-transform:uppercase;">Description</th>
                        <th style="padding:10px 8px;text-align:right;font-size:11px;color:var(--text-muted);text-transform:uppercase;width:110px;">Amount</th>
                        <th style="padding:10px 8px;text-align:left;font-size:11px;color:var(--text-muted);text-transform:uppercase;width:140px;">By</th>
                        <th style="padding:10px 8px;text-align:center;width:30px;"></th>
                    </tr>
                </thead>
                <tbody>
                    {rows or f"<tr><td colspan='6' style='text-align:center;padding:40px;color:var(--text-muted);'>{no_results_msg}<br><br>Allocations are logged automatically as transactions happen.</td></tr>"}
                </tbody>
            </table>
        </div>
        
        {pagination_html}
        
        <script>
        function toggleDetail(id) {{
            const el = document.getElementById('detail_' + id);
            if (el) {{
                el.style.display = el.style.display === 'none' ? '' : 'none';
            }}
        }}
        </script>
        '''
        
        return render_page("Allocation Ledger", content, user, "ledger")
    
    
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
    
    logger.info("[ALLOC LOG] Ledger routes registered ✓")
