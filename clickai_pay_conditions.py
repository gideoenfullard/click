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
import re
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


def _weekday_of(date_str):
    """Weekday (0=Mon .. 6=Sun) from a scanned day cell. Handles a full date
    like '2026-06-08' / '2026/06/08' or a day-name label like 'Mon 8'.
    Returns None when the weekday cannot be determined."""
    s = str(date_str or "").strip()
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).weekday()
        except Exception:
            return None
    sl = s.lower()
    # English and Afrikaans day-name prefixes
    for prefix, wd in (("mon", 0), ("tue", 1), ("wed", 2), ("thu", 3),
                       ("fri", 4), ("sat", 5), ("sun", 6),
                       ("maa", 0), ("din", 1), ("woe", 2), ("don", 3),
                       ("vry", 4), ("son", 6)):
        if sl.startswith(prefix):
            return wd
    return None


# Words written in the In/Out columns that are NOT clock times. The scanner
# passes these through verbatim so the reviewer can see/fix them.
_ABSENT_WORDS = ("absent", "afwesig", "off", "no show", "no-show", "awol", "x")
_SICK_WORDS = ("sick", "siek")
_HOLIDAY_WORDS = ("holiday", "vakansie", "public hol", "pubhol")


def _cell_marker(raw):
    """Classify a single In/Out cell.
    Returns 'time' if it is a clock time, else one of 'holiday', 'sick',
    'absent', 'blank' for the various non-time markers."""
    if raw is None:
        return "blank"
    s = str(raw).strip().lower()
    if s in ("", "-"):
        return "blank"
    if _to_minutes(raw) is not None:
        return "time"
    if any(w in s for w in _HOLIDAY_WORDS):
        return "holiday"
    if any(w in s for w in _SICK_WORDS):
        return "sick"
    if any(w in s for w in _ABSENT_WORDS):
        return "absent"
    # Unknown text (e.g. 'LATE' written in the Out column) — not a time.
    return "blank"


def _day_status(in_raw, out_raw):
    """Decide what a scanned day represents from its In/Out cells.
    Returns (status, in_min, out_min) where status is one of:
      'holiday'  — public holiday marker -> paid, no deduction
      'sick'     — sick marker -> unpaid by default (no note no pay)
      'absent'   — absent / blank both -> unpaid, deduct agreed hours
      'partial'  — has a valid In but no valid Out -> worked to schedule end
      'present'  — both In and Out are valid clock times
    """
    in_mark = _cell_marker(in_raw)
    out_mark = _cell_marker(out_raw)
    in_min = _to_minutes(in_raw)
    out_min = _to_minutes(out_raw)

    if in_mark == "holiday" or out_mark == "holiday":
        return "holiday", in_min, out_min
    if in_mark == "sick" or out_mark == "sick":
        return "sick", in_min, out_min
    if in_mark == "time" and out_mark == "time":
        return "present", in_min, out_min
    if in_mark == "time" and out_mark != "time":
        return "partial", in_min, None
    # in is not a time (absent/blank/unknown) and there is no usable Out
    return "absent", None, None


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
        "pay_model": cond.get("pay_model", "salaried"),      # 'salaried' | 'hourly'
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


def _agreed_hours(cond, period):
    """Agreed (scheduled) hours for every working day in the pay month.
    Returns (agreed_per_date {'YYYY-MM-DD': hours}, total_agreed)."""
    try:
        yr, mo = int(period[:4]), int(period[5:7])
    except Exception:
        now = datetime.now()
        yr, mo = now.year, now.month
    days_in_month = _calendar.monthrange(yr, mo)[1]

    agreed_per_date = {}
    total_agreed = 0.0
    for d in range(1, days_in_month + 1):
        dt = datetime(yr, mo, d)
        in_m, out_m = _day_schedule(cond, dt.weekday())
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
    return agreed_per_date, total_agreed


