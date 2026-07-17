"""
ClickAI Job Cards module (Fase 1)
─────────────────────────────────
A job card is a cost collector: labour + stock issued + bought-in costs,
closing to a customer invoice. The rule: nothing happens except on a job
card — every hour, every part and every supplier invoice attaches to a
job, and the invoice is generated from the card.

Accounting:
- Stock issue:  DR Cost of Sales, CR Stock (at cost), stock qty reduced.
- Labour:       costing/billing only — wages already run through payroll.
- Bought-in:    costing/billing only — the expense was booked at capture.
- Invoice:      DR Debtors, CR Sales + VAT Output (standard invoice GL).
"""

import json
import logging
from flask import request, jsonify, redirect

logger = logging.getLogger(__name__)


def register_jobcards_routes(app, db, login_required, Auth, render_page,
                             generate_id, money, safe_string, now, today,
                             gl, create_journal_entry, log_allocation,
                             next_document_number, RecordFactory):
    """Register all Job Card routes with the Flask app."""

    # ── helpers ──────────────────────────────────────────────────────

    def _biz():
        business = Auth.get_current_business()
        return business, (business.get("id") if business else None)

    def _emp_name(e):
        n = (e.get("name") or "").strip()
        if not n:
            n = f'{(e.get("first_name") or "").strip()} {(e.get("last_name") or "").strip()}'.strip()
        return n or "Employee"

    def _job_lines(biz_id, job_id):
        lines = db.get("job_card_lines", {"business_id": biz_id, "job_card_id": job_id}) or []
        return sorted(lines, key=lambda x: (x.get("date") or "", x.get("created_at") or ""))

    def _job_totals(lines):
        t = {"labour_charge": 0.0, "stock_cost": 0.0, "stock_charge": 0.0,
             "other_cost": 0.0, "other_charge": 0.0, "labour_cost": 0.0}
        for l in lines:
            lt = l.get("line_type")
            if lt == "labour":
                t["labour_charge"] += float(l.get("amount_charge") or 0)
                t["labour_cost"] += float(l.get("amount_cost") or 0)
            elif lt == "stock":
                t["stock_cost"] += float(l.get("amount_cost") or 0)
                t["stock_charge"] += float(l.get("amount_charge") or 0)
            else:
                t["other_cost"] += float(l.get("amount_cost") or 0)
                t["other_charge"] += float(l.get("amount_charge") or 0)
        t["total_cost"] = round(t["stock_cost"] + t["other_cost"] + t["labour_cost"], 2)
        t["total_charge"] = round(t["labour_charge"] + t["stock_charge"] + t["other_charge"], 2)
        return t

    # ── list ─────────────────────────────────────────────────────────

    @app.route("/jobcards")
    @login_required
    def jobcards_page():
        user = Auth.get_current_user()
        business, biz_id = _biz()

        jobs = db.get("job_cards", {"business_id": biz_id}) if biz_id else []
        jobs = sorted(jobs, key=lambda x: x.get("created_at", ""), reverse=True)

        reg_filter = (request.args.get("reg") or "").strip()
        if reg_filter:
            jobs = [j for j in jobs if (j.get("trailer_reg") or "").strip().lower() == reg_filter.lower()]

        open_jobs = [j for j in jobs if j.get("status") == "open"]
        invoiced_jobs = [j for j in jobs if j.get("status") == "invoiced"]

        # Charge totals per job (one query, grouped in Python)
        all_lines = db.get("job_card_lines", {"business_id": biz_id}) if biz_id else []
        charge_by_job = {}
        for l in (all_lines or []):
            jid = l.get("job_card_id")
            charge_by_job[jid] = charge_by_job.get(jid, 0.0) + float(l.get("amount_charge") or 0)

        rows = ""
        for j in jobs:
            status = j.get("status", "open")
            badge = ('<span style="background:var(--green);color:white;padding:2px 10px;border-radius:10px;font-size:11px;">INVOICED</span>'
                     if status == "invoiced" else
                     '<span style="background:var(--primary);color:white;padding:2px 10px;border-radius:10px;font-size:11px;">OPEN</span>')
            rows += f'''
            <tr onclick="window.location='/jobcard/{j.get("id")}'" style="cursor:pointer;">
                <td><strong>{safe_string(j.get("job_number", ""))}</strong></td>
                <td>{j.get("date", "")}</td>
                <td>{safe_string(j.get("customer_name", "") or "-")}</td>
                <td>{safe_string(j.get("trailer_reg", "") or "-")}</td>
                <td>{safe_string((j.get("description") or "")[:60])}</td>
                <td>{badge}</td>
                <td style="text-align:right;font-weight:600;">{money(charge_by_job.get(j.get("id"), 0))}</td>
            </tr>'''

        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <h2>Job Cards</h2>
            <a href="/jobcard/new" class="btn btn-primary">+ New Job Card</a>
        </div>
        {f'<div style="margin-bottom:15px;"><span style="background:var(--card);border:1px solid var(--border);padding:6px 12px;border-radius:6px;">Trailer: <strong>{safe_string(reg_filter)}</strong> <a href="/jobcards" style="margin-left:8px;">clear</a></span></div>' if reg_filter else ''}
        <div class="stats-grid" style="margin-bottom:20px;">
            <div class="stat-card orange"><div class="stat-value">{len(open_jobs)}</div><div class="stat-label">Open Job Cards</div></div>
            <div class="stat-card green"><div class="stat-value">{len(invoiced_jobs)}</div><div class="stat-label">Invoiced</div></div>
        </div>
        <div class="card">
            <table class="data-table">
                <thead><tr><th>Job No</th><th>Date</th><th>Customer</th><th>Trailer Reg</th><th>Description</th><th>Status</th><th style="text-align:right;">To Invoice (excl)</th></tr></thead>
                <tbody>{rows or '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:30px;">No job cards yet</td></tr>'}</tbody>
            </table>
        </div>'''
        return render_page("Job Cards", content, user, "jobs")

    # ── new ──────────────────────────────────────────────────────────

    @app.route("/jobcard/new", methods=["GET", "POST"])
    @login_required
    def jobcard_new():
        user = Auth.get_current_user()
        business, biz_id = _biz()

        if request.method == "POST":
            customer_id = request.form.get("customer_id", "")
            customer_name = ""
            if customer_id:
                _c = db.get_one("customers", customer_id)
                if _c:
                    customer_name = _c.get("name", "")
            existing = db.get("job_cards", {"business_id": biz_id}) or []
            job_number = next_document_number("JC", existing, "job_number")
            job = {
                "id": generate_id(),
                "business_id": biz_id,
                "job_number": job_number,
                "customer_id": customer_id or None,
                "customer_name": customer_name,
                "trailer_reg": request.form.get("trailer_reg", "").strip().upper(),
                "description": request.form.get("description", "").strip(),
                "markup_pct": float(request.form.get("markup_pct") or 0),
                "status": "open",
                "date": request.form.get("date") or today(),
                "notes": "",
                "created_by_name": user.get("name", "") if user else "",
                "created_at": now()
            }
            ok, err = db.save("job_cards", job)
            if ok:
                return redirect(f"/jobcard/{job['id']}")
            return redirect("/jobcard/new?error=Save+failed")

        customers = sorted(db.get("customers", {"business_id": biz_id}) or [],
                           key=lambda c: (c.get("name") or "").lower())
        cust_opts = '<option value="">— Select customer —</option>' + "".join(
            f'<option value="{c.get("id")}">{safe_string(c.get("name", ""))}</option>' for c in customers)

        content = f'''
        <h2 style="margin-bottom:20px;">New Job Card</h2>
        <div class="card" style="max-width:640px;">
            <form method="POST">
                <div style="margin-bottom:15px;">
                    <label style="display:block;margin-bottom:4px;font-weight:600;">Customer</label>
                    <select name="customer_id" required style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">{cust_opts}</select>
                </div>
                <div style="display:flex;gap:15px;margin-bottom:15px;">
                    <div style="flex:1;">
                        <label style="display:block;margin-bottom:4px;font-weight:600;">Trailer Registration (optional)</label>
                        <input type="text" name="trailer_reg" placeholder="e.g. ABC123GP" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);text-transform:uppercase;">
                    </div>
                    <div style="width:160px;">
                        <label style="display:block;margin-bottom:4px;font-weight:600;">Date</label>
                        <input type="date" name="date" value="{today()}" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    </div>
                </div>
                <div style="margin-bottom:15px;">
                    <label style="display:block;margin-bottom:4px;font-weight:600;">Job Description</label>
                    <input type="text" name="description" required placeholder="e.g. Brake overhaul and chassis repair" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                </div>
                <div style="margin-bottom:20px;width:220px;">
                    <label style="display:block;margin-bottom:4px;font-weight:600;">Markup % on bought-in costs</label>
                    <input type="number" name="markup_pct" value="0" min="0" max="100" step="0.5" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                    <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">Applied to supplier invoices linked to this job</div>
                </div>
                <div style="display:flex;gap:10px;">
                    <button type="submit" class="btn btn-primary" style="flex:1;">Create Job Card</button>
                    <a href="/jobcards" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>'''
        return render_page("New Job Card", content, user, "jobs")

    # ── view (the workbench) ─────────────────────────────────────────

    @app.route("/jobcard/<job_id>")
    @login_required
    def jobcard_view(job_id):
        user = Auth.get_current_user()
        business, biz_id = _biz()

        job = db.get_one("job_cards", job_id)
        if not job or job.get("business_id") != biz_id:
            return redirect("/jobcards")

        lines = _job_lines(biz_id, job_id)
        t = _job_totals(lines)
        is_open = job.get("status") == "open"

        employees = db.get("employees", {"business_id": biz_id}) or []
        employees = [e for e in employees if not (e.get("employment_end_date") or "").strip()]
        emp_opts = "".join(
            f'<option value="{e.get("id")}" data-rate="{float(e.get("charge_out_rate") or 0)}">{safe_string(_emp_name(e))}</option>'
            for e in sorted(employees, key=lambda x: _emp_name(x).lower()))

        def _line_rows(kind):
            rows = ""
            for l in lines:
                if l.get("line_type") != kind:
                    continue
                if kind == "labour":
                    detail = f'{safe_string(l.get("employee_name", ""))} — {float(l.get("hours") or 0):g} hrs @ {money(l.get("rate", 0))}'
                elif kind == "stock":
                    detail = f'{float(l.get("qty") or 0):g} x {money(l.get("cost_price", 0))} cost'
                else:
                    detail = f'cost {money(l.get("amount_cost", 0))}'
                del_btn = (f'<button onclick="delLine(\'{l.get("id")}\')" style="background:var(--red);color:white;border:none;border-radius:4px;padding:3px 9px;cursor:pointer;font-size:12px;">✕</button>'
                           if is_open else "")
                rows += f'''
                <tr>
                    <td style="font-size:12px;color:var(--text-muted);">{l.get("date", "")}</td>
                    <td>{safe_string(l.get("description", ""))}<div style="font-size:11px;color:var(--text-muted);">{detail}</div></td>
                    <td style="text-align:right;font-weight:600;">{money(l.get("amount_charge", 0))}</td>
                    <td style="width:40px;text-align:center;">{del_btn}</td>
                </tr>'''
            return rows or '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:14px;font-size:13px;">Nothing yet</td></tr>'

        status_badge = ('<span style="background:var(--green);color:white;padding:4px 14px;border-radius:12px;font-size:13px;">INVOICED</span>'
                        if not is_open else
                        '<span style="background:var(--primary);color:white;padding:4px 14px;border-radius:12px;font-size:13px;">OPEN</span>')
        inv_link = (f'<a href="/invoice/{job.get("invoice_id")}" class="btn btn-secondary" style="margin-left:10px;">View Invoice {safe_string(job.get("invoice_number", ""))}</a>'
                    if job.get("invoice_id") else "")
        reg_link = (f'<a href="/jobcards?reg={safe_string(job.get("trailer_reg"))}" style="font-size:12px;margin-left:8px;">history</a>'
                    if job.get("trailer_reg") else "")

        add_forms = ""
        if is_open:
            add_forms = f'''
            <div class="card" style="margin-bottom:20px;">
                <h3 style="margin:0 0 12px 0;font-size:15px;">Add Labour</h3>
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;">
                    <div><label style="font-size:12px;display:block;">Employee</label>
                        <select id="labEmp" onchange="document.getElementById('labRate').value=this.selectedOptions[0].dataset.rate||0" style="padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);min-width:180px;">{emp_opts}</select></div>
                    <div><label style="font-size:12px;display:block;">Date</label>
                        <input type="date" id="labDate" value="{today()}" style="padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <div><label style="font-size:12px;display:block;">Hours</label>
                        <input type="number" id="labHours" step="0.25" min="0.25" style="width:90px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <div><label style="font-size:12px;display:block;">Rate R/hr</label>
                        <input type="number" id="labRate" step="0.01" style="width:110px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <div style="flex:1;min-width:160px;"><label style="font-size:12px;display:block;">Work done</label>
                        <input type="text" id="labDesc" placeholder="e.g. Replace brake drums" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <button onclick="addLabour()" class="btn btn-primary" style="padding:9px 18px;">Add</button>
                </div>
            </div>
            <div class="card" style="margin-bottom:20px;">
                <h3 style="margin:0 0 12px 0;font-size:15px;">Issue Stock from Fulltech</h3>
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;">
                    <div style="flex:1;min-width:220px;position:relative;"><label style="font-size:12px;display:block;">Stock item</label>
                        <input type="text" id="stkSearch" placeholder="Type to search stock..." oninput="stkLookup(this.value)" autocomplete="off" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);">
                        <div id="stkDrop" style="display:none;position:absolute;top:100%;left:0;right:0;background:var(--card);border:1px solid var(--border);border-radius:6px;max-height:220px;overflow-y:auto;z-index:50;"></div>
                        <input type="hidden" id="stkId"></div>
                    <div><label style="font-size:12px;display:block;">Qty</label>
                        <input type="number" id="stkQty" value="1" step="any" min="0.01" style="width:90px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <div><label style="font-size:12px;display:block;">Sell price ea (excl)</label>
                        <input type="number" id="stkPrice" step="0.01" style="width:130px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <button onclick="addStock()" class="btn btn-primary" style="padding:9px 18px;">Issue</button>
                </div>
                <div style="font-size:12px;color:var(--text-muted);margin-top:6px;">Deducts stock and books DR Cost of Sales / CR Stock at cost price.</div>
            </div>
            <div class="card" style="margin-bottom:20px;">
                <h3 style="margin:0 0 12px 0;font-size:15px;">Other Cost (bought-in / sublet)</h3>
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;">
                    <div style="flex:1;min-width:200px;"><label style="font-size:12px;display:block;">Description</label>
                        <input type="text" id="othDesc" placeholder="e.g. Sandblasting - ABC Blasters" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <div><label style="font-size:12px;display:block;">Cost (excl VAT)</label>
                        <input type="number" id="othCost" step="0.01" style="width:130px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <div><label style="font-size:12px;display:block;">Charge (excl VAT)</label>
                        <input type="number" id="othCharge" step="0.01" style="width:130px;padding:8px;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--text);"></div>
                    <button onclick="addOther()" class="btn btn-primary" style="padding:9px 18px;">Add</button>
                </div>
                <div style="font-size:12px;color:var(--text-muted);margin-top:6px;">Supplier invoices captured on the supplier page with this job selected appear here automatically.</div>
            </div>'''

        actions = ""
        if is_open:
            actions = f'''
            <button onclick="genInvoice()" class="btn btn-primary" style="padding:12px 24px;font-size:15px;font-weight:700;" {"disabled" if not lines else ""}>Generate Invoice — {money(t["total_charge"])} + VAT</button>'''

        margin = round(t["total_charge"] - t["total_cost"], 2)
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:10px;">
            <h2 style="margin:0;">Job Card {safe_string(job.get("job_number", ""))} {status_badge}{inv_link}</h2>
            <a href="/jobcards" class="btn btn-secondary">Back</a>
        </div>
        <div style="color:var(--text-muted);margin-bottom:20px;">
            {safe_string(job.get("customer_name", "") or "-")}
            {(' | Trailer: <strong>' + safe_string(job.get("trailer_reg")) + '</strong>') if job.get("trailer_reg") else ''}{reg_link}
            | {job.get("date", "")} | {safe_string(job.get("description", ""))}
        </div>
        <div class="stats-grid" style="margin-bottom:20px;">
            <div class="stat-card"><div class="stat-value">{money(t["labour_charge"])}</div><div class="stat-label">Labour</div></div>
            <div class="stat-card"><div class="stat-value">{money(t["stock_charge"])}</div><div class="stat-label">Parts / Stock</div></div>
            <div class="stat-card"><div class="stat-value">{money(t["other_charge"])}</div><div class="stat-label">Bought-in</div></div>
            <div class="stat-card orange"><div class="stat-value">{money(t["total_charge"])}</div><div class="stat-label">To Invoice (excl VAT)</div></div>
            <div class="stat-card green"><div class="stat-value">{money(margin)}</div><div class="stat-label">Margin vs cost {money(t["total_cost"])}</div></div>
        </div>
        {add_forms}
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin:0 0 10px 0;font-size:15px;">Labour</h3>
            <table class="data-table"><tbody>{_line_rows("labour")}</tbody></table>
        </div>
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin:0 0 10px 0;font-size:15px;">Parts / Stock Issued</h3>
            <table class="data-table"><tbody>{_line_rows("stock")}</tbody></table>
        </div>
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin:0 0 10px 0;font-size:15px;">Bought-in Costs</h3>
            <table class="data-table"><tbody>{_line_rows("other")}</tbody></table>
        </div>
        <div style="margin-bottom:30px;">{actions}</div>
        <script>
        const JOB_ID = '{job_id}';
        async function _post(url, body) {{
            const r = await fetch(url, {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(body||{{}})}});
            const d = await r.json();
            if (d.success) {{ location.reload(); }} else {{ alert('Error: ' + (d.error || 'Failed')); }}
        }}
        function addLabour() {{
            const sel = document.getElementById('labEmp');
            _post('/api/jobcard/' + JOB_ID + '/labour', {{
                employee_id: sel.value,
                employee_name: sel.selectedOptions[0] ? sel.selectedOptions[0].textContent : '',
                date: document.getElementById('labDate').value,
                hours: parseFloat(document.getElementById('labHours').value) || 0,
                rate: parseFloat(document.getElementById('labRate').value) || 0,
                description: document.getElementById('labDesc').value
            }});
        }}
        let _stkTimer = null;
        function stkLookup(q) {{
            clearTimeout(_stkTimer);
            const drop = document.getElementById('stkDrop');
            if (!q || q.length < 2) {{ drop.style.display = 'none'; return; }}
            _stkTimer = setTimeout(() => {{
                fetch('/api/stock/lookup?q=' + encodeURIComponent(q)).then(r => r.json()).then(items => {{
                    drop.innerHTML = (items || []).slice(0, 12).map(s =>
                        '<div style="padding:8px 10px;cursor:pointer;border-bottom:1px solid var(--border);font-size:13px;" ' +
                        'onclick="pickStk(\\'' + s.id + '\\',' + (s.price || 0) + ', this.textContent)">' +
                        (s.label || s.name || '') + '</div>').join('');
                    drop.style.display = drop.innerHTML ? 'block' : 'none';
                }}).catch(() => {{ drop.style.display = 'none'; }});
            }}, 250);
        }}
        function pickStk(id, price, label) {{
            document.getElementById('stkId').value = id;
            document.getElementById('stkSearch').value = label;
            document.getElementById('stkPrice').value = (price || 0).toFixed ? (price).toFixed(2) : price;
            document.getElementById('stkDrop').style.display = 'none';
        }}
        function addStock() {{
            const sid = document.getElementById('stkId').value;
            if (!sid) {{ alert('Pick a stock item from the list first'); return; }}
            _post('/api/jobcard/' + JOB_ID + '/stock', {{
                stock_id: sid,
                qty: parseFloat(document.getElementById('stkQty').value) || 0,
                selling_price: parseFloat(document.getElementById('stkPrice').value) || 0
            }});
        }}
        function addOther() {{
            _post('/api/jobcard/' + JOB_ID + '/other', {{
                description: document.getElementById('othDesc').value,
                cost: parseFloat(document.getElementById('othCost').value) || 0,
                charge: parseFloat(document.getElementById('othCharge').value) || 0
            }});
        }}
        function delLine(lineId) {{
            if (!confirm('Remove this line? Stock lines are returned to stock and the GL entry reversed.')) return;
            _post('/api/jobcard/' + JOB_ID + '/line/' + lineId + '/delete');
        }}
        function genInvoice() {{
            if (!confirm('Generate the invoice for this job card? The card locks after invoicing.')) return;
            _post('/api/jobcard/' + JOB_ID + '/invoice');
        }}
        </script>'''
        return render_page(f"Job Card {job.get('job_number', '')}", content, user, "jobs")

    # ── line APIs ────────────────────────────────────────────────────

    def _open_job_or_error(job_id, biz_id):
        job = db.get_one("job_cards", job_id)
        if not job or job.get("business_id") != biz_id:
            return None, jsonify({"success": False, "error": "Job card not found"})
        if job.get("status") != "open":
            return None, jsonify({"success": False, "error": "Job card is invoiced and locked"})
        return job, None

    @app.route("/api/jobcard/<job_id>/labour", methods=["POST"])
    @login_required
    def api_jobcard_labour(job_id):
        user = Auth.get_current_user()
        business, biz_id = _biz()
        job, err = _open_job_or_error(job_id, biz_id)
        if err:
            return err
        data = request.get_json(silent=True) or {}
        hours = float(data.get("hours") or 0)
        rate = float(data.get("rate") or 0)
        if hours <= 0:
            return jsonify({"success": False, "error": "Hours must be greater than zero"})
        # Labour cost for margin = employee's payroll hourly rate when known
        cost_rate = 0.0
        emp_id = data.get("employee_id", "")
        if emp_id:
            try:
                _e = db.get_one("employees", emp_id)
                if _e:
                    cost_rate = float(_e.get("hourly_rate") or 0)
            except Exception:
                cost_rate = 0.0
        line = {
            "id": generate_id(), "business_id": biz_id, "job_card_id": job_id,
            "line_type": "labour", "date": (data.get("date") or today())[:10],
            "description": (data.get("description") or "Labour").strip(),
            "employee_id": emp_id or None, "employee_name": data.get("employee_name", ""),
            "hours": hours, "rate": rate,
            "amount_cost": round(hours * cost_rate, 2),
            "amount_charge": round(hours * rate, 2),
            "source": "manual",
            "created_by_name": user.get("name", "") if user else "", "created_at": now()
        }
        ok, e = db.save("job_card_lines", line)
        return jsonify({"success": bool(ok), "error": e if not ok else ""})

    @app.route("/api/jobcard/<job_id>/stock", methods=["POST"])
    @login_required
    def api_jobcard_stock(job_id):
        user = Auth.get_current_user()
        business, biz_id = _biz()
        job, err = _open_job_or_error(job_id, biz_id)
        if err:
            return err
        data = request.get_json(silent=True) or {}
        stock_id = data.get("stock_id", "")
        qty = float(data.get("qty") or 0)
        selling = float(data.get("selling_price") or 0)
        if not stock_id or qty <= 0:
            return jsonify({"success": False, "error": "Stock item and quantity required"})
        st = db.get_one_stock(stock_id)
        if not st:
            return jsonify({"success": False, "error": "Stock item not found"})
        cost = float(st.get("cost_price") or st.get("cost") or 0)
        desc = f'{st.get("code", "") or st.get("stock_code", "")} {st.get("name", "") or st.get("description", "")}'.strip()
        line = {
            "id": generate_id(), "business_id": biz_id, "job_card_id": job_id,
            "line_type": "stock", "date": today(),
            "description": desc or "Stock item",
            "stock_id": stock_id, "stock_code": st.get("code", "") or st.get("stock_code", ""),
            "qty": qty, "cost_price": cost,
            "amount_cost": round(qty * cost, 2),
            "amount_charge": round(qty * selling, 2),
            "rate": selling,
            "source": "manual",
            "created_by_name": user.get("name", "") if user else "", "created_at": now()
        }
        ok, e = db.save("job_card_lines", line)
        if not ok:
            return jsonify({"success": False, "error": e or "Save failed"})
        # Deduct stock (same pattern as invoicing)
        try:
            current_qty = float(st.get("qty") or st.get("quantity") or 0)
            new_qty = current_qty - qty
            db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
        except Exception as _se:
            logger.error(f"[JOBCARD] Stock deduction failed: {_se}")
        # GL: DR Cost of Sales, CR Stock at cost
        try:
            cost_total = round(qty * cost, 2)
            if cost_total > 0:
                create_journal_entry(biz_id, today(),
                                     f"Job {job.get('job_number')} stock issue - {desc}",
                                     f"JC-{job.get('job_number', '')}", [
                    {"account_code": gl(biz_id, "cogs"), "debit": cost_total, "credit": 0},
                    {"account_code": gl(biz_id, "stock"), "debit": 0, "credit": cost_total},
                ])
        except Exception as _ge:
            logger.error(f"[JOBCARD] Stock issue GL failed: {_ge}")
        return jsonify({"success": True})

    @app.route("/api/jobcard/<job_id>/other", methods=["POST"])
    @login_required
    def api_jobcard_other(job_id):
        user = Auth.get_current_user()
        business, biz_id = _biz()
        job, err = _open_job_or_error(job_id, biz_id)
        if err:
            return err
        data = request.get_json(silent=True) or {}
        desc = (data.get("description") or "").strip()
        cost = float(data.get("cost") or 0)
        charge = float(data.get("charge") or 0)
        if not desc or charge <= 0:
            return jsonify({"success": False, "error": "Description and charge amount required"})
        line = {
            "id": generate_id(), "business_id": biz_id, "job_card_id": job_id,
            "line_type": "other", "date": today(), "description": desc,
            "amount_cost": round(cost, 2), "amount_charge": round(charge, 2),
            "source": "manual",
            "created_by_name": user.get("name", "") if user else "", "created_at": now()
        }
        ok, e = db.save("job_card_lines", line)
        return jsonify({"success": bool(ok), "error": e if not ok else ""})

    @app.route("/api/jobcard/<job_id>/line/<line_id>/delete", methods=["POST"])
    @login_required
    def api_jobcard_line_delete(job_id, line_id):
        business, biz_id = _biz()
        job, err = _open_job_or_error(job_id, biz_id)
        if err:
            return err
        line = db.get_one("job_card_lines", line_id)
        if not line or line.get("job_card_id") != job_id:
            return jsonify({"success": False, "error": "Line not found"})
        # Stock lines: return to stock and reverse the GL entry
        if line.get("line_type") == "stock" and line.get("stock_id"):
            try:
                st = db.get_one_stock(line.get("stock_id"))
                if st:
                    current_qty = float(st.get("qty") or st.get("quantity") or 0)
                    new_qty = current_qty + float(line.get("qty") or 0)
                    db.update_stock(line.get("stock_id"), {"qty": new_qty, "quantity": new_qty}, biz_id)
            except Exception as _se:
                logger.error(f"[JOBCARD] Restock failed: {_se}")
            try:
                cost_total = round(float(line.get("amount_cost") or 0), 2)
                if cost_total > 0:
                    create_journal_entry(biz_id, today(),
                                         f"Job {job.get('job_number')} stock issue REVERSED - {line.get('description', '')}",
                                         f"JC-{job.get('job_number', '')}", [
                        {"account_code": gl(biz_id, "stock"), "debit": cost_total, "credit": 0},
                        {"account_code": gl(biz_id, "cogs"), "debit": 0, "credit": cost_total},
                    ])
            except Exception as _ge:
                logger.error(f"[JOBCARD] Reversal GL failed: {_ge}")
        ok = db.delete("job_card_lines", line_id)
        return jsonify({"success": bool(ok)})

    # ── generate invoice ─────────────────────────────────────────────

    @app.route("/api/jobcard/<job_id>/invoice", methods=["POST"])
    @login_required
    def api_jobcard_invoice(job_id):
        user = Auth.get_current_user()
        business, biz_id = _biz()
        job, err = _open_job_or_error(job_id, biz_id)
        if err:
            return err
        if not job.get("customer_id"):
            return jsonify({"success": False, "error": "Job card has no customer"})
        lines = _job_lines(biz_id, job_id)
        if not lines:
            return jsonify({"success": False, "error": "Job card has no lines"})

        items = []
        subtotal = 0.0
        for l in lines:
            charge = round(float(l.get("amount_charge") or 0), 2)
            if charge <= 0:
                continue
            if l.get("line_type") == "labour":
                items.append({"description": f'Labour: {l.get("description", "")} ({l.get("employee_name", "")})',
                              "unit": "hour", "quantity": float(l.get("hours") or 0),
                              "price": float(l.get("rate") or 0), "total": charge})
            elif l.get("line_type") == "stock":
                items.append({"description": l.get("description", ""), "unit": "ea",
                              "quantity": float(l.get("qty") or 0),
                              "price": float(l.get("rate") or 0), "total": charge})
            else:
                items.append({"description": l.get("description", ""), "unit": "ea",
                              "quantity": 1.0, "price": charge, "total": charge})
            subtotal += charge
        if not items:
            return jsonify({"success": False, "error": "No billable lines on this job card"})

        # Decimal maths + INV- prefix: identical to /invoice/new so rounding
        # and numbering can never drift from normal invoices
        from decimal import Decimal
        subtotal_d = Decimal("0")
        for _it in items:
            subtotal_d += Decimal(str(_it["total"]))
        vat_d = (subtotal_d * Decimal("0.15")).quantize(Decimal("0.01"))
        total_d = subtotal_d + vat_d
        subtotal = float(subtotal_d)
        vat = float(vat_d)
        total = float(total_d)

        existing = db.get("invoices", {"business_id": biz_id}) or []
        inv_num = next_document_number("INV-", existing, "invoice_number")
        inv_date = today()
        _reg = f' — Trailer {job.get("trailer_reg")}' if job.get("trailer_reg") else ""
        invoice = RecordFactory.invoice(
            business_id=biz_id,
            customer_id=job.get("customer_id"),
            customer_name=job.get("customer_name", ""),
            items=items,
            invoice_number=inv_num,
            date=inv_date,
            subtotal=subtotal, vat=vat, total=total,
            payment_method="account",
            status="unpaid",
            notes=f'Job Card {job.get("job_number", "")}{_reg}'
        )
        invoice_id = invoice["id"]
        ok, e = db.save("invoices", invoice)
        if not ok:
            return jsonify({"success": False, "error": f"Invoice save failed: {e}"})

        # GL: DR Debtors, CR Sales + VAT Output (standard invoice journal).
        # NO stock deduction here — stock was issued (and costed) on the card.
        try:
            create_journal_entry(biz_id, inv_date,
                                 f"Invoice {inv_num} - {job.get('customer_name', '')} (Job {job.get('job_number', '')})",
                                 inv_num, [
                {"account_code": gl(biz_id, "debtors"), "debit": total, "credit": 0},
                {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": subtotal},
                {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": vat},
            ])
        except Exception as _ge:
            logger.error(f"[JOBCARD] Invoice GL failed (invoice saved): {_ge}")

        try:
            if log_allocation:
                log_allocation(
                    business_id=biz_id, allocation_type="invoice", source_table="invoices", source_id=invoice_id,
                    description=f"Invoice {inv_num} - {job.get('customer_name', '')} (Job {job.get('job_number', '')})",
                    amount=total,
                    gl_entries=[
                        {"account_code": gl(biz_id, "debtors"), "debit": total, "credit": 0},
                        {"account_code": gl(biz_id, "sales"), "debit": 0, "credit": subtotal},
                        {"account_code": gl(biz_id, "vat_output"), "debit": 0, "credit": vat},
                    ],
                    customer_name=job.get("customer_name", ""), payment_method="account",
                    reference=inv_num, transaction_date=inv_date,
                    created_by=user.get("id", "") if user else "",
                    created_by_name=user.get("name", "") if user else ""
                )
        except Exception:
            pass

        db.update("job_cards", job_id, {"status": "invoiced",
                                        "invoice_id": invoice_id,
                                        "invoice_number": inv_num})
        print(f"[JOBCARD] {job.get('job_number')} invoiced as {inv_num} R{total:,.2f}", flush=True)
        return jsonify({"success": True, "invoice_id": invoice_id, "invoice_number": inv_num})

    logger.info("[JOBCARDS] Routes registered: /jobcards, /jobcard/new, /jobcard/<id> + APIs")
