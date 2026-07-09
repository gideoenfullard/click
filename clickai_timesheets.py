# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - TIMESHEETS MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Timesheets scan, template, review, process, discard, add,
#           Timesheet API (scan, save), Timesheets page, detail, report,
#           Timesheet log/delete APIs
# ==============================================================================

import base64
import json
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def _guess_pay_month(period_text, today_str, days=None):
    """Best-effort YYYY-MM for the pay month.

    Priority:
      1. The scanned day dates themselves (e.g. '2026/06/01') — majority
         month wins. This is the reliable source; period text like 'Jun-26'
         is whatever Sonnet wrote and previously fell back to the CURRENT
         month, which silently filtered every deviation out of the salaried
         engine.
      2. The period text ('June 2026', '2026-06', 'Jun-26').
      3. The current month.
    """
    import re as _re
    # 1) Majority YYYY-MM from the scanned day dates
    _counts = {}
    for _d in (days or []):
        _ds = str(_d.get("date", "") if isinstance(_d, dict) else _d)
        _m = _re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", _ds)
        if _m:
            _key = f"{int(_m.group(1)):04d}-{int(_m.group(2)):02d}"
            _counts[_key] = _counts.get(_key, 0) + 1
    if _counts:
        return max(_counts, key=_counts.get)
    # 2) Period text
    s = str(period_text or "")
    ym = _re.search(r"(20\d{2})[-/](\d{1,2})", s)
    if ym:
        return f"{int(ym.group(1)):04d}-{int(ym.group(2)):02d}"
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "mrt": 3, "mei": 5, "okt": 10, "des": 12,
    }
    yr = _re.search(r"(20\d{2})", s)
    low = s.lower()
    mo = None
    mo_key = None
    for k, v in months.items():
        if k in low:
            mo = v
            mo_key = k
            break
    if yr and mo:
        return f"{int(yr.group(1)):04d}-{mo:02d}"
    # 2-digit year written next to the month name (e.g. 'Jun-26')
    if mo and mo_key:
        y2 = _re.search(mo_key + r"[a-z]*\s*[-'/., ]\s*(\d{2})\b", low)
        if y2:
            return f"20{int(y2.group(1)):02d}-{mo:02d}"
    return str(today_str)[:7]


def _cell_is_time(v):
    """True when a scanned In/Out cell holds an actual clock time (not
    'Absent' / 'LATE' / 'HOLIDAY' / blank)."""
    try:
        from clickai_pay_conditions import _cell_marker
        return _cell_marker(v) == "time"
    except Exception:
        import re as _re
        s = str(v or "").strip()
        return bool(_re.match(r"^\d{1,2}\s*[:.h]\s*\d{2}$", s, _re.I)) or s.isdigit()


def _apply_review_edits(form, employees_data, count, db=None, business=None):
    """Overlay the edited per-day In/Out times from the review form onto the
    scanned batch data, then recompute each employee's worked-hour totals.

    Returns the updated employees_data list. Days the reviewer did not touch
    keep their scanned value. This is what makes a Jacqo misread (or a blank
    Out time) fixable and stick — the corrected times are written back to the
    batch and used by both pay models.

    The recompute uses the same rules as the payslip engine: the business
    split_overtime setting, each selected employee's schedule (overtime only
    past the scheduled out-time) and their lunch setting — so the review
    totals and the payslip never disagree.
    """
    try:
        from clickai_pay_conditions import compute_worked_hours
    except Exception:
        compute_worked_hours = None
    try:
        from clickai_pay_conditions import get_conditions as _get_conditions
    except Exception:
        _get_conditions = None

    split_ot = bool(business.get("split_overtime")) if business else False

    for i in range(count):
        if i >= len(employees_data):
            break
        emp = employees_data[i]
        days = emp.get("days", []) or []
        try:
            daycount = int(form.get(f"daycount_{i}", len(days)) or len(days))
        except Exception:
            daycount = len(days)
        for j in range(min(daycount, len(days))):
            in_v = form.get(f"in_{i}_{j}", None)
            out_v = form.get(f"out_{i}_{j}", None)
            if in_v is not None:
                days[j]["in"] = in_v.strip()
            if out_v is not None:
                days[j]["out"] = out_v.strip()
        # Recompute worked totals from the (possibly edited) times so the
        # hourly model and the saved entries reflect the corrections.
        if compute_worked_hours:
            cond = None
            lunch_min = 30
            if db is not None and _get_conditions is not None:
                _eid = (form.get(f"emp_{i}", "") or "").strip()
                if _eid:
                    try:
                        _erec = db.get_one("employees", _eid)
                        if _erec:
                            # The reviewer picked this employee to correct a
                            # misread name — store the real name and id on the
                            # batch so the timesheet matches the payslip and
                            # the payslip preview knows who each row is.
                            if _erec.get("name"):
                                emp["name"] = _erec.get("name")
                            emp["employee_id"] = _eid
                            cond = _get_conditions(_erec)
                            if cond["schedule"].get("lunch_deducted"):
                                lunch_min = int(float(cond["schedule"].get("lunch_minutes", 30) or 30))
                    except Exception:
                        cond = None
            worked = compute_worked_hours(days, split_overtime=split_ot,
                                          lunch_minutes=lunch_min, cond=cond)
            emp["days"] = worked["days"]
            emp["total_hours"] = worked["total_hours"]
            emp["total_overtime"] = worked["total_overtime"]
            emp["total_sunday"] = worked["total_sunday"]
        else:
            emp["days"] = days

        # Manual total override: a typed total only counts as a manual
        # override when it differs from the SERVER RECOMPUTE from the (edited)
        # times — not from the stale scanned original. The review screen's JS
        # writes the recomputed total back into the box on every edit, so
        # comparing against the scanned original wrongly flagged every time
        # correction as a manual override, which made build_payslip_gross use
        # the flat totals and skip the per-day overtime / short-hours lines.
        overridden = False
        def _ovr(field, recomputed, fallback):
            nonlocal overridden
            try:
                sub = form.get(field, None)
                if sub is None:
                    return fallback
                if abs(float(sub) - float(recomputed)) > 0.001:
                    overridden = True
                    return round(float(sub), 2)
            except Exception:
                pass
            return fallback
        emp["total_hours"] = _ovr(f"hours_{i}", emp.get("total_hours", 0), emp.get("total_hours", 0))
        emp["total_overtime"] = _ovr(f"overtime_{i}", emp.get("total_overtime", 0), emp.get("total_overtime", 0))
        emp["total_sunday"] = _ovr(f"sunday_{i}", emp.get("total_sunday", 0), emp.get("total_sunday", 0))
        emp["totals_overridden"] = overridden
    return employees_data


