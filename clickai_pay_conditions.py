# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - PAY CONDITIONS MODULE
# ==============================================================================
# Per-employee work agreement: weekday schedules, rate, overtime, premium days.
# Everything resolves to an HOURLY RATE. The payslip basic = rate x agreed
# hours for the month; deviations (late / early / OT / premium days) are added
# or subtracted as visible lines.
#
# This module is self-contained. It exposes:
#   - calculate_pay_from_timesheet(emp, entries, period) -> pure calculation
#   - register_pay_conditions_routes(app, ...)           -> employee edit page
#
# Wired into clickai.py with a try/except import, like the other modules.
# ==============================================================================

import json
import logging
import calendar as _calendar
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Standard SA monthly hour factor — 45h/week x 52 / 12. Used only as a
# fallback when deriving an hourly rate from a monthly amount and the
# employee has no schedule set.
DEFAULT_MONTHLY_HOURS = 203.67

# Default schedule used when an employee has not been set up yet.
# Mon-Thu 07:00-16:00, Fri 07:00-14:00, no Saturday.
DEFAULT_SCHEDULE = {
    "mon_thu_in": "07:00", "mon_thu_out": "16:00",
    "fri_in": "07:00", "fri_out": "14:00",
    "sat_in": "", "sat_out": "",
    "lunch_minutes": 0, "lunch_deducted": False,
}


# ------------------------------------------------------------------ helpers --

def _to_minutes(t):
    """'07:30' or '7H30' or '07h00' -> minutes since midnight. None on failure."""
    if not t:
        return None
    s = str(t).strip().upper().replace("H", ":").replace(".", ":")
    if ":" not in s:
        # bare hour like '7'
        try:
            return int(float(s)) * 60
        except Exception:
            return None
    parts = s.split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
        return h * 60 + m
    except Exception:
        return None


def _round15(minutes):
    """Round a minute count to the nearest 15."""
    return int(round(minutes / 15.0)) * 15


def _safe_float(v, default=0.0):
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("R", "").replace("%", "").strip()
    if not s or s.lower() in ("off", "on", "true", "false", "null", "none", "-"):
        return default
    try:
        return float(s)
    except Exception:
        return default


def get_conditions(emp):
    """Read the pay-conditions block off an employee record.
    Returns a dict with safe defaults so callers never KeyError."""
    raw = emp.get("pay_conditions")
    cond = {}
    if raw:
        try:
            cond = json.loads(raw) if isinstance(raw, str) else dict(raw)
        except Exception:
            cond = {}
    sched = dict(DEFAULT_SCHEDULE)
    sched.update(cond.get("schedule", {}) or {})
    return {
        "is_setup": bool(cond.get("is_setup", False)),
        "rate_method": cond.get("rate_method", "monthly"),   # 'monthly' | 'hourly'
        "schedule": sched,
        "ot_paid": bool(cond.get("ot_paid", False)),
        "ot_multiplier": _safe_float(cond.get("ot_multiplier", 1.5), 1.5),
        "sat_outside_multiplier": _safe_float(cond.get("sat_outside_multiplier", 1.5), 1.5),
        "sunday_multiplier": _safe_float(cond.get("sunday_multiplier", 2.0), 2.0),
        "public_holiday_paid": bool(cond.get("public_holiday_paid", True)),
    }


def _day_schedule(cond, weekday):
    """weekday: 0=Mon ... 6=Sun. Returns (in_min, out_min) or (None, None)
    if the employee has no agreed hours that day."""
    s = cond["schedule"]
    if weekday <= 3:          # Mon-Thu
        return _to_minutes(s.get("mon_thu_in")), _to_minutes(s.get("mon_thu_out"))
    if weekday == 4:          # Fri
        return _to_minutes(s.get("fri_in")), _to_minutes(s.get("fri_out"))
    if weekday == 5:          # Sat
        return _to_minutes(s.get("sat_in")), _to_minutes(s.get("sat_out"))
    return None, None         # Sun


