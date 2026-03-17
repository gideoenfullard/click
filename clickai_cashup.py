"""
ClickAI Cash Up Module
=======================
Blind Cash Up, X-Reading, Z-Reading
Built as separate module per dev rules.
Import with try/except in clickai.py

Features:
- X-Reading: Mid-day cash monitoring (non-destructive)
- Blind Cash Up: Cashier declares amounts BEFORE seeing system totals
- Z-Reading: End of day close with full reconciliation
- Float tracking
- Discrepancy reporting
- Manager review/approval

DB Table: cash_ups
"""

import json
import logging
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger("clickai")


def register_cashup_routes(app, db, login_required, Auth, generate_id, now, today, render_page=None):
    """Register all cash up routes on the Flask app"""

    # ═══════════════════════════════════════════════════════════════
    # CASH UP PAGE
    # ═══════════════════════════════════════════════════════════════
    @app.route("/cashup")
    @login_required
    def cashup_page():
        """Cash Up / Till Reconciliation page"""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        user_role = user.get("role", "owner") if user else "owner"
        _theme = app.config.get("DEFAULT_THEME", "midnight")
        try:
            from flask import request as req
            _theme = req.cookies.get("clickai_theme", _theme)
        except:
            pass

        # Get today's sales breakdown
        sales = db.get("sales", {"business_id": biz_id, "date": today()}) if biz_id else []
        sales = sales or []

        total_cash = sum(float(s.get("total", 0) or 0) for s in sales if s.get("payment_method") == "cash")
        total_card = sum(float(s.get("total", 0) or 0) for s in sales if s.get("payment_method") == "card")
        total_account = sum(float(s.get("total", 0) or 0) for s in sales if s.get("payment_method") == "account")
        total_sales = total_cash + total_card + total_account
        sale_count = len(sales)

        # Get cashiers who made sales today
        cashier_sales = {}
        for s in sales:
            cid = s.get("created_by") or "unknown"
            cname = s.get("customer_name", "").split(" - ")[-1] if " - " in s.get("customer_name", "") else ""
            # Try to get cashier name from notes
            notes = s.get("notes", "")
            if "Cashier:" in notes:
                cname = notes.split("Cashier:")[-1].strip()
            if cid not in cashier_sales:
                cashier_sales[cid] = {"name": cname or cid[:8], "cash": 0, "card": 0, "account": 0, "count": 0}
            pm = s.get("payment_method", "cash")
            amt = float(s.get("total", 0) or 0)
            cashier_sales[cid][pm] = cashier_sales[cid].get(pm, 0) + amt
            cashier_sales[cid]["count"] += 1

        # Get previous cash ups for today
        cash_ups = db.get("cash_ups", {"business_id": biz_id, "date": today()}) if biz_id else []
        cash_ups = cash_ups or []

        # Get team members for dropdown
        team = []
        try:
            team = db.get_business_users(biz_id) if biz_id else []
            team = team or []
        except:
            pass

        cashiers_json = json.dumps(list(cashier_sales.values()), default=str)
        cashups_json = json.dumps(cash_ups, default=str)
        team_json = json.dumps([{"id": t.get("id", ""), "name": t.get("name", t.get("email", ""))} for t in team], default=str)

        is_manager = user_role in ("owner", "admin", "manager")

        _xread_btn = '''<button class="action-btn" onclick="showPanel('xread')">
            <span class="btn-icon">📊</span>
            <span class="btn-label">X-Reading</span>
        </button>''' if is_manager else ''

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cash Up - ClickAI</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
    --bg: #0a0a0f;
    --surface: #12121a;
    --surface2: #1a1a25;
    --border: #2a2a3a;
    --text: #e0e0e8;
    --text-dim: #888;
    --accent: #00d4ff;
    --accent-glow: rgba(0, 212, 255, 0.15);
    --green: #00ff88;
    --green-glow: rgba(0, 255, 136, 0.15);
    --red: #ff4466;
    --red-glow: rgba(255, 68, 102, 0.15);
    --orange: #ffaa00;
    --orange-glow: rgba(255, 170, 0, 0.15);
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    min-height: 100vh;
    overflow-x: hidden;
}}

