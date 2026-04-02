# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - INVOICING MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Invoices, Invoice APIs, Recurring Invoices, Quotes, Delivery Notes
# ==============================================================================

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def register_invoicing_routes(app, db, login_required, Auth, render_page,
                              generate_id, money, safe_string, safe_uuid,
                              next_document_number, get_user_role, now, today,
                              gl, create_journal_entry, log_allocation,
                              has_reactor_hud, jarvis_hud_header, jarvis_techline,
                              RecordFactory, Email, FraudGuard, RecurringInvoices,
                              JARVIS_HUD_CSS, THEME_REACTOR_SKINS, VAT_RATE):
    """Register all Invoicing routes with the Flask app."""

    # === INVOICES + RECURRING INVOICES ===

    @app.route("/invoices")
    @login_required
    def invoices_page():
        """Invoices list - FAST direct query"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # FAST: Direct query with order and limit
        try:
            invoices = db.get("invoices", {"business_id": biz_id}, limit=200)
            # Sort by date descending
            invoices = sorted(invoices, key=lambda x: x.get("date", ""), reverse=True)
        except Exception as e:
            logger.error(f"[INVOICES] Error loading: {e}")
            invoices = []
        
        rows = ""
        for inv in invoices:
            status = inv.get("status", "")
            status_colors = {"paid": "var(--green)", "delivered": "#3b82f6", "credited": "var(--red)", "outstanding": "var(--orange)", "account": "#f59e0b"}
            status_color = status_colors.get(status, "var(--text-muted)")
            rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='/invoice/{inv.get("id")}'">
                <td><strong>{inv.get("invoice_number", "-")}</strong></td>
                <td>{inv.get("date", "-")}</td>
                <td>{safe_string(inv.get("customer_name", "-"))}</td>
                <td>{money(inv.get("total", 0))}</td>
                <td style="color:{status_color}">{status}</td>
            </tr>
            '''
        
        content = f'''
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 class="card-title" style="margin:0;">Invoices ({len(invoices)})</h3>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <a href="/recurring-invoices" class="btn btn-secondary">🔄 Recurring</a>
                    <a href="/rentals" class="btn btn-secondary">🏠 Rentals</a>
                    <a href="/subscriptions" class="btn btn-secondary">📦 Subscriptions</a>
                    <a href="/invoice/new" class="btn btn-primary">+ New Invoice</a>
                </div>
            </div>
            <div style="margin-bottom:15px;">
                <input type="text" id="searchInvoices" placeholder="🔍 Search by customer, invoice number, amount..." oninput="filterTable('searchInvoices','invoiceTable')" style="width:100%;padding:10px 15px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;">
            </div>
            <table class="table" id="invoiceTable">
                <thead>
                    <tr><th>Number</th><th>Date</th><th>Customer</th><th>Amount</th><th>Status</th></tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted)'>No invoices yet</td></tr>"}
                </tbody>
            </table>
        </div>
        '''
        
        # -- JARVIS: Invoices HUD header --
        if has_reactor_hud():
            _total_inv = len(invoices)
            _paid = len([i for i in invoices if i.get("status") == "paid"])
            _outstanding = len([i for i in invoices if i.get("status") in ("outstanding", "account")])
            _total_amt = sum(float(i.get("total", 0) or 0) for i in invoices)
            _paid_amt = sum(float(i.get("total", 0) or 0) for i in invoices if i.get("status") == "paid")
            _owed_amt = sum(float(i.get("total", 0) or 0) for i in invoices if i.get("status") in ("outstanding", "account"))
            
            _hud = jarvis_hud_header(
                page_name="INVOICES",
                page_count=f"{_total_inv} RECORDS LOADED",
                left_items=[
                    ("INVOICES", str(_total_inv), "c", "", ""),
                    ("TOTAL VALUE", money(_total_amt), "c", "", ""),
                    ("PAID", str(_paid), "g", "g", "g"),
                    ("PAID VALUE", money(_paid_amt), "g", "g", "g"),
                ],
                right_items=[
                    ("OUTSTANDING", str(_outstanding), "o", "o", "o"),
                    ("OWED TO US", money(_owed_amt), "r", "r", "r"),
                    ("CREDITED", str(len([i for i in invoices if i.get("status") == "credited"])), "r", "", ""),
                    ("DELIVERED", str(len([i for i in invoices if i.get("status") == "delivered"])), "c", "", ""),
                ],
                reactor_size="page",
                alert_html=""
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline(f"INVOICES <b>{_total_inv} LOADED</b>")
        
        return render_page("Invoices", content, user, "invoices")
    
    
    @app.route("/invoice/new", methods=["GET", "POST"])
    @login_required
    def invoice_new():
        """Create new invoice - manual form"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            # Handle form submission
            customer_id = request.form.get("customer_id", "")
            customer_name = request.form.get("customer_name", "")
            payment_method = request.form.get("payment_method", "account")  # account/cash/card/eft
            inv_salesman_id = request.form.get("salesman_id", "")
            inv_salesman_name_form = request.form.get("salesman_name", "")
            invoice_date = request.form.get("invoice_date", "") or today()
            inv_reference = request.form.get("reference", "").strip()
            inv_delivery_note = request.form.get("delivery_note", "").strip()
            
            # FAILSAFE: If customer_name is empty but customer_id is set, look it up
            if not customer_name and customer_id:
                try:
                    _cust = db.get_one("customers", customer_id)
                    if _cust:
                        customer_name = _cust.get("name", "")
                        logger.info(f"[INVOICE NEW] Resolved customer name: {customer_name}")
                except Exception:
                    pass
            
            # Get line items from form
            items = []
            descriptions = request.form.getlist("item_desc[]")
            quantities = request.form.getlist("item_qty[]")
            prices = request.form.getlist("item_price[]")
            units = request.form.getlist("item_unit[]")
            
            subtotal = Decimal("0")
            for i, desc in enumerate(descriptions):
                if desc.strip():
                    qty = Decimal(quantities[i] or "1")
                    price = Decimal(prices[i] or "0")
                    line_total = qty * price
                    subtotal += line_total
                    unit_val = units[i].strip() if i < len(units) else ""
                    items.append({
                        "description": desc,
                        "unit": unit_val,
                        "quantity": float(qty),
                        "price": float(price),
                        "total": float(line_total)
                    })
            
            if not items:
                return redirect("/invoice/new?error=No+items")
            
            # Prices are EXCL VAT - ADD VAT to get total
            # subtotal = sum of line items (EXCL VAT)
            vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
            total = subtotal + vat
            
            # Generate invoice number (safe even after deletions)
            existing = db.get("invoices", {"business_id": biz_id}) or []
            inv_num = next_document_number("INV-", existing, "invoice_number")
            
            # Save invoice
            invoice = RecordFactory.invoice(
                business_id=biz_id,
                customer_id=safe_uuid(customer_id),
                customer_name=customer_name,
                items=items,
                invoice_number=inv_num,
                date=invoice_date,
                subtotal=float(subtotal),
                vat=float(vat),
                total=float(total),
                payment_method=payment_method,
                status="paid" if payment_method in ("cash", "card", "eft") else "outstanding",
                created_by=user.get("id", "") if user else "",
                created_by_name=user.get("name", "") if user else "",
                salesman=inv_salesman_id,
                salesman_name=inv_salesman_name_form,
                sales_rep=inv_salesman_name_form,
                reference=inv_reference,
                delivery_note=inv_delivery_note
            )
            invoice_id = invoice["id"]
            
            success, _ = db.save("invoices", invoice)
            
            if success:
                # === DEDUCT STOCK ===
                # Get stock_ids from form if provided
                stock_ids = request.form.getlist("item_stock_id[]")
                for i, desc in enumerate(descriptions):
                    if desc.strip() and i < len(stock_ids) and stock_ids[i]:
                        stock_id = stock_ids[i]
                        stock_item = db.get_one_stock(stock_id)
                        if stock_item:
                            current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                            sold_qty = float(quantities[i] or 0)
                            new_qty = current_qty - sold_qty
                            db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
                            logger.info(f"[INVOICE] Stock {stock_id}: {current_qty} - {sold_qty} = {new_qty}")
                
                # Try to create journal entries (won't crash if tables don't exist)
                try:
                    if payment_method == "account":
                        # Debit Debtors, Credit Sales + VAT
                        create_journal_entry(biz_id, today(), f"Invoice {inv_num} - {customer_name}", inv_num, [
                            {"account_code": gl(biz_id, "debtors"), "debit": float(total), "credit": 0},
                            {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": float(subtotal)},
                            {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": float(vat)},
                        ])
                        # Update customer balance
                        if customer_id:
                            customer = db.get_one("customers", customer_id)
                            if customer:
                                new_balance = float(customer.get("balance", 0)) + float(total)
                                db.update("customers", customer_id, {"balance": new_balance})
                    else:
                        # Cash/Card/EFT - Debit Bank/Cash, Credit Sales + VAT
                        bank_account = "1050" if payment_method == "cash" else "1000"
                        create_journal_entry(biz_id, today(), f"Invoice {inv_num} - {customer_name} ({payment_method.upper()})", inv_num, [
                            {"account_code": bank_account, "debit": float(total), "credit": 0},
                            {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": float(subtotal)},
                            {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": float(vat)},
                        ])
                except Exception as e:
                    logger.error(f"GL entry failed (non-critical): {e}")
                
                # === ALLOCATION LOG ===
                try:
                    if log_allocation:
                        _bank = "1050" if payment_method == "cash" else "1000"
                        _gl = [
                            {"account_code": _bank if payment_method != "account" else "1200", "debit": float(total), "credit": 0},
                            {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": float(subtotal)},
                            {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": float(vat)},
                        ]
                        log_allocation(
                            business_id=biz_id, allocation_type="invoice", source_table="invoices", source_id=invoice_id,
                            description=f"Invoice {inv_num} - {customer_name}",
                            amount=float(total), gl_entries=_gl,
                            customer_name=customer_name, payment_method=payment_method, reference=inv_num,
                            transaction_date=today(),
                            created_by=user.get("id") if user else "", created_by_name=user.get("name", "") if user else ""
                        )
                except Exception:
                    pass
                
                return redirect(f"/invoice/{invoice_id}")
            
            return redirect("/invoice/new?error=Failed+to+save")
        
        # GET - show form (stock via AJAX typeahead now)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_customers = executor.submit(db.get, "customers", {"business_id": biz_id})
            fut_team = executor.submit(db.get, "team_members", {"business_id": biz_id})
        customers = fut_customers.result() if biz_id else []
        inv_team_members = fut_team.result() if biz_id else []
        
        # Check if customer_id is passed in URL
        preselect_customer_id = request.args.get("customer_id", "")
        
        customer_options = '<option value="">-- Select Customer --</option>'
        customer_options += '<option value="NEW" style="color:var(--primary);">+ Add New Customer</option>'
        for c in sorted(customers, key=lambda x: x.get("name", "")):
            selected = 'selected' if c.get("id") == preselect_customer_id else ''
            customer_options += f'<option value="{c.get("id")}" data-name="{safe_string(c.get("name", ""))}" {selected}>{safe_string(c.get("name", ""))}</option>'
        
        # Salesman dropdown for invoice
        inv_salesman_opts = '<option value="">-- Select Salesman --</option>'
        if user:
            inv_salesman_opts += f'<option value="{user.get("id", "")}" data-name="{safe_string(user.get("name", ""))}" selected>{safe_string(user.get("name", ""))} (me)</option>'
        _inv_seen = {user.get("id", "") if user else ""}
        for tm in sorted(inv_team_members, key=lambda x: x.get("name", "")):
            tm_uid = tm.get("user_id") or tm.get("id", "")
            if tm_uid not in _inv_seen:
                _inv_seen.add(tm_uid)
                inv_salesman_opts += f'<option value="{tm_uid}" data-name="{safe_string(tm.get("name", ""))}">{safe_string(tm.get("name", ""))}</option>'
        
        error_msg = request.args.get("error", "")
        error_html = f'<div style="background:var(--red);color:white;padding:10px;border-radius:8px;margin-bottom:15px;">{error_msg}</div>' if error_msg else ""
        
        _dd_css = '<style>.stock-dropdown{position:absolute;top:100%;left:0;right:0;background:var(--card);border:1px solid var(--border);border-radius:6px;max-height:220px;overflow-y:auto;z-index:999;box-shadow:0 4px 12px rgba(0,0,0,0.3);}.stock-dd-item{padding:8px 10px;cursor:pointer;font-size:13px;border-bottom:1px solid var(--border);}.stock-dd-item:hover{background:var(--primary);color:white;}</style>'
        
        content = f'''
        {_dd_css}
        {error_html}
        <div class="card">
            <h3 style="margin:0 0 20px 0;">New Invoice</h3>
            
            <form method="POST" id="invoiceForm">
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label>Customer</label>
                        <select name="customer_id" id="customerSelect" onchange="handleCustomerChange()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            {customer_options}
                        </select>
                        <input type="hidden" name="customer_name" id="customerName">
                    </div>
                    <div>
                        <label>Salesman</label>
                        <select name="salesman_id" id="invSalesmanSelect" onchange="document.getElementById('invSalesmanName').value=this.options[this.selectedIndex]?.dataset?.name||''" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            {inv_salesman_opts}
                        </select>
                        <input type="hidden" name="salesman_name" id="invSalesmanName" value="{safe_string(user.get('name', '')) if user else ''}">
                    </div>
                    <div>
                        <label>Payment Method</label>
                        <select name="payment_method" id="paymentMethod" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            <option value="account">[FORM] Account (Outstanding)</option>
                            <option value="cash">💵 Cash</option>
                            <option value="card">[PAY] Card</option>
                            <option value="eft">[BANK] EFT</option>
                        </select>
                    </div>
                    <div>
                        <label>Date</label>
                        <input type="date" name="invoice_date" value="{today()}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label>Reference</label>
                        <input type="text" name="reference" placeholder="e.g. PO number, order ref" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label>Delivery Note No</label>
                        <input type="text" name="delivery_note" placeholder="e.g. DN-0045" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h4>Line Items</h4>
                
                <table class="table" id="lineItems">
                    <thead>
                        <tr>
                            <th style="width:38%">Description</th>
                            <th style="width:10%">Unit</th>
                            <th style="width:10%">Qty</th>
                            <th style="width:17%">Price (excl)</th>
                            <th style="width:15%">Total</th>
                            <th style="width:10%"></th>
                        </tr>
                    </thead>
                    <tbody id="itemRows">
                        <tr>
                            <td style="position:relative;">
                                <input type="text" name="item_desc[]" autocomplete="off" oninput="stockSearch(this)" onfocus="stockSearch(this)" placeholder="Type 2+ chars to search stock..." style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);">
                                <input type="hidden" name="item_stock_id[]" value="">
                                <div class="stock-dropdown" style="display:none;"></div>
                            </td>
                            <td><input type="text" name="item_unit[]" placeholder="ea" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);text-align:center;"></td>
                            <td><input type="number" name="item_qty[]" value="1" min="0.01" step="any" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                            <td><input type="number" name="item_price[]" step="0.01" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                            <td class="row-total">R0.00</td>
                            <td><button type="button" onclick="deleteRow(this)" style="background:var(--red);color:white;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;">✕</button></td>
                        </tr>
                    </tbody>
                </table>
                
                <button type="button" onclick="addRow()" class="btn btn-secondary" style="margin:10px 0;">+ Add Line</button>
                
                <div style="text-align:right;margin-top:20px;padding:15px;background:rgba(0,0,0,0.2);border-radius:8px;">
                    <div style="margin-bottom:10px;">Subtotal: <strong id="subtotal">R0.00</strong></div>
                    <div style="margin-bottom:10px;">VAT (15%): <strong id="vat">R0.00</strong></div>
                    <div style="font-size:24px;">Total: <strong id="total" style="color:var(--green);">R0.00</strong></div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:20px;">
                    <button type="submit" class="btn btn-primary" style="flex:1;">Create Invoice</button>
                    <a href="/invoices" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <script>
        function handleCustomerChange() {{
            const sel = document.getElementById('customerSelect');
            if (sel.value === 'NEW') {{
                window.location.href = '/customer/new?return=/invoice/new';
                return;
            }}
            const name = sel.options[sel.selectedIndex]?.dataset?.name || '';
            document.getElementById('customerName').value = name;
        }}
        
        // Run on page load to set customer name if pre-selected
        document.addEventListener('DOMContentLoaded', function() {{
            handleCustomerChange();
        }});
        
        // Validate form before submit — block zero amount invoices
        let _skipZeroCheck = false;
        document.getElementById('invoiceForm').addEventListener('submit', function(e) {{
            // Check customer name is set
            const custName = document.getElementById('customerName').value.trim();
            const custSel = document.getElementById('customerSelect').value;
            if (!custSel || custSel === '') {{
                e.preventDefault();
                alert('⚠️ Please select a customer');
                return false;
            }}
            if (!custName) {{
                handleCustomerChange();
            }}
            
            // Check total is not zero (skip if already confirmed)
            if (!_skipZeroCheck) {{
                let subtotal = 0;
                document.querySelectorAll('.row-total').forEach(cell => {{
                    subtotal += parseFloat(cell.textContent.replace('R', '')) || 0;
                }});
                if (subtotal <= 0) {{
                    e.preventDefault();
                    if (confirm('⚠️ Invoice total is R0.00\\n\\nAre you sure you want to create a zero-amount invoice?')) {{
                        _skipZeroCheck = true;
                        // Show loading state so user knows it is working
                        const btn = e.target.querySelector('button[type="submit"]');
                        if (btn) {{ btn.disabled = true; btn.textContent = 'Creating...'; }}
                        e.target.submit();
                    }} else {{
                        // User cancelled — flash the total red so they know what to fix
                        const tot = document.getElementById('total');
                        if (tot) {{
                            tot.style.color = 'var(--red)';
                            tot.style.transition = 'color 0.3s';
                            setTimeout(() => {{ tot.style.color = 'var(--green)'; }}, 2000);
                        }}
                    }}
                    return false;
                }}
            }}
            // Normal submit — show loading state
            const btn = e.target.querySelector('button[type="submit"]');
            if (btn) {{ btn.disabled = true; btn.textContent = 'Creating...'; }}
        }});
        
        function checkStock(input) {{ /* stub */ }}
        let _searchTimer = null;
        function stockSearch(input) {{
            const q = input.value.trim();
            const dd = input.closest('td').querySelector('.stock-dropdown');
            if (q.length < 2) {{ dd.style.display='none'; return; }}
            clearTimeout(_searchTimer);
            _searchTimer = setTimeout(()=>{{
                fetch('/api/stock/lookup?q='+encodeURIComponent(q)).then(r=>r.json()).then(items=>{{
                    if(!items.length){{ dd.style.display='none'; return; }}
                    let h='';
                    items.forEach(s=>{{
                        const lb=(s.label||'').replace(/'/g,"\\'"), un=(s.unit||'').replace(/'/g,"\\'");
                        h+='<div class="stock-dd-item" onmousedown="pickStock(this,\\''+s.id+'\\',\\''+lb+'\\','+s.price+',\\''+un+'\\')">'
                          +'<b>'+(s.code||'')+'</b> '+(s.desc||'')+' <span style="float:right;color:#22c55e;">R'+s.price.toFixed(2)+'</span>'
                          +(s.unit?'<span style="color:#888;font-size:11px;margin-left:4px;">'+s.unit+'</span>':'')+'</div>';
                    }});
                    dd.innerHTML=h; dd.style.display='block';
                }});
            }}, 250);
        }}
        function pickStock(el,stockId,label,price,unit){{
            const row=el.closest('tr');
            row.querySelector('input[name="item_desc[]"]').value=label;
            const sid=row.querySelector('input[name="item_stock_id[]"]'); if(sid) sid.value=stockId;
            const p=row.querySelector('input[name="item_price[]"]'); p.value=price;
            const u=row.querySelector('input[name="item_unit[]"]'); if(u&&unit) u.value=unit;
            el.closest('.stock-dropdown').style.display='none'; calcRow(p);
        }}
        document.addEventListener('click',function(e){{
            if(!e.target.closest('.stock-dropdown')&&!e.target.matches('input[name="item_desc[]"]'))
                document.querySelectorAll('.stock-dropdown').forEach(d=>d.style.display='none');
        }});
        
        function addRow() {{
            const tbody = document.getElementById('itemRows');
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="position:relative;">
                    <input type="text" name="item_desc[]" autocomplete="off" oninput="stockSearch(this)" onfocus="stockSearch(this)" placeholder="Type 2+ chars to search stock..." style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);">
                    <input type="hidden" name="item_stock_id[]" value="">
                    <div class="stock-dropdown" style="display:none;"></div>
                </td>
                <td><input type="text" name="item_unit[]" placeholder="ea" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);text-align:center;"></td>
                <td><input type="number" name="item_qty[]" value="1" min="0.01" step="any" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td><input type="number" name="item_price[]" step="0.01" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td class="row-total">R0.00</td>
                <td><button type="button" onclick="deleteRow(this)" style="background:var(--red);color:white;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;">\u2715</button></td>
            `;
            tbody.appendChild(row);
        }}
        
        function deleteRow(btn) {{
            const tbody = document.getElementById('itemRows');
            if (tbody.children.length > 1) {{
                btn.closest('tr').remove();
                calcTotals();
            }} else {{
                alert('Need at least one line item');
            }}
        }}
        
        function calcRow(input) {{
            const row = input.closest('tr');
            const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
            const price = parseFloat(row.querySelector('input[name="item_price[]"]').value) || 0;
            const total = qty * price;
            row.querySelector('.row-total').textContent = 'R' + total.toFixed(2);
            calcTotals();
        }}
        
        function calcTotals() {{
            let subtotal = 0;
            document.querySelectorAll('.row-total').forEach(cell => {{
                subtotal += parseFloat(cell.textContent.replace('R', '')) || 0;
            }});
            const vat = subtotal * 0.15;
            const total = subtotal + vat;
            document.getElementById('subtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('vat').textContent = 'R' + vat.toFixed(2);
            document.getElementById('total').textContent = 'R' + total.toFixed(2);
        }}
        </script>
        '''
        
        return render_page("New Invoice", content, user, "invoices")
    
    
    @app.route("/invoice/<invoice_id>")
    @login_required
    def invoice_view(invoice_id):
        """View single invoice with PDF option"""
        
        user = Auth.get_current_user()
        
        # Load business FRESH from DB (not cached) for accurate details on invoice
        biz_id = session.get("business_id")
        business = db.get_one("businesses", biz_id) if biz_id else Auth.get_current_business()
        
        invoice = db.get_one("invoices", invoice_id)
        if not invoice:
            return redirect("/invoices")
        
        # FAILSAFE: Calculate totals from items if missing or zero
        raw_items = invoice.get("items", [])
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except:
                raw_items = []
        
        # Calculate from line items
        if raw_items:
            line_total = sum(float(item.get("total", 0)) for item in raw_items)
            if line_total > 0:
                # Line totals are EXCL VAT - ADD VAT
                calculated_subtotal = line_total
                calculated_vat = round(line_total * 0.15, 2)
                calculated_total = round(line_total + calculated_vat, 2)
                
                # Use calculated values if stored values are missing or wrong
                if not invoice.get("subtotal") or float(invoice.get("subtotal", 0)) == 0:
                    invoice["subtotal"] = calculated_subtotal
                if not invoice.get("vat") or float(invoice.get("vat", 0)) == 0:
                    invoice["vat"] = calculated_vat
                if not invoice.get("total") or float(invoice.get("total", 0)) == 0:
                    invoice["total"] = calculated_total
        
        # Get customer details if customer_id exists
        customer = None
        if invoice.get("customer_id"):
            customer = db.get_one("customers", invoice.get("customer_id"))
        
        # Fallback: search by name if ID didn't find a customer
        if not customer and invoice.get("customer_name") and invoice.get("customer_name") != "Cash":
            all_customers = db.get("customers", {"business_id": biz_id}) if biz_id else []
            inv_name = invoice.get("customer_name", "").lower().strip()
            for c in all_customers:
                if c.get("name", "").lower().strip() == inv_name:
                    customer = c
                    logger.info(f"[INVOICE VIEW] Found customer by name match: {c.get('name')}")
                    break
        
        # Parse items - handle both JSON string and list
        raw_items = invoice.get("items", [])
        if isinstance(raw_items, str):
            try:
                items = json.loads(raw_items)
            except:
                items = []
        else:
            items = raw_items if raw_items else []
        
        items_count = len(items)
        logger.info(f"[INVOICE VIEW] Invoice {invoice.get('invoice_number')}: {items_count} items")
        
        items_html = ""
        for item in items:
            # Handle both qty and quantity field names
            qty = item.get("qty") or item.get("quantity") or 1
            desc = item.get("description") or item.get("desc") or "-"
            unit = item.get("unit") or item.get("uom") or ""
            price = float(item.get("price") or item.get("unit_price") or 0)
            total_excl = float(item.get("total") or item.get("line_total") or 0)
            # If no line total, calculate
            if total_excl == 0 and price > 0:
                total_excl = round(float(qty) * price, 2)
            disc = float(item.get("discount") or item.get("disc") or 0)
            vat_rate = 15.0
            vat_amount = round(total_excl * vat_rate / 100, 2)
            total_incl = round(total_excl + vat_amount, 2)
            items_html += f'''
            <tr style="border-bottom:1px solid #e5e7eb;">
                <td style="padding:4px 6px;font-size:11px;">{safe_string(desc)}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{safe_string(unit)}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{qty}</td>
                <td style="text-align:right;padding:4px 6px;font-size:11px;">{money(price)}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{disc:.1f}%</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{vat_rate:.0f}%</td>
                <td style="text-align:right;padding:4px 6px;font-size:11px;">{money(total_excl)}</td>
                <td style="text-align:right;padding:4px 6px;font-size:11px;font-weight:600;">{money(total_incl)}</td>
            </tr>
            '''
        
        status = invoice.get("status", "outstanding")
        status_colors = {
            "paid": "var(--green)",
            "credited": "var(--red)",
            "delivered": "#3b82f6",  # Blue for delivered
            "outstanding": "var(--orange)",
            "account": "#f59e0b"  # Amber for on account
        }
        status_color = status_colors.get(status, "var(--orange)")
        status_badge = f'<span style="background:{status_color};color:white;padding:4px 12px;border-radius:20px;font-size:12px;">{status.upper()}</span>'
        
        biz_name = business.get("name", "Business") if business else "Business"
        
        # Show credit note button - only hide if already fully credited
        cn_btn = "" if status == "credited" else f'<a href="/invoice/{invoice_id}/credit-note" class="btn btn-secondary">Credit Note</a>'
        
        # ── FRAUD GUARD: Hide credit note button if user not allowed ──
        try:
            if FraudGuard and cn_btn:
                _role = get_user_role()
                _guard = FraudGuard.can_cancel_invoice(invoice, _role)
                if not _guard.get("allowed"):
                    cn_btn = f'<span style="color:var(--text-muted);font-size:12px;padding:8px;" title="{_guard.get("reason", "")}">🔒 Credit Note (manager only)</span>'
        except Exception:
            pass
        
        # Delivery note button - hide if already delivered or paid
        dn_btn = "" if status in ("delivered", "paid", "credited") else f'<a href="/invoice/{invoice_id}/create-delivery-note" class="btn btn-secondary">Delivery Note</a>'
        
        # Payment buttons - show for outstanding, delivered, or account invoices
        payment_btns = ""
        if status in ("outstanding", "delivered", "account"):
            payment_btns = f'''
            <button class="btn btn-success" onclick="markPaid('cash')" style="background:var(--green);"><kbd style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:3px;font-size:10px;margin-right:4px;">F1</kbd>💵 Cash</button>
            <button class="btn btn-primary" onclick="markPaid('card')" style="background:#8b5cf6;"><kbd style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:3px;font-size:10px;margin-right:4px;">F2</kbd>💳 Card</button>
            <button class="btn btn-secondary" onclick="markPaid('eft')"><kbd style="background:rgba(0,0,0,0.2);padding:2px 6px;border-radius:3px;font-size:10px;margin-right:4px;">F3</kbd>🏦 EFT</button>
            <button class="btn btn-warning" onclick="markPaid('account')" style="background:var(--orange);">📋 Account</button>
            '''
        
        # Show source quote link if exists
        source_quote = ""
        if invoice.get("source_quote_id"):
            source_quote = f'<a href="/quote/{invoice.get("source_quote_id")}" style="color:var(--text-muted);font-size:12px;">From Quote: {invoice.get("source_quote_number", "View")}</a>'
        
        # Build business details section
        biz_address = safe_string(business.get("address", "")).replace("\n", "<br>") if business else ""
        biz_phone = business.get("phone", "") if business else ""
        biz_email = business.get("email", "") if business else ""
        biz_vat = business.get("vat_number", "") if business else ""
        
        # Resolve prepared by name
        inv_prepared_by = invoice.get("created_by_name") or ""
        if not inv_prepared_by:
            _icb = invoice.get("created_by") or ""
            if _icb:
                try:
                    _iteam = db.get("team_members", {"business_id": biz_id}) or []
                    for t in _iteam:
                        if t.get("id") == _icb or t.get("user_id") == _icb:
                            inv_prepared_by = t.get("name", t.get("email", ""))
                            break
                    if not inv_prepared_by:
                        _iu = db.get_one("users", _icb)
                        if _iu:
                            inv_prepared_by = _iu.get("name", _iu.get("email", ""))
                except:
                    pass
        
        # Resolve salesman name for invoice
        inv_salesman = invoice.get("salesman_name") or invoice.get("sales_rep") or ""
        if not inv_salesman:
            _ism = invoice.get("salesman") or ""
            if _ism:
                try:
                    _iteam2 = db.get("team_members", {"business_id": biz_id}) or []
                    for t in _iteam2:
                        if t.get("id") == _ism or t.get("user_id") == _ism:
                            inv_salesman = t.get("name", t.get("email", ""))
                            break
                    if not inv_salesman:
                        _iu2 = db.get_one("users", _ism)
                        if _iu2:
                            inv_salesman = _iu2.get("name", _iu2.get("email", ""))
                except:
                    pass
        
        # Build customer details section  
        cust_name = safe_string(invoice.get("customer_name", "-"))
        cust_phone = customer.get("phone", "") if customer else ""
        cust_cell = customer.get("cell", "") if customer else ""
        cust_email = customer.get("email", "") if customer else ""
        cust_address = safe_string(customer.get("address", "")).replace("\n", "<br>") if customer else ""
        cust_vat = customer.get("vat_number", "") if customer else ""
        
        # Use cell if no phone
        cust_tel = cust_phone or cust_cell
        
        # Email button - show customer email if available
        email_btn = f'<button class="btn btn-primary" onclick="showEmailModal()" style="background:#3b82f6;">Email</button>'
        
        # Pre-build invoice fields for template (Python 3.11 f-string compat)
        inv_reference = invoice.get("reference", "") or ""
        inv_delivery_note = invoice.get("delivery_note", "") or ""
        inv_sales_person = inv_salesman or inv_prepared_by or ""
        cust_payment_terms = customer.get("payment_terms", "") if customer else ""
        
        # Reference row - show if exists, editable area
        ref_row = f'<tr><td style="padding:4px 0;color:#888;">Reference:</td><td style="padding:4px 0;font-weight:600;">{safe_string(inv_reference)}</td></tr>' if inv_reference else ''
        dn_row = f'<tr><td style="padding:4px 0;color:#888;">Delivery Note:</td><td style="padding:4px 0;font-weight:600;">{safe_string(inv_delivery_note)}</td></tr>' if inv_delivery_note else ''
        sp_row = f'<tr><td style="padding:4px 0;color:#888;">Sales Person:</td><td style="padding:4px 0;font-weight:600;">{safe_string(inv_sales_person)}</td></tr>' if inv_sales_person else ''
        terms_row = f'<tr><td style="padding:4px 0;color:#888;">Payment Terms:</td><td style="padding:4px 0;font-weight:600;">{safe_string(cust_payment_terms)}</td></tr>' if cust_payment_terms else ''
        
        # Zero-amount balance warning
        inv_total = float(invoice.get("total", 0) or 0)
        zero_warning = ""
        if inv_total == 0 and status in ("outstanding", "account"):
            zero_warning = '<div class="no-print" style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);padding:12px 16px;border-radius:8px;margin-bottom:15px;display:flex;justify-content:space-between;align-items:center;"><div><strong>⚠️ Warning:</strong> This invoice has a R0.00 balance. No amount has been entered.</div><button class="btn btn-primary" onclick="document.getElementById(\'editFields\').style.display=\'block\';window.scrollTo(0,0);" style="white-space:nowrap;">✏️ Edit Invoice</button></div>'
        
        # Show error if redirected back from fraud guard
        _inv_error = request.args.get("error", "")
        _inv_error_html = f'<div style="background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--text);padding:12px 16px;border-radius:8px;margin-bottom:15px;"><strong>⚠</strong> {safe_string(_inv_error)}</div>' if _inv_error else ""
        
        content = f'''{_inv_error_html}{zero_warning}
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <div>
                <a href="/invoices" style="color:var(--text-muted);">← Back to Invoices</a>
                {f'<br>{source_quote}' if source_quote else ''}
            </div>
            <div style="display:flex;gap:10px;flex-wrap:wrap;">
                {payment_btns}
                {dn_btn}
                {cn_btn}
                {email_btn}
                <button class="btn btn-secondary" onclick="printDocument();">🖨️ Print</button>
            </div>
        </div>
        
        <!-- EMAIL MODAL -->
        <div id="emailModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:9999;align-items:center;justify-content:center;">
            <div style="background:var(--card);padding:30px;border-radius:12px;width:90%;max-width:450px;">
                <h3 style="margin-top:0;">Email Invoice</h3>
                <p style="color:var(--text-muted);margin-bottom:20px;">Send invoice <strong>{invoice.get("invoice_number", "")}</strong> to:</p>
                
                <input type="text" id="emailTo" value="{cust_email}" placeholder="customer@email.com" 
                       style="width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:16px;margin-bottom:10px;">
                <small style="color:var(--text-muted);display:block;margin-bottom:15px;">Multiple emails: separate with comma (e.g. john@co.za, admin@co.za)</small>
                
                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button onclick="closeEmailModal()" class="btn btn-secondary">Cancel</button>
                    <button onclick="sendInvoiceEmail()" class="btn btn-primary" style="background:#10b981;">Send Email</button>
                </div>
            </div>
        </div>
        
        <!-- EDIT INVOICE DETAILS (no-print) -->
        <div class="no-print card" style="margin-bottom:15px;">
            <div style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;" onclick="document.getElementById('editFields').style.display=document.getElementById('editFields').style.display==='none'?'block':'none'">
                <h3 style="margin:0;">✏️ Edit Invoice Details</h3>
                <span style="color:var(--text-muted);">▼</span>
            </div>
            <div id="editFields" style="display:none;margin-top:15px;">
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Invoice Date</label>
                        <input type="date" id="editDate" value="{invoice.get('date', '')}" class="form-input">
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Sales Person</label>
                        <input type="text" id="editSalesPerson" value="{safe_string(inv_sales_person)}" placeholder="e.g. Piet" class="form-input">
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Reference</label>
                        <input type="text" id="editReference" value="{safe_string(inv_reference)}" placeholder="e.g. PO12345" class="form-input">
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Delivery Note No</label>
                        <input type="text" id="editDeliveryNote" value="{safe_string(inv_delivery_note)}" placeholder="e.g. DN-0045" class="form-input">
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Due Date</label>
                        <input type="date" id="editDueDate" value="{invoice.get('due_date', '')}" class="form-input">
                    </div>
                </div>
                <button class="btn btn-primary" onclick="saveInvoiceEdits()" style="margin-top:12px;">💾 Save Changes</button>
            </div>
        </div>
        
        <div class="card" id="invoicePrint" style="background:white;color:#333;padding:0;overflow:hidden;">
            <!-- TOP BAR -->
            <div style="background:#1a1a2e;color:white;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <h1 style="margin:0;font-size:16px;font-weight:700;letter-spacing:0.5px;">{biz_name}</h1>
                    {f'<p style="margin:4px 0 0 0;font-size:10px;opacity:0.8;">{biz_address}</p>' if biz_address else ''}
                </div>
                <div style="text-align:right;">
                    <h2 style="margin:0;font-size:20px;font-weight:700;letter-spacing:2px;">TAX INVOICE</h2>
                    {status_badge}
                </div>
            </div>
            
            <!-- DETAILS GRID -->
            <div style="padding:10px 25px;display:grid;grid-template-columns:1fr 1fr;gap:0;border-bottom:1px solid #e5e7eb;">
                <!-- LEFT: Document details -->
                <div style="border-right:1px solid #e5e7eb;padding-right:25px;">
                    <table style="width:100%;font-size:11px;color:#333;">
                        <tr><td style="padding:4px 0;color:#888;width:120px;">Number:</td><td style="padding:4px 0;font-weight:600;">{invoice.get("invoice_number", "-")}</td></tr>
                        <tr><td style="padding:4px 0;color:#888;">Date:</td><td style="padding:4px 0;">{invoice.get("date", "-")}</td></tr>
                        <tr><td style="padding:4px 0;color:#888;">Due Date:</td><td style="padding:4px 0;">{invoice.get("due_date", "-")}</td></tr>
                        {sp_row}
                        {ref_row}
                        {dn_row}
                        {terms_row}
                        {f'<tr><td style="padding:4px 0;color:#888;">Our VAT No:</td><td style="padding:4px 0;">{biz_vat}</td></tr>' if biz_vat else ''}
                    </table>
                    {f'<div style="margin-top:8px;font-size:13px;color:#666;"><span>Tel: {biz_phone}</span></div>' if biz_phone else ''}
                    {f'<div style="font-size:13px;color:#666;">{biz_email}</div>' if biz_email else ''}
                </div>
                <!-- RIGHT: Customer details -->
                <div style="padding-left:25px;">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-weight:600;">Bill To</div>
                    <div style="font-size:13px;font-weight:700;color:#1a1a2e;margin-bottom:4px;">{cust_name}</div>
                    {f'<div style="font-size:10px;color:#555;margin-bottom:2px;">{cust_address}</div>' if cust_address else ''}
                    {f'<div style="font-size:10px;color:#555;">Tel: {cust_tel}</div>' if cust_tel else ''}
                    {f'<div style="font-size:10px;color:#555;">{cust_email}</div>' if cust_email else ''}
                    {f'<div style="font-size:10px;color:#555;margin-top:4px;">VAT No: {cust_vat}</div>' if cust_vat else ''}
                </div>
            </div>
            
            <!-- ITEMS TABLE -->
            <div style="padding:0 25px;">
                <table style="width:100%;border-collapse:collapse;font-size:14px;">
                    <thead>
                        <tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">
                            <th style="padding:5px 6px;text-align:left;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;">Description</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:50px;">Unit</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">Qty</th>
                            <th style="padding:5px 6px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Excl. Price</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">Disc %</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">VAT %</th>
                            <th style="padding:5px 6px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Excl. Total</th>
                            <th style="padding:5px 6px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Incl. Total</th>
                        </tr>
                    </thead>
                    <tbody style="color:#333;">
                        {items_html}
                    </tbody>
                </table>
            </div>
            
            <!-- TOTALS + BANKING -->
            <div style="padding:10px 25px 15px;display:flex;justify-content:space-between;align-items:flex-end;">
                <!-- Banking Details -->
                <div style="font-size:12px;color:#666;max-width:55%;">
                    {f"""<div style="border:1px solid #e5e7eb;border-radius:6px;padding:12px;background:#fafafa;">
                        <div style="font-weight:600;color:#333;margin-bottom:6px;font-size:13px;">Banking Details</div>
                        <div>Bank: {business.get("bank_name", "")}</div>
                        <div>Account: {business.get("bank_account", "")}</div>
                        <div>Branch: {business.get("bank_branch", "")}</div>
                    </div>""" if business and business.get("bank_account") else ''}
                    <div style="margin-top:12px;font-size:11px;color:#999;">
                        <p style="margin:2px 0;">Thank you for your business!</p>
                        <p style="margin:2px 0;">Generated by Click AI</p>
                    </div>
                </div>
                <!-- Totals -->
                <table style="width:220px;border-collapse:collapse;">
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:4px 8px;color:#666;font-size:11px;">Total Discount</td>
                        <td style="padding:4px 8px;text-align:right;color:#333;font-size:11px;">R0.00</td>
                    </tr>
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:4px 8px;color:#666;font-size:11px;">Total Exclusive</td>
                        <td style="padding:4px 8px;text-align:right;color:#333;font-size:11px;">{money(invoice.get("subtotal", 0))}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:4px 8px;color:#666;font-size:11px;">Total VAT</td>
                        <td style="padding:4px 8px;text-align:right;color:#333;font-size:11px;">{money(invoice.get("vat", 0))}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:4px 8px;color:#666;font-size:11px;">Sub Total</td>
                        <td style="padding:4px 8px;text-align:right;color:#333;font-size:11px;font-weight:600;">{money(invoice.get("total", 0))}</td>
                    </tr>
                    <tr style="background:#1a1a2e;">
                        <td style="padding:8px 8px;color:white;font-size:13px;font-weight:700;">BALANCE DUE</td>
                        <td style="padding:8px 8px;text-align:right;color:white;font-size:13px;font-weight:700;">{money(invoice.get("total", 0))}</td>
                    </tr>
                </table>
            </div>
        </div>
        
        <script>
        async function markPaid(method) {{
            if (!confirm(`Mark this invoice as paid via ${{method === 'cash' ? 'Cash' : 'Bank/EFT'}}?`)) return;
            
            try {{
                const response = await fetch('/api/invoice/{invoice_id}/pay', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{payment_method: method}})
                }});
                const result = await response.json();
                if (result.success) {{
                    location.reload();
                }} else {{
                    alert('Error: ' + (result.error || 'Failed to process payment'));
                }}
            }} catch (err) {{
                alert('Error: ' + err.message);
            }}
        }}
        
        // SAVE INVOICE EDITS (date, sales person, reference, delivery note)
        async function saveInvoiceEdits() {{
            const data = {{
                date: document.getElementById('editDate').value,
                due_date: document.getElementById('editDueDate').value,
                sales_person: document.getElementById('editSalesPerson').value.trim(),
                reference: document.getElementById('editReference').value.trim(),
                delivery_note: document.getElementById('editDeliveryNote').value.trim()
            }};
            
            try {{
                const response = await fetch('/api/invoice/{invoice_id}/edit', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});
                const result = await response.json();
                if (result.success) {{
                    location.reload();
                }} else {{
                    alert('Error: ' + (result.error || 'Failed to save'));
                }}
            }} catch (err) {{
                alert('Error: ' + err.message);
            }}
        }}
        
        // EMAIL FUNCTIONS
        function showEmailModal() {{
            document.getElementById('emailModal').style.display = 'flex';
            document.getElementById('emailTo').focus();
        }}
        
        function closeEmailModal() {{
            document.getElementById('emailModal').style.display = 'none';
        }}
        
        async function sendInvoiceEmail() {{
            const emailField = document.getElementById('emailTo').value.trim();
            // Support multiple comma-separated emails
            const emails = emailField.split(',').map(e => e.trim()).filter(e => e.includes('@'));
            if (emails.length === 0) {{
                alert('Please enter at least one valid email address');
                return;
            }}
            
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Sending...';
            
            try {{
                const response = await fetch('/api/invoice/{invoice_id}/email', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{to_email: emails.join(',')}})
                }});
                const result = await response.json();
                if (result.success) {{
                    alert('✅ Invoice emailed to ' + emails.join(', '));
                    closeEmailModal();
                }} else {{
                    alert('❌ ' + (result.error || 'Failed to send email'));
                }}
            }} catch (err) {{
                alert('❌ Error: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.textContent = 'Send Email';
            }}
        }}
        
        // Close modal on escape key + F-key interceptor for invoice page
        document.addEventListener('keydown', function(e) {{
            // Block browser defaults for F1-F11 (F1=Help opens Google-like page)
            if (['F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11'].includes(e.key)) {{
                e.preventDefault();
            }}
            if (e.key === 'Escape') closeEmailModal();
            // F1 = Cash payment (same as POS muscle memory)
            if (e.key === 'F1' && typeof markPaid === 'function') {{
                markPaid('cash');
                return;
            }}
            // F2 = Card payment
            if (e.key === 'F2' && typeof markPaid === 'function') {{
                markPaid('card');
                return;
            }}
            // F3 = EFT payment
            if (e.key === 'F3' && typeof markPaid === 'function') {{
                markPaid('eft');
                return;
            }}
        }});
        
        // PRINT FUNCTION - Opens new window for reliable multi-page printing
        function printDocument() {{
            const content = document.getElementById('invoicePrint').innerHTML;
            const printWindow = window.open('', '_blank', 'width=800,height=600');
            
            printWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Invoice</title>
                    <style>
                        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                        body {{ 
                            font-family: Arial, Helvetica, sans-serif; 
                            padding: 0;
                            color: #333;
                            background: white;
                            font-size: 11px;
                        }}
                        table {{ 
                            width: 100%; 
                            border-collapse: collapse; 
                            page-break-inside: auto;
                        }}
                        tr {{ page-break-inside: avoid; }}
                        thead {{ display: table-header-group; }}
                        @media print {{
                            body {{ padding: 0; }}
                            @page {{ size: A4; margin: 10mm 12mm; }}
                        }}
                    </style>
                </head>
                <body>${{content}}</body>
                </html>
            `);
            
            printWindow.document.close();
            printWindow.focus();
            
            // Wait for content to load then print
            setTimeout(function() {{
                printWindow.print();
                printWindow.close();
            }}, 250);
        }}
        </script>
        '''
        
        return render_page(f"Invoice {invoice.get('invoice_number', '')}", content, user, "invoices")
    
    
    @app.route("/api/invoice/<invoice_id>/pay", methods=["POST"])
    @login_required
    def api_invoice_pay(invoice_id):
        """
        Mark invoice as paid - creates full GL entries
        
        GL Flow for Customer Invoice Payment:
        - Debit: Bank (1000) or Cash (1010) - money coming in
        - Credit: Debtors (1200) - customer no longer owes us
        
        This completes the cycle started when invoice was created:
        Invoice Creation: DR Debtors (1200), CR Sales (4000) + VAT Output (2100)
        Invoice Payment:  DR Bank/Cash (1000/1010), CR Debtors (1200)
        """
        try:
            data = request.get_json()
            payment_method = data.get("payment_method", "cash")  # cash, card, eft, or account
            
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            
            invoice = db.get_one("invoices", invoice_id)
            if not invoice:
                return jsonify({"success": False, "error": "Invoice not found"})
            
            if invoice.get("status") == "paid":
                return jsonify({"success": False, "error": "Invoice already paid"})
            
            if invoice.get("status") == "credited":
                return jsonify({"success": False, "error": "Cannot pay credited invoice"})
            
            total = float(invoice.get("total", 0))
            inv_number = invoice.get("invoice_number", "")
            customer_name = invoice.get("customer_name", "")
            
            # ACCOUNT = Customer is on account (owes money, no payment yet)
            if payment_method == "account":
                # Just update status - NO journal entry, NO balance change
                db.update("invoices", invoice_id, {
                    "status": "account",
                    "payment_method": "account"
                })
                
                logger.info(f"[PAYMENT] Invoice {inv_number} marked as ON ACCOUNT - R{total:.2f}")
                
                return jsonify({
                    "success": True,
                    "message": f"Invoice marked as ON ACCOUNT",
                    "invoice_number": inv_number,
                    "amount": total
                })
            
            # CASH/CARD/EFT = Actual payment received
            # Determine which account to debit
            if payment_method == "cash":
                bank_account = "1050"  # Cash On Hand
                bank_name = "Cash"
            elif payment_method == "card":
                bank_account = "1000"  # Bank
                bank_name = "Card"
            else:  # eft
                bank_account = "1000"  # Bank
                bank_name = "EFT"
            
            # Create journal entries: DR Bank/Cash, CR Debtors
            create_journal_entry(
                biz_id,
                today(),
                f"Payment received - {inv_number} - {customer_name} ({bank_name})",
                f"PAY-{inv_number}",
                [
                    {"account_code": bank_account, "debit": total, "credit": 0},  # Bank/Cash increases
                    {"account_code": gl(biz_id, "debtors"), "debit": 0, "credit": total},        # Debtors decreases
                ]
            )
            
            # Update invoice status to paid
            db.update("invoices", invoice_id, {
                "status": "paid",
                "paid_date": today(),
                "payment_method": payment_method
            })
            
            # Update customer balance (reduce what they owe)
            customer_id = invoice.get("customer_id")
            if customer_id:
                customer = db.get_one("customers", customer_id)
                if customer:
                    new_balance = float(customer.get("balance", 0)) - total
                    db.update("customers", customer_id, {"balance": new_balance})
            
            # ═══════════════════════════════════════════════════════════════
            # SAVE TO PAYMENTS TABLE - This is the key for tracking!
            # ═══════════════════════════════════════════════════════════════
            user = Auth.get_current_user()
            payment = RecordFactory.payment(
                business_id=biz_id,
                customer_id=customer_id or "",
                invoice_id=invoice_id,
                amount=total,
                customer_name=customer_name,
                invoice_number=inv_number,
                date=today(),
                method=payment_method,
                reference=f"PAY-{inv_number}",
                created_by=user.get("id", "") if user else ""
            )
            db.save("payments", payment)
            
            logger.info(f"[PAYMENT] Invoice {inv_number} marked as PAID ({bank_name}) - R{total:.2f}")
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="payment", source_table="payments", source_id=payment.get("id", ""),
                        description=f"Payment received - {inv_number} - {customer_name} ({bank_name})",
                        amount=total,
                        gl_entries=[
                            {"account_code": bank_account, "debit": total, "credit": 0},
                            {"account_code": gl(biz_id, "debtors"), "debit": 0, "credit": total},
                        ],
                        customer_name=customer_name, payment_method=payment_method, reference=f"PAY-{inv_number}",
                        transaction_date=today(),
                        created_by=user.get("id") if user else "", created_by_name=user.get("name", "") if user else ""
                    )
            except Exception:
                pass
            
            return jsonify({
                "success": True,
                "message": f"Payment recorded via {bank_name}",
                "invoice_number": inv_number,
                "amount": total
            })
            
        except Exception as e:
            logger.error(f"[PAYMENT] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/invoice/<invoice_id>/edit", methods=["POST"])
    @login_required
    def api_invoice_edit(invoice_id):
        """Edit invoice details — date, sales person, reference, delivery note"""
        try:
            data = request.get_json()
            invoice = db.get_one("invoices", invoice_id)
            if not invoice:
                return jsonify({"success": False, "error": "Invoice not found"})
            
            updates = {}
            if data.get("date"):
                updates["date"] = data["date"]
            if data.get("due_date"):
                updates["due_date"] = data["due_date"]
            if "sales_person" in data:
                updates["salesman_name"] = data["sales_person"]
                updates["sales_rep"] = data["sales_person"]
            if "reference" in data:
                updates["reference"] = data["reference"]
            if "delivery_note" in data:
                updates["delivery_note"] = data["delivery_note"]
            
            if updates:
                db.update("invoices", invoice_id, updates)
                logger.info(f"[INVOICE EDIT] {invoice.get('invoice_number')}: {list(updates.keys())}")
            
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"[INVOICE EDIT] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/invoice/<invoice_id>/email", methods=["POST"])
    @login_required
    def api_invoice_email(invoice_id):
        """Send invoice via email — supports multiple comma-separated addresses"""
        try:
            data = request.get_json()
            to_email = data.get("to_email", "").strip()
            
            # Support multiple comma-separated emails
            if not to_email or "@" not in to_email:
                return jsonify({"success": False, "error": "Valid email address required"})
            
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            invoice = db.get_one("invoices", invoice_id)
            if not invoice:
                return jsonify({"success": False, "error": "Invoice not found"})
            
            # Build email content
            biz_name = business.get("name", "Business") if business else "Business"
            inv_no = invoice.get("invoice_number", "")
            total = float(invoice.get("total", 0))
            date = invoice.get("date", today())
            cust_name = invoice.get("customer_name", "Customer")
            status = invoice.get("status", "outstanding")
            
            # Parse items for email
            raw_items = invoice.get("items", [])
            if isinstance(raw_items, str):
                try:
                    items = json.loads(raw_items)
                except:
                    items = []
            else:
                items = raw_items if raw_items else []
            
            # Build items table
            items_html = ""
            for item in items:
                qty = item.get("qty") or item.get("quantity") or 1
                desc = item.get("description") or item.get("desc") or "-"
                price = float(item.get("price", 0))
                item_total = float(item.get("total", 0))
                items_html += f'<tr><td style="padding:8px;border-bottom:1px solid #eee;">{safe_string(desc)}</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{qty}</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">R{price:,.2f}</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">R{item_total:,.2f}</td></tr>'
            
            subtotal = float(invoice.get("subtotal", 0))
            vat = float(invoice.get("vat", 0))
            
            subject = f"Invoice {inv_no} from {biz_name}"
            
            biz_phone = business.get("phone", "") if business else ""
            biz_email_addr = business.get("email", "") if business else ""
            biz_address = safe_string(business.get("address", "")).replace("\n", "<br>") if business else ""
            biz_vat = business.get("vat_number", "") if business else ""
            biz_bank = business.get("bank_name", "") if business else ""
            biz_bank_acc = business.get("bank_account", "") if business else ""
            biz_bank_branch = business.get("bank_branch", "") if business else ""
            payment_method = invoice.get("payment_method", "account")
            method_label = {"cash": "Cash", "card": "Card", "eft": "EFT", "account": "Account"}.get(payment_method, payment_method)
            salesman = invoice.get("salesman_name", "") or invoice.get("sales_rep", "")
            cashier = invoice.get("created_by_name", "")
            
            # Short email body
            body_html = f'''<html><body style="font-family:Arial,sans-serif;font-size:13px;color:#333;">
            <p>Dear {cust_name},</p>
            <p>Please find attached Invoice <strong>{inv_no}</strong> for <strong>R{total:,.2f}</strong>.</p>
            {f'<p><strong>Banking Details:</strong> {biz_bank} | Acc: {biz_bank_acc} | Branch: {biz_bank_branch}</p>' if biz_bank_acc else ''}
            <p>Thank you for your business!</p>
            <hr style="border:none;border-top:1px solid #ddd;margin:15px 0 8px;">
            <p style="color:#999;font-size:10px;">{biz_name} | {biz_phone} | {biz_email_addr}<br>Sent via Click AI</p>
            </body></html>'''
            
            body_text = f"Invoice {inv_no} from {biz_name}\n\nDear {cust_name},\n\nPlease find attached Invoice {inv_no} for R{total:,.2f}.\n\nThank you for your business!\n\n{biz_name}"
            
            # Build attachment items
            att_items = ""
            for item in items:
                qty = item.get("qty") or item.get("quantity") or 1
                desc = safe_string(item.get("description") or item.get("desc") or "-")
                unit = safe_string(item.get("unit") or "")
                price = float(item.get("price", 0))
                total_excl = float(item.get("total", 0)) or round(float(qty) * price, 2)
                vat_amt = round(total_excl * 0.15, 2)
                total_incl = round(total_excl + vat_amt, 2)
                att_items += f'<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:5px 8px;font-size:11px;">{desc}</td><td style="text-align:center;padding:5px 8px;font-size:11px;">{unit}</td><td style="text-align:center;padding:5px 8px;font-size:11px;">{qty}</td><td style="text-align:right;padding:5px 8px;font-size:11px;">R{price:,.2f}</td><td style="text-align:center;padding:5px 8px;font-size:11px;">15%</td><td style="text-align:right;padding:5px 8px;font-size:11px;">R{total_excl:,.2f}</td><td style="text-align:right;padding:5px 8px;font-size:11px;font-weight:600;">R{total_incl:,.2f}</td></tr>'
            
            attachment_html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Invoice {inv_no}</title>
            <style>body{{font-family:Arial,sans-serif;margin:0;padding:0;color:#333;font-size:12px;}}table{{width:100%;border-collapse:collapse;}}@media print{{@page{{margin:10mm 12mm;}}body{{padding:0;}}}}</style>
            </head><body>
            <div style="background:#1a1a2e;color:white;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;">
                <div><div style="font-size:16px;font-weight:700;">{biz_name}</div>{f'<div style="font-size:10px;opacity:0.8;">{biz_address}</div>' if biz_address else ''}</div>
                <div style="text-align:right;"><div style="font-size:20px;font-weight:700;letter-spacing:2px;">TAX INVOICE</div><span style="background:#10b981;color:white;padding:4px 12px;border-radius:20px;font-size:11px;">{method_label.upper()}</span></div>
            </div>
            <div style="padding:10px 25px;display:flex;gap:40px;border-bottom:1px solid #e5e7eb;">
                <div style="flex:1;border-right:1px solid #e5e7eb;padding-right:25px;">
                    <table style="font-size:11px;width:auto;"><tr><td style="padding:3px 0;color:#888;width:100px;">Number:</td><td style="font-weight:600;">{inv_no}</td></tr><tr><td style="padding:3px 0;color:#888;">Date:</td><td>{date}</td></tr>{f'<tr><td style="padding:3px 0;color:#888;">Our VAT:</td><td>{biz_vat}</td></tr>' if biz_vat else ''}{f'<tr><td style="padding:3px 0;color:#888;">Salesman:</td><td>{salesman}</td></tr>' if salesman else ''}{f'<tr><td style="padding:3px 0;color:#888;">Prepared By:</td><td>{cashier}</td></tr>' if cashier else ''}</table>
                    {f'<div style="margin-top:6px;font-size:10px;color:#666;">Tel: {biz_phone}</div>' if biz_phone else ''}
                </div>
                <div style="flex:1;padding-left:25px;">
                    <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-weight:600;">Bill To</div>
                    <div style="font-size:13px;font-weight:700;">{safe_string(cust_name)}</div>
                </div>
            </div>
            <div style="padding:0 25px;"><table>
                <thead><tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">
                    <th style="padding:5px 8px;text-align:left;color:#475569;font-size:10px;text-transform:uppercase;">Description</th>
                    <th style="padding:5px 8px;text-align:center;color:#475569;font-size:10px;text-transform:uppercase;">Unit</th>
                    <th style="padding:5px 8px;text-align:center;color:#475569;font-size:10px;text-transform:uppercase;width:50px;">Qty</th>
                    <th style="padding:5px 8px;text-align:right;color:#475569;font-size:10px;text-transform:uppercase;">Price</th>
                    <th style="padding:5px 8px;text-align:center;color:#475569;font-size:10px;text-transform:uppercase;">VAT</th>
                    <th style="padding:5px 8px;text-align:right;color:#475569;font-size:10px;text-transform:uppercase;">Excl</th>
                    <th style="padding:5px 8px;text-align:right;color:#475569;font-size:10px;text-transform:uppercase;">Incl</th>
                </tr></thead><tbody>{att_items}</tbody>
            </table></div>
            <div style="padding:15px 25px;display:flex;justify-content:space-between;align-items:flex-end;">
                <div style="font-size:11px;color:#666;max-width:55%;">
                    {f'<div style="border:1px solid #e5e7eb;border-radius:6px;padding:10px;background:#fafafa;margin-bottom:8px;font-size:11px;"><strong>Banking Details</strong><br>{biz_bank} | Acc: {biz_bank_acc} | Branch: {biz_bank_branch}</div>' if biz_bank_acc else ''}
                    <p style="margin:4px 0;font-size:10px;color:#999;">Thank you for your business!</p>
                </div>
                <table style="width:200px;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:4px 8px;color:#666;font-size:11px;">Subtotal</td><td style="padding:4px 8px;text-align:right;font-size:11px;">R{subtotal:,.2f}</td></tr><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:4px 8px;color:#666;font-size:11px;">VAT (15%)</td><td style="padding:4px 8px;text-align:right;font-size:11px;">R{vat:,.2f}</td></tr><tr style="background:#1a1a2e;"><td style="padding:8px;color:white;font-size:13px;font-weight:700;">TOTAL</td><td style="padding:8px;text-align:right;color:white;font-size:13px;font-weight:700;">R{total:,.2f}</td></tr></table>
            </div>
            </body></html>'''
            
            inv_attachment = {
                'filename': f'{inv_no}.html',
                'content': attachment_html,
                'content_type': 'text/html'
            }
            
            # Send email
            success = Email.send(to_email, subject, body_html, body_text, business=business, attachments=[inv_attachment])
            
            if success:
                logger.info(f"[EMAIL] Invoice {inv_no} sent to {to_email}")
                return jsonify({"success": True, "message": f"Invoice sent to {to_email}"})
            else:
                return jsonify({"success": False, "error": "Failed to send email. Check SMTP settings in Settings page."})
            
        except Exception as e:
            logger.error(f"[EMAIL] Error sending invoice: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # RECURRING INVOICES - Auto-billing for retainers, subscriptions, rent
    # ═══════════════════════════════════════════════════════════════════════════════
    
    @app.route("/recurring-invoices")
    @login_required
    def recurring_invoices_page():
        """List all recurring invoices"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        recurring = db.get("recurring_invoices", {"business_id": biz_id}) if biz_id else []
        recurring = sorted(recurring, key=lambda x: x.get("next_date", ""), reverse=False)
        
        # Stats
        active = [r for r in recurring if r.get("status") == "active"]
        paused = [r for r in recurring if r.get("status") == "paused"]
        total_monthly = sum(float(r.get("total", 0)) for r in active if r.get("frequency") == "monthly")
        
        rows = ""
        for r in recurring:
            status = r.get("status", "active")
            status_colors = {"active": "var(--green)", "paused": "var(--orange)", "completed": "var(--text-muted)"}
            status_color = status_colors.get(status, "var(--text-muted)")
            
            frequency = r.get("frequency", "monthly")
            freq_label = RecurringInvoices.FREQUENCIES.get(frequency, {}).get("label", frequency)
            
            next_date = r.get("next_date", "-")
            is_overdue = next_date and next_date < today() and status == "active"
            
            rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='/recurring-invoice/{r.get("id")}'">
                <td><strong>{safe_string(r.get("customer_name", "-"))}</strong></td>
                <td>{freq_label}</td>
                <td>{money(r.get("total", 0))}</td>
                <td style="color:{"var(--red)" if is_overdue else "var(--text)"};">
                    {next_date} {"(OVERDUE)" if is_overdue else ""}
                </td>
                <td>{r.get("invoices_generated", 0)}</td>
                <td style="color:{status_color};">{status.title()}</td>
                <td>
                    {"✉️" if r.get("auto_send") else ""}
                    {"<span style='color:var(--orange);' title='Annual increase pending'>📈</span>" if r.get("escalation_pending") else ""}
                </td>
            </tr>
            '''
        
        content = f'''
        <div class="card" style="margin-bottom: 20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <div>
                    <h2 style="margin:0;">🔄 Recurring Invoices</h2>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;">Auto-generate invoices on a schedule</p>
                </div>
                <a href="/recurring-invoice/new" class="btn btn-primary">+ New Recurring Invoice</a>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 20px;">
                <div style="background: var(--bg); padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: var(--green);">{len(active)}</div>
                    <div style="color: var(--text-muted); font-size: 13px;">Active</div>
                </div>
                <div style="background: var(--bg); padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: var(--orange);">{len(paused)}</div>
                    <div style="color: var(--text-muted); font-size: 13px;">Paused</div>
                </div>
                <div style="background: var(--bg); padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 24px; font-weight: bold;">{money(total_monthly)}</div>
                    <div style="color: var(--text-muted); font-size: 13px;">Monthly Revenue</div>
                </div>
            </div>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Customer</th>
                        <th>Frequency</th>
                        <th>Amount</th>
                        <th>Next Invoice</th>
                        <th>Generated</th>
                        <th>Status</th>
                        <th>Auto-send</th>
                    </tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='7' style='text-align:center;color:var(--text-muted);padding:40px;'>No recurring invoices set up yet.<br><br><a href='/recurring-invoice/new' class='btn btn-primary'>Create your first recurring invoice</a></td></tr>"}
                </tbody>
            </table>
        </div>
        
        <div class="card" style="background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.05));">
            <h3 style="margin: 0 0 10px 0;">How Recurring Invoices Work</h3>
            <ul style="color: var(--text-muted); margin: 0; padding-left: 20px; line-height: 1.8;">
                <li><strong>Set it and forget it</strong> - System automatically creates invoices on schedule</li>
                <li><strong>Auto-email</strong> - Optionally send invoice to customer automatically</li>
                <li><strong>Runs at 2am daily</strong> - Invoices generated overnight, ready for your customers</li>
                <li><strong>Full GL integration</strong> - Each invoice creates proper accounting entries</li>
                <li><strong>Pause anytime</strong> - Put a recurring invoice on hold without deleting</li>
            </ul>
        </div>
        '''
        
        return render_page("Recurring Invoices", content, user, "invoices")
    
    
    @app.route("/recurring-invoice/new", methods=["GET", "POST"])
    @login_required
    def recurring_invoice_new():
        """Create new recurring invoice"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            customer_id = request.form.get("customer_id", "")
            
            # Get customer details
            customer = db.get_one("customers", customer_id) if customer_id else None
            customer_name = customer.get("name", "") if customer else request.form.get("customer_name", "")
            customer_email = customer.get("email", "") if customer else request.form.get("customer_email", "")
            
            # Get line items
            items = []
            descriptions = request.form.getlist("item_desc[]")
            quantities = request.form.getlist("item_qty[]")
            prices = request.form.getlist("item_price[]")
            
            for i, desc in enumerate(descriptions):
                if desc.strip():
                    items.append({
                        "description": desc.strip(),
                        "quantity": float(quantities[i] or 1),
                        "price": float(prices[i] or 0)
                    })
            
            if not items:
                flash("Please add at least one line item", "error")
                return redirect("/recurring-invoice/new")
            
            result = RecurringInvoices.create(biz_id, {
                "customer_id": customer_id,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "items": items,
                "frequency": request.form.get("frequency", "monthly"),
                "start_date": request.form.get("start_date", today()),
                "end_date": request.form.get("end_date") or None,
                "auto_send": request.form.get("auto_send") == "on",
                "notes": request.form.get("notes", ""),
                "escalation_percent": float(request.form.get("escalation_percent") or 0),
                "escalation_month": int(request.form.get("escalation_month") or 0),
                "escalation_auto": request.form.get("escalation_auto", "remind")
            })
            
            if result.get("success"):
                flash(result.get("message"), "success")
                return redirect("/recurring-invoices")
            else:
                flash(result.get("error"), "error")
                return redirect("/recurring-invoice/new")
        
        # GET - show form
        customers = db.get("customers", {"business_id": biz_id}) if biz_id else []
        customers = sorted(customers, key=lambda x: x.get("name", "").lower())
        
        # Pre-fill if customer_id in query string
        prefill_customer = request.args.get("customer_id", "")
        prefill_customer_obj = db.get_one("customers", prefill_customer) if prefill_customer else None
        
        customer_options = '<option value="">-- Select Customer --</option>'
        for c in customers:
            selected = "selected" if c.get("id") == prefill_customer else ""
            customer_options += f'<option value="{c.get("id")}" data-email="{safe_string(c.get("email", ""))}" {selected}>{safe_string(c.get("name", ""))}</option>'
        
        frequency_options = ""
        for key, val in RecurringInvoices.FREQUENCIES.items():
            frequency_options += f'<option value="{key}">{val["label"]}</option>'
        
        content = f'''
        <div style="margin-bottom: 20px;">
            <a href="/recurring-invoices" style="color:var(--text-muted);">← Back to Recurring Invoices</a>
        </div>
        
        <div class="card" style="max-width: 800px;">
            <h2 style="margin: 0 0 20px 0;">🔄 New Recurring Invoice</h2>
            
            <form method="POST" id="recurringForm">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">Customer *</label>
                        <select name="customer_id" id="customerSelect" class="form-input" required onchange="updateCustomerEmail()">
                            {customer_options}
                        </select>
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">Customer Email</label>
                        <input type="email" name="customer_email" id="customerEmail" class="form-input" 
                               value="{safe_string(prefill_customer_obj.get('email', '') if prefill_customer_obj else '')}"
                               placeholder="For auto-sending invoices">
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">Frequency *</label>
                        <select name="frequency" class="form-input" required>
                            {frequency_options}
                        </select>
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">Start Date *</label>
                        <input type="date" name="start_date" class="form-input" value="{today()}" required>
                        <small style="color: var(--text-muted);">First invoice will be generated on this date</small>
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">End Date (Optional)</label>
                        <input type="date" name="end_date" class="form-input">
                        <small style="color: var(--text-muted);">Leave blank for indefinite</small>
                    </div>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                        <input type="checkbox" name="auto_send" checked style="width: 18px; height: 18px;">
                        <span><strong>Auto-send invoice to customer via email</strong></span>
                    </label>
                    <small style="color: var(--text-muted); margin-left: 28px;">Invoice will be emailed automatically when generated</small>
                </div>
                
                <div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.2);border-radius:8px;padding:15px;margin-bottom:20px;">
                    <h4 style="margin:0 0 10px 0;">📈 Annual Price Increase (Optional)</h4>
                    <p style="color:var(--text-muted);font-size:13px;margin:0 0 12px 0;">Set a yearly escalation — system will remind you and can auto-apply the increase</p>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;">Increase %</label>
                            <input type="number" name="escalation_percent" class="form-input" placeholder="e.g. 8" step="0.5" min="0" max="50">
                            <small style="color:var(--text-muted);">0 = no increase</small>
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;">Increase Month</label>
                            <select name="escalation_month" class="form-input">
                                <option value="">-- Select --</option>
                                <option value="1">January</option>
                                <option value="2">February</option>
                                <option value="3">March</option>
                                <option value="4">April</option>
                                <option value="5">May</option>
                                <option value="6">June</option>
                                <option value="7">July</option>
                                <option value="8">August</option>
                                <option value="9">September</option>
                                <option value="10">October</option>
                                <option value="11">November</option>
                                <option value="12">December</option>
                            </select>
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;">Auto-apply?</label>
                            <select name="escalation_auto" class="form-input">
                                <option value="remind">Remind me first</option>
                                <option value="auto">Auto-apply increase</option>
                            </select>
                            <small style="color:var(--text-muted);">Remind = notification before applying</small>
                        </div>
                    </div>
                </div>
                
                <hr style="border: none; border-top: 1px solid var(--border); margin: 25px 0;">
                
                <h3 style="margin: 0 0 15px 0;">Line Items</h3>
                
                <table class="table" id="itemsTable">
                    <thead>
                        <tr>
                            <th style="width: 50%;">Description *</th>
                            <th style="width: 15%;">Qty</th>
                            <th style="width: 20%;">Price (excl VAT)</th>
                            <th style="width: 15%;">Total</th>
                        </tr>
                    </thead>
                    <tbody id="itemsBody">
                        <tr>
                            <td><input type="text" name="item_desc[]" class="form-input" placeholder="e.g., Monthly Retainer" required></td>
                            <td><input type="number" name="item_qty[]" class="form-input" value="1" min="0.01" step="any" onchange="calculateTotals()"></td>
                            <td><input type="number" name="item_price[]" class="form-input" placeholder="0.00" step="0.01" onchange="calculateTotals()"></td>
                            <td style="text-align: right; padding-top: 12px;"><span class="line-total">R0.00</span></td>
                        </tr>
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colspan="4">
                                <button type="button" class="btn btn-secondary" onclick="addRow()" style="font-size: 13px;">+ Add Line</button>
                            </td>
                        </tr>
                        <tr style="background: var(--bg);">
                            <td colspan="2"></td>
                            <td style="text-align: right; font-weight: 500;">Subtotal:</td>
                            <td style="text-align: right;"><span id="subtotal">R0.00</span></td>
                        </tr>
                        <tr style="background: var(--bg);">
                            <td colspan="2"></td>
                            <td style="text-align: right; font-weight: 500;">VAT (15%):</td>
                            <td style="text-align: right;"><span id="vat">R0.00</span></td>
                        </tr>
                        <tr style="background: var(--bg);">
                            <td colspan="2"></td>
                            <td style="text-align: right; font-weight: bold; font-size: 16px;">Total:</td>
                            <td style="text-align: right; font-weight: bold; font-size: 16px;"><span id="total">R0.00</span></td>
                        </tr>
                    </tfoot>
                </table>
                
                <div style="margin-top: 20px;">
                    <label style="display: block; margin-bottom: 5px; font-weight: 500;">Notes (Optional)</label>
                    <textarea name="notes" class="form-input" rows="2" placeholder="Notes to include on each invoice"></textarea>
                </div>
                
                <div style="display: flex; gap: 10px; margin-top: 25px;">
                    <button type="submit" class="btn btn-primary" style="padding: 12px 30px;">GOOD: Create Recurring Invoice</button>
                    <a href="/recurring-invoices" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <script>
        function updateCustomerEmail() {{
            const select = document.getElementById('customerSelect');
            const option = select.options[select.selectedIndex];
            const email = option.dataset.email || '';
            document.getElementById('customerEmail').value = email;
        }}
        
        function addRow() {{
            const tbody = document.getElementById('itemsBody');
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><input type="text" name="item_desc[]" class="form-input" placeholder="Description"></td>
                <td><input type="number" name="item_qty[]" class="form-input" value="1" min="0.01" step="any" onchange="calculateTotals()"></td>
                <td><input type="number" name="item_price[]" class="form-input" placeholder="0.00" step="0.01" onchange="calculateTotals()"></td>
                <td style="text-align: right; padding-top: 12px;">
                    <span class="line-total">R0.00</span>
                    <button type="button" onclick="this.closest('tr').remove(); calculateTotals();" style="margin-left: 10px; background: none; border: none; color: var(--red); cursor: pointer;">✕</button>
                </td>
            `;
            tbody.appendChild(row);
        }}
        
        function calculateTotals() {{
            let subtotal = 0;
            const rows = document.querySelectorAll('#itemsBody tr');
            
            rows.forEach(row => {{
                const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
                const price = parseFloat(row.querySelector('input[name="item_price[]"]').value) || 0;
                const lineTotal = qty * price;
                subtotal += lineTotal;
                row.querySelector('.line-total').textContent = 'R' + lineTotal.toFixed(2);
            }});
            
            const vat = subtotal * 0.15;
            const total = subtotal + vat;
            
            document.getElementById('subtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('vat').textContent = 'R' + vat.toFixed(2);
            document.getElementById('total').textContent = 'R' + total.toFixed(2);
        }}
        
        // Initial calculation
        calculateTotals();
        </script>
        '''
        
        return render_page("New Recurring Invoice", content, user, "invoices")
    
    
    @app.route("/recurring-invoice/<recurring_id>")
    @login_required
    def recurring_invoice_view(recurring_id):
        """View/edit recurring invoice"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        recurring = db.get_one("recurring_invoices", recurring_id)
        if not recurring:
            flash("Recurring invoice not found", "error")
            return redirect("/recurring-invoices")
        
        # Get items
        try:
            items = json.loads(recurring.get("items", "[]"))
        except:
            items = []
        
        # Get generated invoices (check recurring_id field OR notes containing the ID)
        all_invoices = db.get("invoices", {"business_id": biz_id}) or []
        rec_id_short = recurring_id[:8] if recurring_id else ""
        generated_invoices = [inv for inv in all_invoices if inv.get("recurring_id") == recurring_id or f"[Recurring: {rec_id_short}]" in (inv.get("notes") or "")]
        generated_invoices = sorted(generated_invoices, key=lambda x: x.get("date", ""), reverse=True)
        
        status = recurring.get("status", "active")
        frequency = recurring.get("frequency", "monthly")
        freq_label = RecurringInvoices.FREQUENCIES.get(frequency, {}).get("label", frequency)
        
        items_html = ""
        for item in items:
            qty = item.get("quantity", 1)
            price = item.get("price", 0)
            items_html += f'''
            <tr>
                <td>{safe_string(item.get("description", "-"))}</td>
                <td style="text-align: right;">{qty}</td>
                <td style="text-align: right;">{money(price)}</td>
                <td style="text-align: right;">{money(qty * price)}</td>
            </tr>
            '''
        
        history_html = ""
        for inv in generated_invoices[:20]:
            inv_status = inv.get("status", "outstanding")
            status_color = "var(--green)" if inv_status == "paid" else "var(--orange)"
            history_html += f'''
            <tr style="cursor: pointer;" onclick="window.location='/invoice/{inv.get("id")}'">
                <td>{inv.get("invoice_number", "-")}</td>
                <td>{inv.get("date", "-")}</td>
                <td>{money(inv.get("total", 0))}</td>
                <td style="color: {status_color};">{inv_status}</td>
            </tr>
            '''
        
        # Escalation pending banner
        esc_banner = ""
        if recurring.get("escalation_pending") and float(recurring.get("escalation_percent", 0) or 0) > 0:
            esc_pct = recurring.get("escalation_percent", 0)
            new_total = round(float(recurring.get("total", 0)) * (1 + float(esc_pct) / 100), 2)
            esc_banner = f'''
            <div style="background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.4);border-radius:8px;padding:15px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <strong style="color:var(--orange);">📈 Annual Price Increase Due!</strong><br>
                    <span style="color:var(--text-muted);">{esc_pct}% increase pending — current {money(recurring.get("total", 0))} → new {money(new_total)} per invoice</span>
                </div>
                <div style="display:flex;gap:10px;">
                    <button class="btn btn-primary" style="background:var(--green);" onclick="applyEscalation()">✓ Apply {esc_pct}% Increase</button>
                    <button class="btn btn-secondary" onclick="dismissEscalation()">Skip This Year</button>
                </div>
            </div>'''
        
        content = f'''
        {esc_banner}
        <div style="margin-bottom: 20px;">
            <a href="/recurring-invoices" style="color:var(--text-muted);">← Back to Recurring Invoices</a>
        </div>
        
        <div class="card" style="margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <h2 style="margin: 0 0 5px 0;">🔄 {safe_string(recurring.get("customer_name", "Recurring Invoice"))}</h2>
                    <p style="color: var(--text-muted); margin: 0;">
                        {freq_label} • {money(recurring.get("total", 0))} per invoice
                    </p>
                </div>
                <div style="display: flex; gap: 10px;">
                    {"<button class='btn btn-secondary' onclick='pauseRecurring()'>Pause</button>" if status == "active" else ""}
                    {"<button class='btn btn-primary' onclick='resumeRecurring()'>▶️ Resume</button>" if status == "paused" else ""}
                    <button class="btn btn-secondary" onclick="generateNow()">⚡ Generate Now</button>
                    <button class="btn btn-secondary" style="color: var(--red);" onclick="deleteRecurring()">🗑️ Delete</button>
                </div>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
            <div class="card">
                <h3 style="margin: 0 0 15px 0;">Schedule</h3>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-muted);">Status</td>
                        <td style="padding: 8px 0; text-align: right;">
                            <span style="background: {"var(--green)" if status == "active" else "var(--orange)" if status == "paused" else "var(--text-muted)"}; 
                                         color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px;">
                                {status.title()}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-muted);">Frequency</td>
                        <td style="padding: 8px 0; text-align: right;">{freq_label}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-muted);">Next Invoice</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold;">{recurring.get("next_date", "-")}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-muted);">Start Date</td>
                        <td style="padding: 8px 0; text-align: right;">{recurring.get("start_date", "-")}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-muted);">End Date</td>
                        <td style="padding: 8px 0; text-align: right;">{recurring.get("end_date") or "Indefinite"}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-muted);">Auto-send Email</td>
                        <td style="padding: 8px 0; text-align: right;">{"Yes" if recurring.get("auto_send") else "No"}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: var(--text-muted);">Invoices Generated</td>
                        <td style="padding: 8px 0; text-align: right;">{recurring.get("invoices_generated", 0)}</td>
                    </tr>
                    {"<tr><td style='padding:8px 0;color:var(--text-muted);'>Annual Increase</td><td style='padding:8px 0;text-align:right;'>" + str(recurring.get('escalation_percent', 0)) + "% in " + ['', 'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(recurring.get('escalation_month', 0) or 0)] + " (" + recurring.get('escalation_auto', 'remind').title() + ")</td></tr>" if float(recurring.get("escalation_percent", 0) or 0) > 0 else ""}
                </table>
            </div>
            
            <div class="card">
                <h3 style="margin: 0 0 15px 0;">Invoice Template</h3>
                <table class="table" style="font-size: 13px;">
                    <thead>
                        <tr><th>Description</th><th style="text-align: right;">Qty</th><th style="text-align: right;">Price</th><th style="text-align: right;">Total</th></tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                    <tfoot style="background: var(--bg);">
                        <tr>
                            <td colspan="3" style="text-align: right;">Subtotal:</td>
                            <td style="text-align: right;">{money(recurring.get("subtotal", 0))}</td>
                        </tr>
                        <tr>
                            <td colspan="3" style="text-align: right;">VAT (15%):</td>
                            <td style="text-align: right;">{money(recurring.get("vat", 0))}</td>
                        </tr>
                        <tr>
                            <td colspan="3" style="text-align: right; font-weight: bold;">Total:</td>
                            <td style="text-align: right; font-weight: bold;">{money(recurring.get("total", 0))}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
        
        <div class="card">
            <h3 style="margin: 0 0 15px 0;">Generated Invoices ({len(generated_invoices)})</h3>
            <table class="table">
                <thead>
                    <tr><th>Invoice #</th><th>Date</th><th>Amount</th><th>Status</th></tr>
                </thead>
                <tbody>
                    {history_html or "<tr><td colspan='4' style='text-align:center;color:var(--text-muted);'>No invoices generated yet</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <script>
        async function pauseRecurring() {{
            if (!confirm('Pause this recurring invoice? No invoices will be generated until you resume.')) return;
            
            const response = await fetch('/api/recurring-invoice/{recurring_id}/pause', {{method: 'POST'}});
            const result = await response.json();
            
            if (result.success) {{
                location.reload();
            }} else {{
                alert('Error: ' + result.error);
            }}
        }}
        
        async function resumeRecurring() {{
            const response = await fetch('/api/recurring-invoice/{recurring_id}/resume', {{method: 'POST'}});
            const result = await response.json();
            
            if (result.success) {{
                location.reload();
            }} else {{
                alert('Error: ' + result.error);
            }}
        }}
        
        async function generateNow() {{
            if (!confirm('Generate an invoice now? This will also update the next invoice date.')) return;
            
            const response = await fetch('/api/recurring-invoice/{recurring_id}/generate', {{method: 'POST'}});
            const result = await response.json();
            
            if (result.success) {{
                alert('GOOD: Invoice ' + result.invoice_number + ' generated!');
                location.reload();
            }} else {{
                alert('Error: ' + result.error);
            }}
        }}
        
        async function deleteRecurring() {{
            if (!confirm('Delete this recurring invoice? This cannot be undone. Previously generated invoices will not be affected.')) return;
            
            const response = await fetch('/api/recurring-invoice/{recurring_id}/delete', {{method: 'POST'}});
            const result = await response.json();
            
            if (result.success) {{
                window.location = '/recurring-invoices';
            }} else {{
                alert('Error: ' + result.error);
            }}
        }}
        
        async function applyEscalation() {{
            if (!confirm('Apply the annual price increase? All future invoices will use the new prices.')) return;
            const response = await fetch('/api/recurring-invoice/{recurring_id}/escalate', {{method: 'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{action: 'apply'}})}});
            const result = await response.json();
            if (result.success) {{
                alert('✅ ' + result.message);
                location.reload();
            }} else {{
                alert('Error: ' + result.error);
            }}
        }}
        
        async function dismissEscalation() {{
            if (!confirm('Skip the price increase for this year?')) return;
            const response = await fetch('/api/recurring-invoice/{recurring_id}/escalate', {{method: 'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{action: 'dismiss'}})}});
            const result = await response.json();
            if (result.success) {{ location.reload(); }} else {{ alert('Error: ' + result.error); }}
        }}
        </script>
        '''
        
        return render_page("Recurring Invoice", content, user, "invoices")
    
    
    @app.route("/api/recurring-invoice/<recurring_id>/pause", methods=["POST"])
    @login_required
    def api_recurring_pause(recurring_id):
        """Pause a recurring invoice"""
        try:
            result = RecurringInvoices.pause(recurring_id)
            return jsonify(result)
        except Exception as e:
            logger.error(f"[RECURRING] Pause error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/recurring-invoice/<recurring_id>/resume", methods=["POST"])
    @login_required
    def api_recurring_resume(recurring_id):
        """Resume a recurring invoice"""
        try:
            result = RecurringInvoices.resume(recurring_id)
            return jsonify(result)
        except Exception as e:
            logger.error(f"[RECURRING] Resume error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/recurring-invoice/<recurring_id>/generate", methods=["POST"])
    @login_required
    def api_recurring_generate(recurring_id):
        """Manually generate an invoice from recurring template"""
        
        try:
            recurring = db.get_one("recurring_invoices", recurring_id)
            if not recurring:
                return jsonify({"success": False, "error": "Recurring invoice not found"})
            
            invoice = RecurringInvoices.generate_invoice(recurring)
            
            if invoice:
                return jsonify({
                    "success": True,
                    "invoice_number": invoice.get("invoice_number"),
                    "invoice_id": invoice.get("id")
                })
            
            return jsonify({"success": False, "error": "Failed to generate invoice"})
        except Exception as e:
            logger.error(f"[RECURRING] Generate error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/recurring-invoice/<recurring_id>/delete", methods=["POST"])
    @login_required
    def api_recurring_delete(recurring_id):
        """Delete a recurring invoice"""
        try:
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            result = RecurringInvoices.delete(recurring_id, biz_id)
            return jsonify(result)
        except Exception as e:
            logger.error(f"[RECURRING] Delete error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/recurring-invoice/<recurring_id>/escalate", methods=["POST"])
    @login_required
    def api_recurring_escalate(recurring_id):
        """Apply or dismiss annual price escalation"""
        try:
            recurring = db.get_one("recurring_invoices", recurring_id)
            if not recurring:
                return jsonify({"success": False, "error": "Not found"})
            
            data = request.get_json() or {}
            action = data.get("action", "apply")
            
            esc_percent = float(recurring.get("escalation_percent") or 0)
            current_year = str(datetime.now().year)
            
            if action == "apply" and esc_percent > 0:
                # Apply the increase to all items
                try:
                    items = json.loads(recurring.get("items", "[]"))
                except:
                    items = []
                
                multiplier = 1 + (esc_percent / 100)
                old_total = float(recurring.get("total", 0))
                
                for item in items:
                    item["price"] = round(float(item.get("price", 0)) * multiplier, 2)
                
                subtotal = sum(float(item.get("quantity", 1)) * float(item.get("price", 0)) for item in items)
                recurring["items"] = json.dumps(items)
                recurring["subtotal"] = round(subtotal, 2)
                recurring["vat"] = round(subtotal * 0.15, 2)
                recurring["total"] = round(subtotal * 1.15, 2)
                recurring["last_escalation_year"] = current_year
                recurring["escalation_pending"] = False
                
                db.save("recurring_invoices", recurring)
                
                new_total = recurring["total"]
                return jsonify({"success": True, "message": f"Price increased by {esc_percent}%! {money(old_total)} → {money(new_total)} per invoice"})
            
            elif action == "dismiss":
                recurring["escalation_pending"] = False
                recurring["last_escalation_year"] = current_year
                db.save("recurring_invoices", recurring)
                return jsonify({"success": True, "message": "Escalation skipped for this year"})
            
            return jsonify({"success": False, "error": "Invalid action"})
        except Exception as e:
            logger.error(f"[RECURRING] Escalation error: {e}")
            return jsonify({"success": False, "error": str(e)})
    

    # === QUOTES + DELIVERY NOTES ===

    @app.route("/quotes")
    @login_required  
    def quotes_page():
        """Quotes list - FAST direct query"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # FAST: Direct query with order and limit
        try:
            quotes = db.get("quotes", {"business_id": biz_id}, limit=200)
            # Sort by date descending
            quotes = sorted(quotes, key=lambda x: x.get("date", ""), reverse=True)
        except Exception as e:
            logger.error(f"[QUOTES] Error loading: {e}")
            quotes = []
        
        rows = ""
        for q in quotes:
            status = q.get("status", "pending")
            # Auto-expire: check if quote is older than 7 days and still pending/draft
            if status in ("pending", "draft"):
                try:
                    import datetime
                    _qd = q.get("date", "")
                    if _qd:
                        _qdate = datetime.datetime.strptime(_qd[:10], "%Y-%m-%d").date()
                        if (datetime.date.today() - _qdate).days > 30:
                            status = "expired"
                            try:
                                db.update("quotes", q.get("id"), {"status": "expired"})
                            except:
                                pass
                except:
                    pass
            status_color = "var(--green)" if status == "accepted" else "var(--red)" if status in ("declined", "expired") else "#3b82f6" if status in ("converted", "invoiced") else "var(--orange)"
            status_label = "Invoiced" if status in ("converted", "invoiced") else status.title()
            rows += f'''
            <tr style="cursor:pointer;" data-status="{status}">
                <td onclick="window.location='/quote/{q.get("id")}'" ><strong>{q.get("quote_number", "-")}</strong></td>
                <td onclick="window.location='/quote/{q.get("id")}'">{q.get("date", "-")}</td>
                <td onclick="window.location='/quote/{q.get("id")}'">{safe_string(q.get("customer_name", "-"))}</td>
                <td onclick="window.location='/quote/{q.get("id")}'">{money(q.get("total", 0))}</td>
                <td style="color:{status_color};cursor:pointer;" onclick="event.stopPropagation();showStatusModal('{q.get("id")}','{safe_string(q.get("quote_number", "-"))}','{status}')">{status_label} ▾</td>
            </tr>
            '''
        
        content = f'''
        <!-- Update Quote Status Modal -->
        <div id="statusModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center;">
            <div style="background:var(--card);padding:30px;border-radius:12px;width:90%;max-width:400px;box-shadow:0 20px 40px rgba(0,0,0,0.4);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                    <h3 style="margin:0;">Update Quote Status</h3>
                    <span style="cursor:pointer;font-size:20px;color:var(--text-muted);" onclick="closeStatusModal()">✕</span>
                </div>
                <p style="color:var(--text-muted);margin-bottom:15px;">Quote: <strong id="smQuoteNum"></strong></p>
                <div style="margin-bottom:20px;">
                    <label style="display:block;margin-bottom:8px;font-weight:600;">Quote Status</label>
                    <select id="smStatusSelect" style="width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:15px;">
                        <option value="draft">Draft</option>
                        <option value="pending">Pending</option>
                        <option value="accepted">Accepted</option>
                        <option value="declined">Declined</option>
                        <option value="invoiced">Invoiced</option>
                    </select>
                </div>
                <button class="btn btn-primary" style="width:100%;" onclick="saveQuoteStatus()">Save</button>
            </div>
        </div>
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 class="card-title" style="margin:0;">Quotes ({len(quotes)})</h3>
                <a href="/quote/new" class="btn btn-primary">+ New Quote</a>
            </div>
            <div style="display:flex;gap:8px;margin-bottom:15px;flex-wrap:wrap;">
                <button class="btn btn-secondary statusTab" data-filter="all" onclick="filterQuoteStatus('all',this)" style="font-size:12px;padding:6px 12px;font-weight:700;background:var(--primary);color:white;">All</button>
                <button class="btn btn-secondary statusTab" data-filter="draft" onclick="filterQuoteStatus('draft',this)" style="font-size:12px;padding:6px 12px;">Draft</button>
                <button class="btn btn-secondary statusTab" data-filter="pending" onclick="filterQuoteStatus('pending',this)" style="font-size:12px;padding:6px 12px;">Pending</button>
                <button class="btn btn-secondary statusTab" data-filter="accepted" onclick="filterQuoteStatus('accepted',this)" style="font-size:12px;padding:6px 12px;">Accepted</button>
                <button class="btn btn-secondary statusTab" data-filter="declined" onclick="filterQuoteStatus('declined',this)" style="font-size:12px;padding:6px 12px;">Declined</button>
                <button class="btn btn-secondary statusTab" data-filter="invoiced" onclick="filterQuoteStatus('invoiced',this)" style="font-size:12px;padding:6px 12px;">Invoiced</button>
                <button class="btn btn-secondary statusTab" data-filter="expired" onclick="filterQuoteStatus('expired',this)" style="font-size:12px;padding:6px 12px;">Expired</button>
            </div>
            <div style="margin-bottom:15px;">
                <input type="text" id="searchQuotes" placeholder="🔍 Search by customer, quote number, amount..." oninput="filterTable('searchQuotes','quoteTable')" style="width:100%;padding:10px 15px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;">
            </div>
            <table class="table" id="quoteTable">
                <thead>
                    <tr><th>Number</th><th>Date</th><th>Customer</th><th>Amount</th><th>Status</th></tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted)'>No quotes yet</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <script>
        let smQuoteId = null;
        
        function showStatusModal(quoteId, quoteNum, currentStatus) {{
            smQuoteId = quoteId;
            document.getElementById('smQuoteNum').textContent = quoteNum;
            // Map converted → invoiced for display
            const mappedStatus = (currentStatus === 'converted') ? 'invoiced' : currentStatus;
            document.getElementById('smStatusSelect').value = mappedStatus;
            document.getElementById('statusModal').style.display = 'flex';
        }}
        
        function closeStatusModal() {{
            document.getElementById('statusModal').style.display = 'none';
            smQuoteId = null;
        }}
        
        async function saveQuoteStatus() {{
            if (!smQuoteId) return;
            const newStatus = document.getElementById('smStatusSelect').value;
            try {{
                const response = await fetch('/api/quote/' + smQuoteId + '/status', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{status: newStatus}})
                }});
                const data = await response.json();
                if (data.success) {{
                    closeStatusModal();
                    location.reload();
                }} else {{
                    alert('Error: ' + (data.error || 'Update failed'));
                }}
            }} catch (err) {{
                alert('Error: ' + err.message);
            }}
        }}
        
        function filterQuoteStatus(status, btn) {{
            // Highlight active tab
            document.querySelectorAll('.statusTab').forEach(b => {{
                b.style.background = '';
                b.style.color = '';
                b.style.fontWeight = '';
            }});
            btn.style.background = 'var(--primary)';
            btn.style.color = 'white';
            btn.style.fontWeight = '700';
            
            // Filter rows
            const rows = document.querySelectorAll('#quoteTable tbody tr');
            rows.forEach(row => {{
                if (status === 'all') {{
                    row.style.display = '';
                }} else {{
                    const rowStatus = row.getAttribute('data-status') || '';
                    // "invoiced" filter also matches "converted"
                    if (status === 'invoiced') {{
                        row.style.display = (rowStatus === 'invoiced' || rowStatus === 'converted') ? '' : 'none';
                    }} else {{
                        row.style.display = (rowStatus === status) ? '' : 'none';
                    }}
                }}
            }});
        }}
        
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeStatusModal();
        }});
        </script>
        '''
        
        return render_page("Quotes", content, user, "quotes")
    
    
    @app.route("/quote/new", methods=["GET", "POST"])
    @login_required
    def quote_new():
        """Create new quote - manual form"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            customer_id = request.form.get("customer_id", "")
            customer_name = request.form.get("customer_name", "")
            valid_days = int(request.form.get("valid_days", 30))
            salesman_id = request.form.get("salesman_id", "")
            salesman_name_form = request.form.get("salesman_name", "")
            
            items = []
            descriptions = request.form.getlist("item_desc[]")
            quantities = request.form.getlist("item_qty[]")
            prices = request.form.getlist("item_price[]")
            units = request.form.getlist("item_unit[]")
            
            subtotal = Decimal("0")
            for i, desc in enumerate(descriptions):
                if desc.strip():
                    qty = Decimal(quantities[i] or "1")
                    price = Decimal(prices[i] or "0")
                    line_total = qty * price
                    subtotal += line_total
                    unit_val = units[i].strip() if i < len(units) else ""
                    items.append({
                        "description": desc,
                        "unit": unit_val,
                        "quantity": float(qty),
                        "price": float(price),
                        "total": float(line_total)
                    })
            
            if not items:
                return redirect("/quote/new?error=No+items")
            
            # Prices are EXCL VAT - ADD VAT to get total
            vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
            total = subtotal + vat
            
            existing = db.get("quotes", {"business_id": biz_id}) or []
            quote_num = next_document_number("QT", existing, "quote_number")
            
            quote = RecordFactory.quote(
                business_id=biz_id,
                customer_id=safe_uuid(customer_id),
                customer_name=customer_name,
                items=items,
                quote_number=quote_num,
                date=today(),
                valid_until=(datetime.now() + timedelta(days=valid_days)).strftime("%Y-%m-%d"),
                valid_days=valid_days,
                subtotal=float(subtotal),
                vat=float(vat),
                total=float(total),
                status="pending",
                created_by=user.get("id") if user else None,
                created_by_name=user.get("name", "") if user else "",
                salesman=salesman_id,
                salesman_name=salesman_name_form
            )
            quote_id = quote["id"]
            
            success, _ = db.save("quotes", quote)
            
            if success:
                return redirect(f"/quote/{quote_id}")
            
            return redirect("/quote/new?error=Failed+to+save")
        
        # GET - show form (stock via AJAX)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_customers = executor.submit(db.get, "customers", {"business_id": biz_id})
            fut_team = executor.submit(db.get, "team_members", {"business_id": biz_id})
        customers = fut_customers.result() if biz_id else []
        team_members = fut_team.result() if biz_id else []
        
        customer_options = '<option value="">-- Select Customer --</option>'
        customer_options += '<option value="WALKIN" style="color:var(--green);">Walk-in Customer (type name below)</option>'
        customer_options += '<option value="NEW" style="color:var(--primary);">+ Add New Customer to System</option>'
        for c in sorted(customers, key=lambda x: x.get("name", "")):
            customer_options += f'<option value="{c.get("id")}" data-name="{safe_string(c.get("name", ""))}">{safe_string(c.get("name", ""))}</option>'
        
        # Salesman dropdown from team members + current user
        salesman_options = '<option value="">-- Select Salesman --</option>'
        if user:
            salesman_options += f'<option value="{user.get("id", "")}" data-name="{safe_string(user.get("name", ""))}" selected>{safe_string(user.get("name", ""))} (me)</option>'
        seen_ids = {user.get("id", "") if user else ""}
        for tm in sorted(team_members, key=lambda x: x.get("name", "")):
            tm_uid = tm.get("user_id") or tm.get("id", "")
            if tm_uid not in seen_ids:
                seen_ids.add(tm_uid)
                salesman_options += f'<option value="{tm_uid}" data-name="{safe_string(tm.get("name", ""))}">{safe_string(tm.get("name", ""))}</option>'
        
        error_msg = request.args.get("error", "")
        error_html = f'<div style="background:var(--red);color:white;padding:10px;border-radius:8px;margin-bottom:15px;">{error_msg}</div>' if error_msg else ""
        
        _dd_css = '<style>.stock-dropdown{position:absolute;top:100%;left:0;right:0;background:var(--card);border:1px solid var(--border);border-radius:6px;max-height:220px;overflow-y:auto;z-index:999;box-shadow:0 4px 12px rgba(0,0,0,0.3);}.stock-dd-item{padding:8px 10px;cursor:pointer;font-size:13px;border-bottom:1px solid var(--border);}.stock-dd-item:hover{background:var(--primary);color:white;}</style>'
        
        content = f'''
        {_dd_css}
        {error_html}
        <div class="card">
            <h3 style="margin:0 0 20px 0;">New Quote</h3>
            
            <form method="POST" id="quoteForm">
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label>Customer</label>
                        <select name="customer_id" id="customerSelect" onchange="handleCustomerChange()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            {customer_options}
                        </select>
                        <input type="text" name="customer_name" id="customerName" placeholder="Type walk-in customer name" style="display:none;width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);margin-top:6px;">
                    </div>
                    <div>
                        <label>Salesman</label>
                        <select name="salesman_id" id="salesmanSelect" onchange="handleSalesmanChange()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            {salesman_options}
                        </select>
                        <input type="hidden" name="salesman_name" id="salesmanName" value="{safe_string(user.get('name', '')) if user else ''}">
                    </div>
                    <div>
                        <label>Date</label>
                        <input type="date" value="{today()}" disabled style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label>Valid For (Days)</label>
                        <input type="number" name="valid_days" value="30" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h4>Line Items</h4>
                
                <table class="table" id="lineItems">
                    <thead>
                        <tr>
                            <th style="width:38%">Description</th>
                            <th style="width:10%">Unit</th>
                            <th style="width:10%">Qty</th>
                            <th style="width:17%">Price</th>
                            <th style="width:15%">Total</th>
                            <th style="width:10%"></th>
                        </tr>
                    </thead>
                    <tbody id="itemRows">
                        <tr>
                            <td style="position:relative;"><input type="text" name="item_desc[]" autocomplete="off" oninput="stockSearch(this)" onfocus="stockSearch(this)" placeholder="Type 2+ chars to search stock..." style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"><input type="hidden" name="item_stock_id[]" value=""><div class="stock-dropdown" style="display:none;"></div></td>
                            <td><input type="text" name="item_unit[]" placeholder="ea" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);text-align:center;"></td>
                            <td><input type="number" name="item_qty[]" value="1" min="0.01" step="any" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                            <td><input type="number" name="item_price[]" step="0.01" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                            <td class="row-total">R0.00</td>
                            <td><button type="button" onclick="deleteRow(this)" style="background:var(--red);color:white;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;">✕</button></td>
                        </tr>
                    </tbody>
                </table>
                
                <button type="button" onclick="addRow()" class="btn btn-secondary" style="margin:10px 0;">+ Add Line</button>
                
                <div style="text-align:right;margin-top:20px;padding:15px;background:rgba(0,0,0,0.2);border-radius:8px;">
                    <div style="margin-bottom:10px;">Subtotal: <strong id="subtotal">R0.00</strong></div>
                    <div style="margin-bottom:10px;">VAT (15%): <strong id="vat">R0.00</strong></div>
                    <div style="font-size:24px;">Total: <strong id="total" style="color:var(--green);">R0.00</strong></div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:20px;">
                    <button type="submit" class="btn btn-primary" style="flex:1;">Create Quote</button>
                    <a href="/quotes" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <script>
        function handleCustomerChange() {{
            const sel = document.getElementById('customerSelect');
            const nameInput = document.getElementById('customerName');
            if (sel.value === 'NEW') {{
                window.location.href = '/customer/new?return=/quote/new';
                return;
            }}
            if (sel.value === 'WALKIN') {{
                nameInput.style.display = 'block';
                nameInput.focus();
                nameInput.value = '';
                return;
            }}
            nameInput.style.display = 'none';
            const name = sel.options[sel.selectedIndex]?.dataset?.name || '';
            nameInput.value = name;
        }}
        
        function handleSalesmanChange() {{
            const sel = document.getElementById('salesmanSelect');
            const nameInput = document.getElementById('salesmanName');
            nameInput.value = sel.options[sel.selectedIndex]?.dataset?.name || '';
        }}
        
        function checkStock(input) {{ /* stub */ }}
        let _searchTimer = null;
        function stockSearch(input) {{
            const q = input.value.trim();
            const dd = input.closest('td').querySelector('.stock-dropdown');
            if (q.length < 2) {{ dd.style.display='none'; return; }}
            clearTimeout(_searchTimer);
            _searchTimer = setTimeout(()=>{{
                fetch('/api/stock/lookup?q='+encodeURIComponent(q)).then(r=>r.json()).then(items=>{{
                    if(!items.length){{ dd.style.display='none'; return; }}
                    let h='';
                    items.forEach(s=>{{
                        const lb=(s.label||'').replace(/'/g,"\\'"), un=(s.unit||'').replace(/'/g,"\\'");
                        h+='<div class="stock-dd-item" onmousedown="pickStock(this,\\''+s.id+'\\',\\''+lb+'\\','+s.price+',\\''+un+'\\')">'
                          +'<b>'+(s.code||'')+'</b> '+(s.desc||'')+' <span style="float:right;color:#22c55e;">R'+s.price.toFixed(2)+'</span>'
                          +(s.unit?'<span style="color:#888;font-size:11px;margin-left:4px;">'+s.unit+'</span>':'')+'</div>';
                    }});
                    dd.innerHTML=h; dd.style.display='block';
                }});
            }}, 250);
        }}
        function pickStock(el,stockId,label,price,unit){{
            const row=el.closest('tr');
            row.querySelector('input[name="item_desc[]"]').value=label;
            const sid=row.querySelector('input[name="item_stock_id[]"]'); if(sid) sid.value=stockId;
            const p=row.querySelector('input[name="item_price[]"]'); p.value=price;
            const u=row.querySelector('input[name="item_unit[]"]'); if(u&&unit) u.value=unit;
            el.closest('.stock-dropdown').style.display='none'; calcRow(p);
        }}
        document.addEventListener('click',function(e){{
            if(!e.target.closest('.stock-dropdown')&&!e.target.matches('input[name="item_desc[]"]'))
                document.querySelectorAll('.stock-dropdown').forEach(d=>d.style.display='none');
        }});
        
        function addRow() {{
            const tbody = document.getElementById('itemRows');
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="position:relative;"><input type="text" name="item_desc[]" autocomplete="off" oninput="stockSearch(this)" onfocus="stockSearch(this)" placeholder="Type 2+ chars to search stock..." style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"><input type="hidden" name="item_stock_id[]" value=""><div class="stock-dropdown" style="display:none;"></div></td>
                <td><input type="text" name="item_unit[]" placeholder="ea" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);text-align:center;"></td>
                <td><input type="number" name="item_qty[]" value="1" min="0.01" step="any" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td><input type="number" name="item_price[]" step="0.01" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td class="row-total">R0.00</td>
                <td><button type="button" onclick="deleteRow(this)" style="background:var(--red);color:white;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;">✕</button></td>
            `;
            tbody.appendChild(row);
        }}
        
        function deleteRow(btn) {{
            const tbody = document.getElementById('itemRows');
            if (tbody.children.length > 1) {{
                btn.closest('tr').remove();
                calcTotals();
            }} else {{
                alert('Need at least one line item');
            }}
        }}
        
        function calcRow(input) {{
            const row = input.closest('tr');
            const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
            const price = parseFloat(row.querySelector('input[name="item_price[]"]').value) || 0;
            const total = qty * price;
            row.querySelector('.row-total').textContent = 'R' + total.toFixed(2);
            calcTotals();
        }}
        
        function calcTotals() {{
            let subtotal = 0;
            document.querySelectorAll('.row-total').forEach(cell => {{
                subtotal += parseFloat(cell.textContent.replace('R', '')) || 0;
            }});
            const vat = subtotal * 0.15;
            const total = subtotal + vat;
            document.getElementById('subtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('vat').textContent = 'R' + vat.toFixed(2);
            document.getElementById('total').textContent = 'R' + total.toFixed(2);
        }}
        </script>
        '''
        
        return render_page("New Quote", content, user, "quotes")
    
    
    @app.route("/quote/<quote_id>")
    @login_required
    def quote_view(quote_id):
        """View quote with convert to invoice option"""
        
        user = Auth.get_current_user()
        
        # Load business FRESH from DB (not cached) for accurate details on quote
        biz_id = session.get("business_id")
        business = db.get_one("businesses", biz_id) if biz_id else Auth.get_current_business()
        
        quote = db.get_one("quotes", quote_id)
        if not quote:
            return redirect("/quotes")
        
        # FAILSAFE: Calculate totals from items if missing or zero
        raw_items = quote.get("items", [])
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except:
                raw_items = []
        
        if raw_items:
            line_total = sum(float(item.get("total", 0)) for item in raw_items)
            if line_total > 0:
                # Line totals are EXCL VAT - ADD VAT
                calculated_subtotal = line_total
                calculated_vat = round(line_total * 0.15, 2)
                calculated_total = round(line_total + calculated_vat, 2)
                
                if not quote.get("subtotal") or float(quote.get("subtotal", 0)) == 0:
                    quote["subtotal"] = calculated_subtotal
                if not quote.get("vat") or float(quote.get("vat", 0)) == 0:
                    quote["vat"] = calculated_vat
                if not quote.get("total") or float(quote.get("total", 0)) == 0:
                    quote["total"] = calculated_total
        
        # Get customer details if customer_id exists
        customer = None
        if quote.get("customer_id"):
            customer = db.get_one("customers", quote.get("customer_id"))
        
        # Parse items for display
        items = raw_items
        
        items_html = ""
        for item in items:
            # Handle both qty and quantity field names
            qty = item.get("qty") or item.get("quantity") or 1
            desc = item.get("description") or item.get("desc") or "-"
            price = float(item.get("price") or item.get("unit_price") or 0)
            total_excl = float(item.get("total") or item.get("line_total") or 0)
            if total_excl == 0 and price > 0:
                total_excl = round(float(qty) * price, 2)
            disc = float(item.get("discount") or item.get("disc") or 0)
            vat_rate = 15.0
            vat_amount = round(total_excl * vat_rate / 100, 2)
            total_incl = round(total_excl + vat_amount, 2)
            unit = item.get("unit") or item.get("uom") or ""
            items_html += f'''
            <tr style="border-bottom:1px solid #e5e7eb;">
                <td style="padding:4px 6px;font-size:11px;">{safe_string(desc)}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{safe_string(unit)}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{qty}</td>
                <td style="text-align:right;padding:4px 6px;font-size:11px;">{money(price)}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{disc:.1f}%</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;">{vat_rate:.0f}%</td>
                <td style="text-align:right;padding:4px 6px;font-size:11px;">{money(total_excl)}</td>
                <td style="text-align:right;padding:4px 6px;font-size:11px;font-weight:600;">{money(total_incl)}</td>
            </tr>
            '''
        
        status = quote.get("status", "pending")
        biz_name = business.get("name", "Business") if business else "Business"
        
        # Show weight if it's a steel quote
        weight_info = ""
        weight = quote.get("weight_kg")
        if weight:
            weight_info = f'<p style="color:var(--text-muted);margin:10px 0;"> Total Weight: <strong>{float(weight):.1f}kg</strong></p>'
        
        # === QUOTE EXPIRY: 30 days from quote date ===
        import datetime
        quote_expired = False
        days_remaining = 30
        expiry_date_str = ""
        try:
            quote_date_str = quote.get("date", "")
            if quote_date_str:
                quote_date = datetime.datetime.strptime(quote_date_str[:10], "%Y-%m-%d").date()
                expiry_date = quote_date + datetime.timedelta(days=30)
                expiry_date_str = expiry_date.strftime("%Y-%m-%d")
                today_date = datetime.date.today()
                days_remaining = (expiry_date - today_date).days
                if days_remaining < 0 and status in ("pending", "draft"):
                    quote_expired = True
                    status = "expired"
                    # Update in DB so it stays expired
                    try:
                        db.update("quotes", quote_id, {"status": "expired"})
                    except:
                        pass
        except:
            pass
        
        action_buttons = ""
        # Edit button - available for draft, pending, accepted (not converted/invoiced)
        can_edit = status in ("draft", "pending", "accepted", "expired")
        edit_btn = f'<a href="/quote/{quote_id}/edit" class="btn btn-secondary">✏️ Edit</a>' if can_edit else ''
        
        # Status dropdown - always available (like Sage)
        status_dropdown = f'''
        <select id="qvStatusSelect" onchange="updateQuoteStatus(this.value)" style="padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;cursor:pointer;">
            <option value="draft" {"selected" if status == "draft" else ""}>Draft</option>
            <option value="pending" {"selected" if status == "pending" else ""}>Pending</option>
            <option value="accepted" {"selected" if status == "accepted" else ""}>Accepted</option>
            <option value="declined" {"selected" if status == "declined" else ""}>Declined</option>
            <option value="invoiced" {"selected" if status in ("invoiced", "converted") else ""}>Invoiced</option>
        </select>
        '''
        
        if status == "expired":
            action_buttons = f'''
            <span style="background:#ef4444;color:white;padding:8px 16px;border-radius:8px;font-weight:700;font-size:13px;">⚠ EXPIRED</span>
            {edit_btn}
            {status_dropdown}
            <form action="/quote/{quote_id}/convert-to-invoice" method="POST" style="display:inline;">
                <button type="submit" class="btn btn-secondary">➜ Invoice Anyway</button>
            </form>
            '''
        elif status in ("pending", "draft"):
            action_buttons = f'''
            {edit_btn}
            {status_dropdown}
            <form action="/quote/{quote_id}/convert-to-invoice" method="POST" style="display:inline;">
                <button type="submit" class="btn btn-primary">➜ Convert to Invoice</button>
            </form>
            '''
        elif status == "accepted":
            # Check if job card already exists
            existing_job = None
            jobs = db.get("jobs", {"business_id": business.get("id") if business else None})
            for j in jobs:
                if j.get("quote_id") == quote_id:
                    existing_job = j
                    break
            
            if existing_job:
                action_buttons = f'''
                {edit_btn}
                {status_dropdown}
                <a href="/job-card/{existing_job.get("id")}" class="btn btn-primary">View Job Card</a>
                <form action="/quote/{quote_id}/convert-to-invoice" method="POST" style="display:inline;">
                    <button type="submit" class="btn btn-secondary">➜ Invoice</button>
                </form>
                '''
            else:
                action_buttons = f'''
                {edit_btn}
                {status_dropdown}
                <form action="/quote/{quote_id}/create-job-card" method="POST" style="display:inline;">
                    <button type="submit" class="btn btn-primary">Create Job Card</button>
                </form>
                <form action="/quote/{quote_id}/convert-to-invoice" method="POST" style="display:inline;">
                    <button type="submit" class="btn btn-secondary">➜ Invoice</button>
                </form>
                '''
        elif status in ("converted", "invoiced"):
            inv_id = quote.get("converted_invoice_id", "")
            if inv_id:
                action_buttons = f'{status_dropdown} <a href="/invoice/{inv_id}" class="btn btn-secondary">View Invoice</a>'
            else:
                action_buttons = f'{status_dropdown}'
        elif status == "declined":
            action_buttons = f'''
            {edit_btn}
            {status_dropdown}
            <form action="/quote/{quote_id}/convert-to-invoice" method="POST" style="display:inline;">
                <button type="submit" class="btn btn-secondary">➜ Invoice Anyway</button>
            </form>
            '''
        
        # Build business details section
        biz_address = safe_string(business.get("address", "")).replace("\n", "<br>") if business else ""
        biz_phone = business.get("phone", "") if business else ""
        biz_email = business.get("email", "") if business else ""
        biz_vat = business.get("vat_number", "") if business else ""
        
        # Resolve who created this quote
        created_by_name = quote.get("created_by_name") or ""
        if not created_by_name:
            _cb = quote.get("created_by") or ""
            if _cb:
                try:
                    team = db.get("team_members", {"business_id": biz_id}) or []
                    for t in team:
                        if t.get("id") == _cb or t.get("user_id") == _cb:
                            created_by_name = t.get("name", t.get("email", ""))
                            break
                    if not created_by_name:
                        _u = db.get_one("users", _cb)
                        if _u:
                            created_by_name = _u.get("name", _u.get("email", ""))
                except:
                    pass
        
        # Resolve salesman name
        salesman_display = quote.get("salesman_name") or ""
        if not salesman_display:
            _sm = quote.get("salesman") or ""
            if _sm:
                try:
                    _team = db.get("team_members", {"business_id": biz_id}) or []
                    for t in _team:
                        if t.get("id") == _sm or t.get("user_id") == _sm:
                            salesman_display = t.get("name", t.get("email", ""))
                            break
                    if not salesman_display:
                        _u = db.get_one("users", _sm)
                        if _u:
                            salesman_display = _u.get("name", _u.get("email", ""))
                except:
                    pass
        
        # Build customer details section  
        cust_name = safe_string(quote.get("customer_name", "-"))
        cust_phone = customer.get("phone", "") if customer else ""
        cust_cell = customer.get("cell", "") if customer else ""
        cust_email = customer.get("email", "") if customer else ""
        cust_address = safe_string(customer.get("address", "")).replace("\n", "<br>") if customer else ""
        cust_vat = customer.get("vat_number", "") if customer else ""
        cust_tel = cust_phone or cust_cell
        
        content = f'''
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/quotes" style="color:var(--text-muted);">← Back to Quotes</a>
            <div style="display:flex;gap:10px;">
                <button class="btn btn-primary" onclick="showEmailModal()" style="background:#3b82f6;">Email</button>
                <button class="btn btn-secondary" onclick="printDocument();">🖨️ Print</button>
                {action_buttons}
            </div>
        </div>
        
        <!-- EMAIL MODAL -->
        <div id="emailModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:9999;align-items:center;justify-content:center;">
            <div style="background:var(--card);padding:30px;border-radius:12px;width:90%;max-width:450px;">
                <h3 style="margin-top:0;">Email Quote</h3>
                <p style="color:var(--text-muted);margin-bottom:20px;">Send quote <strong>{quote.get("quote_number", "")}</strong> to:</p>
                
                <input type="email" id="emailTo" value="{cust_email}" placeholder="customer@email.com" 
                       style="width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:16px;margin-bottom:15px;">
                
                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button onclick="closeEmailModal()" class="btn btn-secondary">Cancel</button>
                    <button onclick="sendQuoteEmail()" class="btn btn-primary" style="background:#10b981;">Send Email</button>
                </div>
            </div>
        </div>
        
        <div class="card" id="printArea" style="background:white;color:#333;padding:0;overflow:hidden;">
            <!-- TOP BAR -->
            <div style="background:#1e3a5f;color:white;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <h1 style="margin:0;font-size:16px;font-weight:700;letter-spacing:0.5px;">{biz_name}</h1>
                    {f'<p style="margin:4px 0 0 0;font-size:10px;opacity:0.8;">{biz_address}</p>' if biz_address else ''}
                </div>
                <div style="text-align:right;">
                    <h2 style="margin:0;font-size:20px;font-weight:700;letter-spacing:2px;">QUOTATION</h2>
                    <span style="background:{"#10b981" if status == "accepted" else "#ef4444" if status in ("declined", "expired") else "#3b82f6" if status == "converted" else "rgba(255,255,255,0.2)"};color:white;padding:4px 12px;border-radius:20px;font-size:12px;">
                        {status.upper()}
                    </span>
                </div>
            </div>
            
            <!-- DETAILS GRID -->
            <div style="padding:10px 25px;display:grid;grid-template-columns:1fr 1fr;gap:0;border-bottom:1px solid #e5e7eb;">
                <div style="border-right:1px solid #e5e7eb;padding-right:25px;">
                    <table style="width:100%;font-size:11px;color:#333;">
                        <tr><td style="padding:4px 0;color:#888;width:120px;">Number:</td><td style="padding:4px 0;font-weight:600;">{quote.get("quote_number", "-")}</td></tr>
                        <tr><td style="padding:4px 0;color:#888;">Date:</td><td style="padding:4px 0;">{quote.get("date", "-")}</td></tr>
                        <tr><td style="padding:4px 0;color:#888;">Valid Until:</td><td style="padding:4px 0;{"color:#ef4444;font-weight:600;" if status == "expired" else ""}">{expiry_date_str or "7 days"}{"  ⚠ EXPIRED" if status == "expired" else ""}</td></tr>
                        {f'<tr><td style="padding:4px 0;color:#888;">Our VAT No:</td><td style="padding:4px 0;">{biz_vat}</td></tr>' if biz_vat else ''}
                        {f'<tr><td style="padding:4px 0;color:#888;">Prepared By:</td><td style="padding:4px 0;font-weight:600;">{created_by_name}</td></tr>' if created_by_name else ''}
                        {f'<tr><td style="padding:4px 0;color:#888;">Salesman:</td><td style="padding:4px 0;font-weight:600;">{salesman_display}</td></tr>' if salesman_display else ''}
                    </table>
                    {f'<div style="margin-top:8px;font-size:10px;color:#666;">Tel: {biz_phone}</div>' if biz_phone else ''}
                    {f'<div style="font-size:10px;color:#666;">{biz_email}</div>' if biz_email else ''}
                </div>
                <div style="padding-left:25px;">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-weight:600;">Quote To</div>
                    <div style="font-size:13px;font-weight:700;color:#1e3a5f;margin-bottom:4px;">{cust_name}</div>
                    {f'<div style="font-size:10px;color:#555;margin-bottom:2px;">{cust_address}</div>' if cust_address else ''}
                    {f'<div style="font-size:10px;color:#555;">Tel: {cust_tel}</div>' if cust_tel else ''}
                    {f'<div style="font-size:10px;color:#555;">{cust_email}</div>' if cust_email else ''}
                    {f'<div style="font-size:10px;color:#555;margin-top:4px;">VAT No: {cust_vat}</div>' if cust_vat else ''}
                </div>
            </div>
            
            {weight_info}
            
            <!-- ITEMS TABLE -->
            <div style="padding:0 25px;">
                <table style="width:100%;border-collapse:collapse;font-size:14px;">
                    <thead>
                        <tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">
                            <th style="padding:5px 6px;text-align:left;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;">Description</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:50px;">Unit</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">Qty</th>
                            <th style="padding:5px 6px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Excl. Price</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">Disc %</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">VAT %</th>
                            <th style="padding:5px 6px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Excl. Total</th>
                            <th style="padding:5px 6px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Incl. Total</th>
                        </tr>
                    </thead>
                    <tbody style="color:#333;">
                        {items_html}
                    </tbody>
                </table>
            </div>
            
            <!-- TOTALS + BANKING -->
            <div style="padding:10px 25px 15px;display:flex;justify-content:space-between;align-items:flex-end;">
                <div style="font-size:12px;color:#666;max-width:55%;">
                    {f"""<div style="border:1px solid #e5e7eb;border-radius:6px;padding:12px;background:#fafafa;">
                        <div style="font-weight:600;color:#333;margin-bottom:6px;font-size:13px;">Banking Details</div>
                        <div>Bank: {business.get("bank_name", "")}</div>
                        <div>Account: {business.get("bank_account", "")}</div>
                        <div>Branch: {business.get("bank_branch", "")}</div>
                    </div>""" if business and business.get("bank_account") else ''}
                    <div style="margin-top:12px;font-size:11px;color:#999;">
                        <p style="margin:2px 0;">Thank you for your business!</p>
                        <p style="margin:6px 0 2px 0;font-weight:600;color:#555;">Prices valid for 30 days from date of quote.</p>
                        {"<p style='margin:2px 0;color:#ef4444;font-weight:700;'>⚠ This quote has expired.</p>" if status == "expired" else f"<p style='margin:2px 0;color:#888;'>({days_remaining} day{'s' if days_remaining != 1 else ''} remaining)</p>" if days_remaining >= 0 and status in ("pending", "draft") else ""}
                    </div>
                </div>
                <table style="width:220px;border-collapse:collapse;">
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:4px 8px;color:#666;font-size:11px;">Total Exclusive</td>
                        <td style="padding:4px 8px;text-align:right;color:#333;font-size:11px;">{money(quote.get("subtotal", 0))}</td>
                    </tr>
                    <tr style="border-bottom:1px solid #e5e7eb;">
                        <td style="padding:4px 8px;color:#666;font-size:11px;">Total VAT</td>
                        <td style="padding:4px 8px;text-align:right;color:#333;font-size:11px;">{money(quote.get("vat", 0))}</td>
                    </tr>
                    <tr style="background:#1e3a5f;">
                        <td style="padding:8px 8px;color:white;font-size:13px;font-weight:700;">TOTAL</td>
                        <td style="padding:8px 8px;text-align:right;color:white;font-size:13px;font-weight:700;">{money(quote.get("total", 0))}</td>
                    </tr>
                </table>
            </div>
        </div>
            </div>
        </div>
        </div>
        
        <script>
        async function updateQuoteStatus(status) {{
            const response = await fetch('/api/quote/{quote_id}/status', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{status: status}})
            }});
            const data = await response.json();
            if (data.success) location.reload();
        }}
        
        // EMAIL FUNCTIONS
        function showEmailModal() {{
            document.getElementById('emailModal').style.display = 'flex';
            document.getElementById('emailTo').focus();
        }}
        
        function closeEmailModal() {{
            document.getElementById('emailModal').style.display = 'none';
        }}
        
        async function sendQuoteEmail() {{
            const email = document.getElementById('emailTo').value.trim();
            if (!email || !email.includes('@')) {{
                alert('Please enter a valid email address');
                return;
            }}
            
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = 'Sending...';
            
            try {{
                const response = await fetch('/api/quote/{quote_id}/email', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{to_email: email}})
                }});
                const result = await response.json();
                if (result.success) {{
                    alert('✅ Quote emailed to ' + email);
                    closeEmailModal();
                }} else {{
                    alert('❌ ' + (result.error || 'Failed to send email'));
                }}
            }} catch (err) {{
                alert('❌ Error: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.textContent = 'Send Email';
            }}
        }}
        
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeEmailModal();
        }});
        
        // PRINT FUNCTION - Opens new window for reliable multi-page printing
        function printDocument() {{
            const content = document.getElementById('printArea').innerHTML;
            const printWindow = window.open('', '_blank', 'width=800,height=600');
            
            printWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Quote</title>
                    <style>
                        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                        body {{ 
                            font-family: Arial, Helvetica, sans-serif; 
                            padding: 0;
                            color: #333;
                            background: white;
                            font-size: 11px;
                        }}
                        table {{ 
                            width: 100%; 
                            border-collapse: collapse; 
                            page-break-inside: auto;
                        }}
                        tr {{ page-break-inside: avoid; }}
                        thead {{ display: table-header-group; }}
                        @media print {{
                            body {{ padding: 0; }}
                            @page {{ size: A4; margin: 10mm 12mm; }}
                        }}
                    </style>
                </head>
                <body>${{content}}</body>
                </html>
            `);
            
            printWindow.document.close();
            printWindow.focus();
            
            setTimeout(function() {{
                printWindow.print();
                printWindow.close();
            }}, 250);
        }}
        </script>
        '''
        
        return render_page(f"Quote {quote.get('quote_number', '')}", content, user, "quotes")
    
    
    @app.route("/quote/<quote_id>/edit", methods=["GET", "POST"])
    @login_required
    def quote_edit(quote_id):
        """Edit an existing quote - items, customer, salesman"""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        quote = db.get_one("quotes", quote_id)
        if not quote:
            return redirect("/quotes")
        
        # Don't allow editing converted/invoiced quotes
        if quote.get("status") in ("converted", "invoiced"):
            flash("Cannot edit a converted/invoiced quote", "error")
            return redirect(f"/quote/{quote_id}")
        
        if request.method == "POST":
            customer_id = request.form.get("customer_id", "")
            customer_name = request.form.get("customer_name", "")
            salesman_id = request.form.get("salesman_id", "")
            salesman_name_form = request.form.get("salesman_name", "")
            
            items = []
            descriptions = request.form.getlist("item_desc[]")
            quantities = request.form.getlist("item_qty[]")
            prices = request.form.getlist("item_price[]")
            units = request.form.getlist("item_unit[]")
            
            subtotal = Decimal("0")
            for i, desc in enumerate(descriptions):
                if desc.strip():
                    qty = Decimal(quantities[i] or "1")
                    price = Decimal(prices[i] or "0")
                    line_total = qty * price
                    subtotal += line_total
                    unit_val = units[i].strip() if i < len(units) else ""
                    items.append({
                        "description": desc,
                        "unit": unit_val,
                        "quantity": float(qty),
                        "price": float(price),
                        "total": float(line_total)
                    })
            
            if not items:
                return redirect(f"/quote/{quote_id}/edit?error=No+items")
            
            vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
            total = subtotal + vat
            
            updates = {
                "customer_id": safe_uuid(customer_id) or quote.get("customer_id"),
                "customer_name": customer_name or quote.get("customer_name"),
                "items": items,
                "subtotal": float(subtotal),
                "vat": float(vat),
                "total": float(total),
                "salesman": salesman_id,
                "salesman_name": salesman_name_form,
                "updated_at": now()
            }
            
            try:
                db.update("quotes", quote_id, updates)
                logger.info(f"[QUOTE] Edited {quote.get('quote_number')}")
            except Exception as e:
                logger.error(f"[QUOTE] Edit error: {e}")
            
            return redirect(f"/quote/{quote_id}")
        
        # GET - show edit form
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_customers = executor.submit(db.get, "customers", {"business_id": biz_id})
            fut_team = executor.submit(db.get, "team_members", {"business_id": biz_id})
        customers = fut_customers.result() if biz_id else []
        team_members = fut_team.result() if biz_id else []
        
        # Parse existing items
        raw_items = quote.get("items", [])
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except:
                raw_items = []
        
        existing_customer_id = quote.get("customer_id", "")
        existing_customer_name = quote.get("customer_name", "")
        existing_salesman_id = quote.get("salesman", "")
        existing_salesman_name = quote.get("salesman_name", "")
        
        # Build customer options
        customer_options = '<option value="">-- Select Customer --</option>'
        customer_options += '<option value="WALKIN" style="color:var(--green);">Walk-in Customer (type name below)</option>'
        for c in sorted(customers, key=lambda x: x.get("name", "")):
            sel = "selected" if c.get("id") == existing_customer_id else ""
            customer_options += f'<option value="{c.get("id")}" data-name="{safe_string(c.get("name", ""))}" {sel}>{safe_string(c.get("name", ""))}</option>'
        
        # If customer not found in list (walk-in), show name
        walkin_name_display = ""
        if existing_customer_name and not existing_customer_id:
            walkin_name_display = existing_customer_name
        
        # Salesman options
        salesman_options = '<option value="">-- Select Salesman --</option>'
        if user:
            sel_me = "selected" if user.get("id", "") == existing_salesman_id or not existing_salesman_id else ""
            salesman_options += f'<option value="{user.get("id", "")}" data-name="{safe_string(user.get("name", ""))}" {sel_me}>{safe_string(user.get("name", ""))} (me)</option>'
        seen_ids = {user.get("id", "") if user else ""}
        for tm in sorted(team_members, key=lambda x: x.get("name", "")):
            tm_uid = tm.get("user_id") or tm.get("id", "")
            if tm_uid not in seen_ids:
                seen_ids.add(tm_uid)
                sel_tm = "selected" if tm_uid == existing_salesman_id else ""
                salesman_options += f'<option value="{tm_uid}" data-name="{safe_string(tm.get("name", ""))}" {sel_tm}>{safe_string(tm.get("name", ""))}</option>'
        
        # Build existing item rows
        existing_rows = ""
        for item in raw_items:
            desc = safe_string(item.get("description") or item.get("desc") or "")
            unit = safe_string(item.get("unit", ""))
            qty = item.get("quantity") or item.get("qty") or 1
            price = item.get("price") or item.get("unit_price") or 0
            total_val = float(qty) * float(price)
            existing_rows += f'''
            <tr>
                <td style="position:relative;"><input type="text" name="item_desc[]" value="{desc}" autocomplete="off" oninput="stockSearch(this)" onfocus="stockSearch(this)" placeholder="Type 2+ chars to search stock..." style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"><input type="hidden" name="item_stock_id[]" value=""><div class="stock-dropdown" style="display:none;"></div></td>
                <td><input type="text" name="item_unit[]" value="{unit}" placeholder="ea" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);text-align:center;"></td>
                <td><input type="number" name="item_qty[]" value="{qty}" min="0.01" step="any" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td><input type="number" name="item_price[]" value="{price}" step="0.01" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td class="row-total">R{total_val:.2f}</td>
                <td><button type="button" onclick="deleteRow(this)" style="background:var(--red);color:white;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;">✕</button></td>
            </tr>
            '''
        
        if not existing_rows:
            existing_rows = '''
            <tr>
                <td style="position:relative;"><input type="text" name="item_desc[]" autocomplete="off" oninput="stockSearch(this)" onfocus="stockSearch(this)" placeholder="Type 2+ chars to search stock..." style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"><input type="hidden" name="item_stock_id[]" value=""><div class="stock-dropdown" style="display:none;"></div></td>
                <td><input type="text" name="item_unit[]" placeholder="ea" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);text-align:center;"></td>
                <td><input type="number" name="item_qty[]" value="1" min="0.01" step="any" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td><input type="number" name="item_price[]" step="0.01" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td class="row-total">R0.00</td>
                <td><button type="button" onclick="deleteRow(this)" style="background:var(--red);color:white;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;">✕</button></td>
            </tr>
            '''
        
        error_msg = request.args.get("error", "")
        error_html = f'<div style="background:var(--red);color:white;padding:10px;border-radius:8px;margin-bottom:15px;">{error_msg}</div>' if error_msg else ""
        
        _dd_css = '<style>.stock-dropdown{position:absolute;top:100%;left:0;right:0;background:var(--card);border:1px solid var(--border);border-radius:6px;max-height:220px;overflow-y:auto;z-index:999;box-shadow:0 4px 12px rgba(0,0,0,0.3);}.stock-dd-item{padding:8px 10px;cursor:pointer;font-size:13px;border-bottom:1px solid var(--border);}.stock-dd-item:hover{background:var(--primary);color:white;}</style>'
        
        content = f'''
        {_dd_css}
        {error_html}
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <h3 style="margin:0;">Edit Quote — {quote.get("quote_number", "")}</h3>
                <span style="color:var(--text-muted);font-size:13px;">Status: {quote.get("status", "draft").title()}</span>
            </div>
            
            <form method="POST" id="quoteForm">
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label>Customer</label>
                        <select name="customer_id" id="customerSelect" onchange="handleCustomerChange()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            {customer_options}
                        </select>
                        <input type="text" name="customer_name" id="customerName" placeholder="Type walk-in customer name" value="{safe_string(walkin_name_display)}" style="{"display:block" if walkin_name_display else "display:none"};width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);margin-top:6px;">
                    </div>
                    <div>
                        <label>Salesman</label>
                        <select name="salesman_id" id="salesmanSelect" onchange="handleSalesmanChange()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            {salesman_options}
                        </select>
                        <input type="hidden" name="salesman_name" id="salesmanName" value="{safe_string(existing_salesman_name)}">
                    </div>
                    <div>
                        <label>Date</label>
                        <input type="date" value="{quote.get('date', today())}" disabled style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h4>Line Items</h4>
                
                <table class="table" id="lineItems">
                    <thead>
                        <tr>
                            <th style="width:38%">Description</th>
                            <th style="width:10%">Unit</th>
                            <th style="width:10%">Qty</th>
                            <th style="width:17%">Price</th>
                            <th style="width:15%">Total</th>
                            <th style="width:10%"></th>
                        </tr>
                    </thead>
                    <tbody id="itemRows">
                        {existing_rows}
                    </tbody>
                </table>
                
                <button type="button" onclick="addRow()" class="btn btn-secondary" style="margin:10px 0;">+ Add Line</button>
                
                <div style="text-align:right;margin-top:20px;padding:15px;background:rgba(0,0,0,0.2);border-radius:8px;">
                    <div style="margin-bottom:10px;">Subtotal: <strong id="subtotal">R0.00</strong></div>
                    <div style="margin-bottom:10px;">VAT (15%): <strong id="vat">R0.00</strong></div>
                    <div style="font-size:24px;">Total: <strong id="total" style="color:var(--green);">R0.00</strong></div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:20px;">
                    <button type="submit" class="btn btn-primary" style="flex:1;">Save Changes</button>
                    <a href="/quote/{quote_id}" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <script>
        function handleCustomerChange() {{
            const sel = document.getElementById('customerSelect');
            const nameInput = document.getElementById('customerName');
            if (sel.value === 'WALKIN') {{
                nameInput.style.display = 'block';
                nameInput.focus();
                nameInput.value = '';
                return;
            }}
            nameInput.style.display = 'none';
            const name = sel.options[sel.selectedIndex]?.dataset?.name || '';
            nameInput.value = name;
        }}
        
        function handleSalesmanChange() {{
            const sel = document.getElementById('salesmanSelect');
            const nameInput = document.getElementById('salesmanName');
            nameInput.value = sel.options[sel.selectedIndex]?.dataset?.name || '';
        }}
        
        let _searchTimer = null;
        function stockSearch(input) {{
            const q = input.value.trim();
            const dd = input.closest('td').querySelector('.stock-dropdown');
            if (q.length < 2) {{ dd.style.display='none'; return; }}
            clearTimeout(_searchTimer);
            _searchTimer = setTimeout(()=>{{
                fetch('/api/stock/lookup?q='+encodeURIComponent(q)).then(r=>r.json()).then(items=>{{
                    if(!items.length){{ dd.style.display='none'; return; }}
                    let h='';
                    items.forEach(s=>{{
                        const lb=(s.label||'').replace(/'/g,"\\\\'"), un=(s.unit||'').replace(/'/g,"\\\\'");
                        h+='<div class="stock-dd-item" onmousedown="pickStock(this,\\\\''+s.id+'\\\\',\\\\''+lb+'\\\\','+s.price+',\\\\''+un+'\\\\')">'
                          +'<b>'+(s.code||'')+'</b> '+(s.desc||'')+' <span style="float:right;color:#22c55e;">R'+s.price.toFixed(2)+'</span>'
                          +(s.unit?'<span style="color:#888;font-size:11px;margin-left:4px;">'+s.unit+'</span>':'')+'</div>';
                    }});
                    dd.innerHTML=h; dd.style.display='block';
                }});
            }}, 250);
        }}
        function pickStock(el,stockId,label,price,unit){{
            const row=el.closest('tr');
            row.querySelector('input[name="item_desc[]"]').value=label;
            const sid=row.querySelector('input[name="item_stock_id[]"]'); if(sid) sid.value=stockId;
            const p=row.querySelector('input[name="item_price[]"]'); p.value=price;
            const u=row.querySelector('input[name="item_unit[]"]'); if(u&&unit) u.value=unit;
            el.closest('.stock-dropdown').style.display='none'; calcRow(p);
        }}
        document.addEventListener('click',function(e){{
            if(!e.target.closest('.stock-dropdown')&&!e.target.matches('input[name="item_desc[]"]'))
                document.querySelectorAll('.stock-dropdown').forEach(d=>d.style.display='none');
        }});
        
        function addRow() {{
            const tbody = document.getElementById('itemRows');
            const row = document.createElement('tr');
            row.innerHTML = `
                <td style="position:relative;"><input type="text" name="item_desc[]" autocomplete="off" oninput="stockSearch(this)" onfocus="stockSearch(this)" placeholder="Type 2+ chars to search stock..." style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"><input type="hidden" name="item_stock_id[]" value=""><div class="stock-dropdown" style="display:none;"></div></td>
                <td><input type="text" name="item_unit[]" placeholder="ea" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);text-align:center;"></td>
                <td><input type="number" name="item_qty[]" value="1" min="0.01" step="any" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td><input type="number" name="item_price[]" step="0.01" onchange="calcRow(this)" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);"></td>
                <td class="row-total">R0.00</td>
                <td><button type="button" onclick="deleteRow(this)" style="background:var(--red);color:white;border:none;border-radius:4px;padding:6px 10px;cursor:pointer;">✕</button></td>
            `;
            tbody.appendChild(row);
        }}
        
        function deleteRow(btn) {{
            const tbody = document.getElementById('itemRows');
            if (tbody.children.length > 1) {{
                btn.closest('tr').remove();
                calcTotals();
            }} else {{
                alert('Need at least one line item');
            }}
        }}
        
        function calcRow(input) {{
            const row = input.closest('tr');
            const qty = parseFloat(row.querySelector('input[name="item_qty[]"]').value) || 0;
            const price = parseFloat(row.querySelector('input[name="item_price[]"]').value) || 0;
            const total = qty * price;
            row.querySelector('.row-total').textContent = 'R' + total.toFixed(2);
            calcTotals();
        }}
        
        function calcTotals() {{
            let subtotal = 0;
            document.querySelectorAll('.row-total').forEach(cell => {{
                subtotal += parseFloat(cell.textContent.replace('R', '')) || 0;
            }});
            const vat = subtotal * 0.15;
            const total = subtotal + vat;
            document.getElementById('subtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('vat').textContent = 'R' + vat.toFixed(2);
            document.getElementById('total').textContent = 'R' + total.toFixed(2);
        }}
        
        // Calculate totals on page load
        calcTotals();
        </script>
        '''
        
        return render_page(f"Edit Quote {quote.get('quote_number', '')}", content, user, "quotes")
    
    
    @app.route("/api/quote/<quote_id>/status", methods=["POST"])
    @login_required
    def api_quote_status(quote_id):
        """Update quote status"""
        try:
            data = request.get_json()
            new_status = data.get("status", "")
            
            if new_status not in ("draft", "pending", "accepted", "declined", "converted", "invoiced", "expired"):
                return jsonify({"success": False, "error": "Invalid status"})
            
            db.update("quotes", quote_id, {"status": new_status, "updated_at": now()})
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/quote/<quote_id>/email", methods=["POST"])
    @login_required
    def api_quote_email(quote_id):
        """Send quote via email"""
        try:
            data = request.get_json()
            to_email = data.get("to_email", "").strip()
            
            if not to_email or "@" not in to_email:
                return jsonify({"success": False, "error": "Valid email address required"})
            
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            quote = db.get_one("quotes", quote_id)
            if not quote:
                return jsonify({"success": False, "error": "Quote not found"})
            
            # Build email content
            biz_name = business.get("name", "Business") if business else "Business"
            quote_no = quote.get("quote_number", "")
            total = float(quote.get("total", 0))
            date = quote.get("date", today())
            valid_until = quote.get("valid_until", "14 days")
            cust_name = quote.get("customer_name", "Customer")
            status = quote.get("status", "pending")
            
            # Parse items for email
            raw_items = quote.get("items", [])
            if isinstance(raw_items, str):
                try:
                    items = json.loads(raw_items)
                except:
                    items = []
            else:
                items = raw_items if raw_items else []
            
            # Build items table
            items_html = ""
            for item in items:
                qty = item.get("qty") or item.get("quantity") or 1
                desc = item.get("description") or item.get("desc") or "-"
                price = float(item.get("price", 0))
                item_total = float(item.get("total", 0))
                items_html += f'<tr><td style="padding:8px;border-bottom:1px solid #eee;">{safe_string(desc)}</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">{qty}</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">R{price:,.2f}</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">R{item_total:,.2f}</td></tr>'
            
            subtotal = float(quote.get("subtotal", 0))
            vat = float(quote.get("vat", 0))
            
            subject = f"Quotation {quote_no} from {biz_name}"
            
            biz_phone = business.get("phone", "") if business else ""
            biz_email_addr = business.get("email", "") if business else ""
            biz_address = safe_string(business.get("address", "")).replace("\n", "<br>") if business else ""
            biz_vat = business.get("vat_number", "") if business else ""
            salesman = quote.get("salesman_name", "")
            
            body_html = f'''<html><body style="font-family:Arial,sans-serif;font-size:13px;color:#333;">
            <p>Dear {cust_name},</p>
            <p>Thank you for your enquiry. Please find attached our Quotation <strong>{quote_no}</strong> for <strong>R{total:,.2f}</strong>.</p>
            <p>Valid until: {valid_until}</p>
            <p>To accept, please reply to this email or contact us directly.</p>
            <p>We look forward to hearing from you!</p>
            <hr style="border:none;border-top:1px solid #ddd;margin:15px 0 8px;">
            <p style="color:#999;font-size:10px;">{biz_name} | {biz_phone} | {biz_email_addr}<br>Sent via Click AI</p>
            </body></html>'''
            
            body_text = f"Quotation {quote_no} from {biz_name}\n\nDear {cust_name},\n\nPlease find attached our Quotation {quote_no} for R{total:,.2f}.\nValid until: {valid_until}\n\nTo accept, please reply to this email.\n\n{biz_name}"
            
            # Build attachment
            att_items = ""
            for item in items:
                qty = item.get("qty") or item.get("quantity") or 1
                desc = safe_string(item.get("description") or item.get("desc") or "-")
                price = float(item.get("price", 0))
                total_excl = float(item.get("total", 0)) or round(float(qty) * price, 2)
                vat_amt = round(total_excl * 0.15, 2)
                total_incl = round(total_excl + vat_amt, 2)
                att_items += f'<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:5px 8px;font-size:11px;">{desc}</td><td style="text-align:center;padding:5px 8px;font-size:11px;">{qty}</td><td style="text-align:right;padding:5px 8px;font-size:11px;">R{price:,.2f}</td><td style="text-align:right;padding:5px 8px;font-size:11px;">R{total_excl:,.2f}</td><td style="text-align:right;padding:5px 8px;font-size:11px;font-weight:600;">R{total_incl:,.2f}</td></tr>'
            
            attachment_html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Quotation {quote_no}</title>
            <style>body{{font-family:Arial,sans-serif;margin:0;padding:0;color:#333;font-size:12px;}}table{{width:100%;border-collapse:collapse;}}@media print{{@page{{margin:10mm 12mm;}}}}</style>
            </head><body>
            <div style="background:#1e3a5f;color:white;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;">
                <div><div style="font-size:16px;font-weight:700;">{biz_name}</div>{f'<div style="font-size:10px;opacity:0.8;">{biz_address}</div>' if biz_address else ''}</div>
                <div style="text-align:right;"><div style="font-size:20px;font-weight:700;letter-spacing:2px;">QUOTATION</div></div>
            </div>
            <div style="padding:10px 25px;display:flex;gap:40px;border-bottom:1px solid #e5e7eb;">
                <div style="flex:1;">
                    <table style="font-size:11px;width:auto;"><tr><td style="padding:3px 0;color:#888;width:100px;">Quote #:</td><td style="font-weight:600;">{quote_no}</td></tr><tr><td style="padding:3px 0;color:#888;">Date:</td><td>{date}</td></tr><tr><td style="padding:3px 0;color:#888;">Valid Until:</td><td>{valid_until}</td></tr>{f'<tr><td style="padding:3px 0;color:#888;">Salesman:</td><td>{salesman}</td></tr>' if salesman else ''}</table>
                    {f'<div style="margin-top:6px;font-size:10px;color:#666;">Tel: {biz_phone}</div>' if biz_phone else ''}
                </div>
                <div style="flex:1;">
                    <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-weight:600;">Quote To</div>
                    <div style="font-size:13px;font-weight:700;">{safe_string(cust_name)}</div>
                </div>
            </div>
            <div style="padding:0 25px;"><table>
                <thead><tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">
                    <th style="padding:5px 8px;text-align:left;color:#475569;font-size:10px;text-transform:uppercase;">Description</th>
                    <th style="padding:5px 8px;text-align:center;color:#475569;font-size:10px;text-transform:uppercase;width:50px;">Qty</th>
                    <th style="padding:5px 8px;text-align:right;color:#475569;font-size:10px;text-transform:uppercase;">Price</th>
                    <th style="padding:5px 8px;text-align:right;color:#475569;font-size:10px;text-transform:uppercase;">Excl</th>
                    <th style="padding:5px 8px;text-align:right;color:#475569;font-size:10px;text-transform:uppercase;">Incl</th>
                </tr></thead><tbody>{att_items}</tbody>
            </table></div>
            <div style="padding:15px 25px;text-align:right;">
                <table style="width:200px;margin-left:auto;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:4px 8px;color:#666;font-size:11px;">Subtotal</td><td style="padding:4px 8px;text-align:right;font-size:11px;">R{subtotal:,.2f}</td></tr><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:4px 8px;color:#666;font-size:11px;">VAT (15%)</td><td style="padding:4px 8px;text-align:right;font-size:11px;">R{vat:,.2f}</td></tr><tr style="background:#1e3a5f;"><td style="padding:8px;color:white;font-size:13px;font-weight:700;">TOTAL</td><td style="padding:8px;text-align:right;color:white;font-size:13px;font-weight:700;">R{total:,.2f}</td></tr></table>
            </div>
            </body></html>'''
            
            quote_attachment = {
                'filename': f'{quote_no}.html',
                'content': attachment_html,
                'content_type': 'text/html'
            }
            
            # Send email
            success = Email.send(to_email, subject, body_html, body_text, business=business, attachments=[quote_attachment])
            
            if success:
                logger.info(f"[EMAIL] Quote {quote_no} sent to {to_email}")
                return jsonify({"success": True, "message": f"Quote sent to {to_email}"})
            else:
                return jsonify({"success": False, "error": "Failed to send email. Check SMTP settings in Settings page."})
            
        except Exception as e:
            logger.error(f"[EMAIL] Error sending quote: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/quote/<quote_id>/convert-to-invoice", methods=["POST"])
    @login_required
    def quote_to_invoice(quote_id):
        """Convert accepted quote to invoice"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        quote = db.get_one("quotes", quote_id)
        if not quote:
            return redirect("/quotes?error=Quote+not+found")
        
        # Generate invoice number
        existing = db.get("invoices", {"business_id": biz_id}) or []
        inv_num = next_document_number("INV-", existing, "invoice_number")
        
        # Parse quote items
        quote_items = quote.get("items", [])
        if isinstance(quote_items, str):
            try:
                quote_items = json.loads(quote_items)
            except:
                quote_items = []
        
        invoice = RecordFactory.invoice(
            business_id=biz_id,
            customer_id=quote.get("customer_id", ""),
            customer_name=quote.get("customer_name", ""),
            items=quote_items,
            invoice_number=inv_num,
            date=today(),
            due_date=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            subtotal=quote.get("subtotal", 0),
            vat=quote.get("vat", 0),
            total=quote.get("total", 0),
            status="outstanding",
            source_quote_id=quote_id,
            source_quote_number=quote.get("quote_number"),
            created_by=user.get("id", "") if user else "",
            created_by_name=quote.get("created_by_name", ""),
            salesman=quote.get("salesman", ""),
            salesman_name=quote.get("salesman_name", ""),
            sales_rep=quote.get("salesman_name", "")
        )
        invoice_id = invoice["id"]
        
        success, result = db.save("invoices", invoice)
        
        if success:
            # === DEDUCT STOCK ===
            try:
                items_list = json.loads(quote.get("items", "[]"))
                all_stock = db.get_all_stock(biz_id)
                stock_by_code = {s.get("code", "").upper(): s for s in all_stock if s.get("code")}
                
                for item in items_list:
                    code = (item.get("code") or "").upper()
                    stock_id = item.get("stock_id")
                    stock_item = None
                    
                    # Find by stock_id first, then by code
                    if stock_id:
                        stock_item = db.get_one_stock(stock_id)
                    elif code and code in stock_by_code:
                        stock_item = stock_by_code[code]
                    
                    if stock_item:
                        current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                        sold_qty = float(item.get("qty") or item.get("quantity") or 1)
                        new_qty = current_qty - sold_qty
                        db.update_stock(stock_item.get("id"), {"qty": new_qty, "quantity": new_qty}, biz_id)
                        logger.info(f"[QUOTE->INV ROUTE] Stock {code or stock_id}: {current_qty} - {sold_qty} = {new_qty}")
            except Exception as e:
                logger.error(f"[QUOTE->INV ROUTE] Stock deduction error: {e}")
            
            # Create journal entries for GL
            # Debit Debtors (1200), Credit Sales (4000) + VAT Output (2100)
            total = float(quote.get("total", 0))
            subtotal = float(quote.get("subtotal", 0))
            vat = float(quote.get("vat", 0))
            customer_name = quote.get("customer_name", "")
            
            create_journal_entry(
                biz_id,
                today(),
                f"Invoice {inv_num} (from Quote) - {customer_name}",
                inv_num,
                [
                    {"account_code": gl(biz_id, "debtors"), "debit": total, "credit": 0},      # Debtors
                    {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": subtotal},   # Sales
                    {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": vat},        # VAT Output
                ]
            )
            
            # Mark quote as converted
            db.update("quotes", quote_id, {"status": "converted", "converted_invoice_id": invoice_id})
            
            # Update customer balance
            customer_id = quote.get("customer_id")
            if customer_id:
                customer = db.get_one("customers", customer_id)
                if customer:
                    new_balance = float(customer.get("balance", 0)) + float(quote.get("total", 0))
                    db.update("customers", customer_id, {"balance": new_balance})
            
            return redirect(f"/invoice/{invoice_id}?success=Created+from+quote")
        
        return redirect(f"/quote/{quote_id}?error=Failed+to+create+invoice")
    
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # DELIVERY NOTES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    @app.route("/delivery-notes")
    @login_required
    def delivery_notes_list():
        """Delivery notes list"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        notes = db.get("delivery_notes", {"business_id": biz_id}) if biz_id else []
        notes = sorted(notes, key=lambda x: x.get("created_at", ""), reverse=True)
        
        rows = ""
        for dn in notes[:500]:
            status_color = {"draft": "orange", "delivered": "green", "cancelled": "red"}.get(dn.get("status", "draft"), "gray")
            rows += f'''
            <tr onclick="window.location='/delivery-note/{dn.get("id")}'" style="cursor:pointer;">
                <td><strong>{safe_string(dn.get("delivery_note_number", "-"))}</strong></td>
                <td>{dn.get("date", "-")}</td>
                <td>{safe_string(dn.get("customer_name", "-"))}</td>
                <td>{safe_string(dn.get("source_invoice_number", "-"))}</td>
                <td><span style="color:{status_color};">●</span> {dn.get("status", "draft").title()}</td>
            </tr>
            '''
        
        if not rows:
            rows = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:40px;">No delivery notes yet</td></tr>'
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <h2>Delivery Notes</h2>
            <a href="/delivery-note/new" class="btn btn-primary">+ New Delivery Note</a>
        </div>
        
        <div class="card" style="padding:0;overflow:hidden;">
            <div style="padding:15px 15px 0 15px;">
                <input type="text" id="searchDN" placeholder="🔍 Search by customer, DN number, invoice..." oninput="filterTable('searchDN','dnTable')" style="width:100%;padding:10px 15px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;">
            </div>
            <table class="data-table" id="dnTable">
                <thead>
                    <tr>
                        <th>Number</th>
                        <th>Date</th>
                        <th>Customer</th>
                        <th>Invoice</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        '''
        
        return render_page("Delivery Notes", content, user, "delivery-notes")
    
    
    @app.route("/delivery-note/new", methods=["GET", "POST"])
    @login_required
    def delivery_note_new():
        """Create new GRN (goods received note)"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            customer_id = request.form.get("customer_id", "")
            customer_name = request.form.get("customer_name", "")
            source_invoice_id = request.form.get("source_invoice_id", "")
            delivery_address = request.form.get("delivery_address", "")
            notes = request.form.get("notes", "")
            reduce_stock = request.form.get("reduce_stock") == "1"
            
            # Get line items
            items = []
            descriptions = request.form.getlist("item_desc[]")
            quantities = request.form.getlist("item_qty[]")
            stock_ids = request.form.getlist("item_stock_id[]")
            
            for i, desc in enumerate(descriptions):
                if desc.strip():
                    qty = float(quantities[i] or "1")
                    items.append({
                        "description": desc,
                        "quantity": qty,
                        "stock_id": stock_ids[i] if i < len(stock_ids) else None
                    })
            
            if not items:
                return redirect("/delivery-note/new?error=No+items")
            
            # Generate DN number
            existing = db.get("delivery_notes", {"business_id": biz_id}) or []
            dn_num = next_document_number("DN-", existing, "delivery_note_number")
            
            # Get source invoice info
            source_inv_number = ""
            if source_invoice_id:
                inv = db.get_one("invoices", source_invoice_id)
                if inv:
                    source_inv_number = inv.get("invoice_number", "")
                    if not customer_name:
                        customer_name = inv.get("customer_name", "")
                        customer_id = inv.get("customer_id", "")
            
            dn_id = generate_id()
            delivery_note = {
                "id": dn_id,
                "business_id": biz_id,
                "delivery_note_number": dn_num,
                "date": today(),
                "customer_id": customer_id or None,
                "customer_name": customer_name,
                "source_invoice_id": source_invoice_id or None,
                "source_invoice_number": source_inv_number,
                "delivery_address": delivery_address,
                "items": json.dumps(items),
                "notes": notes,
                "status": "draft",
                "created_at": now()
            }
            
            success, _ = db.save("delivery_notes", delivery_note)
            
            if success:
                # Update source invoice status to "delivered"
                if source_invoice_id:
                    db.update("invoices", source_invoice_id, {"status": "delivered"})
                
                # Reduce stock if requested (allow negative)
                if reduce_stock:
                    for item in items:
                        stock_id = item.get("stock_id")
                        if stock_id:
                            stock_item = db.get_one_stock(stock_id)
                            if stock_item:
                                current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                                sold_qty = float(item.get("quantity", 0))
                                new_qty = current_qty - sold_qty
                                # Allow negative stock - use update with biz_id
                                db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
                                logger.info(f"[GRN] Stock {stock_id}: {current_qty} - {sold_qty} = {new_qty}")
                                # Log stock movement
                                try:
                                    db.save("stock_movements", RecordFactory.stock_movement(
                                        business_id=biz_id, stock_id=stock_id, movement_type="out",
                                        quantity=sold_qty, reference=f"GRN {dn_num}"
                                    ))
                                except Exception as sm_err: logger.error(f"[STOCK MOVEMENT] Save failed: {sm_err}")
                
                return redirect(f"/delivery-note/{dn_id}")
            
            return redirect("/delivery-note/new?error=Failed+to+save")
        
        # GET - show form
        source_invoice_id = request.args.get("invoice_id", "")
        source_invoice = None
        prefill_items = []
        prefill_customer = ""
        
        if source_invoice_id:
            source_invoice = db.get_one("invoices", source_invoice_id)
            if source_invoice:
                prefill_customer = source_invoice.get("customer_name", "")
                try:
                    inv_items = json.loads(source_invoice.get("items", "[]"))
                    prefill_items = inv_items
                except:
                    pass
        
        customers = db.get("customers", {"business_id": biz_id}) if biz_id else []
        invoices = db.get("invoices", {"business_id": biz_id, "status": "outstanding"}) if biz_id else []
        stock = db.get_all_stock(biz_id)
        
        customer_options = '<option value="">-- Select Customer --</option>'
        for c in sorted(customers, key=lambda x: x.get("name", "")):
            selected = "selected" if prefill_customer and c.get("name") == prefill_customer else ""
            customer_options += f'<option value="{c.get("id")}" data-name="{safe_string(c.get("name", ""))}" {selected}>{safe_string(c.get("name", ""))}</option>'
        
        invoice_options = '<option value="">-- No linked invoice --</option>'
        for inv in sorted(invoices, key=lambda x: x.get("invoice_number", ""), reverse=True):
            selected = "selected" if inv.get("id") == source_invoice_id else ""
            invoice_options += f'<option value="{inv.get("id")}" {selected}>{inv.get("invoice_number")} - {safe_string(inv.get("customer_name", ""))}</option>'
        
        stock_options = ""
        for s in stock:
            stock_options += f'<option value="{s.get("id")}" data-desc="{safe_string(s.get("description",""))}">{safe_string(s.get("description",""))} (Qty: {s.get("quantity",0)})</option>'
        
        # Build prefill items HTML
        items_html = ""
        if prefill_items:
            for idx, item in enumerate(prefill_items):
                items_html += f'''
                <div class="line-item" style="display:grid;grid-template-columns:3fr 1fr 1fr auto;gap:10px;margin-bottom:10px;align-items:end;">
                    <div>
                        <label>Description</label>
                        <input type="text" name="item_desc[]" class="form-input" value="{safe_string(item.get('description',''))}">
                    </div>
                    <div>
                        <label>Qty</label>
                        <input type="number" name="item_qty[]" class="form-input" value="{item.get('quantity',1)}" step="0.01">
                    </div>
                    <div>
                        <label>Stock Item</label>
                        <select name="item_stock_id[]" class="form-input">
                            <option value="">-- Select --</option>
                            {stock_options}
                        </select>
                    </div>
                    <button type="button" onclick="this.parentElement.remove()" style="background:var(--red);color:white;border:none;padding:10px;border-radius:6px;cursor:pointer;">✕</button>
                </div>
                '''
        else:
            items_html = f'''
            <div class="line-item" style="display:grid;grid-template-columns:3fr 1fr 1fr auto;gap:10px;margin-bottom:10px;align-items:end;">
                <div>
                    <label>Description</label>
                    <input type="text" name="item_desc[]" class="form-input" placeholder="Item description">
                </div>
                <div>
                    <label>Qty</label>
                    <input type="number" name="item_qty[]" class="form-input" value="1" step="0.01">
                </div>
                <div>
                    <label>Stock Item</label>
                    <select name="item_stock_id[]" class="form-input">
                        <option value="">-- Select --</option>
                        {stock_options}
                    </select>
                </div>
                <button type="button" onclick="this.parentElement.remove()" style="background:var(--red);color:white;border:none;padding:10px;border-radius:6px;cursor:pointer;">✕</button>
            </div>
            '''
        
        error_msg = request.args.get("error", "")
        error_html = f'<div style="background:var(--red);color:white;padding:10px;border-radius:8px;margin-bottom:15px;">{error_msg}</div>' if error_msg else ""
        
        content = f'''
        {error_html}
        <div class="card">
            <h3 style="margin:0 0 20px 0;">New Delivery Note</h3>
            
            <form method="POST" id="dnForm">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label>Customer</label>
                        <select name="customer_id" id="customerSelect" class="form-input" onchange="document.getElementById('customerName').value=this.options[this.selectedIndex].dataset.name||''">
                            {customer_options}
                        </select>
                        <input type="hidden" name="customer_name" id="customerName" value="{safe_string(prefill_customer)}">
                    </div>
                    <div>
                        <label>Link to Invoice (optional)</label>
                        <select name="source_invoice_id" class="form-input">
                            {invoice_options}
                        </select>
                    </div>
                </div>
                
                <div style="margin-bottom:20px;">
                    <label>Delivery Address</label>
                    <textarea name="delivery_address" class="form-input" rows="2" placeholder="Delivery address..."></textarea>
                </div>
                
                <h4 style="margin:20px 0 10px 0;">Items</h4>
                <div id="itemsContainer">
                    {items_html}
                </div>
                
                <button type="button" onclick="addLine()" class="btn btn-secondary" style="margin-bottom:20px;">+ Add Line</button>
                
                <div style="margin-bottom:20px;">
                    <label>Notes</label>
                    <textarea name="notes" class="form-input" rows="2" placeholder="Delivery notes..."></textarea>
                </div>
                
                <div style="margin-bottom:20px;">
                    <label style="display:flex;align-items:center;gap:10px;cursor:pointer;">
                        <input type="checkbox" name="reduce_stock" value="1" checked>
                        <span>Reduce stock quantities (allows negative stock)</span>
                    </label>
                </div>
                
                <button type="submit" class="btn btn-primary" style="padding:12px 30px;">Create Delivery Note</button>
            </form>
        </div>
        
        <script>
        const stockOptions = `<option value="">-- Select --</option>{stock_options}`;
        
        function addLine() {{
            const container = document.getElementById('itemsContainer');
            const div = document.createElement('div');
            div.className = 'line-item';
            div.style = 'display:grid;grid-template-columns:3fr 1fr 1fr auto;gap:10px;margin-bottom:10px;align-items:end;';
            div.innerHTML = `
                <div>
                    <label>Description</label>
                    <input type="text" name="item_desc[]" class="form-input" placeholder="Item description">
                </div>
                <div>
                    <label>Qty</label>
                    <input type="number" name="item_qty[]" class="form-input" value="1" step="0.01">
                </div>
                <div>
                    <label>Stock Item</label>
                    <select name="item_stock_id[]" class="form-input">
                        ${{stockOptions}}
                    </select>
                </div>
                <button type="button" onclick="this.parentElement.remove()" style="background:var(--red);color:white;border:none;padding:10px;border-radius:6px;cursor:pointer;">✕</button>
            `;
            container.appendChild(div);
        }}
        </script>
        '''
        
        return render_page("New Delivery Note", content, user, "delivery-notes")
    
    
    @app.route("/delivery-note/<dn_id>")
    @login_required
    def delivery_note_view(dn_id):
        """View delivery note"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        
        dn = db.get_one("delivery_notes", dn_id)
        if not dn:
            return redirect("/delivery-notes?error=Not+found")
        
        # Parse items
        try:
            items = json.loads(dn.get("items", "[]"))
        except:
            items = []
        
        items_html = ""
        for item in items:
            items_html += f'''
            <tr style="border-bottom:1px solid #e5e7eb;">
                <td style="padding:4px 6px;font-size:11px;">{safe_string(item.get("description", "-"))}</td>
                <td style="text-align:center;padding:4px 6px;font-size:11px;font-weight:600;">{item.get("quantity", 1)}</td>
            </tr>
            '''
        
        status = dn.get("status", "draft")
        status_color = {"draft": "orange", "delivered": "green", "cancelled": "red"}.get(status, "gray")
        
        # Action buttons
        actions = ""
        if status == "draft":
            actions = f'''
            <button onclick="updateStatus('delivered')" class="btn btn-primary">GOOD: Mark as Delivered</button>
            <button onclick="updateStatus('cancelled')" class="btn btn-secondary">✕ Cancel</button>
            '''
        
        # Link to invoice
        invoice_link = ""
        if dn.get("source_invoice_id"):
            invoice_link = f'<a href="/invoice/{dn.get("source_invoice_id")}" style="color:var(--primary);">{dn.get("source_invoice_number", "View Invoice")}</a>'
        
        biz_name = business.get("name", "Business") if business else "Business"
        biz_address = safe_string(business.get("address", "")).replace("\n", "<br>") if business else ""
        biz_phone = business.get("phone", "") if business else ""
        
        content = f'''
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/delivery-notes" style="color:var(--text-muted);">← Back to Delivery Notes</a>
            <div style="display:flex;gap:10px;">
                {actions}
                <button onclick="window.print()" class="btn btn-secondary">🖨️ Print</button>
            </div>
        </div>
        
        <div class="card" style="background:white;color:#333;padding:0;overflow:hidden;">
            <!-- TOP BAR -->
            <div style="background:#7c3aed;color:white;padding:25px 40px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <h1 style="margin:0;font-size:28px;font-weight:700;">{biz_name}</h1>
                    {f'<p style="margin:4px 0 0 0;font-size:13px;opacity:0.8;">{biz_address}</p>' if biz_address else ''}
                </div>
                <div style="text-align:right;">
                    <h2 style="margin:0;font-size:32px;font-weight:700;letter-spacing:2px;">DELIVERY NOTE</h2>
                    <span style="background:rgba(255,255,255,0.2);color:white;padding:4px 12px;border-radius:20px;font-size:12px;">
                        {status.upper()}
                    </span>
                </div>
            </div>
            
            <!-- DETAILS GRID -->
            <div style="padding:10px 25px;display:grid;grid-template-columns:1fr 1fr;gap:0;border-bottom:1px solid #e5e7eb;">
                <div style="border-right:1px solid #e5e7eb;padding-right:25px;">
                    <table style="width:100%;font-size:14px;color:#333;">
                        <tr><td style="padding:4px 0;color:#888;width:130px;">DN Number:</td><td style="padding:4px 0;font-weight:600;">{dn.get("delivery_note_number", "-")}</td></tr>
                        <tr><td style="padding:4px 0;color:#888;">Date:</td><td style="padding:4px 0;">{dn.get("date", "-")}</td></tr>
                        <tr><td style="padding:4px 0;color:#888;">Invoice:</td><td style="padding:4px 0;">{invoice_link or "-"}</td></tr>
                    </table>
                    {f'<div style="margin-top:8px;font-size:13px;color:#666;">Tel: {biz_phone}</div>' if biz_phone else ''}
                </div>
                <div style="padding-left:25px;">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;font-weight:600;">Deliver To</div>
                    <div style="font-size:16px;font-weight:700;color:#7c3aed;margin-bottom:4px;">{safe_string(dn.get("customer_name", "-"))}</div>
                    {f'<div style="font-size:10px;color:#555;">{safe_string(dn.get("delivery_address", ""))}</div>' if dn.get("delivery_address") else ''}
                </div>
            </div>
            
            <!-- ITEMS TABLE -->
            <div style="padding:0 25px;">
                <table style="width:100%;border-collapse:collapse;font-size:14px;">
                    <thead>
                        <tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">
                            <th style="padding:5px 6px;text-align:left;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;">Description</th>
                            <th style="padding:5px 6px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Quantity</th>
                        </tr>
                    </thead>
                    <tbody style="color:#333;">
                        {items_html}
                    </tbody>
                </table>
            </div>
            
            <!-- FOOTER -->
            <div style="padding:10px 25px;display:grid;grid-template-columns:1fr 1fr;gap:40px;border-top:1px solid #e5e7eb;margin-top:20px;">
                <div>
                    <div style="font-size:12px;color:#888;text-transform:uppercase;margin-bottom:8px;">Received By (Name & Signature)</div>
                    <div style="border-bottom:1px solid #ccc;height:40px;"></div>
                </div>
                <div>
                    <div style="font-size:12px;color:#888;text-transform:uppercase;margin-bottom:8px;">Date Received</div>
                    <div style="border-bottom:1px solid #ccc;height:40px;"></div>
                </div>
            </div>
            
            {"<div style='padding:0 25px 20px;'><div style='padding:12px;background:#fafafa;border-radius:6px;font-size:13px;color:#666;'><strong>Notes:</strong> " + safe_string(dn.get('notes','')) + "</div></div>" if dn.get('notes') else ""}
        </div>
        
        <script>
        async function updateStatus(status) {{
            if (!confirm('Update status to ' + status + '?')) return;
            
            const response = await fetch('/api/delivery-note/{dn_id}/status', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{status: status}})
            }});
            
            if (response.ok) {{
                location.reload();
            }} else {{
                alert('Failed to update status');
            }}
        }}
        </script>
        '''
        
        return render_page(f"Delivery Note {dn.get('delivery_note_number', '')}", content, user, "delivery-notes")
    
    
    @app.route("/api/delivery-note/<dn_id>/status", methods=["POST"])
    @login_required
    def api_delivery_note_status(dn_id):
        """Update delivery note status"""
        try:
            data = request.get_json()
            new_status = data.get("status", "")
            
            if new_status not in ("draft", "delivered", "cancelled"):
                return jsonify({"success": False, "error": "Invalid status"})
            
            db.update("delivery_notes", dn_id, {"status": new_status})
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/invoice/<invoice_id>/create-delivery-note")
    @login_required
    def invoice_to_delivery_note(invoice_id):
        """Create delivery note directly from invoice data — no form needed"""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        invoice = db.get_one("invoices", invoice_id)
        if not invoice:
            return redirect("/invoices?error=Invoice+not+found")
        
        # Get items from the invoice (handle both JSON string and list)
        raw_items = invoice.get("items", [])
        if isinstance(raw_items, str):
            try:
                inv_items = json.loads(raw_items)
            except:
                inv_items = []
        else:
            inv_items = raw_items if raw_items else []
        
        if not inv_items:
            return redirect(f"/invoice/{invoice_id}?error=Invoice+has+no+items")
        
        # Build DN items from invoice items (description + quantity only, no pricing on DN)
        dn_items = []
        for item in inv_items:
            desc = item.get("description") or item.get("desc") or "-"
            qty = item.get("quantity") or item.get("qty") or 1
            dn_items.append({
                "description": desc,
                "quantity": float(qty),
                "stock_id": item.get("stock_id")
            })
        
        # Generate DN number
        existing = db.get("delivery_notes", {"business_id": biz_id}) or []
        dn_num = next_document_number("DN-", existing, "delivery_note_number")
        
        dn_id = generate_id()
        delivery_note = {
            "id": dn_id,
            "business_id": biz_id,
            "delivery_note_number": dn_num,
            "date": today(),
            "customer_id": invoice.get("customer_id") or None,
            "customer_name": invoice.get("customer_name", ""),
            "source_invoice_id": invoice_id,
            "source_invoice_number": invoice.get("invoice_number", ""),
            "delivery_address": "",
            "items": json.dumps(dn_items),
            "notes": "",
            "status": "draft",
            "created_at": now(),
            "created_by": user.get("email", "") if user else ""
        }
        
        success, _ = db.save("delivery_notes", delivery_note)
        
        if success:
            # Update invoice status
            db.update("invoices", invoice_id, {"status": "delivered"})
            
            # Reduce stock for each item that has a stock_id
            for item in dn_items:
                stock_id = item.get("stock_id")
                if stock_id:
                    try:
                        stock_item = db.get_one_stock(stock_id)
                        if stock_item:
                            current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                            sold_qty = float(item.get("quantity", 0))
                            new_qty = current_qty - sold_qty
                            db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
                            logger.info(f"[DN] Stock {stock_id}: {current_qty} - {sold_qty} = {new_qty}")
                            try:
                                db.save("stock_movements", RecordFactory.stock_movement(
                                    business_id=biz_id, stock_id=stock_id, movement_type="out",
                                    quantity=sold_qty, reference=f"DN {dn_num}"
                                ))
                            except Exception as sm_err:
                                logger.error(f"[STOCK MOVEMENT] Save failed: {sm_err}")
                    except Exception as e:
                        logger.error(f"[DN] Stock reduce error for {stock_id}: {e}")
            
            return redirect(f"/delivery-note/{dn_id}")
        
        return redirect(f"/invoice/{invoice_id}?error=Failed+to+create+delivery+note")

    logger.info("[INVOICING] All invoicing routes registered ✓")
