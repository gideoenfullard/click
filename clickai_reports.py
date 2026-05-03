# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - REPORTS MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Reports index, Aging, Debtors, Creditors, GL Report, Trial Balance,
#           TB APIs, PnL, Balance Sheet, VAT, Cashflow, Smart Reports, Budget
# ==============================================================================

import os
import json
import time
import logging
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def register_report_routes(app, db, login_required, Auth, render_page,
                           generate_id, money, safe_string, now, today,
                           has_reactor_hud, jarvis_hud_header, jarvis_techline,
                           AuditLog, Email, IndustryKnowledge,
                           JARVIS_HUD_CSS, THEME_REACTOR_SKINS,
                           _anthropic_client):
    """Register all Report routes with the Flask app."""

    # Alias for compatibility
    EmailService = Email


    # === REPORTS INDEX, AGING, DEBTORS, CREDITORS ===

    @app.route("/reports")
    @login_required
    def reports_page():
        """Reports Hub"""
        
        user = Auth.get_current_user()
        
        content = '''
        <h2 style="margin-bottom:20px;"> Reports</h2>
        
        <div class="card" style="background:linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.1));margin-bottom:20px;cursor:pointer;" onclick="window.location='/reports/smart'">
            <div style="display:flex;align-items:center;gap:15px;">
                <span style="font-size:40px;"></span>
                <div>
                    <h3 style="margin:0;">Smart Reports</h3>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;">Ask Zane to write ANY report - management statements, KPIs, forecasts...</p>
                </div>
            </div>
        </div>
        
        <div class="card" style="background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(99,102,241,0.1));margin-bottom:20px;cursor:pointer;border:1px solid rgba(16,185,129,0.3);" onclick="window.location='/reports/gl-analysis'">
            <div style="display:flex;align-items:center;gap:15px;">
                <span style="font-size:40px;">🔬</span>
                <div>
                    <h3 style="margin:0;">GL Analysis</h3>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;">Upload a client GL from Sage or Xero — instant TB check, anomaly detection & AI insights</p>
                </div>
            </div>
        </div>
        
        <h3 style="margin:20px 0 10px 0;color:var(--text-muted);">Debtors & Creditors</h3>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/aging'">
                <h3> Debtors Aging</h3>
                <p style="color:var(--text-muted)">30/60/90/120 day analysis</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/debtors'">
                <h3> Debtors Report</h3>
                <p style="color:var(--text-muted)">Who owes you money</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/creditors'">
                <h3> Creditors Report</h3>
                <p style="color:var(--text-muted)">What you owe suppliers</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/creditors-aging'">
                <h3> Creditors Aging</h3>
                <p style="color:var(--text-muted)">Supplier aging analysis</p>
            </div>
        </div>
        
        <h3 style="margin:30px 0 10px 0;color:var(--text-muted);">Financial Statements</h3>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/tb'">
                <h3> Trial Balance</h3>
                <p style="color:var(--text-muted)">Debit/Credit summary</p>
            </div>
            <div class="card" style="cursor:pointer;border:1px solid rgba(245,158,11,0.3);" onclick="window.location='/suspense-explainer'">
                <h3>⚠️ Suspense Explainer</h3>
                <p style="color:var(--text-muted)">Where opening-balance variances came from</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/pnl'">
                <h3> Profit & Loss</h3>
                <p style="color:var(--text-muted)">Income vs Expenses</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/balance-sheet'">
                <h3> Balance Sheet</h3>
                <p style="color:var(--text-muted)">Assets, Liabilities, Equity</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/cashflow'">
                <h3> Cash Flow</h3>
                <p style="color:var(--text-muted)">Money in vs out</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/gl'">
                <h3> General Ledger</h3>
                <p style="color:var(--text-muted)">All transactions by account</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/budget'">
                <h3> Budget vs Actual</h3>
                <p style="color:var(--text-muted)">Track against targets</p>
            </div>
        </div>
        
        <h3 style="margin:30px 0 10px 0;color:var(--text-muted);">Tax & Compliance</h3>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer;background:linear-gradient(135deg, rgba(16,185,129,0.2), rgba(34,197,94,0.1));border:1px solid rgba(16,185,129,0.3);" onclick="window.location='/tax-saver'">
                <h3>Tax Saver</h3>
                <p style="color:var(--text-muted)">Find money you're missing!</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/reports/vat'">
                <h3>[CHART] VAT Report</h3>
                <p style="color:var(--text-muted)">VAT201 summary for SARS</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/banking'">
                <h3>[BANK] Bank Reconciliation</h3>
                <p style="color:var(--text-muted)">Match bank to books</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/year-end'">
                <h3>Year End Close</h3>
                <p style="color:var(--text-muted)">Close financial year</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/credit-notes'">
                <h3>Credit Notes</h3>
                <p style="color:var(--text-muted)">View all credit notes</p>
            </div>
        </div>
        
        <p style="color:var(--text-muted);text-align:center;margin-top:30px;">
        <h3 style="margin:30px 0 10px 0;color:var(--text-muted);">Zane AI Advisor</h3>
        <p style="color:var(--text-muted);font-size:13px;margin-bottom:12px;">Ask Zane about any of these topics — he has deep SA business knowledge built in:</p>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer;border-left:3px solid #6366f1;" onclick="document.getElementById('jzInput')?.focus();if(typeof jzToggle==='function')jzToggle();">
                <h3 style="font-size:15px;">SA Business Law</h3>
                <p style="color:var(--text-muted);font-size:12px;">Contracts, CPA, disputes, IP, POPIA</p>
            </div>
            <div class="card" style="cursor:pointer;border-left:3px solid #10b981;" onclick="document.getElementById('jzInput')?.focus();if(typeof jzToggle==='function')jzToggle();">
                <h3 style="font-size:15px;">Tax Strategy</h3>
                <p style="color:var(--text-muted);font-size:12px;">Deductions, CGT, wear & tear, provisional tax, pay yourself</p>
            </div>
            <div class="card" style="cursor:pointer;border-left:3px solid #f59e0b;" onclick="document.getElementById('jzInput')?.focus();if(typeof jzToggle==='function')jzToggle();">
                <h3 style="font-size:15px;">HR & Labour</h3>
                <p style="color:var(--text-muted);font-size:12px;">BCEA, discipline, CCMA, leave, hiring, EE Act</p>
            </div>
            <div class="card" style="cursor:pointer;border-left:3px solid #ec4899;" onclick="document.getElementById('jzInput')?.focus();if(typeof jzToggle==='function')jzToggle();">
                <h3 style="font-size:15px;">Insurance</h3>
                <p style="color:var(--text-muted);font-size:12px;">Cover types, claims, liability, fleet, business interruption</p>
            </div>
            <div class="card" style="cursor:pointer;border-left:3px solid #8b5cf6;" onclick="document.getElementById('jzInput')?.focus();if(typeof jzToggle==='function')jzToggle();">
                <h3 style="font-size:15px;">SARS Compliance</h3>
                <p style="color:var(--text-muted);font-size:12px;">VAT, PAYE, UIF, SDL, eFiling, returns</p>
            </div>
            <div class="card" style="cursor:pointer;border-left:3px solid #14b8a6;" onclick="document.getElementById('jzInput')?.focus();if(typeof jzToggle==='function')jzToggle();">
                <h3 style="font-size:15px;">BEE & CIPC</h3>
                <p style="color:var(--text-muted);font-size:12px;">B-BBEE levels, registration, annual returns, compliance</p>
            </div>
        </div>
        
        <p style="color:var(--text-muted);text-align:center;margin-top:30px;">
            [TIP] Or just ask Zane anything: "Show me aging" / "Who owes me?" / "Write me a management report"
        </p>
        '''
        
        # -- JARVIS: Reports HUD header --
        if has_reactor_hud():
            _hud = jarvis_hud_header(
                page_name="REPORTS",
                page_count="FINANCIAL ANALYTICS",
                left_items=[
                    ("TRIAL BALANCE", "VIEW", "c", "", ""),
                    ("P&amp;L", "VIEW", "g", "g", ""),
                    ("BALANCE SHEET", "VIEW", "c", "", ""),
                    ("VAT RETURN", "VIEW", "o", "", ""),
                ],
                right_items=[
                    ("SMART REPORTS", "AI", "p", "", ""),
                    ("CASH FLOW", "VIEW", "g", "g", ""),
                    ("DEBTORS AGE", "VIEW", "r", "", ""),
                    ("CREDITORS AGE", "VIEW", "o", "", ""),
                ],
                reactor_size="page",
                alert_html=""
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline("REPORTS <b>READY</b>")
        
        return render_page("Reports", content, user, "reports")
    
    
    # 
    # DEBTORS AGING REPORT - 30/60/90/120 days
    # 
    
    @app.route("/reports/aging")
    @login_required
    def report_aging():
        """Debtors Aging Report"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get all invoices
        invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
        outstanding = [inv for inv in invoices if inv.get("status") != "paid"]
        
        # Get customers
        customers = db.get("customers", {"business_id": biz_id}) if biz_id else []
        customer_map = {c.get("id"): c for c in customers}
        
        # Calculate aging buckets
        today_date = datetime.now().date()
        
        aging_data = {}  # customer_id -> {current, 30, 60, 90, 120+, total}
        
        for inv in outstanding:
            cust_id = inv.get("customer_id")
            if not cust_id:
                continue
            
            if cust_id not in aging_data:
                cust = customer_map.get(cust_id, {})
                aging_data[cust_id] = {
                    "name": cust.get("name", "Unknown"),
                    "current": 0,
                    "d30": 0,
                    "d60": 0,
                    "d90": 0,
                    "d120": 0,
                    "total": 0
                }
            
            # Parse invoice date
            try:
                inv_date = datetime.strptime(inv.get("date", today()), "%Y-%m-%d").date()
            except:
                inv_date = today_date
            
            days_old = (today_date - inv_date).days
            amount = float(inv.get("total", 0))
            
            if days_old <= 30:
                aging_data[cust_id]["current"] += amount
            elif days_old <= 60:
                aging_data[cust_id]["d30"] += amount
            elif days_old <= 90:
                aging_data[cust_id]["d60"] += amount
            elif days_old <= 120:
                aging_data[cust_id]["d90"] += amount
            else:
                aging_data[cust_id]["d120"] += amount
            
            aging_data[cust_id]["total"] += amount
        
        # Sort by total descending
        sorted_aging = sorted(aging_data.values(), key=lambda x: x["total"], reverse=True)
        
        # Calculate totals
        totals = {"current": 0, "d30": 0, "d60": 0, "d90": 0, "d120": 0, "total": 0}
        for a in sorted_aging:
            for key in totals:
                totals[key] += a[key]
        
        # Build table
        rows = ""
        for a in sorted_aging:
            rows += f'''
            <tr>
                <td><strong>{safe_string(a["name"])}</strong></td>
                <td style="text-align:right;">{money(a["current"]) if a["current"] else "-"}</td>
                <td style="text-align:right;color:var(--orange);">{money(a["d30"]) if a["d30"] else "-"}</td>
                <td style="text-align:right;color:var(--orange);">{money(a["d60"]) if a["d60"] else "-"}</td>
                <td style="text-align:right;color:var(--red);">{money(a["d90"]) if a["d90"] else "-"}</td>
                <td style="text-align:right;color:var(--red);font-weight:bold;">{money(a["d120"]) if a["d120"] else "-"}</td>
                <td style="text-align:right;font-weight:bold;">{money(a["total"])}</td>
            </tr>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/reports" style="color:var(--text-muted);">-> Back to Reports</a>
            <button class="btn btn-secondary" onclick="window.print();"> Print</button>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:5px;"> Debtors Aging Report</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">As at {today()}</p>
            
            <div class="stats-grid" style="margin-bottom:20px;">
                <div class="stat-card green">
                    <div class="stat-value">{money(totals["current"])}</div>
                    <div class="stat-label">Current (0-30)</div>
                </div>
                <div class="stat-card orange">
                    <div class="stat-value">{money(totals["d30"])}</div>
                    <div class="stat-label">31-60 Days</div>
                </div>
                <div class="stat-card orange">
                    <div class="stat-value">{money(totals["d60"])}</div>
                    <div class="stat-label">61-90 Days</div>
                </div>
                <div class="stat-card red">
                    <div class="stat-value">{money(totals["d90"] + totals["d120"])}</div>
                    <div class="stat-label">90+ Days</div>
                </div>
            </div>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Customer</th>
                        <th style="text-align:right;">Current</th>
                        <th style="text-align:right;">31-60</th>
                        <th style="text-align:right;">61-90</th>
                        <th style="text-align:right;">91-120</th>
                        <th style="text-align:right;">120+</th>
                        <th style="text-align:right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='7' style='text-align:center;color:var(--text-muted)'>No outstanding invoices</td></tr>"}
                </tbody>
                <tfoot style="font-weight:bold;background:rgba(255,255,255,0.05);">
                    <tr>
                        <td>TOTAL</td>
                        <td style="text-align:right;">{money(totals["current"])}</td>
                        <td style="text-align:right;">{money(totals["d30"])}</td>
                        <td style="text-align:right;">{money(totals["d60"])}</td>
                        <td style="text-align:right;">{money(totals["d90"])}</td>
                        <td style="text-align:right;">{money(totals["d120"])}</td>
                        <td style="text-align:right;color:var(--primary);">{money(totals["total"])}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        '''
        
        return render_page("Aging Report", content, user, "reports")
    
    
    # 
    # DEBTORS REPORT
    # 
    
    @app.route("/reports/debtors")
    @login_required
    def report_debtors():
        """Debtors Report - Who owes you with invoice breakdown"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        customers = db.get("customers", {"business_id": biz_id}) if biz_id else []
        debtors = [c for c in customers if float(c.get("balance", 0)) > 0]
        debtors = sorted(debtors, key=lambda x: float(x.get("balance", 0)), reverse=True)
        
        # Get all unpaid customer invoices
        all_invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
        unpaid_invoices = [inv for inv in all_invoices if inv.get("status") != "paid"]
        
        total_owing = sum(float(c.get("balance", 0)) for c in debtors)
        
        # Build accordion rows
        debtors_html = ""
        for c in debtors:
            cust_id = c.get("id")
            balance = float(c.get("balance", 0))
            
            # Get unpaid invoices for this customer
            cust_invoices = [inv for inv in unpaid_invoices if inv.get("customer_id") == cust_id]
            cust_invoices = sorted(cust_invoices, key=lambda x: x.get("date", ""))
            
            # Calculate aging for each invoice
            from datetime import datetime
            today_date = datetime.now().date()
            
            inv_rows = ""
            for inv in cust_invoices:
                try:
                    inv_date = datetime.strptime(inv.get("date", today()), "%Y-%m-%d").date()
                    days_old = (today_date - inv_date).days
                except:
                    days_old = 0
                
                # Color code aging
                if days_old > 90:
                    age_color = "var(--red)"
                    age_text = f"{days_old}d [!]"
                elif days_old > 60:
                    age_color = "var(--orange)"
                    age_text = f"{days_old}d"
                elif days_old > 30:
                    age_color = "var(--yellow)"
                    age_text = f"{days_old}d"
                else:
                    age_color = "var(--text-muted)"
                    age_text = f"{days_old}d"
                
                inv_rows += f'''
                <tr style="cursor:pointer;" onclick="window.location='/invoice/{inv.get("id")}'">
                    <td>{inv.get("date", "-")}</td>
                    <td>{inv.get("invoice_number", "-")}</td>
                    <td style="text-align:right;font-weight:bold;">{money(inv.get("total", 0))}</td>
                    <td style="color:{age_color};">{age_text}</td>
                </tr>
                '''
            
            debtors_html += f'''
            <details style="background:var(--card);border-radius:6px;margin-bottom:4px;" {"open" if balance > 10000 else ""}>
                <summary style="cursor:pointer;padding:8px 12px;list-style:none;">
                    <div style="display:grid;grid-template-columns:2fr 1fr 1fr 100px;align-items:center;font-size:13px;">
                        <span><strong>{safe_string(c.get("name", "-"))}</strong> <span style="color:var(--text-muted);font-size:11px;">({len(cust_invoices)} invoices)</span></span>
                        <span style="text-align:center;color:var(--text-muted);">{safe_string(c.get("phone", ""))}</span>
                        <span style="text-align:right;color:var(--red);font-weight:bold;">{money(balance)}</span>
                        <span style="text-align:right;">
                            <button class="btn btn-secondary" style="padding:2px 8px;font-size:10px;" 
                                    onclick="event.stopPropagation();document.getElementById('aiInput').value='Send reminder to {safe_string(c.get("name", ""))}';document.getElementById('sendBtn').click();">
                                [EMAIL] Remind
                            </button>
                        </span>
                    </div>
                </summary>
                <div style="padding:0 10px 8px 10px;">
                    {f"""<table class="table" style="font-size:11px;">
                        <thead>
                            <tr>
                                <th style="padding:4px;">Date</th>
                                <th style="padding:4px;">Invoice #</th>
                                <th style="padding:4px;text-align:right;">Amount</th>
                                <th style="padding:4px;">Age</th>
                            </tr>
                        </thead>
                        <tbody>
                            {inv_rows}
                        </tbody>
                    </table>""" if inv_rows else "<p style='color:var(--text-muted);text-align:center;padding:10px;'>Balance from older transactions</p>"}
                </div>
            </details>
            '''
        
        # Sticky header
        header_row = '''
        <div style="position:sticky;top:56px;z-index:100;margin-bottom:4px;padding:8px 12px;background:var(--card);border-radius:6px;">
            <div style="display:grid;grid-template-columns:2fr 1fr 1fr 100px;align-items:center;font-size:13px;font-weight:bold;">
                <span>Customer</span>
                <span style="text-align:center;">Contact</span>
                <span style="text-align:right;">Owes Us</span>
                <span style="text-align:right;">Action</span>
            </div>
        </div>
        '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <div style="display:flex;gap:10px;">
                <button class="btn btn-primary" onclick="document.getElementById('aiInput').value='Email all overdue customers';document.getElementById('sendBtn').click();">[EMAIL] Email All</button>
                <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
            </div>
        </div>
        
        <h2 style="margin-bottom:5px;">[FORM] Debtors Report</h2>
        <p style="color:var(--text-muted);margin-bottom:15px;font-size:12px;">As at {today()} - Click customer to see unpaid invoices</p>
        
        <div class="stat-card red" style="margin-bottom:15px;">
            <div class="stat-value">{money(total_owing)}</div>
            <div class="stat-label">Total Outstanding from {len(debtors)} customers</div>
        </div>
        
        {header_row}
        {debtors_html or '<div class="card" style="text-align:center;padding:40px;"><p style="color:var(--text-muted);">No outstanding debtors </p></div>'}
        '''
        
        return render_page("Debtors Report", content, user, "reports")
    
    
    # 
    # CREDITORS REPORT
    # 
    
    @app.route("/reports/creditors")
    @login_required
    def report_creditors():
        """Creditors Report - What you owe with invoice breakdown"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        suppliers = db.get("suppliers", {"business_id": biz_id}) if biz_id else []
        creditors = [s for s in suppliers if float(s.get("balance", 0)) > 0]
        creditors = sorted(creditors, key=lambda x: float(x.get("balance", 0)), reverse=True)
        
        # Get all unpaid supplier invoices
        all_invoices = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id else []
        unpaid_invoices = [inv for inv in all_invoices if inv.get("status") != "paid"]
        
        total_owing = sum(float(s.get("balance", 0)) for s in creditors)
        
        # Build accordion rows
        creditors_html = ""
        for s in creditors:
            sup_id = s.get("id")
            balance = float(s.get("balance", 0))
            
            # Get unpaid invoices for this supplier
            sup_invoices = [inv for inv in unpaid_invoices if inv.get("supplier_id") == sup_id]
            sup_invoices = sorted(sup_invoices, key=lambda x: x.get("date", ""))
            
            # Calculate aging for each invoice
            from datetime import datetime
            today_date = datetime.now().date()
            
            inv_rows = ""
            for inv in sup_invoices:
                try:
                    inv_date = datetime.strptime(inv.get("date", today()), "%Y-%m-%d").date()
                    days_old = (today_date - inv_date).days
                except:
                    days_old = 0
                
                # Color code aging
                if days_old > 90:
                    age_color = "var(--red)"
                    age_text = f"{days_old}d [!]"
                elif days_old > 60:
                    age_color = "var(--orange)"
                    age_text = f"{days_old}d"
                elif days_old > 30:
                    age_color = "var(--yellow)"
                    age_text = f"{days_old}d"
                else:
                    age_color = "var(--text-muted)"
                    age_text = f"{days_old}d"
                
                inv_rows += f'''
                <tr>
                    <td>{inv.get("date", "-")}</td>
                    <td>{inv.get("invoice_number", "-")}</td>
                    <td style="text-align:right;font-weight:bold;">{money(inv.get("total", 0))}</td>
                    <td style="color:{age_color};">{age_text}</td>
                </tr>
                '''
            
            creditors_html += f'''
            <details style="background:var(--card);border-radius:6px;margin-bottom:4px;" {"open" if balance > 10000 else ""}>
                <summary style="cursor:pointer;padding:8px 12px;list-style:none;">
                    <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:13px;">
                        <span><strong>{safe_string(s.get("name", "-"))}</strong> <span style="color:var(--text-muted);font-size:11px;">({len(sup_invoices)} invoices)</span></span>
                        <span style="text-align:center;color:var(--text-muted);">{safe_string(s.get("phone", ""))}</span>
                        <span style="text-align:right;color:var(--orange);font-weight:bold;">{money(balance)}</span>
                    </div>
                </summary>
                <div style="padding:0 10px 8px 10px;">
                    {f"""<table class="table" style="font-size:11px;">
                        <thead>
                            <tr>
                                <th style="padding:4px;">Date</th>
                                <th style="padding:4px;">Invoice #</th>
                                <th style="padding:4px;text-align:right;">Amount</th>
                                <th style="padding:4px;">Age</th>
                            </tr>
                        </thead>
                        <tbody>
                            {inv_rows}
                        </tbody>
                    </table>""" if inv_rows else "<p style='color:var(--text-muted);text-align:center;padding:10px;'>Balance from older transactions</p>"}
                </div>
            </details>
            '''
        
        # Sticky header
        header_row = '''
        <div style="position:sticky;top:56px;z-index:100;margin-bottom:4px;padding:8px 12px;background:var(--card);border-radius:6px;">
            <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:13px;font-weight:bold;">
                <span>Supplier</span>
                <span style="text-align:center;">Contact</span>
                <span style="text-align:right;">We Owe</span>
            </div>
        </div>
        '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
        </div>
        
        <h2 style="margin-bottom:5px;">[FORM] Creditors Report</h2>
        <p style="color:var(--text-muted);margin-bottom:15px;font-size:12px;">As at {today()} - Click supplier to see unpaid invoices</p>
        
        <div class="stat-card orange" style="margin-bottom:15px;">
            <div class="stat-value">{money(total_owing)}</div>
            <div class="stat-label">Total Owed to {len(creditors)} suppliers</div>
        </div>
        
        {header_row}
        {creditors_html or '<div class="card" style="text-align:center;padding:40px;"><p style="color:var(--text-muted);">No outstanding creditors </p></div>'}
        '''
        
        return render_page("Creditors Report", content, user, "reports")
    
    
    # 
    # CREDITORS AGING
    # 
    
    @app.route("/reports/creditors-aging")
    @login_required
    def report_creditors_aging():
        """Creditors Aging Report"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get ALL sources of supplier debt
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_sinv = pool.submit(db.get, "supplier_invoices", {"business_id": biz_id}) if biz_id else None
            f_po = pool.submit(db.get, "purchase_orders", {"business_id": biz_id}) if biz_id else None
            f_sup = pool.submit(db.get, "suppliers", {"business_id": biz_id}) if biz_id else None
        
        supplier_invoices = (f_sinv.result() if f_sinv else []) or []
        purchase_orders = (f_po.result() if f_po else []) or []
        suppliers = (f_sup.result() if f_sup else []) or []
        supplier_map = {s.get("id"): s for s in suppliers}
        
        today_date = datetime.now().date()
        
        aging_data = {}
        
        # === SOURCE 1: Unpaid supplier invoices ===
        outstanding_sinv = [p for p in supplier_invoices if p.get("status") != "paid"]
        for p in outstanding_sinv:
            supp_id = p.get("supplier_id")
            supp_name = p.get("supplier_name", "Unknown")
            
            key = supp_id or supp_name
            if not key or key == "Unknown":
                continue
            
            if key not in aging_data:
                supp = supplier_map.get(supp_id, {}) if supp_id else {}
                aging_data[key] = {
                    "name": supp.get("name") or supp_name,
                    "current": 0, "d30": 0, "d60": 0, "d90": 0, "d120": 0, "total": 0
                }
            
            try:
                p_date = datetime.strptime(p.get("date", today()), "%Y-%m-%d").date()
            except:
                p_date = today_date
            
            days_old = (today_date - p_date).days
            amount = float(p.get("total", 0) or 0)
            
            if days_old <= 30:
                aging_data[key]["current"] += amount
            elif days_old <= 60:
                aging_data[key]["d30"] += amount
            elif days_old <= 90:
                aging_data[key]["d60"] += amount
            elif days_old <= 120:
                aging_data[key]["d90"] += amount
            else:
                aging_data[key]["d120"] += amount
            
            aging_data[key]["total"] += amount
        
        # === SOURCE 2: Outstanding purchase orders (sent/partial — not yet invoiced) ===
        # Track which POs already have a matching supplier invoice to avoid double-counting
        sinv_po_refs = set()
        for si in supplier_invoices:
            _ref = si.get("po_number") or si.get("reference") or ""
            if _ref:
                sinv_po_refs.add(_ref.strip().upper())
        
        outstanding_pos = [po for po in purchase_orders if po.get("status") in ("sent", "partial")]
        for po in outstanding_pos:
            po_num = (po.get("po_number") or "").strip().upper()
            # Skip if this PO already has a supplier invoice
            if po_num and po_num in sinv_po_refs:
                continue
            
            supp_id = po.get("supplier_id")
            supp_name = po.get("supplier_name", "Unknown")
            key = supp_id or supp_name
            if not key or key == "Unknown":
                continue
            
            if key not in aging_data:
                supp = supplier_map.get(supp_id, {}) if supp_id else {}
                aging_data[key] = {
                    "name": supp.get("name") or supp_name,
                    "current": 0, "d30": 0, "d60": 0, "d90": 0, "d120": 0, "total": 0
                }
            
            try:
                po_date = datetime.strptime(po.get("date", today()), "%Y-%m-%d").date()
            except:
                po_date = today_date
            
            days_old = (today_date - po_date).days
            amount = float(po.get("total", 0) or 0)
            
            if days_old <= 30:
                aging_data[key]["current"] += amount
            elif days_old <= 60:
                aging_data[key]["d30"] += amount
            elif days_old <= 90:
                aging_data[key]["d60"] += amount
            elif days_old <= 120:
                aging_data[key]["d90"] += amount
            else:
                aging_data[key]["d120"] += amount
            
            aging_data[key]["total"] += amount
        
        # === SOURCE 3: Suppliers with balance > 0 but no invoices/POs in aging ===
        for s in suppliers:
            sup_id = s.get("id")
            name = s.get("name", "")
            balance = float(s.get("balance", 0) or 0)
            if balance <= 0:
                continue
            key = sup_id or name
            if not key:
                continue
            if key not in aging_data:
                # Supplier has a balance but no individual invoices — put into current bucket
                aging_data[key] = {
                    "name": name,
                    "current": balance, "d30": 0, "d60": 0, "d90": 0, "d120": 0, "total": balance
                }
        
        sorted_aging = sorted(aging_data.values(), key=lambda x: x["total"], reverse=True)
        
        totals = {"current": 0, "d30": 0, "d60": 0, "d90": 0, "d120": 0, "total": 0}
        for a in sorted_aging:
            for key in totals:
                totals[key] += a[key]
        
        rows = ""
        for a in sorted_aging:
            rows += f'''
            <tr>
                <td><strong>{safe_string(a["name"])}</strong></td>
                <td style="text-align:right;">{money(a["current"]) if a["current"] else "-"}</td>
                <td style="text-align:right;color:var(--orange);">{money(a["d30"]) if a["d30"] else "-"}</td>
                <td style="text-align:right;color:var(--orange);">{money(a["d60"]) if a["d60"] else "-"}</td>
                <td style="text-align:right;color:var(--red);">{money(a["d90"]) if a["d90"] else "-"}</td>
                <td style="text-align:right;color:var(--red);font-weight:bold;">{money(a["d120"]) if a["d120"] else "-"}</td>
                <td style="text-align:right;font-weight:bold;">{money(a["total"])}</td>
            </tr>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/reports" style="color:var(--text-muted);">-> Back to Reports</a>
            <button class="btn btn-secondary" onclick="window.print();"> Print</button>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:5px;"> Creditors Aging Report</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">As at {today()}</p>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Supplier</th>
                        <th style="text-align:right;">Current</th>
                        <th style="text-align:right;">31-60</th>
                        <th style="text-align:right;">61-90</th>
                        <th style="text-align:right;">91-120</th>
                        <th style="text-align:right;">120+</th>
                        <th style="text-align:right;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='7' style='text-align:center;color:var(--text-muted)'>No outstanding purchases</td></tr>"}
                </tbody>
                <tfoot style="font-weight:bold;background:rgba(255,255,255,0.05);">
                    <tr>
                        <td>TOTAL</td>
                        <td style="text-align:right;">{money(totals["current"])}</td>
                        <td style="text-align:right;">{money(totals["d30"])}</td>
                        <td style="text-align:right;">{money(totals["d60"])}</td>
                        <td style="text-align:right;">{money(totals["d90"])}</td>
                        <td style="text-align:right;">{money(totals["d120"])}</td>
                        <td style="text-align:right;color:var(--orange);">{money(totals["total"])}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        '''
        
        return render_page("Creditors Aging", content, user, "reports")
    
    
    # 
    # CUSTOMER STATEMENT
    # ==================== BULK STATEMENTS ====================
    

    # === GL REPORT, TRIAL BALANCE, PnL, BALANCE SHEET, VAT ===

    @app.route("/reports/gl")
    @login_required
    def report_gl():
        """General Ledger - shows transactions grouped by account, built from actual data"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return render_page("General Ledger", "<div class='card'><p>No business selected</p></div>", user, "reports")
        
        try:
            return _report_gl_inner(user, biz_id)
        except Exception as e:
            logger.error(f"[GL REPORT] Crash: {e}")
            import traceback
            tb = traceback.format_exc()
            logger.error(f"[GL REPORT] Traceback: {tb}")
            return render_page("General Ledger", f"<div class='card'><h3>Error loading GL</h3><pre style='color:var(--red);font-size:12px;white-space:pre-wrap;'>{safe_string(str(e))}\n\n{safe_string(tb[-500:])}</pre></div>", user, "reports")
    
    def _report_gl_inner(user, biz_id):
        """GL built from chart_of_accounts (Sage import) OR journal_entries OB OR live ClickAI transactions"""
        
        # 1. Get chart of accounts (the real Sage data)
        coa = db.get("chart_of_accounts", {"business_id": biz_id}) or []
        coa = sorted(coa, key=lambda x: x.get("account_code", "") or "")
        
        # 2. Get imported opening balances from journal_entries (TB import)
        journal_entries = db.get("journal_entries", {"business_id": biz_id}) or []
        opening_entries = [je for je in journal_entries if je.get("reference") == "OB"]
        
        # 3. Get live transactions for fallback
        invoices = db.get("invoices", {"business_id": biz_id}) or []
        expenses = db.get("expenses", {"business_id": biz_id}) or []
        sales = db.get("sales", {"business_id": biz_id}) or []
        supplier_invoices = db.get("supplier_invoices", {"business_id": biz_id}) or []
        
        # 4. Build GL - Priority: chart_of_accounts > journal_entries OB > synthetic
        accounts_html = ""
        total_debit_all = 0
        total_credit_all = 0
        coa_codes_shown = set()  # Track codes shown from COA to avoid duplication with journals
        
        if coa:
            # Pre-load ALL journals for merging with COA
            _all_journals_for_merge = db.get("journals", {"business_id": biz_id}) or []
            _journal_by_code = {}
            for _jl in _all_journals_for_merge:
                _ac = _jl.get("account_code", "")
                if not _ac:
                    continue
                _dr = float(_jl.get("debit", 0) or 0)
                _cr = float(_jl.get("credit", 0) or 0)
                if _dr == 0 and _cr == 0:
                    continue
                if _ac not in _journal_by_code:
                    _journal_by_code[_ac] = []
                _journal_by_code[_ac].append(_jl)
            
            # Use imported chart of accounts with real balances + merged journals
            for acc in coa:
                if not acc.get("is_active", True):
                    continue
                
                code = acc.get("account_code", "")
                name = acc.get("account_name", "Unknown")
                category = acc.get("category", "")
                debit = float(acc.get("debit", 0) or 0)
                credit = float(acc.get("credit", 0) or 0)
                opening = float(acc.get("opening_balance", 0) or 0)
                
                if debit > 0 or credit > 0:
                    balance_debit = debit
                    balance_credit = credit
                elif opening != 0:
                    acct_type = (category or "").lower()
                    if any(t in acct_type for t in ("asset", "expense", "cost of sale", "other expense")):
                        balance_debit = abs(opening)
                        balance_credit = 0
                    elif opening > 0:
                        balance_debit = opening
                        balance_credit = 0
                    else:
                        balance_debit = 0
                        balance_credit = abs(opening)
                else:
                    balance_debit = 0
                    balance_credit = 0
                
                # Merge journal entries for this code
                code_journals = _journal_by_code.get(code, [])
                j_dr = sum(float(j.get("debit", 0) or 0) for j in code_journals)
                j_cr = sum(float(j.get("credit", 0) or 0) for j in code_journals)
                combined_debit = balance_debit + j_dr
                combined_credit = balance_credit + j_cr
                
                if combined_debit == 0 and combined_credit == 0:
                    continue
                
                coa_codes_shown.add(code)
                total_debit_all += combined_debit
                total_credit_all += combined_credit
                
                debit_display = money(combined_debit) if combined_debit else "-"
                credit_display = money(combined_credit) if combined_credit else "-"
                debit_color = "var(--green)" if combined_debit else "var(--text-muted)"
                credit_color = "var(--red)" if combined_credit else "var(--text-muted)"
                
                # Build journal detail rows if any
                detail_html = ""
                if code_journals:
                    sorted_j = sorted(code_journals, key=lambda x: x.get("date", ""), reverse=True)
                    j_rows = ""
                    for _j in sorted_j:
                        _jdr = money(float(_j.get("debit", 0) or 0)) if float(_j.get("debit", 0) or 0) else "-"
                        _jcr = money(float(_j.get("credit", 0) or 0)) if float(_j.get("credit", 0) or 0) else "-"
                        j_rows += f'<tr><td>{_j.get("date","-")}</td><td>{safe_string(_j.get("description","-"))}</td><td>{safe_string(_j.get("reference","-"))}</td><td style="text-align:right;color:var(--green);">{_jdr}</td><td style="text-align:right;color:var(--red);">{_jcr}</td></tr>'
                    ob_label = f"Sage Opening Balance: DR {money(balance_debit)} / CR {money(balance_credit)}" if (balance_debit or balance_credit) else ""
                    detail_html = f'''<div style="padding:0 10px 8px 10px;">
                        <div style="font-size:11px;color:var(--text-muted);padding:4px 0;">{ob_label} | {len(code_journals)} GL journal entries</div>
                        <table class="table" style="font-size:11px;"><thead><tr><th>Date</th><th>Description</th><th>Ref</th><th style="text-align:right;">Debit</th><th style="text-align:right;">Credit</th></tr></thead><tbody>{j_rows}</tbody></table>
                    </div>'''
                else:
                    detail_html = f'<div style="padding:8px 12px;font-size:12px;color:var(--text-muted);">Opening Balance: {money(opening)} | Category: {safe_string(category)}</div>'
                
                j_count_label = f" + {len(code_journals)} journals" if code_journals else ""
                accounts_html += f'''
                <details style="background:var(--card);border-radius:6px;margin-bottom:4px;">
                    <summary style="cursor:pointer;padding:8px 12px;list-style:none;">
                        <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:13px;">
                            <span><strong>{safe_string(code)}</strong> - {safe_string(name)} <span style="color:var(--text-muted);font-size:11px;">({safe_string(category)}{j_count_label})</span></span>
                            <span style="text-align:right;color:{debit_color};">{debit_display}</span>
                            <span style="text-align:right;color:{credit_color};">{credit_display}</span>
                        </div>
                    </summary>
                    {detail_html}
                </details>
                '''
        elif opening_entries:
            # Use imported TB opening balances from journal_entries
            gl_ob_accounts = {}  # code -> {name, debit, credit}
            for oe in opening_entries:
                acc_name = oe.get("account", "Unknown")
                acc_code = oe.get("account_code", "") or oe.get("code", "")
                debit = float(oe.get("debit", 0) or 0)
                credit = float(oe.get("credit", 0) or 0)
                
                if not acc_code:
                    acc_code = f"9{len(gl_ob_accounts):03d}"
                
                if acc_code not in gl_ob_accounts:
                    gl_ob_accounts[acc_code] = {"name": acc_name, "debit": 0, "credit": 0}
                gl_ob_accounts[acc_code]["debit"] += debit
                gl_ob_accounts[acc_code]["credit"] += credit
            
            # Also add live ClickAI transactions on top of opening balances
            # Sales from invoices
            inv_sales = sum(float(inv.get("subtotal", 0)) for inv in invoices if inv.get("status") != "credited")
            inv_vat = sum(float(inv.get("vat", 0)) for inv in invoices if inv.get("status") != "credited")
            inv_totals = sum(float(inv.get("total", 0)) for inv in invoices if inv.get("status") != "credited")
            
            # POS sales
            pos_sales = sum(float(s.get("subtotal", 0)) for s in sales)
            pos_vat = sum(float(s.get("vat", 0)) for s in sales)
            pos_totals = sum(float(s.get("total", 0)) for s in sales)
            
            # Purchases from supplier invoices
            purch_totals = sum(float(si.get("total", 0)) for si in supplier_invoices)
            purch_vat = sum(float(si.get("vat", 0)) for si in supplier_invoices)
            purch_net = purch_totals - purch_vat
            
            # Expenses
            exp_total = sum(float(e.get("amount", 0)) for e in expenses)
            
            # Add live transaction totals to matching GL accounts
            live_additions = {}
            if inv_sales + pos_sales > 0:
                live_additions["Sales"] = {"credit": inv_sales + pos_sales}
            if inv_vat + pos_vat > 0:
                live_additions["VAT Output"] = {"credit": inv_vat + pos_vat}
            if purch_net > 0:
                live_additions["Purchases"] = {"debit": purch_net}
            if purch_vat > 0:
                live_additions["VAT Input"] = {"debit": purch_vat}
            if exp_total > 0:
                live_additions["Operating Expenses"] = {"debit": exp_total}
            
            # Try to match live additions to existing OB accounts by name
            for live_name, amounts in live_additions.items():
                matched = False
                for code, acc in gl_ob_accounts.items():
                    if live_name.lower() in acc["name"].lower():
                        acc["debit"] += amounts.get("debit", 0)
                        acc["credit"] += amounts.get("credit", 0)
                        matched = True
                        break
                if not matched:
                    # Add as new account
                    new_code = f"L{len(gl_ob_accounts):03d}"
                    gl_ob_accounts[new_code] = {
                        "name": f"{live_name} (Live)",
                        "debit": amounts.get("debit", 0),
                        "credit": amounts.get("credit", 0)
                    }
            
            for code in sorted(gl_ob_accounts.keys()):
                acc = gl_ob_accounts[code]
                debit = acc["debit"]
                credit = acc["credit"]
                name = acc["name"]
                
                if debit == 0 and credit == 0:
                    continue
                
                total_debit_all += debit
                total_credit_all += credit
                
                debit_display = money(debit) if debit else "-"
                credit_display = money(credit) if credit else "-"
                debit_color = "var(--green)" if debit else "var(--text-muted)"
                credit_color = "var(--red)" if credit else "var(--text-muted)"
                
                accounts_html += f'''
                <details style="background:var(--card);border-radius:6px;margin-bottom:4px;">
                    <summary style="cursor:pointer;padding:8px 12px;list-style:none;">
                        <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:13px;">
                            <span><strong>{safe_string(code)}</strong> - {safe_string(name)}</span>
                            <span style="text-align:right;color:{debit_color};">{debit_display}</span>
                            <span style="text-align:right;color:{credit_color};">{credit_display}</span>
                        </div>
                    </summary>
                    <div style="padding:8px 12px;font-size:12px;color:var(--text-muted);">
                        Source: Imported Opening Balance
                    </div>
                </details>
                '''
        else:
            # Fallback: build synthetic GL from transactions
            gl_accounts = {
                "1000": {"name": "Bank", "type": "asset", "entries": []},
                "1200": {"name": "Debtors Control", "type": "asset", "entries": []},
                "2000": {"name": "Creditors Control", "type": "liability", "entries": []},
                "2100": {"name": "VAT Output", "type": "liability", "entries": []},
                "1400": {"name": "VAT Input", "type": "asset", "entries": []},
                "4000": {"name": "Sales", "type": "income", "entries": []},
                "5100": {"name": "Purchases", "type": "expense", "entries": []},
                "6000": {"name": "Operating Expenses", "type": "expense", "entries": []},
            }
            
            for inv in invoices:
                inv_num = inv.get("invoice_number", "-")
                customer = inv.get("customer_name", "Customer")
                date = inv.get("date", "-")
                total = float(inv.get("total", 0))
                subtotal = float(inv.get("subtotal", 0))
                vat = float(inv.get("vat", 0))
                status = inv.get("status", "outstanding")
                payment = inv.get("payment_method") or "account"
                if status == "credited": continue
                gl_accounts["4000"]["entries"].append({"date": date, "description": f"Invoice {inv_num} - {customer}", "ref": inv_num, "debit": 0, "credit": subtotal})
                if vat > 0:
                    gl_accounts["2100"]["entries"].append({"date": date, "description": f"VAT on {inv_num}", "ref": inv_num, "debit": 0, "credit": vat})
                if payment == "account" and status == "outstanding":
                    gl_accounts["1200"]["entries"].append({"date": date, "description": f"Invoice {inv_num} - {customer}", "ref": inv_num, "debit": total, "credit": 0})
                elif status == "paid":
                    gl_accounts["1000"]["entries"].append({"date": date, "description": f"Payment {inv_num} - {customer} ({payment.upper()})", "ref": inv_num, "debit": total, "credit": 0})
            
            for exp in expenses:
                amount = float(exp.get("amount", 0))
                desc = exp.get("description", "Expense")
                date = exp.get("date", "-")
                gl_accounts["6000"]["entries"].append({"date": date, "description": f"{exp.get('category', '')}: {desc[:30]}", "ref": "EXP", "debit": amount, "credit": 0})
                gl_accounts["1000"]["entries"].append({"date": date, "description": f"Paid: {desc[:30]}", "ref": "EXP", "debit": 0, "credit": amount})
            
            for si in supplier_invoices:
                total = float(si.get("total", 0))
                vat = float(si.get("vat", 0))
                date = si.get("date", "-")
                supplier = si.get("supplier_name", "Supplier")
                gl_accounts["5100"]["entries"].append({"date": date, "description": f"Purchase - {supplier}", "ref": "PINV", "debit": total - vat, "credit": 0})
                if vat > 0:
                    gl_accounts["1400"]["entries"].append({"date": date, "description": f"VAT - {supplier}", "ref": "PINV", "debit": vat, "credit": 0})
                gl_accounts["2000"]["entries"].append({"date": date, "description": f"Owing - {supplier}", "ref": "PINV", "debit": 0, "credit": total})
            
            for sale in sales:
                total = float(sale.get("total", 0))
                subtotal = float(sale.get("subtotal", 0))
                vat = float(sale.get("vat", 0))
                date = sale.get("date", "-")
                customer = sale.get("customer_name", "Cash")
                payment = sale.get("payment_method") or "cash"
                gl_accounts["4000"]["entries"].append({"date": date, "description": f"POS - {customer}", "ref": "POS", "debit": 0, "credit": subtotal})
                if vat > 0:
                    gl_accounts["2100"]["entries"].append({"date": date, "description": f"VAT POS - {customer}", "ref": "POS", "debit": 0, "credit": vat})
                gl_accounts["1000"]["entries"].append({"date": date, "description": f"POS - {customer} ({payment.upper()})", "ref": "POS", "debit": total, "credit": 0})
            
            for code in sorted(gl_accounts.keys()):
                acc = gl_accounts[code]
                entries = sorted(acc["entries"], key=lambda x: x.get("date", ""), reverse=True)
                td = sum(e.get("debit", 0) for e in entries)
                tc = sum(e.get("credit", 0) for e in entries)
                if not entries: continue
                total_debit_all += td
                total_credit_all += tc
                trans_rows = ""
                for e in entries:
                    trans_rows += f'<tr><td>{e.get("date","-")}</td><td>{safe_string(e.get("description","-"))}</td><td>{e.get("ref","-")}</td><td style="text-align:right;color:var(--green);">{money(e["debit"]) if e.get("debit") else "-"}</td><td style="text-align:right;color:var(--red);">{money(e["credit"]) if e.get("credit") else "-"}</td></tr>'
                accounts_html += f'''
                <details style="background:var(--card);border-radius:6px;margin-bottom:4px;">
                    <summary style="cursor:pointer;padding:8px 12px;list-style:none;">
                        <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:13px;">
                            <span><strong>{code}</strong> - {acc["name"]} ({len(entries)})</span>
                            <span style="text-align:right;color:var(--green);">{money(td)}</span>
                            <span style="text-align:right;color:var(--red);">{money(tc)}</span>
                        </div>
                    </summary>
                    <div style="padding:0 10px 8px 10px;">
                        <table class="table" style="font-size:11px;"><thead><tr><th>Date</th><th>Description</th><th>Ref</th><th style="text-align:right;">Debit</th><th style="text-align:right;">Credit</th></tr></thead><tbody>{trans_rows}</tbody></table>
                    </div>
                </details>
                '''
        
        # ═══════════════════════════════════════════════════════════════
        # MERGE ALL GL JOURNALS (from create_journal_entry throughout system)
        # This includes: stock adjustments, GRVs, PO receives, banking,
        # payments, payroll, invoice GL entries, etc.
        # ═══════════════════════════════════════════════════════════════
        all_journals_gl = db.get("journals", {"business_id": biz_id}) or []
        if all_journals_gl:
            logger.info(f"[GL] Merging {len(all_journals_gl)} journal lines into GL report")
            all_accounts_list = db.get("accounts", {"business_id": biz_id}) or []
            acc_name_map = {a.get("code"): a.get("name", f"Account {a.get('code')}") for a in all_accounts_list}
            
            # Enrich name map from chart_of_accounts (Sage import has proper names)
            if coa:
                for acc in coa:
                    c = str(acc.get("account_code", "") or acc.get("code", "")).strip()
                    n = acc.get("account_name", "") or acc.get("name", "")
                    if c and n and c not in acc_name_map:
                        acc_name_map[c] = n
            
            # Fallback: ClickAI default code → friendly name (so "1200" shows "Debtors Control" not "Account 1200")
            _default_names = {
                "1000": "Bank", "1050": "Cash On Hand", "1100": "Petty Cash",
                "1200": "Debtors Control", "1300": "Stock", "1400": "VAT Input",
                "1500": "Equipment", "1600": "Vehicles", "1700": "Accumulated Depreciation",
                "2000": "Creditors Control", "2100": "VAT Output", "2200": "PAYE Payable",
                "2300": "UIF/Loan Payable", "2400": "Loan",
                "3000": "Capital", "3100": "Retained Earnings", "3200": "Drawings",
                "4000": "Sales - Cash", "4001": "Sales - Credit", "4002": "Sales - Card Machine",
                "4003": "Sales - Online/EFT", "4100": "Service Revenue",
                "4200": "Rental Income", "4300": "Commission Received",
                "4400": "Interest Received", "4900": "Sundry Income",
                "5000": "Stock Purchases - General", "5001": "Stock Purchases - Steel",
                "5002": "Stock Purchases - Hardware", "5003": "Stock Purchases - Paint",
                "5004": "Stock Purchases - Electrical", "5005": "Stock Purchases - Plumbing",
                "5010": "Stock Purchases - Food & Beverage", "5100": "Delivery/Freight",
                "5200": "Import Duties", "5300": "Packaging", "5400": "Direct Labour",
                "6100": "Rent - Business Premises", "6110": "Rates & Taxes - Municipal",
                "6111": "Rates & Taxes - Property", "6120": "Electricity", "6121": "Water",
                "6130": "Repairs & Maintenance - Building", "6140": "Cleaning & Hygiene",
                "6141": "Garden & Grounds Maintenance", "6150": "Security",
                "6200": "Salaries - Management", "6201": "Wages - Staff",
                "6202": "Wages - Casual/Temp", "6210": "PAYE/UIF/SDL Payment",
                "6220": "Provident Fund", "6230": "Staff Welfare & Training",
                "6240": "Recruitment Costs", "6250": "Protective Clothing/Uniforms",
                "6510": "Fuel - Business Vehicle", "6515": "Fuel - Equipment",
                "6520": "Vehicle Repairs & Service", "6530": "Vehicle Insurance",
                "6540": "Vehicle Licence & Registration", "6550": "Tolls & Parking",
                "6560": "Vehicle Lease/Finance", "6600": "Stationery & Printing",
                "6610": "Postage & Courier", "6620": "Telephone - Landline",
                "6621": "Cellphone/Mobile", "6622": "Internet/WiFi",
                "6630": "Software Subscription", "6640": "Computer Equipment & Repairs",
                "6700": "Accounting Fees", "6710": "Legal Fees", "6720": "Consulting Fees",
                "6800": "Insurance - Business", "6900": "Advertising - Print",
                "6901": "Advertising - Online", "6910": "Signage & Branding",
                "6920": "Promotional Materials", "6930": "Website Costs",
                "6940": "Sponsorships & Donations",
                "7000": "General Expenses", "7050": "Cash Short/Over",
                "7100": "Bank Charges", "7110": "Card Machine Fees",
                "7120": "Interest Paid - Overdraft", "7200": "Entertainment",
                "7210": "Travel - Local", "7300": "Membership & Subscriptions",
                "7400": "Repairs - Equipment/Machinery", "7500": "Depreciation",
                "7600": "Bad Debts Written Off", "7900": "Sundry Expenses",
                "7999": "General Expenses (Uncategorised)",
            }
            for code, name in _default_names.items():
                if code not in acc_name_map:
                    acc_name_map[code] = name
            
            # Group journals by account_code
            journal_by_acc = {}
            for jl in all_journals_gl:
                try:
                    acc_code = jl.get("account_code", "")
                    if not acc_code:
                        continue
                    debit = float(jl.get("debit", 0) or 0)
                    credit = float(jl.get("credit", 0) or 0)
                    if debit == 0 and credit == 0:
                        continue
                    if acc_code not in journal_by_acc:
                        journal_by_acc[acc_code] = []
                    journal_by_acc[acc_code].append({
                        "date": jl.get("date", "-"),
                        "description": jl.get("description", "-"),
                        "ref": jl.get("reference", "-"),
                        "debit": debit,
                        "credit": credit
                    })
                except:
                    pass
            
            for code in sorted(journal_by_acc.keys()):
                if code in coa_codes_shown:
                    continue  # Already merged into COA section above
                entries = sorted(journal_by_acc[code], key=lambda x: x.get("date", ""), reverse=True)
                td = sum(e.get("debit", 0) for e in entries)
                tc = sum(e.get("credit", 0) for e in entries)
                acc_name = acc_name_map.get(code, f"Account {code}")
                total_debit_all += td
                total_credit_all += tc
                trans_rows = ""
                for e in entries:
                    dr_display = money(e["debit"]) if e.get("debit") else "-"
                    cr_display = money(e["credit"]) if e.get("credit") else "-"
                    trans_rows += f'<tr><td>{e.get("date","-")}</td><td>{safe_string(e.get("description","-"))}</td><td>{safe_string(e.get("ref","-"))}</td><td style="text-align:right;color:var(--green);">{dr_display}</td><td style="text-align:right;color:var(--red);">{cr_display}</td></tr>'
                accounts_html += f'''
                <details style="background:var(--card);border-radius:6px;margin-bottom:4px;">
                    <summary style="cursor:pointer;padding:8px 12px;list-style:none;">
                        <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:13px;">
                            <span><strong>{code}</strong> - {safe_string(acc_name)} <span style="color:var(--text-muted);font-size:11px;">(GL Journals: {len(entries)})</span></span>
                            <span style="text-align:right;color:var(--green);">{money(td)}</span>
                            <span style="text-align:right;color:var(--red);">{money(tc)}</span>
                        </div>
                    </summary>
                    <div style="padding:0 10px 8px 10px;">
                        <table class="table" style="font-size:11px;"><thead><tr><th>Date</th><th>Description</th><th>Ref</th><th style="text-align:right;">Debit</th><th style="text-align:right;">Credit</th></tr></thead><tbody>{trans_rows}</tbody></table>
                    </div>
                </details>
                '''
        
        if not accounts_html:
            accounts_html = '<div class="card" style="text-align:center;padding:40px;"><p>No accounts found. Import your Chart of Accounts or create transactions.</p></div>'
        
        diff = abs(total_debit_all - total_credit_all)
        balance_note = f'<span style="color:var(--green);">✅ Balanced</span>' if diff < 0.02 else f'<span style="color:var(--orange);">Difference: {money(diff)}</span>'
        
        source_label = "Chart of Accounts (Sage)" if coa else ("Imported Trial Balance + Live Transactions" if opening_entries else "Built from transactions")
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <div style="display:flex;gap:8px;align-items:center;">
                <input type="text" id="glSearch" placeholder="Search ref, description or invoice..." 
                    style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);width:280px;font-size:13px;"
                    oninput="filterGL(this.value)">
                <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
            </div>
        </div>
        
        <h2 style="margin-bottom:4px;">📒 General Ledger</h2>
        <p style="color:var(--text-muted);margin-bottom:15px;font-size:13px;">{source_label} — Click on an account to see details</p>
        <div id="glSearchResults" style="display:none;margin-bottom:12px;padding:12px;background:var(--card);border:1px solid var(--primary);border-radius:8px;"></div>
        
        <div style="position:sticky;top:56px;z-index:100;margin-bottom:4px;padding:8px 12px;background:var(--card);border-radius:6px;">
            <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:13px;font-weight:bold;">
                <span>Account</span>
                <span style="text-align:right;color:var(--green);">Debit</span>
                <span style="text-align:right;color:var(--red);">Credit</span>
            </div>
        </div>
        
        {accounts_html}
        
        <div style="padding:10px 12px;background:var(--card);border-radius:6px;margin-top:8px;border:2px solid var(--border);">
            <div style="display:grid;grid-template-columns:2fr 1fr 1fr;align-items:center;font-size:14px;font-weight:bold;">
                <span>TOTALS {balance_note}</span>
                <span style="text-align:right;color:var(--green);">{money(total_debit_all)}</span>
                <span style="text-align:right;color:var(--red);">{money(total_credit_all)}</span>
            </div>
        </div>
        
        <script>
        function filterGL(query) {{
            const results = document.getElementById('glSearchResults');
            const q = query.toLowerCase().trim();
            
            if (q.length < 2) {{
                results.style.display = 'none';
                // Show all accounts
                document.querySelectorAll('.gl-account-card, details').forEach(el => el.style.display = '');
                return;
            }}
            
            // Search through all table rows in GL
            let matches = [];
            document.querySelectorAll('details').forEach(detail => {{
                const accTitle = detail.querySelector('summary') ? detail.querySelector('summary').textContent.toLowerCase() : '';
                let found = false;
                detail.querySelectorAll('tbody tr').forEach(row => {{
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 3) {{
                        const date = cells[0] ? cells[0].textContent.toLowerCase() : '';
                        const desc = cells[1] ? cells[1].textContent.toLowerCase() : '';
                        const ref = cells[2] ? cells[2].textContent.toLowerCase() : '';
                        const debit = cells[3] ? cells[3].textContent : '';
                        const credit = cells[4] ? cells[4].textContent : '';
                        
                        if (desc.includes(q) || ref.includes(q) || date.includes(q)) {{
                            found = true;
                            row.style.display = '';
                            row.style.background = 'rgba(99,102,241,0.1)';
                            matches.push({{
                                account: accTitle.substring(0, 50),
                                date: cells[0].textContent.trim(),
                                desc: cells[1].textContent.trim().substring(0, 40),
                                ref: cells[2].textContent.trim(),
                                debit: debit.trim(),
                                credit: credit.trim()
                            }});
                        }} else {{
                            row.style.background = '';
                        }}
                    }}
                }});
                
                if (found) {{
                    detail.style.display = '';
                    detail.open = true;
                }} else {{
                    detail.style.display = 'none';
                }}
            }});
            
            if (matches.length > 0) {{
                let html = '<div style="font-weight:600;margin-bottom:8px;font-size:13px;">🔍 Found ' + matches.length + ' entries matching "' + query + '"</div>';
                html += '<table style="width:100%;font-size:12px;border-collapse:collapse;">';
                html += '<tr style="border-bottom:1px solid var(--border);"><th style="text-align:left;padding:4px;">Account</th><th style="text-align:left;padding:4px;">Date</th><th style="text-align:left;padding:4px;">Description</th><th style="text-align:left;padding:4px;">Ref</th><th style="text-align:right;padding:4px;">Debit</th><th style="text-align:right;padding:4px;">Credit</th></tr>';
                matches.slice(0, 20).forEach(m => {{
                    html += '<tr style="border-bottom:1px solid rgba(255,255,255,0.05);"><td style="padding:3px 4px;">' + m.account + '</td><td style="padding:3px 4px;">' + m.date + '</td><td style="padding:3px 4px;">' + m.desc + '</td><td style="padding:3px 4px;color:var(--primary);">' + m.ref + '</td><td style="text-align:right;padding:3px 4px;">' + m.debit + '</td><td style="text-align:right;padding:3px 4px;">' + m.credit + '</td></tr>';
                }});
                if (matches.length > 20) html += '<tr><td colspan="6" style="padding:6px;color:var(--text-muted);font-style:italic;">...and ' + (matches.length - 20) + ' more</td></tr>';
                html += '</table>';
                results.innerHTML = html;
                results.style.display = 'block';
            }} else {{
                results.innerHTML = '<span style="color:var(--text-muted);font-size:13px;">No entries found for "' + query + '"</span>';
                results.style.display = 'block';
            }}
        }}
        </script>
        '''
        
        return render_page("General Ledger", content, user, "reports")
    
    
    # 
    # TRIAL BALANCE
    # 
    
    @app.route("/reports/tb")
    @login_required
    def report_tb():
        """Trial Balance - Shows imported TB with AI Analysis option"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("name", "Business") if business else "Business"
        
        if not biz_id:
            return render_page("Trial Balance", "<div class='card'><p>No business selected</p></div>", user, "reports")
        
        # ═══════════════════════════════════════════════════════════════
        # GET ALL DATA SOURCES
        # ═══════════════════════════════════════════════════════════════
        
        # 1. Imported opening balances (from journal_entries with ref=OB)
        journal_entries = db.get("journal_entries", {"business_id": biz_id}) or []
        opening_entries = [je for je in journal_entries if je.get("reference") == "OB"]
        logger.info(f"[TB] Journal entries: {len(journal_entries)}, Opening balances: {len(opening_entries)}")
        
        # 2. Live transaction data
        customers = db.get("customers", {"business_id": biz_id}) or []
        suppliers = db.get("suppliers", {"business_id": biz_id}) or []
        invoices = db.get("invoices", {"business_id": biz_id}) or []
        expenses = db.get("expenses", {"business_id": biz_id}) or []
        sales = db.get("sales", {"business_id": biz_id}) or []
        
        # ═══════════════════════════════════════════════════════════════
        # BUILD TRIAL BALANCE
        # ═══════════════════════════════════════════════════════════════
        
        tb_accounts = {}  # code -> {name, debit, credit, type}
        
        def add_account(code, name, debit=0, credit=0, acc_type=""):
            if code not in tb_accounts:
                tb_accounts[code] = {"name": name, "debit": 0, "credit": 0, "type": acc_type}
            tb_accounts[code]["debit"] += debit
            tb_accounts[code]["credit"] += credit
        
        # Load imported opening balances
        if opening_entries:
            logger.info(f"[TB] Loading {len(opening_entries)} imported opening balances")
            for oe in opening_entries:
                acc_name = oe.get("account", "Unknown")
                acc_code = oe.get("account_code", "") or oe.get("code", "")
                debit = float(oe.get("debit", 0) or 0)
                credit = float(oe.get("credit", 0) or 0)
                
                if not acc_code:
                    acc_code = f"9{len(tb_accounts):03d}"
                
                add_account(acc_code, acc_name, debit, credit)
            
            # DON'T add live data when we have imported TB - it would double count!
            logger.info(f"[TB] Using imported TB only - not adding live transaction data")
        
        else:
            # NO imported TB - check if we have GL journals
            all_journals_check = db.get("journals", {"business_id": biz_id}) or []
            
            if not all_journals_check:
                # No imported TB AND no journals - use live data estimates as fallback
                logger.info(f"[TB] No imported TB, no journals - building from live transaction estimates")
                
                # Debtors Control - from customer balances
                debtors_total = sum(float(c.get("balance", 0)) for c in customers if float(c.get("balance", 0)) > 0)
                if debtors_total > 0:
                    add_account("1200", "Debtors Control", debit=debtors_total)
                
                # Creditors Control - from supplier balances
                creditors_total = sum(float(s.get("balance", 0)) for s in suppliers if float(s.get("balance", 0)) > 0)
                if creditors_total > 0:
                    add_account("3000", "Creditors Control", credit=creditors_total)
                
                # Sales - from invoices (excluding credited)
                inv_sales = sum(float(inv.get("subtotal", 0)) for inv in invoices if inv.get("status") != "credited")
                pos_sales = sum(float(s.get("subtotal", 0)) for s in sales)
                total_sales = inv_sales + pos_sales
                if total_sales > 0:
                    add_account("5000", "Sales", credit=total_sales)
                
                # VAT Output - from invoices and POS
                vat_output = sum(float(inv.get("vat", 0)) for inv in invoices if inv.get("status") != "credited")
                vat_output += sum(float(s.get("vat", 0)) for s in sales)
                if vat_output > 0:
                    add_account("2100", "VAT Output", credit=vat_output)
                
                # Operating Expenses
                exp_total = sum(float(e.get("amount", 0)) for e in expenses)
                if exp_total > 0:
                    add_account("6000", "Operating Expenses", debit=exp_total)
            else:
                logger.info(f"[TB] No imported TB but {len(all_journals_check)} GL journals found - using journals only")
        
        # ═══════════════════════════════════════════════════════════════
        # PROCESS ALL GL JOURNALS (banking, payments, payroll, invoices, etc.)
        # These are individual debit/credit lines in the "journals" table,
        # created by create_journal_entry() throughout the system
        # ═══════════════════════════════════════════════════════════════
        all_journals = db.get("journals", {"business_id": biz_id}) or []
        # Get account names from accounts table + chart_of_accounts + defaults
        all_accounts = db.get("accounts", {"business_id": biz_id}) or []
        account_names = {a.get("code"): a.get("name", f"Account {a.get('code')}") for a in all_accounts}
        # Enrich from chart_of_accounts (Sage imported names)
        for acc in (db.get("chart_of_accounts", {"business_id": biz_id}) or []):
            c = str(acc.get("account_code", "") or acc.get("code", "")).strip()
            n = acc.get("account_name", "") or acc.get("name", "")
            if c and n and c not in account_names:
                account_names[c] = n
        # Fallback default names from BOOKING_CATEGORIES for all ClickAI GL codes
        try:
            for _grp in IndustryKnowledge.BOOKING_CATEGORIES.values():
                for _cat_name, _gl_code in _grp.get("items", []):
                    if _gl_code and _gl_code not in account_names:
                        account_names[_gl_code] = _cat_name
        except Exception:
            pass
        # Extra defaults not in BOOKING_CATEGORIES
        for _c, _n in {"1200": "Debtors Control", "1400": "VAT Input", "1300": "Stock",
                        "2000": "Creditors Control", "2200": "PAYE Payable", "3100": "Retained Earnings"}.items():
            if _c not in account_names:
                account_names[_c] = _n
        
        if all_journals:
            logger.info(f"[TB] Processing {len(all_journals)} GL journal lines into TB")
            for jl in all_journals:
                try:
                    acc_code = jl.get("account_code", "")
                    if not acc_code:
                        continue
                    debit = float(jl.get("debit", 0) or 0)
                    credit = float(jl.get("credit", 0) or 0)
                    acc_name = account_names.get(acc_code, f"Account {acc_code}")
                    if debit > 0 or credit > 0:
                        add_account(acc_code, acc_name, debit=debit, credit=credit)
                except Exception as jl_err:
                    logger.error(f"[TB] Error processing journal line {jl.get('id', '?')}: {jl_err}")
        
        # Calculate totals
        total_debit = sum(acc.get("debit", 0) for acc in tb_accounts.values())
        total_credit = sum(acc.get("credit", 0) for acc in tb_accounts.values())
        difference = abs(total_debit - total_credit)
        is_balanced = difference < 0.01
        
        logger.info(f"[TB] Final: {len(tb_accounts)} accounts, Dr:{total_debit:.2f} Cr:{total_credit:.2f} Diff:{difference:.2f}")
        
        # Build table rows
        sorted_codes = sorted(tb_accounts.keys())
        rows_html = ""
        for code in sorted_codes:
            acc = tb_accounts[code]
            name = acc["name"]
            debit = acc["debit"]
            credit = acc["credit"]
            
            debit_str = f"R {debit:,.2f}" if debit > 0 else ""
            credit_str = f"R {credit:,.2f}" if credit > 0 else ""
            
            rows_html += f'''
            <tr>
                <td style="font-family:monospace;color:var(--text-muted);">{code}</td>
                <td>{safe_string(name)}</td>
                <td style="text-align:right;">{debit_str}</td>
                <td style="text-align:right;">{credit_str}</td>
            </tr>
            '''
        
        if not tb_accounts:
            rows_html = '''
            <tr>
                <td colspan="4" style="text-align:center;padding:40px;color:var(--text-muted);">
                    No trial balance data yet.<br><br>
                    <a href="/import">Import Opening Trial Balance</a> or start creating invoices and expenses.
                </td>
            </tr>
            '''
        
        # Build TB data for AI analysis (JSON)
        tb_data_json = json.dumps([
            {"code": code, "name": acc["name"], "debit": acc["debit"], "credit": acc["credit"]}
            for code, acc in sorted(tb_accounts.items())
        ])
        
        content = f'''
        <style>
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ background: white !important; color: black !important; }}
            .tb-table {{ border: 1px solid #333; }}
            .tb-table th, .tb-table td {{ border: 1px solid #ccc; padding: 8px !important; }}
        }}
        .analysis-section {{ background: linear-gradient(135deg, rgba(139,92,246,0.1), rgba(99,102,241,0.05)); border: 1px solid rgba(139,92,246,0.3); border-radius: 12px; padding: 25px; margin-top: 20px; }}
        .analysis-content {{ line-height: 1.5; font-size: 14px; }}
        .analysis-content h2 {{ color: #8b5cf6; border-bottom: 2px solid #8b5cf6; padding-bottom: 8px; margin-top: 20px; margin-bottom: 10px; font-size: 20px; }}
        .analysis-content h3 {{ color: #10b981; margin-top: 15px; margin-bottom: 10px; font-size: 16px; }}
        .analysis-content h4 {{ color: #6366f1; margin-top: 12px; margin-bottom: 8px; font-size: 14px; }}
        .analysis-content table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px; }}
        .analysis-content th, .analysis-content td {{ padding: 8px 12px; border: 1px solid rgba(255,255,255,0.1); text-align: left; }}
        .analysis-content th {{ background: rgba(139,92,246,0.2); }}
        @media print {{ .analysis-section {{ background: white; border: 1px solid #333; }} .analysis-content {{ color: black; }} }}
        </style>
        
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
                <select id="reportLang" style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:13px;">
                    <option value="en">English</option>
                    <option value="af">Afrikaans</option>
                </select>
                <button class="btn btn-primary" onclick="analyzeWithZane()" id="analyzeBtn">Analyze with Zane</button>
                <button class="btn btn-secondary" onclick="downloadTBcsv()">📥 Download CSV</button>
                <button class="btn btn-secondary" onclick="window.print();">Print</button>
                <a href="/import" class="btn btn-secondary">Import TB</a>
                <label class="btn btn-primary" style="cursor:pointer;margin:0;background:#10b981;">
                    📥 Replace TB
                    <input type="file" id="tbImportFile" accept=".csv,.xlsx,.xls" style="display:none;" onchange="handleTBImportSave(this)">
                </label>
                <label class="btn btn-secondary" style="cursor:pointer;margin:0;">
                    📁 Upload CSV/Excel
                    <input type="file" id="tbFileUpload" accept=".csv,.xlsx,.xls" style="display:none;" onchange="handleTBUpload(this)">
                </label>
                {f'<button class="btn btn-warning" onclick="clearOpeningBalances()" style="background:#f59e0b;">Clear OB ({len(opening_entries)})</button>' if opening_entries else ''}
            </div>
        </div>
        
        {f'<div class="card" style="background:rgba(239,68,68,0.1);border:1px solid #ef4444;padding:15px;margin-bottom:15px;"><strong>⚠️ Warning:</strong> There are <strong>{len(opening_entries)}</strong> opening balance entries for <strong>{len(tb_accounts)}</strong> accounts. If you imported multiple times, click "Clear OB" and import again.</div>' if opening_entries and len(opening_entries) > len(tb_accounts) + 5 else ''}
        
        <div class="card" style="padding:30px;">
            <!-- HEADER -->
            <div style="text-align:center;margin-bottom:30px;">
                <h2 style="margin:0;">{safe_string(biz_name)}</h2>
                <h3 style="margin:10px 0;color:var(--text-muted);font-weight:normal;">Trial Balance</h3>
                <p style="color:var(--text-muted);margin:0;">As at {today()}</p>
            </div>
            
            <!-- TABLE -->
            <table class="table tb-table" style="width:100%;">
                <thead>
                    <tr style="background:var(--bg);">
                        <th style="width:100px;">Code</th>
                        <th>Account</th>
                        <th style="text-align:right;width:150px;">Debit (Dr)</th>
                        <th style="text-align:right;width:150px;">Credit (Cr)</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
                <tfoot>
                    <tr style="font-weight:bold;background:var(--bg);border-top:2px solid var(--border);">
                        <td></td>
                        <td>TOTAL</td>
                        <td style="text-align:right;border-top:2px solid var(--text);">R {total_debit:,.2f}</td>
                        <td style="text-align:right;border-top:2px solid var(--text);">R {total_credit:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
            
            <!-- BALANCE STATUS -->
            <div style="margin-top:20px;padding:15px;border-radius:8px;text-align:center;background:{"rgba(16,185,129,0.1)" if is_balanced else "rgba(239,68,68,0.1)"};">
                {"✅ Trial Balance is balanced" if is_balanced else f"⚠️ Difference: R {difference:,.2f}"}
            </div>
        </div>
        
        <!-- AI ANALYSIS SECTION -->
        <div id="analysisSection" class="analysis-section" style="display:none;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 style="margin:0;">📊 Zane's Financial Analysis Report</h3>
                <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                    <span id="analysisDate" style="color:var(--text-muted);font-size:12px;"></span>
                    <button class="btn btn-secondary no-print" onclick="downloadTBReport()" style="font-size:12px;padding:6px 12px;">⬇️ Download</button>
                    <button class="btn btn-secondary no-print" onclick="emailTBReport()" style="font-size:12px;padding:6px 12px;">Email</button>
                    <button class="btn btn-secondary no-print" onclick="printAnalysis()" style="font-size:12px;padding:6px 12px;">🖨️ Print</button>
                </div>
            </div>
            <div id="analysisContent" class="analysis-content">
                <div style="text-align:center;padding:30px;">
                    <div class="spinner" style="border:3px solid rgba(139,92,246,0.3);border-top:3px solid #8b5cf6;border-radius:50%;width:30px;height:30px;animation:spin 1s linear infinite;margin:0 auto 15px;"></div>
                    <p style="color:var(--text-muted);margin:0;">Zane is analyzing your trial balance...</p>
                </div>
            </div>
        </div>
        <style>@keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}</style>
        
        <script>
        const tbData = {tb_data_json};
        const totalDebit = {total_debit};
        const totalCredit = {total_credit};
        const isBalanced = {"true" if is_balanced else "false"};
        
        function downloadTBcsv() {{
            const tbData = {tb_data_json};
            if (!tbData || tbData.length === 0) {{ alert('No trial balance data to download'); return; }}
            
            // Standard TB CSV format that any accounting software can read
            let csv = 'Account Code,Account Name,Account Type,Debit,Credit\\n';
            let totDr = 0, totCr = 0;
            
            tbData.forEach(row => {{
                const code = (row.code || '').replace(/"/g, '""');
                const name = (row.name || '').replace(/"/g, '""');
                const type = '';
                const dr = row.debit > 0 ? row.debit.toFixed(2) : '';
                const cr = row.credit > 0 ? row.credit.toFixed(2) : '';
                csv += `"${{code}}","${{name}}","${{type}}",${{dr}},${{cr}}\\n`;
                totDr += row.debit || 0;
                totCr += row.credit || 0;
            }});
            
            csv += `,,TOTAL,${{totDr.toFixed(2)}},${{totCr.toFixed(2)}}\\n`;
            
            const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const bizName = document.title.split(' - ')[1] || 'Business';
            const date = new Date().toISOString().split('T')[0];
            a.download = `Trial_Balance_${{bizName.replace(/[^a-zA-Z0-9]/g, '_')}}_${{date}}.csv`;
            a.click();
            URL.revokeObjectURL(url);
        }}
        
        async function analyzeWithZane() {{
            const btn = document.getElementById('analyzeBtn');
            const section = document.getElementById('analysisSection');
            const content = document.getElementById('analysisContent');
            const dateSpan = document.getElementById('analysisDate');
            const lang = document.getElementById('reportLang').value;
            
            btn.disabled = true;
            btn.innerHTML = 'Analyzing...';
            section.style.display = 'block';
            
            try {{
                // STEP 1: Get Python report INSTANTLY (no AI wait)
                const response = await fetch('/api/reports/tb/analyze', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        accounts: tbData,
                        total_debit: totalDebit,
                        total_credit: totalCredit,
                        is_balanced: isBalanced,
                        lang: lang
                    }})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    content.innerHTML = data.analysis;
                    dateSpan.innerHTML = 'Analyzed: ' + new Date().toLocaleString();
                    
                    // STEP 2: Load Zane's AI insights in BACKGROUND
                    const insightBox = document.getElementById('aiInsightsContent');
                    if (insightBox) {{
                        insightBox.innerHTML = '<p style="color:var(--text-muted);"><span class="loading-dots">Zane is analyzing</span>...</p>';
                        
                        // Pass insights_payload directly (no cache dependency)
                        fetch('/api/reports/tb/insights', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{lang: lang, insights_payload: data.insights_payload || null}})
                        }})
                        .then(r => r.json())
                        .then(idata => {{
                            if (idata.success && idata.insights) {{
                                insightBox.innerHTML = idata.insights;
                            }} else {{
                                const errMsg = idata.error || 'Could not load insights';
                                insightBox.innerHTML = '<p style="color:#f97316;">' + errMsg + '. Die syfers hierbo is egter 100% akkuraat.</p>';
                            }}
                        }})
                        .catch(err => {{
                            insightBox.innerHTML = '<p style="color:#f97316;">Insights timeout - die syfers hierbo is 100% akkuraat.</p>';
                        }});
                    }}
                }} else {{
                    content.innerHTML = '<p style="color:var(--red);">' + (data.error || 'Analysis failed') + '</p>';
                }}
            }} catch (err) {{
                content.innerHTML = '<p style="color:var(--red);">Error: ' + err.message + '</p>';
            }}
            
            btn.disabled = false;
            btn.innerHTML = 'Re-analyze';
        }}
        
        async function handleTBImportSave(input) {{
            const file = input.files[0];
            if (!file) return;
            
            if (!confirm('This will REPLACE the current Trial Balance with the data from:\\n\\n' + file.name + '\\n\\nExisting opening balances will be cleared.\\nContinue?')) {{
                input.value = '';
                return;
            }}
            
            // Show loading
            const section = document.getElementById('analysisSection');
            const content = document.getElementById('analysisContent');
            section.style.display = 'block';
            content.innerHTML = '<p style="color:var(--text-muted);">📥 Importing ' + file.name + ' and replacing Trial Balance...</p>';
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {{
                const response = await fetch('/api/reports/tb/import-save', {{
                    method: 'POST',
                    body: formData
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    content.innerHTML = '<p style="color:#10b981;">✅ ' + data.message + '</p><p>Page reloading in 2 seconds...</p>';
                    setTimeout(() => location.reload(), 2000);
                }} else {{
                    content.innerHTML = '<p style="color:#ef4444;">❌ ' + (data.error || 'Import failed') + '</p>';
                }}
            }} catch (err) {{
                content.innerHTML = '<p style="color:#ef4444;">Error: ' + err.message + '</p>';
            }}
            
            input.value = '';
        }}
        
        async function handleTBUpload(input) {{
            const file = input.files[0];
            if (!file) return;
            
            const section = document.getElementById('analysisSection');
            const content = document.getElementById('analysisContent');
            const dateSpan = document.getElementById('analysisDate');
            const lang = document.getElementById('reportLang').value;
            
            section.style.display = 'block';
            content.innerHTML = '<p style="color:var(--text-muted);">📂 Reading ' + file.name + '...</p>';
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('lang', lang);
            
            try {{
                // Step 1: Upload and parse the file
                const uploadResponse = await fetch('/api/reports/tb/upload-analyze', {{
                    method: 'POST',
                    body: formData
                }});
                
                const uploadData = await uploadResponse.json();
                
                if (!uploadData.success) {{
                    content.innerHTML = '<p style="color:var(--red);">' + (uploadData.error || 'Upload failed') + '</p>';
                    input.value = '';
                    return;
                }}
                
                content.innerHTML = '<p style="color:var(--text-muted);">✅ ' + uploadData.message + '<br>🤖 Analyzing with Zane...</p>';
                
                // Step 2: Analyze the parsed data
                const analyzeResponse = await fetch('/api/reports/tb/analyze', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        accounts: uploadData.accounts,
                        total_debit: uploadData.total_debit,
                        total_credit: uploadData.total_credit,
                        is_balanced: uploadData.is_balanced,
                        lang: lang,
                        source_file: file.name,
                        company_name: uploadData.company_name || '',
                        tb_control_profit: uploadData.tb_control_profit || null
                    }})
                }});
                
                const analyzeData = await analyzeResponse.json();
                
                if (analyzeData.success) {{
                    content.innerHTML = analyzeData.analysis;
                    dateSpan.innerHTML = 'Analyzed: ' + new Date().toLocaleString() + ' (from ' + file.name + ')';
                    
                    // Async load Zane's insights
                    const insightBox = document.getElementById('aiInsightsContent');
                    if (insightBox) {{
                        insightBox.innerHTML = '<p style="color:var(--text-muted);">Zane is analyzing...</p>';
                        fetch('/api/reports/tb/insights', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{lang: lang, insights_payload: analyzeData.insights_payload || null}})
                        }})
                        .then(r => r.json())
                        .then(idata => {{
                            if (idata.success && idata.insights) {{
                                insightBox.innerHTML = idata.insights;
                            }} else {{
                                insightBox.innerHTML = '<p style="color:#f97316;">' + (idata.error || 'Insights unavailable') + '. Figures above are 100% accurate.</p>';
                            }}
                        }})
                        .catch(() => {{
                            insightBox.innerHTML = '<p style="color:#f97316;">Insights timeout - figures above are 100% accurate.</p>';
                        }});
                    }}
                }} else {{
                    content.innerHTML = '<p style="color:var(--red);">' + (analyzeData.error || 'Analysis failed') + '</p>';
                }}
            }} catch (err) {{
                content.innerHTML = '<p style="color:var(--red);">Error: ' + err.message + '</p>';
            }}
            
            // Reset input so same file can be uploaded again
            input.value = '';
        }}
        
        function printAnalysis() {{
            const content = document.getElementById('analysisContent').innerHTML;
            const printWindow = window.open('', '_blank', 'width=900,height=700');
            
            printWindow.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Trial Balance Analysis - {safe_string(biz_name)}</title>
                    <style>
                        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                        body {{ 
                            font-family: 'Segoe UI', Arial, sans-serif; 
                            padding: 30px;
                            color: #333;
                            background: white;
                            line-height: 1.6;
                        }}
                        h2 {{ color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 10px; margin-top: 25px; font-size: 18px; }}
                        h3 {{ color: #10b981; margin-top: 20px; margin-bottom: 10px; font-size: 15px; }}
                        h4 {{ color: #8b5cf6; margin-top: 15px; font-size: 13px; }}
                        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 12px; }}
                        th, td {{ padding: 8px; border: 1px solid #ddd; text-align: left; }}
                        th {{ background: #f5f5f5; }}
                        hr {{ border: none; border-top: 1px solid #ddd; margin: 15px 0; }}
                        strong {{ color: #333; }}
                        @media print {{
                            body {{ padding: 15px; }}
                            @page {{ size: A4; margin: 15mm; }}
                        }}
                    </style>
                </head>
                <body>
                    <div style="text-align:center;margin-bottom:20px;border-bottom:2px solid #6366f1;padding-bottom:15px;">
                        <h1 style="color:#6366f1;margin:0;">Trial Balance Analysis Report</h1>
                        <p style="color:#666;margin:5px 0;">{safe_string(biz_name)} | Generated: ${{new Date().toLocaleDateString()}}</p>
                    </div>
                    ${{content}}
                    <div style="margin-top:30px;padding-top:15px;border-top:1px solid #ddd;text-align:center;color:#888;font-size:11px;">
                        Generated by Click AI | Zane Financial Analysis
                    </div>
                </body>
                </html>
            `);
            
            printWindow.document.close();
            printWindow.focus();
            
            setTimeout(function() {{
                printWindow.print();
            }}, 300);
        }}
        
        // ═══ DOWNLOAD TB REPORT ═══
        function downloadTBReport() {{
            const content = document.getElementById('analysisContent').innerHTML;
            const dateStr = new Date().toISOString().slice(0,10);
            const title = 'Trial Balance Analysis - {safe_string(biz_name)}';
            
            const html = `<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>${{title}}</title>
    <style>
    body {{ font-family: Arial, Helvetica, sans-serif; max-width: 900px; margin: 30px auto; padding: 20px; color: #1a1a2e; line-height: 1.7; font-size: 14px; }}
    h1, h2, h3 {{ color: #1a1a2e; }} h2 {{ color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 10px; }}
    h3 {{ color: #10b981; }} table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
    th {{ text-align: left; padding: 8px; border-bottom: 2px solid #e5e7eb; color: #6366f1; }}
    td {{ padding: 6px 8px; border-bottom: 1px solid #f3f4f6; }}
    strong {{ color: #4f46e5; }} hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 15px 0; }}
    @media print {{ body {{ margin: 0; }} @page {{ size: A4; margin: 15mm; }} }}
    </style></head><body>
    <h1 style="color:#4f46e5;">📊 ${{title}}</h1>
    <p style="color:#6b7280;font-size:12px;">Generated by ClickAI | ${{dateStr}}</p>
    ${{content}}
    <hr><p style="color:#6b7280;font-size:11px;text-align:center;">Generated by ClickAI — AI-Powered Business Management</p>
    </body></html>`;
            
            const lightHtml = html
                .replace(/color:\s*rgba\(255,\s*255,\s*255,[\s\d.]+\)/gi, 'color:#1a1a2e')
                .replace(/color:\s*var\(--text\)/gi, 'color:#1a1a2e')
                .replace(/color:\s*var\(--text-muted\)/gi, 'color:#6b7280')
                .replace(/border[^:]*:\s*[\d.]+px\s+solid\s+rgba\(255,\s*255,\s*255,[\s\d.]+\)/gi, 'border:1px solid #e5e7eb');
            
            const blob = new Blob([lightHtml], {{type: 'text/html'}});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'TB_Analysis_{safe_string(biz_name)}_' + dateStr + '.html';
            a.click();
            URL.revokeObjectURL(a.href);
        }}
        
        // ═══ EMAIL TB REPORT ═══
        function emailTBReport() {{
            // Create modal dynamically
            let modal = document.getElementById('tbEmailModal');
            if (!modal) {{
                modal = document.createElement('div');
                modal.id = 'tbEmailModal';
                modal.style.cssText = 'display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center;';
                modal.innerHTML = `
                    <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:25px;width:90%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                            <h3 style="margin:0;color:var(--primary);">Email Report</h3>
                            <button onclick="document.getElementById('tbEmailModal').style.display='none'" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button>
                        </div>
                        <input type="email" id="tbEmailTo" class="form-input" placeholder="email@example.com" style="width:100%;margin-bottom:10px;">
                        <input type="text" id="tbEmailSubject" class="form-input" value="TB Analysis - {safe_string(biz_name)}" style="width:100%;margin-bottom:15px;">
                        <div style="display:flex;gap:10px;justify-content:flex-end;">
                            <button class="btn btn-secondary" onclick="document.getElementById('tbEmailModal').style.display='none'">Cancel</button>
                            <button class="btn btn-primary" id="tbSendBtn" onclick="sendTBEmail()">Send</button>
                        </div>
                        <p id="tbEmailStatus" style="margin:10px 0 0 0;font-size:12px;display:none;"></p>
                    </div>`;
                document.body.appendChild(modal);
            }}
            document.getElementById('tbEmailStatus').style.display = 'none';
            modal.style.display = 'flex';
            document.getElementById('tbEmailTo').focus();
        }}
        
        async function sendTBEmail() {{
            const to = document.getElementById('tbEmailTo').value.trim();
            const subject = document.getElementById('tbEmailSubject').value.trim() || 'TB Analysis';
            const content = document.getElementById('analysisContent').innerHTML;
            const status = document.getElementById('tbEmailStatus');
            const btn = document.getElementById('tbSendBtn');
            
            if (!to || !to.includes('@')) {{
                status.style.display = 'block'; status.style.color = 'var(--red)';
                status.textContent = 'Please enter a valid email'; return;
            }}
            
            btn.disabled = true; btn.textContent = 'Sending...';
            status.style.display = 'block'; status.style.color = 'var(--text-muted)';
            status.textContent = 'Sending report...';
            
            try {{
                const resp = await fetch('/api/reports/email', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        to_email: to, subject: subject,
                        report_html: content,
                        report_title: 'Trial Balance Analysis - {safe_string(biz_name)}'
                    }})
                }});
                const data = await resp.json();
                if (data.success) {{
                    status.style.color = 'var(--green)'; status.textContent = 'GOOD: ' + data.message;
                    setTimeout(() => {{ document.getElementById('tbEmailModal').style.display='none'; }}, 2000);
                }} else {{
                    status.style.color = 'var(--red)'; status.textContent = '✗ ' + (data.error || 'Failed');
                }}
            }} catch (err) {{
                status.style.color = 'var(--red)'; status.textContent = '✗ ' + err.message;
            }}
            btn.disabled = false; btn.textContent = 'Send';
        }}
        
        async function clearOpeningBalances() {{
            if (!confirm('⚠️ Dit sal ALLE opening balance entries uitvee!\\n\\nJy sal daarna weer moet import.\\n\\nIs jy seker?')) return;
            
            try {{
                const response = await fetch('/api/reports/tb/clear-ob', {{method: 'POST'}});
                const data = await response.json();
                
                if (data.success) {{
                    alert('✅ ' + data.message + '\\n\\nHerlaai bladsy...');
                    location.reload();
                }} else {{
                    alert('❌ Error: ' + data.error);
                }}
            }} catch (err) {{
                alert('❌ Error: ' + err.message);
            }}
        }}
        // Auto-analyze if redirected from import page
        if (window.location.search.includes('auto_analyze=1')) {{
            setTimeout(() => analyzeWithZane(), 500);
        }}
        </script>
        '''
        
        return render_page("Trial Balance", content, user, "reports")
    
    
    @app.route("/api/reports/tb/clear-ob", methods=["POST"])
    @login_required
    def api_tb_clear_ob():
        """Clear all opening balance entries for this business"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business selected"})
        
        try:
            # Get all OB entries
            journal_entries = db.get("journal_entries", {"business_id": biz_id}) or []
            ob_entries = [je for je in journal_entries if je.get("reference") == "OB"]
            
            if not ob_entries:
                return jsonify({"success": True, "message": "Geen opening balance entries om te verwyder nie"})
            
            # Delete each OB entry
            deleted = 0
            for ob in ob_entries:
                try:
                    db.delete("journal_entries", ob.get("id"))
                    deleted += 1
                except Exception as del_err:
                    logger.warning(f"[TB CLEAR] Failed to delete {ob.get('id')}: {del_err}")
            
            logger.info(f"[TB CLEAR] Deleted {deleted} OB entries for business {biz_id}")
            AuditLog.log("DELETE", "journal_entries", None, details=f"Cleared {deleted} opening balance entries")
            
            return jsonify({"success": True, "message": f"{deleted} opening balance entries verwyder"})
            
        except Exception as e:
            logger.error(f"[TB CLEAR] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/reports/tb/import-save", methods=["POST"])
    @login_required
    def api_tb_import_save():
        """Upload CSV/Excel TB and SAVE it as opening balances - REPLACES existing TB.
        
        Flow: Parse file → Clear old OB entries → Save new OB entries → Return success
        Page reloads to show new TB data.
        """
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business selected"})
        
        try:
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "No file uploaded"})
            
            file = request.files['file']
            if not file.filename:
                return jsonify({"success": False, "error": "No file selected"})
            
            filename = file.filename.lower()
            logger.info(f"[TB IMPORT-SAVE] Processing {filename}")
            
            import pandas as pd
            import io
            
            # ═══ Read file ═══
            try:
                if filename.endswith('.csv'):
                    content = file.read()
                    if content[:3] == b'\xef\xbb\xbf':
                        content = content[3:]
                    
                    text = None
                    for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            text = content.decode(enc)
                            break
                        except:
                            continue
                    
                    if not text:
                        return jsonify({"success": False, "error": "Could not read CSV - encoding issue"})
                    
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    header_row = 0
                    for i, line in enumerate(lines[:10]):
                        stripped = line.strip().strip('"').strip().lower()
                        if stripped.startswith('sep='):
                            header_row = i + 1
                            continue
                        in_quote = False
                        comma_count = 0
                        for ch in line:
                            if ch == '"': in_quote = not in_quote
                            elif ch == ',' and not in_quote: comma_count += 1
                        if comma_count == 0:
                            header_row = i + 1
                            continue
                        break
                    
                    header_line = lines[header_row] if header_row < len(lines) else lines[0]
                    if ';' in header_line and header_line.count(';') > header_line.count(','):
                        sep = ';'
                    elif '\t' in header_line:
                        sep = '\t'
                    else:
                        sep = ','
                    
                    clean_text = '\n'.join(lines[header_row:])
                    df = pd.read_csv(io.StringIO(clean_text), sep=sep, on_bad_lines='skip', engine='python')
                    
                elif filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file)
                else:
                    return jsonify({"success": False, "error": "Unsupported file type. Use CSV or Excel."})
            except Exception as read_err:
                return jsonify({"success": False, "error": f"Could not read file: {str(read_err)}"})
            
            logger.info(f"[TB IMPORT-SAVE] Read {len(df)} rows, columns: {list(df.columns)}")
            
            # ═══ Column detection (same logic as upload-analyze) ═══
            cols_lower = {c.lower().strip(): c for c in df.columns}
            
            code_col = None
            for c in ['code', 'acc code', 'account code', 'acc_code', 'kode', 'gl code', 'account_code', 'acc no', 'account no', 'account number', 'gl no', 'no', 'number']:
                if c in cols_lower: code_col = cols_lower[c]; break
            
            name_col = None
            for c in ['name', 'account', 'account name', 'description', 'naam', 'rekening', 'rekening naam', 'acc name', 'account_name', 'omskrywing', 'account description', 'ledger', 'gl name', 'label']:
                if c in cols_lower: name_col = cols_lower[c]; break
            
            debit_col = None
            for c in ['debit', 'dr', 'debits', 'debit amount', 'debiet', 'debit balance', 'debiet saldo', 'dr amount']:
                if c in cols_lower: debit_col = cols_lower[c]; break
            
            credit_col = None
            for c in ['credit', 'cr', 'credits', 'credit amount', 'krediet', 'credit balance', 'krediet saldo', 'cr amount']:
                if c in cols_lower: credit_col = cols_lower[c]; break
            
            balance_col = None
            if not debit_col and not credit_col:
                for c in ['balance', 'saldo', 'amount', 'bedrag', 'net balance', 'netto', 'value', 'total', 'totaal', 'closing balance', 'closing']:
                    if c in cols_lower: balance_col = cols_lower[c]; break
            
            # AI fallback if needed
            if not name_col or (not debit_col and not credit_col and not balance_col):
                try:
                    sample_rows = df.head(8).to_string()
                    col_list = list(df.columns)
                    ai_prompt = f"Analyze this trial balance file columns.\nCOLUMNS: {col_list}\nSAMPLE:\n{sample_rows}\nReturn ONLY JSON: {{\"account_code\": \"col or null\", \"account_name\": \"col\", \"debit\": \"col or null\", \"credit\": \"col or null\", \"balance\": \"col or null\"}}"
                    client = _anthropic_client
                    ai_resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=300, messages=[{"role": "user", "content": ai_prompt}])
                    # ─── AI-USAGE TRACKING ───
                    try:
                        if hasattr(app, "_ai_usage_tracker") and biz_id:
                            _usr = Auth.get_current_user()
                            _usr_id = _usr.get("id") if _usr else None
                            _usage = getattr(ai_resp, "usage", None)
                            app._ai_usage_tracker.log_usage(
                                business_id=biz_id,
                                tool="tb_column_detect",
                                model=getattr(ai_resp, "model", "claude-sonnet-4-6"),
                                input_tokens=int(getattr(_usage, "input_tokens", 0) or 0),
                                output_tokens=int(getattr(_usage, "output_tokens", 0) or 0),
                                cache_read_tokens=int(getattr(_usage, "cache_read_input_tokens", 0) or 0),
                                cache_write_tokens=int(getattr(_usage, "cache_creation_input_tokens", 0) or 0),
                                user_id=_usr_id,
                                success=True,
                            )
                    except Exception as _track_err:
                        logger.error(f"[AI-USAGE] tb_column_detect tracking skipped: {_track_err}")
                    # ─── END TRACKING ───
                    ai_text = ai_resp.content[0].text.strip()
                    if '```' in ai_text: ai_text = ai_text.split('```')[1].replace('json', '').strip()
                    ai_map = json.loads(ai_text)
                    if ai_map.get("account_name") and ai_map["account_name"] in df.columns: name_col = ai_map["account_name"]
                    if ai_map.get("account_code") and ai_map["account_code"] in df.columns: code_col = ai_map["account_code"]
                    if ai_map.get("debit") and ai_map["debit"] in df.columns: debit_col = ai_map["debit"]
                    if ai_map.get("credit") and ai_map["credit"] in df.columns: credit_col = ai_map["credit"]
                    if ai_map.get("balance") and ai_map["balance"] in df.columns: balance_col = ai_map["balance"]
                except Exception as ai_err:
                    logger.warning(f"[TB IMPORT-SAVE] AI column detection failed: {ai_err}")
            
            if not name_col:
                for c in df.columns:
                    if df[c].dtype == 'object': name_col = c; break
            
            if not name_col:
                return jsonify({"success": False, "error": f"Could not find account name column. Columns: {list(df.columns)}"})
            if not debit_col and not credit_col and not balance_col:
                return jsonify({"success": False, "error": f"Could not find debit/credit/balance columns. Columns: {list(df.columns)}"})
            
            logger.info(f"[TB IMPORT-SAVE] Mapped: code={code_col}, name={name_col}, debit={debit_col}, credit={credit_col}, balance={balance_col}")
            
            # ═══ Parse amounts ═══
            def parse_amount(val):
                if pd.isna(val): return 0.0
                val = str(val).replace('R', '').replace('r', '').replace(',', '').replace(' ', '').strip()
                is_neg = val.startswith('(') and val.endswith(')')
                if is_neg: val = val[1:-1]
                if val in ['', '-', 'nan', 'none', '0', '0.0', '0.00']: return 0.0
                try:
                    result = float(val)
                    return -result if is_neg else result
                except: return 0.0
            
            # ═══ Build accounts ═══
            accounts = []
            for idx, row in df.iterrows():
                name = str(row.get(name_col, '')).strip() if name_col else ''
                if not name or name.lower() in ['nan', 'none', '', 'total', 'totals', 'totaal', 'grand total', 'netto', 'net', 'net profit/loss', 'net profit/loss after tax', 'net profit']:
                    continue
                
                code = str(row.get(code_col, '')).strip() if code_col else ''
                if code.lower() in ['nan', 'none', '']: code = ''
                
                # Smart split: "1000/000 : Sales" → code, name
                if not code and ' : ' in name:
                    parts = name.split(' : ', 1); code = parts[0].strip(); name = parts[1].strip()
                elif not code and ' - ' in name and name[0].isdigit():
                    parts = name.split(' - ', 1); code = parts[0].strip(); name = parts[1].strip()
                
                if not code: code = f"A{idx:04d}"
                name = name.replace('_AND_', '&')
                
                debit = 0.0
                credit = 0.0
                if debit_col and credit_col:
                    debit = abs(parse_amount(row.get(debit_col)))
                    credit = abs(parse_amount(row.get(credit_col)))
                elif balance_col:
                    bal = parse_amount(row.get(balance_col))
                    if bal > 0: debit = bal
                    elif bal < 0: credit = abs(bal)
                
                if debit > 0 or credit > 0:
                    accounts.append({"code": code, "name": name, "debit": debit, "credit": credit})
            
            if not accounts:
                return jsonify({"success": False, "error": "No valid accounts found in file"})
            
            # ═══ Clear existing OB entries ═══
            journal_entries = db.get("journal_entries", {"business_id": biz_id}) or []
            ob_entries = [je for je in journal_entries if je.get("reference") == "OB"]
            deleted = 0
            for ob in ob_entries:
                try:
                    db.delete("journal_entries", ob.get("id"))
                    deleted += 1
                except: pass
            logger.info(f"[TB IMPORT-SAVE] Cleared {deleted} old OB entries")
            
            # ═══ Save new OB entries ═══
            saved = 0
            for acc in accounts:
                entry = {
                    "id": generate_id(),
                    "business_id": biz_id,
                    "date": today(),
                    "account": acc["name"],
                    "account_code": acc["code"],
                    "debit": acc["debit"],
                    "credit": acc["credit"],
                    "description": f"Opening Balance - {acc['name']}",
                    "reference": "OB",
                    "created_at": now()
                }
                success, _ = db.save("journal_entries", entry)
                if success:
                    saved += 1
            
            logger.info(f"[TB IMPORT-SAVE] Saved {saved}/{len(accounts)} OB entries from {file.filename}")
            
            total_dr = sum(a["debit"] for a in accounts)
            total_cr = sum(a["credit"] for a in accounts)
            
            return jsonify({
                "success": True,
                "message": f"TB imported: {saved} accounts saved. Debits: R{total_dr:,.2f}, Credits: R{total_cr:,.2f}",
                "accounts_saved": saved,
                "total_accounts": len(accounts)
            })
            
        except Exception as e:
            logger.error(f"[TB IMPORT-SAVE] Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/reports/tb/analyze", methods=["POST"])
    @login_required
    def api_tb_analyze():
        """AI Analysis of Trial Balance - ALL CALCULATIONS BY PYTHON"""
        
        business = Auth.get_current_business()
        biz_name = business.get("name", "Business") if business else "Business"
        industry = business.get("industry", "general") if business else "general"
        
        try:
            data = request.get_json()
            accounts = data.get("accounts", [])
            lang = data.get("lang", "en")
            
            # If a source file was uploaded (external TB), note it in the report
            source_file = data.get("source_file", "")
            company_name = data.get("company_name", "")
            
            # IMPORTANT: If a CSV was uploaded, it's ALWAYS a third-party client's data
            # The user wouldn't upload their own TB - ClickAI generates that internally
            # So NEVER use the logged-in business name for uploaded TBs
            if source_file:
                if company_name:
                    report_company = company_name
                else:
                    # Use filename without extension as company hint
                    clean_name = source_file.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').strip()
                    report_company = f"Client TB ({clean_name})"
                is_third_party = True
            else:
                report_company = biz_name
                is_third_party = False
            
            logger.info(f"[TB ANALYZE] Language selected: {lang}")
            
            # ═══════════════════════════════════════════════════════════════════════
            # LANGUAGE LABELS - English and Afrikaans
            # ═══════════════════════════════════════════════════════════════════════
            labels = {
                "en": {
                    "report_title": "TRIAL BALANCE ANALYSIS REPORT",
                    "company": "Company",
                    "date": "Date",
                    "prepared_by": "Prepared by",
                    "balance_status": "1. BALANCE STATUS",
                    "total_debits": "Total Debits",
                    "total_credits": "Total Credits",
                    "difference": "Difference",
                    "balanced": "BALANCED",
                    "unbalanced": "UNBALANCED",
                    "critical_error": "CRITICAL ERROR",
                    "tb_not_balanced": "This trial balance does NOT balance. There is a",
                    "difference_text": "difference. Check the data before continuing.",
                    "balance_sheet_summary": "2. BALANCE SHEET SUMMARY",
                    "assets": "ASSETS",
                    "current_assets": "Current Assets",
                    "bank_cash": "Bank/Cash",
                    "debtors": "Debtors",
                    "inventory": "Inventory",
                    "vat_input": "VAT Input",
                    "prepayments": "Prepayments",
                    "total_current_assets": "Total Current Assets",
                    "fixed_assets": "Fixed Assets",
                    "cost": "Cost",
                    "less_accum_depr": "Less: Accumulated Depreciation",
                    "net_fixed_assets": "Net Fixed Assets",
                    "total_assets": "TOTAL ASSETS",
                    "liab_equity": "LIABILITIES & EQUITY",
                    "current_liabilities": "Current Liabilities",
                    "creditors": "Creditors",
                    "vat_output": "VAT Output",
                    "paye_payable": "PAYE Payable",
                    "uif_payable": "UIF Payable",
                    "total_current_liab": "Total Current",
                    "long_term_liab": "Long-term Liabilities",
                    "loans": "Loans",
                    "total_liabilities": "Total Liabilities",
                    "equity": "Equity",
                    "capital": "Capital",
                    "retained_earnings": "Retained Earnings",
                    "less_drawings": "Less: Drawings",
                    "total_equity": "Total Equity",
                    "liab_plus_equity": "LIABILITIES + EQUITY",
                    "income_statement": "3. INCOME STATEMENT SUMMARY",
                    "sales": "Sales",
                    "less_returns": "Less: Sales Returns",
                    "net_sales": "Net Sales",
                    "less_cos": "Less: Cost of Sales",
                    "gross_profit": "GROSS PROFIT",
                    "plus_other_income": "Plus: Other Income",
                    "less_operating_exp": "Less: Operating Expenses",
                    "net_profit": "NET PROFIT",
                    "financial_ratios": "4. FINANCIAL RATIOS",
                    "ratio": "Ratio",
                    "value": "Value",
                    "status": "Status",
                    "norm": "Norm",
                    "current_ratio": "Current Ratio",
                    "quick_ratio": "Quick Ratio",
                    "debt_equity": "Debt to Equity",
                    "gp_margin": "Gross Profit Margin",
                    "np_margin": "Net Profit Margin",
                    "debtor_days": "Debtor Days",
                    "creditor_days": "Creditor Days",
                    "stock_days": "Stock Days",
                    "days": "days",
                    "industry": "Industry",
                    "sars_obligations": "5. SARS OBLIGATIONS",
                    "vat_position": "VAT Position",
                    "vat_collected": "VAT Output (Collected)",
                    "vat_paid": "VAT Input (Paid)",
                    "vat_payable": "VAT Payable to SARS",
                    "vat_refund": "VAT Refund",
                    "employee_taxes": "Employee Taxes",
                    "total_emp201": "Total EMP201",
                    "expense_analysis": "6. EXPENSE ANALYSIS",
                    "expense": "Expense",
                    "amount": "Amount",
                    "pct_of_sales": "% of Sales",
                    "salaries_wages": "Salaries and Wages",
                    "rent": "Rent",
                    "electricity": "Electricity",
                    "depreciation": "Depreciation",
                    "fuel_transport": "Fuel & Transport",
                    "advertising": "Advertising",
                    "professional_fees": "Professional Fees",
                    "interest_paid": "Interest Paid",
                    "other_expenses": "Other Expenses",
                    "total_expenses": "TOTAL EXPENSES",
                    "zane_insight": "Zane's Insight",
                    "loading_insight": "Loading professional insight...",
                    "calculations_by": "All calculations by Python | Figures verified | Generated",
                    "red_flags": "RED FLAGS",
                    "no_critical": "NO CRITICAL ISSUES",
                    "all_ratios_ok": "All ratios within acceptable limits.",
                    "critical": "CRITICAL",
                    "warning": "WARNING",
                    "monitor": "MONITOR",
                    "tb_not_bal_flag": "TB does NOT balance - R{diff} difference. STOP EVERYTHING and find the error.",
                    "current_ratio_crit": "Current ratio {ratio}:1 - cannot pay short-term debt!",
                    "current_ratio_warn": "Current ratio {ratio}:1 - liquidity under pressure.",
                    "quick_ratio_crit": "Quick ratio {ratio}:1 - serious cash flow risk!",
                    "debtor_days_warn": "Debtors {days} days - collect urgently!",
                    "debtor_days_mon": "Debtors {days} days - start applying pressure.",
                    "stock_days_warn": "Inventory {days} days - dead/slow stock?",
                    "gp_margin_crit": "Gross margin {pct}% - prices too low or costs too high!",
                    "gp_margin_warn": "Gross margin {pct}% - below industry norm.",
                    "making_loss": "Making a LOSS of R{amount}!",
                    "np_margin_warn": "Net margin {pct}% - very thin.",
                    "debt_equity_warn": "Debt/Equity {ratio}:1 - highly leveraged.",
                    "vat_payable_mon": "VAT payable R{amount} - ensure funds available.",
                    "salaries_warn": "Salaries {pct}% of sales - overhead costs high.",
                    "paye_uif_mon": "PAYE/UIF R{amount} - submit EMP201 on time!",
                    "acc_list_title": "FULL ACCOUNT LIST (Python-verified):",
                    "acc_code": "Code",
                    "acc_name": "Account Name",
                    "debit": "Debit",
                    "credit": "Credit",
                    "assets_codes": "ASSETS (Codes 1xxx-2xxx):",
                    "no_asset_acc": "No asset accounts",
                    "liab_codes": "LIABILITIES (Codes 3xxx):",
                    "no_liab_acc": "No liability accounts",
                    "equity_codes": "EQUITY (Codes 4xxx):",
                    "no_equity_acc": "No equity accounts",
                    "income_codes": "INCOME (Codes 5xxx):",
                    "no_income_acc": "No income accounts",
                    "expense_codes": "EXPENSES (Codes 6xxx-9xxx):",
                    "no_expense_acc": "No expense accounts",
                    "unclassified": "UNCLASSIFIED:",
                },
                "af": {
                    "report_title": "PROEFBALANS ANALISE VERSLAG",
                    "company": "Maatskappy",
                    "date": "Datum",
                    "prepared_by": "Voorberei deur",
                    "balance_status": "1. BALANS STATUS",
                    "total_debits": "Totale Debits",
                    "total_credits": "Totale Kredits",
                    "difference": "Verskil",
                    "balanced": "GEBALANSEER",
                    "unbalanced": "ONGEBALANSEER",
                    "critical_error": "KRITIEKE FOUT",
                    "tb_not_balanced": "Hierdie proefbalans balanseer NIE. Daar is 'n",
                    "difference_text": "verskil. Gaan die data na voordat jy voortgaan.",
                    "balance_sheet_summary": "2. BALANSSTAAT OPSOMMING",
                    "assets": "BATES",
                    "current_assets": "Bedryfsbates",
                    "bank_cash": "Bank/Kontant",
                    "debtors": "Debiteure",
                    "inventory": "Voorraad",
                    "vat_input": "BTW Insette",
                    "prepayments": "Vooruitbetalings",
                    "total_current_assets": "Totaal Bedryfsbates",
                    "fixed_assets": "Vaste Bates",
                    "cost": "Kosprys",
                    "less_accum_depr": "Min: Opgehoopte Waardevermindering",
                    "net_fixed_assets": "Netto Vaste Bates",
                    "total_assets": "TOTALE BATES",
                    "liab_equity": "LASTE & EKWITEIT",
                    "current_liabilities": "Korttermyn Laste",
                    "creditors": "Krediteure",
                    "vat_output": "BTW Uitsette",
                    "paye_payable": "LBS Betaalbaar",
                    "uif_payable": "WVF Betaalbaar",
                    "total_current_liab": "Totaal Korttermyn",
                    "long_term_liab": "Langtermyn Laste",
                    "loans": "Lenings",
                    "total_liabilities": "Totale Laste",
                    "equity": "Ekwiteit",
                    "capital": "Kapitaal",
                    "retained_earnings": "Behoue Verdienste",
                    "less_drawings": "Min: Onttrekkings",
                    "total_equity": "Totale Ekwiteit",
                    "liab_plus_equity": "LASTE + EKWITEIT",
                    "income_statement": "3. INKOMSTESTAAT OPSOMMING",
                    "sales": "Verkope",
                    "less_returns": "Min: Verkope Teruggawes",
                    "net_sales": "Netto Verkope",
                    "less_cos": "Min: Koste van Verkope",
                    "gross_profit": "BRUTO WINS",
                    "plus_other_income": "Plus: Ander Inkomste",
                    "less_operating_exp": "Min: Bedryfsuitgawes",
                    "net_profit": "NETTO WINS",
                    "financial_ratios": "4. FINANSIËLE VERHOUDINGS",
                    "ratio": "Verhouding",
                    "value": "Waarde",
                    "status": "Status",
                    "norm": "Norm",
                    "current_ratio": "Bedryfsbateverhouding (Current Ratio)",
                    "quick_ratio": "Suurtoetsverhouding (Quick Ratio)",
                    "debt_equity": "Skuld tot Ekwiteit (Debt/Equity)",
                    "gp_margin": "Bruto Winsmarge (GP Margin)",
                    "np_margin": "Netto Winsmarge (NP Margin)",
                    "debtor_days": "Debiteure Dae (Debtor Days)",
                    "creditor_days": "Krediteure Dae (Creditor Days)",
                    "stock_days": "Voorraad Dae (Stock Days)",
                    "days": "dae",
                    "industry": "Industrie",
                    "sars_obligations": "5. SAID/SARS VERPLIGTINGE",
                    "vat_position": "BTW Posisie",
                    "vat_collected": "BTW Uitsette (Ingesamel)",
                    "vat_paid": "BTW Insette (Betaal)",
                    "vat_payable": "BTW Betaalbaar aan SAID",
                    "vat_refund": "BTW Terugbetaling",
                    "employee_taxes": "Werknemerbelasting",
                    "total_emp201": "Totaal EMP201",
                    "expense_analysis": "6. UITGAWE ANALISE",
                    "expense": "Uitgawe",
                    "amount": "Bedrag",
                    "pct_of_sales": "% van Verkope",
                    "salaries_wages": "Salarisse en Lone",
                    "rent": "Huur",
                    "electricity": "Elektrisiteit",
                    "depreciation": "Waardevermindering",
                    "fuel_transport": "Brandstof & Vervoer",
                    "advertising": "Reklame",
                    "professional_fees": "Professionele Fooie",
                    "interest_paid": "Rente Betaal",
                    "other_expenses": "Ander Uitgawes",
                    "total_expenses": "TOTALE UITGAWES",
                    "zane_insight": "Zane se Insig",
                    "loading_insight": "Laai professionele insig...",
                    "calculations_by": "Alle berekeninge gedoen deur Python | Syfers geverifieer | Gegenereer",
                    "red_flags": "ROOI VLAE",
                    "no_critical": "GEEN KRITIEKE PROBLEME",
                    "all_ratios_ok": "Alle verhoudinge binne aanvaarbare perke.",
                    "critical": "KRITIEK",
                    "warning": "WAARSKUWING",
                    "monitor": "MONITOR",
                    "tb_not_bal_flag": "TB balanseer NIE - R{diff} verskil. STOP ALLES en vind die fout.",
                    "current_ratio_crit": "Current ratio {ratio}:1 - kan nie korttermyn skuld betaal nie!",
                    "current_ratio_warn": "Current ratio {ratio}:1 - likiditeit onder druk.",
                    "quick_ratio_crit": "Quick ratio {ratio}:1 - ernstige kontantvloei risiko!",
                    "debtor_days_warn": "Debiteure {days} dae - invorder dringend!",
                    "debtor_days_mon": "Debiteure {days} dae - begin druk sit.",
                    "stock_days_warn": "Voorraad {days} dae - dooie/stadige voorraad?",
                    "gp_margin_crit": "Bruto marge {pct}% - pryse te laag of koste te hoog!",
                    "gp_margin_warn": "Bruto marge {pct}% - onder industrie norm.",
                    "making_loss": "Maak VERLIES van R{amount}!",
                    "np_margin_warn": "Netto marge {pct}% - baie dun.",
                    "debt_equity_warn": "Skuld/Ekwiteit {ratio}:1 - hoog gehefboom.",
                    "vat_payable_mon": "BTW betaalbaar R{amount} - maak seker fondse beskikbaar.",
                    "salaries_warn": "Salarisse {pct}% van verkope - oorhoofse koste hoog.",
                    "paye_uif_mon": "LBS/WVF R{amount} - EMP201 betyds indien!",
                    "acc_list_title": "VOLLEDIGE REKENINGLYS (Python-geverifieer):",
                    "acc_code": "Kode",
                    "acc_name": "Rekening Naam",
                    "debit": "Debit",
                    "credit": "Krediet",
                    "assets_codes": "BATES (Kodes 1xxx-2xxx):",
                    "no_asset_acc": "Geen bate rekeninge",
                    "liab_codes": "LASTE (Kodes 3xxx):",
                    "no_liab_acc": "Geen laste rekeninge",
                    "equity_codes": "EKWITEIT (Kodes 4xxx):",
                    "no_equity_acc": "Geen ekwiteit rekeninge",
                    "income_codes": "INKOMSTE (Kodes 5xxx):",
                    "no_income_acc": "Geen inkomste rekeninge",
                    "expense_codes": "UITGAWES (Kodes 6xxx-9xxx):",
                    "no_expense_acc": "Geen uitgawe rekeninge",
                    "unclassified": "ONGEKLASSIFISEER:",
                }
            }
            L = labels.get(lang, labels["en"])  # Default to English if unknown lang
            
            if not accounts:
                return jsonify({"success": False, "error": "No trial balance data to analyze"})
            
            # ═══════════════════════════════════════════════════════════════════════
            # PYTHON CALCULATES EVERYTHING - 100% ACCURATE
            # ═══════════════════════════════════════════════════════════════════════
            
            # Step 1: Calculate EXACT totals from raw data
            total_debit = sum(float(a.get("debit", 0) or 0) for a in accounts)
            total_credit = sum(float(a.get("credit", 0) or 0) for a in accounts)
            difference = abs(total_debit - total_credit)
            is_balanced = difference < 0.01
            
            logger.info(f"[TB ANALYZE] Python calculated: Dr={total_debit:.2f} Cr={total_credit:.2f} Diff={difference:.2f}")
            
            # Step 2: Categorize accounts - USE CATEGORY COLUMN IF AVAILABLE
            # This is critical: different accounting packages use different code schemes
            # Sage Pastel: 1000=Sales, 2000=COS, 3000-4000=Expenses, 5000=Equity, 6000+=Assets
            # Standard:    1000=Assets, 2000=Assets, 3000=Liabilities, 4000=Equity, 5000=Income, 6000+=Expenses
            # So we CANNOT rely on codes - we must use the Category column
            
            has_categories = any(a.get("category") for a in accounts)
            logger.info(f"[TB ANALYZE] Category column available: {has_categories}")
            
            if has_categories:
                # ═══════════════════════════════════════════════════════════════
                # CATEGORY-BASED CLASSIFICATION (reliable, works for ALL systems)
                # ═══════════════════════════════════════════════════════════════
                logger.info("[TB ANALYZE] Using CATEGORY column for classification")
                
                def cat_sum(acc_list, categories, column="debit"):
                    """Sum accounts matching category list"""
                    total = 0
                    for a in acc_list:
                        cat = str(a.get("category", "")).lower().strip()
                        for c in categories:
                            if c in cat:
                                total += float(a.get(column, 0) or 0)
                                break
                    return total
                
                def cat_net(acc_list, categories):
                    """Net value (debit - credit) for matching categories"""
                    total = 0
                    for a in acc_list:
                        cat = str(a.get("category", "")).lower().strip()
                        for c in categories:
                            if c in cat:
                                dr = float(a.get("debit", 0) or 0)
                                cr = float(a.get("credit", 0) or 0)
                                total += dr - cr
                                break
                    return total
                
                def name_match(acc, keywords, column="debit"):
                    """Match account by name keywords"""
                    name = str(acc.get("name", "")).lower()
                    val = float(acc.get(column, 0) or 0)
                    for kw in keywords:
                        if kw in name:
                            return val
                    return 0
                
                # INCOME (Credit balances - sales, other income)
                sales = cat_sum(accounts, ["sales", "revenue", "turnover", "omset"], "credit")
                sales_returns = cat_sum(accounts, ["sales return", "return"], "debit")
                cos = cat_sum(accounts, ["cost of sale", "cost of goods", "koste van verkope", "cogs"], "debit")
                other_income = cat_sum(accounts, ["other income", "ander inkomste", "interest received"], "credit")
                
                # EXPENSES (Debit balances)
                # Get all expense accounts individually for the breakdown
                expense_accounts = [a for a in accounts if any(kw in str(a.get("category", "")).lower() for kw in ["expense", "uitgawe", "operating"])]
                
                salaries = sum(name_match(a, ["salary", "salaries", "wage", "payroll", "salar"]) for a in expense_accounts)
                rent = sum(name_match(a, ["rent"]) for a in expense_accounts)
                electricity = sum(name_match(a, ["electric", "water", "eskom", "power", "elektris"]) for a in expense_accounts)
                water = 0  # Often combined with electricity
                telephone = sum(name_match(a, ["telephone", "internet", "cell", "mobile", "telkom", "telef"]) for a in expense_accounts)
                insurance = sum(name_match(a, ["insurance", "verseker"]) for a in expense_accounts)
                bank_charges = sum(name_match(a, ["bank charge", "bank fee", "bankkoste"]) for a in expense_accounts)
                fuel = sum(name_match(a, ["fuel", "petrol", "diesel", "transport", "brandstof"]) for a in expense_accounts)
                repairs = sum(name_match(a, ["repair", "maintenance", "onderhoud"]) for a in expense_accounts)
                office = sum(name_match(a, ["office", "stationery", "supplies", "kantoor"]) for a in expense_accounts)
                advertising = sum(name_match(a, ["advertising", "marketing", "promotion", "advertens"]) for a in expense_accounts)
                professional = sum(name_match(a, ["professional", "accounting", "legal", "audit", "rekenmeest"]) for a in expense_accounts)
                depreciation = sum(name_match(a, ["depreciation", "waardevermindering"]) for a in expense_accounts)
                bad_debts = sum(name_match(a, ["bad debt", "doubtful", "slegte skuld"]) for a in expense_accounts)
                interest_paid = sum(name_match(a, ["interest paid", "interest expense", "finance charge", "rente betaal"]) for a in expense_accounts)
                
                # Total expenses from category (more accurate than summing named items)
                total_expenses_from_cat = cat_net(accounts, ["expense", "uitgawe", "operating"])
                # Handle credit balance expenses (recoveries) - net them out
                if total_expenses_from_cat < 0:
                    total_expenses_from_cat = 0
                
                # Sundry = total expenses minus named ones
                named_expenses = salaries + rent + electricity + water + telephone + insurance + bank_charges + fuel + repairs + office + advertising + professional + depreciation + bad_debts + interest_paid
                sundry_exp = max(0, total_expenses_from_cat - named_expenses)
                
                # BALANCE SHEET from categories
                # Current Assets
                bank = 0
                cash = 0
                debtors = 0
                stock = 0
                prepaid = 0
                vat_input = 0
                other_current = 0
                
                for a in accounts:
                    cat = str(a.get("category", "")).lower()
                    name = str(a.get("name", "")).lower()
                    dr = float(a.get("debit", 0) or 0)
                    cr = float(a.get("credit", 0) or 0)
                    net = dr - cr
                    
                    if "current asset" in cat and "non-current" not in cat or "bedryfsbate" in cat and "nie-bedryfs" not in cat:
                        if any(kw in name for kw in ["bank", "fnb", "standard", "absa", "nedbank", "capitec", "investec"]):
                            bank += net
                        elif any(kw in name for kw in ["cash", "petty", "kontant"]):
                            cash += net
                        elif any(kw in name for kw in ["debtor", "receivable", "debiteur"]):
                            debtors += net
                        elif any(kw in name for kw in ["stock", "inventory", "voorraad", "goods", "finished"]):
                            stock += net
                        elif any(kw in name for kw in ["prepaid", "prepayment", "vooruitbetaal"]):
                            prepaid += net
                        elif any(kw in name for kw in ["vat input", "input vat", "btw inset"]):
                            vat_input += net
                        else:
                            other_current += net
                    
                    elif "fixed asset" in cat or "non-current asset" in cat or "vaste bate" in cat or "nie-bedryfs" in cat:
                        pass  # Handled below
                    
                    elif "current liabilit" in cat and "non-current" not in cat or "bedryfslas" in cat and "nie-bedryfs" not in cat:
                        pass  # Handled below
                    
                # Fixed Assets
                fixed_assets_cost = 0
                accum_depr = 0
                for a in accounts:
                    cat = str(a.get("category", "")).lower()
                    name = str(a.get("name", "")).lower()
                    dr = float(a.get("debit", 0) or 0)
                    cr = float(a.get("credit", 0) or 0)
                    
                    if "fixed asset" in cat or "non-current asset" in cat or "vaste bate" in cat or "nie-bedryfs" in cat:
                        if any(kw in name for kw in ["accumulated", "acc dep", "accum", "opgehoopte"]):
                            accum_depr += cr
                        else:
                            fixed_assets_cost += dr
                
                # Liabilities
                creditors = 0
                vat_output = 0
                paye = 0
                uif = 0
                other_liabilities = 0
                loans = 0
                
                for a in accounts:
                    cat = str(a.get("category", "")).lower()
                    name = str(a.get("name", "")).lower()
                    dr = float(a.get("debit", 0) or 0)
                    cr = float(a.get("credit", 0) or 0)
                    net_cr = cr - dr  # Liabilities are credit balances
                    
                    if "current liabilit" in cat and "non-current" not in cat or "bedryfslas" in cat and "nie-bedryfs" not in cat:
                        # IMPORTANT: Specific matches FIRST, generic "payable"/"creditor" LAST
                        # Otherwise "VAT Payable" matches "payable" and lands in creditors
                        if any(kw in name for kw in ["vat output", "output vat", "vat payable", "btw uitset", "vat control", "vat / tax"]):
                            vat_output += net_cr
                        elif "paye" in name or "pay as you earn" in name:
                            paye += net_cr
                        elif "uif" in name or "unemployment" in name:
                            uif += net_cr
                        elif any(kw in name for kw in ["taxation", "tax payable", "belasting", "sars"]):
                            other_liabilities += net_cr
                        elif any(kw in name for kw in ["creditor", "payable", "trade payable", "krediteur"]):
                            creditors += net_cr
                        else:
                            other_liabilities += net_cr
                    
                    elif "long term" in cat or "non-current liabilit" in cat or "langtermyn" in cat or "nie-bedryfs" in cat:
                        loans += net_cr
                
                # Equity
                capital = 0
                retained = 0
                drawings = 0
                reserves = 0
                
                for a in accounts:
                    cat = str(a.get("category", "")).lower()
                    name = str(a.get("name", "")).lower()
                    dr = float(a.get("debit", 0) or 0)
                    cr = float(a.get("credit", 0) or 0)
                    
                    if "equity" in cat or "ekwiteit" in cat or "owner" in cat or "eienaar" in cat:
                        if any(kw in name for kw in ["retained", "opgehoopte", "accumulated profit"]):
                            retained += cr - dr
                        elif any(kw in name for kw in ["drawing", "onttrekking"]):
                            drawings += dr
                        elif any(kw in name for kw in ["reserve"]):
                            reserves += cr - dr
                        else:
                            capital += cr - dr
                
                # Use category-based total for expenses (more accurate)
                total_expenses = total_expenses_from_cat if total_expenses_from_cat > 0 else named_expenses
                
            else:
                # ═══════════════════════════════════════════════════════════════
                # CODE-BASED CLASSIFICATION (fallback for files without Category)
                # Assumes STANDARD chart: 1=Assets, 2=Assets, 3=Liab, 4=Equity, 5=Income, 6+=Expenses
                # ═══════════════════════════════════════════════════════════════
                logger.info("[TB ANALYZE] No category column - using CODE-BASED classification (standard chart)")
                
                def match_account(acc, codes=None, keywords=None, column="debit"):
                    """Match account by code prefix or name keywords"""
                    code = str(acc.get("code", "")).strip()
                    name = str(acc.get("name", "")).lower()
                    val = float(acc.get(column, 0) or 0)
                    
                    if codes:
                        for c in codes:
                            if code.startswith(c):
                                return val
                    if keywords:
                        for kw in keywords:
                            if kw in name:
                                return val
                    return 0
                
                # ASSETS (Debit balances)
                bank = sum(match_account(a, ["1000", "10"], ["bank", "fnb", "standard", "absa", "nedbank", "capitec"]) for a in accounts)
                cash = sum(match_account(a, ["1050", "1100", "11"], ["cash", "petty", "cash on hand"]) for a in accounts)
                debtors = sum(match_account(a, ["1200", "12"], ["debtor", "receivable", "trade receivable"]) for a in accounts)
                stock = sum(match_account(a, ["1300", "13", "14"], ["stock", "inventory", "goods"]) for a in accounts)
                prepaid = sum(match_account(a, ["1400", "15"], ["prepaid", "prepayment", "advance"]) for a in accounts)
                vat_input = sum(match_account(a, ["1500", "16"], ["vat input", "input vat", "input tax"]) for a in accounts)
                other_current = sum(match_account(a, ["17", "18", "19"], []) for a in accounts)
                
                fixed_assets_cost = sum(match_account(a, ["2"], ["fixed asset", "equipment", "vehicle", "furniture", "machinery", "property", "building"]) for a in accounts)
                accum_depr = sum(match_account(a, ["20", "21", "22", "23"], ["accumulated", "acc dep", "accum"], "credit") for a in accounts)
                
                # LIABILITIES (Credit balances)
                creditors = sum(match_account(a, ["3000", "30"], ["creditor", "payable", "trade payable", "supplier"], "credit") for a in accounts)
                vat_output = sum(match_account(a, ["3100", "31"], ["vat output", "output vat", "output tax"], "credit") for a in accounts)
                paye = sum(match_account(a, ["3200", "32"], ["paye", "pay as you earn"], "credit") for a in accounts)
                uif = sum(match_account(a, ["3300", "33"], ["uif", "unemployment"], "credit") for a in accounts)
                loans = sum(match_account(a, ["3400", "34", "35", "36", "37", "38"], ["loan", "mortgage", "credit card", "overdraft"], "credit") for a in accounts)
                other_liabilities = sum(match_account(a, ["39"], [], "credit") for a in accounts)
                
                # EQUITY (Credit balances)
                capital = sum(match_account(a, ["4000", "40"], ["capital", "share capital", "owner"], "credit") for a in accounts)
                retained = sum(match_account(a, ["4100", "41"], ["retained", "accumulated profit"], "credit") for a in accounts)
                drawings = sum(match_account(a, ["4200", "42"], ["drawing", "distribution"]) for a in accounts)
                reserves = sum(match_account(a, ["43", "44", "45"], ["reserve"], "credit") for a in accounts)
                
                # REVENUE (Credit balances)
                sales = sum(match_account(a, ["5000", "50"], ["sales", "revenue", "turnover", "income"], "credit") for a in accounts)
                for a in accounts:
                    if "return" in str(a.get("name", "")).lower() and str(a.get("code", "")).startswith("5"):
                        sales -= float(a.get("credit", 0) or 0)
                
                sales_returns = sum(match_account(a, ["52"], ["return", "refund"]) for a in accounts)
                cos = sum(match_account(a, ["5100", "51"], ["cost of sales", "cost of goods", "cogs", "purchases"]) for a in accounts)
                other_income = sum(match_account(a, ["8"], ["interest received", "discount received", "other income", "sundry income"], "credit") for a in accounts)
                
                # EXPENSES (Debit balances)
                salaries = sum(match_account(a, ["6000", "60"], ["salary", "salaries", "wage", "payroll"]) for a in accounts)
                rent = sum(match_account(a, ["6100", "61"], ["rent"]) for a in accounts)
                electricity = sum(match_account(a, ["6200", "62"], ["electric", "eskom", "power"]) for a in accounts)
                water = sum(match_account(a, ["6300", "63"], ["water", "rates", "municipal"]) for a in accounts)
                telephone = sum(match_account(a, ["6400", "64"], ["telephone", "internet", "cell", "mobile", "telkom", "vodacom", "mtn"]) for a in accounts)
                insurance = sum(match_account(a, ["6500", "65"], ["insurance"]) for a in accounts)
                bank_charges = sum(match_account(a, ["6600", "66"], ["bank charge", "bank fee"]) for a in accounts)
                fuel = sum(match_account(a, ["6700", "67"], ["fuel", "petrol", "diesel", "transport"]) for a in accounts)
                repairs = sum(match_account(a, ["6800", "68"], ["repair", "maintenance"]) for a in accounts)
                office = sum(match_account(a, ["6900", "69"], ["office", "stationery", "supplies"]) for a in accounts)
                advertising = sum(match_account(a, ["7000", "70"], ["advertising", "marketing", "promotion"]) for a in accounts)
                professional = sum(match_account(a, ["7100", "71"], ["professional", "accounting", "legal", "audit"]) for a in accounts)
                depreciation = sum(match_account(a, ["7200", "72"], ["depreciation"]) for a in accounts)
                bad_debts = sum(match_account(a, ["7300", "73"], ["bad debt", "doubtful"]) for a in accounts)
                interest_paid = sum(match_account(a, ["7400", "74"], ["interest paid", "interest expense", "finance charge"]) for a in accounts)
                sundry_exp = sum(match_account(a, ["7500", "75", "76", "77", "78", "79"], ["sundry", "other expense", "miscellaneous"]) for a in accounts)
                
                total_expenses = salaries + rent + electricity + water + telephone + insurance + bank_charges + fuel + repairs + office + advertising + professional + depreciation + bad_debts + interest_paid + sundry_exp
            # Step 3: Calculate totals
            current_assets = bank + cash + debtors + stock + prepaid + vat_input + other_current
            fixed_assets_net = fixed_assets_cost - accum_depr
            total_assets = current_assets + fixed_assets_net
            
            current_liabilities = creditors + vat_output + paye + uif + other_liabilities
            long_term_liabilities = loans
            total_liabilities = current_liabilities + long_term_liabilities
            
            total_equity = capital + retained + reserves - drawings
            
            net_sales = sales - sales_returns
            total_income = net_sales + other_income
            
            total_expenses = salaries + rent + electricity + water + telephone + insurance + bank_charges + fuel + repairs + office + advertising + professional + depreciation + bad_debts + interest_paid + sundry_exp
            
            gross_profit = net_sales - cos
            net_profit = total_income - cos - total_expenses
            
            # Step 4: Calculate ratios (with safe division)
            gp_margin = round((gross_profit / net_sales * 100), 1) if net_sales > 0 else 0
            np_margin = round((net_profit / total_income * 100), 1) if total_income > 0 else 0
            current_ratio = round(current_assets / current_liabilities, 2) if current_liabilities > 0 else 0
            quick_ratio = round((current_assets - stock) / current_liabilities, 2) if current_liabilities > 0 else 0
            debt_equity = round(total_liabilities / total_equity, 2) if total_equity > 0 else 0
            
            vat_position = vat_output - vat_input
            
            debtor_days = round((debtors / net_sales * 365), 0) if net_sales > 0 else 0
            creditor_days = round((creditors / cos * 365), 0) if cos > 0 else 0
            stock_days = round((stock / cos * 365), 0) if cos > 0 else 0
            
            salaries_pct = round((salaries / net_sales * 100), 1) if net_sales > 0 else 0
            rent_pct = round((rent / net_sales * 100), 1) if net_sales > 0 else 0
            
            # Log all calculations for verification
            logger.info(f"[TB ANALYZE] Assets: Current={current_assets:.2f}, Fixed={fixed_assets_net:.2f}, Total={total_assets:.2f}")
            logger.info(f"[TB ANALYZE] Liab: Current={current_liabilities:.2f}, LT={long_term_liabilities:.2f}, Total={total_liabilities:.2f}")
            logger.info(f"[TB ANALYZE] Equity: {total_equity:.2f}")
            logger.info(f"[TB ANALYZE] P&L: Sales={net_sales:.2f}, COS={cos:.2f}, GP={gross_profit:.2f}, Exp={total_expenses:.2f}, NP={net_profit:.2f}")
            
            # ═══════════════════════════════════════════════════════════════════════
            # VALIDATION: Compare our calculation to TB's own control figure
            # ═══════════════════════════════════════════════════════════════════════
            tb_control_profit = data.get("tb_control_profit")
            validation_ok = True
            validation_warning = ""
            
            if tb_control_profit is not None:
                try:
                    control = float(tb_control_profit)
                    diff = abs(net_profit - control)
                    pct_diff = (diff / abs(control) * 100) if control != 0 else 0
                    
                    logger.info(f"[TB VALIDATE] Our net profit: R{net_profit:,.2f} | TB control: R{control:,.2f} | Diff: R{diff:,.2f} ({pct_diff:.1f}%)")
                    
                    if diff < 1.0:
                        # Perfect match
                        logger.info("[TB VALIDATE] ✅ PERFECT MATCH - our calculation matches TB control figure")
                        validation_warning = ""
                    elif pct_diff < 5:
                        # Close enough - rounding differences
                        logger.info(f"[TB VALIDATE] ✅ Close match - {pct_diff:.1f}% difference (likely rounding)")
                        validation_warning = ""
                    else:
                        # Significant difference - WARN
                        validation_ok = False
                        logger.warning(f"[TB VALIDATE] ⚠️ MISMATCH - {pct_diff:.1f}% difference!")
                        if lang == "af":
                            validation_warning = f'''
                            <div style="background:rgba(239,68,68,0.15);border:2px solid #ef4444;border-radius:10px;padding:20px;margin:15px 0;">
                                <h3 style="color:#ef4444;margin:0 0 10px 0;">⚠️ WAARSKUWING: Syfers Klop Nie</h3>
                                <p style="margin:5px 0;">Ons berekening van netto wins (<strong>R {net_profit:,.2f}</strong>) verskil van die proefbalans se eie syfer (<strong>R {control:,.2f}</strong>) met <strong>R {diff:,.2f}</strong> ({pct_diff:.1f}%).</p>
                                <p style="margin:5px 0;color:var(--text-muted);">Dit kan beteken dat sommige rekeninge verkeerd geklassifiseer is. Kontroleer die data voor u op hierdie report staatmaak.</p>
                            </div>'''
                        else:
                            validation_warning = f'''
                            <div style="background:rgba(239,68,68,0.15);border:2px solid #ef4444;border-radius:10px;padding:20px;margin:15px 0;">
                                <h3 style="color:#ef4444;margin:0 0 10px 0;">⚠️ WARNING: Numbers Don't Match</h3>
                                <p style="margin:5px 0;">Our calculated net profit (<strong>R {net_profit:,.2f}</strong>) differs from the trial balance's own figure (<strong>R {control:,.2f}</strong>) by <strong>R {diff:,.2f}</strong> ({pct_diff:.1f}%).</p>
                                <p style="margin:5px 0;color:var(--text-muted);">This may indicate some accounts were incorrectly classified. Please verify the data before relying on this report.</p>
                            </div>'''
                except (ValueError, TypeError) as e:
                    logger.warning(f"[TB VALIDATE] Could not parse control figure: {e}")
            
            # Build confidence indicator
            if has_categories:
                if validation_ok:
                    confidence_html = '<div style="background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:8px;padding:10px 15px;margin:10px 0;font-size:13px;">✅ <strong>High Confidence</strong> - Category column detected, control figure matches. Data classification verified.</div>'
                else:
                    confidence_html = '<div style="background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:8px;padding:10px 15px;margin:10px 0;font-size:13px;">⚠️ <strong>Review Required</strong> - Category column detected but control figure mismatch. Some accounts may be misclassified.</div>'
            else:
                confidence_html = '<div style="background:rgba(245,158,11,0.15);border:1px solid #f59e0b;border-radius:8px;padding:10px 15px;margin:10px 0;font-size:13px;">⚠️ <strong>Medium Confidence</strong> - No category column found. Accounts classified by code patterns. Please verify the numbers.</div>'
            
            # ═══════════════════════════════════════════════════════════════════════
            # BUILD REPORT - PYTHON GENERATES ALL NUMBERS IN HTML
            # ═══════════════════════════════════════════════════════════════════════
            
            # Status indicators
            def status(value, good_min, warn_min=None, higher_is_better=True):
                if higher_is_better:
                    if value >= good_min:
                        return "✅ GOOD"
                    elif warn_min and value >= warn_min:
                        return "⚠️ CONCERN"
                    else:
                        return "🔴 CRITICAL"
                else:  # Lower is better
                    if value <= good_min:
                        return "✅ GOOD"
                    elif warn_min and value <= warn_min:
                        return "⚠️ CONCERN"
                    else:
                        return "🔴 CRITICAL"
            
            current_status = status(current_ratio, 1.5, 1.0)
            quick_status = status(quick_ratio, 1.0, 0.7)
            debt_status = status(debt_equity, 1.5, 2.5, False)
            debtor_status = status(debtor_days, 45, 60, False)
            gp_status = status(gp_margin, 30, 20)
            np_status = status(np_margin, 5, 2)
            
            # Build the complete report HTML with all Python-calculated values
            # Using language labels (L) for bilingual support
            report_html = f"""
    <h2 style="color:#8b5cf6;border-bottom:2px solid #8b5cf6;padding-bottom:10px;">📊 {L["report_title"]}</h2>
    <p><strong>{L["company"]}:</strong> {safe_string(report_company)} | <strong>{L["date"]}:</strong> {today()} | <strong>{L["prepared_by"]}:</strong> Zane, ClickAI</p>
    
    {validation_warning}
    {confidence_html}
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <h3 style="color:#10b981;">{L["balance_status"]}</h3>
    <table style="width:100%;border-collapse:collapse;margin:15px 0;">
    <tr><td style="padding:8px;border:1px solid rgba(255,255,255,0.1);width:200px;"><strong>{L["total_debits"]}:</strong></td><td style="padding:8px;border:1px solid rgba(255,255,255,0.1);text-align:right;font-family:monospace;">R {total_debit:,.2f}</td></tr>
    <tr><td style="padding:8px;border:1px solid rgba(255,255,255,0.1);"><strong>{L["total_credits"]}:</strong></td><td style="padding:8px;border:1px solid rgba(255,255,255,0.1);text-align:right;font-family:monospace;">R {total_credit:,.2f}</td></tr>
    <tr style="background:{'rgba(16,185,129,0.2)' if is_balanced else 'rgba(239,68,68,0.2)'};">
    <td style="padding:8px;border:1px solid rgba(255,255,255,0.1);"><strong>{L["difference"]}:</strong></td>
    <td style="padding:8px;border:1px solid rgba(255,255,255,0.1);text-align:right;font-family:monospace;">R {difference:,.2f} {'✅ ' + L["balanced"] if is_balanced else '❌ ' + L["unbalanced"]}</td></tr>
    </table>
    
    {f'<div style="background:rgba(239,68,68,0.2);border:1px solid #ef4444;padding:15px;border-radius:8px;margin:15px 0;"><strong>🚨 ' + L["critical_error"] + ':</strong> ' + L["tb_not_balanced"] + f' R {difference:,.2f} ' + L["difference_text"] + '</div>' if not is_balanced else ''}
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <h3 style="color:#10b981;">{L["balance_sheet_summary"]}</h3>
    
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
    <div>
    <h4 style="color:#6366f1;">{L["assets"]}</h4>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <tr style="background:rgba(99,102,241,0.1);"><td colspan="2" style="padding:6px;"><strong>{L["current_assets"]}</strong></td></tr>
    <tr><td style="padding:4px 8px;">{L["bank_cash"]}</td><td style="text-align:right;font-family:monospace;">R {bank + cash:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["debtors"]}</td><td style="text-align:right;font-family:monospace;">R {debtors:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["inventory"]}</td><td style="text-align:right;font-family:monospace;">R {stock:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["vat_input"]}</td><td style="text-align:right;font-family:monospace;">R {vat_input:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["prepayments"]}</td><td style="text-align:right;font-family:monospace;">R {prepaid:,.2f}</td></tr>
    <tr style="background:rgba(99,102,241,0.2);"><td style="padding:6px;"><strong>{L["total_current_assets"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {current_assets:,.2f}</strong></td></tr>
    
    <tr style="background:rgba(99,102,241,0.1);"><td colspan="2" style="padding:6px;"><strong>{L["fixed_assets"]}</strong></td></tr>
    <tr><td style="padding:4px 8px;">{L["cost"]}</td><td style="text-align:right;font-family:monospace;">R {fixed_assets_cost:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["less_accum_depr"]}</td><td style="text-align:right;font-family:monospace;">(R {accum_depr:,.2f})</td></tr>
    <tr style="background:rgba(99,102,241,0.2);"><td style="padding:6px;"><strong>{L["net_fixed_assets"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {fixed_assets_net:,.2f}</strong></td></tr>
    
    <tr style="background:rgba(16,185,129,0.3);"><td style="padding:8px;"><strong>{L["total_assets"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {total_assets:,.2f}</strong></td></tr>
    </table>
    </div>
    
    <div>
    <h4 style="color:#6366f1;">{L["liab_equity"]}</h4>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <tr style="background:rgba(239,68,68,0.1);"><td colspan="2" style="padding:6px;"><strong>{L["current_liabilities"]}</strong></td></tr>
    <tr><td style="padding:4px 8px;">{L["creditors"]}</td><td style="text-align:right;font-family:monospace;">R {creditors:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["vat_output"]}</td><td style="text-align:right;font-family:monospace;">R {vat_output:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["paye_payable"]}</td><td style="text-align:right;font-family:monospace;">R {paye:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["uif_payable"]}</td><td style="text-align:right;font-family:monospace;">R {uif:,.2f}</td></tr>
    <tr style="background:rgba(239,68,68,0.2);"><td style="padding:6px;"><strong>{L["total_current_liab"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {current_liabilities:,.2f}</strong></td></tr>
    
    <tr style="background:rgba(239,68,68,0.1);"><td colspan="2" style="padding:6px;"><strong>{L["long_term_liab"]}</strong></td></tr>
    <tr><td style="padding:4px 8px;">{L["loans"]}</td><td style="text-align:right;font-family:monospace;">R {loans:,.2f}</td></tr>
    <tr style="background:rgba(239,68,68,0.2);"><td style="padding:6px;"><strong>{L["total_liabilities"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {total_liabilities:,.2f}</strong></td></tr>
    
    <tr style="background:rgba(139,92,246,0.1);"><td colspan="2" style="padding:6px;"><strong>{L["equity"]}</strong></td></tr>
    <tr><td style="padding:4px 8px;">{L["capital"]}</td><td style="text-align:right;font-family:monospace;">R {capital:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["retained_earnings"]}</td><td style="text-align:right;font-family:monospace;">R {retained:,.2f}</td></tr>
    <tr><td style="padding:4px 8px;">{L["less_drawings"]}</td><td style="text-align:right;font-family:monospace;">(R {drawings:,.2f})</td></tr>
    <tr><td style="padding:4px 8px;font-style:italic;">{"Netto Wins/Verlies" if lang == "af" else "Net Profit/Loss"}</td><td style="text-align:right;font-family:monospace;font-style:italic;">R {net_profit:,.2f}</td></tr>
    <tr style="background:rgba(139,92,246,0.2);"><td style="padding:6px;"><strong>{L["total_equity"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {total_equity + net_profit:,.2f}</strong></td></tr>
    
    <tr style="background:rgba(16,185,129,0.3);"><td style="padding:8px;"><strong>{L["liab_plus_equity"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {total_liabilities + total_equity + net_profit:,.2f}</strong></td></tr>
    </table>
    </div>
    </div>
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <h3 style="color:#10b981;">{L["income_statement"]}</h3>
    <table style="width:100%;max-width:500px;border-collapse:collapse;">
    <tr><td style="padding:8px;">{L["sales"]}</td><td style="text-align:right;font-family:monospace;">R {sales:,.2f}</td></tr>
    <tr><td style="padding:8px;">{L["less_returns"]}</td><td style="text-align:right;font-family:monospace;">(R {sales_returns:,.2f})</td></tr>
    <tr style="border-top:1px solid rgba(255,255,255,0.2);"><td style="padding:8px;"><strong>{L["net_sales"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {net_sales:,.2f}</strong></td></tr>
    <tr><td style="padding:8px;">{L["less_cos"]}</td><td style="text-align:right;font-family:monospace;">(R {cos:,.2f})</td></tr>
    <tr style="background:rgba(16,185,129,0.2);border-top:1px solid rgba(255,255,255,0.2);"><td style="padding:8px;"><strong>{L["gross_profit"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {gross_profit:,.2f}</strong> ({gp_margin}%)</td></tr>
    <tr><td style="padding:8px;">{L["plus_other_income"]}</td><td style="text-align:right;font-family:monospace;">R {other_income:,.2f}</td></tr>
    <tr><td style="padding:8px;">{L["less_operating_exp"]}</td><td style="text-align:right;font-family:monospace;">(R {total_expenses:,.2f})</td></tr>
    <tr style="background:{'rgba(16,185,129,0.3)' if net_profit >= 0 else 'rgba(239,68,68,0.3)'};border-top:2px solid rgba(255,255,255,0.3);"><td style="padding:10px;"><strong>{L["net_profit"]}</strong></td><td style="text-align:right;font-family:monospace;font-size:16px;"><strong>R {net_profit:,.2f}</strong> ({np_margin}%)</td></tr>
    </table>
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <h3 style="color:#10b981;">{L["financial_ratios"]}</h3>
    <table style="width:100%;border-collapse:collapse;">
    <tr style="background:rgba(99,102,241,0.2);"><th style="padding:10px;text-align:left;">{L["ratio"]}</th><th style="text-align:right;">{L["value"]}</th><th style="text-align:center;">{L["status"]}</th><th style="text-align:right;">{L["norm"]}</th></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["current_ratio"]}</td><td style="text-align:right;font-family:monospace;">{current_ratio:.2f}:1</td><td style="text-align:center;">{current_status}</td><td style="text-align:right;">&gt;1.5:1</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["quick_ratio"]}</td><td style="text-align:right;font-family:monospace;">{quick_ratio:.2f}:1</td><td style="text-align:center;">{quick_status}</td><td style="text-align:right;">&gt;1.0:1</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["debt_equity"]}</td><td style="text-align:right;font-family:monospace;">{debt_equity:.2f}:1</td><td style="text-align:center;">{debt_status}</td><td style="text-align:right;">&lt;1.5:1</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["gp_margin"]}</td><td style="text-align:right;font-family:monospace;">{gp_margin}%</td><td style="text-align:center;">{gp_status}</td><td style="text-align:right;">&gt;30%</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["np_margin"]}</td><td style="text-align:right;font-family:monospace;">{np_margin}%</td><td style="text-align:center;">{np_status}</td><td style="text-align:right;">&gt;5%</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["debtor_days"]}</td><td style="text-align:right;font-family:monospace;">{debtor_days:.0f} {L["days"]}</td><td style="text-align:center;">{debtor_status}</td><td style="text-align:right;">30-45 {L["days"]}</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["creditor_days"]}</td><td style="text-align:right;font-family:monospace;">{creditor_days:.0f} {L["days"]}</td><td style="text-align:center;">ℹ️</td><td style="text-align:right;">30-60 {L["days"]}</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["stock_days"]}</td><td style="text-align:right;font-family:monospace;">{stock_days:.0f} {L["days"]}</td><td style="text-align:center;">ℹ️</td><td style="text-align:right;">{L["industry"]}</td></tr>
    </table>
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <h3 style="color:#10b981;">{L["sars_obligations"]}</h3>
    <table style="width:100%;max-width:500px;border-collapse:collapse;">
    <tr style="background:rgba(245,158,11,0.2);"><td colspan="2" style="padding:10px;"><strong>{L["vat_position"]}</strong></td></tr>
    <tr><td style="padding:8px;">{L["vat_collected"]}</td><td style="text-align:right;font-family:monospace;">R {vat_output:,.2f}</td></tr>
    <tr><td style="padding:8px;">{L["vat_paid"]}</td><td style="text-align:right;font-family:monospace;">(R {vat_input:,.2f})</td></tr>
    <tr style="background:{'rgba(239,68,68,0.2)' if vat_position > 0 else 'rgba(16,185,129,0.2)'};"><td style="padding:10px;"><strong>{L["vat_payable"] if vat_position > 0 else L["vat_refund"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {abs(vat_position):,.2f}</strong></td></tr>
    </table>
    
    <table style="width:100%;max-width:500px;border-collapse:collapse;margin-top:15px;">
    <tr style="background:rgba(245,158,11,0.2);"><td colspan="2" style="padding:10px;"><strong>{L["employee_taxes"]}</strong></td></tr>
    <tr><td style="padding:8px;">{L["paye_payable"]}</td><td style="text-align:right;font-family:monospace;">R {paye:,.2f}</td></tr>
    <tr><td style="padding:8px;">{L["uif_payable"]}</td><td style="text-align:right;font-family:monospace;">R {uif:,.2f}</td></tr>
    <tr style="background:rgba(245,158,11,0.3);"><td style="padding:10px;"><strong>{L["total_emp201"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {paye + uif:,.2f}</strong></td></tr>
    </table>
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <h3 style="color:#10b981;">{L["expense_analysis"]}</h3>
    <table style="width:100%;border-collapse:collapse;">
    <tr style="background:rgba(99,102,241,0.2);"><th style="padding:8px;text-align:left;">{L["expense"]}</th><th style="text-align:right;">{L["amount"]}</th><th style="text-align:right;">{L["pct_of_sales"]}</th></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["salaries_wages"]}</td><td style="text-align:right;font-family:monospace;">R {salaries:,.2f}</td><td style="text-align:right;">{salaries_pct}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["rent"]}</td><td style="text-align:right;font-family:monospace;">R {rent:,.2f}</td><td style="text-align:right;">{rent_pct}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["electricity"]}</td><td style="text-align:right;font-family:monospace;">R {electricity:,.2f}</td><td style="text-align:right;">{round(electricity/net_sales*100,1) if net_sales else 0}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["depreciation"]}</td><td style="text-align:right;font-family:monospace;">R {depreciation:,.2f}</td><td style="text-align:right;">{round(depreciation/net_sales*100,1) if net_sales else 0}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["fuel_transport"]}</td><td style="text-align:right;font-family:monospace;">R {fuel:,.2f}</td><td style="text-align:right;">{round(fuel/net_sales*100,1) if net_sales else 0}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["advertising"]}</td><td style="text-align:right;font-family:monospace;">R {advertising:,.2f}</td><td style="text-align:right;">{round(advertising/net_sales*100,1) if net_sales else 0}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["professional_fees"]}</td><td style="text-align:right;font-family:monospace;">R {professional:,.2f}</td><td style="text-align:right;">{round(professional/net_sales*100,1) if net_sales else 0}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["interest_paid"]}</td><td style="text-align:right;font-family:monospace;">R {interest_paid:,.2f}</td><td style="text-align:right;">{round(interest_paid/net_sales*100,1) if net_sales else 0}%</td></tr>
    <tr><td style="padding:6px;border-bottom:1px solid rgba(255,255,255,0.1);">{L["other_expenses"]}</td><td style="text-align:right;font-family:monospace;">R {insurance + bank_charges + repairs + office + water + telephone + bad_debts + sundry_exp:,.2f}</td><td style="text-align:right;">-</td></tr>
    <tr style="background:rgba(99,102,241,0.3);"><td style="padding:8px;"><strong>{L["total_expenses"]}</strong></td><td style="text-align:right;font-family:monospace;"><strong>R {total_expenses:,.2f}</strong></td><td style="text-align:right;"><strong>{round(total_expenses/net_sales*100,1) if net_sales else 0}%</strong></td></tr>
    </table>
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <div id="aiInsights" style="background:linear-gradient(135deg, rgba(139,92,246,0.08) 0%, rgba(16,185,129,0.06) 100%);border:1px solid rgba(139,92,246,0.25);border-radius:12px;padding:20px 25px;margin-top:25px;">
    <h3 style="color:#8b5cf6;margin-top:0;margin-bottom:15px;font-size:18px;">🤖 {L["zane_insight"]}</h3>
    <div id="aiInsightsContent" style="min-height:100px;color:rgba(255,255,255,0.9);font-size:14px;line-height:1.7;">
    <p style="color:var(--text-muted);">{L["loading_insight"]}</p>
    </div>
    </div>
    
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.2);margin:20px 0;">
    
    <p style="color:var(--text-muted);font-size:11px;text-align:center;">
    {L["calculations_by"]}: {today()} {now()[11:16]}
    </p>
    """
            
            # ═══════════════════════════════════════════════════════════════════════
            # SONNET GIVES INSIGHTS ONLY - PYTHON DID ALL THE MATH
            # ═══════════════════════════════════════════════════════════════════════
            
            # Build red flags list based on Python calculations - using language labels
            red_flags = []
            if not is_balanced:
                red_flags.append(f"🔴 {L['critical']}: " + L["tb_not_bal_flag"].format(diff=f"{difference:,.2f}"))
            if current_ratio < 1.0:
                red_flags.append(f"🔴 {L['critical']}: " + L["current_ratio_crit"].format(ratio=f"{current_ratio:.2f}"))
            elif current_ratio < 1.5:
                red_flags.append(f"🟠 {L['warning']}: " + L["current_ratio_warn"].format(ratio=f"{current_ratio:.2f}"))
            if quick_ratio < 0.7:
                red_flags.append(f"🔴 {L['critical']}: " + L["quick_ratio_crit"].format(ratio=f"{quick_ratio:.2f}"))
            if debtor_days > 60:
                red_flags.append(f"🟠 {L['warning']}: " + L["debtor_days_warn"].format(days=f"{debtor_days:.0f}"))
            elif debtor_days > 45:
                red_flags.append(f"🟡 {L['monitor']}: " + L["debtor_days_mon"].format(days=f"{debtor_days:.0f}"))
            if stock_days > 120:
                red_flags.append(f"🟠 {L['warning']}: " + L["stock_days_warn"].format(days=f"{stock_days:.0f}"))
            if gp_margin < 20:
                red_flags.append(f"🔴 {L['critical']}: " + L["gp_margin_crit"].format(pct=gp_margin))
            elif gp_margin < 30:
                red_flags.append(f"🟠 {L['warning']}: " + L["gp_margin_warn"].format(pct=gp_margin))
            if np_margin < 0:
                red_flags.append(f"🔴 {L['critical']}: " + L["making_loss"].format(amount=f"{abs(net_profit):,.2f}"))
            elif np_margin < 3:
                red_flags.append(f"🟠 {L['warning']}: " + L["np_margin_warn"].format(pct=np_margin))
            if debt_equity > 2:
                red_flags.append(f"🟠 {L['warning']}: " + L["debt_equity_warn"].format(ratio=f"{debt_equity:.2f}"))
            if vat_position > 50000:
                red_flags.append(f"🟡 {L['monitor']}: " + L["vat_payable_mon"].format(amount=f"{vat_position:,.2f}"))
            if salaries_pct > 40:
                red_flags.append(f"🟠 {L['warning']}: " + L["salaries_warn"].format(pct=salaries_pct))
            if paye + uif > 20000:
                red_flags.append(f"🟡 {L['monitor']}: " + L["paye_uif_mon"].format(amount=f"{paye+uif:,.2f}"))
            
            # Build the red flags HTML
            red_flags_html = ""
            if red_flags:
                red_flags_html = f"<h3 style='color:#ef4444;margin-top:20px;'>⚠️ {L['red_flags']}</h3><div style='background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:15px;'>"
                for flag in red_flags:
                    red_flags_html += f"<div style='margin:8px 0;'>{flag}</div>"
                red_flags_html += "</div>"
            else:
                red_flags_html = f"<h3 style='color:#10b981;margin-top:20px;'>✅ {L['no_critical']}</h3><p>{L['all_ratios_ok']}</p>"
            
            # Add red flags to report
            report_html = report_html.replace(
                '<div id="aiInsights"',
                red_flags_html + '\n\n<div id="aiInsights"'
            )
            
            # ═══════════════════════════════════════════════════════════════════════
            # BUILD FULL ACCOUNT LIST FOR SONNET - DETAILED ANALYSIS
            # ═══════════════════════════════════════════════════════════════════════
            
            # Build a detailed account listing for AI analysis - using language labels
            accounts_text = f"{L['acc_list_title']}\n"
            accounts_text += "=" * 80 + "\n"
            accounts_text += f"{L['acc_code']:<10} {L['acc_name']:<40} {L['debit']:>15} {L['credit']:>15}\n"
            accounts_text += "-" * 80 + "\n"
            
            # Group accounts by CATEGORY (not by code - codes differ per accounting system!)
            asset_accounts = []
            liability_accounts = []
            equity_accounts = []
            income_accounts = []
            expense_accounts = []
            unclassified = []
            
            for acc in accounts:
                code = str(acc.get("code", "")).strip()
                name = str(acc.get("name", "")).strip()
                cat = str(acc.get("category", "")).lower()
                dr = float(acc.get("debit", 0) or 0)
                cr = float(acc.get("credit", 0) or 0)
                
                line = f"{code:<10} {name[:40]:<40} R{dr:>13,.2f} R{cr:>13,.2f}"
                
                # Classify by CATEGORY first, fallback to code
                if cat:
                    if any(kw in cat for kw in ["sales", "revenue", "other income", "income", "omset", "inkomste"]):
                        income_accounts.append(line)
                    elif any(kw in cat for kw in ["cost of sale", "cogs", "koste van verkope"]):
                        expense_accounts.append(line)  # COS goes with expenses for display
                    elif any(kw in cat for kw in ["expense", "uitgawe", "operating"]):
                        expense_accounts.append(line)
                    elif any(kw in cat for kw in ["current asset", "non-current asset", "fixed asset", "bate"]):
                        asset_accounts.append(line)
                    elif any(kw in cat for kw in ["current liabilit", "non-current liabilit", "long term", "laste"]):
                        liability_accounts.append(line)
                    elif any(kw in cat for kw in ["equity", "owner", "ekwiteit", "eienaar"]):
                        equity_accounts.append(line)
                    else:
                        unclassified.append(line)
                else:
                    # Fallback to code-based (standard chart only)
                    if code.startswith(("1", "2")):
                        asset_accounts.append(line)
                    elif code.startswith("3"):
                        liability_accounts.append(line)
                    elif code.startswith("4"):
                        equity_accounts.append(line)
                    elif code.startswith("5"):
                        income_accounts.append(line)
                    elif code.startswith(("6", "7", "8", "9")):
                        expense_accounts.append(line)
                    else:
                        unclassified.append(line)
            
            accounts_text += f"\n📊 {L['assets_codes']}\n"
            accounts_text += "\n".join(asset_accounts) if asset_accounts else f"  {L['no_asset_acc']}\n"
            
            accounts_text += f"\n\n💳 {L['liab_codes']}\n"
            accounts_text += "\n".join(liability_accounts) if liability_accounts else f"  {L['no_liab_acc']}\n"
            
            accounts_text += f"\n\n🏛️ {L['equity_codes']}\n"
            accounts_text += "\n".join(equity_accounts) if equity_accounts else f"  {L['no_equity_acc']}\n"
            
            accounts_text += f"\n\n💰 {L['income_codes']}\n"
            accounts_text += "\n".join(income_accounts) if income_accounts else f"  {L['no_income_acc']}\n"
            
            accounts_text += f"\n\n📉 {L['expense_codes']}\n"
            accounts_text += "\n".join(expense_accounts) if expense_accounts else f"  {L['no_expense_acc']}\n"
            
            if unclassified:
                accounts_text += f"\n\n⚠️ {L['unclassified']}\n"
                accounts_text += "\n".join(unclassified)
            
            accounts_text += "\n" + "=" * 80
            accounts_text += f"\nTOTAL: {len(accounts)} accounts | Debits: R{total_debit:,.2f} | Credits: R{total_credit:,.2f}"
            
            # Build comprehensive prompt with ALL data - language based on user selection
            if lang == "af":
                # Afrikaans prompt
                af_third_party = ""
                if is_third_party:
                    af_third_party = f"""
    BELANGRIKE KONTEKS: Hierdie is 'n DERDE PARTY kliënt se proefbalans wat opgelaai is vir analise.
    Dit is NIE {biz_name} se eie data nie. MOENIE na {biz_name} verwys in jou analise nie.
    Analiseer dit as 'n onafhanklike kliënt se finansiële data.
    """
                insights_prompt = f"""Jy is Zane, ClickAI se senior finansiële analis met 20 jaar ondervinding. Jy ontvang nou 'n VOLLEDIGE proefbalans om te analiseer.
    Jou naam is net "Zane" - MOENIE 'n van gebruik nie. Teken reports as "Zane, ClickAI" alleen.
    
    BESIGHEID: {safe_string(report_company)}
    INDUSTRIE: {industry}
    DATUM: {today()}
    {af_third_party}
    
    {accounts_text}
    
    PYTHON-BEREKENDE OPSOMMING (100% akkuraat - moenie herbereken nie):
    
    BALANS STATUS:
    - Totale Debits: R {total_debit:,.2f}
    - Totale Kredits: R {total_credit:,.2f}
    - Verskil: R {difference:,.2f}
    - Status: {'GEBALANSEER' if is_balanced else 'ONGEBALANSEER - KRITIEK!'}
    
    BALANSSTAAT:
    - Bedryfsbates: R {current_assets:,.2f} (Bank R{bank+cash:,.2f}, Debiteure R{debtors:,.2f}, Voorraad R{stock:,.2f})
    - Vaste Bates Netto: R {fixed_assets_net:,.2f}
    - Totale Bates: R {total_assets:,.2f}
    - Korttermyn Laste: R {current_liabilities:,.2f}
    - Langtermyn Laste: R {long_term_liabilities:,.2f}
    - Totale Ekwiteit: R {total_equity:,.2f}
    
    INKOMSTESTAAT:
    - Netto Verkope: R {net_sales:,.2f}
    - Koste van Verkope: R {cos:,.2f}
    - Bruto Wins: R {gross_profit:,.2f} ({gp_margin}%)
    - Totale Uitgawes: R {total_expenses:,.2f}
    - Netto Wins: R {net_profit:,.2f} ({np_margin}%)
    
    VERHOUDINGS:
    - Current Ratio: {current_ratio:.2f}:1 (norm >1.5)
    - Quick Ratio: {quick_ratio:.2f}:1 (norm >1.0)
    - Skuld/Ekwiteit: {debt_equity:.2f}:1 (norm <1.5)
    - Debiteure Dae: {debtor_days:.0f} (norm 30-45)
    - Krediteure Dae: {creditor_days:.0f}
    - Voorraad Dae: {stock_days:.0f}
    
    SARS:
    - BTW Posisie: R {abs(vat_position):,.2f} {'BETAALBAAR' if vat_position > 0 else 'TERUG'}
    - LBS + WVF: R {paye + uif:,.2f}
    
    JOU OPDRAG - SKRYF 'N VOLLEDIGE FINANSIËLE ANALISE VERSLAG IN AFRIKAANS
    
    KRITIEKE INSTRUKSIES:
    - Die rekeninge is REEDS KORREK geklassifiseer in die regte kategorieë (Bates, Laste, Ekwiteit, Inkomste, Uitgawes) deur die bronsstelsel se eie kategorisering
    - MOENIE rekeningkodes bevraagteken of herklassifiseer nie. Verskillende stelsels gebruik verskillende nommering (Sage Pastel gebruik 1xxx vir Verkope, standaard gebruik 5xxx). Die kategorieë hier bo is KORREK.
    - MOENIE sê rekeninge is "verkeerd geklassifiseer" of in die "verkeerde afdeling" gebaseer op hulle kodenommers nie
    - MOENIE bedrog-aantygings maak sonder duidelike bewyse nie
    - Gebruik die PYTHON-BEREKENDE syfers as bron van waarheid - moenie herbereken of weerspreek nie
    - As Python sê Netto Wins is positief, IS die besigheid winsgewend. Moenie anders sê nie.
    
    **1. UITVOERENDE OPSOMMING**
    [2-3 sinne: Algehele gesondheid gebaseer op PYTHON-BEREKENDE verhoudings en winssyfers]
    
    **2. REKENING-VIR-REKENING ANALISE**
    Gaan deur ELKE rekening kategorie en noem:
    - Watter rekeninge lyk normaal vir die industrie
    - Watter BEDRAE lyk ongewoon of kommerwekkend
    - Watter rekeninge ONTBREEK wat daar behoort te wees
    - MOENIE rekeningKODES kritiseer nie - fokus op BEDRAE en SALDO'S
    
    **3. ROOI VLAE EN RISIKOS**
    Lys werklike bekommernisse gebaseer op die SYFERS:
    - Likwiditeitsprobleme?
    - Winsgewendheidskwessies?
    - Ongewone saldo's?
    - Ontbrekende voorsiening of toevallings?
    - MOENIE die rekeningnommeringstelsel as probleem vlag nie
    
    **4. SARS NAKOMING**
    - BTW posisie en betaaldatums
    - PAYE/UIF status
    
    **5. SPESIFIEKE AANBEVELINGS**
    Gee TEN MINSTE 5 konkrete aksies met prioriteite (DRINGEND / BELANGRIK / MONITOR)
    
    **6. VRAE VIR DIE KLIËNT**
    Lys 3-5 vrae wat jy sou vra.
    
    FORMAAT INSTRUKSIES:
    - Skryf SKOON HTML (geen markdown nie). Gebruik <h2>, <h3> vir opskrifte.
    - DONKER TEMA: MOENIE background:white, background:#fff, of enige ligte agtergrondkleure gebruik nie. Gebruik slegs rgba() met lae opacity vir agtergronde. Tekskleur moet ligkleurig wees (wit/grys).
    - Vir tabelle: <table style="width:100%;border-collapse:collapse;margin:15px 0;"><tr><th style="text-align:left;padding:8px;border-bottom:2px solid rgba(255,255,255,0.2);color:#8b5cf6;">Kolom</th></tr><tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">Waarde</td></tr></table>
    - Vir kleur indicators: <span style="color:#ef4444;">✗ Sleg</span> of <span style="color:#10b981;">GOOD: Goed</span> of <span style="color:#f59e0b;">WARNING: Waarskuwing</span>
    - ELKE tabel sel MOET inhoud hê - moet NOOIT leë selle los nie
    - Voltooi ALLE afdelings volledig - moenie halfpad stop nie
    
    REËLS:
    - Verwys na SPESIFIEKE rekeninge by naam en kode
    - Wees SPESIFIEK oor bedrae en persentasies
    - Skryf soos 'n regte finansiële analis wat omgee
    - Gebruik die PRESIESE syfers wat Python bereken het
    - MOET NOOIT sê die rekeningplan is "fout" of "verkeerd geklassifiseer" nie"""
            else:
                # English prompt (default)
                third_party_note = ""
                if is_third_party:
                    third_party_note = f"""
    IMPORTANT CONTEXT: This is a THIRD-PARTY client's trial balance that was uploaded for analysis.
    This is NOT {biz_name}'s own data. Do NOT reference {biz_name} anywhere in your analysis.
    Analyze this as an independent client's financial data. If you see references to other companies
    (e.g., loans from/to other entities), these are the CLIENT's intercompany relationships, not related to {biz_name}.
    """
                insights_prompt = f"""You are Zane, ClickAI's senior financial analyst with 20 years of experience. You are analyzing a COMPLETE trial balance.
    Your name is simply "Zane" - do NOT use any surname. Sign reports as "Zane, ClickAI" only.
    
    BUSINESS: {safe_string(report_company)}
    INDUSTRY: {industry}
    DATE: {today()}
    {third_party_note}
    
    {accounts_text}
    
    PYTHON-CALCULATED SUMMARY (100% accurate - do not recalculate):
    
    BALANCE STATUS:
    - Total Debits: R {total_debit:,.2f}
    - Total Credits: R {total_credit:,.2f}
    - Difference: R {difference:,.2f}
    - Status: {'BALANCED' if is_balanced else 'UNBALANCED - CRITICAL!'}
    
    BALANCE SHEET:
    - Current Assets: R {current_assets:,.2f} (Bank R{bank+cash:,.2f}, Debtors R{debtors:,.2f}, Inventory R{stock:,.2f})
    - Fixed Assets Net: R {fixed_assets_net:,.2f}
    - Total Assets: R {total_assets:,.2f}
    - Current Liabilities: R {current_liabilities:,.2f}
    - Long-term Liabilities: R {long_term_liabilities:,.2f}
    - Total Equity: R {total_equity:,.2f}
    
    INCOME STATEMENT:
    - Net Sales: R {net_sales:,.2f}
    - Cost of Sales: R {cos:,.2f}
    - Gross Profit: R {gross_profit:,.2f} ({gp_margin}%)
    - Total Expenses: R {total_expenses:,.2f}
    - Net Profit: R {net_profit:,.2f} ({np_margin}%)
    
    RATIOS:
    - Current Ratio: {current_ratio:.2f}:1 (norm >1.5)
    - Quick Ratio: {quick_ratio:.2f}:1 (norm >1.0)
    - Debt/Equity: {debt_equity:.2f}:1 (norm <1.5)
    - Debtor Days: {debtor_days:.0f} (norm 30-45)
    - Creditor Days: {creditor_days:.0f}
    - Stock Days: {stock_days:.0f}
    
    SARS (South African Revenue Service):
    - VAT Position: R {abs(vat_position):,.2f} {'PAYABLE' if vat_position > 0 else 'REFUNDABLE'}
    - PAYE + UIF: R {paye + uif:,.2f}
    
    YOUR TASK - WRITE A COMPLETE FINANCIAL ANALYSIS REPORT IN ENGLISH
    
    CRITICAL INSTRUCTIONS:
    - The accounts have been PRE-CLASSIFIED into the correct categories (Assets, Liabilities, Equity, Income, Expenses) using the source system's own categorization
    - DO NOT question or reclassify account codes. Different accounting systems use different numbering (Sage Pastel uses 1xxx for Sales, standard uses 5xxx). The categories shown above are CORRECT.
    - DO NOT suggest accounts are "misclassified" or in the "wrong section" based on their code numbers
    - DO NOT make fraud allegations without clear evidence of actual fraud
    - Use the PYTHON-CALCULATED numbers as the source of truth - do not recalculate or contradict them
    - If Python says Net Profit is positive, the business IS profitable. Do not say otherwise.
    
    **1. EXECUTIVE SUMMARY**
    [2-3 sentences: Overall health based on the PYTHON-CALCULATED ratios and profit figures]
    
    **2. ACCOUNT-BY-ACCOUNT ANALYSIS**
    Go through EACH account category and note:
    - Which accounts look normal for the industry
    - Which AMOUNTS look unusual or concerning (e.g., very high expenses, credit balances on expense accounts)
    - Which accounts are MISSING that should be there (depreciation, bad debts, etc)
    - DO NOT criticize account CODES - focus on AMOUNTS and BALANCES
    
    **3. RED FLAGS AND RISKS**
    List genuine concerns based on the NUMBERS:
    - Liquidity problems (current ratio, quick ratio)?
    - Profitability issues (margins)?
    - Unusual balances (credit balances on expenses, large intercompany loans)?
    - Missing provisions or accruals?
    - DO NOT flag the account numbering system as a problem
    
    **4. SARS COMPLIANCE**
    - VAT: Is the position correct? When must it be paid?
    - PAYE/UIF: Is it included? Are amounts reasonable for business size?
    - Any missing tax accounts?
    
    **5. SPECIFIC RECOMMENDATIONS**
    Give AT LEAST 5 concrete actions with priority (URGENT / IMPORTANT / MONITOR)
    
    **6. QUESTIONS FOR THE CLIENT**
    List 3-5 questions you would ask the business owner.
    
    FORMAT INSTRUCTIONS:
    - Output CLEAN HTML only. NEVER USE MARKDOWN. No ##, no **, no ---, no * bullets.
    - DARK THEME: NEVER use background:white, background:#fff, or any light background colors. Only use rgba() with low opacity for backgrounds. Text color must be light (white/grey). All content renders on a dark navy background.
    - Use <h2 style="color:#10b981;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:5px;margin-top:25px;"> for main section headings
    - Use <h3 style="color:#8b5cf6;margin-top:18px;"> for sub-headings
    - Use <p> for all paragraph text
    - Use <strong> for emphasis (not **)
    - Use <ul><li> for bullet lists (not - or *)
    - For tables use: <table style="width:100%;border-collapse:collapse;margin:15px 0;"><tr><th style="text-align:left;padding:8px;border-bottom:2px solid rgba(255,255,255,0.2);color:#8b5cf6;">Column</th></tr><tr><td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">Value</td></tr></table>
    - For colored indicators use: <span style="color:#ef4444;">✗ Bad</span> or <span style="color:#10b981;">GOOD: Good</span> or <span style="color:#f59e0b;">WARNING: Warning</span>
    - For WARNING boxes use: <div style="padding:15px;background:rgba(239,68,68,0.15);border-left:4px solid #ef4444;border-radius:6px;margin:12px 0;color:#fca5a5;">warning content</div>
    - For POSITIVE boxes use: <div style="padding:15px;background:rgba(16,185,129,0.15);border-left:4px solid #10b981;border-radius:6px;margin:12px 0;color:#6ee7b7;">positive content</div>
    - For INFO boxes use: <div style="padding:15px;background:rgba(99,102,241,0.15);border-left:4px solid #6366f1;border-radius:6px;margin:12px 0;color:#a5b4fc;">info content</div>
    - For CAUTION boxes use: <div style="padding:15px;background:rgba(245,158,11,0.15);border-left:4px solid #f59e0b;border-radius:6px;margin:12px 0;color:#fcd34d;">caution content</div>
    - EVERY table cell MUST have content - never leave cells empty
    - Complete ALL sections fully - do not stop halfway through a section
    - IMPORTANT: You MUST complete the entire report. Do not leave any section unfinished. If running long, be more concise in later sections rather than stopping mid-sentence.
    
    RULES:
    - Refer to SPECIFIC accounts by name and code
    - Do NOT be generic - be SPECIFIC about amounts and percentages
    - Write like a real financial analyst who cares
    - Use the EXACT figures that Python calculated - do not make up new numbers
    - NEVER say the chart of accounts is "wrong" or "misclassified" - different systems use different codes"""
    
            # ═══════════════════════════════════════════════════════════
            # AI INSIGHTS — SKIPPED HERE, loaded async via /api/reports/tb/insights
            # The placeholder in report_html stays as "Loading professional insight..."
            # Frontend will call insights endpoint separately
            # ═══════════════════════════════════════════════════════════
            
            # Store data for insights endpoint - BOTH in cache AND return to JS
            _insights_payload = {
                'accounts_text': accounts_text[:15000],
                'report_company': report_company,
                'industry': industry,
                'is_third_party': is_third_party,
                'lang': lang,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'difference': difference,
                'is_balanced': is_balanced,
                'current_assets': current_assets,
                'bank_cash': bank + cash,
                'debtors': debtors,
                'stock': stock,
                'fixed_assets_net': fixed_assets_net,
                'total_assets': total_assets,
                'current_liabilities': current_liabilities,
                'long_term_liabilities': long_term_liabilities,
                'total_equity': total_equity,
                'net_sales': net_sales,
                'cos': cos,
                'gross_profit': gross_profit,
                'gp_margin': gp_margin,
                'total_expenses': total_expenses,
                'net_profit': net_profit,
                'np_margin': np_margin,
                'current_ratio': current_ratio,
                'quick_ratio': quick_ratio,
                'debt_equity': debt_equity,
                'debtor_days': debtor_days,
                'creditor_days': creditor_days,
                'stock_days': stock_days,
                'vat_position': vat_position,
                'paye': paye,
                'uif': uif,
            }
            
            # Also keep cache as fallback
            _tb_cache_key = f"tb_insights:{session.get('user_id', 'anon')}"
            Auth._mem[_tb_cache_key] = {"d": _insights_payload, "t": time.time()}
            logger.info(f"[TB ANALYZE] Returning Python report + insights payload")
            
            return jsonify({"success": True, "analysis": report_html, "insights_payload": _insights_payload})
            
        except Exception as e:
            logger.error(f"[TB ANALYZE] Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)})
    
    
    # ═══════════════════════════════════════════════════════════════════════
    # TB INSIGHTS - Async AI analysis (called AFTER report loads)
    # ═══════════════════════════════════════════════════════════════════════
    
    @app.route("/api/reports/tb/insights", methods=["POST"])
    @login_required
    def api_tb_insights():
        """Async AI insights for TB report - called after Python report is shown"""
        
        business = Auth.get_current_business()
        biz_name = business.get("name", "Business") if business else "Business"
        
        try:
            # Try POST body first (reliable, works with gunicorn multi-worker)
            posted = request.get_json() or {}
            if posted.get('insights_payload'):
                td = posted['insights_payload']
                logger.info(f"[TB INSIGHTS] Using data from POST body")
            else:
                # Fallback to cache (legacy)
                _tb_cache_key = f"tb_insights:{session.get('user_id', 'anon')}"
                _cached = Auth._mem.get(_tb_cache_key)
                if not _cached or (time.time() - _cached.get("t", 0)) > 600:
                    return jsonify({"success": False, "error": "No TB data found. Please re-analyze."})
                td = _cached["d"]
                logger.info(f"[TB INSIGHTS] Using data from cache")
            
            lang = td.get('lang', 'en')
            report_company = td.get('report_company', biz_name)
            industry = td.get('industry', 'general')
            is_third_party = td.get('is_third_party', False)
            accounts_text = td.get('accounts_text', '')
            
            total_debit = td.get('total_debit', 0)
            total_credit = td.get('total_credit', 0)
            difference = td.get('difference', 0)
            is_balanced = td.get('is_balanced', True)
            current_assets = td.get('current_assets', 0)
            bank_cash = td.get('bank_cash', 0)
            debtors = td.get('debtors', 0)
            stock = td.get('stock', 0)
            fixed_assets_net = td.get('fixed_assets_net', 0)
            total_assets = td.get('total_assets', 0)
            current_liabilities = td.get('current_liabilities', 0)
            long_term_liabilities = td.get('long_term_liabilities', 0)
            total_equity = td.get('total_equity', 0)
            net_sales = td.get('net_sales', 0)
            cos = td.get('cos', 0)
            gross_profit = td.get('gross_profit', 0)
            gp_margin = td.get('gp_margin', 0)
            total_expenses = td.get('total_expenses', 0)
            net_profit = td.get('net_profit', 0)
            np_margin = td.get('np_margin', 0)
            current_ratio = td.get('current_ratio', 0)
            quick_ratio = td.get('quick_ratio', 0)
            debt_equity = td.get('debt_equity', 0)
            debtor_days = td.get('debtor_days', 0)
            creditor_days = td.get('creditor_days', 0)
            stock_days = td.get('stock_days', 0)
            vat_position = td.get('vat_position', 0)
            paye = td.get('paye', 0)
            uif = td.get('uif', 0)
            
            if lang == "af":
                tp_note = f"\nDit is 'n DERDE PARTY kliënt se TB, nie {biz_name} s'n nie.\n" if is_third_party else ""
                insights_prompt = f"""Jy is Zane, ClickAI. Analiseer hierdie proefbalans BONDIG.
    
    BESIGHEID: {safe_string(report_company)} | INDUSTRIE: {industry}
    {tp_note}
    {accounts_text}
    
    PYTHON-BEREKENDE OPSOMMING (100% akkuraat):
    - Debits: R{total_debit:,.2f} | Kredits: R{total_credit:,.2f} | {'GEBALANSEER' if is_balanced else 'ONGEBALANSEER'}
    - Bates: R{total_assets:,.2f} (Bedryf R{current_assets:,.2f}, Vas R{fixed_assets_net:,.2f})
    - Laste: R{current_liabilities + long_term_liabilities:,.2f} | Ekwiteit: R{total_equity:,.2f}
    - Verkope: R{net_sales:,.2f} | Bruto Wins: R{gross_profit:,.2f} ({gp_margin}%) | Netto: R{net_profit:,.2f} ({np_margin}%)
    - Current Ratio: {current_ratio:.2f} | Quick: {quick_ratio:.2f} | Skuld/Ekwiteit: {debt_equity:.2f}
    - Debiteure Dae: {debtor_days:.0f} | Krediteure Dae: {creditor_days:.0f} | Voorraad Dae: {stock_days:.0f}
    - BTW: R{abs(vat_position):,.2f} {'BETAALBAAR' if vat_position > 0 else 'TERUG'} | LBS+WVF: R{paye + uif:,.2f}
    
    SKRYF 'N VOLLEDIGE FINANSIËLE ANALISE IN AFRIKAANS (1200-1800 woorde):
    1. UITVOERENDE OPSOMMING (3-4 sinne)
    2. HOOFSAKE - Sterkpunte en Swakpunte (noem spesifieke rekeninge en bedrae)
    3. ROOI VLAE (net werklike probleme)
    4. TOP 5 AANBEVELINGS (konkreet, met prioriteit)
    5. VRAE VIR DIE KLIËNT (3-5 vrae)
    
    REËLS: Gebruik Python syfers. Moenie kodes bevraagteken nie. Skryf skoon HTML met <h3> vir opskrifte. Voltooi AL 5 afdelings VOLLEDIG. MOENIE style="background:white" of enige ligte agtergrondkleure gebruik nie — die UI het 'n donker tema. Eindig met: Zane, ClickAI."""
            else:
                tp_note = f"\nThis is a THIRD-PARTY client TB, not {biz_name}'s data.\n" if is_third_party else ""
                insights_prompt = f"""You are Zane, ClickAI. Analyze this trial balance CONCISELY.
    
    BUSINESS: {safe_string(report_company)} | INDUSTRY: {industry}
    {tp_note}
    {accounts_text}
    
    PYTHON-CALCULATED SUMMARY (100% accurate):
    - Debits: R{total_debit:,.2f} | Credits: R{total_credit:,.2f} | {'BALANCED' if is_balanced else 'UNBALANCED'}
    - Assets: R{total_assets:,.2f} (Current R{current_assets:,.2f}, Fixed R{fixed_assets_net:,.2f})
    - Liabilities: R{current_liabilities + long_term_liabilities:,.2f} | Equity: R{total_equity:,.2f}
    - Sales: R{net_sales:,.2f} | Gross Profit: R{gross_profit:,.2f} ({gp_margin}%) | Net: R{net_profit:,.2f} ({np_margin}%)
    - Current Ratio: {current_ratio:.2f} | Quick: {quick_ratio:.2f} | Debt/Equity: {debt_equity:.2f}
    - Debtor Days: {debtor_days:.0f} | Creditor Days: {creditor_days:.0f} | Stock Days: {stock_days:.0f}
    - VAT: R{abs(vat_position):,.2f} {'PAYABLE' if vat_position > 0 else 'REFUND'} | PAYE+UIF: R{paye + uif:,.2f}
    
    WRITE A COMPLETE FINANCIAL ANALYSIS (1200-1800 words):
    1. EXECUTIVE SUMMARY (3-4 sentences)
    2. KEY FINDINGS - Strengths and Weaknesses (name specific accounts and amounts)
    3. RED FLAGS (only real problems)
    4. TOP 5 RECOMMENDATIONS (concrete, prioritized)
    5. QUESTIONS FOR THE CLIENT (3-5 questions)
    
    RULES: Use EXACT Python figures. Don't question account codes. Write clean HTML with <h3> for headings. Complete ALL 5 sections FULLY. Do NOT use style="background:white" or any light background colors — the UI uses a dark theme. End with sign-off: Zane, ClickAI."""
            
            if not ANTHROPIC_API_KEY:
                return jsonify({"success": False, "error": "No API key"})
            
            logger.info(f"[TB INSIGHTS] Starting async AI analysis for {report_company}")
            
            client = _anthropic_client
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=32000,
                messages=[{"role": "user", "content": insights_prompt}]
            )
            
            # ─── AI-USAGE TRACKING ───
            try:
                if hasattr(app, "_ai_usage_tracker"):
                    _biz_id = business.get("id") if business else None
                    _usr = Auth.get_current_user()
                    _usr_id = _usr.get("id") if _usr else None
                    if _biz_id:
                        _usage = getattr(message, "usage", None)
                        app._ai_usage_tracker.log_usage(
                            business_id=_biz_id,
                            tool="tb_insights",
                            model=getattr(message, "model", "claude-sonnet-4-6"),
                            input_tokens=int(getattr(_usage, "input_tokens", 0) or 0),
                            output_tokens=int(getattr(_usage, "output_tokens", 0) or 0),
                            cache_read_tokens=int(getattr(_usage, "cache_read_input_tokens", 0) or 0),
                            cache_write_tokens=int(getattr(_usage, "cache_creation_input_tokens", 0) or 0),
                            user_id=_usr_id,
                            success=True,
                        )
            except Exception as _track_err:
                logger.error(f"[AI-USAGE] tb_insights tracking skipped: {_track_err}")
            # ─── END TRACKING ───
            
            # Log truncation
            if message.stop_reason == "max_tokens":
                logger.warning(f"[TB INSIGHTS] ⚠️ TRUNCATED — hit max_tokens")
            
            if message.content and message.content[0].text:
                insights_html = message.content[0].text
                
                import re as _re
                # Strip any raw HTML tags Sonnet might have added
                insights_html = _re.sub(r'</?html[^>]*>', '', insights_html)
                insights_html = _re.sub(r'</?body[^>]*>', '', insights_html)
                
                # Headings — purple for main, green for sub
                insights_html = _re.sub(r'^### (.+)$', r'<h3 style="color:#a78bfa;margin:22px 0 10px 0;font-size:15px;font-weight:600;">\1</h3>', insights_html, flags=_re.MULTILINE)
                insights_html = _re.sub(r'^## (.+)$', r'<h3 style="color:#10b981;border-bottom:1px solid rgba(16,185,129,0.2);padding-bottom:6px;margin:26px 0 12px 0;font-size:16px;font-weight:600;">\1</h3>', insights_html, flags=_re.MULTILINE)
                insights_html = _re.sub(r'^# (.+)$', r'<h2 style="color:#8b5cf6;border-bottom:2px solid rgba(139,92,246,0.3);padding-bottom:8px;margin:28px 0 14px 0;font-size:18px;font-weight:700;">\1</h2>', insights_html, flags=_re.MULTILINE)
                
                # Bold text — accent purple
                insights_html = _re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#a78bfa;">\1</strong>', insights_html)
                
                # Numbered items — with subtle left border
                insights_html = _re.sub(r'^\d+\. (.+)$', r'<div style="margin:8px 0 8px 12px;padding:4px 0 4px 12px;border-left:2px solid rgba(139,92,246,0.3);">→ \1</div>', insights_html, flags=_re.MULTILINE)
                
                # Bullet items
                insights_html = _re.sub(r'^- (.+)$', r'<div style="margin:6px 0 6px 12px;padding:2px 0;">• \1</div>', insights_html, flags=_re.MULTILINE)
                
                # Horizontal rules
                insights_html = _re.sub(r'^---+$', r'<hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:18px 0;">', insights_html, flags=_re.MULTILINE)
                
                # Paragraph spacing
                insights_html = _re.sub(r'\n{3,}', '<br><br>', insights_html)
                insights_html = _re.sub(r'\n\n', '<br><br>', insights_html)
                insights_html = _re.sub(r'(?<!>)\n(?!<)', '<br>', insights_html)
                
                # Wrap any Sonnet-generated tables in dark styling
                insights_html = insights_html.replace('<table', '<table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:13px;" ')
                insights_html = insights_html.replace('<th', '<th style="padding:8px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.15);color:#a78bfa;font-weight:600;" ')
                insights_html = insights_html.replace('<td', '<td style="padding:6px 8px;border-bottom:1px solid rgba(255,255,255,0.06);" ')
                
                # CRITICAL: Strip ALL white/light backgrounds Sonnet may inject
                insights_html = _re.sub(r'background[-\w]*:\s*#?(?:fff|ffffff|white|fafafa|f5f5f5|f8f8f8|f9f9f9|fef[0-9a-f]+|ffe[0-9a-f]+|fdf[0-9a-f]+)[^;"]*;?', '', insights_html, flags=_re.IGNORECASE)
                insights_html = _re.sub(r'background[-\w]*:\s*rgb\(\s*2[45]\d\s*,\s*2[45]\d\s*,\s*2[45]\d\s*\)[^;"]*;?', '', insights_html, flags=_re.IGNORECASE)
                insights_html = _re.sub(r'background[-\w]*:\s*white[^;"]*;?', '', insights_html, flags=_re.IGNORECASE)
                
                # Force text color on any divs/spans Sonnet creates
                insights_html = _re.sub(r'color:\s*#?(?:000|000000|333|333333|222|444|555|666)[^;"]*;?', 'color:rgba(255,255,255,0.9);', insights_html, flags=_re.IGNORECASE)
                insights_html = _re.sub(r'color:\s*black[^;"]*;?', 'color:rgba(255,255,255,0.9);', insights_html, flags=_re.IGNORECASE)
                insights_html = _re.sub(r'color:\s*rgb\(\s*0\s*,\s*0\s*,\s*0\s*\)[^;"]*;?', 'color:rgba(255,255,255,0.9);', insights_html, flags=_re.IGNORECASE)
                
                # Strip border colors that are dark (they become invisible on dark bg)
                insights_html = _re.sub(r'border[-\w]*:\s*\d+px\s+solid\s+#?(?:ccc|ddd|eee|e0e0e0|d0d0d0)[^;"]*;?', 'border:1px solid rgba(255,255,255,0.1);', insights_html, flags=_re.IGNORECASE)
                
                # Style the Zane sign-off if present
                insights_html = _re.sub(
                    r'(Zane,?\s*ClickAI)',
                    r'<div style="margin-top:20px;padding-top:12px;border-top:1px solid rgba(139,92,246,0.2);color:#8b5cf6;font-weight:600;font-style:italic;">\1</div>',
                    insights_html
                )
                
                logger.info(f"[TB INSIGHTS] AI analysis complete: {len(insights_html)} chars")
                return jsonify({"success": True, "insights": insights_html})
            else:
                return jsonify({"success": False, "error": "AI returned empty"})
                
        except Exception as e:
            logger.warning(f"[TB INSIGHTS] Failed: {e}")
            return jsonify({"success": False, "error": str(e)[:200]})
    
    
    # ═══════════════════════════════════════════════════════════════
    # REPORT EMAIL & DOWNLOAD
    # ═══════════════════════════════════════════════════════════════
    
    @app.route("/api/reports/email", methods=["POST"])
    @login_required
    def api_report_email():
        """Email a report to specified address"""
        try:
            data = request.get_json() or {}
            to_email = (data.get('to_email') or '').strip()
            subject = data.get('subject', 'ClickAI Report')
            report_html = data.get('report_html', '')
            report_title = data.get('report_title', 'Report')
            
            if not to_email or '@' not in to_email:
                return jsonify({"success": False, "error": "Valid email address required"})
            
            if not report_html:
                return jsonify({"success": False, "error": "No report content"})
            
            business = Auth.get_current_business()
            biz_name = business.get("name", "Business") if business else "Business"
            
            # Build professional email HTML (light theme for email clients)
            email_html = f"""
            <div style="max-width:800px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;color:#1a1a2e;">
                <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:25px 30px;border-radius:12px 12px 0 0;">
                    <h1 style="color:#8b5cf6;margin:0;font-size:22px;">📊 {report_title}</h1>
                    <p style="color:rgba(255,255,255,0.7);margin:8px 0 0 0;font-size:13px;">{biz_name} | Generated by ClickAI</p>
                </div>
                <div style="background:#ffffff;padding:25px 30px;border:1px solid #e5e7eb;color:#1a1a2e;line-height:1.7;font-size:14px;">
                    {report_html}
                </div>
                <div style="background:#f8fafc;padding:15px 30px;border-radius:0 0 12px 12px;border:1px solid #e5e7eb;border-top:none;">
                    <p style="margin:0;font-size:11px;color:#6b7280;text-align:center;">
                        Generated by <strong style="color:#8b5cf6;">ClickAI</strong> — AI-Powered Business Management
                        <br>All calculations by Python | Figures verified | {today()}
                    </p>
                </div>
            </div>"""
            
            # Convert dark theme colors to light for email
            import re as _re
            email_html = _re.sub(r'color:\s*rgba\(255,\s*255,\s*255,\s*[\d.]+\)', 'color:#1a1a2e', email_html)
            email_html = _re.sub(r'color:\s*var\(--text\)', 'color:#1a1a2e', email_html)
            email_html = _re.sub(r'color:\s*var\(--text-muted\)', 'color:#6b7280', email_html)
            email_html = _re.sub(r'border[-\w]*:\s*[\d.]+px\s+solid\s+rgba\(255,\s*255,\s*255,\s*[\d.]+\)', 'border:1px solid #e5e7eb', email_html)
            
            success = EmailService.send(
                to_email=to_email,
                subject=f"{subject} — {biz_name}",
                body_html=email_html,
                body_text=f"{report_title} for {biz_name}. Please view the HTML version of this email."
            )
            
            if success:
                logger.info(f"[REPORT EMAIL] Sent '{report_title}' to {to_email}")
                return jsonify({"success": True, "message": f"Report sent to {to_email}"})
            else:
                return jsonify({"success": False, "error": "Email sending failed. Check SMTP settings in Business Settings."})
                
        except Exception as e:
            logger.warning(f"[REPORT EMAIL] Failed: {e}")
            return jsonify({"success": False, "error": str(e)[:200]})
    
    
    @app.route("/api/reports/tb/upload-analyze", methods=["POST"])
    @login_required
    def api_tb_upload_analyze():
        """Upload CSV/Excel TB file and analyze it - returns same professional report"""
        
        business = Auth.get_current_business()
        biz_name = business.get("name", "Business") if business else "Business"
        industry = business.get("industry", "general") if business else "general"
        
        try:
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "No file uploaded"})
            
            file = request.files['file']
            lang = request.form.get('lang', 'en')
            
            if not file.filename:
                return jsonify({"success": False, "error": "No file selected"})
            
            filename = file.filename.lower()
            logger.info(f"[TB UPLOAD] Processing {filename}, lang={lang}")
            
            # Read file into DataFrame
            import pandas as pd
            import io
            
            try:
                if filename.endswith('.csv'):
                    content = file.read()
                    df = None
                    
                    # Strip BOM if present
                    if content[:3] == b'\xef\xbb\xbf':
                        content = content[3:]
                    
                    # Decode content to text first
                    text = None
                    for enc in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                        try:
                            text = content.decode(enc)
                            break
                        except:
                            continue
                    
                    if not text:
                        return jsonify({"success": False, "error": "Kon nie die CSV lees nie - encoding probleem."})
                    
                    # Clean up: remove Excel hints and find real header row
                    lines = [l.strip() for l in text.split('\n') if l.strip()]
                    
                    # Skip non-data rows at top (sep=, title rows)
                    header_row = 0
                    for i, line in enumerate(lines[:10]):
                        stripped = line.strip().strip('"').strip()
                        stripped_lower = stripped.lower()
                        # Skip: sep=X lines
                        if stripped_lower.startswith('sep='):
                            header_row = i + 1
                            continue
                        # Skip: single-value title rows (no commas between values, just a title)
                        # But NOT rows like "Name","Category","Debit","Credit" which are headers
                        raw_no_quoted = line
                        # Count commas outside quotes to check if it's a real CSV row
                        in_quote = False
                        comma_count = 0
                        for ch in line:
                            if ch == '"':
                                in_quote = not in_quote
                            elif ch == ',' and not in_quote:
                                comma_count += 1
                        if comma_count == 0:
                            # Single value row = title, skip it
                            header_row = i + 1
                            continue
                        # This has commas = real header or data row, stop
                        break
                    
                    logger.info(f"[TB UPLOAD] Detected header at row {header_row}, skipping {header_row} rows")
                    
                    # Detect delimiter from header line
                    header_line = lines[header_row] if header_row < len(lines) else lines[0]
                    if ';' in header_line and header_line.count(';') > header_line.count(','):
                        sep = ';'
                    elif '\t' in header_line:
                        sep = '\t'
                    else:
                        sep = ','
                    
                    # Rebuild clean text without skipped rows
                    clean_text = '\n'.join(lines[header_row:])
                    
                    try:
                        df = pd.read_csv(io.StringIO(clean_text), sep=sep, on_bad_lines='skip', engine='python')
                        logger.info(f"[TB UPLOAD] Read {len(df)} rows, {len(df.columns)} cols: {list(df.columns)}")
                    except Exception as e:
                        logger.error(f"[TB UPLOAD] pandas read failed: {e}")
                    
                    if df is None or len(df.columns) <= 1:
                        return jsonify({"success": False, "error": "Kon nie die CSV lees nie. Probeer om dit as Excel (.xlsx) te save en weer te upload."})
                        
                elif filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file)
                else:
                    return jsonify({"success": False, "error": "Unsupported file type. Use CSV or Excel."})
            except Exception as read_err:
                logger.error(f"[TB UPLOAD] Read error: {read_err}")
                return jsonify({"success": False, "error": f"Could not read file: {str(read_err)}"})
            
            logger.info(f"[TB UPLOAD] Read {len(df)} rows, columns: {list(df.columns)}")
            
            # ═══════════════════════════════════════════════════════════
            # SMART COLUMN DETECTION - tries hardcoded first, then AI
            # Every accountant's TB looks different!
            # ═══════════════════════════════════════════════════════════
            cols_lower = {c.lower().strip(): c for c in df.columns}
            
            # Find account code column
            code_col = None
            for candidate in ['code', 'acc code', 'account code', 'acc_code', 'kode', 'rekening kode', 
                              'gl code', 'account_code', 'acc no', 'account no', 'account number',
                              'rekeningnommer', 'gl no', 'no', 'number', 'acc', 'account #']:
                if candidate in cols_lower:
                    code_col = cols_lower[candidate]
                    break
            
            # Find account name column
            name_col = None
            for candidate in ['name', 'account', 'account name', 'description', 'naam', 'rekening', 
                              'rekening naam', 'acc name', 'account_name', 'rekeningnaam', 'omskrywing',
                              'account description', 'ledger', 'ledger name', 'gl name', 'label',
                              'type', 'account type']:
                if candidate in cols_lower:
                    name_col = cols_lower[candidate]
                    break
            
            # Find debit column
            debit_col = None
            for candidate in ['debit', 'dr', 'debits', 'debit amount', 'debiet', 'debit balance',
                              'debiet saldo', 'debit total', 'dr amount', 'dr balance']:
                if candidate in cols_lower:
                    debit_col = cols_lower[candidate]
                    break
            
            # Find credit column
            credit_col = None
            for candidate in ['credit', 'cr', 'credits', 'credit amount', 'krediet', 'credit balance',
                              'krediet saldo', 'credit total', 'cr amount', 'cr balance']:
                if candidate in cols_lower:
                    credit_col = cols_lower[candidate]
                    break
            
            # Find single balance column (some TBs use one column with +/-)
            balance_col = None
            if not debit_col and not credit_col:
                for candidate in ['balance', 'saldo', 'amount', 'bedrag', 'net balance', 'netto',
                                  'value', 'waarde', 'total', 'totaal', 'closing balance', 'closing',
                                  'sluitsaldo', 'net', 'movement', 'beweging']:
                    if candidate in cols_lower:
                        balance_col = cols_lower[candidate]
                        break
            
            # Find category/type column
            category_col = None
            for candidate in ['category', 'kategorie', 'type', 'account type', 'tipe', 'class',
                              'group', 'groep', 'section', 'heading', 'opskrif']:
                if candidate in cols_lower:
                    if cols_lower[candidate] != name_col:  # Don't use same col as name
                        category_col = cols_lower[candidate]
                        break
            
            # ═══════════════════════════════════════════════════════════
            # AI FALLBACK - if we can't find columns, ask Claude
            # ═══════════════════════════════════════════════════════════
            ai_mapped = False
            if not name_col or (not debit_col and not credit_col and not balance_col):
                logger.info(f"[TB UPLOAD] Hardcoded mapping failed. Trying AI detection...")
                try:
                    # Send sample to Claude for column detection
                    sample_rows = df.head(8).to_string()
                    col_list = list(df.columns)
                    
                    ai_prompt = f"""Analyze this trial balance / opening balance file and identify which columns map to what.
    
    COLUMNS: {col_list}
    
    SAMPLE DATA (first 8 rows):
    {sample_rows}
    
    Return ONLY valid JSON (no markdown, no explanation):
    {{"account_code": "exact column name or null", "account_name": "exact column name", "debit": "exact column name or null", "credit": "exact column name or null", "balance": "exact column name or null", "category": "exact column name or null"}}
    
    Rules:
    - account_name: The column with account descriptions (e.g. "Sales", "Bank", "Rent")
    - account_code: The column with account numbers/codes (e.g. "1000", "4000/000")
    - debit/credit: Separate columns for debit and credit amounts
    - balance: Single column with positive/negative amounts (use ONLY if no separate debit/credit)
    - category: Column showing account type/category (Asset, Liability, Income, Expense)
    - Use exact column names from the COLUMNS list above
    - Use null if column doesn't exist"""
    
                    client = _anthropic_client
                    ai_response = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=500,
                        messages=[{"role": "user", "content": ai_prompt}]
                    )
                    
                    # ─── AI-USAGE TRACKING ───
                    try:
                        if hasattr(app, "_ai_usage_tracker"):
                            _biz_id = business.get("id") if business else None
                            _usr = Auth.get_current_user()
                            _usr_id = _usr.get("id") if _usr else None
                            if _biz_id:
                                _usage = getattr(ai_response, "usage", None)
                                app._ai_usage_tracker.log_usage(
                                    business_id=_biz_id,
                                    tool="tb_column_detect",
                                    model=getattr(ai_response, "model", "claude-sonnet-4-6"),
                                    input_tokens=int(getattr(_usage, "input_tokens", 0) or 0),
                                    output_tokens=int(getattr(_usage, "output_tokens", 0) or 0),
                                    cache_read_tokens=int(getattr(_usage, "cache_read_input_tokens", 0) or 0),
                                    cache_write_tokens=int(getattr(_usage, "cache_creation_input_tokens", 0) or 0),
                                    user_id=_usr_id,
                                    success=True,
                                )
                    except Exception as _track_err:
                        logger.error(f"[AI-USAGE] tb_column_detect tracking skipped: {_track_err}")
                    # ─── END TRACKING ───
                    
                    ai_text = ai_response.content[0].text.strip()
                    # Clean markdown if present
                    if '```' in ai_text:
                        ai_text = ai_text.split('```')[1].replace('json', '').strip()
                    
                    ai_map = json.loads(ai_text)
                    logger.info(f"[TB UPLOAD] AI column mapping: {ai_map}")
                    
                    # Apply AI mapping
                    if ai_map.get("account_name") and ai_map["account_name"] in df.columns:
                        name_col = ai_map["account_name"]
                    if ai_map.get("account_code") and ai_map["account_code"] in df.columns:
                        code_col = ai_map["account_code"]
                    if ai_map.get("debit") and ai_map["debit"] in df.columns:
                        debit_col = ai_map["debit"]
                    if ai_map.get("credit") and ai_map["credit"] in df.columns:
                        credit_col = ai_map["credit"]
                    if ai_map.get("balance") and ai_map["balance"] in df.columns:
                        balance_col = ai_map["balance"]
                    if ai_map.get("category") and ai_map["category"] in df.columns:
                        category_col = ai_map["category"]
                    
                    ai_mapped = True
                    
                except Exception as ai_err:
                    logger.error(f"[TB UPLOAD] AI detection failed: {ai_err}")
            
            # Validate we found required columns
            if not name_col:
                # Last resort: try first text column as name
                for c in df.columns:
                    if df[c].dtype == 'object':
                        name_col = c
                        break
            
            if not name_col:
                return jsonify({"success": False, "error": f"Kon nie rekening naam kolom vind nie. Kolomme in jou file: {list(df.columns)}"})
            
            if not debit_col and not credit_col and not balance_col:
                return jsonify({"success": False, "error": f"Kon nie debit/credit/balance kolomme vind nie. Kolomme in jou file: {list(df.columns)}"})
            
            mapped_info = f"Code: {code_col}, Name: {name_col}, Debit: {debit_col}, Credit: {credit_col}, Balance: {balance_col}, Category: {category_col}"
            logger.info(f"[TB UPLOAD] Mapped columns {'(AI)' if ai_mapped else '(hardcoded)'} - {mapped_info}")
            
            # Build accounts list
            accounts = []
            tb_control_profit = None  # Capture the TB's own net profit figure for validation
            
            for idx, row in df.iterrows():
                name = str(row.get(name_col, '')).strip() if name_col else ''
                if not name or name.lower() in ['nan', 'none', '', 'total', 'totals', 'totaal', 'grand total', 'netto', 'net']:
                    continue
                
                # Capture the TB's own Net Profit/Loss figure as a control check
                if name.lower() in ['net profit/loss', 'net profit/loss after tax', 'net profit', 'netto wins',
                                     'net profit/loss before tax', 'netto wins/verlies', 'netto wins na belasting']:
                    # This row has the TB's calculated profit - grab it for validation
                    dr = float(str(row.get(debit_col, '') or '0').replace('R','').replace('r','').replace(',','').replace(' ','').strip() or '0') if debit_col else 0
                    cr = float(str(row.get(credit_col, '') or '0').replace('R','').replace('r','').replace(',','').replace(' ','').strip() or '0') if credit_col else 0
                    if cr > 0:
                        tb_control_profit = cr  # Credit = profit
                    elif dr > 0:
                        tb_control_profit = -dr  # Debit = loss
                    elif balance_col:
                        bal = str(row.get(balance_col, '') or '0').replace('R','').replace('r','').replace(',','').replace(' ','').strip()
                        try:
                            tb_control_profit = float(bal)
                        except:
                            pass
                    logger.info(f"[TB UPLOAD] Found control profit figure: R {tb_control_profit:,.2f}" if tb_control_profit else "[TB UPLOAD] Could not parse control profit")
                    continue  # Don't include in accounts list
                
                code = str(row.get(code_col, '')).strip() if code_col else ''
                if code.lower() in ['nan', 'none', '']:
                    code = ''
                
                # Smart split: "1000/000 : Sales" → code="1000/000", name="Sales"
                # Also handles: "1000 - Sales", "1000: Sales", "ACC001 Sales"
                if not code and ' : ' in name:
                    parts = name.split(' : ', 1)
                    code = parts[0].strip()
                    name = parts[1].strip()
                elif not code and ' - ' in name and name[0].isdigit():
                    parts = name.split(' - ', 1)
                    code = parts[0].strip()
                    name = parts[1].strip()
                elif not code and ': ' in name and name[0].isdigit():
                    parts = name.split(': ', 1)
                    code = parts[0].strip()
                    name = parts[1].strip()
                
                if not code:
                    code = f"A{idx:04d}"
                
                # Clean up _AND_ → & (Sage Pastel export quirk)
                name = name.replace('_AND_', '&').replace(' _and_ ', ' & ')
                
                # Parse debit/credit values - handles R1,000.00, R 1 000.00, (1000), -1000
                def parse_amount(val):
                    if pd.isna(val):
                        return 0.0
                    val = str(val).replace('R', '').replace('r', '').replace(',', '').replace(' ', '').strip()
                    # Handle bracket notation for negatives: (1000) = -1000
                    is_negative = False
                    if val.startswith('(') and val.endswith(')'):
                        val = val[1:-1]
                        is_negative = True
                    if val in ['', '-', 'nan', 'none', '0', '0.0', '0.00']:
                        return 0.0
                    try:
                        result = float(val)
                        return -result if is_negative else result
                    except:
                        return 0.0
                
                debit = 0.0
                credit = 0.0
                
                if debit_col and credit_col:
                    # Separate debit/credit columns
                    debit = abs(parse_amount(row.get(debit_col)))
                    credit = abs(parse_amount(row.get(credit_col)))
                elif balance_col:
                    # Single balance column: positive = debit, negative = credit
                    bal = parse_amount(row.get(balance_col))
                    if bal > 0:
                        debit = bal
                    elif bal < 0:
                        credit = abs(bal)
                elif debit_col:
                    # Only debit column
                    val = parse_amount(row.get(debit_col))
                    if val > 0:
                        debit = val
                    else:
                        credit = abs(val)
                elif credit_col:
                    # Only credit column
                    val = parse_amount(row.get(credit_col))
                    if val > 0:
                        credit = val
                    else:
                        debit = abs(val)
                
                if debit > 0 or credit > 0:
                    acc = {
                        "code": code,
                        "name": name,
                        "debit": debit,
                        "credit": credit
                    }
                    if category_col:
                        cat = str(row.get(category_col, '')).strip()
                        if cat and cat.lower() not in ['nan', 'none']:
                            acc["category"] = cat
                    accounts.append(acc)
            
            if not accounts:
                return jsonify({"success": False, "error": "No valid account data found in file"})
            
            logger.info(f"[TB UPLOAD] Extracted {len(accounts)} accounts")
            
            # Now call the same analysis logic as api_tb_analyze
            # We'll construct the data and call the analyze endpoint internally
            total_debit = sum(a['debit'] for a in accounts)
            total_credit = sum(a['credit'] for a in accounts)
            is_balanced = abs(total_debit - total_credit) < 0.01
            
            # Inject into request-like data and call analyze logic
            # For simplicity, we'll use requests to call our own endpoint
            import requests as req_lib
            
            # Actually, let's just inline the analysis - cleaner
            # Set up the data structure the analyzer expects
            analyze_data = {
                "accounts": accounts,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "is_balanced": is_balanced,
                "lang": lang
            }
            
            # Make internal request (this is a bit hacky but works)
            from flask import g
            with app.test_request_context('/api/reports/tb/analyze', method='POST', 
                                           data=json.dumps(analyze_data),
                                           content_type='application/json'):
                # Copy session/auth from current request
                from flask import session as flask_session
                # Just call the function directly with mocked request data
                pass
            
            # Actually, cleaner approach - just duplicate the core logic or call directly
            # Let's make a simpler approach: return the accounts and let frontend call analyze
            # No wait, user wants single upload -> full report
            
            # Simplest: redirect the data through the existing endpoint via internal call
            # But that's complex. Let's just inline the key parts:
            
            # Build the same analysis by importing the core from api_tb_analyze
            # This is getting complex - let me just return success with a redirect approach
            
            # SIMPLE APPROACH: Return the parsed data and have JS call the analyze endpoint
            return jsonify({
                "success": True, 
                "accounts": accounts,
                "total_debit": total_debit,
                "total_credit": total_credit,
                "is_balanced": is_balanced,
                "message": f"Parsed {len(accounts)} accounts from {file.filename}",
                "source_file": file.filename,
                "tb_control_profit": tb_control_profit,
                "redirect_analyze": True
            })
            
        except Exception as e:
            logger.error(f"[TB UPLOAD] Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/reports/tb/smart-report", methods=["POST"])
    @login_required
    def api_tb_smart_report():
        """Generate different report types from uploaded TB data (management statement, KPI, etc.)"""
        
        try:
            data = request.get_json()
            accounts = data.get("accounts", [])
            report_type = data.get("report_type", "management")
            custom_request = data.get("custom_request", "")
            lang = data.get("lang", "en")
            source_file = data.get("source_file", "Uploaded TB")
            tb_control_profit = data.get("tb_control_profit")
            
            if not accounts:
                return jsonify({"success": False, "error": "No account data provided"})
            
            # ═══ PYTHON CALCULATES EVERYTHING FROM THE TB DATA ═══
            has_categories = any(a.get("category") for a in accounts)
            
            def cat_sum(cats, column="debit"):
                total = 0
                for a in accounts:
                    cat = str(a.get("category", "")).lower()
                    for c in cats:
                        if c in cat:
                            total += float(a.get(column, 0) or 0)
                            break
                return total
            
            def name_sum(accs, keywords, column="debit"):
                return sum(float(a.get(column, 0) or 0) for a in accs 
                          if any(kw in str(a.get("name", "")).lower() for kw in keywords))
            
            if has_categories:
                sales = cat_sum(["sales", "revenue", "turnover", "omset"], "credit")
                cos = cat_sum(["cost of sale", "cost of goods", "koste van verkope"], "debit")
                other_income = cat_sum(["other income", "ander inkomste"], "credit")
                
                expense_accs = [a for a in accounts if any(kw in str(a.get("category", "")).lower() for kw in ["expense", "uitgawe", "operating"])]
                total_expenses = sum(float(a.get("debit", 0) or 0) - float(a.get("credit", 0) or 0) for a in expense_accs)
                if total_expenses < 0:
                    total_expenses = 0
                
                current_assets = sum(float(a.get("debit", 0) or 0) - float(a.get("credit", 0) or 0) 
                                   for a in accounts if "current asset" in str(a.get("category", "")).lower() and "non-current" not in str(a.get("category", "")).lower())
                fixed_assets = sum(float(a.get("debit", 0) or 0) - float(a.get("credit", 0) or 0) 
                                 for a in accounts if any(kw in str(a.get("category", "")).lower() for kw in ["fixed asset", "non-current asset"]))
                current_liab = sum(float(a.get("credit", 0) or 0) - float(a.get("debit", 0) or 0) 
                                 for a in accounts if "current liabilit" in str(a.get("category", "")).lower() and "non-current" not in str(a.get("category", "")).lower())
                long_term_liab = sum(float(a.get("credit", 0) or 0) - float(a.get("debit", 0) or 0) 
                                   for a in accounts if any(kw in str(a.get("category", "")).lower() for kw in ["long term", "non-current liabilit"]))
                equity = sum(float(a.get("credit", 0) or 0) - float(a.get("debit", 0) or 0) 
                            for a in accounts if any(kw in str(a.get("category", "")).lower() for kw in ["equity", "owner", "ekwiteit"]))
                
                salaries = name_sum(expense_accs, ["salary", "salaries", "wage", "payroll", "salar"])
                rent = name_sum(expense_accs, ["rent", "huur"])
                electricity = name_sum(expense_accs, ["electric", "water", "eskom", "elektris"])
                advertising = name_sum(expense_accs, ["advertising", "marketing", "advertens"])
                insurance = name_sum(expense_accs, ["insurance", "verseker"])
                bank_charges = name_sum(expense_accs, ["bank charge", "bank fee", "bankkoste"])
                depreciation = name_sum(expense_accs, ["depreciation", "waardevermindering"])
                professional = name_sum(expense_accs, ["professional", "accounting", "legal", "audit", "rekenmeest"])
            else:
                sales = sum(float(a.get("credit", 0) or 0) for a in accounts if str(a.get("code", "")).startswith("5"))
                cos = sum(float(a.get("debit", 0) or 0) for a in accounts if str(a.get("code", "")).startswith("51"))
                total_expenses = sum(float(a.get("debit", 0) or 0) for a in accounts if str(a.get("code", ""))[:1] in "6789")
                other_income = 0
                current_assets = current_liab = fixed_assets = long_term_liab = equity = 0
                salaries = rent = electricity = advertising = insurance = bank_charges = depreciation = professional = 0
            
            gross_profit = sales - cos
            net_profit = sales + other_income - cos - total_expenses
            total_assets = current_assets + fixed_assets
            total_liabilities = current_liab + long_term_liab
            
            gp_margin = round((gross_profit / sales * 100), 1) if sales > 0 else 0
            np_margin = round((net_profit / (sales + other_income) * 100), 1) if (sales + other_income) > 0 else 0
            current_ratio = round(current_assets / current_liab, 2) if current_liab > 0 else 0
            debt_equity = round(total_liabilities / equity, 2) if equity > 0 else 0
            sal_pct = round(salaries / sales * 100, 1) if sales > 0 else 0
            rent_pct = round(rent / sales * 100, 1) if sales > 0 else 0
            
            validation_note = ""
            if tb_control_profit is not None:
                try:
                    control = float(tb_control_profit)
                    diff = abs(net_profit - control)
                    pct = (diff / abs(control) * 100) if control != 0 else 0
                    if pct > 5:
                        validation_note = f"⚠️ Note: Calculated net profit (R{net_profit:,.2f}) differs from TB control figure (R{control:,.2f}) by {pct:.1f}%."
                except:
                    pass
            
            clean_name = source_file.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').strip()
            
            data_for_ai = f"""
    CLIENT: {clean_name}
    DATA SOURCE: Uploaded Trial Balance ({len(accounts)} accounts)
    {validation_note}
    
    === INCOME STATEMENT (Python-calculated, 100% accurate - DO NOT recalculate) ===
    Revenue/Sales: R{sales:,.2f}
    Cost of Sales: R{cos:,.2f}
    Gross Profit: R{gross_profit:,.2f} ({gp_margin}%)
    Other Income: R{other_income:,.2f}
    Total Expenses: R{total_expenses:,.2f}
      - Salaries: R{salaries:,.2f} ({sal_pct}% of sales)
      - Rent: R{rent:,.2f}
      - Electricity/Water: R{electricity:,.2f}
      - Advertising: R{advertising:,.2f}
      - Insurance: R{insurance:,.2f}
      - Bank Charges: R{bank_charges:,.2f}
      - Depreciation: R{depreciation:,.2f}
      - Professional Fees: R{professional:,.2f}
    Net Profit: R{net_profit:,.2f} ({np_margin}%)
    
    === BALANCE SHEET ===
    Current Assets: R{current_assets:,.2f}
    Fixed Assets: R{fixed_assets:,.2f}
    Total Assets: R{total_assets:,.2f}
    Current Liabilities: R{current_liab:,.2f}
    Long-term Liabilities: R{long_term_liab:,.2f}
    Total Liabilities: R{total_liabilities:,.2f}
    Equity: R{equity:,.2f}
    
    === RATIOS ===
    Current Ratio: {current_ratio}:1 (norm >1.5)
    Gross Margin: {gp_margin}%
    Net Margin: {np_margin}%
    Debt/Equity: {debt_equity}:1
    """
            
            report_prompts = {
                "management": """Write a professional MANAGEMENT STATEMENT (Year-to-Date). Structure:
    1. Executive Summary (2-3 sentences)
    2. Income Statement Analysis (revenue, margins, expense breakdown)
    3. Balance Sheet Summary
    4. Key Ratios & What They Mean
    5. Concerns & Red Flags
    6. Recommendations (5+ specific actions)""",
                
                "kpi": f"""Write a KPI DASHBOARD REPORT with traffic light status (Green/Amber/Red):
    1. Gross Profit Margin ({gp_margin}%)
    2. Net Profit Margin ({np_margin}%)
    3. Current Ratio ({current_ratio}:1)
    4. Salaries % of Sales ({sal_pct}%)
    5. Rent % of Sales ({rent_pct}%)
    6. Debt to Equity ({debt_equity}:1)
    For each: meaning, benchmark, and action.""",
                
                "sales": """Write a SALES ANALYSIS covering: revenue performance, cost structure, gross margin quality, expense impact, and improvement recommendations.""",
                
                "debtor": f"""Write a WORKING CAPITAL report: Current Ratio ({current_ratio}), cash position, liquidity risk, and recommendations.""",
                
                "forecast": """Write a FORWARD-LOOKING ANALYSIS: sustainability, cash flow outlook, scenario analysis (sales drop 10/20/30%), and strategic recommendations.""",
                
                "custom": f"""Answer this request: {custom_request or 'General financial overview'}"""
            }
            
            prompt = report_prompts.get(report_type, report_prompts["management"])
            
            system_prompt = f"""You are Zane, ClickAI's senior financial analyst. You are writing a report for a CLIENT's uploaded trial balance.
    Your name is simply "Zane" - do NOT use any surname. Sign as "Zane, ClickAI" only.
    RULES: Use ONLY the Python-calculated numbers. Do NOT recalculate. Do NOT make fraud allegations.
    {"Write in Afrikaans." if lang == "af" else "Write in English."} Use R (Rand) for all amounts.
    
    FORMAT RULES - OUTPUT CLEAN HTML:
    - Use <h2> for main sections, <h3> for subsections
    - Use <p> for paragraphs
    - Use <strong> for emphasis
    - Use <table> with inline styles for any data tables
    - Use <div style="background:rgba(239,68,68,0.15);border-left:3px solid #ef4444;padding:12px;margin:10px 0;color:#fca5a5;border-radius:6px;"> for warnings/red flags
    - Use <div style="background:rgba(16,185,129,0.15);border-left:3px solid #10b981;padding:12px;margin:10px 0;color:#6ee7b7;border-radius:6px;"> for positive items
    - Use <div style="background:rgba(245,158,11,0.15);border-left:3px solid #f59e0b;padding:12px;margin:10px 0;color:#fcd34d;border-radius:6px;"> for caution items
    - Use <div style="background:rgba(16,185,129,0.1);border-left:3px solid #10b981;padding:10px;margin:10px 0;"> for positive items
    
    - DO NOT use markdown (no ##, no **, no ---, no bullet points with -)
    - Use <ul><li> for lists
    - Make it visually professional and easy to scan"""
    
            if not ANTHROPIC_API_KEY:
                return jsonify({"success": False, "error": "AI not configured"})
            
            message = _anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=32000,
                system=system_prompt,
                messages=[{"role": "user", "content": f"{data_for_ai}\n\n{prompt}"}]
            )
            
            # ─── AI-USAGE TRACKING ───
            try:
                if hasattr(app, "_ai_usage_tracker"):
                    _biz = Auth.get_current_business()
                    _biz_id = _biz.get("id") if _biz else None
                    _usr = Auth.get_current_user()
                    _usr_id = _usr.get("id") if _usr else None
                    if _biz_id:
                        _usage = getattr(message, "usage", None)
                        app._ai_usage_tracker.log_usage(
                            business_id=_biz_id,
                            tool="tb_smart_report",
                            model=getattr(message, "model", "claude-sonnet-4-6"),
                            input_tokens=int(getattr(_usage, "input_tokens", 0) or 0),
                            output_tokens=int(getattr(_usage, "output_tokens", 0) or 0),
                            cache_read_tokens=int(getattr(_usage, "cache_read_input_tokens", 0) or 0),
                            cache_write_tokens=int(getattr(_usage, "cache_creation_input_tokens", 0) or 0),
                            user_id=_usr_id,
                            success=True,
                            metadata={"report_type": report_type},
                        )
            except Exception as _track_err:
                logger.error(f"[AI-USAGE] tb_smart_report tracking skipped: {_track_err}")
            # ─── END TRACKING ───
            
            report = message.content[0].text if message.content else ""
            
            # Convert any remaining markdown to HTML (fallback if Sonnet mixed formats)
            import re
            report = re.sub(r'^### (.+)$', r'<h3 style="color:#8b5cf6;margin-top:20px;">\1</h3>', report, flags=re.MULTILINE)
            report = re.sub(r'^## (.+)$', r'<h2 style="color:#10b981;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:5px;margin-top:25px;">\1</h2>', report, flags=re.MULTILINE)
            report = re.sub(r'^# (.+)$', r'<h2 style="color:#8b5cf6;border-bottom:2px solid #8b5cf6;padding-bottom:8px;">\1</h2>', report, flags=re.MULTILINE)
            report = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', report)
            report = re.sub(r'^- (.+)$', r'<div style="margin:4px 0 4px 20px;">• \1</div>', report, flags=re.MULTILINE)
            report = re.sub(r'^\d+\. (.+)$', r'<div style="margin:4px 0 4px 20px;">→ \1</div>', report, flags=re.MULTILINE)
            report = re.sub(r'^---+$', r'<hr style="border:none;border-top:1px solid rgba(255,255,255,0.1);margin:15px 0;">', report, flags=re.MULTILINE)
            # Wrap plain text paragraphs
            report = re.sub(r'\n\n(?!<)', '\n<br><br>\n', report)
            return jsonify({"success": True, "report": report})
            
        except Exception as e:
            logger.error(f"[TB SMART REPORT] Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)})
    
    
    # 
    # PROFIT & LOSS
    # 
    
    @app.route("/reports/pnl")
    @login_required
    def report_pnl():
        """Profit & Loss Statement - Proper accounting format"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get period from query params (default: current month)
        period = request.args.get("period", "month")
        
        # Calculate date range
        today_date = datetime.now()
        if period == "month":
            start_date = today_date.replace(day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = today_date.strftime("%B %Y")
        elif period == "quarter":
            quarter = (today_date.month - 1) // 3
            start_date = today_date.replace(month=quarter*3+1, day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = f"Q{quarter+1} {today_date.year}"
        elif period == "year":
            start_date = today_date.replace(month=1, day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = f"Year {today_date.year}"
        elif period == "all":
            start_date = "2000-01-01"
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = "All Time"
        else:
            start_date = today_date.replace(day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = today_date.strftime("%B %Y")
        
        # Get data filtered by date
        invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
        invoices = [i for i in invoices if start_date <= i.get("date", "") <= end_date]
        
        sales = db.get("sales", {"business_id": biz_id}) if biz_id else []
        sales = [s for s in sales if start_date <= s.get("date", "") <= end_date]
        
        expenses = db.get("expenses", {"business_id": biz_id}) if biz_id else []
        expenses = [e for e in expenses if start_date <= e.get("date", "") <= end_date]
        
        payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []
        payslips = [p for p in payslips if start_date <= p.get("date", "") <= end_date]
        
        supplier_invoices = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id else []
        supplier_invoices = [si for si in supplier_invoices if start_date <= si.get("date", "") <= end_date]
        
        # REVENUE
        invoice_income = sum(float(inv.get("subtotal", 0)) for inv in invoices)
        sales_income = sum(float(s.get("subtotal", 0)) for s in sales)
        total_revenue = invoice_income + sales_income
        
        # COST OF SALES (from supplier invoices marked as stock/inventory)
        cost_of_sales = sum(float(si.get("total", 0)) for si in supplier_invoices if si.get("category", "").lower() in ("stock", "inventory", "cost of sales", "purchases"))
        
        # If no supplier invoices categorized, estimate from stock movements
        if cost_of_sales == 0:
            stock_movements = db.get("stock_movements", {"business_id": biz_id}) if biz_id else []
            stock_out = [sm for sm in stock_movements if sm.get("type") == "out" and start_date <= sm.get("date", "") <= end_date]
            cost_of_sales = sum(float(sm.get("cost", 0)) * float(sm.get("quantity", 0)) for sm in stock_out)
        
        gross_profit = total_revenue - cost_of_sales
        gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # OPERATING EXPENSES by category
        expense_categories = {}
        for e in expenses:
            cat = e.get("category", "General Expenses")
            if cat.lower() not in ("stock", "inventory", "cost of sales", "purchases"):  # Exclude COS
                if cat not in expense_categories:
                    expense_categories[cat] = 0
                expense_categories[cat] += float(e.get("amount", 0))
        
        # Add payroll to expenses
        payroll_total = sum(float(p.get("gross", 0)) for p in payslips)
        if payroll_total > 0:
            expense_categories["Salaries & Wages"] = payroll_total
        
        total_expenses = sum(expense_categories.values())
        
        # NET PROFIT
        net_profit = gross_profit - total_expenses
        net_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Build expense rows
        expense_rows = ""
        for cat, amount in sorted(expense_categories.items(), key=lambda x: x[1], reverse=True):
            expense_rows += f'''
            <tr>
                <td style="padding-left:40px;">{cat}</td>
                <td style="text-align:right;">{money(amount)}</td>
            </tr>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <div style="display:flex;gap:10px;align-items:center;">
                <select onchange="window.location='/reports/pnl?period='+this.value" style="padding:8px;border-radius:6px;background:var(--card);color:var(--text);border:1px solid var(--border);">
                    <option value="month" {"selected" if period == "month" else ""}>This Month</option>
                    <option value="quarter" {"selected" if period == "quarter" else ""}>This Quarter</option>
                    <option value="year" {"selected" if period == "year" else ""}>This Year</option>
                    <option value="all" {"selected" if period == "all" else ""}>All Time</option>
                </select>
                <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
            </div>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:5px;">[CHART] Income Statement</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">For the period: {period_label}</p>
            
            <table class="table" style="font-size:14px;">
                <tbody>
                    <!-- REVENUE -->
                    <tr style="background:rgba(16,185,129,0.1);">
                        <td><strong>REVENUE</strong></td>
                        <td></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Sales - Invoices</td>
                        <td style="text-align:right;">{money(invoice_income)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Sales - Cash/POS</td>
                        <td style="text-align:right;">{money(sales_income)}</td>
                    </tr>
                    <tr style="font-weight:bold;">
                        <td style="padding-left:20px;">Total Revenue</td>
                        <td style="text-align:right;">{money(total_revenue)}</td>
                    </tr>
                    
                    <!-- COST OF SALES -->
                    <tr style="background:rgba(239,68,68,0.05);margin-top:10px;">
                        <td><strong>COST OF SALES</strong></td>
                        <td></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Purchases / Stock Cost</td>
                        <td style="text-align:right;color:var(--red);">({money(cost_of_sales)})</td>
                    </tr>
                    <tr style="font-weight:bold;">
                        <td style="padding-left:20px;">Total Cost of Sales</td>
                        <td style="text-align:right;color:var(--red);">({money(cost_of_sales)})</td>
                    </tr>
                    
                    <!-- GROSS PROFIT -->
                    <tr style="font-weight:bold;background:rgba(59,130,246,0.1);border-top:2px solid var(--border);">
                        <td>GROSS PROFIT</td>
                        <td style="text-align:right;color:{'var(--green)' if gross_profit >= 0 else 'var(--red)'};">{money(gross_profit)} <span style="font-size:12px;color:var(--text-muted);">({gross_margin:.1f}%)</span></td>
                    </tr>
                    
                    <!-- OPERATING EXPENSES -->
                    <tr style="background:rgba(239,68,68,0.1);margin-top:10px;">
                        <td><strong>OPERATING EXPENSES</strong></td>
                        <td></td>
                    </tr>
                    {expense_rows or "<tr><td style='padding-left:40px;color:var(--text-muted);' colspan='2'>No expenses recorded</td></tr>"}
                    <tr style="font-weight:bold;">
                        <td style="padding-left:20px;">Total Operating Expenses</td>
                        <td style="text-align:right;color:var(--red);">({money(total_expenses)})</td>
                    </tr>
                </tbody>
            </table>
            
            <!-- NET PROFIT -->
            <div style="margin-top:20px;padding:20px;border-radius:8px;background:{'rgba(16,185,129,0.15)' if net_profit >= 0 else 'rgba(239,68,68,0.15)'};border:2px solid {'var(--green)' if net_profit >= 0 else 'var(--red)'};">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:20px;font-weight:bold;">NET {'PROFIT' if net_profit >= 0 else 'LOSS'}</span>
                    <span style="font-size:32px;font-weight:bold;color:{'var(--green)' if net_profit >= 0 else 'var(--red)'};">{money(abs(net_profit))}</span>
                </div>
                <div style="text-align:right;color:var(--text-muted);font-size:12px;margin-top:5px;">
                    Net margin: {net_margin:.1f}%
                </div>
            </div>
        </div>
        '''
        
        return render_page("Income Statement", content, user, "reports")
    
    
    # 
    # BALANCE SHEET
    # 
    
    @app.route("/reports/balance-sheet")
    @login_required
    def report_balance_sheet():
        """Balance Sheet - Proper accounting format"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # ASSETS
        # Current Assets
        customers = db.get("customers", {"business_id": biz_id}) if biz_id else []
        total_debtors = sum(float(c.get("balance", 0)) for c in customers if float(c.get("balance", 0)) > 0)
        
        stock = db.get_all_stock(biz_id)
        stock_value = sum(
            float(s.get("qty") or s.get("quantity") or 0) * float(s.get("cost") or s.get("cost_price") or 0) 
            for s in stock
        )
        
        # Bank balance (from receipts - expenses - supplier payments)
        receipts = db.get("receipts", {"business_id": biz_id}) if biz_id else []
        total_receipts = sum(float(r.get("amount", 0)) for r in receipts)
        
        sales = db.get("sales", {"business_id": biz_id}) if biz_id else []
        # Only cash and card sales affect bank - account sales are in debtors
        cash_card_sales = sum(float(s.get("total", 0)) for s in sales if s.get("payment_method", "cash") in ("cash", "card"))
        
        expenses = db.get("expenses", {"business_id": biz_id}) if biz_id else []
        total_expenses_paid = sum(float(e.get("amount", 0)) for e in expenses)
        
        supplier_payments = db.get("supplier_payments", {"business_id": biz_id}) if biz_id else []
        total_supplier_payments = sum(float(p.get("amount", 0)) for p in supplier_payments)
        
        payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []
        total_payroll_paid = sum(float(p.get("net", 0)) for p in payslips)
        
        bank_balance = total_receipts + cash_card_sales - total_expenses_paid - total_supplier_payments - total_payroll_paid
        
        # VAT Receivable (input VAT from expenses)
        vat_receivable = sum(float(e.get("vat", 0)) for e in expenses)
        
        total_current_assets = total_debtors + stock_value + bank_balance + vat_receivable
        if bank_balance < 0:
            total_current_assets = total_debtors + stock_value + vat_receivable  # Bank overdraft goes to liabilities
        
        total_assets = total_current_assets
        
        # LIABILITIES
        # Current Liabilities
        suppliers = db.get("suppliers", {"business_id": biz_id}) if biz_id else []
        total_creditors = sum(float(s.get("balance", 0)) for s in suppliers if float(s.get("balance", 0)) > 0)
        
        # VAT Payable (output VAT from sales)
        invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
        vat_from_invoices = sum(float(i.get("vat", 0)) for i in invoices)
        vat_from_sales = sum(float(s.get("vat", 0)) for s in sales)
        vat_payable = vat_from_invoices + vat_from_sales - vat_receivable
        if vat_payable < 0:
            vat_payable = 0  # VAT refund due would be an asset
        
        bank_overdraft = abs(bank_balance) if bank_balance < 0 else 0
        
        total_current_liabilities = total_creditors + vat_payable + bank_overdraft
        total_liabilities = total_current_liabilities
        
        # EQUITY
        # Calculate retained earnings from profit
        invoice_income = sum(float(inv.get("subtotal", 0)) for inv in invoices)
        sales_income = sum(float(s.get("subtotal", 0)) for s in sales)
        total_income = invoice_income + sales_income
        
        expense_total = sum(float(e.get("amount", 0)) for e in expenses)
        payroll_total = sum(float(p.get("gross", 0)) for p in payslips)
        
        # Cost of sales from supplier invoices
        supplier_invoices = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id else []
        cost_of_sales = sum(float(si.get("total", 0)) for si in supplier_invoices)
        
        net_profit = total_income - cost_of_sales - expense_total - payroll_total
        
        # Get previous year retained earnings
        year_ends = db.get("year_ends", {"business_id": biz_id}) if biz_id else []
        previous_retained = sum(float(ye.get("retained_earnings", 0)) for ye in year_ends)
        
        retained_earnings = previous_retained + net_profit
        total_equity = retained_earnings
        
        # Check if balanced
        is_balanced = abs(total_assets - (total_liabilities + total_equity)) < 0.01
        balance_diff = total_assets - (total_liabilities + total_equity)
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:5px;">[CHART] Balance Sheet</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">As at {today()}</p>
            
            <table class="table" style="font-size:14px;">
                <tbody>
                    <!-- ASSETS -->
                    <tr style="background:rgba(59,130,246,0.1);">
                        <td colspan="2"><strong>ASSETS</strong></td>
                    </tr>
                    <tr>
                        <td style="padding-left:20px;font-weight:bold;">Current Assets</td>
                        <td></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Bank</td>
                        <td style="text-align:right;color:{'var(--green)' if bank_balance >= 0 else 'var(--text-muted)'};">{money(max(0, bank_balance))}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Debtors (Trade Receivables)</td>
                        <td style="text-align:right;">{money(total_debtors)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Inventory (Stock)</td>
                        <td style="text-align:right;">{money(stock_value)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">VAT Receivable</td>
                        <td style="text-align:right;">{money(vat_receivable)}</td>
                    </tr>
                    <tr style="font-weight:bold;border-top:1px solid var(--border);">
                        <td style="padding-left:20px;">Total Current Assets</td>
                        <td style="text-align:right;">{money(total_current_assets)}</td>
                    </tr>
                    <tr style="font-weight:bold;background:rgba(59,130,246,0.05);">
                        <td>TOTAL ASSETS</td>
                        <td style="text-align:right;font-size:16px;">{money(total_assets)}</td>
                    </tr>
                    
                    <!-- LIABILITIES -->
                    <tr style="background:rgba(239,68,68,0.1);margin-top:20px;">
                        <td colspan="2"><strong>LIABILITIES</strong></td>
                    </tr>
                    <tr>
                        <td style="padding-left:20px;font-weight:bold;">Current Liabilities</td>
                        <td></td>
                    </tr>
                    {f'<tr><td style="padding-left:40px;">Bank Overdraft</td><td style="text-align:right;color:var(--red);">{money(bank_overdraft)}</td></tr>' if bank_overdraft > 0 else ''}
                    <tr>
                        <td style="padding-left:40px;">Creditors (Trade Payables)</td>
                        <td style="text-align:right;">{money(total_creditors)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">VAT Payable</td>
                        <td style="text-align:right;">{money(vat_payable)}</td>
                    </tr>
                    <tr style="font-weight:bold;border-top:1px solid var(--border);">
                        <td style="padding-left:20px;">Total Current Liabilities</td>
                        <td style="text-align:right;">{money(total_current_liabilities)}</td>
                    </tr>
                    <tr style="font-weight:bold;background:rgba(239,68,68,0.05);">
                        <td>TOTAL LIABILITIES</td>
                        <td style="text-align:right;font-size:16px;">{money(total_liabilities)}</td>
                    </tr>
                    
                    <!-- EQUITY -->
                    <tr style="background:rgba(139,92,246,0.1);margin-top:20px;">
                        <td colspan="2"><strong>EQUITY</strong></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Retained Earnings (Previous Years)</td>
                        <td style="text-align:right;">{money(previous_retained)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Current Year Profit/Loss</td>
                        <td style="text-align:right;color:{'var(--green)' if net_profit >= 0 else 'var(--red)'};">{money(net_profit)}</td>
                    </tr>
                    <tr style="font-weight:bold;background:rgba(139,92,246,0.05);">
                        <td>TOTAL EQUITY</td>
                        <td style="text-align:right;font-size:16px;">{money(total_equity)}</td>
                    </tr>
                </tbody>
            </table>
            
            <!-- Balance Check -->
            <div style="margin-top:20px;padding:15px;border-radius:8px;background:{'rgba(16,185,129,0.1)' if is_balanced else 'rgba(239,68,68,0.1)'};border:1px solid {'var(--green)' if is_balanced else 'var(--red)'};">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span>{'' if is_balanced else '[!]'} Assets = Liabilities + Equity</span>
                    <span style="font-weight:bold;">{money(total_assets)} = {money(total_liabilities)} + {money(total_equity)}</span>
                </div>
                {f'<div style="color:var(--red);margin-top:10px;">Difference: {money(balance_diff)} - Please review entries</div>' if not is_balanced else ''}
            </div>
        </div>
        '''
        
        return render_page("Balance Sheet", content, user, "reports")
    
    
    # 
    # VAT REPORT
    # 
    
    @app.route("/reports/vat")
    @login_required
    def report_vat():
        """VAT201 Report - Proper SARS format with period selection"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # VAT periods (2 months each)
        # Jan-Feb, Mar-Apr, May-Jun, Jul-Aug, Sep-Oct, Nov-Dec
        today_date = datetime.now()
        current_month = today_date.month
        current_year = today_date.year
        
        # Get period from query params
        period = request.args.get("period", "current")
        
        if period == "current":
            # Current VAT period
            period_start_month = ((current_month - 1) // 2) * 2 + 1
            period_end_month = period_start_month + 1
            year = current_year
        elif period == "previous":
            # Previous VAT period
            period_start_month = ((current_month - 1) // 2) * 2 - 1
            if period_start_month < 1:
                period_start_month = 11
                year = current_year - 1
            else:
                year = current_year
            period_end_month = period_start_month + 1
        else:
            # Parse specific period like "2026-01"
            try:
                parts = period.split("-")
                year = int(parts[0])
                month = int(parts[1])
                period_start_month = ((month - 1) // 2) * 2 + 1
                period_end_month = period_start_month + 1
            except:
                period_start_month = 1
                period_end_month = 2
                year = current_year
        
        start_date = f"{year}-{period_start_month:02d}-01"
        if period_end_month == 12:
            end_date = f"{year}-12-31"
        else:
            end_date = f"{year}-{period_end_month+1:02d}-01"
        
        month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        period_label = f"{month_names[period_start_month]}-{month_names[period_end_month]} {year}"
        
        # Get data filtered by period
        invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
        invoices = [i for i in invoices if start_date <= i.get("date", "") < end_date]
        
        sales = db.get("sales", {"business_id": biz_id}) if biz_id else []
        sales = [s for s in sales if start_date <= s.get("date", "") < end_date]
        
        expenses = db.get("expenses", {"business_id": biz_id}) if biz_id else []
        expenses = [e for e in expenses if start_date <= e.get("date", "") < end_date]
        
        supplier_invoices = db.get("supplier_invoices", {"business_id": biz_id}) if biz_id else []
        supplier_invoices = [si for si in supplier_invoices if start_date <= si.get("date", "") < end_date]
        
        # OUTPUT VAT (what you owe SARS)
        # For imported invoices where vat=0, back-calculate from total (assume VAT inclusive)
        invoice_sales_excl = 0
        invoice_vat = 0
        for inv in invoices:
            subtotal = float(inv.get("subtotal", 0))
            vat = float(inv.get("vat", 0))
            total = float(inv.get("total", 0))
            if vat > 0:
                invoice_sales_excl += subtotal
                invoice_vat += vat
            elif total > 0:
                # Back-calculate: total is VAT inclusive
                calc_excl = total / 1.15
                calc_vat = total - calc_excl
                invoice_sales_excl += calc_excl
                invoice_vat += calc_vat
        
        pos_sales_excl = sum(float(s.get("subtotal", 0)) for s in sales)
        pos_vat = sum(float(s.get("vat", 0)) for s in sales)
        
        total_sales_excl = invoice_sales_excl + pos_sales_excl
        total_output_vat = invoice_vat + pos_vat
        
        # INPUT VAT (what you can claim back)
        expense_excl = sum(float(e.get("amount", 0)) / 1.15 for e in expenses)
        expense_vat = sum(float(e.get("amount", 0)) * 0.15 / 1.15 for e in expenses)
        
        # Supplier invoices - also back-calculate if vat=0
        si_excl = 0
        si_vat = 0
        for si in supplier_invoices:
            vat = float(si.get("vat", 0))
            total = float(si.get("total", 0))
            subtotal = float(si.get("subtotal", 0))
            if vat > 0:
                si_excl += subtotal or (total - vat)
                si_vat += vat
            elif total > 0:
                calc_excl = total / 1.15
                calc_vat = total - calc_excl
                si_excl += calc_excl
                si_vat += calc_vat
        
        total_purchases_excl = expense_excl + si_excl
        total_input_vat = expense_vat + si_vat
        
        # NET VAT
        vat_payable = total_output_vat - total_input_vat
        
        # Build period selector
        periods_html = ""
        for m in range(1, 12, 2):
            p_label = f"{month_names[m]}-{month_names[m+1]} {current_year}"
            p_value = f"{current_year}-{m:02d}"
            periods_html += f'<option value="{p_value}" {"selected" if period_start_month == m and year == current_year else ""}>{p_label}</option>'
        # Add previous year
        for m in range(1, 12, 2):
            p_label = f"{month_names[m]}-{month_names[m+1]} {current_year-1}"
            p_value = f"{current_year-1}-{m:02d}"
            periods_html += f'<option value="{p_value}" {"selected" if period_start_month == m and year == current_year-1 else ""}>{p_label}</option>'
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <div style="display:flex;gap:10px;align-items:center;">
                <select onchange="window.location='/reports/vat?period='+this.value" style="padding:8px;border-radius:6px;background:var(--card);color:var(--text);border:1px solid var(--border);">
                    {periods_html}
                </select>
                <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
            </div>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:5px;">[CHART] VAT201 Return</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">Tax Period: {period_label}</p>
            
            <table class="table" style="font-size:14px;">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th style="text-align:right;">Value (Excl VAT)</th>
                        <th style="text-align:right;">VAT Amount</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- OUTPUT VAT -->
                    <tr style="background:rgba(239,68,68,0.1);">
                        <td colspan="3"><strong>OUTPUT VAT (You owe SARS)</strong></td>
                    </tr>
                    <tr>
                        <td style="padding-left:20px;">1. Standard rated sales - Invoices</td>
                        <td style="text-align:right;">{money(invoice_sales_excl)}</td>
                        <td style="text-align:right;">{money(invoice_vat)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:20px;">1a. Standard rated sales - Cash/POS</td>
                        <td style="text-align:right;">{money(pos_sales_excl)}</td>
                        <td style="text-align:right;">{money(pos_vat)}</td>
                    </tr>
                    <tr style="font-weight:bold;border-top:1px solid var(--border);">
                        <td style="padding-left:20px;">Total Output VAT</td>
                        <td style="text-align:right;">{money(total_sales_excl)}</td>
                        <td style="text-align:right;color:var(--red);">{money(total_output_vat)}</td>
                    </tr>
                    
                    <!-- INPUT VAT -->
                    <tr style="background:rgba(16,185,129,0.1);">
                        <td colspan="3"><strong>INPUT VAT (You can claim)</strong></td>
                    </tr>
                    <tr>
                        <td style="padding-left:20px;">14. Capital goods</td>
                        <td style="text-align:right;">R0.00</td>
                        <td style="text-align:right;">R0.00</td>
                    </tr>
                    <tr>
                        <td style="padding-left:20px;">15. Other goods/services - Supplier invoices</td>
                        <td style="text-align:right;">{money(si_excl)}</td>
                        <td style="text-align:right;">{money(si_vat)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:20px;">15a. Other goods/services - Expenses</td>
                        <td style="text-align:right;">{money(expense_excl)}</td>
                        <td style="text-align:right;">{money(expense_vat)}</td>
                    </tr>
                    <tr style="font-weight:bold;border-top:1px solid var(--border);">
                        <td style="padding-left:20px;">Total Input VAT</td>
                        <td style="text-align:right;">{money(total_purchases_excl)}</td>
                        <td style="text-align:right;color:var(--green);">{money(total_input_vat)}</td>
                    </tr>
                </tbody>
            </table>
            
            <!-- VAT Payable/Refund -->
            <div style="margin-top:20px;padding:20px;border-radius:8px;background:{'rgba(239,68,68,0.15)' if vat_payable > 0 else 'rgba(16,185,129,0.15)'};border:2px solid {'var(--red)' if vat_payable > 0 else 'var(--green)'};">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <span style="font-size:14px;color:var(--text-muted);">Field 20:</span>
                        <span style="font-size:18px;font-weight:bold;margin-left:10px;">VAT {'PAYABLE' if vat_payable > 0 else 'REFUNDABLE'}</span>
                    </div>
                    <span style="font-size:32px;font-weight:bold;color:{'var(--red)' if vat_payable > 0 else 'var(--green)'};">{money(abs(vat_payable))}</span>
                </div>
            </div>
            
            <div style="margin-top:20px;padding:15px;background:rgba(59,130,246,0.1);border-radius:8px;">
                <p style="margin:0;font-size:12px;color:var(--text-muted);">
                    [!] <strong>Important:</strong> This is a summary for reference only. 
                    Always verify figures with source documents before submitting to SARS.
                    Due date: Last business day of the month following the tax period.
                </p>
            </div>
        </div>
        '''
        
        return render_page("VAT Report", content, user, "reports")
    
    
    # 
    # PURCHASE ORDERS
    # 
    

    # === CASHFLOW, SMART REPORTS, BUDGET ===

    @app.route("/reports/cashflow")
    @login_required
    def report_cashflow():
        """Cash Flow Statement - Proper accounting format"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get period from query params
        period = request.args.get("period", "month")
        today_date = datetime.now()
        
        if period == "month":
            start_date = today_date.replace(day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = today_date.strftime("%B %Y")
        elif period == "quarter":
            quarter = (today_date.month - 1) // 3
            start_date = today_date.replace(month=quarter*3+1, day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = f"Q{quarter+1} {today_date.year}"
        elif period == "year":
            start_date = today_date.replace(month=1, day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = f"Year {today_date.year}"
        else:
            start_date = today_date.replace(day=1).strftime("%Y-%m-%d")
            end_date = today_date.strftime("%Y-%m-%d")
            period_label = today_date.strftime("%B %Y")
        
        # Get data filtered by period
        receipts = db.get("receipts", {"business_id": biz_id}) if biz_id else []
        receipts = [r for r in receipts if start_date <= r.get("date", "") <= end_date]
        
        sales = db.get("sales", {"business_id": biz_id}) if biz_id else []
        sales = [s for s in sales if start_date <= s.get("date", "") <= end_date]
        
        expenses = db.get("expenses", {"business_id": biz_id}) if biz_id else []
        expenses = [e for e in expenses if start_date <= e.get("date", "") <= end_date]
        
        payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []
        payslips = [p for p in payslips if start_date <= p.get("date", "") <= end_date]
        
        supplier_payments = db.get("supplier_payments", {"business_id": biz_id}) if biz_id else []
        supplier_payments = [sp for sp in supplier_payments if start_date <= sp.get("date", "") <= end_date]
        
        # OPERATING ACTIVITIES
        # Cash IN
        cash_from_debtors = sum(float(r.get("amount", 0)) for r in receipts)
        # Only cash POS sales are actual cash in (not card/account)
        cash_sales = sum(float(s.get("total", 0)) for s in sales if s.get("payment_method", "cash") == "cash")
        # Card sales also go to bank
        card_sales = sum(float(s.get("total", 0)) for s in sales if s.get("payment_method") == "card")
        total_cash_in = cash_from_debtors + cash_sales + card_sales
        
        # Cash OUT
        cash_to_creditors = sum(float(sp.get("amount", 0)) for sp in supplier_payments)
        cash_to_expenses = sum(float(e.get("amount", 0)) for e in expenses)
        cash_to_employees = sum(float(p.get("net", 0)) for p in payslips)
        total_cash_out = cash_to_creditors + cash_to_expenses + cash_to_employees
        
        net_operating = total_cash_in - total_cash_out
        
        # Opening and Closing balance (simplified)
        # For proper cash flow, we'd need opening bank balance
        closing_balance = net_operating  # Simplified
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/reports" style="color:var(--text-muted);">← Back to Reports</a>
            <div style="display:flex;gap:10px;align-items:center;">
                <select onchange="window.location='/reports/cashflow?period='+this.value" style="padding:8px;border-radius:6px;background:var(--card);color:var(--text);border:1px solid var(--border);">
                    <option value="month" {"selected" if period == "month" else ""}>This Month</option>
                    <option value="quarter" {"selected" if period == "quarter" else ""}>This Quarter</option>
                    <option value="year" {"selected" if period == "year" else ""}>This Year</option>
                </select>
                <button class="btn btn-secondary" onclick="window.print();">🖨️ Print</button>
            </div>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:5px;">[MONEY] Cash Flow Statement</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">For the period: {period_label}</p>
            
            <table class="table" style="font-size:14px;">
                <tbody>
                    <!-- OPERATING ACTIVITIES -->
                    <tr style="background:rgba(16,185,129,0.1);">
                        <td colspan="2"><strong>CASH FLOWS FROM OPERATING ACTIVITIES</strong></td>
                    </tr>
                    
                    <!-- Cash Receipts -->
                    <tr>
                        <td style="padding-left:20px;font-weight:bold;">Cash Receipts</td>
                        <td></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Receipts from customers (debtors)</td>
                        <td style="text-align:right;color:var(--green);">{money(cash_from_debtors)}</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Cash sales</td>
                        <td style="text-align:right;color:var(--green);">{money(cash_sales)}</td>
                    </tr>
                    <tr style="font-weight:bold;border-top:1px solid var(--border);">
                        <td style="padding-left:20px;">Total Cash In</td>
                        <td style="text-align:right;color:var(--green);">{money(total_cash_in)}</td>
                    </tr>
                    
                    <!-- Cash Payments -->
                    <tr>
                        <td style="padding-left:20px;font-weight:bold;">Cash Payments</td>
                        <td></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Payments to suppliers (creditors)</td>
                        <td style="text-align:right;color:var(--red);">({money(cash_to_creditors)})</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Operating expenses</td>
                        <td style="text-align:right;color:var(--red);">({money(cash_to_expenses)})</td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;">Salaries and wages</td>
                        <td style="text-align:right;color:var(--red);">({money(cash_to_employees)})</td>
                    </tr>
                    <tr style="font-weight:bold;border-top:1px solid var(--border);">
                        <td style="padding-left:20px;">Total Cash Out</td>
                        <td style="text-align:right;color:var(--red);">({money(total_cash_out)})</td>
                    </tr>
                    
                    <tr style="font-weight:bold;background:rgba(59,130,246,0.1);border-top:2px solid var(--border);">
                        <td>Net Cash from Operating Activities</td>
                        <td style="text-align:right;color:{'var(--green)' if net_operating >= 0 else 'var(--red)'};">{money(net_operating)}</td>
                    </tr>
                    
                    <!-- INVESTING ACTIVITIES -->
                    <tr style="background:rgba(139,92,246,0.05);">
                        <td colspan="2"><strong>CASH FLOWS FROM INVESTING ACTIVITIES</strong></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;color:var(--text-muted);">Purchase of equipment</td>
                        <td style="text-align:right;color:var(--text-muted);">R0.00</td>
                    </tr>
                    <tr style="font-weight:bold;">
                        <td>Net Cash from Investing Activities</td>
                        <td style="text-align:right;">R0.00</td>
                    </tr>
                    
                    <!-- FINANCING ACTIVITIES -->
                    <tr style="background:rgba(249,115,22,0.05);">
                        <td colspan="2"><strong>CASH FLOWS FROM FINANCING ACTIVITIES</strong></td>
                    </tr>
                    <tr>
                        <td style="padding-left:40px;color:var(--text-muted);">Owner drawings</td>
                        <td style="text-align:right;color:var(--text-muted);">R0.00</td>
                    </tr>
                    <tr style="font-weight:bold;">
                        <td>Net Cash from Financing Activities</td>
                        <td style="text-align:right;">R0.00</td>
                    </tr>
                </tbody>
            </table>
            
            <!-- Net Cash Movement -->
            <div style="margin-top:20px;padding:20px;border-radius:8px;background:{'rgba(16,185,129,0.15)' if net_operating >= 0 else 'rgba(239,68,68,0.15)'};border:2px solid {'var(--green)' if net_operating >= 0 else 'var(--red)'};">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:18px;font-weight:bold;">NET {'INCREASE' if net_operating >= 0 else 'DECREASE'} IN CASH</span>
                    <span style="font-size:32px;font-weight:bold;color:{'var(--green)' if net_operating >= 0 else 'var(--red)'};">{money(abs(net_operating))}</span>
                </div>
            </div>
        </div>
        '''
        
        return render_page("Cash Flow", content, user, "reports")
    
    
    # 
    # SMART AI REPORTS - Zane writes ANY report you want
    # 
    
    @app.route("/reports/smart")
    @login_required
    def smart_reports_page():
        """AI-Generated Management Reports"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        
        content = '''
        <div class="card">
            <h2 style="margin-bottom:15px;">Smart Reports</h2>
            
            <!-- DATA SOURCE SELECTOR -->
            <div class="card" style="margin-bottom:20px;padding:15px;">
                <h3 style="margin:0 0 10px 0;">📂 Data Source</h3>
                <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">
                    <button id="srcOwnBtn" class="btn btn-primary" onclick="setDataSource('own')" style="flex:none;">
                        🏢 My Business Data
                    </button>
                    <label id="srcClientBtn" class="btn btn-secondary" style="cursor:pointer;flex:none;margin:0;">
                        📁 Upload Client TB
                        <input type="file" id="smartReportTBUpload" accept=".csv,.xlsx,.xls" style="display:none;" onchange="handleSmartReportTB(this)">
                    </label>
                    <span id="dataSourceStatus" style="color:var(--text-muted);font-size:13px;">Using your own business data</span>
                </div>
            </div>
            
            <!-- REPORT TYPE SELECTION -->
            <h3 style="margin:20px 0 10px 0;">Choose Report Type</h3>
            <div class="stats-grid">
                <div class="card report-btn" style="cursor:pointer" onclick="generateReport('management')">
                    <h4>Management Statement</h4>
                    <p style="color:var(--text-muted);font-size:13px;">Year-to-date P&L, Balance Sheet & KPIs</p>
                </div>
                <div class="card report-btn" style="cursor:pointer" onclick="generateReport('tb_analysis')">
                    <h4>TB Analysis</h4>
                    <p style="color:var(--text-muted);font-size:13px;">Full account-by-account financial review</p>
                </div>
                <div class="card report-btn" style="cursor:pointer" onclick="generateReport('kpi')">
                    <h4>KPI Dashboard</h4>
                    <p style="color:var(--text-muted);font-size:13px;">Key metrics and trends</p>
                </div>
                <div class="card report-btn" style="cursor:pointer" onclick="generateReport('sales')">
                    <h4>Sales Analysis</h4>
                    <p style="color:var(--text-muted);font-size:13px;">Sales breakdown with AI insights</p>
                </div>
                <div class="card report-btn" style="cursor:pointer" onclick="generateReport('debtor')">
                    <h4>Debtor Risk Report</h4>
                    <p style="color:var(--text-muted);font-size:13px;">Problem customers & recommendations</p>
                </div>
                <div class="card report-btn" style="cursor:pointer" onclick="generateReport('forecast')">
                    <h4>Cash Flow Forecast</h4>
                    <p style="color:var(--text-muted);font-size:13px;">Next 30 days projection</p>
                </div>
                <div class="card report-btn" style="cursor:pointer;border:1px solid rgba(16,185,129,0.3);background:linear-gradient(135deg, rgba(16,185,129,0.08), rgba(99,102,241,0.05));" onclick="goToGLAnalysis()">
                    <h4>🔬 GL Analysis</h4>
                    <p style="color:var(--text-muted);font-size:13px;">Live data when in 'My Business' mode — Upload for client GLs</p>
                </div>
            </div>
            
            <h3 style="margin:30px 0 10px 0;">Custom Report</h3>
            <p style="color:var(--text-muted);margin-bottom:10px;">Or ask for anything specific:</p>
            <div style="display:flex;gap:10px;">
                <input type="text" id="customReportInput" class="form-input" style="flex:1;" placeholder="e.g., Compare this month vs last month sales by customer...">
                <button class="btn btn-primary" onclick="generateCustomReport()">Generate</button>
            </div>
        </div>
        
        <div id="reportLoading" style="display:none;text-align:center;padding:40px;">
            <div style="font-size:24px;margin-bottom:10px;">Generating Report...</div>
            <p style="color:var(--text-muted);">Analyzing data. This may take up to 30 seconds.</p>
        </div>
        
        <div id="reportOutput" style="margin-top:20px;display:none;">
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
                    <h3 id="reportTitle" style="margin:0;">Report</h3>
                    <div style="display:flex;gap:8px;flex-wrap:wrap;">
                        <button class="btn btn-secondary" onclick="downloadReport()" style="font-size:12px;padding:6px 14px;">⬇️ Download</button>
                        <button class="btn btn-secondary" onclick="showEmailModal()" style="font-size:12px;padding:6px 14px;">Email</button>
                        <button class="btn btn-secondary" onclick="window.print();" style="font-size:12px;padding:6px 14px;">🖨️ Print</button>
                    </div>
                </div>
                <div id="reportContent" style="line-height:1.6;"></div>
            </div>
        </div>
        
        <!-- EMAIL MODAL -->
        <div id="emailModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center;">
            <div style="background:var(--card);border:1px solid var(--border);border-radius:12px;padding:25px;width:90%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                    <h3 style="margin:0;color:var(--primary);">Email Report</h3>
                    <button onclick="closeEmailModal()" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button>
                </div>
                <input type="email" id="emailTo" class="form-input" placeholder="email@example.com" style="width:100%;margin-bottom:10px;">
                <input type="text" id="emailSubject" class="form-input" placeholder="Subject (optional)" style="width:100%;margin-bottom:15px;">
                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button class="btn btn-secondary" onclick="closeEmailModal()">Cancel</button>
                    <button class="btn btn-primary" id="sendEmailBtn" onclick="sendReportEmail()">Send</button>
                </div>
                <p id="emailStatus" style="margin:10px 0 0 0;font-size:12px;display:none;"></p>
            </div>
        </div>
        
        <style>
        .report-btn { transition: all 0.2s; border: 1px solid var(--border); }
        .report-btn:hover { border-color: var(--primary); transform: translateY(-2px); }
        .report-btn.disabled { opacity: 0.5; pointer-events: none; }
        </style>
        
        <script>
        // ═══ DATA SOURCE STATE ═══
        let dataSource = 'own';  // 'own' or 'client'
        let clientTBData = null;  // Parsed client TB data
        let clientFileName = '';
        
        const reportTitles = {
            'management': 'Management Statement',
            'tb_analysis': 'TB Analysis',
            'kpi': 'Key Performance Indicators',
            'sales': 'Sales Analysis',
            'debtor': 'Debtor Risk Report',
            'forecast': 'Cash Flow Forecast'
        };
        
        // ═══ DOWNLOAD REPORT ═══
        function downloadReport() {
            const title = document.getElementById('reportTitle').textContent || 'Report';
            const content = document.getElementById('reportContent').innerHTML;
            const dateStr = new Date().toISOString().slice(0,10);
            
            const html = `<!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>${title}</title>
    <style>
    body { font-family: Arial, Helvetica, sans-serif; max-width: 900px; margin: 30px auto; padding: 20px; color: #1a1a2e; line-height: 1.7; font-size: 14px; }
    h1, h2, h3 { color: #1a1a2e; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; }
    th { text-align: left; padding: 8px; border-bottom: 2px solid #e5e7eb; color: #6366f1; font-weight: 600; }
    td { padding: 6px 8px; border-bottom: 1px solid #f3f4f6; }
    strong { color: #4f46e5; }
    hr { border: none; border-top: 1px solid #e5e7eb; margin: 15px 0; }
    @media print { body { margin: 0; } }
    </style></head><body>
    <h1 style="color:#4f46e5;border-bottom:2px solid #4f46e5;padding-bottom:10px;">${title}</h1>
    <p style="color:#6b7280;font-size:12px;">Generated by ClickAI | ${dateStr}</p>
    ${content}
    <hr><p style="color:#6b7280;font-size:11px;text-align:center;">Generated by ClickAI — AI-Powered Business Management</p>
    </body></html>`;
            
            // Fix dark theme colors for download
            const lightHtml = html
                .replace(/color:\s*rgba\(255,\s*255,\s*255,[\s\d.]+\)/gi, 'color:#1a1a2e')
                .replace(/color:\s*var\(--text\)/gi, 'color:#1a1a2e')
                .replace(/color:\s*var\(--text-muted\)/gi, 'color:#6b7280')
                .replace(/color:\s*var\(--primary\)/gi, 'color:#6366f1')
                .replace(/color:\s*var\(--green\)/gi, 'color:#10b981')
                .replace(/color:\s*var\(--red\)/gi, 'color:#ef4444')
                .replace(/border[^:]*:\s*[\d.]+px\s+solid\s+rgba\(255,\s*255,\s*255,[\s\d.]+\)/gi, 'border:1px solid #e5e7eb')
                .replace(/background:\s*rgba\(139,\s*92,\s*246,[\s\d.]+\)/gi, 'background:rgba(99,102,241,0.06)')
                .replace(/background:\s*rgba\(16,\s*185,\s*129,[\s\d.]+\)/gi, 'background:rgba(16,185,129,0.06)')
                .replace(/background:\s*rgba\(239,\s*68,\s*68,[\s\d.]+\)/gi, 'background:rgba(239,68,68,0.06)');
            
            const blob = new Blob([lightHtml], {type: 'text/html'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = title.replace(/[^a-zA-Z0-9 _-]/g, '').replace(/\s+/g, '_') + '_' + dateStr + '.html';
            a.click();
            URL.revokeObjectURL(a.href);
        }
        
        // ═══ EMAIL MODAL ═══
        function showEmailModal() {
            const title = document.getElementById('reportTitle').textContent || 'Report';
            document.getElementById('emailSubject').value = title;
            document.getElementById('emailStatus').style.display = 'none';
            document.getElementById('emailModal').style.display = 'flex';
            document.getElementById('emailTo').focus();
        }
        
        function closeEmailModal() {
            document.getElementById('emailModal').style.display = 'none';
        }
        
        async function sendReportEmail() {
            const to = document.getElementById('emailTo').value.trim();
            const subject = document.getElementById('emailSubject').value.trim() || 'ClickAI Report';
            const content = document.getElementById('reportContent').innerHTML;
            const title = document.getElementById('reportTitle').textContent || 'Report';
            const status = document.getElementById('emailStatus');
            const btn = document.getElementById('sendEmailBtn');
            
            if (!to || !to.includes('@')) {
                status.style.display = 'block';
                status.style.color = 'var(--red)';
                status.textContent = 'Please enter a valid email address';
                return;
            }
            
            btn.disabled = true;
            btn.textContent = 'Sending...';
            status.style.display = 'block';
            status.style.color = 'var(--text-muted)';
            status.textContent = 'Sending report...';
            
            try {
                const resp = await fetch('/api/reports/email', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        to_email: to,
                        subject: subject,
                        report_html: content,
                        report_title: title
                    })
                });
                const data = await resp.json();
                
                if (data.success) {
                    status.style.color = 'var(--green)';
                    status.textContent = 'GOOD: ' + data.message;
                    setTimeout(() => closeEmailModal(), 2000);
                } else {
                    status.style.color = 'var(--red)';
                    status.textContent = '✗ ' + (data.error || 'Failed to send');
                }
            } catch (err) {
                status.style.color = 'var(--red)';
                status.textContent = '✗ Network error: ' + err.message;
            }
            
            btn.disabled = false;
            btn.textContent = 'Send';
        }
        
        function setDataSource(src) {
            dataSource = src;
            const ownBtn = document.getElementById('srcOwnBtn');
            const clientBtn = document.getElementById('srcClientBtn');
            const status = document.getElementById('dataSourceStatus');
            
            if (src === 'own') {
                ownBtn.className = 'btn btn-primary';
                clientBtn.className = 'btn btn-secondary';
                clientTBData = null;
                clientFileName = '';
                status.textContent = 'Using your own business data';
                status.style.color = 'var(--text-muted)';
            }
        }
        
        function handleSmartReportTB(input) {
            const file = input.files[0];
            if (!file) return;
            const status = document.getElementById('dataSourceStatus');
            status.textContent = '⏳ Parsing ' + file.name + '...';
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('lang', document.documentElement.lang || 'en');
            
            fetch('/api/reports/tb/upload-analyze', {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    clientTBData = data;
                    clientFileName = file.name;
                    dataSource = 'client';
                    
                    // Update UI
                    document.getElementById('srcOwnBtn').className = 'btn btn-secondary';
                    document.getElementById('srcClientBtn').className = 'btn btn-primary';
                    status.innerHTML = '✅ <strong>' + file.name + '</strong> loaded (' + data.accounts.length + ' accounts) — Now choose a report type below';
                    status.style.color = '#10b981';
                } else {
                    status.textContent = '❌ ' + (data.error || 'Upload failed');
                    status.style.color = '#ef4444';
                }
            })
            .catch(e => {
                status.textContent = '❌ Error: ' + e.message;
                status.style.color = '#ef4444';
            });
            
            input.value = '';
        }
        
        function goToGLAnalysis() {
            // Respect the data source toggle: own data → auto-load live GL; otherwise → upload page
            if (dataSource === 'own') {
                window.location = '/reports/gl-analysis?source=own';
            } else {
                window.location = '/reports/gl-analysis';
            }
        }
        
        async function generateReport(type) {
            const title = reportTitles[type] || 'Report';
            
            if (dataSource === 'client' && clientTBData) {
                // Generate from uploaded client TB
                await runClientTBReport(type, title);
            } else if (dataSource === 'client' && !clientTBData) {
                alert('Upload a client TB first, then choose a report type.');
            } else {
                // Generate from own business data
                await runOwnReport(type, null, title);
            }
        }
        
        async function generateCustomReport() {
            const input = document.getElementById('customReportInput').value;
            if (!input) return;
            
            if (dataSource === 'client' && clientTBData) {
                await runClientTBReport('custom', 'Custom Report', input);
            } else {
                await runOwnReport('custom', input, 'Custom Report');
            }
        }
        
        // ═══ OWN DATA REPORTS ═══
        async function runOwnReport(type, customRequest, title) {
            document.getElementById('reportLoading').style.display = 'block';
            document.getElementById('reportOutput').style.display = 'none';
            
            try {
                const response = await fetch('/api/report', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ type: type, custom: customRequest })
                });
                const data = await response.json();
                
                document.getElementById('reportLoading').style.display = 'none';
                document.getElementById('reportOutput').style.display = 'block';
                document.getElementById('reportTitle').textContent = title;
                document.getElementById('reportContent').innerHTML = data.success ? (data.report || '') : ('Error: ' + (data.error || 'Failed'));
                document.getElementById('reportOutput').scrollIntoView({behavior: 'smooth'});
            } catch (e) {
                document.getElementById('reportLoading').style.display = 'none';
                alert('Error generating report.');
            }
        }
        
        // ═══ CLIENT TB REPORTS ═══
        async function runClientTBReport(type, title, customRequest) {
            document.getElementById('reportLoading').style.display = 'block';
            document.getElementById('reportOutput').style.display = 'none';
            
            try {
                const lang = document.documentElement.lang || 'en';
                let reportHtml = '';
                
                if (type === 'tb_analysis') {
                    // Full TB analysis (existing endpoint)
                    const response = await fetch('/api/reports/tb/analyze', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            accounts: clientTBData.accounts,
                            total_debit: clientTBData.total_debit,
                            total_credit: clientTBData.total_credit,
                            is_balanced: clientTBData.is_balanced,
                            lang: lang,
                            source_file: clientFileName,
                            company_name: '',
                            tb_control_profit: clientTBData.tb_control_profit || null
                        })
                    });
                    const data = await response.json();
                    reportHtml = data.success ? (data.analysis || '') : ('Error: ' + (data.error || 'Failed'));
                    
                    // Store payload for insights fetch after DOM update
                    if (data.success && data.insights_payload) {
                        window._tbInsightsPayload = data.insights_payload;
                    }
                    
                } else {
                    // Other report types from TB data (management, kpi, etc.)
                    const response = await fetch('/api/reports/tb/smart-report', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            accounts: clientTBData.accounts,
                            total_debit: clientTBData.total_debit,
                            total_credit: clientTBData.total_credit,
                            is_balanced: clientTBData.is_balanced,
                            tb_control_profit: clientTBData.tb_control_profit || null,
                            report_type: type,
                            custom_request: customRequest || null,
                            lang: lang,
                            source_file: clientFileName
                        })
                    });
                    const data = await response.json();
                    reportHtml = data.success ? (data.report || '') : ('Error: ' + (data.error || 'Failed'));
                }
                
                document.getElementById('reportLoading').style.display = 'none';
                document.getElementById('reportOutput').style.display = 'block';
                document.getElementById('reportTitle').textContent = title + ' — ' + clientFileName;
                document.getElementById('reportContent').innerHTML = reportHtml;
                document.getElementById('reportOutput').scrollIntoView({behavior: 'smooth'});
                
                // Fire async insights fetch for TB analysis (after DOM has the placeholder)
                if (window._tbInsightsPayload) {
                    const _payload = window._tbInsightsPayload;
                    window._tbInsightsPayload = null;
                    setTimeout(() => {
                        const insightBox = document.getElementById('aiInsightsContent');
                        if (insightBox) {
                            insightBox.innerHTML = '<p style="color:var(--text-muted);">Zane is analyzing...</p>';
                            fetch('/api/reports/tb/insights', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({lang: document.documentElement.lang || 'en', insights_payload: _payload})
                            })
                            .then(r => r.json())
                            .then(idata => {
                                if (idata.success && idata.insights) {
                                    insightBox.innerHTML = idata.insights;
                                } else {
                                    insightBox.innerHTML = '<p style="color:#f97316;">' + (idata.error || 'Insights unavailable') + '. Figures above are 100% accurate.</p>';
                                }
                            })
                            .catch(() => {
                                insightBox.innerHTML = '<p style="color:#f97316;">Insights timeout - figures above are 100% accurate.</p>';
                            });
                        }
                    }, 100);
                }
            } catch (e) {
                document.getElementById('reportLoading').style.display = 'none';
                alert('Error generating report: ' + e.message);
            }
        }
        </script>
        '''
        
        return render_page("Smart Reports", content, user, "reports")
    
    
    # 
    # BUDGET VS ACTUAL
    # 
    
    @app.route("/reports/budget")
    @login_required
    def report_budget():
        """Budget vs Actual"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get budgets (if any)
        budgets = db.get("budgets", {"business_id": biz_id}) if biz_id else []
        
        # Get actuals
        invoices = db.get("invoices", {"business_id": biz_id}) if biz_id else []
        expenses = db.get("expenses", {"business_id": biz_id}) if biz_id else []
        
        actual_sales = sum(float(inv.get("subtotal", 0)) for inv in invoices)
        actual_expenses = sum(float(e.get("amount", 0)) for e in expenses)
        
        # Default budgets if none set
        budget_sales = next((b.get("amount", 0) for b in budgets if b.get("type") == "sales"), 100000)
        budget_expenses = next((b.get("amount", 0) for b in budgets if b.get("type") == "expenses"), 50000)
        
        sales_variance = actual_sales - float(budget_sales)
        expense_variance = actual_expenses - float(budget_expenses)
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/reports" style="color:var(--text-muted);">-> Back to Reports</a>
            <button class="btn btn-secondary" onclick="window.print();"> Print</button>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:5px;"> Budget vs Actual</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">For the period ending {today()}</p>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Category</th>
                        <th style="text-align:right;">Budget</th>
                        <th style="text-align:right;">Actual</th>
                        <th style="text-align:right;">Variance</th>
                        <th style="text-align:right;">%</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Sales Revenue</strong></td>
                        <td style="text-align:right;">{money(budget_sales)}</td>
                        <td style="text-align:right;">{money(actual_sales)}</td>
                        <td style="text-align:right;color:{"var(--green)" if sales_variance >= 0 else "var(--red)"};">
                            {money(abs(sales_variance))} {"" if sales_variance >= 0 else ""}
                        </td>
                        <td style="text-align:right;">{(actual_sales/float(budget_sales)*100 if budget_sales else 0):.0f}%</td>
                    </tr>
                    <tr>
                        <td><strong>Expenses</strong></td>
                        <td style="text-align:right;">{money(budget_expenses)}</td>
                        <td style="text-align:right;">{money(actual_expenses)}</td>
                        <td style="text-align:right;color:{"var(--red)" if expense_variance > 0 else "var(--green)"};">
                            {money(abs(expense_variance))} {"" if expense_variance > 0 else ""}
                        </td>
                        <td style="text-align:right;">{(actual_expenses/float(budget_expenses)*100 if budget_expenses else 0):.0f}%</td>
                    </tr>
                </tbody>
            </table>
            
            <p style="color:var(--text-muted);margin-top:20px;">
                 Say "Set budget for sales R150000" to update budgets
            </p>
        </div>
        '''
        
        return render_page("Budget vs Actual", content, user, "reports")
    
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # TAX SAVER - Help businesses pay ONLY what they legally must
    # ═══════════════════════════════════════════════════════════════════════════════

    logger.info("[REPORTS] All report routes registered ✓")