/* ─── TOP NAV ─── */
.top-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
}}
.top-bar h1 {{
    font-family: 'Orbitron', monospace;
    font-size: 1.1rem;
    color: var(--accent);
    letter-spacing: 3px;
    text-transform: uppercase;
}}
.top-bar .back-btn {{
    color: var(--text-dim);
    text-decoration: none;
    font-size: 0.9rem;
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 4px;
    transition: all 0.2s;
}}
.top-bar .back-btn:hover {{ color: var(--accent); border-color: var(--accent); }}

/* ─── STATS ROW ─── */
.stats-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    padding: 16px 20px;
}}
.stat-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
    position: relative;
    overflow: hidden;
}}
.stat-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent);
}}
.stat-card.cash::before {{ background: var(--green); }}
.stat-card.card::before {{ background: var(--orange); }}
.stat-card.account::before {{ background: var(--accent); }}
.stat-label {{
    font-size: 0.7rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
    font-family: 'Orbitron', monospace;
    margin-bottom: 6px;
}}
.stat-value {{
    font-size: 1.5rem;
    font-weight: 700;
    font-family: 'Orbitron', monospace;
}}
.stat-card.cash .stat-value {{ color: var(--green); }}
.stat-card.card .stat-value {{ color: var(--orange); }}
.stat-card.account .stat-value {{ color: var(--accent); }}
.stat-card.total .stat-value {{ color: var(--text); }}
.stat-sub {{
    font-size: 0.75rem;
    color: var(--text-dim);
    margin-top: 4px;
}}

/* ─── MAIN CONTENT ─── */
.main {{
    padding: 0 20px 100px 20px;
    max-width: 800px;
    margin: 0 auto;
}}

