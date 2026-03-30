"""
ClickAI Pulse Module
=====================
Business Pulse dashboard — real-time activity monitoring, overdue invoice
tracking, staff activity per user, stock alerts.

UPGRADED to track ALL activity types:
- Invoices, Quotes, POS Sales, Payments, Credit Notes
- Delivery Notes, Purchase Orders, Job Cards, GRVs
- Expenses, Bank Transactions, Cash-Ups, Timesheets
- Journals, Scanned Documents, Stock Movements, Supplier Payments

Overdue invoices shown per-invoice (not just per-customer grouping).
Every action tracked to exact user via created_by field.

DB Tables read (all read-only, no writes except cache):
  invoices, sales, payments, quotes, credit_notes, delivery_notes,
  purchase_orders, jobs, goods_received, expenses, bank_transactions,
  cash_ups, timesheet_entries, journals, scanned_documents,
  stock_movements, supplier_payments, reminders, todos, notes, daily_briefings

Routes:
  /pulse                  — Page (skeleton, data via AJAX)
  /api/pulse/data         — POST, returns all dashboard data
  /api/briefing/generate  — POST, background AI briefing
  /api/assistant/items    — GET, reminders + todos
  /api/assistant/toggle   — POST, complete/uncomplete
  /api/assistant/delete   — POST, delete item
"""

import json
import logging
import time
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Module-level caches (survive across requests, reset on restart)
_pulse_cache = {}
_briefing_cache = {}