def derive_hourly_rate(emp, cond, period_workdays_hours):
    """Resolve the employee's hourly rate.
    'hourly'  -> use hourly_rate directly.
    'monthly' -> basic_salary / agreed hours for this month
                 (falls back to DEFAULT_MONTHLY_HOURS if no schedule)."""
    if cond["rate_method"] == "hourly":
        return _safe_float(emp.get("hourly_rate", 0))
    monthly = _safe_float(emp.get("basic_salary", 0))
    if monthly <= 0:
        return _safe_float(emp.get("hourly_rate", 0))
    divisor = period_workdays_hours if period_workdays_hours and period_workdays_hours > 0 else DEFAULT_MONTHLY_HOURS
    return monthly / divisor


# --------------------------------------------------------------- the engine --

def calculate_pay_from_timesheet(emp, entries, period, public_holidays=None):
    """Pure calculation. No Flask, no DB.

    emp     : employee record (dict)
    entries : list of timesheet entries, each with 'date' (YYYY-MM-DD) and
              ideally 'in'/'out' clock times; falls back to 'hours'/'overtime'.
    period  : 'YYYY-MM' for the pay month.
    public_holidays : optional set/list of 'YYYY-MM-DD' strings.

    Returns a dict:
      {
        is_setup, hourly_rate, agreed_hours, base_pay,
        lines: [ {date, day, label, hours, amount, kind} ... ],
        gross  # base_pay + sum(line amounts, signed)
      }
    'kind' is one of: base, ot, late, early, premium, holiday.
    """
    public_holidays = set(public_holidays or [])
    cond = get_conditions(emp)

    # ---- agreed hours for every working day in the period --------------
    try:
        yr, mo = int(period[:4]), int(period[5:7])
    except Exception:
        now = datetime.now()
        yr, mo = now.year, now.month
    days_in_month = _calendar.monthrange(yr, mo)[1]

    agreed_per_date = {}      # 'YYYY-MM-DD' -> agreed hours that day
    total_agreed = 0.0
    for d in range(1, days_in_month + 1):
        dt = datetime(yr, mo, d)
        wd = dt.weekday()
        in_m, out_m = _day_schedule(cond, wd)
        if in_m is None or out_m is None:
            continue
        worked = out_m - in_m
        if cond["schedule"].get("lunch_deducted"):
            worked -= int(_safe_float(cond["schedule"].get("lunch_minutes", 0)))
        if worked <= 0:
            continue
        hrs = worked / 60.0
        agreed_per_date[dt.strftime("%Y-%m-%d")] = hrs
        total_agreed += hrs

    # ---- fallback: employee not set up -> old behaviour ----------------
    if not cond["is_setup"]:
        basic = _safe_float(emp.get("basic_salary", 0))
        return {
            "is_setup": False,
            "hourly_rate": 0.0,
            "agreed_hours": 0.0,
            "base_pay": round(basic, 2),
            "lines": [],
            "gross": round(basic, 2),
        }

    rate = derive_hourly_rate(emp, cond, total_agreed)
    base_pay = rate * total_agreed

    lines = []

    # ---- walk each timesheet entry -------------------------------------
    for e in entries:
        date_str = str(e.get("date", "")).strip()
        if not date_str or not date_str.startswith(period):
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            continue
        wd = dt.weekday()
        day_name = dt.strftime("%A")
        in_m = _to_minutes(e.get("in"))
        out_m = _to_minutes(e.get("out"))
        sched_in, sched_out = _day_schedule(cond, wd)
        is_holiday = date_str in public_holidays

        # --- Sunday, or a worked Saturday with no Saturday agreement ----
        # -> entire worked time is premium, not part of base.
        outside_day = (wd == 6) or (wd == 5 and sched_in is None)
        if outside_day and in_m is not None and out_m is not None and out_m > in_m:
            worked_min = _round15(out_m - in_m)
            mult = cond["sunday_multiplier"] if wd == 6 else cond["sat_outside_multiplier"]
            hrs = worked_min / 60.0
            lines.append({
                "date": date_str, "day": day_name,
                "label": f"{day_name} worked @ {mult}x",
                "hours": round(hrs, 2),
                "amount": round(hrs * rate * mult, 2),
                "kind": "premium",
            })
            continue

        # --- public holiday ---------------------------------------------
        if is_holiday and sched_in is not None and not cond["public_holiday_paid"]:
            # not paid for the holiday: subtract that day's agreed hours
            agreed = agreed_per_date.get(date_str, 0.0)
            if agreed > 0:
                lines.append({
                    "date": date_str, "day": day_name,
                    "label": "Public holiday — not paid",
                    "hours": round(agreed, 2),
                    "amount": -round(agreed * rate, 2),
                    "kind": "holiday",
                })
            continue

        # --- normal working day: compare clock times -------------------
        if sched_in is None or sched_out is None:
            continue   # no agreement this weekday and not flagged outside
        if in_m is None or out_m is None:
            continue   # no clock times scanned — leave base as-is

        # late arrival
        if in_m > sched_in:
            late = _round15(in_m - sched_in)
            if late > 0:
                hrs = late / 60.0
                lines.append({
                    "date": date_str, "day": day_name,
                    "label": f"{late} min late",
                    "hours": round(hrs, 2),
                    "amount": -round(hrs * rate, 2),
                    "kind": "late",
                })

        # left early
        if out_m < sched_out:
            early = _round15(sched_out - out_m)
            if early > 0:
                hrs = early / 60.0
                lines.append({
                    "date": date_str, "day": day_name,
                    "label": f"{early} min early",
                    "hours": round(hrs, 2),
                    "amount": -round(hrs * rate, 2),
                    "kind": "early",
                })

        # overtime — worked past agreed out-time
        if out_m > sched_out and cond["ot_paid"]:
            ot = _round15(out_m - sched_out)
            if ot > 0:
                hrs = ot / 60.0
                mult = cond["ot_multiplier"]
                lines.append({
                    "date": date_str, "day": day_name,
                    "label": f"{ot} min OT @ {mult}x",
                    "hours": round(hrs, 2),
                    "amount": round(hrs * rate * mult, 2),
                    "kind": "ot",
                })

    gross = base_pay + sum(l["amount"] for l in lines)
    return {
        "is_setup": True,
        "hourly_rate": round(rate, 4),
        "agreed_hours": round(total_agreed, 2),
        "base_pay": round(base_pay, 2),
        "lines": lines,
        "gross": round(gross, 2),
    }