def _easter_sunday(year):
    """Easter Sunday for a year (Meeus/Jones/Butcher Gregorian algorithm)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day)


def sa_public_holidays(year):
    """South African public holidays (Public Holidays Act 36 of 1994) for a
    year, as a set of 'YYYY-MM-DD' strings. Includes Good Friday and Family
    Day (Easter-derived) and applies the Act's rule that when a public
    holiday falls on a Sunday, the following Monday is also a public holiday.
    Tenant-agnostic — no business-specific dates."""
    fixed = [(1, 1),    # New Year's Day
             (3, 21),   # Human Rights Day
             (4, 27),   # Freedom Day
             (5, 1),    # Workers' Day
             (6, 16),   # Youth Day
             (8, 9),    # National Women's Day
             (9, 24),   # Heritage Day
             (12, 16),  # Day of Reconciliation
             (12, 25),  # Christmas Day
             (12, 26)]  # Day of Goodwill
    easter = _easter_sunday(year)
    dates = [datetime(year, m, d) for m, d in fixed]
    dates.append(easter - timedelta(days=2))   # Good Friday
    dates.append(easter + timedelta(days=1))   # Family Day
    out = set()
    for dt in dates:
        out.add(dt.strftime("%Y-%m-%d"))
        if dt.weekday() == 6:  # falls on a Sunday -> Monday is also a holiday
            out.add((dt + timedelta(days=1)).strftime("%Y-%m-%d"))
    return out


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
    if public_holidays is None:
        # Default to the SA public holiday calendar for the pay-month's year
        # so a blank cell on a public holiday is never deducted as absent.
        try:
            public_holidays = sa_public_holidays(int(str(period)[:4]))
        except Exception:
            public_holidays = set()
    else:
        public_holidays = set(public_holidays)
    cond = get_conditions(emp)

    # ---- agreed hours for every working day in the period --------------
    agreed_per_date, total_agreed = _agreed_hours(cond, period)

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
        sched_in, sched_out = _day_schedule(cond, wd)

        # Classify the scanned day from its In/Out cells (handles Absent /
        # Sick / Holiday / blank / In-with-no-Out). The public holiday
        # calendar rescues a blank/absent/sick cell into a paid holiday so it
        # is never deducted — but a day actually WORKED on a public holiday
        # keeps its worked treatment (times, late/early/OT) unchanged.
        status, in_m, out_m = _day_status(e.get("in"), e.get("out"))
        if date_str in public_holidays and status in ("absent", "sick"):
            status = "holiday"

        # --- Sunday, or a worked Saturday with no Saturday agreement ----
        # -> entire worked time is premium, not part of base.
        outside_day = (wd == 6) or (wd == 5 and sched_in is None)
        if outside_day:
            if status == "present" and in_m is not None and out_m is not None and out_m > in_m:
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
            continue   # no base on an outside day, so nothing to deduct

        # No agreed schedule this weekday -> nothing in the base to adjust.
        if sched_in is None or sched_out is None:
            continue

        # --- public holiday on a scheduled day --------------------------
        if status == "holiday":
            if not cond["public_holiday_paid"]:
                agreed = agreed_per_date.get(date_str, 0.0)
                if agreed > 0:
                    lines.append({
                        "date": date_str, "day": day_name,
                        "label": "Public holiday — not paid",
                        "hours": round(agreed, 2),
                        "amount": -round(agreed * rate, 2),
                        "kind": "holiday",
                    })
            # paid public holiday is already covered by the base -> no line
            continue

        # --- sick or absent on a scheduled day -> deduct the day --------
        if status in ("sick", "absent"):
            agreed = agreed_per_date.get(date_str, 0.0)
            if agreed > 0:
                label = "Sick — not paid (no note)" if status == "sick" else "Absent — not paid"
                lines.append({
                    "date": date_str, "day": day_name,
                    "label": label,
                    "hours": round(agreed, 2),
                    "amount": -round(agreed * rate, 2),
                    "kind": status,
                })
            continue

        # --- In but no Out -> treat as worked to the scheduled out-time -
        if status == "partial":
            out_m = sched_out

        if in_m is None or out_m is None:
            continue   # nothing usable

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


def build_entries_from_days(days, pay_month):
    """Turn scanned day rows into engine entries with real calendar dates.

    The scanner returns each day as a label like 'Mon 6' / 'Wed 8' plus the
    clock 'in'/'out' times. The engine needs an ISO date (YYYY-MM-DD) per day
    so it can find the weekday and apply the employee's schedule. This rebuilds
    the date from the day-of-month number in the label and the pay month.

    days      : [{'date': 'Mon 6', 'in': '07:00', 'out': '16:00'}, ...]
    pay_month : 'YYYY-MM'.
    Returns   : [{'date': 'YYYY-MM-DD'|original, 'in': .., 'out': ..}, ...].
                Days whose number cannot be resolved keep their original label
                (the engine then leaves that day's base unchanged).
    """
    try:
        yr = int(str(pay_month)[:4])
        mo = int(str(pay_month)[5:7])
        dim = _calendar.monthrange(yr, mo)[1]
    except Exception:
        yr = mo = dim = None

    out = []
    for d in (days or []):
        label = str(d.get("date", "")).strip()
        iso = label

        # 1) Already a full date like '2026-06-08' or '2026/06/08' -> use it
        #    directly. (The old day-of-month regex grabbed the '20' out of the
        #    year and sent every day to the 20th — fixed here.)
        full = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", label)
        if full:
            try:
                _y, _m, _dd = int(full.group(1)), int(full.group(2)), int(full.group(3))
                iso = f"{_y:04d}-{_m:02d}-{_dd:02d}"
            except Exception:
                iso = label
        # 2) Short label like 'Mon 6' -> rebuild from the pay month.
        elif yr and mo:
            m = re.search(r"(\d{1,2})", label)
            if m:
                dom = int(m.group(1))
                if 1 <= dom <= dim:
                    iso = f"{yr:04d}-{mo:02d}-{dom:02d}"

        out.append({"date": iso, "in": d.get("in"), "out": d.get("out")})
    return out


# ------------------------------------------------- worked-hours (hourly) --

def _is_sunday(date_label):
    """Sunday detection. Prefers a real ISO date; falls back to the label."""
    s = str(date_label or "")
    full = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if full:
        try:
            return datetime(int(full.group(1)), int(full.group(2)),
                            int(full.group(3))).weekday() == 6
        except Exception:
            pass
    sl = s.lower()
    return "sun" in sl or "son" in sl   # English / Afrikaans


def compute_worked_hours(days, split_overtime=False, lunch_minutes=30,
                         lunch_threshold_min=300, ot_threshold_hours=8,
                         cond=None):
    """Worked hours from clock In/Out per day, for the HOURLY model.

    Mirrors the timesheet scanner: deduct `lunch_minutes` once a day passes
    `lunch_threshold_min`, split overtime only when the business has
    split_overtime on, and bank Sunday time separately.

    Overtime rule (owner decisions 2026-07-06): overtime exists ONLY when the
    employee's pay conditions (`cond`) define a valid schedule for the day's
    weekday AND the clock-out is past the scheduled out-time. Working the
    full scheduled day (e.g. 07:30-16:30) is all normal time. With no (valid)
    schedule for the day — not set up, unmatched, or an out-time at/before
    the clock-in — there is NO overtime: all worked time is normal.

    Returns {days:[{date,in,out,hours,overtime,sunday,is_sunday,status}],
             total_hours, total_overtime, total_sunday}.
    """
    out_days = []
    total_h = total_ot = total_sun = 0.0
    for d in (days or []):
        d_in = d.get("in")
        d_out = d.get("out")
        status, in_m, out_m = _day_status(d_in, d_out)
        is_sun = _is_sunday(d.get("date"))

        hours = ot = sunday = 0.0
        if status == "present" and in_m is not None and out_m is not None:
            if out_m < in_m:          # overnight
                out_m += 24 * 60
            worked = out_m - in_m
            if worked > lunch_threshold_min:
                worked -= int(lunch_minutes)
            if worked < 0:
                worked = 0
            wh = worked / 60.0
            if split_overtime:
                sched_out_m = None
                if cond and cond.get("is_setup"):
                    wd = _weekday_of(d.get("date"))
                    if wd is not None and wd != 6:
                        _si, _so = _day_schedule(cond, wd)
                        if _so is not None:
                            sched_out_m = _so
                # Sanity guard: a scheduled out-time at/before the clock-in
                # time is invalid (e.g. 04:30 captured instead of 16:30) and
                # would wrongly turn the WHOLE day into overtime. Treat it as
                # no usable schedule for the day.
                if sched_out_m is not None and sched_out_m <= in_m:
                    sched_out_m = None
                if sched_out_m is not None:
                    # OT only past the scheduled out-time
                    ot = max(0.0, (out_m - sched_out_m) / 60.0)
                    if ot > wh:
                        ot = wh
                    hours = wh - ot
                else:
                    # No (valid) schedule for this day -> no OT at all;
                    # all worked time counts as normal (owner decision
                    # 2026-07-06: OT exists ONLY past a scheduled out-time).
                    hours = wh
                    ot = 0.0
            else:
                hours = wh
                ot = 0.0

        if is_sun:
            sunday = hours + ot
            hours = ot = 0.0
            total_sun += sunday
        else:
            total_h += hours
            total_ot += ot

        out_days.append({
            "date": d.get("date"), "in": d_in, "out": d_out,
            "hours": round(hours, 2), "overtime": round(ot, 2),
            "sunday": round(sunday, 2), "is_sunday": is_sun,
            "status": status,
        })

    return {
        "days": out_days,
        "total_hours": round(total_h, 2),
        "total_overtime": round(total_ot, 2),
        "total_sunday": round(total_sun, 2),
    }


def calculate_hourly_pay(emp, period, worked):
    """Gross for an HOURLY employee from worked Normal/OT/Sunday hours.
    `worked` is the dict returned by compute_worked_hours.
    Returns the same shape as calculate_pay_from_timesheet."""
    cond = get_conditions(emp)
    _, total_agreed = _agreed_hours(cond, period)
    rate = derive_hourly_rate(emp, cond, total_agreed)

    nh = _safe_float(worked.get("total_hours", 0))
    oth = _safe_float(worked.get("total_overtime", 0))
    sun = _safe_float(worked.get("total_sunday", 0))
    ot_mult = cond["ot_multiplier"]
    sun_mult = cond["sunday_multiplier"]

    lines = []
    if nh > 0:
        lines.append({"label": f"Normal {nh:.1f}h @ {round(rate,2)}/h",
                      "hours": round(nh, 2), "amount": round(nh * rate, 2),
                      "kind": "normal"})
    if oth > 0:
        lines.append({"label": f"Overtime {oth:.1f}h @ {ot_mult}x",
                      "hours": round(oth, 2),
                      "amount": round(oth * rate * ot_mult, 2), "kind": "ot"})
    if sun > 0:
        lines.append({"label": f"Sunday {sun:.1f}h @ {sun_mult}x",
                      "hours": round(sun, 2),
                      "amount": round(sun * rate * sun_mult, 2), "kind": "premium"})

    gross = sum(l["amount"] for l in lines)
    return {
        "is_setup": cond["is_setup"],
        "pay_model": "hourly",
        "hourly_rate": round(rate, 4),
        "normal_hours": round(nh, 2),
        "overtime_hours": round(oth, 2),
        "sunday_hours": round(sun, 2),
        "agreed_hours": round(total_agreed, 2),
        "base_pay": 0.0,
        "lines": lines,
        "gross": round(gross, 2),
    }


def build_payslip_gross(emp, employee_data, period, business=None,
                        public_holidays=None):
    """Single entry point used by both the preview and the post step.

    Branches on the employee's pay_model:
      - 'hourly'   -> pay Normal + Overtime + Sunday hours actually worked.
      - 'salaried' -> monthly basic +/- absence/late/early/OT deviations.

    `employee_data` is one entry of the batch (has a 'days' list with in/out).
    Returns the calculation dict (with 'pay_model' and 'gross')."""
    cond = get_conditions(emp)
    days = employee_data.get("days", []) if isinstance(employee_data, dict) else []

    # Pay the worked-hours (hourly) model when the worker is explicitly on the
    # hourly model OR their rate is an hourly rate. Hourly staff often have no
    # fixed schedule, so the salaried (schedule-deviation) engine would return
    # zero for them — this routes them to hours x rate instead.
    use_hourly = cond["pay_model"] == "hourly" or cond["rate_method"] == "hourly"
    if cond["is_setup"] and use_hourly:
        # If the reviewer manually overrode the totals on the review screen,
        # honour those typed totals. Otherwise compute from the daily times
        # (with the business overtime-split rule).
        if isinstance(employee_data, dict) and employee_data.get("totals_overridden"):
            worked = {
                "total_hours": _safe_float(employee_data.get("total_hours", 0)),
                "total_overtime": _safe_float(employee_data.get("total_overtime", 0)),
                "total_sunday": _safe_float(employee_data.get("total_sunday", 0)),
            }
        else:
            split_ot = bool(business.get("split_overtime")) if business else False
            lunch_min = 30
            if cond["schedule"].get("lunch_deducted"):
                lunch_min = int(_safe_float(cond["schedule"].get("lunch_minutes", 30)) or 30)
            worked = compute_worked_hours(days, split_overtime=split_ot,
                                          lunch_minutes=lunch_min, cond=cond)
        return calculate_hourly_pay(emp, period, worked)

    # salaried (and the not-set-up fallback) -> deviation engine
    entries = build_entries_from_days(days, period)
    result = calculate_pay_from_timesheet(emp, entries, period,
                                          public_holidays=public_holidays)
    result["pay_model"] = "salaried"
    return result


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
                "pay_model": f.get("pay_model", "salaried"),
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

        def _selm(model):
            return "selected" if cond["pay_model"] == model else ""

        content = f'''
        <div class="card">
            <h2 style="margin-bottom:5px;">Pay Conditions</h2>
            <p style="color:var(--text-muted);margin-bottom:20px;">{safe_string(emp.get("name", "-"))} — the work agreement that determines pay</p>
            <form method="POST">

                <h3 style="margin:15px 0 10px;">Pay model</h3>
                <select name="pay_model" style="padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);width:100%;max-width:360px;">
                    <option value="salaried" {_selm("salaried")}>Salaried — full monthly amount, deduct absences/late</option>
                    <option value="hourly" {_selm("hourly")}>Hourly — pay only for hours actually worked</option>
                </select>
                <p style="color:var(--text-muted);font-size:12px;margin-top:6px;">Salaried pays the monthly basic and docks absent days, late-coming and unpaid sick. Hourly pays Normal + Overtime + Sunday hours from the timesheet.</p>

                <h3 style="margin:20px 0 10px;">How is the rate set?</h3>
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
