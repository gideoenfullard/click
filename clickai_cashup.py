"""
ClickAI Cash Up Module
=======================
Complete till reconciliation system.

Flow:
1. Isaac (cashier) does BLIND CASH UP — counts cash by denomination, declares card/account
   → System does NOT show expected amounts until after submission
   → Prints a slip
   → Saved to cash_ups table

2. Daphne (manager) views HISTORY — sees all blind cashups
   → Compares declared vs system amounts
   → Can approve/flag discrepancies
   → Does Z-READING to close the day (locks the day)

3. X-READING — mid-day snapshot (non-destructive, anyone can do)

DB Table: cash_ups
"""

import json
import logging
from datetime import datetime, date
from decimal import Decimal

logger = logging.getLogger("clickai")


def register_cashup_routes(app, db, login_required, Auth, generate_id, now, today, render_page=None):
    """Register all cash up routes on the Flask app"""

    # Helper to get render_page from clickai at runtime
    def _render(title, content, user, active="cashup"):
        try:
            import clickai as _ck
            return _ck.render_page(title, content, user, active)
        except:
            return f"<html><body>{content}</body></html>"

    def _money(amt):
        try:
            return f"R{float(amt):,.2f}"
        except:
            return f"R{amt}"

    def _get_sales_breakdown(biz_id, for_date=None):
        """Get sales breakdown by payment method for a date"""
        d = for_date or today()
        sales = db.get("sales", {"business_id": biz_id}) or []
        # Filter by date — check both date field and created_at
        day_sales = [s for s in sales if s.get("date") == d or (s.get("created_at") or "")[:10] == d]
        # Exclude sales already closed by a Z-reading (so counters start fresh after Z-read)
        day_sales = [s for s in day_sales if not s.get("z_closed")]

        cash_total = sum(float(s.get("total", 0) or 0) for s in day_sales if s.get("payment_method") == "cash")
        card_total = sum(float(s.get("total", 0) or 0) for s in day_sales if s.get("payment_method") == "card")
        acc_total = sum(float(s.get("total", 0) or 0) for s in day_sales if s.get("payment_method") == "account")
        count = len(day_sales)

        # Per-cashier breakdown
        cashiers = {}
        for s in day_sales:
            cid = s.get("created_by") or "unknown"
            if cid not in cashiers:
                cashiers[cid] = {"name": "", "cash": 0, "card": 0, "account": 0, "count": 0}
            pm = s.get("payment_method", "cash")
            cashiers[cid][pm] = cashiers[cid].get(pm, 0) + float(s.get("total", 0) or 0)
            cashiers[cid]["count"] += 1
            # Try to get cashier name
            cn = s.get("cashier_name", "")
            if not cn:
                notes = s.get("notes", "")
                if "Cashier:" in notes:
                    cn = notes.split("Cashier:")[-1].strip()
            if cn:
                cashiers[cid]["name"] = cn

        return {
            "cash": round(cash_total, 2),
            "card": round(card_total, 2),
            "account": round(acc_total, 2),
            "total": round(cash_total + card_total + acc_total, 2),
            "count": count,
            "cashiers": cashiers
        }

    # ═══════════════════════════════════════════════════════════════
    # MAIN CASHUP PAGE
    # ═══════════════════════════════════════════════════════════════
    @app.route("/cashup")
    @login_required
    def cashup_page():
        """Cash Up — Blind Cash Up, History, Z-Read"""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("name", "Business") if business else "Business"
        user_name = user.get("name", "") if user else ""
        user_role = "owner"
        try:
            import clickai as _ck
            user_role = _ck.get_user_role()
        except:
            user_role = user.get("role", "owner") if user else "owner"
        is_manager = user_role in ("owner", "admin", "manager")

        from flask import request as req
        view_date = req.args.get("date", today())
        tab = req.args.get("tab", "blind")

        breakdown = _get_sales_breakdown(biz_id, view_date)

        # Get existing cashups for this date
        all_cashups = db.get("cash_ups", {"business_id": biz_id}) or []
        day_cashups = [c for c in all_cashups if c.get("date") == view_date]
        day_cashups = sorted(day_cashups, key=lambda x: x.get("created_at", ""), reverse=True)

        # Check if day is closed (Z-Read done)
        z_reads = [c for c in day_cashups if c.get("type") == "z_reading"]
        day_closed = len(z_reads) > 0

        # Build history rows
        history_html = ""
        for cu in day_cashups:
            cu_type = cu.get("type", "?")
            type_badge = {"blind_cashup": "🔒 Blind", "x_reading": "📊 X-Read", "z_reading": "🔐 Z-Read"}.get(cu_type, cu_type)
            type_color = {"blind_cashup": "#3b82f6", "x_reading": "#f59e0b", "z_reading": "#10b981"}.get(cu_type, "#888")
            cu_time = (cu.get("created_at") or "")[-8:-3] if len(cu.get("created_at", "")) > 8 else ""
            cashier = cu.get("cashier_name") or cu.get("created_by_name") or "—"
            declared = float(cu.get("declared_total", 0) or cu.get("system_total", 0) or 0)
            system = float(cu.get("system_total", 0) or 0)
            disc = float(cu.get("total_discrepancy", 0) or 0)
            disc_color = "#10b981" if abs(disc) < 1 else "#ef4444" if disc < 0 else "#f59e0b"
            status = cu.get("status", "pending")
            status_badge = {"approved": "✅", "flagged": "🚩", "pending": "⏳"}.get(status, "")

            history_html += f'''
            <tr onclick="showDetail('{cu.get("id")}')" style="cursor:pointer;">
                <td style="padding:10px 8px;"><span style="font-size:12px;color:var(--text-muted);">{cu_time}</span></td>
                <td style="padding:10px 8px;"><span style="background:{type_color}22;color:{type_color};padding:3px 10px;border-radius:6px;font-size:12px;font-weight:600;">{type_badge}</span></td>
                <td style="padding:10px 8px;font-size:13px;">{cashier}</td>
                <td style="padding:10px 8px;text-align:right;font-weight:600;">{_money(declared)}</td>
                <td style="padding:10px 8px;text-align:right;font-weight:600;">{_money(system)}</td>
                <td style="padding:10px 8px;text-align:right;font-weight:700;color:{disc_color};">{_money(disc)}</td>
                <td style="padding:10px 8px;text-align:center;">{status_badge}</td>
            </tr>'''

        # SA Rand denominations
        denoms = [
            ("R200", 200), ("R100", 100), ("R50", 50), ("R20", 20), ("R10", 10),
            ("R5", 5), ("R2", 2), ("R1", 1), ("50c", 0.50), ("20c", 0.20), ("10c", 0.10)
        ]

        denom_rows = ""
        for label, val in denoms:
            denom_rows += f'''
            <tr>
                <td style="padding:6px 10px;font-weight:600;font-size:14px;">{label}</td>
                <td style="padding:6px 10px;text-align:center;">
                    <input type="number" id="d_{label.replace('.','')}" min="0" value="0" 
                           style="width:70px;text-align:center;padding:6px;border:1px solid var(--border);border-radius:6px;background:var(--card);color:var(--text);font-size:14px;"
                           oninput="calcDenoms()">
                </td>
                <td style="padding:6px 10px;text-align:right;font-weight:600;" id="dt_{label.replace('.','')}">{_money(0)}</td>
            </tr>'''

        # Team members for cashier dropdown
        team = []
        try:
            team = db.get_business_users(biz_id) if biz_id else []
            team = team or []
        except:
            pass
        cashier_opts = "".join([f'<option value="{t.get("id","")}">{t.get("name", t.get("email",""))}</option>' for t in team])

        closed_banner = ""
        if day_closed:
            z = z_reads[0]
            closed_banner = f'''
            <div style="background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:8px;padding:15px;margin-bottom:15px;display:flex;align-items:center;gap:10px;">
                <span style="font-size:24px;">🔐</span>
                <div>
                    <strong style="color:#10b981;">Day Closed</strong>
                    <div style="font-size:12px;color:var(--text-muted);">Z-Reading done at {(z.get("created_at") or "")[-8:-3]} by {z.get("created_by_name", "manager")}</div>
                </div>
            </div>'''

        _approve_btns_html = ('<button onclick="approveCashup()" class="btn btn-primary" style="padding:8px 16px;">✅ Approve</button>'
                              '<button onclick="flagCashup()" class="btn btn-secondary" style="padding:8px 16px;">🚩 Flag</button>') if is_manager else ''
        _is_manager_js = "true" if is_manager else "false"

        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
            <h2 style="margin:0;">💰 Cash Up</h2>
            <div style="display:flex;gap:8px;align-items:center;">
                <input type="date" id="cuDate" value="{view_date}" onchange="window.location='/cashup?date='+this.value+'&tab={tab}'" class="form-input" style="width:auto;">
                {'<span style="font-weight:700;">' + _money(breakdown["total"]) + ' (' + str(breakdown["count"]) + ' sales)</span>' if is_manager and tab != 'blind' else '<span style="font-weight:700;">' + str(breakdown["count"]) + ' sales today</span>'}
            </div>
        </div>

        {closed_banner}

        <!-- TABS -->
        <div style="display:flex;gap:0;margin-bottom:20px;border-bottom:2px solid var(--border);">
            <a href="/cashup?date={view_date}&tab=blind" style="padding:10px 20px;font-weight:600;font-size:14px;text-decoration:none;border-bottom:3px solid {'var(--primary)' if tab == 'blind' else 'transparent'};color:{'var(--primary)' if tab == 'blind' else 'var(--text-muted)'};">🔒 Blind Cash Up</a>
            <a href="/cashup?date={view_date}&tab=history" style="padding:10px 20px;font-weight:600;font-size:14px;text-decoration:none;border-bottom:3px solid {'var(--primary)' if tab == 'history' else 'transparent'};color:{'var(--primary)' if tab == 'history' else 'var(--text-muted)'};">📋 History ({len(day_cashups)})</a>
            {'<a href="/cashup?date=' + view_date + '&tab=zread" style="padding:10px 20px;font-weight:600;font-size:14px;text-decoration:none;border-bottom:3px solid ' + ("var(--primary)" if tab == "zread" else "transparent") + ';color:' + ("var(--primary)" if tab == "zread" else "var(--text-muted)") + ';">🔐 Close Day</a>' if is_manager else ''}
        </div>

        <!-- BLIND CASH UP TAB -->
        <div id="tabBlind" style="display:{'block' if tab == 'blind' else 'none'};">
            <div class="card" style="margin-bottom:15px;">
                <h3 style="margin:0 0 15px 0;">🔒 Blind Cash Up</h3>
                <p style="color:var(--text-muted);font-size:13px;margin-bottom:15px;">Count your cash by denomination. You will NOT see system totals until after submission.</p>

                <div style="margin-bottom:15px;">
                    <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Cashier</label>
                    <select id="cuCashier" class="form-input" style="width:100%;max-width:300px;">
                        <option value="{user.get('id','')}">{user_name} (me)</option>
                        {cashier_opts}
                    </select>
                </div>

                <div style="margin-bottom:15px;">
                    <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Float Amount (starting cash in till)</label>
                    <input type="number" id="cuFloat" value="500" step="50" class="form-input" style="width:150px;">
                </div>

                <h4 style="margin:20px 0 10px;">💵 Cash Denomination Count</h4>
                <table style="width:100%;max-width:400px;border-collapse:collapse;">
                    <thead><tr style="border-bottom:2px solid var(--border);">
                        <th style="text-align:left;padding:6px 10px;font-size:11px;color:var(--text-muted);">NOTE/COIN</th>
                        <th style="text-align:center;padding:6px 10px;font-size:11px;color:var(--text-muted);">COUNT</th>
                        <th style="text-align:right;padding:6px 10px;font-size:11px;color:var(--text-muted);">TOTAL</th>
                    </tr></thead>
                    <tbody>{denom_rows}</tbody>
                    <tfoot><tr style="border-top:2px solid var(--border);">
                        <td colspan="2" style="padding:10px;font-weight:700;font-size:16px;">CASH COUNTED</td>
                        <td style="padding:10px;text-align:right;font-weight:700;font-size:18px;color:var(--primary);" id="cashCountedTotal">{_money(0)}</td>
                    </tr></tfoot>
                </table>

                <h4 style="margin:20px 0 10px;">💳 Other Declarations</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:400px;">
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);">Card Total</label>
                        <input type="number" id="cuCard" value="0" step="0.01" class="form-input" style="width:100%;">
                    </div>
                    <div>
                        <label style="font-size:12px;color:var(--text-muted);">Account Total</label>
                        <input type="number" id="cuAccount" value="0" step="0.01" class="form-input" style="width:100%;">
                    </div>
                </div>

                <div style="margin-top:20px;padding:15px;background:rgba(99,102,241,0.08);border-radius:8px;">
                    <div style="display:flex;justify-content:space-between;font-size:16px;font-weight:700;">
                        <span>DECLARED TOTAL:</span>
                        <span id="declaredTotal">{_money(0)}</span>
                    </div>
                </div>

                <button onclick="submitBlindCashup()" class="btn btn-primary" style="margin-top:15px;padding:12px 30px;font-size:15px;"
                    {'disabled style="opacity:0.5;margin-top:15px;padding:12px 30px;font-size:15px;"' if day_closed else ''}>
                    ✅ Submit Blind Cash Up
                </button>
            </div>
        </div>

        <!-- HISTORY TAB -->
        <div id="tabHistory" style="display:{'block' if tab == 'history' else 'none'};">
            <div class="card" style="padding:0;overflow-x:auto;">
                <table style="width:100%;border-collapse:collapse;">
                    <thead><tr style="border-bottom:2px solid var(--border);">
                        <th style="padding:10px 8px;text-align:left;font-size:11px;color:var(--text-muted);">TIME</th>
                        <th style="padding:10px 8px;text-align:left;font-size:11px;color:var(--text-muted);">TYPE</th>
                        <th style="padding:10px 8px;text-align:left;font-size:11px;color:var(--text-muted);">CASHIER</th>
                        <th style="padding:10px 8px;text-align:right;font-size:11px;color:var(--text-muted);">DECLARED</th>
                        <th style="padding:10px 8px;text-align:right;font-size:11px;color:var(--text-muted);">SYSTEM</th>
                        <th style="padding:10px 8px;text-align:right;font-size:11px;color:var(--text-muted);">DIFF</th>
                        <th style="padding:10px 8px;text-align:center;font-size:11px;color:var(--text-muted);">STATUS</th>
                    </tr></thead>
                    <tbody>
                        {history_html or '<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--text-muted);">No cash ups for this date</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Detail panel (shown when row clicked) -->
            <div id="detailPanel" class="card" style="display:none;margin-top:15px;"></div>
        </div>

        <!-- Z-READ / CLOSE DAY TAB (manager only) -->
        <div id="tabZread" style="display:{'block' if tab == 'zread' else 'none'};">
            <div class="card">
                <h3 style="margin:0 0 15px;">🔐 Close Day — Z-Reading</h3>
                {f'<p style="color:#10b981;font-weight:600;">✅ This day is already closed.</p>' if day_closed else f"""
                <p style="color:var(--text-muted);font-size:13px;margin-bottom:15px;">
                    This locks the day. No more blind cashups can be submitted after this.<br>
                    Make sure all cashiers have done their blind cashup first.
                </p>

                <div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:20px;margin-bottom:15px;">
                    <h4 style="margin:0 0 10px;">📊 Day Summary — {view_date}</h4>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-bottom:15px;">
                        <div style="text-align:center;padding:15px;background:rgba(16,185,129,0.08);border-radius:8px;">
                            <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Cash Sales</div>
                            <div style="font-size:20px;font-weight:700;">{_money(breakdown["cash"])}</div>
                        </div>
                        <div style="text-align:center;padding:15px;background:rgba(59,130,246,0.08);border-radius:8px;">
                            <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Card Sales</div>
                            <div style="font-size:20px;font-weight:700;">{_money(breakdown["card"])}</div>
                        </div>
                        <div style="text-align:center;padding:15px;background:rgba(245,158,11,0.08);border-radius:8px;">
                            <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Account Sales</div>
                            <div style="font-size:20px;font-weight:700;">{_money(breakdown["account"])}</div>
                        </div>
                    </div>
                    <div style="text-align:center;padding:10px;font-size:18px;font-weight:700;border-top:2px solid var(--border);">
                        TOTAL: {_money(breakdown["total"])} &nbsp;•&nbsp; {breakdown["count"]} transactions
                    </div>

                    <div style="margin-top:15px;">
                        <strong style="font-size:13px;">Blind Cashups Done:</strong>
                        <span style="font-weight:700;">{len([c for c in day_cashups if c.get("type") == "blind_cashup"])}</span>
                    </div>
                </div>

                <div style="margin-bottom:15px;">
                    <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Manager Notes (optional)</label>
                    <textarea id="zNotes" class="form-input" rows="3" style="width:100%;" placeholder="Any notes about today..."></textarea>
                </div>

                <button onclick="closeDay()" class="btn btn-primary" style="padding:12px 30px;font-size:15px;background:#10b981;">
                    🔐 Close Day (Z-Reading)
                </button>
                """}
            </div>
        </div>

        <script>
        const denoms = {json.dumps([[label, val] for label, val in denoms])};
        const systemBreakdown = {json.dumps(breakdown)};

        function calcDenoms() {{
            let cashTotal = 0;
            denoms.forEach(([label, val]) => {{
                const id = label.replace('.','');
                const count = parseInt(document.getElementById('d_' + id).value) || 0;
                const lineTotal = count * val;
                document.getElementById('dt_' + id).textContent = 'R' + lineTotal.toFixed(2);
                cashTotal += lineTotal;
            }});
            document.getElementById('cashCountedTotal').textContent = 'R' + cashTotal.toFixed(2);
            updateDeclaredTotal();
        }}

        function updateDeclaredTotal() {{
            const cashEl = document.getElementById('cashCountedTotal');
            const cash = parseFloat(cashEl.textContent.replace('R','').replace(/,/g,'')) || 0;
            const card = parseFloat(document.getElementById('cuCard').value) || 0;
            const acc = parseFloat(document.getElementById('cuAccount').value) || 0;
            document.getElementById('declaredTotal').textContent = 'R' + (cash + card + acc).toFixed(2);
        }}

        document.getElementById('cuCard').addEventListener('input', updateDeclaredTotal);
        document.getElementById('cuAccount').addEventListener('input', updateDeclaredTotal);

        async function submitBlindCashup() {{
            // Collect denominations
            const denomData = {{}};
            let cashCounted = 0;
            denoms.forEach(([label, val]) => {{
                const id = label.replace('.','');
                const count = parseInt(document.getElementById('d_' + id).value) || 0;
                denomData[label] = count;
                cashCounted += count * val;
            }});

            const floatAmt = parseFloat(document.getElementById('cuFloat').value) || 0;
            const cardDeclared = parseFloat(document.getElementById('cuCard').value) || 0;
            const accDeclared = parseFloat(document.getElementById('cuAccount').value) || 0;
            const cashDeclared = cashCounted - floatAmt;  // Cash sales = counted - float
            const declaredTotal = cashDeclared + cardDeclared + accDeclared;

            const cashierSelect = document.getElementById('cuCashier');
            const cashierName = cashierSelect.options[cashierSelect.selectedIndex].text;
            const cashierId = cashierSelect.value;

            // System values (NOT shown to cashier before submit)
            const sysCash = systemBreakdown.cash;
            const sysCard = systemBreakdown.card;
            const sysAcc = systemBreakdown.account;
            const sysTotal = systemBreakdown.total;

            const payload = {{
                type: "blind_cashup",
                cashier_id: cashierId,
                cashier_name: cashierName.replace(' (me)',''),
                float_amount: floatAmt,
                cash_counted: cashCounted,
                cash_declared: cashDeclared,
                card_declared: cardDeclared,
                account_declared: accDeclared,
                declared_total: declaredTotal,
                denominations: denomData,
                system_cash: sysCash,
                system_card: sysCard,
                system_account: sysAcc,
                system_total: sysTotal,
                cash_discrepancy: round2(cashDeclared - sysCash),
                card_discrepancy: round2(cardDeclared - sysCard),
                total_discrepancy: round2(declaredTotal - sysTotal),
                sale_count: systemBreakdown.count
            }};

            try {{
                const r = await fetch('/api/cashup/save', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(payload)
                }});
                const d = await r.json();
                if (d.success) {{
                    // Show result with comparison
                    const disc = declaredTotal - sysTotal;
                    const discStr = disc >= 0 ? '+R' + disc.toFixed(2) : '-R' + Math.abs(disc).toFixed(2);
                    const discColor = Math.abs(disc) < 1 ? '#10b981' : disc < 0 ? '#ef4444' : '#f59e0b';

                    const resultHtml = `
                    <div style="text-align:center;padding:20px;">
                        <h3 style="margin-bottom:15px;">✅ Blind Cash Up Submitted</h3>
                        <table style="width:100%;max-width:350px;margin:0 auto;border-collapse:collapse;text-align:left;">
                            <tr style="border-bottom:1px solid var(--border);"><td style="padding:8px;">Cash (declared)</td><td style="text-align:right;font-weight:600;">R${{cashDeclared.toFixed(2)}}</td></tr>
                            <tr style="border-bottom:1px solid var(--border);"><td style="padding:8px;">Cash (system)</td><td style="text-align:right;font-weight:600;">R${{sysCash.toFixed(2)}}</td></tr>
                            <tr style="border-bottom:1px solid var(--border);"><td style="padding:8px;">Card (declared)</td><td style="text-align:right;font-weight:600;">R${{cardDeclared.toFixed(2)}}</td></tr>
                            <tr style="border-bottom:1px solid var(--border);"><td style="padding:8px;">Card (system)</td><td style="text-align:right;font-weight:600;">R${{sysCard.toFixed(2)}}</td></tr>
                            <tr style="border-bottom:2px solid var(--border);"><td style="padding:8px;font-weight:700;">TOTAL</td><td style="text-align:right;font-weight:700;">R${{declaredTotal.toFixed(2)}} vs R${{sysTotal.toFixed(2)}}</td></tr>
                            <tr><td style="padding:8px;font-weight:700;">DISCREPANCY</td><td style="text-align:right;font-weight:700;font-size:18px;color:${{discColor}};">${{discStr}}</td></tr>
                        </table>
                        <div style="margin-top:20px;display:flex;gap:10px;justify-content:center;">
                            <button onclick="printSlip('${{d.id}}')" class="btn btn-secondary" style="padding:10px 20px;">🖨️ Print Slip</button>
                            <button onclick="window.location='/cashup?tab=history'" class="btn btn-primary" style="padding:10px 20px;">📋 View History</button>
                        </div>
                    </div>`;

                    document.getElementById('tabBlind').innerHTML = '<div class="card">' + resultHtml + '</div>';
                }} else {{
                    alert('Error: ' + (d.error || 'Save failed'));
                }}
            }} catch(e) {{ alert('Error: ' + e.message); }}
        }}

        function round2(n) {{ return Math.round(n * 100) / 100; }}

        function printSlip(cashupId) {{
            // Fetch and print
            fetch('/api/cashup/slip/' + cashupId)
                .then(r => r.json())
                .then(d => {{
                    if (!d.success) return alert('Error loading slip');
                    const pw = window.open('', 'cashup_slip', 'width=400,height=600');
                    pw.document.write(d.html);
                    pw.document.close();
                    setTimeout(() => {{ pw.focus(); pw.print(); }}, 300);
                }});
        }}

        async function showDetail(id) {{
            try {{
                const r = await fetch('/api/cashup/detail/' + id);
                const d = await r.json();
                if (!d.success) return;
                const c = d.cashup;
                const panel = document.getElementById('detailPanel');

                let denomHtml = '';
                try {{
                    const dems = typeof c.denominations === 'string' ? JSON.parse(c.denominations) : c.denominations;
                    if (dems) {{
                        Object.entries(dems).forEach(([k, v]) => {{
                            if (v > 0) denomHtml += '<span style="margin-right:8px;font-size:12px;">' + k + ':' + v + '</span>';
                        }});
                    }}
                }} catch(e) {{}}

                const disc = parseFloat(c.total_discrepancy || 0);
                const discColor = Math.abs(disc) < 1 ? '#10b981' : disc < 0 ? '#ef4444' : '#f59e0b';

                panel.innerHTML = `
                <h4 style="margin:0 0 10px;">${{c.type === 'blind_cashup' ? '🔒 Blind Cash Up' : c.type === 'z_reading' ? '🔐 Z-Reading' : '📊 X-Reading'}} Detail</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:15px;">
                    <div><span style="font-size:10px;color:var(--text-muted);">CASHIER</span><div style="font-weight:600;">${{c.cashier_name || '—'}}</div></div>
                    <div><span style="font-size:10px;color:var(--text-muted);">TIME</span><div style="font-weight:600;">${{(c.created_at || '').slice(-8,-3)}}</div></div>
                    <div><span style="font-size:10px;color:var(--text-muted);">FLOAT</span><div style="font-weight:600;">R${{parseFloat(c.float_amount || 0).toFixed(2)}}</div></div>
                </div>
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <tr style="border-bottom:1px solid var(--border);"><th style="text-align:left;padding:6px;">Method</th><th style="text-align:right;padding:6px;">Declared</th><th style="text-align:right;padding:6px;">System</th><th style="text-align:right;padding:6px;">Diff</th></tr>
                    <tr style="border-bottom:1px solid var(--border);"><td style="padding:6px;">Cash</td><td style="text-align:right;">R${{parseFloat(c.cash_declared||0).toFixed(2)}}</td><td style="text-align:right;">R${{parseFloat(c.system_cash||0).toFixed(2)}}</td><td style="text-align:right;color:${{Math.abs(parseFloat(c.cash_discrepancy||0)) < 1 ? '#10b981' : '#ef4444'}};">R${{parseFloat(c.cash_discrepancy||0).toFixed(2)}}</td></tr>
                    <tr style="border-bottom:1px solid var(--border);"><td style="padding:6px;">Card</td><td style="text-align:right;">R${{parseFloat(c.card_declared||0).toFixed(2)}}</td><td style="text-align:right;">R${{parseFloat(c.system_card||0).toFixed(2)}}</td><td style="text-align:right;">R${{parseFloat(c.card_discrepancy||0).toFixed(2)}}</td></tr>
                    <tr style="border-bottom:2px solid var(--border);font-weight:700;"><td style="padding:6px;">TOTAL</td><td style="text-align:right;">R${{parseFloat(c.declared_total||0).toFixed(2)}}</td><td style="text-align:right;">R${{parseFloat(c.system_total||0).toFixed(2)}}</td><td style="text-align:right;color:${{discColor}};font-size:16px;">R${{disc.toFixed(2)}}</td></tr>
                </table>
                ${{denomHtml ? '<div style="margin-top:10px;"><span style="font-size:10px;color:var(--text-muted);">DENOMINATIONS:</span><div>' + denomHtml + '</div></div>' : ''}}
                <div style="margin-top:15px;display:flex;gap:8px;">
                    <button onclick="printSlip('${{c.id}}')" class="btn btn-secondary" style="padding:8px 16px;">🖨️ Print</button>
                    {_approve_btns_html}
                </div>
                `;
                panel.style.display = 'block';
            }} catch(e) {{ console.error(e); }}
        }}

        async function closeDay() {{
            if (!confirm('This will CLOSE the day. No more blind cashups can be done for {view_date}.\\n\\nContinue?')) return;
            const notes = document.getElementById('zNotes') ? document.getElementById('zNotes').value : '';
            try {{
                const r = await fetch('/api/cashup/save', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        type: 'z_reading',
                        notes: notes,
                        system_cash: systemBreakdown.cash,
                        system_card: systemBreakdown.card,
                        system_account: systemBreakdown.account,
                        system_total: systemBreakdown.total,
                        sale_count: systemBreakdown.count
                    }})
                }});
                const d = await r.json();
                if (d.success) {{
                    alert('✅ Day closed successfully!');
                    window.location = '/cashup?date={view_date}&tab=history';
                }} else alert('Error: ' + (d.error || 'Failed'));
            }} catch(e) {{ alert('Error: ' + e.message); }}
        }}

        // Replace template vars in JS
        document.querySelectorAll('#tabHistory button, #detailPanel button').forEach(b => {{
            // handled via onclick
        }});
        </script>
        '''

        return _render("Cash Up", content, user)


    # ═══════════════════════════════════════════════════════════════
    # SAVE CASHUP API
    # ═══════════════════════════════════════════════════════════════
    @app.route("/api/cashup/save", methods=["POST"])
    @login_required
    def api_cashup_save():
        """Save a cash up record"""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        try:
            from flask import jsonify
            data = app.current_app if hasattr(app, 'current_app') else None
            data = __import__('flask').request.json

            cashup_type = data.get("type", "unknown")

            record = {
                "id": generate_id(),
                "business_id": biz_id,
                "date": today(),
                "type": cashup_type,
                "status": "pending",
                "created_by": user.get("id") if user else None,
                "created_by_name": user.get("name", "") if user else "",
                "created_at": now(),
            }

            if cashup_type == "blind_cashup":
                record.update({
                    "cashier_id": data.get("cashier_id"),
                    "cashier_name": data.get("cashier_name", ""),
                    "float_amount": float(data.get("float_amount", 0)),
                    "cash_counted": float(data.get("cash_counted", 0)),
                    "cash_declared": float(data.get("cash_declared", 0)),
                    "card_declared": float(data.get("card_declared", 0)),
                    "account_declared": float(data.get("account_declared", 0)),
                    "declared_total": float(data.get("declared_total", 0)),
                    "denominations": json.dumps(data.get("denominations", {})),
                    "system_cash": float(data.get("system_cash", 0)),
                    "system_card": float(data.get("system_card", 0)),
                    "system_account": float(data.get("system_account", 0)),
                    "system_total": float(data.get("system_total", 0)),
                    "cash_discrepancy": float(data.get("cash_discrepancy", 0)),
                    "card_discrepancy": float(data.get("card_discrepancy", 0)),
                    "total_discrepancy": float(data.get("total_discrepancy", 0)),
                    "sale_count": int(data.get("sale_count", 0)),
                })

            elif cashup_type == "z_reading":
                record.update({
                    "notes": data.get("notes", ""),
                    "system_cash": float(data.get("system_cash", 0)),
                    "system_card": float(data.get("system_card", 0)),
                    "system_account": float(data.get("system_account", 0)),
                    "system_total": float(data.get("system_total", 0)),
                    "sale_count": int(data.get("sale_count", 0)),
                })

            elif cashup_type == "x_reading":
                record.update({
                    "system_cash": float(data.get("system_cash", 0)),
                    "system_card": float(data.get("system_card", 0)),
                    "system_account": float(data.get("system_account", 0)),
                    "system_total": float(data.get("system_total", 0)),
                    "sale_count": int(data.get("sale_count", 0)),
                })

            success, err = db.save("cash_ups", record)
            if success:
                logger.info(f"[CASHUP] {cashup_type} saved by {record.get('created_by_name')} | total={record.get('declared_total', record.get('system_total', 0))}")
                
                # FIX: Post discrepancy to GL Cash Over/Short control account (7100)
                if cashup_type == "blind_cashup":
                    total_disc = float(record.get("total_discrepancy", 0))
                    if abs(total_disc) > 0.01:
                        try:
                            import clickai as _ck
                            ref = f"CASHUP-{record['id'][:8]}"
                            cashier_name = record.get("cashier_name", "Cashier")
                            if total_disc > 0:
                                # Over = cash more than expected: Debit Cash On Hand, Credit Cash Over/Short
                                _ck.create_journal_entry(biz_id, today(), f"Cash over - {cashier_name}", ref, [
                                    {"account_code": "1050", "debit": abs(total_disc), "credit": 0},
                                    {"account_code": "7050", "debit": 0, "credit": abs(total_disc)},
                                ])
                            else:
                                # Short = cash less than expected: Debit Cash Over/Short, Credit Cash On Hand
                                _ck.create_journal_entry(biz_id, today(), f"Cash short - {cashier_name}", ref, [
                                    {"account_code": "7050", "debit": abs(total_disc), "credit": 0},
                                    {"account_code": "1050", "debit": 0, "credit": abs(total_disc)},
                                ])
                            logger.info(f"[CASHUP] GL posted discrepancy R{total_disc:.2f} for {cashier_name}")
                        except Exception as gl_err:
                            logger.error(f"[CASHUP] GL posting failed: {gl_err}")
                
                # FIX: Z-Reading marks daily POS sales as closed for that date
                if cashup_type == "z_reading":
                    try:
                        z_date = record.get("date", today())
                        sales = db.get("sales", {"business_id": biz_id}) or []
                        day_sales = [s for s in sales if s.get("date") == z_date or (s.get("created_at") or "")[:10] == z_date]
                        closed_count = 0
                        for s in day_sales:
                            if not s.get("z_closed"):
                                db.update("sales", s["id"], {"z_closed": True, "z_reading_id": record["id"]})
                                closed_count += 1
                        logger.info(f"[CASHUP] Z-Reading closed {closed_count} sales for {z_date}")
                    except Exception as z_err:
                        logger.error(f"[CASHUP] Z-Reading close failed: {z_err}")
                
                return jsonify({"success": True, "id": record["id"]})
            else:
                logger.error(f"[CASHUP] Save failed: {err}")
                return jsonify({"success": False, "error": str(err)})

        except Exception as e:
            logger.error(f"[CASHUP] Error: {e}")
            from flask import jsonify
            return jsonify({"success": False, "error": str(e)})


    # ═══════════════════════════════════════════════════════════════
    # CASHUP DETAIL API
    # ═══════════════════════════════════════════════════════════════
    @app.route("/api/cashup/detail/<cashup_id>")
    @login_required
    def api_cashup_detail(cashup_id):
        from flask import jsonify
        record = db.get_one("cash_ups", cashup_id)
        if not record:
            return jsonify({"success": False, "error": "Not found"})
        return jsonify({"success": True, "cashup": record})


    # ═══════════════════════════════════════════════════════════════
    # PRINT SLIP API
    # ═══════════════════════════════════════════════════════════════
    @app.route("/api/cashup/slip/<cashup_id>")
    @login_required
    def api_cashup_slip(cashup_id):
        """Generate printable slip HTML for a cashup"""
        from flask import jsonify

        business = Auth.get_current_business()
        biz_name = business.get("name", "Business") if business else "Business"

        record = db.get_one("cash_ups", cashup_id)
        if not record:
            return jsonify({"success": False, "error": "Not found"})

        cu_type = record.get("type", "?")
        type_label = {"blind_cashup": "BLIND CASH UP", "x_reading": "X-READING", "z_reading": "Z-READING"}.get(cu_type, cu_type.upper())
        cu_date = record.get("date", "")
        cu_time = (record.get("created_at") or "")[-8:-3]
        cashier = record.get("cashier_name") or record.get("created_by_name") or ""

        # Denomination breakdown
        denom_lines = ""
        try:
            dems = json.loads(record.get("denominations", "{}")) if isinstance(record.get("denominations"), str) else record.get("denominations", {})
            for k, v in (dems or {}).items():
                if int(v) > 0:
                    denom_lines += f"<tr><td>{k}</td><td style='text-align:center;'>{v}</td></tr>\n"
        except:
            pass

        cash_counted = float(record.get("cash_counted", 0))
        float_amt = float(record.get("float_amount", 0))
        cash_declared = float(record.get("cash_declared", 0))
        card_declared = float(record.get("card_declared", 0))
        acc_declared = float(record.get("account_declared", 0))
        declared_total = float(record.get("declared_total", 0))
        sys_cash = float(record.get("system_cash", 0))
        sys_card = float(record.get("system_card", 0))
        sys_total = float(record.get("system_total", 0))
        disc = float(record.get("total_discrepancy", 0))

        slip_html = f"""<!DOCTYPE html>
<html><head><style>
body {{ width: 72mm; margin: 0; padding: 4mm; font-family: 'Courier New', monospace; font-size: 12px; color: #000; background: #fff; }}
table {{ width: 100%; border-collapse: collapse; }}
td {{ padding: 2px 0; }}
.center {{ text-align: center; }}
.right {{ text-align: right; }}
.bold {{ font-weight: bold; }}
.line {{ border-top: 1px dashed #000; margin: 4px 0; }}
.dline {{ border-top: 2px solid #000; margin: 4px 0; }}
@page {{ size: 80mm auto; margin: 0; }}
@media print {{ body {{ width: 72mm; }} }}
</style></head><body>
<div class="center bold" style="font-size:14px;">{biz_name}</div>
<div class="center" style="font-size:10px;">━━━━━━━━━━━━━━━━━━━━━━━━</div>
<div class="center bold" style="font-size:13px;margin:4px 0;">{type_label}</div>
<div class="line"></div>
<table>
<tr><td>Date:</td><td class="right">{cu_date}</td></tr>
<tr><td>Time:</td><td class="right">{cu_time}</td></tr>
<tr><td>Cashier:</td><td class="right">{cashier}</td></tr>
<tr><td>Float:</td><td class="right">R{float_amt:.2f}</td></tr>
</table>
<div class="line"></div>
{f'''<div class="bold">DENOMINATIONS</div>
<table>{denom_lines}</table>
<table><tr class="bold"><td>Cash Counted:</td><td class="right">R{cash_counted:.2f}</td></tr></table>
<div class="line"></div>''' if denom_lines else ''}
<div class="bold">DECLARED</div>
<table>
<tr><td>Cash Sales:</td><td class="right">R{cash_declared:.2f}</td></tr>
<tr><td>Card Sales:</td><td class="right">R{card_declared:.2f}</td></tr>
<tr><td>Account Sales:</td><td class="right">R{acc_declared:.2f}</td></tr>
</table>
<div class="dline"></div>
<table><tr class="bold"><td>DECLARED TOTAL:</td><td class="right" style="font-size:14px;">R{declared_total:.2f}</td></tr></table>
<div class="dline"></div>
<div class="bold">SYSTEM</div>
<table>
<tr><td>Cash Sales:</td><td class="right">R{sys_cash:.2f}</td></tr>
<tr><td>Card Sales:</td><td class="right">R{sys_card:.2f}</td></tr>
<tr><td>System Total:</td><td class="right bold">R{sys_total:.2f}</td></tr>
</table>
<div class="dline"></div>
<table><tr class="bold"><td>DISCREPANCY:</td><td class="right" style="font-size:16px;">{"+" if disc >= 0 else ""}R{disc:.2f}</td></tr></table>
<div class="line"></div>
<div class="center" style="font-size:10px;margin-top:6px;">
Sale Count: {record.get("sale_count", 0)}<br>
Printed: {now()}<br>
━━━━━━━━━━━━━━━━━━━━━━━━
</div>
</body></html>"""

        return jsonify({"success": True, "html": slip_html})


    # ═══════════════════════════════════════════════════════════════
    # CASHUP HISTORY API (for external use / Zane)
    # ═══════════════════════════════════════════════════════════════
    @app.route("/api/cashup/history")
    @login_required
    def api_cashup_history():
        """Get cash up history"""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        from flask import request as req, jsonify
        date_filter = req.args.get("date", today())

        records = db.get("cash_ups", {"business_id": biz_id}) or []
        day_records = [r for r in records if r.get("date") == date_filter]
        day_records = sorted(day_records, key=lambda x: x.get("created_at", ""), reverse=True)
        return jsonify({"success": True, "cash_ups": day_records})


    logger.info("[CASHUP] Cash Up module loaded — routes: /cashup, /api/cashup/save, /api/cashup/detail, /api/cashup/slip, /api/cashup/history")