/* ─── ACTION BUTTONS ─── */
.actions {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin: 16px 0;
}}
.action-btn {{
    padding: 18px 16px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--surface);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
    position: relative;
    overflow: hidden;
}}
.action-btn:hover {{
    border-color: var(--accent);
    background: var(--accent-glow);
}}
.action-btn .btn-icon {{
    font-size: 1.8rem;
    display: block;
    margin-bottom: 6px;
}}
.action-btn .btn-label {{
    font-family: 'Orbitron', monospace;
    font-size: 0.65rem;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
.action-btn.primary {{
    border-color: var(--green);
    background: var(--green-glow);
}}
.action-btn.primary:hover {{
    background: rgba(0, 255, 136, 0.25);
    box-shadow: 0 0 20px rgba(0, 255, 136, 0.1);
}}

/* ─── PANELS ─── */
.panel {{
    display: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    margin: 16px 0;
    animation: slideIn 0.3s ease;
}}
.panel.active {{ display: block; }}
@keyframes slideIn {{
    from {{ opacity: 0; transform: translateY(10px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}
.panel-title {{
    font-family: 'Orbitron', monospace;
    font-size: 0.8rem;
    letter-spacing: 3px;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
}}

/* ─── FORM ELEMENTS ─── */
.form-group {{
    margin-bottom: 14px;
}}
.form-group label {{
    display: block;
    font-size: 0.75rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 6px;
    font-weight: 600;
}}
.form-input {{
    width: 100%;
    padding: 12px 14px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    transition: border-color 0.2s;
}}
.form-input:focus {{
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-glow);
}}
.form-input::placeholder {{ color: #555; }}
select.form-input {{
    appearance: none;
    cursor: pointer;
}}

/* ─── DENOMINATION GRID ─── */
.denom-grid {{
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 8px;
    align-items: center;
}}
.denom-label {{
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-dim);
    min-width: 70px;
}}
.denom-label.note {{ color: var(--green); }}
.denom-label.coin {{ color: var(--orange); }}
.denom-input {{
    width: 80px;
    padding: 8px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    font-size: 1rem;
    font-weight: 600;
    text-align: center;
}}
.denom-input:focus {{
    outline: none;
    border-color: var(--accent);
}}
.denom-total {{
    font-family: 'Orbitron', monospace;
    font-size: 0.85rem;
    color: var(--text);
    min-width: 90px;
    text-align: right;
}}

/* ─── RESULT BOX ─── */
.result-box {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-top: 16px;
}}
.result-row {{
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 0.95rem;
}}
.result-row:last-child {{ border-bottom: none; }}
.result-row .rl {{ color: var(--text-dim); }}
.result-row .rv {{ font-weight: 700; font-family: 'Orbitron', monospace; font-size: 0.85rem; }}
.result-row.total {{ border-top: 2px solid var(--border); padding-top: 12px; margin-top: 4px; }}
.result-row.total .rv {{ font-size: 1.1rem; }}
.result-row.over .rv {{ color: var(--green); }}
.result-row.short .rv {{ color: var(--red); }}
.result-row.match .rv {{ color: var(--green); }}

/* ─── SUBMIT BTN ─── */
.submit-btn {{
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 6px;
    font-family: 'Orbitron', monospace;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 16px;
}}
.submit-btn.green {{
    background: var(--green);
    color: #000;
}}
.submit-btn.green:hover {{ box-shadow: 0 0 20px rgba(0, 255, 136, 0.3); }}
.submit-btn.blue {{
    background: var(--accent);
    color: #000;
}}
.submit-btn.blue:hover {{ box-shadow: 0 0 20px rgba(0, 212, 255, 0.3); }}

/* ─── HISTORY ─── */
.history-item {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 10px;
}}
.history-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}}
.history-type {{
    font-family: 'Orbitron', monospace;
    font-size: 0.7rem;
    letter-spacing: 2px;
    padding: 3px 10px;
    border-radius: 3px;
    text-transform: uppercase;
}}
.history-type.xread {{ background: var(--accent-glow); color: var(--accent); }}
.history-type.blind {{ background: var(--green-glow); color: var(--green); }}
.history-type.zread {{ background: var(--orange-glow); color: var(--orange); }}
.history-time {{ font-size: 0.85rem; color: var(--text-dim); }}
.history-detail {{ font-size: 0.9rem; color: var(--text-dim); }}
.history-detail span {{ color: var(--text); font-weight: 600; }}
.disc-over {{ color: var(--green) !important; }}
.disc-short {{ color: var(--red) !important; }}
.disc-match {{ color: var(--green) !important; }}

/* ─── HIDDEN TOTALS (for blind cash up) ─── */
.system-reveal {{
    display: none;
    animation: revealSlide 0.5s ease;
}}
.system-reveal.show {{ display: block; }}
@keyframes revealSlide {{
    from {{ opacity: 0; transform: scale(0.95); }}
    to {{ opacity: 1; transform: scale(1); }}
}}

.empty-state {{
    text-align: center;
    padding: 40px 20px;
    color: var(--text-dim);
}}
.empty-state .icon {{ font-size: 2.5rem; margin-bottom: 10px; }}

@media (max-width: 480px) {{
    .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
    .actions {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<div class="top-bar">
    <a href="/pos" class="back-btn">&larr; POS</a>
    <h1>Cash Up</h1>
    <a href="/" class="back-btn">Dashboard</a>
</div>

<!-- ═══ SYSTEM STATS (visible to managers only, on X-Reading) ═══ -->
{'<div class="stats-row" id="statsRow">' if is_manager else '<div class="stats-row" id="statsRow" style="display:none;">'}
    <div class="stat-card cash">
        <div class="stat-label">Cash</div>
        <div class="stat-value" id="sysCash">{'R' + f'{total_cash:,.2f}' if is_manager else '—'}</div>
        <div class="stat-sub">{sum(1 for s in sales if s.get('payment_method')=='cash')} sales</div>
    </div>
    <div class="stat-card card">
        <div class="stat-label">Card</div>
        <div class="stat-value" id="sysCard">{'R' + f'{total_card:,.2f}' if is_manager else '—'}</div>
        <div class="stat-sub">{sum(1 for s in sales if s.get('payment_method')=='card')} sales</div>
    </div>
    <div class="stat-card account">
        <div class="stat-label">Account</div>
        <div class="stat-value" id="sysAccount">{'R' + f'{total_account:,.2f}' if is_manager else '—'}</div>
        <div class="stat-sub">{sum(1 for s in sales if s.get('payment_method')=='account')} sales</div>
    </div>
    <div class="stat-card total">
        <div class="stat-label">Total</div>
        <div class="stat-value">{'R' + f'{total_sales:,.2f}' if is_manager else '—'}</div>
        <div class="stat-sub">{sale_count} sales today</div>
    </div>
</div>

<div class="main">

    <!-- ═══ ACTION BUTTONS ═══ -->
    <div class="actions">
        {_xread_btn}
        <button class="action-btn primary" onclick="showPanel('blind')">
            <span class="btn-icon">🔒</span>
            <span class="btn-label">Blind Cash Up</span>
        </button>
    </div>

    <!-- ═══ X-READING PANEL (managers only) ═══ -->
    {'<div class="panel" id="panel-xread">' if is_manager else '<div class="panel" id="panel-xread" style="display:none !important;">'}
        <div class="panel-title">X-Reading — Mid-Day Check</div>
        <p style="color: var(--text-dim); font-size: 0.9rem; margin-bottom: 16px;">
            Non-destructive reading. Check current till status without closing the shift.
        </p>
        <div class="result-box">
            <div class="result-row">
                <span class="rl">Cash Sales</span>
                <span class="rv" style="color:var(--green)">{'R' + f'{total_cash:,.2f}' if is_manager else '—'}</span>
            </div>
            <div class="result-row">
                <span class="rl">Card Sales</span>
                <span class="rv" style="color:var(--orange)">{'R' + f'{total_card:,.2f}' if is_manager else '—'}</span>
            </div>
            <div class="result-row">
                <span class="rl">Account Sales</span>
                <span class="rv" style="color:var(--accent)">{'R' + f'{total_account:,.2f}' if is_manager else '—'}</span>
            </div>
            <div class="result-row total">
                <span class="rl">Total Sales</span>
                <span class="rv">{'R' + f'{total_sales:,.2f}' if is_manager else '—'}</span>
            </div>
            <div class="result-row">
                <span class="rl">Transactions</span>
                <span class="rv">{sale_count}</span>
            </div>
        </div>
        <button class="submit-btn blue" onclick="saveXReading()">Save X-Reading</button>
    </div>

    <!-- ═══ BLIND CASH UP PANEL ═══ -->
    <div class="panel" id="panel-blind">
        <div class="panel-title">🔒 Blind Cash Up</div>
        <p style="color: var(--text-dim); font-size: 0.9rem; margin-bottom: 16px;">
            Count your cash, card slips, and vouchers. Enter totals below.<br>
            System totals are <strong style="color:var(--red)">hidden</strong> until you submit.
        </p>

        <div class="form-group">
            <label>Cashier / Till Operator</label>
            <select class="form-input" id="blindCashier">
                <option value="">— Select —</option>
            </select>
        </div>

        <div class="form-group">
            <label>Float Amount (start of day)</label>
            <input type="number" class="form-input" id="blindFloat" placeholder="e.g. 500.00" step="0.01" value="0">
        </div>

        <h3 style="font-family:'Orbitron',monospace; font-size:0.7rem; letter-spacing:2px; color:var(--green); margin: 18px 0 12px; text-transform:uppercase;">
            Cash Denomination Count
        </h3>
        <div class="denom-grid" id="denomGrid">
            <!-- Filled by JS -->
        </div>
        <div class="result-box" style="margin-top:12px;">
            <div class="result-row total">
                <span class="rl">Total Cash Counted</span>
                <span class="rv" id="totalCashCounted" style="color:var(--green)">R0.00</span>
            </div>
        </div>

        <div class="form-group" style="margin-top:16px;">
            <label>Card Slips Total</label>
            <input type="number" class="form-input" id="blindCard" placeholder="Total from card machine" step="0.01" value="0">
        </div>

        <div class="form-group">
            <label>Account Sales / Vouchers</label>
            <input type="number" class="form-input" id="blindAccount" placeholder="Account sales total" step="0.01" value="0">
        </div>

        <div class="result-box">
            <div class="result-row total">
                <span class="rl">Your Declared Total</span>
                <span class="rv" id="declaredTotal" style="font-size:1.2rem;">R0.00</span>
            </div>
        </div>

        <button class="submit-btn green" onclick="submitBlindCashUp()">Submit & Reveal</button>

        <!-- ═══ SYSTEM REVEAL (shown after submit) ═══ -->
        <div class="system-reveal" id="systemReveal">
            <h3 style="font-family:'Orbitron',monospace; font-size:0.75rem; letter-spacing:3px; color:var(--accent); margin: 20px 0 12px; text-transform:uppercase; text-align:center;">
                ⚡ System Comparison
            </h3>
            <div class="result-box" id="revealBox">
                <!-- Filled by JS after submit -->
            </div>
        </div>
    </div>

    <!-- ═══ TODAY'S HISTORY ═══ -->
    <h3 style="font-family:'Orbitron',monospace; font-size:0.7rem; letter-spacing:2px; color:var(--text-dim); margin: 24px 0 12px; text-transform:uppercase;">
        Today's Cash Ups
    </h3>
    <div id="historyList">
        <div class="empty-state" id="emptyHistory">
            <div class="icon">🧾</div>
            <div>No cash ups recorded today</div>
        </div>
    </div>

</div>

<script>
// ═══ DATA ═══
const SYS_CASH = {total_cash};
const SYS_CARD = {total_card};
const SYS_ACCOUNT = {total_account};
const SYS_TOTAL = {total_sales};
const SALE_COUNT = {sale_count};
const IS_MANAGER = {'true' if is_manager else 'false'};
const TODAY_DATE = '{today()}';
const TEAM = {team_json};
const HISTORY = {cashups_json};

// SA denominations
const DENOMINATIONS = [
    {{ label: 'R200', value: 200, type: 'note' }},
    {{ label: 'R100', value: 100, type: 'note' }},
    {{ label: 'R50', value: 50, type: 'note' }},
    {{ label: 'R20', value: 20, type: 'note' }},
    {{ label: 'R10', value: 10, type: 'note' }},
    {{ label: 'R5', value: 5, type: 'coin' }},
    {{ label: 'R2', value: 2, type: 'coin' }},
    {{ label: 'R1', value: 1, type: 'coin' }},
    {{ label: '50c', value: 0.50, type: 'coin' }},
    {{ label: '20c', value: 0.20, type: 'coin' }},
    {{ label: '10c', value: 0.10, type: 'coin' }},
];

// ═══ INIT ═══
document.addEventListener('DOMContentLoaded', () => {{
    buildDenomGrid();
    buildTeamDropdown();
    renderHistory();

    // Hide stats on load for EVERYONE — only show when X-Reading panel is opened
    document.getElementById('statsRow').style.display = 'none';
}});

function buildDenomGrid() {{
    const grid = document.getElementById('denomGrid');
    grid.innerHTML = DENOMINATIONS.map((d, i) => `
        <div class="denom-label ${{d.type}}">${{d.label}}</div>
        <input type="number" class="denom-input" id="denom_${{i}}" 
               data-value="${{d.value}}" placeholder="0" min="0"
               oninput="updateCashTotal()">
        <div class="denom-total" id="denomTotal_${{i}}">R0.00</div>
    `).join('');
}}

function buildTeamDropdown() {{
    const sel = document.getElementById('blindCashier');
    TEAM.forEach(t => {{
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = t.name;
        sel.appendChild(opt);
    }});
}}

// ═══ PANELS ═══
let activePanel = null;
function showPanel(id) {{
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById('panel-' + id);
    if (activePanel === id) {{
        activePanel = null;
        return;
    }}
    panel.classList.add('active');
    activePanel = id;

    // Hide system stats when blind cash up is active (for everyone)
    // Only show stats on X-Reading for managers
    if (id === 'blind' || !IS_MANAGER) {{
        document.getElementById('statsRow').style.display = 'none';
    }} else {{
        document.getElementById('statsRow').style.display = '';
    }}
}}

// ═══ DENOMINATION COUNTING ═══
function updateCashTotal() {{
    let total = 0;
    DENOMINATIONS.forEach((d, i) => {{
        const qty = parseInt(document.getElementById('denom_' + i).value) || 0;
        const lineTotal = qty * d.value;
        document.getElementById('denomTotal_' + i).textContent = 'R' + lineTotal.toFixed(2);
        total += lineTotal;
    }});
    document.getElementById('totalCashCounted').textContent = 'R' + total.toFixed(2);
    updateDeclaredTotal();
}}

function updateDeclaredTotal() {{
    const cash = getCashCounted();
    const card = parseFloat(document.getElementById('blindCard').value) || 0;
    const account = parseFloat(document.getElementById('blindAccount').value) || 0;
    const floatAmt = parseFloat(document.getElementById('blindFloat').value) || 0;
    const total = (cash - floatAmt) + card + account;
    document.getElementById('declaredTotal').textContent = 'R' + total.toFixed(2);
}}

function getCashCounted() {{
    let total = 0;
    DENOMINATIONS.forEach((d, i) => {{
        const qty = parseInt(document.getElementById('denom_' + i).value) || 0;
        total += qty * d.value;
    }});
    return total;
}}

// Update declared total when card/account/float changes
document.addEventListener('input', (e) => {{
    if (['blindCard', 'blindAccount', 'blindFloat'].includes(e.target.id)) {{
        updateDeclaredTotal();
    }}
}});

// ═══ X-READING SAVE ═══
async function saveXReading() {{
    try {{
        const resp = await fetch('/api/cashup/save', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
                type: 'x_reading',
                system_cash: SYS_CASH,
                system_card: SYS_CARD,
                system_account: SYS_ACCOUNT,
                system_total: SYS_TOTAL,
                sale_count: SALE_COUNT
            }})
        }});
        const data = await resp.json();
        if (data.success) {{
            alert('X-Reading saved at ' + new Date().toLocaleTimeString());
            location.reload();
        }} else {{
            alert('Error: ' + (data.error || 'Failed'));
        }}
    }} catch(e) {{
        alert('Error: ' + e.message);
    }}
}}

