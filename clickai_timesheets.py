# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - TIMESHEETS MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Timesheets scan, template, review, process, discard, add,
#           Timesheet API (scan, save), Timesheets page, detail, report,
#           Timesheet log/delete APIs
# ==============================================================================

import json
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


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
        
        for i, emp in enumerate(employees_data):
            scanned_name = emp.get("name", "Unknown")
            total_hours = emp.get("total_hours", 0)
            total_overtime = emp.get("total_overtime", 0)
            total_sunday = emp.get("total_sunday", 0)
            days = emp.get("days", [])
            
            # Job card info from scan
            scanned_job_number = emp.get("job_number", "")
            scanned_job_id = emp.get("job_id", "")
            scanned_job_title = emp.get("job_title", "")
            
            logger.info(f"[TIMESHEET REVIEW] Scanned employee: '{scanned_name}' job: '{scanned_job_number}'")
            
            # Try to match to existing employee - fuzzy match
            matched_id = ""
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
                    logger.info(f"[TIMESHEET REVIEW] Matched '{scanned_name}' to '{db_emp.get('name')}'")
                    break
            
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
                        </tr>
                    </thead>
                    <tbody>
                '''
                calc_hours = 0
                calc_ot = 0
                calc_sunday = 0
                
                for day in days:
                    d_date = day.get("date", "-")
                    d_in = day.get("in", "-")
                    d_out = day.get("out", "-")
                    d_hours = day.get("hours", 0)
                    d_ot = day.get("overtime", 0)
                    d_sunday = day.get("sunday", 0)
                    is_sun = day.get("is_sunday", False)
                    
                    calc_hours += d_hours
                    calc_ot += d_ot
                    calc_sunday += d_sunday
                    
                    row_style = "background:rgba(59,130,246,0.15);" if is_sun else ""
                    
                    days_html += f'''
                    <tr style="{row_style}">
                        <td>{d_date} {"☀️" if is_sun else ""}</td>
                        <td>{d_in}</td>
                        <td>{d_out}</td>
                        <td>{d_hours if d_hours > 0 else "-"}</td>
                        <td style="color:#f59e0b;font-weight:bold;">{d_ot if d_ot > 0 else "-"}</td>
                        <td style="color:#3b82f6;font-weight:bold;">{d_sunday if d_sunday > 0 else "-"}</td>
                    </tr>
                    '''
                
                days_html += f'''
                    <tr style="background:rgba(34,197,94,0.15); font-weight:bold;">
                        <td colspan="3">🧮 CALCULATED BY FLASK</td>
                        <td>{calc_hours}</td>
                        <td style="color:#f59e0b;">{calc_ot}</td>
                        <td style="color:#3b82f6;">{calc_sunday}</td>
                    </tr>
                </tbody></table>
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
                        <label class="form-label">Normal ✏️</label>
                        <input type="number" name="hours_{i}" value="{total_hours}" class="form-input" style="width:80px;background:#1a1a2e;border:2px solid #22c55e;" step="0.5">
                    </div>
                    <div>
                        <label class="form-label" style="color:#f59e0b;">OT ✏️</label>
                        <input type="number" name="overtime_{i}" value="{total_overtime}" class="form-input" style="width:80px;background:#1a1a2e;border:2px solid #f59e0b;" step="0.5">
                    </div>
                    <div>
                        <label class="form-label" style="color:#3b82f6;">Sunday ✏️</label>
                        <input type="number" name="sunday_{i}" value="{total_sunday}" class="form-input" style="width:80px;background:#1a1a2e;border:2px solid #3b82f6;" step="0.5">
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
        
        content = f'''
        <div style="margin-bottom:20px;">
            <a href="/timesheets" style="color:var(--text-muted);">← Timesheets</a>
            <h1 style="margin-top:8px;">Review Scanned Timesheet {ai_badge}</h1>
            <p style="color:var(--text-muted);">Period: <strong>{period or "Not specified"}</strong> • {len(employees_data)} employees</p>
        </div>
        
        <div style="background:rgba(139,92,246,0.1); border:1px solid #8b5cf6; border-radius:8px; padding:12px 16px; margin-bottom:20px;">
            <strong>✏️ Edit Before Approving</strong><br>
            <span style="color:var(--text-muted);">Fix any wrong hours in the green boxes below. Match employee name from dropdown. Then approve.</span>
        </div>
        
        <form method="POST" action="/timesheets/process/{batch_id}">
            {cards_html}
            
            <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:20px;padding-bottom:30px;">
                <button type="submit" class="btn btn-primary" style="padding:14px 24px;flex:1;min-width:200px;">GOOD: Approve & Save</button>
                <a href="/timesheets" class="btn btn-secondary" style="padding:14px 20px;">← Back</a>
                <a href="/timesheets/discard/{batch_id}" class="btn" style="background:var(--red);color:white;padding:14px 20px;" onclick="return confirm('Discard this timesheet scan?')">🗑</a>
            </div>
            
            <input type="hidden" name="count" value="{len(employees_data)}">
        </form>
        '''
        
        return render_page("Review Timesheet", content, user, "timesheets")
    
    
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
        
        for i in range(count):
            emp_id = request.form.get(f"emp_{i}", "")
            job_id = request.form.get(f"job_{i}", "")
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
        
        # Mark batch as processed
        db.save("timesheet_batches", {"id": batch_id, "status": "processed"})
        
        logger.info(f"[TIMESHEET PROCESS] Done: saved {saved}, job_logged {job_logged}, errors: {len(errors)}")
        
        if errors:
            flash(f"Saved {saved} entries ({job_logged} linked to job cards). Errors: {', '.join(errors)}", "error")
        else:
            flash(f"Saved {saved} timesheet entries ({job_logged} linked to job cards)", "success")
        
        return redirect("/payroll")
    
    
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
            base64_data = base64.b64encode(file_data).decode('utf-8')
            
            filename = file.filename.lower()
            if filename.endswith('.png'):
                media_type = "image/png"
            elif filename.endswith('.gif'):
                media_type = "image/gif"
            else:
                media_type = "image/jpeg"
            
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
            {{"date": "Wed 8", "in": "07:00", "out": "16:00"}}
          ]
        }}
      ]
    }}
    
    IMPORTANT:
    - Only read what is written - DO NOT calculate hours
    - Read times in 24hr format (07:00, 16:00, etc)
    - If a time is unclear, make your best guess
    - If a day is blank or marked off, skip it
    - Look for job numbers written as JC-001, JC 001, Job 001, J001, etc - normalize to JC-XXXX-XXX format
    - If no job number is found for an employee, set job_number to null
    - DO NOT add any hours or overtime fields - just in/out times"""
    
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
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
            def parse_time(t):
                """Convert time string to minutes since midnight"""
                if not t or t == "-":
                    return None
                t = str(t).strip().replace(".", ":").replace(",", ":")
                try:
                    if ":" in t:
                        parts = t.split(":")
                        h = int(parts[0])
                        m = int(parts[1]) if len(parts) > 1 else 0
                    else:
                        h = int(t)
                        m = 0
                    return h * 60 + m
                except:
                    return None
            
            def is_sunday(date_str):
                """Check if day is Sunday"""
                date_lower = str(date_str).lower()
                return "sun" in date_lower or "son" in date_lower  # English or Afrikaans
            
            def calc_hours(time_in, time_out, lunch_break=30):
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
                
                # Overtime is anything over 8 hours
                normal = min(worked_hours, 8)
                overtime = max(0, worked_hours - 8)
                
                return round(normal, 1), round(overtime, 1)
            
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
                    
                    hours, ot = calc_hours(time_in, time_out)
                    
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
                        "hours": hours,
                        "overtime": ot,
                        "sunday": sunday_hours,
                        "is_sunday": is_sunday(d_date)
                    })
                
                processed_employees.append({
                    "name": emp_name,
                    "job_number": job_number,
                    "job_id": matched_job_id,
                    "job_title": matched_job_title,
                    "days": calculated_days,
                    "total_hours": round(total_hours, 1),
                    "total_overtime": round(total_overtime, 1),
                    "total_sunday": round(total_sunday, 1)
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
        
        # Get employees
        employees = db.get("employees", {"business_id": biz_id}) if biz_id else []
        
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