def register_timesheet_routes(app, db, login_required, Auth, render_page,
                              generate_id, money, safe_string, now, today,
                              _anthropic_client):
    """Register all Timesheet routes with the Flask app."""

    # === TIMESHEET SCANNING & MANAGEMENT ===

    @app.route("/timesheets/scan")
    @login_required
    def timesheets_scan():
        """Scan handwritten timesheet with AI vision - shows full daily breakdown"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        
        content = '''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/timesheets" style="color:var(--text-muted);">← Back to Timesheets</a>
            <a href="/timesheets/template" target="_blank" class="btn btn-secondary" style="padding:8px 16px;">Download Template</a>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:15px;">📷 Scan Timesheet</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">
                Take a photo of your handwritten timesheet or clock card. AI reads the clock in/out times, Flask calculates the hours.
            </p>
            
            <div id="uploadArea" style="border:2px dashed var(--border);border-radius:12px;padding:40px;text-align:center;cursor:pointer;transition:all 0.2s;" 
                 onclick="document.getElementById('fileInput').click()">
                <div style="font-size:48px;margin-bottom:15px;">[FORM]</div>
                <p style="font-size:18px;margin-bottom:10px;">Drop timesheet here or click to upload</p>
                <p style="color:var(--text-muted);font-size:14px;">Or use camera on mobile</p>
                <input type="file" id="fileInput" accept="image/*" capture="environment" style="display:none;" onchange="handleFile(this.files[0])">
            </div>
            
            <div id="preview" style="display:none;margin-top:20px;">
                <img id="previewImg" style="max-width:100%;max-height:400px;border-radius:8px;margin-bottom:15px;">
                <div style="display:flex;gap:10px;">
                    <button class="btn btn-primary" onclick="scanTimesheet()">🔍 Extract Hours</button>
                    <button class="btn btn-secondary" onclick="resetScan()">🔄 Different Image</button>
                </div>
            </div>
            
            <div id="scanning" style="display:none;text-align:center;padding:40px;">
                <div style="font-size:48px;animation:pulse 1s infinite;">👀</div>
                <p style="margin-top:15px;">AI is reading clock in/out times...</p>
                <p style="font-size:12px;color:var(--text-muted);">Flask will calculate the hours</p>
            </div>
        </div>
        
        <script>
        let currentFile = null;
        
        function handleFile(file) {
            if (!file) return;
            currentFile = file;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                document.getElementById('previewImg').src = e.target.result;
                document.getElementById('uploadArea').style.display = 'none';
                document.getElementById('preview').style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
        
        async function scanTimesheet() {
            if (!currentFile) return;
            
            document.getElementById('preview').style.display = 'none';
            document.getElementById('scanning').style.display = 'block';
            
            const formData = new FormData();
            formData.append('file', currentFile);
            
            try {
                const response = await fetch('/api/scan/timesheet', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success && data.batch_id) {
                    // Redirect to review page
                    window.location.href = '/timesheets/review/' + data.batch_id;
                } else {
                    alert('Could not read timesheet: ' + (data.error || 'Unknown error'));
                    resetScan();
                }
            } catch (err) {
                alert('Error scanning timesheet: ' + err.message);
                resetScan();
            }
        }
        
        function resetScan() {
            currentFile = null;
            document.getElementById('uploadArea').style.display = 'block';
            document.getElementById('preview').style.display = 'none';
            document.getElementById('scanning').style.display = 'none';
            document.getElementById('fileInput').value = '';
        }
        </script>
        '''
        
        return render_page("Scan Timesheet", content, user, "timesheets")
    
    
    @app.route("/timesheets/template")
    @login_required
    def timesheets_template():
        """Generate printable timesheet template PDF with active job numbers"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("business_name", business.get("name", "Company")) if business else "Company"
        
        # Get active jobs
        jobs = db.get("jobs", {"business_id": biz_id}) if biz_id else []
        active_jobs = [j for j in jobs if j.get("status") not in ["completed", "invoiced"]]
        
        # Build job list HTML
        jobs_list = ""
        for j in active_jobs[:8]:  # Max 8 jobs on template
            jobs_list += f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><div style="width:14px;height:14px;border:1px solid #333;"></div><span style="font-size:11px;">{j.get("job_number", "")} - {safe_string(j.get("title", "")[:25])}</span></div>'
        
        if not jobs_list:
            jobs_list = '<div style="font-size:11px;color:#666;">No active jobs</div>'
        
        # Generate HTML that will be converted to PDF-like display
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Timesheet - {biz_name}</title>
            <style>
                @media print {{
                    body {{ margin: 0; padding: 20px; }}
                    .no-print {{ display: none !important; }}
                }}
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background: white;
                    color: #000;
                }}
                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    border-bottom: 3px solid #333;
                    padding-bottom: 15px;
                    margin-bottom: 20px;
                }}
                .title {{
                    font-size: 24px;
                    font-weight: bold;
                    margin: 0;
                }}
                .subtitle {{
                    font-size: 14px;
                    color: #666;
                    margin: 5px 0 0 0;
                }}
                .info-grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin-bottom: 20px;
                }}
                .info-box {{
                    border: 1px solid #ccc;
                    padding: 12px;
                    border-radius: 4px;
                }}
                .info-label {{
                    font-size: 11px;
                    color: #666;
                    text-transform: uppercase;
                    margin-bottom: 5px;
                }}
                .info-value {{
                    border-bottom: 1px solid #333;
                    min-height: 24px;
                    padding: 4px 0;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                th, td {{
                    border: 1px solid #333;
                    padding: 10px 8px;
                    text-align: center;
                    font-size: 13px;
                }}
                th {{
                    background: #f0f0f0;
                    font-weight: bold;
                    font-size: 12px;
                }}
                .day-cell {{
                    text-align: left;
                    font-weight: bold;
                }}
                .write-line {{
                    border-bottom: 1px solid #999;
                    min-height: 22px;
                }}
                .totals-row {{
                    background: #f5f5f5;
                    font-weight: bold;
                }}
                .signature-section {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 40px;
                    margin-top: 30px;
                    padding-top: 20px;
                    border-top: 1px solid #ccc;
                }}
                .sig-line {{
                    border-bottom: 1px solid #333;
                    height: 40px;
                    margin-bottom: 5px;
                }}
                .sig-label {{
                    font-size: 11px;
                    color: #666;
                }}
                .jobs-box {{
                    border: 1px solid #ccc;
                    padding: 12px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                }}
                .jobs-title {{
                    font-size: 12px;
                    font-weight: bold;
                    margin-bottom: 10px;
                    color: #333;
                }}
                .print-btn {{
                    background: #6366f1;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    font-size: 16px;
                    border-radius: 8px;
                    cursor: pointer;
                    margin-bottom: 20px;
                }}
                .print-btn:hover {{
                    background: #4f46e5;
                }}
            </style>
        </head>
        <body>
            <button class="print-btn no-print" onclick="window.print()">🖨️ Print Timesheet</button>
            
            <div class="header">
                <div>
                    <h1 class="title">WEEKLY TIMESHEET</h1>
                    <p class="subtitle">{safe_string(biz_name)}</p>
                </div>
                <div style="text-align:right;">
                    <div class="info-label">Week Ending</div>
                    <div class="info-value" style="width:150px;"></div>
                </div>
            </div>
            
            <div class="info-grid">
                <div class="info-box">
                    <div class="info-label">Employee Name</div>
                    <div class="info-value"></div>
                </div>
                <div class="info-box">
                    <div class="info-label">Employee ID / Code</div>
                    <div class="info-value"></div>
                </div>
            </div>
            
            <div class="jobs-box">
                <div class="jobs-title">📌 ACTIVE JOB CARDS (tick which job you worked on)</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
                    {jobs_list}
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                        <div style="width:14px;height:14px;border:1px solid #333;"></div>
                        <span style="font-size:11px;">Other: _______________</span>
                    </div>
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th style="width:80px;">DAY</th>
                        <th style="width:80px;">DATE</th>
                        <th style="width:100px;">JOB #</th>
                        <th style="width:70px;">IN</th>
                        <th style="width:70px;">OUT</th>
                        <th style="width:70px;">IN</th>
                        <th style="width:70px;">OUT</th>
                        <th style="width:60px;">HOURS</th>
                        <th>NOTES</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td class="day-cell">Mon</td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                    </tr>
                    <tr>
                        <td class="day-cell">Tue</td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                    </tr>
                    <tr>
                        <td class="day-cell">Wed</td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                    </tr>
                    <tr>
                        <td class="day-cell">Thu</td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                    </tr>
                    <tr>
                        <td class="day-cell">Fri</td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                    </tr>
                    <tr>
                        <td class="day-cell">Sat</td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                    </tr>
                    <tr>
                        <td class="day-cell" style="color:#c00;">Sun</td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                        <td><div class="write-line"></div></td>
                    </tr>
                    <tr class="totals-row">
                        <td colspan="7" style="text-align:right;">TOTAL HOURS:</td>
                        <td><div class="write-line"></div></td>
                        <td></td>
                    </tr>
                </tbody>
            </table>
            
            <div style="font-size:11px;color:#666;margin-bottom:20px;">
                <strong>Instructions:</strong> Write job number (e.g. JC-2026-001) for each day. 
                Use 24hr time format (07:00, 16:30). Two IN/OUT columns for split shifts.
            </div>
            
            <div class="signature-section">
                <div>
                    <div class="sig-line"></div>
                    <div class="sig-label">Employee Signature & Date</div>
                </div>
                <div>
                    <div class="sig-line"></div>
                    <div class="sig-label">Supervisor Signature & Date</div>
                </div>
            </div>
            
            <div style="text-align:center;margin-top:30px;font-size:10px;color:#999;" class="no-print">
                Generated by Click AI - {today()}
            </div>
        </body>
        </html>
        '''
        
        return html
    
    
    @app.route("/timesheets/review/<batch_id>")
    @login_required
    def timesheets_review(batch_id):
        """Review scanned timesheet with full daily breakdown before saving"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get batch
        batch = db.get_one("timesheet_batches", batch_id)
        if not batch:
            return redirect("/timesheets")
        
        # Parse data
        raw_data = batch.get("data", "{}")
        parsed = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        
        if isinstance(parsed, list):
            employees_data = parsed
            period = batch.get("period", "")
        else:
            employees_data = parsed.get("employees", [])
            period = parsed.get("period", "") or batch.get("period", "")
        
        # Get employees for matching
        all_employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
        logger.info(f"[TIMESHEET REVIEW] Found {len(all_employees)} employees for business {biz_id}")
        for e in all_employees:
            logger.info(f"[TIMESHEET REVIEW] Employee: {e.get('name')} ({e.get('id')})")
        
        # Build cards for each scanned employee
        cards_html = ""
        
        # Get active jobs for dropdown
        jobs = db.get("jobs", {"business_id": biz_id}) if biz_id else []
        active_jobs = [j for j in jobs if j.get("status") not in ["completed", "invoiced"]]
        
        # Pay-conditions helpers for the live recalc: per-day scheduled
        # out-time (OT only past it) and per-employee lunch minutes, so the
        # on-screen recalculation matches the payslip engine exactly.
        _rv_get_conditions = _rv_day_schedule = _rv_weekday_of = None
        try:
            from clickai_pay_conditions import (get_conditions as _rv_get_conditions,
                                                _day_schedule as _rv_day_schedule,
                                                _weekday_of as _rv_weekday_of)
        except Exception:
            pass
        _js_sched = {}   # row index -> [scheduled out-time minutes or None per day]
        _js_lunch = {}   # row index -> lunch minutes
        
        for i, emp in enumerate(employees_data):
            scanned_name = emp.get("name", "Unknown")
            total_hours = round(float(emp.get("total_hours", 0) or 0), 2)
            total_overtime = round(float(emp.get("total_overtime", 0) or 0), 2)
            total_sunday = emp.get("total_sunday", 0)
            days = emp.get("days", [])
            
            # Job card info from scan
            scanned_job_number = emp.get("job_number", "")
            scanned_job_id = emp.get("job_id", "")
            scanned_job_title = emp.get("job_title", "")
            
            logger.info(f"[TIMESHEET REVIEW] Scanned employee: '{scanned_name}' job: '{scanned_job_number}'")
            
            # Try to match to existing employee - fuzzy match
            matched_id = ""
            matched_emp = None
            for db_emp in all_employees:
                db_name = db_emp.get("name", "").lower().strip()
                scan_name = scanned_name.lower().strip()
                # Match if exact, or if one contains the other, or first name matches
                first_name_db = db_name.split()[0] if db_name.split() else ""
                first_name_scan = scan_name.split()[0] if scan_name.split() else ""
                if (db_name == scan_name or 
                    scan_name in db_name or 
                    db_name in scan_name or
                    (first_name_db and first_name_db == first_name_scan) or
                    (first_name_scan and first_name_scan == first_name_db)):
                    matched_id = db_emp.get("id", "")
                    matched_emp = db_emp
                    logger.info(f"[TIMESHEET REVIEW] Matched '{scanned_name}' to '{db_emp.get('name')}'")
                    break
            
            # Per-day scheduled out-time + lunch for the live JS recalc
            _row_cond = None
            _row_lunch = 30
            if matched_emp is not None and _rv_get_conditions is not None:
                try:
                    _rc = _rv_get_conditions(matched_emp)
                    if _rc.get("is_setup"):
                        _row_cond = _rc
                        if _rc["schedule"].get("lunch_deducted"):
                            _row_lunch = int(float(_rc["schedule"].get("lunch_minutes", 30) or 30))
                except Exception:
                    _row_cond = None
            _js_lunch[i] = _row_lunch
            _row_sched = []
            for _d in days:
                _so_val = None
                if _row_cond is not None and _rv_weekday_of and _rv_day_schedule:
                    _wd = _rv_weekday_of(_d.get("date"))
                    if _wd is not None and _wd != 6:
                        _si, _so = _rv_day_schedule(_row_cond, _wd)
                        if _so is not None:
                            _so_val = _so
                _row_sched.append(_so_val)
            _js_sched[i] = _row_sched
            
            # Dropdown of employees
            emp_options = '<option value="">-- Select Employee --</option>'
            for db_emp in all_employees:
                selected = "selected" if db_emp.get("id") == matched_id else ""
                emp_options += f'<option value="{db_emp.get("id", "")}" {selected}>{safe_string(db_emp.get("name", ""))}</option>'
            
            # Dropdown of jobs
            job_options = '<option value="">-- No Job Card --</option>'
            for job in active_jobs:
                selected = "selected" if job.get("id") == scanned_job_id else ""
                job_options += f'<option value="{job.get("id", "")}" {selected}>{job.get("job_number", "")} - {safe_string(job.get("title", "")[:30])}</option>'
            
            # Job match indicator
            job_match_html = ""
            if scanned_job_number:
                if scanned_job_id:
                    job_match_html = f'<span style="color:#22c55e;font-size:12px;">GOOD: {scanned_job_number}</span>'
                else:
                    job_match_html = f'<span style="color:#f59e0b;font-size:12px;">Warning: {scanned_job_number} (not matched)</span>'
            
            # Build daily breakdown table
            days_html = ""
            if days:
                days_html = '''
                <table class="table" style="font-size:13px; margin-top:12px;">
                    <thead>
                        <tr style="background:rgba(255,255,255,0.05);">
                            <th>Date</th>
                            <th>In</th>
                            <th>Out</th>
                            <th>Hours</th>
                            <th style="color:#f59e0b;">OT</th>
                            <th style="color:#3b82f6;">Sun</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                '''
                calc_hours = 0
                calc_ot = 0
                calc_sunday = 0
                
                for j, day in enumerate(days):
                    d_date = day.get("date", "-")
                    d_in = day.get("in", "-")
                    d_out = day.get("out", "-")
                    d_hours = day.get("hours", 0)
                    d_ot = day.get("overtime", 0)
                    d_sunday = day.get("sunday", 0)
                    is_sun = day.get("is_sunday", False)
                    # Show the day of the week alongside the date for easier checking.
                    _wd_lbl = ""
                    if _rv_weekday_of:
                        _wd = _rv_weekday_of(d_date)
                        if _wd is not None:
                            _wd_lbl = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[_wd]
                    
                    calc_hours += d_hours
                    calc_ot += d_ot
                    calc_sunday += d_sunday
                    
                    row_style = "background:rgba(59,130,246,0.15);" if is_sun else ""
                    in_border = "1px solid var(--border)" if _cell_is_time(d_in) else "2px solid #f59e0b"
                    out_border = "1px solid var(--border)" if _cell_is_time(d_out) else "2px solid #f59e0b"
                    
                    _sun_flag = "1" if is_sun else "0"
                    days_html += f'''
                    <tr style="{row_style}">
                        <td style="white-space:nowrap;">{(_wd_lbl + " ") if _wd_lbl else ""}{d_date} {"☀️" if is_sun else ""}</td>
                        <td><input type="text" name="in_{i}_{j}" value="{safe_string(str(d_in))}" data-sun="{_sun_flag}" oninput="tsRecalc({i})" style="width:78px;padding:5px;border-radius:5px;border:{in_border};background:#1a1a2e;color:var(--text);"></td>
                        <td><input type="text" name="out_{i}_{j}" value="{safe_string(str(d_out))}" oninput="tsRecalc({i})" style="width:78px;padding:5px;border-radius:5px;border:{out_border};background:#1a1a2e;color:var(--text);"></td>
                        <td id="h_{i}_{j}">{d_hours if d_hours > 0 else "-"}</td>
                        <td id="ot_{i}_{j}" style="color:#f59e0b;font-weight:bold;">{d_ot if d_ot > 0 else "-"}</td>
                        <td id="su_{i}_{j}" style="color:#3b82f6;font-weight:bold;">{d_sunday if d_sunday > 0 else "-"}</td>
                        <td style="white-space:nowrap;">
                            <select name="status_{i}_{j}" onchange="tsRecalc({i})" style="padding:4px;border-radius:5px;border:1px solid var(--border);background:#1a1a2e;color:var(--text);font-size:12px;">
                                <option value="">Worked</option>
                                <option value="SICK">Sick (paid)</option>
                                <option value="AWP">AWP</option>
                                <option value="AWOL">AWOL</option>
                            </select>
                            <input type="number" name="stathrs_{i}_{j}" value="8" step="0.5" min="0" oninput="tsRecalc({i})" style="width:52px;padding:4px;border-radius:5px;border:1px solid var(--border);background:#1a1a2e;color:var(--text);display:none;">
                        </td>
                    </tr>
                    '''
                
                days_html += f'''
                    <tr style="background:rgba(34,197,94,0.15); font-weight:bold;">
                        <td colspan="3">CALCULATED BY FLASK</td>
                        <td id="tot_h_{i}">{calc_hours}</td>
                        <td id="tot_ot_{i}" style="color:#f59e0b;">{calc_ot}</td>
                        <td id="tot_su_{i}" style="color:#3b82f6;">{calc_sunday}</td>
                        <td></td>
                    </tr>
                </tbody></table>
                <input type="hidden" name="daycount_{i}" value="{len(days)}">
                '''
            else:
                days_html = '<p style="color:var(--text-muted);font-size:13px;">No daily breakdown available</p>'
            
            match_color = "#22c55e" if matched_id else "#f59e0b"
            match_status = "GOOD: Matched" if matched_id else "[!] No match"
            
            cards_html += f'''
            <div class="card" style="margin-bottom:16px; border-left: 4px solid {match_color};">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <div>
                        <h3 style="margin:0; font-size:18px;">👤 {safe_string(scanned_name)}</h3>
                        <span style="color:{match_color}; font-size:12px;">{match_status}</span>
                        {f' • {job_match_html}' if job_match_html else ''}
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:24px; font-weight:bold; color:#22c55e;">{total_hours} hrs</div>
                        <div style="display:flex; gap:12px; justify-content:flex-end;">
                            <span style="font-size:14px; color:#f59e0b;">{total_overtime} OT</span>
                            <span style="font-size:14px; color:#3b82f6;">{total_sunday} Sun</span>
                        </div>
                    </div>
                </div>
                
                <details open style="background:rgba(139,92,246,0.1); border-radius:8px; padding:12px; margin-bottom:16px;">
                    <summary style="cursor:pointer; font-size:12px; color:#a78bfa;">DAILY BREAKDOWN (times read by AI, hours by Flask)</summary>
                    {days_html}
                </details>
                
                <div style="display:flex; gap:12px; align-items:center; background:rgba(34,197,94,0.1); padding:12px; border-radius:8px; flex-wrap:wrap;">
                    <div style="flex:1; min-width:150px;">
                        <label class="form-label">Match to Employee</label>
                        <select name="emp_{i}" class="form-input">{emp_options}</select>
                    </div>
                    <div style="flex:1; min-width:180px;">
                        <label class="form-label" style="color:#8b5cf6;">Link to Job Card</label>
                        <select name="job_{i}" class="form-input" style="border:1px solid #8b5cf6;">{job_options}</select>
                    </div>
                    <div>
                        <label class="form-label">Normal</label>
                        <input type="number" name="hours_{i}" value="{total_hours}" class="form-input" style="width:80px;background:#1a1a2e;border:1px solid #22c55e;" step="any">
                        <input type="hidden" name="hours_orig_{i}" value="{total_hours}">
                    </div>
                    <div>
                        <label class="form-label" style="color:#f59e0b;">OT</label>
                        <input type="number" name="overtime_{i}" value="{total_overtime}" class="form-input" style="width:80px;background:#1a1a2e;border:1px solid #f59e0b;" step="any">
                        <input type="hidden" name="ot_orig_{i}" value="{total_overtime}">
                    </div>
                    <div>
                        <label class="form-label" style="color:#3b82f6;">Sunday</label>
                        <input type="number" name="sunday_{i}" value="{total_sunday}" class="form-input" style="width:80px;background:#1a1a2e;border:1px solid #3b82f6;" step="0.5">
                        <input type="hidden" name="sun_orig_{i}" value="{total_sunday}">
                    </div>
                </div>
            </div>
            '''
        
        # Get AI source from parsed data
        ai_source = parsed.get("ai_source", "") if isinstance(parsed, dict) else ""
        if "haiku" in ai_source.lower():
            ai_badge = '<span style="background:#22c55e;color:white;padding:4px 10px;border-radius:4px;font-size:12px;margin-left:10px;"> Google+Haiku</span>'
        elif "google" in ai_source.lower():
            ai_badge = '<span style="background:#22c55e;color:white;padding:4px 10px;border-radius:4px;font-size:12px;margin-left:10px;"> Google</span>'
        elif "sonnet" in ai_source.lower():
            ai_badge = '<span style="background:#8b5cf6;color:white;padding:4px 10px;border-radius:4px;font-size:12px;margin-left:10px;">🟣 Sonnet</span>'
        else:
            ai_badge = '<span style="background:#6366f1;color:white;padding:4px 10px;border-radius:4px;font-size:12px;margin-left:10px;">AI</span>'
        
        _all_batch_days = []
        for _e in employees_data:
            if isinstance(_e, dict):
                _all_batch_days.extend(_e.get("days", []) or [])
        _pay_month_default = _guess_pay_month(period, today(), days=_all_batch_days)
        _split_ot_js = "true" if (business and business.get("split_overtime")) else "false"
        content = f'''
        <div style="margin-bottom:20px;">
            <a href="/timesheets" style="color:var(--text-muted);">← Timesheets</a>
            <h1 style="margin-top:8px;">Review Scanned Timesheet {ai_badge}</h1>
            <p style="color:var(--text-muted);">Period: <strong>{period or "Not specified"}</strong> • {len(employees_data)} employees</p>
        </div>
        
        <div style="background:rgba(139,92,246,0.1); border:1px solid #8b5cf6; border-radius:8px; padding:12px 16px; margin-bottom:20px;">
            <strong>Edit before approving</strong><br>
            <span style="color:var(--text-muted);">Fix any In/Out time Jacqo misread (orange boxes), and fill in any missing Out time. Hours recalculate from the times when you approve. Match each name from the dropdown, then approve.</span>
        </div>
        
        <form method="POST" action="/timesheets/process/{batch_id}">
            {cards_html}
            
            <div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin-top:20px;">
                <label style="display:block;font-weight:600;margin-bottom:6px;">Pay month</label>
                <input type="month" name="pay_month" value="{_pay_month_default}" style="padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);">
                <div style="color:var(--text-muted);font-size:12px;margin-top:6px;">The month this timesheet is paid for. Used to work out overtime and late-coming against each employee's schedule.</div>
            </div>
            
            <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:20px;padding-bottom:30px;">
                <button type="submit" class="btn btn-primary" style="padding:14px 24px;flex:1;min-width:200px;">Approve Timesheet</button>
                <a href="/timesheets" class="btn btn-secondary" style="padding:14px 20px;">← Back</a>
                <a href="/timesheets/discard/{batch_id}" class="btn" style="background:var(--red);color:white;padding:14px 20px;" onclick="return confirm('Discard this timesheet scan?')">🗑</a>
            </div>
            
            <input type="hidden" name="count" value="{len(employees_data)}">
        </form>
        '''
        content += r"""
        <script>
        (function(){
          var TS_SPLIT_OT = __SPLIT_OT__;
          var TS_LUNCH = 30;
          var TS_SCHED = __SCHED_MAP__;
          var TS_LUNCHMAP = __LUNCH_MAP__;
          function tsParse(t){
            if(!t) return null;
            t = String(t).trim().toLowerCase().replace(/\./g,':').replace(/,/g,':').replace(/h/g,':');
            if(t==='' || t==='-') return null;
            var h,m;
            if(t.indexOf(':')>=0){ var pp=t.split(':'); h=parseInt(pp[0],10); m=(pp.length>1 && pp[1]!=='')?parseInt(pp[1],10):0; }
            else { h=parseInt(t,10); m=0; }
            if(isNaN(h)||isNaN(m)) return null;
            return h*60+m;
          }
          function tsDay(inStr,outStr,schedOut,lunch){
            var ti=tsParse(inStr), to=tsParse(outStr);
            if(ti===null||to===null) return [0,0];
            if(to<ti) to+=1440;
            var w=to-ti;
            if(w>300) w-=(lunch!=null?lunch:TS_LUNCH);
            if(w<0) w=0;
            var wh=w/60;
            if(TS_SPLIT_OT){
              if(schedOut!=null && schedOut>ti){
                var ot=Math.max(0,(to-schedOut)/60);
                if(ot>wh) ot=wh;
                return [wh-ot, ot];
              }
              return [wh, 0];
            }
            return [wh,0];
          }
          function tsFmt(x){ return String(Math.round(x*100)/100); }
          window.tsRecalc=function(i){
            var dcEl=document.getElementsByName('daycount_'+i)[0];
            var dc=dcEl?parseInt(dcEl.value,10):0;
            var th=0,tot=0,tsu=0;
            for(var j=0;j<dc;j++){
              var inp=document.getElementsByName('in_'+i+'_'+j)[0];
              var outp=document.getElementsByName('out_'+i+'_'+j)[0];
              var stEl=document.getElementsByName('status_'+i+'_'+j)[0];
              var shEl=document.getElementsByName('stathrs_'+i+'_'+j)[0];
              var isSun=inp && inp.getAttribute('data-sun')==='1';
              var status=stEl?stEl.value:'';
              if(shEl) shEl.style.display=(status==='SICK'||status==='AWP')?'':'none';
              var nh=0,oth=0,suh=0;
              if(status==='SICK'||status==='AWP'){ nh=shEl?(parseFloat(shEl.value)||0):0; }
              else if(status==='AWOL'){ nh=0; }
              else {
                var so=(TS_SCHED[i]||[])[j]; if(so===undefined) so=null;
                var lu=(TS_LUNCHMAP[i]!=null)?TS_LUNCHMAP[i]:null;
                var r=tsDay(inp?inp.value:'', outp?outp.value:'', so, lu);
                if(isSun){ suh=r[0]+r[1]; } else { nh=r[0]; oth=r[1]; }
              }
              var hc=document.getElementById('h_'+i+'_'+j);
              var oc=document.getElementById('ot_'+i+'_'+j);
              var sc=document.getElementById('su_'+i+'_'+j);
              if(hc) hc.textContent=nh>0?tsFmt(nh):'-';
              if(oc) oc.textContent=oth>0?tsFmt(oth):'-';
              if(sc) sc.textContent=suh>0?tsFmt(suh):'-';
              th+=nh; tot+=oth; tsu+=suh;
            }
            th=Math.round(th*100)/100; tot=Math.round(tot*100)/100; tsu=Math.round(tsu*100)/100;
            var e;
            e=document.getElementById('tot_h_'+i); if(e) e.textContent=tsFmt(th);
            e=document.getElementById('tot_ot_'+i); if(e) e.textContent=tsFmt(tot);
            e=document.getElementById('tot_su_'+i); if(e) e.textContent=tsFmt(tsu);
            e=document.getElementsByName('hours_'+i)[0]; if(e) e.value=th;
            e=document.getElementsByName('overtime_'+i)[0]; if(e) e.value=tot;
            e=document.getElementsByName('sunday_'+i)[0]; if(e) e.value=tsu;
          };
        })();
        </script>
""".replace("__SPLIT_OT__", _split_ot_js) \
   .replace("__SCHED_MAP__", json.dumps({str(k): v for k, v in _js_sched.items()})) \
   .replace("__LUNCH_MAP__", json.dumps({str(k): v for k, v in _js_lunch.items()}))
        
        return render_page("Review Timesheet", content, user, "timesheets")
    
    
    @app.route("/timesheets/view/<batch_id>")
    @login_required
    def timesheets_view(batch_id):
        """Read-only view of a scanned timesheet batch — works at any time,
        including after the payslips were built (the batch is never deleted)."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        batch = db.get_one("timesheet_batches", batch_id)
        if not batch:
            flash("Timesheet not found", "error")
            return redirect("/timesheets")

        raw_data = batch.get("data", "{}")
        parsed = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        if isinstance(parsed, list):
            employees_data = parsed
            period = batch.get("period", "")
        else:
            employees_data = parsed.get("employees", [])
            period = parsed.get("period", "") or batch.get("period", "")

        status = batch.get("status", "")
        created = str(batch.get("created_at", ""))[:16].replace("T", " ")

        cards_html = ""
        for emp in employees_data:
            name = emp.get("name", "Unknown")
            days = emp.get("days", [])
            rows = ""
            for day in days:
                is_sun = day.get("is_sunday", False)
                rows += f'''
                <tr style="{'background:rgba(59,130,246,0.12);' if is_sun else ''}">
                    <td style="padding:4px 8px;white-space:nowrap;">{day.get("date","-")}</td>
                    <td style="padding:4px 8px;">{safe_string(str(day.get("in","-")))}</td>
                    <td style="padding:4px 8px;">{safe_string(str(day.get("out","-")))}</td>
                    <td style="padding:4px 8px;text-align:right;">{day.get("hours",0) or "-"}</td>
                    <td style="padding:4px 8px;text-align:right;color:#f59e0b;">{day.get("overtime",0) or "-"}</td>
                    <td style="padding:4px 8px;text-align:right;color:#3b82f6;">{day.get("sunday",0) or "-"}</td>
                </tr>'''
            cards_html += f'''
            <div class="card" style="margin-bottom:14px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <h3 style="margin:0;font-size:17px;">{safe_string(name)}</h3>
                    <div style="font-size:13px;color:var(--text-muted);">
                        {emp.get("total_hours",0)} hrs · {emp.get("total_overtime",0)} OT · {emp.get("total_sunday",0)} Sun
                    </div>
                </div>
                <table style="width:100%;font-size:13px;">
                    <thead><tr style="border-bottom:1px solid var(--border);">
                        <th style="text-align:left;padding:4px 8px;">Date</th>
                        <th style="text-align:left;padding:4px 8px;">In</th>
                        <th style="text-align:left;padding:4px 8px;">Out</th>
                        <th style="text-align:right;padding:4px 8px;">Hours</th>
                        <th style="text-align:right;padding:4px 8px;">OT</th>
                        <th style="text-align:right;padding:4px 8px;">Sun</th>
                    </tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>'''

        reopen = ""
        if status not in ("processed",):
            reopen = f'<a href="/timesheets/review/{batch_id}" class="btn btn-primary" style="padding:10px 18px;">Open in review</a>'

        content = f'''
        <div style="margin-bottom:18px;">
            <a href="/timesheets" style="color:var(--text-muted);">← Timesheets</a>
            <h1 style="margin-top:8px;">Timesheet — {period or "Not specified"}</h1>
            <p style="color:var(--text-muted);">Status: <strong>{status or "—"}</strong> · Scanned {created} · {len(employees_data)} employees (read-only)</p>
        </div>
        {cards_html or '<div class="card"><p style="color:var(--text-muted);">No data on this timesheet.</p></div>'}
        <div style="display:flex;gap:10px;margin-top:6px;">
            {reopen}
            <a href="/timesheets" class="btn btn-secondary" style="padding:10px 18px;">← Back</a>
        </div>
        '''
        return render_page("View Timesheet", content, user, "timesheets")
    
    
    @app.route("/timesheets/payslip-preview/<batch_id>", methods=["GET", "POST"])
    @login_required
    def timesheets_payslip_preview(batch_id):
        """Build payslip previews from a reviewed timesheet using each
        employee's pay conditions. Shows the deviation lines before posting.
        POST comes from the review form (applies the reviewer's edits);
        GET comes from the Approve flow, reading the already-saved batch."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        batch = db.get_one("timesheet_batches", batch_id)
        if not batch:
            flash("Timesheet batch not found", "error")
            return redirect("/timesheets")

        # Pay-conditions engine (try/except so a missing module never crashes payroll)
        try:
            from clickai_pay_conditions import build_payslip_gross
        except Exception as e:
            logger.error(f"[TIMESHEET PREVIEW] pay conditions module not available: {e}")
            flash("Pay conditions module not loaded — hours are saved, but payslips cannot be built", "error")
            return redirect(f"/timesheets/review/{batch_id}")

        raw_data = batch.get("data", "{}")
        parsed = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        if isinstance(parsed, list):
            employees_data = parsed
            wrapper = {"employees": employees_data}
        else:
            employees_data = parsed.get("employees", [])
            wrapper = parsed
        # Pay month (YYYY-MM) comes from the review screen; fall back to today.
        period = (request.form.get("pay_month", "") or request.args.get("pay_month", "")
                  or today()[:7])
        if len(period) < 7:
            period = today()[:7]
        period = period[:7]

        if request.method == "POST":
            count = int(request.form.get("count", 0))

            # Apply the reviewer's In/Out edits, recompute, and persist back to the
            # batch so the corrections stick and the post step reads the fixed data.
            employees_data = _apply_review_edits(request.form, employees_data, count,
                                                 db=db, business=business)
            wrapper["employees"] = employees_data
            wrapper["period"] = wrapper.get("period", "") or batch.get("period", "")
            # Never downgrade a processed batch back to approved — reopening a
            # consumed batch is how the same hours end up paid twice.
            _b_status = "processed" if batch.get("status") == "processed" else "approved"
            try:
                db.save("timesheet_batches", {"id": batch_id, "data": json.dumps(wrapper), "status": _b_status})
            except Exception as _se:
                logger.error(f"[TIMESHEET PREVIEW] could not persist edits: {_se}")
            _emp_ids = [request.form.get(f"emp_{i}", "") for i in range(count)]
        else:
            # GET (from the Approve flow): the batch was just saved by
            # timesheets_process — read it as-is, using the employee ids the
            # reviewer confirmed there.
            count = len(employees_data)
            _emp_ids = [(e.get("employee_id") or "") if isinstance(e, dict) else ""
                        for e in employees_data]

        # Deduction maths — the same helper the posting route uses, so the
        # preview matches the posted payslip to the cent.
        try:
            from clickai_payroll import calc_monthly_paye as _paye_fn
        except Exception:
            _paye_fn = None

        def _sf(x):
            try:
                return float(x or 0)
            except Exception:
                return 0.0

        cards = ""
        hidden_emps = ""

        for i in range(count):
            emp_id = _emp_ids[i] if i < len(_emp_ids) else ""
            if not emp_id:
                continue
            emp = db.get_one("employees", emp_id)
            if not emp:
                continue

            hidden_emps += f'<input type="hidden" name="emp_{i}" value="{emp_id}">'

            employee_data = employees_data[i] if i < len(employees_data) else {"days": []}
            result = build_payslip_gross(emp, employee_data, period, business=business)
            model = result.get("pay_model", "salaried")

            # Full payslip figures — identical formulas to /payroll/post-batch
            # so what you see here is what gets posted, to the cent.
            _gross = _sf(result.get("gross", 0))
            if model == "hourly":
                _travel = _non_tax = _rma = 0.0
            else:
                _travel = _sf(emp.get("travel_allowance", 0))
                _non_tax = _sf(emp.get("non_taxable_allowance", 0))
                _rma = _sf(emp.get("rma_funeral", 0))
            _medical = _sf(emp.get("medical_aid", 0))
            _union = _sf(emp.get("union_fees", 0))
            _pension = _sf(emp.get("pension", 0))
            _loan = _sf(emp.get("loan_deduction", 0))
            _other_d = _sf(emp.get("other_deduction", 0))
            _provident = _sf(emp.get("provident_fund_amount", 0))
            _paye = 0.0
            if _paye_fn:
                try:
                    _paye = _sf(_paye_fn(_gross, _sf(emp.get("age", 0)), _pension, _provident,
                                         _sf(emp.get("medical_members", 0)), _travel))
                except Exception as _pe:
                    logger.error(f"[TIMESHEET PREVIEW] PAYE calc failed for {emp.get('name')}: {_pe}")
            _uif = min((_gross + _travel * 0.8) * 0.01, 177.12)
            _tot_ded = _paye + _uif + _medical + _union + _pension + _provident + _loan + _other_d + _rma
            _tot_earn = _gross + _travel + _non_tax
            _net = _tot_earn - _tot_ded
            _ded_bits = [("PAYE", _paye), ("UIF", _uif), ("Medical", _medical), ("Union", _union),
                         ("Pension", _pension), ("Provident", _provident), ("RMA", _rma),
                         ("Loan", _loan), ("Other", _other_d)]
            _ded_txt = " · ".join(f"{n} {money(v)}" for n, v in _ded_bits if v > 0.005) or "None"
            _extra_rows = ""
            if _travel > 0.005:
                _extra_rows += (f'<tr><td style="padding:6px 0;"></td><td>Travel Allowance</td>'
                                f'<td style="text-align:right;color:var(--green);">+{money(_travel)}</td></tr>')
            if _non_tax > 0.005:
                _extra_rows += (f'<tr><td style="padding:6px 0;"></td><td>Non-Taxable Allowance</td>'
                                f'<td style="text-align:right;color:var(--green);">+{money(_non_tax)}</td></tr>')

            # Build the line rows
            if not result["is_setup"]:
                lines_html = ('<tr><td colspan="3" style="color:var(--text-muted);padding:8px 0;">'
                              'No pay conditions set up — using basic salary. '
                              f'<a href="/employee/{emp_id}/pay-conditions" style="color:var(--accent);">Set up now</a></td></tr>')
            elif not result["lines"]:
                lines_html = '<tr><td colspan="3" style="color:var(--text-muted);padding:8px 0;">No deviations — worked exactly to schedule.</td></tr>'
            else:
                lines_html = ""
                for ln in result["lines"]:
                    colour = "var(--green)" if ln["amount"] >= 0 else "var(--red)"
                    sign = "+" if ln["amount"] >= 0 else "-"
                    lines_html += f'''
                    <tr>
                        <td style="padding:6px 0;">{ln.get("date", "")}</td>
                        <td>{safe_string(ln["label"])}</td>
                        <td style="text-align:right;color:{colour};">{sign}{money(abs(ln["amount"]))}</td>
                    </tr>'''

            if model == "hourly":
                rate_note = (f'Hourly · {money(result["hourly_rate"])}/h · '
                             f'{result.get("normal_hours",0):.1f} normal + '
                             f'{result.get("overtime_hours",0):.1f} OT + '
                             f'{result.get("sunday_hours",0):.1f} Sun')
            elif result["is_setup"]:
                rate_note = (f'Salaried · {money(result["hourly_rate"])}/h · '
                             f'{result["agreed_hours"]:.1f} agreed hours · '
                             f'base {money(result["base_pay"])}')
            else:
                rate_note = ""

            cards += f'''
            <div class="card" style="margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <div>
                        <div style="font-size:18px;font-weight:bold;">{safe_string(emp.get("name", "-"))}</div>
                        <div style="font-size:12px;color:var(--text-muted);">{rate_note}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:12px;color:var(--text-muted);">TOTAL EARNINGS {money(_tot_earn)}</div>
                        <div style="font-size:12px;color:var(--text-muted);">NET PAY</div>
                        <div style="font-size:24px;font-weight:bold;color:var(--green);">{money(_net)}</div>
                    </div>
                </div>
                <table style="width:100%;font-size:13px;">
                    <thead><tr style="border-bottom:1px solid var(--border);">
                        <th style="text-align:left;padding:4px 0;">Date</th>
                        <th style="text-align:left;">{"Item" if model == "hourly" else "Adjustment"}</th>
                        <th style="text-align:right;">Amount</th>
                    </tr></thead>
                    <tbody>{lines_html}{_extra_rows}</tbody>
                </table>
                <div style="margin-top:8px;font-size:12px;color:var(--text-muted);">Deductions: {_ded_txt} = -{money(_tot_ded)}</div>
                <div style="margin-top:12px;">
                    <button type="submit" name="only" value="{emp_id}" class="btn btn-secondary" style="padding:8px 16px;font-size:13px;">Post this payslip</button>
                </div>
            </div>'''

        if not cards:
            flash("No employees matched — select employees on the review page first", "error")
            return redirect(f"/timesheets/review/{batch_id}")

        content = f'''
        <div class="card">
            <h2 style="margin-bottom:5px;">Payslip Preview — {period}</h2>
            <p style="color:var(--text-muted);margin-bottom:10px;">Each adjustment is shown against the employee's agreed schedule. Check the figures, then post the payslips. Posting creates each payslip and its GL journal.</p>
        </div>
        <form method="POST" action="/payroll/post-batch/{batch_id}">
            <input type="hidden" name="count" value="{count}">
            <input type="hidden" name="pay_month" value="{period}">
            {hidden_emps}
            {cards}
            <div class="card" style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
                <button type="submit" name="post_all" value="1" class="btn btn-primary" style="padding:12px 24px;">Create &amp; Post All Payslips</button>
                <a href="/timesheets/review/{batch_id}" class="btn btn-secondary" style="padding:12px 20px;">← Back to review</a>
            </div>
        </form>
        '''
        return render_page("Payslip Preview", content, user, "timesheets")
    
    
    @app.route("/timesheets/process/<batch_id>", methods=["POST"])
    @login_required
    def timesheets_process(batch_id):
        """Process reviewed timesheet and save to payroll + job cards"""
        
        logger.info(f"[TIMESHEET PROCESS] Starting for batch {batch_id}")
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        count = int(request.form.get("count", 0))
        logger.info(f"[TIMESHEET PROCESS] Processing {count} employees")
        saved = 0
        job_logged = 0
        errors = []

        # Apply the reviewer's In/Out edits, recompute worked totals, and
        # persist back to the batch so the saved hours reflect the fixes and
        # the timesheet can be re-opened later.
        batch = db.get_one("timesheet_batches", batch_id)
        employees_data = []
        if batch:
            raw_data = batch.get("data", "{}")
            parsed = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            if isinstance(parsed, list):
                employees_data = parsed
                wrapper = {"employees": employees_data}
            else:
                employees_data = parsed.get("employees", [])
                wrapper = parsed
            employees_data = _apply_review_edits(request.form, employees_data, count,
                                                 db=db, business=business)
            wrapper["employees"] = employees_data
            wrapper["period"] = wrapper.get("period", "") or batch.get("period", "")
            try:
                db.save("timesheet_batches", {"id": batch_id, "data": json.dumps(wrapper)})
            except Exception as _se:
                logger.error(f"[TIMESHEET PROCESS] could not persist edits: {_se}")
        
        # Re-approving this batch REPLACES its previously saved entries instead
        # of adding to them — running Approve & Save twice must never double
        # the hours (or the job-card labour cost).
        try:
            _old_entries = db.get("timesheet_entries", {"business_id": biz_id, "batch_id": batch_id}) or []
        except Exception:
            _old_entries = []
        if _old_entries:
            # Roll this batch's labour back off any linked job cards first
            _old_job_ids = {e.get("job_id") for e in _old_entries if e.get("job_id")}
            for _jid in _old_job_ids:
                _job = db.get_one("jobs", _jid)
                if not _job:
                    continue
                try:
                    _lab = json.loads(_job.get("labour_entries", "[]"))
                except Exception:
                    _lab = []
                _keep = [le for le in _lab if le.get("batch_id") != batch_id]
                _removed = [le for le in _lab if le.get("batch_id") == batch_id]
                if _removed:
                    _rem_cost = sum(float(le.get("cost", 0) or 0) for le in _removed)
                    _rem_hours = sum(float(le.get("hours", 0) or 0) for le in _removed)
                    _new_lab_cost = max(0.0, float(_job.get("total_labour_cost", 0) or 0) - _rem_cost)
                    _new_hours = max(0.0, float(_job.get("actual_hours", 0) or 0) - _rem_hours)
                    _new_actual = float(_job.get("total_material_cost", 0) or 0) + _new_lab_cost + float(_job.get("total_additional_cost", 0) or 0)
                    db.update("jobs", _jid, {
                        "labour_entries": json.dumps(_keep),
                        "total_labour_cost": _new_lab_cost,
                        "actual_hours": _new_hours,
                        "total_actual_cost": _new_actual,
                        "profit_loss": float(_job.get("quote_value", 0) or 0) - _new_actual,
                    }, biz_id)
            try:
                db.delete_many("timesheet_entries", [e.get("id") for e in _old_entries if e.get("id")], biz_id)
                logger.info(f"[TIMESHEET PROCESS] Replaced {len(_old_entries)} previous entries for batch {batch_id}")
            except Exception as _de:
                logger.error(f"[TIMESHEET PROCESS] Could not remove previous entries for batch {batch_id}: {_de}")

        for i in range(count):
            emp_id = request.form.get(f"emp_{i}", "")
            job_id = request.form.get(f"job_{i}", "")
            # Use the recomputed totals from the (edited) times, not the
            # read-only display boxes.
            if i < len(employees_data):
                hours = float(employees_data[i].get("total_hours", 0) or 0)
                overtime = float(employees_data[i].get("total_overtime", 0) or 0)
                sunday = float(employees_data[i].get("total_sunday", 0) or 0)
            else:
                hours = float(request.form.get(f"hours_{i}", 0) or 0)
                overtime = float(request.form.get(f"overtime_{i}", 0) or 0)
                sunday = float(request.form.get(f"sunday_{i}", 0) or 0)
            
            logger.info(f"[TIMESHEET PROCESS] Row {i}: emp_id={emp_id}, job_id={job_id}, hours={hours}, ot={overtime}, sun={sunday}")
            
            if emp_id and (hours > 0 or overtime > 0 or sunday > 0):
                emp = db.get_one("employees", emp_id)
                if emp:
                    # Save timesheet entry
                    entry = {
                        "id": generate_id(),
                        "business_id": biz_id,
                        "employee_id": emp_id,
                        "employee_name": emp.get("name"),
                        "date": today(),
                        "hours": hours,
                        "overtime": overtime,
                        "sunday_hours": sunday,
                        "job_id": job_id if job_id else None,
                        "batch_id": batch_id,
                        "description": f"Scanned timesheet - {hours}h normal, {overtime}h OT, {sunday}h Sunday"
                    }
                    success, msg = db.save("timesheet_entries", entry)
                    if success:
                        saved += 1
                        logger.info(f"[TIMESHEET PROCESS] Saved entry for {emp.get('name')}")
                        
                        # === LOG TO JOB CARD IF LINKED ===
                        if job_id:
                            job = db.get_one("jobs", job_id)
                            if job:
                                # Get employee hourly rate
                                hourly_rate = float(emp.get("hourly_rate", 0))
                                ot_rate = hourly_rate * 1.5
                                sunday_rate = hourly_rate * 2
                                
                                total_hours_worked = hours + overtime + sunday
                                total_labour_cost = (hours * hourly_rate) + (overtime * ot_rate) + (sunday * sunday_rate)
                                
                                # Get existing labour entries
                                try:
                                    labour_entries = json.loads(job.get("labour_entries", "[]"))
                                except:
                                    labour_entries = []
                                
                                # Add new entry
                                labour_entry = {
                                    "date": today(),
                                    "employee": emp.get("name"),
                                    "employee_id": emp_id,
                                    "task": f"From timesheet scan",
                                    "hours": total_hours_worked,
                                    "normal_hours": hours,
                                    "overtime_hours": overtime,
                                    "sunday_hours": sunday,
                                    "rate": hourly_rate,
                                    "cost": total_labour_cost,
                                    "source": "timesheet_scan",
                                    "batch_id": batch_id,
                                    "timestamp": now()
                                }
                                labour_entries.append(labour_entry)
                                
                                # Update job totals
                                current_labour_cost = float(job.get("total_labour_cost", 0))
                                current_hours = float(job.get("actual_hours", 0))
                                new_labour_cost = current_labour_cost + total_labour_cost
                                new_hours = current_hours + total_hours_worked
                                
                                total_actual_cost = float(job.get("total_material_cost", 0)) + new_labour_cost + float(job.get("total_additional_cost", 0))
                                quote_value = float(job.get("quote_value", 0))
                                profit_loss = quote_value - total_actual_cost
                                
                                # Update job card
                                job_update = {
                                    "labour_entries": json.dumps(labour_entries),
                                    "total_labour_cost": new_labour_cost,
                                    "actual_hours": new_hours,
                                    "total_actual_cost": total_actual_cost,
                                    "profit_loss": profit_loss
                                }
                                
                                # Auto-start job if not started
                                if job.get("status") == "not_started":
                                    job_update["status"] = "in_progress"
                                    job_update["started_at"] = now()
                                
                                db.update("jobs", job_id, job_update, biz_id)
                                job_logged += 1
                                logger.info(f"[TIMESHEET PROCESS] Logged {total_hours_worked}h to job {job.get('job_number')} for {emp.get('name')}")
                    else:
                        errors.append(f"{emp.get('name')}: {msg}")
                        logger.error(f"[TIMESHEET PROCESS] Failed to save entry: {msg}")
                else:
                    logger.warning(f"[TIMESHEET PROCESS] Employee not found: {emp_id}")
            else:
                logger.info(f"[TIMESHEET PROCESS] Skipping row {i} - no emp_id or zero hours")
        
        # Mark batch as approved (NOT processed) — the hours are saved to
        # timesheet entries / job cards, but the batch stays available so
        # Run Payroll or a batch post can still create the payslips. It is
        # only marked processed once payslips have actually been created.
        db.save("timesheet_batches", {"id": batch_id, "status": "approved"})
        
        logger.info(f"[TIMESHEET PROCESS] Done: saved {saved}, job_logged {job_logged}, errors: {len(errors)}")
        
        if errors:
            flash(f"Saved {saved} entries ({job_logged} linked to job cards). Errors: {', '.join(errors)}", "error")
        else:
            flash(f"Approved — {saved} timesheet entries saved ({job_logged} linked to job cards). Check the payslips below, then post.", "success")
        
        # Flow straight into the payslip preview so approving the timesheet
        # leads to the payslips in one motion — no manual detour via Payroll.
        _pm = (request.form.get("pay_month", "") or today()[:7])[:7]
        return redirect(f"/timesheets/payslip-preview/{batch_id}?pay_month={_pm}")
    
    
    @app.route("/timesheets/discard/<batch_id>")
    @login_required
    def timesheets_discard(batch_id):
        """Discard a timesheet batch"""
        db.save("timesheet_batches", {"id": batch_id, "status": "discarded"})
        return redirect("/timesheets")
    
    
    @app.route("/timesheets/add", methods=["GET", "POST"])
    @login_required
    def timesheets_add():
        """Manual timesheet entry"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
        
        if request.method == "POST":
            emp_id = request.form.get("employee_id")
            period = request.form.get("period", "")
            hours = float(request.form.get("hours", 0) or 0)
            overtime = float(request.form.get("overtime", 0) or 0)
            sunday = float(request.form.get("sunday_hours", 0) or 0)
            description = request.form.get("description", "")
            
            # Get employee name
            emp = next((e for e in employees if e.get("id") == emp_id), None)
            emp_name = emp.get("name", "Unknown") if emp else "Unknown"
            
            entry = {
                "id": generate_id(),
                "business_id": biz_id,
                "employee_id": emp_id,
                "employee_name": emp_name,
                "date": today(),
                "period": period,
                "hours": hours,
                "overtime": overtime,
                "sunday_hours": sunday,
                "description": description or f"Manual entry - {hours}h normal, {overtime}h OT",
                "processed": False,
                "created_at": now()
            }
            
            success, _ = db.save("timesheet_entries", entry)
            if success:
                flash(f"Timesheet added for {emp_name}", "success")
            else:
                flash("Failed to save timesheet", "error")
            
            return redirect("/payroll")
        
        # Build employee options
        emp_options = '<option value="">-- Select Employee --</option>'
        for e in employees:
            emp_options += f'<option value="{e.get("id")}">{safe_string(e.get("name", "-"))}</option>'
        
        content = f'''
        <div class="card">
            <h2 style="margin-bottom:20px;">➕ Add Timesheet Entry</h2>
            
            <form method="POST">
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:15px;">
                    <div>
                        <label class="form-label">Employee *</label>
                        <select name="employee_id" class="form-input" required>
                            {emp_options}
                        </select>
                    </div>
                    <div>
                        <label class="form-label">Period (Month)</label>
                        <input type="month" name="period" class="form-input" value="{today()[:7]}">
                    </div>
                    <div>
                        <label class="form-label">Normal Hours</label>
                        <input type="number" name="hours" value="0" class="form-input" step="0.5" min="0">
                    </div>
                    <div>
                        <label class="form-label">Overtime Hours (1.5×)</label>
                        <input type="number" name="overtime" value="0" class="form-input" step="0.5" min="0">
                    </div>
                    <div>
                        <label class="form-label">Sunday Hours (2×)</label>
                        <input type="number" name="sunday_hours" value="0" class="form-input" step="0.5" min="0">
                    </div>
                    <div>
                        <label class="form-label">Description</label>
                        <input type="text" name="description" class="form-input" placeholder="e.g. Week 1-4 January">
                    </div>
                </div>
                
                <div style="display:flex;gap:10px;margin-top:20px;">
                    <button type="submit" class="btn btn-primary" style="padding:12px 30px;">💾 Save Timesheet</button>
                    <a href="/payroll" class="btn btn-secondary" style="padding:12px 30px;">Cancel</a>
                </div>
            </form>
        </div>
        '''
        
        return render_page("Add Timesheet", content, user, "payroll")
    
    
    @app.route("/api/scan/timesheet", methods=["POST"])
    @login_required
    def api_scan_timesheet():
        """Scan timesheet with full daily breakdown - extracts in/out times, Flask calculates hours"""
        
        try:
            file = request.files.get("file")
            if not file:
                return jsonify({"success": False, "error": "No file uploaded"})
            
            file_data = file.read()
            if not file_data:
                return jsonify({"success": False, "error": "The uploaded file is empty — please try again"})
            base64_data = base64.b64encode(file_data).decode('utf-8')
            
            # Detect the real file type from its magic bytes. The filename extension is
            # unreliable — phone photos and "saved as" files are often mislabelled, which
            # makes the vision API reject them with "Could not process image".
            _head = file_data[:16]
            if _head[:4] == b"%PDF":
                media_type = "application/pdf"
            elif _head[:8] == b"\x89PNG\r\n\x1a\n":
                media_type = "image/png"
            elif _head[:3] == b"\xff\xd8\xff":
                media_type = "image/jpeg"
            elif _head[:4] == b"GIF8":
                media_type = "image/gif"
            elif _head[:4] == b"RIFF" and file_data[8:12] == b"WEBP":
                media_type = "image/webp"
            elif _head[4:8] == b"ftyp" and file_data[8:12] in (b"heic", b"heif", b"heix", b"mif1"):
                return jsonify({"success": False, "error": "HEIC photos aren't supported. On your phone, save or share the timesheet as JPG (or take a screenshot), then upload that."})
            else:
                return jsonify({"success": False, "error": "Unsupported file type. Please upload a JPG, PNG, or PDF of the timesheet."})
            
            # Get employees for context
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
            emp_names = [e.get("name", "") for e in employees]
            
            # Get active jobs for context
            jobs = db.get("jobs", {"business_id": biz_id}) if biz_id else []
            active_jobs = [j for j in jobs if j.get("status") not in ["completed", "invoiced"]]
            job_numbers = [j.get("job_number", "") for j in active_jobs]
            
            client = _anthropic_client
            
            # IMPORTANT: Only extract times - Flask calculates hours
            prompt = f"""Analyze this handwritten timesheet/clockcard image carefully.
    
    READ ONLY - DO NOT CALCULATE ANYTHING. Just extract exactly what is written.
    
    Known employees: {', '.join(emp_names) if emp_names else 'Not specified'}
    Active job numbers: {', '.join(job_numbers) if job_numbers else 'JC-2026-001, JC-2026-002, etc'}
    
    For EACH employee on the sheet, extract:
    1. Employee name (read carefully, exactly as written)
    2. For each day: the date/day AND the clock in time AND clock out time (exactly as written)
    3. Job number/code if written (look for JC-XXX, JC XXX, Job XXX, or similar patterns)
    
    Return ONLY valid JSON in this exact format:
    {{
      "period": "Week of 6-12 Jan 2026",
      "employees": [
        {{
          "name": "John Smith",
          "job_number": "JC-2026-001",
          "days": [
            {{"date": "Mon 6", "in": "07:00", "out": "16:00"}},
            {{"date": "Tue 7", "in": "07:00", "out": "17:30"}},
            {{"date": "Wed 8", "in": "07:00", "out": "16:00"}},
            {{"date": "Sat 11", "in": "08:00", "out": "13:00"}},
            {{"date": "Sun 12", "in": "08:00", "out": "12:00"}}
          ]
        }}
      ]
    }}
    
    IMPORTANT:
    - Only read what is written - DO NOT calculate hours
    - Read times in 24hr format (07:00, 16:00, etc)
    - If a time is unclear, make your best guess
    - Read EVERY dated row that has clock times, including Saturdays and Sundays - never skip a weekend row that has times written
    - Only skip a row when it is genuinely blank or marked off (no times written)
    - Look for job numbers written as JC-001, JC 001, Job 001, J001, etc - normalize to JC-XXXX-XXX format
    - If no job number is found for an employee, set job_number to null
    - DO NOT add any hours or overtime fields - just in/out times"""
    
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            ({"type": "document", "source": {"type": "base64", "media_type": media_type, "data": base64_data}} if media_type == "application/pdf" else {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_data}}),
                            {"type": "text", "text": prompt}
                        ]
                    }
                ]
            )
            
            # ─── AI-USAGE TRACKING ───
            try:
                if hasattr(app, "_ai_usage_tracker") and biz_id:
                    _usage = getattr(message, "usage", None)
                    app._ai_usage_tracker.log_usage(
                        business_id=biz_id,
                        tool="timesheet_scan",
                        model=getattr(message, "model", "claude-sonnet-4-6"),
                        input_tokens=int(getattr(_usage, "input_tokens", 0) or 0),
                        output_tokens=int(getattr(_usage, "output_tokens", 0) or 0),
                        cache_read_tokens=int(getattr(_usage, "cache_read_input_tokens", 0) or 0),
                        cache_write_tokens=int(getattr(_usage, "cache_creation_input_tokens", 0) or 0),
                        success=True,
                    )
            except Exception as _track_err:
                logger.error(f"[AI-USAGE] timesheet_scan tracking skipped: {_track_err}")
            # ─── END TRACKING ───
            
            response_text = message.content[0].text.strip()
            
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            parsed = json.loads(response_text)
            raw_employees = parsed.get("employees", [])
            period = parsed.get("period", "")
            
            # ═══════════════════════════════════════════════════════════════════════
            # FLASK CALCULATES HOURS - Not Claude!
            # ═══════════════════════════════════════════════════════════════════════
            # Per-business setting: when off, all worked hours count as normal (no OT split)
            split_overtime = bool(business.get("split_overtime")) if business else False

            # Pay-conditions helpers — overtime is only time worked past the
            # employee's scheduled out-time (owner decision 2026-07-06). The
            # scanned name is matched to an employee so the scan view shows
            # the same Normal/OT split the payslip will use. Falls back to
            # the old flat 8-hour split when the module or a match is missing.
            _pc_get_conditions = _pc_day_schedule = _pc_weekday_of = None
            try:
                from clickai_pay_conditions import (get_conditions as _pc_get_conditions,
                                                    _day_schedule as _pc_day_schedule,
                                                    _weekday_of as _pc_weekday_of)
            except Exception:
                pass
            _sched_emps = db.get("employees", {"business_id": biz_id}) if biz_id else []

            def _match_employee_cond(scan_name):
                """Fuzzy name match (same rule as the review screen) -> the
                employee's pay conditions, or None when unmatched/not set up."""
                if not _pc_get_conditions or not scan_name:
                    return None
                sn = str(scan_name).lower().strip()
                sn_first = sn.split()[0] if sn.split() else ""
                for _de in _sched_emps:
                    dn = (_de.get("name", "") or "").lower().strip()
                    dn_first = dn.split()[0] if dn.split() else ""
                    if (dn == sn or sn in dn or dn in sn or
                            (dn_first and dn_first == sn_first)):
                        try:
                            _c = _pc_get_conditions(_de)
                            return _c if _c.get("is_setup") else None
                        except Exception:
                            return None
                return None
            
            def parse_time(t):
                """Convert time string to minutes since midnight"""
                if not t or t == "-":
                    return None
                t = str(t).strip().lower().replace(".", ":").replace(",", ":").replace("h", ":")
                try:
                    if ":" in t:
                        parts = t.split(":")
                        h = int(parts[0])
                        m = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
                    else:
                        h = int(t)
                        m = 0
                    return h * 60 + m
                except:
                    return None
            
            # Use the same Sunday detection as the payslip recompute so the
            # scan view and the payslip never disagree (parses a real ISO date
            # when present, else falls back to the label text).
            try:
                from clickai_pay_conditions import _is_sunday as is_sunday
            except Exception:
                def is_sunday(date_str):
                    sl = str(date_str or "").lower()
                    return "sun" in sl or "son" in sl  # English or Afrikaans
            
            def calc_hours(time_in, time_out, lunch_break=30, sched_out=None):
                """Calculate work hours from in/out times"""
                if time_in is None or time_out is None:
                    return 0, 0
                
                # Handle overnight (out < in means next day)
                if time_out < time_in:
                    time_out += 24 * 60
                
                worked_minutes = time_out - time_in
                
                # Only deduct lunch if worked more than 5 hours
                if worked_minutes > 300:
                    worked_minutes -= lunch_break
                
                if worked_minutes < 0:
                    worked_minutes = 0
                
                worked_hours = worked_minutes / 60
                
                # Overtime split is controlled per-business.
                # When split_overtime is off, all worked hours count as normal.
                # OT exists ONLY past a valid scheduled out-time (owner
                # decision 2026-07-06). A sched_out at/before the clock-in is
                # invalid (would turn the whole day into OT) and is ignored.
                # No (valid) schedule -> no OT: all hours normal.
                if split_overtime:
                    if sched_out is not None and sched_out <= time_in:
                        sched_out = None
                    if sched_out is not None:
                        overtime = max(0, (time_out - sched_out) / 60)
                        if overtime > worked_hours:
                            overtime = worked_hours
                        normal = worked_hours - overtime
                    else:
                        normal = worked_hours
                        overtime = 0
                else:
                    normal = worked_hours
                    overtime = 0
                
                # Return exact hours — totals are rounded once at the end so
                # summing per-day values never drifts (kept identical to the
                # payslip recompute in compute_worked_hours).
                return normal, overtime
            
            # Process each employee - Flask calculates!
            processed_employees = []
            for emp in raw_employees:
                emp_name = emp.get("name", "Unknown")
                job_number = emp.get("job_number", None)
                days = emp.get("days", [])
                
                # Try to match job number to actual job
                matched_job_id = None
                matched_job_title = None
                if job_number:
                    # Normalize job number format
                    jn_clean = job_number.upper().replace(" ", "-").replace("JC", "JC-").replace("--", "-")
                    for job in active_jobs:
                        if jn_clean in job.get("job_number", "").upper() or job.get("job_number", "").upper() in jn_clean:
                            matched_job_id = job.get("id")
                            matched_job_title = job.get("title", "")
                            job_number = job.get("job_number")  # Use exact format
                            break
                
                # Schedule-aware OT: use the matched employee's agreed
                # out-time per weekday and their lunch setting.
                _emp_cond = _match_employee_cond(emp_name)
                _emp_lunch = 30
                if _emp_cond and _emp_cond["schedule"].get("lunch_deducted"):
                    try:
                        _emp_lunch = int(float(_emp_cond["schedule"].get("lunch_minutes", 30) or 30))
                    except Exception:
                        _emp_lunch = 30

                calculated_days = []
                total_hours = 0
                total_overtime = 0
                total_sunday = 0
                
                for day in days:
                    d_date = day.get("date", "-")
                    d_in = day.get("in", "-")
                    d_out = day.get("out", "-")
                    
                    time_in = parse_time(d_in)
                    time_out = parse_time(d_out)
                    
                    _sched_out = None
                    if _emp_cond and _pc_weekday_of and _pc_day_schedule:
                        _wd = _pc_weekday_of(d_date)
                        if _wd is not None and _wd != 6:
                            _si, _so = _pc_day_schedule(_emp_cond, _wd)
                            if _so is not None:
                                _sched_out = _so
                    
                    hours, ot = calc_hours(time_in, time_out, lunch_break=_emp_lunch, sched_out=_sched_out)
                    
                    # Check if Sunday - all hours count as Sunday rate
                    sunday_hours = 0
                    if is_sunday(d_date):
                        sunday_hours = hours + ot
                        total_sunday += sunday_hours
                        hours = 0
                        ot = 0
                    else:
                        total_hours += hours
                        total_overtime += ot
                    
                    calculated_days.append({
                        "date": d_date,
                        "in": d_in,
                        "out": d_out,
                        "hours": round(hours, 2),
                        "overtime": round(ot, 2),
                        "sunday": round(sunday_hours, 2),
                        "is_sunday": is_sunday(d_date)
                    })
                
                processed_employees.append({
                    "name": emp_name,
                    "job_number": job_number,
                    "job_id": matched_job_id,
                    "job_title": matched_job_title,
                    "days": calculated_days,
                    "total_hours": round(total_hours, 2),
                    "total_overtime": round(total_overtime, 2),
                    "total_sunday": round(total_sunday, 2)
                })
            
            # Save as a batch for review
            batch_id = generate_id()
            db.save("timesheet_batches", {
                "id": batch_id,
                "business_id": biz_id,
                "period": period,
                "data": json.dumps({"period": period, "employees": processed_employees}),
                "status": "pending",
                "created_at": now()
            })
            
            return jsonify({
                "success": True,
                "batch_id": batch_id,
                "period": period,
                "employees": processed_employees
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"[TIMESHEET SCAN] JSON parse error: {e}")
            return jsonify({"success": False, "error": "Could not parse timesheet data"})
        except Exception as e:
            logger.error(f"[TIMESHEET SCAN] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/scan/timesheet/save", methods=["POST"])
    @login_required
    def api_scan_timesheet_save():
        """Save scanned timesheet entries"""
        
        try:
            data = request.get_json()
            entries = data.get("entries", [])
            
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
            emp_map = {e.get("name", "").lower(): e for e in employees}
            
            count = 0
            for entry in entries:
                name = entry.get("name", "")
                hours = float(entry.get("hours", 0)) + float(entry.get("overtime", 0) * 1.5)  # OT at 1.5x
                
                # Find employee
                employee = emp_map.get(name.lower())
                if not employee:
                    # Try partial match
                    for emp_name, emp in emp_map.items():
                        if name.lower() in emp_name or emp_name in name.lower():
                            employee = emp
                            break
                
                if employee and hours > 0:
                    db.save("timesheet_entries", {
                        "id": generate_id(),
                        "business_id": biz_id,
                        "employee_id": employee.get("id"),
                        "employee_name": employee.get("name"),
                        "date": entry.get("date", today()),
                        "hours": hours,
                        "description": f"Scanned timesheet - {entry.get('hours', 0)}h normal, {entry.get('overtime', 0)}h OT",
                        "created_at": now()
                    })
                    count += 1
            
            return jsonify({"success": True, "count": count})
            
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    # === TIMESHEETS PAGE, DETAIL, REPORT, APIs ===

    @app.route("/timesheets")
    @login_required
    def timesheets_page():
        """Employee Timesheets"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get employees — always alphabetical so the cards and dropdowns keep
        # a stable order (the database returns rows in a different order on
        # every request, which made employees jump around the page).
        employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
        employees.sort(key=lambda e: (e.get("name") or "").lower())
        
        # Get this week's timesheet entries
        today_date = datetime.now().date()
        week_start = today_date - timedelta(days=today_date.weekday())  # Monday
        week_end = week_start + timedelta(days=6)  # Sunday
        
        entries = db.get("timesheet_entries", {"business_id": biz_id}) if biz_id else []
        week_entries = []
        for e in entries:
            try:
                entry_date = datetime.strptime(e.get("date", ""), "%Y-%m-%d").date()
                if week_start <= entry_date <= week_end:
                    week_entries.append(e)
            except:
                pass
        
        # Group by employee
        employee_hours = {}
        for emp in employees:
            emp_id = emp.get("id")
            emp_entries = [e for e in week_entries if e.get("employee_id") == emp_id]
            total_hours = sum(float(e.get("hours", 0)) for e in emp_entries)
            employee_hours[emp_id] = {
                "name": emp.get("name"),
                "entries": emp_entries,
                "total_hours": total_hours
            }
        
        # Build employee cards
        emp_cards = ""
        for emp in employees:
            emp_id = emp.get("id")
            data = employee_hours.get(emp_id, {"total_hours": 0, "entries": []})
            hours = data["total_hours"]
            hourly_rate = float(emp.get("hourly_rate", 0))
            week_earnings = hours * hourly_rate
            
            emp_cards += f'''
            <div class="card" style="cursor:pointer;" onclick="window.location='/timesheet/{emp_id}'">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <h3 style="margin:0;">{safe_string(emp.get("name", "-"))}</h3>
                        <p style="color:var(--text-muted);margin:5px 0 0 0;">{safe_string(emp.get("position", "Employee"))}</p>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:24px;font-weight:bold;color:var(--primary);">{hours:.1f}h</div>
                        <div style="color:var(--text-muted);font-size:14px;">this week</div>
                        {f'<div style="color:var(--green);font-size:14px;">{money(week_earnings)}</div>' if hourly_rate else ''}
                    </div>
                </div>
            </div>
            '''
        
        # Get jobs for dropdown
        jobs = db.get("jobs", {"business_id": biz_id}) if biz_id else []
        active_jobs = [j for j in jobs if j.get("status") != "completed"]
        job_options = "".join([f'<option value="{j.get("id")}">{j.get("job_number")} - {safe_string(j.get("title", ""))}</option>' for j in active_jobs])
        
        emp_options = "".join([f'<option value="{e.get("id")}">{safe_string(e.get("name", ""))}</option>' for e in employees])

        # Scanned timesheet batches — including processed ones, so a timesheet
        # can be re-opened and viewed at any time after the payslips are built.
        batches = db.get("timesheet_batches", {"business_id": biz_id}) if biz_id else []
        batches = [b for b in batches if b.get("status") != "discarded"]
        batches.sort(key=lambda b: str(b.get("created_at", "")), reverse=True)
        _status_label = {"pending": "Pending review", "approved": "Approved",
                         "processed": "Payslips built"}
        _status_colour = {"pending": "#f59e0b", "approved": "#3b82f6",
                          "processed": "#22c55e"}
        archive_rows = ""
        for b in batches[:50]:
            try:
                _d = json.loads(b.get("data", "{}")) if isinstance(b.get("data"), str) else (b.get("data") or {})
                _emps = _d if isinstance(_d, list) else _d.get("employees", [])
            except Exception:
                _emps = []
            st = b.get("status", "")
            _names = ", ".join(safe_string(e.get("name", "")) for e in _emps if isinstance(e, dict) and e.get("name"))
            # A pending (freshly scanned) batch opens in REVIEW so it can be
            # checked and approved; processed/approved ones open read-only.
            _open_url = f'/timesheets/review/{b.get("id")}' if st == "pending" else f'/timesheets/view/{b.get("id")}'
            _btn_label = "Review" if st == "pending" else "View"
            _btn_style = "btn-primary" if st == "pending" else "btn-secondary"
            archive_rows += f'''
            <tr style="cursor:pointer;" onclick="window.location='{_open_url}'">
                <td style="padding:8px;">{safe_string(b.get("period","") or "—")}</td>
                <td style="padding:8px;">{_names or "—"} ({len(_emps)})</td>
                <td style="padding:8px;"><span style="color:{_status_colour.get(st,'var(--text-muted)')};">{_status_label.get(st, st or "—")}</span></td>
                <td style="padding:8px;color:var(--text-muted);">{str(b.get("created_at",""))[:10]}</td>
                <td style="padding:8px;text-align:right;"><a href="{_open_url}" class="btn {_btn_style}" style="padding:5px 12px;font-size:12px;">{_btn_label}</a></td>
            </tr>'''
        archive_section = f'''
        <div class="card" style="margin-top:20px;">
            <h3 style="margin:0 0 12px 0;">Scanned Timesheets</h3>
            <table style="width:100%;font-size:13px;">
                <thead><tr style="border-bottom:1px solid var(--border);color:var(--text-muted);">
                    <th style="text-align:left;padding:8px;">Period</th>
                    <th style="text-align:left;padding:8px;">Employees</th>
                    <th style="text-align:left;padding:8px;">Status</th>
                    <th style="text-align:left;padding:8px;">Scanned</th>
                    <th></th>
                </tr></thead>
                <tbody>{archive_rows or '<tr><td colspan="5" style="padding:10px;color:var(--text-muted);">No scanned timesheets yet.</td></tr>'}</tbody>
            </table>
        </div>
        '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <h2 style="margin:0;">Timesheets</h2>
            <a href="/timesheets/scan" class="btn btn-primary" style="background:#8b5cf6;">
                📷 Scan Timesheet
            </a>
        </div>
        
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin:0 0 15px 0;"> Quick Clock In</h3>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px;align-items:end;">
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">Employee</label>
                    <select id="clockEmployee" class="form-input">
                        <option value="">Select...</option>
                        {emp_options}
                    </select>
                </div>
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">Job (optional)</label>
                    <select id="clockJob" class="form-input">
                        <option value="">No job</option>
                        {job_options}
                    </select>
                </div>
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">Hours</label>
                    <input type="number" id="clockHours" class="form-input" value="8" min="0.5" max="24" step="0.5">
                </div>
                <button class="btn btn-primary" onclick="quickClockIn()"> Log Time</button>
            </div>
        </div>
        
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
            <h2 style="margin:0;"> This Week ({week_start.strftime("%d %b")} - {week_end.strftime("%d %b")})</h2>
            <div style="display:flex;gap:10px;">
                <button class="btn btn-primary" onclick="window.location='/timesheets/scan'"> Scan Timesheet</button>
                <button class="btn btn-secondary" onclick="window.location='/timesheets/report'"> Report</button>
            </div>
        </div>
        
        <div class="stats-grid">
            {emp_cards or '<div class="card"><p style="color:var(--text-muted);text-align:center;">No employees yet. Add employees in Payroll.</p></div>'}
        </div>
        
        {archive_section}
        
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:10px;"> Tips</h3>
            <p style="color:var(--text-muted);">
                 Say "Log 8 hours for John on JOB-0001"<br>
                 Say "Show me timesheet for this week"<br>
                 Click an employee to see their full timesheet
            </p>
        </div>
        
        <script>
        async function quickClockIn() {{
            const empId = document.getElementById('clockEmployee').value;
            const jobId = document.getElementById('clockJob').value;
            const hours = document.getElementById('clockHours').value;
            
            if (!empId) {{
                alert('Please select an employee');
                return;
            }}
            
            const response = await fetch('/api/timesheet/log', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    employee_id: empId,
                    job_id: jobId || null,
                    hours: parseFloat(hours),
                    date: '{today()}'
                }})
            }});
            
            const data = await response.json();
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error: ' + (data.error || 'Failed to log time'));
            }}
        }}
        </script>
        '''
        
        return render_page("Timesheets", content, user, "timesheets")
    
    
    @app.route("/timesheet/<employee_id>")
    @login_required
    def timesheet_detail(employee_id):
        """Individual employee timesheet"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        employee = db.get_one("employees", employee_id)
        if not employee:
            return redirect("/timesheets")
        
        # Get all entries for this employee
        entries = db.get("timesheet_entries", {"business_id": biz_id, "employee_id": employee_id}) if biz_id else []
        entries = sorted(entries, key=lambda x: x.get("date", ""), reverse=True)
        
        # Get jobs for reference
        jobs = db.get("jobs", {"business_id": biz_id}) if biz_id else []
        job_map = {j.get("id"): j for j in jobs}
        
        # Calculate totals
        today_date = datetime.now().date()
        week_start = today_date - timedelta(days=today_date.weekday())
        month_start = today_date.replace(day=1)
        
        week_hours = 0
        month_hours = 0
        total_hours = 0
        
        for e in entries:
            hours = float(e.get("hours", 0))
            total_hours += hours
            try:
                entry_date = datetime.strptime(e.get("date", ""), "%Y-%m-%d").date()
                if entry_date >= week_start:
                    week_hours += hours
                if entry_date >= month_start:
                    month_hours += hours
            except:
                pass
        
        hourly_rate = float(employee.get("hourly_rate", 0))
        
        # Build entries table
        rows = ""
        for e in entries[:500]:
            job_id = e.get("job_id")
            job = job_map.get(job_id, {}) if job_id else {}
            job_info = f'{job.get("job_number", "")} - {safe_string(job.get("title", ""))}' if job else "-"
            hours = float(e.get("hours", 0))
            
            rows += f'''
            <tr>
                <td>{e.get("date", "-")}</td>
                <td>{job_info}</td>
                <td>{safe_string(e.get("description", "-"))}</td>
                <td style="text-align:right;font-weight:bold;">{hours:.1f}h</td>
                <td style="text-align:right;">{money(hours * hourly_rate) if hourly_rate else "-"}</td>
                <td>
                    <button class="btn btn-secondary" style="padding:4px 8px;font-size:12px;" onclick="deleteEntry('{e.get("id")}')"></button>
                </td>
            </tr>
            '''
        
        # Get jobs for dropdown
        active_jobs = [j for j in jobs if j.get("status") != "completed"]
        job_options = "".join([f'<option value="{j.get("id")}">{j.get("job_number")} - {safe_string(j.get("title", ""))}</option>' for j in active_jobs])
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/timesheets" style="color:var(--text-muted);">-> Back to Timesheets</a>
            <button class="btn btn-secondary" onclick="window.print();"> Print</button>
        </div>
        
        <div class="card" style="margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;align-items:start;">
                <div>
                    <h2 style="margin:0;">{safe_string(employee.get("name", "-"))}</h2>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;">{safe_string(employee.get("position", "Employee"))}</p>
                    {f'<p style="color:var(--green);margin:5px 0 0 0;">Rate: {money(hourly_rate)}/hour</p>' if hourly_rate else ''}
                </div>
            </div>
            
            <div class="stats-grid" style="margin-top:20px;">
                <div class="stat-card">
                    <div class="stat-value">{week_hours:.1f}h</div>
                    <div class="stat-label">This Week</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{month_hours:.1f}h</div>
                    <div class="stat-label">This Month</div>
                </div>
                <div class="stat-card green">
                    <div class="stat-value">{money(month_hours * hourly_rate) if hourly_rate else f"{month_hours:.0f}h"}</div>
                    <div class="stat-label">Month Earnings</div>
                </div>
            </div>
        </div>
        
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin:0 0 15px 0;"> Log Time</h3>
            <div style="display:grid;grid-template-columns:1fr 1fr 2fr auto;gap:10px;align-items:end;">
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">Date</label>
                    <input type="date" id="logDate" class="form-input" value="{today()}">
                </div>
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">Hours</label>
                    <input type="number" id="logHours" class="form-input" value="8" min="0.5" max="24" step="0.5">
                </div>
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">Job / Description</label>
                    <select id="logJob" class="form-input">
                        <option value="">General work</option>
                        {job_options}
                    </select>
                </div>
                <button class="btn btn-primary" onclick="logTime()"> Add</button>
            </div>
        </div>
        
        <div class="card">
            <h3 style="margin:0 0 15px 0;"> Time Entries</h3>
            <table class="table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Job</th>
                        <th>Description</th>
                        <th style="text-align:right;">Hours</th>
                        <th style="text-align:right;">Value</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    {rows or "<tr><td colspan='6' style='text-align:center;color:var(--text-muted)'>No time entries yet</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <script>
        async function logTime() {{
            const date = document.getElementById('logDate').value;
            const hours = document.getElementById('logHours').value;
            const jobId = document.getElementById('logJob').value;
            
            const response = await fetch('/api/timesheet/log', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{
                    employee_id: '{employee_id}',
                    job_id: jobId || null,
                    hours: parseFloat(hours),
                    date: date
                }})
            }});
            
            const data = await response.json();
            if (data.success) {{
                location.reload();
            }} else {{
                alert('Error: ' + (data.error || 'Failed to log time'));
            }}
        }}
        
        async function deleteEntry(entryId) {{
            if (!confirm('Delete this time entry?')) return;
            
            const response = await fetch('/api/timesheet/delete/' + entryId, {{
                method: 'POST'
            }});
            
            const data = await response.json();
            if (data.success) {{
                location.reload();
            }}
        }}
        </script>
        '''
        
        return render_page(f"Timesheet - {employee.get('name', '')}", content, user, "timesheets")
    
    
    @app.route("/timesheets/report")
    @login_required
    def timesheets_report():
        """Timesheet report"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get date range from query params
        today_date = datetime.now().date()
        month_start = today_date.replace(day=1)
        
        start_date = request.args.get("start", month_start.strftime("%Y-%m-%d"))
        end_date = request.args.get("end", today_date.strftime("%Y-%m-%d"))
        
        # Get all entries in range
        entries = db.get("timesheet_entries", {"business_id": biz_id}) if biz_id else []
        filtered_entries = []
        for e in entries:
            try:
                entry_date = e.get("date", "")
                if start_date <= entry_date <= end_date:
                    filtered_entries.append(e)
            except:
                pass
        
        # Get employees and jobs
        employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
        emp_map = {e.get("id"): e for e in employees}
        
        jobs = db.get("jobs", {"business_id": biz_id}) if biz_id else []
        job_map = {j.get("id"): j for j in jobs}
        
        # Group by employee
        employee_summary = {}
        job_summary = {}
        
        for e in filtered_entries:
            emp_id = e.get("employee_id")
            job_id = e.get("job_id")
            hours = float(e.get("hours", 0))
            
            # Employee summary
            if emp_id not in employee_summary:
                emp = emp_map.get(emp_id, {})
                employee_summary[emp_id] = {
                    "name": emp.get("name", "Unknown"),
                    "rate": float(emp.get("hourly_rate", 0)),
                    "hours": 0
                }
            employee_summary[emp_id]["hours"] += hours
            
            # Job summary
            if job_id:
                if job_id not in job_summary:
                    job = job_map.get(job_id, {})
                    job_summary[job_id] = {
                        "number": job.get("job_number", "-"),
                        "title": job.get("title", "Unknown"),
                        "hours": 0
                    }
                job_summary[job_id]["hours"] += hours
        
        # Build tables
        emp_rows = ""
        total_hours = 0
        total_cost = 0
        for emp_id, data in sorted(employee_summary.items(), key=lambda x: x[1]["hours"], reverse=True):
            cost = data["hours"] * data["rate"]
            total_hours += data["hours"]
            total_cost += cost
            emp_rows += f'''
            <tr>
                <td><strong>{safe_string(data["name"])}</strong></td>
                <td style="text-align:right;">{data["hours"]:.1f}h</td>
                <td style="text-align:right;">{money(data["rate"])}/h</td>
                <td style="text-align:right;font-weight:bold;">{money(cost)}</td>
            </tr>
            '''
        
        job_rows = ""
        for job_id, data in sorted(job_summary.items(), key=lambda x: x[1]["hours"], reverse=True):
            job_rows += f'''
            <tr>
                <td><strong>{data["number"]}</strong></td>
                <td>{safe_string(data["title"])}</td>
                <td style="text-align:right;font-weight:bold;">{data["hours"]:.1f}h</td>
            </tr>
            '''
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/timesheets" style="color:var(--text-muted);">-> Back to Timesheets</a>
            <button class="btn btn-secondary" onclick="window.print();"> Print</button>
        </div>
        
        <div class="card" style="margin-bottom:20px;">
            <h2 style="margin:0 0 15px 0;"> Timesheet Report</h2>
            <form style="display:flex;gap:10px;align-items:end;">
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">From</label>
                    <input type="date" name="start" class="form-input" value="{start_date}">
                </div>
                <div>
                    <label style="display:block;margin-bottom:5px;font-size:13px;color:var(--text-muted);">To</label>
                    <input type="date" name="end" class="form-input" value="{end_date}">
                </div>
                <button type="submit" class="btn btn-primary"> Update</button>
            </form>
        </div>
        
        <div class="stats-grid" style="margin-bottom:20px;">
            <div class="stat-card">
                <div class="stat-value">{total_hours:.1f}h</div>
                <div class="stat-label">Total Hours</div>
            </div>
            <div class="stat-card green">
                <div class="stat-value">{money(total_cost)}</div>
                <div class="stat-label">Total Labour Cost</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(employee_summary)}</div>
                <div class="stat-label">Employees</div>
            </div>
        </div>
        
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin:0 0 15px 0;"> By Employee</h3>
            <table class="table">
                <thead>
                    <tr><th>Employee</th><th style="text-align:right;">Hours</th><th style="text-align:right;">Rate</th><th style="text-align:right;">Cost</th></tr>
                </thead>
                <tbody>
                    {emp_rows or "<tr><td colspan='4' style='text-align:center;color:var(--text-muted)'>No time entries</td></tr>"}
                </tbody>
                <tfoot style="font-weight:bold;background:rgba(255,255,255,0.05);">
                    <tr>
                        <td>TOTAL</td>
                        <td style="text-align:right;">{total_hours:.1f}h</td>
                        <td></td>
                        <td style="text-align:right;color:var(--primary);">{money(total_cost)}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
        
        <div class="card">
            <h3 style="margin:0 0 15px 0;"> By Job</h3>
            <table class="table">
                <thead>
                    <tr><th>Job #</th><th>Title</th><th style="text-align:right;">Hours</th></tr>
                </thead>
                <tbody>
                    {job_rows or "<tr><td colspan='3' style='text-align:center;color:var(--text-muted)'>No job time logged</td></tr>"}
                </tbody>
            </table>
        </div>
        '''
        
        return render_page("Timesheet Report", content, user, "timesheets")
    
    
    @app.route("/api/timesheet/log", methods=["POST"])
    @login_required
    def api_timesheet_log():
        """Log time entry"""
        
        try:
            data = request.get_json()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            employee_id = data.get("employee_id")
            job_id = data.get("job_id")
            hours = float(data.get("hours", 0))
            date = data.get("date", today())
            description = data.get("description", "")
            
            if not employee_id or hours <= 0:
                return jsonify({"success": False, "error": "Need employee and hours"})
            
            # Get employee name
            employee = db.get_one("employees", employee_id)
            emp_name = employee.get("name", "Unknown") if employee else "Unknown"
            
            # Get job info if provided
            job_info = ""
            if job_id:
                job = db.get_one("jobs", job_id)
                if job:
                    job_info = f"{job.get('job_number', '')} - {job.get('title', '')}"
                    description = description or job_info
            
            entry = {
                "id": generate_id(),
                "business_id": biz_id,
                "employee_id": employee_id,
                "employee_name": emp_name,
                "job_id": job_id,
                "date": date,
                "hours": hours,
                "description": description,
                "created_at": now()
            }
            
            db.save("timesheet_entries", entry)
            
            # Also add to job time_entries if job specified
            if job_id:
                job = db.get_one("jobs", job_id)
                if job:
                    try:
                        time_entries = json.loads(job.get("time_entries", "[]"))
                    except:
                        time_entries = []
                    
                    hourly_rate = float(employee.get("hourly_rate", 0)) if employee else 0
                    time_entries.append({
                        "date": date,
                        "employee": emp_name,
                        "hours": hours,
                        "rate": hourly_rate,
                        "total": hours * hourly_rate
                    })
                    
                    db.save("jobs", {"id": job_id, "time_entries": json.dumps(time_entries)})
            
            return jsonify({"success": True})
            
        except Exception as e:
            logger.error(f"[TIMESHEET] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/timesheet/delete/<entry_id>", methods=["POST"])
    @login_required
    def api_timesheet_delete(entry_id):
        """Delete time entry"""
        
        try:
            entry = db.get_one("timesheet_entries", entry_id)
            if entry:
                db.delete("timesheet_entries", entry_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    logger.info("[TIMESHEETS] All timesheet routes registered ✓")