// ═══ BLIND CASH UP ═══
async function submitBlindCashUp() {{
    const cashier = document.getElementById('blindCashier');
    const cashierName = cashier.options[cashier.selectedIndex]?.text || '';
    const cashierId = cashier.value;

    if (!cashierId) {{
        alert('Please select a cashier first');
        return;
    }}

    // ═══ CHECK: Has this cashier already done a blind cashup today? ═══
    try {{
        const histResp = await fetch('/api/cashup/history?date=' + encodeURIComponent(TODAY_DATE));
        const histData = await histResp.json();
        if (histData.success && histData.cash_ups) {{
            const existing = histData.cash_ups.filter(c => 
                c.type === 'blind_cashup' && c.cashier_id === cashierId
            );
            if (existing.length > 0) {{
                alert('⚠ ' + cashierName + ' het reeds vandag \'n blind cashup ingedien.\\n\\nNet een blind cashup per kassier per dag.');
                return;
            }}
        }}
    }} catch(e) {{
        console.log('History check failed, proceeding:', e);
    }}

    const floatAmt = parseFloat(document.getElementById('blindFloat').value) || 0;
    const cashCounted = getCashCounted();
    const cardDeclared = parseFloat(document.getElementById('blindCard').value) || 0;
    const accountDeclared = parseFloat(document.getElementById('blindAccount').value) || 0;

    // Cash sales = cash counted minus the float
    const cashSalesDeclared = cashCounted - floatAmt;
    const declaredTotal = cashSalesDeclared + cardDeclared + accountDeclared;

    // Calculate discrepancies
    const cashDisc = cashSalesDeclared - SYS_CASH;
    const cardDisc = cardDeclared - SYS_CARD;
    const totalDisc = declaredTotal - (SYS_CASH + SYS_CARD + SYS_ACCOUNT);

    // Build denomination breakdown
    const denomBreakdown = {{}};
    DENOMINATIONS.forEach((d, i) => {{
        const qty = parseInt(document.getElementById('denom_' + i).value) || 0;
        if (qty > 0) denomBreakdown[d.label] = qty;
    }});

    // ═══ SAVE FIRST — before showing anything ═══
    try {{
        const resp = await fetch('/api/cashup/save', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
                type: 'blind_cashup',
                cashier_id: cashierId,
                cashier_name: cashierName,
                float_amount: floatAmt,
                cash_counted: cashCounted,
                cash_declared: cashSalesDeclared,
                card_declared: cardDeclared,
                account_declared: accountDeclared,
                declared_total: declaredTotal,
                denominations: denomBreakdown,
                system_cash: SYS_CASH,
                system_card: SYS_CARD,
                system_account: SYS_ACCOUNT,
                system_total: SYS_CASH + SYS_CARD + SYS_ACCOUNT,
                cash_discrepancy: cashDisc,
                card_discrepancy: cardDisc,
                total_discrepancy: totalDisc,
                sale_count: SALE_COUNT
            }})
        }});
        const data = await resp.json();
        if (!data.success) {{
            alert('Save failed: ' + (data.error || 'Unknown error'));
            return;
        }}
    }} catch(e) {{
        alert('Save error — check your connection and try again.');
        console.error('Save error:', e);
        return;
    }}

    // ═══ DISABLE ALL INPUTS — cashup is locked ═══
    document.querySelectorAll('#panel-blind input, #panel-blind select').forEach(el => el.disabled = true);
    document.querySelector('#panel-blind .submit-btn').style.display = 'none';

    // ═══ SHOW RESULT ═══
    const revealBox = document.getElementById('revealBox');
    const discClass = (v) => v > 0.01 ? 'over' : v < -0.01 ? 'short' : 'match';
    const discLabel = (v) => v > 0.01 ? '+R' + v.toFixed(2) + ' OVER' : v < -0.01 ? '-R' + Math.abs(v).toFixed(2) + ' SHORT' : 'EXACT MATCH ✓';

    if (IS_MANAGER) {{
        // Managers see full comparison
        revealBox.innerHTML = `
            <div class="result-row">
                <span class="rl">System Cash Sales</span>
                <span class="rv" style="color:var(--green)">R${{SYS_CASH.toFixed(2)}}</span>
            </div>
            <div class="result-row">
                <span class="rl">Your Cash Count (minus float)</span>
                <span class="rv">R${{cashSalesDeclared.toFixed(2)}}</span>
            </div>
            <div class="result-row ${{discClass(cashDisc)}}">
                <span class="rl">Cash Discrepancy</span>
                <span class="rv">${{discLabel(cashDisc)}}</span>
            </div>
            <hr style="border:none;border-top:1px solid var(--border);margin:8px 0">
            <div class="result-row">
                <span class="rl">System Card Sales</span>
                <span class="rv" style="color:var(--orange)">R${{SYS_CARD.toFixed(2)}}</span>
            </div>
            <div class="result-row">
                <span class="rl">Your Card Slips</span>
                <span class="rv">R${{cardDeclared.toFixed(2)}}</span>
            </div>
            <div class="result-row ${{discClass(cardDisc)}}">
                <span class="rl">Card Discrepancy</span>
                <span class="rv">${{discLabel(cardDisc)}}</span>
            </div>
            <hr style="border:none;border-top:1px solid var(--border);margin:8px 0">
            <div class="result-row">
                <span class="rl">System Account Sales</span>
                <span class="rv" style="color:var(--accent)">R${{SYS_ACCOUNT.toFixed(2)}}</span>
            </div>
            <div class="result-row">
                <span class="rl">Your Account/Vouchers</span>
                <span class="rv">R${{accountDeclared.toFixed(2)}}</span>
            </div>
            <hr style="border:none;border-top:2px solid var(--border);margin:10px 0">
            <div class="result-row total ${{discClass(totalDisc)}}">
                <span class="rl" style="font-size:1rem;">TOTAL DISCREPANCY</span>
                <span class="rv" style="font-size:1.2rem;">${{discLabel(totalDisc)}}</span>
            </div>
        `;
        document.getElementById('statsRow').style.display = '';
    }} else {{
        // Staff only see confirmation — NO system totals, NO discrepancies
        revealBox.innerHTML = `
            <div style="text-align:center;padding:20px;">
                <div style="font-size:2rem;margin-bottom:10px;">✅</div>
                <div style="font-size:1.1rem;font-weight:700;color:var(--green);margin-bottom:8px;">Cash Up Submitted</div>
                <div style="color:var(--text-dim);font-size:0.9rem;">Your declared total: <strong>R${{declaredTotal.toFixed(2)}}</strong></div>
                <div style="color:var(--text-dim);font-size:0.85rem;margin-top:8px;">Your manager will review the results.</div>
            </div>
        `;
    }}

    document.getElementById('systemReveal').classList.add('show');
}}

