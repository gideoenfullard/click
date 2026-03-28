# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - POS & BAR ROUTES MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: POS page, POS history, POS API endpoints, Bar/Restaurant POS,
#           POS settings
# ==============================================================================

import json
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)

# SA VAT rate constant (same as in clickai.py)
VAT_RATE = Decimal("0.15")


def register_pos_routes(app, db, login_required, Auth, render_page,
                        generate_id, money, safe_string, safe_uuid,
                        next_document_number, get_user_role, get_zane_chat,
                        RecordFactory, CSS, now, today, extract_time,
                        create_journal_entry, log_allocation, gl,
                        AuditLog, Email):
    """Register all POS and Bar routes with the Flask app."""

    @app.route("/pos")
    @login_required
    def pos_page():
        """POS - Stylish List Layout with Smart Search"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        _pos_theme = request.cookies.get("clickai_theme", "midnight")
        
        # Get stock, customers, suppliers IN PARALLEL (was sequential — each takes 0.5-2s)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            f_stock = pool.submit(db.get_all_stock, biz_id)
            f_customers = pool.submit(db.get, "customers", {"business_id": biz_id}) if biz_id else None
            f_suppliers = pool.submit(db.get, "suppliers", {"business_id": biz_id}) if biz_id else None
            f_cashiers = pool.submit(db.get_business_users, biz_id) if biz_id else None
        
        stock = f_stock.result(timeout=15) or []
        customers = f_customers.result(timeout=15) if f_customers else []
        customers = customers or []
        suppliers = f_suppliers.result(timeout=15) if f_suppliers else []
        suppliers = suppliers or []
        try:
            cashier_list = f_cashiers.result(timeout=15) if f_cashiers else []
            cashier_list = cashier_list or []
        except Exception:
            cashier_list = []
        
        # Sort stock by category then code
        stock = sorted(stock, key=lambda x: (x.get("category") or "ZZZ", x.get("code") or ""))
        
        # Build stock rows for the table (only first 100 visible for fast render)
        stock_rows = ""
        total_stock_count = len(stock)
        for row_idx, item in enumerate(stock):
            code = safe_string(item.get("code", ""))
            desc = safe_string(item.get("description", ""))
            price = float(item.get("price") or item.get("selling_price") or 0)
            qty = float(item.get("qty") or item.get("quantity") or 0)
            category = safe_string(item.get("category", ""))
            
            # Stock status styling
            stock_class = ""
            stock_badge = ""
            if qty < 0:
                stock_class = "negative"
                stock_badge = f'<span class="stock-badge negative">{qty:.0f}</span>'
            elif qty == 0:
                stock_class = "zero"
                stock_badge = f'<span class="stock-badge zero">0</span>'
            elif qty < 5:
                stock_class = "low"
                stock_badge = f'<span class="stock-badge low">{qty:.0f}</span>'
            else:
                stock_badge = f'<span class="stock-badge">{qty:.0f}</span>'
            
            row_hidden = ' style="display:none"' if row_idx >= 100 else ''
            stock_rows += f'''
            <tr class="stock-row {stock_class}"{row_hidden}
                data-id="{item.get("id")}"
                data-code="{code}"
                data-desc="{desc}"
                data-price="{price}"
                data-qty="{qty}"
                data-search="{code.lower()} {desc.lower()}"
                onclick="addToCart('{item.get("id")}', '{code}', '{desc}', {price}, {qty})">
                <td class="col-code">{code}</td>
                <td class="col-desc">{desc}</td>
                <td class="col-price">R{price:,.2f}</td>
                <td class="col-stock">{stock_badge}</td>
                <td class="col-action">
                    <button class="qty-btn" onclick="addBulkToCart(event, '{item.get("id")}', '{code}', '{desc}', {price}, {qty})" title="Enter quantity">QTY</button>
                </td>
            </tr>
            '''
        
        # Customer options - sorted alphabetically
        customer_options = '<option value="">-- Countersale --</option>'
        customer_options += '<option value="NEW" style="color:#10b981;">+ Add New</option>'
        for c in sorted(customers, key=lambda x: (x.get("name") or "").lower()):
            customer_options += f'<option value="{c.get("id")}" data-name="{safe_string(c.get("name"))}">{safe_string(c.get("name"))}</option>'
        
        # Supplier options - sorted alphabetically
        supplier_options = '<option value="">-- Select Supplier --</option>'
        supplier_options += '<option value="NEW" style="color:#10b981;">+ Add New</option>'
        for s in sorted(suppliers, key=lambda x: (x.get("name") or "").lower()):
            supplier_options += f'<option value="{s.get("id")}" data-name="{safe_string(s.get("name"))}">{safe_string(s.get("name"))}</option>'
        
        # JSON data for searchable dropdown
        import json
        customer_list = [{"id": "", "name": "Countersale"}] + [{"id": "NEW", "name": "+ Add New"}]
        customer_list += [{"id": c.get("id"), "name": c.get("name", ""), "address": c.get("address", ""), "phone": c.get("phone", "") or c.get("cell", ""), "vat_number": c.get("vat_number", ""), "email": c.get("email", "")} for c in sorted(customers, key=lambda x: (x.get("name") or "").lower())]
        supplier_list = [{"id": "", "name": "Select Supplier"}] + [{"id": "NEW", "name": "+ Add New"}]
        supplier_list += [{"id": s.get("id"), "name": s.get("name", "")} for s in sorted(suppliers, key=lambda x: (x.get("name") or "").lower())]
        customer_json = json.dumps(customer_list).replace("'", "&#39;")
        supplier_json = json.dumps(supplier_list).replace("'", "&#39;")
        
        # POS print settings
        pos_settings = {
            "auto_print": business.get("pos_auto_print", False) if business else False,
            "print_duplicates": True,  # Always print 2 copies
            "print_format": business.get("pos_print_format", "ask") if business else "ask",
            "slip_footer": business.get("pos_slip_footer", "Thank you for your purchase!") if business else "Thank you for your purchase!",
            "business_name": (business.get("name") or business.get("business_name") or "Business") if business else "Business",
            "vat_number": business.get("vat_number", "") if business else "",
            "phone": business.get("phone", "") if business else "",
            "address": business.get("address", "") if business else "",
            "email": business.get("email", "") if business else "",
            "bank_name": business.get("bank_name", "") if business else "",
            "bank_account": business.get("bank_account", "") if business else "",
            "bank_branch": business.get("bank_branch", "") if business else ""
        }
        pos_settings_json = json.dumps(pos_settings).replace("'", "&#39;")
        
        # cashier_list already loaded in parallel above
        current_user_id = user.get("id", "") if user else ""
        current_user_name = user.get("name", user.get("email", "Me")) if user else "Me"
        # Extract first name
        if current_user_name and " " in current_user_name:
            current_user_name = current_user_name.split()[0]
        
        cashier_buttons = ""
        for cu in cashier_list:
            cu_id = cu.get("id") or ""
            cu_name = str(cu.get("name") or cu.get("email") or "Staff").replace("'", "").replace('"', "").replace("&", "")
            if " " in cu_name:
                cu_name = cu_name.split()[0]
            cu_name = cu_name[:12]
            is_active = "active" if cu_id == current_user_id else ""
            cashier_buttons += f'<button class="cashier-btn {is_active}" data-uid="{cu_id}" onclick="switchCashier(this, &apos;{cu_id}&apos;, &apos;{cu_name}&apos;)">{cu_name}</button>'
        
        # Salesman options for POS quote modal
        pos_salesman_options = f'<option value="{current_user_id}" data-name="{current_user_name}">{current_user_name} (me)</option>'
        _pos_seen_ids = {current_user_id}
        for cu in cashier_list:
            cu_id = cu.get("id") or ""
            if cu_id and cu_id not in _pos_seen_ids:
                _pos_seen_ids.add(cu_id)
                cu_name = str(cu.get("name") or cu.get("email") or "Staff").replace("'", "").replace('"', "").replace("&", "")
                if " " in cu_name:
                    cu_name = cu_name.split()[0]
                cu_name = cu_name[:12]
                pos_salesman_options += f'<option value="{cu_id}" data-name="{cu_name}">{cu_name}</option>'
        
        pos_css = '''
        <style>
        :root {
            --pos-bg: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #0f0f1a 100%);
            --pos-card: rgba(30, 30, 50, 0.95);
            --pos-glow: rgba(99, 102, 241, 0.3);
            --pos-green: #10b981;
            --pos-red: #ef4444;
            --pos-orange: #f59e0b;
            --pos-blue: #3b82f6;
        }
        
        body {
            background: var(--pos-bg);
            overflow: hidden;
        }
        
        /* ═══ CASHIER BAR ═══ */
        .cashier-bar {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 20px;
            background: rgba(20, 20, 40, 0.9);
            border-bottom: 1px solid rgba(99, 102, 241, 0.2);
        }
        .cashier-bar label {
            color: var(--text-muted, #888);
            font-size: 12px;
            font-weight: bold;
            white-space: nowrap;
        }
        .cashier-btn {
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid rgba(255,255,255,0.15);
            background: rgba(255,255,255,0.05);
            color: #aaa;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .cashier-btn:hover {
            background: rgba(99, 102, 241, 0.2);
            color: white;
        }
        .cashier-btn.active {
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: white;
            border-color: #8b5cf6;
            font-weight: bold;
            box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
        }
        
        /* ═══ MAIN LAYOUT ═══ */
        .pos-container {
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
            height: 100%;
            min-height: 0;
            padding: 0 20px;
        }
        .pos-cart {
            display: none !important;
        }
        
        @media (max-width: 1000px) {
            .pos-container {
                grid-template-columns: 1fr;
                height: auto;
            }
            .pos-cart {
                max-height: 50vh;
            }
        }
        
        /* ═══ SEARCH BAR ═══ */
        .pos-search-wrapper {
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 15px 0;
            background: transparent;
        }
        
        .pos-search {
            position: relative;
        }
        
        .pos-search input {
            width: 100%;
            padding: 16px 20px 16px 50px;
            font-size: 18px;
            background: var(--pos-card);
            border: 2px solid transparent;
            border-radius: 16px;
            color: white;
            transition: all 0.3s;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }
        
        .pos-search input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 30px var(--pos-glow);
        }
        
        .pos-search input::placeholder {
            color: rgba(255,255,255,0.4);
        }
        
        .pos-search-icon {
            position: absolute;
            left: 18px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 20px;
            opacity: 0.5;
        }
        
        .pos-search-hint {
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 12px;
            color: rgba(255,255,255,0.3);
            background: rgba(0,0,0,0.3);
            padding: 4px 10px;
            border-radius: 6px;
        }
        
        /* ═══ STOCK TABLE ═══ */
        .pos-table-wrapper {
            flex: 1;
            overflow-y: auto;
            background: var(--pos-card);
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        .pos-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .pos-table thead {
            position: sticky;
            top: 0;
            z-index: 10;
        }
        
        .pos-table thead th {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.1));
            padding: 14px 16px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: rgba(255,255,255,0.7);
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .pos-table thead th:first-child {
            border-radius: 16px 0 0 0;
        }
        
        .pos-table thead th:last-child {
            border-radius: 0 16px 0 0;
        }
        
        .stock-row {
            cursor: pointer;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        
        .stock-row:hover {
            background: linear-gradient(90deg, rgba(99, 102, 241, 0.15), transparent);
        }
        
        .stock-row:active {
            background: rgba(99, 102, 241, 0.25);
        }
        
        .stock-row td {
            padding: 14px 16px;
            vertical-align: middle;
        }
        
        .stock-row.negative {
            background: rgba(239, 68, 68, 0.1);
        }
        
        .stock-row.zero {
            opacity: 0.5;
        }
        
        .stock-row.low {
            background: rgba(245, 158, 11, 0.05);
        }
        
        .col-code {
            font-weight: 700;
            color: var(--primary);
            font-size: 14px;
            width: 140px;
        }
        
        .col-desc {
            color: rgba(255,255,255,0.9);
            font-size: 14px;
        }
        
        .col-price {
            font-weight: 700;
            color: var(--pos-green);
            font-size: 16px;
            width: 120px;
            text-align: right;
        }
        
        .col-stock {
            width: 80px;
            text-align: center;
        }
        
        .col-action {
            width: 70px;
            text-align: center;
        }
        
        .stock-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            background: rgba(255,255,255,0.1);
            color: rgba(255,255,255,0.7);
        }
        
        .stock-badge.negative {
            background: rgba(239, 68, 68, 0.2);
            color: var(--pos-red);
        }
        
        .stock-badge.zero {
            background: rgba(255,255,255,0.05);
            color: rgba(255,255,255,0.3);
        }
        
        .stock-badge.low {
            background: rgba(245, 158, 11, 0.2);
            color: var(--pos-orange);
        }
        
        .qty-btn {
            padding: 6px 12px;
            background: linear-gradient(135deg, var(--primary), #7c3aed);
            border: none;
            border-radius: 8px;
            color: white;
            font-size: 11px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .qty-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
        }
        
        /* ═══ CART PANEL ═══ */
        .pos-cart {
            background: var(--pos-card);
            border-radius: 16px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            height: 100%;
            min-height: 0;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        .pos-cart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .pos-cart-title {
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(135deg, #fff, rgba(255,255,255,0.7));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .pos-cart-count {
            font-size: 13px;
            color: rgba(255,255,255,0.5);
            background: rgba(255,255,255,0.1);
            padding: 4px 12px;
            border-radius: 20px;
        }
        
        .pos-cart-items {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        
        .cart-item {
            display: flex;
            align-items: center;
            padding: 8px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            margin-bottom: 6px;
            transition: all 0.2s;
        }
        
        .cart-item:hover {
            background: rgba(255,255,255,0.06);
        }
        
        .cart-item-info {
            flex: 1;
            min-width: 0;
        }
        
        .cart-item-name {
            font-weight: 600;
            font-size: 11px;
            line-height: 1.2;
        }
        
        .cart-item-code {
            font-size: 10px;
            color: var(--primary);
            margin-top: 1px;
        }
        
        .cart-item-price {
            font-size: 10px;
            color: rgba(255,255,255,0.5);
        }
        
        .cart-item-qty {
            display: flex;
            align-items: center;
            gap: 4px;
            margin: 0 8px;
        }
        
        .cart-qty-btn {
            width: 24px;
            height: 24px;
            border-radius: 6px;
            border: none;
            background: rgba(255,255,255,0.1);
            color: white;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .cart-qty-btn:hover {
            background: var(--primary);
        }
        
        .cart-qty-btn.minus:hover {
            background: var(--pos-red);
        }
        
        .cart-qty-display {
            min-width: 28px;
            text-align: center;
            font-weight: 700;
            font-size: 12px;
            cursor: pointer;
            padding: 3px;
            border-radius: 4px;
            transition: all 0.2s;
        }
        
        .cart-qty-display:hover {
            background: rgba(255,255,255,0.1);
        }
        
        .cart-item-total {
            font-weight: 700;
            font-size: 12px;
            color: var(--pos-green);
            min-width: 70px;
            text-align: right;
        }
        .cart-del-btn {
            background: none;
            border: none;
            color: #666;
            font-size: 14px;
            cursor: pointer;
            padding: 4px 6px;
            margin-left: 4px;
            border-radius: 4px;
            transition: all 0.15s;
            line-height: 1;
        }
        .cart-del-btn:hover {
            color: #ef4444;
            background: rgba(239,68,68,0.15);
        }
        
        /* ═══ TOTALS ═══ */
        .pos-totals {
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 10px;
        }
        
        .pos-total-row {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            font-size: 12px;
            color: rgba(255,255,255,0.6);
        }
        
        .pos-total-row.grand {
            border-top: 1px solid rgba(255,255,255,0.1);
            margin-top: 8px;
            padding-top: 12px;
            font-size: 15px;
            font-weight: 700;
            color: white;
        }
        
        .pos-total-row.grand span:last-child {
            color: var(--pos-green);
            font-size: 18px;
        }
        
        /* ═══ EMPTY STATE ═══ */
        .pos-empty {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 15px;
            color: rgba(255,255,255,0.3);
            text-align: center;
            font-size: 12px;
        }
        
        .pos-empty-icon {
            font-size: 20px;
            margin-bottom: 5px;
            opacity: 0.3;
        }
        
        /* ═══ HEADER ═══ */
        .pos-header {
            position: sticky;
            top: 0;
            z-index: 1000;
            background: var(--pos-card);
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
        }
        
        .pos-header-nav {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .pos-header-nav a {
            color: rgba(255,255,255,0.6);
            text-decoration: none;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.2s;
        }
        
        .pos-header-nav a:hover {
            background: rgba(255,255,255,0.05);
            color: white;
        }
        
        .pos-header-nav a.active {
            color: white;
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(139, 92, 246, 0.2));
        }
        
        .pos-logo {
            font-weight: 800;
            font-size: 16px;
            padding: 8px 16px;
            border-radius: 10px;
            background: linear-gradient(135deg, var(--primary), #7c3aed);
            color: white;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
        }
        
        .pos-logo:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 20px rgba(99, 102, 241, 0.5);
        }
        
        .pos-header-actions {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .pos-header-total {
            font-size: 22px;
            font-weight: 800;
            color: var(--pos-green);
            margin-right: 15px;
            text-shadow: 0 0 20px rgba(16, 185, 129, 0.5);
        }
        
        .pos-pay-btn {
            padding: 10px 18px;
            border: none;
            border-radius: 10px;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .pos-pay-btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        
        .pos-pay-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        
        .pos-pay-btn.cash {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
        }
        
        .pos-pay-btn.card {
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            color: white;
        }
        
        .pos-pay-btn.account {
            background: linear-gradient(135deg, #f59e0b, #d97706);
            color: white;
        }
        
        .pos-pay-btn.quote {
            background: linear-gradient(135deg, #8b5cf6, #7c3aed);
            color: white;
        }
        
        .pos-pay-btn.po {
            background: linear-gradient(135deg, #ec4899, #db2777);
            color: white;
        }
        
        .pos-pay-btn.clear {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
        }
        
        .key-hint {
            font-size: 9px;
            background: rgba(0,0,0,0.3);
            padding: 2px 5px;
            border-radius: 4px;
            font-family: monospace;
        }
        
        /* Customer/Supplier select - DARK & VISIBLE */
        .entity-select-wrapper {
            display: flex;
            align-items: center;
            gap: 4px;
            background: rgba(20, 20, 35, 0.95);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 8px;
            padding: 2px;
        }
        .entity-toggle {
            padding: 6px 10px;
            border: none;
            background: transparent;
            color: rgba(255,255,255,0.5);
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s;
        }
        .entity-toggle.active {
            background: var(--primary);
            color: white;
        }
        .entity-toggle:hover:not(.active) {
            background: rgba(255,255,255,0.1);
        }
        .entity-dropdown {
            position: relative;
        }
        .entity-search {
            padding: 8px 12px;
            border-radius: 6px;
            background: rgba(30, 30, 50, 0.95);
            color: #fff;
            border: none;
            font-size: 13px;
            cursor: pointer;
            width: 150px;
        }
        .entity-search:focus {
            outline: none;
            box-shadow: 0 0 0 2px var(--primary);
        }
        .entity-search::placeholder {
            color: rgba(255,255,255,0.7);
        }
        .entity-list {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #1a1a2e;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            max-height: 250px;
            overflow-y: auto;
            z-index: 1000;
            margin-top: 4px;
            min-width: 200px;
        }
        .entity-item {
            padding: 8px 12px;
            color: #fff;
            cursor: pointer;
            font-size: 13px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .entity-item:hover, .entity-item.highlighted {
            background: var(--primary);
        }
        .entity-item.new-item {
            color: #10b981;
            font-weight: 600;
        }
        
        /* ═══ SHORTCUTS BAR ═══ */
        .pos-shortcuts {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--pos-card);
            border-top: 1px solid rgba(255,255,255,0.1);
            padding: 10px 20px;
            display: flex;
            gap: 25px;
            justify-content: center;
            flex-wrap: wrap;
            font-size: 12px;
            color: rgba(255,255,255,0.4);
            backdrop-filter: blur(10px);
        }
        
        .pos-shortcuts span {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .pos-shortcuts kbd {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 5px;
            padding: 3px 8px;
            font-family: monospace;
            font-weight: 600;
            color: rgba(255,255,255,0.7);
        }
        
        /* ═══ RESPONSIVE ═══ */
        @media (max-width: 1200px) {
            .pos-header-actions {
                gap: 8px;
            }
            .pos-pay-btn {
                padding: 8px 12px;
                font-size: 12px;
            }
        }
        
        @media (max-width: 768px) {
            .pos-header {
                flex-direction: column;
                gap: 10px;
            }
            .pos-header-actions {
                width: 100%;
                justify-content: center;
            }
        }
        
        /* ═══ SCROLLBAR ═══ */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255,255,255,0.3);
        }
        
        /* ═══ NO RESULTS ═══ */
        .no-results {
            display: none;
            padding: 40px;
            text-align: center;
            color: rgba(255,255,255,0.4);
        }
        
        .no-results.show {
            display: block;
        }
        
        /* ═══════════════════════════════════════════════════════════════
           POS REACTOR UPGRADE - Visual enhancements
           ═══════════════════════════════════════════════════════════════ */
        
        /* Animated glow border on search */
        .pos-search input {
            border: 2px solid rgba(99, 102, 241, 0.3) !important;
            animation: searchPulse 3s ease-in-out infinite;
        }
        @keyframes searchPulse {
            0%, 100% { border-color: rgba(99, 102, 241, 0.3); box-shadow: 0 0 15px rgba(99, 102, 241, 0.1); }
            50% { border-color: rgba(99, 102, 241, 0.6); box-shadow: 0 0 25px rgba(99, 102, 241, 0.3); }
        }
        .pos-search input:focus {
            animation: none !important;
            border-color: #6366f1 !important;
            box-shadow: 0 0 40px rgba(99, 102, 241, 0.5), inset 0 0 20px rgba(99, 102, 241, 0.05) !important;
        }
        
        /* Reactor glow on cart panel */
        .pos-cart {
            border: 1px solid rgba(99, 102, 241, 0.2) !important;
            box-shadow: 0 0 30px rgba(99, 102, 241, 0.08), 0 8px 32px rgba(0, 0, 0, 0.3) !important;
            position: relative;
            overflow: hidden;
        }
        .pos-cart::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, #6366f1, #10b981, #6366f1, transparent);
            animation: cartTopGlow 4s linear infinite;
        }
        @keyframes cartTopGlow {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
        }
        .pos-cart::before { background-size: 200% 100%; }
        
        /* Stock table reactor styling */
        .pos-table-wrapper {
            border: 1px solid rgba(99, 102, 241, 0.15) !important;
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.05), 0 8px 32px rgba(0, 0, 0, 0.3) !important;
        }
        
        .pos-table thead th {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(16, 185, 129, 0.08)) !important;
            text-shadow: 0 0 10px rgba(99, 102, 241, 0.3);
            letter-spacing: 1.5px !important;
        }
        
        /* Row hover with cyan glow like dashboard */
        .stock-row:hover {
            background: linear-gradient(90deg, rgba(6, 182, 212, 0.12), rgba(99, 102, 241, 0.08), transparent) !important;
            box-shadow: inset 3px 0 0 #06b6d4;
        }
        
        .stock-row:active {
            background: linear-gradient(90deg, rgba(16, 185, 129, 0.2), rgba(99, 102, 241, 0.1), transparent) !important;
        }
        
        /* Price column glow */
        .col-price {
            text-shadow: 0 0 8px rgba(16, 185, 129, 0.4) !important;
        }
        
        /* Code column cyan tint like dashboard */
        .col-code {
            color: #06b6d4 !important;
            text-shadow: 0 0 6px rgba(6, 182, 212, 0.3);
        }
        
        /* QTY button upgrade */
        .qty-btn {
            background: linear-gradient(135deg, #6366f1, #06b6d4) !important;
            box-shadow: 0 2px 10px rgba(99, 102, 241, 0.3);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .qty-btn:hover {
            box-shadow: 0 4px 20px rgba(6, 182, 212, 0.5) !important;
        }
        
        /* Header total glow effect */
        .pos-header-total {
            text-shadow: 0 0 30px rgba(0, 255, 136, 0.7), 0 0 60px rgba(0, 255, 136, 0.3) !important;
            font-size: 24px !important;
        }
        
        /* Payment buttons - more vibrant with glow */
        .pos-pay-btn.cash {
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
        }
        .pos-pay-btn.card {
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.3);
        }
        .pos-pay-btn.account {
            box-shadow: 0 0 15px rgba(245, 158, 11, 0.3);
        }
        .pos-pay-btn.quote {
            box-shadow: 0 0 15px rgba(139, 92, 246, 0.3);
        }
        .pos-pay-btn.cash:hover {
            box-shadow: 0 0 25px rgba(16, 185, 129, 0.5), 0 4px 15px rgba(0,0,0,0.3) !important;
        }
        .pos-pay-btn.card:hover {
            box-shadow: 0 0 25px rgba(59, 130, 246, 0.5), 0 4px 15px rgba(0,0,0,0.3) !important;
        }
        .pos-pay-btn.account:hover {
            box-shadow: 0 0 25px rgba(245, 158, 11, 0.5), 0 4px 15px rgba(0,0,0,0.3) !important;
        }
        .pos-pay-btn.quote:hover {
            box-shadow: 0 0 25px rgba(139, 92, 246, 0.5), 0 4px 15px rgba(0,0,0,0.3) !important;
        }
        
        /* Cashier buttons - reactor style */
        .cashier-btn {
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            font-size: 12px !important;
        }
        .cashier-btn.active {
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.5), 0 0 40px rgba(99, 102, 241, 0.2) !important;
            animation: activeCashierPulse 2s ease-in-out infinite;
        }
        @keyframes activeCashierPulse {
            0%, 100% { box-shadow: 0 0 15px rgba(99, 102, 241, 0.4); }
            50% { box-shadow: 0 0 25px rgba(99, 102, 241, 0.6), 0 0 40px rgba(99, 102, 241, 0.2); }
        }
        
        /* Cashier bar reactor border */
        .cashier-bar {
            border-bottom: 1px solid rgba(6, 182, 212, 0.2) !important;
            background: linear-gradient(135deg, rgba(15, 15, 30, 0.95), rgba(20, 20, 45, 0.95)) !important;
        }
        
        /* Cart item hover glow */
        .cart-item:hover {
            background: rgba(99, 102, 241, 0.08) !important;
            box-shadow: inset 2px 0 0 #6366f1;
        }
        
        /* Grand total in cart - reactor green */
        .pos-total-row.grand span:last-child {
            text-shadow: 0 0 15px rgba(16, 185, 129, 0.5) !important;
            font-size: 20px !important;
        }
        
        /* Cart empty state - add subtle animation */
        .pos-empty-icon {
            animation: emptyFloat 3s ease-in-out infinite;
        }
        @keyframes emptyFloat {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }
        
        /* Header - reactor gradient border bottom */
        .pos-header {
            border-bottom: 1px solid transparent !important;
            background-image: linear-gradient(rgba(30,30,50,0.95), rgba(30,30,50,0.95)), 
                              linear-gradient(90deg, transparent, rgba(99,102,241,0.4), rgba(6,182,212,0.3), rgba(16,185,129,0.3), transparent) !important;
            background-origin: border-box !important;
            background-clip: padding-box, border-box !important;
        }
        
        /* Stock badge upgrades - glow on good stock */
        .stock-badge:not(.negative):not(.zero):not(.low) {
            background: rgba(16, 185, 129, 0.15) !important;
            color: #10b981 !important;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        
        .stock-badge.low {
            animation: lowStockPulse 2s ease-in-out infinite;
        }
        @keyframes lowStockPulse {
            0%, 100% { background: rgba(245, 158, 11, 0.15); }
            50% { background: rgba(245, 158, 11, 0.25); }
        }
        
        .stock-badge.negative {
            animation: negStockPulse 1.5s ease-in-out infinite;
        }
        @keyframes negStockPulse {
            0%, 100% { background: rgba(239, 68, 68, 0.15); }
            50% { background: rgba(239, 68, 68, 0.3); }
        }
        
        /* Keyboard bar at bottom - reactor style */
        .keyboard-bar {
            background: linear-gradient(180deg, rgba(15,15,30,0.95), rgba(10,10,25,0.98)) !important;
            border-top: 1px solid rgba(6, 182, 212, 0.15) !important;
            box-shadow: 0 -4px 20px rgba(0,0,0,0.3) !important;
        }
        
        /* Custom button in cart header */
        .pos-cart-header button, .pos-cart-header .btn {
            border: 1px solid rgba(99, 102, 241, 0.3) !important;
        }
        
        /* Scan effect on row click */
        @keyframes rowFlash {
            0% { background: rgba(16, 185, 129, 0.3); }
            100% { background: transparent; }
        }
        .stock-row.just-added {
            animation: rowFlash 0.4s ease-out;
        }
    
        /* ═══ POS REACTOR HUD ═══ */
        .pos-reactor-wrap{border:1px solid rgba(80,180,255,0.12);background:rgba(4,12,35,0.5);position:relative;overflow:visible;margin:0;}
        .pos-reactor-wrap::before{content:'';position:absolute;top:0;left:0;width:20px;height:20px;border-top:2px solid rgba(100,200,255,0.35);border-left:2px solid rgba(100,200,255,0.35);z-index:5;pointer-events:none;}
        .pos-reactor-wrap::after{content:'';position:absolute;bottom:0;right:0;width:20px;height:20px;border-bottom:2px solid rgba(100,200,255,0.35);border-right:2px solid rgba(100,200,255,0.35);z-index:5;pointer-events:none;}
        .pos-reactor-hero{display:flex;align-items:center;justify-content:center;padding:10px 20px;position:relative;gap:0;}
        .pos-btn-flank{display:flex;flex-direction:column;gap:4px;width:180px;flex:1;max-width:200px;}
        .pos-hud-btn{padding:8px 10px;border:1px solid rgba(80,180,255,0.12);background:rgba(10,30,60,0.3);cursor:pointer;transition:all 0.2s;display:flex;align-items:center;gap:8px;font-family:'Rajdhani',sans-serif;font-weight:600;color:#a0d8f8;font-size:12px;letter-spacing:0.5px;text-transform:uppercase;}
        .pos-hud-btn:hover:not(:disabled){border-color:rgba(0,200,255,0.35);background:rgba(0,200,255,0.06);color:#00ddff;text-shadow:0 0 8px rgba(0,200,255,0.3);}
        .pos-hud-btn:disabled{opacity:0.35;cursor:not-allowed;}
        .pos-hud-btn .pk,.pos-entity-btn .pk,.f11-btn .pk{font-family:'Share Tech Mono',monospace;font-size:10px;color:#00ccff;padding:2px 6px;border:1px solid rgba(0,200,255,0.3);letter-spacing:0.5px;flex-shrink:0;background:rgba(0,200,255,0.08);text-shadow:0 0 6px rgba(0,200,255,0.4);}
        .pos-btn-flank.L .pos-hud-btn{border-left:2px solid rgba(80,180,255,0.3);}
        .pos-btn-flank.R .pos-hud-btn{border-right:2px solid rgba(80,180,255,0.3);flex-direction:row-reverse;}
        .pos-reactor-cn{width:16px;height:2px;position:relative;flex-shrink:0;}
        .pos-reactor-cn::before{content:'';position:absolute;inset:0;background:linear-gradient(90deg,rgba(80,180,255,0.05),rgba(80,180,255,0.3));}
        .pos-reactor-cn.R::before{background:linear-gradient(90deg,rgba(80,180,255,0.3),rgba(80,180,255,0.05));}
        .pos-reactor-cn::after{content:'';position:absolute;right:-2px;top:-2.5px;width:7px;height:7px;border-radius:50%;background:rgba(80,180,255,0.35);box-shadow:0 0 8px rgba(80,180,255,0.4);}
        .pos-reactor-cn.R::after{left:-2px;right:auto;}
        .pos-rx{position:relative;flex-shrink:0;width:160px;height:160px;}
        .pos-rx .j-rg{position:absolute;border-radius:50%;border:1px solid rgba(80,180,255,0.2);}
        .pos-rx .j-rg.r1{inset:0;border-color:rgba(80,180,255,0.25);border-top-color:rgba(120,210,255,0.65);animation:jspin 8s linear infinite;box-shadow:0 0 25px rgba(80,180,255,0.08);}
        .pos-rx .j-rg.r2{inset:12px;border-color:rgba(60,160,240,0.15);border-bottom-color:rgba(100,200,255,0.55);animation:jspin 6s linear infinite reverse;}
        .pos-rx .j-rg.r3{inset:24px;border-color:rgba(80,180,255,0.1);border-top-color:rgba(140,220,255,0.45);animation:jspin 4s linear infinite;}
        .pos-rx .j-rg.r4{inset:36px;border:2px solid rgba(100,200,255,0.08);border-top-color:rgba(160,230,255,0.5);animation:jspin 12s linear infinite reverse;}
        .pos-rx .pos-rx-core{position:absolute;inset:42px;border-radius:50%;background:radial-gradient(circle,rgba(120,210,255,0.12) 0%,transparent 100%);border:1px solid rgba(100,200,255,0.2);display:flex;align-items:center;justify-content:center;flex-direction:column;box-shadow:0 0 30px rgba(80,180,255,0.1);}
        .pos-rx .pos-rx-core .j-brand{font-family:'Orbitron',monospace;font-size:13px;font-weight:800;color:#55bbff;text-shadow:0 0 18px rgba(85,187,255,0.6);letter-spacing:2px;}
        .pos-rx .pos-rx-core .j-sub{font-family:'Share Tech Mono',monospace;font-size:6.5px;color:#4499cc;letter-spacing:3px;margin-top:3px;}
        .pos-hud-total{font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#00ff88;text-shadow:0 0 12px rgba(0,255,136,0.5);margin-top:4px;letter-spacing:1px;}
        .pos-lbl{position:absolute;bottom:-4px;left:50%;transform:translateX(-50%);text-align:center;z-index:2;}
        .pos-lbl span{font-family:'Orbitron',monospace;font-size:10px;font-weight:600;color:#5aaadd;letter-spacing:3px;text-shadow:0 0 10px rgba(90,170,221,0.3);}
        .pos-entity-bar{display:flex;align-items:center;justify-content:center;gap:0;padding:8px 20px;border-top:1px solid rgba(80,180,255,0.06);}
        .pos-entity-btn{display:flex;align-items:center;justify-content:center;gap:5px;min-width:44px;padding:0 10px;height:36px;border:1px solid rgba(80,180,255,0.15);background:rgba(10,30,60,0.4);color:#a0d8f8;font-family:'Rajdhani',sans-serif;font-weight:700;font-size:14px;cursor:pointer;transition:all 0.2s;letter-spacing:1px;flex-shrink:0;}
        .pos-entity-btn:hover{border-color:rgba(0,200,255,0.35);color:#00ddff;background:rgba(0,200,255,0.06);}
        .pos-entity-btn.active{background:rgba(80,180,255,0.12);color:#00ddff;border-color:rgba(0,200,255,0.3);}
        .pos-entity-btn.L{border-right:none;}
        .pos-entity-btn.R{border-left:none;}
        .pos-entity-input{height:36px;width:240px;border:1px solid rgba(80,180,255,0.15);background:rgba(6,16,40,0.5);color:#e0f0ff;font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:600;padding:0 14px;letter-spacing:0.5px;text-align:center;outline:none;}
        .pos-entity-input::placeholder{color:#4a7a9a;letter-spacing:1px;}
        .pos-entity-input:focus{border-color:rgba(0,200,255,0.35);background:rgba(0,200,255,0.04);}
        @keyframes jspin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
        .entity-list .entity-item{padding:8px 14px;cursor:pointer;color:#a0d8f8;font-family:'Rajdhani',sans-serif;font-size:14px;font-weight:600;border-bottom:1px solid rgba(80,180,255,0.04);transition:all 0.1s;}
        .entity-list .entity-item:hover,.entity-list .entity-item.highlighted{background:rgba(0,200,255,0.06);color:#00ddff;}
        @media(max-width:1200px){.pos-btn-flank{max-width:160px;}.pos-hud-btn{font-size:11px;padding:6px 8px;}}
        @media(max-width:900px){.pos-reactor-hero{flex-wrap:wrap;gap:8px;}.pos-btn-flank{flex-direction:row;flex-wrap:wrap;width:100%;max-width:100%;}.pos-rx{width:120px;height:120px;}.pos-rx .pos-rx-core{inset:32px;}.pos-reactor-cn{display:none;}}
    
        /* ═══ F11 FULLSCREEN MODE ═══ */
        .f11-header{display:none;padding:2px 6px;background:rgba(4,12,35,0.98);border-bottom:1px solid rgba(80,180,255,0.15);align-items:center;gap:0;justify-content:space-between;height:36px;min-height:36px;max-height:36px;overflow:hidden;}
        .f11-left{display:flex;align-items:center;gap:1px;flex-wrap:nowrap;overflow:hidden;}
        .f11-btn{padding:4px 6px;border:1px solid rgba(80,180,255,0.15);background:rgba(10,30,60,0.4);cursor:pointer;transition:all 0.15s;display:inline-flex;align-items:center;gap:3px;font-family:'Rajdhani',sans-serif;font-weight:700;color:#a0d8f8;font-size:10px;letter-spacing:0.2px;text-transform:uppercase;white-space:nowrap;line-height:1;}
        .f11-btn:hover{border-color:rgba(0,200,255,0.4);background:rgba(0,200,255,0.1);color:#00eeff;}
        .f11-btn:disabled{opacity:0.3;cursor:not-allowed;}
        .f11-btn .pk{font-family:'Share Tech Mono',monospace;font-size:8px;color:#00ccff;padding:1px 3px;border:1px solid rgba(0,200,255,0.25);background:rgba(0,200,255,0.06);}
        .f11-right{display:flex;align-items:center;gap:6px;flex-shrink:0;margin-left:auto;padding-left:4px;}
        .f11-cust{font-family:'Rajdhani',sans-serif;font-size:11px;color:#a0d8f8;font-weight:700;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
        .f11-total{font-family:'Orbitron',monospace;font-size:16px;font-weight:800;color:#00ff88;text-shadow:0 0 12px rgba(0,255,136,0.5);letter-spacing:0.5px;}
        .f11-exit{padding:4px 8px;border:1px solid rgba(255,80,80,0.25);background:rgba(255,40,40,0.08);cursor:pointer;display:inline-flex;align-items:center;gap:3px;font-family:'Rajdhani',sans-serif;font-weight:700;color:#ff8888;font-size:10px;text-transform:uppercase;}
        .f11-exit:hover{border-color:rgba(255,80,80,0.5);background:rgba(255,40,40,0.15);color:#ffaaaa;}
        .f11-exit .pk{color:#ff6666;border-color:rgba(255,80,80,0.25);background:rgba(255,40,40,0.06);font-size:8px;padding:1px 3px;}
        .f11-order-wrap{display:none;flex:1;overflow:hidden;flex-direction:column;}
        .f11-search{padding:6px 12px;border-bottom:1px solid rgba(80,180,255,0.08);position:relative;}
        .f11-search input{width:100%;height:44px;background:rgba(8,20,50,0.9);border:2px solid rgba(0,200,255,0.5);color:#e8f4ff;font-family:'Rajdhani',sans-serif;font-size:17px;font-weight:600;padding:0 14px 0 40px;outline:none;letter-spacing:0.5px;border-radius:4px;box-shadow:0 0 12px rgba(0,200,255,0.15);animation:f11searchPulse 2.5s ease-in-out infinite;}
        @keyframes f11searchPulse{0%,100%{border-color:rgba(0,200,255,0.5);box-shadow:0 0 12px rgba(0,200,255,0.15);}50%{border-color:rgba(0,220,255,0.8);box-shadow:0 0 24px rgba(0,200,255,0.3);}}
        .f11-search::before{content:'🔍';position:absolute;left:22px;top:50%;transform:translateY(-50%);font-size:16px;z-index:1;opacity:0.7;}
        .f11-search input::placeholder{color:#7ab0d0;font-weight:500;}
        .f11-search input:focus{border-color:rgba(0,220,255,0.8);background:rgba(0,200,255,0.06);box-shadow:0 0 24px rgba(0,200,255,0.3);animation:none;}
        .f11-dd{display:none;position:fixed;left:20px;right:20px;background:rgba(6,14,36,0.98);border:1px solid rgba(80,180,255,0.25);max-height:calc(100vh - 160px);overflow-y:auto;z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,0.6);}
        .f11-dd.show{display:block;}
        .f11-dd-item{display:flex;align-items:center;padding:14px 20px;cursor:pointer;border-bottom:1px solid rgba(80,180,255,0.04);transition:all 0.1s;gap:16px;}
        .f11-dd-item:hover,.f11-dd-item.sel{background:rgba(0,200,255,0.08);border-left:3px solid #00ccff;}
        .f11-dd-code{font-family:'Share Tech Mono',monospace;font-size:15px;color:#7abade;min-width:140px;letter-spacing:0.5px;}
        .f11-dd-desc{flex:1;font-size:16px;color:#d8ecff;font-weight:600;}
        .f11-dd-price{font-family:'Share Tech Mono',monospace;font-size:15px;color:#00ff88;font-weight:700;min-width:100px;text-align:right;}
        .f11-dd-qty{font-family:'Share Tech Mono',monospace;font-size:11px;color:#5a8aaa;min-width:50px;text-align:right;}
        .f11-dd-empty{padding:16px;text-align:center;color:#5a8aaa;font-size:14px;}
        .f11-dd-rel{border-left:2px solid rgba(245,158,11,0.4) !important;}
        .f11-dd-rel .f11-dd-code{color:#f59e0b;}
        .f11-table-wrap{flex:1;overflow-y:auto;padding:0 20px;}
        .f11-table{width:100%;border-collapse:collapse;}
        .f11-table th{text-align:left;padding:10px 12px;font-family:'Share Tech Mono',monospace;font-size:11px;color:#7abade;letter-spacing:1.5px;border-bottom:2px solid rgba(80,180,255,0.15);position:sticky;top:0;background:#0a0a1a;z-index:2;}
        .f11-table th.r{text-align:right;}
        .f11-table td{padding:10px 12px;font-size:15px;font-weight:600;color:#d8ecff;border-bottom:1px solid rgba(80,180,255,0.04);}
        .f11-table td.r{text-align:right;font-family:'Share Tech Mono',monospace;}
        .f11-table td.code{color:#7abade;font-family:'Share Tech Mono',monospace;font-size:14px;}
        .f11-table td.qty{color:#00ff88;font-weight:700;}
        .f11-table td.tot{color:#00ff88;font-weight:700;}
        .f11-table tr:hover td{background:rgba(0,200,255,0.04);color:#fff;}
        .f11-table tr.f11-sel td{background:rgba(80,180,255,0.08);border-bottom:1px solid rgba(0,200,255,0.15);}
        .f11-table tr.f11-sel td:first-child{border-left:2px solid #00ccff;}
        .f11-onhand{font-size:12px;color:#5a8aaa;font-family:'Share Tech Mono',monospace;}
        .f11-del-btn{background:none;border:1px solid rgba(239,68,68,0.2);color:#5a6a7a;font-size:14px;cursor:pointer;padding:3px 7px;border-radius:4px;transition:all 0.15s;line-height:1;font-weight:700;}
        .f11-del-btn:hover{color:#ef4444;background:rgba(239,68,68,0.15);border-color:rgba(239,68,68,0.4);text-shadow:0 0 8px rgba(239,68,68,0.5);}
    
        /* F11 state toggle — hide ALL page elements, show fixed overlay */
        body.f11-mode .pos-header{display:none !important;}
        body.f11-mode .pos-reactor-wrap{position:fixed !important;top:38px;left:0;right:0;z-index:9100;border:none !important;background:none !important;margin:0 !important;padding:0 !important;pointer-events:none;overflow:visible !important;}
        body.f11-mode .pos-reactor-wrap::before,body.f11-mode .pos-reactor-wrap::after{display:none !important;}
        body.f11-mode .pos-reactor-hero{display:none !important;}
        body.f11-mode .pos-reactor-wrap .pos-lbl{display:none !important;}
        body.f11-mode .pos-entity-bar{pointer-events:auto;display:none;background:rgba(4,12,35,0.98);border:1px solid rgba(80,180,255,0.2);border-radius:0 0 8px 8px;padding:6px 12px;position:absolute;left:50%;transform:translateX(-50%);z-index:9600;}
        body.f11-mode .container{display:none !important;}
        body.f11-mode .cashier-bar{display:none !important;}
        body.f11-mode .zane-chat{display:none !important;}
        body.f11-mode .f11-header{display:flex !important;position:fixed !important;top:0;left:0;right:0;z-index:9000;background:rgba(4,12,35,0.98) !important;}
        body.f11-mode .f11-order-wrap{display:flex !important;position:fixed !important;top:38px;left:0;right:0;bottom:0;z-index:8999;background:rgba(4,12,35,0.98) !important;}
        body.f11-mode{overflow:hidden !important;}
    
        /* ═══ LIGHT THEME POS ═══ */
        [data-theme="light"] body{background:#f0f2f5 !important;}
        [data-theme="light"] .cashier-bar{background:#fff;border-bottom:1px solid #e2e5ea;}
        [data-theme="light"] .cashier-bar label{color:#6b7280;}
        [data-theme="light"] .cashier-btn{border:1px solid #d1d5db;background:#f4f6f9;color:#374151;}
        [data-theme="light"] .cashier-btn:hover{background:#e8eaf0;border-color:#9ca3af;}
        [data-theme="light"] .cashier-btn.active{background:#4f46e5;color:#fff;border-color:#4f46e5;box-shadow:0 2px 8px rgba(79,70,229,0.3);text-shadow:none;}
        [data-theme="light"] .pos-header{background:#fff !important;border-bottom:1px solid #e2e5ea;box-shadow:0 1px 3px rgba(0,0,0,0.06);}
        [data-theme="light"] .pos-header-nav a{color:#6b7280;}
        [data-theme="light"] .pos-header-nav a:hover{color:#4f46e5;}
        [data-theme="light"] .pos-header-nav a.active{color:#4f46e5;border-bottom-color:#4f46e5;}
        [data-theme="light"] .pos-search{background:#fff;border:1px solid #d1d5db;box-shadow:0 1px 3px rgba(0,0,0,0.04);}
        [data-theme="light"] .pos-search input{background:transparent !important;color:#1a1a2e !important;}
        [data-theme="light"] .pos-search input::placeholder{color:#9ca3af !important;}
        [data-theme="light"] .pos-search-icon{color:#9ca3af;}
        [data-theme="light"] .pos-search-hint{color:#9ca3af;background:#f4f6f9;}
        [data-theme="light"] .pos-table-wrapper{background:#fff;border:1px solid #e2e5ea;box-shadow:0 1px 3px rgba(0,0,0,0.04);}
        [data-theme="light"] .pos-table thead{background:#f8f9fb;}
        [data-theme="light"] .pos-table thead th{background:#f8f9fb !important;color:#6b7280 !important;border-bottom:2px solid #e2e5ea !important;}
        [data-theme="light"] .stock-row{border-bottom:1px solid #f0f2f5;}
        [data-theme="light"] .stock-row:hover{background:#f0f4ff !important;}
        [data-theme="light"] .stock-row:active{background:#e0e7ff !important;}
        [data-theme="light"] .stock-row td{color:#374151;}
        [data-theme="light"] .col-code{color:#4f46e5 !important;}
        [data-theme="light"] .col-desc{color:#1f2937 !important;}
        [data-theme="light"] .col-price{color:#059669 !important;}
        [data-theme="light"] .stock-badge{background:#e0e7ff;color:#4f46e5;}
        [data-theme="light"] .stock-badge.negative{background:#fee2e2;color:#dc2626;}
        [data-theme="light"] .stock-badge.zero{background:#f4f6f9;color:#9ca3af;}
        [data-theme="light"] .stock-badge.low{background:#fef3c7;color:#d97706;}
        [data-theme="light"] .stock-row.negative{background:#fef2f2;}
        [data-theme="light"] .stock-row.zero{background:#fafafa;}
        [data-theme="light"] .stock-row.low{background:#fffbeb;}
        [data-theme="light"] .qty-btn{background:#4f46e5 !important;color:#fff !important;border:none;}
        [data-theme="light"] .qty-btn:hover{background:#4338ca !important;}
        [data-theme="light"] .pos-cart{background:#fff;border:1px solid #e2e5ea;box-shadow:0 1px 3px rgba(0,0,0,0.04);}
        [data-theme="light"] .pos-cart-header{border-bottom:1px solid #e2e5ea;}
        [data-theme="light"] .pos-cart-title{color:#1f2937;background:none;-webkit-text-fill-color:#1f2937;}
        [data-theme="light"] .pos-cart-count{color:#6b7280;}
        [data-theme="light"] .cart-item{border-bottom:1px solid #f0f2f5;}
        [data-theme="light"] .cart-item:hover{background:#f8f9fb;}
        [data-theme="light"] .cart-item-name{color:#1f2937;}
        [data-theme="light"] .cart-item-code{color:#6b7280;}
        [data-theme="light"] .cart-item-price{color:#6b7280;}
        [data-theme="light"] .cart-item-total{color:#059669;}
        [data-theme="light"] .cart-qty-btn{background:#f4f6f9;color:#374151;border-color:#d1d5db;}
        [data-theme="light"] .cart-qty-btn:hover{background:#e0e7ff;color:#4f46e5;}
        [data-theme="light"] .cart-qty-display{color:#1f2937;background:#f8f9fb;}
        [data-theme="light"] .cart-del-btn{color:#9ca3af;}
        [data-theme="light"] .cart-del-btn:hover{color:#dc2626;background:#fee2e2;}
        [data-theme="light"] .pos-totals{border-top:2px solid #e2e5ea;}
        [data-theme="light"] .pos-total-row{color:#6b7280;}
        [data-theme="light"] .pos-total-row span:last-child{color:#374151;}
        [data-theme="light"] .pos-total-row.grand{color:#1f2937;}
        [data-theme="light"] .pos-total-row.grand span:last-child{color:#4f46e5;}
        [data-theme="light"] .pos-empty{color:#9ca3af;}
        [data-theme="light"] .pos-shortcuts{background:#fff;border-top:1px solid #e2e5ea;color:#9ca3af;}
        [data-theme="light"] .pos-shortcuts kbd{background:#f4f6f9;border-color:#d1d5db;color:#374151;}
        [data-theme="light"] .entity-search{background:#fff !important;border:1px solid #d1d5db !important;color:#1f2937 !important;}
        [data-theme="light"] .entity-search::placeholder{color:#9ca3af !important;}
        [data-theme="light"] .entity-list{background:#fff !important;border-color:#d1d5db !important;box-shadow:0 4px 12px rgba(0,0,0,0.1) !important;}
        [data-theme="light"] .entity-list .entity-item{color:#374151 !important;border-bottom-color:#f0f2f5 !important;}
        [data-theme="light"] .entity-list .entity-item:hover,[data-theme="light"] .entity-list .entity-item.highlighted{background:#e0e7ff !important;color:#4f46e5 !important;}
        [data-theme="light"] .entity-item.new-item{color:#059669 !important;}
        [data-theme="light"] .pos-entity-btn{border-color:#d1d5db;background:#f4f6f9;color:#374151;}
        [data-theme="light"] .pos-entity-btn:hover{background:#e0e7ff;color:#4f46e5;}
        [data-theme="light"] .pos-entity-btn.active{background:#4f46e5;color:#fff;border-color:#4f46e5;}
        [data-theme="light"] .pos-entity-input{background:#fff !important;border-color:#d1d5db !important;color:#1f2937 !important;}
        [data-theme="light"] .pos-reactor-wrap{background:#fff;border-color:#e2e5ea;}
        [data-theme="light"] .pos-reactor-wrap::before,[data-theme="light"] .pos-reactor-wrap::after{border-color:#d1d5db;}
        [data-theme="light"] .pos-hud-btn{border-color:#d1d5db;background:#f8f9fb;color:#374151;}
        [data-theme="light"] .pos-hud-btn:hover{background:#e0e7ff;color:#4f46e5;border-color:#4f46e5;}
        [data-theme="light"] .pos-hud-btn:disabled{opacity:0.35;}
        [data-theme="light"] .pos-hud-btn .pk,[data-theme="light"] .pos-entity-btn .pk,[data-theme="light"] .f11-btn .pk{color:#4f46e5;border-color:rgba(79,70,229,0.3);background:rgba(79,70,229,0.06);text-shadow:none;}
        [data-theme="light"] .pos-rx{border-color:rgba(79,70,229,0.2);}
        [data-theme="light"] .pos-rx-core{background:#fff;}
        [data-theme="light"] .j-brand{color:#4f46e5 !important;text-shadow:none !important;}
        [data-theme="light"] .j-sub{color:#9ca3af !important;}
        [data-theme="light"] .pos-hud-total{color:#059669 !important;text-shadow:none !important;}
        [data-theme="light"] .pos-reactor-cn{border-color:rgba(79,70,229,0.15);}
        [data-theme="light"] .pos-lbl span{color:#9ca3af;}
        [data-theme="light"] .pos-entity-bar{border-top-color:#e2e5ea;}
        [data-theme="light"] .no-results{color:#6b7280;background:#f8f9fb;}
        [data-theme="light"] .j-rg{border-color:rgba(79,70,229,0.1) !important;box-shadow:none !important;}
        [data-theme="light"] .f11-header{background:#fff !important;border-bottom:1px solid #e2e5ea;}
        [data-theme="light"] .f11-btn{border-color:#d1d5db;background:#f4f6f9;color:#374151;}
        [data-theme="light"] .f11-btn:hover{background:#e0e7ff;color:#4f46e5;border-color:#4f46e5;}
        [data-theme="light"] .f11-btn:disabled{opacity:0.3;}
        [data-theme="light"] .f11-cust{color:#374151;}
        [data-theme="light"] .f11-total{color:#059669;text-shadow:none;}
        [data-theme="light"] .f11-exit{border-color:#fca5a5;background:#fef2f2;color:#dc2626;}
        [data-theme="light"] .f11-exit .pk{color:#dc2626;border-color:#fca5a5;background:#fef2f2;}
        [data-theme="light"] .f11-order-wrap{background:#f0f2f5 !important;}
        [data-theme="light"] .f11-search{border-bottom-color:#e2e5ea;}
        [data-theme="light"] .f11-search input{background:#fff !important;border-color:#d1d5db !important;color:#1f2937 !important;}
        [data-theme="light"] .f11-search input::placeholder{color:#9ca3af !important;}
        [data-theme="light"] .f11-table th{background:#f8f9fb !important;color:#6b7280 !important;border-bottom-color:#e2e5ea !important;}
        [data-theme="light"] .f11-table td{color:#374151 !important;border-bottom-color:#f0f2f5 !important;}
        [data-theme="light"] .f11-table tr.f11-sel td{background:#e0e7ff !important;border-bottom-color:#c7d2fe !important;}
        [data-theme="light"] body.f11-mode .f11-header{background:#fff !important;}
        [data-theme="light"] body.f11-mode .f11-order-wrap{background:#f0f2f5 !important;}
        [data-theme="light"] body.f11-mode .pos-entity-bar{background:#fff;border-color:#e2e5ea;}
        [data-theme="light"] .f11-dd-item{color:#374151;border-bottom-color:#f0f2f5;}
        [data-theme="light"] .f11-dd-item:hover{background:#e0e7ff;}
    
        </style>
        '''
        
        pos_html = f'''
        <div class="cashier-bar">
            <label>👤 Kassier:</label>
            {cashier_buttons}
        </div>
        <div class="pos-container">
            <!-- Stock List Panel -->
            <div style="display:flex;flex-direction:column;height:100%;overflow:hidden;">
                <div class="pos-search-wrapper">
                    <div class="pos-search">
                        <span class="pos-search-icon">🔍</span>
                        <input type="text" id="stockSearch" placeholder="Search code or description..." oninput="filterStock()" autofocus>
                        <span class="pos-search-hint">5*CODE = 5 pcs</span>
                    </div>
                </div>
                
                <div class="pos-table-wrapper">
                    <table class="pos-table">
                        <tbody id="stockBody">
                            {stock_rows if stock_rows else '<tr><td colspan="5" class="pos-empty">No stock items</td></tr>'}
                        </tbody>
                    </table>
                    <div class="no-results" id="noResults">
                        <div style="font-size:48px;margin-bottom:15px;">🔍</div>
                        <div>No items found</div>
                        <div style="font-size:12px;margin-top:5px;">Try a different search term</div>
                    </div>
                    <div id="stockCount" style="text-align:center;padding:8px;color:var(--text-muted);font-size:12px;">
                        Showing 100 of {total_stock_count} items &bull; Type to search all
                    </div>
                </div>
            </div>
            
            <!-- Cart Panel -->
            <div class="pos-cart">
                <div class="pos-cart-header">
                    <span class="pos-cart-title">🛒 Cart</span>
                    <div style="display:flex;align-items:center;gap:10px;">
                        <button id="btnAddItem" onclick="showCustomItemModal()" style="background:#8b5cf6;color:white;border:none;padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer;" title="Add custom/once-off item">+ Custom</button>
                        <span class="pos-cart-count" id="cartCount">0 items</span>
                    </div>
                </div>
                
                <div class="pos-cart-items" id="cartItems">
                    <div class="pos-empty">
                        <div class="pos-empty-icon">🛒</div>
                        <div>Cart is empty</div>
                        <div style="font-size:12px;margin-top:5px;">Click items to add</div>
                    </div>
                </div>
                
                <div class="pos-totals">
                    <div class="pos-total-row">
                        <span>Subtotal (excl VAT)</span>
                        <span id="subtotal">R0.00</span>
                    </div>
                    <div class="pos-total-row">
                        <span>VAT (15%)</span>
                        <span id="vatAmount">R0.00</span>
                    </div>
                    <div class="pos-total-row grand">
                        <span>TOTAL</span>
                        <span id="grandTotal">R0.00</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Shortcuts Bar -->
        <div class="pos-shortcuts">
            <span><kbd>Type</kbd> Search</span>
            <span><kbd>Enter</kbd> Add first result</span>
            <span><kbd>5*CODE</kbd> Add 5 pcs</span>
            <span><kbd>↑↓</kbd> Navigate</span>
            <span><kbd>F1</kbd> Cash</span>
            <span><kbd>F2</kbd> Card</span>
            <span><kbd>F3</kbd> Account</span>
            <span><kbd>F4</kbd> Quote</span>
            <span><kbd>F5</kbd> PO</span>
            <span><kbd>F6</kbd> Invoice</span>
            <span><kbd>F7</kbd> Edit Cust</span>
            <span><kbd>F8</kbd> Cust</span>
            <span><kbd>F9</kbd> Supp</span>
            <span><kbd>F10</kbd> Credit</span>
            <span><kbd>ESC</kbd> Clear</span>
        </div>
        '''
        
        pos_js = '''
        <script>
        // === F-KEY INTERCEPTOR (capture phase — fires BEFORE browser defaults like F1=Help) ===
        document.addEventListener('keydown', function(e) {
            if (['F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11'].includes(e.key)) {
                e.preventDefault();
                // Do NOT stopPropagation — let the POS keydown handler still receive it
            }
        }, true);  // true = capture phase
        </script>
        <script>
        let cart = [];
        let selectedRowIndex = -1;
        let currentCashierId = null;
        let currentCashierName = null;
        
        // Initialize cashier - restore from cookie or use logged-in user
        document.addEventListener('DOMContentLoaded', function() {
            const myUid = '{_safe_uid}';
            const myName = '{_safe_uname}';
            
            const savedCashier = document.cookie.split(';').find(c => c.trim().startsWith('pos_cashier='));
            if (savedCashier) {
                const uid = savedCashier.split('=')[1];
                const btn = document.querySelector('.cashier-btn[data-uid="' + uid + '"]');
                if (btn) {
                    // Cookie cashier exists as a valid team member — use it
                    document.querySelectorAll('.cashier-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentCashierId = uid;
                    currentCashierName = btn.textContent.trim();
                    return;
                }
                // Cookie cashier not found in team — clear stale cookie, fall through to default
                document.cookie = 'pos_cashier=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
            }
            // Default: use the logged-in user's own button, or set their ID directly
            const myBtn = document.querySelector('.cashier-btn[data-uid="' + myUid + '"]');
            if (myBtn) {
                document.querySelectorAll('.cashier-btn').forEach(b => b.classList.remove('active'));
                myBtn.classList.add('active');
                currentCashierId = myUid;
                currentCashierName = myBtn.textContent.trim();
            } else {
                // No button for this user — just use their ID
                currentCashierId = myUid;
                currentCashierName = myName;
            }
        });
        
        function switchCashier(btn, uid, name) {
            document.querySelectorAll('.cashier-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentCashierId = uid;
            currentCashierName = name;
            // Save to cookie - expires end of day
            const midnight = new Date(); midnight.setHours(23,59,59);
            document.cookie = `pos_cashier=${uid};expires=${midnight.toUTCString()};path=/`;
        }
        
        function addToCart(id, code, desc, price, stock) {
            if (stock <= 0) {
                if (!confirm('Warning: Stock is ' + stock + ' - add anyway?')) {
                    return;
                }
            }
            
            const existing = cart.find(item => item.id === id);
            if (existing) {
                existing.qty++;
            } else {
                cart.push({id, code, desc, price, qty: 1, maxQty: 99999});
            }
            
            updateCart();
            
            // Visual feedback
            showAddedFeedback(code);
        }
        
        function showAddedFeedback(code) {
            // Reactor flash on the row
            const row = document.querySelector(`tr[data-code="${code}"]`);
            if (row) {
                row.classList.remove('just-added');
                void row.offsetWidth; // force reflow
                row.classList.add('just-added');
                setTimeout(() => row.classList.remove('just-added'), 500);
            }
        }
        
        async function addBulkToCart(event, id, code, desc, price, stock) {
            event.stopPropagation();
            
            const qtyStr = await posPrompt('Enter quantity for ' + code + ':', '10');
            if (qtyStr === null) return;
            
            const qty = parseInt(qtyStr);
            if (isNaN(qty) || qty <= 0) {
                alert('Invalid quantity');
                return;
            }
            
            if (qty > stock && stock > 0) {
                if (!confirm('Warning: Only ' + stock + ' in stock - add ' + qty + ' anyway?')) {
                    return;
                }
            }
            
            const existing = cart.find(item => item.id === id);
            if (existing) {
                existing.qty += qty;
            } else {
                cart.push({id, code, desc, price, qty: qty, maxQty: 99999});
            }
            
            updateCart();
            showAddedFeedback(code);
        }
        
        function updateQty(id, delta) {
            const item = cart.find(i => i.id === id);
            if (!item) return;
            
            item.qty += delta;
            
            if (item.qty <= 0) {
                cart = cart.filter(i => i.id !== id);
            }
            
            updateCart();
        }
        
        function removeFromCart(id) {
            cart = cart.filter(i => i.id !== id);
            updateCart();
        }
        
        async function setQty(id) {
            const item = cart.find(i => i.id === id);
            if (!item) return;
            
            const newQty = await posPrompt('Enter quantity:', item.qty);
            if (newQty === null) return;
            
            const qty = parseInt(newQty);
            if (isNaN(qty) || qty < 0) {
                alert('Invalid quantity');
                return;
            }
            
            if (qty === 0) {
                cart = cart.filter(i => i.id !== id);
            } else {
                item.qty = qty;
            }
            
            updateCart();
        }
        
        function updateCart() {
            const container = document.getElementById('cartItems');
            const count = document.getElementById('cartCount');
            
            if (cart.length === 0) {
                container.innerHTML = `
                    <div class="pos-empty">
                        <div class="pos-empty-icon">🛒</div>
                        <div>Cart is empty</div>
                        <div style="font-size:12px;margin-top:5px;">Click items to add</div>
                    </div>
                `;
                count.textContent = '0 items';
                document.getElementById('subtotal').textContent = 'R0.00';
                document.getElementById('vatAmount').textContent = 'R0.00';
                document.getElementById('grandTotal').textContent = 'R0.00';
                document.getElementById('headerTotal').textContent = 'R0.00';
                if (typeof renderF11Table === 'function' && f11Mode) { renderF11Table(); syncF11Buttons(); }
                document.getElementById('btnCash').disabled = true;
                document.getElementById('btnCard').disabled = true;
                // Account/Invoice - enabled if customer selected (will show "cart empty" message)
                const hasCustomer = !!document.getElementById('entityValue').value;
                document.getElementById('btnAccount').disabled = !hasCustomer;
                document.getElementById('btnQuote').disabled = true;
                document.getElementById('btnInvoice').disabled = !hasCustomer;
                document.getElementById('btnPO').disabled = true;
                document.getElementById('btnCredit').disabled = true;
                return;
            }
            
            let html = '';
            let total = 0;
            let itemCount = 0;
            
            cart.forEach(item => {
                const lineTotal = item.price * item.qty;
                total += lineTotal;
                itemCount += item.qty;
                
                html += `
                    <div class="cart-item">
                        <div class="cart-item-info">
                            <div class="cart-item-name">${item.desc}</div>
                            <div class="cart-item-code">${item.code}</div>
                            <div class="cart-item-price">R${item.price.toFixed(2)} each</div>
                        </div>
                        <div class="cart-item-qty">
                            <button class="cart-qty-btn minus" onclick="updateQty('${item.id}', -1)">−</button>
                            <span class="cart-qty-display" onclick="setQty('${item.id}')" title="Click to edit">${item.qty}</span>
                            <button class="cart-qty-btn" onclick="updateQty('${item.id}', 1)">+</button>
                        </div>
                        <div class="cart-item-total">R${lineTotal.toFixed(2)}</div>
                        <button class="cart-del-btn" onclick="removeFromCart('${item.id}')" title="Remove">✕</button>
                    </div>
                `;
            });
            
            container.innerHTML = html;
            count.textContent = itemCount + ' item' + (itemCount !== 1 ? 's' : '');
            
            // Round to nearest cent
            // 'total' here is sum of line items (qty × price) - prices are EXCL VAT
            let subtotal = Math.round(total * 100) / 100;
            const vat = Math.round(subtotal * 0.15 * 100) / 100;  // ADD 15% VAT
            const grandTotal = Math.round((subtotal + vat) * 100) / 100;
            
            document.getElementById('subtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('vatAmount').textContent = 'R' + vat.toFixed(2);
            document.getElementById('grandTotal').textContent = 'R' + grandTotal.toFixed(2);
            document.getElementById('headerTotal').textContent = 'R' + grandTotal.toFixed(2);
            // Sync F11 view
            if (typeof renderF11Table === 'function' && f11Mode) { renderF11Table(); syncF11Buttons(); updateF11CustName(); }
            
            document.getElementById('btnCash').disabled = false;
            document.getElementById('btnCard').disabled = false;
            document.getElementById('btnAccount').disabled = !document.getElementById('entityValue').value;
            document.getElementById('btnQuote').disabled = false;
            document.getElementById('btnInvoice').disabled = !document.getElementById('entityValue').value;
            document.getElementById('btnCredit').disabled = !document.getElementById('entityValue').value;
            document.getElementById('btnPO').disabled = false;
        }
        
        // Searchable Entity Dropdown
        let currentEntityType = 'customer';
        let dropdownOpen = false;
        let entityData = [];
        let highlightedIndex = -1;
        
        // Load data on page load
        function loadEntityData() {
            const custData = document.getElementById('customerData').value.replace(/&#39;/g, "'");
            const suppData = document.getElementById('supplierData').value.replace(/&#39;/g, "'");
            window.customerList = JSON.parse(custData);
            window.supplierList = JSON.parse(suppData);
            entityData = window.customerList;
        }
        
        // Remember customer selection when switching to supplier
        let lastCustomerId = '';
        let lastCustomerName = '';
        let lastSupplierId = '';
        let lastSupplierName = '';
        
        function toggleEntity(type) {
            // In F11 mode, show the entity bar (normally hidden)
            if (f11Mode) {
                var ebar = document.querySelector('.pos-entity-bar');
                if (ebar) ebar.style.display = 'flex';
            }
            const btnCust = document.getElementById('btnCust');
            const btnSupp = document.getElementById('btnSupp');
            const searchInput = document.getElementById('entitySearch');
            const valueInput = document.getElementById('entityValue');
            const btnAddItem = document.getElementById('btnAddItem');
            
            // Save current selection before switching
            if (currentEntityType === 'customer' && valueInput.value) {
                lastCustomerId = valueInput.value;
                lastCustomerName = searchInput.value;
            } else if (currentEntityType === 'supplier' && valueInput.value) {
                lastSupplierId = valueInput.value;
                lastSupplierName = searchInput.value;
            }
            
            currentEntityType = type;
            
            if (type === 'customer') {
                btnCust.classList.add('active');
                btnSupp.classList.remove('active');
                entityData = window.customerList || [];
                searchInput.placeholder = 'Countersale';
                // Update add item button for sales
                if (btnAddItem) {
                    btnAddItem.textContent = '+ Custom';
                    btnAddItem.title = 'Add custom/once-off item';
                }
                // Restore last customer if available
                if (lastCustomerId) {
                    searchInput.value = lastCustomerName;
                    valueInput.value = lastCustomerId;
                    return; // Don't open dropdown
                }
            } else {
                btnSupp.classList.add('active');
                btnCust.classList.remove('active');
                entityData = window.supplierList || [];
                searchInput.placeholder = 'Select Supplier';
                // Update add item button for PO
                if (btnAddItem) {
                    btnAddItem.textContent = '+ PO Item';
                    btnAddItem.title = 'Add item to order - no price needed';
                    btnAddItem.style.background = '#f59e0b';  // Orange for PO
                }
                // Restore last supplier if available
                if (lastSupplierId) {
                    searchInput.value = lastSupplierName;
                    valueInput.value = lastSupplierId;
                    return; // Don't open dropdown
                }
            }
            
            // Clear and open
            searchInput.value = '';
            valueInput.value = '';
            openEntityDropdown();
        }
        
        // Get current customer (even if supplier is selected)
        function getCurrentCustomer() {
            let id = '';
            let name = '';
            if (currentEntityType === 'customer') {
                id = document.getElementById('entityValue').value;
                name = document.getElementById('entitySearch').value;
            } else {
                id = lastCustomerId;
                name = lastCustomerName;
            }
            // Look up full customer details from data
            let address = '', phone = '', vat_number = '', email = '';
            if (id) {
                try {
                    const customers = JSON.parse(document.getElementById('customerData').value.replace(/&#39;/g, "'"));
                    const found = customers.find(c => c.id === id);
                    if (found) {
                        address = found.address || '';
                        phone = found.phone || '';
                        vat_number = found.vat_number || '';
                        email = found.email || '';
                        if (!name) name = found.name || '';
                    }
                } catch(e) {}
            }
            return { id, name, address, phone, vat_number, email };
        }
        
        // Get current supplier (even if customer is selected)
        function getCurrentSupplier() {
            if (currentEntityType === 'supplier') {
                return {
                    id: document.getElementById('entityValue').value,
                    name: document.getElementById('entitySearch').value
                };
            }
            return { id: lastSupplierId, name: lastSupplierName };
        }
        
        function openEntityDropdown() {
            const list = document.getElementById('entityList');
            const searchInput = document.getElementById('entitySearch');
            dropdownOpen = true;
            highlightedIndex = -1;
            renderEntityList('');
            list.style.display = 'block';
            searchInput.focus();
        }
        
        function closeEntityDropdown(keepValue = true) {
            const list = document.getElementById('entityList');
            const searchInput = document.getElementById('entitySearch');
            list.style.display = 'none';
            dropdownOpen = false;
            highlightedIndex = -1;
            if (!keepValue) {
                searchInput.value = '';
                document.getElementById('entityValue').value = '';
            }
            if (f11Mode) {
                // Hide entity bar overlay in F11 mode
                var ebar = document.querySelector('.pos-entity-bar');
                if (ebar) ebar.style.display = 'none';
                if (typeof updateF11CustName === 'function') updateF11CustName();
                var f11El = document.getElementById('f11Search');
                if (f11El) f11El.focus();
            } else {
                document.getElementById('stockSearch').focus();
            }
        }
        
        function renderEntityList(filter) {
            const list = document.getElementById('entityList');
            const lowerFilter = filter.toLowerCase();
            
            let html = '';
            let visibleCount = 0;
            entityData.forEach((item, idx) => {
                const name = item.name || '';
                if (lowerFilter === '' || name.toLowerCase().includes(lowerFilter)) {
                    const isNew = item.id === 'NEW';
                    const highlighted = idx === highlightedIndex ? 'highlighted' : '';
                    html += '<div class="entity-item ' + (isNew ? 'new-item ' : '') + highlighted + '" data-id="' + (item.id || '') + '" data-name="' + name + '" data-idx="' + idx + '" onclick="selectEntity(this)">' + name + '</div>';
                    visibleCount++;
                }
            });
            
            if (visibleCount === 0) {
                html = '<div class="entity-item" style="color:#888;">No matches</div>';
            }
            list.innerHTML = html;
        }
        
        async function selectEntity(el) {
            const id = el.dataset.id;
            const name = el.dataset.name;
            
            // Handle "Add New" option
            if (id === 'NEW') {
                const entityType = currentEntityType === 'customer' ? 'Customer' : 'Supplier';
                const newName = await posPrompt('👤 ' + entityType + ' name:', '');
                if (newName && newName.trim()) {
                    const endpoint = currentEntityType === 'customer' ? '/api/customer/quick-add' : '/api/supplier/quick-add';
                    fetch(endpoint, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({name: newName.trim()})
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            document.getElementById('entitySearch').value = newName.trim();
                            document.getElementById('entityValue').value = data.id;
                            // Add to list
                            const newItem = {id: data.id, name: newName.trim()};
                            if (currentEntityType === 'customer') {
                                window.customerList.push(newItem);
                            } else {
                                window.supplierList.push(newItem);
                            }
                            closeEntityDropdown(true);
                            // Enable buttons now that customer is selected!
                            document.getElementById('btnAccount').disabled = false;
                            document.getElementById('btnInvoice').disabled = false;
                        } else {
                            alert('Failed: ' + (data.error || 'Unknown error'));
                        }
                    })
                    .catch(err => {
                        // Offline: queue customer for later sync
                        if (!navigator.onLine || err.message.includes('fetch') || err.message.includes('network')) {
                            const tempId = 'OFFLINE_' + Date.now();
                            if (window.queueOfflineItem) {
                                window.queueOfflineItem('customer_queue', {
                                    name: newName.trim(), type: currentEntityType,
                                    offline_date: new Date().toISOString()
                                }).then(() => {
                                    // Use temp ID locally so they can still make sales
                                    document.getElementById('entitySearch').value = newName.trim();
                                    document.getElementById('entityValue').value = '';
                                    const newItem = {id: '', name: newName.trim()};
                                    if (currentEntityType === 'customer') window.customerList.push(newItem);
                                    else window.supplierList.push(newItem);
                                    closeEntityDropdown(true);
                                    alert('📴 ' + newName.trim() + ' saved offline. Will sync when internet returns.');
                                }).catch(() => alert('Could not save offline'));
                            } else { alert('Error: ' + err.message); }
                        } else { alert('Error: ' + err.message); }
                    });
                }
                return;
            }
            
            document.getElementById('entitySearch').value = name;
            document.getElementById('entityValue').value = id;
            closeEntityDropdown(true);
            
            // Update button states - Invoice/Account/Credit need customer, cart can be empty (will show message)
            document.getElementById('btnAccount').disabled = !id;
            document.getElementById('btnInvoice').disabled = !id;
            document.getElementById('btnCredit').disabled = !id || cart.length === 0;
        }
        
        function navigateEntityList(direction) {
            const items = document.querySelectorAll('.entity-item[data-idx]');
            if (items.length === 0) return;
            
            // Remove old highlight
            items.forEach(i => i.classList.remove('highlighted'));
            
            // Find visible indices
            const visibleIndices = Array.from(items).map(i => parseInt(i.dataset.idx));
            const currentPos = visibleIndices.indexOf(highlightedIndex);
            
            let newPos = currentPos + direction;
            if (newPos < 0) newPos = visibleIndices.length - 1;
            if (newPos >= visibleIndices.length) newPos = 0;
            
            highlightedIndex = visibleIndices[newPos];
            
            // Highlight new item
            const newItem = document.querySelector('.entity-item[data-idx="' + highlightedIndex + '"]');
            if (newItem) {
                newItem.classList.add('highlighted');
                newItem.scrollIntoView({ block: 'nearest' });
            }
        }
        
        function selectHighlightedEntity() {
            const item = document.querySelector('.entity-item.highlighted');
            if (item && item.dataset.id !== undefined) {
                selectEntity(item);
            }
        }
        
        // Entity search input handler
        document.addEventListener('DOMContentLoaded', function() {
            loadEntityData();
            
            const entitySearch = document.getElementById('entitySearch');
            entitySearch.addEventListener('input', function() {
                renderEntityList(this.value);
                highlightedIndex = -1;
            });
            
            entitySearch.addEventListener('keydown', function(e) {
                if (!dropdownOpen) return;
                
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    navigateEntityList(1);
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    navigateEntityList(-1);
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    selectHighlightedEntity();
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    closeEntityDropdown(false);
                }
            });
            
            entitySearch.addEventListener('focus', function() {
                if (!dropdownOpen) openEntityDropdown();
            });
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (dropdownOpen && !e.target.closest('.entity-dropdown') && !e.target.closest('.pos-entity-btn') && !e.target.closest('.f11-btn')) {
                closeEntityDropdown(true);
            }
        });
        
        function clearCart() {
            cart = [];
            updateCart();
        }
        
        function filterStock() {
            if (window.isNavigating) { window.isNavigating = false; return; }
            window.originalSearch = null;
            
            const raw = document.getElementById('stockSearch').value;
            let search = raw.toLowerCase().trim();
            const rows = document.querySelectorAll('.stock-row');
            const noResults = document.getElementById('noResults');
            
            if (search.match(/^\d+\*\s*/)) {
                search = search.replace(/^\d+\*\s*/, '');
            }
            search = search.replace(/\s*[xX]\s*/g, 'x');
            
            selectedRowIndex = -1;
            
            if (search === '') {
                let v = 0;
                rows.forEach((row, i) => {
                    if (v < 500) { row.style.display = ''; v++; if (selectedRowIndex === -1) selectedRowIndex = i; }
                    else { row.style.display = 'none'; }
                });
                const el = document.getElementById('stockCount');
                if (el) { el.style.display = ''; el.textContent = 'Showing ' + v + ' of ' + rows.length + ' items \u2022 Type to search all'; }
                noResults.classList.remove('show');
                rows.forEach(r => r.classList.remove('highlighted'));
                return;
            }
            
            const tokens = search.split(/\s+/).filter(t => t.length > 0);
            
            let visibleCount = 0;
            rows.forEach((row, index) => {
                const haystack = ((row.getAttribute('data-code') || '') + ' ' + (row.getAttribute('data-desc') || '')).toLowerCase().replace(/\s*[xX]\s*/g, 'x');
                if (tokens.every(t => haystack.indexOf(t) !== -1)) {
                    row.style.display = '';
                    visibleCount++;
                    if (selectedRowIndex === -1) selectedRowIndex = index;
                } else {
                    row.style.display = 'none';
                }
            });
            
            const stockCountEl = document.getElementById('stockCount');
            if (visibleCount === 0) {
                noResults.classList.add('show');
                if (stockCountEl) stockCountEl.style.display = 'none';
            } else {
                noResults.classList.remove('show');
                if (stockCountEl) { stockCountEl.style.display = ''; stockCountEl.textContent = visibleCount + ' matches'; }
            }
            rows.forEach(r => r.classList.remove('highlighted'));
        }
        function highlightRow() {
            const rows = document.querySelectorAll('.stock-row');
            rows.forEach((row, index) => {
                row.classList.remove('highlighted');
                if (index === selectedRowIndex && row.style.display !== 'none') {
                    row.classList.add('highlighted');
                }
            });
        }
        
        let posLocked = false;
        
        async function completeSale(method) {
            if (cart.length === 0) {
                alert('🛒 Cart is empty!\\n\\nAdd items to cart first.\\n\\nTip: Search for stock items above and click to add them.');
                document.getElementById('stockSearch').focus();
                return;
            }
            
            // Prevent double submission (any POS transaction)
            if (posLocked) {
                console.log('[POS] Transaction already in progress, ignoring');
                return;
            }
            posLocked = true;
            
            // Use getCurrentCustomer - works even if supplier is selected
            const customer = getCurrentCustomer();
            const customerId = customer.id;
            const customerName = customer.name || ('Countersale ' + ({cash:'Cash',card:'Card',account:'Account'}[method]||'') + (currentCashierName ? ' - '+currentCashierName : ''));
            
            if (method === 'account' && !customerId) {
                alert('Warning: Please select a customer for account sale (F8)');
                toggleEntity('customer');
                posLocked = false;
                return;
            }
            
            // Calculate totals — prices are EXCL VAT
            let subtotal = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
            subtotal = Math.round(subtotal * 100) / 100;
            const vat = Math.round(subtotal * 0.15 * 100) / 100;
            const grandTotal = Math.round((subtotal + vat) * 100) / 100;
            const itemCount = cart.reduce((sum, item) => sum + item.qty, 0);
            
            let cashReceived = 0;
            let changeGiven = 0;
            
            if (method === 'cash') {
                const received = await posPrompt('CASH R' + grandTotal.toFixed(2) + ' (' + itemCount + ' items) — Cash received:', grandTotal.toFixed(2));
                if (received === null) { posLocked = false; return; }
                cashReceived = parseFloat(received);
                if (isNaN(cashReceived) || cashReceived < 0) { alert('Invalid amount'); posLocked = false; return; }
                changeGiven = cashReceived - grandTotal;
                if (changeGiven < -0.01) { alert('Short R' + Math.abs(changeGiven).toFixed(2)); posLocked = false; return; }
            } else if (method === 'card') {
                // Card — no prompt needed, just go
            } else if (method === 'account') {
                // Account — customer already selected
            }
            
            const items = cart.map(item => ({
                stock_id: (item.isCustom || item.isPOItem) ? null : item.id,
                code: item.code,
                description: item.desc,
                quantity: item.qty,
                price: item.price,
                total: item.price * item.qty
            }));
            
            try {
                const response = await fetch('/api/pos/sale', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        items: items,
                        customer_id: customerId,
                        customer_name: customerName,
                        payment_method: method,
                        subtotal: subtotal,
                        vat: vat,
                        total: grandTotal,
                        cashier_id: currentCashierId,
                        cashier_name: currentCashierName
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Show print dialog based on settings - pass cash info and customer details
                    showPrintDialog(data.sale_number, data.sale_id, method, customer, items, subtotal, vat, grandTotal, cashReceived, changeGiven);
                    clearCart();
                    // posLocked will be reset on page reload after print
                } else {
                    alert('Error: ' + (data.error || 'Sale failed'));
                    posLocked = false;
                }
            } catch (err) {
                // ═══ OFFLINE MODE: Queue sale locally instead of losing it ═══
                if (!navigator.onLine || err.message.includes('fetch') || err.message.includes('network') || err.message.includes('Network')) {
                    try {
                        await queueOfflineSale({
                            items: items,
                            customer_id: customerId,
                            customer_name: customerName,
                            payment_method: method,
                            subtotal: subtotal,
                            vat: vat,
                            total: grandTotal,
                            cashier_id: currentCashierId,
                            cashier_name: currentCashierName,
                            offline_date: new Date().toISOString().slice(0,10),
                            offline_time: new Date().toISOString()
                        });
                        
                        const offlineNum = 'OFF' + Date.now().toString().slice(-6);
                        
                        // ═══ STILL PRINT — LAN printer works without internet ═══
                        showPrintDialog(offlineNum, '', method, customer, items, subtotal, vat, grandTotal, cashReceived, changeGiven);
                        clearCart();
                        updateOfflineIndicator();
                    } catch (dbErr) {
                        alert('OFFLINE SAVE FAILED\\n\\nCould not save sale locally.\\n\\nPlease write down:\\nTotal: R' + grandTotal.toFixed(2) + ' (' + method + ')');
                    }
                } else {
                    alert('Connection error: ' + err.message);
                }
                posLocked = false;
            }
        }
        
        async function createQuote() {
            if (posLocked) { console.log('[POS] Transaction in progress'); return; }
            const customer = getCurrentCustomer();
            const customerId = customer.id;
            const customerName = customer.name || '';
            
            // LOGIC:
            // Cart empty + no customer = Quick Quote (once-off, new customer)
            // Cart empty + customer selected = Quick Quote with custom items for this customer
            // Cart has items + no customer = Quick Customer modal
            // Cart has items + customer = Normal quote with stock items
            
            if (cart.length === 0) {
                // Show quick quote modal - pass customer if selected
                showQuickQuoteModal(customerId, customerName);
                return;
            }
            
            // Cart has items
            if (!customerId) {
                // Show quick customer modal instead of just alert
                showQuickCustomerModal();
                return;
            }
            
            // Cart has items AND customer selected - create quote with stock items
            const items = cart.map(item => ({
                stock_id: (item.isCustom || item.isPOItem) ? null : item.id,
                code: item.code,
                description: item.desc,
                quantity: item.qty,
                price: item.price,
                total: item.price * item.qty
            }));
            
            // Prices are EXCL VAT - ADD VAT
            const subtotal = Math.round(items.reduce((sum, item) => sum + item.total, 0) * 100) / 100;
            const vat = Math.round(subtotal * 0.15 * 100) / 100;
            const grandTotal = Math.round((subtotal + vat) * 100) / 100;
            
            try {
                const response = await fetch('/api/pos/quote', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        items: items,
                        customer_id: customerId,
                        customer_name: customerName,
                        subtotal: subtotal,
                        vat: vat,
                        total: grandTotal,
                        cashier_id: currentCashierId,
                        cashier_name: currentCashierName
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Quote ' + data.quote_number + ' created!');
                    clearCart();
                    if (confirm('Open quote now?')) {
                        window.location = '/quote/' + data.quote_id;
                    }
                } else {
                    alert('Error: ' + (data.error || 'Quote failed'));
                }
            } catch (err) {
                if (!navigator.onLine || err.message.includes('fetch') || err.message.includes('network') || err.message.includes('Network')) {
                    try {
                        await (window.queueOfflineItem || queueOfflineSale)('quote_queue', {
                            items: items, customer_id: customerId, customer_name: customerName,
                            subtotal: subtotal, vat: vat, total: grandTotal,
                            offline_date: new Date().toISOString().slice(0,10), offline_time: new Date().toISOString()
                        });
                        alert('📴 OFFLINE QUOTE SAVED\\n\\nFor: ' + (customerName || 'Walk-in') + '\\nTotal: R' + grandTotal.toFixed(2) + '\\n\\nWill sync when internet returns.');
                        clearCart();
                    } catch(e) { alert('Could not save quote offline'); }
                } else { alert('Connection error: ' + err.message); }
            }
        }
        
        async function createInvoice() {
            if (cart.length === 0) {
                alert('🛒 Cart is empty!\\n\\nAdd items to cart first, then click Invoice.\\n\\nTip: Search for stock items above and click to add them.');
                document.getElementById('stockSearch').focus();
                return;
            }
            
            // Prevent double submission (any POS transaction)
            if (posLocked) {
                console.log('[POS] Transaction already in progress, ignoring');
                return;
            }
            posLocked = true;
            
            // Use getCurrentCustomer - works even if supplier is selected
            const customer = getCurrentCustomer();
            const customerId = customer.id;
            const customerName = customer.name || '';
            
            if (!customerId) {
                alert('Warning: Please select a customer for the invoice (F8)');
                toggleEntity('customer');
                posLocked = false;
                return;
            }
            let subtotal = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
            subtotal = Math.round(subtotal * 100) / 100;
            const vat = Math.round(subtotal * 0.15 * 100) / 100;
            const grandTotal = Math.round((subtotal + vat) * 100) / 100;
            const itemCount = cart.reduce((sum, item) => sum + item.qty, 0);
            
            let preview = '═══════════════════════\\n';
            preview += 'INVOICE PREVIEW\\n';
            preview += '═══════════════════════\\n\\n';
            preview += 'Customer: ' + customerName + '\\n';
            preview += '───────────────────────\\n';
            
            cart.forEach(item => {
                const lineTotal = item.price * item.qty;
                preview += item.qty + 'x ' + item.code + '\\n';
                preview += '   @ R' + item.price.toFixed(2) + ' = R' + lineTotal.toFixed(2) + '\\n';
            });
            
            preview += '───────────────────────\\n';
            preview += 'Subtotal: R' + subtotal.toFixed(2) + '\\n';
            preview += 'VAT (15%): R' + vat.toFixed(2) + '\\n';
            preview += 'TOTAL: R' + grandTotal.toFixed(2) + ' (' + itemCount + ' items)\\n';
            preview += '═══════════════════════\\n\\n';
            preview += 'Create invoice?';
            
            if (!confirm(preview)) {
                posLocked = false;
                return;
            }
            
            const items = cart.map(item => ({
                stock_id: (item.isCustom || item.isPOItem) ? null : item.id,
                code: item.code,
                description: item.desc,
                quantity: item.qty,
                price: item.price,
                total: item.price * item.qty
            }));
            
            try {
                const response = await fetch('/api/pos/invoice', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        items: items,
                        customer_id: customerId,
                        customer_name: customerName,
                        subtotal: subtotal,
                        vat: vat,
                        total: grandTotal,
                        cashier_id: currentCashierId,
                        cashier_name: currentCashierName
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Invoice ' + data.invoice_number + ' created!');
                    clearCart();
                    posLocked = false;
                    if (confirm('Open invoice now?')) {
                        window.location = '/invoice/' + data.invoice_id;
                    }
                } else {
                    alert('Error: ' + (data.error || 'Invoice failed'));
                    posLocked = false;
                }
            } catch (err) {
                alert('Connection error — Invoices require internet for sequential numbering.');
                posLocked = false;
            }
        }
        
        async function createPO() {
            if (posLocked) { console.log('[POS] Transaction in progress'); return; }
            
            // ALWAYS switch to supplier mode first — GRV/PO needs a supplier, not customer
            if (currentEntityType !== 'supplier') {
                toggleEntity('supplier');
            }
            
            const supplier = getCurrentSupplier();
            const supplierId = supplier.id;
            const supplierName = supplier.name || '';
            
            // LOGIC:
            // Cart empty + no supplier = Quick PO (once-off, new supplier)
            // Cart empty + supplier selected = Quick PO with custom items for this supplier
            // Cart has items + no supplier = Ask to select supplier
            // Cart has items + supplier = Normal PO with stock items
            
            if (cart.length === 0) {
                // Show quick PO modal - pass supplier if selected
                showQuickPOModal(supplierId, supplierName);
                return;
            }
            
            // Cart has items
            if (!supplierId) {
                // Switch to supplier mode and ask
                toggleEntity('supplier');
                alert('Select a supplier for the PO (F9)');
                return;
            }
            
            // Cart has items AND supplier selected - create PO with stock items
            // Ask for reference name (who is ordering)
            const poRef = await posPrompt('Reference name for PO (e.g. person ordering):', currentCashierName || '');
            if (poRef === null) return; // cancelled
            
            // PO items - NO PRICES (supplier must not see our selling prices)
            const items = cart.map(item => ({
                stock_id: (item.isCustom || item.isPOItem) ? null : item.id,
                code: item.code,
                description: item.desc,
                qty: item.qty
            }));
            
            try {
                const response = await fetch('/api/pos/purchase-order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        items: items,
                        supplier_id: supplierId,
                        supplier_name: supplierName,
                        reference: poRef
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    clearCart();
                    
                    // Offer options: View, Email, or Done
                    const choice = prompt(
                        'PO ' + data.po_number + ' created!\\n\\n' +
                        'What would you like to do?\\n\\n' +
                        '1 = Open PO\\n' +
                        '2 = Email to Supplier\\n' +
                        '3 = Done\\n\\n' +
                        'Enter 1, 2, or 3:',
                        '2'
                    );
                    
                    if (choice === '1') {
                        window.location = '/purchase/' + data.po_id;
                    } else if (choice === '2') {
                        // Email PO directly
                        try {
                            const emailResp = await fetch('/api/purchase/' + data.po_id + '/email', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})});
                            const emailData = await emailResp.json();
                            if (emailData.success) {
                                alert('✅ ' + emailData.message);
                            } else {
                                alert('❌ ' + emailData.error + '\\n\\nOpen PO to add supplier email.');
                                window.location = '/purchase/' + data.po_id;
                            }
                        } catch(e) {
                            alert('Email error: ' + e.message);
                        }
                    }
                    // choice === '3' or cancelled = just stay on POS
                } else {
                    alert('Error: ' + (data.error || 'PO failed'));
                }
            } catch (err) {
                alert('Connection error');
            }
        }
        
        // ═══ CREDIT NOTE FROM POS ═══
        async function createCreditNote() {
            if (cart.length === 0) return;
            if (posLocked) { console.log('[POS] Transaction in progress'); return; }
            
            // Use getCurrentCustomer - works even if supplier is selected
            const customer = getCurrentCustomer();
            const customerId = customer.id;
            const customerName = customer.name || '';
            
            if (!customerId) {
                alert('Warning: Please select a customer for the credit note (F8)');
                toggleEntity('customer');
                return;
            }
            
            // Build preview - prices are EXCL VAT, ADD VAT
            let subtotal = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
            subtotal = Math.round(subtotal * 100) / 100;
            const vat = Math.round(subtotal * 0.15 * 100) / 100;
            const grandTotal = Math.round((subtotal + vat) * 100) / 100;
            const itemCount = cart.reduce((sum, item) => sum + item.qty, 0);
            
            let preview = '═══════════════════════\\n';
            preview += 'Warning: CREDIT NOTE PREVIEW\\n';
            preview += '═══════════════════════\\n\\n';
            preview += 'Customer: ' + customerName + '\\n';
            preview += '───────────────────────\\n';
            
            cart.forEach(item => {
                const lineTotal = item.price * item.qty;
                preview += item.qty + 'x ' + item.code + '\\n';
                preview += '   @ R' + item.price.toFixed(2) + ' = R' + lineTotal.toFixed(2) + '\\n';
            });
            
            preview += '───────────────────────\\n';
            preview += 'Subtotal: R' + subtotal.toFixed(2) + '\\n';
            preview += 'VAT (15%): R' + vat.toFixed(2) + '\\n';
            preview += 'CREDIT TOTAL: -R' + grandTotal.toFixed(2) + '\\n';
            preview += '═══════════════════════\\n\\n';
            preview += 'This will REDUCE customer balance.\\nCreate credit note?';
            
            if (!confirm(preview)) {
                return;
            }
            
            const items = cart.map(item => ({
                stock_id: (item.isCustom || item.isPOItem) ? null : item.id,
                code: item.code,
                description: item.desc,
                quantity: item.qty,
                price: item.price,
                total: item.price * item.qty
            }));
            
            try {
                const response = await fetch('/api/pos/credit-note', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        items: items,
                        customer_id: customerId,
                        customer_name: customerName,
                        subtotal: subtotal,
                        vat: vat,
                        total: grandTotal
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Credit Note ' + data.credit_note_number + ' created!\\nCustomer balance reduced by R' + grandTotal.toFixed(2));
                    clearCart();
                    if (confirm('View credit note?')) {
                        window.location = '/credit-note/' + data.credit_note_id;
                    }
                } else {
                    alert('Error: ' + (data.error || 'Credit note failed'));
                }
            } catch (err) {
                alert('Connection error');
            }
        }
        
        // ═══ KEYBOARD SHORTCUTS ═══
        document.addEventListener('keydown', function(e) {
            const activeEl = document.activeElement;
            const isSearchInput = activeEl.id === 'stockSearch';
            const isInput = activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA';
            const searchInput = document.getElementById('stockSearch');
            
            // ENTER - Add item (highlighted or first visible)
            if (e.key === 'Enter' && isSearchInput) {
                e.preventDefault();
                
                const raw = window.originalSearch || searchInput.value.trim();
                let qty = 1;
                let searchCode = raw;
                
                // Parse "5*code"
                const starPos = raw.indexOf('*');
                if (starPos > 0) {
                    const numPart = raw.substring(0, starPos);
                    const codePart = raw.substring(starPos + 1).trim();
                    const parsedQty = parseInt(numPart, 10);
                    if (parsedQty > 0) {
                        qty = parsedQty;
                        searchCode = codePart;
                    }
                }
                
                searchCode = searchCode.toLowerCase().replace(/\\s*x\\s*/gi, 'x');
                
                // Use highlighted row if exists, else first visible
                const highlighted = document.querySelector('.stock-row.highlighted');
                const rows = document.querySelectorAll('.stock-row');
                let found = highlighted;
                
                if (!found) {
                    for (let row of rows) {
                        if (row.style.display === 'none') continue;
                        if (searchCode === '') { found = row; break; }
                        let data = (row.getAttribute('data-search') || '').toLowerCase().replace(/\\s*x\\s*/gi, 'x');
                        if (data.indexOf(searchCode) !== -1) { found = row; break; }
                    }
                }
                
                if (found) {
                    const id = found.getAttribute('data-id');
                    const code = found.getAttribute('data-code');
                    const desc = found.getAttribute('data-desc');
                    const price = parseFloat(found.getAttribute('data-price')) || 0;
                    const stock = parseFloat(found.getAttribute('data-qty')) || 0;
                    
                    const existing = cart.find(item => item.id === id);
                    if (existing) {
                        existing.qty += qty;
                    } else {
                        cart.push({id, code, desc, price, qty: qty, maxQty: 99999});
                    }
                    updateCart();
                    showAddedFeedback(code);
                } else if (searchCode !== '') {
                    alert('Not found: ' + searchCode);
                }
                
                // Clear and reset
                searchInput.value = '';
                window.originalSearch = null;
                document.querySelectorAll('.stock-row').forEach(r => r.classList.remove('highlighted'));
                filterStock();
                searchInput.focus();
                return;
            }
            
            // Arrow keys for navigation
            if (e.key === 'ArrowDown' && isSearchInput) {
                e.preventDefault();
                navigateRows(1);
                return;
            }
            
            if (e.key === 'ArrowUp' && isSearchInput) {
                e.preventDefault();
                navigateRows(-1);
                return;
            }
            
            // F1 = Cash
            if (e.key === 'F1') {
                e.preventDefault();
                if (cart.length > 0) completeSale('cash');
                return;
            }
            
            // F2 = Card
            if (e.key === 'F2') {
                e.preventDefault();
                if (cart.length > 0) completeSale('card');
                return;
            }
            
            // F3 = Account
            if (e.key === 'F3') {
                e.preventDefault();
                if (cart.length > 0 && getCurrentCustomer().id) {
                    completeSale('account');
                } else if (cart.length > 0) {
                    alert('Warning: Select a customer for account sales (F8)');
                }
                return;
            }
            
            // F4 = Quote (works with empty cart too - opens Quick Quote)
            if (e.key === 'F4') {
                e.preventDefault();
                createQuote();
                return;
            }
            
            // F5 = PO (works with empty cart too - opens Quick PO)
            if (e.key === 'F5') {
                e.preventDefault();
                createPO();
                return;
            }
            
            // F6 = Invoice
            if (e.key === 'F6') {
                e.preventDefault();
                if (cart.length > 0 && getCurrentCustomer().id) {
                    createInvoice();
                } else if (cart.length > 0) {
                    alert('Warning: Select a customer for invoice (F8)');
                }
                return;
            }
            
            // F7 = Edit Customer Details
            if (e.key === 'F7') {
                e.preventDefault();
                showEditCustomerModal();
                return;
            }
            
            // F8 = Customers
            if (e.key === 'F8') {
                e.preventDefault();
                toggleEntity('customer');
                return;
            }
            
            // F9 = Suppliers
            if (e.key === 'F9') {
                e.preventDefault();
                toggleEntity('supplier');
                return;
            }
            
            // F10 = Credit Note
            if (e.key === 'F10') {
                e.preventDefault();
                if (cart.length > 0 && getCurrentCustomer().id) {
                    createCreditNote();
                } else if (cart.length > 0) {
                    alert('Warning: Select a customer for credit note (F8)');
                }
                return;
            }
            
            // F11 = Toggle Fullscreen Order Mode
            if (e.key === 'F11') {
                e.preventDefault();
                toggleF11();
                return;
            }
            
            // ESC in F11 mode = exit fullscreen (if no dropdown/modal open)
            if (e.key === 'Escape' && f11Mode && !dropdownOpen) {
                e.preventDefault();
                toggleF11();
                return;
            }
            
            // === PRINT MODAL KEYBOARD HANDLING ===
            const printModal = document.getElementById('printSlipModal');
            if (printModal && printModal.style.display === 'flex') {
                const buttons = [
                    document.getElementById('btnPrintThermal'),
                    document.getElementById('btnPrintA4'),
                    document.getElementById('btnPrintSkip')
                ].filter(b => b);  // Filter out nulls
                
                if (buttons.length > 0) {
                    const currentIndex = buttons.findIndex(btn => btn === document.activeElement);
                    
                    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                        e.preventDefault();
                        e.stopPropagation();
                        const nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % buttons.length;
                        buttons[nextIndex].focus();
                        return;
                    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                        e.preventDefault();
                        e.stopPropagation();
                        const prevIndex = currentIndex < 0 ? 0 : (currentIndex - 1 + buttons.length) % buttons.length;
                        buttons[prevIndex].focus();
                        return;
                    } else if (e.key === 'Tab') {
                        e.preventDefault();
                        e.stopPropagation();
                        if (e.shiftKey) {
                            const prevIndex = currentIndex < 0 ? buttons.length - 1 : (currentIndex - 1 + buttons.length) % buttons.length;
                            buttons[prevIndex].focus();
                        } else {
                            const nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1) % buttons.length;
                            buttons[nextIndex].focus();
                        }
                        return;
                    } else if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        e.stopPropagation();
                        if (document.activeElement && buttons.includes(document.activeElement)) {
                            document.activeElement.click();
                        } else {
                            // Default to thermal print
                            buttons[0].click();
                        }
                        return;
                    } else if (e.key === 'Escape') {
                        e.preventDefault();
                        e.stopPropagation();
                        closePrintModal();
                        return;
                    } else if (e.key === '1') {
                        e.preventDefault();
                        e.stopPropagation();
                        doPrintSlip('thermal');
                        return;
                    } else if (e.key === '2') {
                        e.preventDefault();
                        e.stopPropagation();
                        doPrintSlip('a4');
                        return;
                    } else if (e.key === '3') {
                        e.preventDefault();
                        e.stopPropagation();
                        closePrintModal();
                        return;
                    }
                }
            }
            
            // ESC = Close dropdown first, then clear search, then cart
            if (e.key === 'Escape') {
                e.preventDefault();
                
                // If quick customer modal is open, close it first
                const quickCustModal = document.getElementById('quickCustomerModal');
                if (quickCustModal && quickCustModal.style.display === 'flex') {
                    closeQuickCustomerModal();
                    return;
                }
                
                // If custom item modal is open, close it first
                const customModal = document.getElementById('customItemModal');
                if (customModal && customModal.style.display === 'flex') {
                    closeCustomItemModal();
                    return;
                }
                
                // If entity dropdown is open, close it
                if (dropdownOpen) {
                    closeEntityDropdown(false);
                    return;
                }
                
                // If navigating or search has text, just clear search
                const hasHighlight = document.querySelector('.stock-row.highlighted');
                if (searchInput.value || hasHighlight || window.originalSearch) {
                    searchInput.value = '';
                    window.originalSearch = null;
                    document.querySelectorAll('.stock-row').forEach(r => r.classList.remove('highlighted'));
                    filterStock();
                    return;
                }
                
                // If search already empty, offer to clear cart
                if (cart.length > 0 && confirm('🗑️ Clear cart?')) {
                    clearCart();
                }
                return;
            }
            
            // Focus search on typing
            if (!isInput && /^[a-zA-Z0-9]$/.test(e.key)) {
                if (f11Mode) {
                    var f11El = document.getElementById('f11Search');
                    if (f11El) f11El.focus();
                } else {
                    searchInput.focus();
                }
            }
        }, true);
        
        function navigateRows(direction) {
            const rows = Array.from(document.querySelectorAll('.stock-row')).filter(r => r.style.display !== 'none');
            if (rows.length === 0) return;
            
            const searchInput = document.getElementById('stockSearch');
            
            // Store original search on first navigation
            if (window.originalSearch === undefined || window.originalSearch === null) {
                window.originalSearch = searchInput.value;
            }
            
            const currentIndex = rows.findIndex(r => r.classList.contains('highlighted'));
            let newIndex = currentIndex + direction;
            
            // If no highlight yet, start at first (down) or last (up)
            if (currentIndex === -1) {
                newIndex = direction > 0 ? 0 : rows.length - 1;
            }
            
            if (newIndex < 0) newIndex = rows.length - 1;
            if (newIndex >= rows.length) newIndex = 0;
            
            rows.forEach(r => r.classList.remove('highlighted'));
            rows[newIndex].classList.add('highlighted');
            rows[newIndex].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            
            // Show selected item in search bar (set flag to prevent filterStock)
            const code = rows[newIndex].getAttribute('data-code') || '';
            const desc = rows[newIndex].getAttribute('data-desc') || '';
            window.isNavigating = true;
            searchInput.value = code + ' - ' + desc;
        }
        
        // Initial focus
        document.getElementById('stockSearch').focus();
        
        // === CUSTOM ITEM FUNCTIONS ===
        function showCustomItemModal(forPO = false) {
            // Update modal for PO mode (no price required) or sale mode (price required)
            if (forPO || currentEntityType === 'supplier') {
                document.getElementById('customModalTitle').innerHTML = 'Add Item to PO';
                document.getElementById('customModalDesc').innerHTML = 'Add item to order from supplier (price optional)';
                document.getElementById('customPriceLabel').innerHTML = '💰 Est. Cost (optional)';
                document.getElementById('customAddBtn').innerHTML = 'GOOD: Add to PO (Enter)';
                document.getElementById('customPrice').placeholder = 'Leave blank if unknown';
            } else {
                document.getElementById('customModalTitle').innerHTML = 'Add Custom Item';
                document.getElementById('customModalDesc').innerHTML = 'Add any item not in your stock list - perfect for special orders, services, or once-off items';
                document.getElementById('customPriceLabel').innerHTML = '💰 Price (incl VAT) *';
                document.getElementById('customAddBtn').innerHTML = 'GOOD: Add to Cart (Enter)';
                document.getElementById('customPrice').placeholder = '0.00';
            }
            document.getElementById('customItemModal').style.display = 'flex';
            document.getElementById('customDesc').value = '';
            document.getElementById('customPrice').value = '';
            document.getElementById('customQty').value = '1';
            setTimeout(() => document.getElementById('customDesc').focus(), 100);
        }
        
        function closeCustomItemModal() {
            document.getElementById('customItemModal').style.display = 'none';
            document.getElementById('customDesc').value = '';
            document.getElementById('customPrice').value = '';
            document.getElementById('customQty').value = '1';
        }
        
        function addCustomItem() {
            const desc = document.getElementById('customDesc').value.trim();
            const price = parseFloat(document.getElementById('customPrice').value) || 0;
            const qty = parseInt(document.getElementById('customQty').value) || 1;
            
            if (!desc) {
                alert('Please enter a description');
                return;
            }
            
            // For PO mode (supplier selected), price is optional
            // For sale mode, price is required
            const isPOMode = currentEntityType === 'supplier';
            if (!isPOMode && price <= 0) {
                alert('Please enter a valid price');
                return;
            }
            
            // Generate unique ID for custom item
            const customId = 'CUSTOM-' + Date.now();
            
            // Add to cart
            cart.push({
                id: customId,
                code: isPOMode ? 'ORDER' : 'CUSTOM',
                desc: desc,
                price: price,
                qty: qty,
                maxQty: 99999,
                isCustom: true,
                isPOItem: isPOMode
            });
            
            updateCart();
            closeCustomItemModal();
            showAddedFeedback(isPOMode ? 'ORDER' : 'CUSTOM');
        }
        
        // === EDIT CUSTOMER (F7) ===
        async function showEditCustomerModal() {
            const customer = getCurrentCustomer();
            if (!customer.id) {
                alert('Select a customer first (F8)');
                toggleEntity('customer');
                return;
            }
            
            // Fetch full customer details
            try {
                const response = await fetch('/api/customer/' + customer.id);
                const data = await response.json();
                
                if (data.success) {
                    const c = data.customer;
                    document.getElementById('editCustId').value = c.id;
                    document.getElementById('editCustName').value = c.name || '';
                    document.getElementById('editCustPhone').value = c.phone || '';
                    document.getElementById('editCustEmail').value = c.email || '';
                    document.getElementById('editCustVat').value = c.vat_number || '';
                    document.getElementById('editCustAddress').value = c.address || '';
                    document.getElementById('editCustSubtitle').textContent = 'Editing: ' + (c.name || 'Customer');
                    
                    document.getElementById('editCustomerModal').style.display = 'flex';
                    setTimeout(() => document.getElementById('editCustName').focus(), 100);
                } else {
                    alert('Could not load customer details');
                }
            } catch (err) {
                alert('Error: ' + err.message);
            }
        }
        
        function closeEditCustomerModal() {
            document.getElementById('editCustomerModal').style.display = 'none';
        }
        
        async function submitEditCustomer() {
            const id = document.getElementById('editCustId').value;
            const name = document.getElementById('editCustName').value.trim();
            const phone = document.getElementById('editCustPhone').value.trim();
            const email = document.getElementById('editCustEmail').value.trim();
            const vat_number = document.getElementById('editCustVat').value.trim();
            const address = document.getElementById('editCustAddress').value.trim();
            
            if (!name) {
                alert('Customer name is required');
                document.getElementById('editCustName').focus();
                return;
            }
            
            try {
                const response = await fetch('/api/customer/' + id + '/update', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name, phone, email, vat_number, address})
                });
                const data = await response.json();
                
                if (data.success) {
                    // Update the displayed name
                    document.getElementById('entitySearch').value = name;
                    closeEditCustomerModal();
                    alert('Customer updated!');
                } else {
                    alert('Error: ' + (data.error || 'Update failed'));
                }
            } catch (err) {
                alert('Error: ' + err.message);
            }
        }
        
        // === QUICK QUOTE (F4 with empty cart) ===
        let qqLineItems = [];
        let qqLineCounter = 0;
        
        // Store selected customer/supplier for quick modals
        let qqSelectedCustomerId = null;
        let qpSelectedSupplierId = null;
        
        function showQuickQuoteModal(customerId = null, customerName = '') {
            qqLineItems = [];
            qqLineCounter = 0;
            qqSelectedCustomerId = customerId;
            
            // Clear or prefill customer fields
            if (customerId && customerName) {
                // Existing customer - prefill and make read-only
                document.getElementById('qqCustName').value = customerName;
                document.getElementById('qqCustName').readOnly = true;
                document.getElementById('qqCustName').style.background = '#2a2a4a';
                document.getElementById('qqCustPhone').value = '';
                document.getElementById('qqCustPhone').style.display = 'none';
                document.getElementById('qqCustEmail').value = '';
                document.getElementById('qqCustEmail').style.display = 'none';
                document.getElementById('qqCustVat').value = '';
                document.getElementById('qqCustVat').style.display = 'none';
                document.getElementById('qqCustAddress').value = '';
                document.getElementById('qqCustAddress').style.display = 'none';
                // Hide labels too - add a subtitle instead
                document.getElementById('qqCustSection').innerHTML = `
                    <h3 style="margin:0 0 15px 0;color:#10b981;font-size:16px;">👤 Customer: ${customerName}</h3>
                    <p style="color:rgba(255,255,255,0.5);font-size:12px;margin:0;">Adding custom items for existing customer</p>
                `;
            } else {
                // New customer - reset to editable
                document.getElementById('qqCustName').value = '';
                document.getElementById('qqCustName').readOnly = false;
                document.getElementById('qqCustName').style.background = '#1a1a2e';
                document.getElementById('qqCustSection').innerHTML = `
                    <h3 style="margin:0 0 15px 0;color:#10b981;font-size:16px;">👤 Customer Details</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Name *</label>
                            <input type="text" id="qqCustName" placeholder="Company or person" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Phone</label>
                            <input type="text" id="qqCustPhone" placeholder="082 123 4567" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Email</label>
                            <input type="text" id="qqCustEmail" placeholder="email@example.com" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">VAT Number</label>
                            <input type="text" id="qqCustVat" placeholder="4123456789" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                    </div>
                    <div style="margin-top:15px;">
                        <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Address</label>
                        <input type="text" id="qqCustAddress" placeholder="Street, City, Code" 
                            style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                    </div>
                `;
            }
            
            document.getElementById('qqLines').innerHTML = '';
            qqUpdateTotal();
            
            // Add first empty line
            qqAddLine();
            
            document.getElementById('quickQuoteModal').style.display = 'flex';
            // Focus on first line item description instead of customer name if customer is pre-selected
            setTimeout(() => {
                const firstInput = document.querySelector('#qqLines input');
                if (firstInput) firstInput.focus();
                else if (!customerId) document.getElementById('qqCustName')?.focus();
            }, 100);
        }
        
        function closeQuickQuoteModal() {
            document.getElementById('quickQuoteModal').style.display = 'none';
        }
        
        function qqAddLine() {
            qqLineCounter++;
            const lineId = 'qqLine' + qqLineCounter;
            
            const lineHtml = `
            <div id="${lineId}" style="display:grid;grid-template-columns:2fr 80px 100px 40px;gap:10px;margin-bottom:10px;align-items:center;">
                <input type="text" placeholder="Description" onchange="qqUpdateLine('${lineId}')" 
                    style="padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;">
                <input type="number" placeholder="Qty" value="1" min="1" onchange="qqUpdateLine('${lineId}')"
                    style="padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;text-align:center;">
                <input type="number" placeholder="Price" step="0.01" onchange="qqUpdateLine('${lineId}')"
                    style="padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;text-align:right;">
                <button onclick="qqRemoveLine('${lineId}')" style="background:#ef4444;color:white;border:none;padding:8px;border-radius:6px;cursor:pointer;">✕</button>
            </div>`;
            
            document.getElementById('qqLines').insertAdjacentHTML('beforeend', lineHtml);
        }
        
        function qqRemoveLine(lineId) {
            const el = document.getElementById(lineId);
            if (el) el.remove();
            qqUpdateTotal();
        }
        
        function qqUpdateLine(lineId) {
            qqUpdateTotal();
        }
        
        function qqUpdateTotal() {
            let subtotal = 0;
            const lines = document.getElementById('qqLines').children;
            
            for (let line of lines) {
                const inputs = line.querySelectorAll('input');
                if (inputs.length >= 3) {
                    const qty = parseFloat(inputs[1].value) || 0;
                    const price = parseFloat(inputs[2].value) || 0;
                    subtotal += qty * price;
                }
            }
            
            const vat = subtotal * 0.15;
            const total = subtotal + vat;
            
            document.getElementById('qqSubtotal').textContent = 'R' + subtotal.toFixed(2);
            document.getElementById('qqVat').textContent = 'R' + vat.toFixed(2);
            document.getElementById('qqTotal').textContent = 'R' + total.toFixed(2);
        }
        
        async function submitQuickQuote() {
            // Get customer name from visible element or section text
            let custName = '';
            const custNameEl = document.getElementById('qqCustName');
            if (custNameEl) {
                custName = custNameEl.value.trim();
            } else if (qqSelectedCustomerId) {
                // Customer was pre-selected, get name from section
                const section = document.getElementById('qqCustSection');
                const match = section?.innerText?.match(/Customer: (.+)/);
                custName = match ? match[1].trim() : '';
            }
            
            const custPhone = document.getElementById('qqCustPhone')?.value?.trim() || '';
            const custEmail = document.getElementById('qqCustEmail')?.value?.trim() || '';
            const custVat = document.getElementById('qqCustVat')?.value?.trim() || '';
            const custAddress = document.getElementById('qqCustAddress')?.value?.trim() || '';
            
            if (!custName && !qqSelectedCustomerId) {
                alert('Please enter a customer name');
                document.getElementById('qqCustName')?.focus();
                return;
            }
            
            // Gather line items
            const items = [];
            const lines = document.getElementById('qqLines').children;
            
            for (let line of lines) {
                const inputs = line.querySelectorAll('input');
                if (inputs.length >= 3) {
                    const desc = inputs[0].value.trim();
                    const qty = parseFloat(inputs[1].value) || 0;
                    const price = parseFloat(inputs[2].value) || 0;
                    
                    if (desc && qty > 0 && price > 0) {
                        items.push({
                            description: desc,
                            quantity: qty,
                            price: price,
                            total: qty * price
                        });
                    }
                }
            }
            
            if (items.length === 0) {
                alert('Please add at least one line item');
                return;
            }
            
            try {
                const response = await fetch('/api/pos/quick-quote', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        customer_id: qqSelectedCustomerId || null,
                        customer: {
                            name: custName,
                            phone: custPhone,
                            email: custEmail,
                            vat_number: custVat,
                            address: custAddress
                        },
                        items: items
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    closeQuickQuoteModal();
                    alert('Quote ' + data.quote_number + ' created!');
                    if (confirm('Open quote now?')) {
                        window.location = '/quote/' + data.quote_id;
                    }
                } else {
                    alert('Error: ' + (data.error || 'Quote creation failed'));
                }
            } catch (err) {
                alert('Error: ' + err.message);
            }
        }
        
        // === QUICK PO (F5 with empty cart) ===
        let qpLineCounter = 0;
        
        function showQuickPOModal(supplierId = null, supplierName = '') {
            qpLineCounter = 0;
            qpSelectedSupplierId = supplierId;
            
            // Clear or prefill supplier fields
            if (supplierId && supplierName) {
                // Existing supplier - show simplified header
                document.getElementById('qpSupplierSection').innerHTML = `
                    <h3 style="margin:0 0 15px 0;color:#3b82f6;font-size:16px;">🏭 Supplier: ${supplierName}</h3>
                    <p style="color:rgba(255,255,255,0.5);font-size:12px;margin:0;">Adding custom items for existing supplier</p>
                `;
            } else {
                // New supplier - show full form
                document.getElementById('qpSupplierSection').innerHTML = `
                    <h3 style="margin:0 0 15px 0;color:#3b82f6;font-size:16px;">🏭 Supplier Details</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Supplier Name *</label>
                            <input type="text" id="qpSupplierName" placeholder="Company name" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Phone</label>
                            <input type="text" id="qpSupplierPhone" placeholder="012 345 6789" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Email</label>
                            <input type="text" id="qpSupplierEmail" placeholder="orders@supplier.com" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">VAT Number</label>
                            <input type="text" id="qpSupplierVat" placeholder="4123456789" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                    </div>
                `;
            }
            
            document.getElementById('qpNotes').value = '';
            if (document.getElementById('qpReference')) document.getElementById('qpReference').value = '';
            document.getElementById('qpLines').innerHTML = '';
            document.getElementById('qpTotalItems').textContent = '0';
            
            // Add first empty line
            qpAddLine();
            
            document.getElementById('quickPOModal').style.display = 'flex';
            // Focus on first line item if supplier pre-selected
            setTimeout(() => {
                const firstInput = document.querySelector('#qpLines input');
                if (firstInput) firstInput.focus();
                else if (!supplierId) document.getElementById('qpSupplierName')?.focus();
            }, 100);
        }
        
        function closeQuickPOModal() {
            document.getElementById('quickPOModal').style.display = 'none';
        }
        
        function qpAddLine() {
            qpLineCounter++;
            const lineId = 'qpLine' + qpLineCounter;
            
            const lineHtml = `
            <div id="${lineId}" style="display:grid;grid-template-columns:2fr 80px 40px;gap:10px;margin-bottom:10px;align-items:center;">
                <input type="text" placeholder="Description / Item" onchange="qpUpdateTotal()" 
                    style="padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;">
                <input type="number" placeholder="Qty" value="1" min="1" onchange="qpUpdateTotal()"
                    style="padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;text-align:center;">
                <button onclick="qpRemoveLine('${lineId}')" style="background:#ef4444;color:white;border:none;padding:8px;border-radius:6px;cursor:pointer;">✕</button>
            </div>`;
            
            document.getElementById('qpLines').insertAdjacentHTML('beforeend', lineHtml);
            qpUpdateTotal();
        }
        
        function qpRemoveLine(lineId) {
            const el = document.getElementById(lineId);
            if (el) el.remove();
            qpUpdateTotal();
        }
        
        function qpUpdateTotal() {
            let totalItems = 0;
            const lines = document.getElementById('qpLines').children;
            
            for (let line of lines) {
                const inputs = line.querySelectorAll('input');
                if (inputs.length >= 2) {
                    const desc = inputs[0].value.trim();
                    const qty = parseInt(inputs[1].value) || 0;
                    if (desc && qty > 0) {
                        totalItems += qty;
                    }
                }
            }
            
            document.getElementById('qpTotalItems').textContent = totalItems;
        }
        
        async function submitQuickPO() {
            // Get supplier name from visible element or section text
            let supplierName = '';
            const supplierNameEl = document.getElementById('qpSupplierName');
            if (supplierNameEl) {
                supplierName = supplierNameEl.value.trim();
            } else if (qpSelectedSupplierId) {
                // Supplier was pre-selected, get name from section
                const section = document.getElementById('qpSupplierSection');
                const match = section?.innerText?.match(/Supplier: (.+)/);
                supplierName = match ? match[1].trim() : '';
            }
            
            const supplierPhone = document.getElementById('qpSupplierPhone')?.value?.trim() || '';
            const supplierEmail = document.getElementById('qpSupplierEmail')?.value?.trim() || '';
            const supplierVat = document.getElementById('qpSupplierVat')?.value?.trim() || '';
            const notes = document.getElementById('qpNotes').value.trim();
            const reference = document.getElementById('qpReference')?.value?.trim() || '';
            
            if (!supplierName && !qpSelectedSupplierId) {
                alert('Please enter a supplier name');
                document.getElementById('qpSupplierName')?.focus();
                return;
            }
            
            // Gather line items
            const items = [];
            const lines = document.getElementById('qpLines').children;
            
            for (let line of lines) {
                const inputs = line.querySelectorAll('input');
                if (inputs.length >= 2) {
                    const desc = inputs[0].value.trim();
                    const qty = parseInt(inputs[1].value) || 0;
                    
                    if (desc && qty > 0) {
                        items.push({
                            description: desc,
                            qty: qty
                        });
                    }
                }
            }
            
            if (items.length === 0) {
                alert('Please add at least one item');
                return;
            }
            
            try {
                const response = await fetch('/api/pos/quick-po', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        supplier_id: qpSelectedSupplierId || null,
                        supplier: {
                            name: supplierName,
                            phone: supplierPhone,
                            email: supplierEmail,
                            vat_number: supplierVat
                        },
                        items: items,
                        notes: notes,
                        reference: reference
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    closeQuickPOModal();
                    
                    // Offer options: View, Email, or Done
                    const choice = prompt(
                        'PO ' + data.po_number + ' created!\\n\\n' +
                        'What would you like to do?\\n\\n' +
                        '1 = Open PO\\n' +
                        '2 = Email to Supplier\\n' +
                        '3 = Done\\n\\n' +
                        'Enter 1, 2, or 3:',
                        '2'
                    );
                    
                    if (choice === '1') {
                        window.location = '/purchase/' + data.po_id;
                    } else if (choice === '2') {
                        try {
                            const emailResp = await fetch('/api/purchase/' + data.po_id + '/email', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})});
                            const emailData = await emailResp.json();
                            if (emailData.success) {
                                alert('✅ ' + emailData.message);
                            } else {
                                alert('❌ ' + emailData.error + '\\n\\nOpen PO to add supplier email.');
                                window.location = '/purchase/' + data.po_id;
                            }
                        } catch(e) {
                            alert('Email error: ' + e.message);
                        }
                    }
                } else {
                    alert('Error: ' + (data.error || 'PO creation failed'));
                }
            } catch (err) {
                alert('Error: ' + err.message);
            }
        }
        
        // === QUICK CUSTOMER FOR QUOTES ===
        function showQuickCustomerModal() {
            document.getElementById('quickCustomerModal').style.display = 'flex';
            document.getElementById('quickCustName').value = '';
            document.getElementById('quickCustPhone').value = '';
            document.getElementById('quickCustEmail').value = '';
            document.getElementById('quickCustVat').value = '';
            document.getElementById('quickCustAddress').value = '';
            setTimeout(() => document.getElementById('quickCustName').focus(), 100);
        }
        
        function closeQuickCustomerModal() {
            document.getElementById('quickCustomerModal').style.display = 'none';
        }
        
        async function submitQuickCustomer() {
            const name = document.getElementById('quickCustName').value.trim();
            const phone = document.getElementById('quickCustPhone').value.trim();
            const email = document.getElementById('quickCustEmail').value.trim();
            const vat_number = document.getElementById('quickCustVat').value.trim();
            const address = document.getElementById('quickCustAddress').value.trim();
            
            if (!name) {
                alert('Please enter a customer name');
                document.getElementById('quickCustName').focus();
                return;
            }
            
            // Create customer first
            try {
                const response = await fetch('/api/customer/quick-add', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name, phone, email, vat_number, address})
                });
                const result = await response.json();
                
                if (result.success) {
                    // Set this customer as selected
                    document.getElementById('entityValue').value = result.customer_id;
                    document.getElementById('entitySearch').value = name;
                    currentEntityType = 'customer';
                    
                    closeQuickCustomerModal();
                    
                    // Now create the quote
                    await createQuoteWithCustomer(result.customer_id, name);
                } else {
                    alert('Error creating customer: ' + (result.error || 'Unknown error'));
                }
            } catch (err) {
                alert('Error: ' + err.message);
            }
        }
        
        async function createQuoteWithCustomer(customerId, customerName) {
            const items = cart.map(item => ({
                stock_id: (item.isCustom || item.isPOItem) ? null : item.id,
                code: item.code,
                description: item.desc,
                quantity: item.qty,
                price: item.price,
                total: item.price * item.qty
            }));
            
            const total = items.reduce((sum, item) => sum + item.total, 0);
            
            // Get salesman from quick quote modal
            const salesmanSel = document.getElementById('quickQuoteSalesman');
            const salesmanId = salesmanSel ? salesmanSel.value : currentCashierId;
            const salesmanName = salesmanSel ? (salesmanSel.options[salesmanSel.selectedIndex]?.dataset?.name || '') : currentCashierName;
            
            try {
                const response = await fetch('/api/pos/quote', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        items: items,
                        customer_id: customerId,
                        customer_name: customerName,
                        total: total,
                        cashier_id: currentCashierId,
                        cashier_name: currentCashierName,
                        salesman_id: salesmanId,
                        salesman_name: salesmanName
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Quote ' + data.quote_number + ' created!');
                    clearCart();
                    if (confirm('Open quote now?')) {
                        window.location = '/quote/' + data.quote_id;
                    }
                } else {
                    alert('Error: ' + (data.error || 'Quote failed'));
                }
            } catch (err) {
                if (!navigator.onLine || err.message.includes('fetch') || err.message.includes('network') || err.message.includes('Network')) {
                    try {
                        const subtotal = Math.round(total * 100) / 100;
                        const vatAmt = Math.round(subtotal * 0.15 * 100) / 100;
                        await (window.queueOfflineItem || queueOfflineSale)('quote_queue', {
                            items: items, customer_id: customerId, customer_name: customerName,
                            subtotal: subtotal, vat: vatAmt, total: Math.round((subtotal + vatAmt) * 100) / 100,
                            offline_date: new Date().toISOString().slice(0,10), offline_time: new Date().toISOString()
                        });
                        alert('📴 OFFLINE QUOTE SAVED\\n\\nFor: ' + (customerName || 'Walk-in') + '\\nTotal: R' + total.toFixed(2) + '\\n\\nWill sync when internet returns.');
                        clearCart();
                    } catch(e) { alert('Could not save quote offline'); }
                } else { alert('Connection error: ' + err.message); }
            }
        }
        
        // === CREDIT NOTE FUNCTIONS ===
        function showCreditNoteModal() {
            const customerId = document.getElementById('entityValue').value;
            const customerName = document.getElementById('entitySearch').value || '';
            
            if (!customerId || currentEntityType !== 'customer') {
                alert('Warning: Select a customer first (F8)');
                toggleEntity('customer');
                return;
            }
            
            document.getElementById('cnCustomerName').textContent = 'Invoices for: ' + customerName;
            document.getElementById('creditNoteModal').style.display = 'flex';
            
            // Load customer invoices
            document.getElementById('invoiceList').innerHTML = '<p style="color:rgba(255,255,255,0.5);text-align:center;padding:20px;">Loading...</p>';
            
            fetch('/api/pos/customer-invoices?customer_id=' + customerId)
                .then(r => r.json())
                .then(data => {
                    if (data.success && data.invoices.length > 0) {
                        let html = '';
                        data.invoices.forEach(inv => {
                            const statusColor = inv.status === 'paid' ? '#10b981' : inv.status === 'credited' ? '#888' : '#f59e0b';
                            const disabled = inv.status === 'credited' ? 'pointer-events:none;opacity:0.5;' : '';
                            const invNum = inv.invoice_number || 'INV-?';
                            html += '<div onclick="createCreditNote(\\'' + inv.id + '\\', \\'' + invNum + '\\')" style="'+disabled+'padding:12px;margin-bottom:8px;background:rgba(255,255,255,0.05);border-radius:8px;cursor:pointer;border:1px solid rgba(255,255,255,0.1);" onmouseover="this.style.background=\\'rgba(239,68,68,0.2)\\'" onmouseout="this.style.background=\\'rgba(255,255,255,0.05)\\'">';
                            html += '<div style="display:flex;justify-content:space-between;align-items:center;">';
                            html += '<div><strong style="color:white;">' + invNum + '</strong>';
                            html += '<span style="color:rgba(255,255,255,0.5);font-size:12px;margin-left:10px;">' + (inv.date || '-') + '</span></div>';
                            html += '<div style="text-align:right;">';
                            html += '<div style="color:white;font-weight:bold;">R' + (inv.total || 0).toFixed(2) + '</div>';
                            html += '<div style="color:' + statusColor + ';font-size:11px;text-transform:uppercase;">' + (inv.status || 'outstanding') + '</div>';
                            html += '</div></div></div>';
                        });
                        document.getElementById('invoiceList').innerHTML = html;
                    } else {
                        document.getElementById('invoiceList').innerHTML = '<p style="color:rgba(255,255,255,0.5);text-align:center;padding:20px;">No invoices found for this customer</p>';
                    }
                })
                .catch(err => {
                    document.getElementById('invoiceList').innerHTML = '<p style="color:#ef4444;text-align:center;padding:20px;">Error loading invoices</p>';
                });
        }
        
        function closeCreditNoteModal() {
            document.getElementById('creditNoteModal').style.display = 'none';
        }
        
        function createCreditNote(invoiceId, invoiceNum) {
            const invDisplay = invoiceNum || 'this invoice';
            if (confirm('Create credit note for ' + invDisplay + '?')) {
                window.location = '/invoice/' + invoiceId + '/credit-note';
            }
        }
        
        // ═══ PRINT FUNCTIONS ═══
        let posSettings = {};
        let lastSaleData = null;
        
        function loadPosSettings() {
            try {
                const settingsJson = document.getElementById('posSettings').value.replace(/&#39;/g, "'");
                posSettings = JSON.parse(settingsJson);
            } catch (e) {
                posSettings = { auto_print: false, print_format: 'ask', slip_footer: 'Thank you!' };
            }
        }
        
        function showPrintDialog(saleNum, saleId, method, customerObj, items, subtotal, vat, total, cashReceived = 0, changeGiven = 0) {
            loadPosSettings();
            
            // Handle both old string format and new object format
            const customerName = (typeof customerObj === 'string') ? customerObj : (customerObj.name || 'Countersale');
            const customerAddress = (typeof customerObj === 'object') ? (customerObj.address || '') : '';
            const customerPhone = (typeof customerObj === 'object') ? (customerObj.phone || '') : '';
            const customerVat = (typeof customerObj === 'object') ? (customerObj.vat_number || '') : '';
            
            lastSaleData = { saleNum, saleId, method, customerName, items, subtotal, vat, total, cashReceived, changeGiven };
            
            // Build slip content
            const now = new Date();
            const time = now.toLocaleTimeString('en-ZA', {hour: '2-digit', minute: '2-digit'});
            const date = now.toLocaleDateString('en-ZA');
            
            const methodLabel = {cash: '💵 CASH', card: '💳 CARD', account: '📒 ACCOUNT'}[method] || method.toUpperCase();
            
            let itemsHtml = '';
            items.forEach(item => {
                const lineTotal = item.price * item.quantity;
                // Prefer description, fall back to code only if description is empty/missing
                const itemName = (item.description && item.description.trim()) ? item.description : (item.code || 'Item');
                itemsHtml += '<tr><td style="padding:3px 0;font-size:13px;">' + item.quantity + 'x ' + itemName + '</td><td style="text-align:right;padding:3px 0;font-size:13px;white-space:nowrap;">R' + lineTotal.toFixed(2) + '</td></tr>';
            });
            
            // Cash payment details (only for cash sales)
            let cashHtml = '';
            if (method === 'cash' && cashReceived > 0) {
                cashHtml = `
                    <div style="margin-top:8px;padding:8px;background:#f5f5f5;border-radius:6px;">
                        <div style="display:flex;justify-content:space-between;font-size:14px;padding:2px 0;">
                            <span>Cash Received</span><span>R${cashReceived.toFixed(2)}</span>
                        </div>
                        <div style="display:flex;justify-content:space-between;font-size:18px;font-weight:bold;padding:2px 0;color:#10b981;">
                            <span>Change</span><span>R${changeGiven.toFixed(2)}</span>
                        </div>
                    </div>
                `;
            }
            
            const slipHtml = `
                <div style="text-align:center;border-bottom:2px dashed #000;padding-bottom:8px;margin-bottom:8px;">
                    <div style="font-size:18px;font-weight:bold;">${posSettings.business_name || 'Business'}</div>
                    ${posSettings.phone ? '<div style="font-size:12px;color:#666;">Tel: ' + posSettings.phone + '</div>' : ''}
                    ${posSettings.vat_number ? '<div style="font-size:12px;color:#666;">VAT: ' + posSettings.vat_number + '</div>' : ''}
                    <div style="margin-top:6px;font-size:15px;font-weight:bold;">${saleNum}</div>
                    ${saleNum.startsWith('OFF') ? '<div style="background:#dc2626;color:white;padding:2px 6px;border-radius:3px;font-size:11px;display:inline-block;margin-top:4px;">OFFLINE</div>' : ''}
                    <div style="font-size:12px;color:#666;">${date} ${time}</div>
                    ${currentCashierName ? '<div style="font-size:12px;color:#666;margin-top:2px;">Cashier: ' + currentCashierName + '</div>' : ''}
                </div>
                
                <div style="margin-bottom:8px;font-size:13px;">
                    <span style="background:#333;color:white;padding:3px 8px;border-radius:3px;font-size:12px;">${methodLabel}</span>
                    <span style="margin-left:8px;font-size:13px;">${customerName || 'Countersale'}</span>
                    ${customerAddress ? '<div style="font-size:11px;color:#666;margin-top:4px;margin-left:4px;">' + customerAddress.replace(/\\n/g, '<br>') + '</div>' : ''}
                    ${customerPhone ? '<div style="font-size:11px;color:#666;margin-left:4px;">Tel: ' + customerPhone + '</div>' : ''}
                    ${customerVat ? '<div style="font-size:11px;color:#666;margin-left:4px;font-weight:bold;">VAT: ' + customerVat + '</div>' : ''}
                </div>
                
                <table style="width:100%;border-collapse:collapse;margin-bottom:8px;">
                    ${itemsHtml}
                </table>
                
                <div style="border-top:2px dashed #000;padding-top:6px;">
                    <div style="display:flex;justify-content:space-between;font-size:13px;color:#666;padding:2px 0;">
                        <span>Subtotal</span><span>R${subtotal.toFixed(2)}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:13px;color:#666;padding:2px 0;">
                        <span>VAT (15%)</span><span>R${vat.toFixed(2)}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:22px;font-weight:bold;margin-top:6px;">
                        <span>TOTAL</span><span>R${total.toFixed(2)}</span>
                    </div>
                </div>
                
                ${cashHtml}
                
                <div style="text-align:center;margin-top:8px;padding-top:8px;border-top:2px dashed #000;font-size:12px;color:#666;">
                    ${posSettings.slip_footer || 'Thank you for your purchase!'}
                </div>
            `;
            
            document.getElementById('slipContent').innerHTML = slipHtml;
            
            // Show CHANGE banner if cash sale with change due
            var changeBanner = document.getElementById('changeBanner');
            if (!changeBanner) {
                changeBanner = document.createElement('div');
                changeBanner.id = 'changeBanner';
                changeBanner.style.cssText = 'text-align:center;padding:20px;font-size:36px;font-weight:900;border-radius:8px 8px 0 0;display:none;';
                var modalInner = document.querySelector('#printSlipModal > div');
                if (modalInner) modalInner.insertBefore(changeBanner, modalInner.firstChild);
            }
            if (changeGiven >= 0.01) {
                changeBanner.style.display = 'block';
                changeBanner.style.background = '#10b981';
                changeBanner.style.color = 'white';
                changeBanner.textContent = 'CHANGE: R' + changeGiven.toFixed(2);
            } else {
                changeBanner.style.display = 'none';
            }
            
            // Check settings for auto behavior
            posLocked = false;  // Sale is committed — unlock POS for next sale
            
            // === ALWAYS AUTO-PRINT THERMAL — no format selection needed ===
            // Show the modal briefly (for change banner visibility), then auto-fire thermal
            document.getElementById('printSlipModal').style.display = 'flex';
            // Hide the button row — we're going straight to thermal
            var _btnRow = document.getElementById('printButtonRow');
            if (_btnRow) _btnRow.style.display = 'none';
            
            // Small delay so change banner is visible before print dialog opens
            // doPrintSlip handles all cleanup after print() returns
            setTimeout(function() {
                doPrintSlip('thermal');
            }, changeGiven >= 0.01 ? 1200 : 200);  // longer delay if there's change to show
        }
        
        function doPrintSlip(format) {
            var fullHtml;
            
            if (format === 'a4' && lastSaleData) {
                // === BUILD FULL A4 TAX INVOICE ===
                var sd = lastSaleData;
                var now = new Date();
                var dateStr = now.toLocaleDateString('en-ZA');
                var timeStr = now.toLocaleTimeString('en-ZA', {hour:'2-digit', minute:'2-digit'});
                var methodLabel = {cash:'Cash', card:'Card', account:'Account', eft:'EFT'}[sd.method] || sd.method;
                
                var biz = posSettings || {};
                var bizName = biz.business_name || 'Business';
                var bizVat = biz.vat_number || '';
                var bizPhone = biz.phone || '';
                var bizAddr = (biz.address || '').replace(/\\n/g, '<br>');
                var bizEmail = biz.email || '';
                var bizBank = biz.bank_name || '';
                var bizBankAcc = biz.bank_account || '';
                var bizBankBranch = biz.bank_branch || '';
                
                // Build items rows
                var itemsRows = '';
                (sd.items || []).forEach(function(item) {
                    var qty = item.quantity || item.qty || 1;
                    var desc = item.description || item.desc || '-';
                    var price = parseFloat(item.price || 0);
                    var lineTotal = parseFloat(item.total || (qty * price));
                    var vatAmt = Math.round(lineTotal * 0.15 * 100) / 100;
                    var inclTotal = Math.round((lineTotal + vatAmt) * 100) / 100;
                    itemsRows += '<tr style="border-bottom:1px solid #e5e7eb;">' +
                        '<td style="padding:6px 8px;font-size:12px;">' + desc + '</td>' +
                        '<td style="text-align:center;padding:6px 8px;font-size:12px;">' + qty + '</td>' +
                        '<td style="text-align:right;padding:6px 8px;font-size:12px;">R' + price.toFixed(2) + '</td>' +
                        '<td style="text-align:center;padding:6px 8px;font-size:12px;">15%</td>' +
                        '<td style="text-align:right;padding:6px 8px;font-size:12px;">R' + lineTotal.toFixed(2) + '</td>' +
                        '<td style="text-align:right;padding:6px 8px;font-size:12px;font-weight:600;">R' + inclTotal.toFixed(2) + '</td>' +
                        '</tr>';
                });
                
                var cashierLine = currentCashierName ? '<tr><td style="padding:4px 0;color:#888;">Prepared By:</td><td style="padding:4px 0;font-weight:600;">' + currentCashierName + '</td></tr>' : '';
                
                var paymentInfo = '';
                if (sd.method === 'cash' && sd.cashReceived) {
                    paymentInfo = '<div style="margin-top:10px;font-size:11px;color:#555;">' +
                        'Cash Received: R' + parseFloat(sd.cashReceived).toFixed(2) +
                        ' | Change: R' + parseFloat(sd.changeGiven || 0).toFixed(2) + '</div>';
                }
                
                var bankingHtml = '';
                if (bizBankAcc) {
                    bankingHtml = '<div style="border:1px solid #e5e7eb;border-radius:6px;padding:12px;background:#fafafa;margin-bottom:10px;">' +
                        '<div style="font-weight:600;color:#333;margin-bottom:6px;font-size:13px;">Banking Details</div>' +
                        '<div style="font-size:12px;">Bank: ' + bizBank + '</div>' +
                        '<div style="font-size:12px;">Account: ' + bizBankAcc + '</div>' +
                        '<div style="font-size:12px;">Branch: ' + bizBankBranch + '</div></div>';
                }
                
                fullHtml = '<!DOCTYPE html><html><head><title>Tax Invoice</title>' +
                    '<style>' +
                    '* { margin:0; padding:0; box-sizing:border-box; }' +
                    'body { font-family: Arial, Helvetica, sans-serif; color:#333; background:#fff; padding:0; font-size:12px; }' +
                    'table { width:100%; border-collapse:collapse; page-break-inside:auto; }' +
                    'tr { page-break-inside:avoid; }' +
                    'thead { display:table-header-group; }' +
                    '@media print { @page { size:A4; margin:10mm 12mm; } body { padding:0; } }' +
                    '</style></head><body>' +
                    
                    '<div style="background:#1a1a2e;color:white;padding:12px 25px;display:flex;justify-content:space-between;align-items:center;">' +
                    '<div><h1 style="margin:0;font-size:16px;font-weight:700;letter-spacing:0.5px;">' + bizName + '</h1>' +
                    (bizAddr ? '<p style="margin:4px 0 0 0;font-size:10px;opacity:0.8;">' + bizAddr + '</p>' : '') +
                    '</div>' +
                    '<div style="text-align:right;">' +
                    '<h2 style="margin:0;font-size:20px;font-weight:700;letter-spacing:2px;">TAX INVOICE</h2>' +
                    '<span style="background:#10b981;color:white;padding:4px 12px;border-radius:20px;font-size:11px;">' + methodLabel.toUpperCase() + '</span>' +
                    '</div></div>' +
                    
                    '<div style="padding:10px 25px;display:flex;gap:40px;border-bottom:1px solid #e5e7eb;">' +
                    '<div style="flex:1;border-right:1px solid #e5e7eb;padding-right:25px;">' +
                    '<table style="font-size:11px;color:#333;">' +
                    '<tr><td style="padding:4px 0;color:#888;width:110px;">Number:</td><td style="padding:4px 0;font-weight:600;">' + (sd.saleNum || '-') + '</td></tr>' +
                    '<tr><td style="padding:4px 0;color:#888;">Date:</td><td style="padding:4px 0;">' + dateStr + ' ' + timeStr + '</td></tr>' +
                    (bizVat ? '<tr><td style="padding:4px 0;color:#888;">Our VAT No:</td><td style="padding:4px 0;">' + bizVat + '</td></tr>' : '') +
                    cashierLine +
                    '</table>' +
                    (bizPhone ? '<div style="margin-top:8px;font-size:10px;color:#666;">Tel: ' + bizPhone + '</div>' : '') +
                    '</div>' +
                    '<div style="flex:1;padding-left:25px;">' +
                    '<div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;font-weight:600;">Bill To</div>' +
                    '<div style="font-size:13px;font-weight:700;color:#1a1a2e;">' + (sd.customerName || 'Cash Customer') + '</div>' +
                    '</div></div>' +
                    
                    '<div style="padding:0 25px;">' +
                    '<table>' +
                    '<thead><tr style="background:#f1f5f9;border-bottom:2px solid #cbd5e1;">' +
                    '<th style="padding:6px 8px;text-align:left;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;">Description</th>' +
                    '<th style="padding:6px 8px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">Qty</th>' +
                    '<th style="padding:6px 8px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Excl. Price</th>' +
                    '<th style="padding:6px 8px;text-align:center;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:60px;">VAT %</th>' +
                    '<th style="padding:6px 8px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Excl. Total</th>' +
                    '<th style="padding:6px 8px;text-align:right;color:#475569;font-weight:600;font-size:10px;text-transform:uppercase;width:100px;">Incl. Total</th>' +
                    '</tr></thead>' +
                    '<tbody>' + itemsRows + '</tbody>' +
                    '</table></div>' +
                    
                    '<div style="padding:15px 25px;display:flex;justify-content:space-between;align-items:flex-end;">' +
                    '<div style="font-size:12px;color:#666;max-width:55%;">' +
                    bankingHtml +
                    paymentInfo +
                    '<p style="margin:8px 0 2px;font-size:11px;color:#999;">Thank you for your purchase!</p>' +
                    '</div>' +
                    '<table style="width:220px;border-collapse:collapse;">' +
                    '<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:4px 8px;color:#666;font-size:11px;">Total Exclusive</td><td style="padding:4px 8px;text-align:right;font-size:11px;">R' + parseFloat(sd.subtotal || 0).toFixed(2) + '</td></tr>' +
                    '<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:4px 8px;color:#666;font-size:11px;">VAT (15%)</td><td style="padding:4px 8px;text-align:right;font-size:11px;">R' + parseFloat(sd.vat || 0).toFixed(2) + '</td></tr>' +
                    '<tr style="background:#1a1a2e;"><td style="padding:8px;color:white;font-size:13px;font-weight:700;">TOTAL</td><td style="padding:8px;text-align:right;color:white;font-size:13px;font-weight:700;">R' + parseFloat(sd.total || 0).toFixed(2) + '</td></tr>' +
                    '</table></div>' +
                    
                    '</body></html>';
            } else {
                // === THERMAL SLIP (existing behavior) ===
                var slipContent = document.getElementById('slipContent').innerHTML;
                
                var styles = format === 'thermal' ? 
                    'body { width: 72mm; margin: 0; padding: 4mm; font-family: "Courier New", monospace; font-size: 16px; font-weight: bold; color: #000; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; } * { font-weight: bold !important; color: #000 !important; background: transparent !important; } table { width: 100%; border-collapse: collapse; } td { font-weight: bold !important; padding: 2px 0; } @page { size: 80mm auto; margin: 0; } @media print { body { width: 72mm; } }' :
                    'body { width: 210mm; margin: 20mm; font-family: Arial, sans-serif; font-size: 18px; color: #000; background: #fff; } @page { size: A4; margin: 20mm; }';
                
                fullHtml = '<!DOCTYPE html><html><head><title>POS Slip</title><style>' + styles + '</style></head><body>' + slipContent + '</body></html>';
            }
            
            // === THERMAL PRINT via hidden iframe ===
            // Exit fullscreen before print (browsers block print dialog in fullscreen)
            if (document.fullscreenElement) { try { document.exitFullscreen(); } catch(e) {} }
            
            // Use hidden iframe — avoids popup window staying open
            var pf = document.getElementById('posPrintFrame');
            if (!pf) {
                pf = document.createElement('iframe');
                pf.id = 'posPrintFrame';
                pf.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:80mm;height:600px;border:none;';
                document.body.appendChild(pf);
            }
            var fd = pf.contentDocument || pf.contentWindow.document;
            fd.open(); fd.write(fullHtml); fd.close();
            
            function _afterPrint() {
                // Close the slip modal
                var modal = document.getElementById('printSlipModal');
                if (modal) modal.style.display = 'none';
                var _btnRow = document.getElementById('printButtonRow');
                if (_btnRow) _btnRow.style.display = 'flex';
                // Return to fullscreen
                if (f11Mode && !document.fullscreenElement) {
                    try { document.documentElement.requestFullscreen(); } catch(e) {}
                }
                // Reset POS for next sale
                if (typeof afterSaleReset === 'function') afterSaleReset();
            }
            
            function _executePrint() {
                try {
                    pf.contentWindow.focus();
                    pf.contentWindow.print();
                    // print() blocks until user clicks Print or Cancel
                    // When we reach here, dialog is closed — go back to POS immediately
                    _afterPrint();
                } catch(e) {
                    console.log('[POS] Print error:', e);
                    _afterPrint();
                }
            }
            
            // Wait for iframe content to load, then print
            if (fd.readyState === 'complete') { setTimeout(_executePrint, 300); }
            else { pf.onload = function() { setTimeout(_executePrint, 200); }; setTimeout(_executePrint, 1000); }
            
            // Duplicate copy (store copy) — fires 3s after first print
            if (posSettings.print_duplicates) {
                setTimeout(function() {
                    var dupHtml = fullHtml.replace('</body>', '<div style="text-align:center;font-size:11px;margin-top:10px;border-top:1px dashed #000;padding-top:5px;">** STORE COPY **</div></body>');
                    fd.open(); fd.write(dupHtml); fd.close();
                    function _executeDup() {
                        try { pf.contentWindow.focus(); pf.contentWindow.print(); } catch(e) {}
                        // Return to fullscreen again after store copy
                        if (f11Mode && !document.fullscreenElement) {
                            try { document.documentElement.requestFullscreen(); } catch(e) {}
                        }
                    }
                    if (fd.readyState === 'complete') { setTimeout(_executeDup, 300); }
                    else { pf.onload = function() { setTimeout(_executeDup, 200); }; setTimeout(_executeDup, 1000); }
                }, 3000);
            }
        }
        
        function closePrintModal() {
            document.getElementById('printSlipModal').style.display = 'none';
            // Show the button row again in case someone opens it manually later
            var _btnRow = document.getElementById('printButtonRow');
            if (_btnRow) _btnRow.style.display = 'flex';
            afterSaleReset();
        }
        
        function afterSaleReset() {
            // Update stock quantities LOCALLY — no page reload needed
            if (lastSaleData && lastSaleData.items) {
                lastSaleData.items.forEach(function(item) {
                    // Find stock row by ID or code
                    var row = document.querySelector('tr[data-id="' + item.stock_id + '"]') || 
                              document.querySelector('tr[data-code="' + item.code + '"]');
                    if (row) {
                        var oldQty = parseFloat(row.getAttribute('data-qty')) || 0;
                        var newQty = oldQty - item.quantity;
                        row.setAttribute('data-qty', newQty);
                        
                        // Update the onclick to pass new qty
                        var id = row.getAttribute('data-id');
                        var code = row.getAttribute('data-code');
                        var desc = row.getAttribute('data-desc');
                        var price = parseFloat(row.getAttribute('data-price')) || 0;
                        row.setAttribute('onclick', "addToCart('" + id + "', '" + code + "', '" + desc + "', " + price + ", " + newQty + ")");
                        
                        // Update qty badge display
                        var badgeCell = row.querySelector('.col-stock');
                        if (badgeCell) {
                            var cls = '';
                            var badgeCls = 'stock-badge';
                            if (newQty < 0) { cls = 'negative'; badgeCls += ' negative'; }
                            else if (newQty === 0) { cls = 'zero'; badgeCls += ' zero'; }
                            else if (newQty < 5) { cls = 'low'; badgeCls += ' low'; }
                            badgeCell.innerHTML = '<span class="' + badgeCls + '">' + Math.round(newQty) + '</span>';
                            
                            // Update row class
                            row.classList.remove('negative', 'zero', 'low');
                            if (cls) row.classList.add(cls);
                        }
                    }
                });
            }
            
            // Clear cart and reset state
            cart = [];
            updateCart();
            posLocked = false;
            lastSaleData = null;
            
            // === AUTO-RETURN TO FULLSCREEN after print ===
            if (f11Mode && !document.fullscreenElement) {
                try { document.documentElement.requestFullscreen(); } catch(e) {}
            }
            
            // Focus search bar AFTER fullscreen settles (browser steals focus during fullscreen transition)
            setTimeout(function() {
                if (f11Mode) {
                    var f11s = document.getElementById('f11Search');
                    if (f11s) { f11s.value = ''; f11s.focus(); }
                    if (typeof renderF11Table === 'function') renderF11Table();
                    if (typeof syncF11Buttons === 'function') syncF11Buttons();
                } else {
                    var search = document.getElementById('stockSearch');
                    if (search) { search.value = ''; search.focus(); }
                }
            }, 400);
            
            // Flash success on reactor
            var rx = document.querySelector('.pos-rx-core');
            if (rx) {
                rx.style.transition = 'box-shadow 0.3s';
                rx.style.boxShadow = '0 0 40px rgba(16,185,129,0.5)';
                setTimeout(function() { rx.style.boxShadow = ''; }, 1500);
            }
        }
        
        function showEmailSlipModal() {
            // Try to get customer email if one was selected
            const customer = getCurrentCustomer ? getCurrentCustomer() : {id: '', name: ''};
            let customerEmail = '';
            
            // Look up customer email from customerData
            try {
                const customers = JSON.parse(document.getElementById('customerData').value);
                const found = customers.find(c => c.id === customer.id);
                if (found && found.email) customerEmail = found.email;
            } catch(e) {}
            
            document.getElementById('slipEmailTo').value = customerEmail;
            document.getElementById('emailSlipModal').style.display = 'flex';
            document.getElementById('slipEmailTo').focus();
        }
        
        function closeEmailSlipModal() {
            document.getElementById('emailSlipModal').style.display = 'none';
        }
        
        async function sendSlipEmail() {
            const email = document.getElementById('slipEmailTo').value.trim();
            if (!email || !email.includes('@')) {
                alert('Please enter a valid email address');
                return;
            }
            
            if (!lastSaleData) {
                alert('No sale data available');
                return;
            }
            
            try {
                const response = await fetch('/api/pos/email-slip', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        to_email: email,
                        sale_number: lastSaleData.saleNum,
                        sale_id: lastSaleData.saleId,
                        customer_name: lastSaleData.customerName,
                        items: lastSaleData.items,
                        subtotal: lastSaleData.subtotal,
                        vat: lastSaleData.vat,
                        total: lastSaleData.total,
                        payment_method: lastSaleData.method
                    })
                });
                
                const data = await response.json();
                if (data.success) {
                    alert('✅ Slip emailed to ' + email);
                    closeEmailSlipModal();
                } else {
                    alert('❌ ' + (data.error || 'Failed to send email'));
                }
            } catch(e) {
                alert('❌ Error: ' + e.message);
            }
        }
        
        // Add keyboard shortcut for email (4)
        document.addEventListener('keydown', function(e) {
            if (document.getElementById('printSlipModal').style.display === 'flex' && e.key === '4') {
                showEmailSlipModal();
            }
            if (document.getElementById('emailSlipModal').style.display === 'flex' && e.key === 'Escape') {
                closeEmailSlipModal();
            }
        });
        </script>
        
        <!-- Custom Item Modal - BIG & WELCOMING -->
        <div id="customItemModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:linear-gradient(135deg, #1e1e32 0%, #2a2a4a 100%);padding:40px;border-radius:20px;max-width:700px;width:95%;border:2px solid rgba(139,92,246,0.5);box-shadow:0 25px 50px rgba(0,0,0,0.5);">
                <div style="text-align:center;margin-bottom:30px;">
                    <div style="font-size:48px;margin-bottom:10px;">✏️</div>
                    <h2 style="margin:0;color:white;font-size:28px;" id="customModalTitle">Add Custom Item</h2>
                    <p style="color:rgba(255,255,255,0.6);font-size:16px;margin-top:10px;" id="customModalDesc">
                        Add any item not in your stock list - perfect for special orders, services, or once-off items
                    </p>
                </div>
                
                <div style="margin-bottom:25px;">
                    <label style="display:block;margin-bottom:8px;color:white;font-size:16px;font-weight:bold;">📝 Description *</label>
                    <input type="text" id="customDesc" placeholder="e.g. Special order bracket, Transport, Labour, etc..." 
                        style="width:100%;padding:18px;border-radius:10px;border:2px solid rgba(139,92,246,0.3);background:#1a1a2e;color:white;font-size:18px;box-sizing:border-box;"
                        onkeypress="if(event.key==='Enter'){document.getElementById('customPrice').focus();}">
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:25px;margin-bottom:30px;">
                    <div id="customPriceDiv">
                        <label style="display:block;margin-bottom:8px;color:white;font-size:16px;font-weight:bold;" id="customPriceLabel">💰 Price (incl VAT) *</label>
                        <input type="number" id="customPrice" placeholder="0.00" step="0.01"
                            style="width:100%;padding:18px;border-radius:10px;border:2px solid rgba(139,92,246,0.3);background:#1a1a2e;color:white;font-size:24px;text-align:right;box-sizing:border-box;"
                            onkeypress="if(event.key==='Enter'){document.getElementById('customAddBtn').click();}">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:16px;font-weight:bold;">📦 Quantity</label>
                        <input type="number" id="customQty" value="1" min="1"
                            style="width:100%;padding:18px;border-radius:10px;border:2px solid rgba(139,92,246,0.3);background:#1a1a2e;color:white;font-size:24px;text-align:center;box-sizing:border-box;">
                    </div>
                </div>
                
                <div style="display:flex;gap:15px;">
                    <button onclick="closeCustomItemModal()" style="flex:1;padding:18px;border-radius:10px;border:2px solid rgba(255,255,255,0.3);background:transparent;color:white;cursor:pointer;font-size:16px;font-weight:bold;">✕ Cancel (Esc)</button>
                    <button onclick="addCustomItem()" style="flex:2;padding:18px;border-radius:10px;border:none;background:linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%);color:white;cursor:pointer;font-size:18px;font-weight:bold;box-shadow:0 4px 15px rgba(139,92,246,0.4);" id="customAddBtn">GOOD: Add to Cart (Enter)</button>
                </div>
                
                <p style="text-align:center;color:rgba(255,255,255,0.4);font-size:13px;margin-top:20px;">
                    Tip: After adding, press <kbd style="background:#333;padding:2px 6px;border-radius:4px;">F4</kbd> to create a quote
                </p>
            </div>
        </div>
        
        <!-- Quick Quote Modal (F4 with empty cart) - Full quote without stock/customer -->
        <div id="quickQuoteModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);z-index:9999;justify-content:center;align-items:flex-start;overflow-y:auto;padding:20px;">
            <div style="background:linear-gradient(135deg, #1e1e32 0%, #2a2a4a 100%);padding:30px;border-radius:20px;max-width:800px;width:95%;border:2px solid rgba(16,185,129,0.5);box-shadow:0 25px 50px rgba(0,0,0,0.5);margin:auto;">
                <div style="text-align:center;margin-bottom:20px;">
                    <div style="font-size:40px;margin-bottom:8px;">📝</div>
                    <h2 style="margin:0;color:white;font-size:24px;">Quick Quote</h2>
                    <p style="color:rgba(255,255,255,0.6);font-size:13px;margin-top:5px;">
                        Create a quote without stock items or saved customer
                    </p>
                </div>
                
                <!-- Customer Section -->
                <div id="qqCustSection" style="background:rgba(0,0,0,0.2);padding:20px;border-radius:12px;margin-bottom:20px;">
                    <h3 style="margin:0 0 15px 0;color:#10b981;font-size:16px;">👤 Customer Details</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Name *</label>
                            <input type="text" id="qqCustName" placeholder="Company or person" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Phone</label>
                            <input type="text" id="qqCustPhone" placeholder="082 123 4567" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Email</label>
                            <input type="text" id="qqCustEmail" placeholder="email@example.com" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">VAT Number</label>
                            <input type="text" id="qqCustVat" placeholder="4123456789" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                    </div>
                    <div style="margin-top:15px;">
                        <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Address</label>
                        <input type="text" id="qqCustAddress" placeholder="Street, City, Code" 
                            style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                    </div>
                </div>
                
                <!-- Line Items Section -->
                <div style="background:rgba(0,0,0,0.2);padding:20px;border-radius:12px;margin-bottom:20px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                        <h3 style="margin:0;color:#f59e0b;font-size:16px;">📦 Line Items</h3>
                        <button onclick="qqAddLine()" style="background:#f59e0b;color:white;border:none;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;">+ Add Item</button>
                    </div>
                    <div id="qqLines" style="max-height:250px;overflow-y:auto;">
                        <!-- Line items will be added here -->
                    </div>
                    <div style="display:flex;justify-content:flex-end;margin-top:15px;padding-top:15px;border-top:1px solid rgba(255,255,255,0.1);">
                        <div style="text-align:right;">
                            <span style="color:var(--text-muted);font-size:14px;">Total (excl VAT):</span>
                            <span id="qqSubtotal" style="color:white;font-size:18px;font-weight:bold;margin-left:10px;">R0.00</span>
                        </div>
                    </div>
                    <div style="display:flex;justify-content:flex-end;margin-top:5px;">
                        <div style="text-align:right;">
                            <span style="color:var(--text-muted);font-size:14px;">VAT (15%):</span>
                            <span id="qqVat" style="color:white;font-size:16px;margin-left:10px;">R0.00</span>
                        </div>
                    </div>
                    <div style="display:flex;justify-content:flex-end;margin-top:5px;">
                        <div style="text-align:right;">
                            <span style="color:#10b981;font-size:16px;font-weight:bold;">Total (incl VAT):</span>
                            <span id="qqTotal" style="color:#10b981;font-size:22px;font-weight:bold;margin-left:10px;">R0.00</span>
                        </div>
                    </div>
                </div>
                
                <!-- Buttons -->
                <div style="display:flex;gap:15px;">
                    <button onclick="closeQuickQuoteModal()" style="flex:1;padding:15px;border-radius:10px;border:2px solid rgba(255,255,255,0.3);background:transparent;color:white;cursor:pointer;font-size:16px;">✕ Cancel</button>
                    <button onclick="submitQuickQuote()" style="flex:2;padding:15px;border-radius:10px;border:none;background:linear-gradient(135deg, #10b981 0%, #34d399 100%);color:white;cursor:pointer;font-size:18px;font-weight:bold;box-shadow:0 4px 15px rgba(16,185,129,0.4);">GOOD: Create Quote</button>
                </div>
            </div>
        </div>
        
        <!-- Quick PO Modal (F5 with empty cart) - Full PO without stock/supplier -->
        <div id="quickPOModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);z-index:9999;justify-content:center;align-items:flex-start;overflow-y:auto;padding:20px;">
            <div style="background:linear-gradient(135deg, #1e1e32 0%, #2a2a4a 100%);padding:30px;border-radius:20px;max-width:800px;width:95%;border:2px solid rgba(59,130,246,0.5);box-shadow:0 25px 50px rgba(0,0,0,0.5);margin:auto;">
                <div style="text-align:center;margin-bottom:20px;">
                    <div style="font-size:40px;margin-bottom:8px;">📦</div>
                    <h2 style="margin:0;color:white;font-size:24px;">Quick Purchase Order</h2>
                    <p style="color:rgba(255,255,255,0.6);font-size:13px;margin-top:5px;">
                        Create a PO without stock items or saved supplier
                    </p>
                </div>
                
                <!-- Supplier Section -->
                <div id="qpSupplierSection" style="background:rgba(0,0,0,0.2);padding:20px;border-radius:12px;margin-bottom:20px;">
                    <h3 style="margin:0 0 15px 0;color:#3b82f6;font-size:16px;">🏭 Supplier Details</h3>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Supplier Name *</label>
                            <input type="text" id="qpSupplierName" placeholder="Company name" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Phone</label>
                            <input type="text" id="qpSupplierPhone" placeholder="012 345 6789" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Email</label>
                            <input type="text" id="qpSupplierEmail" placeholder="orders@supplier.com" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">VAT Number</label>
                            <input type="text" id="qpSupplierVat" placeholder="4123456789" 
                                style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                        </div>
                    </div>
                </div>
                
                <!-- Line Items Section -->
                <div style="background:rgba(0,0,0,0.2);padding:20px;border-radius:12px;margin-bottom:20px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                        <h3 style="margin:0;color:#f59e0b;font-size:16px;">📋 Order Items</h3>
                        <button onclick="qpAddLine()" style="background:#f59e0b;color:white;border:none;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:13px;">+ Add Item</button>
                    </div>
                    <div id="qpLines" style="max-height:250px;overflow-y:auto;">
                        <!-- Line items will be added here -->
                    </div>
                    <div style="display:flex;justify-content:flex-end;margin-top:15px;padding-top:15px;border-top:1px solid rgba(255,255,255,0.1);">
                        <div style="text-align:right;">
                            <span style="color:var(--text-muted);font-size:14px;">Total Items:</span>
                            <span id="qpTotalItems" style="color:white;font-size:18px;font-weight:bold;margin-left:10px;">0</span>
                        </div>
                    </div>
                </div>
                
                <!-- Reference -->
                <div style="background:rgba(0,0,0,0.2);padding:15px;border-radius:12px;margin-bottom:15px;">
                    <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Reference (who is ordering)</label>
                    <input type="text" id="qpReference" placeholder="Name / reference" 
                        style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;">
                </div>
                
                <!-- Notes -->
                <div style="background:rgba(0,0,0,0.2);padding:15px;border-radius:12px;margin-bottom:20px;">
                    <label style="display:block;margin-bottom:5px;color:white;font-size:13px;">Notes / Special Instructions</label>
                    <textarea id="qpNotes" rows="2" placeholder="Delivery instructions, urgency, etc." 
                        style="width:100%;padding:10px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:14px;box-sizing:border-box;resize:none;"></textarea>
                </div>
                
                <!-- Buttons -->
                <div style="display:flex;gap:15px;">
                    <button onclick="closeQuickPOModal()" style="flex:1;padding:15px;border-radius:10px;border:2px solid rgba(255,255,255,0.3);background:transparent;color:white;cursor:pointer;font-size:16px;">✕ Cancel</button>
                    <button onclick="submitQuickPO()" style="flex:2;padding:15px;border-radius:10px;border:none;background:linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);color:white;cursor:pointer;font-size:18px;font-weight:bold;box-shadow:0 4px 15px rgba(59,130,246,0.4);">GOOD: Create PO</button>
                </div>
            </div>
        </div>
        
        <!-- Edit Customer Modal (F7) -->
        <div id="editCustomerModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:linear-gradient(135deg, #1e1e32 0%, #2a2a4a 100%);padding:40px;border-radius:20px;max-width:600px;width:95%;border:2px solid rgba(99,102,241,0.5);box-shadow:0 25px 50px rgba(0,0,0,0.5);">
                <div style="text-align:center;margin-bottom:25px;">
                    <div style="font-size:48px;margin-bottom:10px;">📝</div>
                    <h2 style="margin:0;color:white;font-size:28px;">Edit Customer Details</h2>
                    <p style="color:rgba(255,255,255,0.6);font-size:14px;margin-top:10px;" id="editCustSubtitle">
                        Update customer information
                    </p>
                </div>
                
                <input type="hidden" id="editCustId">
                
                <div style="margin-bottom:20px;">
                    <label style="display:block;margin-bottom:8px;color:white;font-size:16px;font-weight:bold;">👤 Customer Name *</label>
                    <input type="text" id="editCustName" placeholder="Company or person name" 
                        style="width:100%;padding:15px;border-radius:10px;border:2px solid rgba(99,102,241,0.3);background:#1a1a2e;color:white;font-size:18px;box-sizing:border-box;">
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">📱 Phone</label>
                        <input type="text" id="editCustPhone" placeholder="e.g. 082 123 4567" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">Email</label>
                        <input type="text" id="editCustEmail" placeholder="email@example.com" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">🏢 VAT Number</label>
                        <input type="text" id="editCustVat" placeholder="e.g. 4123456789" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">📍 Address</label>
                        <input type="text" id="editCustAddress" placeholder="Street, City, Code" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                </div>
                
                <div style="display:flex;gap:15px;">
                    <button onclick="closeEditCustomerModal()" style="flex:1;padding:15px;border-radius:10px;border:2px solid rgba(255,255,255,0.3);background:transparent;color:white;cursor:pointer;font-size:16px;">✕ Cancel</button>
                    <button onclick="submitEditCustomer()" style="flex:2;padding:15px;border-radius:10px;border:none;background:linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);color:white;cursor:pointer;font-size:18px;font-weight:bold;box-shadow:0 4px 15px rgba(99,102,241,0.4);">GOOD: Save Changes</button>
                </div>
            </div>
        </div>
        
        <!-- Quick Customer Modal for Quotes -->
        <div id="quickCustomerModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:linear-gradient(135deg, #1e1e32 0%, #2a2a4a 100%);padding:40px;border-radius:20px;max-width:600px;width:95%;border:2px solid rgba(16,185,129,0.5);box-shadow:0 25px 50px rgba(0,0,0,0.5);">
                <div style="text-align:center;margin-bottom:25px;">
                    <div style="font-size:48px;margin-bottom:10px;">👤</div>
                    <h2 style="margin:0;color:white;font-size:28px;">Customer Details for Quote</h2>
                    <p style="color:rgba(255,255,255,0.6);font-size:14px;margin-top:10px;">
                        Enter customer details for this quote (will also be saved for future use)
                    </p>
                </div>
                
                <div style="margin-bottom:20px;">
                    <label style="display:block;margin-bottom:8px;color:white;font-size:16px;font-weight:bold;">👤 Customer Name *</label>
                    <input type="text" id="quickCustName" placeholder="Company or person name" 
                        style="width:100%;padding:15px;border-radius:10px;border:2px solid rgba(16,185,129,0.3);background:#1a1a2e;color:white;font-size:18px;box-sizing:border-box;">
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">📱 Phone</label>
                        <input type="text" id="quickCustPhone" placeholder="e.g. 082 123 4567" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">Email</label>
                        <input type="text" id="quickCustEmail" placeholder="email@example.com" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">🏢 VAT Number</label>
                        <input type="text" id="quickCustVat" placeholder="e.g. 4123456789" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:8px;color:white;font-size:14px;">📍 Address</label>
                        <input type="text" id="quickCustAddress" placeholder="Street, City, Code" 
                            style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(255,255,255,0.2);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;">
                    </div>
                </div>
                
                <div style="margin-bottom:20px;">
                    <label style="display:block;margin-bottom:8px;color:white;font-size:16px;font-weight:bold;">🧑‍💼 Salesman</label>
                    <select id="quickQuoteSalesman" style="width:100%;padding:12px;border-radius:8px;border:2px solid rgba(16,185,129,0.3);background:#1a1a2e;color:white;font-size:16px;box-sizing:border-box;-webkit-appearance:menulist;appearance:menulist;">
                        {pos_salesman_options}
                    </select>
                </div>
                
                <div style="display:flex;gap:15px;">
                    <button onclick="closeQuickCustomerModal()" style="flex:1;padding:15px;border-radius:10px;border:2px solid rgba(255,255,255,0.3);background:transparent;color:white;cursor:pointer;font-size:16px;">✕ Cancel</button>
                    <button onclick="submitQuickCustomer()" style="flex:2;padding:15px;border-radius:10px;border:none;background:linear-gradient(135deg, #10b981 0%, #34d399 100%);color:white;cursor:pointer;font-size:18px;font-weight:bold;box-shadow:0 4px 15px rgba(16,185,129,0.4);" id="quickCustSubmitBtn">GOOD: Create Quote</button>
                </div>
            </div>
        </div>
        
        <!-- Credit Note Modal -->
        <div id="creditNoteModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:#1e1e32;padding:25px;border-radius:12px;max-width:500px;width:90%;border:1px solid rgba(239,68,68,0.3);">
                <h3 style="margin:0 0 15px 0;color:white;">Credit Note from Invoice</h3>
                <p style="color:rgba(255,255,255,0.6);font-size:13px;margin-bottom:15px;" id="cnCustomerName">
                    Select a customer first (F8)
                </p>
                
                <div id="invoiceList" style="max-height:300px;overflow-y:auto;margin-bottom:15px;">
                    <p style="color:rgba(255,255,255,0.5);text-align:center;padding:20px;">Loading invoices...</p>
                </div>
                
                <div style="display:flex;gap:10px;">
                    <button onclick="closeCreditNoteModal()" style="flex:1;padding:12px;border-radius:6px;border:1px solid rgba(255,255,255,0.2);background:transparent;color:white;cursor:pointer;">Cancel</button>
                </div>
            </div>
        </div>
        
        <!-- Print Slip Modal -->
        <div id="printSlipModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);z-index:9999;justify-content:center;align-items:flex-start;overflow-y:auto;padding:20px;">
            <div style="background:white;border-radius:8px;max-width:450px;width:100%;margin:auto;">
                <div id="slipContent" style="padding:12px;font-family:'Courier New',monospace;font-size:13px;color:#000;"></div>
                <div style="padding:20px;border-top:2px solid #eee;display:flex;gap:15px;flex-wrap:wrap;" id="printButtonRow">
                    <button id="btnPrintThermal" tabindex="0" onclick="doPrintSlip('thermal')" 
                        onfocus="this.style.outline='4px solid yellow';this.style.outlineOffset='2px';this.style.transform='scale(1.05)'" 
                        onblur="this.style.outline='none';this.style.transform='scale(1)'"
                        style="flex:1;padding:18px;border-radius:8px;border:3px solid #10b981;background:#10b981;color:white;cursor:pointer;font-weight:bold;font-size:16px;transition:transform 0.1s;" autofocus>🖨️ THERMAL [1]</button>
                    <button id="btnPrintA4" tabindex="0" onclick="doPrintSlip('a4')" 
                        onfocus="this.style.outline='4px solid yellow';this.style.outlineOffset='2px';this.style.transform='scale(1.05)'" 
                        onblur="this.style.outline='none';this.style.transform='scale(1)'"
                        style="flex:1;padding:18px;border-radius:8px;border:3px solid #3b82f6;background:#3b82f6;color:white;cursor:pointer;font-weight:bold;font-size:16px;transition:transform 0.1s;">📄 A4 [2]</button>
                    <button id="btnPrintSkip" tabindex="0" onclick="closePrintModal()" 
                        onfocus="this.style.outline='4px solid yellow';this.style.outlineOffset='2px';this.style.transform='scale(1.05)'" 
                        onblur="this.style.outline='none';this.style.transform='scale(1)'"
                        style="flex:1;padding:18px;border-radius:8px;border:2px solid #ccc;background:white;color:#333;cursor:pointer;font-size:16px;transition:transform 0.1s;">✕ Skip [3]</button>
                </div>
                <div style="padding:10px 20px 20px 20px;border-top:1px solid #eee;">
                    <button onclick="showEmailSlipModal()" style="width:100%;padding:15px;border-radius:8px;border:2px solid #8b5cf6;background:white;color:#8b5cf6;cursor:pointer;font-size:14px;">Email Slip to Customer [4]</button>
                </div>
                <div style="text-align:center;padding:10px;color:#666;font-size:12px;">
                    Use Tab/Arrows to navigate • Enter to select • Or press 1, 2, 3, 4
                </div>
            </div>
        </div>
        
        <!-- Email Slip Modal -->
        <div id="emailSlipModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.9);z-index:10000;justify-content:center;align-items:center;">
            <div style="background:var(--card);border-radius:12px;max-width:400px;width:90%;padding:25px;">
                <h3 style="margin:0 0 15px 0;">Email Slip</h3>
                <input type="email" id="slipEmailTo" placeholder="customer@email.com" 
                       style="width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:16px;margin-bottom:15px;">
                <div style="display:flex;gap:10px;">
                    <button onclick="closeEmailSlipModal()" style="flex:1;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;">Cancel</button>
                    <button onclick="sendSlipEmail()" style="flex:1;padding:12px;border-radius:8px;border:none;background:#10b981;color:white;cursor:pointer;font-weight:bold;">Send</button>
                </div>
            </div>
        </div>
        
        <script>
        // ═══════════════════════════════════════════════════════════
        // OFFLINE POS — IndexedDB Queue & Auto-Sync
        // Safe: If anything fails, POS works exactly as before
        // ═══════════════════════════════════════════════════════════
        (function() {
            const DB_NAME = 'clickai_offline';
            const DB_VERSION = 2;
            const STORE_NAME = 'pos_queue';
            
            function openDB() {
                return new Promise((resolve, reject) => {
                    const req = indexedDB.open(DB_NAME, DB_VERSION);
                    req.onupgradeneeded = (e) => {
                        const db = e.target.result;
                        ['pos_queue','expense_queue','quote_queue','customer_queue'].forEach(s => {
                            if (!db.objectStoreNames.contains(s)) db.createObjectStore(s, { keyPath: 'id', autoIncrement: true });
                        });
                    };
                    req.onsuccess = (e) => resolve(e.target.result);
                    req.onerror = (e) => reject(e.target.error);
                });
            }
            
            // Queue a sale for later sync
            window.queueOfflineSale = async function(saleData) {
                const db = await openDB();
                return new Promise((resolve, reject) => {
                    const tx = db.transaction(STORE_NAME, 'readwrite');
                    saleData.queued_at = new Date().toISOString();
                    const req = tx.objectStore(STORE_NAME).add(saleData);
                    req.onsuccess = () => { console.log('[OFFLINE] Sale queued: R' + saleData.total); resolve(); };
                    req.onerror = () => reject(req.error);
                });
            };
            
            // Get all queued sales
            async function getQueue() {
                const db = await openDB();
                return new Promise((resolve, reject) => {
                    const req = db.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).getAll();
                    req.onsuccess = () => resolve(req.result || []);
                    req.onerror = () => resolve([]);
                });
            }
            
            // Clear queue after sync
            async function clearQueue() {
                const db = await openDB();
                return new Promise((resolve) => {
                    const req = db.transaction(STORE_NAME, 'readwrite').objectStore(STORE_NAME).clear();
                    req.onsuccess = () => resolve();
                    req.onerror = () => resolve();
                });
            }
            
            // Sync offline sales to server
            window.syncOfflineSales = async function() {
                if (!navigator.onLine) { alert('Still offline — connect to internet first.'); return; }
                
                const queue = await getQueue();
                if (queue.length === 0) { updateUI(); return; }
                
                const textEl = document.getElementById('offlineText');
                if (textEl) textEl.textContent = 'SYNCING ' + queue.length + '...';
                
                try {
                    const resp = await fetch('/api/pos/sync-offline', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ sales: queue })
                    });
                    const data = await resp.json();
                    
                    if (data.success) {
                        await clearQueue();
                        let msg = 'SYNC COMPLETE\\n\\n' + data.message;
                        if (data.errors && data.errors.length) msg += '\\n\\nErrors:\\n' + data.errors.join('\\n');
                        alert(msg);
                        updateUI();
                        if (data.synced > 0) location.reload();
                    } else {
                        alert('Sync failed: ' + (data.error || 'Unknown'));
                        updateUI();
                    }
                } catch (err) {
                    alert('Sync failed: ' + err.message);
                    updateUI();
                }
            };
            
            // Update online/offline indicator
            async function updateUI() {
                const offlineEl = document.getElementById('offlineIndicator');
                const onlineEl = document.getElementById('onlineIndicator');
                const countEl = document.getElementById('offlineCount');
                const textEl = document.getElementById('offlineText');
                if (!offlineEl) return;
                
                try {
                    const queue = await getQueue();
                    const n = queue.length;
                    
                    if (!navigator.onLine) {
                        // Offline
                        offlineEl.style.display = 'inline-flex';
                        offlineEl.style.alignItems = 'center';
                        offlineEl.style.background = 'rgba(239,68,68,0.2)';
                        offlineEl.style.color = '#fca5a5';
                        if (onlineEl) onlineEl.style.display = 'none';
                        textEl.textContent = '🔴 OFFLINE';
                        if (n > 0) { countEl.style.display = 'inline'; countEl.textContent = n + ' queued'; }
                        else { countEl.style.display = 'none'; }
                    } else if (n > 0) {
                        // Online with pending sales — auto-sync
                        offlineEl.style.display = 'inline-flex';
                        offlineEl.style.alignItems = 'center';
                        offlineEl.style.background = 'rgba(245,158,11,0.2)';
                        offlineEl.style.color = '#fcd34d';
                        if (onlineEl) onlineEl.style.display = 'none';
                        textEl.textContent = '⚠️ SYNC';
                        countEl.style.display = 'inline';
                        countEl.textContent = n + ' pending';
                        // Auto-sync after 2 seconds
                        setTimeout(() => syncOfflineSales(), 2000);
                    } else {
                        // Online, nothing pending
                        offlineEl.style.display = 'none';
                        if (onlineEl) { onlineEl.style.display = 'inline'; setTimeout(() => { onlineEl.style.display = 'none'; }, 3000); }
                    }
                } catch (e) { console.log('[OFFLINE] UI update failed:', e); }
            }
            window.updateOfflineIndicator = updateUI;
            
            // Listen for connection changes
            window.addEventListener('online', () => { console.log('[OFFLINE] Internet restored'); updateUI(); });
            window.addEventListener('offline', () => { console.log('[OFFLINE] Internet lost'); updateUI(); });
            
            // Check on load
            updateUI();
            
            // Cache POS page for offline via service worker
            if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
                navigator.serviceWorker.controller.postMessage({ type: 'CACHE_POS' });
            }
        })();
        </script>
        '''
        _safe_uid = str(current_user_id or '').replace("'", "")
        _safe_uname = str(current_user_name or 'Me').replace("'", "").replace("\\", "")
        
        # Fix: pos_js is a plain string, not an f-string, so {_safe_uid} and {_safe_uname}
        # remain as literal text. Replace them now that the variables are defined.
        pos_js = pos_js.replace("{_safe_uid}", _safe_uid).replace("{_safe_uname}", _safe_uname)
        
        return f'''<!DOCTYPE html>
    <html lang="en" data-theme="{_pos_theme}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>POS - Click AI</title>
        <link rel="manifest" href="/manifest.json">
        <meta name="theme-color" content="#8b5cf6">
        {CSS}
        {pos_css}
        <style>
        .stock-row.highlighted {{
            background: linear-gradient(90deg, rgba(99, 102, 241, 0.25), rgba(99, 102, 241, 0.1)) !important;
            outline: 2px solid var(--primary);
        }}
        </style>
    </head>
    <body>
        <script>
        /* ═══ F11 CORE — must be before pos_js ═══ */
        var f11Mode = false;
        var f11SelectedRow = 0;
        
        function toggleF11() {{
            f11Mode = !f11Mode;
            document.body.classList.toggle('f11-mode', f11Mode);
            if (f11Mode) {{
                try {{ document.documentElement.requestFullscreen(); }} catch(e) {{}}
                if (typeof renderF11Table === 'function') renderF11Table();
                if (typeof syncF11Buttons === 'function') syncF11Buttons();
                if (typeof updateF11CustName === 'function') updateF11CustName();
                setTimeout(function() {{
                    var hdr = document.querySelector('.f11-header');
                    var wrap = document.querySelector('.f11-order-wrap');
                    if (hdr && wrap) {{ wrap.style.top = hdr.offsetHeight + 'px'; }}
                }}, 50);
                var el = document.getElementById('f11Search');
                if (el) {{ el.value = ''; el.focus(); }}
            }} else {{
                try {{ if(document.fullscreenElement) document.exitFullscreen(); }} catch(e) {{}}
                var el = document.getElementById('stockSearch');
                if (el) el.focus();
            }}
        }}
        </script>
        <script>
        document.addEventListener('fullscreenchange', function() {{
            // DO NOTHING — browser fullscreen may drop due to prompt/alert/permissions
            // but our F11 CSS mode must stay active. Only toggleF11() can exit F11.
        }});
        
        // === POS FORCE FULLSCREEN ON LOAD ===
        // POS must always run in fullscreen mode for cashiers
        document.addEventListener('DOMContentLoaded', function() {{
            // Small delay to let the page render first, then auto-enter F11
            setTimeout(function() {{
                if (!f11Mode) {{
                    toggleF11();
                }}
            }}, 300);
        }});
        </script>
        <header class="pos-header" style="padding:6px 20px 4px;">
            <div class="pos-header-nav">
                <a href="/">Dashboard</a>
                <a href="/pos" class="active">POS</a>
                <a href="/pos/history">History</a>
                <a href="/stock">Stock</a>
                <a href="/customers">Customers</a>
                <span id="offlineIndicator" style="display:none;padding:4px 10px;font-size:11px;font-weight:700;margin-left:8px;cursor:pointer;" onclick="syncOfflineSales()" title="Click to sync when online">
                    <span id="offlineText">🔴 OFFLINE</span>
                    <span id="offlineCount" style="display:none;background:rgba(255,255,255,0.2);padding:1px 6px;margin-left:4px;font-size:10px;"></span>
                </span>
                <span id="onlineIndicator" style="padding:2px 8px;font-size:10px;color:#10b981;display:none;">🟢 Online</span>
            </div>
        </header>
    
        <div class="pos-reactor-wrap">
            <div class="pos-reactor-hero">
                <div class="pos-btn-flank L">
                    <button class="pos-hud-btn" onclick="completeSale('cash')" id="btnCash" disabled><span class="pk">F1</span>CASH</button>
                    <button class="pos-hud-btn" onclick="completeSale('card')" id="btnCard" disabled><span class="pk">F2</span>CARD</button>
                    <button class="pos-hud-btn" onclick="completeSale('account')" id="btnAccount" disabled><span class="pk">F3</span>ACCOUNT</button>
                    <button class="pos-hud-btn" onclick="createQuote()" id="btnQuote" disabled><span class="pk">F4</span>QUOTE</button>
                </div>
                <div class="pos-reactor-cn"></div>
                <div class="pos-rx">
                    <div class="j-rg r1"></div><div class="j-rg r2"></div><div class="j-rg r3"></div><div class="j-rg r4"></div>
                    <div class="pos-rx-core">
                        <div class="j-brand">CLICK.AI</div>
                        <div class="j-sub">// POINT OF SALE</div>
                        <div class="pos-hud-total" id="headerTotal">R0.00</div>
                    </div>
                </div>
                <div class="pos-reactor-cn R"></div>
                <div class="pos-btn-flank R">
                    <button class="pos-hud-btn" onclick="createPO()" id="btnPO" disabled>PO<span class="pk">F5</span></button>
                    <button class="pos-hud-btn" onclick="createInvoice()" id="btnInvoice" disabled>INVOICE<span class="pk">F6</span></button>
                    <button class="pos-hud-btn" onclick="createCreditNote()" id="btnCredit" disabled>CREDIT NOTE<span class="pk">F10</span></button>
                    <button class="pos-hud-btn" onclick="toggleF11()">FULLSCREEN<span class="pk">F11</span></button>
                    <button class="pos-hud-btn" onclick="window.location='/cashup'" style="border-color:rgba(0,255,136,0.3);color:#00ff88;">CASH UP<span class="pk">💰</span></button>
                </div>
                <div class="pos-lbl"><span>POINT OF SALE</span></div>
            </div>
            <div class="pos-entity-bar">
                <button class="pos-entity-btn L active" id="btnCust" onclick="toggleEntity('customer')" title="F8"><span class="pk">F8</span>C</button>
                <div class="entity-dropdown" style="position:relative;">
                    <input type="text" class="pos-entity-input entity-search" id="entitySearch" placeholder="F7 · CASH SALE" onclick="openEntityDropdown()" autocomplete="off">
                    <input type="hidden" id="entityValue" value="">
                    <div class="entity-list" id="entityList" style="display:none;position:absolute;top:100%;left:0;right:0;z-index:9500;max-height:300px;overflow-y:auto;background:rgba(10,20,40,0.95);border:1px solid rgba(80,180,255,0.2);"></div>
                </div>
                <button class="pos-entity-btn R" id="btnSupp" onclick="toggleEntity('supplier')" title="F9">S<span class="pk">F9</span></button>
                <input type="hidden" id="supplierData" value='{supplier_json}'>
                <input type="hidden" id="customerData" value='{customer_json}'>
                <input type="hidden" id="posSettings" value='{pos_settings_json}'>
            </div>
        </div>
    
        <!-- F11 FULLSCREEN HEADER -->
        <div class="f11-header">
            <div class="f11-left">
                <button class="f11-btn" onclick="completeSale('cash')" id="f11Cash" disabled><span class="pk">F1</span>CASH</button>
                <button class="f11-btn" onclick="completeSale('card')" id="f11Card" disabled><span class="pk">F2</span>CARD</button>
                <button class="f11-btn" onclick="completeSale('account')" id="f11Account" disabled><span class="pk">F3</span>ACC</button>
                <button class="f11-btn" onclick="createQuote()" id="f11Quote" disabled><span class="pk">F4</span>QTE</button>
                <button class="f11-btn" onclick="createPO()" id="f11PO" disabled><span class="pk">F5</span>PO</button>
                <button class="f11-btn" onclick="createInvoice()" id="f11Invoice" disabled><span class="pk">F6</span>INV</button>
                <button class="f11-btn" onclick="showEditCustomerModal()"><span class="pk">F7</span>EDIT</button>
                <button class="f11-btn" onclick="toggleEntity('customer')"><span class="pk">F8</span>CUST</button>
                <button class="f11-btn" onclick="toggleEntity('supplier')"><span class="pk">F9</span>SUPP</button>
                <button class="f11-btn" onclick="createCreditNote()" id="f11Credit" disabled><span class="pk">F10</span>CR</button>
                <button class="f11-btn" onclick="showCustomItemModal()" style="border-color:rgba(139,92,246,0.3);color:#c4b5fd;">+ITEM</button>
            </div>
            <div class="f11-right">
                <div class="f11-cust" id="f11CustName">Countersale</div>
                <div class="f11-total" id="f11Total">R0.00</div>
                <button class="f11-exit" onclick="toggleF11()"><span class="pk">F11</span>EXIT</button>
            </div>
        </div>
    
        <!-- F11 ORDER TABLE -->
        <div class="f11-order-wrap">
            <div class="f11-search">
                <input type="text" id="f11Search" placeholder="Scan barcode or type code / description..." autocomplete="off">
            </div>
            <div class="f11-table-wrap">
                <table class="f11-table">
                    <thead><tr>
                        <th style="width:140px;">CODE</th><th>DESCRIPTION</th>
                        <th class="r" style="width:60px;">QTY</th><th class="r" style="width:100px;">PRICE</th>
                        <th class="r" style="width:80px;">DISC</th><th class="r" style="width:110px;">TOTAL</th>
                        <th style="width:80px;">ON-HAND</th>
                        <th style="width:44px;"></th>
                    </tr></thead>
                    <tbody id="f11Body"></tbody>
                </table>
            </div>
        </div>
    
        <main class="container" style="padding-top:8px;height:calc(100vh - 250px);overflow:hidden;display:flex;flex-direction:column;">
            {pos_html}
        </main>
        
        {get_zane_chat()}
        {pos_js}
        <script>
        // Cashier fallback - ensure currentCashierId is never null
        if (!currentCashierId) {{
            currentCashierId = '{_safe_uid}';
            currentCashierName = '{_safe_uname}';
        }}
        </script>
    
        <!-- Custom prompt modal (replaces native prompt which breaks F11 fullscreen) -->
        <div id="posPromptOverlay" style="display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.6);z-index:99999;align-items:center;justify-content:center;">
            <div style="background:#1a1a2e;border:1px solid rgba(99,102,241,0.4);border-radius:12px;padding:24px 28px;min-width:320px;box-shadow:0 8px 32px rgba(0,0,0,0.5);">
                <div id="posPromptLabel" style="color:#e2e8f0;font-size:15px;font-weight:600;margin-bottom:14px;"></div>
                <input type="text" id="posPromptInput" style="width:100%;padding:10px 14px;border-radius:8px;border:1px solid rgba(99,102,241,0.4);background:#0f0f23;color:#fff;font-size:16px;outline:none;" />
                <div style="display:flex;gap:10px;margin-top:16px;justify-content:flex-end;">
                    <button onclick="posPromptCancel()" style="padding:8px 20px;border-radius:8px;border:1px solid rgba(255,255,255,0.15);background:rgba(255,255,255,0.05);color:#aaa;cursor:pointer;font-size:14px;">Cancel</button>
                    <button onclick="posPromptOk()" style="padding:8px 20px;border-radius:8px;border:none;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;cursor:pointer;font-size:14px;font-weight:600;">OK</button>
                </div>
            </div>
        </div>
        <script>
        var _posPromptResolve = null;
        function posPrompt(label, defaultVal) {{
            return new Promise(function(resolve) {{
                _posPromptResolve = resolve;
                document.getElementById('posPromptLabel').textContent = label;
                var inp = document.getElementById('posPromptInput');
                inp.value = defaultVal || '';
                var overlay = document.getElementById('posPromptOverlay');
                overlay.style.display = 'flex';
                setTimeout(function() {{ inp.focus(); inp.select(); }}, 50);
            }});
        }}
        function posPromptOk() {{
            var val = document.getElementById('posPromptInput').value;
            document.getElementById('posPromptOverlay').style.display = 'none';
            if (_posPromptResolve) {{ _posPromptResolve(val); _posPromptResolve = null; }}
        }}
        function posPromptCancel() {{
            document.getElementById('posPromptOverlay').style.display = 'none';
            if (_posPromptResolve) {{ _posPromptResolve(null); _posPromptResolve = null; }}
        }}
        document.getElementById('posPromptInput').addEventListener('keydown', function(e) {{
            if (e.key === 'Enter') {{ e.preventDefault(); posPromptOk(); }}
            if (e.key === 'Escape') {{ e.preventDefault(); posPromptCancel(); }}
        }});
        document.getElementById('posPromptOverlay').addEventListener('click', function(e) {{
            if (e.target === this) posPromptCancel();
        }});
        </script>
    
        <script>
        /* ═══ F11 FULLSCREEN ORDER MODE ═══ */
        // f11Mode and f11SelectedRow declared in earlier script block
        // toggleF11 defined in earlier script block
    
        function renderF11Table() {{
            const tbody = document.getElementById('f11Body');
            if (!tbody) return;
            if (cart.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:#5a8aaa;font-size:16px;">Scan barcode or type to add items...</td></tr>';
                document.getElementById('f11Total').textContent = 'R0.00';
                return;
            }}
            let html = '';
            let grandTotal = 0;
            cart.forEach((item, idx) => {{
                const lineTotal = item.price * item.qty;
                grandTotal += lineTotal;
                const sel = idx === f11SelectedRow ? ' f11-sel' : '';
                // Find stock qty
                const stockRow = document.querySelector('.stock-row[data-id="' + item.id + '"]');
                const onHand = stockRow ? stockRow.getAttribute('data-qty') : '—';
                html += '<tr class="' + sel + '" onclick="f11SelectedRow=' + idx + ';renderF11Table();">';
                html += '<td class="code">' + item.code + '</td>';
                html += '<td>' + item.desc + '</td>';
                html += '<td class="r qty" style="cursor:pointer;" onclick="event.stopPropagation();f11EditQty(' + idx + ')">' + item.qty + '</td>';
                html += '<td class="r" style="cursor:pointer;" onclick="event.stopPropagation();f11EditPrice(' + idx + ')">R' + item.price.toFixed(2) + '</td>';
                html += '<td class="r" style="color:#5a8aaa;cursor:pointer;" onclick="event.stopPropagation();f11EditDisc(' + idx + ')">' + (item.disc ? item.disc + '%' : '—') + '</td>';
                html += '<td class="r tot">R' + lineTotal.toFixed(2) + '</td>';
                html += '<td><span class="f11-onhand">' + onHand + '</span></td>';
                html += '<td style="text-align:center;"><button class="f11-del-btn" onclick="event.stopPropagation();f11RemoveItem(' + idx + ')" title="Remove item">✕</button></td>';
                html += '</tr>';
            }});
            tbody.innerHTML = html;
            const vat = Math.round(grandTotal * 0.15 * 100) / 100;
            document.getElementById('f11Total').textContent = 'R' + (grandTotal + vat).toFixed(2);
        }}
    
        function syncF11Buttons() {{
            const hasItems = cart.length > 0;
            const hasCust = !!document.getElementById('entityValue').value;
            ['f11Cash','f11Card'].forEach(id => {{ const el = document.getElementById(id); if(el) el.disabled = !hasItems; }});
            ['f11Account','f11Invoice','f11Credit'].forEach(id => {{ const el = document.getElementById(id); if(el) el.disabled = !(hasItems && hasCust); }});
            ['f11Quote','f11PO'].forEach(id => {{ const el = document.getElementById(id); if(el) el.disabled = !hasItems; }});
        }}
    
        async function f11EditQty(idx) {{
            if (idx < 0 || idx >= cart.length) return;
            var item = cart[idx];
            var newQty = await posPrompt('Qty for ' + item.code + ':', item.qty);
            if (newQty === null) return;
            var qty = parseFloat(newQty);
            if (isNaN(qty) || qty < 0) {{ alert('Invalid qty'); return; }}
            if (qty === 0) {{ cart.splice(idx, 1); if (f11SelectedRow >= cart.length) f11SelectedRow = Math.max(0, cart.length - 1); }}
            else {{ item.qty = qty; }}
            updateCart(); renderF11Table(); syncF11Buttons();
        }}
    
        async function f11EditPrice(idx) {{
            if (idx < 0 || idx >= cart.length) return;
            var item = cart[idx];
            var newPrice = await posPrompt('Price for ' + item.code + ':', item.price.toFixed(2));
            if (newPrice === null) return;
            var price = parseFloat(newPrice);
            if (isNaN(price) || price < 0) {{ alert('Invalid price'); return; }}
            item.price = price;
            updateCart(); renderF11Table(); syncF11Buttons();
        }}
    
        async function f11EditDisc(idx) {{
            if (idx < 0 || idx >= cart.length) return;
            var item = cart[idx];
            var cur = item.disc || 0;
            var newDisc = await posPrompt('Discount % for ' + item.code + ':', cur);
            if (newDisc === null) return;
            var disc = parseFloat(newDisc);
            if (isNaN(disc) || disc < 0 || disc > 100) {{ alert('Invalid discount (0-100)'); return; }}
            item.disc = disc;
            updateCart(); renderF11Table(); syncF11Buttons();
        }}
    
        function f11RemoveItem(idx) {{
            if (idx < 0 || idx >= cart.length) return;
            cart.splice(idx, 1);
            if (f11SelectedRow >= cart.length) f11SelectedRow = Math.max(0, cart.length - 1);
            updateCart(); renderF11Table(); syncF11Buttons();
        }}
    
        function updateF11CustName() {{
            const el = document.getElementById('f11CustName');
            if (!el) return;
            const search = document.getElementById('entitySearch');
            el.textContent = (search && search.value) ? search.value : 'Countersale';
        }}
    
        // F11 smart search with live dropdown
        document.addEventListener('DOMContentLoaded', function() {{
            const f11Input = document.getElementById('f11Search');
            const f11DD = document.getElementById('f11Dropdown');
            if (!f11Input || !f11DD) return;
            let f11Matches = [];
            let f11Sel = -1;
    
            function f11ShowDD() {{
                const rect = f11Input.getBoundingClientRect();
                f11DD.style.top = (rect.bottom + 2) + 'px';
                f11DD.classList.add('show');
            }}
    
            function f11FilterDD() {{
                let raw = f11Input.value.trim();
                if (!raw) {{ f11DD.classList.remove('show'); f11Matches = []; f11Sel = -1; return; }}
                let qty = 1, searchTerm = raw;
                const star = raw.indexOf('*');
                if (star > 0) {{
                    const num = parseInt(raw.substring(0, star), 10);
                    if (num > 0) {{ qty = num; searchTerm = raw.substring(star + 1).trim(); }}
                }}
                const terms = searchTerm.toLowerCase().replace(/\s*x\s*/gi, 'x').split(/\s+/).filter(t => t.length > 0);
                if (!terms.length) {{ f11DD.classList.remove('show'); return; }}
    
                f11Matches = [];
                const rows = document.querySelectorAll('.stock-row');
                for (let row of rows) {{
                    let data = ((row.getAttribute('data-code') || '') + ' ' + (row.getAttribute('data-desc') || '')).toLowerCase().replace(/\s*x\s*/gi, 'x');
                    if (terms.every(t => data.indexOf(t) !== -1)) {{
                        f11Matches.push({{
                            el: row, id: row.getAttribute('data-id'),
                            code: row.getAttribute('data-code') || '',
                            desc: row.getAttribute('data-desc') || '',
                            price: parseFloat(row.getAttribute('data-price')) || 0,
                            qty: qty, related: false
                        }});
                        if (f11Matches.length >= 500) break;
                    }}
                }}
                f11Sel = f11Matches.length > 0 ? 0 : -1;
                f11RenderDD();
            }}
    
            function f11RenderDD() {{
                if (f11Matches.length === 0) {{
                    f11DD.innerHTML = '<div class="f11-dd-empty">No matches found</div>';
                    f11ShowDD();
                    return;
                }}
                var seenRH = false;
                f11DD.innerHTML = f11Matches.map(function(m, i) {{
                    var hdr = '';
                    if (m.related && !seenRH) {{ seenRH = true; hdr = '<div style="padding:5px 16px;font-size:10px;font-weight:700;color:#f59e0b;letter-spacing:2px;border-top:1px solid rgba(245,158,11,0.3);background:rgba(245,158,11,0.05);">⚡ ALSO NEEDED?</div>'; }}
                    return hdr + '<div class="f11-dd-item' + (i === f11Sel ? ' sel' : '') + (m.related ? ' f11-dd-rel' : '') + '" data-idx="' + i + '">' +
                    '<span class="f11-dd-code">' + m.code + '</span>' +
                    '<span class="f11-dd-desc">' + m.desc.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</span>' +
                    '<span class="f11-dd-price">R' + m.price.toFixed(2) + '</span></div>';
                }}).join('');
                f11ShowDD();
    
                f11DD.querySelectorAll('.f11-dd-item').forEach(el => {{
                    el.addEventListener('click', function() {{
                        f11AddMatch(parseInt(this.getAttribute('data-idx')));
                    }});
                }});
    
                const selEl = f11DD.querySelector('.sel');
                if (selEl) selEl.scrollIntoView({{block: 'nearest'}});
            }}
    
            function f11AddMatch(idx) {{
                if (idx < 0 || idx >= f11Matches.length) return;
                const m = f11Matches[idx];
                const existing = cart.find(item => item.id === m.id);
                if (existing) {{ existing.qty += m.qty; }}
                else {{ cart.push({{id: m.id, code: m.code, desc: m.desc, price: m.price, qty: m.qty, maxQty: 99999}}); }}
                updateCart();
                renderF11Table();
                syncF11Buttons();
                f11SelectedRow = cart.length - 1;
                renderF11Table();
                f11Input.value = '';
                f11DD.classList.remove('show');
                f11Matches = [];
                f11Sel = -1;
                f11Input.focus();
            }}
    
            f11Input.addEventListener('input', f11FilterDD);
    
            f11Input.addEventListener('keydown', function(e) {{
                if (f11DD.classList.contains('show') && f11Matches.length > 0) {{
                    if (e.key === 'ArrowDown') {{ e.preventDefault(); f11Sel = Math.min(f11Sel + 1, f11Matches.length - 1); f11RenderDD(); return; }}
                    if (e.key === 'ArrowUp') {{ e.preventDefault(); f11Sel = Math.max(f11Sel - 1, 0); f11RenderDD(); return; }}
                    if (e.key === 'Enter') {{ e.preventDefault(); f11AddMatch(f11Sel); return; }}
                    if (e.key === 'Escape') {{ e.preventDefault(); f11DD.classList.remove('show'); return; }}
                }}
                if (e.key === 'Delete' && cart.length > 0 && !f11DD.classList.contains('show')) {{
                    e.preventDefault();
                    cart.splice(f11SelectedRow, 1);
                    if (f11SelectedRow >= cart.length) f11SelectedRow = Math.max(0, cart.length - 1);
                    updateCart();
                    renderF11Table();
                    syncF11Buttons();
                }}
                if (!f11DD.classList.contains('show') && !f11Input.value.trim()) {{
                    if (e.key === 'ArrowDown') {{ e.preventDefault(); f11SelectedRow = Math.min(f11SelectedRow + 1, cart.length - 1); renderF11Table(); }}
                    if (e.key === 'ArrowUp') {{ e.preventDefault(); f11SelectedRow = Math.max(f11SelectedRow - 1, 0); renderF11Table(); }}
                    if ((e.key === '+' || e.key === '=') && cart.length > 0) {{ e.preventDefault(); cart[f11SelectedRow].qty++; updateCart(); renderF11Table(); syncF11Buttons(); }}
                    if (e.key === '-' && cart.length > 0 && cart[f11SelectedRow].qty > 1) {{ e.preventDefault(); cart[f11SelectedRow].qty--; updateCart(); renderF11Table(); syncF11Buttons(); }}
                    if ((e.key === 'q' || e.key === 'Q') && cart.length > 0) {{ e.preventDefault(); f11EditQty(f11SelectedRow); }}
                    if ((e.key === 'p' || e.key === 'P') && cart.length > 0) {{ e.preventDefault(); f11EditPrice(f11SelectedRow); }}
                    if ((e.key === 'd' || e.key === 'D') && cart.length > 0) {{ e.preventDefault(); f11EditDisc(f11SelectedRow); }}
                }}
            }});
        }});
    
        // Hook into updateCart to sync F11 view
        const _origUpdateCart = typeof updateCart === 'function' ? updateCart : null;
        // We'll override after pos_js loads — see observer below
    
        // Sync F11 when entity changes
        const _origToggleEntity = typeof toggleEntity === 'function' ? toggleEntity : null;
        </script>
        <script>
        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.register('/sw.js', {{scope: '/'}})
                .then(r => console.log('[SW] POS registered'))
                .catch(e => console.log('[SW] Non-critical:', e));
        }}
        </script>
        <div class="f11-dd" id="f11Dropdown" style="position:fixed;z-index:99999;"></div>
    </body>
    </html>'''
    
    @app.route("/pos/history")
    @login_required
    def pos_history():
        """POS History - View all transactions with X-Read and Z-Read"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Staff/cashier roles only see TODAY - no previous Z-reads or history
        user_role = get_user_role()
        is_staff_pos = user_role in ("staff", "cashier", "pos_only", "sales", "waiter")
        
        # Get filter params - support date range
        date_from = request.args.get("from", "")
        date_to = request.args.get("to", "")
        single_date = request.args.get("date", "")  # Backward compatible
        show_type = request.args.get("type", "all")
        search_q = request.args.get("q", "").strip().lower()
        
        # STAFF OVERRIDE: Force today only — no access to previous days
        if is_staff_pos:
            date_from = today()
            date_to = today()
            single_date = ""
        # Determine date range (managers/owners)
        elif single_date:
            # Single date mode (backward compatible, used for Z-Read cash-up)
            date_from = single_date
            date_to = single_date
        elif not date_from and not date_to:
            # Default: last 30 days
            from datetime import timedelta
            date_to = today()
            date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        elif date_from and not date_to:
            date_to = today()
        elif date_to and not date_from:
            date_from = "2020-01-01"
        
        is_single_day = (date_from == date_to)
        
        # Get all sales in date range
        all_sales = db.get("sales", {"business_id": biz_id}) if biz_id else []
        sales = [s for s in all_sales if date_from <= (s.get("date") or "") <= date_to]
        sales = sorted(sales, key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Get invoices in date range
        all_invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
        invoices = [i for i in all_invoices if date_from <= (i.get("date") or "") <= date_to]
        
        # Get quotes in date range
        all_quotes = db.get("quotes", {"business_id": biz_id}) if biz_id else []
        quotes = [q for q in all_quotes if date_from <= (q.get("date") or "") <= date_to]
        
        # Calculate totals — POS Sales
        cash_total = sum(float(s.get("total", 0)) for s in sales if s.get("payment_method") == "cash")
        card_total = sum(float(s.get("total", 0)) for s in sales if s.get("payment_method") == "card")
        account_total = sum(float(s.get("total", 0)) for s in sales if s.get("payment_method") == "account")
        invoice_total = sum(float(i.get("total", 0)) for i in invoices)
        quote_total = sum(float(q.get("total", 0)) for q in quotes)
        
        # Calculate totals — Invoices by payment method
        inv_cash_total = sum(float(i.get("total", 0)) for i in invoices if i.get("payment_method") == "cash")
        inv_card_total = sum(float(i.get("total", 0)) for i in invoices if i.get("payment_method") == "card")
        inv_eft_total = sum(float(i.get("total", 0)) for i in invoices if i.get("payment_method") == "eft")
        inv_account_total = sum(float(i.get("total", 0)) for i in invoices if i.get("payment_method") in ("account", ""))
        
        # COMBINED totals — what actually matters for the cash drawer
        all_cash = cash_total + inv_cash_total
        all_card = card_total + inv_card_total
        all_account = account_total + inv_account_total
        
        grand_total = cash_total + card_total + account_total
        transaction_count = len(sales)
        
        # === EXPECTED CASH FOR Z-READ ===
        # Cash in drawer = ALL cash received today (POS sales + cash-paid invoices)
        today_str = today()
        today_cash_sales = sum(float(s.get("total", 0)) for s in all_sales 
                              if s.get("payment_method") == "cash" and (s.get("date") or "") == today_str)
        today_cash_invoices = sum(float(i.get("total", 0)) for i in all_invoices 
                                 if i.get("payment_method") in ("cash",) and (i.get("date") or "") == today_str)
        expected_cash_drawer = today_cash_sales + today_cash_invoices
        
        # Build transaction rows
        rows = ""
        
        # Combine and sort by time
        transactions = []
        for s in sales:
            # Handle items that might be a list or JSON string
            s_items = s.get("items", [])
            if isinstance(s_items, str):
                try:
                    s_items = json.loads(s_items)
                except:
                    s_items = []
            
            # Build searchable text from items
            items_text = " ".join([str(it.get("description", "")) for it in s_items]) if s_items else ""
            
            # Default customer name based on payment method
            pm = s.get("payment_method", "cash").lower()
            default_name = {"cash": "Countersale Cash", "card": "Countersale Card", "account": "Countersale Account"}.get(pm, "Countersale")
            
            transactions.append({
                "id": s.get("id"),
                "number": s.get("sale_number", "-"),
                "date": s.get("date", ""),
                "time": extract_time(s.get("created_at", "")),
                "type": pm.upper(),
                "customer": s.get("customer_name") or default_name,
                "total": float(s.get("total", 0)),
                "items": len(s_items) if s_items else 0,
                "items_text": items_text,
                "source": "sale",
                "created_at": s.get("created_at", "")
            })
        
        for i in invoices:
            # Handle items that might be a list or JSON string
            i_items = i.get("items", [])
            if isinstance(i_items, str):
                try:
                    i_items = json.loads(i_items)
                except:
                    i_items = []
            
            items_text = " ".join([str(it.get("description", "")) for it in i_items]) if i_items else ""
            
            transactions.append({
                "id": i.get("id"),
                "number": i.get("invoice_number", "-"),
                "date": i.get("date", ""),
                "time": extract_time(i.get("created_at", "")),
                "type": "INVOICE",
                "customer": i.get("customer_name", "-"),
                "total": float(i.get("total", 0)),
                "items": len(i_items) if i_items else 0,
                "items_text": items_text,
                "source": "invoice",
                "created_at": i.get("created_at", "")
            })
        
        for q in quotes:
            # Handle items that might be a list or JSON string
            q_items = q.get("items", [])
            if isinstance(q_items, str):
                try:
                    q_items = json.loads(q_items)
                except:
                    q_items = []
            
            items_text = " ".join([str(it.get("description", "")) for it in q_items]) if q_items else ""
            
            transactions.append({
                "id": q.get("id"),
                "number": q.get("quote_number", "-"),
                "date": q.get("date", ""),
                "time": extract_time(q.get("created_at", "")),
                "type": "QUOTE",
                "customer": q.get("customer_name", "-"),
                "total": float(q.get("total", 0)),
                "items": len(q_items) if q_items else 0,
                "items_text": items_text,
                "source": "quote",
                "created_at": q.get("created_at", "")
            })
        
        # Sort by created_at descending
        transactions = sorted(transactions, key=lambda x: x.get("created_at", ""), reverse=True)
        
        # Filter by type
        if show_type != "all":
            transactions = [t for t in transactions if t.get("type", "").lower() == show_type.lower()]
        
        # Search filter - search by customer name, slip number, or item description
        if search_q:
            transactions = [t for t in transactions if 
                search_q in t.get("customer", "").lower() or
                search_q in t.get("number", "").lower() or
                search_q in t.get("items_text", "").lower() or
                search_q in str(t.get("total", ""))
            ]
        
        for t in transactions:
            type_color = {
                "CASH": "#10b981",
                "CARD": "#3b82f6",
                "ACCOUNT": "#f59e0b",
                "INVOICE": "#8b5cf6",
                "QUOTE": "#ec4899"
            }.get(t["type"], "#888")
            
            if t["source"] == "sale":
                view_url = f"/sale/{t['id']}"
            elif t["source"] == "invoice":
                view_url = f"/invoice/{t['id']}"
            else:
                view_url = f"/quote/{t['id']}"
            
            rows += f'''
            <tr onclick="window.location='{view_url}'" style="cursor:pointer;">
                <td><strong>{t["number"]}</strong></td>
                {"" if is_single_day else f'<td>{t["date"]}</td>'}
                <td>{t["time"]}</td>
                <td><span style="background:{type_color};color:white;padding:2px 8px;border-radius:4px;font-size:11px;">{t["type"]}</span></td>
                <td>{safe_string(t["customer"])}</td>
                <td style="text-align:center;">{t["items"]}</td>
                <td style="text-align:right;font-weight:bold;">{money(t["total"])}</td>
            </tr>
            '''
        
        # Date range description
        if is_single_day:
            date_desc = date_from
        else:
            date_desc = f"{date_from} to {date_to}"
        
        # Build date filter HTML (staff can't see date controls)
        if is_staff_pos:
            date_filter_html = ""
            zread_buttons_html = ""
        else:
            date_filter_html = f'''<input type="date" id="dateFrom" value="{date_from}" style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                <span style="color:var(--text-muted);">to</span>
                <input type="date" id="dateTo" value="{date_to}" style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">'''
            zread_buttons_html = '<button onclick="printXRead()" class="btn btn-secondary">X-Read</button><button onclick="printZRead()" class="btn btn-primary">Z-Read (Close Day)</button>'
        
        # Pre-build Z-read invoice section (avoids nested f-strings in JS template)
        _zr_inv_section = ""
        if inv_cash_total or inv_card_total or inv_eft_total:
            _zr_inv_rows = f'<tr><td>Cash Invoices:</td><td style="text-align:right;">{money(inv_cash_total)}</td></tr>'
            if inv_card_total:
                _zr_inv_rows += f'<tr><td>Card Invoices:</td><td style="text-align:right;">{money(inv_card_total)}</td></tr>'
            if inv_eft_total:
                _zr_inv_rows += f'<tr><td>EFT Invoices:</td><td style="text-align:right;">{money(inv_eft_total)}</td></tr>'
            _zr_inv_section = f'<hr style="border:1px dashed #000;margin:12px 0;"><div style="margin-bottom:8px;"><strong>INVOICES (Cash Paid)</strong></div><table style="width:100%;border-collapse:collapse;">{_zr_inv_rows}</table>'
        
        _zr_cash_inv_row = f'<tr><td style="font-size:12px;">+ Cash Invoices:</td><td style="text-align:right;font-size:12px;">{money(inv_cash_total)}</td></tr>' if inv_cash_total else ''
        
        content = f'''
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:15px;margin-bottom:20px;">
                <div>
                    <h2 style="margin:0;">POS History</h2>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;">{date_desc} &bull; {len(transactions)} transactions</p>
                </div>
                <a href="/pos" class="btn btn-primary">← Back to POS</a>
            </div>
            
            <!-- Search & Filters -->
            <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:15px;">
                <input type="text" id="searchBox" value="{search_q}" placeholder="🔍 Search customer, slip #, item..." 
                       style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);flex:1;min-width:200px;"
                       onkeydown="if(event.key==='Enter')applyFilters()">
                {date_filter_html}
                <select id="typeFilter" style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    <option value="all" {"selected" if show_type == "all" else ""}>All Types</option>
                    <option value="cash" {"selected" if show_type == "cash" else ""}>Cash</option>
                    <option value="card" {"selected" if show_type == "card" else ""}>Card</option>
                    <option value="account" {"selected" if show_type == "account" else ""}>Account</option>
                    <option value="invoice" {"selected" if show_type == "invoice" else ""}>Invoice</option>
                    <option value="quote" {"selected" if show_type == "quote" else ""}>Quote</option>
                </select>
                <button onclick="applyFilters()" class="btn btn-primary" style="padding:8px 16px;">Filter</button>
            </div>
            
            <!-- Quick Filters -->
            <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;">
                <button onclick="quickFilter('today')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">Today</button>
                <button onclick="quickFilter('yesterday')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">Yesterday</button>
                <button onclick="quickFilter('week')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">This Week</button>
                <button onclick="quickFilter('month')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">This Month</button>
                <button onclick="quickFilter('30days')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">Last 30 Days</button>
                <button onclick="quickFilter('90days')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">Last 90 Days</button>
                <button onclick="quickFilter('year')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">This Year</button>
                <button onclick="quickFilter('all')" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">All Time</button>
            </div>
            <!-- Summary Cards -->
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:15px;margin-bottom:25px;">
                <div style="background:linear-gradient(135deg,#10b981,#059669);padding:20px;border-radius:12px;text-align:center;">
                    <div style="font-size:24px;font-weight:bold;color:white;">{money(cash_total)}</div>
                    <div style="color:rgba(255,255,255,0.8);font-size:13px;">💵 Cash</div>
                </div>
                <div style="background:linear-gradient(135deg,#3b82f6,#2563eb);padding:20px;border-radius:12px;text-align:center;">
                    <div style="font-size:24px;font-weight:bold;color:white;">{money(card_total)}</div>
                    <div style="color:rgba(255,255,255,0.8);font-size:13px;">💳 Card</div>
                </div>
                <div style="background:linear-gradient(135deg,#f59e0b,#d97706);padding:20px;border-radius:12px;text-align:center;">
                    <div style="font-size:24px;font-weight:bold;color:white;">{money(account_total)}</div>
                    <div style="color:rgba(255,255,255,0.8);font-size:13px;">📒 Account</div>
                </div>
            </div>
            
            <!-- Grand Total -->
            <div style="background:var(--bg);padding:20px;border-radius:12px;margin-bottom:25px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:15px;">
                <div>
                    <span style="font-size:32px;font-weight:bold;">{money(grand_total)}</span>
                    <span style="color:var(--text-muted);margin-left:10px;">{transaction_count} transactions</span>
                </div>
                <div style="display:flex;gap:10px;">
                    {zread_buttons_html}
                </div>
            </div>
            
            <!-- Transactions Table -->
            <table class="table">
                <thead>
                    <tr>
                        <th>Slip #</th>
                        {"" if is_single_day else "<th>Date</th>"}
                        <th>Time</th>
                        <th>Type</th>
                        <th>Customer</th>
                        <th style="text-align:center;">Items</th>
                        <th style="text-align:right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {rows or f"<tr><td colspan='{'7' if not is_single_day else '6'}' style='text-align:center;color:var(--text-muted);padding:40px;'>No transactions found</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <!-- X-Read Modal -->
        <div id="xreadModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:white;padding:0;border-radius:8px;max-width:400px;width:90%;max-height:90vh;overflow-y:auto;">
                <div id="xreadContent" style="padding:30px;font-family:monospace;font-size:14px;color:#000;"></div>
                <div style="padding:15px;border-top:1px solid #eee;display:flex;gap:10px;">
                    <button onclick="window.print()" class="btn btn-primary" style="flex:1;">🖨️ Print</button>
                    <button onclick="closeModal('xreadModal')" class="btn btn-secondary" style="flex:1;">Close</button>
                </div>
            </div>
        </div>
        
        <!-- Z-Read Modal with Cash Denomination Count -->
        <div id="zreadModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:9999;justify-content:center;align-items:center;">
            <div style="background:white;padding:0;border-radius:8px;max-width:500px;width:95%;max-height:95vh;overflow-y:auto;">
                <div id="zreadContent" style="padding:30px;font-family:monospace;font-size:14px;color:#000;"></div>
                <!-- Cash Count Section -->
                <div id="cashCountSection" style="padding:0 30px 15px 30px;font-family:monospace;color:#000;">
                    <div style="border-top:2px dashed #000;margin:10px 0 15px 0;"></div>
                    <strong style="font-size:15px;">CASH COUNT</strong>
                    <p style="color:#666;font-size:11px;margin:4px 0 12px 0;">Enter quantity of each denomination:</p>
                    <table style="width:100%;border-collapse:collapse;" id="denomTable">
                        <tr style="background:#f5f5f5;font-weight:bold;">
                            <td style="padding:4px 8px;">Denomination</td>
                            <td style="padding:4px 8px;text-align:center;width:70px;">Qty</td>
                            <td style="padding:4px 8px;text-align:right;width:100px;">Total</td>
                        </tr>
                        <tr><td style="padding:4px 8px;">R200 Notes</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="200" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr style="background:#fafafa;"><td style="padding:4px 8px;">R100 Notes</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="100" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr><td style="padding:4px 8px;">R50 Notes</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="50" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr style="background:#fafafa;"><td style="padding:4px 8px;">R20 Notes</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="20" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr><td style="padding:4px 8px;">R10 Notes</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="10" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr style="background:#fafafa;"><td style="padding:4px 8px;">R5 Coins</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="5" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr><td style="padding:4px 8px;">R2 Coins</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="2" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr style="background:#fafafa;"><td style="padding:4px 8px;">R1 Coins</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="1" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr><td style="padding:4px 8px;">50c Coins</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="0.5" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr style="background:#fafafa;"><td style="padding:4px 8px;">20c Coins</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="0.2" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                        <tr><td style="padding:4px 8px;">10c Coins</td><td style="text-align:center;"><input type="number" class="denom-input" data-val="0.1" value="0" min="0" onchange="calcCashUp()" oninput="calcCashUp()" style="width:55px;text-align:center;padding:4px;border:1px solid #ccc;border-radius:4px;font-family:monospace;"></td><td style="text-align:right;padding:4px 8px;" class="denom-total">R0.00</td></tr>
                    </table>
                    <div style="border-top:2px dashed #000;margin:12px 0;"></div>
                    <table style="width:100%;border-collapse:collapse;">
                        <tr style="font-size:16px;font-weight:bold;">
                            <td style="padding:4px 8px;">COUNTED:</td>
                            <td style="text-align:right;padding:4px 8px;" id="cashCounted">R0.00</td>
                        </tr>
                        <tr style="font-size:14px;">
                            <td style="padding:4px 8px;">Expected Cash:</td>
                            <td style="text-align:right;padding:4px 8px;" id="cashExpected">{money(expected_cash_drawer)}</td>
                        </tr>
                        <tr id="diffRow" style="font-size:16px;font-weight:bold;">
                            <td style="padding:4px 8px;">DIFFERENCE:</td>
                            <td style="text-align:right;padding:4px 8px;" id="cashDiff">R0.00</td>
                        </tr>
                    </table>
                    <div id="cashStatus" style="text-align:center;padding:10px;margin-top:10px;border-radius:6px;font-weight:bold;font-size:13px;background:#fef3c7;color:#92400e;">
                        Tel die geld en vul die hoeveelhede in
                    </div>
                </div>
                <div style="padding:15px;border-top:1px solid #eee;display:flex;gap:10px;">
                    <button onclick="confirmZRead()" class="btn btn-primary" style="flex:1;background:#ef4444;">GOOD: Close Day & Print</button>
                    <button onclick="closeModal('zreadModal')" class="btn btn-secondary" style="flex:1;">Cancel</button>
                </div>
            </div>
        </div>
        
        <script>
        function applyFilters() {{
            const from = document.getElementById('dateFrom').value;
            const to = document.getElementById('dateTo').value;
            const type = document.getElementById('typeFilter').value;
            const q = document.getElementById('searchBox').value.trim();
            let url = '/pos/history?from=' + from + '&to=' + to + '&type=' + type;
            if (q) url += '&q=' + encodeURIComponent(q);
            window.location = url;
        }}
        
        function quickFilter(period) {{
            const today = new Date();
            let from, to;
            to = today.toISOString().split('T')[0];
            
            if (period === 'today') {{
                from = to;
            }} else if (period === 'yesterday') {{
                const y = new Date(today); y.setDate(y.getDate() - 1);
                from = to = y.toISOString().split('T')[0];
            }} else if (period === 'week') {{
                const d = new Date(today); d.setDate(d.getDate() - d.getDay() + 1); // Monday
                from = d.toISOString().split('T')[0];
            }} else if (period === 'month') {{
                from = today.getFullYear() + '-' + String(today.getMonth()+1).padStart(2,'0') + '-01';
            }} else if (period === '30days') {{
                const d = new Date(today); d.setDate(d.getDate() - 30);
                from = d.toISOString().split('T')[0];
            }} else if (period === '90days') {{
                const d = new Date(today); d.setDate(d.getDate() - 90);
                from = d.toISOString().split('T')[0];
            }} else if (period === 'year') {{
                from = today.getFullYear() + '-01-01';
            }} else if (period === 'all') {{
                from = '2020-01-01';
            }}
            
            const type = document.getElementById('typeFilter').value;
            const q = document.getElementById('searchBox').value.trim();
            let url = '/pos/history?from=' + from + '&to=' + to + '&type=' + type;
            if (q) url += '&q=' + encodeURIComponent(q);
            window.location = url;
        }}
        
        function closeModal(id) {{
            document.getElementById(id).style.display = 'none';
        }}
        
        function printXRead() {{
            const content = `
    <div style="text-align:center;margin-bottom:20px;">
    <strong style="font-size:18px;">X-READ</strong><br>
    <span style="color:#666;">Interim Report</span><br>
    <span>{date_desc}</span><br>
    <span style="font-size:11px;">Printed: ${{new Date().toLocaleTimeString()}}</span>
    </div>
    <hr style="border:1px dashed #000;margin:15px 0;">
    <div style="margin-bottom:15px;">
    <strong>SALES SUMMARY</strong>
    </div>
    <table style="width:100%;border-collapse:collapse;">
    <tr><td>Cash Sales:</td><td style="text-align:right;">{money(cash_total)}</td></tr>
    <tr><td>Card Sales:</td><td style="text-align:right;">{money(card_total)}</td></tr>
    <tr><td>Account Sales:</td><td style="text-align:right;">{money(account_total)}</td></tr>
    <tr><td>Invoices:</td><td style="text-align:right;">{money(invoice_total)}</td></tr>
    <tr><td>Quotes:</td><td style="text-align:right;">{money(quote_total)}</td></tr>
    </table>
    <hr style="border:1px dashed #000;margin:15px 0;">
    <table style="width:100%;border-collapse:collapse;">
    <tr style="font-size:18px;font-weight:bold;">
    <td>TOTAL:</td>
    <td style="text-align:right;">{money(grand_total)}</td>
    </tr>
    <tr><td>Transactions:</td><td style="text-align:right;">{transaction_count}</td></tr>
    </table>
    <hr style="border:1px dashed #000;margin:15px 0;">
    <div style="text-align:center;color:#666;font-size:11px;">
    *** X-READ - NOT A CLOSE ***
    </div>
            `;
            document.getElementById('xreadContent').innerHTML = content;
            document.getElementById('xreadModal').style.display = 'flex';
        }}
        
        const expectedCash = {float(expected_cash_drawer)};
        
        function calcCashUp() {{
            let counted = 0;
            document.querySelectorAll('.denom-input').forEach((input, idx) => {{
                const val = parseFloat(input.dataset.val);
                const qty = parseInt(input.value) || 0;
                const lineTotal = val * qty;
                counted += lineTotal;
                const totalCells = document.querySelectorAll('.denom-total');
                if (totalCells[idx]) totalCells[idx].textContent = 'R' + lineTotal.toFixed(2);
            }});
            
            document.getElementById('cashCounted').textContent = 'R' + counted.toFixed(2);
            const diff = counted - expectedCash;
            const diffEl = document.getElementById('cashDiff');
            const diffRow = document.getElementById('diffRow');
            const statusEl = document.getElementById('cashStatus');
            
            diffEl.textContent = (diff >= 0 ? 'R' : '-R') + Math.abs(diff).toFixed(2);
            
            if (Math.abs(diff) < 0.01) {{
                diffEl.style.color = '#059669';
                diffRow.style.color = '#059669';
                statusEl.style.background = '#d1fae5';
                statusEl.style.color = '#065f46';
                statusEl.textContent = 'Cash balanseer perfek!';
            }} else if (diff > 0) {{
                diffEl.style.color = '#2563eb';
                diffRow.style.color = '#2563eb';
                statusEl.style.background = '#dbeafe';
                statusEl.style.color = '#1e40af';
                statusEl.textContent = 'R' + diff.toFixed(2) + ' OOR (surplus)';
            }} else {{
                diffEl.style.color = '#dc2626';
                diffRow.style.color = '#dc2626';
                statusEl.style.background = '#fee2e2';
                statusEl.style.color = '#991b1b';
                statusEl.textContent = 'R' + Math.abs(diff).toFixed(2) + ' KORT (tekort)';
            }}
        }}
        
        function printZRead() {{
            // ═══ CHECK: Has day already been closed with a Z-read? ═══
            fetch('/api/cashup/history?date=' + '{date_from}')
                .then(r => r.json())
                .then(data => {{
                    if (data.success && data.cash_ups) {{
                        const existing = (data.cash_ups || []).filter(c => c.type === 'z_reading');
                        if (existing.length > 0) {{
                            alert('Dag is reeds afgesluit met n Z-Read. Jy kan nie weer n Z-Read doen nie.');
                            return;
                        }}
                    }}
                    _showZReadModal();
                }})
                .catch(e => {{
                    console.log('Z-read check failed, proceeding:', e);
                    _showZReadModal();
                }});
        }}
        
        function _showZReadModal() {{
            // Reset denomination inputs
            document.querySelectorAll('.denom-input').forEach(input => {{ input.value = 0; }});
            document.querySelectorAll('.denom-total').forEach(cell => {{ cell.textContent = 'R0.00'; }});
            document.getElementById('cashCounted').textContent = 'R0.00';
            document.getElementById('cashDiff').textContent = 'R0.00';
            document.getElementById('cashDiff').style.color = '#000';
            document.getElementById('diffRow').style.color = '#000';
            document.getElementById('cashStatus').textContent = 'Tel die geld en vul die hoeveelhede in';
            document.getElementById('cashStatus').style.background = '#fef3c7';
            document.getElementById('cashStatus').style.color = '#92400e';
            
            const content = `
    <div style="text-align:center;margin-bottom:20px;">
    <strong style="font-size:18px;">Z-READ</strong><br>
    <span style="color:#666;">End of Day Report</span><br>
    <span>{date_desc}</span><br>
    <span style="font-size:11px;">Printed: ${{new Date().toLocaleTimeString()}}</span>
    </div>
    <hr style="border:1px dashed #000;margin:15px 0;">
    <div style="margin-bottom:8px;">
    <strong>POS SALES</strong>
    </div>
    <table style="width:100%;border-collapse:collapse;">
    <tr><td>Cash (POS):</td><td style="text-align:right;">{money(cash_total)}</td></tr>
    <tr><td>Card (POS):</td><td style="text-align:right;">{money(card_total)}</td></tr>
    <tr><td>Account (POS):</td><td style="text-align:right;">{money(account_total)}</td></tr>
    <tr style="font-weight:bold;border-top:1px solid #000;"><td>POS Total:</td><td style="text-align:right;">{money(grand_total)}</td></tr>
    <tr><td style="font-size:11px;">Transactions:</td><td style="text-align:right;font-size:11px;">{transaction_count}</td></tr>
    </table>
    {_zr_inv_section}
    <hr style="border:2px solid #000;margin:15px 0;">
    <div style="margin-bottom:8px;">
    <strong>CASH IN DRAWER (Expected)</strong>
    </div>
    <table style="width:100%;border-collapse:collapse;">
    <tr><td style="font-size:12px;">POS Cash Sales:</td><td style="text-align:right;font-size:12px;">{money(cash_total)}</td></tr>
    {_zr_cash_inv_row}
    <tr style="font-size:18px;font-weight:bold;border-top:1px solid #000;">
    <td>EXPECTED CASH:</td>
    <td style="text-align:right;">{money(expected_cash_drawer)}</td>
    </tr>
    </table>
            `;
            document.getElementById('zreadContent').innerHTML = content;
            document.getElementById('zreadModal').style.display = 'flex';
        }}
        
        function buildCashCountPrintHtml() {{
            let html = '<hr style="border:1px dashed #000;margin:15px 0;"><strong>CASH DENOMINATION COUNT</strong><br><br>';
            html += '<table style="width:100%;border-collapse:collapse;font-size:12px;">';
            html += '<tr style="font-weight:bold;"><td>Denom</td><td style="text-align:center;">Qty</td><td style="text-align:right;">Total</td></tr>';
            const denomLabels = ['R200','R100','R50','R20','R10','R5','R2','R1','50c','20c','10c'];
            document.querySelectorAll('.denom-input').forEach((input, idx) => {{
                const qty = parseInt(input.value) || 0;
                if (qty > 0) {{
                    const val = parseFloat(input.dataset.val);
                    const lineTotal = val * qty;
                    html += '<tr><td>' + denomLabels[idx] + '</td><td style="text-align:center;">' + qty + '</td><td style="text-align:right;">R' + lineTotal.toFixed(2) + '</td></tr>';
                }}
            }});
            html += '</table>';
            
            const counted = document.getElementById('cashCounted').textContent;
            const diff = document.getElementById('cashDiff').textContent;
            const status = document.getElementById('cashStatus').textContent;
            
            html += '<hr style="border:1px dashed #000;margin:10px 0;">';
            html += '<table style="width:100%;border-collapse:collapse;">';
            html += '<tr style="font-weight:bold;"><td>Counted:</td><td style="text-align:right;">' + counted + '</td></tr>';
            html += '<tr><td>Expected:</td><td style="text-align:right;">{money(expected_cash_drawer)}</td></tr>';
            html += '<tr style="font-weight:bold;font-size:16px;"><td>Difference:</td><td style="text-align:right;">' + diff + '</td></tr>';
            html += '</table>';
            html += '<div style="text-align:center;margin:10px 0;font-weight:bold;">' + status + '</div>';
            
            return html;
        }}
        
        async function confirmZRead() {{
            const counted = document.getElementById('cashCounted').textContent;
            const diff = document.getElementById('cashDiff').textContent;
            const status = document.getElementById('cashStatus').textContent;
            
            if (!confirm('Close day for {date_desc}?\\n\\n' + status + '\\nCounted: ' + counted + '\\nDifference: ' + diff + '\\n\\nThis will mark the day as CLOSED.')) return;
            
            // ═══ SAVE Z-READ TO DATABASE — marks day as closed ═══
            try {{
                const resp = await fetch('/api/cashup/save', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        type: 'z_reading',
                        system_cash: {cash_total},
                        system_card: {card_total},
                        system_account: {account_total},
                        system_total: {grand_total},
                        sale_count: {transaction_count},
                        cash_counted: counted,
                        cash_difference: diff,
                        cash_status: status
                    }})
                }});
                const data = await resp.json();
                if (!data.success) {{
                    alert('Z-Read save failed: ' + (data.error || 'Unknown'));
                }}
            }} catch(e) {{
                console.error('Z-Read save error:', e);
            }}
            
            // Build print content with cash count
            const zContent = document.getElementById('zreadContent').innerHTML;
            const cashHtml = buildCashCountPrintHtml();
            
            const printWindow = window.open('', '_blank', 'width=400,height=700');
            printWindow.document.write('<html><head><title>Z-Read</title><style>body {{ font-family: monospace; font-size: 14px; padding: 20px; color: #000; max-width: 80mm; margin: 0 auto; }} table {{ width: 100%; border-collapse: collapse; }} td {{ padding: 3px 0; }} @media print {{ @page {{ size: 80mm auto; margin: 5mm; }} }}</style></head><body>' + zContent + cashHtml + '<hr style="border:1px dashed #000;margin:15px 0;"><div style="text-align:center;margin-top:30px;"><div style="border-top:1px solid #000;width:200px;margin:0 auto;padding-top:5px;">Cashier Signature</div></div><div style="text-align:center;color:#666;font-size:11px;margin-top:20px;">*** Z-READ - DAY CLOSED ***</div></body></html>');
            printWindow.document.close();
            setTimeout(function() {{ printWindow.print(); }}, 300);
            closeModal('zreadModal');
        }}
        
        // Close modal on background click
        document.getElementById('xreadModal').addEventListener('click', function(e) {{
            if (e.target === this) closeModal('xreadModal');
        }});
        document.getElementById('zreadModal').addEventListener('click', function(e) {{
            if (e.target === this) closeModal('zreadModal');
        }});
        </script>
        
        <style>
        @media print {{
            body * {{ visibility: hidden; }}
            #xreadContent, #xreadContent *, #zreadContent, #zreadContent * {{ visibility: visible; }}
            #xreadContent, #zreadContent {{ position: absolute; left: 0; top: 0; width: 80mm; }}
        }}
        </style>
        '''
        
        return render_page("POS History", content, user, "pos")
    
    
    @app.route("/sale/<sale_id>")
    @login_required
    def view_sale(sale_id):
        """View individual sale/slip - matches POS slip format exactly"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_name = business.get("name", "Business") if business else "Business"
        biz_phone = business.get("phone", "") if business else ""
        biz_vat = business.get("vat_number", "") if business else ""
        slip_footer = business.get("pos_slip_footer", "Thank you for your purchase!") if business else "Thank you for your purchase!"
        
        sale = db.get_one("sales", sale_id)
        if not sale:
            flash("Sale not found", "error")
            return redirect("/pos/history")
        
        # Handle items that might be a list or JSON string
        items = sale.get("items", [])
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except:
                items = []
        elif not isinstance(items, list):
            items = []
        
        # Build items HTML exactly like POS slip: qty x description | total
        items_html = ""
        for item in items:
            qty = item.get("quantity") or item.get("qty", 1)
            price = float(item.get("price", 0))
            total = qty * price
            item_name = safe_string(item.get("description") or item.get("code") or "Item")
            items_html += f'<tr><td style="padding:3px 0;font-size:13px;">{qty}x {item_name}</td><td style="text-align:right;padding:3px 0;font-size:13px;white-space:nowrap;">R{total:.2f}</td></tr>'
        
        payment_method = sale.get("payment_method", "cash").lower()
        method_label = {"cash": "💵 CASH", "card": "💳 CARD", "account": "📒 ACCOUNT"}.get(payment_method, payment_method.upper())
        customer_name = safe_string(sale.get("customer_name") or {"cash": "Countersale", "card": "Countersale", "account": "Countersale"}.get(payment_method, "Countersale"))
        
        # Extract sale date/time
        sale_date = sale.get("date", "-")
        sale_time = extract_time(sale.get("created_at", ""))
        sale_number = sale.get("sale_number", "-")
        
        # Cash payment details
        cash_html = ""
        cash_received = float(sale.get("cash_received", 0) or 0)
        change_given = float(sale.get("change_given", 0) or 0)
        if payment_method == "cash" and cash_received > 0:
            cash_html = f'''
                <div style="margin-top:8px;padding:8px;background:#f5f5f5;border-radius:6px;">
                    <div style="display:flex;justify-content:space-between;font-size:14px;padding:2px 0;">
                        <span>Cash Received</span><span>R{cash_received:.2f}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:18px;font-weight:bold;padding:2px 0;color:#10b981;">
                        <span>Change</span><span>R{change_given:.2f}</span>
                    </div>
                </div>
            '''
        
        # Build slip HTML matching POS format exactly
        content = f'''
        <div style="max-width:500px;margin:0 auto;">
            <a href="/pos/history" style="color:var(--text-muted);display:block;margin-bottom:15px;">← Back to History</a>
            
            <div id="reprintContent" class="card" style="background:white;color:#000;padding:12px;font-family:'Courier New',monospace;font-size:13px;">
                <div style="text-align:center;border-bottom:2px dashed #000;padding-bottom:8px;margin-bottom:8px;">
                    <div style="font-size:18px;font-weight:bold;">{biz_name}</div>
                    {f'<div style="font-size:12px;color:#666;">Tel: {biz_phone}</div>' if biz_phone else ''}
                    {f'<div style="font-size:12px;color:#666;">VAT: {biz_vat}</div>' if biz_vat else ''}
                    <div style="margin-top:6px;font-size:15px;font-weight:bold;">{sale_number}</div>
                    <div style="font-size:12px;color:#666;">{sale_date} {sale_time}</div>
                    {f'<div style="font-size:12px;color:#666;margin-top:2px;">Cashier: {safe_string(sale.get("cashier_name", ""))}</div>' if sale.get("cashier_name") else ''}
                </div>
                
                <div style="margin-bottom:8px;font-size:13px;">
                    <span style="background:#333;color:white;padding:3px 8px;border-radius:3px;font-size:12px;">{method_label}</span>
                    <span style="margin-left:8px;font-size:13px;">{customer_name}</span>
                </div>
                
                <table style="width:100%;border-collapse:collapse;margin-bottom:8px;">
                    {items_html}
                </table>
                
                <div style="border-top:2px dashed #000;padding-top:6px;">
                    <div style="display:flex;justify-content:space-between;font-size:13px;color:#666;padding:2px 0;">
                        <span>Subtotal</span><span>R{float(sale.get("subtotal", 0)):.2f}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:13px;color:#666;padding:2px 0;">
                        <span>VAT (15%)</span><span>R{float(sale.get("vat", 0)):.2f}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;font-size:22px;font-weight:bold;margin-top:6px;">
                        <span>TOTAL</span><span>R{float(sale.get("total", 0)):.2f}</span>
                    </div>
                </div>
                
                {cash_html}
                
                <div style="text-align:center;margin-top:8px;padding-top:8px;border-top:2px dashed #000;font-size:12px;color:#666;">
                    {slip_footer}
                </div>
            </div>
            
            <div style="margin-top:20px;display:flex;gap:10px;">
                <button onclick="reprintSlip('thermal')" class="btn btn-primary" style="flex:1;">🖨️ Thermal Slip</button>
                <button onclick="reprintSlip('a4')" class="btn btn-secondary" style="flex:1;">🖨️ A4 Print</button>
            </div>
        </div>
        
        <script>
        function reprintSlip(format) {{
            const slipContent = document.getElementById('reprintContent').innerHTML;
            
            const styles = format === 'thermal' ?
                'body {{ width: 72mm; margin: 0; padding: 4mm; font-family: Courier New, monospace; font-size: 16px; font-weight: bold; color: #000; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }} * {{ font-weight: bold !important; color: #000 !important; background: transparent !important; }} table {{ width: 100%; border-collapse: collapse; }} td {{ font-weight: bold !important; padding: 2px 0; }} @page {{ size: 80mm auto; margin: 0; }} @media print {{ body {{ width: 72mm; }} }}' :
                'body {{ width: 210mm; margin: 20mm; font-family: Arial, sans-serif; font-size: 18px; color: #000; background: #fff; }} @page {{ size: A4; margin: 20mm; }}';
            
            var fullHtml = '<!DOCTYPE html><html><head><title>POS Slip</title><style>' + styles + '</style></head><body>' + slipContent + '</body></html>';
            
            var printWin = window.open('', 'pos_slip_print', 'width=400,height=600,menubar=no,toolbar=no,location=no,status=no');
            if (printWin) {{
                printWin.document.open();
                printWin.document.write(fullHtml);
                printWin.document.close();
                var tryPrint = function() {{
                    try {{ printWin.focus(); printWin.print(); }} catch(e) {{ console.log('[POS] Print error:', e); }}
                    setTimeout(function() {{ try {{ printWin.close(); }} catch(e) {{}} }}, 2000);
                }};
                if (printWin.document.readyState === 'complete') {{ setTimeout(tryPrint, 400); }}
                else {{ printWin.onload = function() {{ setTimeout(tryPrint, 200); }}; setTimeout(tryPrint, 1500); }}
            }}
        }}
        </script>
        '''
        
        return render_page(f"Sale {sale.get('sale_number', '')}", content, user, "pos")
    
    
    @app.route("/api/pos/email-slip", methods=["POST"])
    @login_required
    def api_pos_email_slip():
        """Email POS slip to customer"""
        try:
            data = request.get_json()
            to_email = data.get("to_email", "").strip()
            
            if not to_email or "@" not in to_email:
                return jsonify({"success": False, "error": "Valid email address required"})
            
            business = Auth.get_current_business()
            biz_name = business.get("name", "Business") if business else "Business"
            biz_phone = business.get("phone", "") if business else ""
            biz_vat = business.get("vat_number", "") if business else ""
            
            sale_number = data.get("sale_number", "")
            customer_name = data.get("customer_name", "Customer")
            items = data.get("items", [])
            subtotal = float(data.get("subtotal", 0))
            vat = float(data.get("vat", 0))
            total = float(data.get("total", 0))
            payment_method = data.get("payment_method", "cash")
            
            # Build items HTML
            items_html = ""
            for item in items:
                desc = item.get("description") or item.get("code", "Item")
                qty = item.get("quantity", 1)
                price = float(item.get("price", 0))
                line_total = float(item.get("total", price * qty))
                items_html += f'<tr><td style="padding:8px;border-bottom:1px solid #eee;">{qty}x {desc}</td><td style="padding:8px;border-bottom:1px solid #eee;text-align:right;">R{line_total:,.2f}</td></tr>'
            
            method_label = {"cash": "💵 Cash", "card": "💳 Card", "account": "📒 Account"}.get(payment_method, payment_method.upper())
            
            subject = f"Receipt {sale_number} from {biz_name}"
            
            body_html = f'''
            <html>
            <body style="font-family: 'Courier New', monospace; padding: 20px; background: #f5f5f5;">
                <div style="max-width: 400px; margin: 0 auto; background: white; padding: 25px; border-radius: 8px; border: 1px solid #ddd;">
                    <div style="text-align: center; border-bottom: 2px dashed #333; padding-bottom: 15px; margin-bottom: 15px;">
                        <div style="font-size: 24px; font-weight: bold;">{biz_name}</div>
                        {f'<div style="color: #666;">Tel: {biz_phone}</div>' if biz_phone else ''}
                        {f'<div style="color: #666;">VAT: {biz_vat}</div>' if biz_vat else ''}
                        <div style="margin-top: 10px; font-size: 18px; font-weight: bold;">{sale_number}</div>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <span style="background: #333; color: white; padding: 4px 8px; border-radius: 3px; font-size: 12px;">{method_label}</span>
                        <span style="margin-left: 10px;">{customer_name}</span>
                    </div>
                    
                    <table style="width: 100%; border-collapse: collapse; margin-bottom: 15px;">
                        {items_html}
                    </table>
                    
                    <div style="border-top: 2px dashed #333; padding-top: 10px;">
                        <div style="display: flex; justify-content: space-between; color: #666; padding: 4px 0;">
                            <span>Subtotal</span><span>R{subtotal:,.2f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; color: #666; padding: 4px 0;">
                            <span>VAT (15%)</span><span>R{vat:,.2f}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 20px; font-weight: bold; margin-top: 10px;">
                            <span>TOTAL</span><span>R{total:,.2f}</span>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin-top: 15px; padding-top: 15px; border-top: 2px dashed #333; color: #666;">
                        Thank you for your purchase!
                    </div>
                </div>
            </body>
            </html>
            '''
            
            body_text = f"Receipt {sale_number} from {biz_name}\n\nCustomer: {customer_name}\nPayment: {method_label}\n\nSubtotal: R{subtotal:,.2f}\nVAT: R{vat:,.2f}\nTOTAL: R{total:,.2f}\n\nThank you for your purchase!"
            
            success = Email.send(to_email, subject, body_html, body_text, business=business)
            
            if success:
                logger.info(f"[POS] Slip {sale_number} emailed to {to_email}")
                return jsonify({"success": True, "message": f"Slip emailed to {to_email}"})
            else:
                return jsonify({"success": False, "error": "Failed to send email. Check SMTP settings."})
            
        except Exception as e:
            logger.error(f"[POS] Email slip error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/sale", methods=["POST"])
    @login_required
    def api_pos_sale():
        """
        POS Sale API - with full GL integration
        
        GL Flow for POS Sales:
        
        CASH/CARD SALE:
        - Debit: Cash (1100) or Bank (1000) - money in
        - Credit: Sales (4000) - revenue
        - Credit: VAT Output (2100) - VAT collected
        
        ACCOUNT SALE:
        - Debit: Debtors (1200) - customer owes us
        - Credit: Sales (4000) - revenue
        - Credit: VAT Output (2100) - VAT collected
        
        Plus Cost of Sales (if stock has cost):
        - Debit: Cost of Sales (5000)
        - Credit: Stock (1300)
        """
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            data = request.get_json()
            items = data.get("items", [])
            customer_id = data.get("customer_id", "")
            payment_method = data.get("payment_method", "cash")
            # Build sale label: "Countersale Cash - Piet" or "Countersale Card - Isaac"
            method_label = {"cash": "Cash", "card": "Card", "account": "Account"}.get(payment_method, "Sale")
            cashier_display = data.get("cashier_name", "")
            default_name = f"Countersale {method_label} - {cashier_display}" if cashier_display else f"Countersale {method_label}"
            customer_name = data.get("customer_name") or default_name
            cashier_id = data.get("cashier_id") or (user.get("id") if user else None)
            logger.info(f"[POS] Sale by cashier_id={cashier_id}, cashier_name={cashier_display}, logged_in_user={user.get('id') if user else 'none'}")
            
            if not items:
                return jsonify({"success": False, "error": "No items in cart"})
            
            # Use frontend-calculated values (prices are EXCL VAT, VAT is ADDED)
            subtotal = Decimal(str(data.get("subtotal", 0)))
            vat = Decimal(str(data.get("vat", 0)))
            total = Decimal(str(data.get("total", 0)))
            
            # Fallback calculation if frontend didn't send values
            if subtotal == 0:
                subtotal = sum(Decimal(str(item.get("total", 0))) for item in items)
                vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
                total = subtotal + vat
            
            # Create sale record
            sale_id = generate_id()
            sale_num = f"POS{int(time.time()) % 100000:05d}"
            sale = {
                "id": sale_id,
                "business_id": biz_id,
                "sale_number": sale_num,
                "date": today(),
                "customer_id": safe_uuid(customer_id),
                "customer_name": customer_name,
                "payment_method": payment_method,
                "items": json.dumps(items),
                "subtotal": float(subtotal),
                "vat": float(vat),
                "total": float(total),
                "created_by": cashier_id,
                "created_at": now()
            }
            
            success, err = db.save("sales", sale)
            
            # If created_by column doesn't exist, retry without it
            if not success and "created_by" in str(err):
                logger.warning(f"[POS] created_by column missing, retrying without it")
                sale.pop("created_by", None)
                sale["notes"] = f"Cashier: {data.get('cashier_name', '')}"
                success, err = db.save("sales", sale)
            
            if not success:
                logger.error(f"[POS] Sale save failed: {err}")
                return jsonify({"success": False, "error": f"Failed to save sale: {str(err)[:200]}"})
            
            # === GL ENTRIES ===
            
            # Determine debit account based on payment method
            if payment_method == "cash":
                debit_account = "1050"  # Cash On Hand (POS counter cash)
                debit_name = "Cash"
            elif payment_method == "card":
                debit_account = "1000"  # Bank (card payments go to bank)
                debit_name = "Card"
            else:  # account
                debit_account = "1200"  # Debtors
                debit_name = "Account"
            
            # Create journal entry for the sale
            create_journal_entry(
                biz_id,
                today(),
                f"POS Sale {sale_num} - {customer_name} ({debit_name})",
                sale_num,
                [
                    {"account_code": debit_account, "debit": float(total), "credit": 0},  # Cash/Bank/Debtors
                    {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": float(subtotal)},       # Sales
                    {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": float(vat)},            # VAT Output
                ]
            )
            
            # Update stock quantities and create Cost of Sales entries
            total_cost = Decimal("0")
            logger.info(f"[POS DEBUG] Processing {len(items)} items for stock update")
            for item in items:
                logger.info(f"[POS DEBUG] Item received: {item}")
                stock_id = item.get("stock_id")
                qty_sold = int(item.get("quantity", 0))
                
                logger.info(f"[POS DEBUG] stock_id={stock_id}, qty_sold={qty_sold}")
                
                if stock_id:
                    stock_item = db.get_one_stock(stock_id)
                    logger.info(f"[POS DEBUG] Found stock_item: {stock_item.get('code') if stock_item else 'NOT FOUND'}")
                    if stock_item:
                        # Update stock quantity
                        current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                        new_qty = current_qty - qty_sold  # Allow negative
                        logger.info(f"[POS DEBUG] Updating stock {stock_id}: {current_qty} - {qty_sold} = {new_qty}")
                        
                        if qty_sold > 0:
                            success = db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
                            logger.info(f"[POS DEBUG] Stock update result: {success}")
                            if not success:
                                logger.error(f"[POS] Failed to update stock {stock_id} - qty was {current_qty}, tried to set {new_qty}")
                            else:
                                # Log stock movement
                                try:
                                    db.save("stock_movements", RecordFactory.stock_movement(
                                        business_id=biz_id, stock_id=stock_id, movement_type="out",
                                        quantity=qty_sold, reference=f"POS Sale {sale_num}"
                                    ))
                                except Exception as sm_err: logger.error(f"[STOCK MOVEMENT] Save failed: {sm_err}")
                        else:
                            logger.warning(f"[POS DEBUG] Skipping stock update - qty_sold is 0")
                        
                        # Calculate cost of sales
                        cost_price = Decimal(str(stock_item.get("cost") or stock_item.get("cost_price") or 0))
                        line_cost = cost_price * qty_sold
                        total_cost += line_cost
            
            # Create Cost of Sales journal entry (if there's cost)
            if total_cost > 0:
                create_journal_entry(
                    biz_id,
                    today(),
                    f"COS - POS Sale {sale_num}",
                    f"COS-{sale_num}",
                    [
                        {"account_code": gl(biz_id, "cogs"), "debit": float(total_cost), "credit": 0},   # Cost of Sales
                        {"account_code": gl(biz_id, "stock"), "debit": 0, "credit": float(total_cost)},   # Stock
                    ]
                )
            
            # Update customer balance if account sale
            if customer_id and payment_method == "account":
                customer = db.get_one("customers", customer_id)
                if customer:
                    new_balance = float(customer.get("balance", 0)) + float(total)
                    db.update("customers", customer_id, {"balance": new_balance})
            
            logger.info(f"[POS] Sale {sale_num}: R{total:.2f} ({payment_method}) - GL entries created")
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    _stock_moves = []
                    for item in items:
                        if item.get("stock_id"):
                            _stock_moves.append({"stock_id": item.get("stock_id"), "code": item.get("code", ""), "description": item.get("description", ""), "qty_change": -int(item.get("quantity", 0))})
                    log_allocation(
                        business_id=biz_id, allocation_type="pos_sale", source_table="sales", source_id=sale_id,
                        description=f"POS Sale {sale_num} - {customer_name} ({debit_name})",
                        amount=float(total),
                        gl_entries=[
                            {"account_code": debit_account, "debit": float(total), "credit": 0},
                            {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": float(subtotal)},
                            {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": float(vat)},
                        ],
                        stock_movements=_stock_moves,
                        customer_name=customer_name, payment_method=payment_method, reference=sale_num,
                        transaction_date=today(),
                        created_by=cashier_id or "", created_by_name=cashier_display or ""
                    )
            except Exception:
                pass
            
            return jsonify({
                "success": True,
                "message": f"R{total:.2f} - {len(items)} items",
                "sale_id": sale_id,
                "sale_number": sale_num
            })
            
        except Exception as e:
            logger.error(f"[POS] Sale error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/sync-offline", methods=["POST"])
    @login_required
    def api_pos_sync_offline():
        """Process queued offline POS sales — called when internet returns"""
        try:
            data = request.get_json() or {}
            sales_queue = data.get("sales", [])
            
            if not sales_queue:
                return jsonify({"success": True, "synced": 0, "message": "Nothing to sync"})
            
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            synced = 0
            errors = []
            
            for queued_sale in sales_queue:
                try:
                    items = queued_sale.get("items", [])
                    customer_id = queued_sale.get("customer_id", "")
                    payment_method = queued_sale.get("payment_method", "cash")
                    method_label = {"cash": "Cash", "card": "Card", "account": "Account"}.get(payment_method, "Sale")
                    cashier_display = queued_sale.get("cashier_name", "")
                    default_name = f"Countersale {method_label} - {cashier_display}" if cashier_display else f"Countersale {method_label}"
                    customer_name = queued_sale.get("customer_name") or default_name
                    cashier_id = queued_sale.get("cashier_id") or (user.get("id") if user else None)
                    
                    subtotal = Decimal(str(queued_sale.get("subtotal", 0)))
                    vat = Decimal(str(queued_sale.get("vat", 0)))
                    total = Decimal(str(queued_sale.get("total", 0)))
                    
                    # Use original date/time from when sale was made offline
                    sale_date = queued_sale.get("offline_date") or today()
                    sale_time = queued_sale.get("offline_time") or now()
                    
                    sale_id = generate_id()
                    sale_num = f"POS{int(time.time()) % 100000:05d}"
                    
                    sale = {
                        "id": sale_id,
                        "business_id": biz_id,
                        "sale_number": sale_num,
                        "date": sale_date,
                        "customer_id": safe_uuid(customer_id),
                        "customer_name": customer_name,
                        "payment_method": payment_method,
                        "items": json.dumps(items),
                        "subtotal": float(subtotal),
                        "vat": float(vat),
                        "total": float(total),
                        "created_by": cashier_id,
                        "created_at": sale_time,
                        "notes": f"OFFLINE SALE — synced {now()}"
                    }
                    
                    success, err = db.save("sales", sale)
                    if not success and "created_by" in str(err):
                        sale.pop("created_by", None)
                        sale["notes"] = f"OFFLINE SALE — Cashier: {queued_sale.get('cashier_name', '')} — synced {now()}"
                        success, err = db.save("sales", sale)
                    
                    if not success:
                        errors.append(f"Sale R{total}: {str(err)[:100]}")
                        continue
                    
                    # GL entries
                    if payment_method == "cash":
                        debit_account, debit_name = "1050", "Cash"
                    elif payment_method == "card":
                        debit_account, debit_name = "1000", "Card"
                    else:
                        debit_account, debit_name = "1200", "Account"
                    
                    create_journal_entry(
                        biz_id, sale_date,
                        f"OFFLINE POS Sale {sale_num} - {customer_name} ({debit_name})",
                        sale_num,
                        [
                            {"account_code": debit_account, "debit": float(total), "credit": 0},
                            {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": float(subtotal)},
                            {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": float(vat)},
                        ]
                    )
                    
                    # Update stock
                    for item in items:
                        stock_id = item.get("stock_id")
                        qty_sold = int(item.get("quantity", 0))
                        if stock_id and qty_sold > 0:
                            stock_item = db.get_one_stock(stock_id)
                            if stock_item:
                                current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                                new_qty = current_qty - qty_sold
                                db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
                    
                    # Update customer balance for account sales
                    if payment_method == "account" and customer_id:
                        try:
                            cust = db.get_by_id("customers", customer_id)
                            if cust:
                                old_bal = float(cust.get("balance") or 0)
                                db.update("customers", customer_id, {"balance": old_bal + float(total)})
                        except Exception:
                            pass
                    
                    synced += 1
                    logger.info(f"[POS OFFLINE SYNC] Sale {sale_num}: R{total:.2f} ({payment_method}) — originally {sale_date} {sale_time}")
                    
                except Exception as e:
                    errors.append(f"Sale error: {str(e)[:100]}")
            
            msg = f"Synced {synced}/{len(sales_queue)} offline sales"
            if errors:
                msg += f" ({len(errors)} errors)"
            
            logger.info(f"[POS OFFLINE SYNC] {msg}")
            return jsonify({"success": True, "synced": synced, "errors": errors, "message": msg})
            
        except Exception as e:
            logger.error(f"[POS OFFLINE SYNC] Failed: {e}")
            return jsonify({"success": False, "error": str(e)[:200]})
    
    
    @app.route("/api/pos/quote", methods=["POST"])
    @login_required
    def api_pos_quote():
        """Create quote from POS cart"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            data = request.get_json()
            items = data.get("items", [])
            customer_id = data.get("customer_id", "")
            customer_name = data.get("customer_name", "")
            cashier_id = data.get("cashier_id") or (user.get("id") if user else None)
            cashier_display = data.get("cashier_name") or (user.get("name", "") if user else "")
            
            # DEBUG LOG
            logger.info(f"[POS QUOTE] Received customer_id: '{customer_id}' name: '{customer_name}'")
            
            if not items:
                return jsonify({"success": False, "error": "No items in cart"})
            
            if not customer_name:
                return jsonify({"success": False, "error": "Customer required for quote"})
            
            # Use safe_uuid to handle invalid UUIDs (returns None if invalid)
            safe_customer_id = safe_uuid(customer_id)
            
            logger.info(f"[POS QUOTE] UUID valid: {safe_customer_id is not None}, using: {safe_customer_id}")
            
            # Use frontend-calculated values (prices are EXCL VAT, VAT is ADDED)
            subtotal = Decimal(str(data.get("subtotal", 0)))
            vat = Decimal(str(data.get("vat", 0)))
            total = Decimal(str(data.get("total", 0)))
            
            # Fallback calculation if frontend didn't send values
            if subtotal == 0:
                subtotal = sum(Decimal(str(item.get("total", 0))) for item in items)
                vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
                total = subtotal + vat
            
            # Generate quote number
            existing = db.get("quotes", {"business_id": biz_id}) if biz_id else []
            quote_num = next_document_number("Q-", existing, "quote_number")
            
            # Create quote using RecordFactory
            user = Auth.get_current_user()
            pos_salesman_id = data.get("salesman_id") or cashier_id
            pos_salesman_name = data.get("salesman_name") or cashier_display
            quote = RecordFactory.quote(
                business_id=biz_id,
                customer_id=safe_customer_id,
                customer_name=customer_name,
                items=items,
                quote_number=quote_num,
                date=today(),
                subtotal=float(subtotal),
                vat=float(vat),
                total=float(total),
                status="draft",
                created_by=cashier_id,
                created_by_name=cashier_display,
                salesman=pos_salesman_id,
                salesman_name=pos_salesman_name
            )
            quote_id = quote["id"]
            
            success, err = db.save("quotes", quote)
            
            if success:
                logger.info(f"[POS] Quote {quote_num} created: R{total:.2f}")
                AuditLog.log("CREATE", "quotes", quote_id, details=f"Quote from POS - {customer_name}")
                return jsonify({
                    "success": True,
                    "quote_id": quote_id,
                    "quote_number": quote_num
                })
            else:
                return jsonify({"success": False, "error": str(err)})
                
        except Exception as e:
            logger.error(f"[POS] Quote error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/quick-quote", methods=["POST"])
    @login_required
    def api_pos_quick_quote():
        """
        Create a quote on-the-fly without needing stock items or saved customer.
        Customer is created if not exists, items are custom (non-stock).
        If customer_id is provided, uses existing customer.
        """
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            data = request.get_json()
            customer_data = data.get("customer", {})
            items = data.get("items", [])
            existing_customer_id = data.get("customer_id")  # Pre-selected customer
            
            customer_name = customer_data.get("name", "").strip()
            customer_phone = customer_data.get("phone", "").strip()
            customer_email = customer_data.get("email", "").strip()
            customer_vat = customer_data.get("vat_number", "").strip()
            customer_address = customer_data.get("address", "").strip()
            
            if not items:
                return jsonify({"success": False, "error": "No items in quote"})
            
            # Use existing customer if provided
            if existing_customer_id:
                customer_id = existing_customer_id
                # Get customer name if not provided
                if not customer_name:
                    cust = db.get_one("customers", existing_customer_id)
                    customer_name = cust.get("name", "Customer") if cust else "Customer"
            else:
                if not customer_name:
                    return jsonify({"success": False, "error": "Customer name required"})
                
                # Check if customer exists by name/phone, create if not
                existing_customers = db.get("customers", {"business_id": biz_id}) or []
                customer_id = None
                
                for c in existing_customers:
                    if c.get("name", "").lower() == customer_name.lower():
                        customer_id = c.get("id")
                        # Update VAT if provided and not already set
                        if customer_vat and not c.get("vat_number"):
                            db.update("customers", customer_id, {"vat_number": customer_vat})
                        break
                    if customer_phone and c.get("phone") == customer_phone:
                        customer_id = c.get("id")
                        customer_name = c.get("name", customer_name)
                        break
                
                # Create customer if not found
                if not customer_id:
                    new_customer = RecordFactory.customer(
                        business_id=biz_id,
                        name=customer_name,
                        phone=customer_phone,
                        email=customer_email,
                        vat_number=customer_vat,
                        address=customer_address
                    )
                    customer_id = new_customer["id"]
                    db.save("customers", new_customer)
                    logger.info(f"[QUICK QUOTE] Created new customer: {customer_name}")
            
            # Calculate totals - items come with excl VAT prices
            subtotal = Decimal("0")
            quote_items = []
            
            for item in items:
                desc = item.get("description", "Item")
                qty = Decimal(str(item.get("quantity", 1)))
                price = Decimal(str(item.get("price", 0)))  # Price excl VAT
                line_total = qty * price
                subtotal += line_total
                
                quote_items.append({
                    "code": "CUSTOM",
                    "description": desc,
                    "quantity": float(qty),
                    "price": float(price),
                    "total": float(line_total)
                })
            
            # Prices are EXCL VAT - ADD VAT to get total
            vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
            total = subtotal + vat
            
            # Generate quote number
            existing_quotes = db.get("quotes", {"business_id": biz_id}) or []
            quote_num = next_document_number("Q-", existing_quotes, "quote_number")
            
            # Create quote
            qq_salesman_id = data.get("salesman_id") or (user.get("id") if user else None)
            qq_salesman_name = data.get("salesman_name") or (user.get("name", "") if user else "")
            quote = RecordFactory.quote(
                business_id=biz_id,
                customer_id=customer_id,
                customer_name=customer_name,
                items=quote_items,
                quote_number=quote_num,
                date=today(),
                subtotal=float(subtotal),
                vat=float(vat),
                total=float(total),
                status="draft",
                created_by=user.get("id") if user else None,
                created_by_name=user.get("name", "") if user else "",
                salesman=qq_salesman_id,
                salesman_name=qq_salesman_name
            )
            quote_id = quote["id"]
            
            success, err = db.save("quotes", quote)
            
            if success:
                logger.info(f"[QUICK QUOTE] Created {quote_num} for {customer_name}: R{total:.2f}")
                AuditLog.log("CREATE", "quotes", quote_id, details=f"Quick quote - {customer_name}")
                return jsonify({
                    "success": True,
                    "quote_id": quote_id,
                    "quote_number": quote_num,
                    "customer_id": customer_id
                })
            else:
                return jsonify({"success": False, "error": str(err)})
                
        except Exception as e:
            logger.error(f"[QUICK QUOTE] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/quick-po", methods=["POST"])
    @login_required
    def api_pos_quick_po():
        """
        Create a PO on-the-fly without needing stock items or saved supplier.
        Supplier is created if not exists, items are custom (non-stock).
        If supplier_id is provided, uses existing supplier.
        """
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            data = request.get_json()
            supplier_data = data.get("supplier", {})
            items = data.get("items", [])
            notes = data.get("notes", "")
            existing_supplier_id = data.get("supplier_id")  # Pre-selected supplier
            
            supplier_name = supplier_data.get("name", "").strip()
            supplier_phone = supplier_data.get("phone", "").strip()
            supplier_email = supplier_data.get("email", "").strip()
            supplier_vat = supplier_data.get("vat_number", "").strip()
            
            if not items:
                return jsonify({"success": False, "error": "No items in PO"})
            
            # Use existing supplier if provided
            if existing_supplier_id:
                supplier_id = existing_supplier_id
                # Get supplier name if not provided
                if not supplier_name:
                    sup = db.get_one("suppliers", existing_supplier_id)
                    supplier_name = sup.get("name", "Supplier") if sup else "Supplier"
            else:
                if not supplier_name:
                    return jsonify({"success": False, "error": "Supplier name required"})
                
                # Check if supplier exists by name/phone, create if not
                existing_suppliers = db.get("suppliers", {"business_id": biz_id}) or []
                supplier_id = None
                
                for s in existing_suppliers:
                    if s.get("name", "").lower() == supplier_name.lower():
                        supplier_id = s.get("id")
                        # Update VAT if provided and not already set
                        if supplier_vat and not s.get("vat_number"):
                            db.update("suppliers", supplier_id, {"vat_number": supplier_vat})
                        break
                    if supplier_phone and s.get("phone") == supplier_phone:
                        supplier_id = s.get("id")
                        supplier_name = s.get("name", supplier_name)
                        break
                
                # Create supplier if not found
                if not supplier_id:
                    new_supplier = RecordFactory.supplier(
                        business_id=biz_id,
                        name=supplier_name,
                        phone=supplier_phone,
                        email=supplier_email,
                        vat_number=supplier_vat
                    )
                    supplier_id = new_supplier["id"]
                    db.save("suppliers", new_supplier)
                    logger.info(f"[QUICK PO] Created new supplier: {supplier_name}")
            
            # Build PO items (no prices - PO is just a request)
            po_items = []
            total_qty = 0
            
            for item in items:
                desc = item.get("description", "Item")
                qty = int(item.get("qty", 1))
                total_qty += qty
                
                po_items.append({
                    "code": "CUSTOM",
                    "description": desc,
                    "qty": qty
                })
            
            # Generate PO number using standard next_document_number()
            existing_pos = db.get("purchase_orders", {"business_id": biz_id}) or []
            po_num = next_document_number("PO-", existing_pos, field="po_number")
            
            # Create PO
            po = {
                "id": generate_id(),
                "business_id": biz_id,
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "po_number": po_num,
                "date": today(),
                "items": po_items,
                "notes": notes,
                "reference": data.get("reference", ""),
                "status": "draft",
                "created_at": now(),
                "created_by": user.get("id") if user else None
            }
            
            success, err = db.save("purchase_orders", po)
            
            if success:
                logger.info(f"[QUICK PO] Created {po_num} for {supplier_name}: {total_qty} items")
                AuditLog.log("CREATE", "purchase_orders", po["id"], details=f"Quick PO - {supplier_name}")
                return jsonify({
                    "success": True,
                    "po_id": po["id"],
                    "po_number": po_num,
                    "supplier_id": supplier_id
                })
            else:
                return jsonify({"success": False, "error": str(err)})
                
        except Exception as e:
            logger.error(f"[QUICK PO] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/invoice", methods=["POST"])
    @login_required
    def api_pos_invoice():
        """Create invoice from POS cart"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            data = request.get_json()
            items = data.get("items", [])
            customer_id = data.get("customer_id", "")
            customer_name = data.get("customer_name", "")
            cashier_id = data.get("cashier_id") or (user.get("id") if user else None)
            cashier_display = data.get("cashier_name") or (user.get("name", "") if user else "")
            
            if not items:
                return jsonify({"success": False, "error": "No items in cart"})
            
            # Validate customer_id using safe_uuid
            safe_customer_id = safe_uuid(customer_id)
            if not safe_customer_id:
                return jsonify({"success": False, "error": "Please select a valid customer from the list"})
            
            # Use frontend-calculated values (prices are EXCL VAT, VAT is ADDED)
            subtotal = Decimal(str(data.get("subtotal", 0)))
            vat = Decimal(str(data.get("vat", 0)))
            total = Decimal(str(data.get("total", 0)))
            
            # Fallback calculation if frontend didn't send values
            if subtotal == 0:
                subtotal = sum(Decimal(str(item.get("total", 0))) for item in items)
                vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
                total = subtotal + vat
            
            # Generate invoice number (safe even after deletions)
            existing = db.get("invoices", {"business_id": biz_id}) if biz_id else []
            inv_num = next_document_number("INV-", existing, "invoice_number")
            
            # Create invoice
            user = Auth.get_current_user()
            invoice = RecordFactory.invoice(
                business_id=biz_id,
                customer_id=safe_customer_id,
                customer_name=customer_name,
                items=items,
                invoice_number=inv_num,
                date=today(),
                due_date=today(),
                subtotal=float(subtotal),
                vat=float(vat),
                total=float(total),
                status="outstanding",
                payment_method="account",
                created_by=cashier_id,
                created_by_name=cashier_display,
                salesman=data.get("salesman_id") or cashier_id,
                salesman_name=data.get("salesman_name") or cashier_display,
                sales_rep=data.get("salesman_name") or cashier_display
            )
            invoice_id = invoice["id"]
            
            success, err = db.save("invoices", invoice)
            
            if not success:
                return jsonify({"success": False, "error": str(err)})
            
            # Update stock quantities
            for item in items:
                stock_id = item.get("stock_id")
                qty_sold = int(item.get("quantity", 0))
                
                if stock_id and qty_sold > 0:
                    stock_item = db.get_one_stock(stock_id)
                    if stock_item:
                        current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                        new_qty = current_qty - qty_sold
                        db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
                        logger.info(f"[POS INV] Stock {stock_id}: {current_qty} - {qty_sold} = {new_qty}")
                        # Log stock movement
                        try:
                            db.save("stock_movements", RecordFactory.stock_movement(
                                business_id=biz_id, stock_id=stock_id, movement_type="out",
                                quantity=qty_sold, reference=f"Invoice {inv_num}"
                            ))
                        except Exception as sm_err: logger.error(f"[STOCK MOVEMENT] Save failed: {sm_err}")
            
            # Update customer balance
            customer = db.get_one("customers", customer_id)
            if customer:
                new_balance = float(customer.get("balance", 0)) + float(total)
                db.update("customers", customer_id, {"balance": new_balance})
            
            # Create journal entries (Debit Debtors, Credit Sales + VAT)
            try:
                create_journal_entry(biz_id, today(), f"Invoice {inv_num} - {customer_name}", inv_num, [
                    {"account_code": gl(biz_id, "debtors"), "debit": float(total), "credit": 0},
                    {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": float(subtotal)},
                    {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": float(vat)},
                ])
            except Exception as je:
                logger.warning(f"[POS INV] Journal entry failed: {je}")
            
            logger.info(f"[POS] Invoice {inv_num} created: R{total:.2f}")
            AuditLog.log("CREATE", "invoices", invoice_id, details=f"Invoice from POS - {customer_name}")
            
            return jsonify({
                "success": True,
                "invoice_id": invoice_id,
                "invoice_number": inv_num
            })
                
        except Exception as e:
            logger.error(f"[POS] Invoice error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/customer-invoices")
    @login_required
    def api_pos_customer_invoices():
        """Get invoices AND sales for a customer (for credit note selection)"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        customer_id = request.args.get("customer_id", "")
        
        if not customer_id:
            return jsonify({"success": False, "error": "Customer ID required"})
        
        try:
            # Get invoices
            all_invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
            invoices = [inv for inv in all_invoices if inv.get("customer_id") == customer_id]
            
            # Also get sales for this customer
            all_sales = db.get("sales", {"business_id": biz_id}) if biz_id else []
            sales = [s for s in all_sales if s.get("customer_id") == customer_id]
            
            # Combine and sort
            combined = []
            
            for inv in invoices:
                combined.append({
                    "id": inv.get("id"),
                    "invoice_number": inv.get("invoice_number", "-"),
                    "date": inv.get("date", "-"),
                    "total": float(inv.get("total", 0)),
                    "status": inv.get("status", "outstanding"),
                    "type": "invoice"
                })
            
            for sale in sales:
                combined.append({
                    "id": sale.get("id"),
                    "invoice_number": sale.get("sale_number", "-"),
                    "date": sale.get("date", "-"),
                    "total": float(sale.get("total", 0)),
                    "status": "paid",  # Sales are immediate payment
                    "type": "sale",
                    "payment_method": sale.get("payment_method", "cash")
                })
            
            # Sort by date descending
            combined = sorted(combined, key=lambda x: x.get("date", ""), reverse=True)[:20]
            
            return jsonify({"success": True, "invoices": combined})
            
        except Exception as e:
            logger.error(f"[POS] Customer invoices error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/credit-note", methods=["POST"])
    @login_required
    def api_pos_credit_note():
        """Create credit note from POS cart"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # ── FRAUD GUARD: Check role for POS credit notes ──
        try:
            if FraudGuard:
                _role = get_user_role()
                if _role in ("cashier", "pos_only", "waiter"):
                    return jsonify({"success": False, "error": "Only a manager or owner can issue credit notes from POS. Ask your manager for help."})
        except Exception:
            pass
        
        try:
            data = request.get_json()
            items = data.get("items", [])
            customer_id = data.get("customer_id", "")
            customer_name = data.get("customer_name", "")
            total = Decimal(str(data.get("total", 0)))
            
            if not items:
                return jsonify({"success": False, "error": "No items in cart"})
            
            if not customer_id:
                return jsonify({"success": False, "error": "Customer required for credit note"})
            
            # Use frontend-calculated values (prices are EXCL VAT, VAT is ADDED)
            subtotal = Decimal(str(data.get("subtotal", 0)))
            vat = Decimal(str(data.get("vat", 0)))
            total = Decimal(str(data.get("total", 0)))
            
            # Fallback calculation if frontend didn't send values
            if subtotal == 0:
                subtotal = sum(Decimal(str(item.get("total", 0))) for item in items)
                vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"))
                total = subtotal + vat
            
            # Generate credit note number
            existing = db.get("credit_notes", {"business_id": biz_id}) if biz_id else []
            cn_num = next_document_number("CN-", existing, "credit_note_number")
            
            # Create credit note
            cn_id = generate_id()
            credit_note = {
                "id": cn_id,
                "business_id": biz_id,
                "credit_note_number": cn_num,
                "date": today(),
                "customer_id": customer_id,
                "customer_name": customer_name,
                "invoice_id": None,  # Direct credit note, not linked to invoice
                "items": json.dumps(items),
                "subtotal": float(subtotal),
                "vat": float(vat),
                "total": float(total),
                "reason": "POS Credit Note",
                "created_at": now()
            }
            
            success, err = db.save("credit_notes", credit_note)
            
            if not success:
                return jsonify({"success": False, "error": str(err)})
            
            # Return stock to inventory
            for item in items:
                stock_id = item.get("stock_id")
                qty_returned = int(item.get("quantity", 0))
                
                if stock_id and qty_returned > 0:
                    stock_item = db.get_one_stock(stock_id)
                    if stock_item:
                        current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
                        new_qty = current_qty + qty_returned
                        db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
                        logger.info(f"[POS CN] Stock {stock_id}: {current_qty} + {qty_returned} = {new_qty}")
                        # Log stock movement
                        try:
                            db.save("stock_movements", RecordFactory.stock_movement(
                                business_id=biz_id, stock_id=stock_id, movement_type="in",
                                quantity=qty_returned, reference=f"Credit Note {cn_num}"
                            ))
                        except Exception as sm_err: logger.error(f"[STOCK MOVEMENT] Save failed: {sm_err}")
            
            # Update customer balance (reduce it)
            customer = db.get_one("customers", customer_id)
            if customer:
                new_balance = float(customer.get("balance", 0)) - float(total)
                db.update("customers", customer_id, {"balance": new_balance})
            
            # Create journal entries (reverse of invoice)
            # Credit Debtors, Debit Sales + VAT
            try:
                create_journal_entry(biz_id, today(), f"Credit Note {cn_num} - {customer_name}", cn_num, [
                    {"account_code": gl(biz_id, "debtors"), "debit": 0, "credit": float(total)},  # Credit Debtors
                    {"account_code": gl(biz_id, "sales"), "debit": float(subtotal), "credit": 0},  # Debit Sales
                    {"account_code": gl(biz_id, "vat_output"), "debit": float(vat), "credit": 0},  # Debit VAT
                ])
            except Exception as je:
                logger.warning(f"[POS CN] Journal entry failed: {je}")
            
            logger.info(f"[POS] Credit Note {cn_num} created: -R{total:.2f}")
            AuditLog.log("CREATE", "credit_notes", cn_id, details=f"Credit Note from POS - {customer_name}")
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    log_allocation(
                        business_id=biz_id, allocation_type="credit_note", source_table="credit_notes", source_id=cn_id,
                        description=f"POS Credit Note {cn_num} - {customer_name}",
                        amount=float(total),
                        gl_entries=[
                            {"account_code": gl(biz_id, "debtors"), "debit": 0, "credit": float(total)},
                            {"account_code": gl(biz_id, "sales"), "debit": float(subtotal), "credit": 0},
                            {"account_code": gl(biz_id, "vat_output"), "debit": float(vat), "credit": 0},
                        ],
                        customer_name=customer_name, reference=cn_num,
                        transaction_date=today(),
                        created_by=user.get("id") if user else "", created_by_name=user.get("name", "") if user else ""
                    )
            except Exception:
                pass
            
            return jsonify({
                "success": True,
                "credit_note_id": cn_id,
                "credit_note_number": cn_num
            })
                
        except Exception as e:
            logger.error(f"[POS] Credit note error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/pos/purchase-order", methods=["POST"])
    @login_required
    def api_pos_purchase_order():
        """Create purchase order from POS cart - NO PRICES"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            data = request.get_json()
            items = data.get("items", [])
            supplier_id = data.get("supplier_id", "")
            supplier_name = data.get("supplier_name", "")
            
            if not items:
                return jsonify({"success": False, "error": "No items in cart"})
            
            if not supplier_name:
                return jsonify({"success": False, "error": "Supplier name required"})
            
            # Use provided supplier_id or find/create supplier
            supplier_email = ""
            if not supplier_id:
                suppliers = db.get("suppliers", {"business_id": biz_id, "name": supplier_name}) if biz_id else []
                if suppliers:
                    supplier_id = suppliers[0].get("id")
                    supplier_email = suppliers[0].get("email", "")
                else:
                    # Create new supplier
                    supplier_id = generate_id()
                    db.save("suppliers", {
                        "id": supplier_id,
                        "business_id": biz_id,
                        "name": supplier_name,
                        "balance": 0,
                        "created_at": now()
                    })
            else:
                # Look up supplier email from existing record
                sup = db.get_one("suppliers", supplier_id)
                if sup:
                    supplier_email = sup.get("email", "")
            
            # Generate PO number using standard next_document_number()
            existing = db.get("purchase_orders", {"business_id": biz_id}) if biz_id else []
            po_num = next_document_number("PO-", existing, field="po_number")
            
            # Clean items - remove any prices that might have snuck in
            clean_items = []
            for item in items:
                sid = item.get("stock_id") or ""
                # Clear fake IDs from custom items
                if sid.startswith("CUSTOM") or not sid:
                    sid = None
                clean_items.append({
                    "stock_id": sid,
                    "code": item.get("code", ""),
                    "description": item.get("description", ""),
                    "qty": item.get("qty") or item.get("quantity", 1),
                    "qty_received": 0
                })
            
            # Create purchase order - NO PRICES
            po_id = generate_id()
            po = {
                "id": po_id,
                "business_id": biz_id,
                "po_number": po_num,
                "date": today(),
                "supplier_id": supplier_id,
                "supplier_name": supplier_name,
                "items": json.dumps(clean_items),
                "status": "draft",
                "sales_person": data.get("sales_person", ""),
                "reference": data.get("reference", ""),
                "created_at": now()
            }
            
            success, err = db.save("purchase_orders", po)
            
            if success:
                logger.info(f"[POS] PO {po_num} created for {supplier_name}")
                AuditLog.log("CREATE", "purchase_orders", po_id, details=f"PO from POS - {supplier_name}")
                return jsonify({
                    "success": True,
                    "po_id": po_id,
                    "po_number": po_num
                })
            else:
                return jsonify({"success": False, "error": str(err)})
                
        except Exception as e:
            logger.error(f"[POS] PO error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    

    # === BAR / RESTAURANT POS ===

    @app.route("/bar")
    @login_required
    def bar_pos():
        """Bar/Restaurant POS with tables"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get stock items (drinks/food) - from BOTH tables
        items = db.get_all_stock(biz_id) if biz_id else []
        items = sorted(items, key=lambda x: x.get("description", ""))
        
        # Get open tabs/tables
        tabs = db.get("bar_tabs", {"business_id": biz_id, "status": "open"}) if biz_id else []
        
        # Group items by category
        categories = {}
        for item in items:
            cat = item.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        # Build category tabs
        cat_tabs = ""
        cat_content = ""
        first = True
        for cat, cat_items in categories.items():
            active = "active" if first else ""
            cat_tabs += f'<button class="tab-btn {active}" onclick="showCategory(this, \'{cat}\')">{cat}</button>'
            
            items_html = ""
            for item in cat_items:
                items_html += f'''
                <div class="bar-item" onclick="addToOrder('{item.get("id")}', '{safe_string(item.get("description", ""))}', {item.get("selling_price", 0)})">
                    <div style="font-weight:bold;">{safe_string(item.get("description", "-"))}</div>
                    <div style="color:var(--green);">{money(item.get("selling_price", 0))}</div>
                </div>
                '''
            
            cat_content += f'<div class="cat-items {"" if first else "hidden"}" id="cat-{cat}">{items_html}</div>'
            first = False
        
        # Build tables
        tables_html = ""
        for i in range(1, 13):
            tab = next((t for t in tabs if t.get("table_number") == i), None)
            status = "occupied" if tab else ""
            amount = money(tab.get("total", 0)) if tab else ""
            tables_html += f'''
            <div class="table-btn {status}" onclick="selectTable({i})">
                <div style="font-size:20px;">T{i}</div>
                {f'<div style="font-size:12px;color:var(--green);">{amount}</div>' if amount else ''}
            </div>
            '''
        
        content = f'''
        <style>
        .bar-layout {{ display: grid; grid-template-columns: 1fr 300px; gap: 20px; height: calc(100vh - 200px); }}
        .bar-items {{ overflow-y: auto; }}
        .bar-item {{ background: var(--bg-card); padding: 15px; border-radius: 8px; cursor: pointer; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }}
        .bar-item:hover {{ background: rgba(99,102,241,0.2); }}
        .tab-btn {{ background: transparent; border: none; color: var(--text-muted); padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent; }}
        .tab-btn.active {{ color: var(--primary); border-bottom-color: var(--primary); }}
        .hidden {{ display: none; }}
        .table-btn {{ background: var(--bg-card); padding: 20px; border-radius: 8px; cursor: pointer; text-align: center; }}
        .table-btn.occupied {{ background: rgba(239,68,68,0.2); border: 2px solid var(--red); }}
        .table-btn.selected {{ background: rgba(99,102,241,0.3); border: 2px solid var(--primary); }}
        .order-panel {{ background: var(--bg-card); border-radius: 12px; padding: 15px; display: flex; flex-direction: column; }}
        .order-items {{ flex: 1; overflow-y: auto; }}
        .order-item {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); }}
        @media (max-width: 768px) {{ .bar-layout {{ grid-template-columns: 1fr; }} }}
        </style>
        
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2 style="margin:0;"> Bar POS</h2>
            <a href="/pos" class="btn btn-secondary">Standard POS</a>
        </div>
        
        <div style="margin-bottom:15px;">
            <h4 style="margin:0 0 10px 0;color:var(--text-muted);">Tables</h4>
            <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:10px;">
                {tables_html}
            </div>
        </div>
        
        <div class="bar-layout">
            <div class="bar-items">
                <div style="display:flex;gap:5px;margin-bottom:15px;flex-wrap:wrap;">
                    {cat_tabs}
                </div>
                {cat_content}
            </div>
            
            <div class="order-panel">
                <h3 style="margin:0 0 10px 0;">Current Order <span id="tableLabel"></span></h3>
                <div class="order-items" id="orderItems">
                    <p style="color:var(--text-muted);text-align:center;">Select a table first</p>
                </div>
                <div style="border-top:1px solid var(--border);padding-top:10px;margin-top:10px;">
                    <div style="display:flex;justify-content:space-between;font-size:20px;font-weight:bold;margin-bottom:15px;">
                        <span>Total</span>
                        <span id="orderTotal">R0.00</span>
                    </div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                        <button class="btn btn-secondary" onclick="printBill()"> Bill</button>
                        <button class="btn btn-primary" onclick="payOrder()"> Pay</button>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        let currentTable = null;
        let currentOrder = [];
        let currentTabId = null;
        
        function showCategory(btn, cat) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.cat-items').forEach(c => c.classList.add('hidden'));
            btn.classList.add('active');
            document.getElementById('cat-' + cat).classList.remove('hidden');
        }}
        
        function selectTable(num) {{
            document.querySelectorAll('.table-btn').forEach(t => t.classList.remove('selected'));
            event.target.closest('.table-btn').classList.add('selected');
            currentTable = num;
            document.getElementById('tableLabel').textContent = '- Table ' + num;
            loadTableOrder(num);
        }}
        
        async function loadTableOrder(tableNum) {{
            const response = await fetch('/api/bar/table/' + tableNum);
            const data = await response.json();
            currentOrder = data.items || [];
            currentTabId = data.tab_id;
            renderOrder();
        }}
        
        function addToOrder(itemId, name, price) {{
            if (!currentTable) {{
                alert('Select a table first');
                return;
            }}
            currentOrder.push({{ id: itemId, name: name, price: price, qty: 1 }});
            renderOrder();
            saveOrder();
        }}
        
        function renderOrder() {{
            let html = '';
            let total = 0;
            currentOrder.forEach((item, i) => {{
                total += item.price * item.qty;
                html += '<div class="order-item"><span>' + item.qty + 'x ' + item.name + '</span><span>R' + (item.price * item.qty).toFixed(2) + '</span></div>';
            }});
            document.getElementById('orderItems').innerHTML = html || '<p style="color:var(--text-muted);text-align:center;">No items</p>';
            document.getElementById('orderTotal').textContent = 'R' + total.toFixed(2);
        }}
        
        async function saveOrder() {{
            await fetch('/api/bar/save-order', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ table: currentTable, items: currentOrder, tab_id: currentTabId }})
            }});
        }}
        
        async function payOrder() {{
            if (!currentTable || currentOrder.length === 0) return;
            if (confirm('Complete payment for Table ' + currentTable + '?')) {{
                await fetch('/api/bar/pay', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ table: currentTable, tab_id: currentTabId }})
                }});
                location.reload();
            }}
        }}
        
        function printBill() {{
            if (!currentTable) return;
            window.open('/bar/bill/' + currentTable, '_blank');
        }}
        </script>
        '''
        
        return render_page("Bar POS", content, user, "pos")
    
    
    @app.route("/api/bar/table/<int:table_num>")
    @login_required
    def api_bar_table(table_num):
        """Get table order"""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        tabs = db.get("bar_tabs", {"business_id": biz_id, "table_number": table_num, "status": "open"}) if biz_id else []
        tab = tabs[0] if tabs else None
        
        if tab:
            try:
                items = json.loads(tab.get("items", "[]"))
            except:
                items = []
            return jsonify({"tab_id": tab.get("id"), "items": items})
        
        return jsonify({"tab_id": None, "items": []})
    
    
    @app.route("/api/bar/save-order", methods=["POST"])
    @login_required
    def api_bar_save_order():
        """Save table order"""
        try:
            data = request.get_json()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            table_num = data.get("table")
            items = data.get("items", [])
            tab_id = data.get("tab_id")
            
            total = sum(item.get("price", 0) * item.get("qty", 1) for item in items)
            
            if tab_id:
                # Update existing tab
                db.save("bar_tabs", {
                    "id": tab_id,
                    "items": json.dumps(items),
                    "total": total
                })
            else:
                # Create new tab
                tab_id = generate_id()
                db.save("bar_tabs", {
                    "id": tab_id,
                    "business_id": biz_id,
                    "table_number": table_num,
                    "items": json.dumps(items),
                    "total": total,
                    "status": "open",
                    "created_at": now()
                })
            
            return jsonify({"success": True, "tab_id": tab_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/bar/pay", methods=["POST"])
    @login_required
    def api_bar_pay():
        """Close tab and record sale"""
        try:
            data = request.get_json()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            tab_id = data.get("tab_id")
            
            if tab_id:
                tab = db.get_one("bar_tabs", tab_id)
                if tab:
                    # Record as POS sale
                    try:
                        items = json.loads(tab.get("items", "[]"))
                    except:
                        items = []
                    
                    total = float(tab.get("total", 0))
                    vat = total * float(VAT_RATE) / (1 + float(VAT_RATE))
                    subtotal = total - vat
                    
                    db.save("sales", {
                        "id": generate_id(),
                        "business_id": biz_id,
                        "date": today(),
                        "items": json.dumps(items),
                        "subtotal": subtotal,
                        "vat": vat,
                        "total": total,
                        "payment_method": "cash",
                        "source": "bar",
                        "created_at": now()
                    })
                    
                    # Close tab
                    db.save("bar_tabs", {"id": tab_id, "status": "closed"})
            
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/bar/bill/<int:table_num>")
    @login_required
    def bar_bill(table_num):
        """Print bill for table"""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("name", "Business") if business else "Business"
        
        tabs = db.get("bar_tabs", {"business_id": biz_id, "table_number": table_num, "status": "open"}) if biz_id else []
        tab = tabs[0] if tabs else None
        
        if not tab:
            return "No open tab for this table"
        
        try:
            items = json.loads(tab.get("items", "[]"))
        except:
            items = []
        
        items_html = ""
        for item in items:
            items_html += f'<tr><td>{item.get("qty", 1)}x {item.get("name", "-")}</td><td style="text-align:right;">{money(item.get("price", 0) * item.get("qty", 1))}</td></tr>'
        
        return f'''
        <html>
        <head><title>Bill - Table {table_num}</title>
        <style>
            body {{ font-family: monospace; max-width: 300px; margin: 20px auto; }}
            table {{ width: 100%; }}
            .total {{ font-size: 18px; font-weight: bold; border-top: 2px solid #000; padding-top: 10px; }}
        </style>
        </head>
        <body>
            <h2 style="text-align:center;">{biz_name}</h2>
            <p style="text-align:center;">Table {table_num}</p>
            <hr>
            <table>{items_html}</table>
            <hr>
            <div class="total" style="display:flex;justify-content:space-between;">
                <span>TOTAL</span>
                <span>{money(tab.get("total", 0))}</span>
            </div>
            <p style="text-align:center;margin-top:20px;color:#666;">Thank you!</p>
            <script>window.print();</script>
        </body>
        </html>
        '''


    # === POS SETTINGS ===

    @app.route("/api/settings/pos", methods=["POST"])
    @login_required
    def api_settings_pos():
        """Save POS print settings"""
        
        try:
            business = Auth.get_current_business()
            if not business:
                flash("No business found", "error")
                return redirect("/settings")
            
            updates = {
                "id": business.get("id"),
                "pos_auto_print": bool(request.form.get("pos_auto_print")),
                "pos_print_duplicates": bool(request.form.get("pos_print_duplicates")),
                "pos_print_format": request.form.get("pos_print_format", "ask"),
                "pos_slip_footer": request.form.get("pos_slip_footer", "Thank you for your purchase!"),
            }
            
            db.save("businesses", updates)
            flash("POS settings saved", "success")
            
            return redirect("/settings")
        except Exception as e:
            logger.error(f"[SETTINGS POS] Error: {e}")
            flash(f"Error saving POS settings: {str(e)}", "error")
            return redirect("/settings")

    logger.info("[POS] All POS & Bar routes registered ✓")