def register_pulse_routes(app, db, login_required, Auth, generate_id, now, today,
                          render_page, get_user_role, extract_time,
                          has_reactor_hud, jarvis_hud_header, jarvis_techline,
                          JARVIS_HUD_CSS, THEME_REACTOR_SKINS,
                          DailyBriefing=None):
    """Register all Pulse dashboard routes."""

    global _pulse_cache, _briefing_cache

    # ─────────────────────────────────────────────────────────
    # PULSE PAGE — Lightweight skeleton, data loads via AJAX
    # ─────────────────────────────────────────────────────────
    @app.route("/pulse")
    @login_required
    def business_pulse():
        from flask import session, redirect

        # SESSION CLEANUP — keep cookie under 4KB
        for key in list(session.keys()):
            if key.startswith("zane_chat") or key.startswith("zane_import") or key == "zane_pending_delete" or key == "zane_last_error":
                session.pop(key, None)

        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("name", "Business") if business else "Business"

        if not biz_id:
            return redirect("/")

        role = get_user_role()
        is_manager = role in ("owner", "admin", "manager")

        # ── mdToHtml JS (regular string, not f-string — regex backslashes) ──
        pulse_md_to_html_js = '''
    function mdToHtml(text) {
        if (!text) return '';
        let html = text;
        if (html.includes('|')) {
            html = html.replace(/^(\\|.+\\|)\\n\\|[-:| ]+\\|\\n((?:\\|.+\\|\\n?)*)/gm, function(match, header, body) {
                const hCells = header.split('|').filter(c => c.trim()).map(c => '<th style="padding:8px 12px;text-align:left;border-bottom:2px solid rgba(139,92,246,0.3);">' + c.trim() + '</th>').join('');
                const rows = body.trim().split('\\n').map(row => {
                    const cells = row.split('|').filter(c => c.trim()).map(c => '<td style="padding:6px 12px;border-bottom:1px solid rgba(255,255,255,0.1);">' + c.trim() + '</td>').join('');
                    return '<tr>' + cells + '</tr>';
                }).join('');
                return '<table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:14px;"><thead><tr>' + hCells + '</tr></thead><tbody>' + rows + '</tbody></table>';
            });
        }
        html = html.replace(/^### (.+)$/gm, '<h4 style="margin:12px 0 6px;color:var(--primary);">$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3 style="margin:14px 0 8px;color:var(--primary);">$1</h3>');
        html = html.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
        html = html.replace(/\\*(.+?)\\*/g, '<em>$1</em>');
        html = html.replace(/^- (.+)$/gm, '<li style="margin:3px 0;">$1</li>');
        html = html.replace(/(<li[^>]*>.*<\\/li>\\n?)+/g, '<ul style="margin:8px 0;padding-left:20px;">$&</ul>');
        html = html.replace(/\\n\\n/g, '</p><p style="margin:8px 0;">');
        html = html.replace(/\\n/g, '<br>');
        html = '<p style="margin:8px 0;">' + html + '</p>';
        return html;
    }
    '''

        # ── Zane chat (managers only) ──
        zane_chat_html = ""
        if is_manager:
            zane_chat_html = '''
    <div style="margin-bottom:25px;">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <span style="font-size:18px;font-weight:600;color:var(--text);">Ask Zane</span>
            <span style="color:var(--text-muted);font-size:13px;">Ask anything about your business</span>
        </div>
        <div id="pulseZaneChips" style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;">
            <button onclick="pulseAsk(&#39;Who owes me the most money?&#39;)" class="pz-chip">Who owes me?</button>
            <button onclick="pulseAsk(&#39;How does my cash flow look?&#39;)" class="pz-chip">Cash flow</button>
            <button onclick="pulseAsk(&#39;What stock do I need to reorder urgently?&#39;)" class="pz-chip">Reorder stock</button>
            <button onclick="pulseAsk(&#39;Are my margins healthy for my type of business?&#39;)" class="pz-chip">Margins</button>
            <button onclick="pulseAsk(&#39;What can I deduct from SARS?&#39;)" class="pz-chip">SARS deductions</button>
        </div>
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:20px;">
            <input type="text" id="pulseZaneInput" placeholder="Ask anything about your business..."
                   onkeypress="if(event.key===&#39;Enter&#39;)pulseSendZane()"
                   style="flex:1;padding:14px 18px;border-radius:10px;border:1px solid rgba(139,92,246,0.3);background:rgba(255,255,255,0.05);color:var(--text);font-size:16px;outline:none;">
            <button onclick="pulseSendZane()" id="pulseZaneSendBtn" style="padding:14px 28px;background:#8b5cf6;color:white;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:600;">Send</button>
        </div>
        <div id="pulseZaneArea"></div>
    </div>
        '''

        content = f'''
    <div style="margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <h1 style="margin:0;font-size:28px;">Business Pulse</h1>
                <p style="color:var(--text-muted);margin:5px 0 0 0;">{biz_name} &bull; {today()}</p>
            </div>
            <div style="text-align:right;">
                <button onclick="loadPulseData(true)" id="pulseRefreshBtn" style="background:rgba(16,185,129,0.2);border:1px solid rgba(16,185,129,0.3);color:#10b981;padding:8px 16px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:bold;">&#8635; Refresh Now</button>
                <div id="pulseLastUpdate" style="color:var(--text-muted);font-size:11px;margin-top:4px;">
                    <span style="display:inline-block;width:8px;height:8px;background:#10b981;border-radius:50%;margin-right:4px;animation:livePulse 2s infinite;"></span>Live &bull; updates every 30s
                </div>
            </div>
        </div>
    </div>

    <!-- Hide popup Zane on Pulse -->
    <style>.zane-chat {{ display:none !important; }}</style>

    <style>
    @keyframes livePulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.3; }} }}
    </style>

    <style>
    @media (max-width: 768px) {{
        #assistantCards {{ grid-template-columns: 1fr !important; }}
        .pulse-grid {{ grid-template-columns: 1fr !important; }}
    }}
    .pulse-loading {{
        text-align: center;
        padding: 20px;
        color: var(--text-muted);
    }}
    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>

    <div id="assistantCards" style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;">
        <!-- REMINDERS -->
        <div class="card" style="border:1px solid rgba(251,191,36,0.3);margin:0;padding:15px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <h3 style="margin:0;color:#fbbf24;font-size:16px;">&#128276; Reminders <span id="reminderBadge" style="background:#ef4444;color:white;padding:2px 8px;border-radius:10px;font-size:11px;display:none;margin-left:6px;">0</span></h3>
                <button onclick="quickZane('show my reminders')" style="font-size:11px;padding:3px 8px;background:rgba(251,191,36,0.2);border:1px solid rgba(251,191,36,0.3);color:#fbbf24;border-radius:4px;cursor:pointer;">+ Ask Zane</button>
            </div>
            <div id="reminderList" style="max-height:250px;overflow-y:auto;">
                <div style="text-align:center;padding:15px;color:var(--text-muted);font-size:13px;">Loading...</div>
            </div>
        </div>
        <!-- TO-DO -->
        <div class="card" style="border:1px solid rgba(99,102,241,0.3);margin:0;padding:15px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <h3 style="margin:0;color:#6366f1;font-size:16px;">&#128203; To-Do <span id="todoBadge" style="background:#6366f1;color:white;padding:2px 8px;border-radius:10px;font-size:11px;display:none;margin-left:6px;">0</span></h3>
                <button onclick="quickZane('show my to-do list')" style="font-size:11px;padding:3px 8px;background:rgba(99,102,241,0.2);border:1px solid rgba(99,102,241,0.3);color:#6366f1;border-radius:4px;cursor:pointer;">+ Ask Zane</button>
            </div>
            <div id="todoList" style="max-height:250px;overflow-y:auto;">
                <div style="text-align:center;padding:15px;color:var(--text-muted);font-size:13px;">Loading...</div>
            </div>
        </div>
    </div>

    <!-- ZANE'S BRIEFING -->
    <div id="briefingContainer" class="card" style="background:linear-gradient(135deg, rgba(139,92,246,0.15), rgba(99,102,241,0.1));border:1px solid rgba(139,92,246,0.3);margin-bottom:25px;min-height:150px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:15px;">
            <div>
                <h3 style="margin:0;color:#8b5cf6;">&#129302; Zane's Catch-up</h3>
                <span id="briefingDate" style="color:var(--text-muted);font-size:12px;">Loading...</span>
            </div>
            <button onclick="generateBriefing(true)" id="refreshBtn" style="background:rgba(139,92,246,0.2);border:1px solid rgba(139,92,246,0.3);color:#8b5cf6;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px;">&#8635; Refresh</button>
        </div>
        <div id="briefingContent" style="color:var(--text);line-height:1.8;font-size:14px;">
            <div style="text-align:center;padding:30px;">
                <div style="border:3px solid rgba(139,92,246,0.3);border-top:3px solid #8b5cf6;border-radius:50%;width:30px;height:30px;animation:spin 1s linear infinite;margin:0 auto 15px;"></div>
                <p style="color:var(--text-muted);margin:0;">Zane is catching up on what happened...</p>
            </div>
        </div>
    </div>

    {zane_chat_html}

    <!-- TODAY'S SNAPSHOT -->
    <div class="stats-grid" style="margin-bottom:15px;">
        <div class="stat-card" style="background:linear-gradient(135deg, rgba(16,185,129,0.3), rgba(16,185,129,0.1));">
            <div class="stat-value" style="color:#10b981;" id="pulseTodayPayments">...</div>
            <div class="stat-label">Received Today</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="pulseTodaySales">...</div>
            <div class="stat-label">POS Sales Today</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="pulseTodayInvoiced">...</div>
            <div class="stat-label">Invoiced Today</div>
        </div>
        <div class="stat-card" style="background:linear-gradient(135deg, rgba(99,102,241,0.2), rgba(99,102,241,0.05));">
            <div class="stat-value" id="pulseWeekTotal">...</div>
            <div class="stat-label">This Week</div>
        </div>
    </div>

    <!-- CASH POSITION -->
    <div class="stats-grid" style="margin-bottom:15px;">
        <div class="stat-card" style="background:linear-gradient(135deg, rgba(16,185,129,0.2), rgba(16,185,129,0.05));">
            <div class="stat-value" style="color:#10b981;" id="pulseOwedToYou">...</div>
            <div class="stat-label">Owed TO You</div>
        </div>
        <div class="stat-card" style="background:linear-gradient(135deg, rgba(239,68,68,0.2), rgba(239,68,68,0.05));">
            <div class="stat-value" style="color:#ef4444;" id="pulseYouOwe">...</div>
            <div class="stat-label">You OWE</div>
        </div>
        <div class="stat-card" style="background:linear-gradient(135deg, rgba(239,68,68,0.3), rgba(239,68,68,0.1));">
            <div class="stat-value" style="color:#ef4444;" id="pulseDangerTotal">...</div>
            <div class="stat-label">90+ Days Risk</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#f97316;" id="pulseOpenInvoices">...</div>
            <div class="stat-label">Open Invoices</div>
        </div>
    </div>

    <!-- NEW ROW: Expenses + Bank today -->
    <div class="stats-grid" style="margin-bottom:25px;">
        <div class="stat-card">
            <div class="stat-value" style="color:#f43f5e;" id="pulseTodayExpenses">...</div>
            <div class="stat-label">Expenses Today</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#06b6d4;" id="pulseBankTxns">...</div>
            <div class="stat-label">Bank Txns Today</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#8b5cf6;" id="pulseTimesheetHrs">...</div>
            <div class="stat-label">Timesheet Hrs Today</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#14b8a6;" id="pulseCashUps">...</div>
            <div class="stat-label">Cash-Ups Today</div>
        </div>
    </div>

    <div class="pulse-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">

        <!-- LEFT COLUMN: DEBTORS -->
        <div>
            <div class="card" style="border:2px solid rgba(239,68,68,0.5);margin-bottom:20px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                    <h3 style="margin:0;color:#ef4444;">DANGER ZONE (90+ days)</h3>
                    <span style="background:#ef4444;color:white;padding:4px 12px;border-radius:20px;font-weight:bold;" id="pulseDangerCount">-</span>
                </div>
                <div id="pulseDangerList"><div class="pulse-loading">Loading...</div></div>
            </div>

            <div class="card" style="border:1px solid rgba(249,115,22,0.3);margin-bottom:20px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <h3 style="margin:0;color:#f97316;">WARNING (60-90 days)</h3>
                    <span style="background:#f97316;color:white;padding:3px 10px;border-radius:15px;font-size:13px;" id="pulseWarningCount">-</span>
                </div>
                <div id="pulseWarningList"><div class="pulse-loading">Loading...</div></div>
            </div>

            <div class="card" style="border:1px solid rgba(234,179,8,0.2);margin-bottom:20px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <h3 style="margin:0;color:#eab308;font-size:16px;">Watch (30-60 days)</h3>
                    <span style="color:#eab308;font-size:13px;" id="pulseWatchInfo">-</span>
                </div>
                <div id="pulseWatchList"><div class="pulse-loading">Loading...</div></div>
            </div>

            <!-- OVERDUE INVOICES - Per-Invoice Detail -->
            <div class="card" style="border:1px solid rgba(239,68,68,0.3);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <h3 style="margin:0;color:#ef4444;font-size:16px;">&#128196; Overdue Invoices (Detail)</h3>
                    <span style="color:#ef4444;font-size:13px;" id="pulseOverdueInfo">-</span>
                </div>
                <div id="pulseOverdueList"><div class="pulse-loading">Loading...</div></div>
            </div>
        </div>

        <!-- RIGHT COLUMN: ACTIVITY -->
        <div>
            <div class="card" style="margin-bottom:20px;border:1px solid rgba(139,92,246,0.3);">
                <h3 style="margin:0 0 15px 0;color:#8b5cf6;">&#128100; Staff Activity Today</h3>
                <div id="pulseTeamActivity"><div class="pulse-loading">Loading...</div></div>
            </div>

            <div class="card" style="margin-bottom:20px;border:1px solid rgba(16,185,129,0.3);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                    <h3 style="margin:0;color:#10b981;">&#9889; Live Feed — Wie het wat gedoen</h3>
                    <span style="color:var(--text-muted);font-size:11px;">Laaste 7 dae</span>
                </div>
                <div id="pulseRecentActivity"><div class="pulse-loading">Loading...</div></div>
            </div>

            <div class="card" style="margin-bottom:20px;">
                <h3 style="margin:0 0 15px 0;">Stock Alerts</h3>
                <div id="pulseStockAlerts"><div class="pulse-loading">Loading...</div></div>
            </div>

            <div class="card" style="background:linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.05));">
                <h3 style="margin:0 0 15px 0;">Quick Actions</h3>
                <div style="display:flex;flex-direction:column;gap:10px;">
                    <a href="/reports/aging" class="btn btn-secondary" style="text-align:center;">View Full Aging Report</a>
                    <a href="/customers" class="btn btn-secondary" style="text-align:center;">Manage Customers</a>
                    <a href="/stock" class="btn btn-secondary" style="text-align:center;">Manage Stock</a>
                    <a href="/pos" class="btn btn-primary" style="text-align:center;">Open POS</a>
                </div>
            </div>
        </div>
    </div>

    <style>
        .pz-chip {{
            font-size:12px;padding:6px 14px;background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.2);
            color:#a78bfa;border-radius:20px;cursor:pointer;white-space:nowrap;transition:all 0.2s;
        }}
        .pz-chip:hover {{ background:rgba(139,92,246,0.25); }}
        .pz-q {{ color:var(--text-muted);font-size:14px;margin-bottom:8px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05); }}
        .pz-a {{ color:var(--text);font-size:15px;line-height:1.8;padding:20px 0 30px 0;border-bottom:1px solid rgba(255,255,255,0.05); }}
        .pz-a table {{ border-collapse:collapse;margin:10px 0; }}
        .pz-a td, .pz-a th {{ padding:6px 12px;border:1px solid rgba(255,255,255,0.1);text-align:left; }}
        .pz-a th {{ background:rgba(139,92,246,0.1); }}
        .pz-a strong {{ color:#a78bfa; }}
        .pz-a h2, .pz-a h3 {{ color:#a78bfa;margin-top:15px; }}
        .pz-loading {{ color:var(--text-muted);font-size:14px;padding:15px 0; }}
        .pz-loading span {{ display:inline-block; animation:pzpulse 1.5s infinite; }}
        @keyframes pzpulse {{ 0%,100% {{ opacity:0.4; }} 50% {{ opacity:1; }} }}
        #pulseZaneInput:focus {{ border-color:#8b5cf6;box-shadow:0 0 0 2px rgba(139,92,246,0.15); }}
    </style>

    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        loadPulseData(false);
        loadAssistantItems();
        generateBriefing(false);

        // AUTO-REFRESH every 30 seconds
        setInterval(function() {{
            loadPulseData(false);
            loadAssistantItems();
        }}, 30000);
    }});

    // ═══════════════════════════════════════════════════
    // PULSE DATA — Load all stats via AJAX
    // ═══════════════════════════════════════════════════
    async function loadPulseData(force) {{
        try {{
            const res = await fetch('/api/pulse/data', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{force: force}})
            }});
            const d = await res.json();
            if (!d.success) return;

            // Stat cards — row 1
            document.getElementById('pulseTodayPayments').textContent = d.today_payments || 'R0.00';
            document.getElementById('pulseTodaySales').textContent = d.today_sales || 'R0.00';
            document.getElementById('pulseTodayInvoiced').textContent = d.today_invoiced || 'R0.00';
            document.getElementById('pulseWeekTotal').textContent = d.week_total || 'R0.00';

            // Stat cards — row 2
            document.getElementById('pulseOwedToYou').textContent = d.owed_to_you || 'R0.00';
            document.getElementById('pulseYouOwe').textContent = d.you_owe || 'R0.00';
            document.getElementById('pulseDangerTotal').textContent = d.danger_total || 'R0.00';
            document.getElementById('pulseOpenInvoices').textContent = d.open_invoices || '0';

            // Stat cards — row 3 (NEW)
            document.getElementById('pulseTodayExpenses').textContent = d.today_expenses || 'R0.00';
            document.getElementById('pulseBankTxns').textContent = d.today_bank_txns || '0';
            document.getElementById('pulseTimesheetHrs').textContent = d.today_timesheet_hrs || '0h';
            document.getElementById('pulseCashUps').textContent = d.today_cashups || '0';

            // Aging zones
            document.getElementById('pulseDangerCount').textContent = d.danger_count || '0';
            document.getElementById('pulseDangerList').innerHTML = d.danger_html || '<div style="padding:20px;text-align:center;color:var(--text-muted);">No accounts over 90 days</div>';
            document.getElementById('pulseWarningCount').textContent = d.warning_count || '0';
            document.getElementById('pulseWarningList').innerHTML = d.warning_html || '<div style="padding:15px;text-align:center;color:var(--text-muted);font-size:13px;">No accounts 60-90 days</div>';
            document.getElementById('pulseWatchInfo').textContent = d.watch_info || '-';
            document.getElementById('pulseWatchList').innerHTML = d.watch_html || '<div style="padding:15px;text-align:center;color:var(--text-muted);font-size:13px;">No accounts 30-60 days</div>';

            // Overdue invoice detail (NEW)
            document.getElementById('pulseOverdueInfo').textContent = d.overdue_info || '-';
            document.getElementById('pulseOverdueList').innerHTML = d.overdue_html || '<div style="padding:15px;text-align:center;color:var(--text-muted);font-size:13px;">No overdue invoices</div>';

            // Team & Activity
            document.getElementById('pulseTeamActivity').innerHTML = d.team_html || '<div style="padding:15px;text-align:center;color:var(--text-muted);font-size:13px;">No team activity today</div>';
            document.getElementById('pulseRecentActivity').innerHTML = d.activity_html || '<div style="padding:20px;text-align:center;color:var(--text-muted);">No recent activity</div>';
            document.getElementById('pulseStockAlerts').innerHTML = d.stock_html || '<div style="padding:20px;text-align:center;color:var(--green);">Stock looking good!</div>';

            // Timestamp
            const now = new Date();
            const timeStr = now.toLocaleTimeString('en-ZA', {{hour:'2-digit', minute:'2-digit', second:'2-digit'}});
            const el = document.getElementById('pulseLastUpdate');
            if (el) el.innerHTML = '<span style="display:inline-block;width:8px;height:8px;background:#10b981;border-radius:50%;margin-right:4px;animation:livePulse 2s infinite;"></span>Updated ' + timeStr + ' &bull; ' + (d.compiled_in || '') + ' &bull; next in 30s';

        }} catch(e) {{
            console.error('Pulse data error:', e);
        }}
    }}

    // ═══════════════════════════════════════════════════
    // ASSISTANT CARDS
    // ═══════════════════════════════════════════════════
    async function loadAssistantItems() {{
        try {{
            const res = await fetch('/api/assistant/items');
            const data = await res.json();
            if (!data.success) return;

            const reminders = data.reminders || [];
            const reminderList = document.getElementById('reminderList');
            const reminderBadge = document.getElementById('reminderBadge');

            if (reminders.length > 0) {{
                reminderBadge.style.display = 'inline';
                reminderBadge.textContent = reminders.length;
                reminderList.innerHTML = reminders.map(r => {{
                    const isOverdue = r.is_overdue;
                    const borderColor = isOverdue ? '#ef4444' : '#fbbf24';
                    return `<div style="padding:10px;background:rgba(251,191,36,0.08);border-radius:6px;margin-bottom:6px;border-left:3px solid ${{borderColor}};">
                        <div style="display:flex;justify-content:space-between;">
                            <span style="font-size:13px;color:#fff;">${{r.title}}</span>
                            <button onclick="completeReminder('${{r.id}}')" style="font-size:10px;padding:2px 6px;background:rgba(16,185,129,0.3);border:1px solid rgba(16,185,129,0.3);color:#10b981;border-radius:3px;cursor:pointer;">&#10003;</button>
                        </div>
                        <div style="font-size:11px;color:${{isOverdue ? '#ef4444' : 'var(--text-muted)'}};margin-top:4px;">
                            ${{isOverdue ? '&#9888;&#65039; OVERDUE - ' : ''}}${{r.due_display}}
                        </div>
                    </div>`;
                }}).join('');
            }} else {{
                reminderList.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted);font-size:13px;">No pending reminders</div>';
            }}

            const todos = data.todos || [];
            const todoList = document.getElementById('todoList');
            const todoBadge = document.getElementById('todoBadge');

            if (todos.length > 0) {{
                todoBadge.style.display = 'inline';
                todoBadge.textContent = todos.length;
                todoList.innerHTML = todos.map(t => {{
                    const priorityColors = {{'high': '#ef4444', 'medium': '#f59e0b', 'low': '#6366f1'}};
                    const pColor = priorityColors[t.priority] || '#6366f1';
                    return `<div style="padding:10px;background:rgba(99,102,241,0.08);border-radius:6px;margin-bottom:6px;border-left:3px solid ${{pColor}};">
                        <div style="display:flex;justify-content:space-between;">
                            <span style="font-size:13px;color:#fff;">${{t.title}}</span>
                            <button onclick="completeTodo('${{t.id}}')" style="font-size:10px;padding:2px 6px;background:rgba(16,185,129,0.3);border:1px solid rgba(16,185,129,0.3);color:#10b981;border-radius:3px;cursor:pointer;">&#10003;</button>
                        </div>
                        <div style="font-size:11px;color:var(--text-muted);margin-top:3px;">${{t.priority}} priority${{t.due_display ? ' &bull; ' + t.due_display : ''}}</div>
                    </div>`;
                }}).join('');
            }} else {{
                todoList.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted);font-size:13px;">All done! &#128640;</div>';
            }}
        }} catch(e) {{
            console.error('Assistant items error:', e);
        }}
    }}

    async function completeReminder(id) {{
        await fetch('/api/assistant/toggle', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{id: id, type: 'reminder'}})
        }});
        loadAssistantItems();
    }}

    async function completeTodo(id) {{
        await fetch('/api/assistant/toggle', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{id: id, type: 'todo'}})
        }});
        loadAssistantItems();
    }}

    // ═══════════════════════════════════════════════════
    // BRIEFING
    // ═══════════════════════════════════════════════════
    async function generateBriefing(force) {{
        const content = document.getElementById('briefingContent');
        const dateEl = document.getElementById('briefingDate');
        const refreshBtn = document.getElementById('refreshBtn');

        if (force) {{
            refreshBtn.innerHTML = '&#8987; Generating...';
            refreshBtn.disabled = true;
            loadPulseData(true);
        }}

        try {{
            const res = await fetch('/api/briefing/generate', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{force: force}})
            }});
            const data = await res.json();

            if (data.success && data.generating) {{
                content.innerHTML = '<div style="text-align:center;padding:20px;"><div style="border:3px solid rgba(139,92,246,0.3);border-top:3px solid #8b5cf6;border-radius:50%;width:25px;height:25px;animation:spin 1s linear infinite;margin:0 auto 10px;"></div><p style="color:var(--text-muted);margin:0;font-size:13px;">Zane is catching up on what happened...</p></div>';
                dateEl.textContent = 'Generating...';
                let tries = 0;
                const poll = setInterval(async () => {{
                    tries++;
                    if (tries > 20) {{
                        clearInterval(poll);
                        content.innerHTML = '<div style="color:var(--text-muted);padding:10px;">Briefing is taking long — refresh the page to try again.</div>';
                        refreshBtn.innerHTML = '&#8635; Refresh';
                        refreshBtn.disabled = false;
                        return;
                    }}
                    try {{
                        const r2 = await fetch('/api/briefing/generate', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{force: false}})
                        }});
                        const d2 = await r2.json();
                        if (d2.success && !d2.generating && d2.briefing) {{
                            clearInterval(poll);
                            let html = (d2.briefing || '')
                                .replace(/\\n\\n/g, '<br><br>')
                                .replace(/\\n/g, '<br>')
                                .replace(/[*][*]([^*]+)[*][*]/g, '<b style="color:#8b5cf6;">$1</b>');
                            content.innerHTML = html;
                            dateEl.textContent = 'Fresh &bull; just generated';
                            refreshBtn.innerHTML = '&#8635; Refresh';
                            refreshBtn.disabled = false;
                        }}
                    }} catch(e) {{}}
                }}, 3000);
            }} else if (data.success) {{
                let html = (data.briefing || 'No briefing available.')
                    .replace(/\\n\\n/g, '<br><br>')
                    .replace(/\\n/g, '<br>')
                    .replace(/[*][*]([^*]+)[*][*]/g, '<b style="color:#8b5cf6;">$1</b>');
                content.innerHTML = html;
                if (data.cached) {{
                    dateEl.textContent = 'Cached from ' + (data.generated_at || 'earlier today');
                }} else {{
                    dateEl.textContent = 'Fresh &bull; just generated';
                }}
            }} else {{
                content.innerHTML = '<div style="color:var(--text-muted);padding:10px;">Could not generate briefing: ' + (data.error || 'unknown error') + '</div>';
            }}
        }} catch(e) {{
            content.innerHTML = '<div style="color:var(--text-muted);padding:10px;">Briefing unavailable</div>';
        }}

        refreshBtn.innerHTML = '&#8635; Refresh';
        refreshBtn.disabled = false;
    }}

    function quickZane(msg) {{ pulseAsk(msg); }}

    function pulseAsk(msg) {{
        const input = document.getElementById('pulseZaneInput');
        if (input) {{ input.value = msg; }}
        pulseSendZane();
    }}
    {pulse_md_to_html_js}
    async function pulseSendZane() {{
        const input = document.getElementById('pulseZaneInput');
        const area = document.getElementById('pulseZaneArea');
        const btn = document.getElementById('pulseZaneSendBtn');
        const msg = input.value.trim();
        if (!msg) return;

        const chips = document.getElementById('pulseZaneChips');
        if (chips) chips.style.display = 'none';

        area.innerHTML += '<div class="pz-q"><strong>You:</strong> ' + msg.replace(/</g,'&lt;') + '</div>';

        input.value = '';
        input.disabled = true;
        btn.disabled = true;
        btn.textContent = '...';

        area.innerHTML += '<div class="pz-loading" id="pzThinking"><span>Zane is thinking...</span></div>';
        document.getElementById('pzThinking').scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});

        try {{
            const response = await fetch('/api/ai', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ command: msg, current_page: '/pulse' }})
            }});

            const data = await response.json();
            const el = document.getElementById('pzThinking');
            if (el) el.remove();

            const reply = data.response || data.error || 'Sorry, something went wrong.';
            const div = document.createElement('div');
            div.className = 'pz-a';
            div.innerHTML = mdToHtml(reply);
            area.appendChild(div);
            div.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }} catch(e) {{
            const el = document.getElementById('pzThinking');
            if (el) el.remove();
            area.innerHTML += '<div class="pz-a" style="color:#ef4444;">Could not reach Zane — check your internet connection.</div>';
        }}

        input.disabled = false;
        btn.disabled = false;
        btn.textContent = 'Send';
        input.focus();
    }}
    </script>
    '''

        # JARVIS HUD
        if has_reactor_hud():
            _hud = jarvis_hud_header(
                page_name="BUSINESS PULSE",
                page_count="AI-POWERED INSIGHTS",
                left_items=[
                    ("ANALYSIS", "AI", "p", "", ""),
                    ("TRENDS", "LIVE", "g", "g", ""),
                    ("KPIs", "ACTIVE", "c", "", ""),
                    ("FORECAST", "READY", "o", "", ""),
                ],
                right_items=[
                    ("HEALTH", "SCANNING", "g", "g", ""),
                    ("RISKS", "MONITORED", "r", "", ""),
                    ("GROWTH", "TRACKING", "g", "g", "g"),
                    ("ZANE", "ONLINE", "c", "", ""),
                ],
                reactor_size="page",
                alert_html=""
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline("PULSE <b>AI ACTIVE</b>")

        return render_page("Business Pulse", content, user, "pulse")

    # ─────────────────────────────────────────────────────────
    # PULSE DATA API — All dashboard stats compiled here
    # ─────────────────────────────────────────────────────────
    @app.route("/api/pulse/data", methods=["POST"])
    @login_required
    def api_pulse_data():
        """Compile all Pulse dashboard data. Cached 25s per business."""
        global _pulse_cache
        from flask import request, jsonify

        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None

            if not biz_id:
                return jsonify({"success": False, "error": "No business"})

            force = request.json.get("force", False) if request.is_json else False

            # Cache check (25s TTL)
            cache_key = biz_id
            if not force and cache_key in _pulse_cache:
                cached = _pulse_cache[cache_key]
                age = time.time() - cached.get("ts", 0)
                if age < 25:
                    logger.info(f"[PULSE] Cache hit ({age:.0f}s old)")
                    return jsonify(cached["data"])

            logger.info(f"[PULSE] Compiling {'FRESH (forced)' if force else 'NEW'} data")
            _start = time.time()

            today_str = today()
            today_date = datetime.now().date()
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            week_ago_str = (today_date - timedelta(days=7)).strftime("%Y-%m-%d")

            # ── PARALLEL DATA LOAD (all tables) ──
            pool = ThreadPoolExecutor(max_workers=16)
            try:
                f_invoices = pool.submit(db.get, "invoices", {"business_id": biz_id})
                f_sales = pool.submit(db.get, "sales", {"business_id": biz_id})
                f_payments = pool.submit(db.get, "payments", {"business_id": biz_id})
                f_quotes = pool.submit(db.get, "quotes", {"business_id": biz_id})
                f_suppliers = pool.submit(db.get, "suppliers", {"business_id": biz_id})
                f_stock = pool.submit(db.get_all_stock, biz_id)
                f_users = pool.submit(db.get_business_users, biz_id)
                f_credit_notes = pool.submit(db.get, "credit_notes", {"business_id": biz_id})
                f_delivery_notes = pool.submit(db.get, "delivery_notes", {"business_id": biz_id})
                f_purchase_orders = pool.submit(db.get, "purchase_orders", {"business_id": biz_id})
                f_jobs = pool.submit(db.get, "jobs", {"business_id": biz_id})
                f_grvs = pool.submit(db.get, "goods_received", {"business_id": biz_id})
                # NEW data sources
                f_expenses = pool.submit(db.get, "expenses", {"business_id": biz_id})
                f_bank_txns = pool.submit(db.get, "bank_transactions", {"business_id": biz_id})
                f_cashups = pool.submit(db.get, "cash_ups", {"business_id": biz_id})
                f_timesheets = pool.submit(db.get, "timesheet_entries", {"business_id": biz_id})
                # Additional activity sources
                f_journals = pool.submit(db.get, "journals", {"business_id": biz_id})
                f_scan_inbox = pool.submit(db.get, "scanned_documents", {"business_id": biz_id})
                f_stock_moves = pool.submit(db.get, "stock_movements", {"business_id": biz_id})
                f_supplier_payments = pool.submit(db.get, "supplier_payments", {"business_id": biz_id})

                def _safe(future, label=""):
                    try:
                        return future.result(timeout=20) or []
                    except Exception as e:
                        logger.warning(f"[PULSE] {label} fetch failed: {e}")
                        return []

                invoices = _safe(f_invoices, "invoices")
                sales = _safe(f_sales, "sales")
                payments = _safe(f_payments, "payments")
                quotes = _safe(f_quotes, "quotes")
                suppliers = _safe(f_suppliers, "suppliers")
                stock = _safe(f_stock, "stock")
                credit_notes = _safe(f_credit_notes, "credit_notes")
                delivery_notes = _safe(f_delivery_notes, "delivery_notes")
                purchase_orders = _safe(f_purchase_orders, "purchase_orders")
                jobs_list = _safe(f_jobs, "jobs")
                grvs = _safe(f_grvs, "grvs")
                expenses = _safe(f_expenses, "expenses")
                bank_txns = _safe(f_bank_txns, "bank_transactions")
                cashups = _safe(f_cashups, "cash_ups")
                timesheets = _safe(f_timesheets, "timesheet_entries")
                journals = _safe(f_journals, "journals")
                scan_docs = _safe(f_scan_inbox, "scanned_documents")
                stock_moves = _safe(f_stock_moves, "stock_movements")
                supplier_payments = _safe(f_supplier_payments, "supplier_payments")

                try:
                    team_users = f_users.result(timeout=20) or []
                except Exception:
                    team_users = []
                    logger.warning("[PULSE] get_business_users timed out")
            finally:
                pool.shutdown(wait=False)

            user_names = {u.get("id"): (u.get("name") or u.get("email") or "Unknown") for u in team_users}
            logger.info(f"[PULSE] DB loaded in {time.time()-_start:.1f}s (parallel, {len(team_users)} users)")

            # ── Today's totals ──
            today_payments = sum(float(p.get("amount", 0)) for p in payments if str(p.get("date", ""))[:10] == today_str)
            today_invoiced = sum(float(inv.get("total", 0)) for inv in invoices if str(inv.get("date", ""))[:10] == today_str)
            today_sales_total = sum(float(s.get("total", 0)) for s in sales if str(s.get("date", ""))[:10] == today_str)

            # NEW: Today expenses
            today_expenses = sum(float(e.get("amount", e.get("total", 0)) or 0) for e in expenses if str(e.get("date", e.get("created_at", "")))[:10] == today_str)

            # NEW: Today bank transactions count
            today_bank_count = sum(1 for bt in bank_txns if str(bt.get("date", bt.get("created_at", "")))[:10] == today_str)

            # NEW: Today timesheet hours
            today_ts_hours = 0.0
            for ts in timesheets:
                ts_date = str(ts.get("date", ts.get("created_at", "")))[:10]
                if ts_date == today_str:
                    hrs = float(ts.get("hours", ts.get("total_hours", 0)) or 0)
                    today_ts_hours += hrs

            # NEW: Today cash-ups count
            today_cashup_count = sum(1 for cu in cashups if str(cu.get("date", cu.get("created_at", "")))[:10] == today_str)

            # This week
            week_sales = sum(float(s.get("total", 0) or 0) for s in sales if str(s.get("date", ""))[:10] >= week_ago_str)
            week_invoiced = sum(float(inv.get("total", 0) or 0) for inv in invoices if str(inv.get("date", ""))[:10] >= week_ago_str)

            # Cash position
            outstanding_invoices = [inv for inv in invoices if inv.get("status") != "paid"]
            total_owed_to_us = sum(float(inv.get("total", 0) or 0) for inv in outstanding_invoices)
            total_we_owe = sum(float(s.get("balance", 0) or 0) for s in suppliers)

            def fmt(amount):
                return f"R{amount:,.2f}"

            # ── AGING ANALYSIS (per-customer grouping) ──
            customer_aging = {}
            for inv in outstanding_invoices:
                cust_name = inv.get("customer_name", "Unknown")
                amount = float(inv.get("total", 0) or 0)
                try:
                    inv_date = datetime.strptime(str(inv.get("date", ""))[:10], "%Y-%m-%d").date()
                    days = (today_date - inv_date).days
                except Exception:
                    days = 0

                if cust_name not in customer_aging:
                    customer_aging[cust_name] = {"name": cust_name, "total": 0, "oldest_days": 0}
                customer_aging[cust_name]["total"] += amount
                customer_aging[cust_name]["oldest_days"] = max(customer_aging[cust_name]["oldest_days"], days)

            danger_zone = sorted([c for c in customer_aging.values() if c["oldest_days"] >= 90], key=lambda x: x["total"], reverse=True)
            warning_zone = sorted([c for c in customer_aging.values() if 60 <= c["oldest_days"] < 90], key=lambda x: x["total"], reverse=True)
            watch_zone = sorted([c for c in customer_aging.values() if 30 <= c["oldest_days"] < 60], key=lambda x: x["total"], reverse=True)

            danger_total = sum(c["total"] for c in danger_zone)
            watch_total = sum(c["total"] for c in watch_zone)

            # Danger HTML
            danger_html = ""
            for c in danger_zone[:10]:
                cname_safe = c["name"][:25].replace("'", "\\'").replace('"', "")
                danger_html += f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:12px;background:rgba(239,68,68,0.1);border-radius:8px;margin-bottom:8px;border-left:4px solid #ef4444;">
                    <div><strong style="color:#fff;">{c["name"][:25]}</strong><div style="color:#ef4444;font-size:12px;">{c["oldest_days"]} days overdue</div></div>
                    <div style="text-align:right;"><div style="color:#ef4444;font-weight:bold;font-size:18px;">{fmt(c["total"])}</div>
                    <button onclick="quickZane('Stuur herinnering aan {cname_safe}')" style="font-size:10px;padding:3px 8px;background:#ef4444;border:none;border-radius:4px;color:white;cursor:pointer;margin-top:4px;">&#128241; Herinner</button></div></div>'''

            # Warning HTML
            warning_html = ""
            for c in warning_zone[:10]:
                cname_safe = c["name"][:20].replace("'", "\\'").replace('"', "")
                warning_html += f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:10px;background:rgba(249,115,22,0.1);border-radius:6px;margin-bottom:6px;border-left:3px solid #f97316;">
                    <div><strong style="color:#fff;">{c["name"][:25]}</strong><span style="color:#f97316;font-size:11px;margin-left:8px;">{c["oldest_days"]}d</span></div>
                    <div style="display:flex;align-items:center;gap:8px;"><span style="color:#f97316;font-weight:bold;">{fmt(c["total"])}</span>
                    <button onclick="quickZane('Stuur herinnering aan {cname_safe}')" style="font-size:9px;padding:2px 6px;background:#f97316;border:none;border-radius:3px;color:white;cursor:pointer;">&#128241;</button></div></div>'''

            # Watch HTML
            watch_html = ""
            for c in watch_zone[:8]:
                watch_html += f'''<div style="display:flex;justify-content:space-between;padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">
                    <span style="color:#ccc;">{c["name"][:20]}</span><span style="color:#eab308;">{fmt(c["total"])}</span></div>'''

            # ── OVERDUE INVOICES — PER-INVOICE DETAIL (NEW) ──
            overdue_invoices = []
            for inv in outstanding_invoices:
                try:
                    inv_date = datetime.strptime(str(inv.get("date", ""))[:10], "%Y-%m-%d").date()
                    days = (today_date - inv_date).days
                except Exception:
                    days = 0
                if days >= 30:
                    overdue_invoices.append({
                        "invoice_number": inv.get("invoice_number", "?"),
                        "customer_name": inv.get("customer_name", "Unknown"),
                        "total": float(inv.get("total", 0) or 0),
                        "date": str(inv.get("date", ""))[:10],
                        "days": days,
                        "created_by": inv.get("created_by", ""),
                    })

            overdue_invoices.sort(key=lambda x: x["days"], reverse=True)
            overdue_total = sum(o["total"] for o in overdue_invoices)

            overdue_html = ""
            for o in overdue_invoices[:15]:
                who = user_names.get(o["created_by"], "")
                who_tag = f' <span style="color:var(--text-muted);font-size:10px;">by {who}</span>' if who else ""
                if o["days"] >= 90:
                    badge_color = "#ef4444"
                elif o["days"] >= 60:
                    badge_color = "#f97316"
                else:
                    badge_color = "#eab308"
                overdue_html += f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-left:3px solid {badge_color};margin-bottom:4px;background:rgba(255,255,255,0.02);border-radius:0 6px 6px 0;font-size:13px;">
                    <div>
                        <span style="color:{badge_color};font-weight:bold;">{o["invoice_number"]}</span>
                        <span style="color:#ccc;margin-left:6px;">{o["customer_name"][:20]}</span>{who_tag}
                        <div style="font-size:11px;color:var(--text-muted);">{o["date"]} &mdash; {o["days"]}d overdue</div>
                    </div>
                    <span style="color:{badge_color};font-weight:bold;white-space:nowrap;">{fmt(o["total"])}</span>
                </div>'''
            if len(overdue_invoices) > 15:
                overdue_html += f'<div style="text-align:center;color:var(--text-muted);font-size:12px;padding:8px;">+{len(overdue_invoices)-15} more overdue invoices</div>'

            # ── TEAM ACTIVITY (all 13+ transaction types, per user) ──
            team_data = {}

            def _ensure_team(uid):
                if uid not in team_data:
                    team_data[uid] = {
                        "name": user_names.get(uid, uid[:8] if uid else "System"),
                        "today": [], "yesterday": [],
                        "today_totals": {"invoices": 0, "quotes": 0, "sales": 0, "payments": 0,
                                         "credit_notes": 0, "delivery_notes": 0, "purchase_orders": 0,
                                         "jobs": 0, "grvs": 0, "expenses": 0, "bank_txns": 0,
                                         "cashups": 0, "timesheets": 0,
                                         "journals": 0, "scans": 0, "stock_moves": 0, "sup_payments": 0,
                                         "inv_amt": 0, "q_amt": 0, "s_amt": 0, "p_amt": 0,
                                         "cn_amt": 0, "dn_amt": 0, "po_amt": 0, "j_amt": 0,
                                         "grv_amt": 0, "exp_amt": 0, "bt_amt": 0, "cu_amt": 0,
                                         "ts_hrs": 0, "jnl_amt": 0, "sm_amt": 0, "sp_amt": 0},
                        "yesterday_totals": {"invoices": 0, "quotes": 0, "sales": 0, "payments": 0,
                                             "credit_notes": 0, "delivery_notes": 0, "purchase_orders": 0,
                                             "jobs": 0, "grvs": 0, "expenses": 0, "bank_txns": 0,
                                             "cashups": 0, "timesheets": 0,
                                             "journals": 0, "scans": 0, "stock_moves": 0, "sup_payments": 0,
                                             "inv_amt": 0, "q_amt": 0, "s_amt": 0, "p_amt": 0,
                                             "cn_amt": 0, "dn_amt": 0, "po_amt": 0, "j_amt": 0,
                                             "grv_amt": 0, "exp_amt": 0, "bt_amt": 0, "cu_amt": 0,
                                             "ts_hrs": 0, "jnl_amt": 0, "sm_amt": 0, "sp_amt": 0}
                    }

            # Ensure ALL team members show (even idle ones)
            for u in team_users:
                uid = u.get("id", "")
                if uid:
                    _ensure_team(uid)

            def _gather(records, date_field, uid_field, get_text, get_amount, icon, color, type_key, amt_key, extra_date_field=None):
                """Generic gatherer for any record type into team_data."""
                for rec in records:
                    rec_date = str(rec.get(date_field, rec.get(extra_date_field or "created_at", "")))[:10]
                    if rec_date not in (today_str, yesterday_str):
                        continue
                    uid = rec.get(uid_field) or rec.get("created_by") or "unknown"
                    _ensure_team(uid)
                    amt = get_amount(rec)
                    text = get_text(rec)
                    ts = str(rec.get("created_at", ""))
                    time_str = ts[11:16] if len(ts) > 16 else ""
                    action = {"time": time_str, "sort": ts, "icon": icon, "color": color, "text": text, "amount": amt}
                    day_key = "today" if rec_date == today_str else "yesterday"
                    team_data[uid][day_key].append(action)
                    team_data[uid][f"{day_key}_totals"][type_key] += 1
                    team_data[uid][f"{day_key}_totals"][amt_key] += amt

            # ── Gather all record types ──

            # Quotes
            _gather(quotes, "created_at", "created_by",
                    lambda q: f"Quote {q.get('quote_number', '')} vir {(q.get('customer_name', '') or 'Unknown')[:25]}",
                    lambda q: float(q.get("total", 0) or 0),
                    "&#128221;", "#f59e0b", "quotes", "q_amt")

            # Invoices
            _gather(invoices, "date", "created_by",
                    lambda i: f"Invoice {i.get('invoice_number', '')} vir {(i.get('customer_name', '') or 'Unknown')[:25]} ({i.get('status', 'draft')})",
                    lambda i: float(i.get("total", 0) or 0),
                    "&#128196;", "#3b82f6", "invoices", "inv_amt")

            # POS Sales
            _gather(sales, "date", "created_by",
                    lambda s: f"POS Sale ({s.get('payment_method', 'cash')}) {s.get('items_count', len(s.get('items', [])) if isinstance(s.get('items'), list) else '')} items",
                    lambda s: float(s.get("total", 0) or 0),
                    "&#128176;", "#10b981", "sales", "s_amt")

            # Payments
            _gather(payments, "date", "created_by",
                    lambda p: f"Betaling ontvang van {(p.get('customer_name', '') or 'Customer')[:25]} ({p.get('payment_method', '') or 'n/a'})",
                    lambda p: float(p.get("amount", 0) or 0),
                    "&#10003;", "#10b981", "payments", "p_amt")

            # Credit Notes
            _gather(credit_notes, "date", "created_by",
                    lambda cn: f"Credit Note {cn.get('credit_note_number', cn.get('number', ''))} vir {(cn.get('customer_name', '') or 'Unknown')[:25]} ({cn.get('reason', '') or 'no reason'})" if cn.get('reason') else f"Credit Note {cn.get('credit_note_number', cn.get('number', ''))} vir {(cn.get('customer_name', '') or 'Unknown')[:25]}",
                    lambda cn: float(cn.get("total", 0) or 0),
                    "&#9888;", "#ef4444", "credit_notes", "cn_amt", "created_at")

            # Delivery Notes
            _gather(delivery_notes, "date", "created_by",
                    lambda dn: f"Aflewering {dn.get('delivery_note_number', dn.get('number', ''))} na {(dn.get('customer_name', '') or 'Unknown')[:25]}",
                    lambda dn: float(dn.get("total", 0) or 0),
                    "&#128666;", "#8b5cf6", "delivery_notes", "dn_amt", "created_at")

            # Purchase Orders
            _gather(purchase_orders, "date", "created_by",
                    lambda po: f"Bestelling {po.get('po_number', po.get('number', ''))} aan {(po.get('supplier_name', '') or 'Unknown')[:25]} ({po.get('status', 'draft')})",
                    lambda po: float(po.get("total", 0) or 0),
                    "&#128230;", "#f97316", "purchase_orders", "po_amt", "created_at")

            # Job Cards
            _gather(jobs_list, "date", "created_by",
                    lambda j: f"Job {j.get('job_number', j.get('number', ''))} vir {(j.get('customer_name', '') or 'Unknown')[:25]}" + (f" — {j.get('status', '')}" if j.get("status") else ""),
                    lambda j: float(j.get("total", j.get("quoted_total", 0)) or 0),
                    "&#128295;", "#06b6d4", "jobs", "j_amt", "created_at")

            # GRVs
            _gather(grvs, "date", "created_by",
                    lambda g: f"GRV {g.get('grv_number', g.get('number', ''))} van {(g.get('supplier_name', '') or 'Unknown')[:25]} ontvang",
                    lambda g: float(g.get("total", 0) or 0),
                    "&#128230;", "#14b8a6", "grvs", "grv_amt", "created_at")

            # ── NEW: Expenses ──
            _gather(expenses, "date", "created_by",
                    lambda e: f"Uitgawe: {(e.get('description', e.get('category', '')) or 'Onbekend')[:30]}" + (f" ({e.get('supplier_name', '')[:20]})" if e.get('supplier_name') else ""),
                    lambda e: float(e.get("amount", e.get("total", 0)) or 0),
                    "&#128181;", "#f43f5e", "expenses", "exp_amt", "created_at")

            # ── NEW: Bank Transactions ──
            def _bank_text(bt):
                amt = float(bt.get("amount", 0) or 0)
                direction = "Inbetaling" if amt >= 0 else "Betaling uit"
                desc = (bt.get("description", bt.get("reference", "")) or "")[:30]
                return f"Bank {direction}: {desc}"

            _gather(bank_txns, "date", "created_by",
                    _bank_text,
                    lambda bt: abs(float(bt.get("amount", 0) or 0)),
                    "&#127974;", "#0ea5e9", "bank_txns", "bt_amt", "created_at")

            # ── NEW: Cash-Ups (rich detail) ──
            def _cashup_text(cu):
                cu_type = cu.get("type", cu.get("reading_type", "close"))
                cashier = cu.get("cashier_name", "") or ""
                sys_total = float(cu.get("system_total", 0) or 0)
                decl_total = float(cu.get("declared_total", 0) or 0)
                type_label = {"x_reading": "X-Read", "blind_cashup": "Blind Cash-Up", "z_reading": "Z-Close"}.get(cu_type, cu_type)

                if cu_type == "blind_cashup" and decl_total > 0:
                    diff = decl_total - sys_total
                    if abs(diff) < 0.01:
                        status = "&#10003; Balanced"
                    elif diff > 0:
                        status = f"&#9650; R{diff:.2f} over"
                    else:
                        status = f"&#9888; R{abs(diff):.2f} short"
                    return f"{type_label}: {cashier} declared R{decl_total:,.2f} {status}" if cashier else f"{type_label}: declared R{decl_total:,.2f} {status}"
                elif cu_type == "x_reading":
                    return f"{type_label}: R{sys_total:,.2f} so far" + (f" ({cashier})" if cashier else "")
                elif cu_type == "z_reading":
                    who = cu.get("created_by_name", "") or cashier or ""
                    return f"{type_label}: Day closed at R{sys_total:,.2f}" + (f" by {who}" if who else "")
                else:
                    return f"Cash-Up ({type_label}) R{sys_total:,.2f}" + (f" — {cashier}" if cashier else "")

            _gather(cashups, "date", "created_by",
                    _cashup_text,
                    lambda cu: float(cu.get("system_total", cu.get("declared_total", 0)) or 0),
                    "&#128176;", "#84cc16", "cashups", "cu_amt", "created_at")

            # ── Journals ──
            _gather(journals, "date", "created_by",
                    lambda j: f"Joernaal {j.get('journal_number', j.get('reference', ''))} — {(j.get('description', j.get('memo', '')) or 'Geen beskrywing')[:30]}",
                    lambda j: float(j.get("total", j.get("debit_total", 0)) or 0),
                    "&#128210;", "#7c3aed", "journals", "jnl_amt", "created_at")

            # ── Scanned Documents ──
            _gather(scan_docs, "created_at", "created_by",
                    lambda sd: f"Skandeer: {(sd.get('document_type', sd.get('type', '')) or 'dokument')} — {(sd.get('filename', sd.get('description', sd.get('supplier_name', ''))) or '')[:30]}" + (f" ({sd.get('status', '')})" if sd.get('status') else ""),
                    lambda sd: float(sd.get("total", sd.get("amount", 0)) or 0),
                    "&#128196;", "#ec4899", "scans", "sm_amt", "created_at")

            # ── Stock Movements ──
            _gather(stock_moves, "created_at", "created_by",
                    lambda sm: f"Voorraad {sm.get('movement_type', sm.get('type', 'adjustment'))}: {(sm.get('stock_code', sm.get('description', '')) or '')[:25]} qty {sm.get('quantity', sm.get('qty', 0))}",
                    lambda sm: abs(float(sm.get("value", sm.get("total", 0)) or 0)),
                    "&#128230;", "#d97706", "stock_moves", "sm_amt", "created_at")

            # ── Supplier Payments ──
            _gather(supplier_payments, "date", "created_by",
                    lambda sp: f"Betaal aan {(sp.get('supplier_name', '') or 'Verskaffer')[:25]} ({sp.get('payment_method', '') or 'n/a'})",
                    lambda sp: float(sp.get("amount", sp.get("total", 0)) or 0),
                    "&#128181;", "#dc2626", "sup_payments", "sp_amt", "created_at")

            # ── NEW: Timesheets (track hours not amount) ──
            for ts_entry in timesheets:
                ts_date = str(ts_entry.get("date", ts_entry.get("created_at", "")))[:10]
                if ts_date not in (today_str, yesterday_str):
                    continue
                uid = ts_entry.get("created_by") or ts_entry.get("employee_id") or "unknown"
                _ensure_team(uid)
                hrs = float(ts_entry.get("hours", ts_entry.get("total_hours", 0)) or 0)
                emp_name = (ts_entry.get("employee_name", "") or "")[:20]
                project = (ts_entry.get("project", ts_entry.get("task", ts_entry.get("description", ""))) or "")[:25]
                ts_ts = str(ts_entry.get("created_at", ""))
                time_str = ts_ts[11:16] if len(ts_ts) > 16 else ""
                text = f"Timesheet: {emp_name} {hrs:.1f}h" + (f" — {project}" if project else "")
                action = {"time": time_str, "sort": ts_ts, "icon": "&#128337;", "color": "#a855f7",
                          "text": text, "amount": 0}
                day_key = "today" if ts_date == today_str else "yesterday"
                team_data[uid][day_key].append(action)
                team_data[uid][f"{day_key}_totals"]["timesheets"] += 1
                team_data[uid][f"{day_key}_totals"]["ts_hrs"] += hrs

            # ── Build day summary helper ──
            def _day_summary(totals):
                parts = []
                if totals["invoices"]: parts.append(f'<span style="color:#3b82f6;">{totals["invoices"]} inv {fmt(totals["inv_amt"])}</span>')
                if totals["quotes"]: parts.append(f'<span style="color:#f59e0b;">{totals["quotes"]} quotes {fmt(totals["q_amt"])}</span>')
                if totals["sales"]: parts.append(f'<span style="color:#10b981;">{totals["sales"]} sales {fmt(totals["s_amt"])}</span>')
                if totals["payments"]: parts.append(f'<span style="color:#10b981;">{totals["payments"]} pay {fmt(totals["p_amt"])}</span>')
                if totals.get("credit_notes"): parts.append(f'<span style="color:#ef4444;">{totals["credit_notes"]} CN {fmt(totals["cn_amt"])}</span>')
                if totals.get("delivery_notes"): parts.append(f'<span style="color:#8b5cf6;">{totals["delivery_notes"]} DN {fmt(totals["dn_amt"])}</span>')
                if totals.get("purchase_orders"): parts.append(f'<span style="color:#f97316;">{totals["purchase_orders"]} PO {fmt(totals["po_amt"])}</span>')
                if totals.get("jobs"): parts.append(f'<span style="color:#06b6d4;">{totals["jobs"]} jobs {fmt(totals["j_amt"])}</span>')
                if totals.get("grvs"): parts.append(f'<span style="color:#14b8a6;">{totals["grvs"]} GRV {fmt(totals["grv_amt"])}</span>')
                if totals.get("expenses"): parts.append(f'<span style="color:#f43f5e;">{totals["expenses"]} exp {fmt(totals["exp_amt"])}</span>')
                if totals.get("bank_txns"): parts.append(f'<span style="color:#0ea5e9;">{totals["bank_txns"]} bank {fmt(totals["bt_amt"])}</span>')
                if totals.get("cashups"): parts.append(f'<span style="color:#84cc16;">{totals["cashups"]} cash-up</span>')
                if totals.get("timesheets"): parts.append(f'<span style="color:#a855f7;">{totals["timesheets"]} ts {totals["ts_hrs"]:.1f}h</span>')
                if totals.get("journals"): parts.append(f'<span style="color:#7c3aed;">{totals["journals"]} jnl {fmt(totals["jnl_amt"])}</span>')
                if totals.get("scans"): parts.append(f'<span style="color:#ec4899;">{totals["scans"]} scan</span>')
                if totals.get("stock_moves"): parts.append(f'<span style="color:#d97706;">{totals["stock_moves"]} stk mv</span>')
                if totals.get("sup_payments"): parts.append(f'<span style="color:#dc2626;">{totals["sup_payments"]} sup pay {fmt(totals["sp_amt"])}</span>')
                return " &bull; ".join(parts) if parts else '<span style="color:#ef4444;">No activity</span>'

            # ── Build action lines helper ──
            def _action_lines(actions):
                actions.sort(key=lambda x: x["sort"], reverse=True)
                html = ""
                for a in actions:
                    time_badge = f'<span style="color:var(--text-muted);font-size:11px;min-width:42px;display:inline-block;">{a["time"]}</span>' if a["time"] else ""
                    amt_str = fmt(a["amount"]) if a["amount"] else ""
                    html += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-left:3px solid {a["color"]};margin-bottom:3px;background:rgba(255,255,255,0.02);border-radius:0 4px 4px 0;font-size:12px;">'
                    html += f'<div>{time_badge} {a["icon"]} {a["text"]}</div>'
                    if amt_str:
                        html += f'<div style="color:{a["color"]};font-weight:bold;white-space:nowrap;margin-left:8px;">{amt_str}</div>'
                    html += '</div>'
                return html

            # ── Build team HTML ──
            team_html = ""
            sorted_team = sorted(team_data.items(), key=lambda x: len(x[1]["today"]) + len(x[1]["yesterday"]), reverse=True)

            for uid, data in sorted_team:
                name = data["name"] or uid[:8]
                if name == "System":
                    continue

                today_actions = data["today"]
                yesterday_actions = data["yesterday"]
                has_today = len(today_actions) > 0
                has_yesterday = len(yesterday_actions) > 0

                # Staff with NO activity at all
                if not has_today and not has_yesterday:
                    team_html += f'''<div style="padding:12px;background:rgba(239,68,68,0.08);border-radius:8px;margin-bottom:10px;border-left:4px solid #ef4444;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <div style="font-weight:bold;color:#ef4444;">&#128100; {name}</div>
                            <span style="color:#ef4444;font-size:12px;">&#9888; No activity today or yesterday</span>
                        </div>
                    </div>'''
                    continue

                border_color = "#10b981" if has_today else "#f97316"
                team_html += f'<div style="padding:12px;background:rgba(255,255,255,0.03);border-radius:8px;margin-bottom:10px;border-left:4px solid {border_color};">'
                team_html += f'<div style="font-weight:bold;color:white;margin-bottom:10px;">&#128100; {name}</div>'

                # TODAY
                if has_today:
                    today_total_amt = sum(data["today_totals"].get(k, 0) for k in ("inv_amt", "q_amt", "s_amt", "p_amt", "exp_amt", "bt_amt", "cu_amt"))
                    team_html += f'<div style="margin-bottom:8px;">'
                    team_html += f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid rgba(255,255,255,0.1);">'
                    team_html += f'<span style="color:#10b981;font-weight:bold;font-size:12px;">TODAY — {len(today_actions)} actions &bull; {fmt(today_total_amt)}</span>'
                    team_html += f'<span style="font-size:11px;">{_day_summary(data["today_totals"])}</span></div>'
                    team_html += f'<div style="max-height:180px;overflow-y:auto;">{_action_lines(today_actions)}</div></div>'
                else:
                    team_html += f'<div style="padding:8px;background:rgba(239,68,68,0.1);border-radius:6px;margin-bottom:8px;font-size:12px;color:#ef4444;">&#9888; No activity today yet</div>'

                # YESTERDAY (collapsed)
                if has_yesterday:
                    yesterday_total_amt = sum(data["yesterday_totals"].get(k, 0) for k in ("inv_amt", "q_amt", "s_amt", "p_amt", "exp_amt", "bt_amt", "cu_amt"))
                    collapse_id = f"yday_{uid[:8]}"
                    team_html += f'<div style="margin-top:4px;">'
                    team_html += f'<div onclick="var el=document.getElementById(\'{collapse_id}\');el.style.display=el.style.display===\'none\'?\'block\':\'none\';" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-top:1px solid rgba(255,255,255,0.05);">'
                    team_html += f'<span style="color:var(--text-muted);font-size:11px;">&#9660; YESTERDAY — {len(yesterday_actions)} actions &bull; {fmt(yesterday_total_amt)}</span>'
                    team_html += f'<span style="font-size:10px;color:var(--text-muted);">{_day_summary(data["yesterday_totals"])}</span></div>'
                    team_html += f'<div id="{collapse_id}" style="display:none;max-height:150px;overflow-y:auto;margin-top:4px;">{_action_lines(yesterday_actions)}</div></div>'

                team_html += '</div>'

            # ── RECENT ACTIVITY (ALL types, 7 days, with WHO) ──
            activity_html = ""
            activity_feed = []
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            def _add_activity(records, date_field, get_text, get_amount, icon, color, uid_field="created_by", extra_date_field=None):
                for rec in records:
                    rec_date = str(rec.get(date_field, rec.get(extra_date_field or "created_at", "")))[:10]
                    if rec_date >= seven_days_ago:
                        who = user_names.get(rec.get(uid_field, rec.get("created_by", "")), "")
                        if who:
                            who_tag = f'<strong style="color:#d1d5db;">{who}</strong> &mdash; '
                        else:
                            who_tag = ""
                        activity_feed.append({
                            "date": rec_date,
                            "time": extract_time(rec.get("created_at", "")),
                            "text": who_tag + get_text(rec),
                            "amount": get_amount(rec),
                            "icon": icon, "color": color
                        })

            _add_activity(payments, "date",
                          lambda p: f'Betaling ontvang van {(p.get("customer_name", "") or "Customer")[:20]} ({p.get("payment_method", "") or "n/a"})',
                          lambda p: float(p.get("amount", 0) or 0), "&#10003;", "#10b981")

            _add_activity(invoices, "date",
                          lambda i: f'Invoice {i.get("invoice_number", "")} vir {(i.get("customer_name", "") or "Unknown")[:20]} ({i.get("status", "draft")})',
                          lambda i: float(i.get("total", 0) or 0), "&#128196;", "#f59e0b")

            _add_activity(sales, "date",
                          lambda s: f'POS Sale ({s.get("payment_method", "cash")})',
                          lambda s: float(s.get("total", 0) or 0), "&#128176;", "#10b981")

            _add_activity(credit_notes, "date",
                          lambda cn: f'Credit Note {cn.get("credit_note_number", cn.get("number", ""))} vir {(cn.get("customer_name", "") or "Unknown")[:20]}',
                          lambda cn: float(cn.get("total", 0) or 0), "&#9888;", "#ef4444", extra_date_field="created_at")

            _add_activity(delivery_notes, "date",
                          lambda dn: f'Aflewering {dn.get("delivery_note_number", dn.get("number", ""))} na {(dn.get("customer_name", "") or "Unknown")[:20]}',
                          lambda dn: float(dn.get("total", 0) or 0), "&#128666;", "#8b5cf6", extra_date_field="created_at")

            _add_activity(purchase_orders, "date",
                          lambda po: f'Bestelling {po.get("po_number", po.get("number", ""))} aan {(po.get("supplier_name", "") or "Unknown")[:20]} ({po.get("status", "draft")})',
                          lambda po: float(po.get("total", 0) or 0), "&#128230;", "#f97316", extra_date_field="created_at")

            _add_activity(jobs_list, "date",
                          lambda j: f'Job {j.get("job_number", j.get("number", ""))} vir {(j.get("customer_name", "") or "Unknown")[:20]}',
                          lambda j: float(j.get("total", j.get("quoted_total", 0)) or 0), "&#128295;", "#06b6d4", extra_date_field="created_at")

            _add_activity(grvs, "date",
                          lambda g: f'GRV {g.get("grv_number", g.get("number", ""))} van {(g.get("supplier_name", "") or "Unknown")[:20]} ontvang',
                          lambda g: float(g.get("total", 0) or 0), "&#128230;", "#14b8a6", extra_date_field="created_at")

            _add_activity(expenses, "date",
                          lambda e: f'Uitgawe: {(e.get("description", e.get("category", "")) or "Onbekend")[:25]}',
                          lambda e: float(e.get("amount", e.get("total", 0)) or 0), "&#128181;", "#f43f5e", extra_date_field="created_at")

            def _bank_activity_text(bt):
                amt = float(bt.get("amount", 0) or 0)
                direction = "Inbetaling" if amt >= 0 else "Betaling uit"
                desc = (bt.get("description", bt.get("reference", "")) or "")[:25]
                return f'Bank {direction}: {desc}'

            _add_activity(bank_txns, "date",
                          _bank_activity_text,
                          lambda bt: abs(float(bt.get("amount", 0) or 0)), "&#127974;", "#0ea5e9", extra_date_field="created_at")

            _add_activity(cashups, "date",
                          _cashup_text,
                          lambda cu: float(cu.get("system_total", cu.get("declared_total", 0)) or 0), "&#128176;", "#84cc16", extra_date_field="created_at")

            # Journals in activity feed
            _add_activity(journals, "date",
                          lambda j: f'Joernaal {j.get("journal_number", j.get("reference", ""))} — {(j.get("description", j.get("memo", "")) or "Geen beskrywing")[:25]}',
                          lambda j: float(j.get("total", j.get("debit_total", 0)) or 0), "&#128210;", "#7c3aed", extra_date_field="created_at")

            # Scanned documents in activity feed
            _add_activity(scan_docs, "created_at",
                          lambda sd: f'Skandeer: {(sd.get("document_type", sd.get("type", "")) or "dokument")} — {(sd.get("filename", sd.get("description", sd.get("supplier_name", ""))) or "")[:25]}',
                          lambda sd: float(sd.get("total", sd.get("amount", 0)) or 0), "&#128196;", "#ec4899", extra_date_field="created_at")

            # Stock movements in activity feed
            _add_activity(stock_moves, "created_at",
                          lambda sm: f'Voorraad {sm.get("movement_type", sm.get("type", "adjustment"))}: {(sm.get("stock_code", sm.get("description", "")) or "")[:20]} qty {sm.get("quantity", sm.get("qty", 0))}',
                          lambda sm: abs(float(sm.get("value", sm.get("total", 0)) or 0)), "&#128230;", "#d97706", extra_date_field="created_at")

            # Supplier payments in activity feed
            _add_activity(supplier_payments, "date",
                          lambda sp: f'Betaal aan {(sp.get("supplier_name", "") or "Verskaffer")[:20]} ({sp.get("payment_method", "") or "n/a"})',
                          lambda sp: float(sp.get("amount", sp.get("total", 0)) or 0), "&#128181;", "#dc2626", extra_date_field="created_at")

            # Timesheets in activity feed
            for ts_entry in timesheets:
                ts_date = str(ts_entry.get("date", ts_entry.get("created_at", "")))[:10]
                if ts_date >= seven_days_ago:
                    who = user_names.get(ts_entry.get("created_by", ts_entry.get("employee_id", "")), "")
                    emp_name = (ts_entry.get("employee_name", "") or "")[:20]
                    hrs = float(ts_entry.get("hours", ts_entry.get("total_hours", 0)) or 0)
                    project = (ts_entry.get("project", ts_entry.get("task", ts_entry.get("description", ""))) or "")[:25]
                    who_tag = f'<strong style="color:#d1d5db;">{who}</strong> &mdash; ' if who else ""
                    text = f"Timesheet: {emp_name} {hrs:.1f}h" + (f" — {project}" if project else "")
                    activity_feed.append({
                        "date": ts_date,
                        "time": extract_time(ts_entry.get("created_at", "")),
                        "text": who_tag + text,
                        "amount": 0,
                        "icon": "&#128337;", "color": "#a855f7"
                    })

            activity_feed.sort(key=lambda x: (x["date"], x["time"]), reverse=True)

            today_acts = [a for a in activity_feed if a["date"] == today_str]
            yesterday_acts = [a for a in activity_feed if a["date"] == yesterday_str]
            older_acts = [a for a in activity_feed if a["date"] < yesterday_str]

            if today_acts:
                activity_html += '<div style="margin-bottom:15px;"><div style="color:var(--text-muted);font-size:12px;margin-bottom:8px;">TODAY</div>'
                for a in today_acts[:20]:
                    time_badge = f'<span style="color:var(--text-muted);font-size:11px;margin-right:6px;">{a["time"]}</span>' if a["time"] else ""
                    amt_html = f'<div style="color:{a["color"]};font-weight:bold;white-space:nowrap;">{fmt(a["amount"])}</div>' if a["amount"] else ""
                    activity_html += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:8px;background:rgba(255,255,255,0.03);border-radius:6px;margin-bottom:4px;border-left:3px solid {a["color"]};"><div style="font-size:13px;">{time_badge}<span style="margin-right:6px;">{a["icon"]}</span>{a["text"]}</div>{amt_html}</div>'
                if len(today_acts) > 20:
                    activity_html += f'<div style="text-align:center;color:var(--text-muted);font-size:12px;padding:6px;">+{len(today_acts)-20} more today</div>'
                activity_html += '</div>'

            if yesterday_acts:
                activity_html += '<div style="margin-bottom:15px;"><div style="color:var(--text-muted);font-size:12px;margin-bottom:8px;">YESTERDAY</div>'
                for a in yesterday_acts[:12]:
                    time_badge = f'<span style="color:var(--text-muted);font-size:10px;margin-right:4px;">{a["time"]}</span>' if a["time"] else ""
                    amt_html = f'<div style="color:{a["color"]};font-size:13px;">{fmt(a["amount"])}</div>' if a["amount"] else ""
                    activity_html += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:6px;border-bottom:1px solid rgba(255,255,255,0.05);"><div style="font-size:13px;">{time_badge}<span style="margin-right:6px;">{a["icon"]}</span>{a["text"]}</div>{amt_html}</div>'
                activity_html += '</div>'

            if older_acts:
                activity_html += '<div><div style="color:var(--text-muted);font-size:12px;margin-bottom:8px;">EARLIER THIS WEEK</div>'
                for a in older_acts[:10]:
                    amt_html = f'<div style="color:var(--text-muted);font-size:12px;">{fmt(a["amount"])}</div>' if a["amount"] else ""
                    activity_html += f'<div style="display:flex;justify-content:space-between;align-items:center;padding:5px;border-bottom:1px solid rgba(255,255,255,0.03);"><div style="font-size:12px;color:var(--text-muted);"><span style="margin-right:6px;">{a["icon"]}</span>{a["date"][5:]} {a["text"]}</div>{amt_html}</div>'
                activity_html += '</div>'

            # ── STOCK ALERTS ──
            stock_html = ""
            below_cost = []
            out_of_stock = []
            low_stock = []

            for item in stock:
                code = item.get("code", item.get("description", ""))[:30]
                qty = float(item.get("qty_on_hand", item.get("quantity", 0)) or 0)
                cost = float(item.get("cost_price", item.get("cost", 0)) or 0)
                price = float(item.get("selling_price", item.get("price", 0)) or 0)

                if price > 0 and cost > 0 and price < cost:
                    below_cost.append({"code": code, "cost": cost, "price": price, "loss": cost - price})
                if qty <= 0:
                    out_of_stock.append({"code": code})
                elif qty <= 5:
                    low_stock.append({"code": code, "qty": qty})

            below_cost.sort(key=lambda x: x["loss"], reverse=True)

            if below_cost:
                stock_html += '<div style="margin-bottom:15px;"><div style="color:#ef4444;font-weight:bold;margin-bottom:8px;">SELLING BELOW COST:</div>'
                for item in below_cost[:5]:
                    stock_html += f'<div style="padding:6px;background:rgba(239,68,68,0.1);border-radius:4px;margin-bottom:4px;font-size:13px;">{item["code"]}: Cost R{item["cost"]:.2f} &rarr; Sell R{item["price"]:.2f} <span style="color:#ef4444;">(Lose R{item["loss"]:.2f}/unit)</span></div>'
                stock_html += '</div>'

            if out_of_stock:
                stock_html += f'<div style="margin-bottom:15px;"><div style="color:#f97316;font-weight:bold;margin-bottom:8px;">&#9888;&#65039; OUT OF STOCK ({len(out_of_stock)}):</div>'
                for item in out_of_stock[:5]:
                    stock_html += f'<div style="padding:4px 0;font-size:13px;color:#ccc;">{item["code"]}</div>'
                if len(out_of_stock) > 5:
                    stock_html += f'<div style="color:var(--text-muted);font-size:12px;">+{len(out_of_stock)-5} more</div>'
                stock_html += '</div>'

            if low_stock:
                stock_html += f'<div><div style="color:#eab308;font-weight:bold;margin-bottom:8px;">LOW STOCK ({len(low_stock)}):</div>'
                for item in low_stock[:5]:
                    stock_html += f'<div style="padding:4px 0;font-size:13px;color:#ccc;">{item["code"]} &mdash; {item["qty"]:.0f} left</div>'
                if len(low_stock) > 5:
                    stock_html += f'<div style="color:var(--text-muted);font-size:12px;">+{len(low_stock)-5} more</div>'
                stock_html += '</div>'

            elapsed = time.time() - _start
            logger.info(f"[PULSE] Data compiled in {elapsed:.1f}s")

            result = {
                "success": True,
                "today_payments": fmt(today_payments),
                "today_sales": fmt(today_sales_total),
                "today_invoiced": fmt(today_invoiced),
                "week_total": fmt(week_sales + week_invoiced),
                "owed_to_you": fmt(total_owed_to_us),
                "you_owe": fmt(total_we_owe),
                "danger_total": fmt(danger_total),
                "open_invoices": str(len(outstanding_invoices)),
                # NEW stat cards
                "today_expenses": fmt(today_expenses),
                "today_bank_txns": str(today_bank_count),
                "today_timesheet_hrs": f"{today_ts_hours:.1f}h",
                "today_cashups": str(today_cashup_count),
                # Aging
                "danger_count": str(len(danger_zone)),
                "danger_html": danger_html,
                "warning_count": str(len(warning_zone)),
                "warning_html": warning_html,
                "watch_info": f"{len(watch_zone)} accounts &bull; {fmt(watch_total)}",
                "watch_html": watch_html,
                # Overdue invoice detail (NEW)
                "overdue_info": f"{len(overdue_invoices)} invoices &bull; {fmt(overdue_total)}",
                "overdue_html": overdue_html,
                # Activity
                "team_html": team_html,
                "activity_html": activity_html,
                "stock_html": stock_html,
                "compiled_in": f"{elapsed:.1f}s"
            }

            _pulse_cache[cache_key] = {"data": result, "ts": time.time()}
            return jsonify(result)

        except Exception as e:
            logger.error(f"[PULSE DATA] Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)})

    # ─────────────────────────────────────────────────────────
    # BRIEFING API — Background AI generation
    # ─────────────────────────────────────────────────────────
    @app.route("/api/briefing/generate", methods=["POST"])
    @login_required
    def api_briefing_generate():
        """Generate a catch-up briefing. NEVER blocks — returns instantly."""
        global _briefing_cache
        from flask import request, jsonify

        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            user_id = user.get("id") if user else None

            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})

            force = request.json.get("force", False) if request.is_json else False
            today_str = today()

            if force:
                _briefing_cache.pop(biz_id, None)

            if not force:
                # Layer 1: In-memory cache
                mem = _briefing_cache.get(biz_id)
                if mem and mem.get("date") == today_str:
                    logger.info("[BRIEFING] Memory cache hit")
                    return jsonify(mem["result"])

                # Layer 2: DB cache
                try:
                    briefings = db.get("daily_briefings", {"business_id": biz_id}) or []
                    today_briefings = [b for b in briefings if b.get("date") == today_str]

                    if today_briefings:
                        latest = sorted(today_briefings, key=lambda x: x.get("created_at", ""), reverse=True)[0]
                        logger.info(f"[BRIEFING] DB cache hit from {latest.get('created_at', '')}")

                        result = {
                            "success": True,
                            "briefing": latest.get("briefing", ""),
                            "days": latest.get("days_covered", 1),
                            "cached": True,
                            "generated_at": latest.get("created_at", "")
                        }
                        _briefing_cache[biz_id] = {"date": today_str, "result": result, "ts": time.time()}
                        return jsonify(result)
                except Exception as cache_err:
                    logger.warning(f"[BRIEFING] DB cache check failed: {cache_err}")

            # Layer 3: Background generation
            gen_key = f"_gen_{biz_id}"
            if _briefing_cache.get(gen_key):
                return jsonify({"success": True, "generating": True, "briefing": ""})

            _briefing_cache[gen_key] = True

            if DailyBriefing is None:
                _briefing_cache.pop(gen_key, None)
                return jsonify({"success": False, "error": "DailyBriefing not available"})

            def _bg_generate(biz_id, user_id, today_str, gen_key):
                try:
                    logger.info("[BRIEFING] Background generation starting")
                    result = DailyBriefing.generate_catchup(biz_id, user_id)

                    if result.get("success"):
                        result["cached"] = False
                        result["generated_at"] = now()
                        _briefing_cache[biz_id] = {
                            "date": today_str,
                            "result": {**result, "cached": True},
                            "ts": time.time()
                        }
                        logger.info("[BRIEFING] Background generation complete")
                    else:
                        logger.error(f"[BRIEFING] Background generation failed: {result.get('error')}")
                except Exception as e:
                    logger.error(f"[BRIEFING] Background thread error: {e}")
                finally:
                    _briefing_cache.pop(gen_key, None)

            t = threading.Thread(target=_bg_generate, args=(biz_id, user_id, today_str, gen_key), daemon=True)
            t.start()

            logger.info("[BRIEFING] Returning immediately — generating in background")
            return jsonify({"success": True, "generating": True, "briefing": ""})

        except Exception as e:
            logger.error(f"[BRIEFING API] Error: {e}")
            return jsonify({"success": False, "error": str(e)})

    # ─────────────────────────────────────────────────────────
    # ASSISTANT APIs — Reminders, To-Dos, Notes
    # ─────────────────────────────────────────────────────────
    @app.route("/api/assistant/items", methods=["GET"])
    @login_required
    def api_assistant_items():
        """Get all pending reminders + todos for Pulse cards."""
        from flask import jsonify
        try:
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False})

            today_str = today()

            # Reminders
            reminders = db.get("reminders", {"business_id": biz_id}) or []
            pending_reminders = [r for r in reminders if r.get("status") != "completed"]
            pending_reminders.sort(key=lambda x: (x.get("due_date", "9999"), x.get("due_time", "99:99")))

            reminder_items = []
            for r in pending_reminders[:25]:
                due = r.get("due_date", "")
                due_time = r.get("due_time", "")
                is_overdue = due < today_str if due else False
                is_today = due == today_str

                if is_overdue:
                    due_display = f"Due {due}" + (f" {due_time}" if due_time else "")
                elif is_today:
                    due_display = f"Today" + (f" {due_time}" if due_time else "")
                elif due:
                    due_display = f"Due {due}" + (f" {due_time}" if due_time else "")
                else:
                    due_display = "No due date"

                reminder_items.append({
                    "id": r.get("id", ""),
                    "title": r.get("message", r.get("title", "Reminder")),
                    "message": r.get("message", ""),
                    "due_date": due,
                    "due_time": due_time,
                    "due_display": due_display,
                    "priority": r.get("priority", "normal"),
                    "linked_to": r.get("linked_to", ""),
                    "is_overdue": is_overdue,
                    "overdue": is_overdue,
                    "today": is_today
                })

            # Todos
            todos = db.get("todos", {"business_id": biz_id}) or []
            pending_todos = [t for t in todos if t.get("status") != "completed"]
            priority_order = {"high": 0, "normal": 1, "low": 2}
            pending_todos.sort(key=lambda x: (priority_order.get(x.get("priority", "normal"), 1), x.get("created_at", "")))

            todo_items = []
            for t in pending_todos[:25]:
                todo_items.append({
                    "id": t.get("id", ""),
                    "title": t.get("task", t.get("title", "To-do")),
                    "task": t.get("task", ""),
                    "priority": t.get("priority", "normal"),
                    "category": t.get("category", "general")
                })

            # Notes
            notes = db.get("notes", {"business_id": biz_id}) or []
            notes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            note_items = []
            for n in notes[:10]:
                note_items.append({
                    "id": n.get("id", ""),
                    "content": n.get("content", "")[:100],
                    "linked_name": n.get("linked_name", ""),
                    "tags": n.get("tags", ""),
                    "date": str(n.get("created_at", ""))[:10]
                })

            return jsonify({
                "success": True,
                "reminders": reminder_items,
                "todos": todo_items,
                "notes": note_items,
                "counts": {
                    "reminders_today": sum(1 for r in reminder_items if r["today"]),
                    "reminders_overdue": sum(1 for r in reminder_items if r["overdue"]),
                    "todos": len(todo_items)
                }
            })
        except Exception as e:
            logger.error(f"[ASSISTANT API] Error: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/assistant/toggle", methods=["POST"])
    @login_required
    def api_assistant_toggle():
        """Mark a reminder or todo as completed/pending."""
        from flask import request, jsonify
        try:
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False})

            data = request.json or {}
            item_id = data.get("id", "")
            item_type = data.get("type", "")

            if not item_id or item_type not in ("reminder", "todo"):
                return jsonify({"success": False, "error": "Invalid request"})

            table = "reminders" if item_type == "reminder" else "todos"
            items = db.get(table, {"business_id": biz_id}) or []
            item = next((i for i in items if i.get("id") == item_id), None)

            if not item:
                return jsonify({"success": False, "error": "Item not found"})

            new_status = "completed" if item.get("status") != "completed" else "pending"
            item["status"] = new_status
            if new_status == "completed":
                item["completed_at"] = now()
            else:
                item.pop("completed_at", None)

            db.save(table, item)
            return jsonify({"success": True, "status": new_status})
        except Exception as e:
            logger.error(f"[ASSISTANT TOGGLE] Error: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/assistant/delete", methods=["POST"])
    @login_required
    def api_assistant_delete():
        """Delete a reminder, todo, or note."""
        from flask import request, jsonify
        try:
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False})

            data = request.json or {}
            item_id = data.get("id", "")
            item_type = data.get("type", "")

            table_map = {"reminder": "reminders", "todo": "todos", "note": "notes"}
            table = table_map.get(item_type)

            if not item_id or not table:
                return jsonify({"success": False, "error": "Invalid request"})

            db.delete(table, item_id, biz_id)
            return jsonify({"success": True})
        except Exception as e:
            logger.error(f"[ASSISTANT DELETE] Error: {e}")
            return jsonify({"success": False, "error": str(e)})

    logger.info("[PULSE] All routes registered ✓")