// ═══ HISTORY RENDER ═══
function renderHistory() {{
    const list = document.getElementById('historyList');
    if (!HISTORY || HISTORY.length === 0) return;

    document.getElementById('emptyHistory').style.display = 'none';

    const sorted = HISTORY.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
    
    list.innerHTML = sorted.map(h => {{
        const type = h.type || 'unknown';
        const typeClass = type === 'x_reading' ? 'xread' : type === 'blind_cashup' ? 'blind' : 'zread';
        const typeLabel = type === 'x_reading' ? 'X-Read' : type === 'blind_cashup' ? 'Blind Cash Up' : type;
        const time = h.created_at ? new Date(h.created_at).toLocaleTimeString() : '';
        
        let detail = '';
        if (type === 'x_reading') {{
            detail = `Total: <span>R${{(h.system_total || 0).toFixed(2)}}</span> | ${{h.sale_count || 0}} sales`;
        }} else if (type === 'blind_cashup') {{
            const disc = h.total_discrepancy || 0;
            const discCls = disc > 0.01 ? 'disc-over' : disc < -0.01 ? 'disc-short' : 'disc-match';
            const discTxt = disc > 0.01 ? '+R' + disc.toFixed(2) + ' over' : disc < -0.01 ? '-R' + Math.abs(disc).toFixed(2) + ' short' : 'Exact match';
            detail = `Cashier: <span>${{h.cashier_name || '—'}}</span> | Declared: <span>R${{(h.declared_total || 0).toFixed(2)}}</span> | <span class="${{discCls}}">${{discTxt}}</span>`;
        }}
        
        return `<div class="history-item">
            <div class="history-header">
                <span class="history-type ${{typeClass}}">${{typeLabel}}</span>
                <span class="history-time">${{time}}</span>
            </div>
            <div class="history-detail">${{detail}}</div>
        </div>`;
    }}).join('');
}}
</script>