# ----------------------------------------------------------- routes / page --

def register_pay_conditions_routes(app, db, login_required, Auth, render_page,
                                   safe_string, today):
    """Register the employee Pay Conditions edit page."""

    from flask import request, redirect, flash

    @app.route("/employee/<emp_id>/pay-conditions", methods=["GET", "POST"])
    @login_required
    def employee_pay_conditions(emp_id):
        user = Auth.get_current_user()
        emp = db.get_one("employees", emp_id)
        if not emp:
            flash("Employee not found", "error")
            return redirect("/payroll")

        if request.method == "POST":
            f = request.form
            conditions = {
                "is_setup": True,
                "rate_method": f.get("rate_method", "monthly"),
                "schedule": {
                    "mon_thu_in": f.get("mon_thu_in", "").strip(),
                    "mon_thu_out": f.get("mon_thu_out", "").strip(),
                    "fri_in": f.get("fri_in", "").strip(),
                    "fri_out": f.get("fri_out", "").strip(),
                    "sat_in": f.get("sat_in", "").strip(),
                    "sat_out": f.get("sat_out", "").strip(),
                    "lunch_minutes": _safe_float(f.get("lunch_minutes", 0)),
                    "lunch_deducted": f.get("lunch_deducted") == "on",
                },
                "ot_paid": f.get("ot_paid") == "on",
                "ot_multiplier": _safe_float(f.get("ot_multiplier", 1.5), 1.5),
                "sat_outside_multiplier": _safe_float(f.get("sat_outside_multiplier", 1.5), 1.5),
                "sunday_multiplier": _safe_float(f.get("sunday_multiplier", 2.0), 2.0),
                "public_holiday_paid": f.get("public_holiday_paid") == "on",
            }
            try:
                db.update("employees", emp_id, {"pay_conditions": json.dumps(conditions)})
                flash(f"Pay conditions saved for {emp.get('name')}", "success")
            except Exception as e:
                logger.error(f"[PAY-COND] Save failed: {e}")
                flash("Could not save pay conditions — check the logs", "error")
            return redirect(f"/employee/{emp_id}")

        cond = get_conditions(emp)
        s = cond["schedule"]

        def _chk(v):
            return "checked" if v else ""

        def _sel(method):
            return "selected" if cond["rate_method"] == method else ""

        content = f'''
        <div class="card">
            <h2 style="margin-bottom:5px;">Pay Conditions</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">{safe_string(emp.get("name", "-"))} — the work agreement that determines pay</p>
            <form method="POST">

                <h3 style="margin:15px 0 10px;">How is the rate set?</h3>
                <select name="rate_method" style="padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);width:100%;max-width:360px;">
                    <option value="monthly" {_sel("monthly")}>Monthly amount (rate derived from hours)</option>
                    <option value="hourly" {_sel("hourly")}>Hourly rate (entered directly)</option>
                </select>
                <p style="color:var(--text-muted);font-size:12px;margin-top:6px;">Monthly uses Basic Salary; hourly uses Rate per Hour — both on the employee Edit page.</p>

                <h3 style="margin:20px 0 10px;">Work schedule</h3>
                <table style="width:100%;max-width:480px;">
                    <tr><td style="padding:6px 0;">Mon–Thu</td>
                        <td><input type="time" name="mon_thu_in" value="{s.get('mon_thu_in','')}" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td>
                        <td><input type="time" name="mon_thu_out" value="{s.get('mon_thu_out','')}" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td></tr>
                    <tr><td style="padding:6px 0;">Friday</td>
                        <td><input type="time" name="fri_in" value="{s.get('fri_in','')}" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td>
                        <td><input type="time" name="fri_out" value="{s.get('fri_out','')}" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td></tr>
                    <tr><td style="padding:6px 0;">Saturday</td>
                        <td><input type="time" name="sat_in" value="{s.get('sat_in','')}" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td>
                        <td><input type="time" name="sat_out" value="{s.get('sat_out','')}" style="padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></td></tr>
                </table>
                <p style="color:var(--text-muted);font-size:12px;margin-top:6px;">Leave Saturday blank if the employee has no Saturday agreement. A worked Saturday with no agreement is paid at the Saturday premium below.</p>

                <div style="margin-top:12px;">
                    <label>Lunch minutes
                        <input type="number" name="lunch_minutes" value="{int(s.get('lunch_minutes',0) or 0)}" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </label>
                    <label style="margin-left:15px;">
                        <input type="checkbox" name="lunch_deducted" {_chk(s.get('lunch_deducted'))}> Deduct lunch from hours
                    </label>
                </div>

                <h3 style="margin:20px 0 10px;">Overtime &amp; premium days</h3>
                <label style="display:block;margin-bottom:8px;">
                    <input type="checkbox" name="ot_paid" {_chk(cond['ot_paid'])}> Pay overtime when worked past the out-time
                </label>
                <div style="display:flex;gap:20px;flex-wrap:wrap;">
                    <label>OT multiplier
                        <input type="number" step="0.1" name="ot_multiplier" value="{cond['ot_multiplier']}" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </label>
                    <label>Saturday (outside agreement)
                        <input type="number" step="0.1" name="sat_outside_multiplier" value="{cond['sat_outside_multiplier']}" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </label>
                    <label>Sunday
                        <input type="number" step="0.1" name="sunday_multiplier" value="{cond['sunday_multiplier']}" style="width:80px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </label>
                </div>
                <label style="display:block;margin-top:12px;">
                    <input type="checkbox" name="public_holiday_paid" {_chk(cond['public_holiday_paid'])}> Paid for public holidays
                </label>

                <div style="display:flex;gap:10px;margin-top:25px;">
                    <button type="submit" class="btn btn-primary" style="padding:12px 24px;">Save Pay Conditions</button>
                    <a href="/employee/{emp_id}" class="btn btn-secondary" style="padding:12px 20px;">Cancel</a>
                </div>
            </form>
        </div>
        '''
        return render_page("Pay Conditions", content, user, "payroll")

    logger.info("[PAY-COND] Pay conditions routes registered")
