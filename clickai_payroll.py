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
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def safe_float(v):
    """Module-level safe float — tolerates None, 'off', '', 'R1 234,50' etc."""
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
        except Exception:
            return 0.0
    return 0.0


def _industry_fund_label(provident_fund_type):
    """Display name for the MIBFA industry-fund line on screens and payslips."""
    if provident_fund_type == "mibfa_pension":
        return "Pension Fund"
    if provident_fund_type in ("mibfa", "mibfa_provident"):
        return "Provident Fund"
    return "Pension Fund"


def calc_monthly_paye(basic, age=0, pension=0, provident=0, medical_members=0, travel=0):
    """Monthly PAYE — SARS 2026/27 tax tables.

    Section 11F: retirement-fund contributions (pension + provident) reduce
    taxable income before PAYE is calculated.
    Section 6A: the medical scheme fees tax credit reduces PAYE after the
    age rebate. 2026/27 monthly credit: R376 main member, R376 first
    dependant, R254 each further dependant. medical_members is the total
    number of people on the scheme including the employee.
    Travel allowance: 80% is included in the PAYE base (SARS standard
    inclusion rate — matches Sage, verified against the Sage payslip).
    """
    basic = safe_float(basic)
    pension = safe_float(pension)
    provident = safe_float(provident)
    travel = safe_float(travel)
    age = safe_float(age)
    members = int(safe_float(medical_members))

    # Section 11F — taxable income is salary less retirement contributions.
    # 80% of any travel allowance is added to the taxable base first.
    taxable_monthly = max(0.0, basic + (travel * 0.8) - pension - provident)
    annual = taxable_monthly * 12

    if annual <= 245100:
        paye = (annual * 0.18) / 12
    elif annual <= 383100:
        paye = (44118 + (annual - 245100) * 0.26) / 12
    elif annual <= 530200:
        paye = (79998 + (annual - 383100) * 0.31) / 12
    elif annual <= 695800:
        paye = (125599 + (annual - 530200) * 0.36) / 12
    elif annual <= 887000:
        paye = (185215 + (annual - 695800) * 0.39) / 12
    elif annual <= 1878600:
        paye = (259783 + (annual - 887000) * 0.41) / 12
    else:
        paye = (666339 + (annual - 1878600) * 0.45) / 12

    # Age rebates — primary for all; secondary 65+; tertiary 75+
    annual_rebate = 17820
    if age >= 75:
        annual_rebate += 9765 + 3249
    elif age >= 65:
        annual_rebate += 9765
    paye = max(0.0, paye - (annual_rebate / 12))

    # Section 6A — medical scheme fees tax credit
    if members >= 1:
        mtc = 376.0  # main member
        if members >= 2:
            mtc += 376.0  # first dependant
        if members > 2:
            mtc += 254.0 * (members - 2)  # each further dependant
        paye = max(0.0, paye - mtc)

    return paye


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
                <td><a href="/payroll/payslip-preview/{e.get("id")}" onclick="event.stopPropagation();" class="btn btn-secondary" style="padding:5px 10px;font-size:12px;">View Payslip</a></td>
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
                <a href="/timesheets" class="btn btn-secondary" style="padding:6px 14px;font-size:13px;">View all scanned timesheets</a>
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
                    <a href="/timesheets" class="btn btn-secondary">Scanned Timesheets</a>
                    <a href="/payroll/run" class="btn btn-primary">▶️ Run Payroll</a>
                    <a href="/payroll/report" class="btn btn-secondary">📊 Monthly Report</a>
                    <a href="/payroll/payslips" class="btn btn-secondary">Payslips by Month</a>
                </div>
            </div>
            <div style="overflow-x:auto;">
            <table class="table">
                <thead>
                    <tr><th>Name</th><th>ID</th><th>Position</th><th>Salary</th><th>Payslip</th></tr>
                </thead>
                <tbody>
                    {emp_rows or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted)'>No employees yet</td></tr>"}
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
            try:
                non_taxable_allowance = float(request.form.get("non_taxable_allowance", 0) or 0)
            except:
                non_taxable_allowance = 0
            
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
            
            # MEIBC / RMA statutory fields (amounts entered per employee, like Sage transaction codes)
            try:
                rma_funeral = float(request.form.get("rma_funeral", 0) or 0)
            except:
                rma_funeral = 0
            try:
                sick_fund = float(request.form.get("sick_fund", 0) or 0)
            except:
                sick_fund = 0
            try:
                council_levy = float(request.form.get("council_levy", 0) or 0)
            except:
                council_levy = 0
            
            try:
                provident_fund_amount = float(request.form.get("provident_fund_amount", 0) or 0)
            except:
                provident_fund_amount = 0
            
            try:
                medical_members = int(float(request.form.get("medical_members", 0) or 0))
            except:
                medical_members = 0
            
            # Industry fund (MIBFA/CETA)
            provident_fund = request.form.get("provident_fund", "off")
            if provident_fund in ("mibfa", "mibfa_provident", "mibfa_pension"):
                pension = basic_salary * 0.075
                pension_employer = basic_salary * 0.083
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
            
            # Manual employer provident override — Sage shows this as the
            # Fringe Benefit on the payslip and it feeds the UIF base
            try:
                _manual_pe = float(request.form.get("pension_employer", 0) or 0)
            except:
                _manual_pe = 0
            if _manual_pe > 0:
                pension_employer = _manual_pe
            
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
                employee["provident_fund_amount"] = provident_fund_amount
                employee["medical_members"] = medical_members
                employee["rma_funeral"] = rma_funeral
                employee["sick_fund"] = sick_fund
                employee["council_levy"] = council_levy
                employee["non_taxable_allowance"] = non_taxable_allowance
                employee["employee_code"] = request.form.get("employee_code", "").strip()
                employee["leave_balance"] = safe_float(request.form.get("leave_balance", 0))
                emp_id = employee["id"]

                # Pay Conditions — only attach if the schedule was filled in
                _pc_mt_in = request.form.get("pc_mon_thu_in", "").strip()
                _pc_mt_out = request.form.get("pc_mon_thu_out", "").strip()
                if _pc_mt_in and _pc_mt_out:
                    _pc = {
                        "is_setup": True,
                        "rate_method": request.form.get("pc_rate_method", "monthly"),
                        "schedule": {
                            "mon_thu_in": _pc_mt_in,
                            "mon_thu_out": _pc_mt_out,
                            "fri_in": request.form.get("pc_fri_in", "").strip(),
                            "fri_out": request.form.get("pc_fri_out", "").strip(),
                            "sat_in": request.form.get("pc_sat_in", "").strip(),
                            "sat_out": request.form.get("pc_sat_out", "").strip(),
                            "lunch_minutes": safe_float(request.form.get("pc_lunch_minutes", 0)),
                            "lunch_deducted": request.form.get("pc_lunch_deducted") == "on",
                        },
                        "ot_paid": request.form.get("pc_ot_paid") == "on",
                        "ot_multiplier": safe_float(request.form.get("pc_ot_multiplier", 1.5)) or 1.5,
                        "sat_outside_multiplier": safe_float(request.form.get("pc_sat_outside_multiplier", 1.5)) or 1.5,
                        "sunday_multiplier": safe_float(request.form.get("pc_sunday_multiplier", 2.0)) or 2.0,
                        "public_holiday_paid": request.form.get("pc_public_holiday_paid") == "on",
                    }
                    employee["pay_conditions"] = json.dumps(_pc)

                # Save via db helper (logs + auto-handles unknown columns)
                try:
                    ok, result = db.save("employees", employee)
                    if ok:
                        return redirect("/payroll")
                    else:
                        logger.error(f"[EMPLOYEE] Save failed: {result}")
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
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Employee Code</label>
                        <input type="text" name="employee_code" placeholder="e.g., DAP001" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Leave Balance (days)</label>
                        <input type="number" step="0.0001" name="leave_balance" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
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
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Non-Taxable Allowance (R)</label>
                        <input type="number" name="non_taxable_allowance" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <small style="color:var(--text-muted);font-size:11px;">Paid out but excluded from PAYE, UIF, SDL and COIDA</small>
                    </div>
                    <div></div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">DEDUCTIONS</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Medical Aid (R)</label>
                        <input type="number" name="medical_aid" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Medical Aid Members</label>
                        <input type="number" name="medical_members" step="1" min="0" value="0" placeholder="Total people on the scheme, including the employee" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Total people on the medical scheme, including the employee. Used for the SARS medical tax credit. Leave 0 if no medical aid.</p>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
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
                            <option value="mibfa_provident">MIBFA Provident Fund (7.5% + 8.3%)</option>
                            <option value="mibfa_pension">MIBFA Pension Fund (7.5% + 8.3%)</option>
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
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Provident Fund (R)</label>
                        <input type="number" name="provident_fund_amount" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Provident Fund Employer (R)</label>
                        <input type="number" name="pension_employer" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employer contribution — shown as Fringe Benefit on the payslip. Leave 0 to use the Industry Fund percentage.</p>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">RMA Funeral Benefit (R)</label>
                        <input type="number" name="rma_funeral" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employee deduction — shows on the payslip.</p>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Loan Repayment (R)</label>
                        <input type="number" name="loan_deduction" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Bargaining Council Sick Fund (R)</label>
                        <input type="number" name="sick_fund" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employer contribution (MIBFA/MEIBC) — Company Contributions, not deducted from the employee.</p>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Bargaining Council Levy (R)</label>
                        <input type="number" name="council_levy" step="0.01" value="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employer contribution — Company Contributions, not deducted from the employee.</p>
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
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
                
                <details style="margin-top:20px;border:1px solid var(--border);border-radius:8px;padding:0;">
                    <summary style="cursor:pointer;padding:14px 16px;font-weight:600;color:var(--text-muted);font-size:14px;list-style:none;">📋 PAY CONDITIONS (optional — set up the work agreement)</summary>
                    <div style="padding:0 16px 16px;">
                        <p style="color:var(--text-muted);font-size:12px;margin:0 0 15px;">Leave blank to skip — you can set this up later from the employee page. If filled in, the payslip is built from the schedule below.</p>

                        <label style="display:block;margin-bottom:5px;font-weight:500;">How is the rate set?</label>
                        <select name="pc_rate_method" style="width:100%;max-width:360px;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);margin-bottom:15px;">
                            <option value="monthly">Monthly amount (rate derived from hours)</option>
                            <option value="hourly">Hourly rate (entered directly)</option>
                        </select>

                        <h4 style="margin:10px 0;color:var(--text-muted);">Work schedule</h4>
                        <table style="width:100%;max-width:480px;">
                            <tr><td style="padding:6px 0;">Mon–Thu</td>
                                <td><input type="time" name="pc_mon_thu_in" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td>
                                <td><input type="time" name="pc_mon_thu_out" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td></tr>
                            <tr><td style="padding:6px 0;">Friday</td>
                                <td><input type="time" name="pc_fri_in" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td>
                                <td><input type="time" name="pc_fri_out" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td></tr>
                            <tr><td style="padding:6px 0;">Saturday</td>
                                <td><input type="time" name="pc_sat_in" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td>
                                <td><input type="time" name="pc_sat_out" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td></tr>
                        </table>
                        <p style="color:var(--text-muted);font-size:12px;margin:6px 0 12px;">Leave Saturday blank if there is no Saturday agreement.</p>

                        <div style="margin-bottom:12px;">
                            <label>Lunch minutes
                                <input type="number" name="pc_lunch_minutes" value="0" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            </label>
                            <label style="margin-left:15px;">
                                <input type="checkbox" name="pc_lunch_deducted"> Deduct lunch from hours
                            </label>
                        </div>

                        <h4 style="margin:10px 0;color:var(--text-muted);">Overtime &amp; premium days</h4>
                        <label style="display:block;margin-bottom:8px;">
                            <input type="checkbox" name="pc_ot_paid"> Pay overtime when worked past the out-time
                        </label>
                        <div style="display:flex;gap:20px;flex-wrap:wrap;margin-bottom:10px;">
                            <label>OT multiplier
                                <input type="number" step="0.1" name="pc_ot_multiplier" value="1.5" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            </label>
                            <label>Saturday (outside)
                                <input type="number" step="0.1" name="pc_sat_outside_multiplier" value="1.5" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            </label>
                            <label>Sunday
                                <input type="number" step="0.1" name="pc_sunday_multiplier" value="2.0" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            </label>
                        </div>
                        <label style="display:block;">
                            <input type="checkbox" name="pc_public_holiday_paid" checked> Paid for public holidays
                        </label>
                    </div>
                </details>

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
            
            if (fund === 'mibfa' || fund === 'mibfa_provident' || fund === 'mibfa_pension') {
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
            if (fund === 'mibfa' || fund === 'mibfa_provident' || fund === 'mibfa_pension' || fund === 'ceta') toggleFund();
        });
        </script>
        '''
        
        return render_page("Add Employee", content, user, "payroll")
    
    
    # ── Hourly-employee payroll support (Option B) ──────────────────────────────
    # Hourly employees have no basic_salary; their pay is worked-hours x rate,
    # captured on scanned timesheets. These helpers let the monthly Run Payroll
    # (and the preview) build an hourly payslip the SAME way posting a timesheet
    # batch does (clickai_pay_conditions.build_payslip_gross -> identical
    # deductions / GL). Hours are pulled from pending/approved timesheet_batches,
    # matched by employee_id or name, and aggregated. Consumed batches are marked
    # processed by the run so the same hours are never paid twice across months.
    def _load_hourly_batch_map(biz_id):
        """Return (days_map, batch_ids). days_map is keyed by both employee_id and
        lower-cased name -> aggregated list of timesheet days. batch_ids = the
        batches that contributed (to mark processed after paying)."""
        days_map, batch_ids = {}, set()
        if not biz_id:
            return days_map, batch_ids
        batches = []
        for _st in ("pending", "approved"):
            try:
                batches += db.get("timesheet_batches", {"business_id": biz_id, "status": _st}) or []
            except Exception:
                pass
        for b in batches:
            raw = b.get("data", "{}")
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                continue
            entries = parsed if isinstance(parsed, list) else parsed.get("employees", [])
            used = False
            for e in entries:
                if not isinstance(e, dict):
                    continue
                d = e.get("days", [])
                if not isinstance(d, list) or not d:
                    continue
                for k in (e.get("employee_id"), (e.get("name") or "").strip().lower()):
                    if k:
                        days_map.setdefault(k, []).extend(d)
                used = True
            if used and b.get("id"):
                batch_ids.add(b.get("id"))
        return days_map, batch_ids

    def _hourly_days_for_employee(emp, biz_id):
        """Aggregated timesheet days for one (hourly) employee from unposted batches."""
        days_map, _ = _load_hourly_batch_map(biz_id)
        return days_map.get(emp.get("id")) or days_map.get((emp.get("name") or "").strip().lower()) or []

    def _compute_hourly_figures(emp, days, pay_month, business, sdl_applies):
        """Gross + deductions for an hourly employee (no save). Mirrors the
        timesheet-batch post exactly. Returns None if there is no payable gross."""
        try:
            from clickai_pay_conditions import build_payslip_gross
        except Exception as e:
            logger.error(f"[PAYROLL HOURLY] pay conditions module not available: {e}")
            return None
        result = build_payslip_gross(emp, {"days": days}, pay_month, business=business)
        gross = safe_float(result.get("gross", 0))
        if gross <= 0:
            return None
        non_taxable_allow = safe_float(emp.get("non_taxable_allowance", 0))
        medical = safe_float(emp.get("medical_aid", 0))
        union_fees = safe_float(emp.get("union_fees", 0))
        pension = safe_float(emp.get("pension", 0))
        loan = safe_float(emp.get("loan_deduction", 0))
        other_ded = safe_float(emp.get("other_deduction", 0))
        pension_employer = safe_float(emp.get("pension_employer", 0))
        provident = safe_float(emp.get("provident_fund_amount", 0))
        _emp_age = safe_float(emp.get("age", 0))
        _medical_members = safe_float(emp.get("medical_members", 0))
        paye = calc_monthly_paye(gross, _emp_age, pension, provident, _medical_members)
        uif = min(gross * 0.01, 177.12)
        uif_employer = uif
        sdl = gross * 0.01 if sdl_applies else 0
        coida = gross * 0.01
        total_ded = paye + uif + medical + union_fees + pension + provident + loan + other_ded
        net = (gross + non_taxable_allow) - total_ded
        total_employer = uif_employer + sdl + coida + pension_employer
        total_cost = gross + non_taxable_allow + total_employer
        return {
            "gross": gross, "non_taxable_allow": non_taxable_allow,
            "medical": medical, "union_fees": union_fees, "pension": pension,
            "loan": loan, "other_ded": other_ded, "pension_employer": pension_employer,
            "provident": provident, "paye": paye, "uif": uif, "uif_employer": uif_employer,
            "sdl": sdl, "coida": coida, "total_ded": total_ded, "net": net,
            "total_employer": total_employer, "total_cost": total_cost,
            "normal_hours": safe_float(result.get("normal_hours", 0)),
            "overtime_hours": safe_float(result.get("overtime_hours", 0)),
        }

    def _save_hourly_payslip(emp, figs, pay_date, pay_month, biz_id):
        """Persist an hourly payslip (figs from _compute_hourly_figures) + GL journal.
        Mirrors the timesheet-batch post. Returns True on success."""
        gross = figs["gross"]; non_taxable_allow = figs["non_taxable_allow"]
        medical = figs["medical"]; union_fees = figs["union_fees"]; pension = figs["pension"]
        loan = figs["loan"]; other_ded = figs["other_ded"]; pension_employer = figs["pension_employer"]
        provident = figs["provident"]; paye = figs["paye"]; uif = figs["uif"]
        uif_employer = figs["uif_employer"]; sdl = figs["sdl"]; coida = figs["coida"]
        total_ded = figs["total_ded"]; net = figs["net"]
        total_employer = figs["total_employer"]; total_cost = figs["total_cost"]
        payslip_id = generate_id()
        payslip = {
            "id": payslip_id,
            "business_id": biz_id,
            "employee_id": emp.get("id"),
            "employee_name": emp.get("name"),
            "date": pay_date,
            "period": pay_month,
            "basic": round(gross, 2),
            "gross": round(gross + non_taxable_allow, 2),
            "non_taxable_allowance": round(non_taxable_allow, 2),
            "hours_worked": round(figs["normal_hours"], 2),
            "overtime_hours": round(figs["overtime_hours"], 2),
            "paye": round(paye, 2),
            "uif": round(uif, 2),
            "uif_employee": round(uif, 2),
            "uif_employer": round(uif_employer, 2),
            "medical_aid": round(medical, 2),
            "union_fees": round(union_fees, 2),
            "pension": round(pension, 2),
            "pension_employee": round(pension, 2),
            "pension_employer": round(pension_employer, 2),
            "provident_fund": round(provident, 2),
            "loan_deduction": round(loan, 2),
            "other_deduction": round(other_ded, 2),
            "sdl": round(sdl, 2),
            "coida": round(coida, 2),
            "total_deductions": round(total_ded, 2),
            "total_employer": round(total_employer, 2),
            "total_cost": round(total_cost, 2),
            "net": round(net, 2)
        }
        try:
            url = f"{db.url}/rest/v1/payslips"
            response = requests.post(
                url,
                headers={**db.headers, "Prefer": "return=representation"},
                json=payslip,
                timeout=30
            )
            if response.status_code not in (200, 201):
                logger.error(f"[PAYROLL HOURLY] Payslip save failed for {emp.get('name')}: {response.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"[PAYROLL HOURLY] Payslip error for {emp.get('name')}: {e}")
            return False
        if loan > 0 and emp.get("loan_balance"):
            new_balance = max(0, safe_float(emp.get("loan_balance", 0)) - loan)
            try:
                db.update("employees", emp["id"], {"loan_balance": round(new_balance, 2)})
            except Exception:
                pass
        payroll_entries = [
            {"account_code": gl(biz_id, "salaries"), "debit": round(gross, 2), "credit": 0},
        ]
        employer_uif_amount = round(uif_employer, 2) if uif_employer > 0 else 0
        employer_sdl_amount = round(sdl, 2) if sdl > 0 else 0
        total_employer_expense = employer_uif_amount + employer_sdl_amount
        if total_employer_expense > 0:
            payroll_entries.append({"account_code": "6210", "debit": round(total_employer_expense, 2), "credit": 0})
        if paye > 0:
            payroll_entries.append({"account_code": gl(biz_id, "paye"), "debit": 0, "credit": round(paye, 2)})
        if uif > 0 or employer_uif_amount > 0:
            payroll_entries.append({"account_code": "2210", "debit": 0, "credit": round(uif + employer_uif_amount, 2)})
        if employer_sdl_amount > 0:
            payroll_entries.append({"account_code": "2220", "debit": 0, "credit": round(employer_sdl_amount, 2)})
        other_deduction_total = round(medical + union_fees + pension + provident + loan + other_ded, 2)
        if other_deduction_total > 0:
            payroll_entries.append({"account_code": gl(biz_id, "loan"), "debit": 0, "credit": other_deduction_total})
        payroll_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(net, 2)})
        try:
            create_journal_entry(biz_id, pay_date, f"Salary - {emp.get('name')}", f"PAY-{payslip_id[:8]}", payroll_entries)
        except Exception as e:
            logger.error(f"[PAYROLL HOURLY] Journal entry failed for {emp.get('name')}: {e}")
        return True

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
        
        # safe_float is now defined at module level (used by all routes)
            return 0.0
        
        if request.method == "POST":
            pay_date = request.form.get("pay_date", today())
            payslips_created = 0
            skipped = 0
            
            # Get existing payslips for this date to avoid duplicates
            existing_payslips = db.get("payslips", {"business_id": biz_id, "date": pay_date}) if biz_id else []
            existing_emp_ids = {p.get("employee_id") for p in existing_payslips}
            
            # SDL is only payable if the total annual payroll exceeds R500,000.
            # Below that threshold the employer is exempt — SDL must be R0.
            _total_annual_payroll = sum(safe_float(e.get("basic_salary", 0)) * 12 for e in employees)
            _sdl_applies = _total_annual_payroll > 500000

            # Option B: pull hourly employees' timesheet hours for this run
            _hourly_map, _hourly_batch_ids = _load_hourly_batch_map(biz_id)
            
            for emp in employees:
                # Skip if payslip already exists for this employee + date
                if emp.get("id") in existing_emp_ids:
                    skipped += 1
                    continue
                
                basic = safe_float(emp.get("basic_salary", 0))
                if basic <= 0:
                    # Hourly employee: build from timesheet hours (same engine/rules
                    # as posting a timesheet batch). Salaried path below is skipped.
                    _h_days = _hourly_map.get(emp.get("id")) or _hourly_map.get((emp.get("name") or "").strip().lower()) or []
                    if _h_days:
                        _h_figs = _compute_hourly_figures(emp, _h_days, pay_date[:7], business, _sdl_applies)
                        if _h_figs and _save_hourly_payslip(emp, _h_figs, pay_date, pay_date[:7], biz_id):
                            payslips_created += 1
                    continue
                
                # Get deductions from employee
                medical = safe_float(emp.get("medical_aid", 0))
                union_fees = safe_float(emp.get("union_fees", 0))
                pension = safe_float(emp.get("pension", 0))
                loan = safe_float(emp.get("loan_deduction", 0))
                other_ded = safe_float(emp.get("other_deduction", 0))
                pension_employer = safe_float(emp.get("pension_employer", 0))
                # Provident fund — separate employee deduction (apart from pension)
                provident = safe_float(emp.get("provident_fund_amount", 0))
                # Travel allowance — added to earnings; 80% PAYE-taxable (Sage)
                travel = safe_float(emp.get("travel_allowance", 0))
                # RMA Funeral Benefit — employee deduction (Sage)
                rma_funeral = safe_float(emp.get("rma_funeral", 0))
                # Bargaining Council Sick Fund + Levy — employer contributions (Sage)
                sick_fund = safe_float(emp.get("sick_fund", 0))
                council_levy = safe_float(emp.get("council_levy", 0))
                
                other_allow = safe_float(emp.get("other_allowance", 0))
                non_taxable_allow = safe_float(emp.get("non_taxable_allowance", 0))
                gross = basic + travel + other_allow + non_taxable_allow
                
                # PAYE — SARS 2026/27 (Section 11F retirement deduction +
                # Section 6A medical credit + 80% travel inclusion inside the helper).
                # Other Allowance is a fully-taxable cash allowance — 100% in the base.
                _emp_age = safe_float(emp.get("age", 0))
                _medical_members = safe_float(emp.get("medical_members", 0))
                paye = calc_monthly_paye(basic + other_allow, _emp_age, pension, provident, _medical_members, travel)
                
                # UIF - 1% of remuneration capped at R177.12. Remuneration =
                # basic + other allowance + 80% travel + employer provident (fringe benefit) —
                # verified to the cent against the Sage payslip.
                uif = min((basic + other_allow + travel * 0.8 + pension_employer) * 0.01, 177.12)
                uif_employer = uif  # Employer matches
                
                # SDL - 1% of the PAYE remuneration base (employer only) —
                # only if total payroll over R500k threshold
                _sdl_base = max(0.0, basic + other_allow + travel * 0.8 - pension - provident)
                sdl = _sdl_base * 0.01 if _sdl_applies else 0
                
                # COIDA - ~1% (employer only)
                coida = (basic + other_allow) * 0.01
                
                # Total deductions from employee
                total_ded = paye + uif + medical + union_fees + pension + provident + loan + other_ded + rma_funeral
                net = gross - total_ded
                
                # Employer contributions
                total_employer = uif_employer + sdl + coida + pension_employer + sick_fund + council_levy
                total_cost = gross + total_employer
                
                payslip_id = generate_id()
                payslip = {
                    "id": payslip_id,
                    "business_id": biz_id,
                    "employee_id": emp.get("id"),
                    "employee_name": emp.get("name"),
                    "date": pay_date,
                    "basic": basic,
                    "gross": round(gross, 2),
                    "travel_allowance": round(travel, 2),
                    "other_allowance": round(other_allow, 2),
                    "non_taxable_allowance": round(non_taxable_allow, 2),
                    "paye": round(paye, 2),
                    "uif": round(uif, 2),
                    "uif_employee": round(uif, 2),
                    "uif_employer": round(uif_employer, 2),
                    "medical_aid": round(medical, 2),
                    "union_fees": round(union_fees, 2),
                    "pension": round(pension, 2),
                    "pension_employee": round(pension, 2),
                    "pension_employer": round(pension_employer, 2),
                    "provident_fund": round(provident, 2),
                    "rma_funeral": round(rma_funeral, 2),
                    "sick_fund": round(sick_fund, 2),
                    "council_levy": round(council_levy, 2),
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
                            # EXPENSE SIDE (Debits) — gross includes travel allowance
                            {"account_code": gl(biz_id, "salaries"), "debit": round(gross, 2), "credit": 0},           # Salary expense
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
                        
                        # Other deductions as liabilities (medical, pension, provident, union, loan, RMA)
                        other_deduction_total = round(medical + union_fees + pension + provident + loan + other_ded + rma_funeral, 2)
                        if other_deduction_total > 0:
                            payroll_entries.append({"account_code": gl(biz_id, "loan"), "debit": 0, "credit": round(other_deduction_total, 2)})  # Other payroll deductions payable
                        
                        # Net pay to bank
                        payroll_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(net, 2)})  # Bank (NET pay)
                        
                        create_journal_entry(biz_id, pay_date, f"Salary - {emp.get('name')}", f"PAY-{payslip_id[:8]}", payroll_entries)
                    else:
                        logger.error(f"[PAYROLL] Payslip save failed: {response.text[:200]}")
                except Exception as e:
                    logger.error(f"[PAYROLL] Payslip error: {e}")
            
            # Mark the timesheet batches we just paid from as processed so the
            # same hours are not paid again on next month's run.
            for _bid in _hourly_batch_ids:
                try:
                    db.save("timesheet_batches", {"id": _bid, "status": "processed"})
                except Exception:
                    pass

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
                # Hourly employee: show a preview row from timesheet hours (Option B).
                # SDL is employer-side and not shown here, so sdl_applies=False is fine.
                already_exists = emp.get("id") in today_emp_ids
                if already_exists:
                    existing_count += 1
                _h_days = _hourly_days_for_employee(emp, biz_id)
                _h_figs = _compute_hourly_figures(emp, _h_days, today()[:7], business, False) if _h_days else None
                if _h_figs:
                    total_gross += _h_figs["gross"]
                    total_net += _h_figs["net"]
                    _row_style = "opacity:0.5;" if already_exists else ""
                    _skip_badge = '<span style="background:#f59e0b;color:white;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:5px;">EXISTS</span>' if already_exists else ""
                    _h_other = _h_figs["medical"] + _h_figs["union_fees"] + _h_figs["pension"] + _h_figs["provident"] + _h_figs["loan"] + _h_figs["other_ded"]
                    preview_rows += f'''
            <tr style="{_row_style}">
                <td>{safe_string(emp.get("name", "-"))}<span style="background:#3b82f6;color:white;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:5px;">HOURLY</span>{_skip_badge}</td>
                <td>{money(_h_figs["gross"])}</td>
                <td style="color:var(--red);">-{money(_h_figs["paye"])}</td>
                <td style="color:var(--red);">-{money(_h_figs["uif"])}</td>
                <td style="color:var(--red);">-{money(_h_other)}</td>
                <td style="color:var(--green);font-weight:bold;">{money(_h_figs["net"])}</td>
                <td><a href="/payroll/payslip-preview/{emp.get("id")}" target="_blank" style="color:var(--accent);text-decoration:none;">View</a></td>
            </tr>
            '''
                continue
            
            # Check if already has payslip today
            already_exists = emp.get("id") in today_emp_ids
            if already_exists:
                existing_count += 1
            
            # Deductions from employee
            medical = safe_float(emp.get("medical_aid", 0))
            union_fees = safe_float(emp.get("union_fees", 0))
            pension = safe_float(emp.get("pension", 0))
            provident = safe_float(emp.get("provident_fund_amount", 0))
            pension_employer = safe_float(emp.get("pension_employer", 0))
            travel = safe_float(emp.get("travel_allowance", 0))
            rma_funeral = safe_float(emp.get("rma_funeral", 0))
            other = safe_float(emp.get("loan_deduction", 0)) + safe_float(emp.get("other_deduction", 0))
            other_allow = safe_float(emp.get("other_allowance", 0))
            non_taxable_allow = safe_float(emp.get("non_taxable_allowance", 0))
            
            gross = basic + travel + other_allow + non_taxable_allow

            # PAYE — SARS 2026/27 (Section 11F retirement deduction +
            # Section 6A medical credit + 80% travel inclusion inside the helper).
            # Other Allowance is a fully-taxable cash allowance — 100% in the base.
            _emp_age = safe_float(emp.get("age", 0))
            _medical_members = safe_float(emp.get("medical_members", 0))
            paye = calc_monthly_paye(basic + other_allow, _emp_age, pension, provident, _medical_members, travel)
            # UIF base = basic + other allowance + 80% travel + employer provident (fringe) — Sage
            uif = min((basic + other_allow + travel * 0.8 + pension_employer) * 0.01, 177.12)
            
            total_ded = paye + uif + medical + union_fees + pension + provident + other + rma_funeral
            net = gross - total_ded
            total_gross += gross
            total_net += net
            
            row_style = "opacity:0.5;" if already_exists else ""
            skip_badge = '<span style="background:#f59e0b;color:white;padding:2px 6px;border-radius:4px;font-size:10px;margin-left:5px;">EXISTS</span>' if already_exists else ""
            
            preview_rows += f'''
            <tr style="{row_style}">
                <td>{safe_string(emp.get("name", "-"))}{skip_badge}</td>
                <td>{money(gross)}</td>
                <td style="color:var(--red);">-{money(paye)}</td>
                <td style="color:var(--red);">-{money(uif)}</td>
                <td style="color:var(--red);">-{money(medical + union_fees + pension + provident + other + rma_funeral)}</td>
                <td style="color:var(--green);font-weight:bold;">{money(net)}</td>
                <td><a href="/payroll/payslip-preview/{emp.get("id")}" target="_blank" style="color:var(--accent);text-decoration:none;">View</a></td>
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
                        <tr><th>Employee</th><th>Gross</th><th>PAYE</th><th>UIF</th><th>Other</th><th>Net Pay</th><th></th></tr>
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
                            <td></td>
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
    
    
    @app.route("/payroll/payslip-preview/<emp_id>")
    @login_required
    def payslip_preview(emp_id):
        """Pre-process payslip preview for one employee, with timesheet hours as a check"""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        emp = db.get_one("employees", emp_id)
        if not emp:
            return redirect("/payroll")
        
        basic = safe_float(emp.get("basic_salary", 0))
        fund_label = _industry_fund_label(emp.get("provident_fund"))
        
        # Pro-forma controls: full month as if fully worked, minus hours
        # off/late deducted at basic ÷ average working hours per month.
        # Defaults: 0 hours off, 195 hours (45h week × 52 ÷ 12 — SA standard).
        hours_off = max(0.0, safe_float(request.args.get("hours_off", 0)))
        avg_hours = safe_float(request.args.get("avg_hours", 195)) or 195.0
        hours_rate = basic / avg_hours if avg_hours > 0 else 0.0
        hours_off_amount = round(hours_off * hours_rate, 2)
        basic_full = basic
        basic = max(0.0, basic - hours_off_amount)

        # Hourly employees have no basic salary — their pay is this month's
        # worked hours x rate. Use that as the earnings base so the payslip
        # shows the real amount instead of zero.
        _emp_rate = safe_float(emp.get("hourly_rate", 0))
        is_hourly = basic_full <= 0 and _emp_rate > 0
        hourly_normal = hourly_ot = 0.0
        _ps_debug = ""
        if is_hourly:
            # Hourly hours can sit in two places depending on timesheet state:
            #   (1) an unprocessed pending/approved BATCH (paid by Run Payroll), or
            #   (2) already posted to timesheet_entries when the batch was reviewed
            #       (batch marked 'processed'; paid from this preview via Create & Post).
            # Check both so the payslip shows the real hours + amount.
            _h_days = _hourly_days_for_employee(emp, biz_id)

            # --- TEMP DIAGNOSTIC: gather where this hourly employee's hours live ---
            _diag = {}
            try:
                _dm, _bids = _load_hourly_batch_map(biz_id)
                _all_tse = db.get("timesheet_entries", {"business_id": biz_id, "employee_id": emp_id}) if biz_id else []
                _diag = {
                    "batch_matched": len(_h_days),
                    "batch_count": len(_bids),
                    "batch_keys": list(_dm.keys())[:30],
                    "tse_total": len(_all_tse),
                    "tse_months": sorted({str(e.get("date", ""))[:7] for e in _all_tse if e.get("date")}),
                    "tse_sample": [{"date": e.get("date"), "hours": e.get("hours"),
                                    "normal_hours": e.get("normal_hours"), "overtime": e.get("overtime"),
                                    "sunday": e.get("sunday_hours")} for e in _all_tse[:6]],
                }
                logger.info("[PS-PREVIEW DIAG] id=%s name=%r %s", emp_id, emp.get("name"), _diag)
            except Exception as _de:
                _diag = {"error": str(_de)}
                logger.error(f"[PS-PREVIEW DIAG] failed: {_de}")
            # --- end diagnostic ---

            _gross_h = 0.0
            if _h_days:
                # (1) Unprocessed batch — use the run's exact gross engine
                try:
                    from clickai_pay_conditions import build_payslip_gross
                    _hres = build_payslip_gross(emp, {"days": _h_days}, today()[:7], business=business)
                    _gross_h = safe_float(_hres.get("gross", 0))
                    hourly_normal = safe_float(_hres.get("normal_hours", 0))
                    hourly_ot = safe_float(_hres.get("overtime_hours", 0))
                except Exception as _he:
                    logger.error(f"[PAYSLIP-PREVIEW] hourly gross failed for {emp.get('name')}: {_he}")
            if _gross_h <= 0:
                # (2) Processed hours posted to timesheet_entries for THIS pay month.
                # Field is 'hours' (normal) + 'overtime' + 'sunday_hours'; system rates
                # are OT x1.5 and Sunday x2 (matches the timesheet posting).
                _pm = today()[:7]
                _tse = db.get("timesheet_entries", {"business_id": biz_id, "employee_id": emp_id}) if biz_id else []
                _tse = [e for e in _tse if str(e.get("date", "")).startswith(_pm)]
                hourly_normal = sum(safe_float(e.get("hours", e.get("normal_hours", 0))) for e in _tse)
                hourly_ot = sum(safe_float(e.get("overtime", 0)) for e in _tse)
                _sun = sum(safe_float(e.get("sunday_hours", 0)) for e in _tse)
                _gross_h = round(hourly_normal * _emp_rate + hourly_ot * _emp_rate * 1.5 + _sun * _emp_rate * 2, 2)
            basic = round(_gross_h, 2)
            basic_full = basic
            hours_off_amount = 0.0
            import html as _html
            _ps_debug = (
                '<div style="background:#fde68a;color:#111;padding:12px;border:2px solid #d97706;'
                'border-radius:8px;margin:10px 0;font-family:monospace;font-size:12px;white-space:pre-wrap;">'
                '<b>DEBUG - hourly hours lookup (temporary)</b>\n'
                'employee: ' + _html.escape(str(emp.get("name"))) + '  id=' + str(emp_id) + '  rate=R' + str(_emp_rate) + '\n'
                'pay month checked: ' + today()[:7] + '\n'
                'batch_matched_days=' + str(_diag.get("batch_matched")) + '  pending/approved_batches=' + str(_diag.get("batch_count")) + '\n'
                'batch_map_keys=' + _html.escape(str(_diag.get("batch_keys"))) + '\n'
                'timesheet_entries_total=' + str(_diag.get("tse_total")) + '  months=' + _html.escape(str(_diag.get("tse_months"))) + '\n'
                'entries_sample=' + _html.escape(str(_diag.get("tse_sample"))) + '\n'
                'computed gross=R' + str(_gross_h) + '\n'
                + ('error=' + _html.escape(str(_diag.get("error"))) + '\n' if _diag.get("error") else '')
                + '</div>'
            )
            earnings_first_row = (f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                                  f'Wages ({hourly_normal + hourly_ot:.2f} hrs @ {money(_emp_rate)}/h)</td>'
                                  f'<td style="padding:6px 0;text-align:right;color:#333;">{money(basic_full)}</td></tr>')
        else:
            earnings_first_row = ('<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                                  f'Basic Salary</td><td style="padding:6px 0;text-align:right;color:#333;">{money(basic_full)}</td></tr>')
        
        # Deductions from employee
        medical = safe_float(emp.get("medical_aid", 0))
        union_fees = safe_float(emp.get("union_fees", 0))
        pension = safe_float(emp.get("pension", 0))
        provident = safe_float(emp.get("provident_fund_amount", 0))
        loan = safe_float(emp.get("loan_deduction", 0))
        other_ded = safe_float(emp.get("other_deduction", 0))
        travel = safe_float(emp.get("travel_allowance", 0))
        rma_funeral = safe_float(emp.get("rma_funeral", 0))
        sick_fund = safe_float(emp.get("sick_fund", 0))
        council_levy = safe_float(emp.get("council_levy", 0))
        pension_employer = safe_float(emp.get("pension_employer", 0))
        
        other_allow = safe_float(emp.get("other_allowance", 0))
        non_taxable_allow = safe_float(emp.get("non_taxable_allowance", 0))
        gross = basic + travel + other_allow + non_taxable_allow
        
        # PAYE — SARS 2026/27 (Section 11F retirement deduction +
        # Section 6A medical credit + 80% travel inclusion inside the helper).
        # Other Allowance is a fully-taxable cash allowance — 100% in the base.
        _emp_age = safe_float(emp.get("age", 0))
        _medical_members = safe_float(emp.get("medical_members", 0))
        paye = calc_monthly_paye(basic + other_allow, _emp_age, pension, provident, _medical_members, travel)
        
        # UIF base = basic + other allowance + 80% travel + employer provident (fringe) — Sage
        uif = min((basic + other_allow + travel * 0.8 + pension_employer) * 0.01, 177.12)
        total_ded = paye + uif + medical + union_fees + pension + provident + loan + other_ded + rma_funeral
        net = gross - total_ded
        
        # Timesheet hours for the current month (a check, not used in the calculation).
        # Hourly staff: hours come from timesheet BATCHES (same as the wages above).
        # Salaried staff: hours come from timesheet_entries.
        ts_month = today()[:7]
        if is_hourly:
            ts_normal = hourly_normal
            ts_ot = hourly_ot
        else:
            entries = db.get("timesheet_entries", {"business_id": biz_id, "employee_id": emp_id}) if biz_id else []
            month_entries = [e for e in entries if str(e.get("date", "")).startswith(ts_month)]
            ts_normal = sum(safe_float(e.get("normal_hours", e.get("hours", 0))) for e in month_entries)
            ts_ot = sum(safe_float(e.get("overtime", 0)) for e in month_entries)
        ts_total = ts_normal + ts_ot
        
        # Employer contributions (shown below the payslip as a check, not part of the payslip)
        uif_employer = uif
        sdl = max(0.0, basic + other_allow + travel * 0.8 - pension - provident) * 0.01
        coida = (basic + other_allow) * 0.01
        total_employer = uif_employer + sdl + coida + pension_employer + sick_fund + council_levy
        total_cost = gross + total_employer

        # Sage-style payslip header data
        biz_name = business.get("name", "Business") if business else "Business"
        biz_addr = business.get("address", "") if business else ""
        emp_code = emp.get("employee_code", "") or emp.get("code", "") or "-"
        emp_id_num = emp.get("id_number", "-")
        emp_position = emp.get("position", "")
        emp_started = emp.get("start_date", "") or emp.get("employed_from", "") or "-"
        emp_rate = safe_float(emp.get("hourly_rate", 0))
        leave_balance = safe_float(emp.get("leave_balance", 0))

        # YTD totals — sum this employee's payslips in the current tax year
        ytd_gross = ytd_paye = ytd_uif = ytd_net = 0.0
        try:
            _pyear = today()[:4]
            _all_ps = db.get("payslips", {"employee_id": emp_id}) if emp_id else []
            for _p in _all_ps:
                if str(_p.get("date", ""))[:4] == _pyear:
                    ytd_gross += safe_float(_p.get("gross", 0)) or safe_float(_p.get("basic", 0))
                    ytd_paye += safe_float(_p.get("paye", 0))
                    ytd_uif += safe_float(_p.get("uif", 0)) or safe_float(_p.get("uif_employee", 0))
                    ytd_net += safe_float(_p.get("net", 0))
        except Exception as _e:
            logger.error(f"[PAYSLIP-PREVIEW] YTD calc failed: {_e}")

        # Build deduction rows - only show if > 0 (mirrors payslip_view)
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
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">{fund_label} (Employee)</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(pension)}</td></tr>'
        if provident > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Provident Fund</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(provident)}</td></tr>'
        if rma_funeral > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">RMA Funeral Benefit</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(rma_funeral)}</td></tr>'
        if loan > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Loan Repayment</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(loan)}</td></tr>'
        if other_ded > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Other Deductions</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(other_ded)}</td></tr>'

        # Check if a payslip already exists for this employee today
        _today = today()
        _existing = db.get("payslips", {"business_id": biz_id, "employee_id": emp_id, "date": _today}) if biz_id else []
        _has_payslip = len(_existing) > 0

        if _has_payslip:
            action_block = f'''
            <div class="card" style="margin-top:15px;background:rgba(245,158,11,0.15);border:1px solid #f59e0b;">
                <p style="margin-bottom:10px;"><strong>[!] A payslip already exists for {safe_string(emp.get("name", "-"))} on {_today}.</strong></p>
                <a href="/payslip/{_existing[0].get("id")}" class="btn btn-primary">View existing payslip</a>
            </div>
            '''
        else:
            action_block = f'''
            <div class="card" style="margin-top:15px;">
                <form method="POST" action="/payroll/payslip-create/{emp_id}">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Pay Date</label>
                    <input type="date" name="pay_date" value="{_today}" style="padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);margin-bottom:15px;">
                    <div style="display:flex;gap:10px;flex-wrap:wrap;">
                        <button type="submit" class="btn btn-primary" style="padding:12px 24px;">Create &amp; Post Payslip</button>
                        <a href="/payroll" class="btn btn-secondary" style="padding:12px 20px;">Cancel</a>
                    </div>
                    <p style="color:var(--text-muted);font-size:12px;margin-top:10px;">This creates the payslip and posts it to the GL. You can still edit it afterwards.</p>
                </form>
            </div>
            '''

        ts_note = ""
        if ts_total > 0:
            ts_note = f'''
            <div class="card" style="margin-top:15px;">
                <h3 style="margin-bottom:10px;">Timesheet Hours — {ts_month}</h3>
                <p style="color:var(--text-muted);font-size:12px;margin-bottom:10px;">Captured hours for this month, shown as a check.</p>
                <table style="width:100%;">
                    <tr><td style="padding:6px 0;">Normal hours</td><td style="text-align:right;">{ts_normal:.1f}</td></tr>
                    <tr><td style="padding:6px 0;">Overtime hours</td><td style="text-align:right;">{ts_ot:.1f}</td></tr>
                    <tr style="font-weight:bold;border-top:1px solid var(--border);"><td style="padding:6px 0;">Total hours</td><td style="text-align:right;">{ts_total:.1f}</td></tr>
                </table>
            </div>
            '''
        else:
            ts_note = '<div class="card" style="margin-top:15px;"><p style="color:var(--text-muted);">No timesheet hours captured for this month.</p></div>'
        
        content = f'''
        <style>
            .print-only {{ display: none; }}
            @media print {{
                body * {{ visibility: hidden !important; }}
                .print-area, .print-area * {{ visibility: visible !important; }}
                .print-area .print-only {{ display: block !important; }}
                .print-area {{ position: absolute; left: 0; top: -15mm; width: 100%; }}
            }}
        </style>
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <a href="/payroll" style="color:var(--text-muted);">← Back to Payroll</a>
            <div style="display:flex;gap:10px;align-items:center;">
                <span style="background:rgba(245,158,11,0.2);border:1px solid #f59e0b;border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600;">PRO-FORMA — no records created</span>
                <button class="btn btn-primary" onclick="window.print();">Print</button>
            </div>
        </div>

        <div class="no-print card" style="max-width:720px;margin:0 auto 15px;">
            <form method="GET" action="/payroll/payslip-preview/{emp_id}" style="display:flex;gap:15px;align-items:flex-end;flex-wrap:wrap;">
                <div>
                    <label style="display:block;margin-bottom:5px;font-weight:500;font-size:13px;">Hours Off / Late</label>
                    <input type="number" name="hours_off" step="0.25" min="0" value="{hours_off:g}" style="width:120px;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <div>
                    <label style="display:block;margin-bottom:5px;font-weight:500;font-size:13px;">Avg Working Hours / Month</label>
                    <input type="number" name="avg_hours" step="0.01" min="1" value="{avg_hours:g}" style="width:140px;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <button type="submit" class="btn btn-secondary">Recalculate</button>
                <p style="color:var(--text-muted);font-size:12px;margin:0;flex-basis:100%;">Full month with all deductions as if fully worked. Hours off/late are deducted at basic salary ÷ average working hours per month ({money(hours_rate)}/hour).</p>
            </form>
        </div>

        <div class="print-area">
        <div class="print-only" style="background:white;color:#333;max-width:720px;margin:0 auto;padding:30px 30px 0;">
            <div style="display:flex;justify-content:space-between;margin-bottom:12px;padding-bottom:12px;border-bottom:2px solid #333;">
                <div>
                    <h2 style="color:#333;margin:0;font-size:17px;">{safe_string(biz_name)}</h2>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">{safe_string(biz_addr)}</p>
                </div>
                <div style="text-align:right;">
                    <h1 style="color:#333;margin:0;font-size:20px;">PAYSLIP</h1>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">Pay Date: {_today}</p>
                </div>
            </div>
            <table style="width:100%;font-size:12px;color:#444;">
                <tr>
                    <td style="padding:3px 0;width:50%;"><strong>Employee:</strong> {safe_string(emp.get("name", "-"))}</td>
                    <td style="padding:3px 0;"><strong>Employee Code:</strong> {safe_string(emp_code)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Job Title:</strong> {safe_string(emp_position) or "-"}</td>
                    <td style="padding:3px 0;"><strong>ID Number:</strong> {safe_string(emp_id_num)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Employed From:</strong> {safe_string(emp_started)}</td>
                    <td style="padding:3px 0;"><strong>Rate per Hour:</strong> {money(emp_rate) if emp_rate > 0 else "-"}</td>
                </tr>
            </table>
            <div style="margin-top:14px;border-top:1px dashed #999;text-align:center;color:#999;font-size:9px;letter-spacing:2px;padding-top:4px;">FOLD HERE</div>
        </div>

        <div class="card" style="background:white;color:#333;max-width:720px;margin:0 auto;padding:30px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #333;">
                <div>
                    <h2 style="color:#333;margin:0;font-size:17px;">{safe_string(biz_name)}</h2>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">{safe_string(biz_addr)}</p>
                </div>
                <div style="text-align:right;">
                    <h1 style="color:#333;margin:0;font-size:20px;">PAYSLIP</h1>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">Pay Date: {_today}</p>
                </div>
            </div>

            <table style="width:100%;font-size:12px;color:#444;margin-bottom:20px;">
                <tr>
                    <td style="padding:3px 0;width:50%;"><strong>Employee:</strong> {safe_string(emp.get("name", "-"))}</td>
                    <td style="padding:3px 0;"><strong>Employee Code:</strong> {safe_string(emp_code)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Job Title:</strong> {safe_string(emp_position) or "-"}</td>
                    <td style="padding:3px 0;"><strong>ID Number:</strong> {safe_string(emp_id_num)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Employed From:</strong> {safe_string(emp_started)}</td>
                    <td style="padding:3px 0;"><strong>Rate per Hour:</strong> {money(emp_rate) if emp_rate > 0 else "-"}</td>
                </tr>
            </table>

            <div style="display:flex;gap:20px;flex-wrap:wrap;">
                <div style="flex:1;min-width:260px;">
                    <h4 style="color:#333;margin:10px 0 6px;font-size:12px;border-bottom:1px solid #ccc;padding-bottom:3px;">EARNINGS</h4>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        {earnings_first_row}
                        {f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Hours Off / Late ({hours_off:g} hrs)</td><td style="padding:6px 0;text-align:right;color:#ef4444;">-{money(hours_off_amount)}</td></tr>' if hours_off_amount > 0 else ''}
                        {f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Travel Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(travel)}</td></tr>' if travel > 0 else ''}
                        {f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Other Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(other_allow)}</td></tr>' if other_allow > 0 else ''}
                        {f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Non-Taxable Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(non_taxable_allow)}</td></tr>' if non_taxable_allow > 0 else ''}
                        <tr style="border-bottom:2px solid #333;background:#f9f9f9;">
                            <td style="padding:7px 0;color:#333;font-weight:bold;">TOTAL EARNINGS</td>
                            <td style="padding:7px 0;text-align:right;color:#333;font-weight:bold;">{money(gross)}</td>
                        </tr>
                    </table>
                </div>
                <div style="flex:1;min-width:260px;">
                    <h4 style="color:#333;margin:10px 0 6px;font-size:12px;border-bottom:1px solid #ccc;padding-bottom:3px;">DEDUCTIONS</h4>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        {deduction_rows}
                        <tr style="border-bottom:2px solid #333;background:#fef2f2;">
                            <td style="padding:7px 0;color:#333;font-weight:bold;">TOTAL DEDUCTIONS</td>
                            <td style="padding:7px 0;text-align:right;color:#ef4444;font-weight:bold;">-{money(total_ded)}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:#10b981;border-radius:8px;color:white;margin-top:18px;">
                <span style="font-size:16px;font-weight:bold;">NETT PAY</span>
                <span style="font-size:24px;font-weight:bold;">{money(net)}</span>
            </div>

            <div style="margin-top:14px;padding:10px 14px;background:#f5f5f5;border-radius:8px;font-size:12px;color:#555;">
                <strong>Leave Type:</strong> Annual Leave &nbsp;·&nbsp; <strong>Closing Balance:</strong> {leave_balance:.4f} days
            </div>

            <div style="margin-top:20px;text-align:center;color:#999;font-size:10px;">
                Preview · ClickAI · Computer-generated payslip · {_today}
            </div>
        </div>

        </div>

        <div style="max-width:720px;margin:20px auto 0;padding:14px;background:var(--card);border:1px solid var(--border);border-radius:8px;">
            <h4 style="margin:0 0 8px;color:var(--text-muted);font-size:11px;">COMPANY CONTRIBUTIONS</h4>
            <p style="color:var(--text-muted);font-size:11px;margin:0 0 8px;">For the business — not part of the employee's payslip and not printed.</p>
            <table style="width:100%;font-size:12px;color:var(--text);">
                <tr><td style="padding:3px 0;">UIF</td><td style="text-align:right;">{money(uif_employer)}</td></tr>
                <tr><td style="padding:3px 0;">SDL (Skills Levy)</td><td style="text-align:right;">{money(sdl)}</td></tr>
                <tr><td style="padding:3px 0;">COIDA</td><td style="text-align:right;">{money(coida)}</td></tr>
                {f'<tr><td style="padding:3px 0;">{fund_label} (Employer)</td><td style="text-align:right;">{money(pension_employer)}</td></tr>' if pension_employer > 0 else ""}
                {f'<tr><td style="padding:3px 0;">Bargaining Council Sick Fund</td><td style="text-align:right;">{money(sick_fund)}</td></tr>' if sick_fund > 0 else ""}
                {f'<tr><td style="padding:3px 0;">Bargaining Council Levy</td><td style="text-align:right;">{money(council_levy)}</td></tr>' if council_levy > 0 else ""}
                <tr style="border-top:1px solid var(--border);font-weight:bold;"><td style="padding:5px 0;">Total Cost to Company</td><td style="text-align:right;">{money(total_cost)}</td></tr>
                {f'<tr><td style="padding:3px 0;color:var(--text-muted);">Fringe Benefits (period total)</td><td style="text-align:right;color:var(--text-muted);">{money(pension_employer)}</td></tr>' if pension_employer > 0 else ""}
            </table>
        </div>
        {action_block}
        {ts_note}
        '''
        
        content = _ps_debug + content
        return render_page("Payslip Preview", content, user, "payroll")
    
    
    @app.route("/payroll/payslip-create/<emp_id>", methods=["POST"])
    @login_required
    def payslip_create(emp_id):
        """Create a single payslip for one employee and post it to the GL."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        if not biz_id:
            flash("Please select a business first", "error")
            return redirect("/payroll")

        emp = db.get_one("employees", emp_id)
        if not emp:
            flash("Employee not found", "error")
            return redirect("/payroll")

        pay_date = request.form.get("pay_date", today())

        # Guard: don't create a duplicate payslip for the same employee + date
        existing = db.get("payslips", {"business_id": biz_id, "employee_id": emp_id, "date": pay_date}) if biz_id else []
        if existing:
            flash(f"A payslip for {emp.get('name')} on {pay_date} already exists", "error")
            return redirect(f"/payslip/{existing[0].get('id')}")

        basic = safe_float(emp.get("basic_salary", 0))
        if basic <= 0:
            # Hourly employee: paid from timesheet hours via Run Payroll (which now
            # includes hourly staff) or by posting their timesheet batch.
            flash(f"{emp.get('name')} is hourly - use Run Payroll or post their timesheet batch to pay worked hours", "error")
            return redirect("/payroll")

        # Deductions from employee
        medical = safe_float(emp.get("medical_aid", 0))
        union_fees = safe_float(emp.get("union_fees", 0))
        pension = safe_float(emp.get("pension", 0))
        loan = safe_float(emp.get("loan_deduction", 0))
        other_ded = safe_float(emp.get("other_deduction", 0))
        pension_employer = safe_float(emp.get("pension_employer", 0))
        provident = safe_float(emp.get("provident_fund_amount", 0))
        travel = safe_float(emp.get("travel_allowance", 0))
        rma_funeral = safe_float(emp.get("rma_funeral", 0))
        sick_fund = safe_float(emp.get("sick_fund", 0))
        council_levy = safe_float(emp.get("council_levy", 0))
        
        other_allow = safe_float(emp.get("other_allowance", 0))
        non_taxable_allow = safe_float(emp.get("non_taxable_allowance", 0))
        gross = basic + travel + other_allow + non_taxable_allow

        # PAYE — SARS 2026/27 (Section 11F retirement deduction +
        # Section 6A medical credit + 80% travel inclusion inside the helper).
        # Other Allowance is a fully-taxable cash allowance — 100% in the base.
        _emp_age = safe_float(emp.get("age", 0))
        _medical_members = safe_float(emp.get("medical_members", 0))
        paye = calc_monthly_paye(basic + other_allow, _emp_age, pension, provident, _medical_members, travel)

        # UIF — 1% of remuneration capped at R177.12. Remuneration =
        # basic + other allowance + 80% travel + employer provident (fringe benefit) — Sage
        uif = min((basic + other_allow + travel * 0.8 + pension_employer) * 0.01, 177.12)
        uif_employer = uif

        # SDL — only if this business's total annual payroll exceeds R500k
        _all_emps = db.get("employees", {"business_id": biz_id}) if biz_id else []
        _total_annual_payroll = sum(safe_float(e.get("basic_salary", 0)) * 12 for e in _all_emps)
        _sdl_base = max(0.0, basic + other_allow + travel * 0.8 - pension - provident)
        sdl = _sdl_base * 0.01 if _total_annual_payroll > 500000 else 0

        # COIDA — ~1% (employer only)
        coida = (basic + other_allow) * 0.01

        total_ded = paye + uif + medical + union_fees + pension + provident + loan + other_ded + rma_funeral
        net = gross - total_ded
        total_employer = uif_employer + sdl + coida + pension_employer + sick_fund + council_levy
        total_cost = gross + total_employer

        payslip_id = generate_id()
        payslip = {
            "id": payslip_id,
            "business_id": biz_id,
            "employee_id": emp.get("id"),
            "employee_name": emp.get("name"),
            "date": pay_date,
            "basic": basic,
            "gross": round(gross, 2),
            "travel_allowance": round(travel, 2),
            "other_allowance": round(other_allow, 2),
            "non_taxable_allowance": round(non_taxable_allow, 2),
            "paye": round(paye, 2),
            "uif": round(uif, 2),
            "uif_employee": round(uif, 2),
            "uif_employer": round(uif_employer, 2),
            "medical_aid": round(medical, 2),
            "union_fees": round(union_fees, 2),
            "pension": round(pension, 2),
            "pension_employee": round(pension, 2),
            "pension_employer": round(pension_employer, 2),
            "provident_fund": round(provident, 2),
            "rma_funeral": round(rma_funeral, 2),
            "sick_fund": round(sick_fund, 2),
            "council_levy": round(council_levy, 2),
            "loan_deduction": round(loan, 2),
            "other_deduction": round(other_ded, 2),
            "sdl": round(sdl, 2),
            "coida": round(coida, 2),
            "total_deductions": round(total_ded, 2),
            "total_employer": round(total_employer, 2),
            "total_cost": round(total_cost, 2),
            "net": round(net, 2)
        }

        # Direct save (avoids created_at schema-cache issue)
        try:
            url = f"{db.url}/rest/v1/payslips"
            response = requests.post(
                url,
                headers={**db.headers, "Prefer": "return=representation"},
                json=payslip,
                timeout=30
            )
            if response.status_code not in (200, 201):
                logger.error(f"[PAYROLL] Single payslip save failed: {response.text[:200]}")
                flash("Could not save payslip — check the logs", "error")
                return redirect(f"/payroll/payslip-preview/{emp_id}")
        except Exception as e:
            logger.error(f"[PAYROLL] Single payslip error: {e}")
            flash("Could not save payslip — check the logs", "error")
            return redirect(f"/payroll/payslip-preview/{emp_id}")

        # Update loan balance if employee has a loan
        if loan > 0 and emp.get("loan_balance"):
            new_balance = max(0, safe_float(emp.get("loan_balance", 0)) - loan)
            try:
                db.update("employees", emp["id"], {"loan_balance": round(new_balance, 2)})
                logger.info(f"[PAYROLL] Loan balance for {emp.get('name')}: {money(new_balance)}")
            except Exception:
                pass

        # GL journal — same balanced pattern as payroll_run
        payroll_entries = [
            {"account_code": gl(biz_id, "salaries"), "debit": round(gross, 2), "credit": 0},
        ]
        employer_uif_amount = round(uif_employer, 2) if uif_employer > 0 else 0
        employer_sdl_amount = round(sdl, 2) if sdl > 0 else 0
        total_employer_expense = employer_uif_amount + employer_sdl_amount
        if total_employer_expense > 0:
            payroll_entries.append({"account_code": "6210", "debit": round(total_employer_expense, 2), "credit": 0})
        if paye > 0:
            payroll_entries.append({"account_code": gl(biz_id, "paye"), "debit": 0, "credit": round(paye, 2)})
        if uif > 0 or employer_uif_amount > 0:
            payroll_entries.append({"account_code": "2210", "debit": 0, "credit": round(uif + employer_uif_amount, 2)})
        if employer_sdl_amount > 0:
            payroll_entries.append({"account_code": "2220", "debit": 0, "credit": round(employer_sdl_amount, 2)})
        other_deduction_total = round(medical + union_fees + pension + provident + loan + other_ded + rma_funeral, 2)
        if other_deduction_total > 0:
            payroll_entries.append({"account_code": gl(biz_id, "loan"), "debit": 0, "credit": other_deduction_total})
        payroll_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(net, 2)})

        try:
            create_journal_entry(biz_id, pay_date, f"Salary - {emp.get('name')}", f"PAY-{payslip_id[:8]}", payroll_entries)
        except Exception as e:
            logger.error(f"[PAYROLL] Journal entry failed for {emp.get('name')}: {e}")

        flash(f"Payslip created for {emp.get('name')} — posted to GL", "success")
        return redirect(f"/payslip/{payslip_id}")
    
    
    @app.route("/payroll/post-batch/<batch_id>", methods=["POST"])
    @login_required
    def payroll_post_batch(batch_id):
        """Post payslips for a reviewed timesheet batch using the pay-conditions
        engine (base +/- overtime, late, early, Sunday premium). Posts the whole
        batch (post_all) or a single employee (only=<emp_id>)."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            flash("Please select a business first", "error")
            return redirect("/payroll")

        try:
            from clickai_pay_conditions import build_payslip_gross
        except Exception as e:
            logger.error(f"[POST BATCH] pay conditions module not available: {e}")
            flash("Pay conditions module not loaded — use Approve & Save instead", "error")
            return redirect(f"/timesheets/review/{batch_id}")

        batch = db.get_one("timesheet_batches", batch_id)
        if not batch:
            flash("Timesheet batch not found", "error")
            return redirect("/payroll")

        raw_data = batch.get("data", "{}")
        parsed = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        employees_data = parsed if isinstance(parsed, list) else parsed.get("employees", [])

        pay_month = request.form.get("pay_month", "") or today()[:7]
        if len(pay_month) < 7:
            pay_month = today()[:7]
        pay_month = pay_month[:7]

        # Pay date = last day of the pay month (keeps the payslip in the right tax month)
        try:
            _yr, _mo = int(pay_month[:4]), int(pay_month[5:7])
            _first_next = datetime(_yr + 1, 1, 1) if _mo == 12 else datetime(_yr, _mo + 1, 1)
            pay_date = (_first_next - timedelta(days=1)).strftime("%Y-%m-%d")
        except Exception:
            pay_date = today()

        only = request.form.get("only", "").strip()
        count = int(request.form.get("count", 0) or 0)

        # SDL only if this business's total annual payroll exceeds R500k
        _all_emps = db.get("employees", {"business_id": biz_id}) if biz_id else []
        _total_annual_payroll = sum(safe_float(e.get("basic_salary", 0)) * 12 for e in _all_emps)
        _sdl_applies = _total_annual_payroll > 500000

        posted = 0
        skipped = 0
        errors = []

        for i in range(count):
            emp_id = request.form.get(f"emp_{i}", "").strip()
            if not emp_id:
                continue
            if only and emp_id != only:
                continue

            emp = db.get_one("employees", emp_id)
            if not emp:
                continue

            # Duplicate guard — one payslip per employee per pay date
            existing = db.get("payslips", {"business_id": biz_id, "employee_id": emp_id, "date": pay_date}) if biz_id else []
            if existing:
                skipped += 1
                continue

            days = employees_data[i].get("days", []) if i < len(employees_data) else []
            employee_data = employees_data[i] if i < len(employees_data) else {"days": days}
            result = build_payslip_gross(emp, employee_data, pay_month, business=business)
            gross = safe_float(result.get("gross", 0))
            non_taxable_allow = safe_float(emp.get("non_taxable_allowance", 0))
            if gross <= 0:
                skipped += 1
                continue

            # Deductions on the engine gross (same rules as payroll_run / payslip_create)
            medical = safe_float(emp.get("medical_aid", 0))
            union_fees = safe_float(emp.get("union_fees", 0))
            pension = safe_float(emp.get("pension", 0))
            loan = safe_float(emp.get("loan_deduction", 0))
            other_ded = safe_float(emp.get("other_deduction", 0))
            pension_employer = safe_float(emp.get("pension_employer", 0))
            provident = safe_float(emp.get("provident_fund_amount", 0))

            _emp_age = safe_float(emp.get("age", 0))
            _medical_members = safe_float(emp.get("medical_members", 0))
            paye = calc_monthly_paye(gross, _emp_age, pension, provident, _medical_members)

            uif = min(gross * 0.01, 177.12)
            uif_employer = uif
            sdl = gross * 0.01 if _sdl_applies else 0
            coida = gross * 0.01

            total_ded = paye + uif + medical + union_fees + pension + provident + loan + other_ded
            net = (gross + non_taxable_allow) - total_ded
            total_employer = uif_employer + sdl + coida + pension_employer
            total_cost = gross + non_taxable_allow + total_employer

            payslip_id = generate_id()
            payslip = {
                "id": payslip_id,
                "business_id": biz_id,
                "employee_id": emp.get("id"),
                "employee_name": emp.get("name"),
                "date": pay_date,
                "period": pay_month,
                "basic": round(gross, 2),
                "gross": round(gross + non_taxable_allow, 2),
                "non_taxable_allowance": round(non_taxable_allow, 2),
                "hours_worked": round(safe_float(result.get("normal_hours", 0)), 2),
                "overtime_hours": round(safe_float(result.get("overtime_hours", 0)), 2),
                "paye": round(paye, 2),
                "uif": round(uif, 2),
                "uif_employee": round(uif, 2),
                "uif_employer": round(uif_employer, 2),
                "medical_aid": round(medical, 2),
                "union_fees": round(union_fees, 2),
                "pension": round(pension, 2),
                "pension_employee": round(pension, 2),
                "pension_employer": round(pension_employer, 2),
                "provident_fund": round(provident, 2),
                "loan_deduction": round(loan, 2),
                "other_deduction": round(other_ded, 2),
                "sdl": round(sdl, 2),
                "coida": round(coida, 2),
                "total_deductions": round(total_ded, 2),
                "total_employer": round(total_employer, 2),
                "total_cost": round(total_cost, 2),
                "net": round(net, 2)
            }

            try:
                url = f"{db.url}/rest/v1/payslips"
                response = requests.post(
                    url,
                    headers={**db.headers, "Prefer": "return=representation"},
                    json=payslip,
                    timeout=30
                )
                if response.status_code not in (200, 201):
                    logger.error(f"[POST BATCH] Payslip save failed for {emp.get('name')}: {response.text[:200]}")
                    errors.append(emp.get("name", emp_id))
                    continue
            except Exception as e:
                logger.error(f"[POST BATCH] Payslip error for {emp.get('name')}: {e}")
                errors.append(emp.get("name", emp_id))
                continue

            # Loan balance
            if loan > 0 and emp.get("loan_balance"):
                new_balance = max(0, safe_float(emp.get("loan_balance", 0)) - loan)
                try:
                    db.update("employees", emp["id"], {"loan_balance": round(new_balance, 2)})
                except Exception:
                    pass

            # GL journal — same balanced pattern as payroll_run / payslip_create
            payroll_entries = [
                {"account_code": gl(biz_id, "salaries"), "debit": round(gross, 2), "credit": 0},
            ]
            employer_uif_amount = round(uif_employer, 2) if uif_employer > 0 else 0
            employer_sdl_amount = round(sdl, 2) if sdl > 0 else 0
            total_employer_expense = employer_uif_amount + employer_sdl_amount
            if total_employer_expense > 0:
                payroll_entries.append({"account_code": "6210", "debit": round(total_employer_expense, 2), "credit": 0})
            if paye > 0:
                payroll_entries.append({"account_code": gl(biz_id, "paye"), "debit": 0, "credit": round(paye, 2)})
            if uif > 0 or employer_uif_amount > 0:
                payroll_entries.append({"account_code": "2210", "debit": 0, "credit": round(uif + employer_uif_amount, 2)})
            if employer_sdl_amount > 0:
                payroll_entries.append({"account_code": "2220", "debit": 0, "credit": round(employer_sdl_amount, 2)})
            other_deduction_total = round(medical + union_fees + pension + provident + loan + other_ded, 2)
            if other_deduction_total > 0:
                payroll_entries.append({"account_code": gl(biz_id, "loan"), "debit": 0, "credit": other_deduction_total})
            payroll_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(net, 2)})

            try:
                create_journal_entry(biz_id, pay_date, f"Salary - {emp.get('name')}", f"PAY-{payslip_id[:8]}", payroll_entries)
            except Exception as e:
                logger.error(f"[POST BATCH] Journal entry failed for {emp.get('name')}: {e}")

            posted += 1

        # Single-employee post: stay on review so the rest can still be posted
        if only:
            if posted:
                msg = "Posted payslip for 1 employee"
                if skipped:
                    msg += f" ({skipped} already had a payslip for {pay_date})"
                if errors:
                    msg += f" — errors: {', '.join(errors)}"
                flash(msg, "success")
            else:
                msg = "Nothing posted"
                if skipped:
                    msg += f" — a payslip for {pay_date} already exists"
                if errors:
                    msg += f" — errors: {', '.join(errors)}"
                flash(msg, "error")
            return redirect(f"/timesheets/review/{batch_id}")

        # Whole batch: mark processed and return to payroll
        try:
            db.save("timesheet_batches", {"id": batch_id, "status": "processed"})
        except Exception:
            pass
        msg = f"Posted {posted} payslip(s) for {pay_month}"
        if skipped:
            msg += f", skipped {skipped} (already existed)"
        if errors:
            msg += f" — errors: {', '.join(errors)}"
        flash(msg, "success" if posted else "error")
        return redirect("/payroll")
    
    
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
            <a href="/employee/{emp_id}/pay-conditions" class="btn btn-secondary">📋 Pay Conditions</a>
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
                    <p style="color:var(--text-muted);margin:0;font-size:11px;">Provident Fund</p>
                    <p style="margin:3px 0;color:var(--red);">{money(employee.get("provident_fund_amount", 0))}</p>
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
        
        # safe_float is module-level
        
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
            non_taxable_allowance = safe_float(request.form.get("non_taxable_allowance", 0))
            
            medical_aid = safe_float(request.form.get("medical_aid", 0))
            union_fees = safe_float(request.form.get("union_fees", 0))
            loan_deduction = safe_float(request.form.get("loan_deduction", 0))
            other_deduction = safe_float(request.form.get("other_deduction", 0))
            provident_fund_amount = safe_float(request.form.get("provident_fund_amount", 0))
            rma_funeral = safe_float(request.form.get("rma_funeral", 0))
            sick_fund = safe_float(request.form.get("sick_fund", 0))
            council_levy = safe_float(request.form.get("council_levy", 0))
            
            provident_fund = request.form.get("provident_fund", "off")
            if provident_fund in ("mibfa", "mibfa_provident", "mibfa_pension"):
                pension = basic_salary * 0.075
                pension_employer = basic_salary * 0.083
            elif provident_fund == "ceta":
                pension = basic_salary * 0.05
                pension_employer = basic_salary * 0.05
            elif provident_fund == "on":
                pension = safe_float(request.form.get("pension", 0))
                pension_employer = 0
            else:
                pension = 0
                pension_employer = 0
            
            # Manual employer provident override — Sage shows this as the
            # Fringe Benefit on the payslip and it feeds the UIF base
            _manual_pe = safe_float(request.form.get("pension_employer", 0))
            if _manual_pe > 0:
                pension_employer = _manual_pe
            
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
                "non_taxable_allowance": non_taxable_allowance,
                "medical_aid": medical_aid,
                "medical_members": int(safe_float(request.form.get("medical_members", 0))),
                "union_fees": union_fees,
                "provident_fund": provident_fund,
                "pension": pension,
                "pension_employer": pension_employer,
                "provident_fund_amount": provident_fund_amount,
                "rma_funeral": rma_funeral,
                "sick_fund": sick_fund,
                "council_levy": council_levy,
                "loan_deduction": loan_deduction,
                "loan_total": safe_float(request.form.get("loan_total", 0)),
                "loan_balance": safe_float(request.form.get("loan_balance", 0)),
                "loan_period_months": int(request.form.get("loan_period_months", 0) or 0),
                "loan_start_date": request.form.get("loan_start_date", ""),
                "other_deduction": other_deduction,
                "employee_code": request.form.get("employee_code", "").strip(),
                "bank_name": bank_name,
                "bank_account": bank_account,
                "bank_branch": bank_branch
            }
            
            try:
                ok = db.update("employees", emp_id, updates)
                if ok:
                    flash("Employee updated", "success")
                else:
                    logger.error(f"[EMPLOYEE] Update did not change row id={emp_id}")
                    flash("Failed to save employee changes", "error")
            except Exception as e:
                logger.error(f"[EMPLOYEE] Update error id={emp_id}: {e}")
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
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Employee Code</label>
                        <input type="text" name="employee_code" value="{safe_string(employee.get('employee_code', ''))}" placeholder="e.g., DAP001" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Leave Balance (days)</label>
                        <input type="number" step="0.0001" name="leave_balance" value="{safe_float(employee.get('leave_balance', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
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
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Non-Taxable Allowance (R)</label>
                        <input type="number" name="non_taxable_allowance" step="0.01" value="{safe_float(employee.get('non_taxable_allowance', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <small style="color:var(--text-muted);font-size:11px;">Paid out but excluded from PAYE, UIF, SDL and COIDA</small>
                    </div>
                    <div></div>
                </div>
                
                <h3 style="margin:25px 0 15px 0;padding-top:15px;border-top:1px solid var(--border);color:var(--text-muted);font-size:14px;">DEDUCTIONS</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Medical Aid (R)</label>
                        <input type="number" name="medical_aid" step="0.01" value="{safe_float(employee.get('medical_aid', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Medical Aid Members</label>
                        <input type="number" name="medical_members" step="1" min="0" value="{int(safe_float(employee.get('medical_members', 0)))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Total people on the medical scheme, including the employee. Used for the SARS medical tax credit. Leave 0 if no medical aid.</p>
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
                            <option value="mibfa_provident" {"selected" if employee.get("provident_fund") in ("mibfa", "mibfa_provident") else ""}>MIBFA Provident Fund (7.5% + 8.3%)</option>
                            <option value="mibfa_pension" {"selected" if employee.get("provident_fund") == "mibfa_pension" else ""}>MIBFA Pension Fund (7.5% + 8.3%)</option>
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
                <div id="mibfaInfo" style="display:{"block" if employee.get("provident_fund") in ("mibfa", "mibfa_provident", "mibfa_pension") else "none"};background:rgba(99,102,241,0.08);padding:15px;border-radius:8px;margin-bottom:15px;border:1px solid rgba(99,102,241,0.2);">
                    <div style="font-weight:600;color:var(--primary);margin-bottom:10px;font-size:13px;">🏭 MIBFA BREAKDOWN (7.5% Employee + 8.3% Employer)</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                        <div style="background:var(--card);padding:10px;border-radius:6px;">
                            <div id="mibfaEeTitle" style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">{_industry_fund_label(employee.get("provident_fund"))} (Employee)</div>
                            <div style="font-size:18px;font-weight:700;">R{safe_float(employee.get('basic_salary', 0)) * 0.075:.2f}</div>
                            <div style="font-size:11px;color:var(--text-muted);">7.5% of basic salary</div>
                        </div>
                        <div style="background:var(--card);padding:10px;border-radius:6px;">
                            <div id="mibfaErTitle" style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">{_industry_fund_label(employee.get("provident_fund"))} (Employer)</div>
                            <div style="font-size:18px;font-weight:700;">R{safe_float(employee.get('basic_salary', 0)) * 0.083:.2f}</div>
                            <div style="font-size:11px;color:var(--text-muted);">8.3% of basic salary</div>
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
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Provident Fund (R)</label>
                        <input type="number" name="provident_fund_amount" step="0.01" value="{safe_float(employee.get('provident_fund_amount', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Provident Fund Employer (R)</label>
                        <input type="number" name="pension_employer" step="0.01" value="{safe_float(employee.get('pension_employer', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employer contribution — shown as Fringe Benefit on the payslip. Leave 0 to use the Industry Fund percentage.</p>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Other Deduction (R)</label>
                        <input type="number" name="other_deduction" step="0.01" value="{safe_float(employee.get('other_deduction', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">RMA Funeral Benefit (R)</label>
                        <input type="number" name="rma_funeral" step="0.01" value="{safe_float(employee.get('rma_funeral', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employee deduction — shows on the payslip.</p>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Bargaining Council Sick Fund (R)</label>
                        <input type="number" name="sick_fund" step="0.01" value="{safe_float(employee.get('sick_fund', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employer contribution (MIBFA/MEIBC) — not deducted from the employee.</p>
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Bargaining Council Levy (R)</label>
                        <input type="number" name="council_levy" step="0.01" value="{safe_float(employee.get('council_levy', 0))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                        <p style="color:var(--text-muted);font-size:11px;margin:4px 0 0;">Employer contribution — not deducted from the employee.</p>
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
            const isMibfa = (fund === 'mibfa' || fund === 'mibfa_provident' || fund === 'mibfa_pension');
            if (mibfaInfo) {{
                mibfaInfo.style.display = isMibfa ? 'block' : 'none';
            }}
            const lbl = (fund === 'mibfa_pension') ? 'Pension Fund' : 'Provident Fund';
            const eeT = document.getElementById('mibfaEeTitle');
            const erT = document.getElementById('mibfaErTitle');
            if (eeT) eeT.textContent = lbl + ' (Employee)';
            if (erT) erT.textContent = lbl + ' (Employer)';
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
        _emp_fund = db.get_one("employees", payslip.get("employee_id")) if payslip.get("employee_id") else None
        fund_label = _industry_fund_label(_emp_fund.get("provident_fund") if _emp_fund else None)
        
        # Get all values safely
        # safe_float is module-level
        
        basic = safe_float(payslip.get("basic", 0))
        gross = safe_float(payslip.get("gross", 0)) or basic
        travel = safe_float(payslip.get("travel_allowance", 0))
        other_allow = safe_float(payslip.get("other_allowance", 0))
        non_taxable_allow = safe_float(payslip.get("non_taxable_allowance", 0))

        # Earnings rows: hourly workers (hours stored on the payslip) show a
        # Wages line with hours x rate; salaried workers show Basic Salary.
        hours_worked = safe_float(payslip.get("hours_worked", 0))
        overtime_hours = safe_float(payslip.get("overtime_hours", 0))
        emp_rate = safe_float(_emp_fund.get("hourly_rate", 0)) if _emp_fund else 0.0
        if hours_worked > 0 or overtime_hours > 0:
            _wage = round(gross - travel - other_allow, 2)
            _norm_amt = round(hours_worked * emp_rate, 2)
            _ot_amt = round(_wage - _norm_amt, 2)
            earnings_rows = (f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                             f'Wages ({hours_worked:.2f} hrs @ {money(emp_rate)}/h)</td>'
                             f'<td style="padding:6px 0;text-align:right;color:#333;">{money(_norm_amt)}</td></tr>')
            if _ot_amt > 0.005:
                earnings_rows += (f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                                  f'Overtime / premium ({overtime_hours:.2f} hrs)</td>'
                                  f'<td style="padding:6px 0;text-align:right;color:#333;">{money(_ot_amt)}</td></tr>')
        else:
            earnings_rows = ('<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                             f'Basic Salary</td><td style="padding:6px 0;text-align:right;color:#333;">{money(basic)}</td></tr>')

        paye = safe_float(payslip.get("paye", 0))
        uif = safe_float(payslip.get("uif", 0)) or safe_float(payslip.get("uif_employee", 0))
        medical = safe_float(payslip.get("medical_aid", 0))
        union_fees = safe_float(payslip.get("union_fees", 0))
        pension = safe_float(payslip.get("pension", 0)) or safe_float(payslip.get("pension_employee", 0))
        provident = safe_float(payslip.get("provident_fund", 0))
        rma_funeral = safe_float(payslip.get("rma_funeral", 0))
        loan = safe_float(payslip.get("loan_deduction", 0))
        other_ded = safe_float(payslip.get("other_deduction", 0))
        total_ded = paye + uif + medical + union_fees + pension + provident + loan + other_ded + rma_funeral
        net = safe_float(payslip.get("net", 0)) or (gross - total_ded)
        
        # Employer contributions
        uif_employer = safe_float(payslip.get("uif_employer", 0)) or uif
        sdl = safe_float(payslip.get("sdl", 0)) or (gross * 0.01)  # 1% SDL
        coida = safe_float(payslip.get("coida", 0)) or (gross * 0.01)  # ~1% COIDA
        pension_employer = safe_float(payslip.get("pension_employer", 0))
        sick_fund = safe_float(payslip.get("sick_fund", 0))
        council_levy = safe_float(payslip.get("council_levy", 0))
        total_employer = uif_employer + sdl + coida + pension_employer + sick_fund + council_levy
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
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">{fund_label} (Employee)</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(pension)}</td></tr>'
        if provident > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Provident Fund</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(provident)}</td></tr>'
        if rma_funeral > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">RMA Funeral Benefit</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(rma_funeral)}</td></tr>'
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

        # --- Sage-style payslip data ----------------------------------------
        _emp = db.get_one("employees", payslip.get("employee_id")) if payslip.get("employee_id") else None
        _emp = _emp or {}
        biz_addr = business.get("address", "") if business else ""
        emp_code = _emp.get("employee_code", "") or _emp.get("code", "") or "-"
        emp_id_num = _emp.get("id_number", "-")
        emp_position = _emp.get("position", "") or payslip.get("position", "")
        emp_started = _emp.get("start_date", "") or _emp.get("employed_from", "") or "-"
        emp_rate = safe_float(_emp.get("hourly_rate", 0))
        leave_balance = safe_float(_emp.get("leave_balance", 0))

        # YTD totals — sum this employee's payslips in the same tax year
        ytd_gross = ytd_paye = ytd_uif = ytd_net = 0.0
        try:
            _pdate = str(payslip.get("date", ""))
            _pyear = _pdate[:4] if len(_pdate) >= 4 else ""
            _all_ps = db.get("payslips", {"employee_id": payslip.get("employee_id")}) if payslip.get("employee_id") else []
            for _p in _all_ps:
                if str(_p.get("date", ""))[:4] == _pyear:
                    ytd_gross += safe_float(_p.get("gross", 0)) or safe_float(_p.get("basic", 0))
                    ytd_paye += safe_float(_p.get("paye", 0))
                    ytd_uif += safe_float(_p.get("uif", 0)) or safe_float(_p.get("uif_employee", 0))
                    ytd_net += safe_float(_p.get("net", 0))
        except Exception as _e:
            logger.error(f"[PAYSLIP] YTD calc failed: {_e}")

        content = f'''
        <style>
            .print-only {{ display: none; }}
            @media print {{
                body * {{ visibility: hidden !important; }}
                .print-area, .print-area * {{ visibility: visible !important; }}
                .print-area .print-only {{ display: block !important; }}
                .print-area {{ position: absolute; left: 0; top: -15mm; width: 100%; }}
            }}
        </style>
        
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/payroll" style="color:var(--text-muted);">← Back to Payroll</a>
            <div style="display:flex;gap:10px;">
                <a href="/payslip/{payslip_id}/edit" class="btn btn-secondary">✏️ Edit</a>
                <button class="btn btn-primary" onclick="window.print();">🖨️ Print</button>
                <a href="/payslip/{payslip_id}/delete" class="btn" style="background:var(--red);color:white;" onclick="return confirm('Delete this payslip?');">🗑️ Delete</a>
            </div>
        </div>

        <div class="print-area">
        <div class="print-only" style="background:white;color:#333;max-width:720px;margin:0 auto;padding:30px 30px 0;">
            <div style="display:flex;justify-content:space-between;margin-bottom:12px;padding-bottom:12px;border-bottom:2px solid #333;">
                <div>
                    <h2 style="color:#333;margin:0;font-size:17px;">{safe_string(biz_name)}</h2>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">{safe_string(biz_addr)}</p>
                </div>
                <div style="text-align:right;">
                    <h1 style="color:#333;margin:0;font-size:20px;">PAYSLIP</h1>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">Pay Date: {payslip.get("date", "-")}</p>
                </div>
            </div>
            <table style="width:100%;font-size:12px;color:#444;">
                <tr>
                    <td style="padding:3px 0;width:50%;"><strong>Employee:</strong> {safe_string(payslip.get("employee_name", "-"))}</td>
                    <td style="padding:3px 0;"><strong>Employee Code:</strong> {safe_string(emp_code)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Job Title:</strong> {safe_string(emp_position) or "-"}</td>
                    <td style="padding:3px 0;"><strong>ID Number:</strong> {safe_string(emp_id_num)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Employed From:</strong> {safe_string(emp_started)}</td>
                    <td style="padding:3px 0;"><strong>Rate per Hour:</strong> {money(emp_rate) if emp_rate > 0 else "-"}</td>
                </tr>
            </table>
            <div style="margin-top:14px;border-top:1px dashed #999;text-align:center;color:#999;font-size:9px;letter-spacing:2px;padding-top:4px;">FOLD HERE</div>
        </div>
        
        <div class="card" id="payslipPrint" style="background:white;color:#333;max-width:720px;margin:0 auto;padding:30px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #333;">
                <div>
                    <h2 style="color:#333;margin:0;font-size:17px;">{safe_string(biz_name)}</h2>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">{safe_string(biz_addr)}</p>
                </div>
                <div style="text-align:right;">
                    <h1 style="color:#333;margin:0;font-size:20px;">PAYSLIP</h1>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">Pay Date: {payslip.get("date", "-")}</p>
                </div>
            </div>

            <table style="width:100%;font-size:12px;color:#444;margin-bottom:20px;">
                <tr>
                    <td style="padding:3px 0;width:50%;"><strong>Employee:</strong> {safe_string(payslip.get("employee_name", "-"))}</td>
                    <td style="padding:3px 0;"><strong>Employee Code:</strong> {safe_string(emp_code)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Job Title:</strong> {safe_string(emp_position) or "-"}</td>
                    <td style="padding:3px 0;"><strong>ID Number:</strong> {safe_string(emp_id_num)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Employed From:</strong> {safe_string(emp_started)}</td>
                    <td style="padding:3px 0;"><strong>Rate per Hour:</strong> {money(emp_rate) if emp_rate > 0 else "-"}</td>
                </tr>
            </table>

            <div style="display:flex;gap:20px;flex-wrap:wrap;">
                <div style="flex:1;min-width:260px;">
                    <h4 style="color:#333;margin:10px 0 6px;font-size:12px;border-bottom:1px solid #ccc;padding-bottom:3px;">EARNINGS</h4>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        {earnings_rows}
                        {f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Travel Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(travel)}</td></tr>' if travel > 0 else ''}
                        {f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Other Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(other_allow)}</td></tr>' if other_allow > 0 else ''}
                        {f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Non-Taxable Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(non_taxable_allow)}</td></tr>' if non_taxable_allow > 0 else ''}
                        <tr style="border-bottom:2px solid #333;background:#f9f9f9;">
                            <td style="padding:7px 0;color:#333;font-weight:bold;">TOTAL EARNINGS</td>
                            <td style="padding:7px 0;text-align:right;color:#333;font-weight:bold;">{money(gross)}</td>
                        </tr>
                    </table>
                </div>
                <div style="flex:1;min-width:260px;">
                    <h4 style="color:#333;margin:10px 0 6px;font-size:12px;border-bottom:1px solid #ccc;padding-bottom:3px;">DEDUCTIONS</h4>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        {deduction_rows}
                        <tr style="border-bottom:2px solid #333;background:#fef2f2;">
                            <td style="padding:7px 0;color:#333;font-weight:bold;">TOTAL DEDUCTIONS</td>
                            <td style="padding:7px 0;text-align:right;color:#ef4444;font-weight:bold;">-{money(total_ded)}</td>
                        </tr>
                    </table>
                </div>
            </div>

            <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:#10b981;border-radius:8px;color:white;margin-top:18px;">
                <span style="font-size:16px;font-weight:bold;">NETT PAY</span>
                <span style="font-size:24px;font-weight:bold;">{money(net)}</span>
            </div>

            <div style="margin-top:14px;padding:10px 14px;background:#f5f5f5;border-radius:8px;font-size:12px;color:#555;">
                <strong>Leave Type:</strong> Annual Leave &nbsp;·&nbsp; <strong>Closing Balance:</strong> {leave_balance:.4f} days
            </div>

            <div style="margin-top:20px;text-align:center;color:#999;font-size:10px;">
                Generated by ClickAI · Computer-generated payslip · {payslip.get("date", "-")}
            </div>
        </div>

        </div>

        <div class="no-print" style="max-width:720px;margin:20px auto 0;padding:14px;background:var(--card);border:1px solid var(--border);border-radius:8px;">
            <h4 style="margin:0 0 8px;color:var(--text-muted);font-size:11px;">COMPANY CONTRIBUTIONS</h4>
            <p style="color:var(--text-muted);font-size:11px;margin:0 0 8px;">For the business — not part of the employee's payslip and not printed.</p>
            <table style="width:100%;font-size:12px;color:var(--text);">
                <tr><td style="padding:3px 0;">UIF</td><td style="text-align:right;">{money(uif_employer)}</td></tr>
                <tr><td style="padding:3px 0;">SDL (Skills Levy)</td><td style="text-align:right;">{money(sdl)}</td></tr>
                <tr><td style="padding:3px 0;">COIDA</td><td style="text-align:right;">{money(coida)}</td></tr>
                {f'<tr><td style="padding:3px 0;">{fund_label} (Employer)</td><td style="text-align:right;">{money(pension_employer)}</td></tr>' if pension_employer > 0 else ""}
                {f'<tr><td style="padding:3px 0;">Bargaining Council Sick Fund</td><td style="text-align:right;">{money(sick_fund)}</td></tr>' if sick_fund > 0 else ""}
                {f'<tr><td style="padding:3px 0;">Bargaining Council Levy</td><td style="text-align:right;">{money(council_levy)}</td></tr>' if council_levy > 0 else ""}
                <tr style="border-top:1px solid var(--border);font-weight:bold;"><td style="padding:5px 0;">Total Cost to Company</td><td style="text-align:right;">{money(total_cost)}</td></tr>
                {f'<tr><td style="padding:3px 0;color:var(--text-muted);">Fringe Benefits (period total)</td><td style="text-align:right;color:var(--text-muted);">{money(pension_employer)}</td></tr>' if pension_employer > 0 else ""}
            </table>
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
        
        # safe_float is module-level
        
        if request.method == "POST":
            # Update payslip with form values
            basic = safe_float(request.form.get("basic", 0))
            travel = safe_float(request.form.get("travel_allowance", 0))
            other_allow = safe_float(payslip.get("other_allowance", 0))
            non_taxable_allow = safe_float(payslip.get("non_taxable_allowance", 0))
            gross = safe_float(request.form.get("gross", 0)) or (basic + travel + other_allow + non_taxable_allow)
            paye = safe_float(request.form.get("paye", 0))
            uif = safe_float(request.form.get("uif", 0))
            medical = safe_float(request.form.get("medical_aid", 0))
            union_fees = safe_float(request.form.get("union_fees", 0))
            pension = safe_float(request.form.get("pension", 0))
            provident = safe_float(request.form.get("provident_fund", 0))
            rma_funeral = safe_float(request.form.get("rma_funeral", 0))
            loan = safe_float(request.form.get("loan_deduction", 0))
            other = safe_float(request.form.get("other_deduction", 0))
            
            total_ded = paye + uif + medical + union_fees + pension + provident + loan + other + rma_funeral
            net = gross - total_ded
            
            updates = {
                "basic": basic,
                "travel_allowance": travel,
                "other_allowance": other_allow,
                "non_taxable_allowance": non_taxable_allow,
                "gross": gross,
                "paye": paye,
                "uif": uif,
                "medical_aid": medical,
                "union_fees": union_fees,
                "pension": pension,
                "provident_fund": provident,
                "rma_funeral": rma_funeral,
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
        travel = safe_float(payslip.get("travel_allowance", 0))
        gross = safe_float(payslip.get("gross", 0)) or basic
        paye = safe_float(payslip.get("paye", 0))
        uif = safe_float(payslip.get("uif", 0))
        medical = safe_float(payslip.get("medical_aid", 0))
        union_fees = safe_float(payslip.get("union_fees", 0))
        pension = safe_float(payslip.get("pension", 0))
        provident = safe_float(payslip.get("provident_fund", 0))
        rma_funeral = safe_float(payslip.get("rma_funeral", 0))
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
                        <label style="display:block;margin-bottom:5px;">Travel Allowance</label>
                        <input type="number" name="travel_allowance" step="0.01" value="{travel}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
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
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;">Provident Fund</label>
                        <input type="number" name="provident_fund" step="0.01" value="{provident}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;">RMA Funeral Benefit</label>
                        <input type="number" name="rma_funeral" step="0.01" value="{rma_funeral}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
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
                    <a href="https://ufiling.labour.gov.za/uif/login" target="_blank" class="btn btn-primary" style="background:#3b82f6;">🔗 uFiling (UIF)</a>
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
    
    
    @app.route("/payroll/payslips")
    @login_required
    def payroll_payslips():
        """Bulk view of all payslips for a selected month / pay-run."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []

        from collections import defaultdict
        from datetime import datetime as dt

        by_month = defaultdict(list)
        for p in payslips:
            period = str(p.get("date") or p.get("created_at") or "")[:7]  # YYYY-MM
            if period and len(period) >= 7:
                by_month[period].append(p)

        available_months = sorted(by_month.keys(), reverse=True)

        selected = request.args.get("month", "")
        if selected not in by_month:
            selected = available_months[0] if available_months else ""

        def _month_label(_m):
            try:
                return dt.strptime(_m, "%Y-%m").strftime("%B %Y")
            except Exception:
                return _m

        options_html = ""
        for m in available_months:
            sel = " selected" if m == selected else ""
            options_html += f'<option value="{m}"{sel}>{_month_label(m)} ({len(by_month[m])} slips)</option>'

        slips = sorted(by_month.get(selected, []), key=lambda x: safe_string(x.get("employee_name", "")).lower())

        rows_html = ""
        tot = {"gross": 0, "paye": 0, "uif": 0, "pension": 0, "net": 0}
        for p in slips:
            gross = safe_float(p.get("gross", 0))
            paye = safe_float(p.get("paye", 0))
            uif = safe_float(p.get("uif", 0)) or safe_float(p.get("uif_employee", 0))
            pension = safe_float(p.get("pension", 0)) or safe_float(p.get("pension_employee", 0))
            net = safe_float(p.get("net", 0)) or (gross - (paye + uif + pension))
            tot["gross"] += gross
            tot["paye"] += paye
            tot["uif"] += uif
            tot["pension"] += pension
            tot["net"] += net
            rows_html += f'''
                <tr style="border-bottom:1px solid var(--border);">
                    <td style="padding:12px;font-weight:600;">{safe_string(p.get("employee_name", "-"))}</td>
                    <td style="padding:12px;text-align:right;">{money(gross)}</td>
                    <td style="padding:12px;text-align:right;color:#ef4444;">{money(paye)}</td>
                    <td style="padding:12px;text-align:right;color:#3b82f6;">{money(uif)}</td>
                    <td style="padding:12px;text-align:right;color:#8b5cf6;">{money(pension)}</td>
                    <td style="padding:12px;text-align:right;font-weight:600;">{money(net)}</td>
                    <td style="padding:12px;text-align:center;"><a href="/payslip/{p.get("id")}" class="btn btn-secondary" style="padding:5px 10px;font-size:12px;">View</a></td>
                </tr>'''

        if slips:
            rows_html += f'''
                <tr style="background:var(--bg);border-top:2px solid var(--text);font-weight:700;">
                    <td style="padding:14px;">TOTAL ({len(slips)} slips)</td>
                    <td style="padding:14px;text-align:right;">{money(tot["gross"])}</td>
                    <td style="padding:14px;text-align:right;color:#ef4444;">{money(tot["paye"])}</td>
                    <td style="padding:14px;text-align:right;color:#3b82f6;">{money(tot["uif"])}</td>
                    <td style="padding:14px;text-align:right;color:#8b5cf6;">{money(tot["pension"])}</td>
                    <td style="padding:14px;text-align:right;">{money(tot["net"])}</td>
                    <td style="padding:14px;"></td>
                </tr>'''
        else:
            rows_html = '<tr><td colspan="7" style="padding:20px;text-align:center;color:var(--text-muted);">No payslips for this month.</td></tr>'

        if not available_months:
            selector_html = '<p style="color:var(--text-muted);margin:0;">No payslips have been created yet.</p>'
        else:
            selector_html = f'''
            <form method="GET" action="/payroll/payslips" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
                <label style="font-weight:500;">Month / Pay-Run:</label>
                <select name="month" onchange="this.form.submit()" style="padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);min-width:220px;">
                    {options_html}
                </select>
            </form>'''

        print_all_btn = f'<a href="/payroll/payslips/print?month={selected}" class="btn btn-primary" target="_blank">🖨️ Print All</a>' if slips else ''
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <div>
                <h2 style="margin:0;">Payslips by Month</h2>
                <p style="color:var(--text-muted);margin:5px 0 0 0;">All payslips for a selected pay-run</p>
            </div>
            <div style="display:flex;gap:10px;">
                {print_all_btn}
                <a href="/payroll" class="btn btn-secondary">← Back to Payroll</a>
            </div>
        </div>

        <div class="card" style="margin-bottom:20px;">
            {selector_html}
        </div>

        <div class="card" style="overflow-x:auto;">
            <table style="width:100%;">
                <thead>
                    <tr style="background:var(--bg);">
                        <th style="padding:12px;text-align:left;">Employee</th>
                        <th style="padding:12px;text-align:right;">Gross</th>
                        <th style="padding:12px;text-align:right;">PAYE</th>
                        <th style="padding:12px;text-align:right;">UIF</th>
                        <th style="padding:12px;text-align:right;">Pension</th>
                        <th style="padding:12px;text-align:right;">Net Pay</th>
                        <th style="padding:12px;text-align:center;">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        '''

        return render_page("Payslips by Month", content, user, "payroll")

    def _payslip_print_card(payslip, business):
        """Render one payslip as a print-ready Sage-style card (used by Print All).
        Mirrors the single-payslip layout in payslip_view."""
        biz_name = business.get("name", "Business") if business else "Business"
        biz_addr = business.get("address", "") if business else ""
        _emp = db.get_one("employees", payslip.get("employee_id")) if payslip.get("employee_id") else None
        _emp = _emp or {}
        fund_label = _industry_fund_label(_emp.get("provident_fund"))

        basic = safe_float(payslip.get("basic", 0))
        gross = safe_float(payslip.get("gross", 0)) or basic
        travel = safe_float(payslip.get("travel_allowance", 0))
        other_allow = safe_float(payslip.get("other_allowance", 0))
        non_taxable_allow = safe_float(payslip.get("non_taxable_allowance", 0))

        hours_worked = safe_float(payslip.get("hours_worked", 0))
        overtime_hours = safe_float(payslip.get("overtime_hours", 0))
        emp_rate = safe_float(_emp.get("hourly_rate", 0))
        if hours_worked > 0 or overtime_hours > 0:
            _wage = round(gross - travel - other_allow - non_taxable_allow, 2)
            _norm_amt = round(hours_worked * emp_rate, 2)
            _ot_amt = round(_wage - _norm_amt, 2)
            earnings_rows = (f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                             f'Wages ({hours_worked:.2f} hrs @ {money(emp_rate)}/h)</td>'
                             f'<td style="padding:6px 0;text-align:right;color:#333;">{money(_norm_amt)}</td></tr>')
            if _ot_amt > 0.005:
                earnings_rows += (f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                                  f'Overtime / premium ({overtime_hours:.2f} hrs)</td>'
                                  f'<td style="padding:6px 0;text-align:right;color:#333;">{money(_ot_amt)}</td></tr>')
        else:
            earnings_rows = ('<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">'
                             f'Basic Salary</td><td style="padding:6px 0;text-align:right;color:#333;">{money(basic)}</td></tr>')

        paye = safe_float(payslip.get("paye", 0))
        uif = safe_float(payslip.get("uif", 0)) or safe_float(payslip.get("uif_employee", 0))
        medical = safe_float(payslip.get("medical_aid", 0))
        union_fees = safe_float(payslip.get("union_fees", 0))
        pension = safe_float(payslip.get("pension", 0)) or safe_float(payslip.get("pension_employee", 0))
        provident = safe_float(payslip.get("provident_fund", 0))
        rma_funeral = safe_float(payslip.get("rma_funeral", 0))
        loan = safe_float(payslip.get("loan_deduction", 0))
        other_ded = safe_float(payslip.get("other_deduction", 0))
        total_ded = paye + uif + medical + union_fees + pension + provident + loan + other_ded + rma_funeral
        net = safe_float(payslip.get("net", 0)) or (gross - total_ded)

        deduction_rows = (
            f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">PAYE (Tax)</td>'
            f'<td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(paye)}</td></tr>'
            f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">UIF (1%)</td>'
            f'<td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(uif)}</td></tr>'
        )
        if medical > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Medical Aid</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(medical)}</td></tr>'
        if union_fees > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Union Fees</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(union_fees)}</td></tr>'
        if pension > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">{fund_label} (Employee)</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(pension)}</td></tr>'
        if provident > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Provident Fund</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(provident)}</td></tr>'
        if rma_funeral > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">RMA Funeral Benefit</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(rma_funeral)}</td></tr>'
        if loan > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Loan Repayment</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(loan)}</td></tr>'
        if other_ded > 0:
            deduction_rows += f'<tr style="border-bottom:1px solid #eee;"><td style="padding:8px 0;color:#666;">Other Deductions</td><td style="padding:8px 0;text-align:right;color:#ef4444;">-{money(other_ded)}</td></tr>'

        emp_code = _emp.get("employee_code", "") or _emp.get("code", "") or "-"
        emp_id_num = _emp.get("id_number", "-")
        emp_position = _emp.get("position", "") or payslip.get("position", "")
        emp_started = _emp.get("start_date", "") or _emp.get("employed_from", "") or "-"
        leave_balance = safe_float(_emp.get("leave_balance", 0))

        travel_row = f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Travel Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(travel)}</td></tr>' if travel > 0 else ''
        other_row = f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Other Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(other_allow)}</td></tr>' if other_allow > 0 else ''
        nontax_row = f'<tr style="border-bottom:1px solid #eee;"><td style="padding:6px 0;color:#666;">Non-Taxable Allowance</td><td style="padding:6px 0;text-align:right;color:#333;">{money(non_taxable_allow)}</td></tr>' if non_taxable_allow > 0 else ''

        return f'''
        <div class="payslip-sheet" style="background:white;color:#333;max-width:720px;margin:0 auto 24px;padding:30px;border:1px solid #ddd;border-radius:8px;">
            <div style="display:flex;justify-content:space-between;margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #333;">
                <div>
                    <h2 style="color:#333;margin:0;font-size:17px;">{safe_string(biz_name)}</h2>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">{safe_string(biz_addr)}</p>
                </div>
                <div style="text-align:right;">
                    <h1 style="color:#333;margin:0;font-size:20px;">PAYSLIP</h1>
                    <p style="color:#666;margin:4px 0 0;font-size:12px;">Pay Date: {payslip.get("date", "-")}</p>
                </div>
            </div>
            <table style="width:100%;font-size:12px;color:#444;margin-bottom:20px;">
                <tr>
                    <td style="padding:3px 0;width:50%;"><strong>Employee:</strong> {safe_string(payslip.get("employee_name", "-"))}</td>
                    <td style="padding:3px 0;"><strong>Employee Code:</strong> {safe_string(emp_code)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Job Title:</strong> {safe_string(emp_position) or "-"}</td>
                    <td style="padding:3px 0;"><strong>ID Number:</strong> {safe_string(emp_id_num)}</td>
                </tr>
                <tr>
                    <td style="padding:3px 0;"><strong>Employed From:</strong> {safe_string(emp_started)}</td>
                    <td style="padding:3px 0;"><strong>Rate per Hour:</strong> {money(emp_rate) if emp_rate > 0 else "-"}</td>
                </tr>
            </table>
            <div style="display:flex;gap:20px;flex-wrap:wrap;">
                <div style="flex:1;min-width:260px;">
                    <h4 style="color:#333;margin:10px 0 6px;font-size:12px;border-bottom:1px solid #ccc;padding-bottom:3px;">EARNINGS</h4>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        {earnings_rows}
                        {travel_row}
                        {other_row}
                        {nontax_row}
                        <tr style="border-bottom:2px solid #333;background:#f9f9f9;">
                            <td style="padding:7px 0;color:#333;font-weight:bold;">TOTAL EARNINGS</td>
                            <td style="padding:7px 0;text-align:right;color:#333;font-weight:bold;">{money(gross)}</td>
                        </tr>
                    </table>
                </div>
                <div style="flex:1;min-width:260px;">
                    <h4 style="color:#333;margin:10px 0 6px;font-size:12px;border-bottom:1px solid #ccc;padding-bottom:3px;">DEDUCTIONS</h4>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        {deduction_rows}
                        <tr style="border-bottom:2px solid #333;background:#fef2f2;">
                            <td style="padding:7px 0;color:#333;font-weight:bold;">TOTAL DEDUCTIONS</td>
                            <td style="padding:7px 0;text-align:right;color:#ef4444;font-weight:bold;">-{money(total_ded)}</td>
                        </tr>
                    </table>
                </div>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:#10b981;border-radius:8px;color:white;margin-top:18px;">
                <span style="font-size:16px;font-weight:bold;">NETT PAY</span>
                <span style="font-size:24px;font-weight:bold;">{money(net)}</span>
            </div>
            <div style="margin-top:14px;padding:10px 14px;background:#f5f5f5;border-radius:8px;font-size:12px;color:#555;">
                <strong>Leave Type:</strong> Annual Leave &nbsp;&middot;&nbsp; <strong>Closing Balance:</strong> {leave_balance:.4f} days
            </div>
            <div style="margin-top:20px;text-align:center;color:#999;font-size:10px;">
                Generated by ClickAI &middot; Computer-generated payslip &middot; {payslip.get("date", "-")}
            </div>
        </div>'''

    @app.route("/payroll/payslips/print")
    @login_required
    def payroll_payslips_print():
        """Print all payslips for a selected month / pay-run, one slip per page."""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        payslips = db.get("payslips", {"business_id": biz_id}) if biz_id else []

        by_month = defaultdict(list)
        for p in payslips:
            period = str(p.get("date") or p.get("created_at") or "")[:7]  # YYYY-MM
            if period and len(period) >= 7:
                by_month[period].append(p)

        available_months = sorted(by_month.keys(), reverse=True)
        selected = request.args.get("month", "")
        if selected not in by_month:
            selected = available_months[0] if available_months else ""

        slips = sorted(by_month.get(selected, []), key=lambda x: safe_string(x.get("employee_name", "")).lower())

        try:
            label = datetime.strptime(selected, "%Y-%m").strftime("%B %Y") if selected else ""
        except Exception:
            label = selected

        biz_name = business.get("name", "Business") if business else "Business"

        if not slips:
            cards = '<p style="max-width:720px;margin:0 auto;color:#666;text-align:center;">No payslips for this month.</p>'
        else:
            cards = "".join(_payslip_print_card(p, business) for p in slips)

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Payslips &mdash; {safe_string(label)}</title>
<style>
    body {{ margin:0; background:#e9eaed; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif; padding:20px 0; }}
    .toolbar {{ max-width:720px; margin:0 auto 20px; display:flex; justify-content:space-between; align-items:center; gap:10px; }}
    .toolbar a, .toolbar button {{ padding:10px 16px; border-radius:6px; cursor:pointer; font-size:14px; text-decoration:none; }}
    .btn-back {{ background:#fff; color:#333; border:1px solid #ccc; }}
    .btn-print {{ background:#2563eb; color:#fff; border:none; }}
    @media print {{
        body {{ background:#fff; padding:0; }}
        .no-print {{ display:none !important; }}
        .payslip-sheet {{ border:none !important; border-radius:0 !important; page-break-after:always; }}
        .payslip-sheet:last-child {{ page-break-after:auto; }}
    }}
</style>
</head>
<body>
    <div class="toolbar no-print">
        <div>
            <div style="font-weight:700;font-size:16px;color:#222;">{safe_string(biz_name)} &mdash; Payslips</div>
            <div style="color:#666;font-size:13px;">{safe_string(label)} &middot; {len(slips)} payslip(s)</div>
        </div>
        <div style="display:flex;gap:10px;">
            <a class="btn-back" href="/payroll/payslips?month={selected}">&larr; Back</a>
            <button class="btn-print" onclick="window.print();">Print</button>
        </div>
    </div>
    {cards}
    <script>
        window.addEventListener('load', function() {{ setTimeout(function() {{ window.print(); }}, 400); }});
    </script>
</body>
</html>'''

    logger.info("[PAYROLL] All payroll routes registered ✓")