</body>
</html>"""

        from flask import make_response
        resp = make_response(html)
        return resp


    # ═══════════════════════════════════════════════════════════════
    # CASH UP SAVE API
    # ═══════════════════════════════════════════════════════════════
    @app.route("/api/cashup/save", methods=["POST"])
    @login_required
    def api_cashup_save():
        """Save a cash up record (x-reading, blind cash up, z-reading)"""
        from flask import request, jsonify
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        try:
            data = request.json
            cashup_type = data.get("type", "unknown")

            record = {
                "id": generate_id(),
                "business_id": biz_id,
                "date": today(),
                "type": cashup_type,
                "created_by": user.get("id") if user else None,
                "created_at": now(),
            }

            if cashup_type == "x_reading":
                record.update({
                    "system_cash": data.get("system_cash", 0),
                    "system_card": data.get("system_card", 0),
                    "system_account": data.get("system_account", 0),
                    "system_total": data.get("system_total", 0),
                    "sale_count": data.get("sale_count", 0),
                })

            elif cashup_type == "blind_cashup":
                record.update({
                    "cashier_id": data.get("cashier_id"),
                    "cashier_name": data.get("cashier_name", ""),
                    "float_amount": data.get("float_amount", 0),
                    "cash_counted": data.get("cash_counted", 0),
                    "cash_declared": data.get("cash_declared", 0),
                    "card_declared": data.get("card_declared", 0),
                    "account_declared": data.get("account_declared", 0),
                    "declared_total": data.get("declared_total", 0),
                    "denominations": json.dumps(data.get("denominations", {})),
                    "system_cash": data.get("system_cash", 0),
                    "system_card": data.get("system_card", 0),
                    "system_account": data.get("system_account", 0),
                    "system_total": data.get("system_total", 0),
                    "cash_discrepancy": data.get("cash_discrepancy", 0),
                    "card_discrepancy": data.get("card_discrepancy", 0),
                    "total_discrepancy": data.get("total_discrepancy", 0),
                    "sale_count": data.get("sale_count", 0),
                })

            elif cashup_type == "z_reading":
                record.update({
                    "system_cash": data.get("system_cash", 0),
                    "system_card": data.get("system_card", 0),
                    "system_account": data.get("system_account", 0),
                    "system_total": data.get("system_total", 0),
                    "sale_count": data.get("sale_count", 0),
                    "cash_counted": data.get("cash_counted", ""),
                    "cash_difference": data.get("cash_difference", ""),
                    "cash_status": data.get("cash_status", ""),
                    "created_by_name": user.get("name", "") if user else "",
                })

            from flask import jsonify
            success, err = db.save("cash_ups", record)
            if success:
                logger.info(f"[CASHUP] {cashup_type} saved for biz={biz_id}")
                return jsonify({"success": True, "id": record["id"]})
            else:
                logger.error(f"[CASHUP] Save failed: {err}")
                return jsonify({"success": False, "error": str(err)})

        except Exception as e:
            logger.error(f"[CASHUP] Error: {e}")
            from flask import jsonify
            return jsonify({"success": False, "error": str(e)})


    # ═══════════════════════════════════════════════════════════════
    # CASH UP HISTORY API
    # ═══════════════════════════════════════════════════════════════
    @app.route("/api/cashup/history")
    @login_required
    def api_cashup_history():
        """Get cash up history"""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        from flask import request as req, jsonify
        date_filter = req.args.get("date", today())

        records = db.get("cash_ups", {"business_id": biz_id, "date": date_filter}) if biz_id else []
        return jsonify({"success": True, "cash_ups": records or []})

    logger.info("[CASHUP] Cash Up module loaded - routes: /cashup, /api/cashup/save, /api/cashup/history")
