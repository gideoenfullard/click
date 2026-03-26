# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - PAYROLL MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Payroll page, Employee new/view/edit, Payroll run,
#           Payslip view/edit/delete, Payroll monthly report
# ==============================================================================

import json
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def register_payroll_routes(app, db, login_required, Auth, render_page,
                            generate_id, money, safe_string, now, today,
                            gl, create_journal_entry,
                            has_reactor_hud, jarvis_hud_header, jarvis_techline,
                            RecordFactory,
                            JARVIS_HUD_CSS, THEME_REACTOR_SKINS):
    """Register all Payroll, Employee and Payslip routes with the Flask app."""

    @app.route("/payroll")
    @login_required
    def payroll_page():
        """Payroll with employee management, timesheet staging, and payslips"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
        payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []
        
        # Get pending timesheet batches for staging
        timesheet_batches = db.get("timesheet_batches", {"business_id": biz_id, "status": "pending"}) if biz_id else []
        # Also get approved ones waiting to be processed
        approved_batches = db.get("timesheet_batches", {"business_id": biz_id, "status": "approved"}) if biz_id else []
        staging_batches = timesheet_batches + approved_batches
        
        # Get recent payslips
        recent_payslips = sorted(payslips, key=lambda x: x.get("date", ""), reverse=True)[:10]
        
        # Calculate totals
        total_salaries = sum(float(e.get("basic_salary", 0)) for e in employees)
        
        # Build staging rows
        staging_rows = ""
        for batch in staging_batches:
            batch_data = json.loads(batch.get("data", "{}")) if isinstance(batch.get("data"), str) else batch.get("data", {})
            emp_count = len(batch_data.get("employees", []))
            period = batch.get("period", batch_data.get("period", "-"))
            status = batch.get("status", "pending")
            status_badge = '<span style="background:#f59e0b;color:white;padding:2px 8px;border-radius:4px;font-size:11px;">PENDING</span>' if status == "pending" else '<span style="background:#10b981;color:white;padding:2px 8px;border-radius:4px;font-size:11px;">APPROVED</span>'
            
            # AI source badge
            ai_source = batch_data.get("ai_source", "")
            if "haiku" in ai_source.lower():
                ai_badge = '<span style="background:#22c55e;color:white;padding:2px 8px;border-radius:4px;font-size:11px;"> Google+Haiku</span>'
            elif "google" in ai_source.lower():
                ai_badge = '<span style="background:#22c55e;color:white;padding:2px 8px;border-radius:4px;font-size:11px;"> Google</span>'
            elif "sonnet" in ai_source.lower():
                ai_badge = '<span style="background:#8b5cf6;color:white;padding:2px 8px;border-radius:4px;font-size:11px;">🟣 Sonnet</span>'
            else:
                ai_badge = '<span style="background:#6366f1;color:white;padding:2px 8px;border-radius:4px;font-size:11px;">AI</span>'
            
            staging_rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='/timesheets/review/{batch.get("id")}'">
                <td>{period}</td>
                <td>{emp_count} employees</td>
                <td>{ai_badge}</td>
                <td>{status_badge}</td>
                <td><a href="/timesheets/review/{batch.get("id")}" class="btn btn-secondary" style="padding:5px 10px;font-size:12px;">Review</a></td>
            </tr>
            '''
        
        emp_rows = ""
        for e in employees:
            emp_rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='/employee/{e.get("id")}'">
                <td><strong>{safe_string(e.get("name", "-"))}</strong></td>
                <td>{safe_string((e.get("id_number", "") or "-")[:6])}****</td>
                <td>{safe_string(e.get("position", "-"))}</td>
                <td>{money(e.get("basic_salary", 0))}</td>
            </tr>
            '''
        
        payslip_rows = ""
        for p in recent_payslips:
            payslip_rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='/payslip/{p.get("id")}'">
                <td>{p.get("date", "-")}</td>
                <td>{safe_string(p.get("employee_name", "-"))}</td>
                <td>{money(p.get("gross", 0))}</td>
                <td>{money(p.get("net", 0))}</td>
            </tr>
            '''
        
        # Staging section - only show if there are batches
        staging_section = ""
        if staging_batches:
            staging_section = f'''
        <div class="card" style="border:2px solid #f59e0b;background:rgba(245,158,11,0.05);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
                <h3 class="card-title" style="margin:0;">[FORM] Timesheet Staging ({len(staging_batches)})</h3>
            </div>
            <div style="overflow-x:auto;">
            <table class="table">
                <thead>
                    <tr><th>Period</th><th>Employees</th><th>Scanned By</th><th>Status</th><th>Action</th></tr>
                </thead>
                <tbody>
                    {staging_rows}
                </tbody>
            </table>
            </div>
        </div>
        '''
        
        content = f'''
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{len(employees)}</div>
                <div class="stat-label">Employees</div>
            </div>
            <div class="stat-card green">
                <div class="stat-value">{money(total_salaries)}</div>
                <div class="stat-label">Monthly Payroll</div>
            </div>
            <div class="stat-card" style="background:rgba(245,158,11,0.1);">
                <div class="stat-value">{len(staging_batches)}</div>
                <div class="stat-label">Timesheets Pending</div>
            </div>
        </div>
        
        {staging_section}
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
                <h3 class="card-title" style="margin:0;">Employees</h3>
                <div style="display:flex;gap:10px;flex-wrap:wrap;">
                    <a href="/employee/new" class="btn btn-secondary">+ Add Employee</a>
                    <a href="/timesheets/add" class="btn btn-secondary">+ Add Timesheet</a>
                    <a href="/payroll/run" class="btn btn-primary">▶️ Run Payroll</a>
                    <a href="/payroll/report" class="btn btn-secondary">📊 Monthly Report</a>
                </div>
            </div>
            <div style="overflow-x:auto;">
            <table class="table">
                <thead>
                    <tr><th>Name</th><th>ID</th><th>Position</th><th>Salary</th></tr>
                </thead>
                <tbody>
                    {emp_rows or "<tr><td colspan='4' style='text-align:center;color:var(--text-muted)'>No employees yet</td></tr>"}
                </tbody>
            </table>
            </div>
        </div>
        
        <div class="card">
            <h3 class="card-title">Recent Payslips</h3>
            <div style="overflow-x:auto;">
            <table class="table">
                <thead>
                    <tr><th>Date</th><th>Employee</th><th>Gross</th><th>Net Pay</th></tr>
                </thead>
                <tbody>
                    {payslip_rows or "<tr><td colspan='4' style='text-align:center;color:var(--text-muted)'>No payslips yet - run payroll to generate</td></tr>"}
                </tbody>
            </table>
            </div>
        </div>
        '''
        
        # -- JARVIS: Payroll HUD header --
        if has_reactor_hud():
            _emp_count = len(employees)
            _ps_count = len(payslips)
            _pending = len(staging_batches)
            
            _hud = jarvis_hud_header(
                page_name="PAYROLL",
                page_count=f"{_emp_count} EMPLOYEES",
                left_items=[
                    ("EMPLOYEES", str(_emp_count), "c", "", ""),
                    ("TOTAL SALARIES", money(total_salaries), "o", "o", "o"),
                    ("PAYSLIPS", str(_ps_count), "g", "g", ""),
                    ("PENDING", str(_pending), "o" if _pending > 0 else "c", "o" if _pending > 0 else "", "o" if _pending > 0 else ""),
                ],
                right_items=[
                    ("COST/MONTH", money(total_salaries), "r", "r", "r"),
                    ("BATCHES", str(len(staging_batches)), "c", "", ""),
                    ("RECENT", str(len(recent_payslips)), "g", "", ""),
                    ("STATUS", "ACTIVE", "g", "g", ""),
                ],
                reactor_size="page",
                alert_html=""
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline(f"PAYROLL <b>{_emp_count} EMPLOYEES</b>")
        
        return render_page("Payroll", content, user, "payroll")
    
    
    @app.route("/employee/new", methods=["GET", "POST"])
    @login_required
    def employee_new():
        """Add new employee with full SARS-compliant deductions"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            id_number = request.form.get("id_number", "").strip()
            position = request.form.get("position", "").strip()
            tax_number = request.form.get("tax_number", "").strip()
            bank_name = request.form.get("bank_name", "").strip()
            bank_account = request.form.get("bank_account", "").strip()
            bank_branch = request.form.get("bank_branch", "").strip()
            pay_type = request.form.get("pay_type", "monthly")
            
            # Parse salary/rate
            try:
                basic_salary = float((request.form.get("basic_salary", "0") or "0").replace(",", "").replace("R", "").strip())
            except:
                basic_salary = 0
            try:
                hourly_rate = float((request.form.get("hourly_rate", "0") or "0").replace(",", "").replace("R", "").strip())
            except:
                hourly_rate = 0
            
            # Allowances
            try:
                travel_allowance = float(request.form.get("travel_allowance", 0) or 0)
            except:
                travel_allowance = 0
            try:
                other_allowance = float(request.form.get("other_allowance", 0) or 0)
            except:
                other_allowance = 0
            
            # Deductions
            try:
                medical_aid = float(request.form.get("medical_aid", 0) or 0)
            except:
                medical_aid = 0
            try:
                union_fees = float(request.form.get("union_fees", 0) or 0)
            except:
                union_fees = 0
            try:
                loan_deduction = float(request.form.get("loan_deduction", 0) or 0)
            except:
                loan_deduction = 0
            try:
                other_deduction = float(request.form.get("other_deduction", 0) or 0)
            except:
                other_deduction = 0
            
            # Industry fund (MIBFA/CETA)
            provident_fund = request.form.get("provident_fund", "off")
            if provident_fund == "mibfa":
                pension = basic_salary * 0.075
                pension_employer = basic_salary * 0.075
            elif provident_fund == "ceta":
                pension = basic_salary * 0.05
                pension_employer = basic_salary * 0.05
            elif provident_fund == "on":
                try:
                    pension = float(request.form.get("pension", 0) or 0)
                except:
                    pension = 0
                pension_employer = 0
            else:
                pension = 0
                pension_employer = 0
            
            # Calculate age from ID
            age = 30
            if len(id_number) >= 6:
                try:
                    year = int(id_number[:2])
                    year = 1900 + year if year > 25 else 2000 + year
                    import datetime
                    age = datetime.datetime.now().year - year
                except:
                    pass
            
            if not name:
                pass
            else:
                employee = RecordFactory.employee(
                    business_id=biz_id,
                    name=name,
                    id_number=id_number,
                    age=age,
                    position=position,
                    pay_type=pay_type,
                    basic_salary=basic_salary,
                    hourly_rate=hourly_rate,
                    tax_number=tax_number,
                    travel_allowance=travel_allowance,
                    other_allowance=other_allowance,
                    medical_aid=medical_aid,
                    union_fees=union_fees,
                    provident_fund=provident_fund,
                    pension=pension,
                    pension_employer=pension_employer,
                    loan_deduction=loan_deduction,
                    other_deduction=other_deduction,
                    bank_name=bank_name,
                    bank_account=bank_account,
                    bank_branch=bank_branch
                )
                emp_id = employee["id"]
                
                # Direct POST 
                try:
                    url = f"{db.url}/rest/v1/employees"
                    response = requests.post(
                        url,
                        headers={**db.headers, "Prefer": "return=representation"},
                        json=employee,
                        timeout=30
                    )
                    if response.status_code in (200, 201):
                        return redirect("/payroll")
                    else:
                        logger.error(f"[EMPLOYEE] Save failed: {response.text[:200]}")
                except Exception as e:
                    logger.error(f"[EMPLOYEE] Save error: {e}")
        
        content = '''
        <div class="card" style="max-width: 700px;">
            <h2 style="margin-bottom: 20px;">Add Employee</h2>
            <form method="POST">
                <h3 style="margin-bottom:15px;color:var(--text-muted);font-size:14px;">👤 PERSONAL DETAILS</h3>
                <div style="display:grid;grid-template-columns:2fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Full Name *</label>
                        <input type="text" name="name" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Position</label>
                        <input type="text" name="position" placeholder="e.g., Welder" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">SA ID Number</label>
                        <input type="text" name="id_number" maxlength="13" placeholder="13 digits" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Tax Number</label>
                        <input type="text" name="tax_number" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">[MONEY] PAY DETAILS</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Pay Type</label>
                        <select name="pay_type" id="payType" onchange="togglePayType()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            <option value="monthly">Monthly Salary</option>
                            <option value="hourly">Hourly Rate</option>
                        </select>
                    </div>
                    <div id="salaryGroup">
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Monthly Salary (R)</label>
                        <input type="number" name="basic_salary" step="0.01" placeholder="0.00" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div id="hourlyGroup" style="display:none;">
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Hourly Rate (R)</label>
                        <input type="number" name="hourly_rate" step="0.01" placeholder="0.00" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Travel Allowance (R)</label>
                        <input type="number" name="travel_allowance" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Other Allowance (R)</label>
                        <input type="number" name="other_allowance" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">DEDUCTIONS</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Medical Aid (R)</label>
                        <input type="number" name="medical_aid" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Union Fees (R)</label>
                        <input type="number" name="union_fees" step="0.01" value="0" placeholder="NUMSA, etc." style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Industry Fund</label>
                        <select name="provident_fund" id="industryFund" onchange="toggleFund()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            <option value="off">None</option>
                            <option value="mibfa">MIBFA - Metal (7.5%+7.5%)</option>
                            <option value="ceta">CETA - Construction (5%+5%)</option>
                            <option value="on">Custom amount</option>
                        </select>
                    </div>
                    <div id="pensionGroup" style="display:none;">
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Pension Amount (R)</label>
                        <input type="number" name="pension" id="pensionAmount" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Loan Repayment (R)</label>
                        <input type="number" name="loan_deduction" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Other Deduction (R)</label>
                        <input type="number" name="other_deduction" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">[BANK] BANK DETAILS</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:15px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Bank</label>
                        <select name="bank_name" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            <option value="">Select...</option>
                            <option value="FNB">FNB</option>
                            <option value="ABSA">ABSA</option>
                            <option value="Standard Bank">Standard Bank</option>
                            <option value="Nedbank">Nedbank</option>
                            <option value="Capitec">Capitec</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Account Number</label>
                        <input type="text" name="bank_account" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Branch Code</label>
                        <input type="text" name="bank_branch" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:25px;">
                    <button type="submit" class="btn btn-primary" style="padding:12px 24px;">GOOD: Save Employee</button>
                    <a href="/payroll" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <script>
        function togglePayType() {
            const type = document.getElementById('payType').value;
            document.getElementById('salaryGroup').style.display = type === 'monthly' ? '' : 'none';
            document.getElementById('hourlyGroup').style.display = type === 'hourly' ? '' : 'none';
        }
        function toggleFund() {
            const fund = document.getElementById('industryFund').value;
            const pensionGroup = document.getElementById('pensionGroup');
            const pensionInput = document.getElementById('pensionAmount');
            const salary = parseFloat(document.querySelector('input[name="basic_salary"]')?.value || 0);
            
            if (fund === 'mibfa') {
                pensionInput.value = (salary * 0.075).toFixed(2);
                pensionGroup.style.display = '';
            } else if (fund === 'ceta') {
                pensionInput.value = (salary * 0.05).toFixed(2);
                pensionGroup.style.display = '';
            } else if (fund === 'on') {
                pensionGroup.style.display = '';
            } else {
                pensionGroup.style.display = 'none';
                pensionInput.value = 0;
            }
        }
        document.querySelector('input[name="basic_salary"]')?.addEventListener('change', function() {
            const fund = document.getElementById('industryFund').value;
            if (fund === 'mibfa' || fund === 'ceta') toggleFund();
        });
        </script>
        '''
        
        return render_page("Add Employee", content, user, "payroll")
    
    
    @app.route("/payroll/run", methods=["GET", "POST"])
    @login_required
    def payroll_run():
        """Run payroll for all employees"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            flash("Please select a business first", "error")
            return redirect("/payroll")
        
        employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
        
        if not employees:
            flash("No employees to run payroll for", "error")
            return redirect("/payroll")
        
        # Safe float helper
        def safe_float(v):
            if v is None:
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                cleaned = v.replace(',', '').replace('R', '').replace('%', '').strip()
                if not cleaned or cleaned.lower() in ('off', 'on', 'true', 'false', 'null', 'none', '-', ''):
                    return 0.0
                try:
                    return float(cleaned)
                except:
                    return 0.0
            return 0.0
        
        if request.method == "POST":
            pay_date = request.form.get("pay_date", today())
            payslips_created = 0
            skipped = 0
            
            # Get existing payslips for this date to avoid duplicates
            existing_payslips = db.get("payslips", {"business_id": biz_id, "date": pay_date}) if biz_id else []
            existing_emp_ids = {p.get("employee_id") for p in existing_payslips}
            
            for emp in employees:
                # Skip if payslip already exists for this employee + date
                if emp.get("id") in existing_emp_ids:
                    skipped += 1
                    continue
                
                basic = safe_float(emp.get("basic_salary", 0))
                if basic <= 0:
                    continue
                
                # Get deductions from employee
                medical = safe_float(emp.get("medical_aid", 0))
                union_fees = safe_float(emp.get("union_fees", 0))
                pension = safe_float(emp.get("pension", 0))
                loan = safe_float(emp.get("loan_deduction", 0))
                other_ded = safe_float(emp.get("other_deduction", 0))
                pension_employer = safe_float(emp.get("pension_employer", 0))
                
                # PAYE calculation (2025/26 tax tables simplified)
                annual = basic * 12
                if annual <= 237100:
                    paye = (annual * 0.18) / 12
                elif annual <= 370500:
                    paye = (42678 + (annual - 237100) * 0.26) / 12
                elif annual <= 512800:
                    paye = (77362 + (annual - 370500) * 0.31) / 12
                elif annual <= 673000:
                    paye = (121475 + (annual - 512800) * 0.36) / 12
                elif annual <= 857900:
                    paye = (179147 + (annual - 673000) * 0.39) / 12
                elif annual <= 1817000:
                    paye = (251258 + (annual - 857900) * 0.41) / 12
                else:
                    paye = (644489 + (annual - 1817000) * 0.45) / 12
                
                # Apply rebates (primary rebate for < 65 years)
                paye = max(0, paye - (17235 / 12))  # R17,235 primary rebate
                
                # UIF - 1% capped at R177.12
                uif = min(basic * 0.01, 177.12)
                uif_employer = uif  # Employer matches
                
                # SDL - 1% (employer only, but track it)
                sdl = basic * 0.01
                
                # COIDA - ~1% (employer only)
                coida = basic * 0.01
                
                # Total deductions from employee
                total_ded = paye + uif + medical + union_fees + pension + loan + other_ded
                net = basic - total_ded
                
                # Employer contributions
                total_employer = uif_employer + sdl + coida + pension_employer
                total_cost = basic + total_employer
                
                payslip_id = generate_id()
                payslip = {
                    "id": payslip_id,
                    "business_id": biz_id,
                    "employee_id": emp.get("id"),
                    "employee_name": emp.get("name"),
                    "date": pay_date,
                    "basic": basic,
                    "gross": basic,
                    "paye": round(paye, 2),
                    "uif": round(uif, 2),
                    "uif_employee": round(uif, 2),
                    "uif_employer": round(uif_employer, 2),
                    "medical_aid": round(medical, 2),
                    "union_fees": round(union_fees, 2),
                    "pension": round(pension, 2),
                    "pension_employee": round(pension, 2),
                    "pension_employer": round(pension_employer, 2),
                    "loan_deduction": round(loan, 2),
                    "other_deduction": round(other_ded, 2),
                    "sdl": round(sdl, 2),
                    "coida": round(coida, 2),
                    "total_deductions": round(total_ded, 2),
                    "total_employer": round(total_employer, 2),
                    "total_cost": round(total_cost, 2),
                    "net": round(net, 2)
                }
                
                # Direct save without created_at
                try:
                    url = f"{db.url}/rest/v1/payslips"
                    response = requests.post(
                        url,
                        headers={**db.headers, "Prefer": "return=representation"},
                        json=payslip,
                        timeout=30
                    )
                    if response.status_code in (200, 201):
                        payslips_created += 1
                        
                        # Update loan balance if employee has a loan
                        if loan > 0 and emp.get("loan_balance"):
                            new_balance = max(0, float(emp.get("loan_balance", 0)) - loan)
                            try:
                                db.update("employees", emp["id"], {"loan_balance": round(new_balance, 2)})
                                logger.info(f"[PAYROLL] Loan balance for {emp.get('name')}: {money(new_balance)}")
                            except:
                                pass
                        
                        # Create journal entries for GL
                        # Employee salary: Debit expense, Credit liabilities and bank
                        # Must be balanced: Total Debits = Total Credits
                        payroll_entries = [
                            # EXPENSE SIDE (Debits)
                            {"account_code": gl(biz_id, "electricity"), "debit": round(basic, 2), "credit": 0},           # Salary expense
                        ]
                        
                        # Employer contributions as expense
                        employer_uif_amount = round(uif_employer, 2) if uif_employer > 0 else 0
                        employer_sdl_amount = round(sdl, 2) if sdl > 0 else 0
                        total_employer_expense = employer_uif_amount + employer_sdl_amount
                        if total_employer_expense > 0:
                            payroll_entries.append({"account_code": "6210", "debit": round(total_employer_expense, 2), "credit": 0})  # Employer statutory costs
                        
                        # LIABILITY & PAYMENT SIDE (Credits)
                        if paye > 0:
                            payroll_entries.append({"account_code": gl(biz_id, "paye"), "debit": 0, "credit": round(paye, 2)})      # PAYE Payable
                        if uif > 0 or employer_uif_amount > 0:
                            payroll_entries.append({"account_code": "2210", "debit": 0, "credit": round(uif + employer_uif_amount, 2)})  # UIF Payable (employee + employer)
                        if employer_sdl_amount > 0:
                            payroll_entries.append({"account_code": "2220", "debit": 0, "credit": round(employer_sdl_amount, 2)})  # SDL Payable
                        
                        # Other deductions as liabilities (medical, pension, union, loan)
                        other_deduction_total = round(medical + union_fees + pension + loan + other_ded, 2)
                        if other_deduction_total > 0:
                            payroll_entries.append({"account_code": gl(biz_id, "loan"), "debit": 0, "credit": round(other_deduction_total, 2)})  # Other payroll deductions payable
                        
                        # Net pay to bank
                        payroll_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(net, 2)})  # Bank (NET pay)
                        
                        create_journal_entry(biz_id, pay_date, f"Salary - {emp.get('name')}", f"PAY-{payslip_id[:8]}", payroll_entries)
                    else:
                        logger.error(f"[PAYROLL] Payslip save failed: {response.text[:200]}")
                except Exception as e:
                    logger.error(f"[PAYROLL] Payslip error: {e}")
            
            if skipped > 0:
                flash(f"Created {payslips_created} payslips. Skipped {skipped} (already exist for {pay_date})", "success")
            else:
                flash(f"Created {payslips_created} payslips", "success")
            return redirect("/payroll")
        
        # Preview
        preview_rows = ""
        total_gross = 0
        total_net = 0
        
        # Check for existing payslips today
        today_payslips = db.get("payslips", {"business_id": biz_id, "date": today()}) if biz_id else []
        today_emp_ids = {p.get("employee_id") for p in today_payslips}
        existing_count = 0
        
        for emp in employees:
            basic = safe_float(emp.get("basic_salary", 0))
            if basic <= 0:
                continue
            
            # Check if already has payslip today
            already_exists = emp.get("id") in today_emp_ids
            if already_exists:
                existing_count += 1
            
            annual = basic * 12
            if annual <= 237100:
                paye = (annual * 0.18) / 12
            elif annual <= 370500:
                paye = (42678 + (annual - 237100) * 0.26) / 12
            else:
                paye = (77362 + (annual - 370500) * 0.31) / 12
            
            paye = max(0, paye - (17235 / 12))
            uif = min(basic * 0.01, 177.12)
            medical = safe_float(emp.get("medical_aid", 0))
            union_fees = safe_float(emp.get("union_fees", 0))
            pension = safe_float(emp.get("pension", 0))
            other = safe_float(emp.get("loan_deduction", 0)) + safe_float(emp.get("other_deduction", 0))
            
            total_ded = paye + uif + medical + union_fees + pension + other
            net = basic - total_ded
            total_gross += basic
            total_net += net
            
            row_style = "opacity:0.5;" if already_exists else ""
            skip_badge = '<span style="background:#f59e0b;color:white;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:5px;">EXISTS</span>' if already_exists else ""
            
            preview_rows += f'''
            <tr style="{row_style}">
                <td>{safe_string(emp.get("name", "-"))}{skip_badge}</td>
                <td>{money(basic)}</td>
                <td style="color:var(--red);">-{money(paye)}</td>
                <td style="color:var(--red);">-{money(uif)}</td>
                <td style="color:var(--red);">-{money(medical + union_fees + pension + other)}</td>
                <td style="color:var(--green);font-weight:bold;">{money(net)}</td>
            </tr>
            '''
        
        existing_warning = ""
        if existing_count > 0:
            existing_warning = f'<div style="background:rgba(245,158,11,0.2);border:1px solid #f59e0b;border-radius:8px;padding:12px;margin-bottom:15px;"><strong>[!] {existing_count} employee(s) already have payslips for today.</strong> They will be skipped to preserve your edits.</div>'
        
        content = f'''
        <div class="card">
            <h2 style="margin-bottom:20px;">Run Payroll</h2>
            {existing_warning}
            <form method="POST">
                <div style="margin-bottom:20px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Pay Date</label>
                    <input type="date" name="pay_date" value="{today()}" style="padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                
                <h3 style="margin-bottom:15px;">Preview ({len(employees)} employees)</h3>
                <table class="table">
                    <thead>
                        <tr><th>Employee</th><th>Gross</th><th>PAYE</th><th>UIF</th><th>Other</th><th>Net Pay</th></tr>
                    </thead>
                    <tbody>
                        {preview_rows}
                    </tbody>
                    <tfoot>
                        <tr style="font-weight:bold;border-top:2px solid var(--border);">
                            <td>TOTAL</td>
                            <td>{money(total_gross)}</td>
                            <td></td>
                            <td></td>
                            <td></td>
                            <td style="color:var(--green);">{money(total_net)}</td>
                        </tr>
                    </tfoot>
                </table>
                
                <div style="display:flex;gap:10px;margin-top:20px;">
                    <button type="submit" class="btn btn-primary">Process Payroll</button>
                    <a href="/payroll" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        '''
        
        return render_page("Run Payroll", content, user, "payroll")
    
    
    @app.route("/employee/<emp_id>")
    @login_required
    def employee_view(emp_id):
        """Employee detail view"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        employee = db.get_one("employees", emp_id)
        if not employee:
            return redirect("/payroll")
        
        # Get payslips for this employee
        all_payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []
        payslips = [p for p in all_payslips if p.get("employee_id") == emp_id]
        payslips = sorted(payslips, key=lambda x: x.get("date", ""), reverse=True)
        
        payslip_rows = ""
        for p in payslips[:12]:
            payslip_rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='/payslip/{p.get("id")}'">
                <td>{p.get("date", "-")}</td>
                <td>{money(p.get("gross", 0))}</td>
                <td style="color:var(--red);">{money(p.get("paye", 0))}</td>
                <td style="color:var(--red);">{money(p.get("uif", 0))}</td>
                <td style="color:var(--green);font-weight:bold;">{money(p.get("net", 0))}</td>
            </tr>
            '''
        
        ytd_gross = sum(float(p.get("gross", 0)) for p in payslips)
        ytd_paye = sum(float(p.get("paye", 0)) for p in payslips)
        ytd_net = sum(float(p.get("net", 0)) for p in payslips)
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <a href="/payroll" style="color:var(--text-muted);">← Back to Payroll</a>
            <a href="/employee/{emp_id}/edit" class="btn btn-secondary">✏️ Edit Employee</a>
        </div>
        
        <div class="card">
            <h2 style="margin:0 0 15px 0;">{safe_string(employee.get("name", "-"))}</h2>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:20px;">
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:12px;">POSITION</p>
                    <p style="margin:5px 0;">{safe_string(employee.get("position", "-"))}</p>
                </div>
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:12px;">ID NUMBER</p>
                    <p style="margin:5px 0;">{safe_string(employee.get("id_number", "-"))}</p>
                </div>
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:12px;">BASIC SALARY</p>
                    <p style="margin:5px 0;font-weight:bold;">{money(employee.get("basic_salary", 0))}</p>
                </div>
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:12px;">TAX NUMBER</p>
                    <p style="margin:5px 0;">{safe_string(employee.get("tax_number", "-"))}</p>
                </div>
            </div>
            
            <h4 style="margin:20px 0 10px 0;color:var(--text-muted);font-size:13px;border-top:1px solid var(--border);padding-top:15px;">MONTHLY DEDUCTIONS</h4>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:15px;">
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:11px;">Medical Aid</p>
                    <p style="margin:3px 0;color:var(--red);">{money(employee.get("medical_aid", 0))}</p>
                </div>
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:11px;">Union Fees</p>
                    <p style="margin:3px 0;color:var(--red);">{money(employee.get("union_fees", 0))}</p>
                </div>
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:11px;">Pension</p>
                    <p style="margin:3px 0;color:var(--red);">{money(employee.get("pension", 0))}</p>
                </div>
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:11px;">Loan</p>
                    <p style="margin:3px 0;color:var(--red);">{money(employee.get("loan_deduction", 0))}</p>
                </div>
                <div>
                    <p style="color:var(--text-muted);margin:0;font-size:11px;">Other</p>
                    <p style="margin:3px 0;color:var(--red);">{money(employee.get("other_deduction", 0))}</p>
                </div>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{money(ytd_gross)}</div>
                <div class="stat-label">YTD Gross</div>
            </div>
            <div class="stat-card red">
                <div class="stat-value">{money(ytd_paye)}</div>
                <div class="stat-label">YTD PAYE</div>
            </div>
            <div class="stat-card green">
                <div class="stat-value">{money(ytd_net)}</div>
                <div class="stat-label">YTD Net</div>
            </div>
        </div>
        
        <div class="card">
            <h3 style="margin-bottom:15px;"> Payslip History</h3>
            <table class="table">
                <thead>
                    <tr><th>Date</th><th>Gross</th><th>PAYE</th><th>UIF</th><th>Net Pay</th></tr>
                </thead>
                <tbody>
                    {payslip_rows or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted)'>No payslips yet</td></tr>"}
                </tbody>
            </table>
        </div>
        '''
        
        return render_page(employee.get("name", "Employee"), content, user, "payroll")
    
    
    @app.route("/employee/<emp_id>/edit", methods=["GET", "POST"])
    @login_required
    def employee_edit(emp_id):
        """Edit employee details and deductions"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        employee = db.get_one("employees", emp_id)
        if not employee:
            return redirect("/payroll")
        
        def safe_float(v):
            if v is None:
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                cleaned = v.replace(',', '').replace('R', '').replace('%', '').strip()
                if not cleaned or cleaned.lower() in ('off', 'on', 'true', 'false', 'null', 'none', '-', ''):
                    return 0.0
                try:
                    return float(cleaned)
                except:
                    return 0.0
            return 0.0
        
        if request.method == "POST":
            # Get all form values
            name = request.form.get("name", "").strip()
            position = request.form.get("position", "").strip()
            id_number = request.form.get("id_number", "").strip()
            tax_number = request.form.get("tax_number", "").strip()
            
            basic_salary = safe_float(request.form.get("basic_salary", 0))
            hourly_rate = safe_float(request.form.get("hourly_rate", 0))
            pay_type = request.form.get("pay_type", "monthly")
            
            travel_allowance = safe_float(request.form.get("travel_allowance", 0))
            other_allowance = safe_float(request.form.get("other_allowance", 0))
            
            medical_aid = safe_float(request.form.get("medical_aid", 0))
            union_fees = safe_float(request.form.get("union_fees", 0))
            loan_deduction = safe_float(request.form.get("loan_deduction", 0))
            other_deduction = safe_float(request.form.get("other_deduction", 0))
            
            provident_fund = request.form.get("provident_fund", "off")
            if provident_fund == "mibfa":
                pension = basic_salary * 0.075
                pension_employer = basic_salary * 0.075
            elif provident_fund == "ceta":
                pension = basic_salary * 0.05
                pension_employer = basic_salary * 0.05
            elif provident_fund == "on":
                pension = safe_float(request.form.get("pension", 0))
                pension_employer = 0
            else:
                pension = 0
                pension_employer = 0
            
            bank_name = request.form.get("bank_name", "").strip()
            bank_account = request.form.get("bank_account", "").strip()
            bank_branch = request.form.get("bank_branch", "").strip()
            
            # Update via PATCH
            updates = {
                "name": name,
                "position": position,
                "id_number": id_number,
                "tax_number": tax_number,
                "pay_type": pay_type,
                "basic_salary": basic_salary,
                "hourly_rate": hourly_rate,
                "travel_allowance": travel_allowance,
                "other_allowance": other_allowance,
                "medical_aid": medical_aid,
                "union_fees": union_fees,
                "provident_fund": provident_fund,
                "pension": pension,
                "pension_employer": pension_employer,
                "loan_deduction": loan_deduction,
                "loan_total": safe_float(request.form.get("loan_total", 0)),
                "loan_balance": safe_float(request.form.get("loan_balance", 0)),
                "loan_period_months": int(request.form.get("loan_period_months", 0) or 0),
                "loan_start_date": request.form.get("loan_start_date", ""),
                "other_deduction": other_deduction,
                "bank_name": bank_name,
                "bank_account": bank_account,
                "bank_branch": bank_branch
            }
            
            try:
                url = f"{db.url}/rest/v1/employees?id=eq.{emp_id}"
                response = requests.patch(
                    url,
                    headers={**db.headers, "Prefer": "return=representation"},
                    json=updates,
                    timeout=30
                )
                if response.status_code in (200, 204):
                    flash("Employee updated", "success")
                else:
                    flash(f"Failed to save: {response.text[:100]}", "error")
            except Exception as e:
                flash(f"Error: {e}", "error")
            
            return redirect(f"/employee/{emp_id}")
        
        # GET - show form with current values
        content = f'''
        <div style="margin-bottom:20px;">
            <a href="/employee/{emp_id}" style="color:var(--text-muted);">← Back to Employee</a>
        </div>
        
        <div class="card" style="max-width:700px;">
            <h2 style="margin-bottom:20px;">Edit Employee</h2>
            <form method="POST">
                <h3 style="margin-bottom:15px;color:var(--text-muted);font-size:14px;">👤 PERSONAL DETAILS</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Full Name *</label>
                        <input type="text" name="name" value="{safe_string(employee.get('name', ''))}" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Position</label>
                        <input type="text" name="position" value="{safe_string(employee.get('position', ''))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">SA ID Number</label>
                        <input type="text" name="id_number" value="{safe_string(employee.get('id_number', ''))}" maxlength="13" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Tax Number</label>
                        <input type="text" name="tax_number" value="{safe_string(employee.get('tax_number', ''))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">[MONEY] PAY DETAILS</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Pay Type</label>
                        <select name="pay_type" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            <option value="monthly" {"selected" if employee.get("pay_type") == "monthly" else ""}>Monthly Salary</option>
                            <option value="hourly" {"selected" if employee.get("pay_type") == "hourly" else ""}>Hourly Rate</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Monthly Salary (R)</label>
                        <input type="number" name="basic_salary" step="0.01" value="{safe_float(employee.get('basic_salary', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Hourly Rate (R)</label>
                        <input type="number" name="hourly_rate" step="0.01" value="{safe_float(employee.get('hourly_rate', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Travel Allowance (R)</label>
                        <input type="number" name="travel_allowance" step="0.01" value="{safe_float(employee.get('travel_allowance', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Other Allowance (R)</label>
                        <input type="number" name="other_allowance" step="0.01" value="{safe_float(employee.get('other_allowance', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">DEDUCTIONS</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Medical Aid (R)</label>
                        <input type="number" name="medical_aid" step="0.01" value="{safe_float(employee.get('medical_aid', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Union Fees (R)</label>
                        <input type="number" name="union_fees" step="0.01" value="{safe_float(employee.get('union_fees', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Industry Fund</label>
                        <select name="provident_fund" id="fundSelect" onchange="toggleFundFields()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            <option value="off" {"selected" if employee.get("provident_fund") in (None, "", "off") else ""}>None</option>
                            <option value="mibfa" {"selected" if employee.get("provident_fund") == "mibfa" else ""}>MIBFA - Metal Industry</option>
                            <option value="ceta" {"selected" if employee.get("provident_fund") == "ceta" else ""}>CETA - Construction</option>
                            <option value="on" {"selected" if employee.get("provident_fund") == "on" else ""}>Custom amount</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Pension Amount (R)</label>
                        <input type="number" name="pension" step="0.01" value="{safe_float(employee.get('pension', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <!-- MIBFA Breakdown Info -->
                <div id="mibfaInfo" style="display:{"block" if employee.get("provident_fund") == "mibfa" else "none"};background:rgba(99,102,241,0.08);padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid rgba(99,102,241,0.2);">
                    <div style="font-weight:600;color:var(--primary);margin-bottom:10px;font-size:13px;">🏭 MIBFA BREAKDOWN (7.5% Employee + 7.5% Employer)</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div style="background:var(--card);padding:10px;border-radius:6px;">
                            <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Pension Fund (Employee)</div>
                            <div style="font-size:18px;font-weight:700;">R{safe_float(employee.get('basic_salary', 0)) * 0.075:.2f}</div>
                            <div style="font-size:11px;color:var(--text-muted);">7.5% of basic salary</div>
                        </div>
                        <div style="background:var(--card);padding:10px;border-radius:6px;">
                            <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Provident Fund (Employer)</div>
                            <div style="font-size:18px;font-weight:700;">R{safe_float(employee.get('basic_salary', 0)) * 0.075:.2f}</div>
                            <div style="font-size:11px;color:var(--text-muted);">7.5% of basic salary</div>
                        </div>
                    </div>
                </div>
                
                <!-- LOAN TRACKING -->
                <div style="background:rgba(245,158,11,0.08);padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid rgba(245,158,11,0.2);">
                    <div style="font-weight:600;color:#f59e0b;margin-bottom:10px;font-size:13px;">💰 LOAN / ADVANCE</div>
                    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(130px, 1fr));gap:15px;">
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;font-size:13px;">Monthly Repayment (R)</label>
                            <input type="number" name="loan_deduction" step="0.01" value="{safe_float(employee.get('loan_deduction', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;font-size:13px;">Total Loan Amount (R)</label>
                            <input type="number" name="loan_total" step="0.01" value="{safe_float(employee.get('loan_total', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;font-size:13px;">Balance Owing (R)</label>
                            <input type="number" name="loan_balance" step="0.01" value="{safe_float(employee.get('loan_balance', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;font-size:13px;">Period (months)</label>
                            <input type="number" name="loan_period_months" value="{employee.get('loan_period_months', 0) or 0}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        </div>
                        <div>
                            <label style="display:block;margin-bottom:5px;font-weight:500;font-size:13px;">Start Date</label>
                            <input type="date" name="loan_start_date" value="{employee.get('loan_start_date', '')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        </div>
                    </div>
                </div>
                
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Other Deduction (R)</label>
                        <input type="number" name="other_deduction" step="0.01" value="{safe_float(employee.get('other_deduction', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">[BANK] BANK DETAILS</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Bank</label>
                        <select name="bank_name" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            <option value="">Select...</option>
                            <option value="FNB" {"selected" if employee.get("bank_name") == "FNB" else ""}>FNB</option>
                            <option value="ABSA" {"selected" if employee.get("bank_name") == "ABSA" else ""}>ABSA</option>
                            <option value="Standard Bank" {"selected" if employee.get("bank_name") == "Standard Bank" else ""}>Standard Bank</option>
                            <option value="Nedbank" {"selected" if employee.get("bank_name") == "Nedbank" else ""}>Nedbank</option>
                            <option value="Capitec" {"selected" if employee.get("bank_name") == "Capitec" else ""}>Capitec</option>
                        </select>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Account Number</label>
                        <input type="text" name="bank_account" value="{safe_string(employee.get('bank_account', ''))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Branch Code</label>
                        <input type="text" name="bank_branch" value="{safe_string(employee.get('bank_branch', ''))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <div style="display:flex;gap:10px;flex-wrap:wrap;">
                    <button type="submit" class="btn btn-primary">💾 Save Changes</button>
                    <a href="/employee/{emp_id}" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <script>
        function toggleFundFields() {{
            const fund = document.getElementById('fundSelect').value;
            const mibfaInfo = document.getElementById('mibfaInfo');
            if (mibfaInfo) {{
                mibfaInfo.style.display = (fund === 'mibfa') ? 'block' : 'none';
            }}
        }}
        </script>
        '''
        
        return render_page("Edit Employee", content, user, "payroll")
    
    
    @app.route("/payslip/<payslip_id>")
    @login_required
    def payslip_view(payslip_id):
        """View payslip detail with all deductions"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        
        payslip = db.get_one("payslips", payslip_id)
        if not payslip:
            return redirect("/payroll")
        
        biz_name = business.get("name", "Business") if business else "Business"
        
        # Get all values safely
        def safe_float(v):
            try:
                return float(v) if v else 0
            except:
                return 0
        
        basic = safe_float(payslip.get("basic", 0))
        gross = safe_float(payslip.get("gross", 0)) or basic
        paye = safe_float(payslip.get("paye", 0))
        uif = safe_float(payslip.get("uif", 0)) or safe_float(payslip.get("uif_employee", 0))
        medical = safe_float(payslip.get("medical_aid", 0))
        union_fees = safe_float(payslip.get("union_fees", 0))
        pension = safe_float(payslip.get("pension", 0)) or safe_float(payslip.get("pension_employee", 0))
        loan = safe_float(payslip.get("loan_deduction", 0))
        other_ded = safe_float(payslip.get("other_deduction", 0))
        total_ded = paye + uif + medical + union_fees + pension + loan + other_ded
        net = safe_float(payslip.get("net", 0)) or (gross - total_ded)
        
        # Employer contributions
        uif_employer = safe_float(payslip.get("uif_employer", 0)) or uif
        sdl = safe_float(payslip.get("sdl", 0)) or (gross * 0.01)  # 1% SDL
        coida = safe_float(payslip.get("coida", 0)) or (gross * 0.01)  # ~1% COIDA
        pension_employer = safe_float(payslip.get("pension_employer", 0))
        total_employer = uif_employer + sdl + coida + pension_employer
        total_cost = gross + total_employer
        
        # Build deduction rows - only show if > 0
        deduction_rows = f'''
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 0;color:#666;">PAYE (Tax)</td>
                <td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(paye)}</td>
            </tr>
            <tr style="border-bottom:1px solid #eee;">
                <td style="padding:8px 0;color:#666;">UIF (1%)</td>
                <td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(uif)}</td>
            </tr>
        '''
        if medical > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Medical Aid</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(medical)}</td></tr>'
        if union_fees > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Union Fees</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(union_fees)}</td></tr>'
        if pension > 0:
            # Show Pension Fund separately
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Pension Fund (Employee)</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(pension)}</td></tr>'
        if loan > 0:
            # Get employee loan balance if available
            emp = db.get_one("employees", payslip.get("employee_id")) if payslip.get("employee_id") else None
            loan_balance = float(emp.get("loan_balance", 0)) if emp else 0
            loan_period = int(emp.get("loan_period_months", 0) or 0) if emp else 0
            loan_info = ""
            if loan_balance > 0:
                months_remaining = int(loan_balance / loan) if loan > 0 else 0
                loan_info = f'<div style="font-size:11px;color:#888;">Balance: {money(loan_balance)} ({months_remaining} months remaining)</div>'
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Loan Repayment{loan_info}</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(loan)}</td></tr>'
        if other_ded > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Other Deductions</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(other_ded)}</td></tr>'
        
        content = f'''
        <style>
            @media print {{ .no-print {{ display: none !important; }} }}
        </style>
        
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/payroll" style="color:var(--text-muted);">← Back to Payroll</a>
            <div style="display:flex;gap:10px;">
                <a href="/payslip/{payslip_id}/edit" class="btn btn-secondary">✏️ Edit</a>
                <button class="btn btn-primary" onclick="window.print();">🖨️ Print</button>
                <a href="/payslip/{payslip_id}/delete" class="btn" style="background:var(--red);color:white;" onclick="return confirm('Delete this payslip?');">🗑️ Delete</a>
            </div>
        </div>
        
        <div class="card" id="payslipPrint" style="background:white;color:#333;max-width:600px;margin:0 auto;">
            <div style="display:flex;justify-content:space-between;margin-bottom:25px;padding-bottom:15px;border-bottom:2px solid #333;">
                <div>
                    <h1 style="color:#333;margin:0;font-size:22px;">PAYSLIP</h1>
                    <p style="color:#666;margin:5px 0 0 0;font-size:14px;">{payslip.get("date", "-")}</p>
                </div>
                <div style="text-align:right;">
                    <h2 style="color:#333;margin:0;font-size:18px;">{safe_string(biz_name)}</h2>
                </div>
            </div>
            
            <div style="background:#f5f5f5;padding:15px;border-radius:8px;margin-bottom:20px;">
                <h3 style="margin:0;color:#333;font-size:16px;">{safe_string(payslip.get("employee_name", "-"))}</h3>
            </div>
            
            <h4 style="color:#333;margin:20px 0 10px 0;font-size:13px;">EARNINGS</h4>
            <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
                <tr style="border-bottom:1px solid #eee;">
                    <td style="padding:8px 0;color:#666;">Basic Salary</td>
                    <td style="padding:8px 0;text-align:right;color:#333;">{money(basic)}</td>
                </tr>
                <tr style="border-bottom:2px solid #333;background:#f9f9f9;">
                    <td style="padding:10px 0;color:#333;font-weight:bold;">GROSS PAY</td>
                    <td style="padding:10px 0;text-align:right;color:#333;font-weight:bold;">{money(gross)}</td>
                </tr>
            </table>
            
            <h4 style="color:#333;margin:20px 0 10px 0;font-size:13px;">DEDUCTIONS</h4>
            <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
                {deduction_rows}
                <tr style="border-bottom:2px solid #333;background:#fef2f2;">
                    <td style="padding:10px 0;color:#333;font-weight:bold;">TOTAL DEDUCTIONS</td>
                    <td style="padding:10px 0;text-align:right;color:#ef4444;font-weight:bold;">-{money(total_ded)}</td>
                </tr>
            </table>
            
            <div style="display:flex;justify-content:space-between;align-items:center;padding:20px;background:#10b981;border-radius:8px;color:white;">
                <span style="font-size:18px;font-weight:bold;">NET PAY</span>
                <span style="font-size:26px;font-weight:bold;">{money(net)}</span>
            </div>
            
            <div style="margin-top:20px;padding:15px;background:#f5f5f5;border-radius:8px;">
                <h4 style="margin:0 0 10px 0;color:#888;font-size:11px;">EMPLOYER CONTRIBUTIONS (Company Cost)</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:12px;color:#666;">
                    <div>UIF: {money(uif_employer)}</div>
                    <div>SDL: {money(sdl)}</div>
                    <div>COIDA: {money(coida)}</div>
                    {f"<div>Provident Fund (Employer): {money(pension_employer)}</div>" if pension_employer > 0 else ""}
                </div>
                <p style="margin:10px 0 0 0;font-size:13px;color:#333;font-weight:bold;">Total Cost to Company: {money(total_cost)}</p>
            </div>
            
            <div style="margin-top:25px;text-align:center;color:#888;font-size:11px;">
                Generated by ClickAI | Computer-generated payslip
            </div>
        </div>
        '''
        
        return render_page("Payslip", content, user, "payroll")
    
    
    @app.route("/payslip/<payslip_id>/edit", methods=["GET", "POST"])
    @login_required
    def payslip_edit(payslip_id):
        """Edit payslip amounts"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        
        payslip = db.get_one("payslips", payslip_id)
        if not payslip:
            return redirect("/payroll")
        
        def safe_float(v):
            try:
                return float(v) if v else 0
            except:
                return 0
        
        if request.method == "POST":
            # Update payslip with form values
            basic = safe_float(request.form.get("basic", 0))
            gross = safe_float(request.form.get("gross", 0)) or basic
            paye = safe_float(request.form.get("paye", 0))
            uif = safe_float(request.form.get("uif", 0))
            medical = safe_float(request.form.get("medical_aid", 0))
            union_fees = safe_float(request.form.get("union_fees", 0))
            pension = safe_float(request.form.get("pension", 0))
            loan = safe_float(request.form.get("loan_deduction", 0))
            other = safe_float(request.form.get("other_deduction", 0))
            
            total_ded = paye + uif + medical + union_fees + pension + loan + other
            net = gross - total_ded
            
            updates = {
                "basic": basic,
                "gross": gross,
                "paye": paye,
                "uif": uif,
                "medical_aid": medical,
                "union_fees": union_fees,
                "pension": pension,
                "loan_deduction": loan,
                "other_deduction": other,
                "total_deductions": total_ded,
                "net": net
            }
            
            # Use PATCH for update (not db.save which uses POST)
            try:
                url = f"{db.url}/rest/v1/payslips?id=eq.{payslip_id}"
                response = requests.patch(
                    url,
                    headers={**db.headers, "Prefer": "return=representation"},
                    json=updates,
                    timeout=30
                )
                if response.status_code in (200, 204):
                    flash("Payslip updated", "success")
                else:
                    flash(f"Failed to save: {response.text[:100]}", "error")
                    logger.error(f"[PAYSLIP EDIT] Failed: {response.text[:200]}")
            except Exception as e:
                flash(f"Error: {e}", "error")
                logger.error(f"[PAYSLIP EDIT] Error: {e}")
            
            return redirect(f"/payslip/{payslip_id}")
        
        # GET - show form
        basic = safe_float(payslip.get("basic", 0))
        gross = safe_float(payslip.get("gross", 0)) or basic
        paye = safe_float(payslip.get("paye", 0))
        uif = safe_float(payslip.get("uif", 0))
        medical = safe_float(payslip.get("medical_aid", 0))
        union_fees = safe_float(payslip.get("union_fees", 0))
        pension = safe_float(payslip.get("pension", 0))
        loan = safe_float(payslip.get("loan_deduction", 0))
        other = safe_float(payslip.get("other_deduction", 0))
        
        content = f'''
        <div style="margin-bottom:20px;">
            <a href="/payslip/{payslip_id}" style="color:var(--text-muted);">← Back to Payslip</a>
        </div>
        
        <div class="card" style="max-width:600px;">
            <h2 style="margin-bottom:20px;">Edit Payslip</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">{safe_string(payslip.get("employee_name", ""))}</p>
            
            <form method="POST">
                <h4 style="margin-bottom:15px;color:var(--text-muted);font-size:13px;">EARNINGS</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;">Basic Salary</label>
                        <input type="number" name="basic" step="0.01" value="{basic}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;">Gross Pay</label>
                        <input type="number" name="gross" step="0.01" value="{gross}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                
                <h4 style="margin-bottom:15px;color:var(--text-muted);font-size:13px;">DEDUCTIONS</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;">PAYE (Tax)</label>
                        <input type="number" name="paye" step="0.01" value="{paye}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;">UIF (1%)</label>
                        <input type="number" name="uif" step="0.01" value="{uif}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;">Medical Aid</label>
                        <input type="number" name="medical_aid" step="0.01" value="{medical}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;">Union Fees</label>
                        <input type="number" name="union_fees" step="0.01" value="{union_fees}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;">Pension/Provident</label>
                        <input type="number" name="pension" step="0.01" value="{pension}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;">Loan Repayment</label>
                        <input type="number" name="loan_deduction" step="0.01" value="{loan}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="margin-bottom:20px;">
                    <label style="display:block;margin-bottom:5px;">Other Deduction</label>
                    <input type="number" name="other_deduction" step="0.01" value="{other}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                
                <div style="display:flex;gap:10px;">
                    <button type="submit" class="btn btn-primary">💾 Save Changes</button>
                    <a href="/payslip/{payslip_id}" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        '''
        
        return render_page("Edit Payslip", content, user, "payroll")
    
    
    @app.route("/payslip/<payslip_id>/delete", methods=["POST", "GET"])
    @login_required
    def payslip_delete(payslip_id):
        """Delete a payslip"""
        
        payslip = db.get_one("payslips", payslip_id)
        if payslip:
            try:
                url = f"{db.url}/rest/v1/payslips?id=eq.{payslip_id}"
                response = requests.delete(url, headers=db.headers, timeout=30)
                if response.status_code in (200, 204):
                    flash("Payslip deleted", "success")
                else:
                    flash("Failed to delete payslip", "error")
            except Exception as e:
                flash(f"Error: {e}", "error")
        
        return redirect("/payroll")
    
    
    @app.route("/payroll/report")
    @login_required
    def payroll_monthly_report():
        """Monthly PAYE, SDL, UIF totals report"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []
        
        # Group by month
        from collections import defaultdict
        monthly = defaultdict(lambda: {"paye": 0, "sdl": 0, "uif_employee": 0, "uif_employer": 0, "uif_total": 0, "pension_employee": 0, "pension_employer": 0, "gross": 0, "net": 0, "count": 0})
        
        for p in payslips:
            date = str(p.get("date") or p.get("created_at") or "")[:7]  # YYYY-MM
            if not date or len(date) < 7:
                continue
            m = monthly[date]
            m["paye"] += float(p.get("paye") or 0)
            m["sdl"] += float(p.get("sdl") or 0)
            m["uif_employee"] += float(p.get("uif_employee") or p.get("uif") or 0)
            m["uif_employer"] += float(p.get("uif_employer") or 0)
            m["uif_total"] += float(p.get("uif_employee") or p.get("uif") or 0) + float(p.get("uif_employer") or 0)
            m["pension_employee"] += float(p.get("pension_employee") or p.get("pension") or 0)
            m["pension_employer"] += float(p.get("pension_employer") or 0)
            m["gross"] += float(p.get("gross") or 0)
            m["net"] += float(p.get("net") or 0)
            m["count"] += 1
        
        # Sort months descending
        sorted_months = sorted(monthly.keys(), reverse=True)
        
        # Grand totals
        grand = {"paye": 0, "sdl": 0, "uif_total": 0, "pension_employee": 0, "pension_employer": 0, "gross": 0, "net": 0}
        
        rows_html = ""
        for month in sorted_months:
            m = monthly[month]
            for k in grand:
                grand[k] += m.get(k, 0)
            
            # Format month name
            try:
                from datetime import datetime as dt
                month_name = dt.strptime(month, "%Y-%m").strftime("%B %Y")
            except:
                month_name = month
            
            rows_html += f'''
            <tr style="border-bottom:1px solid var(--border);">
                <td style="padding:12px;font-weight:600;">{month_name}</td>
                <td style="padding:12px;text-align:center;">{m["count"]}</td>
                <td style="padding:12px;text-align:right;">{money(m["gross"])}</td>
                <td style="padding:12px;text-align:right;color:#ef4444;font-weight:600;">{money(m["paye"])}</td>
                <td style="padding:12px;text-align:right;color:#f59e0b;">{money(m["sdl"])}</td>
                <td style="padding:12px;text-align:right;color:#3b82f6;">{money(m["uif_total"])}</td>
                <td style="padding:12px;text-align:right;color:#8b5cf6;">{money(m["pension_employee"] + m["pension_employer"])}</td>
                <td style="padding:12px;text-align:right;font-weight:600;">{money(m["net"])}</td>
            </tr>
            '''
        
        # Grand total row
        rows_html += f'''
        <tr style="background:var(--bg);border-top:2px solid var(--text);font-weight:700;">
            <td style="padding:14px;">TOTAL (Tax Year)</td>
            <td style="padding:14px;text-align:center;"></td>
            <td style="padding:14px;text-align:right;">{money(grand["gross"])}</td>
            <td style="padding:14px;text-align:right;color:#ef4444;">{money(grand["paye"])}</td>
            <td style="padding:14px;text-align:right;color:#f59e0b;">{money(grand["sdl"])}</td>
            <td style="padding:14px;text-align:right;color:#3b82f6;">{money(grand["uif_total"])}</td>
            <td style="padding:14px;text-align:right;color:#8b5cf6;">{money(grand["pension_employee"] + grand["pension_employer"])}</td>
            <td style="padding:14px;text-align:right;">{money(grand["net"])}</td>
        </tr>
        '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <div>
                <h2 style="margin:0;">📊 Payroll Monthly Report</h2>
                <p style="color:var(--text-muted);margin:5px 0 0 0;">PAYE, SDL, UIF & Pension totals per month</p>
            </div>
            <div style="display:flex;gap:10px;">
                <a href="/payroll" class="btn btn-secondary">← Back to Payroll</a>
                <button onclick="window.print()" class="btn btn-secondary">🖨️ Print</button>
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(140px, 1fr));gap:15px;margin-bottom:20px;">
            <div class="card" style="text-align:center;">
                <div style="font-size:20px;font-weight:700;color:#ef4444;">{money(grand["paye"])}</div>
                <div style="font-size:12px;color:var(--text-muted);">Total PAYE</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:20px;font-weight:700;color:#f59e0b;">{money(grand["sdl"])}</div>
                <div style="font-size:12px;color:var(--text-muted);">Total SDL</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:20px;font-weight:700;color:#3b82f6;">{money(grand["uif_total"])}</div>
                <div style="font-size:12px;color:var(--text-muted);">Total UIF</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:20px;font-weight:700;color:#8b5cf6;">{money(grand["pension_employee"] + grand["pension_employer"])}</div>
                <div style="font-size:12px;color:var(--text-muted);">Total Pension</div>
            </div>
        </div>
        
        <!-- UIF Links -->
        <div class="card" style="margin-bottom:20px;background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.2);">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                <div>
                    <strong>📋 SARS & UIF Online Submissions</strong>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;font-size:13px;">Submit declarations and payments online</p>
                </div>
                <div style="display:flex;gap:10px;flex-wrap:wrap;">
                    <a href="https://www.ufiling.co.za" target="_blank" class="btn btn-primary" style="background:#3b82f6;">🔗 uFiling (UIF)</a>
                    <a href="https://www.sarsefiling.co.za" target="_blank" class="btn btn-secondary">🔗 SARS eFiling</a>
                    <a href="https://www.labour.gov.za/coida" target="_blank" class="btn btn-secondary">🔗 COID Online</a>
                </div>
            </div>
        </div>
        
        <!-- Monthly Table -->
        <div class="card" style="overflow-x:auto;">
            <table style="width:100%;">
                <thead>
                    <tr style="background:var(--bg);">
                        <th style="padding:12px;text-align:left;">Month</th>
                        <th style="padding:12px;text-align:center;">Slips</th>
                        <th style="padding:12px;text-align:right;">Gross</th>
                        <th style="padding:12px;text-align:right;">PAYE</th>
                        <th style="padding:12px;text-align:right;">SDL</th>
                        <th style="padding:12px;text-align:right;">UIF (Total)</th>
                        <th style="padding:12px;text-align:right;">Pension</th>
                        <th style="padding:12px;text-align:right;">Net Pay</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        '''
        
        return render_page("Payroll Monthly Report", content, user, "payroll")
    
    

    logger.info("[PAYROLL] All payroll routes registered ✓")
