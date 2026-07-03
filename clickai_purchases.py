# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - PURCHASES & SUPPLIERS MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Suppliers (page, new, view, edit), Purchases (page, new, view, edit),
#           PO APIs (status, delete, email, receive, create-invoice),
#           Supplier Invoices page
# ==============================================================================

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def register_purchases_routes(app, db, login_required, Auth, render_page,
                              generate_id, money, safe, safe_string, now, today,
                              gl, create_journal_entry, log_allocation,
                              get_user_role, next_document_number,
                              smart_stock_code, format_extra_data,
                              has_reactor_hud, jarvis_hud_header, jarvis_techline,
                              RecordFactory, Email,
                              JARVIS_HUD_CSS, THEME_REACTOR_SKINS,
                              calc_all_supplier_balances=None, calc_supplier_balance=None,
                              build_linked_documents_panel=None):
    """Register all Supplier and Purchase routes with the Flask app."""

    # Import form helpers from clickai module level (defined in clickai.py)
    # These are needed by supplier_new and supplier_edit
    # Lazy import wrappers — avoids circular import with clickai.py
    def _supplier_form(v=None, is_edit=False):
        import clickai as _main
        return _main._supplier_form(v=v, is_edit=is_edit)

    def _get_form_fields(*args, **kwargs):
        import clickai as _main
        return _main._get_form_fields(*args, **kwargs)

    # ──────────────────────────────────────────────────────────────────────
    # SUPPLIER PAYMENT ALLOCATIONS — links a supplier payment to specific
    # supplier invoices. The supplier_payment_allocations table is the source
    # of truth for which of our payments covered which supplier invoice.
    # A supplier invoice's amount_paid / status are derived from it (cached).
    # ──────────────────────────────────────────────────────────────────────

    def get_supplier_invoice_allocations(biz_id, invoice_id):
        """All allocation rows posted against one supplier invoice."""
        if not biz_id or not invoice_id:
            return []
        try:
            return db.get("supplier_payment_allocations",
                          {"business_id": biz_id, "supplier_invoice_id": invoice_id}) or []
        except Exception as e:
            logger.warning(f"[SUP ALLOC] get_supplier_invoice_allocations failed: {e}")
            return []

    def supplier_invoice_allocated_total(biz_id, invoice_id):
        """Sum of all amounts allocated to one supplier invoice."""
        return round(sum(float(a.get("amount", 0) or 0)
                         for a in get_supplier_invoice_allocations(biz_id, invoice_id)), 2)

    def recalc_supplier_invoice_status(biz_id, invoice_id):
        """Recompute one supplier invoice's amount_paid + status from its
        allocations, then write the derived values back (cache).
        supplier_payment_allocations stays the source of truth — this can be
        re-run any time to repair a supplier invoice whose status has drifted.
        Returns {"allocated": x, "total": y, "status": "paid"/"unpaid"}.
        """
        inv = db.get_one("supplier_invoices", invoice_id)
        if not inv:
            return {"allocated": 0.0, "total": 0.0, "status": "unknown"}
        total = round(float(inv.get("total", 0) or 0), 2)
        allocated = supplier_invoice_allocated_total(biz_id, invoice_id)
        cur_status = (inv.get("status") or "").lower()
        # Never override a credited/cancelled invoice — those are final states.
        if cur_status in ("credited", "cancelled"):
            return {"allocated": allocated, "total": total, "status": cur_status}
        new_status = "paid" if allocated >= total and total > 0 else "unpaid"
        try:
            db.update("supplier_invoices", invoice_id,
                      {"amount_paid": allocated, "status": new_status}, biz_id)
        except Exception as e:
            logger.warning(f"[SUP ALLOC] recalc_supplier_invoice_status update failed: {e}")
        return {"allocated": allocated, "total": total, "status": new_status}

    # === SUPPLIERS ===

    @app.route("/suppliers")
    @login_required
    def suppliers_page():
        """Suppliers list - FAST direct query"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        role = get_user_role()
        can_see_balances = role in ["owner", "admin", "manager", "bookkeeper", "accountant"]
        
        # FAST: Direct query with order, limit
        try:
            suppliers = db.get("suppliers", {"business_id": biz_id}, limit=2000)
            # Sort by name
            suppliers = sorted(suppliers, key=lambda x: (x.get("name") or "").lower())
        except Exception as e:
            logger.error(f"[SUPPLIERS] Error loading: {e}")
            suppliers = []
        
        total_suppliers = len(suppliers)
        
        # Calculate all supplier balances from source documents (batch)
        _all_sup_balances = calc_all_supplier_balances(biz_id) if can_see_balances else {}
        
        creditors = [s for s in suppliers if _all_sup_balances.get(s.get("id"), 0) > 0]
        total_owed = sum(_all_sup_balances.get(s.get("id"), 0) for s in creditors) if can_see_balances else 0
        
        # Build rows - COMPACT VIEW (details on View page)
        suppliers_html = ""
        for s in suppliers:
            balance = _all_sup_balances.get(s.get("id"), 0) if can_see_balances else 0
            balance_color = "var(--orange)" if balance > 0 else "var(--green)" if balance < 0 else "var(--text-muted)"
            balance_display = money(balance) if can_see_balances else "---"
            sup_id = s.get("id")
            
            # Use cell as phone fallback
            phone = s.get("phone") or s.get("cell") or ""
            
            # Search data for JS filtering
            search_text = f"{s.get('code', '')} {s.get('name', '')} {s.get('contact_name', '')} {phone} {s.get('email', '')}".lower()
            
            suppliers_html += f'''
            <div class="supplier-row" data-search="{safe_string(search_text)}" data-balance="{balance}" style="background:var(--card);border-radius:6px;margin-bottom:4px;padding:10px 12px;cursor:pointer;" onclick="window.location='/supplier/{sup_id}'">
                <div style="display:grid;grid-template-columns:70px 1fr 150px 150px 100px;align-items:center;gap:10px;font-size:13px;">
                    <span style="color:var(--text-muted);font-family:monospace;font-size:11px;">{safe_string(s.get("code", ""))}</span>
                    <div>
                        <strong>{safe_string(s.get("name", "-"))}</strong>
                        <span style="color:var(--text-muted);font-size:11px;display:block;">{safe_string(s.get("contact_name", ""))}</span>
                    </div>
                    <span style="color:var(--text-muted);font-size:12px;">{safe_string(phone)}</span>
                    <span style="color:var(--primary);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{safe_string(s.get("email", ""))}">{safe_string(s.get("email", ""))}</span>
                    <span style="text-align:right;color:{balance_color};font-weight:bold;">{balance_display}</span>
                </div>
            </div>
            '''
        
        header_row = '''
        <div style="position:sticky;top:56px;z-index:100;margin-bottom:4px;padding:10px 12px;background:var(--card);border-radius:6px;">
            <div style="display:grid;grid-template-columns:70px 1fr 150px 150px 100px;align-items:center;gap:10px;font-size:12px;font-weight:bold;color:var(--text-muted);">
                <span>Code</span>
                <span>Supplier / Contact</span>
                <span>Phone</span>
                <span>Email</span>
                <span style="text-align:right;">We Owe</span>
            </div>
        </div>
        '''
        
        summary_html = ""
        if total_owed > 0 and can_see_balances:
            summary_html = f'''
            <div style="background: rgba(249,115,22,0.1); border: 1px solid rgba(249,115,22,0.3); padding:10px 15px; border-radius: 8px; margin-bottom: 15px;font-size:13px;">
                <strong>{len(creditors)} suppliers</strong> - we owe a total of <strong style="color: var(--orange);">{money(total_owed)}</strong>
            </div>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
            <h2 style="margin:0;">Suppliers (<span id="supplierCount">{total_suppliers}</span>)</h2>
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                <a href="/supplier-invoices" class="btn btn-secondary" style="font-size:12px;padding:6px 12px;">📋 Supplier Invoices</a>
                <a href="/supplier-credit-notes" class="btn btn-secondary" style="font-size:12px;padding:6px 12px;">↩️ Credit Notes</a>
                <a href="/supplier-return/new" class="btn btn-secondary" style="font-size:12px;padding:6px 12px;">↩️ Supplier Return</a>
                <a href="/supplier-statements/print" class="btn btn-secondary" style="font-size:12px;padding:6px 12px;">🖨️ Bulk Statements</a>
                <input type="text" id="supplierSearch" placeholder="🔍 Search name, code, phone..." 
                    oninput="filterSuppliers()" 
                    style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);width:250px;">
                <select id="balanceFilter" onchange="filterSuppliers()" style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    <option value="">All</option>
                    <option value="creditors">We Owe</option>
                    <option value="credit">In Credit</option>
                    <option value="zero">Zero Balance</option>
                </select>
                {('<button onclick="confirmDeleteAllSuppliers()" class="btn btn-secondary" style="background:rgba(239,68,68,0.12);color:var(--red);border:1px solid rgba(239,68,68,0.35);" title="Delete every supplier (owner/admin only)">🗑️ Delete All</button>') if role in ("owner", "admin") else ''}
                <a href="/supplier/new" class="btn btn-primary">+ Add Supplier</a>
            </div>
        </div>
        
        {summary_html}
        
        {header_row}
        <div id="suppliersList">
        {suppliers_html or '<div class="card" style="text-align:center;padding:40px;"><p style="color:var(--text-muted);margin-bottom:15px;"><strong>Tip:</strong> No suppliers yet!</p><div><a href="/import" class="btn btn-primary">Import from Excel</a> <a href="/supplier/new" class="btn btn-secondary" style="margin-left:10px;">Add manually</a></div></div>'}
        </div>
        
        <script>
        async function confirmDeleteAllSuppliers() {{
            const total = {total_suppliers};
            if (total === 0) {{
                alert('There are no suppliers to delete.');
                return;
            }}
            if (!confirm('⚠️ DELETE ALL SUPPLIERS\\n\\nThis will permanently delete all ' + total + ' suppliers from this business.\\n\\nSupplier invoices, purchase orders and financial records will NOT be deleted, but they will be orphaned (no linked supplier).\\n\\nContinue?')) return;
            
            const phrase = prompt('To confirm, type: DELETE ALL');
            if ((phrase || '').trim() !== 'DELETE ALL') {{
                alert('Confirmation phrase did not match. Nothing was deleted.');
                return;
            }}
            
            try {{
                const resp = await fetch('/api/suppliers/delete-all', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{confirm: 'DELETE ALL'}})
                }});
                const data = await resp.json();
                if (data.success) {{
                    alert('✅ Deleted ' + data.deleted + ' of ' + data.total + ' suppliers.' + (data.failed ? ('\\nFailed: ' + data.failed) : ''));
                    window.location.reload();
                }} else {{
                    alert('❌ ' + (data.error || 'Delete failed'));
                }}
            }} catch (e) {{
                alert('❌ Network error: ' + e.message);
            }}
        }}
        
        function filterSuppliers() {{
            const search = document.getElementById('supplierSearch').value.toLowerCase();
            const balanceFilter = document.getElementById('balanceFilter').value;
            const rows = document.querySelectorAll('.supplier-row');
            let visible = 0;
            
            rows.forEach(row => {{
                const searchText = row.dataset.search || '';
                const balance = parseFloat(row.dataset.balance) || 0;
                
                let show = true;
                
                // Text search
                if (search && !searchText.includes(search)) {{
                    show = false;
                }}
                
                // Balance filter
                if (balanceFilter === 'creditors' && balance <= 0) show = false;
                if (balanceFilter === 'credit' && balance >= 0) show = false;
                if (balanceFilter === 'zero' && balance !== 0) show = false;
                
                row.style.display = show ? '' : 'none';
                if (show) visible++;
            }});
            
            document.getElementById('supplierCount').textContent = visible;
        }}
        
        // Focus search on page load
        document.getElementById('supplierSearch')?.focus();
        </script>
        '''
        
        # -- JARVIS: Suppliers HUD header --
        if has_reactor_hud():
            _with_bal = len(creditors)
            _in_credit = len([s for s in suppliers if _all_sup_balances.get(s.get("id"), 0) < 0])
            _j_alert = ""
            if _with_bal > 5 and can_see_balances:
                _top3 = ", ".join([f"{safe(s.get('name','-')[:20])} ({money(_all_sup_balances.get(s.get('id'), 0))})" for s in sorted(creditors, key=lambda x: -_all_sup_balances.get(x.get('id'), 0))[:3]])
                _j_alert = f'<div class="j-ticker"><b>&#9888; CREDITORS</b><span class="jt-msg">{_with_bal} suppliers with balance &mdash; {_top3}</span><a href="/supplier-invoices" class="jt-act">VIEW INVOICES &rarr;</a></div>'
            
            _hud = jarvis_hud_header(
                page_name="SUPPLIERS",
                page_count=f"{total_suppliers} RECORDS LOADED",
                left_items=[
                    ("SUPPLIERS", str(total_suppliers), "c", "", ""),
                    ("WE OWE", money(total_owed) if can_see_balances else "---", "o", "o", "o"),
                    ("WITH BALANCE", str(_with_bal), "o", "", ""),
                    ("IN CREDIT", str(_in_credit), "g", "g", "g"),
                ],
                right_items=[
                    ("ACTIVE", str(total_suppliers - _in_credit - _with_bal), "g", "g", ""),
                    ("OWING", str(_with_bal), "r", "r", "r"),
                    ("NEW MTD", "0", "c", "", ""),
                    ("AVG DAYS", "24", "p", "", ""),
                ],
                reactor_size="page",
                alert_html=_j_alert
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline(f"SUPPLIERS <b>{total_suppliers} LOADED</b>")
        
        return render_page("Suppliers", content, user, "suppliers")
    
    
    @app.route("/supplier/new", methods=["GET", "POST"])
    @login_required
    def supplier_new():
        """Create new supplier - comprehensive form"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            code = request.form.get("code", "").strip()
            
            if not code and biz_id and name:
                try:
                    import re
                    name_clean = re.sub(r'[^a-zA-Z]', '', name).upper()
                    prefix = name_clean[:3] if len(name_clean) >= 3 else name_clean.ljust(3, 'X')
                    existing = db.get("suppliers", {"business_id": biz_id}, limit=5000)
                    max_num = 0
                    for s in existing:
                        ec = s.get("code", "")
                        if ec.upper().startswith(prefix):
                            nums = re.findall(r'\d+', ec)
                            if nums and int(nums[-1]) > max_num:
                                max_num = int(nums[-1])
                    code = f"{prefix}{(max_num + 1):03d}"
                    logger.info(f"[SUPPLIER] Smart code for '{name}': {code}")
                except Exception as e:
                    logger.error(f"[SUPPLIER] Smart code error: {e}")
                    code = f"S{generate_id()[:6].upper()}"
            
            if not name:
                flash("Supplier name is required", "error")
            else:
                fields = _get_form_fields()
                fields["address"] = fields.get("physical_address", "")
                try:
                    fields["discount_percentage"] = float(request.form.get("discount_percentage", 0) or 0)
                except:
                    fields["discount_percentage"] = 0
                try:
                    fields["credit_limit"] = float(request.form.get("credit_limit", 0) or 0)
                except:
                    fields["credit_limit"] = 0
                
                supplier = RecordFactory.supplier(
                    business_id=biz_id, name=name, code=code,
                    created_by=user.get("id", "") if user else "",
                    **fields
                )
                supplier_id = supplier["id"]
                
                success, err = db.save("suppliers", supplier)
                if success:
                    flash(f"Supplier '{name}' created", "success")
                    return redirect("/suppliers")
                else:
                    flash(f"Error creating supplier: {err}", "error")
        
        content = _supplier_form()
        return render_page("New Supplier", content, user, "suppliers")
    
    
    @app.route("/supplier/<supplier_id>")
    @login_required
    def supplier_view(supplier_id):
        """Supplier detail with full history"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Check user role - staff should not see balances
        role = get_user_role()
        can_see_balances = role in ["owner", "admin", "manager", "bookkeeper", "accountant"]
        
        supplier = db.get_one("suppliers", supplier_id)
        if not supplier:
            return redirect("/suppliers")
        
        # Get expenses/bills for this supplier (only if can see balances)
        # Match by supplier_id OR by supplier_name/supplier field for banking-created expenses
        all_expenses = db.get("expenses", {"business_id": biz_id}) if biz_id and can_see_balances else []
        _sup_name_upper = (supplier.get("name") or "").upper().strip()
        expenses = [e for e in all_expenses if
                    e.get("supplier_id") == supplier_id or
                    (not e.get("supplier_id") and _sup_name_upper and (
                        (e.get("supplier_name") or "").upper().strip() == _sup_name_upper or
                        (e.get("supplier") or "").upper().strip() == _sup_name_upper
                    ))]
        expenses = sorted(expenses, key=lambda x: x.get("date", ""), reverse=True)
        
        # Get supplier invoices (imported from Sage etc)
        all_supplier_invoices = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id and can_see_balances else []
        supplier_invoices = [si for si in all_supplier_invoices if si.get("supplier_id") == supplier_id]
        supplier_invoices = sorted(supplier_invoices, key=lambda x: x.get("date", ""), reverse=True)
        
        # Get payments to supplier (only if can see balances)
        # Match by supplier_id OR by supplier_name for unlinked banking payments
        all_payments = db.get("supplier_payments", {"business_id": biz_id}) if biz_id and can_see_balances else []
        payments = [p for p in all_payments if
                    p.get("supplier_id") == supplier_id or
                    (not p.get("supplier_id") and _sup_name_upper and (p.get("supplier_name") or "").upper().strip() == _sup_name_upper)]
        payments = sorted(payments, key=lambda x: x.get("date", ""), reverse=True)
        
        # Get purchase orders for this supplier
        try:
            all_pos = db.get("purchase_orders", {"business_id": biz_id}) if biz_id else []
            purchase_orders = [po for po in all_pos if po.get("supplier_id") == supplier_id]
            purchase_orders = sorted(purchase_orders, key=lambda x: x.get("date", ""), reverse=True)
        except Exception:
            purchase_orders = []
        
        # Get scanned documents for this supplier
        all_scanned_docs = db.get("scanned_documents", {"business_id": biz_id}) if biz_id else []
        scanned_docs = [d for d in all_scanned_docs if d.get("supplier_id") == supplier_id]
        scanned_docs = sorted(scanned_docs, key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Fetch GL accounts - try ALL sources: accounts, chart_of_accounts, then full defaults
        _gl_options = ""
        _gl_json = []
        
        # Source 1: ClickAI accounts table (code, name)
        _src_accounts = db.get("accounts", {"business_id": biz_id}) if biz_id else []
        if _src_accounts:
            for acc in sorted(_src_accounts, key=lambda x: x.get("code", "")):
                _code = acc.get("code", "")
                _name = acc.get("name", "")
                if _code and _name:
                    _gl_json.append({"code": _code, "name": _name})
        
        # Source 2: Sage chart_of_accounts (account_code, account_name) - merge if new codes
        _src_coa = db.get("chart_of_accounts", {"business_id": biz_id}) if biz_id else []
        if _src_coa:
            _existing_codes = {a["code"] for a in _gl_json}
            for acc in sorted(_src_coa, key=lambda x: x.get("account_code", "")):
                _code = acc.get("account_code", "")
                _name = acc.get("account_name", "")
                if _code and _name and _code not in _existing_codes:
                    _gl_json.append({"code": _code, "name": _name})
                    _existing_codes.add(_code)
        
        # Source 3: Full DEFAULT_ACCOUNTS if nothing found
        if not _gl_json:
            for _da in [
                ("1000", "Bank"), ("1050", "Cash On Hand"), ("1100", "Petty Cash"),
                ("1200", "Debtors Control"), ("1300", "Stock"), ("1400", "VAT Input"),
                ("1500", "Equipment"), ("1600", "Vehicles"), ("1700", "Accumulated Depreciation"),
                ("2000", "Creditors Control"), ("2100", "VAT Output"),
                ("2200", "PAYE Payable"), ("2300", "UIF Payable"), ("2400", "Loan Account"),
                ("3000", "Capital"), ("3100", "Retained Earnings"), ("3200", "Drawings"),
                ("4000", "Sales"), ("4100", "Services Income"),
                ("4200", "Interest Received"), ("4300", "Discount Received"),
                ("5000", "Cost of Sales"), ("5100", "Purchases"), ("5200", "Carriage Inwards"),
                ("6000", "Salaries & Wages"), ("6100", "Rent"), ("6200", "Electricity"),
                ("6300", "Telephone"), ("6400", "Insurance"), ("6500", "Fuel"),
                ("6600", "Repairs & Maintenance"), ("6700", "Bank Charges"),
                ("6800", "Advertising"), ("6900", "Depreciation"),
                ("7000", "General Expenses"), ("7050", "Cash Over/Short"),
            ]:
                _gl_json.append({"code": _da[0], "name": _da[1]})
        
        # Sort and build HTML options
        _gl_json = sorted(_gl_json, key=lambda x: x["code"])
        for _ga in _gl_json:
            _sel = ' selected' if _ga["code"] in ("7000", "7000/000") else ''
            _gl_options += f'<option value="{_ga["code"]}"{_sel}>{_ga["code"]} — {_ga["name"]}</option>\n'
        
        _gl_json_str = json.dumps(_gl_json)
        
        # Calculate balance from source documents
        # (supplier_invoices - payments - active supplier credit notes)
        # A payment settles cash + any settlement discount taken
        _si_total = sum(float(si.get("total", 0)) for si in supplier_invoices if si.get("status") != "cancelled")
        _pay_total = sum(float(p.get("amount", 0)) + float(p.get("discount_total", 0) or 0) for p in payments)
        # Active supplier credit notes reduce what we owe
        _scn_total = 0.0
        if can_see_balances:
            try:
                _bal_cns = db.get("supplier_credit_notes", {"business_id": biz_id}) if biz_id else []
                _scn_total = sum(float(_c.get("total", 0) or 0) for _c in _bal_cns
                                 if _c.get("supplier_id") == supplier_id
                                 and (_c.get("status") or "active") == "active")
            except Exception:
                _scn_total = 0.0
        balance = round(_si_total - _pay_total - _scn_total, 2) if can_see_balances else 0
        
        # ── Open supplier invoices for the Record Payment allocation list ──
        # Open = not paid/credited/cancelled and still has an outstanding amount
        # (total minus what is already allocated to it).
        _open_sinvoices = []
        _sup_disc_pct = round(float(supplier.get("discount_percentage", 0) or 0), 2)
        if can_see_balances:
            for _si in supplier_invoices:
                _sist = (_si.get("status") or "").lower()
                if _sist in ("paid", "credited", "cancelled"):
                    continue
                _si_tot = round(float(_si.get("total", 0) or 0), 2)
                if _si_tot <= 0:
                    continue
                _si_already = supplier_invoice_allocated_total(biz_id, _si.get("id", ""))
                _si_outstanding = round(_si_tot - _si_already, 2)
                if _si_outstanding <= 0:
                    continue
                _si_cap_disc = round(float(_si.get("discount_amount", 0) or 0), 2)
                _si_settle_disc = round(_si_outstanding * _sup_disc_pct / 100, 2) if (_sup_disc_pct > 0 and _si_cap_disc == 0) else 0.0
                _open_sinvoices.append({
                    "id": _si.get("id", ""),
                    "number": _si.get("invoice_number", "-"),
                    "date": _si.get("date", "-"),
                    "outstanding": _si_outstanding,
                    "discount": _si_settle_disc,
                    "net_to_pay": round(_si_outstanding - _si_settle_disc, 2)
                })
            _open_sinvoices.sort(key=lambda x: x["date"])
        
        _sp_alloc_rows_html = ""
        for _osi in _open_sinvoices:
            if _osi.get("discount", 0) > 0:
                _disc_line = (f'<div style="color:var(--green);font-size:11px;margin-top:3px;">'
                              f'<label style="cursor:pointer;"><input type="checkbox" class="spDiscChk" data-invid="{_osi["id"]}" '
                              f'onchange="spToggleDisc(this)" checked style="vertical-align:middle;margin-right:4px;">'
                              f'Take {_sup_disc_pct:g}% discount (-{money(_osi["discount"])}) &rarr; pay {money(_osi["net_to_pay"])}</label></div>')
                _prefill = f'{_osi["net_to_pay"]:.2f}'
            else:
                _disc_line = ""
                _prefill = ""
            _sp_alloc_rows_html += f'''
            <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);">
                <div style="flex:1;font-size:13px;">
                    <strong>{safe_string(_osi["number"])}</strong>
                    <span style="color:var(--text-muted);"> · {_osi["date"]}</span><br>
                    <span style="color:var(--text-muted);font-size:12px;">Outstanding: {money(_osi["outstanding"])}</span>
                    {_disc_line}
                </div>
                <input type="number" class="spAllocAmt" data-invid="{_osi["id"]}" data-outstanding="{_osi["outstanding"]}"
                       data-disc="{_osi["discount"]}" data-nettopay="{_osi["net_to_pay"]}" value="{_prefill}"
                       placeholder="0.00" step="0.01" min="0" max="{_osi["outstanding"]}"
                       style="width:110px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);text-align:right;">
            </div>
            '''
        if not _sp_alloc_rows_html:
            _sp_alloc_rows_html = '<p style="color:var(--text-muted);font-size:13px;padding:8px 0;">No open invoices — this payment will go on account.</p>'
        
        # Stats - only if can see balances
        total_billed = sum(float(e.get("total", e.get("amount", 0))) for e in expenses) if can_see_balances else 0
        total_paid = sum(float(p.get("amount", 0)) for p in payments) if can_see_balances else 0
        
        # YTD Stats - spending at this supplier
        import datetime
        now_dt = datetime.datetime.now()
        # SA financial year: March to February
        if now_dt.month >= 3:
            fy_year = now_dt.year
            ytd_start = f"{now_dt.year}-03-01"
        else:
            fy_year = now_dt.year - 1
            ytd_start = f"{now_dt.year - 1}-03-01"
        fy_label = f"Mar {fy_year} - Feb {fy_year + 1}"
        
        # Combine expenses + supplier_invoices for full picture
        ytd_expenses = [e for e in expenses if (e.get("date") or "") >= ytd_start]
        ytd_exp_total = sum(float(e.get("total", e.get("amount", 0))) for e in ytd_expenses)
        ytd_si = [si for si in supplier_invoices if (si.get("date") or "") >= ytd_start]
        ytd_si_total = sum(float(si.get("total", 0)) for si in ytd_si)
        ytd_spend = ytd_exp_total + ytd_si_total
        
        # Previous financial year comparison
        prev_fy_start = f"{fy_year - 1}-03-01"
        prev_fy_end = f"{fy_year}-02-28"
        prev_expenses = [e for e in expenses if prev_fy_start <= (e.get("date") or "") <= prev_fy_end]
        prev_exp_total = sum(float(e.get("total", e.get("amount", 0))) for e in prev_expenses)
        prev_si = [si for si in supplier_invoices if prev_fy_start <= (si.get("date") or "") <= prev_fy_end]
        prev_spend = prev_exp_total + sum(float(si.get("total", 0)) for si in prev_si)
        
        ytd_growth = ""
        if prev_spend > 0 and can_see_balances:
            pct = ((ytd_spend - prev_spend) / prev_spend) * 100
            if pct > 0:
                ytd_growth = f'<span style="color:var(--red);font-size:12px;">▲ {pct:.0f}% vs prev FY</span>'
            elif pct < 0:
                ytd_growth = f'<span style="color:var(--green);font-size:12px;">▼ {abs(pct):.0f}% vs prev FY</span>'
        
        expenses_html = ""
        if can_see_balances:
            for e in expenses[:200]:
                status = e.get("status", "outstanding")
                status_color = "var(--green)" if status == "paid" else "var(--orange)"
                expenses_html += f'''
                <tr style="cursor:pointer;" onclick="window.location='/expense/{e.get("id")}'">
                    <td>{e.get("invoice_number", e.get("reference", "-"))}</td>
                    <td>{e.get("date", "-")}</td>
                    <td>{safe_string(e.get("description", "-"))[:40]}</td>
                    <td>{money(e.get("total", e.get("amount", 0)))}</td>
                    <td style="color:{status_color};">{status.upper()}</td>
                </tr>
                '''
        
        supplier_inv_html = ""
        if can_see_balances:
            for si in supplier_invoices[:200]:
                si_status = si.get("status", "outstanding")
                si_color = "var(--green)" if si_status == "paid" else "var(--orange)"
                _si_paid_via = ""
                if si_status == "paid" and si.get("paid_date"):
                    _si_method = "Banking" if si.get("paid_via") == "banking_recon" else (si.get("paid_via") or "")
                    _si_paid_via = f' <span style="font-size:10px;color:var(--text-muted);">({si.get("paid_date", "")[:10]}{" - " + _si_method if _si_method else ""})</span>'
                supplier_inv_html += f'''
                <tr style="cursor:pointer;" onclick="window.location='/supplier-invoice/{si.get("id")}'">
                    <td>{safe_string(si.get("invoice_number", "-"))}</td>
                    <td>{si.get("date", "-")}</td>
                    <td>{si.get("due_date", "-")}</td>
                    <td>{money(si.get("total", 0))}</td>
                    <td style="color:{si_color};">{si_status.upper()}{_si_paid_via}</td>
                </tr>
                '''
        
        payments_html = ""
        if can_see_balances:
            for p in payments[:200]:
                _p_ref = p.get("reference", "-")
                _p_source = p.get("source", "")
                _p_source_html = ""
                if _p_source == "banking_recon":
                    _p_ledger_link = f'/ledger?q={_p_ref}' if _p_ref and _p_ref != "-" else '/ledger'
                    _p_source_html = f'<a href="{_p_ledger_link}" style="color:var(--primary);text-decoration:none;font-size:12px;">Banking</a>'
                elif _p_source:
                    _p_source_html = f'<span style="font-size:12px;color:var(--text-muted);">{safe_string(_p_source[:20])}</span>'
                else:
                    _p_source_html = '<span style="font-size:12px;color:var(--text-muted);">Manual</span>'
                
                _p_id = p.get("id", "")
                _p_amt_str = money(p.get("amount", 0))
                _p_reverse = (
                    f' &middot; <form method="POST" action="/supplier/{supplier_id}/reverse-payment/{_p_id}" '
                    f'style="display:inline;" onsubmit="return confirm(\'Reverse this payment of {_p_amt_str}? '
                    f'This removes the payment and posts an opposite journal. Use it only for a payment captured twice.\');">'
                    f'<button type="submit" style="padding:1px 7px;font-size:10px;background:var(--red);color:#fff;border:none;border-radius:4px;cursor:pointer;">Reverse</button></form>'
                ) if _p_id else ""
                payments_html += f'''
                <tr>
                    <td>{_p_ref}</td>
                    <td>{p.get("date", "-")}</td>
                    <td style="color:var(--green);">{money(p.get("amount", 0))}</td>
                    <td>{p.get("method", "-")}</td>
                    <td>{_p_source_html}</td>
                    <td><a href="/supplier-payment/{p.get("id", "")}/remittance" style="color:var(--primary);text-decoration:none;font-size:12px;">View</a>{_p_reverse}</td>
                </tr>
                '''
        
        # Build scanned documents HTML - hide amounts for staff
        scanned_docs_html = ""
        
        # Build Account Statement / Ledger for supplier
        _sup_ledger_items = []
        if can_see_balances:
            for si in supplier_invoices:
                if si.get("status") != "cancelled":
                    _sup_ledger_items.append({
                        "date": si.get("date", ""),
                        "type": "Invoice",
                        "reference": si.get("invoice_number", "-"),
                        "debit": 0,
                        "credit": float(si.get("total", 0)),
                        "link": f"/supplier-invoice/{si.get('id', '')}"
                    })
            for p in payments:
                _sup_ledger_items.append({
                    "date": p.get("date", ""),
                    "type": "Payment",
                    "reference": p.get("reference", "-"),
                    "debit": float(p.get("amount", 0)),
                    "credit": 0,
                    "link": "",
                    "source": p.get("source", "")
                })
                # Settlement discount taken with this payment — its own debit line
                _p_disc = float(p.get("discount_total", 0) or 0)
                if _p_disc > 0.005:
                    _sup_ledger_items.append({
                        "date": p.get("date", ""),
                        "type": "Settlement Discount",
                        "reference": p.get("reference", "-"),
                        "debit": _p_disc,
                        "credit": 0,
                        "link": "",
                        "source": p.get("source", "")
                    })
            # Include supplier credit notes (they reduce what we owe — show as debits)
            try:
                _sup_cns = db.get("supplier_credit_notes", {"business_id": biz_id}) if biz_id else []
                for _cn in _sup_cns:
                    if _cn.get("supplier_id") == supplier_id and (_cn.get("status") or "active") == "active":
                        # ── Extract extra info from the reason field (META JSON tail) ──
                        # Scanned credit notes pack the supplier's own CN number and the
                        # target invoice number into the 'reason' field as:
                        #   "human description | META:{...json...}"
                        # We pull those out here so we can show them on the statement
                        # alongside our internal SCR-xxxx reference.
                        _cn_reason = _cn.get("reason", "") or ""
                        _supplier_cn_num = ""
                        _vs_invoice_num = ""
                        try:
                            if "| META:" in _cn_reason:
                                _meta_str = _cn_reason.split("| META:", 1)[1].strip()
                                _meta_obj = json.loads(_meta_str)
                                _supplier_cn_num = (_meta_obj.get("supplier_cn_number") or "").strip()
                                _vs_invoice_num = (_meta_obj.get("original_invoice_number") or "").strip()
                        except Exception:
                            pass
                        # Fallback: if META wasn't there (e.g. legacy CN from old endpoint),
                        # try to look up the original invoice number from original_invoice_id
                        if not _vs_invoice_num and _cn.get("original_invoice_id"):
                            try:
                                _orig_inv = db.get_one("supplier_invoices", _cn.get("original_invoice_id"))
                                if _orig_inv:
                                    _vs_invoice_num = _orig_inv.get("invoice_number", "") or ""
                            except Exception:
                                pass
                        # Build a richer reference label: SCR-xxxx + supplier's own number
                        # + vs invoice — all on one line, with the SCR being the clickable link.
                        _cn_extras_bits = []
                        if _supplier_cn_num:
                            _cn_extras_bits.append(f"Ref: {safe_string(_supplier_cn_num)}")
                        if _vs_invoice_num:
                            _cn_extras_bits.append(f"vs {safe_string(_vs_invoice_num)}")
                        _cn_extras_html = ""
                        if _cn_extras_bits:
                            _cn_extras_html = f' <span style="font-size:11px;color:var(--text-muted);">· {" · ".join(_cn_extras_bits)}</span>'
                        _sup_ledger_items.append({
                            "date": _cn.get("date", ""),
                            "type": "Credit Note",
                            "reference": _cn.get("cn_number", "-"),
                            "reference_extras_html": _cn_extras_html,
                            "debit": float(_cn.get("total", 0) or 0),
                            "credit": 0,
                            "link": f"/supplier-credit-note/{_cn.get('id','')}"
                        })
            except Exception:
                pass
        _sup_ledger_items.sort(key=lambda x: x.get("date", ""))
        _sup_running = 0
        _sup_ledger_html = ""
        for _sli in _sup_ledger_items:
            _sup_running += _sli["credit"] - _sli["debit"]  # credit = we owe more, debit = we paid
            _sref = f'<a href="{_sli["link"]}" style="color:var(--primary);text-decoration:none;">{safe_string(_sli["reference"])}</a>' if _sli.get("link") else safe_string(_sli["reference"])
            _sref += _sli.get("reference_extras_html", "")  # extras for credit notes (supplier CN number + vs invoice)
            _ssrc = f' <span style="font-size:10px;color:var(--text-muted);">({_sli.get("source","")})</span>' if _sli.get("source") else ""
            _sbal_color = "color:var(--orange);" if _sup_running > 0.01 else "color:var(--green);" if _sup_running < -0.01 else ""
            _sup_ledger_html += f'''<tr>
                <td style="font-size:12px;">{_sli["date"]}</td>
                <td style="font-size:12px;">{_sli["type"]}{_ssrc}</td>
                <td style="font-size:12px;">{_sref}</td>
                <td style="text-align:right;font-size:12px;">{money(_sli["debit"]) if _sli["debit"] else "-"}</td>
                <td style="text-align:right;font-size:12px;color:var(--orange);">{money(_sli["credit"]) if _sli["credit"] else "-"}</td>
                <td style="text-align:right;font-size:12px;font-weight:bold;{_sbal_color}">{money(_sup_running)}</td>
            </tr>'''
        for doc in scanned_docs[:20]:
            doc_date = doc.get("date", doc.get("created_at", "")[:10] if doc.get("created_at") else "-")
            amount_display = money(doc.get("amount", 0)) if can_see_balances else "---"
            scanned_docs_html += f'''
            <div style="background:var(--bg);border-radius:8px;padding:12px;cursor:pointer;border:1px solid var(--border);" 
                 onclick="viewScannedDoc('{doc.get("id")}')">
                <div style="font-size:24px;text-align:center;margin-bottom:8px;">📄</div>
                <div style="font-weight:600;font-size:13px;text-align:center;margin-bottom:4px;">{safe_string(doc.get("reference", "Document"))}</div>
                <div style="font-size:11px;color:var(--text-muted);text-align:center;">{doc_date}</div>
                <div style="font-size:12px;color:var(--primary);text-align:center;margin-top:4px;">{amount_display}</div>
            </div>
            '''
        
        # Balance display - hidden for staff
        balance_display = money(balance) if can_see_balances else "---"
        balance_section = f'''
                <div style="text-align:right;">
                    <p style="color:var(--text-muted);margin:0;font-size:12px;">WE OWE</p>
                    <p style="font-size:28px;font-weight:bold;margin:0;color:{"var(--orange)" if balance > 0 else "var(--green)"};">
                        {balance_display}
                    </p>
                </div>
        ''' if can_see_balances else ''
        
        # Stats section - hidden for staff
        stats_section = f'''
        <div class="stats-grid">
            <div class="stat-card" style="border:2px solid var(--orange);background:rgba(249,115,22,0.08);">
                <div class="stat-value" style="color:var(--orange);">{money(ytd_spend)}</div>
                <div class="stat-label">YTD Spend</div>
                <div style="font-size:10px;color:var(--text-muted);">{fy_label}</div>
                {ytd_growth}
            </div>
            <div class="stat-card">
                <div class="stat-value">{money(total_billed)}</div>
                <div class="stat-label">Total Billed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:var(--green);">{money(total_paid)}</div>
                <div class="stat-label">Total Paid</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(expenses)}</div>
        ''' if can_see_balances else f'''
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{len(scanned_docs)}</div>
        '''
        
        # Build payment button separately (can't have backslashes in f-string)
        supplier_name_escaped = safe_string(supplier.get("name", "")).replace("'", "")
        payment_button = f'''<button class="btn btn-primary" onclick="document.getElementById('paymentModal').style.display='flex'">💰 Record Payment</button>''' if can_see_balances else ""
        
        # Build purchase orders HTML separately (avoids nested f-string issues)
        po_html = ""
        for po in purchase_orders[:200]:
            po_status = po.get("status", "draft")
            po_color = "var(--green)" if po_status == "received" else "var(--orange)"
            po_html += f'''
            <tr style="cursor:pointer;" onclick="window.location='/purchase/{po.get("id")}'">
                <td>{po.get("po_number", "-")}</td>
                <td>{po.get("date", "-")}</td>
                <td>{money(po.get("total", 0))}</td>
                <td style="color:{po_color};">{po_status.upper()}</td>
            </tr>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/suppliers" style="color:var(--text-muted);">← Back to Suppliers</a>
            <div style="display:flex;gap:10px;">
                <a href="/supplier/{supplier_id}/edit" class="btn btn-secondary">✏️ Edit</a>
                <a href="/purchase/new?supplier_id={supplier_id}" class="btn btn-secondary">New PO</a>
                <a href="/ledger?q={safe_string(supplier.get('name', ''))}" class="btn btn-secondary" style="font-size:12px;">GL Trail</a>
                <a href="/supplier-statement/{supplier_id}/print" class="btn btn-secondary">Statement</a>
                <a href="/supplier-return/new?supplier_id={supplier_id}&mode=discount" class="btn btn-secondary">↩️ Discount Credit</a>
                <button class="btn btn-primary" onclick="openCaptureInvoice()">📄 Capture Invoice</button>
                {payment_button}
            </div>
        </div>
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div style="flex:1;">
                    <h2 style="margin:0;">{safe_string(supplier.get("name", "-"))}</h2>
                    <p style="color:var(--text-muted);margin:5px 0;font-family:monospace;font-size:12px;">
                        Code: {safe_string(supplier.get("code", "-"))}
                    </p>
                </div>
                {balance_section}
            </div>
            
            <!-- Contact Details Grid -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;margin-top:20px;padding-top:15px;border-top:1px solid var(--border);">
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">CONTACT PERSON</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("contact_name", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">PHONE</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("phone", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">CELL</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("cell", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">EMAIL</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("email", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">FAX</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("fax", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">WEBSITE</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("website", "-"))}</span>
                </div>
            </div>
            
            <!-- Address -->
            <div style="margin-top:15px;padding-top:15px;border-top:1px solid var(--border);">
                <span style="color:var(--text-muted);font-size:11px;display:block;">ADDRESS</span>
                <span style="font-size:14px;">{safe_string(supplier.get("address", "-"))}</span>
            </div>
            
            <!-- Financial Details Grid -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-top:15px;padding-top:15px;border-top:1px solid var(--border);">
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">VAT NUMBER</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("vat_number", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">CREDIT LIMIT</span>
                    <span style="font-size:14px;">{money(supplier.get("credit_limit", 0)) if can_see_balances else "---"}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">DISCOUNT %</span>
                    <span style="font-size:14px;">{supplier.get("discount_percentage", 0) or 0}%</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">PAYMENT TERMS</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("payment_terms", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">CATEGORY</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("category", "-"))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">VAT TYPE</span>
                    <span style="font-size:14px;">{safe_string(supplier.get("vat_type", "-"))}</span>
                </div>
            </div>
            
            <!-- Notes -->
            {"<div style='margin-top:15px;padding-top:15px;border-top:1px solid var(--border);'><span style='color:var(--text-muted);font-size:11px;display:block;'>NOTES</span><p style='font-size:14px;margin:5px 0;background:var(--bg);padding:10px;border-radius:6px;'>" + safe_string(supplier.get("notes")) + "</p></div>" if supplier.get("notes") else ""}
            
            <!-- Extra Data (Sage User Fields) -->
            {"<div style='margin-top:15px;padding-top:15px;border-top:1px solid var(--border);'><span style='color:var(--text-muted);font-size:11px;display:block;margin-bottom:10px;'>ADDITIONAL INFO</span>" + format_extra_data(supplier.get("extra_data")) + "</div>" if supplier.get("extra_data") else ""}
        </div>
        
        {stats_section}
                <div class="stat-label">Bills/Expenses</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(payments)}</div>
                <div class="stat-label">Payments Made</div>
            </div>
        </div>
        
        {'<div class="card" style="margin-top:20px;">' + """
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 style="margin:0;">Account Statement</h3>
                <span style="font-size:12px;color:var(--text-muted);">""" + f'{len(_sup_ledger_items)} transactions' + """</span>
            </div>
            <div style="overflow-x:auto;">
            <table class="table" id="supLedgerTable">
                <thead>
                    <tr><th>Date</th><th>Type</th><th>Reference</th><th style="text-align:right;">Paid (DR)</th><th style="text-align:right;">Owed (CR)</th><th style="text-align:right;">Balance</th></tr>
                </thead>
                <tbody>
                    """ + (_sup_ledger_html or "<tr><td colspan='6' style='text-align:center;color:var(--text-muted);'>No transactions yet</td></tr>") + """
                </tbody>
            </table>
            </div>
        </div>""" if can_see_balances else ''}
        
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                    <h3 style="margin:0;">Recent Bills/Expenses ({len(expenses)})</h3>
                    <input type="text" placeholder="🔍 Search..." oninput="filterTable(this, 'expensesTable')" style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);width:180px;font-size:12px;">
                </div>
                <table class="table" id="expensesTable">
                    <thead>
                        <tr><th>Reference</th><th>Date</th><th>Description</th><th>Amount</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        {expenses_html or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted);'>No expenses yet</td></tr>"}
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                    <h3 style="margin:0;">Payments Made ({len(payments)})</h3>
                    <input type="text" placeholder="🔍 Search..." oninput="filterTable(this, 'paymentsTable')" style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);width:180px;font-size:12px;">
                </div>
                <table class="table" id="paymentsTable">
                    <thead>
                        <tr><th>Reference</th><th>Date</th><th>Amount</th><th>Method</th><th>Source</th><th>Remittance</th></tr>
                    </thead>
                    <tbody>
                        {payments_html or "<tr><td colspan='6' style='text-align:center;color:var(--text-muted);'>No payments yet</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        ''' + (f'''
        <div class="card" style="margin-top:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 style="margin:0;">Invoices ({len(supplier_invoices)})</h3>
                <input type="text" placeholder="🔍 Search invoices..." oninput="filterTable(this, 'supplierInvTable')" style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);width:200px;font-size:12px;">
            </div>
            <table class="table" id="supplierInvTable">
                <thead>
                    <tr><th>Invoice #</th><th>Date</th><th>Due Date</th><th>Amount</th><th>Status</th></tr>
                </thead>
                <tbody>
                    {supplier_inv_html or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted);'>No invoices</td></tr>"}
                </tbody>
            </table>
        </div>
        ''' if can_see_balances else '') + f'''
        </div>
        
        <!-- Purchase Orders Section -->
        <div class="card" style="margin-top:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 style="margin:0;">📋 Purchase Orders ({len(purchase_orders)})</h3>
                <input type="text" placeholder="🔍 Search POs..." oninput="filterTable(this, 'poTable')" style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);width:180px;font-size:12px;">
            </div>
            <table class="table" id="poTable">
                <thead>
                    <tr><th>PO Number</th><th>Date</th><th>Total</th><th>Status</th></tr>
                </thead>
                <tbody>
                    {po_html if po_html else "<tr><td colspan='4' style='text-align:center;color:var(--text-muted)'>No purchase orders</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <!-- Scanned Documents Section -->
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">Scanned Documents ({len(scanned_docs)})</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:15px;">
                {scanned_docs_html if scanned_docs else '<p style="color:var(--text-muted);text-align:center;">No scanned documents yet</p>'}
            </div>
        </div>
        
        <!-- Modal for viewing scanned document -->
        <div id="scanModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:1000;align-items:center;justify-content:center;">
            <div style="background:var(--card);border-radius:12px;max-width:90%;max-height:90%;overflow:auto;position:relative;">
                <button onclick="closeScanModal()" style="position:absolute;top:10px;right:10px;background:var(--red);color:white;border:none;border-radius:50%;width:30px;height:30px;cursor:pointer;font-size:18px;">×</button>
                <div id="scanModalContent" style="padding:20px;text-align:center;">
                    <p>Loading...</p>
                </div>
            </div>
        </div>
        
        <script>
        // Search/filter any table by text
        function filterTable(input, tableId) {{
            const q = input.value.toLowerCase().trim();
            const table = document.getElementById(tableId);
            if (!table) return;
            const rows = table.querySelectorAll('tbody tr');
            let visible = 0;
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                const match = !q || q.split(/\s+/).every(term => text.includes(term));
                row.style.display = match ? '' : 'none';
                if (match) visible++;
            }});
        }}
        
        // Auto-collapse tables with more than 50 rows
        document.addEventListener('DOMContentLoaded', function() {{
            document.querySelectorAll('.card table.table tbody').forEach(function(tbody) {{
                var rows = tbody.querySelectorAll('tr');
                if (rows.length > 50) {{
                    for (var i = 50; i < rows.length; i++) {{
                        rows[i].style.display = 'none';
                        rows[i].classList.add('extra-row');
                    }}
                    var table = tbody.closest('table');
                    var btn = document.createElement('div');
                    btn.style.cssText = 'text-align:center;padding:10px;cursor:pointer;color:var(--primary);font-size:13px;font-weight:600;border-top:1px solid var(--border);margin-top:-1px;';
                    btn.innerHTML = '▼ Show all ' + rows.length + ' records';
                    btn.onclick = function() {{
                        var extra = tbody.querySelectorAll('.extra-row');
                        var hidden = extra[0].style.display === 'none';
                        extra.forEach(function(r) {{ r.style.display = hidden ? '' : 'none'; }});
                        btn.innerHTML = hidden ? '▲ Show first 50' : '▼ Show all ' + rows.length + ' records';
                    }};
                    table.parentNode.insertBefore(btn, table.nextSibling);
                }}
            }});
        }});
        async function viewScannedDoc(docId) {{
            document.getElementById('scanModal').style.display = 'flex';
            document.getElementById('scanModalContent').innerHTML = '<p>Loading document...</p>';
            
            try {{
                const response = await fetch('/api/scanned-document/' + docId);
                const data = await response.json();
                
                if (data.success && data.image_data) {{
                    document.getElementById('scanModalContent').innerHTML = `
                        <img src="data:image/jpeg;base64,${{data.image_data}}" style="max-width:100%;max-height:80vh;" />
                        <div style="margin-top:15px;">
                            <p><strong>${{data.reference || 'Document'}}</strong></p>
                            <p style="color:var(--text-muted);">${{data.date || ''}}</p>
                        </div>
                    `;
                }} else {{
                    document.getElementById('scanModalContent').innerHTML = '<p style="color:var(--red);">Document image not available</p>';
                }}
            }} catch(e) {{
                document.getElementById('scanModalContent').innerHTML = '<p style="color:var(--red);">Error loading document</p>';
            }}
        }}
        
        function closeScanModal() {{
            document.getElementById('scanModal').style.display = 'none';
        }}
        
        document.getElementById('scanModal').addEventListener('click', function(e) {{
            if (e.target === this) closeScanModal();
        }});
        </script>
        
        <!-- Capture Supplier Invoice Modal -->
        <div id="captureInvoiceModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:var(--card);border-radius:12px;padding:30px;width:90%;max-width:550px;max-height:90vh;overflow-y:auto;border:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                    <h2 style="margin:0;">📄 Capture Invoice</h2>
                    <button onclick="closeCaptureInvoice()" style="background:none;border:none;color:var(--text-muted);font-size:24px;cursor:pointer;">&times;</button>
                </div>
                <p style="color:var(--text-muted);margin-bottom:20px;font-size:13px;">For expenses like diesel, stationery, etc. — no stock codes needed.</p>
                
                <div style="display:flex;flex-direction:column;gap:14px;">
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Invoice Number</label>
                        <input type="text" id="capInvNumber" placeholder="e.g. INV-2024-001" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Date</label>
                        <input type="date" id="capInvDate" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Description</label>
                        <input type="text" id="capInvDesc" placeholder="e.g. Diesel for bakkie, Stationery" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">GL Account (Expense Type)</label>
                        <div style="display:flex;gap:6px;">
                            <input type="text" id="capInvGLSearch" placeholder="Type to filter accounts..." oninput="filterGLDropdown(this.value)" style="flex:1;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:13px;">
                            <button type="button" onclick="zaneGLSuggest()" id="zaneSuggestBtn" style="padding:8px 12px;background:var(--primary);color:white;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;white-space:nowrap;">🤖 Suggest</button>
                        </div>
                        <select id="capInvGL" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);margin-top:4px;font-size:13px;">
                            {_gl_options}
                        </select>
                        <div id="zaneSuggestMsg" style="display:none;margin-top:4px;padding:6px 10px;border-radius:6px;font-size:12px;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);"></div>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Amount (VAT Inclusive)</label>
                        <input type="number" id="capInvAmount" placeholder="0.00" step="0.01" min="0.01" oninput="updateCapInvDiscount()" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:18px;font-weight:700;">
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <input type="checkbox" id="capInvVat" checked onchange="updateCapInvDiscount()">
                        <label for="capInvVat" style="font-size:13px;">VAT Inclusive (15%)</label>
                    </div>
                    <div id="capInvDiscountBox" style="display:none;padding:10px 12px;border-radius:6px;background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.3);font-size:13px;">
                        <div style="display:flex;justify-content:space-between;"><span>Net (excl VAT)</span><span id="capInvNet">R0.00</span></div>
                        <div style="display:flex;justify-content:space-between;color:var(--green);font-weight:600;"><span id="capInvDiscLabel">Discount Received</span><span id="capInvDiscAmt">-R0.00</span></div>
                        <div style="display:flex;justify-content:space-between;"><span>VAT (15%)</span><span id="capInvVatAmt">R0.00</span></div>
                        <div style="display:flex;justify-content:space-between;font-weight:700;border-top:1px solid rgba(34,197,94,0.3);margin-top:4px;padding-top:4px;"><span>Invoice Total</span><span id="capInvTotal">R0.00</span></div>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <input type="checkbox" id="capInvPaid">
                        <label for="capInvPaid" style="font-size:13px;">Already Paid</label>
                    </div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:20px;">
                    <button onclick="submitCaptureInvoice()" id="capInvBtn" style="flex:1;padding:12px;background:var(--primary);color:white;border:none;border-radius:8px;cursor:pointer;font-weight:700;font-size:15px;">Save Invoice</button>
                    <button onclick="closeCaptureInvoice()" style="padding:12px 20px;background:var(--card);color:var(--text-muted);border:1px solid var(--border);border-radius:8px;cursor:pointer;">Cancel</button>
                </div>
                <div id="capInvMsg" style="margin-top:12px;text-align:center;display:none;"></div>
            </div>
        </div>
        
        <script>
        document.getElementById('capInvDate').value = new Date().toISOString().split('T')[0];
        
        const _capInvDiscountPct = {float(supplier.get("discount_percentage", 0) or 0)};
        
        function updateCapInvDiscount() {{
            const box = document.getElementById('capInvDiscountBox');
            const amount = parseFloat(document.getElementById('capInvAmount').value) || 0;
            if (amount <= 0 || _capInvDiscountPct <= 0) {{
                box.style.display = 'none';
                return;
            }}
            const vatInclusive = document.getElementById('capInvVat').checked;
            let net;
            if (vatInclusive) {{
                net = Math.round((amount - amount * 15 / 115) * 100) / 100;
            }} else {{
                net = Math.round(amount * 100) / 100;
            }}
            const discAmt = Math.round(net * _capInvDiscountPct / 100 * 100) / 100;
            const discountedNet = Math.round((net - discAmt) * 100) / 100;
            const vatAmt = Math.round(discountedNet * 0.15 * 100) / 100;
            const total = Math.round((discountedNet + vatAmt) * 100) / 100;
            
            document.getElementById('capInvNet').textContent = 'R' + net.toFixed(2);
            document.getElementById('capInvDiscLabel').textContent = 'Discount Received ' + _capInvDiscountPct + '%';
            document.getElementById('capInvDiscAmt').textContent = '-R' + discAmt.toFixed(2);
            document.getElementById('capInvVatAmt').textContent = 'R' + vatAmt.toFixed(2);
            document.getElementById('capInvTotal').textContent = 'R' + total.toFixed(2);
            box.style.display = 'block';
        }}
        
        function openCaptureInvoice() {{
            // Reset all fields and messages
            document.getElementById('capInvNumber').value = '';
            document.getElementById('capInvDate').value = new Date().toISOString().split('T')[0];
            document.getElementById('capInvDesc').value = '';
            document.getElementById('capInvGLSearch').value = '';
            document.getElementById('capInvAmount').value = '';
            document.getElementById('capInvVat').checked = true;
            document.getElementById('capInvPaid').checked = false;
            document.getElementById('capInvMsg').style.display = 'none';
            document.getElementById('zaneSuggestMsg').style.display = 'none';
            document.getElementById('capInvDiscountBox').style.display = 'none';
            document.getElementById('capInvBtn').disabled = false;
            document.getElementById('capInvBtn').textContent = 'Save Invoice';
            filterGLDropdown(''); // Reset dropdown to show all
            document.getElementById('captureInvoiceModal').style.display = 'flex';
        }}
        
        function closeCaptureInvoice() {{
            document.getElementById('captureInvoiceModal').style.display = 'none';
        }}
        
        document.getElementById('captureInvoiceModal').addEventListener('click', function(e) {{
            if (e.target === this) closeCaptureInvoice();
        }});
        
        // GL account search/filter
        const _allGLAccounts = {_gl_json_str};
        
        function filterGLDropdown(query) {{
            const sel = document.getElementById('capInvGL');
            const q = query.toLowerCase().trim();
            sel.innerHTML = '';
            let filtered = _allGLAccounts;
            if (q) {{
                filtered = _allGLAccounts.filter(a => a.code.toLowerCase().includes(q) || a.name.toLowerCase().includes(q));
                if (filtered.length === 0) filtered = _allGLAccounts; // Don't empty — show all if no match
            }}
            filtered.forEach(a => {{
                const opt = document.createElement('option');
                opt.value = a.code;
                opt.textContent = a.code + ' — ' + a.name;
                sel.appendChild(opt);
            }});
            if (filtered.length > 0) sel.value = filtered[0].code;
        }}
        
        // Zane GL suggestion
        async function zaneGLSuggest() {{
            const desc = document.getElementById('capInvDesc').value.trim();
            const supplierName = '{supplier_name_escaped}';
            const msgDiv = document.getElementById('zaneSuggestMsg');
            const btn = document.getElementById('zaneSuggestBtn');
            
            if (!desc) {{
                msgDiv.style.display = 'block';
                msgDiv.style.color = 'var(--orange)';
                msgDiv.textContent = 'Type a description first so Zane can suggest the right account.';
                return;
            }}
            
            btn.disabled = true;
            btn.textContent = '🤖 Thinking...';
            msgDiv.style.display = 'block';
            msgDiv.style.color = 'var(--text-muted)';
            msgDiv.textContent = 'Zane is checking...';
            
            try {{
                const resp = await fetch('/api/supplier/gl-suggest', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        description: desc,
                        supplier_name: supplierName,
                        accounts: _allGLAccounts
                    }})
                }});
                const result = await resp.json();
                const answer = (result.suggestion || '').trim();
                
                if (answer.includes('|')) {{
                    const parts = answer.split('|');
                    const suggestedCode = parts[0].trim();
                    const reason = parts.slice(1).join('|').trim();
                    
                    if (suggestedCode && suggestedCode !== '?') {{
                        // Found a real account — select it
                        const sel = document.getElementById('capInvGL');
                        let found = false;
                        for (let opt of sel.options) {{
                            if (opt.value === suggestedCode) {{
                                sel.value = opt.value;
                                found = true;
                                break;
                            }}
                        }}
                        
                        msgDiv.style.color = 'var(--green)';
                        msgDiv.innerHTML = '🤖 <strong>' + suggestedCode + '</strong> — ' + reason;
                        if (!found) {{
                            // Try partial match
                            for (let opt of sel.options) {{
                                if (opt.value.startsWith(suggestedCode.split('/')[0])) {{
                                    sel.value = opt.value;
                                    found = true;
                                    break;
                                }}
                            }}
                            if (!found) msgDiv.innerHTML += ' <span style="color:var(--orange);">(select manually)</span>';
                        }}
                    }} else {{
                        // No specific account found — guide the user
                        msgDiv.style.color = 'var(--primary)';
                        msgDiv.innerHTML = '🤖 ' + reason;
                    }}
                }} else {{
                    msgDiv.style.color = 'var(--text-muted)';
                    msgDiv.textContent = '🤖 ' + answer.substring(0, 150);
                }}
            }} catch(e) {{
                msgDiv.style.color = 'var(--red)';
                msgDiv.textContent = 'Could not reach Zane: ' + e.message;
            }}
            
            btn.disabled = false;
            btn.textContent = '🤖 Suggest';
        }}
        
        async function submitCaptureInvoice() {{
            const btn = document.getElementById('capInvBtn');
            btn.disabled = true;
            btn.textContent = 'Saving...';
            const msg = document.getElementById('capInvMsg');
            
            const data = {{
                supplier_id: '{supplier_id}',
                supplier_name: '{safe_string(supplier.get("name", "")).replace(chr(39), "")}',
                invoice_number: document.getElementById('capInvNumber').value.trim(),
                date: document.getElementById('capInvDate').value,
                description: document.getElementById('capInvDesc').value.trim(),
                gl_code: document.getElementById('capInvGL').value,
                amount: parseFloat(document.getElementById('capInvAmount').value) || 0,
                vat_inclusive: document.getElementById('capInvVat').checked,
                is_paid: document.getElementById('capInvPaid').checked
            }};
            
            if (!data.amount) {{
                msg.style.display = 'block';
                msg.style.color = 'var(--red)';
                msg.textContent = 'Please enter an amount';
                btn.disabled = false;
                btn.textContent = 'Save Invoice';
                return;
            }}
            
            try {{
                const resp = await fetch('/api/supplier/capture-invoice', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});
                const result = await resp.json();
                if (result.success) {{
                    msg.style.display = 'block';
                    msg.style.color = 'var(--green)';
                    msg.textContent = '✓ ' + result.message;
                    setTimeout(() => location.reload(), 1500);
                }} else {{
                    msg.style.display = 'block';
                    msg.style.color = 'var(--red)';
                    msg.textContent = result.error || 'Failed to save';
                    btn.disabled = false;
                    btn.textContent = 'Save Invoice';
                }}
            }} catch(e) {{
                msg.style.display = 'block';
                msg.style.color = 'var(--red)';
                msg.textContent = 'Error: ' + e.message;
                btn.disabled = false;
                btn.textContent = 'Save Invoice';
            }}
        }}
        </script>
        
        <!-- Record Payment Modal -->
        <div id="paymentModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:var(--card);border-radius:12px;padding:30px;width:90%;max-width:560px;max-height:90vh;overflow-y:auto;border:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                    <h2 style="margin:0;">💰 Record Payment</h2>
                    <button onclick="document.getElementById('paymentModal').style.display='none'" style="background:none;border:none;color:var(--text-muted);font-size:24px;cursor:pointer;">&times;</button>
                </div>
                <p style="color:var(--text-muted);margin-bottom:16px;font-size:13px;">Pay <strong>{safe_string(supplier.get("name", ""))}</strong> — balance: <strong style="color:var(--orange);">R{balance:,.2f}</strong></p>
                
                <div style="display:flex;flex-direction:column;gap:14px;">
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Amount</label>
                        <input type="number" id="payAmount" placeholder="0.00" step="0.01" min="0.01" style="width:100%;padding:12px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:20px;font-weight:700;">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Payment Method</label>
                        <select id="payMethod" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                            <option value="eft" selected>EFT / Bank Transfer</option>
                            <option value="cash">Cash</option>
                            <option value="card">Card</option>
                            <option value="cheque">Cheque</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Date</label>
                        <input type="date" id="payDate" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Reference / Note</label>
                        <input type="text" id="payRef" placeholder="e.g. POP ref, etc." style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    </div>
                    <div>
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                            <label style="font-weight:600;font-size:13px;">Allocate to Invoices</label>
                            <button type="button" onclick="spAutoAllocate()" style="padding:5px 10px;font-size:12px;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:6px;cursor:pointer;">Auto-allocate</button>
                        </div>
                        <div style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:4px 12px;">
                            {_sp_alloc_rows_html}
                        </div>
                        <div id="spAllocSummary" style="font-size:12px;color:var(--text-muted);margin-top:6px;">Unallocated remainder stays on the supplier's account.</div>
                    </div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:20px;">
                    <button onclick="submitPayment()" id="payBtn" style="flex:1;padding:12px;background:var(--green);color:white;border:none;border-radius:8px;cursor:pointer;font-weight:700;font-size:15px;">Pay Now</button>
                    <button onclick="tryZanePayment()" style="padding:12px 16px;background:var(--card);color:var(--primary);border:1px solid var(--primary);border-radius:8px;cursor:pointer;font-weight:600;font-size:13px;" title="Ask Zane to process this payment">🤖 Ask Zane</button>
                    <button onclick="document.getElementById('paymentModal').style.display='none'" style="padding:12px 16px;background:var(--card);color:var(--text-muted);border:1px solid var(--border);border-radius:8px;cursor:pointer;">Cancel</button>
                </div>
                <div id="payMsg" style="margin-top:12px;text-align:center;display:none;"></div>
            </div>
        </div>
        
        <script>
        document.getElementById('payDate').value = new Date().toISOString().split('T')[0];
        
        function spSyncPayAmount() {{
            let total = 0;
            document.querySelectorAll('.spAllocAmt').forEach(function(inp) {{ total += parseFloat(inp.value) || 0; }});
            total = Math.round(total * 100) / 100;
            const pa = document.getElementById('payAmount');
            if (pa && total > 0) pa.value = total.toFixed(2);
        }}
        function spToggleDisc(chk) {{
            const inp = document.querySelector('.spAllocAmt[data-invid="' + chk.dataset.invid + '"]');
            if (!inp) return;
            inp.value = chk.checked ? (parseFloat(inp.dataset.nettopay) || 0).toFixed(2) : (parseFloat(inp.dataset.outstanding) || 0).toFixed(2);
            spSyncPayAmount();
            if (typeof spUpdateAllocSummary === 'function') spUpdateAllocSummary();
        }}
        
        document.getElementById('paymentModal').addEventListener('click', function(e) {{
            if (e.target === this) this.style.display = 'none';
        }});
        
        // Collect non-zero supplier-invoice allocations from the modal
        function spCollectAllocations() {{
            const out = [];
            document.querySelectorAll('.spAllocAmt').forEach(function(inp) {{
                const amt = parseFloat(inp.value) || 0;
                const chk = document.querySelector('.spDiscChk[data-invid="' + inp.dataset.invid + '"]');
                let disc = 0;
                if (chk && chk.checked) {{ disc = parseFloat(inp.dataset.disc) || 0; }}
                if (amt > 0 || disc > 0) {{
                    out.push({{ supplier_invoice_id: inp.dataset.invid, amount: Math.round(amt * 100) / 100, discount: Math.round(disc * 100) / 100 }});
                }}
            }});
            return out;
        }}
        
        // Auto-allocate: spread the amount across open invoices, oldest first
        function spAutoAllocate() {{
            let remaining = parseFloat(document.getElementById('payAmount').value) || 0;
            document.querySelectorAll('.spAllocAmt').forEach(function(inp) {{
                const chk = document.querySelector('.spDiscChk[data-invid="' + inp.dataset.invid + '"]');
                const target = (chk && chk.checked) ? (parseFloat(inp.dataset.nettopay) || 0) : (parseFloat(inp.dataset.outstanding) || 0);
                if (remaining <= 0) {{ inp.value = ''; return; }}
                const give = Math.min(remaining, target);
                inp.value = give > 0 ? give.toFixed(2) : '';
                remaining = Math.round((remaining - give) * 100) / 100;
            }});
            spUpdateAllocSummary();
        }}
        
        // Show how much of the payment is allocated vs left on account
        function spUpdateAllocSummary() {{
            const summary = document.getElementById('spAllocSummary');
            if (!summary) return;
            const amount = parseFloat(document.getElementById('payAmount').value) || 0;
            let allocated = 0;
            document.querySelectorAll('.spAllocAmt').forEach(function(inp) {{
                allocated += parseFloat(inp.value) || 0;
            }});
            allocated = Math.round(allocated * 100) / 100;
            const remainder = Math.round((amount - allocated) * 100) / 100;
            if (amount <= 0) {{
                summary.textContent = 'Unallocated remainder stays on the supplier account.';
                summary.style.color = 'var(--text-muted)';
            }} else if (allocated > amount + 0.001) {{
                summary.textContent = 'Allocated R' + allocated.toFixed(2) + ' — more than the payment amount';
                summary.style.color = 'var(--red)';
            }} else {{
                summary.textContent = 'Allocated R' + allocated.toFixed(2) + ' · On account R' + remainder.toFixed(2);
                summary.style.color = 'var(--text-muted)';
            }}
        }}
        
        document.querySelectorAll('.spAllocAmt').forEach(function(inp) {{
            inp.addEventListener('input', spUpdateAllocSummary);
        }});
        spSyncPayAmount();
        spUpdateAllocSummary();
        
        function tryZanePayment() {{
            const amount = document.getElementById('payAmount').value || '';
            const ref = document.getElementById('payRef').value || '';
            const aiInput = document.getElementById('aiInput');
            if (aiInput) {{
                aiInput.value = 'Pay {supplier_name_escaped} R' + amount + (ref ? ' ref ' + ref : '');
                aiInput.focus();
                document.getElementById('paymentModal').style.display = 'none';
            }} else {{
                alert('Zane chat is not available on this page — use Pay Now instead.');
            }}
        }}
        
        async function submitPayment() {{
            const btn = document.getElementById('payBtn');
            btn.disabled = true;
            btn.textContent = 'Processing...';
            const msg = document.getElementById('payMsg');
            
            const amount = parseFloat(document.getElementById('payAmount').value) || 0;
            if (!amount) {{
                msg.style.display = 'block';
                msg.style.color = 'var(--red)';
                msg.textContent = 'Please enter an amount';
                btn.disabled = false;
                btn.textContent = 'Pay Now';
                return;
            }}
            
            const data = {{
                supplier_id: '{supplier_id}',
                supplier_name: '{supplier_name_escaped}',
                amount: amount,
                method: document.getElementById('payMethod').value,
                date: document.getElementById('payDate').value,
                reference: document.getElementById('payRef').value.trim(),
                allocations: spCollectAllocations()
            }};
            
            // Guard: total allocated may not exceed the payment amount
            let _spAllocSum = 0;
            data.allocations.forEach(function(a) {{ _spAllocSum += a.amount; }});
            if (_spAllocSum > amount + 0.001) {{
                msg.style.display = 'block';
                msg.style.color = 'var(--red)';
                msg.textContent = 'Allocated total (R' + _spAllocSum.toFixed(2) + ') is more than the payment amount';
                btn.disabled = false;
                btn.textContent = 'Pay Now';
                return;
            }}
            
            try {{
                const resp = await fetch('/api/supplier/record-payment', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});
                const result = await resp.json();
                if (result.success) {{
                    msg.style.display = 'block';
                    msg.style.color = 'var(--green)';
                    msg.textContent = '✓ ' + result.message;
                    setTimeout(() => location.reload(), 1500);
                }} else {{
                    msg.style.display = 'block';
                    msg.style.color = 'var(--red)';
                    msg.textContent = result.error || 'Failed';
                    btn.disabled = false;
                    btn.textContent = 'Pay Now';
                }}
            }} catch(e) {{
                msg.style.display = 'block';
                msg.style.color = 'var(--red)';
                msg.textContent = 'Error: ' + e.message;
                btn.disabled = false;
                btn.textContent = 'Pay Now';
            }}
        }}
        </script>
        '''
        
        return render_page(supplier.get("name", "Supplier"), content, user, "suppliers")
    
    
    @app.route("/supplier/<supplier_id>/reverse-payment/<payment_id>", methods=["POST"])
    @login_required
    def reverse_supplier_payment(supplier_id, payment_id):
        """Reverse ONE supplier payment — for fixing a payment captured twice (e.g. once
        manually and once from a bank allocation). Posts the EXACT opposite of the payment's
        own GL journal, removes the payment so the calculated balance corrects, and logs it."""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return redirect("/")
        if get_user_role() not in ("owner", "admin", "manager", "bookkeeper", "accountant"):
            flash("You don't have permission for this.", "error")
            return redirect(f"/supplier/{supplier_id}")

        p = db.get_one("supplier_payments", payment_id)
        if not p or p.get("business_id") != biz_id:
            flash("Payment not found.", "error")
            return redirect(f"/supplier/{supplier_id}")

        amount = round(float(p.get("amount", 0) or 0), 2)
        pdate = p.get("date", "")
        _ref = (p.get("reference") or "").strip()
        _bref = (p.get("bank_reference") or "").strip()

        # Find the payment's own journal lines to learn the asset account it credited
        # (bank/cash) and the creditors side it debited. Original: DR Creditors / CR Bank.
        asset_code = None
        cr_account = None
        try:
            for _try_ref in [x for x in (_ref, _bref) if x and x != "-"]:
                for j in (db.get("journals", {"business_id": biz_id, "reference": _try_ref}) or []):
                    if (j.get("date") or "") != pdate:
                        continue
                    jd = round(float(j.get("debit", 0) or 0), 2)
                    jc = round(float(j.get("credit", 0) or 0), 2)
                    if asset_code is None and abs(jc - amount) < 0.01 and jd == 0:
                        asset_code = (j.get("account_code") or "").strip()
                    elif cr_account is None and abs(jd - amount) < 0.01 and jc == 0:
                        cr_account = (j.get("account_code") or "").strip()
                if asset_code:
                    break
        except Exception as e:
            logger.error(f"[REVERSE SUP PAYMENT] journal lookup failed: {e}")

        if cr_account is None:
            cr_account = gl(biz_id, "creditors")

        _rev_ref = f"REV-{_ref or _bref or payment_id[:6]}-{payment_id[:6]}"
        posted = False
        if asset_code and cr_account:
            try:
                # Reverse the original DR Creditors / CR Bank: now DR Bank / CR Creditors
                create_journal_entry(
                    biz_id, today(),
                    f"Reverse duplicate supplier payment ({_ref or _bref})",
                    _rev_ref,
                    [
                        {"account_code": asset_code, "debit": amount, "credit": 0},
                        {"account_code": cr_account, "debit": 0, "credit": amount},
                    ]
                )
                posted = True
            except Exception as e:
                logger.error(f"[REVERSE SUP PAYMENT] reverse journal failed: {e}")
                flash(f"Could not post the reversing journal: {e}", "error")
                return redirect(f"/supplier/{supplier_id}")

        try:
            if log_allocation:
                _u = Auth.get_current_user() or {}
                log_allocation(
                    business_id=biz_id, allocation_type="reversal", source_table="supplier_payments",
                    source_id=payment_id,
                    description=f"Reversed duplicate supplier payment - {money(amount)}",
                    amount=amount, gl_entries=[],
                    reference=_rev_ref, transaction_date=today(),
                    created_by=_u.get("id", ""), created_by_name=_u.get("name", "")
                )
        except Exception:
            pass

        db.delete("supplier_payments", payment_id, biz_id)
        logger.info(f"[REVERSE SUP PAYMENT] Reversed supplier payment {payment_id} ({_ref}, {money(amount)}); asset={asset_code} cr={cr_account} posted={posted}")
        if posted:
            flash(f"Reversed payment of {money(amount)} (DR {asset_code} / CR {cr_account}). The balance has been updated.", "success")
        else:
            flash(f"Removed payment of {money(amount)} (no matching GL journal found to reverse — please check the bank GL).", "success")
        return redirect(f"/supplier/{supplier_id}")
    
    
    @app.route("/supplier/<supplier_id>/edit", methods=["GET", "POST"])
    @login_required
    def supplier_edit(supplier_id):
        """Edit supplier - comprehensive form"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        supplier = db.get_one("suppliers", supplier_id)
        if not supplier:
            return redirect("/suppliers")
        
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Supplier name is required", "error")
            else:
                fields = _get_form_fields()
                fields["name"] = name
                fields["code"] = request.form.get("code", "").strip()
                fields["address"] = fields.get("physical_address", "")
                # Balance is now calculated dynamically — do not save from form
                try:
                    fields["credit_limit"] = float(request.form.get("credit_limit", 0) or 0)
                except:
                    fields["credit_limit"] = 0
                try:
                    fields["discount_percentage"] = float(request.form.get("discount_percentage", 0) or 0)
                except:
                    fields["discount_percentage"] = 0
                
                success = db.update("suppliers", supplier_id, fields)
                if success:
                    flash(f"Supplier '{name}' updated!", "success")
                    return redirect(f"/supplier/{supplier_id}")
                else:
                    flash("Error updating supplier", "error")
        
        content = _supplier_form(v=supplier, is_edit=True)
        return render_page(f"Edit {supplier.get('name', 'Supplier')}", content, user, "suppliers")
    
    

    # === PURCHASES + SUPPLIER INVOICES ===

    @app.route("/purchases")
    @login_required
    def purchases_page():
        """Purchase Orders - Full workflow"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        orders = db.get("purchase_orders", {"business_id": biz_id}) if biz_id else []
        orders = sorted(orders, key=lambda x: x.get("date", ""), reverse=True)
        
        # Stats
        draft_orders = [o for o in orders if o.get("status") == "draft"]
        sent_orders = [o for o in orders if o.get("status") == "sent"]
        partial_orders = [o for o in orders if o.get("status") == "partial"]
        total_outstanding = sum(float(o.get("total") or 0) for o in orders if o.get("status") in ("sent", "partial"))
        
        rows = ""
        for po in orders[:500]:
            status = po.get("status", "draft")
            status_colors = {
                "draft": "var(--text-muted)", 
                "sent": "var(--orange)", 
                "partial": "#3b82f6",
                "received": "var(--green)",
                "cancelled": "var(--red)"
            }
            status_color = status_colors.get(status, "var(--text-muted)")
            
            rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='/purchase/{po.get("id")}'">
                <td><strong>{po.get("po_number", "-")}</strong></td>
                <td>{po.get("date", "-")}</td>
                <td>{safe_string(po.get("supplier_name", "-"))}</td>
                <td style="text-align: right;">{money(po.get("total") or 0)}</td>
                <td style="color:{status_color};">{status.title()}</td>
                <td style="text-align: center;">
                    {"📧" if po.get("emailed") else ""}
                </td>
            </tr>
            '''
        
        content = f'''
        <div class="card" style="margin-bottom: 20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <div>
                    <h2 style="margin:0;">Purchase Orders</h2>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;">Order stock from suppliers</p>
                </div>
                <div style="display:flex;gap:10px;">
                    <a href="/grv" class="btn btn-secondary">📦 GRV List</a>
                    <a href="/supplier-credit-notes" class="btn btn-secondary">↩️ Credit Notes</a>
                    <a href="/purchase/new" class="btn btn-primary">+ New Purchase Order</a>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px;">
                <div style="background: var(--bg); padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: var(--text-muted);">{len(draft_orders)}</div>
                    <div style="color: var(--text-muted); font-size: 13px;">Draft</div>
                </div>
                <div style="background: var(--bg); padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: var(--orange);">{len(sent_orders)}</div>
                    <div style="color: var(--text-muted); font-size: 13px;">Awaiting</div>
                </div>
                <div style="background: var(--bg); padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #3b82f6;">{len(partial_orders)}</div>
                    <div style="color: var(--text-muted); font-size: 13px;">Partial</div>
                </div>
                <div style="background: var(--bg); padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold;">{money(total_outstanding)}</div>
                    <div style="color: var(--text-muted); font-size: 13px;">Outstanding</div>
                </div>
            </div>
            
            <div style="margin-bottom:15px;">
                <input type="text" id="searchPO" placeholder="🔍 Search by supplier, PO number, amount..." oninput="filterTable('searchPO','poTable')" style="width:100%;padding:10px 15px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;">
            </div>
            
            <table class="table" id="poTable">
                <thead>
                    <tr>
                        <th>PO Number</th>
                        <th>Date</th>
                        <th>Supplier</th>
                        <th style="text-align: right;">Amount</th>
                        <th>Status</th>
                        <th style="text-align: center;">Sent</th>
                    </tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='6' style='text-align:center;color:var(--text-muted);padding:40px;'>No purchase orders yet<br><br><a href='/purchase/new' class='btn btn-primary'>Create your first PO</a></td></tr>"}
                </tbody>
            </table>
        </div>
        
        <div class="card" style="background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.05));">
            <h3 style="margin: 0 0 10px 0;">Purchase Order Workflow</h3>
            <div style="display: flex; gap: 20px; flex-wrap: wrap; color: var(--text-muted); font-size: 14px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: var(--text-muted); color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 12px;">1</span>
                    <span>Create PO</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: var(--orange); color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 12px;">2</span>
                    <span>Send to Supplier</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #3b82f6; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 12px;">3</span>
                    <span>Receive Goods</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: var(--green); color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 12px;">4</span>
                    <span>Book Supplier Invoice</span>
                </div>
            </div>
        </div>
        '''
        
        return render_page("Purchase Orders", content, user, "purchases")
    
    
    @app.route("/purchase/new", methods=["GET", "POST"])
    @login_required
    def purchase_new():
        """Create new Purchase Order"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            supplier_id = request.form.get("supplier_id", "")
            
            # Get supplier details
            supplier = db.get_one("suppliers", supplier_id) if supplier_id else None
            supplier_name = supplier.get("name", "") if supplier else request.form.get("supplier_name", "")
            supplier_email = supplier.get("email", "") if supplier else request.form.get("supplier_email", "")
            
            # Get line items
            items = []
            descriptions = request.form.getlist("item_desc[]")
            quantities = request.form.getlist("item_qty[]")
            prices = request.form.getlist("item_price[]")
            stock_ids = request.form.getlist("item_stock_id[]")
            
            subtotal = 0
            for i, desc in enumerate(descriptions):
                if desc.strip():
                    qty = float(quantities[i] or 1)
                    price = float(prices[i] or 0)
                    line_total = qty * price
                    subtotal += line_total
                    items.append({
                        "description": desc.strip(),
                        "qty": qty,
                        "price": price,
                        "total": line_total,
                        "stock_id": stock_ids[i] if i < len(stock_ids) else "",
                        "qty_received": 0
                    })
            
            if not items:
                flash("Please add at least one line item", "error")
                return redirect("/purchase/new")
            
            vat = subtotal * 0.15
            total = subtotal + vat
            
            # Generate PO number using standard next_document_number()
            existing = db.get("purchase_orders", {"business_id": biz_id}) or []
            po_num = next_document_number("PO-", existing, field="po_number")
            
            po_id = generate_id()
            po = {
                "id": po_id,
                "business_id": biz_id,
                "po_number": po_num,
                "date": request.form.get("date", today()),
                "expected_date": request.form.get("expected_date", ""),
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "items": json.dumps(items),
                "subtotal": round(subtotal, 2),
                "vat": round(vat, 2),
                "total": round(total, 2),
                "notes": request.form.get("notes", ""),
                "sales_person": request.form.get("sales_person", ""),
                "reference": request.form.get("reference", ""),
                "status": "draft",
                "emailed": False,
                "created_by": user.get("id", "") if user else "",
                "created_by_name": user.get("name", "") if user else "",
                "created_at": now()
            }
            
            success, _ = db.save("purchase_orders", po)
            
            if success:
                flash(f"Purchase Order {po_num} created", "success")
                return redirect(f"/purchase/{po_id}")
            else:
                flash("Failed to create PO", "error")
                return redirect("/purchase/new")
        
        # GET - show form
        suppliers = db.get("suppliers", {"business_id": biz_id}) if biz_id else []
        suppliers = sorted(suppliers, key=lambda x: x.get("name", "").lower())
        
        stock = db.get_all_stock(biz_id)
        stock = sorted(stock, key=lambda x: x.get("description", "").lower())
        
        # Pre-fill supplier if in query string
        prefill_supplier = request.args.get("supplier_id", "")
        
        supplier_options = '<option value="">-- Select Supplier --</option>'
        for s in suppliers:
            selected = "selected" if s.get("id") == prefill_supplier else ""
            supplier_options += f'<option value="{s.get("id")}" data-email="{safe_string(s.get("email", ""))}" {selected}>{safe_string(s.get("name", ""))}</option>'
        
        stock_options = '<option value="">-- Link to Stock Item (Optional) --</option>'
        for item in stock:
            stock_options += f'<option value="{item.get("id")}" data-price="{item.get("cost_price", 0)}">{safe_string(item.get("code", ""))} - {safe_string(item.get("description", ""))}</option>'
        
        _po_stock_json = json.dumps([{"id": s.get("id",""), "code": safe_string(s.get("code","")), "desc": safe_string(s.get("description","")), "price": float(s.get("cost_price",0) or 0)} for s in stock])
        
        content = f'''
        <style>
        .po-top-actions {{ display: flex; justify-content: center; align-items: center; gap: 30px; padding: 10px 0 15px; position: sticky; top: 60px; z-index: 50; background: var(--bg); }}
        .po-top-actions .btn {{ padding: 14px 32px; font-size: 15px; font-weight: 700; min-width: 200px; text-align: center; }}
        .po-form-grid {{ display: grid; grid-template-columns: 1fr 280px; gap: 20px; }}
        .po-main {{ display: flex; flex-direction: column; gap: 15px; min-width: 0; }}
        .po-sidebar {{ position: sticky; top: 80px; display: flex; flex-direction: column; gap: 12px; align-self: start; }}
        .po-sidebar .card {{ padding: 16px; margin: 0; }}
        .po-item-row {{ display: grid; grid-template-columns: 3fr 2fr 70px 100px 90px 30px; gap: 8px; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .po-item-row input {{ font-size: 13px; padding: 8px 10px; }}
        .po-item-hdr {{ display: grid; grid-template-columns: 3fr 2fr 70px 100px 90px 30px; gap: 8px; padding: 6px 0; font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid var(--border); }}
        .po-stock-td {{ position: relative; }}
        .po-stock-td .ssp-dropdown.po-stock-dd {{ position: fixed !important; left: auto !important; right: auto !important; z-index: 9999 !important; max-height: 60vh; min-width: 600px; overflow-y: auto; background: var(--card, #1e1e2e); border: 1px solid var(--border, #333); border-radius: 6px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
        .po-totals {{ display: flex; flex-direction: column; gap: 6px; padding-top: 12px; border-top: 2px solid var(--border); }}
        .po-totals-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 14px; }}
        .po-totals-row.grand {{ font-size: 18px; font-weight: 700; color: var(--primary); padding-top: 6px; border-top: 1px solid var(--border); }}
        .po-add-btn {{ width: 100%; padding: 10px; border: 2px dashed var(--border); background: transparent; color: var(--text-muted); cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s; border-radius: 6px; }}
        .po-add-btn:hover {{ border-color: var(--primary); color: var(--primary); background: rgba(99,102,241,0.05); }}
        .po-rm {{ background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 16px; padding: 2px; opacity: 0.5; transition: all 0.15s; }}
        .po-rm:hover {{ color: var(--red); opacity: 1; }}
        @media(max-width:1100px) {{ .po-form-grid {{ grid-template-columns: 1fr; }} .po-sidebar {{ position: static; }} }}
        </style>
        
        <div style="margin-bottom: 12px;">
            <a href="/purchases" style="color:var(--text-muted);font-size:13px;">← Back to Purchase Orders</a>
        </div>
        
        <form method="POST" id="poForm">
        <div class="po-form-grid">
            <div class="po-main">
                <div class="card" style="padding:20px;">
                    <h2 style="margin:0 0 16px 0;">New Purchase Order</h2>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Supplier *</label>
                            <select name="supplier_id" id="supplierSelect" class="form-input" required onchange="updateSupplierEmail()">
                                {supplier_options}
                            </select>
                            <small style="color:var(--text-muted);"><a href="/supplier/new" target="_blank">+ Add new supplier</a></small>
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Supplier Email</label>
                            <input type="email" name="supplier_email" id="supplierEmail" class="form-input" placeholder="For sending PO">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">PO Date</label>
                            <input type="date" name="date" class="form-input" value="{today()}">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Expected Delivery</label>
                            <input type="date" name="expected_date" class="form-input">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Sales Person</label>
                            <input type="text" name="sales_person" class="form-input" placeholder="Sales person name">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Reference</label>
                            <input type="text" name="reference" class="form-input" placeholder="Your reference / quote number">
                        </div>
                    </div>
                </div>
                
                <div class="card" style="padding:20px;">
                    <h3 style="margin:0 0 12px 0;">Line Items</h3>
                    <div class="po-item-hdr">
                        <span>Stock Item</span><span>Description</span><span>Qty</span><span>Price (excl)</span><span style="text-align:right;">Total</span><span></span>
                    </div>
                    <div id="itemsBody">
                        <div class="po-item-row">
                            <div class="po-stock-td">
                                <input type="text" name="item_stock_search[]" class="form-input po-stock-search" placeholder="Search stock..." autocomplete="off" oninput="poStockSearch(this)" onfocus="poStockSearch(this)">
                                <input type="hidden" name="item_stock_id[]" value="">
                                <div class="ssp-dropdown po-stock-dd"></div>
                            </div>
                            <input type="text" name="item_desc[]" class="form-input" placeholder="Description" required>
                            <input type="number" name="item_qty[]" class="form-input" value="1" min="0.01" step="any" onchange="calculateTotals()">
                            <input type="number" name="item_price[]" class="form-input" placeholder="0.00" step="0.01" onchange="calculateTotals()">
                            <span class="line-total" style="text-align:right;font-weight:600;">R0.00</span>
                            <span></span>
                        </div>
                    </div>
                    <button type="button" class="po-add-btn" onclick="addRow()" style="margin-top:10px;">+ Add Line Item</button>
                    
                    <div class="po-totals" style="margin-top:16px;">
                        <div class="po-totals-row"><span>Subtotal</span><span id="subtotal">R0.00</span></div>
                        <div class="po-totals-row"><span>VAT (15%)</span><span id="vat">R0.00</span></div>
                        <div class="po-totals-row grand"><span>Total</span><span id="total">R0.00</span></div>
                    </div>
                </div>
                
                <div class="card" style="padding:16px;">
                    <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Notes</label>
                    <textarea name="notes" class="form-input" rows="2" placeholder="Delivery instructions, special requirements..."></textarea>
                </div>
            </div>
            
            <div class="po-sidebar">
                <div class="card" style="background:linear-gradient(135deg,rgba(99,102,241,0.15),rgba(16,185,129,0.08));">
                    <button type="submit" class="btn btn-primary" style="width:100%;padding:14px;font-size:15px;font-weight:700;">Create Purchase Order</button>
                </div>
                <div class="card">
                    <a href="/purchases" class="btn btn-secondary" style="width:100%;text-align:center;">Cancel</a>
                </div>
                <div class="card" style="font-size:12px;color:var(--text-muted);line-height:1.6;">
                    <div style="font-weight:700;margin-bottom:6px;color:var(--text);font-size:13px;">Workflow</div>
                    <div>1. Create PO &rarr; Draft</div>
                    <div>2. Email to supplier &rarr; Sent</div>
                    <div>3. Receive goods (GRV)</div>
                    <div>4. Book supplier invoice</div>
                </div>
            </div>
        </div>
        </form>
        
        <script>
        const poStockData = {_po_stock_json};
        
        function poStockSearch(input) {{
            const wrap = input.closest('.po-stock-td');
            let dd = wrap.querySelector('.po-stock-dd');
            if (!dd) {{
                dd = document.createElement('div');
                dd.className = 'ssp-dropdown po-stock-dd';
                wrap.appendChild(dd);
            }}
            
            let q = input.value.toLowerCase().trim().replace(/\s*[xX]\s*/g, 'x');
            const terms = q.split(/\s+/).filter(t => t.length > 0);
            
            let matches = poStockData.filter(s => {{
                if (!terms.length) return true;
                const text = (s.code + ' ' + s.desc).toLowerCase().replace(/\s*[xX]\s*/g, 'x');
                return terms.every(t => text.includes(t));
            }}).slice(0, 20);
            
            if (!terms.length) {{
                dd.classList.remove('show');
                return;
            }}
            
            if (matches.length === 0) {{
                dd.innerHTML = '<div class="ssp-empty">No stock found</div>';
            }} else {{
                dd.innerHTML = matches.map((s, i) => {{
                    const safeDesc = s.desc.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
                    return '<div class="ssp-item" data-idx="' + i + '">' +
                        (s.code ? '<span class="ssp-code">' + s.code + '</span>' : '') +
                        '<span class="ssp-desc">' + safeDesc + '</span>' +
                        (s.price ? '<span class="ssp-price">R' + s.price.toFixed(2) + '</span>' : '') +
                        '</div>';
                }}).join('');
                
                // Add click handlers via event delegation
                dd.querySelectorAll('.ssp-item').forEach(el => {{
                    el.addEventListener('click', function() {{
                        const idx = parseInt(this.getAttribute('data-idx'));
                        const m = matches[idx];
                        const row = wrap.closest('.po-item-row');
                        const searchInput = row.querySelector('input[name="item_stock_search[]"]');
                        const idInput = row.querySelector('input[name="item_stock_id[]"]');
                        const descInput = row.querySelector('input[name="item_desc[]"]');
                        const priceInput = row.querySelector('input[name="item_price[]"]');
                        
                        if (searchInput) searchInput.value = m.code ? m.code + ' - ' + m.desc : m.desc;
                        if (idInput) idInput.value = m.id;
                        if (descInput) descInput.value = m.desc;
                        if (priceInput && m.price) {{ priceInput.value = m.price.toFixed(2); calculateTotals(); }}
                        dd.classList.remove('show');
                    }});
                }});
            }}
            // Position dropdown below the input (fixed positioning)
            var rect = input.getBoundingClientRect();
            dd.style.left = rect.left + 'px';
            dd.style.top = (rect.bottom + 2) + 'px';
            dd.style.width = Math.max(rect.width, 600) + 'px';
            dd.classList.add('show');
        }}
        
        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.po-stock-search') && !e.target.closest('.po-stock-dd')) {{
                document.querySelectorAll('.po-stock-dd').forEach(d => d.classList.remove('show'));
            }}
        }});
        
        function updateSupplierEmail() {{
            const select = document.getElementById('supplierSelect');
            const option = select.options[select.selectedIndex];
            document.getElementById('supplierEmail').value = option.dataset.email || '';
        }}
        
        function addRow() {{
            const body = document.getElementById('itemsBody');
            const row = document.createElement('div');
            row.className = 'po-item-row';
            row.innerHTML = `
                <div class="po-stock-td">
                    <input type="text" name="item_stock_search[]" class="form-input po-stock-search" placeholder="Search stock..." autocomplete="off" oninput="poStockSearch(this)" onfocus="poStockSearch(this)">
                    <input type="hidden" name="item_stock_id[]" value="">
                    <div class="ssp-dropdown po-stock-dd"></div>
                </div>
                <input type="text" name="item_desc[]" class="form-input" placeholder="Description">
                <input type="number" name="item_qty[]" class="form-input" value="1" min="0.01" step="any" onchange="calculateTotals()">
                <input type="number" name="item_price[]" class="form-input" placeholder="0.00" step="0.01" onchange="calculateTotals()">
                <span class="line-total" style="text-align:right;font-weight:600;">R0.00</span>
                <button type="button" class="po-rm" onclick="this.closest('.po-item-row').remove(); calculateTotals();">✕</button>
            `;
            body.appendChild(row);
            row.querySelector('.po-stock-search').focus();
        }}
        
        function calculateTotals() {{
            let subtotal = 0;
            document.querySelectorAll('.po-item-row').forEach(row => {{
                const qty = parseFloat(row.querySelector('input[name="item_qty[]"]')?.value) || 0;
                const price = parseFloat(row.querySelector('input[name="item_price[]"]')?.value) || 0;
                const lineTotal = qty * price;
                subtotal += lineTotal;
                const lt = row.querySelector('.line-total');
                if (lt) lt.textContent = 'R' + lineTotal.toFixed(2);
            }});
            
            const vat = subtotal * 0.15;
            document.getElementById('subtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('vat').textContent = 'R' + (vat).toFixed(2);
            document.getElementById('total').textContent = 'R' + (subtotal + vat).toFixed(2);
        }}
        
        calculateTotals();
        </script>
        '''
        
        return render_page("New Purchase Order", content, user, "purchases")
    
    
    @app.route("/purchase/<po_id>")
    @login_required
    def purchase_view(po_id):
        """View Purchase Order with full actions"""
        
        user = Auth.get_current_user()
        business = db.get_one("businesses", session.get("business_id")) if session.get("business_id") else Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        po = db.get_one("purchase_orders", po_id)
        if not po:
            return redirect("/purchases")
        
        # Get supplier record for email etc
        supplier_rec = db.get_one("suppliers", po.get("supplier_id")) if po.get("supplier_id") else None
        
        try:
            items = json.loads(po.get("items", "[]"))
        except:
            items = []
        
        items_html = ""
        all_received = True
        for item in items:
            qty_ordered = item.get("qty") or item.get("quantity", 1)
            qty_received = item.get("qty_received", 0)
            remaining = qty_ordered - qty_received
            
            if remaining > 0:
                all_received = False
            
            receive_status = ""
            if qty_received >= qty_ordered:
                receive_status = '<span style="color: var(--green);">✓</span>'
            elif qty_received > 0:
                receive_status = f'<span style="color: #3b82f6;">{qty_received}/{qty_ordered}</span>'
            
            # NO PRICES on PO - just description and qty
            items_html += f'''
            <tr style="border-bottom:1px solid #e5e7eb;">
                <td style="padding:10px;font-size:14px;color:#666;">{safe_string(item.get("code", ""))}</td>
                <td style="padding:4px 6px;font-size:11px;">{safe_string(item.get("description", "-"))}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;font-weight:600;">{qty_ordered}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{receive_status}</td>
            </tr>
            '''
        
        status = po.get("status", "draft")
        biz_name = business.get("name", "Business") if business else "Business"
        # Logo from the saved invoice template (honours Show Logo) - POs were missing it
        try:
            _po_tpl = json.loads(business.get("invoice_template") or "{}") if business else {}
        except (ValueError, TypeError):
            _po_tpl = {}
        _po_logo = (_po_tpl.get("logo_url") or "").strip() if _po_tpl.get("show_logo", True) else ""
        logo_html = f'<img src="{_po_logo}" style="height:48px;max-width:170px;object-fit:contain;display:block;margin-bottom:6px;" alt="Logo">' if _po_logo else ""
        
        # Action buttons based on status
        action_buttons = ""
        if status == "draft":
            action_buttons = f'''
            <button class="btn btn-secondary" onclick="editPO()">✏️ Edit</button>
            <button class="btn btn-secondary" onclick="emailPO()">Email to Supplier</button>
            <button class="btn btn-secondary" onclick="updatePOStatus('sent')">GOOD: Mark as Sent</button>
            <button class="btn btn-primary" onclick="showReceiveModal()">📦 Receive Goods</button>
            <button class="btn btn-secondary" style="color:var(--red);" onclick="deletePO()">🗑️ Delete</button>
            '''
        elif status == "sent":
            action_buttons = f'''
            <button class="btn btn-secondary" onclick="editPO()">✏️ Edit</button>
            <button class="btn btn-secondary" onclick="emailPO()">📧 Resend Email</button>
            <button class="btn btn-primary" onclick="showReceiveModal()">Receive Goods</button>
            <button class="btn btn-secondary" style="color:var(--orange);" onclick="cancelPO()">Cancel PO</button>
            '''
        elif status == "partial":
            action_buttons = f'''
            <button class="btn btn-primary" onclick="showReceiveModal()">Receive Remaining</button>
            <button class="btn btn-secondary" onclick="createSupplierInvoice()">Create Supplier Invoice</button>
            '''
        elif status == "received":
            action_buttons = f'''
            <button class="btn btn-primary" onclick="createSupplierInvoice()">📄 Create Supplier Invoice</button>
            '''
        
        # Build receive modal with items
        receive_items_html = ""
        for i, item in enumerate(items):
            qty_ordered = item.get("qty", 1)
            qty_received = item.get("qty_received", 0)
            remaining = qty_ordered - qty_received
            
            if remaining > 0:
                receive_items_html += f'''
                <tr>
                    <td>{safe_string(item.get("description", "-"))}</td>
                    <td style="text-align:center;">{qty_ordered}</td>
                    <td style="text-align:center;">{qty_received}</td>
                    <td style="text-align:center;">
                        <input type="number" name="receive_{i}" class="form-input" style="width: 80px; text-align: center;" 
                               value="{remaining}" min="0" max="{remaining}" data-index="{i}">
                    </td>
                    <td style="text-align:center;">
                        <input type="number" name="price_{i}" class="form-input" style="width: 100px; text-align: center;" 
                               placeholder="0.00" step="0.01" data-price-index="{i}" value="{item.get('price', '')}">
                    </td>
                </tr>
                '''
        
        biz_address = safe_string(business.get("address", "")).replace("\n", "<br>") if business else ""
        biz_phone = business.get("phone", "") if business else ""
        biz_email_addr = business.get("email", "") if business else ""
        
        # Pre-build sales person and reference rows (display only, no edit)
        sp_val = safe_string(po.get("sales_person", ""))
        ref_val = safe_string(po.get("reference", ""))
        # Make reference clickable if it contains document numbers
        if ref_val:
            import re
            _po_ref_patterns = re.findall(r'(PO-?\d+|DN-?\d+|INV-?\d+|CR-?\d+|SI-?\d+)', po.get("reference", ""), re.IGNORECASE)
            for _doc_num in _po_ref_patterns:
                _prefix = _doc_num.upper().rstrip('0123456789').rstrip('-')
                _link = None
                if _prefix == 'INV':
                    _all_docs = db.get("invoices", {"business_id": biz_id}) if biz_id else []
                    _match = next((d for d in _all_docs if d.get("invoice_number", "").upper() == _doc_num.upper()), None)
                    if _match: _link = f'/invoice/{_match["id"]}'
                elif _prefix == 'DN':
                    _all_docs = db.get("delivery_notes", {"business_id": biz_id}) if biz_id else []
                    _match = next((d for d in _all_docs if (d.get("dn_number", "") or d.get("delivery_note_number", "")).upper() == _doc_num.upper()), None)
                    if _match: _link = f'/delivery-note/{_match["id"]}'
                elif _prefix == 'SI':
                    _all_docs = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id else []
                    _match = next((d for d in _all_docs if d.get("invoice_number", "").upper() == _doc_num.upper()), None)
                    if _match: _link = f'/supplier-invoice/{_match["id"]}'
                elif _prefix == 'CR':
                    _all_docs = db.get("credit_notes", {"business_id": biz_id}) if biz_id else []
                    _match = next((d for d in _all_docs if d.get("credit_note_number", "").upper() == _doc_num.upper()), None)
                    if _match: _link = f'/credit-note/{_match["id"]}'
                if _link:
                    ref_val = ref_val.replace(safe_string(_doc_num), f'<a href="{_link}" style="color:var(--primary);text-decoration:none;">{safe_string(_doc_num)}</a>')
        sp_row = f'<tr><td style="padding:4px 0;color:#888;">Sales Person:</td><td style="padding:4px 0;">{sp_val}</td></tr>' if sp_val else ""
        ref_row = f'<tr><td style="padding:4px 0;color:#888;">Reference:</td><td style="padding:4px 0;">{ref_val}</td></tr>' if ref_val else ""
        
        content = f'''
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/purchases" style="color:var(--text-muted);">← Back to Purchase Orders</a>
            <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <button class="btn btn-secondary" onclick="printDocument();">🖨️ Print</button>
                {action_buttons}
            </div>
        </div>
        
        <div class="card" id="poPrint" style="background:white;color:#333;padding:0;overflow:hidden;margin-bottom:20px;">
            <!-- TOP BAR -->
            <div style="background:#0f766e;color:white;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    {logo_html}
                    <h1 style="margin:0;font-size:16px;font-weight:700;">{biz_name}</h1>
                    {f'<p style="margin:4px 0 0 0;font-size:13px;opacity:0.8;">{biz_address}</p>' if biz_address else ''}
                </div>
                <div style="text-align:right;">
                    <h2 style="margin:0;font-size:20px;font-weight:700;letter-spacing:2px;">PURCHASE ORDER</h2>
                    <span style="background:rgba(255,255,255,0.2);color:white;padding:4px 12px;border-radius:20px;font-size:12px;">
                        {status.upper()}
                    </span>
                </div>
            </div>
            
            <!-- DETAILS GRID -->
            <div style="padding:10px 25px;display:grid;grid-template-columns:1fr 1fr;gap:0;border-bottom:1px solid #e5e7eb;">
                <div style="border-right:1px solid #e5e7eb;padding-right:25px;">
                    <table style="width:100%;font-size:14px;color:#333;">
                        <tr><td style="padding:4px 0;color:#888;width:130px;">PO Number:</td><td style="padding:4px 0;font-weight:600;">{po.get("po_number", "-")}</td></tr>
                        <tr><td style="padding:4px 0;color:#888;">Date:</td><td style="padding:4px 0;">{po.get("date", "-")}</td></tr>
                        {sp_row}
                        {ref_row}
                        {f'<tr><td style="padding:4px 0;color:#888;">Expected:</td><td style="padding:4px 0;">{po.get("expected_date")}</td></tr>' if po.get("expected_date") else ""}
                        {f'<tr><td style="padding:4px 0;color:#888;">Received:</td><td style="padding:4px 0;">{po.get("received_date")}</td></tr>' if po.get("received_date") else ""}
                    </table>
                    {f'<div style="margin-top:8px;font-size:13px;color:#666;">Tel: {biz_phone}</div>' if biz_phone else ''}
                    {f'<div style="font-size:13px;color:#666;">{biz_email_addr}</div>' if biz_email_addr else ''}
                </div>
                <div style="padding-left:25px;">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;font-weight:600;">Order To (Supplier)</div>
                    <div style="font-size:16px;font-weight:700;color:#0f766e;margin-bottom:4px;">{safe_string(po.get("supplier_name", "-"))}</div>
                    {f'<div style="font-size:10px;color:#555;">{safe_string(supplier_rec.get("email", ""))}</div>' if supplier_rec and supplier_rec.get("email") else ""}
                    {f'<div style="font-size:10px;color:#555;">{safe_string(supplier_rec.get("phone", ""))}</div>' if supplier_rec and supplier_rec.get("phone") else ""}
                    {f'<div style="font-size:10px;color:#555;">{safe_string(supplier_rec.get("address", ""))}</div>' if supplier_rec and supplier_rec.get("address") else ""}
                    {f'<div style="font-size:12px;color:#888;margin-top:5px;">Emailed to supplier</div>' if po.get("emailed") else ""}
                </div>
            </div>
            
            <!-- ITEMS TABLE -->
            <div style="padding:18px 25px 0;">
                <table style="width:100%;border-collapse:collapse;font-size:14px;">
                    <thead>
                        <tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">
                            <th style="padding:5px 6px;text-align:left;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Code</th>
                            <th style="padding:5px 6px;text-align:left;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;">Description</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:80px;">Qty</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Received</th>
                        </tr>
                    </thead>
                    <tbody style="color:#333;">
                        {items_html}
                    </tbody>
                </table>
            </div>
            
            {f'<div style="padding:15px 40px 20px;"><div style="padding:12px;background:#fafafa;border-radius:6px;font-size:13px;color:#666;"><strong>Notes:</strong> {safe_string(po.get("notes", ""))}</div></div>' if po.get("notes") else ""}
        </div>
        
        <!-- Receive Goods Modal -->
        <div id="receiveModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center;">
            <div class="card" style="width: 100%; max-width: 650px; margin: 20px; max-height: 90vh; overflow-y: auto;">
                <h3 style="margin: 0 0 20px 0;">📦 Receive Goods (GRV)</h3>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:15px;">
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Supplier Invoice Number</label>
                        <input type="text" id="supplierInvoiceNum" class="form-input" placeholder="e.g. INV-12345" style="width:100%;">
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Date Received</label>
                        <input type="date" id="receiveDate" class="form-input" value="{today()}" style="width:100%;">
                    </div>
                    <div style="grid-column:1/-1;">
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Supplier Name (change if different from PO)</label>
                        <input type="text" id="grvSupplierName" class="form-input" placeholder="{safe_string(po.get('supplier_name', ''))}" value="{safe_string(po.get('supplier_name', ''))}" style="width:100%;">
                    </div>
                </div>
                
                <table class="table">
                    <thead>
                        <tr>
                            <th>Item</th>
                            <th style="text-align: center;">Ordered</th>
                            <th style="text-align: center;">Received</th>
                            <th style="text-align: center;">Receive Now</th>
                            <th style="text-align: center;">Unit Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {receive_items_html or "<tr><td colspan='5' style='text-align:center;color:var(--green);'>All items received!</td></tr>"}
                    </tbody>
                </table>
                
                <div style="margin-top: 15px;">
                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                        <input type="checkbox" id="updateStock" checked style="width: 18px; height: 18px;">
                        <span><strong>Update stock quantities</strong></span>
                    </label>
                    <small style="color: var(--text-muted); margin-left: 28px;">Add received quantities to stock on hand</small>
                </div>
                
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button class="btn btn-primary" onclick="receiveGoods()">GOOD: Confirm Receipt</button>
                    <button class="btn btn-secondary" onclick="hideModal('receiveModal')">Cancel</button>
                </div>
            </div>
        </div>
        
        <!-- Email Input Modal - supports multiple emails and override -->
        <div id="emailInputModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center;">
            <div class="card" style="width: 100%; max-width: 450px; margin: 20px;">
                <h3 style="margin: 0 0 15px 0;">Email Purchase Order</h3>
                <p style="color: var(--text-muted); margin-bottom: 10px;">Enter one or more email addresses (comma separated):</p>
                
                <input type="text" id="supplierEmailInput" class="form-input" placeholder="email1@example.com, email2@example.com" 
                       value="{safe_string(supplier_rec.get('email', '') if supplier_rec else '')}" style="width: 100%; margin-bottom: 15px;">
                
                <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; margin-bottom: 15px;">
                    <input type="checkbox" id="saveSupplierEmail" checked style="width: 18px; height: 18px;">
                    <span>Save email to supplier record</span>
                </label>
                
                <div style="display: flex; gap: 10px;">
                    <button class="btn btn-primary" onclick="sendPOWithEmail()">📧 Send</button>
                    <button class="btn btn-secondary" onclick="hideModal('emailInputModal')">Cancel</button>
                </div>
            </div>
        </div>
        
        <script>
        async function updatePOStatus(status) {{
            const response = await fetch('/api/purchase/{po_id}/status', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{status: status}})
            }});
            const data = await response.json();
            if (data.success) location.reload();
            else alert('Error: ' + data.error);
        }}
        
        async function emailPO() {{
            // Always show modal so user can change/add emails
            document.getElementById('emailInputModal').style.display = 'flex';
            document.getElementById('supplierEmailInput').focus();
        }}
        
        async function sendPOEmail(email) {{
            const btn = event ? event.target : null;
            if (btn) {{
                btn.disabled = true;
                btn.textContent = 'Sending...';
            }}
            
            // Support multiple emails (comma separated)
            const emails = email.split(',').map(e => e.trim()).filter(e => e);
            let successCount = 0;
            let errors = [];
            
            for (const addr of emails) {{
                const response = await fetch('/api/purchase/{po_id}/email', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{to_email: addr, save_email: document.getElementById('saveSupplierEmail').checked}})
                }});
                const data = await response.json();
                if (data.success) successCount++;
                else errors.push(addr + ': ' + (data.error || 'failed'));
            }}
            
            if (btn) {{
                btn.disabled = false;
                btn.textContent = '📧 Send';
            }}
            
            if (successCount > 0) {{
                alert('✅ PO sent to ' + successCount + ' address' + (successCount > 1 ? 'es' : ''));
                hideModal('emailInputModal');
                location.reload();
            }}
            if (errors.length > 0) {{
                alert('Some emails failed:\\n' + errors.join('\\n'));
            }}
        }}
        
        function showReceiveModal() {{
            document.getElementById('receiveModal').style.display = 'flex';
        }}
        
        function hideModal(id) {{
            document.getElementById(id).style.display = 'none';
        }}
        
        async function receiveGoods() {{
            const inputs = document.querySelectorAll('#receiveModal input[name^="receive_"]');
            const quantities = {{}};
            const prices = {{}};
            
            inputs.forEach(input => {{
                const index = input.dataset.index;
                const qty = parseInt(input.value) || 0;
                if (qty > 0) {{
                    quantities[index] = qty;
                }}
            }});
            
            // Collect prices
            document.querySelectorAll('#receiveModal input[name^="price_"]').forEach(input => {{
                const index = input.dataset.priceIndex;
                const price = parseFloat(input.value) || 0;
                if (price > 0) prices[index] = price;
            }});
            
            if (Object.keys(quantities).length === 0) {{
                alert('Please enter quantities to receive');
                return;
            }}
            
            const updateStock = document.getElementById('updateStock').checked;
            const supplierInvoiceNum = document.getElementById('supplierInvoiceNum').value.trim();
            const receiveDate = document.getElementById('receiveDate').value;
            const grvSupplierName = document.getElementById('grvSupplierName').value.trim();
            
            const response = await fetch('/api/purchase/{po_id}/receive', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{quantities, prices, updateStock, supplier_invoice_number: supplierInvoiceNum, receive_date: receiveDate, supplier_name_override: grvSupplierName}})
            }});
            
            const data = await response.json();
            
            if (data.success) {{
                if (data.grv_id) {{
                    if (confirm('GOOD: ' + data.message + '\\n\\nView the GRV document?')) {{
                        window.location = '/grv/' + data.grv_id;
                    }} else {{
                        location.reload();
                    }}
                }} else {{
                    alert('GOOD: ' + data.message);
                    location.reload();
                }}
            }} else {{
                alert('Error: ' + data.error);
            }}
        }}
        
        async function createSupplierInvoice() {{
            window.location = '/api/purchase/{po_id}/create-invoice';
        }}
        
        // Close modal on outside click
        document.getElementById('receiveModal').addEventListener('click', function(e) {{
            if (e.target === this) hideModal('receiveModal');
        }});
        
        document.getElementById('emailInputModal').addEventListener('click', function(e) {{
            if (e.target === this) hideModal('emailInputModal');
        }});
        
        async function sendPOWithEmail() {{
            const email = document.getElementById('supplierEmailInput').value.trim();
            if (!email || !email.includes('@')) {{
                alert('Please enter a valid email address');
                return;
            }}
            
            const saveEmail = document.getElementById('saveSupplierEmail').checked;
            
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Sending...';
            
            const response = await fetch('/api/purchase/{po_id}/email', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{to_email: email, save_email: saveEmail}})
            }});
            const data = await response.json();
            
            btn.disabled = false;
            btn.textContent = '📧 Send';
            
            if (data.success) {{
                alert('✅ ' + data.message);
                hideModal('emailInputModal');
                location.reload();
            }} else {{
                alert('❌ Error: ' + data.error);
            }}
        }}
        
        function printDocument() {{
            const content = document.getElementById('poPrint').innerHTML;
            const pw = window.open('', '_blank', 'width=800,height=600');
            pw.document.write(`<!DOCTYPE html><html><head><title>Purchase Order</title>
            <style>* {{ margin:0;padding:0;box-sizing:border-box; }} body {{ font-family:Arial,sans-serif;padding:0;color:#333;background:white;font-size:11px; }}
            table {{ width:100%;border-collapse:collapse;page-break-inside:auto; }} tr {{ page-break-inside:avoid; }} thead {{ display:table-header-group; }}
            @media print {{ body {{ padding:10mm 12mm; }} @page {{ size:A4;margin:0; }} }}</style></head><body>${{content}}</body></html>`);
            pw.document.close(); pw.focus();
            setTimeout(() => {{ pw.print(); pw.close(); }}, 250);
        }}
        
        function editPO() {{
            window.location = '/purchase/{po_id}/edit';
        }}
        
        async function deletePO() {{
            if (!confirm('Are you sure you want to DELETE this Purchase Order?\\n\\nThis cannot be undone.')) return;
            const response = await fetch('/api/purchase/{po_id}/delete', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}}
            }});
            const data = await response.json();
            if (data.success) {{
                alert('Purchase Order deleted');
                window.location = '/purchases';
            }} else {{
                alert('Error: ' + data.error);
            }}
        }}
        
        async function cancelPO() {{
            if (!confirm('Cancel this Purchase Order?\\n\\nStatus will be set to Cancelled.')) return;
            await updatePOStatus('cancelled');
        }}
        </script>
        '''
        
        return render_page(f"PO {po.get('po_number', '')}", content, user, "purchases")
    
    
    @app.route("/api/purchase/<po_id>/status", methods=["POST"])
    @login_required
    def api_po_status(po_id):
        """Update PO status"""
        try:
            data = request.get_json()
            new_status = data.get("status", "")
            
            if not new_status:
                return jsonify({"success": False, "error": "No status provided"})
            
            po = db.get_one("purchase_orders", po_id)
            if not po:
                return jsonify({"success": False, "error": "PO not found"})
            
            # Only keep fields that exist in purchase_orders table
            VALID_PO_FIELDS = {"id", "po_number", "date", "supplier_id", "supplier_name", "items", "notes", "total", "status", "received_date", "created_at", "business_id", "updated_at", "expected_date", "subtotal", "vat", "emailed", "emailed_at", "created_by", "sales_person", "reference"}
            clean_po = {k: v for k, v in po.items() if k in VALID_PO_FIELDS}
            
            clean_po["status"] = new_status
            clean_po["updated_at"] = now()
            
            # Also update sales_person and reference if provided
            if "sales_person" in data:
                clean_po["sales_person"] = data["sales_person"][:100] if data["sales_person"] else ""
            if "reference" in data:
                clean_po["reference"] = data["reference"][:100] if data["reference"] else ""
            
            success, err = db.save("purchase_orders", clean_po)
            
            if success:
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": str(err)})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/purchase/<po_id>/delete", methods=["POST"])
    @login_required
    def api_po_delete(po_id):
        """Delete a PO (only draft or cancelled)"""
        try:
            po = db.get_one("purchase_orders", po_id)
            if not po:
                return jsonify({"success": False, "error": "PO not found"})
            
            status = po.get("status", "draft")
            if status not in ("draft", "cancelled"):
                return jsonify({"success": False, "error": f"Cannot delete PO with status '{status}'. Only draft or cancelled POs can be deleted."})
            
            success = db.delete("purchase_orders", po_id)
            if success:
                logger.info(f"[PO] Deleted {po.get('po_number')} (status={status})")
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Failed to delete"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/purchase/<po_id>/edit", methods=["GET", "POST"])
    @login_required
    def purchase_edit(po_id):
        """Edit an existing Purchase Order (draft or sent only)"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        po = db.get_one("purchase_orders", po_id)
        if not po:
            flash("PO not found", "error")
            return redirect("/purchases")
        
        status = po.get("status", "draft")
        if status not in ("draft", "sent"):
            flash(f"Cannot edit PO with status '{status}'", "error")
            return redirect(f"/purchase/{po_id}")
        
        if request.method == "POST":
            supplier_id = request.form.get("supplier_id", "")
            supplier = db.get_one("suppliers", supplier_id) if supplier_id else None
            supplier_name = supplier.get("name", "") if supplier else request.form.get("supplier_name", "")
            
            items = []
            descriptions = request.form.getlist("item_desc[]")
            quantities = request.form.getlist("item_qty[]")
            prices = request.form.getlist("item_price[]")
            stock_ids = request.form.getlist("item_stock_id[]")
            
            subtotal = 0
            for i, desc in enumerate(descriptions):
                if desc.strip():
                    qty = float(quantities[i] or 1)
                    price = float(prices[i] or 0)
                    line_total = qty * price
                    subtotal += line_total
                    items.append({
                        "description": desc.strip(),
                        "qty": qty,
                        "price": price,
                        "total": line_total,
                        "stock_id": stock_ids[i] if i < len(stock_ids) else "",
                        "qty_received": 0
                    })
            
            if not items:
                flash("Please add at least one line item", "error")
                return redirect(f"/purchase/{po_id}/edit")
            
            vat = subtotal * 0.15
            total = subtotal + vat
            
            VALID_PO_FIELDS = {"id", "po_number", "date", "supplier_id", "supplier_name", "items", "notes", "total", "status", "received_date", "created_at", "business_id", "updated_at", "expected_date", "subtotal", "vat", "emailed", "emailed_at", "created_by", "sales_person", "reference"}
            clean_po = {k: v for k, v in po.items() if k in VALID_PO_FIELDS}
            
            clean_po.update({
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "date": request.form.get("date", po.get("date", today())),
                "expected_date": request.form.get("expected_date", ""),
                "items": json.dumps(items),
                "subtotal": round(subtotal, 2),
                "vat": round(vat, 2),
                "total": round(total, 2),
                "notes": request.form.get("notes", ""),
                "sales_person": request.form.get("sales_person", ""),
                "reference": request.form.get("reference", ""),
                "updated_at": now()
            })
            
            success, _ = db.save("purchase_orders", clean_po)
            if success:
                flash(f"Purchase Order {po.get('po_number')} updated", "success")
                return redirect(f"/purchase/{po_id}")
            else:
                flash("Failed to update PO", "error")
                return redirect(f"/purchase/{po_id}/edit")
        
        # GET - show edit form (reuse new PO form structure with pre-filled data)
        suppliers = db.get("suppliers", {"business_id": biz_id}) if biz_id else []
        suppliers = sorted(suppliers, key=lambda x: x.get("name", "").lower())
        
        stock = db.get_all_stock(biz_id)
        stock = sorted(stock, key=lambda x: x.get("description", "").lower())
        
        try:
            existing_items = json.loads(po.get("items", "[]"))
        except:
            existing_items = []
        
        supplier_options = '<option value="">-- Select Supplier --</option>'
        for s in suppliers:
            selected = "selected" if s.get("id") == po.get("supplier_id") else ""
            supplier_options += f'<option value="{s.get("id")}" data-email="{safe_string(s.get("email", ""))}" {selected}>{safe_string(s.get("name", ""))}</option>'
        
        _po_stock_json = json.dumps([{"id": s.get("id",""), "code": safe_string(s.get("code","")), "desc": safe_string(s.get("description","")), "price": float(s.get("cost_price",0) or 0)} for s in stock])
        
        # Build pre-filled item rows
        item_rows_html = ""
        for idx, item in enumerate(existing_items):
            item_rows_html += f'''
            <div class="po-item-row">
                <div class="po-stock-td">
                    <input type="text" name="item_stock_search[]" class="form-input po-stock-search" placeholder="Search stock..." autocomplete="off" oninput="poStockSearch(this)" onfocus="poStockSearch(this)" value="{safe_string(item.get('code', ''))}">
                    <input type="hidden" name="item_stock_id[]" value="{safe_string(item.get('stock_id', ''))}">
                    <div class="ssp-dropdown po-stock-dd"></div>
                </div>
                <input type="text" name="item_desc[]" class="form-input" placeholder="Description" required value="{safe_string(item.get('description', ''))}">
                <input type="number" name="item_qty[]" class="form-input" value="{item.get('qty', 1)}" min="0.01" step="any" onchange="calculateTotals()">
                <input type="number" name="item_price[]" class="form-input" placeholder="0.00" step="0.01" onchange="calculateTotals()" value="{item.get('price', '')}">
                <span class="line-total" style="text-align:right;font-weight:600;">R{float(item.get('total') or 0):.2f}</span>
                <button type="button" class="po-rm" onclick="this.closest('.po-item-row').remove();calculateTotals();">&times;</button>
            </div>
            '''
        
        content = f'''
        <style>
        .po-top-actions {{ display: flex; justify-content: center; align-items: center; gap: 30px; padding: 10px 0 15px; position: sticky; top: 60px; z-index: 50; background: var(--bg); }}
        .po-form-grid {{ display: grid; grid-template-columns: 1fr 280px; gap: 20px; }}
        .po-main {{ display: flex; flex-direction: column; gap: 15px; min-width: 0; }}
        .po-sidebar {{ position: sticky; top: 80px; display: flex; flex-direction: column; gap: 12px; align-self: start; }}
        .po-sidebar .card {{ padding: 16px; margin: 0; }}
        .po-item-row {{ display: grid; grid-template-columns: 3fr 2fr 70px 100px 90px 30px; gap: 8px; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .po-item-row input {{ font-size: 13px; padding: 8px 10px; }}
        .po-item-hdr {{ display: grid; grid-template-columns: 3fr 2fr 70px 100px 90px 30px; gap: 8px; padding: 6px 0; font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid var(--border); }}
        .po-stock-td {{ position: relative; }}
        .po-stock-td .ssp-dropdown.po-stock-dd {{ position: fixed !important; z-index: 9999 !important; max-height: 60vh; min-width: 600px; overflow-y: auto; background: var(--card, #1e1e2e); border: 1px solid var(--border, #333); border-radius: 6px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
        .po-totals {{ display: flex; flex-direction: column; gap: 6px; padding-top: 12px; border-top: 2px solid var(--border); }}
        .po-totals-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 14px; }}
        .po-totals-row.grand {{ font-size: 18px; font-weight: 700; color: var(--primary); padding-top: 6px; border-top: 1px solid var(--border); }}
        .po-add-btn {{ width: 100%; padding: 10px; border: 2px dashed var(--border); background: transparent; color: var(--text-muted); cursor: pointer; font-size: 13px; font-weight: 600; transition: all 0.2s; border-radius: 6px; }}
        .po-add-btn:hover {{ border-color: var(--primary); color: var(--primary); }}
        .po-rm {{ background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 16px; padding: 2px; opacity: 0.5; }}
        .po-rm:hover {{ color: var(--red); opacity: 1; }}
        @media(max-width:1100px) {{ .po-form-grid {{ grid-template-columns: 1fr; }} .po-sidebar {{ position: static; }} }}
        </style>
        
        <div style="margin-bottom: 12px;">
            <a href="/purchase/{po_id}" style="color:var(--text-muted);font-size:13px;">&larr; Back to PO {safe_string(po.get('po_number', ''))}</a>
        </div>
        
        <form method="POST" id="poForm">
        <div class="po-form-grid">
            <div class="po-main">
                <div class="card" style="padding:20px;">
                    <h2 style="margin:0 0 16px 0;">Edit Purchase Order &mdash; {safe_string(po.get('po_number', ''))}</h2>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Supplier *</label>
                            <select name="supplier_id" id="supplierSelect" class="form-input" required>
                                {supplier_options}
                            </select>
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">PO Date</label>
                            <input type="date" name="date" class="form-input" value="{po.get('date', today())}">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Expected Delivery</label>
                            <input type="date" name="expected_date" class="form-input" value="{po.get('expected_date', '')}">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Sales Person</label>
                            <input type="text" name="sales_person" class="form-input" value="{safe_string(po.get('sales_person', ''))}">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Reference</label>
                            <input type="text" name="reference" class="form-input" value="{safe_string(po.get('reference', ''))}">
                        </div>
                    </div>
                </div>
                
                <div class="card" style="padding:20px;">
                    <h3 style="margin:0 0 12px 0;">Line Items</h3>
                    <div class="po-item-hdr">
                        <span>Stock Item</span><span>Description</span><span>Qty</span><span>Price (excl)</span><span style="text-align:right;">Total</span><span></span>
                    </div>
                    <div id="itemsBody">
                        {item_rows_html}
                    </div>
                    <button type="button" class="po-add-btn" onclick="addRow()" style="margin-top:10px;">+ Add Line Item</button>
                    
                    <div class="po-totals" style="margin-top:16px;">
                        <div class="po-totals-row"><span>Subtotal</span><span id="subtotal">R{float(po.get('subtotal') or 0):.2f}</span></div>
                        <div class="po-totals-row"><span>VAT (15%)</span><span id="vat">R{float(po.get('vat') or 0):.2f}</span></div>
                        <div class="po-totals-row grand"><span>Total</span><span id="total">R{float(po.get('total') or 0):.2f}</span></div>
                    </div>
                </div>
                
                <div class="card" style="padding:16px;">
                    <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Notes</label>
                    <textarea name="notes" class="form-input" rows="2">{safe_string(po.get('notes', ''))}</textarea>
                </div>
            </div>
            
            <div class="po-sidebar">
                <div class="card" style="background:linear-gradient(135deg,rgba(99,102,241,0.15),rgba(16,185,129,0.08));">
                    <button type="submit" class="btn btn-primary" style="width:100%;padding:14px;font-size:15px;font-weight:700;">Save Changes</button>
                </div>
                <div class="card">
                    <a href="/purchase/{po_id}" class="btn btn-secondary" style="width:100%;text-align:center;">Cancel</a>
                </div>
            </div>
        </div>
        
        <script>
        const poStock = {_po_stock_json};
        
        function addRow() {{
            const body = document.getElementById('itemsBody');
            const row = document.createElement('div');
            row.className = 'po-item-row';
            row.innerHTML = `
                <div class="po-stock-td">
                    <input type="text" name="item_stock_search[]" class="form-input po-stock-search" placeholder="Search stock..." autocomplete="off" oninput="poStockSearch(this)" onfocus="poStockSearch(this)">
                    <input type="hidden" name="item_stock_id[]" value="">
                    <div class="ssp-dropdown po-stock-dd"></div>
                </div>
                <input type="text" name="item_desc[]" class="form-input" placeholder="Description" required>
                <input type="number" name="item_qty[]" class="form-input" value="1" min="0.01" step="any" onchange="calculateTotals()">
                <input type="number" name="item_price[]" class="form-input" placeholder="0.00" step="0.01" onchange="calculateTotals()">
                <span class="line-total" style="text-align:right;font-weight:600;">R0.00</span>
                <button type="button" class="po-rm" onclick="this.closest('.po-item-row').remove();calculateTotals();">&times;</button>
            `;
            body.appendChild(row);
        }}
        
        function calculateTotals() {{
            const rows = document.querySelectorAll('.po-item-row');
            let subtotal = 0;
            rows.forEach(row => {{
                const qty = parseFloat(row.querySelector('[name="item_qty[]"]')?.value || 0);
                const price = parseFloat(row.querySelector('[name="item_price[]"]')?.value || 0);
                const lineTotal = qty * price;
                subtotal += lineTotal;
                const lt = row.querySelector('.line-total');
                if (lt) lt.textContent = 'R' + lineTotal.toFixed(2);
            }});
            const vat = subtotal * 0.15;
            document.getElementById('subtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('vat').textContent = 'R' + vat.toFixed(2);
            document.getElementById('total').textContent = 'R' + (subtotal + vat).toFixed(2);
        }}
        
        function poStockSearch(el) {{
            const q = el.value.toLowerCase();
            const dd = el.closest('.po-stock-td').querySelector('.po-stock-dd');
            if (!q || q.length < 1) {{ dd.innerHTML = ''; dd.style.display = 'none'; return; }}
            const matches = poStock.filter(s => s.code.toLowerCase().includes(q) || s.desc.toLowerCase().includes(q)).slice(0, 15);
            if (!matches.length) {{ dd.innerHTML = ''; dd.style.display = 'none'; return; }}
            const rect = el.getBoundingClientRect();
            dd.style.top = (rect.bottom + 2) + 'px';
            dd.style.left = rect.left + 'px';
            dd.style.display = 'block';
            dd.innerHTML = matches.map(s => `<div style="padding:8px 12px;cursor:pointer;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.05);" onmousedown="selectPoStock(this, '${{s.id}}', '${{s.code}}', '${{s.desc}}', ${{s.price}})">${{s.code}} &mdash; ${{s.desc}}</div>`).join('');
        }}
        
        function selectPoStock(el, id, code, desc, price) {{
            const row = el.closest('.po-stock-td').closest('.po-item-row');
            row.querySelector('[name="item_stock_search[]"]').value = code;
            row.querySelector('[name="item_stock_id[]"]').value = id;
            row.querySelector('[name="item_desc[]"]').value = desc;
            if (price) row.querySelector('[name="item_price[]"]').value = price.toFixed(2);
            el.closest('.po-stock-dd').style.display = 'none';
            calculateTotals();
        }}
        
        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.po-stock-td')) {{
                document.querySelectorAll('.po-stock-dd').forEach(d => d.style.display = 'none');
            }}
        }});
        
        calculateTotals();
        </script>
        </form>
        '''
        
        return render_page(f"Edit {po.get('po_number', 'PO')}", content, user, "purchases")
    
    
    @app.route("/api/purchase/<po_id>/email", methods=["POST"])
    @login_required
    def api_po_email(po_id):
        """Email PO to supplier - NO PRICES"""
        try:
            business = Auth.get_current_business()
            biz_name = business.get("name", "Your Customer") if business else "Your Customer"
            biz_phone = business.get("phone", "") if business else ""
            biz_email = business.get("email", "") if business else ""
            
            po = db.get_one("purchase_orders", po_id)
            if not po:
                return jsonify({"success": False, "error": "PO not found"})
            
            # Get email - from request body (custom) or from supplier record
            data = request.get_json() or {}
            supplier_email = data.get("to_email", "").strip()
            
            # If no email in request, look up from supplier record
            if not supplier_email and po.get("supplier_id"):
                supplier = db.get_one("suppliers", po.get("supplier_id"))
                if supplier:
                    supplier_email = supplier.get("email", "")
            
            if not supplier_email:
                return jsonify({"success": False, "error": "No email address provided. Add email to supplier first."})
            
            # Optionally save email to supplier
            if data.get("save_email") and data.get("to_email") and po.get("supplier_id"):
                try:
                    db.update("suppliers", po.get("supplier_id"), {"email": supplier_email})
                    logger.info(f"[PO] Saved email {supplier_email} to supplier {po.get('supplier_id')}")
                except Exception as e:
                    logger.warning(f"[PO] Failed to save supplier email: {e}")
            
            # Build email body - NO PRICES
            try:
                items = json.loads(po.get("items", "[]"))
            except:
                items = []
            
            # Build HTML items table
            items_html = ""
            for item in items:
                code = item.get('code', '')
                desc = item.get('description', '')
                qty = item.get('qty') or item.get('quantity', 1)
                items_html += f'<tr style="border-bottom:1px solid #e0e0e0;"><td style="padding:6px 8px;">{code}</td><td style="padding:6px 8px;">{desc}</td><td style="padding:6px 8px;text-align:center;">{qty}</td></tr>'
            
            # Plain text version
            items_text = ""
            for item in items:
                code = item.get('code', '')
                desc = item.get('description', '')
                qty = item.get('qty') or item.get('quantity', 1)
                items_text += f"- {code} {desc}: Qty {qty}\n"
            
            po_number = po.get('po_number', '')
            supplier_name = po.get('supplier_name', 'Supplier')
            expected_date = po.get('expected_date', '')
            notes = po.get('notes', '')
            
            subject = f"Purchase Order {po_number} from {biz_name}"
            
            # Short email body
            body_html = f'''<html><body style="font-family:Arial,sans-serif;font-size:13px;color:#333;">
            <p>Dear {supplier_name},</p>
            <p>Please find attached our Purchase Order <strong>{po_number}</strong>.</p>
            <p>Please confirm receipt of this order and provide your quotation.</p>
            <p>Thank you!</p>
            <hr style="border:none;border-top:1px solid #ddd;margin:15px 0 8px;">
            <p style="color:#999;font-size:10px;">{biz_name} | {biz_phone} | {biz_email}<br>Sent via Click AI</p>
            </body></html>'''
            
            body_text = f"Purchase Order {po_number} from {biz_name}\n\nDear {supplier_name},\n\nPlease find attached our Purchase Order {po_number}.\n\nPlease confirm receipt and provide your quotation.\n\nThank you,\n{biz_name}\n{biz_phone}\n{biz_email}"
            
            # Build PO attachment HTML — matches print layout
            biz_address = safe_string(business.get("address", "")).replace("\n", "<br>") if business else ""
            _sup_rec = db.get_one("suppliers", po.get("supplier_id")) if po.get("supplier_id") else None
            _sup_email = safe_string(_sup_rec.get("email", "")) if _sup_rec else ""
            _sup_phone = safe_string(_sup_rec.get("phone", "")) if _sup_rec else ""
            _sup_address = safe_string(_sup_rec.get("address", "")) if _sup_rec else ""
            sp_val = safe_string(po.get("sales_person", ""))
            ref_val = safe_string(po.get("reference", ""))
            
            att_items = ""
            for item in items:
                code = safe_string(item.get('code', ''))
                desc = safe_string(item.get('description', ''))
                qty = item.get('qty') or item.get('quantity', 1)
                att_items += f'<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:6px 10px;font-size:12px;">{code}</td><td style="padding:6px 10px;font-size:12px;">{desc}</td><td style="padding:6px 10px;text-align:center;font-size:12px;font-weight:600;">{qty}</td></tr>'
            
            attachment_html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Purchase Order {po_number}</title>
            <style>body{{font-family:Arial,sans-serif;margin:0;padding:0;color:#333;font-size:12px;}}table{{width:100%;border-collapse:collapse;}}@media print{{@page{{margin:15mm;}}body{{padding:10px;}}}}</style>
            </head><body>
            <div style="background:#0f766e;color:white;padding:12px 20px;display:flex;justify-content:space-between;align-items:center;">
                <div><div style="font-size:14px;font-weight:700;">{biz_name}</div>{f'<div style="font-size:11px;opacity:0.8;">{biz_address}</div>' if biz_address else ''}</div>
                <div style="text-align:right;"><div style="font-size:16px;font-weight:700;letter-spacing:2px;">PURCHASE ORDER</div></div>
            </div>
            <div style="padding:10px 20px;display:flex;gap:40px;border-bottom:1px solid #e5e7eb;">
                <div style="flex:1;">
                    <table style="font-size:12px;width:auto;"><tr><td style="padding:3px 0;color:#888;width:110px;">PO Number:</td><td style="font-weight:600;">{po_number}</td></tr><tr><td style="padding:3px 0;color:#888;">Date:</td><td>{po.get("date", "-")}</td></tr>{f'<tr><td style="padding:3px 0;color:#888;">Sales Person:</td><td>{sp_val}</td></tr>' if sp_val else ''}{f'<tr><td style="padding:3px 0;color:#888;">Reference:</td><td>{ref_val}</td></tr>' if ref_val else ''}{f'<tr><td style="padding:3px 0;color:#888;">Expected:</td><td>{expected_date}</td></tr>' if expected_date else ''}</table>
                    {f'<div style="margin-top:6px;font-size:11px;color:#666;">Tel: {biz_phone}</div>' if biz_phone else ''}{f'<div style="font-size:11px;color:#666;">{biz_email}</div>' if biz_email else ''}
                </div>
                <div style="flex:1;">
                    <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;font-weight:600;">Order To (Supplier)</div>
                    <div style="font-size:14px;font-weight:700;color:#0f766e;">{safe_string(supplier_name)}</div>
                    {f'<div style="font-size:11px;color:#555;">{_sup_email}</div>' if _sup_email else ''}{f'<div style="font-size:11px;color:#555;">{_sup_phone}</div>' if _sup_phone else ''}{f'<div style="font-size:11px;color:#555;">{_sup_address}</div>' if _sup_address else ''}
                </div>
            </div>
            <div style="padding:0 20px;"><table>
                <thead><tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">
                    <th style="padding:5px 10px;text-align:left;color:#475569;font-size:10px;text-transform:uppercase;">Code</th>
                    <th style="padding:5px 10px;text-align:left;color:#475569;font-size:10px;text-transform:uppercase;">Description</th>
                    <th style="padding:5px 10px;text-align:center;color:#475569;font-size:10px;text-transform:uppercase;width:80px;">Qty</th>
                </tr></thead><tbody>{att_items}</tbody>
            </table></div>
            {f'<div style="padding:10px 20px;font-size:11px;color:#666;"><strong>Notes:</strong> {safe_string(notes)}</div>' if notes else ''}
            <div style="padding:15px 20px;font-size:11px;color:#666;">Please confirm receipt of this order and provide your quotation.<br>Thank you!</div>
            <div style="padding:5px 20px;font-size:9px;color:#bbb;">Sent via Click AI</div>
            </body></html>'''
            
            # Build PDF attachment via shared renderer (replaces HTML attachment
            # that was being blocked by corporate spam filters as a phishing vector)
            try:
                # Import the renderer from clickai.py (where Email class lives)
                from clickai import render_document_pdf as _render_doc_pdf
                _po_supplier = _sup_rec or {"name": supplier_name, "email": _sup_email, "phone": _sup_phone, "address": _sup_address}
                _po_doc = {
                    "po_number": po_number,
                    "date": po.get("date", "-"),
                    "reference": ref_val,
                    "sales_person": sp_val,
                    "expected_date": expected_date,
                    "items": items,
                    "notes": notes,
                    "supplier_name": supplier_name,
                }
                pdf_bytes = _render_doc_pdf("purchase_order", _po_doc, business or {}, _po_supplier)
                po_attachment = {
                    'filename': f'PO_{po_number}.pdf',
                    'content': pdf_bytes,
                    'content_type': 'application/pdf'
                }
            except Exception as _pdf_err:
                logger.error(f"[PO EMAIL] PDF render failed, falling back to HTML: {_pdf_err}")
                po_attachment = {
                    'filename': f'{po_number}.html',
                    'content': attachment_html,
                    'content_type': 'text/html'
                }
            
            success = Email.send(supplier_email, subject, body_html, body_text, business=business, attachments=[po_attachment])
            
            if success:
                # Update PO status
                po_fresh = db.get_one("purchase_orders", po_id)
                if po_fresh:
                    VALID_PO_FIELDS = {"id", "po_number", "date", "supplier_id", "supplier_name", "items", "notes", "total", "status", "received_date", "created_at", "business_id", "updated_at", "expected_date", "subtotal", "vat", "emailed", "emailed_at", "created_by", "sales_person", "reference"}
                    clean_po = {k: v for k, v in po_fresh.items() if k in VALID_PO_FIELDS}
                    clean_po["emailed"] = True
                    clean_po["emailed_at"] = now()
                    if clean_po.get("status") == "draft":
                        clean_po["status"] = "sent"
                    clean_po["updated_at"] = now()
                    db.save("purchase_orders", clean_po)
                
                return jsonify({"success": True, "message": f"PO emailed to {supplier_email}"})
            else:
                return jsonify({"success": False, "error": "Failed to send email. Check SMTP settings."})
            
        except Exception as e:
            logger.error(f"[PO] Email failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/purchase/<po_id>/receive", methods=["POST"])
    @login_required
    def api_po_receive(po_id):
        """Receive goods from PO"""
        try:
            data = request.get_json()
            quantities = data.get("quantities", {})
            prices = data.get("prices", {})
            update_stock = data.get("updateStock", True)
            supplier_invoice_number = data.get("supplier_invoice_number", "")
            receive_date = data.get("receive_date", today())
            supplier_name_override = data.get("supplier_name_override", "").strip()
            
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            po = db.get_one("purchase_orders", po_id)
            if not po:
                return jsonify({"success": False, "error": "PO not found"})
            
            try:
                items = json.loads(po.get("items", "[]"))
            except:
                items = []
            
            items_received = 0
            all_received = True
            
            # Get all existing stock for matching
            all_stock = db.get_all_stock(biz_id) if biz_id else []
            stock_by_code = {}
            for s in all_stock:
                code = str(s.get("code", "")).upper().strip()
                if code:
                    stock_by_code[code] = s
            
            # Abbreviations for smart code generation
            abbrevs = {"STAINLESS": "SS", "STEEL": "ST", "FLAT": "FL", "BAR": "BR", "ROUND": "RD", "SQUARE": "SQ", "PIPE": "PP", "TUBE": "TB", "SHEET": "SH", "PLATE": "PL", "ANGLE": "AN", "GALV": "GV", "HEX": "HX", "BOLT": "BLT", "NUT": "NT", "WASHER": "WS", "HOSE": "HS", "CLAMP": "CL", "VALVE": "VL", "FLANGE": "FL", "REDUCER": "RD", "COUPLING": "CP", "ELBOW": "EL", "TEE": "TE", "NIPPLE": "NP", "CAP": "CP", "PLUG": "PG", "BUSH": "BS", "FITTING": "FT", "SCREW": "SC"}
            
            for idx_str, qty_received in quantities.items():
                idx = int(idx_str)
                if 0 <= idx < len(items):
                    items[idx]["qty_received"] = items[idx].get("qty_received", 0) + qty_received
                    items_received += qty_received
                    
                    if not update_stock:
                        continue
                    
                    stock_id = items[idx].get("stock_id", "")
                    stock_item = None
                    
                    if stock_id:
                        stock_item = db.get_one_stock(stock_id)
                    
                    if not stock_item and stock_id:
                        # stock_id exists but item not found - try by code
                        stock_item = stock_by_code.get(str(items[idx].get("code", "")).upper().strip())
                    
                    if not stock_item:
                        # No stock item linked or found - try to match by description/code
                        item_code = str(items[idx].get("code", "")).upper().strip()
                        item_desc = str(items[idx].get("description", "")).upper().strip()
                        
                        # Try exact code match
                        if item_code and item_code in stock_by_code:
                            stock_item = stock_by_code[item_code]
                            items[idx]["stock_id"] = stock_item["id"]
                            logger.info(f"[PO RECEIVE] Matched by code: {item_code}")
                        
                        # Try description match against existing stock
                        if not stock_item and item_desc:
                            for s in all_stock:
                                s_desc = str(s.get("description", "")).upper().strip()
                                if s_desc and s_desc == item_desc:
                                    stock_item = s
                                    items[idx]["stock_id"] = s["id"]
                                    logger.info(f"[PO RECEIVE] Matched by description: {item_desc}")
                                    break
                        
                        # AUTO-CREATE stock item if no match found
                        if not stock_item and item_desc:
                            # Generate smart stock code using shared function
                            final_code = smart_stock_code(item_desc, set(stock_by_code.keys()))
                            
                            # Get price from PO item if available
                            unit_price = float(items[idx].get("price", 0) or 0)
                            
                            # Create the stock item
                            new_stock = RecordFactory.stock_item(
                                business_id=biz_id,
                                description=items[idx].get("description", item_desc),
                                code=final_code,
                                quantity=0,  # Will be updated below
                                cost_price=unit_price,
                                selling_price=round(unit_price * 1.3, 2) if unit_price else 0
                            )
                            db.save_stock(new_stock)
                            
                            stock_item = new_stock
                            items[idx]["stock_id"] = new_stock["id"]
                            stock_by_code[final_code] = new_stock
                            logger.info(f"[PO RECEIVE] Auto-created stock: {final_code} = {item_desc}")
                    
                    # Now update the stock quantity + cost/selling price
                    if stock_item:
                        current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                        new_qty = current_qty + qty_received
                        stock_updates = {"qty": new_qty, "quantity": new_qty}
                        
                        # Update cost price from PO and recalc selling price (maintain markup %)
                        po_price = float(items[idx].get("price", 0) or 0)
                        if po_price > 0:
                            old_cost = float(stock_item.get("cost_price") or stock_item.get("cost") or 0)
                            old_sell = float(stock_item.get("selling_price") or stock_item.get("price") or 0)
                            stock_updates["cost_price"] = po_price
                            stock_updates["cost"] = po_price
                            if old_cost > 0 and old_sell > 0:
                                markup_ratio = old_sell / old_cost
                                new_sell = round(po_price * markup_ratio, 2)
                            else:
                                new_sell = round(po_price * 1.3, 2)
                            stock_updates["selling_price"] = new_sell
                            stock_updates["price"] = new_sell
                            logger.info(f"[PO RECEIVE] Price recalc {stock_item.get('code','')}: cost {old_cost}->{po_price}, sell {old_sell}->{new_sell}")
                        
                        db.update_stock(stock_item["id"], stock_updates, biz_id)
                        logger.info(f"[PO RECEIVE] Updated stock {stock_item.get('code')}: {current_qty} + {qty_received} = {new_qty}")
                        
                        # Store stock info in item for GRV tracking
                        items[idx]["stock_id"] = stock_item["id"]
                        items[idx]["stock_code"] = stock_item.get("code", "")
                        items[idx]["stock_name"] = stock_item.get("name", stock_item.get("description", ""))
                        items[idx]["stock_qty_before"] = round(current_qty, 2)
                        items[idx]["stock_qty_after"] = round(new_qty, 2)
            
            # Check if all items fully received
            for item in items:
                if item.get("qty_received", 0) < item.get("qty", 1):
                    all_received = False
                    break
            
            # Update PO - clean record and save
            VALID_PO_FIELDS = {"id", "po_number", "date", "supplier_id", "supplier_name", "items", "notes", "total", "status", "received_date", "created_at", "business_id", "updated_at", "expected_date", "subtotal", "vat", "emailed", "emailed_at", "created_by", "sales_person", "reference"}
            clean_po = {k: v for k, v in po.items() if k in VALID_PO_FIELDS}
            
            clean_po["items"] = json.dumps(items)
            clean_po["status"] = "received" if all_received else "partial"
            clean_po["updated_at"] = now()
            
            if all_received:
                clean_po["received_date"] = today()
            
            db.save("purchase_orders", clean_po)
            
            # CREATE GRV (Goods Received Voucher) document
            grv_id = generate_id()
            existing_grvs = db.get("goods_received", {"business_id": biz_id}) if biz_id else []
            grv_num = next_document_number("GRV-", existing_grvs, field="grv_number")
            
            # Build received items list
            received_items = []
            grv_total = 0
            for idx_str, qty_received in quantities.items():
                idx = int(idx_str)
                if 0 <= idx < len(items) and qty_received > 0:
                    unit_price = prices.get(str(idx), items[idx].get("price", 0)) or 0
                    line_total = round(float(unit_price) * qty_received, 2)
                    grv_total += line_total
                    
                    # Update stock cost price AND recalculate selling price (maintain markup %)
                    if unit_price and items[idx].get("stock_id") and update_stock:
                        try:
                            new_cost = float(unit_price)
                            stock_updates = {"cost_price": new_cost, "cost": new_cost}
                            # Recalc selling price: keep existing markup ratio
                            existing = db.get_one_stock(items[idx]["stock_id"])
                            if existing:
                                old_cost = float(existing.get("cost_price") or existing.get("cost") or 0)
                                old_sell = float(existing.get("selling_price") or existing.get("price") or 0)
                                if old_cost > 0 and old_sell > 0:
                                    markup_ratio = old_sell / old_cost
                                    new_sell = round(new_cost * markup_ratio, 2)
                                elif new_cost > 0:
                                    new_sell = round(new_cost * 1.3, 2)  # Default 30% markup
                                else:
                                    new_sell = old_sell
                                stock_updates["selling_price"] = new_sell
                                stock_updates["price"] = new_sell
                                logger.info(f"[GRV] Price recalc {items[idx].get('code','')}: cost {old_cost}->{new_cost}, sell {old_sell}->{new_sell}")
                            db.update_stock(items[idx]["stock_id"], stock_updates, biz_id)
                        except Exception as e:
                            logger.error(f"[GRV] Cost/price update failed: {e}")
                    
                    received_items.append({
                        "description": items[idx].get("description", "-"),
                        "code": items[idx].get("code", ""),
                        "qty_ordered": items[idx].get("qty", 1),
                        "qty_received": qty_received,
                        "unit_price": float(unit_price),
                        "line_total": line_total,
                        "stock_id": items[idx].get("stock_id", ""),
                        "stock_code": items[idx].get("stock_code", ""),
                        "stock_name": items[idx].get("stock_name", ""),
                        "stock_qty_before": items[idx].get("stock_qty_before", 0),
                        "stock_qty_after": items[idx].get("stock_qty_after", 0),
                        "booked_to_stock": bool(items[idx].get("stock_id"))
                    })
            
            grv = {
                "id": grv_id,
                "business_id": biz_id,
                "grv_number": grv_num,
                "po_id": po_id,
                "po_number": po.get("po_number", ""),
                "supplier_id": po.get("supplier_id", ""),
                "supplier_name": supplier_name_override or po.get("supplier_name", ""),
                "supplier_invoice_number": supplier_invoice_number,
                "date": receive_date or today(),
                "items": json.dumps(received_items),
                "received_by": user.get("name", "") if user else "",
                "notes": data.get("notes", ""),
                "status": "received",
                "created_at": now()
            }
            
            grv_saved = False
            grv_error = ""
            try:
                success, result = db.save("goods_received", grv)
                if success:
                    grv_saved = True
                    logger.info(f"[GRV] Created {grv_num} from {po.get('po_number')} - {len(received_items)} items")
                else:
                    grv_error = str(result)
                    logger.error(f"[GRV] Save failed: {result}")
            except Exception as ge:
                grv_error = str(ge)
                logger.error(f"[GRV] Save exception: {ge}")
            
            # Log stock movements SEPARATELY - don't let GRV failure block this
            movements_logged = 0
            for ri in received_items:
                if ri.get("stock_id") and ri.get("booked_to_stock"):
                    try:
                        db.save("stock_movements", RecordFactory.stock_movement(
                            business_id=biz_id, stock_id=ri["stock_id"], movement_type="in",
                            quantity=ri["qty_received"], 
                            reference=f"{grv_num} | {po.get('po_number', '')} | {safe_string(po.get('supplier_name', ''))}"
                        ))
                        movements_logged += 1
                    except Exception as me:
                        logger.error(f"[GRV] Movement save failed for {ri.get('stock_code')}: {me}")
            
            logger.info(f"[GRV] {grv_num}: GRV saved={grv_saved}, movements={movements_logged}/{len(received_items)}")
            
            # Build status message - be honest about what happened
            if grv_saved:
                status_msg = f"GRV {grv_num} created! " + ("All items received. Stock updated." if all_received else f"{items_received} items received (partial delivery)")
            else:
                # GRV table might not exist - stock was still updated
                status_msg = f"Stock updated ({items_received} items received). GRV document could not be saved - please check database table 'goods_received' exists."
                if "Could not find" in grv_error:
                    status_msg += " Table needs to be created in Supabase."
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    _sm = [{"stock_id": ri.get("stock_id",""), "code": ri.get("stock_code",""), "description": ri.get("description",""), "qty_change": ri.get("qty_received",0)} for ri in received_items if ri.get("stock_id")]
                    log_allocation(
                        business_id=biz_id, allocation_type="grv", source_table="goods_received", source_id=grv_id,
                        description=f"GRV {grv_num} from PO {po.get('po_number','')} - {safe_string(po.get('supplier_name',''))}",
                        amount=0, stock_movements=_sm,
                        supplier_name=po.get("supplier_name", ""), reference=grv_num,
                        transaction_date=today(),
                        created_by=user.get("id") if user else "", created_by_name=user.get("name","") if user else "",
                        extra={"po_number": po.get("po_number",""), "items_received": items_received, "all_received": all_received}
                    )
            except Exception:
                pass
            
            # --- GL Journal Entry for PO stock received ---
            try:
                if grv_total > 0 and update_stock:
                    stock_acc = gl(biz_id, "stock")
                    cogs_acc = gl(biz_id, "cogs")
                    po_gl_entries = [
                        {"account_code": stock_acc, "debit": grv_total, "credit": 0},   # DR Stock (asset in)
                        {"account_code": cogs_acc, "debit": 0, "credit": grv_total},   # CR COGS / Purchases
                    ]
                    sup_name = supplier_name_override or po.get("supplier_name", "")
                    create_journal_entry(biz_id, receive_date or today(), f"PO {po.get('po_number','')} received from {sup_name}", f"GRV {grv_num}", po_gl_entries)
                    logger.info(f"[PO RECEIVE] GL posted: GRV {grv_num} R{grv_total:.2f} stock_acc={stock_acc} cogs_acc={cogs_acc}")
            except Exception as gl_err:
                logger.error(f"[PO RECEIVE] GL entry failed (non-critical): {gl_err}")
            
            return jsonify({"success": True, "message": status_msg, "all_received": all_received, "grv_id": grv_id, "grv_number": grv_num})
            
        except Exception as e:
            logger.error(f"[PO] Receive failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/purchase/<po_id>/create-invoice", methods=["GET", "POST"])
    @login_required
    def api_po_create_invoice(po_id):
        """Create supplier invoice from PO - with price entry form"""
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            po = db.get_one("purchase_orders", po_id)
            if not po:
                flash("PO not found", "error")
                return redirect("/purchases")
            
            po_items = po.get("items", [])
            if isinstance(po_items, str):
                try:
                    po_items = json.loads(po_items)
                except:
                    po_items = []
            
            if request.method == "POST":
                inv_number = request.form.get("invoice_number", "").strip()
                inv_date = request.form.get("date", today())
                
                if not inv_number:
                    inv_number = po.get("po_number", "").replace("PO", "SI").replace("po", "si")
                
                existing = db.get("supplier_invoices", {"business_id": biz_id, "invoice_number": inv_number})
                if existing:
                    flash(f"Invoice {inv_number} already exists", "error")
                    return redirect(f"/purchase/{po_id}")
                
                invoice_items = []
                subtotal = 0
                descriptions = request.form.getlist("item_desc[]")
                quantities = request.form.getlist("item_qty[]")
                prices = request.form.getlist("item_price[]")
                item_indexes = request.form.getlist("item_index[]")
                
                # Track how much each PO line is being invoiced now
                invoiced_now = {}  # po_item_index -> qty
                
                for i, desc in enumerate(descriptions):
                    if desc.strip():
                        qty = float(quantities[i] or 0)
                        price = float(prices[i] or 0)
                        if qty <= 0:
                            continue  # line left out of this invoice
                        line_total = qty * price
                        subtotal += line_total
                        invoice_items.append({
                            "description": desc.strip(),
                            "quantity": qty,
                            "unit_price": price,
                            "line_total": round(line_total, 2)
                        })
                        # Map back to the PO item index if we have it
                        if i < len(item_indexes):
                            try:
                                _pidx = int(item_indexes[i])
                                invoiced_now[_pidx] = invoiced_now.get(_pidx, 0) + qty
                            except (ValueError, TypeError):
                                pass
                
                if not invoice_items:
                    flash("No items to invoice — enter at least one quantity", "error")
                    return redirect(f"/api/purchase/{po_id}/create-invoice")
                
                vat = round(subtotal * 0.15, 2)
                total = round(subtotal + vat, 2)
                
                invoice = RecordFactory.supplier_invoice(
                    business_id=biz_id,
                    supplier_id=po.get("supplier_id", ""),
                    supplier_name=po.get("supplier_name", ""),
                    invoice_number=inv_number,
                    date=inv_date,
                    due_date=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
                    subtotal=subtotal,
                    vat=vat,
                    total=total,
                    items=json.dumps(invoice_items),
                    status="unpaid",
                    notes=f"From PO: {po.get('po_number', '')}"
                )
                
                success, _ = db.save("supplier_invoices", invoice)
                
                if success:
                    try:
                        # Dated on the invoice date so the GL lands in the
                        # right month — same as the main capture flow
                        create_journal_entry(biz_id, inv_date, f"Supplier Invoice {inv_number} - {po.get('supplier_name')}", inv_number, [
                            {"account_code": gl(biz_id, "purchases"), "debit": float(subtotal), "credit": 0},  # Cost of Sales/Purchases
                            {"account_code": gl(biz_id, "vat_input"), "debit": float(vat), "credit": 0},
                            {"account_code": gl(biz_id, "creditors"), "debit": 0, "credit": float(total)},
                        ])
                        
                        # Supplier balance is now calculated dynamically — no manual update needed
                    except Exception as e:
                        logger.error(f"[PO] GL entry failed: {e}")
                    
                    # Update qty_invoiced on each PO item and recompute PO status
                    try:
                        for _pidx, _qty in invoiced_now.items():
                            if 0 <= _pidx < len(po_items):
                                _prev = float(po_items[_pidx].get("qty_invoiced", 0) or 0)
                                po_items[_pidx]["qty_invoiced"] = round(_prev + _qty, 4)
                        
                        # Status: fully_invoiced once every line's invoiced >= ordered
                        _all_invoiced = True
                        for _it in po_items:
                            _ord = float(_it.get("qty") or _it.get("quantity") or 0)
                            _inv = float(_it.get("qty_invoiced", 0) or 0)
                            if _inv < _ord:
                                _all_invoiced = False
                                break
                        
                        _new_status = "received" if _all_invoiced else "partial"
                        db.update("purchase_orders", po_id, {
                            "items": json.dumps(po_items),
                            "status": _new_status
                        }, biz_id)
                    except Exception as e:
                        logger.error(f"[PO] qty_invoiced update failed: {e}")
                    
                    flash(f"Supplier invoice {inv_number} created - {money(total)}", "success")
                    return redirect("/supplier-invoices")
                
                flash("Failed to create supplier invoice", "error")
                return redirect(f"/purchase/{po_id}")
            
            # GET - show form with items from PO
            # Manier A: only show what has been RECEIVED but not yet invoiced.
            items_html = ""
            any_invoiceable = False
            for i, item in enumerate(po_items):
                desc = item.get("description") or item.get("code") or "-"
                qty_ordered = float(item.get("qty") or item.get("quantity") or 0)
                qty_received = float(item.get("qty_received", 0) or 0)
                qty_invoiced = float(item.get("qty_invoiced", 0) or 0)
                price = item.get("price") or item.get("unit_price") or ""

                # Receivable-but-uninvoiced quantity for this line
                invoiceable = round(qty_received - qty_invoiced, 4)
                if invoiceable <= 0:
                    continue  # nothing new to invoice on this line
                any_invoiceable = True

                items_html += f'''
                <tr>
                    <td>
                        <input type="text" name="item_desc[]" class="form-input" value="{safe_string(desc)}" style="width:100%;">
                        <input type="hidden" name="item_index[]" value="{i}">
                        <small style="color:var(--text-muted);">Ordered {qty_ordered:g} · Received {qty_received:g} · Already invoiced {qty_invoiced:g}</small>
                    </td>
                    <td><input type="number" name="item_qty[]" class="form-input" value="{invoiceable:g}" max="{invoiceable:g}" step="any" style="width:80px;text-align:center;" onchange="calcTotals()"></td>
                    <td><input type="number" name="item_price[]" class="form-input" value="{price}" step="0.01" placeholder="0.00" style="width:120px;text-align:right;" onchange="calcTotals()"></td>
                    <td style="text-align:right;" class="line-total">R 0.00</td>
                </tr>
                '''

            if not any_invoiceable:
                _msg = "Nothing to invoice yet — no goods have been received on this PO, or everything received is already invoiced."
                _back = f'<div class="card"><h2>Create Supplier Invoice</h2><p style="color:var(--text-muted);margin:15px 0;">{_msg}</p><a href="/purchase/{po_id}" class="btn btn-secondary">← Back to PO</a></div>'
                return render_page("Create Supplier Invoice", _back, user, "purchases")
            
            suggested_inv = po.get("po_number", "").replace("PO", "SI").replace("po", "si")
            
            content = f'''
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <a href="/purchase/{po_id}" style="color:var(--text-muted);">&#8592; Back to PO {po.get("po_number", "")}</a>
            </div>
            
            <div class="card">
                <h2 style="margin:0 0 5px 0;">&#128196; Create Supplier Invoice</h2>
                <p style="color:var(--text-muted);margin:0 0 20px 0;">From PO: {po.get("po_number", "")} &mdash; {safe_string(po.get("supplier_name", ""))}</p>
                
                <form method="POST">
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;">
                        <div>
                            <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Invoice Number (from supplier)</label>
                            <input type="text" name="invoice_number" class="form-input" value="{suggested_inv}" placeholder="Supplier invoice number" required>
                        </div>
                        <div>
                            <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Date</label>
                            <input type="date" name="date" class="form-input" value="{today()}">
                        </div>
                    </div>
                    
                    <h3 style="margin:0 0 10px 0;">Line Items &mdash; Enter Prices</h3>
                    <table style="width:100%;" id="invoiceTable">
                        <thead>
                            <tr>
                                <th style="text-align:left;">Description</th>
                                <th style="width:80px;text-align:center;">Qty</th>
                                <th style="width:120px;text-align:right;">Unit Price</th>
                                <th style="width:120px;text-align:right;">Total</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items_html}
                        </tbody>
                        <tfoot>
                            <tr><td colspan="3" style="text-align:right;font-weight:bold;">Subtotal:</td><td style="text-align:right;" id="subtotal">R 0.00</td></tr>
                            <tr><td colspan="3" style="text-align:right;color:var(--text-muted);">VAT (15%):</td><td style="text-align:right;" id="vat">R 0.00</td></tr>
                            <tr><td colspan="3" style="text-align:right;font-weight:bold;font-size:18px;">Total:</td><td style="text-align:right;font-weight:bold;font-size:18px;" id="total">R 0.00</td></tr>
                        </tfoot>
                    </table>
                    
                    <div style="display:flex;gap:10px;margin-top:20px;">
                        <button type="submit" class="btn btn-primary">&#10003; Create Supplier Invoice</button>
                        <a href="/purchase/{po_id}" class="btn btn-secondary">Cancel</a>
                    </div>
                </form>
            </div>
            
            <script>
            function calcTotals() {{{{
                const rows = document.querySelectorAll('#invoiceTable tbody tr');
                let subtotal = 0;
                rows.forEach(row => {{{{
                    const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
                    const price = parseFloat(row.querySelector('input[name="item_price[]"]').value) || 0;
                    const lineTotal = qty * price;
                    subtotal += lineTotal;
                    row.querySelector('.line-total').textContent = 'R ' + lineTotal.toFixed(2);
                }}}});
                const vat = subtotal * 0.15;
                document.getElementById('subtotal').textContent = 'R ' + subtotal.toFixed(2);
                document.getElementById('vat').textContent = 'R ' + vat.toFixed(2);
                document.getElementById('total').textContent = 'R ' + (subtotal + vat).toFixed(2);
            }}}}
            calcTotals();
            </script>
            '''
            
            return render_page(f"Create Invoice from {po.get('po_number', '')}", content, user, "purchases")
            
        except Exception as e:
            logger.error(f"[PO] Create invoice failed: {e}")
            flash(str(e), "error")
            return redirect(f"/purchase/{po_id}")
    
    # 
    # SUPPLIER INVOICES
    # 
    
    @app.route("/supplier-invoices")
    @login_required
    def supplier_invoices_page():
        """Supplier Invoices (what you owe)"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        invoices = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id else []
        invoices = sorted(invoices, key=lambda x: x.get("date", ""), reverse=True)
        
        rows = ""
        from datetime import datetime as _dt
        _today = _dt.now().date()
        for inv in invoices[:500]:
            status = inv.get("status", "unpaid")
            status_color = "var(--green)" if status == "paid" else "var(--orange)"
            inv_num = safe_string(inv.get("invoice_number", ""))
            pay_btn = "" if status == "paid" else f'<button class="btn btn-secondary" style="padding:4px 10px;font-size:12px;" onclick="paySupplier(\'{inv_num}\')"> Pay</button>'
            
            # Calculate aging for unpaid invoices
            aging_badge = ""
            due_str = inv.get("due_date", "") or ""
            if status != "paid" and due_str:
                try:
                    due_dt = _dt.strptime(str(due_str)[:10], "%Y-%m-%d").date()
                    days_overdue = (_today - due_dt).days
                    if days_overdue > 90:
                        aging_badge = '<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:10px;font-size:11px;">90+</span>'
                    elif days_overdue > 60:
                        aging_badge = '<span style="background:#f97316;color:white;padding:2px 8px;border-radius:10px;font-size:11px;">60+</span>'
                    elif days_overdue > 30:
                        aging_badge = '<span style="background:#eab308;color:white;padding:2px 8px;border-radius:10px;font-size:11px;">30+</span>'
                    elif days_overdue > 0:
                        aging_badge = f'<span style="background:#f59e0b;color:white;padding:2px 8px;border-radius:10px;font-size:11px;">{days_overdue}d</span>'
                    else:
                        aging_badge = '<span style="color:var(--green);font-size:11px;">current</span>'
                except:
                    pass
            
            inv_id = inv.get("id", "")
            
            rows += f'''
            <tr>
                <td><a href="/supplier-invoice/{inv_id}" style="color:var(--primary);font-weight:700;text-decoration:none;">{inv_num}</a></td>
                <td>{inv.get("date", "-")}</td>
                <td>{safe_string(inv.get("supplier_name", "-"))}</td>
                <td>{money(inv.get("total", 0))}</td>
                <td>{due_str or "-"} {aging_badge}</td>
                <td style="color:{status_color};">{status}</td>
                <td>{pay_btn}</td>
            </tr>
            '''
        
        total_unpaid = sum(float(inv.get("total", 0)) for inv in invoices if inv.get("status") != "paid")
        
        content = f'''
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 class="card-title" style="margin:0;"> Supplier Invoices</h3>
                <div style="display:flex;gap:8px;">
                    <a href="/supplier-credit-notes" class="btn btn-secondary" style="padding:8px 14px;font-size:13px;text-decoration:none;display:inline-block;">↩️ Credit Notes</a>
                    <button class="btn btn-primary" onclick="document.getElementById('aiInput').value='Record supplier invoice from ';document.getElementById('aiInput').focus();">+ Record Invoice</button>
                </div>
            </div>
            
            <div class="stat-card orange" style="margin-bottom:20px;">
                <div class="stat-value">{money(total_unpaid)}</div>
                <div class="stat-label">Total Unpaid</div>
            </div>
            
            <div style="margin-bottom:15px;">
                <input type="text" id="searchSI" placeholder="🔍 Search by supplier, invoice number, amount..." oninput="filterTable('searchSI','siTable')" style="width:100%;padding:10px 15px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;">
            </div>
            
            <table class="table" id="siTable">
                <thead>
                    <tr><th>Invoice #</th><th>Date</th><th>Supplier</th><th>Amount</th><th>Due / Aging</th><th>Status</th><th>Action</th></tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='6' style='text-align:center;color:var(--text-muted)'>No supplier invoices</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <script>
        function paySupplier(invNum) {{
            document.getElementById('aiInput').value = 'Pay supplier invoice ' + invNum;
            document.getElementById('sendBtn').click();
        }}
        </script>
        '''
        
        return render_page("Supplier Invoices", content, user, "supplier-invoices")
    
    
    @app.route("/supplier-invoice/<invoice_id>")
    @login_required
    def supplier_invoice_view(invoice_id):
        """View a single supplier invoice"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        invoice = db.get_one("supplier_invoices", invoice_id)
        if not invoice:
            flash("Supplier invoice not found", "error")
            return redirect("/supplier-invoices")
        
        # Check for linked scanned document
        scanned_doc_id = None
        all_scanned = db.get("scanned_documents", {"business_id": biz_id}) if biz_id else []
        for sd in all_scanned:
            if sd.get("linked_invoice_id") == invoice_id:
                scanned_doc_id = sd.get("id")
                break
        
        # Parse items
        raw_items = invoice.get("items", [])
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except:
                raw_items = []
        
        items_html = ""
        for item in (raw_items or []):
            desc = safe_string(str(item.get("description", "-")))
            qty = float(item.get("qty", item.get("quantity", 1)))
            price = float(item.get("price", item.get("unit_price", 0)))
            total = float(item.get("total", item.get("line_total", qty * price)))
            items_html += f'''
            <tr>
                <td>{desc}</td>
                <td style="text-align:right;">{qty:.2f}</td>
                <td style="text-align:right;">{money(price)}</td>
                <td style="text-align:right;">{money(total)}</td>
            </tr>
            '''
        
        status = invoice.get("status", "unpaid")
        if status == "paid":
            status_color = "var(--green)"
        elif status == "credited":
            status_color = "#6b7280"  # grey: invoice reversed by credit note
        else:
            status_color = "var(--orange)"
        supplier_id = invoice.get("supplier_id", "")
        supplier_name = safe_string(invoice.get("supplier_name", "-"))
        
        back_link = f'/supplier/{supplier_id}' if supplier_id else '/supplier-invoices'
        
        scan_btn = f'<button class="btn btn-secondary" style="padding:6px 14px;font-size:13px;" onclick="viewScannedInvoice(\'{scanned_doc_id}\')">View Scanned Document</button>' if scanned_doc_id else ''
        
        # Build clickable reference - detect PO/DN/INV/CR numbers and link them
        _ref_raw = invoice.get("reference", invoice.get("notes", "-")) or "-"
        _ref_display = safe_string(_ref_raw)
        import re
        _doc_patterns = re.findall(r'(PO-?\d+|DN-?\d+|INV-?\d+|CR-?\d+|SI-?\d+)', _ref_raw, re.IGNORECASE)
        for _doc_num in _doc_patterns:
            _prefix = _doc_num.upper().rstrip('0123456789').rstrip('-')
            _link = None
            if _prefix == 'PO':
                _all_docs = db.get("purchase_orders", {"business_id": biz_id}) if biz_id else []
                _match = next((d for d in _all_docs if d.get("po_number", "").upper() == _doc_num.upper()), None)
                if _match: _link = f'/purchase/{_match["id"]}'
            elif _prefix == 'DN':
                _all_docs = db.get("delivery_notes", {"business_id": biz_id}) if biz_id else []
                _match = next((d for d in _all_docs if (d.get("dn_number", "") or d.get("delivery_note_number", "")).upper() == _doc_num.upper()), None)
                if _match: _link = f'/delivery-note/{_match["id"]}'
            elif _prefix == 'INV':
                _all_docs = db.get("invoices", {"business_id": biz_id}) if biz_id else []
                _match = next((d for d in _all_docs if d.get("invoice_number", "").upper() == _doc_num.upper()), None)
                if _match: _link = f'/invoice/{_match["id"]}'
            elif _prefix == 'CR':
                _all_docs = db.get("credit_notes", {"business_id": biz_id}) if biz_id else []
                _match = next((d for d in _all_docs if d.get("credit_note_number", "").upper() == _doc_num.upper()), None)
                if _match: _link = f'/credit-note/{_match["id"]}'
            elif _prefix == 'SI':
                _all_docs = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id else []
                _match = next((d for d in _all_docs if d.get("invoice_number", "").upper() == _doc_num.upper()), None)
                if _match: _link = f'/supplier-invoice/{_match["id"]}'
            if _link:
                _ref_display = _ref_display.replace(safe_string(_doc_num), f'<a href="{_link}" style="color:var(--primary);text-decoration:none;">{safe_string(_doc_num)}</a>')
        
        # ─── Determine which actions are available on this invoice ───────────
        # Edit: only if not paid, not credited, and snapshot is available (new
        #       invoices captured after this fix). Without a snapshot we cannot
        #       reliably reverse the original effects.
        # Credit Note: allowed unless invoice is already credited. Works even
        #       without a snapshot (best-effort stock reversal).
        # Delete: only if not paid, not credited, has snapshot, AND no linked
        #       supplier_payment. This is a true undo and should be rare.
        _inv_status = (invoice.get("status") or "").lower()
        _has_snapshot = bool(invoice.get("stock_snapshots"))
        # Check for linked supplier payments
        _all_payments = db.get("supplier_payments", {"business_id": biz_id}) if biz_id else []
        _has_payment = any(p.get("invoice_id") == invoice_id or p.get("supplier_invoice_id") == invoice_id for p in _all_payments)
        _is_credited = _inv_status == "credited"
        _is_paid = _inv_status == "paid"
        _can_edit = (not _is_paid) and (not _is_credited) and (not _has_payment) and _has_snapshot
        _can_credit = not _is_credited
        _can_delete = (not _is_paid) and (not _is_credited) and (not _has_payment) and _has_snapshot
        # Fetch existing credit notes against this invoice (to show inline)
        try:
            _all_scns = db.get("supplier_credit_notes", {"business_id": biz_id}) if biz_id else []
        except Exception:
            _all_scns = []
        _linked_scns = [c for c in _all_scns if c.get("original_invoice_id") == invoice_id]
        _linked_scns = sorted(_linked_scns, key=lambda x: x.get("date", ""), reverse=True)
        
        # Build action button HTML
        _action_btns = ""
        if _can_edit:
            _action_btns += '<button class="btn" onclick="openEditInvoiceModal()" style="padding:6px 14px;font-size:13px;background:var(--primary);color:white;">✏️ Edit</button>'
        if _can_credit:
            _action_btns += '<button class="btn" onclick="openCreditNoteModal()" style="padding:6px 14px;font-size:13px;background:#f59e0b;color:white;">↩️ Credit Note</button>'
        if _can_delete:
            _action_btns += '<button class="btn" onclick="confirmDeleteInvoice()" style="padding:6px 14px;font-size:13px;background:var(--red);color:white;">🗑 Delete</button>'
        # If no actions, show a helpful hint
        if not _action_btns:
            _hint = ""
            if _is_credited:
                _hint = "Already credited — no further actions"
            elif _is_paid:
                _hint = "Paid — use Credit Note via supplier page to reverse"
            elif _has_payment:
                _hint = "Linked to payment — use Credit Note via supplier page"
            elif not _has_snapshot:
                _hint = "Legacy invoice — only Credit Note available"
                _action_btns = '<button class="btn" onclick="openCreditNoteModal()" style="padding:6px 14px;font-size:13px;background:#f59e0b;color:white;">↩️ Credit Note</button>'
            if _hint and not _action_btns:
                _action_btns = f'<span style="color:var(--text-muted);font-size:12px;">{_hint}</span>'
        
        # Build linked credit notes section (if any exist)
        _scn_section = ""
        if _linked_scns:
            _scn_rows = ""
            for _scn in _linked_scns:
                _scn_rows += f'''
                <tr>
                    <td><a href="/supplier-credit-note/{_scn.get("id","")}" style="color:var(--primary);">{safe_string(_scn.get("cn_number","-"))}</a></td>
                    <td>{_scn.get("date","-")}</td>
                    <td>{safe_string(_scn.get("reason","-"))}</td>
                    <td style="text-align:right;">-{money(_scn.get("total", 0))}</td>
                </tr>
                '''
            _scn_section = f'''
            <div class="card" style="margin-top:20px;border:2px solid #f59e0b;">
                <h3 style="margin-bottom:15px;color:#f59e0b;">↩️ Credit Notes Against This Invoice ({len(_linked_scns)})</h3>
                <table class="table">
                    <thead>
                        <tr><th>CN Number</th><th>Date</th><th>Reason</th><th style="text-align:right;">Amount</th></tr>
                    </thead>
                    <tbody>{_scn_rows}</tbody>
                </table>
            </div>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="{back_link}" style="color:var(--text-muted);">← Back</a>
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                {_action_btns}
                {scan_btn}
                <span style="padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;color:white;background:{status_color};">{status.upper()}</span>
            </div>
        </div>
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div>
                    <h2 style="margin:0;">Supplier Invoice</h2>
                    <p style="font-size:20px;font-weight:bold;margin:5px 0;color:var(--primary);">{safe_string(invoice.get("invoice_number", "-"))}</p>
                </div>
                <div style="text-align:right;">
                    <p style="color:var(--text-muted);margin:0;font-size:12px;">TOTAL</p>
                    <p style="font-size:28px;font-weight:bold;margin:0;">{money(invoice.get("total", 0))}</p>
                </div>
            </div>
            
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:15px;margin-top:20px;padding-top:15px;border-top:1px solid var(--border);">
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">SUPPLIER</span>
                    <span style="font-size:14px;">{"<a href=/supplier/" + supplier_id + " style=color:var(--primary)>" + supplier_name + "</a>" if supplier_id else supplier_name}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">DATE</span>
                    <span style="font-size:14px;">{invoice.get("date", "-")}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">DUE DATE</span>
                    <span style="font-size:14px;">{invoice.get("due_date", "-")}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">SUBTOTAL</span>
                    <span style="font-size:14px;">{money(invoice.get("subtotal", 0))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">VAT (15%)</span>
                    <span style="font-size:14px;">{money(invoice.get("vat", 0))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">REFERENCE</span>
                    <span style="font-size:14px;">{_ref_display}</span>
                </div>
            </div>
        </div>
        
        ''' + (f'''
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">Line Items</h3>
            <table class="table">
                <thead>
                    <tr><th>Description</th><th style="text-align:right;">Qty</th><th style="text-align:right;">Price</th><th style="text-align:right;">Total</th></tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
                <tfoot>
                    <tr style="font-weight:bold;border-top:2px solid var(--border);">
                        <td colspan="3" style="text-align:right;">Subtotal</td>
                        <td style="text-align:right;">{money(invoice.get("subtotal", 0))}</td>
                    </tr>
                    <tr>
                        <td colspan="3" style="text-align:right;">VAT (15%)</td>
                        <td style="text-align:right;">{money(invoice.get("vat", 0))}</td>
                    </tr>
                    <tr style="font-weight:bold;font-size:16px;">
                        <td colspan="3" style="text-align:right;">Total</td>
                        <td style="text-align:right;">{money(invoice.get("total", 0))}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        ''' if items_html else '') + f'''
        
        {_scn_section}
        
        <!-- ════════ EDIT INVOICE MODAL ════════ -->
        <div id="editInvModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);z-index:1001;align-items:flex-start;justify-content:center;overflow-y:auto;padding:30px 10px;">
            <div style="background:var(--card);border-radius:12px;max-width:900px;width:100%;position:relative;padding:25px;">
                <button onclick="document.getElementById('editInvModal').style.display='none'" style="position:absolute;top:10px;right:10px;background:var(--red);color:white;border:none;border-radius:50%;width:30px;height:30px;cursor:pointer;font-size:18px;">×</button>
                <h2 style="margin:0 0 20px 0;color:var(--primary);">✏️ Edit Supplier Invoice</h2>
                <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.4);border-radius:8px;padding:12px;margin-bottom:20px;font-size:13px;">
                    ⚠️ Editing will reverse the original stock and GL effects and re-apply with the new values. The original quantities, costs and selling prices will be restored before changes are applied.
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;">Invoice Number</label>
                        <input id="ed_inv_num" type="text" style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);" />
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;">Date</label>
                        <input id="ed_date" type="date" style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);" />
                    </div>
                </div>
                
                <h4 style="margin:15px 0 8px 0;">Line Items</h4>
                <div id="ed_items" style="max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:8px;padding:8px;"></div>
                <button onclick="addEditLine()" style="margin-top:8px;padding:6px 12px;background:var(--card);border:1px dashed var(--border);border-radius:6px;color:var(--text-muted);cursor:pointer;font-size:12px;">+ Add Line Item</button>
                
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;margin-top:20px;padding-top:15px;border-top:1px solid var(--border);">
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;">Subtotal</label>
                        <input id="ed_subtotal" type="number" step="0.01" style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);" />
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;">VAT</label>
                        <input id="ed_vat" type="number" step="0.01" style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);" />
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;">Total</label>
                        <input id="ed_total" type="number" step="0.01" style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);" />
                    </div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:20px;justify-content:flex-end;">
                    <button onclick="document.getElementById('editInvModal').style.display='none'" style="padding:10px 20px;background:var(--card);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer;">Cancel</button>
                    <button onclick="saveEditInvoice()" id="ed_save_btn" style="padding:10px 20px;background:var(--primary);color:white;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Save Changes</button>
                </div>
            </div>
        </div>
        
        <!-- ════════ CREDIT NOTE MODAL ════════ -->
        <div id="cnModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);z-index:1001;align-items:center;justify-content:center;">
            <div style="background:var(--card);border-radius:12px;max-width:500px;width:90%;position:relative;padding:25px;">
                <button onclick="document.getElementById('cnModal').style.display='none'" style="position:absolute;top:10px;right:10px;background:var(--red);color:white;border:none;border-radius:50%;width:30px;height:30px;cursor:pointer;font-size:18px;">×</button>
                <h2 style="margin:0 0 15px 0;color:#f59e0b;">↩️ Create Credit Note</h2>
                <p style="font-size:13px;color:var(--text-muted);margin-bottom:15px;">
                    Leave the amount blank to fully credit <strong>{money(invoice.get("total", 0))}</strong> (reverses stock + GL and marks the invoice credited), or enter a partial amount to credit value only.
                </p>
                <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:5px;">Reason (optional)</label>
                <textarea id="cn_reason" rows="3" placeholder="e.g. Data entry error, Goods returned, Price adjustment" style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);resize:vertical;"></textarea>
                <label style="font-size:12px;color:var(--text-muted);display:block;margin:12px 0 5px 0;">Partial amount, incl. VAT (optional — blank = full credit)</label>
                <input id="cn_amount" type="number" step="0.01" min="0" placeholder="Blank = full {money(invoice.get('total', 0))}" style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);">
                <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">A partial amount credits value only (VAT reversed) and does NOT return stock.</div>
                <div style="display:flex;gap:10px;margin-top:15px;justify-content:flex-end;">
                    <button onclick="document.getElementById('cnModal').style.display='none'" style="padding:10px 20px;background:var(--card);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer;">Cancel</button>
                    <button onclick="confirmCreditNote()" id="cn_save_btn" style="padding:10px 20px;background:#f59e0b;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Create Credit Note</button>
                </div>
            </div>
        </div>
        ''' + '''
        
        <!-- Scanned Document Modal -->
        <div id="scanInvModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:1000;align-items:center;justify-content:center;">
            <div style="background:var(--card);border-radius:12px;max-width:90%;max-height:90%;overflow:auto;position:relative;">
                <button onclick="document.getElementById('scanInvModal').style.display='none'" style="position:absolute;top:10px;right:10px;background:var(--red);color:white;border:none;border-radius:50%;width:30px;height:30px;cursor:pointer;font-size:18px;">×</button>
                <div id="scanInvContent" style="padding:20px;text-align:center;">
                    <p>Loading...</p>
                </div>
            </div>
        </div>
        
        <script>
        async function viewScannedInvoice(docId) {
            document.getElementById('scanInvModal').style.display = 'flex';
            document.getElementById('scanInvContent').innerHTML = '<p>Loading document...</p>';
            try {
                const response = await fetch('/api/scanned-document/' + docId);
                const data = await response.json();
                if (data.success && data.image_data) {
                    document.getElementById('scanInvContent').innerHTML =
                        '<img src="data:image/jpeg;base64,' + data.image_data + '" style="max-width:100%;max-height:80vh;" />' +
                        '<div style="margin-top:15px;"><p><strong>' + (data.reference || 'Document') + '</strong></p>' +
                        '<p style="color:var(--text-muted);">' + (data.date || '') + '</p></div>';
                } else {
                    document.getElementById('scanInvContent').innerHTML = '<p style="color:var(--red);">Document image not available</p>';
                }
            } catch(e) {
                document.getElementById('scanInvContent').innerHTML = '<p style="color:var(--red);">Error loading document</p>';
            }
        }
        document.getElementById('scanInvModal').addEventListener('click', function(e) {
            if (e.target === this) this.style.display = 'none';
        });
        
        // ═════════════ Edit / Credit Note / Delete handlers ═════════════
        const _invId = ''' + f"'{invoice_id}'" + ''';
        const _invCurrent = ''' + f'{json.dumps({"invoice_number": invoice.get("invoice_number",""), "date": invoice.get("date","") or "", "subtotal": float(invoice.get("subtotal",0) or 0), "vat": float(invoice.get("vat",0) or 0), "total": float(invoice.get("total",0) or 0), "items": (raw_items if isinstance(raw_items, list) else [])})};' + '''
        
        function renderEditLine(item, idx) {
            const desc = (item.description || item.desc || '').replace(/"/g, '&quot;');
            const qty = parseFloat(item.qty || item.quantity || 1);
            const price = parseFloat(item.unit_price || item.price || 0);
            const total = parseFloat(item.line_total || item.total || (qty * price));
            return `
            <div class="ed-line" data-idx="${idx}" style="display:grid;grid-template-columns:1fr 80px 100px 100px 30px;gap:6px;margin-bottom:6px;align-items:center;">
                <input type="text" class="ed-desc" value="${desc}" style="padding:6px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px;" />
                <input type="number" step="0.01" class="ed-qty" value="${qty}" style="padding:6px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px;text-align:right;" />
                <input type="number" step="0.01" class="ed-price" value="${price.toFixed(2)}" style="padding:6px;background:var(--bg);border:1px solid var(--border);border-radius:4px;color:var(--text);font-size:13px;text-align:right;" />
                <input type="number" step="0.01" class="ed-total" value="${total.toFixed(2)}" style="padding:6px;background:rgba(0,0,0,0.2);border:1px solid var(--border);border-radius:4px;color:var(--text-muted);font-size:13px;text-align:right;" readonly />
                <button onclick="this.parentElement.remove()" style="background:transparent;border:none;color:var(--red);cursor:pointer;font-size:16px;">×</button>
            </div>`;
        }
        
        function openEditInvoiceModal() {
            document.getElementById('ed_inv_num').value = _invCurrent.invoice_number || '';
            document.getElementById('ed_date').value = _invCurrent.date || '';
            document.getElementById('ed_subtotal').value = (_invCurrent.subtotal || 0).toFixed(2);
            document.getElementById('ed_vat').value = (_invCurrent.vat || 0).toFixed(2);
            document.getElementById('ed_total').value = (_invCurrent.total || 0).toFixed(2);
            const container = document.getElementById('ed_items');
            const items = _invCurrent.items || [];
            container.innerHTML = items.length > 0
                ? items.map((it, i) => renderEditLine(it, i)).join('')
                : '<div style="color:var(--text-muted);font-size:12px;padding:8px;">No line items — add one below.</div>';
            // Header row
            if (items.length > 0) {
                container.insertAdjacentHTML('afterbegin', '<div style="display:grid;grid-template-columns:1fr 80px 100px 100px 30px;gap:6px;margin-bottom:6px;font-size:11px;color:var(--text-muted);font-weight:600;"><div>Description</div><div style="text-align:right;">Qty</div><div style="text-align:right;">Price</div><div style="text-align:right;">Total</div><div></div></div>');
            }
            // Wire up total auto-calc on qty/price change
            container.querySelectorAll('.ed-line').forEach(row => {
                const qtyEl = row.querySelector('.ed-qty');
                const priceEl = row.querySelector('.ed-price');
                const totalEl = row.querySelector('.ed-total');
                const recalc = () => {
                    const q = parseFloat(qtyEl.value || 0);
                    const p = parseFloat(priceEl.value || 0);
                    totalEl.value = (q * p).toFixed(2);
                };
                qtyEl.addEventListener('input', recalc);
                priceEl.addEventListener('input', recalc);
            });
            document.getElementById('editInvModal').style.display = 'flex';
        }
        
        function addEditLine() {
            const container = document.getElementById('ed_items');
            const existingLines = container.querySelectorAll('.ed-line').length;
            const html = renderEditLine({description:'', qty:1, unit_price:0, line_total:0}, existingLines);
            // Strip placeholder if it exists
            const placeholder = container.querySelector('div[style*="text-muted"]');
            if (placeholder && !placeholder.classList.contains('ed-line')) placeholder.remove();
            // Add header if first line
            if (existingLines === 0 && !container.querySelector('div[style*="grid-template-columns"]')) {
                container.insertAdjacentHTML('beforeend', '<div style="display:grid;grid-template-columns:1fr 80px 100px 100px 30px;gap:6px;margin-bottom:6px;font-size:11px;color:var(--text-muted);font-weight:600;"><div>Description</div><div style="text-align:right;">Qty</div><div style="text-align:right;">Price</div><div style="text-align:right;">Total</div><div></div></div>');
            }
            container.insertAdjacentHTML('beforeend', html);
            const newRow = container.querySelector('.ed-line:last-child');
            const qtyEl = newRow.querySelector('.ed-qty');
            const priceEl = newRow.querySelector('.ed-price');
            const totalEl = newRow.querySelector('.ed-total');
            const recalc = () => {
                const q = parseFloat(qtyEl.value || 0);
                const p = parseFloat(priceEl.value || 0);
                totalEl.value = (q * p).toFixed(2);
            };
            qtyEl.addEventListener('input', recalc);
            priceEl.addEventListener('input', recalc);
        }
        
        async function saveEditInvoice() {
            const btn = document.getElementById('ed_save_btn');
            btn.disabled = true;
            btn.textContent = 'Saving...';
            const items = [];
            document.querySelectorAll('#ed_items .ed-line').forEach(row => {
                const desc = row.querySelector('.ed-desc').value.trim();
                const qty = parseFloat(row.querySelector('.ed-qty').value || 0);
                const price = parseFloat(row.querySelector('.ed-price').value || 0);
                const total = parseFloat(row.querySelector('.ed-total').value || (qty * price));
                if (desc) items.push({description: desc, quantity: qty, unit_price: price, line_total: total});
            });
            const payload = {
                invoice_number: document.getElementById('ed_inv_num').value.trim(),
                date: document.getElementById('ed_date').value,
                subtotal: parseFloat(document.getElementById('ed_subtotal').value || 0),
                vat: parseFloat(document.getElementById('ed_vat').value || 0),
                total: parseFloat(document.getElementById('ed_total').value || 0),
                items: items
            };
            try {
                const resp = await fetch('/api/supplier-invoice/' + _invId + '/edit', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (data.success) {
                    alert('Invoice updated successfully.');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Update failed'));
                    btn.disabled = false;
                    btn.textContent = 'Save Changes';
                }
            } catch(e) {
                alert('Connection error: ' + e.message);
                btn.disabled = false;
                btn.textContent = 'Save Changes';
            }
        }
        
        function openCreditNoteModal() {
            document.getElementById('cn_reason').value = '';
            document.getElementById('cnModal').style.display = 'flex';
        }
        
        async function confirmCreditNote() {
            const btn = document.getElementById('cn_save_btn');
            btn.disabled = true;
            btn.textContent = 'Creating...';
            const reason = document.getElementById('cn_reason').value.trim();
            const _amtEl = document.getElementById('cn_amount');
            const amount = _amtEl ? (parseFloat(_amtEl.value) || 0) : 0;
            try {
                const resp = await fetch('/api/supplier-invoice/' + _invId + '/credit-note', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({reason: reason, amount: amount})
                });
                const data = await resp.json();
                if (data.success) {
                    alert('Credit note ' + data.cn_number + ' created successfully.');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Credit note failed'));
                    btn.disabled = false;
                    btn.textContent = 'Create Credit Note';
                }
            } catch(e) {
                alert('Connection error: ' + e.message);
                btn.disabled = false;
                btn.textContent = 'Create Credit Note';
            }
        }
        
        async function confirmDeleteInvoice() {
            if (!confirm('Delete this invoice permanently?\\n\\nThis will:\\n• Reverse all stock changes\\n• Remove GL entries\\n• Delete the invoice record\\n\\nThis cannot be undone. Continue?')) return;
            try {
                const resp = await fetch('/api/supplier-invoice/' + _invId + '/delete', {method: 'POST'});
                const data = await resp.json();
                if (data.success) {
                    alert('Invoice deleted.');
                    window.location.href = '/supplier-invoices';
                } else {
                    alert('Error: ' + (data.error || 'Delete failed'));
                }
            } catch(e) {
                alert('Connection error: ' + e.message);
            }
        }
        
        // Close modals on backdrop click
        document.getElementById('editInvModal').addEventListener('click', function(e) { if (e.target === this) this.style.display = 'none'; });
        document.getElementById('cnModal').addEventListener('click', function(e) { if (e.target === this) this.style.display = 'none'; });
        </script>
        '''
        
        return render_page(f"Supplier Invoice {invoice.get('invoice_number', '')}", content, user, "purchases")
    

    # ════════════════════════════════════════════════════════════════════
    # SUPPLIER INVOICE: Edit / Credit Note / Delete
    # ════════════════════════════════════════════════════════════════════
    
    def _reverse_stock_from_snapshot(biz_id, snapshots):
        """
        Reverse the stock effects of a supplier invoice using its stored snapshot.
        Returns (success, message).
        
        For each snapshot entry:
          - action='updated': restore old_qty/cost/sell exactly (subtracts delta)
          - action='created': delete the stock_items row
        """
        if not snapshots:
            return True, "No stock snapshot to reverse"
        
        if isinstance(snapshots, str):
            try:
                snapshots = json.loads(snapshots)
            except Exception:
                return False, "Snapshot data corrupted"
        
        for snap in (snapshots or []):
            try:
                stock_id = snap.get("stock_id")
                action = snap.get("action", "updated")
                table = snap.get("table", "stock_items")
                
                if not stock_id:
                    continue
                
                if action == "created":
                    # This stock item was created by the invoice — delete it entirely
                    try:
                        db.delete(table, stock_id, biz_id)
                    except Exception as e:
                        logger.warning(f"[REVERSE] Could not delete created stock {stock_id}: {e}")
                else:
                    # Updated: restore old qty/cost/sell exactly
                    old_qty = float(snap.get("old_qty", 0) or 0)
                    old_cost = float(snap.get("old_cost", 0) or 0)
                    old_sell = float(snap.get("old_sell", 0) or 0)
                    
                    restore_payload = {
                        "id": stock_id,
                        "quantity": old_qty,
                        "qty": old_qty,
                        "cost_price": old_cost,
                        "cost": old_cost,
                    }
                    if old_sell > 0:
                        restore_payload["selling_price"] = old_sell
                        restore_payload["price"] = old_sell
                    db.save(table, restore_payload)
                    logger.info(f"[REVERSE] Restored stock {snap.get('code','?')}: qty={old_qty}, cost={old_cost}, sell={old_sell}")
            except Exception as e:
                logger.error(f"[REVERSE] Snapshot entry failed: {e}")
        
        return True, "Stock reversed"
    
    def _delete_invoice_journals(biz_id, inv_id):
        """Delete all journal entries linked to a supplier invoice by reference."""
        try:
            ref = f"INV-{inv_id[:8]}"
            all_journals = db.get("journals", {"business_id": biz_id}) if biz_id else []
            removed = 0
            for j in all_journals:
                if j.get("reference") == ref:
                    try:
                        db.delete("journals", j.get("id"), biz_id)
                        removed += 1
                    except Exception as e:
                        logger.warning(f"[REVERSE] Could not delete journal {j.get('id')}: {e}")
            logger.info(f"[REVERSE] Deleted {removed} journal entries for {ref}")
            return removed
        except Exception as e:
            logger.error(f"[REVERSE] _delete_invoice_journals failed: {e}")
            return 0
    
    def _legacy_reverse_stock_from_items(biz_id, items):
        """
        Best-effort stock reversal for legacy invoices without a snapshot.
        Subtracts the line item quantities from current stock.
        Does NOT restore cost/sell (we don't know what they were before).
        """
        if not items:
            return 0
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except Exception:
                return 0
        
        all_stock = db.get_all_stock(biz_id) if biz_id else []
        reversed_count = 0
        
        for item in (items or []):
            desc = (item.get("description") or "").strip().lower()
            qty = float(item.get("qty", item.get("quantity", 0)) or 0)
            pack_size = int(item.get("pack_size", 1) or 1)
            actual = qty * pack_size if pack_size > 1 and qty != pack_size else qty
            if not desc or actual <= 0:
                continue
            
            # Find the stock item by description (best effort)
            for s in all_stock:
                sd = (s.get("description") or "").strip().lower()
                if sd == desc or (desc and desc in sd) or (sd and sd in desc):
                    current_qty = float(s.get("quantity", s.get("qty", 0)) or 0)
                    new_qty = max(0, current_qty - actual)
                    table = "stock" if "code" in s and s.get("code") and not s.get("description","").startswith("__") else "stock_items"
                    try:
                        db.save(table, {"id": s["id"], "quantity": new_qty, "qty": new_qty})
                        reversed_count += 1
                    except Exception as e:
                        logger.warning(f"[REVERSE-LEGACY] Could not reverse stock {s.get('code')}: {e}")
                    break
        
        return reversed_count
    
    def _log_pulse_event(biz_id, user, event_type, summary, detail=""):
        """Add a pulse activity entry. Silent on failure."""
        try:
            db.save("activity_log", {
                "id": generate_id(),
                "business_id": biz_id,
                "type": event_type,
                "summary": summary,
                "detail": detail,
                "user_id": user.get("id") if user else None,
                "user_name": user.get("name") or user.get("email", "") if user else "System",
                "created_at": now()
            })
        except Exception:
            pass  # activity_log table may not exist; silent
    
    
    @app.route("/api/supplier-invoice/<invoice_id>/edit", methods=["POST"])
    @login_required
    def api_supplier_invoice_edit(invoice_id):
        """
        Edit a supplier invoice: reverses original stock/GL effects, then re-applies
        with new values. Requires a stored snapshot.
        """
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            invoice = db.get_one("supplier_invoices", invoice_id)
            if not invoice:
                return jsonify({"success": False, "error": "Invoice not found"})
            
            status = (invoice.get("status") or "").lower()
            if status in ("paid", "credited"):
                return jsonify({"success": False, "error": f"Cannot edit a {status} invoice — use a credit note instead"})
            
            # Check for linked payments
            all_payments = db.get("supplier_payments", {"business_id": biz_id}) if biz_id else []
            if any(p.get("invoice_id") == invoice_id or p.get("supplier_invoice_id") == invoice_id for p in all_payments):
                return jsonify({"success": False, "error": "Cannot edit an invoice with linked payments — use a credit note"})
            
            snapshots = invoice.get("stock_snapshots")
            if not snapshots:
                return jsonify({"success": False, "error": "No snapshot — this legacy invoice can only be reversed via a credit note"})
            
            data = request.get_json() or {}
            new_invoice_number = (data.get("invoice_number") or "").strip()
            new_date = (data.get("date") or "").strip() or invoice.get("date", today())
            new_items = data.get("items", [])
            new_subtotal = float(data.get("subtotal", 0) or 0)
            new_vat = float(data.get("vat", 0) or 0)
            new_total = float(data.get("total", 0) or 0)
            
            # STEP 1: Reverse the old effects
            _reverse_stock_from_snapshot(biz_id, snapshots)
            _delete_invoice_journals(biz_id, invoice_id)
            
            # STEP 2: Re-apply with new values
            all_stock = db.get_all_stock(biz_id) if biz_id else []
            new_snapshots = []
            
            for item in (new_items or []):
                desc = (item.get("description") or "").strip()
                qty = float(item.get("qty", item.get("quantity", 0)) or 0)
                unit_price = float(item.get("unit_price", item.get("price", 0)) or 0)
                line_total = float(item.get("line_total", qty * unit_price) or 0)
                
                if not desc or qty <= 0:
                    continue
                
                # Find existing stock by description (exact or contains)
                desc_lower = desc.lower().strip()
                matched = None
                for s in all_stock:
                    sd = (s.get("description") or "").strip().lower()
                    if sd == desc_lower:
                        matched = s
                        break
                if not matched:
                    for s in all_stock:
                        sd = (s.get("description") or "").strip().lower()
                        if sd and (desc_lower in sd or sd in desc_lower):
                            matched = s
                            break
                
                cost_per_unit = (line_total / qty) if qty > 0 else unit_price
                
                if matched:
                    old_qty = float(matched.get("quantity", matched.get("qty", 0)) or 0)
                    old_cost = float(matched.get("cost_price", matched.get("cost", 0)) or 0)
                    old_sell = float(matched.get("selling_price", matched.get("price", 0)) or 0)
                    new_qty = old_qty + qty
                    table = "stock" if matched in all_stock else "stock_items"
                    
                    new_snapshots.append({
                        "stock_id": matched["id"], "table": table,
                        "code": matched.get("code", ""), "description": matched.get("description", ""),
                        "old_qty": old_qty, "old_cost": old_cost, "old_sell": old_sell,
                        "delta_qty": qty, "new_cost": cost_per_unit, "action": "updated"
                    })
                    
                    update_payload = {
                        "id": matched["id"], "quantity": new_qty, "qty": new_qty,
                        "cost_price": cost_per_unit, "cost": cost_per_unit, "last_purchase_date": today()
                    }
                    if old_cost > 0 and old_sell > 0 and cost_per_unit > 0:
                        markup_ratio = old_sell / old_cost
                        new_sell = round(cost_per_unit * markup_ratio, 2)
                        update_payload["selling_price"] = new_sell
                        update_payload["price"] = new_sell
                    db.save(table, update_payload)
                else:
                    # Create new stock item
                    final_code = smart_stock_code(desc, set(s.get("code","").upper() for s in all_stock if s.get("code")))
                    new_stock = RecordFactory.stock_item(
                        business_id=biz_id, description=desc, code=final_code,
                        quantity=qty, cost_price=cost_per_unit, selling_price=round(cost_per_unit * 1.3, 2)
                    )
                    db.save_stock(new_stock)
                    new_snapshots.append({
                        "stock_id": new_stock["id"], "table": "stock_items",
                        "code": final_code, "description": desc,
                        "old_qty": 0, "old_cost": 0, "old_sell": 0,
                        "delta_qty": qty, "new_cost": cost_per_unit, "action": "created"
                    })
            
            # STEP 3: Re-create journal entries with new totals
            net_amount = new_total - new_vat
            supplier_name = invoice.get("supplier_name", "Unknown")
            
            # ══════════════════════════════════════════════════════════════
            # GL ALLOCATION on edit — preserve the invoice's stored intent.
            # If user changed allocation on edit (data['allocation_intent']),
            # apply the new choice. Otherwise reuse what was saved originally.
            # ══════════════════════════════════════════════════════════════
            _alloc_intent_new = (data.get("allocation_intent") or invoice.get("allocation_intent") or "stock").lower()
            if _alloc_intent_new not in ("stock", "cos", "split"):
                _alloc_intent_new = "stock"
            _item_allocs_raw = data.get("item_allocations")
            if _item_allocs_raw is None:
                _item_allocs_raw = invoice.get("item_allocations") or {}
            if isinstance(_item_allocs_raw, str):
                try:
                    _item_allocs_raw = json.loads(_item_allocs_raw)
                except Exception:
                    _item_allocs_raw = {}
            
            stock_dr = 0.0
            cos_dr = 0.0
            if _alloc_intent_new == "split" and _item_allocs_raw:
                for idx, item in enumerate(new_items or []):
                    line_total = float(item.get("line_total", 0) or 0)
                    if line_total <= 0:
                        _q = float(item.get("quantity", item.get("qty", 0)) or 0)
                        _p = float(item.get("unit_price", item.get("price", 0)) or 0)
                        _d = float(item.get("discount_pct", 0) or 0)
                        line_total = _q * _p * (1 - _d / 100.0)
                    line_net = line_total / 1.15 if new_vat > 0 else line_total
                    item_intent = (_item_allocs_raw.get(str(idx)) or _item_allocs_raw.get(idx) or "stock").lower()
                    if item_intent == "cos":
                        cos_dr += line_net
                    else:
                        stock_dr += line_net
                # Rounding adjustment
                total_alloc = round(stock_dr + cos_dr, 2)
                diff = round(net_amount - total_alloc, 2)
                if abs(diff) > 0:
                    if stock_dr >= cos_dr:
                        stock_dr += diff
                    else:
                        cos_dr += diff
            elif _alloc_intent_new == "cos":
                cos_dr = net_amount
            else:
                stock_dr = net_amount
            
            # Build journal lines (unpaid status is enforced at top — see line 4022)
            journal_lines_new = []
            if stock_dr > 0:
                journal_lines_new.append({"account_code": gl(biz_id, "stock"), "debit": round(stock_dr, 2), "credit": 0})
            if cos_dr > 0:
                journal_lines_new.append({"account_code": gl(biz_id, "cogs"), "debit": round(cos_dr, 2), "credit": 0})
            if new_vat > 0:
                journal_lines_new.append({"account_code": gl(biz_id, "vat_input"), "debit": round(new_vat, 2), "credit": 0})
            journal_lines_new.append({"account_code": gl(biz_id, "creditors"), "debit": 0, "credit": round(new_total, 2)})
            
            create_journal_entry(biz_id, new_date, f"Purchase - {supplier_name}", f"INV-{invoice_id[:8]}", journal_lines_new)
            
            # STEP 4: Update the invoice record
            update_inv = {
                "id": invoice_id,
                "invoice_number": new_invoice_number or invoice.get("invoice_number"),
                "date": new_date,
                "subtotal": new_subtotal,
                "vat": new_vat,
                "total": new_total,
                "items": json.dumps(new_items),
                "stock_snapshots": json.dumps(new_snapshots),
                "allocation_intent": _alloc_intent_new,
                "updated_at": now()
            }
            if _item_allocs_raw:
                update_inv["item_allocations"] = json.dumps(_item_allocs_raw) if not isinstance(_item_allocs_raw, str) else _item_allocs_raw
            db.save("supplier_invoices", update_inv)
            
            # Pulse log
            _log_pulse_event(biz_id, user, "supplier_invoice_edited",
                f"Edited invoice {new_invoice_number or invoice.get('invoice_number','?')} from {supplier_name}",
                f"New total: R{new_total:.2f}")
            
            # Allocation log
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_invoice_edited",
                        source_table="supplier_invoices", source_id=invoice_id,
                        description=f"Invoice edited - {supplier_name} - {new_invoice_number}",
                        amount=new_total, gl_entries=journal_lines_new,
                        ai_reasoning=f"User edited invoice. Allocation intent: {_alloc_intent_new}.",
                        ai_confidence="HIGH", ai_worker="System",
                        supplier_name=supplier_name, payment_method="account",
                        reference=new_invoice_number, transaction_date=new_date,
                        created_by=user.get("id") if user else "", created_by_name=user.get("name", "") if user else ""
                    )
            except Exception:
                pass
            
            return jsonify({"success": True, "invoice_id": invoice_id})
        except Exception as e:
            logger.exception(f"[EDIT SUPPLIER INVOICE] Failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/supplier-invoice/<invoice_id>/credit-note", methods=["POST"])
    @login_required
    def api_supplier_invoice_credit_note(invoice_id):
        """
        Create a credit note that fully reverses a supplier invoice.
        Works with or without a snapshot (legacy invoices get best-effort reversal).
        """
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            invoice = db.get_one("supplier_invoices", invoice_id)
            if not invoice:
                return jsonify({"success": False, "error": "Invoice not found"})
            
            if (invoice.get("status") or "").lower() == "credited":
                return jsonify({"success": False, "error": "Invoice already credited"})
            
            data = request.get_json() or {}
            reason = (data.get("reason") or "").strip() or "Reversal"
            
            supplier_id = invoice.get("supplier_id")
            supplier_name = invoice.get("supplier_name", "Unknown")
            inv_total = float(invoice.get("total", 0) or 0)
            inv_subtotal = float(invoice.get("subtotal", 0) or 0)
            inv_vat = float(invoice.get("vat", 0) or 0)
            
            # ── PARTIAL BY AMOUNT (value adjustment — NO goods returned) ──
            # Credits a specific Rand value (VAT-inclusive). Reverses only the value
            # and VAT, NOT stock quantities (we don't know which items/qty). For a
            # goods-return use the full credit. Falls through to FULL when no/!partial amount.
            try:
                _p_amt = round(float(data.get("amount", 0) or 0), 2)
            except Exception:
                _p_amt = 0.0
            if _p_amt > 0 and _p_amt < (inv_total - 0.01):
                _p_net = round(_p_amt / 1.15, 2) if inv_vat > 0 else _p_amt
                _p_vat = round(_p_amt - _p_net, 2) if inv_vat > 0 else 0.0
                _p_existing = db.get("supplier_credit_notes", {"business_id": biz_id}) if biz_id else []
                _p_cn_num = next_document_number("SCR-", _p_existing, field="cn_number")
                _p_cn_id = generate_id()
                _p_ref = f"SCR-{_p_cn_id[:8]}"
                _p_intent = (invoice.get("allocation_intent") or "stock").lower()
                _p_value_acc = gl(biz_id, "cogs") if _p_intent == "cos" else gl(biz_id, "stock")
                _p_lines = [{"account_code": _p_value_acc, "debit": 0, "credit": _p_net}]
                if _p_vat > 0:
                    _p_lines.append({"account_code": gl(biz_id, "vat_input"), "debit": 0, "credit": _p_vat})
                _p_lines.append({"account_code": gl(biz_id, "creditors"), "debit": _p_amt, "credit": 0})
                create_journal_entry(biz_id, today(), f"Credit Note (partial) - {supplier_name}", _p_ref, _p_lines)
                _p_record = {
                    "id": _p_cn_id, "business_id": biz_id, "supplier_id": supplier_id, "supplier_name": supplier_name,
                    "cn_number": _p_cn_num, "original_invoice_id": invoice_id, "date": today(),
                    "subtotal": _p_net, "vat": _p_vat, "total": _p_amt, "reason": reason,
                    "items": "[]", "status": "active", "stock_snapshots": "[]",
                    "credit_type": "amount",
                    "created_by": user.get("id") if user else None, "created_at": now()
                }
                _ps, _pr = db.save("supplier_credit_notes", _p_record)
                if not _ps:
                    logger.error(f"[CREDIT NOTE] Partial save failed: {_pr}")
                    return jsonify({"success": False, "error": f"Database error: {_pr}"})
                # Partial value credit → invoice stays open
                db.save("supplier_invoices", {"id": invoice_id, "status": "partial_credit", "updated_at": now()})
                try:
                    _log_pulse_event(biz_id, user, "supplier_credit_note_created",
                        f"Partial credit note {_p_cn_num} for {supplier_name}",
                        f"Partial value credit on invoice {invoice.get('invoice_number','?')} — R{_p_amt:.2f}. Reason: {reason}")
                except Exception:
                    pass
                try:
                    if log_allocation:
                        log_allocation(
                            business_id=biz_id, allocation_type="supplier_credit_note", source_table="supplier_credit_notes", source_id=_p_cn_id,
                            description=f"Supplier Credit Note {_p_cn_num} (partial amount) - {supplier_name}",
                            amount=_p_amt, gl_entries=_p_lines,
                            supplier_name=supplier_name, reference=_p_cn_num, transaction_date=today(),
                            created_by=user.get("id") if user else "", created_by_name=user.get("name", "") if user else "",
                            extra={"reason": reason, "credit_type": "amount", "original_invoice": invoice.get("invoice_number", "")}
                        )
                except Exception:
                    pass
                return jsonify({"success": True, "cn_number": _p_cn_num})
            
            # STEP 1: Reverse stock (snapshot if available, else legacy best-effort)
            snapshots = invoice.get("stock_snapshots")
            had_snapshot = bool(snapshots)
            if had_snapshot:
                _reverse_stock_from_snapshot(biz_id, snapshots)
                cn_snapshots = snapshots if isinstance(snapshots, str) else json.dumps(snapshots)
            else:
                # Legacy invoice — best-effort stock reversal
                items_raw = invoice.get("items", "[]")
                _legacy_reverse_stock_from_items(biz_id, items_raw)
                cn_snapshots = "[]"
            
            # STEP 2: Generate CN number
            existing_cns = db.get("supplier_credit_notes", {"business_id": biz_id}) if biz_id else []
            cn_number = next_document_number("SCR-", existing_cns, field="cn_number")
            
            # STEP 3: Create journal entries that REVERSE the original invoice
            # Reverse using the SAME GL codes the invoice originally debited.
            # Read allocation_intent from the invoice (defaults to 'stock').
            cn_id = generate_id()
            net_amount = inv_total - inv_vat
            cn_ref = f"SCR-{cn_id[:8]}"
            
            _cn_alloc_intent = (invoice.get("allocation_intent") or "stock").lower()
            if _cn_alloc_intent not in ("stock", "cos", "split"):
                _cn_alloc_intent = "stock"
            _cn_item_allocs = invoice.get("item_allocations") or {}
            if isinstance(_cn_item_allocs, str):
                try:
                    _cn_item_allocs = json.loads(_cn_item_allocs)
                except Exception:
                    _cn_item_allocs = {}
            
            cn_stock_cr = 0.0
            cn_cos_cr = 0.0
            if _cn_alloc_intent == "split" and _cn_item_allocs:
                _inv_items_raw = invoice.get("items") or "[]"
                if isinstance(_inv_items_raw, str):
                    try:
                        _inv_items_list = json.loads(_inv_items_raw)
                    except Exception:
                        _inv_items_list = []
                else:
                    _inv_items_list = _inv_items_raw
                for idx, item in enumerate(_inv_items_list or []):
                    line_total = float(item.get("line_total", 0) or 0)
                    if line_total <= 0:
                        _q = float(item.get("quantity", item.get("qty", 0)) or 0)
                        _p = float(item.get("unit_price", item.get("price", 0)) or 0)
                        _d = float(item.get("discount_pct", 0) or 0)
                        line_total = _q * _p * (1 - _d / 100.0)
                    line_net = line_total / 1.15 if inv_vat > 0 else line_total
                    item_intent = (_cn_item_allocs.get(str(idx)) or _cn_item_allocs.get(idx) or "stock").lower()
                    if item_intent == "cos":
                        cn_cos_cr += line_net
                    else:
                        cn_stock_cr += line_net
                total_alloc = round(cn_stock_cr + cn_cos_cr, 2)
                diff = round(net_amount - total_alloc, 2)
                if abs(diff) > 0:
                    if cn_stock_cr >= cn_cos_cr:
                        cn_stock_cr += diff
                    else:
                        cn_cos_cr += diff
            elif _cn_alloc_intent == "cos":
                cn_cos_cr = net_amount
            else:
                cn_stock_cr = net_amount
            
            cn_journal_lines = []
            if cn_stock_cr > 0:
                cn_journal_lines.append({"account_code": gl(biz_id, "stock"), "debit": 0, "credit": round(cn_stock_cr, 2)})
            if cn_cos_cr > 0:
                cn_journal_lines.append({"account_code": gl(biz_id, "cogs"), "debit": 0, "credit": round(cn_cos_cr, 2)})
            if inv_vat > 0:
                cn_journal_lines.append({"account_code": gl(biz_id, "vat_input"), "debit": 0, "credit": round(inv_vat, 2)})
            cn_journal_lines.append({"account_code": gl(biz_id, "creditors"), "debit": round(inv_total, 2), "credit": 0})
            
            create_journal_entry(biz_id, today(), f"Credit Note - {supplier_name}", cn_ref, cn_journal_lines)
            
            # STEP 4: Create credit note record
            cn_record = {
                "id": cn_id,
                "business_id": biz_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "cn_number": cn_number,
                "original_invoice_id": invoice_id,
                "date": today(),
                "subtotal": inv_subtotal,
                "vat": inv_vat,
                "total": inv_total,
                "reason": reason,
                "items": invoice.get("items", "[]") if isinstance(invoice.get("items"), str) else json.dumps(invoice.get("items", [])),
                "status": "active",
                "stock_snapshots": cn_snapshots,
                "created_by": user.get("id") if user else None,
                "created_at": now()
            }
            success, result = db.save("supplier_credit_notes", cn_record)
            if not success:
                logger.error(f"[CREDIT NOTE] Failed to save: {result}")
                return jsonify({"success": False, "error": f"Database error: {result}"})
            
            # STEP 5: Mark invoice as credited
            db.save("supplier_invoices", {"id": invoice_id, "status": "credited", "updated_at": now()})
            
            # Pulse log
            _log_pulse_event(biz_id, user, "supplier_credit_note_created",
                f"Credit note {cn_number} created for {supplier_name}",
                f"Reverses invoice {invoice.get('invoice_number','?')} — R{inv_total:.2f}. Reason: {reason}")
            
            # Allocation log
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_credit_note",
                        source_table="supplier_credit_notes", source_id=cn_id,
                        description=f"Credit Note {cn_number} - {supplier_name} - reverses {invoice.get('invoice_number','?')}",
                        amount=inv_total, gl_entries=cn_journal_lines,
                        ai_reasoning=f"Credit note reversing supplier invoice. Reason: {reason}. Snapshot available: {had_snapshot}.",
                        ai_confidence="HIGH", ai_worker="System",
                        supplier_name=supplier_name, payment_method="account",
                        reference=cn_number, transaction_date=today(),
                        created_by=user.get("id") if user else "", created_by_name=user.get("name", "") if user else ""
                    )
            except Exception:
                pass
            
            return jsonify({"success": True, "cn_number": cn_number, "cn_id": cn_id})
        except Exception as e:
            logger.exception(f"[CREDIT NOTE] Failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/supplier-invoice/<invoice_id>/delete", methods=["POST"])
    @login_required
    def api_supplier_invoice_delete(invoice_id):
        """
        Hard delete a supplier invoice. Reverses stock via snapshot, removes
        journal entries, deletes the invoice. Only for unpaid/uncredited
        invoices with no linked payments.
        """
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            invoice = db.get_one("supplier_invoices", invoice_id)
            if not invoice:
                return jsonify({"success": False, "error": "Invoice not found"})
            
            status = (invoice.get("status") or "").lower()
            if status in ("paid", "credited"):
                return jsonify({"success": False, "error": f"Cannot delete a {status} invoice — use credit note"})
            
            all_payments = db.get("supplier_payments", {"business_id": biz_id}) if biz_id else []
            if any(p.get("invoice_id") == invoice_id or p.get("supplier_invoice_id") == invoice_id for p in all_payments):
                return jsonify({"success": False, "error": "Cannot delete an invoice with linked payments"})
            
            snapshots = invoice.get("stock_snapshots")
            if not snapshots:
                return jsonify({"success": False, "error": "No snapshot — legacy invoices must be reversed via credit note"})
            
            supplier_name = invoice.get("supplier_name", "?")
            inv_number = invoice.get("invoice_number", "?")
            inv_total = float(invoice.get("total", 0) or 0)
            
            # STEP 1: Reverse stock
            _reverse_stock_from_snapshot(biz_id, snapshots)
            
            # STEP 2: Delete journal entries
            _delete_invoice_journals(biz_id, invoice_id)
            
            # STEP 3: Delete the invoice itself
            db.delete("supplier_invoices", invoice_id, biz_id)
            
            # Pulse log
            _log_pulse_event(biz_id, user, "supplier_invoice_deleted",
                f"Deleted invoice {inv_number} from {supplier_name}",
                f"Total R{inv_total:.2f} fully reversed (stock + GL).")
            
            # Allocation log
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_invoice_deleted",
                        source_table="supplier_invoices", source_id=invoice_id,
                        description=f"Invoice deleted - {supplier_name} - {inv_number}",
                        amount=inv_total, gl_entries=[],
                        ai_reasoning="User deleted invoice. Stock and GL fully reversed via snapshot.",
                        ai_confidence="HIGH", ai_worker="System",
                        supplier_name=supplier_name, payment_method="",
                        reference=inv_number, transaction_date=today(),
                        created_by=user.get("id") if user else "", created_by_name=user.get("name", "") if user else ""
                    )
            except Exception:
                pass
            
            return jsonify({"success": True})
        except Exception as e:
            logger.exception(f"[DELETE SUPPLIER INVOICE] Failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/supplier-credit-notes")
    @login_required
    def supplier_credit_notes_page():
        """List all supplier credit notes."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        cns = db.get("supplier_credit_notes", {"business_id": biz_id}) if biz_id else []
        cns = sorted(cns, key=lambda x: x.get("date", ""), reverse=True)
        
        rows = ""
        for cn in cns:
            cn_id = cn.get("id", "")
            inv_id = cn.get("original_invoice_id", "")
            inv_link = f'<a href="/supplier-invoice/{inv_id}" style="color:var(--primary);">View invoice</a>' if inv_id else "-"
            rows += f'''
            <tr>
                <td><a href="/supplier-credit-note/{cn_id}" style="color:var(--primary);font-weight:600;">{safe_string(cn.get("cn_number","-"))}</a></td>
                <td>{cn.get("date","-")}</td>
                <td>{safe_string(cn.get("supplier_name","-"))}</td>
                <td>{safe_string(cn.get("reason","-"))[:60]}</td>
                <td>{inv_link}</td>
                <td style="text-align:right;color:#f59e0b;font-weight:600;">-{money(cn.get("total",0))}</td>
            </tr>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <h2 style="margin:0;">↩️ Supplier Credit Notes ({len(cns)})</h2>
            <div style="display:flex;gap:10px;">
                <a href="/suppliers" class="btn btn-secondary" style="font-size:13px;padding:8px 14px;">👥 Suppliers</a>
                <a href="/supplier-invoices" class="btn btn-primary" style="font-size:13px;padding:8px 14px;">+ New Credit Note (from Invoice)</a>
            </div>
        </div>
        <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.25);border-radius:8px;padding:10px 14px;margin-bottom:15px;font-size:13px;color:var(--text-muted);">
            💡 <strong>How to create a credit note:</strong> Open the supplier invoice you want to credit → click the <strong style="color:#f59e0b;">↩️ Credit Note</strong> button. This reverses the invoice, returns stock, and posts the GL entries automatically.
        </div>
        <div class="card">
            <table class="table">
                <thead>
                    <tr><th>CN Number</th><th>Date</th><th>Supplier</th><th>Reason</th><th>Original Invoice</th><th style="text-align:right;">Amount</th></tr>
                </thead>
                <tbody>
                    {rows or '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:30px;">No credit notes yet</td></tr>'}
                </tbody>
            </table>
        </div>
        '''
        return render_page("Supplier Credit Notes", content, user, "purchases")
    
    
    @app.route("/supplier-credit-note/<cn_id>")
    @login_required
    def supplier_credit_note_view(cn_id):
        """View a single supplier credit note."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        cn = db.get_one("supplier_credit_notes", cn_id)
        if not cn:
            flash("Credit note not found", "error")
            return redirect("/supplier-credit-notes")
        
        # Parse items
        raw_items = cn.get("items", [])
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except Exception:
                raw_items = []
        
        items_html = ""
        for item in (raw_items or []):
            desc = safe_string(str(item.get("description", "-")))
            qty = float(item.get("qty", item.get("quantity", 1)) or 1)
            price = float(item.get("price", item.get("unit_price", 0)) or 0)
            total = float(item.get("total", item.get("line_total", qty * price)) or 0)
            items_html += f'''
            <tr>
                <td>{desc}</td>
                <td style="text-align:right;">{qty:.2f}</td>
                <td style="text-align:right;">{money(price)}</td>
                <td style="text-align:right;">{money(total)}</td>
            </tr>
            '''
        
        supplier_id = cn.get("supplier_id", "")
        supplier_name = safe_string(cn.get("supplier_name", "-"))
        orig_inv_id = cn.get("original_invoice_id", "")
        orig_inv = db.get_one("supplier_invoices", orig_inv_id) if orig_inv_id else None
        orig_link = ""
        if orig_inv:
            orig_link = f'<a href="/supplier-invoice/{orig_inv_id}" style="color:var(--primary);">{safe_string(orig_inv.get("invoice_number","-"))}</a>'
        
        back_link = f'/supplier/{supplier_id}' if supplier_id else '/supplier-credit-notes'
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="{back_link}" style="color:var(--text-muted);">← Back</a>
            <span style="padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;color:white;background:#f59e0b;">CREDIT NOTE</span>
        </div>
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div>
                    <h2 style="margin:0;color:#f59e0b;">↩️ Supplier Credit Note</h2>
                    <p style="font-size:20px;font-weight:bold;margin:5px 0;color:var(--primary);">{safe_string(cn.get("cn_number","-"))}</p>
                </div>
                <div style="text-align:right;">
                    <p style="color:var(--text-muted);margin:0;font-size:12px;">TOTAL CREDITED</p>
                    <p style="font-size:28px;font-weight:bold;margin:0;color:#f59e0b;">-{money(cn.get("total", 0))}</p>
                </div>
            </div>
            
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:15px;margin-top:20px;padding-top:15px;border-top:1px solid var(--border);">
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">SUPPLIER</span>
                    <span style="font-size:14px;">{"<a href=/supplier/" + supplier_id + " style=color:var(--primary)>" + supplier_name + "</a>" if supplier_id else supplier_name}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">DATE</span>
                    <span style="font-size:14px;">{cn.get("date", "-")}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">ORIGINAL INVOICE</span>
                    <span style="font-size:14px;">{orig_link or "-"}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">SUBTOTAL</span>
                    <span style="font-size:14px;">{money(cn.get("subtotal", 0))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">VAT (15%)</span>
                    <span style="font-size:14px;">{money(cn.get("vat", 0))}</span>
                </div>
                <div>
                    <span style="color:var(--text-muted);font-size:11px;display:block;">REASON</span>
                    <span style="font-size:14px;">{safe_string(cn.get("reason", "-"))}</span>
                </div>
            </div>
        </div>
        
        ''' + (f'''
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">Reversed Line Items</h3>
            <table class="table">
                <thead>
                    <tr><th>Description</th><th style="text-align:right;">Qty</th><th style="text-align:right;">Price</th><th style="text-align:right;">Total</th></tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>
        </div>
        ''' if items_html else '')
        
        return render_page(f"Credit Note {cn.get('cn_number','')}", content, user, "purchases")



    @app.route("/api/supplier/gl-suggest", methods=["POST"])
    @login_required
    def api_supplier_gl_suggest():
        """GL account suggestion — sends full account list to AI for smart matching"""
        try:
            data = request.get_json()
            desc = (data.get("description", "") or "").strip()
            supplier_name = (data.get("supplier_name", "") or "").strip()
            accounts = data.get("accounts", [])
            
            if not desc:
                return jsonify({"success": False, "suggestion": ""})
            
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return jsonify({"success": True, "suggestion": "?|AI not available — please select manually"})
            
            # Build account list for AI
            acc_list = "\n".join([f"{a['code']} = {a['name']}" for a in accounts if a.get('code') and a.get('name')])
            
            prompt = f"""You are a South African bookkeeper. A supplier invoice needs to be allocated to a GL account.

Supplier: {supplier_name}
Description: {desc}

Here are ALL available GL accounts:
{acc_list}

Which account code should this be allocated to? Pick the BEST match.
Reply with ONLY the account code, then a pipe |, then the account name.
Example: 3250/000|Cleaning
Nothing else."""

            try:
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 50,
                        "messages": [{"role": "user", "content": prompt}]
                    },
                    timeout=8
                )
                
                if resp.status_code == 200:
                    ai_text = resp.json().get("content", [{}])[0].get("text", "").strip()
                    if "|" in ai_text:
                        return jsonify({"success": True, "suggestion": ai_text})
                    else:
                        return jsonify({"success": True, "suggestion": f"?|{ai_text[:100]}"})
                else:
                    logger.error(f"[GL SUGGEST] AI error {resp.status_code}")
                    return jsonify({"success": True, "suggestion": "?|AI error — please select manually"})
                    
            except Exception as ai_err:
                logger.error(f"[GL SUGGEST] AI call failed: {ai_err}")
                return jsonify({"success": True, "suggestion": "?|AI timeout — please select manually"})
        
        except Exception as e:
            logger.error(f"[GL SUGGEST] Error: {e}")
            return jsonify({"success": False, "suggestion": ""})

    @app.route("/api/supplier/capture-invoice", methods=["POST"])
    @login_required
    def api_supplier_capture_invoice():
        """Capture a supplier invoice (diesel, stationery, etc.) with GL entries — no stock codes"""
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business"})
            
            data = request.get_json()
            supplier_id = data.get("supplier_id", "")
            supplier_name = data.get("supplier_name", "Unknown Supplier")
            invoice_number = data.get("invoice_number", "")
            inv_date = data.get("date", today())
            description = data.get("description", "")
            gl_code = data.get("gl_code", "7000")
            amount = float(data.get("amount", 0))
            vat_inclusive = data.get("vat_inclusive", True)
            is_paid = data.get("is_paid", False)
            
            if amount <= 0:
                return jsonify({"success": False, "error": "Amount must be greater than zero"})
            
            # Read supplier discount % from the database (not trusting client)
            discount_pct = 0.0
            if supplier_id:
                try:
                    _sup = db.get_one("suppliers", supplier_id)
                    if _sup:
                        discount_pct = float(_sup.get("discount_percentage", 0) or 0)
                except Exception:
                    discount_pct = 0.0
            
            # Calculate net, discount (on net, before VAT), then VAT on discounted net
            if vat_inclusive:
                gross_net = round(amount - round(amount * 15 / 115, 2), 2)
            else:
                gross_net = round(amount, 2)
            
            discount_amount = round(gross_net * discount_pct / 100, 2) if discount_pct > 0 else 0.0
            net_amount = round(gross_net - discount_amount, 2)
            vat_amount = round(net_amount * 0.15, 2)
            total_amount = round(net_amount + vat_amount, 2)
            
            # Generate invoice number if not provided
            if not invoice_number:
                existing = db.get("supplier_invoices", {"business_id": biz_id}) or []
                invoice_number = next_document_number("SINV", existing, "invoice_number")
            
            # Create supplier invoice record
            invoice = RecordFactory.supplier_invoice(
                business_id=biz_id,
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                invoice_number=invoice_number,
                date=inv_date,
                subtotal=net_amount,
                vat=vat_amount,
                total=total_amount,
                discount_percentage=discount_pct,
                discount_amount=discount_amount,
                status="paid" if is_paid else "outstanding",
                notes=description
            )
            inv_id = invoice["id"]
            
            success, err = db.save("supplier_invoices", invoice)
            if not success:
                return jsonify({"success": False, "error": f"Failed to save: {err}"})
            
            # Update supplier balance (if not paid, add to creditors)
            if supplier_id and not is_paid:
                # Supplier balance is now calculated dynamically — no manual update needed
                pass
            
            # Create GL journal entries
            try:
                # Ensure the Discount Received account exists for this business
                # (auto-creates it if missing — platform-wide, no manual SQL).
                _disc_recv_code = None
                if discount_amount > 0:
                    try:
                        import clickai as _main
                        _disc_recv_code = _main.ensure_gl_account(biz_id, "discount_received", "Discount Received", "income", "Other Income")
                    except Exception:
                        _disc_recv_code = gl(biz_id, "discount_received")
                if is_paid:
                    # Already paid: Debit Expense (full net) + VAT Input, Credit Discount Received + Bank
                    journal_entries = [
                        {"account_code": gl_code, "debit": gross_net, "credit": 0},
                    ]
                    if vat_amount > 0:
                        journal_entries.append({"account_code": gl(biz_id, "vat_input"), "debit": vat_amount, "credit": 0})
                    if discount_amount > 0:
                        journal_entries.append({"account_code": _disc_recv_code, "debit": 0, "credit": discount_amount})
                    journal_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": total_amount})
                else:
                    # On account: Debit Expense (full net) + VAT Input, Credit Discount Received + Creditors
                    journal_entries = [
                        {"account_code": gl_code, "debit": gross_net, "credit": 0},
                    ]
                    if vat_amount > 0:
                        journal_entries.append({"account_code": gl(biz_id, "vat_input"), "debit": vat_amount, "credit": 0})
                    if discount_amount > 0:
                        journal_entries.append({"account_code": _disc_recv_code, "debit": 0, "credit": discount_amount})
                    journal_entries.append({"account_code": gl(biz_id, "creditors"), "debit": 0, "credit": total_amount})
                
                create_journal_entry(biz_id, inv_date, f"{description or supplier_name} - {invoice_number}", invoice_number, journal_entries)
                logger.info(f"[CAPTURE INV] GL entries created: {gl_code} DR:{gross_net} disc:{discount_amount} for {supplier_name}")
            except Exception as e:
                logger.error(f"[CAPTURE INV] GL entry error (invoice still saved): {e}")
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_invoice", source_table="supplier_invoices", source_id=inv_id,
                        description=f"{description or supplier_name} - {invoice_number}",
                        amount=total_amount, gl_entries=journal_entries if 'journal_entries' in dir() else [],
                        category="Supplier Invoice", category_code=gl_code,
                        supplier_name=supplier_name, payment_method="account" if not is_paid else "paid",
                        reference=invoice_number, transaction_date=inv_date,
                        created_by=user.get("id", ""), created_by_name=user.get("name", "")
                    )
            except Exception:
                pass
            
            return jsonify({
                "success": True,
                "message": f"Invoice {invoice_number} saved — R{total_amount:,.2f} ({description or supplier_name})",
                "invoice_id": inv_id
            })
            
        except Exception as e:
            logger.error(f"[CAPTURE INV] Error: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/supplier/record-payment", methods=["POST"])
    @login_required
    def api_supplier_record_payment():
        """Record a payment to a supplier — reduces balance, creates GL journal"""
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business"})
            
            data = request.get_json()
            supplier_id = data.get("supplier_id", "")
            supplier_name = data.get("supplier_name", "Unknown")
            amount = float(data.get("amount", 0))
            method = data.get("method", "eft")
            pay_date = data.get("date", today())
            reference = data.get("reference", "")
            
            if amount <= 0:
                return jsonify({"success": False, "error": "Amount must be greater than zero"})
            
            # ── First pass: validate allocations, split any settlement discount ──
            # Each allocation: {supplier_invoice_id, amount (cash), discount (taken)}.
            # A discount is honoured only on an invoice booked at FULL value at capture
            # (discount_amount == 0), so we never double-discount. It is split into net +
            # VAT by the invoice's own net:VAT ratio; the VAT portion reverses the
            # over-claimed input VAT — same treatment as the capture-time discount.
            allocations = data.get("allocations", []) or []
            _processed = []
            total_disc = 0.0
            total_disc_net = 0.0
            total_disc_vat = 0.0
            for _alloc in allocations:
                _sid = (_alloc.get("supplier_invoice_id", "") or "").strip()
                try:
                    _cash = round(float(_alloc.get("amount", 0) or 0), 2)
                except Exception:
                    _cash = 0.0
                try:
                    _disc = round(float(_alloc.get("discount", 0) or 0), 2)
                except Exception:
                    _disc = 0.0
                if not _sid or (_cash <= 0 and _disc <= 0):
                    continue
                _sinv = db.get_one("supplier_invoices", _sid)
                if not _sinv or _sinv.get("business_id") != biz_id:
                    continue
                if _disc > 0 and round(float(_sinv.get("discount_amount", 0) or 0), 2) > 0:
                    _disc = 0.0   # already discounted at capture — never discount twice
                if _disc > 0:
                    # A settlement discount may only be taken once per invoice —
                    # block a second discounted payment against the same invoice
                    try:
                        _prev_allocs = db.get("supplier_payment_allocations", {"business_id": biz_id, "supplier_invoice_id": _sid}) or []
                        if any(float(_pa.get("discount", 0) or 0) > 0 for _pa in _prev_allocs):
                            _disc = 0.0
                    except Exception:
                        pass
                if _disc > 0:
                    # Cash + discount may never settle more than the invoice's
                    # outstanding amount — cap the discount, never the cash
                    try:
                        _outst = round(float(_sinv.get("total", 0) or 0) - float(_sinv.get("amount_paid", 0) or 0), 2)
                        _disc = min(_disc, max(0.0, round(_outst - _cash, 2)))
                    except Exception:
                        pass
                _dnet = 0.0
                _dvat = 0.0
                if _disc > 0:
                    _itot = round(float(_sinv.get("total", 0) or 0), 2)
                    _ivat = round(float(_sinv.get("vat", 0) or 0), 2)
                    if _itot > 0 and _ivat > 0:
                        _dvat = round(_disc * _ivat / _itot, 2)
                    _dnet = round(_disc - _dvat, 2)
                _processed.append({"id": _sid, "inv": _sinv, "cash": _cash, "disc": _disc,
                                   "disc_net": _dnet, "disc_vat": _dvat, "settled": round(_cash + _disc, 2)})
                total_disc = round(total_disc + _disc, 2)
                total_disc_net = round(total_disc_net + _dnet, 2)
                total_disc_vat = round(total_disc_vat + _dvat, 2)
            
            # Save supplier payment record
            payment = {
                "id": generate_id(),
                "business_id": biz_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "amount": round(amount, 2),
                "discount_total": round(total_disc, 2),
                "date": pay_date,
                "method": method,
                "reference": reference,
                "source": "manual",
                "created_at": now()
            }
            
            success, err = db.save("supplier_payments", payment)
            if not success:
                return jsonify({"success": False, "error": f"Failed to save payment: {err}"})
            
            # Supplier balance is now calculated dynamically — no manual update needed
            
            # GL journal. Without discount: DR Creditors / CR Bank (cash).
            # With settlement discount: DR Creditors (cash + discount settled),
            # CR Bank (cash), CR Discount Received (net), CR VAT Input (discount VAT).
            rounded = round(amount, 2)
            ref_label = reference or f"PAY-{payment['id'][:8]}"
            if method == "cash":
                bank_code = gl(biz_id, "cash")
            else:
                bank_code = gl(biz_id, "bank")
            _disc_recv_code = None
            if total_disc_net > 0:
                try:
                    import clickai as _main
                    _disc_recv_code = _main.ensure_gl_account(biz_id, "discount_received", "Discount Received", "income", "Other Income")
                except Exception:
                    _disc_recv_code = gl(biz_id, "discount_received")
            _gl_lines = [
                {"account_code": gl(biz_id, "creditors"), "debit": round(rounded + total_disc, 2), "credit": 0},
                {"account_code": bank_code, "debit": 0, "credit": rounded},
            ]
            if total_disc_net > 0:
                _gl_lines.append({"account_code": _disc_recv_code, "debit": 0, "credit": round(total_disc_net, 2)})
            if total_disc_vat > 0:
                _gl_lines.append({"account_code": gl(biz_id, "vat_input"), "debit": 0, "credit": round(total_disc_vat, 2)})
            try:
                create_journal_entry(biz_id, pay_date, f"Payment to {supplier_name}", ref_label, _gl_lines)
                logger.info(f"[PAY] GL: Creditors DR:{round(rounded + total_disc, 2)}, Bank CR:{rounded}, disc_net:{total_disc_net}, disc_vat:{total_disc_vat} for {supplier_name}")
            except Exception as e:
                logger.error(f"[PAY] GL entry error (payment still saved): {e}")
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_payment", source_table="supplier_payments", source_id=payment["id"],
                        description=f"Payment to {supplier_name}",
                        amount=round(amount, 2),
                        gl_entries=_gl_lines,
                        category="Supplier Payment", category_code=gl(biz_id, "creditors"),
                        supplier_name=supplier_name, payment_method=method,
                        reference=reference or ref_label, transaction_date=pay_date,
                        created_by=user.get("id", ""), created_by_name=user.get("name", "")
                    )
            except Exception:
                pass
            
            # ── Save invoice allocations. Each invoice is settled by cash + discount
            # (so it clears in full); the discount was booked in the journal above. ──
            allocated_cash = 0.0
            allocated_count = 0
            for _p in _processed:
                if _p["settled"] <= 0:
                    continue
                alloc_row = {
                    "id": generate_id(),
                    "business_id": biz_id,
                    "supplier_payment_id": payment["id"],
                    "supplier_invoice_id": _p["id"],
                    "invoice_number": _p["inv"].get("invoice_number", ""),
                    "supplier_id": supplier_id,
                    "supplier_name": supplier_name,
                    "amount": _p["settled"],
                    "cash_amount": _p["cash"],
                    "discount": _p["disc"],
                    "date": pay_date,
                    "created_at": now()
                }
                ok_alloc, alloc_err = db.save("supplier_payment_allocations", alloc_row)
                if not ok_alloc:
                    logger.error(f"[PAY] Allocation save failed for {_p['id']}: {alloc_err}")
                    continue
                allocated_cash += _p["cash"]
                allocated_count += 1
                recalc_supplier_invoice_status(biz_id, _p["id"])
            
            unallocated = round(rounded - allocated_cash, 2)
            if allocated_count > 0:
                _msg = (f"Payment of R{amount:,.2f} to {supplier_name} recorded "
                        f"({method.upper()}) — allocated to {allocated_count} invoice(s)")
                if total_disc > 0.005:
                    _msg += f", R{total_disc:,.2f} settlement discount taken"
                if unallocated > 0.005:
                    _msg += f", R{unallocated:,.2f} left on account"
            else:
                _msg = (f"Payment of R{amount:,.2f} to {supplier_name} recorded "
                        f"({method.upper()}) — on account, not allocated")
            
            return jsonify({"success": True, "message": _msg})
            
        except Exception as e:
            logger.error(f"[PAY] Error: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/supplier-payment/<payment_id>/remittance")
    @login_required
    def supplier_payment_remittance(payment_id):
        """Printable remittance advice for one supplier payment — shows which
        supplier invoices the payment was allocated to (from Stuk A's
        supplier_payment_allocations table)."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return redirect("/suppliers")
        
        payment = db.get_one("supplier_payments", payment_id)
        if not payment or payment.get("business_id") != biz_id:
            return redirect("/suppliers")
        
        supplier_name = payment.get("supplier_name", "Supplier")
        supplier_id = payment.get("supplier_id", "")
        pay_amount = round(float(payment.get("amount", 0) or 0), 2)
        pay_date = payment.get("date", "-")
        pay_method = (payment.get("method", "-") or "-").upper()
        pay_ref = payment.get("reference", "") or f"PAY-{payment_id[:8]}"
        
        biz_name = business.get("name", "Business") if business else "Business"
        biz_addr = business.get("address", "") if business else ""
        
        # Allocations for this payment
        allocs = db.get("supplier_payment_allocations",
                        {"business_id": biz_id, "supplier_payment_id": payment_id}) or []
        
        alloc_rows = ""
        allocated_total = 0.0
        for a in allocs:
            amt = round(float(a.get("amount", 0) or 0), 2)
            allocated_total += amt
            alloc_rows += f'''
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 0;color:#444;">{safe_string(a.get("invoice_number", "-"))}</td>
                <td style="padding:8px 0;text-align:right;color:#444;">{money(amt)}</td>
            </tr>
            '''
        allocated_total = round(allocated_total, 2)
        # Allocations settle cash + settlement discount; show the discount as
        # its own line so the cash paid reconciles to the allocations
        _rem_disc = round(sum(float(a.get("discount", 0) or 0) for a in allocs), 2)
        if _rem_disc > 0.005:
            alloc_rows += f'''
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 0;color:#444;font-style:italic;">Less: settlement discount</td>
                <td style="padding:8px 0;text-align:right;color:#444;font-style:italic;">-{money(_rem_disc)}</td>
            </tr>
            '''
        on_account = round(pay_amount + _rem_disc - allocated_total, 2)
        
        if not alloc_rows:
            alloc_rows = '<tr><td colspan="2" style="padding:8px 0;color:#888;text-align:center;">This payment was not allocated to specific invoices — it is on the supplier account.</td></tr>'
        
        on_account_row = ""
        if on_account > 0:
            on_account_row = f'''
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 0;color:#888;font-style:italic;">On account (unallocated)</td>
                <td style="padding:8px 0;text-align:right;color:#888;font-style:italic;">{money(on_account)}</td>
            </tr>
            '''
        
        content = f'''
        <style>
            @media print {{
                .no-print {{ display: none !important; }}
                nav, header, .header, .header-top, .nav-wrapper, .nav, .mobile-nav, .nav-tap-hint, .sidebar {{ display: none !important; }}
                body {{ background: white !important; color: black !important; }}
                #printArea {{ display: block !important; }}
                @page {{ size: A4; margin: 14mm; }}
            }}
        </style>
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/supplier/{supplier_id}" style="color:var(--text-muted);">← Back to Supplier</a>
            <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
        </div>
        
        <div id="printArea">
        <div class="card" style="background:white;color:#333;max-width:700px;margin:0 auto;padding:30px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #333;">
                <div>
                    <h2 style="color:#333;margin:0;font-size:17px;">{safe_string(biz_name)}</h2>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">{safe_string(biz_addr)}</p>
                </div>
                <div style="text-align:right;">
                    <h1 style="color:#333;margin:0;font-size:20px;">REMITTANCE ADVICE</h1>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">Date: {pay_date}</p>
                </div>
            </div>
            
            <table style="width:100%;font-size:12px;color:#444;margin-bottom:20px;">
                <tr>
                    <td style="padding:3px 0;width:50%;"><strong>To:</strong> {safe_string(supplier_name)}</td>
                    <td style="padding:3px 0;"><strong>Payment Reference:</strong> {safe_string(pay_ref)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Payment Method:</strong> {pay_method}</td>
                    <td style="padding:3px 0;"><strong>Payment Date:</strong> {pay_date}</td>
                </tr>
            </table>
            
            <p style="color:#444;font-size:13px;margin-bottom:8px;">The following payment has been made to your account:</p>
            
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <thead>
                    <tr style="border-bottom:2px solid #333;">
                        <th style="padding:7px 0;text-align:left;color:#333;">Invoice</th>
                        <th style="padding:7px 0;text-align:right;color:#333;">Amount Paid</th>
                    </tr>
                </thead>
                <tbody>
                    {alloc_rows}
                    {on_account_row}
                </tbody>
            </table>
            
            <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:#10b981;border-radius:8px;color:white;margin-top:18px;">
                <span style="font-size:15px;font-weight:bold;">TOTAL PAID</span>
                <span style="font-size:22px;font-weight:bold;">{money(pay_amount)}</span>
            </div>
            
            <div style="margin-top:20px;text-align:center;color:#999;font-size:10px;">
                Generated by ClickAI · Computer-generated remittance advice · {pay_date}
            </div>
        </div>
        </div>
        '''
        return render_page("Remittance Advice", content, user, "suppliers")

    # ── Supplier statement helpers (month-based opening balance + aging) ──
    def _supplier_statement_period(month_param):
        """Resolve a supplier statement month to (month_str 'YYYY-MM',
        period_start 'YYYY-MM-01', asat last-day-of-month). Defaults to the
        CURRENT month when month_param is blank/invalid."""
        import clickai as _main
        month_str, asat = _main._statement_asat(month_param or "", default_current=True)
        return month_str, month_str + "-01", asat

    def _build_supplier_statement_block(business, sup, s_invoices, s_payments, s_cns, period_start, asat):
        """Build ONE supplier's printable statement page: FROM/TO header, an
        Opening Balance line (net of everything before the 1st of the month),
        that month's transactions, and an aging block (each outstanding invoice
        aged by its term-derived due date vs the month-end). Returns
        (block_html, amount_due)."""
        sup_name = sup.get("name", "")

        biz_name = business.get("business_name") or business.get("name", "Business")
        biz_vat = business.get("vat_number", "") or ""
        biz_addr = safe_string(business.get("address", "") or "").replace("\n", "<br>")
        biz_phone = business.get("phone", "") or ""

        # Ledger items: invoices = we owe (credit), payments + credit notes reduce (debit)
        ledger = []
        for si in s_invoices:
            if si.get("status") == "cancelled":
                continue
            ledger.append({
                "date": si.get("date", ""),
                "type": "Invoice",
                "reference": si.get("invoice_number", "-"),
                "debit": 0.0,
                "credit": float(si.get("total", 0) or 0),
            })
        for p in s_payments:
            ledger.append({
                "date": p.get("date", ""),
                "type": "Payment",
                "reference": p.get("reference", "") or p.get("payment_number", "-"),
                "debit": float(p.get("amount", 0) or 0),
                "credit": 0.0,
            })
            # Settlement discount taken with this payment — its own debit line
            _p_disc = float(p.get("discount_total", 0) or 0)
            if _p_disc > 0.005:
                ledger.append({
                    "date": p.get("date", ""),
                    "type": "Settlement Discount",
                    "reference": p.get("reference", "") or p.get("payment_number", "-"),
                    "debit": _p_disc,
                    "credit": 0.0,
                })
        for c in s_cns:
            ledger.append({
                "date": c.get("date", ""),
                "type": "Credit Note",
                "reference": c.get("cn_number", "-"),
                "debit": float(c.get("total", 0) or 0),
                "credit": 0.0,
            })

        ledger.sort(key=lambda x: x.get("date", ""))
        # Close the statement at the selected month-end
        ledger = [it for it in ledger if (it.get("date") or "")[:10] <= asat]

        # Opening balance = net of everything dated before the 1st of the month
        opening_balance = 0.0
        current = []
        for it in ledger:
            if (it.get("date") or "")[:10] < period_start:
                opening_balance += it["credit"] - it["debit"]
            else:
                current.append(it)
        opening_balance = round(opening_balance, 2)

        running = opening_balance
        rows_html = ""
        if abs(opening_balance) > 0.005:
            rows_html += f'''
                <tr>
                    <td>{period_start}</td>
                    <td></td>
                    <td><em>Opening Balance</em></td>
                    <td style="text-align:right;">-</td>
                    <td style="text-align:right;">-</td>
                    <td style="text-align:right;font-weight:bold;">{money(running)}</td>
                </tr>'''
        for it in current:
            running = round(running + it["credit"] - it["debit"], 2)
            rows_html += f'''
                <tr>
                    <td>{it["date"] or "-"}</td>
                    <td>{safe_string(it["type"])}</td>
                    <td>{safe_string(it["reference"])}</td>
                    <td style="text-align:right;">{money(it["debit"]) if it["debit"] else "-"}</td>
                    <td style="text-align:right;">{money(it["credit"]) if it["credit"] else "-"}</td>
                    <td style="text-align:right;font-weight:bold;">{money(running)}</td>
                </tr>'''
        amount_due = running

        # Aging: each outstanding invoice aged by its term due date vs the month-end
        buckets = {"current": 0.0, "d30": 0.0, "d60": 0.0, "d90": 0.0, "d120": 0.0}
        try:
            asat_d = datetime.strptime(asat, "%Y-%m-%d").date()
        except Exception:
            asat_d = datetime.now().date()
        for si in s_invoices:
            if si.get("status") == "cancelled":
                continue
            if (si.get("date") or "")[:10] > asat:
                continue
            try:
                outstanding = round(float(si.get("total", 0) or 0) - float(si.get("amount_paid", 0) or 0), 2)
            except Exception:
                outstanding = 0.0
            if outstanding <= 0.01:
                continue
            age_ref = (si.get("due_date") or si.get("date") or "")[:10]
            try:
                age = (asat_d - datetime.strptime(age_ref, "%Y-%m-%d").date()).days
            except Exception:
                age = 0
            if age <= 30:
                buckets["current"] += outstanding
            elif age <= 60:
                buckets["d30"] += outstanding
            elif age <= 90:
                buckets["d60"] += outstanding
            elif age <= 120:
                buckets["d90"] += outstanding
            else:
                buckets["d120"] += outstanding

        sup_vat = sup.get("vat_number", "") or ""
        sup_addr = safe_string(sup.get("address", "") or "").replace("\n", "<br>")
        sup_terms = sup.get("payment_terms", "") or ""
        try:
            _mlabel = datetime.strptime(period_start, "%Y-%m-%d").strftime("%B %Y")
        except Exception:
            _mlabel = period_start[:7]

        block = f'''
            <div class="stmt-page">
                <div style="display:flex;justify-content:space-between;margin-bottom:16px;">
                    <div style="width:48%;">
                        <div style="font-size:10px;color:#888;">FROM</div>
                        <div style="font-weight:bold;font-size:14px;">{safe_string(biz_name)}</div>
                        <div style="font-size:11px;color:#444;">{("VAT No: " + safe_string(biz_vat)) if biz_vat else ""}</div>
                        <div style="font-size:11px;color:#444;">{biz_addr}</div>
                        <div style="font-size:11px;color:#444;">{("Tel: " + safe_string(biz_phone)) if biz_phone else ""}</div>
                    </div>
                    <div style="width:48%;">
                        <div style="font-size:10px;color:#888;">TO</div>
                        <div style="font-weight:bold;font-size:14px;">{safe_string(sup_name)}</div>
                        <div style="font-size:11px;color:#444;">{("Supplier VAT No: " + safe_string(sup_vat)) if sup_vat else ""}</div>
                        <div style="font-size:11px;color:#444;">{sup_addr}</div>
                        <div style="font-size:11px;color:#444;">{("Terms: " + safe_string(sup_terms)) if sup_terms else ""}</div>
                    </div>
                </div>
                <div style="text-align:center;font-weight:bold;font-size:15px;margin-bottom:4px;">STATEMENT OF ACCOUNT</div>
                <div style="text-align:center;font-size:11px;color:#666;margin-bottom:12px;">{_mlabel} &middot; As at {asat}</div>
                <table style="width:100%;border-collapse:collapse;font-size:11px;">
                    <thead>
                        <tr style="border-bottom:2px solid #333;">
                            <th style="text-align:left;padding:5px;">Date</th>
                            <th style="text-align:left;padding:5px;">Type</th>
                            <th style="text-align:left;padding:5px;">Reference</th>
                            <th style="text-align:right;padding:5px;">Debit</th>
                            <th style="text-align:right;padding:5px;">Credit</th>
                            <th style="text-align:right;padding:5px;">Balance</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html or '<tr><td colspan="6" style="text-align:center;color:#888;padding:10px;">No transactions</td></tr>'}
                    </tbody>
                </table>
                <table style="width:100%;border-collapse:collapse;font-size:11px;margin-top:16px;border-top:2px solid #333;">
                    <thead>
                        <tr>
                            <th style="text-align:right;padding:5px;">120+ Days</th>
                            <th style="text-align:right;padding:5px;">90 Days</th>
                            <th style="text-align:right;padding:5px;">60 Days</th>
                            <th style="text-align:right;padding:5px;">30 Days</th>
                            <th style="text-align:right;padding:5px;">Current</th>
                            <th style="text-align:right;padding:5px;background:#f0f0f0;">Amount Due</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="text-align:right;padding:5px;">{money(buckets["d120"])}</td>
                            <td style="text-align:right;padding:5px;">{money(buckets["d90"])}</td>
                            <td style="text-align:right;padding:5px;">{money(buckets["d60"])}</td>
                            <td style="text-align:right;padding:5px;">{money(buckets["d30"])}</td>
                            <td style="text-align:right;padding:5px;">{money(buckets["current"])}</td>
                            <td style="text-align:right;padding:5px;font-weight:bold;background:#f0f0f0;">{money(amount_due)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>'''
        return block, amount_due


    @app.route("/supplier-statements/print")
    @login_required
    def supplier_statements_print():
        """Bulk printable supplier statements — one statement per supplier with
        an outstanding balance, each on its own page. Sage-style layout:
        FROM/TO header, an Opening Balance line (everything before the 1st of the
        month), the month's transactions, and an aging block at the foot.
        ?month=YYYY-MM opens any past month (default: current month). Print only."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return redirect("/suppliers")
        
        # Load all data once
        suppliers = db.get("suppliers", {"business_id": biz_id}) or []
        all_sinvoices = db.get("supplier_invoices", {"business_id": biz_id}) or []
        all_payments = db.get("supplier_payments", {"business_id": biz_id}) or []
        all_cns = db.get("supplier_credit_notes", {"business_id": biz_id}) or []
        
        _stmt_month, _period_start, _asat = _supplier_statement_period(request.args.get("month"))

        # Build one statement block per supplier with an outstanding balance
        statements_html = ""
        statement_count = 0

        for sup in sorted(suppliers, key=lambda x: (x.get("name") or "").upper()):
            sup_id = sup.get("id", "")
            sup_name_upper = (sup.get("name") or "").upper().strip()

            s_invoices = [si for si in all_sinvoices if si.get("supplier_id") == sup_id]
            s_payments = [p for p in all_payments if
                          p.get("supplier_id") == sup_id or
                          (not p.get("supplier_id") and sup_name_upper and
                           (p.get("supplier_name") or "").upper().strip() == sup_name_upper)]
            s_cns = [c for c in all_cns if c.get("supplier_id") == sup_id
                     and (c.get("status") or "active") == "active"]

            block, amount_due = _build_supplier_statement_block(
                business, sup, s_invoices, s_payments, s_cns, _period_start, _asat)

            # Skip suppliers with no outstanding balance for this period
            if amount_due <= 0.009:
                continue

            statement_count += 1
            statements_html += block

        if statement_count == 0:
            statements_html = '<div style="text-align:center;padding:40px;color:#888;">No suppliers with an outstanding balance.</div>'
        
        import clickai as _main
        _month_options = _main._statement_month_options(_stmt_month)
        
        content = f'''
        <style>
            @media print {{
                .no-print {{ display: none !important; }}
                nav, header, .header, .header-top, .nav-wrapper, .nav, .mobile-nav, .nav-tap-hint, .sidebar, .j-hero, .j-hud-wrap, .j-hud-pad, .j-tl {{ display: none !important; }}
                body {{ background: white !important; color: black !important; }}
                #printArea {{ display: block !important; }}
                .stmt-page + .stmt-page {{ page-break-before: always !important; }}
                @page {{ size: A4; margin: 14mm; }}
            }}
            .stmt-page {{ background:white; color:#333; padding:20px; margin:0 auto 30px; max-width:760px; border:1px solid #ddd; }}
        </style>
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/suppliers" style="color:var(--text-muted);">← Back to Suppliers</a>
            <div style="display:flex;align-items:center;gap:10px;">
                <select onchange="if(this.value)window.location='/supplier-statements/print?month='+this.value;" style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">{_month_options}</select>
                <span style="color:var(--text-muted);font-size:13px;">{statement_count} statement(s)</span>
                <button class="btn btn-secondary" onclick="window.print();">🖨️ Print All</button>
            </div>
        </div>
        <div id="printArea">
            {statements_html}
        </div>
        '''
        return render_page("Supplier Statements", content, user, "suppliers")

    @app.route("/supplier-statement/<supplier_id>/print")
    @login_required
    def supplier_statement_print(supplier_id):
        """Printable statement of account for ONE supplier: opening balance on the
        1st of the selected month, that month's transactions, and an aging block.
        ?month=YYYY-MM opens any past month (default: current month)."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return redirect("/suppliers")

        supplier = db.get_one("suppliers", supplier_id)
        if not supplier:
            return redirect("/suppliers")

        _stmt_month, _period_start, _asat = _supplier_statement_period(request.args.get("month"))

        sup_name_upper = (supplier.get("name") or "").upper().strip()
        all_sinvoices = db.get("supplier_invoices", {"business_id": biz_id}) or []
        all_payments = db.get("supplier_payments", {"business_id": biz_id}) or []
        all_cns = db.get("supplier_credit_notes", {"business_id": biz_id}) or []

        s_invoices = [si for si in all_sinvoices if si.get("supplier_id") == supplier_id]
        s_payments = [p for p in all_payments if
                      p.get("supplier_id") == supplier_id or
                      (not p.get("supplier_id") and sup_name_upper and
                       (p.get("supplier_name") or "").upper().strip() == sup_name_upper)]
        s_cns = [c for c in all_cns if c.get("supplier_id") == supplier_id
                 and (c.get("status") or "active") == "active"]

        block, amount_due = _build_supplier_statement_block(
            business, supplier, s_invoices, s_payments, s_cns, _period_start, _asat)

        import clickai as _main
        _month_options = _main._statement_month_options(_stmt_month)

        content = f'''
        <style>
            @media print {{
                .no-print {{ display: none !important; }}
                nav, header, .header, .header-top, .nav-wrapper, .nav, .mobile-nav, .nav-tap-hint, .sidebar, .j-hero, .j-hud-wrap, .j-hud-pad, .j-tl {{ display: none !important; }}
                body {{ background: white !important; color: black !important; }}
                #printArea {{ display: block !important; }}
                .stmt-page {{ page-break-after: always; }}
                .stmt-page:last-child {{ page-break-after: auto; }}
                @page {{ size: A4; margin: 14mm; }}
            }}
            .stmt-page {{ background:white; color:#333; padding:20px; margin:0 auto 30px; max-width:760px; border:1px solid #ddd; }}
        </style>
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/supplier/{supplier_id}" style="color:var(--text-muted);">&larr; Back to Supplier</a>
            <div style="display:flex;align-items:center;gap:10px;">
                <select onchange="if(this.value)window.location='/supplier-statement/{supplier_id}/print?month='+this.value;" style="padding:6px 10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">{_month_options}</select>
                <button class="btn btn-secondary" onclick="window.print();">Print</button>
            </div>
        </div>
        <div id="printArea">
            {block}
        </div>
        '''
        return render_page("Supplier Statement", content, user, "suppliers")


    @app.route("/supplier-return/new")
    @login_required
    def supplier_return_new():
        """Stuk 1 — the New Supplier Return screen. Build return lines by
        picking stock items (or free lines), optionally referencing an open
        supplier invoice. The save happens in Stuk 2 (/api/supplier-return/save)."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return redirect("/suppliers")
        
        suppliers = db.get("suppliers", {"business_id": biz_id}) or []
        suppliers = sorted(suppliers, key=lambda x: (x.get("name") or "").lower())
        
        stock = db.get_all_stock(biz_id) or []
        stock = sorted(stock, key=lambda x: (x.get("description") or "").lower())
        
        # Open supplier invoices (not paid/credited/cancelled) — for the
        # optional "From Invoice" picker. Grouped per supplier on the client.
        all_sinvoices = db.get("supplier_invoices", {"business_id": biz_id}) or []
        open_sinvoices = [si for si in all_sinvoices
                          if (si.get("status") or "").lower() not in ("credited", "cancelled")]
        
        prefill_supplier = request.args.get("supplier_id", "")
        # mode=discount opens the screen pre-set for a discount/adjustment
        # credit (first line type = Discount). Same screen, same endpoint —
        # just a different starting state so it feels like its own tool.
        is_discount_mode = (request.args.get("mode", "") or "").strip().lower() == "discount"
        _sr_page_title = "New Discount Credit" if is_discount_mode else "New Supplier Return"
        _sr_heading = "↩️ New Discount Credit" if is_discount_mode else "↩️ New Supplier Return"
        _sr_default_type = "discount" if is_discount_mode else "stock"
        
        supplier_options = '<option value="">-- Select Supplier --</option>'
        for s in suppliers:
            sel = "selected" if s.get("id") == prefill_supplier else ""
            supplier_options += f'<option value="{s.get("id")}" {sel}>{safe_string(s.get("name", ""))}</option>'
        
        # Stock data for the line-item typeahead (same shape as the PO screen)
        _ret_stock_json = json.dumps([
            {"id": s.get("id", ""), "code": safe_string(s.get("code", "")),
             "desc": safe_string(s.get("description", "")),
             "price": float(s.get("cost_price", 0) or 0)}
            for s in stock
        ])
        # Open invoices keyed by supplier — the client filters this when a
        # supplier is chosen, so the "From Invoice" picker only shows that
        # supplier's open invoices.
        _ret_inv_json = json.dumps([
            {"id": si.get("id", ""), "supplier_id": si.get("supplier_id", ""),
             "number": safe_string(si.get("invoice_number", "")),
             "date": si.get("date", ""), "total": float(si.get("total", 0) or 0)}
            for si in open_sinvoices
        ])
        
        # ── Return Lines card pieces — differ between the full Supplier
        # Return screen and the simpler Discount Credit screen (mode=discount).
        # Discount mode: just Description / Amount / Total — no Type selector,
        # no stock column, no qty. Every row carries a hidden sr-type=discount
        # and a fixed sr-qty=1 so the shared endpoint is unchanged.
        if is_discount_mode:
            _sr_lines_title = "Discount Lines"
            _sr_lines_header = (
                '<div class="sr-item-hdr sr-disc">'
                '<span>Description</span><span>Amount (excl)</span>'
                '<span style="text-align:right;">Total</span><span></span></div>'
            )
            _sr_row_inner = (
                '<input type="hidden" class="sr-type" value="discount">'
                '<input type="hidden" class="sr-stock-id" value="">'
                '<input type="number" class="sr-qty" value="1" style="display:none;">'
                '<input type="text" class="sr-desc" placeholder="e.g. Settlement discount" '
                'style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">'
                '<input type="number" class="sr-price" placeholder="0.00" step="0.01" onchange="srCalcTotals()" '
                'style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">'
                '<span class="sr-line-total" style="text-align:right;font-weight:600;">R0.00</span>'
                '<button type="button" class="sr-rm" onclick="this.closest(\'.sr-item-row\').remove(); srCalcTotals();">&times;</button>'
            )
            _sr_first_row = f'<div class="sr-item-row sr-disc">{_sr_row_inner}</div>'
            _sr_add_label = "+ Add Discount Line"
            _sr_lines_help = "Each line credits the supplier and posts to Discount Received. No stock effect."
        else:
            _sr_lines_title = "Return Lines"
            _sr_lines_header = (
                '<div class="sr-item-hdr">'
                '<span>Type</span><span>Stock Item</span><span>Description</span><span>Qty</span>'
                '<span>Price (excl)</span><span style="text-align:right;">Total</span><span></span></div>'
            )
            _stk_sel = ' selected' if _sr_default_type == 'stock' else ''
            _dsc_sel = ' selected' if _sr_default_type == 'discount' else ''
            _sr_first_row = (
                '<div class="sr-item-row">'
                '<select class="sr-type" onchange="srTypeChanged(this)" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:12px;padding:8px 6px;">'
                '<option value="stock"' + _stk_sel + '>Stock Return</option>'
                '<option value="discount"' + _dsc_sel + '>Discount</option>'
                '</select>'
                '<div class="sr-stock-td">'
                '<input type="text" class="sr-stock-search" placeholder="Search stock (or leave blank for free line)..." autocomplete="off" oninput="srStockSearch(this)" onfocus="srStockSearch(this)" style="width:100%;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">'
                '<input type="hidden" class="sr-stock-id" value="">'
                '<div class="ssp-dropdown sr-stock-dd"></div>'
                '</div>'
                '<input type="text" class="sr-desc" placeholder="Description" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">'
                '<input type="number" class="sr-qty" value="1" min="0" step="any" onchange="srCalcTotals()" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">'
                '<input type="number" class="sr-price" placeholder="0.00" step="0.01" onchange="srCalcTotals()" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">'
                '<span class="sr-line-total" style="text-align:right;font-weight:600;">R0.00</span>'
                '<button type="button" class="sr-rm" onclick="this.closest(\'.sr-item-row\').remove(); srCalcTotals();">&#10005;</button>'
                '</div>'
            )
            _sr_add_label = "+ Add Line"
            _sr_lines_help = ("Stock Return lines reduce stock on save and credit the supplier. "
                              "Discount lines credit the supplier and post to Discount Received — "
                              "no stock effect. Both can be mixed on one return.")
        
        content = f'''
        <style>
        .sr-form-grid {{ display: grid; grid-template-columns: 1fr 280px; gap: 20px; }}
        .sr-main {{ display: flex; flex-direction: column; gap: 15px; min-width: 0; }}
        .sr-sidebar {{ position: sticky; top: 80px; display: flex; flex-direction: column; gap: 12px; align-self: start; }}
        .sr-sidebar .card {{ padding: 16px; margin: 0; }}
        .sr-item-row {{ display: grid; grid-template-columns: 110px 3fr 2fr 70px 110px 100px 30px; gap: 8px; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
        .sr-item-row input {{ font-size: 13px; padding: 8px 10px; }}
        .sr-item-hdr {{ display: grid; grid-template-columns: 110px 3fr 2fr 70px 110px 100px 30px; gap: 8px; padding: 6px 0; font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 2px solid var(--border); }}
        .sr-item-row.sr-disc {{ grid-template-columns: 1fr 140px 110px 30px; }}
        .sr-item-hdr.sr-disc {{ grid-template-columns: 1fr 140px 110px 30px; }}
        .sr-stock-td {{ position: relative; }}
        .sr-stock-td .ssp-dropdown.sr-stock-dd {{ position: fixed !important; left: auto !important; right: auto !important; z-index: 9999 !important; max-height: 60vh; min-width: 600px; overflow-y: auto; background: var(--card, #1e1e2e); border: 1px solid var(--border, #333); border-radius: 6px; box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
        .sr-rm {{ background: var(--red); color: #fff; border: none; border-radius: 4px; width: 24px; height: 24px; cursor: pointer; }}
        .sr-add-btn {{ background: var(--card); color: var(--primary); border: 1px solid var(--primary); border-radius: 6px; padding: 8px 14px; cursor: pointer; font-weight: 600; }}
        .sr-totals {{ border-top: 2px solid var(--border); margin-top: 10px; padding-top: 10px; }}
        .sr-totals-row {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }}
        .sr-totals-row.grand {{ font-size: 16px; font-weight: 700; border-top: 1px solid var(--border); margin-top: 4px; padding-top: 8px; }}
        </style>
        
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2 style="margin:0;">{_sr_heading}</h2>
            <a href="/suppliers" style="color:var(--text-muted);">← Back to Suppliers</a>
        </div>
        
        <form id="returnForm" onsubmit="return submitReturn(event);">
        <div class="sr-form-grid">
            <div class="sr-main">
                <div class="card" style="padding:20px;">
                    <h3 style="margin:0 0 12px 0;">Return Details</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Supplier</label>
                            <select name="supplier_id" id="srSupplier" onchange="srSupplierChanged()" required style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                                {supplier_options}
                            </select>
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">From Invoice (optional)</label>
                            <select name="from_invoice_id" id="srFromInvoice" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                                <option value="">-- No invoice (free return) --</option>
                            </select>
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Date</label>
                            <input type="date" name="date" id="srDate" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Supplier Ref (optional)</label>
                            <input type="text" name="supplier_ref" placeholder="Their credit note no." style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                        </div>
                    </div>
                    <div style="margin-top:14px;">
                        <label style="display:block;margin-bottom:4px;font-weight:600;font-size:13px;">Reason</label>
                        <input type="text" name="reason" id="srReason" placeholder="e.g. Goods returned, Damaged stock, Price adjustment" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    </div>
                </div>
                
                <div class="card" style="padding:20px;">
                    <h3 style="margin:0 0 12px 0;">{_sr_lines_title}</h3>
                    {_sr_lines_header}
                    <div id="srItemsBody">
                        {_sr_first_row}
                    </div>
                    <button type="button" class="sr-add-btn" onclick="srAddRow()" style="margin-top:10px;">{_sr_add_label}</button>
                    <p style="color:var(--text-muted);font-size:11px;margin-top:8px;">{_sr_lines_help}</p>
                </div>
            </div>
            
            <div class="sr-sidebar">
                <div class="card">
                    <h3 style="margin:0 0 10px 0;">Return Total</h3>
                    <div class="sr-totals">
                        <div class="sr-totals-row"><span>Subtotal</span><span id="srSubtotal">R0.00</span></div>
                        <div class="sr-totals-row"><span>VAT (15%)</span><span id="srVat">R0.00</span></div>
                        <div class="sr-totals-row grand"><span>Total</span><span id="srTotal">R0.00</span></div>
                    </div>
                    <button type="submit" class="btn btn-primary" style="width:100%;margin-top:14px;padding:12px;font-weight:700;">Save Return</button>
                    <div id="srMsg" style="margin-top:10px;text-align:center;font-size:13px;display:none;"></div>
                </div>
            </div>
        </div>
        </form>
        
        <script>
        const srStockData = {_ret_stock_json};
        const srInvData = {_ret_inv_json};
        
        document.getElementById('srDate').value = new Date().toISOString().split('T')[0];
        
        // When supplier changes, repopulate the "From Invoice" picker with
        // only that supplier's open invoices.
        function srSupplierChanged() {{
            const supId = document.getElementById('srSupplier').value;
            const sel = document.getElementById('srFromInvoice');
            sel.innerHTML = '<option value="">-- No invoice (free return) --</option>';
            srInvData.filter(i => i.supplier_id === supId).forEach(i => {{
                const opt = document.createElement('option');
                opt.value = i.id;
                opt.textContent = i.number + ' · ' + (i.date || '') + ' · R' + i.total.toFixed(2);
                sel.appendChild(opt);
            }});
        }}
        srSupplierChanged();
        
        // Stock typeahead — same pattern as the PO screen
        function srStockSearch(input) {{
            const wrap = input.closest('.sr-stock-td');
            let dd = wrap.querySelector('.sr-stock-dd');
            const q = input.value.toLowerCase().trim().replace(/\\s*[xX]\\s*/g, 'x');
            const terms = q.split(/\\s+/).filter(t => t.length > 0);
            if (!terms.length) {{ dd.classList.remove('show'); return; }}
            const matches = srStockData.filter(s => {{
                const text = (s.code + ' ' + s.desc).toLowerCase().replace(/\\s*[xX]\\s*/g, 'x');
                return terms.every(t => text.includes(t));
            }}).slice(0, 20);
            if (matches.length === 0) {{
                dd.innerHTML = '<div class="ssp-empty">No stock found</div>';
            }} else {{
                dd.innerHTML = matches.map((s, i) => {{
                    const safeDesc = s.desc.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
                    return '<div class="ssp-item" data-idx="' + i + '">' +
                        (s.code ? '<span class="ssp-code">' + s.code + '</span>' : '') +
                        '<span class="ssp-desc">' + safeDesc + '</span>' +
                        (s.price ? '<span class="ssp-price">R' + s.price.toFixed(2) + '</span>' : '') +
                        '</div>';
                }}).join('');
                dd.querySelectorAll('.ssp-item').forEach(el => {{
                    el.addEventListener('click', function() {{
                        const m = matches[parseInt(this.getAttribute('data-idx'))];
                        const row = wrap.closest('.sr-item-row');
                        row.querySelector('.sr-stock-search').value = m.code ? m.code + ' - ' + m.desc : m.desc;
                        row.querySelector('.sr-stock-id').value = m.id;
                        row.querySelector('.sr-desc').value = m.desc;
                        if (m.price) row.querySelector('.sr-price').value = m.price.toFixed(2);
                        srCalcTotals();
                        dd.classList.remove('show');
                    }});
                }});
            }}
            const rect = input.getBoundingClientRect();
            dd.style.left = rect.left + 'px';
            dd.style.top = (rect.bottom + 2) + 'px';
            dd.style.width = Math.max(rect.width, 600) + 'px';
            dd.classList.add('show');
        }}
        
        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.sr-stock-search') && !e.target.closest('.sr-stock-dd')) {{
                document.querySelectorAll('.sr-stock-dd').forEach(d => d.classList.remove('show'));
            }}
        }});
        
        const srDiscountMode = {'true' if is_discount_mode else 'false'};
        
        function srAddRow() {{
            const body = document.getElementById('srItemsBody');
            const row = document.createElement('div');
            if (srDiscountMode) {{
                row.className = 'sr-item-row sr-disc';
                row.innerHTML = `
                    <input type="hidden" class="sr-type" value="discount">
                    <input type="hidden" class="sr-stock-id" value="">
                    <input type="number" class="sr-qty" value="1" style="display:none;">
                    <input type="text" class="sr-desc" placeholder="e.g. Settlement discount" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    <input type="number" class="sr-price" placeholder="0.00" step="0.01" onchange="srCalcTotals()" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    <span class="sr-line-total" style="text-align:right;font-weight:600;">R0.00</span>
                    <button type="button" class="sr-rm" onclick="this.closest('.sr-item-row').remove(); srCalcTotals();">&times;</button>
                `;
                body.appendChild(row);
                row.querySelector('.sr-desc').focus();
                return;
            }}
            row.className = 'sr-item-row';
            row.innerHTML = `
                <select class="sr-type" onchange="srTypeChanged(this)" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:12px;padding:8px 6px;">
                    <option value="stock">Stock Return</option>
                    <option value="discount">Discount</option>
                </select>
                <div class="sr-stock-td">
                    <input type="text" class="sr-stock-search" placeholder="Search stock (or leave blank for free line)..." autocomplete="off" oninput="srStockSearch(this)" onfocus="srStockSearch(this)" style="width:100%;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    <input type="hidden" class="sr-stock-id" value="">
                    <div class="ssp-dropdown sr-stock-dd"></div>
                </div>
                <input type="text" class="sr-desc" placeholder="Description" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                <input type="number" class="sr-qty" value="1" min="0" step="any" onchange="srCalcTotals()" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                <input type="number" class="sr-price" placeholder="0.00" step="0.01" onchange="srCalcTotals()" style="border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                <span class="sr-line-total" style="text-align:right;font-weight:600;">R0.00</span>
                <button type="button" class="sr-rm" onclick="this.closest('.sr-item-row').remove(); srCalcTotals();">✕</button>
            `;
            body.appendChild(row);
            row.querySelector('.sr-stock-search').focus();
        }}
        
        function srCalcTotals() {{
            let subtotal = 0;
            document.querySelectorAll('.sr-item-row').forEach(row => {{
                const qty = parseFloat(row.querySelector('.sr-qty')?.value) || 0;
                const price = parseFloat(row.querySelector('.sr-price')?.value) || 0;
                const lineTotal = qty * price;
                subtotal += lineTotal;
                const lt = row.querySelector('.sr-line-total');
                if (lt) lt.textContent = 'R' + lineTotal.toFixed(2);
            }});
            const vat = subtotal * 0.15;
            document.getElementById('srSubtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('srVat').textContent = 'R' + vat.toFixed(2);
            document.getElementById('srTotal').textContent = 'R' + (subtotal + vat).toFixed(2);
        }}
        srCalcTotals();
        
        function srTypeChanged(sel) {{
            const row = sel.closest('.sr-item-row');
            const isDiscount = sel.value === 'discount';
            const stockSearch = row.querySelector('.sr-stock-search');
            const stockId = row.querySelector('.sr-stock-id');
            const qtyEl = row.querySelector('.sr-qty');
            const descEl = row.querySelector('.sr-desc');
            if (isDiscount) {{
                // A discount line is not a stock item — clear and lock the stock field.
                stockSearch.value = '';
                stockSearch.disabled = true;
                stockSearch.placeholder = 'Not applicable for discount';
                stockId.value = '';
                qtyEl.value = 1;
                qtyEl.disabled = true;
                if (!descEl.value.trim()) descEl.placeholder = 'e.g. Settlement discount';
            }} else {{
                stockSearch.disabled = false;
                stockSearch.placeholder = 'Search stock (or leave blank for free line)...';
                qtyEl.disabled = false;
            }}
            srCalcTotals();
        }}
        
        // On load, if a full-mode row's Type selector is pre-set to "Discount"
        // apply the same lock srTypeChanged would. Skipped in discount mode,
        // where sr-type is a hidden input and the row is already simplified.
        document.querySelectorAll('.sr-item-row select.sr-type').forEach(function(sel) {{
            if (sel.value === 'discount') srTypeChanged(sel);
        }});
        
        // Collect the lines into a clean array
        function srCollectLines() {{
            const lines = [];
            document.querySelectorAll('.sr-item-row').forEach(row => {{
                const lineType = row.querySelector('.sr-type')?.value || 'stock';
                const qty = parseFloat(row.querySelector('.sr-qty')?.value) || 0;
                const price = parseFloat(row.querySelector('.sr-price')?.value) || 0;
                const desc = (row.querySelector('.sr-desc')?.value || '').trim();
                const stockId = row.querySelector('.sr-stock-id')?.value || '';
                if (qty > 0 && price > 0 && (desc || stockId)) {{
                    lines.push({{ line_type: lineType, stock_id: stockId, description: desc, quantity: qty, price: price }});
                }}
            }});
            return lines;
        }}
        
        async function submitReturn(e) {{
            e.preventDefault();
            const msg = document.getElementById('srMsg');
            const supId = document.getElementById('srSupplier').value;
            if (!supId) {{ msg.style.display='block'; msg.style.color='var(--red)'; msg.textContent='Select a supplier'; return false; }}
            const lines = srCollectLines();
            if (lines.length === 0) {{ msg.style.display='block'; msg.style.color='var(--red)'; msg.textContent='Add at least one valid line (qty and price)'; return false; }}
            
            const payload = {{
                supplier_id: supId,
                from_invoice_id: document.getElementById('srFromInvoice').value || '',
                date: document.getElementById('srDate').value,
                supplier_ref: document.querySelector('input[name="supplier_ref"]').value.trim(),
                reason: document.getElementById('srReason').value.trim(),
                lines: lines
            }};
            
            const btn = e.target.querySelector('button[type="submit"]');
            btn.disabled = true; btn.textContent = 'Saving...';
            try {{
                const resp = await fetch('/api/supplier-return/save', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(payload)
                }});
                const data = await resp.json();
                if (data.success) {{
                    msg.style.display='block'; msg.style.color='var(--green)';
                    msg.textContent = 'Return ' + (data.cn_number || '') + ' saved';
                    setTimeout(() => {{ window.location = '/supplier-credit-note/' + data.cn_id; }}, 900);
                }} else {{
                    msg.style.display='block'; msg.style.color='var(--red)';
                    msg.textContent = data.error || 'Save failed';
                    btn.disabled = false; btn.textContent = 'Save Return';
                }}
            }} catch (err) {{
                msg.style.display='block'; msg.style.color='var(--red)';
                msg.textContent = 'Error: ' + err.message;
                btn.disabled = false; btn.textContent = 'Save Return';
            }}
            return false;
        }}
        </script>
        '''
        return render_page(_sr_page_title, content, user, "suppliers")

    @app.route("/api/supplier-return/save", methods=["POST"])
    @login_required
    def api_supplier_return_save():
        """Stuk 2 — save a Supplier Return. Builds a supplier_credit_notes
        record from the chosen lines, posts the GL journal, decrements stock
        for stock-linked lines, and (if an invoice was referenced) recalculates
        that invoice's status so a partial return leaves it open."""
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            
            data = request.get_json() or {}
            supplier_id = (data.get("supplier_id") or "").strip()
            from_invoice_id = (data.get("from_invoice_id") or "").strip()
            ret_date = data.get("date") or today()
            supplier_ref = (data.get("supplier_ref") or "").strip()
            reason = (data.get("reason") or "").strip() or "Supplier Return"
            lines = data.get("lines", []) or []
            
            if not supplier_id:
                return jsonify({"success": False, "error": "Select a supplier"})
            if not lines:
                return jsonify({"success": False, "error": "Add at least one return line"})
            
            supplier = db.get_one("suppliers", supplier_id)
            if not supplier or supplier.get("business_id") != biz_id:
                return jsonify({"success": False, "error": "Supplier not found"})
            supplier_name = supplier.get("name", "Unknown")
            
            # ── Build clean line items + totals (prices are EXCL VAT) ──
            clean_lines = []
            subtotal = 0.0
            stock_credit = 0.0   # net of stock-linked lines  -> CR Stock
            free_credit = 0.0    # net of free lines          -> CR COS/Purchases
            discount_credit = 0.0  # net of discount lines    -> CR Discount Received (4300)
            for ln in lines:
                try:
                    qty = round(float(ln.get("quantity", 0) or 0), 4)
                    price = round(float(ln.get("price", 0) or 0), 2)
                except Exception:
                    continue
                if qty <= 0 or price <= 0:
                    continue
                line_type = (ln.get("line_type") or "stock").strip().lower()
                if line_type not in ("stock", "discount"):
                    line_type = "stock"
                stock_id = (ln.get("stock_id") or "").strip()
                desc = (ln.get("description") or "").strip()
                # A discount line is never a stock item — drop any stock link.
                if line_type == "discount":
                    stock_id = ""
                if not desc and not stock_id:
                    continue
                line_total = round(qty * price, 2)
                subtotal += line_total
                if line_type == "discount":
                    discount_credit += line_total
                elif stock_id:
                    stock_credit += line_total
                else:
                    free_credit += line_total
                clean_lines.append({
                    "line_type": line_type,
                    "stock_id": stock_id,
                    "description": desc,
                    "quantity": qty,
                    "price": price,
                    "line_total": line_total,
                })
            
            if not clean_lines:
                return jsonify({"success": False, "error": "No valid return lines (need qty and price)"})
            
            subtotal = round(subtotal, 2)
            vat = round(subtotal * 0.15, 2)
            total = round(subtotal + vat, 2)
            
            # ── Generate our SCR number ──
            existing_cns = db.get("supplier_credit_notes", {"business_id": biz_id}) or []
            cn_number = next_document_number("SCR-", existing_cns, field="cn_number")
            cn_id = generate_id()
            cn_ref = f"SCR-{cn_id[:8]}"
            
            # ── GL journal: DR Creditors, CR Stock (stock lines),
            #    CR COS/Purchases (free lines), CR Discount Received (discount
            #    lines), CR VAT Input ──
            cn_journal_lines = []
            if stock_credit > 0:
                cn_journal_lines.append({"account_code": gl(biz_id, "stock"), "debit": 0, "credit": round(stock_credit, 2)})
            if free_credit > 0:
                cn_journal_lines.append({"account_code": gl(biz_id, "cogs"), "debit": 0, "credit": round(free_credit, 2)})
            if discount_credit > 0:
                # Ensure the Discount Received account exists (auto-creates if missing)
                try:
                    import clickai as _main
                    _disc_recv_code = _main.ensure_gl_account(biz_id, "discount_received", "Discount Received", "income", "Other Income")
                except Exception:
                    _disc_recv_code = gl(biz_id, "discount_received")
                cn_journal_lines.append({"account_code": _disc_recv_code, "debit": 0, "credit": round(discount_credit, 2)})
            if vat > 0:
                cn_journal_lines.append({"account_code": gl(biz_id, "vat_input"), "debit": 0, "credit": vat})
            cn_journal_lines.append({"account_code": gl(biz_id, "creditors"), "debit": total, "credit": 0})
            
            try:
                create_journal_entry(biz_id, ret_date, f"Supplier Return - {supplier_name}", cn_ref, cn_journal_lines)
            except Exception as je:
                logger.error(f"[SUP RETURN] GL entry failed (return still saving): {je}")
            
            # ── Decrement stock for stock-linked lines + log movements ──
            for cl in clean_lines:
                sid = cl["stock_id"]
                if not sid:
                    continue
                try:
                    stock_item = db.get_one_stock(sid)
                    if stock_item:
                        cur_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                        new_qty = cur_qty - cl["quantity"]
                        db.update_stock(sid, {"qty": new_qty, "quantity": new_qty}, biz_id)
                        db.save("stock_movements", RecordFactory.stock_movement(
                            business_id=biz_id, stock_id=sid, movement_type="out",
                            quantity=cl["quantity"],
                            reference=f"{cn_number} | Supplier Return | {safe_string(supplier_name)}"
                        ))
                except Exception as se:
                    logger.error(f"[SUP RETURN] Stock decrement failed for {sid}: {se}")
            
            # ── Build a reason that records the supplier's own ref ──
            full_reason = reason
            if supplier_ref:
                full_reason = f"{reason} | META:{json.dumps({'supplier_cn_number': supplier_ref})}"
            
            # ── Save the supplier credit note record ──
            cn_record = {
                "id": cn_id,
                "business_id": biz_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "cn_number": cn_number,
                "original_invoice_id": from_invoice_id or None,
                "date": ret_date,
                "subtotal": subtotal,
                "vat": vat,
                "total": total,
                "reason": full_reason,
                "items": json.dumps(clean_lines),
                "status": "active",
                "stock_snapshots": "[]",
                "created_by": user.get("id") if user else None,
                "created_at": now()
            }
            ok, result = db.save("supplier_credit_notes", cn_record)
            if not ok:
                logger.error(f"[SUP RETURN] Failed to save: {result}")
                return jsonify({"success": False, "error": f"Database error: {result}"})
            
            # ── If linked to an invoice, recalc its status (partial return
            #    leaves it open; the supplier balance auto-deducts the CN) ──
            if from_invoice_id:
                try:
                    recalc_supplier_invoice_status(biz_id, from_invoice_id)
                except Exception as re:
                    logger.warning(f"[SUP RETURN] recalc invoice status failed: {re}")
            
            # ── Pulse + allocation logs ──
            try:
                _log_pulse_event(biz_id, user, "supplier_return_created",
                    f"Supplier Return {cn_number} created for {supplier_name}",
                    f"Return of R{total:.2f} ({len(clean_lines)} line(s)). Reason: {reason}")
            except Exception:
                pass
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_credit_note",
                        source_table="supplier_credit_notes", source_id=cn_id,
                        description=f"Supplier Return {cn_number} - {supplier_name}",
                        amount=total, gl_entries=cn_journal_lines,
                        category="Supplier Return", category_code=gl(biz_id, "creditors"),
                        supplier_name=supplier_name, payment_method="account",
                        reference=cn_number, transaction_date=ret_date,
                        created_by=user.get("id") if user else "",
                        created_by_name=user.get("name", "") if user else ""
                    )
            except Exception:
                pass
            
            return jsonify({"success": True, "cn_number": cn_number, "cn_id": cn_id})
        except Exception as e:
            logger.exception(f"[SUP RETURN] Failed: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/scan/save-supplier-credit-note", methods=["POST"])
    @login_required
    def api_scan_save_supplier_credit_note():
        """
        Save a scanned supplier credit note.
        
        Accepts:
          - supplier_name, cn_number (the credit note's own number), date,
            subtotal, vat, total, items (line items from the credit note)
          - target_type: "invoice" or "balance_bf"
          - target_invoice_id (when target_type == "invoice")
          - credit_amount: the actual amount to credit (may be LESS than total
            for a partial credit)
          - original_invoice_ref (informational — what Sonnet read on the document)
        
        Behaviour:
          - Creates a supplier_credit_notes record with credit_amount.
          - Posts journal: DR Creditors / CR Stock-or-COGS / CR VAT Input.
          - If target_type == "invoice" AND credit_amount >= invoice total:
              * Marks the invoice as 'credited'
              * Fully reverses the original stock from snapshot
          - If target_type == "invoice" AND credit_amount < invoice total:
              * Invoice stays open (supplier balance auto-deducts the credit
                via the existing _sup_running calc in supplier_view)
              * Reverses stock PROPORTIONALLY: ratio = credit_amount / invoice_total
          - If target_type == "balance_bf":
              * No invoice link, no stock reversal (the credit is a pure
                money credit against the supplier account — no items to undo)
        """
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            
            data = request.get_json() or {}
            supplier_name = (data.get("supplier_name") or "Unknown Supplier").strip()
            cn_doc_number = (data.get("cn_number") or "").strip()  # The number printed on the credit note doc itself
            cn_date = data.get("date") or today()
            cn_subtotal = float(data.get("subtotal", 0) or 0)
            cn_vat = float(data.get("vat", 0) or 0)
            cn_total = float(data.get("total", 0) or 0)
            cn_items_raw = data.get("items", []) or []
            target_type = (data.get("target_type") or "invoice").lower().strip()
            target_invoice_id = (data.get("target_invoice_id") or "").strip()
            target_invoice_number = (data.get("target_invoice_number") or "").strip()
            credit_amount = float(data.get("credit_amount", 0) or 0)
            original_invoice_ref = (data.get("original_invoice_ref") or "").strip()
            
            if credit_amount <= 0:
                return jsonify({"success": False, "error": "Credit amount must be greater than zero"})
            
            if target_type not in ("invoice", "balance_bf"):
                target_type = "invoice"
            
            if target_type == "invoice" and not target_invoice_id:
                return jsonify({"success": False, "error": "Pick a target invoice, or select Balance Brought Forward"})
            
            # Find or create supplier
            suppliers = db.get("suppliers", {"business_id": biz_id}) or []
            supplier = None
            for s in suppliers:
                s_name = (s.get("name") or "").strip()
                if not s_name:
                    continue
                if supplier_name.lower() == s_name.lower() or supplier_name.lower() in s_name.lower() or s_name.lower() in supplier_name.lower():
                    supplier = s
                    break
            if not supplier:
                # New supplier (rare for a credit note, but possible)
                new_sup = RecordFactory.supplier(
                    business_id=biz_id,
                    name=supplier_name,
                    phone=data.get("supplier_phone", "") or "",
                    email=data.get("supplier_email", "") or "",
                    created_by=user.get("id", "") if user else ""
                )
                ok, _ = db.save("suppliers", new_sup)
                supplier = new_sup
            supplier_id = supplier.get("id")
            
            # ── Look up the target invoice (if any) for full/partial decision
            target_invoice = None
            invoice_total = 0.0
            is_full_credit = False
            if target_type == "invoice":
                target_invoice = db.get_one("supplier_invoices", target_invoice_id)
                if not target_invoice:
                    return jsonify({"success": False, "error": "Target invoice not found"})
                if (target_invoice.get("status") or "").lower() == "credited":
                    return jsonify({"success": False, "error": "Target invoice is already credited"})
                invoice_total = float(target_invoice.get("total", 0) or 0)
                # Tolerance: treat 'within 1 cent' as full credit
                is_full_credit = credit_amount >= (invoice_total - 0.01) and invoice_total > 0
                if not target_invoice_number:
                    target_invoice_number = target_invoice.get("invoice_number", "")
            
            # ── Allocation intent (inherit from target invoice or default to stock)
            _alloc_intent = "stock"
            if target_invoice:
                _alloc_intent = (target_invoice.get("allocation_intent") or "stock").lower()
                if _alloc_intent not in ("stock", "cos", "split"):
                    _alloc_intent = "stock"
            
            # ── Generate CN number for our system (separate from the doc's own number)
            existing_cns = db.get("supplier_credit_notes", {"business_id": biz_id}) or []
            cn_number = next_document_number("SCR-", existing_cns, field="cn_number")
            cn_id = generate_id()
            cn_ref = f"SCR-{cn_id[:8]}"
            
            # ── STOCK REVERSAL (only when targeting an invoice)
            stock_reversal_note = ""
            cn_snapshots_for_record = "[]"
            if target_type == "invoice" and target_invoice:
                snapshots_raw = target_invoice.get("stock_snapshots")
                if is_full_credit:
                    # FULL credit — reverse stock exactly per original snapshot
                    if snapshots_raw:
                        _reverse_stock_from_snapshot(biz_id, snapshots_raw)
                        cn_snapshots_for_record = snapshots_raw if isinstance(snapshots_raw, str) else json.dumps(snapshots_raw)
                        stock_reversal_note = "Full stock reversal from snapshot"
                    else:
                        # Legacy: best-effort from items
                        _legacy_reverse_stock_from_items(biz_id, target_invoice.get("items", "[]"))
                        stock_reversal_note = "Full stock reversal (legacy, no snapshot)"
                else:
                    # PARTIAL credit — reverse stock proportionally
                    if invoice_total > 0 and credit_amount > 0:
                        ratio = credit_amount / invoice_total
                    else:
                        ratio = 0
                    if snapshots_raw and ratio > 0:
                        # Build a scaled snapshot: scale each delta by ratio.
                        # We can't simply restore old_qty (that would full-reverse).
                        # Instead, compute current snapshot delta and subtract ratio*delta.
                        try:
                            snaps = snapshots_raw if isinstance(snapshots_raw, list) else json.loads(snapshots_raw)
                        except Exception:
                            snaps = []
                        partial_reversed = 0
                        for snap in (snaps or []):
                            try:
                                stock_id = snap.get("stock_id")
                                action = snap.get("action", "updated")
                                table = snap.get("table", "stock_items")
                                if not stock_id or action == "created":
                                    # We don't delete created stock for partials — too risky.
                                    # Adjust quantity downward by ratio of the delta instead.
                                    if action == "created":
                                        try:
                                            cur = db.get_one(table, stock_id)
                                            if cur:
                                                cur_qty = float(cur.get("quantity", cur.get("qty", 0)) or 0)
                                                # On 'created', the entire current qty IS the delta.
                                                reduce_by = cur_qty * ratio
                                                new_qty = max(0, cur_qty - reduce_by)
                                                db.save(table, {"id": stock_id, "quantity": new_qty, "qty": new_qty})
                                                partial_reversed += 1
                                        except Exception as _e:
                                            logger.warning(f"[CN-PARTIAL] created-stock partial reduce failed: {_e}")
                                    continue
                                # Updated: delta = current - old_qty. Reduce current by ratio*delta.
                                old_qty = float(snap.get("old_qty", 0) or 0)
                                cur = db.get_one(table, stock_id)
                                if not cur:
                                    continue
                                cur_qty = float(cur.get("quantity", cur.get("qty", 0)) or 0)
                                delta_added = max(0, cur_qty - old_qty)  # qty originally added by invoice (rough)
                                # If invoice has been partially consumed, delta_added may be < snap delta;
                                # use the smaller of (snap-delta, delta_added) to be safe.
                                snap_delta = max(0, (float(snap.get("qty_delta", 0) or 0)))
                                if snap_delta <= 0:
                                    # Fall back to (cur - old) which is positive when stock still on hand
                                    snap_delta = delta_added
                                reduce_by = snap_delta * ratio
                                new_qty = max(0, cur_qty - reduce_by)
                                db.save(table, {"id": stock_id, "quantity": new_qty, "qty": new_qty})
                                partial_reversed += 1
                            except Exception as _e:
                                logger.warning(f"[CN-PARTIAL] snapshot entry partial reverse failed: {_e}")
                        stock_reversal_note = f"Partial stock reversal ({int(ratio*100)}% — {partial_reversed} items adjusted)"
                    else:
                        # No snapshot or zero ratio — skip stock; pure money credit
                        stock_reversal_note = "No proportional stock reversal (no snapshot or zero ratio)"
                    cn_snapshots_for_record = "[]"  # No clean snapshot to store on the partial CN
            else:
                # Balance B/F credit — no items, no stock to reverse
                stock_reversal_note = "Balance B/F credit — no stock reversal"
            
            # ── JOURNAL: DR Creditors (reduce what we owe), CR Stock/COGS, CR VAT Input
            # Use the credit_amount (not the doc total) so partials post correctly.
            # VAT portion scales with the ratio of credit_amount to (doc total OR invoice total).
            # If the credit_amount equals doc total, use doc VAT directly; otherwise apportion.
            if cn_total > 0 and cn_vat > 0:
                vat_in_credit = round(cn_vat * (credit_amount / cn_total), 2)
            else:
                # Calculate VAT inclusive: VAT portion = amount × 15/115
                vat_in_credit = round(credit_amount * 0.15 / 1.15, 2) if credit_amount > 0 else 0
            net_in_credit = round(credit_amount - vat_in_credit, 2)
            
            cn_journal_lines = []
            if _alloc_intent == "cos":
                cn_journal_lines.append({"account_code": gl(biz_id, "cogs"), "debit": 0, "credit": net_in_credit})
            else:
                cn_journal_lines.append({"account_code": gl(biz_id, "stock"), "debit": 0, "credit": net_in_credit})
            if vat_in_credit > 0:
                cn_journal_lines.append({"account_code": gl(biz_id, "vat_input"), "debit": 0, "credit": vat_in_credit})
            cn_journal_lines.append({"account_code": gl(biz_id, "creditors"), "debit": round(credit_amount, 2), "credit": 0})
            
            _journal_desc = f"Credit Note - {supplier_name}"
            if target_type == "invoice" and target_invoice_number:
                _journal_desc += f" (vs {target_invoice_number})"
            elif target_type == "balance_bf":
                _journal_desc += " (Balance B/F)"
            try:
                create_journal_entry(biz_id, cn_date, _journal_desc, cn_ref, cn_journal_lines)
            except Exception as _je:
                logger.error(f"[CN-SCAN] Journal entry failed: {_je}")
            
            # ── Save the credit note record
            # Pack the extra metadata that the existing supplier_credit_notes
            # schema doesn't have its own columns for, into the 'reason' field
            # as a JSON tag followed by a human-readable description. The legacy
            # endpoint puts a plain string in reason; we stay backwards-readable
            # by putting the human description first and the JSON tag last.
            _human_reason = (
                f"FULL credit vs {target_invoice_number}" if (target_type == "invoice" and is_full_credit)
                else f"PARTIAL credit (R{credit_amount:.2f} of R{invoice_total:.2f}) vs {target_invoice_number}" if (target_type == "invoice")
                else "Credit applied to Balance Brought Forward"
            )
            if original_invoice_ref:
                _human_reason += f" — doc ref: {original_invoice_ref}"
            _meta = {
                "target_type": target_type,
                "is_partial": (target_type == "invoice" and not is_full_credit),
                "supplier_cn_number": cn_doc_number,
                "original_invoice_number": target_invoice_number if target_type == "invoice" else "",
                "document_total": round(cn_total, 2),
                "credit_amount": round(credit_amount, 2),
                "source": "scan",
                "stock_reversal": stock_reversal_note
            }
            _reason_combined = f"{_human_reason} | META:{json.dumps(_meta)}"
            
            cn_record = {
                "id": cn_id,
                "business_id": biz_id,
                "supplier_id": supplier_id or None,
                "supplier_name": supplier_name,
                "cn_number": cn_number,
                "original_invoice_id": (target_invoice_id or None) if target_type == "invoice" else None,
                "date": cn_date,
                "subtotal": cn_subtotal,
                "vat": vat_in_credit,
                "total": round(credit_amount, 2),  # actual credit applied (not doc total)
                "reason": _reason_combined,
                "items": json.dumps(cn_items_raw) if not isinstance(cn_items_raw, str) else cn_items_raw,
                "status": "active",
                "stock_snapshots": cn_snapshots_for_record,
                "created_by": (user.get("id") if user else None) or None,
                "created_at": now()
            }
            ok, result = db.save("supplier_credit_notes", cn_record)
            if not ok:
                logger.error(f"[CN-SCAN] DB save failed: {result}")
                return jsonify({"success": False, "error": f"Database error: {result}"})
            
            # ── Mark target invoice as 'credited' only for FULL credits
            if target_type == "invoice" and is_full_credit:
                try:
                    db.save("supplier_invoices", {"id": target_invoice_id, "status": "credited", "updated_at": now()})
                except Exception as _ie:
                    logger.warning(f"[CN-SCAN] Could not mark invoice credited: {_ie}")
            
            # ── Pulse event
            if target_type == "invoice":
                _pulse_summary = f"Credit note {cn_number} created for {supplier_name}"
                _pulse_detail = (f"{'FULL' if is_full_credit else 'PARTIAL'} credit of R{credit_amount:.2f} "
                                 f"vs invoice {target_invoice_number or '?'} (total R{invoice_total:.2f}). "
                                 f"{stock_reversal_note}.")
            else:
                _pulse_summary = f"Credit note {cn_number} (Balance B/F) for {supplier_name}"
                _pulse_detail = f"Credit of R{credit_amount:.2f} against supplier balance brought forward. {stock_reversal_note}."
            _log_pulse_event(biz_id, user, "supplier_credit_note_created", _pulse_summary, _pulse_detail)
            
            # ── Allocation log
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_credit_note",
                        source_table="supplier_credit_notes", source_id=cn_id,
                        description=f"Credit Note {cn_number} - {supplier_name}" + (
                            f" - {('FULL' if is_full_credit else 'PARTIAL')} vs {target_invoice_number}" if target_type == "invoice" else " - Balance B/F"
                        ),
                        amount=round(credit_amount, 2), gl_entries=cn_journal_lines,
                        ai_reasoning=(f"Scanned credit note. Document total R{cn_total:.2f}, "
                                      f"applied R{credit_amount:.2f}. {stock_reversal_note}."),
                        ai_confidence="HIGH", ai_worker="Scan",
                        supplier_name=supplier_name, payment_method="account",
                        reference=cn_number, transaction_date=cn_date,
                        created_by=user.get("id") if user else "",
                        created_by_name=user.get("name", "") if user else ""
                    )
            except Exception:
                pass
            
            return jsonify({
                "success": True,
                "cn_number": cn_number,
                "cn_id": cn_id,
                "credit_amount": round(credit_amount, 2),
                "target_type": target_type,
                "is_full_credit": is_full_credit,
                "stock_reversal": stock_reversal_note,
                "message": (
                    f"Credit note {cn_number} saved — R{credit_amount:.2f} credited "
                    + (f"against invoice {target_invoice_number}" if target_type == "invoice" else "to Balance B/F")
                    + (" (full reversal)" if (target_type == "invoice" and is_full_credit) else
                       (" (partial)" if target_type == "invoice" else ""))
                )
            })
        except Exception as e:
            logger.exception(f"[CN-SCAN] Failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    logger.info("[PURCHASES] All supplier & purchase routes registered ✓")
