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
                              JARVIS_HUD_CSS, THEME_REACTOR_SKINS):
    """Register all Supplier and Purchase routes with the Flask app."""

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
        creditors = [s for s in suppliers if float(s.get("balance", 0)) > 0]
        total_owed = sum(float(s.get("balance", 0)) for s in creditors) if can_see_balances else 0
        
        # Build rows - COMPACT VIEW (details on View page)
        suppliers_html = ""
        for s in suppliers:
            balance = float(s.get("balance", 0) or 0)
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
                <input type="text" id="supplierSearch" placeholder="🔍 Search name, code, phone..." 
                    oninput="filterSuppliers()" 
                    style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);width:250px;">
                <select id="balanceFilter" onchange="filterSuppliers()" style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    <option value="">All</option>
                    <option value="creditors">We Owe</option>
                    <option value="credit">In Credit</option>
                    <option value="zero">Zero Balance</option>
                </select>
                <a href="/supplier/new" class="btn btn-primary">+ Add Supplier</a>
            </div>
        </div>
        
        {summary_html}
        
        {header_row}
        <div id="suppliersList">
        {suppliers_html or '<div class="card" style="text-align:center;padding:40px;"><p style="color:var(--text-muted);margin-bottom:15px;"><strong>Tip:</strong> No suppliers yet!</p><div><a href="/import" class="btn btn-primary">Import from Excel</a> <a href="/supplier/new" class="btn btn-secondary" style="margin-left:10px;">Add manually</a></div></div>'}
        </div>
        
        <script>
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
            _in_credit = len([s for s in suppliers if float(s.get("balance", 0) or 0) < 0])
            _j_alert = ""
            if _with_bal > 5 and can_see_balances:
                _top3 = ", ".join([f"{safe(s.get('name','-')[:20])} ({money(float(s.get('balance',0)))})" for s in sorted(creditors, key=lambda x: -float(x.get('balance',0)))[:3]])
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
        """Create new supplier - simple form"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            address = request.form.get("address", "").strip()
            code = request.form.get("code", "").strip()
            contact_name = request.form.get("contact_name", "").strip()
            category = request.form.get("category", "").strip()
            vat_number = request.form.get("vat_number", "").strip()
            
            # AUTO-GENERATE SMART CODE if not provided (e.g., AFR001 for Afrisam)
            if not code and biz_id and name:
                try:
                    import re
                    # Get first 3 letters of name (uppercase, letters only)
                    name_clean = re.sub(r'[^a-zA-Z]', '', name).upper()
                    prefix = name_clean[:3] if len(name_clean) >= 3 else name_clean.ljust(3, 'X')
                    
                    # Get existing codes with this prefix
                    existing = db.get("suppliers", {"business_id": biz_id}, limit=5000)
                    max_num = 0
                    for s in existing:
                        existing_code = s.get("code", "")
                        if existing_code.upper().startswith(prefix):
                            nums = re.findall(r'\d+', existing_code)
                            if nums:
                                num = int(nums[-1])
                                if num > max_num:
                                    max_num = num
                    
                    # Generate next code: AFR001, AFR002, etc.
                    code = f"{prefix}{(max_num + 1):03d}"
                    logger.info(f"[SUPPLIER] Smart code for '{name}': {code}")
                except Exception as e:
                    logger.error(f"[SUPPLIER] Smart code error: {e}")
                    code = f"S{generate_id()[:6].upper()}"
            
            if not name:
                flash("Supplier name is required", "error")
            else:
                supplier = RecordFactory.supplier(
                    business_id=biz_id,
                    name=name,
                    code=code,
                    phone=phone,
                    email=email,
                    address=address,
                    contact_name=contact_name,
                    category=category,
                    vat_number=vat_number,
                    created_by=user.get("id", "") if user else ""
                )
                supplier_id = supplier["id"]
                
                success, err = db.save("suppliers", supplier)
                if success:
                    flash(f"Supplier '{name}' created", "success")
                    return redirect("/suppliers")
                else:
                    flash(f"Error creating supplier: {err}", "error")
        
        content = '''
        <div class="card" style="max-width: 600px;">
            <h2 style="margin-bottom: 20px;">New Supplier</h2>
            <form method="POST">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Name *</label>
                        <input type="text" name="name" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Code</label>
                        <input type="text" name="code" placeholder="Auto: AFR001" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <small style="color:var(--text-muted);">Leave empty - auto-generates from name (e.g. Afrisam → AFR001)</small>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Contact Person</label>
                        <input type="text" name="contact_name" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Category</label>
                        <input type="text" name="category" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Phone</label>
                        <input type="text" name="phone" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Email</label>
                        <input type="email" name="email" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="margin-bottom: 15px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">VAT Number</label>
                    <input type="text" name="vat_number" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <div style="margin-bottom: 20px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Address</label>
                    <textarea name="address" rows="2" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></textarea>
                </div>
                <div style="display:flex;gap:10px;">
                    <button type="submit" class="btn btn-primary">Create Supplier</button>
                    <a href="/suppliers" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        '''
        
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
        all_expenses = db.get("expenses", {"business_id": biz_id}) if biz_id and can_see_balances else []
        expenses = [e for e in all_expenses if e.get("supplier_id") == supplier_id]
        expenses = sorted(expenses, key=lambda x: x.get("date", ""), reverse=True)
        
        # Get supplier invoices (imported from Sage etc)
        all_supplier_invoices = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id and can_see_balances else []
        supplier_invoices = [si for si in all_supplier_invoices if si.get("supplier_id") == supplier_id]
        supplier_invoices = sorted(supplier_invoices, key=lambda x: x.get("date", ""), reverse=True)
        
        # Get payments to supplier (only if can see balances)
        all_payments = db.get("supplier_payments", {"business_id": biz_id}) if biz_id and can_see_balances else []
        payments = [p for p in all_payments if p.get("supplier_id") == supplier_id]
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
        balance = float(supplier.get("balance", 0)) if can_see_balances else 0
        
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
                supplier_inv_html += f'''
                <tr style="cursor:pointer;" onclick="window.location='/supplier-invoice/{si.get("id")}'">
                    <td>{safe_string(si.get("invoice_number", "-"))}</td>
                    <td>{si.get("date", "-")}</td>
                    <td>{si.get("due_date", "-")}</td>
                    <td>{money(si.get("total", 0))}</td>
                    <td style="color:{si_color};">{si_status.upper()}</td>
                </tr>
                '''
        
        payments_html = ""
        if can_see_balances:
            for p in payments[:200]:
                payments_html += f'''
                <tr>
                    <td>{p.get("reference", "-")}</td>
                    <td>{p.get("date", "-")}</td>
                    <td style="color:var(--green);">{money(p.get("amount", 0))}</td>
                    <td>{p.get("method", "-")}</td>
                </tr>
                '''
        
        # Build scanned documents HTML - hide amounts for staff
        scanned_docs_html = ""
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
        
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px;">
            <div class="card">
                <h3 style="margin-bottom:15px;">Recent Bills/Expenses</h3>
                <table class="table">
                    <thead>
                        <tr><th>Reference</th><th>Date</th><th>Description</th><th>Amount</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                        {expenses_html or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted);'>No expenses yet</td></tr>"}
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h3 style="margin-bottom:15px;">Payments Made</h3>
                <table class="table">
                    <thead>
                        <tr><th>Reference</th><th>Date</th><th>Amount</th><th>Method</th></tr>
                    </thead>
                    <tbody>
                        {payments_html or "<tr><td colspan='4' style='text-align:center;color:var(--text-muted);'>No payments yet</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        ''' + (f'''
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">Invoices ({len(supplier_invoices)})</h3>
            <table class="table">
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
            <h3 style="margin-bottom:15px;">📋 Purchase Orders ({len(purchase_orders)})</h3>
            <table class="table">
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
                        <input type="number" id="capInvAmount" placeholder="0.00" step="0.01" min="0.01" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);font-size:18px;font-weight:700;">
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <input type="checkbox" id="capInvVat" checked>
                        <label for="capInvVat" style="font-size:13px;">VAT Inclusive (15%)</label>
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
            <div style="background:var(--card);border-radius:12px;padding:30px;width:90%;max-width:500px;border:1px solid var(--border);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                    <h2 style="margin:0;">💰 Record Payment</h2>
                    <button onclick="document.getElementById('paymentModal').style.display='none'" style="background:none;border:none;color:var(--text-muted);font-size:24px;cursor:pointer;">&times;</button>
                </div>
                <p style="color:var(--text-muted);margin-bottom:16px;font-size:13px;">Pay <strong>{safe_string(supplier.get("name", ""))}</strong> — balance: <strong style="color:var(--orange);">R{float(supplier.get("balance", 0)):,.2f}</strong></p>
                
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
                        <input type="text" id="payRef" placeholder="e.g. INV-001, POP ref, etc." style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
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
        
        document.getElementById('paymentModal').addEventListener('click', function(e) {{
            if (e.target === this) this.style.display = 'none';
        }});
        
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
                reference: document.getElementById('payRef').value.trim()
            }};
            
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
    
    
    @app.route("/supplier/<supplier_id>/edit", methods=["GET", "POST"])
    @login_required
    def supplier_edit(supplier_id):
        """Edit supplier"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        supplier = db.get_one("suppliers", supplier_id)
        if not supplier:
            return redirect("/suppliers")
        
        if request.method == "POST":
            supplier["name"] = request.form.get("name", "").strip()
            supplier["phone"] = request.form.get("phone", "").strip()
            supplier["email"] = request.form.get("email", "").strip()
            supplier["address"] = request.form.get("address", "").strip()
            
            try:
                supplier["balance"] = float(request.form.get("balance", 0) or 0)
            except:
                pass
            
            db.save("suppliers", supplier)
            flash(f"Supplier '{supplier['name']}' updated!", "success")
            return redirect(f"/supplier/{supplier_id}")
        
        content = f'''
        <div style="margin-bottom:20px;">
            <a href="/supplier/{supplier_id}" style="color:var(--text-muted);">← Back to {safe_string(supplier.get("name", "Supplier"))}</a>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:20px;">Edit Supplier</h2>
            <form method="POST">
                <div style="margin-bottom: 20px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Name *</label>
                    <input type="text" name="name" value="{safe_string(supplier.get("name", ""))}" required 
                        style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <div style="margin-bottom: 20px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Phone</label>
                    <input type="text" name="phone" value="{safe_string(supplier.get("phone", ""))}"
                        style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <div style="margin-bottom: 20px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Email</label>
                    <input type="email" name="email" value="{safe_string(supplier.get("email", ""))}"
                        style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <div style="margin-bottom: 20px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Address</label>
                    <textarea name="address" rows="2" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">{safe_string(supplier.get("address", ""))}</textarea>
                </div>
                <div style="margin-bottom: 20px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Balance (we owe them)</label>
                    <input type="number" name="balance" value="{supplier.get("balance", 0)}" step="0.01"
                        style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <div style="display:flex;gap:10px;">
                    <button type="submit" class="btn btn-primary">Save Changes</button>
                    <a href="/supplier/{supplier_id}" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        '''
        
        return render_page("Edit Supplier", content, user, "suppliers")
    
    

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
        business = Auth.get_current_business()
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
            <div style="padding:0 25px;">
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
            @media print {{ body {{ padding:0; }} @page {{ size:A4;margin:10mm 12mm; }} }}</style></head><body>${{content}}</body></html>`);
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
                <span class="line-total" style="text-align:right;font-weight:600;">R{item.get('total', 0):.2f}</span>
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
                        <div class="po-totals-row"><span>Subtotal</span><span id="subtotal">R{po.get('subtotal', 0):.2f}</span></div>
                        <div class="po-totals-row"><span>VAT (15%)</span><span id="vat">R{po.get('vat', 0):.2f}</span></div>
                        <div class="po-totals-row grand"><span>Total</span><span id="total">R{po.get('total', 0):.2f}</span></div>
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
                    
                    # Now update the stock quantity
                    if stock_item:
                        current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                        new_qty = current_qty + qty_received
                        db.update_stock(stock_item["id"], {"qty": new_qty, "quantity": new_qty}, biz_id)
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
                    
                    # Update stock cost price if price was entered
                    if unit_price and items[idx].get("stock_id") and update_stock:
                        try:
                            db.update_stock(items[idx]["stock_id"], {"cost_price": float(unit_price)}, biz_id)
                        except:
                            pass
                    
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
                
                for i, desc in enumerate(descriptions):
                    if desc.strip():
                        qty = float(quantities[i] or 0)
                        price = float(prices[i] or 0)
                        line_total = qty * price
                        subtotal += line_total
                        invoice_items.append({
                            "description": desc.strip(),
                            "quantity": qty,
                            "unit_price": price,
                            "line_total": round(line_total, 2)
                        })
                
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
                        create_journal_entry(biz_id, today(), f"Supplier Invoice {inv_number} - {po.get('supplier_name')}", inv_number, [
                            {"account_code": gl(biz_id, "purchases"), "debit": float(subtotal), "credit": 0},  # Cost of Sales/Purchases
                            {"account_code": gl(biz_id, "vat_input"), "debit": float(vat), "credit": 0},
                            {"account_code": gl(biz_id, "creditors"), "debit": 0, "credit": float(total)},
                        ])
                        
                        if po.get("supplier_id"):
                            supplier = db.get_one("suppliers", po.get("supplier_id"))
                            if supplier:
                                new_balance = float(supplier.get("balance") or 0) + float(total)
                                db.update("suppliers", po.get("supplier_id"), {"balance": new_balance})
                    except Exception as e:
                        logger.error(f"[PO] GL entry failed: {e}")
                    
                    flash(f"Supplier invoice {inv_number} created - {money(total)}", "success")
                    return redirect("/supplier-invoices")
                
                flash("Failed to create supplier invoice", "error")
                return redirect(f"/purchase/{po_id}")
            
            # GET - show form with items from PO
            items_html = ""
            for i, item in enumerate(po_items):
                desc = item.get("description") or item.get("code") or "-"
                qty = item.get("qty") or item.get("quantity") or 1
                price = item.get("price") or item.get("unit_price") or ""
                
                items_html += f'''
                <tr>
                    <td><input type="text" name="item_desc[]" class="form-input" value="{safe_string(desc)}" style="width:100%;"></td>
                    <td><input type="number" name="item_qty[]" class="form-input" value="{qty}" step="any" style="width:80px;text-align:center;" onchange="calcTotals()"></td>
                    <td><input type="number" name="item_price[]" class="form-input" value="{price}" step="0.01" placeholder="0.00" style="width:120px;text-align:right;" onchange="calcTotals()"></td>
                    <td style="text-align:right;" class="line-total">R 0.00</td>
                </tr>
                '''
            
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
            
            rows += f'''
            <tr>
                <td><strong>{inv_num}</strong></td>
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
                <button class="btn btn-primary" onclick="document.getElementById('aiInput').value='Record supplier invoice from ';document.getElementById('aiInput').focus();">+ Record Invoice</button>
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
        }}
        function paySupplier(invNum) {{
            document.getElementById('aiInput').value = 'Pay supplier invoice ' + invNum;
            document.getElementById('sendBtn').click();
        }}
        </script>
        '''
        
        return render_page("Supplier Invoices", content, user, "supplier-invoices")
    
    

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
            
            # Calculate VAT
            if vat_inclusive:
                vat_amount = round(amount * 15 / 115, 2)
                net_amount = round(amount - vat_amount, 2)
                total_amount = round(amount, 2)
            else:
                net_amount = round(amount, 2)
                vat_amount = round(amount * 0.15, 2)
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
                status="paid" if is_paid else "outstanding",
                notes=description
            )
            inv_id = invoice["id"]
            
            success, err = db.save("supplier_invoices", invoice)
            if not success:
                return jsonify({"success": False, "error": f"Failed to save: {err}"})
            
            # Update supplier balance (if not paid, add to creditors)
            if supplier_id and not is_paid:
                try:
                    supplier = db.get_one("suppliers", supplier_id)
                    if supplier:
                        new_balance = float(supplier.get("balance", 0)) + total_amount
                        db.save("suppliers", {"id": supplier_id, "balance": new_balance})
                except Exception as e:
                    logger.error(f"[CAPTURE INV] Supplier balance update error: {e}")
            
            # Create GL journal entries
            try:
                if is_paid:
                    # Already paid: Debit Expense + VAT Input, Credit Bank
                    journal_entries = [
                        {"account_code": gl_code, "debit": net_amount, "credit": 0},
                    ]
                    if vat_amount > 0:
                        journal_entries.append({"account_code": gl(biz_id, "vat_input"), "debit": vat_amount, "credit": 0})
                    journal_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": total_amount})
                else:
                    # On account: Debit Expense + VAT Input, Credit Creditors
                    journal_entries = [
                        {"account_code": gl_code, "debit": net_amount, "credit": 0},
                    ]
                    if vat_amount > 0:
                        journal_entries.append({"account_code": gl(biz_id, "vat_input"), "debit": vat_amount, "credit": 0})
                    journal_entries.append({"account_code": gl(biz_id, "creditors"), "debit": 0, "credit": total_amount})
                
                create_journal_entry(biz_id, inv_date, f"{description or supplier_name} - {invoice_number}", invoice_number, journal_entries)
                logger.info(f"[CAPTURE INV] GL entries created: {gl_code} DR:{net_amount} for {supplier_name}")
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
            
            # Save supplier payment record
            payment = {
                "id": generate_id(),
                "business_id": biz_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "amount": round(amount, 2),
                "date": pay_date,
                "method": method,
                "reference": reference,
                "source": "manual",
                "created_by": user.get("name", user.get("email", "")),
                "created_at": now()
            }
            
            success, err = db.save("supplier_payments", payment)
            if not success:
                return jsonify({"success": False, "error": f"Failed to save payment: {err}"})
            
            # Update supplier balance
            if supplier_id:
                try:
                    supplier = db.get_one("suppliers", supplier_id)
                    if supplier:
                        old_balance = float(supplier.get("balance", 0))
                        new_balance = round(old_balance - amount, 2)
                        db.save("suppliers", {"id": supplier_id, "balance": new_balance})
                        logger.info(f"[PAY] Supplier balance: R{old_balance:,.2f} → R{new_balance:,.2f}")
                except Exception as e:
                    logger.error(f"[PAY] Balance update error: {e}")
            
            # GL journal: Debit Creditors, Credit Bank
            try:
                rounded = round(amount, 2)
                ref_label = reference or f"PAY-{payment['id'][:8]}"
                
                # Choose bank account based on method
                if method == "cash":
                    bank_code = gl(biz_id, "cash")
                elif method == "card":
                    bank_code = gl(biz_id, "bank")
                else:
                    bank_code = gl(biz_id, "bank")
                
                create_journal_entry(biz_id, pay_date, f"Payment to {supplier_name}", ref_label, [
                    {"account_code": gl(biz_id, "creditors"), "debit": rounded, "credit": 0},
                    {"account_code": bank_code, "debit": 0, "credit": rounded},
                ])
                logger.info(f"[PAY] GL entry: Creditors DR:{rounded}, Bank CR:{rounded} for {supplier_name}")
            except Exception as e:
                logger.error(f"[PAY] GL entry error (payment still saved): {e}")
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="supplier_payment", source_table="supplier_payments", source_id=payment["id"],
                        description=f"Payment to {supplier_name}",
                        amount=round(amount, 2),
                        gl_entries=[
                            {"account_code": gl(biz_id, "creditors"), "debit": rounded, "credit": 0},
                            {"account_code": bank_code, "debit": 0, "credit": rounded},
                        ],
                        category="Supplier Payment", category_code=gl(biz_id, "creditors"),
                        supplier_name=supplier_name, payment_method=method,
                        reference=reference or ref_label, transaction_date=pay_date,
                        created_by=user.get("id", ""), created_by_name=user.get("name", "")
                    )
            except Exception:
                pass
            
            return jsonify({
                "success": True,
                "message": f"Payment of R{amount:,.2f} to {supplier_name} recorded ({method.upper()})"
            })
            
        except Exception as e:
            logger.error(f"[PAY] Error: {e}")
            return jsonify({"success": False, "error": str(e)})

    logger.info("[PURCHASES] All supplier & purchase routes registered ✓")
