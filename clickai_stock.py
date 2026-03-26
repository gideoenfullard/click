# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - STOCK MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Stock pages, movements, detail, new/edit, Fulltech tools,
#           Stock APIs (all, search, lookup, adjust, issue-to-job, zane-edit),
#           Customer/Supplier list APIs
# ==============================================================================

import json
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def register_stock_routes(app, db, login_required, Auth, render_page,
                          generate_id, money, safe_string, now, today, _t,
                          gl, create_journal_entry, get_user_role,
                          smart_stock_code,
                          has_reactor_hud, jarvis_hud_header, jarvis_techline,
                          RecordFactory, Email, AuditLog, BoltPricer,
                          JARVIS_HUD_CSS, THEME_REACTOR_SKINS, _pulse_cache):
    """Register all Stock & Fulltech routes with the Flask app."""

    @app.route("/stock")
    @login_required
    def stock_page():
        """Stock list - FAST skeleton, JS loads from sessionStorage or API"""
        _t("start")
        
        user = Auth.get_current_user()
        _t("get_user")
        business = Auth.get_current_business()
        _t("get_biz")
        
        # NO DATABASE CALL HERE! JS will handle it.
        _t("before_render")
        
        content = '''
        <!-- Stats - filled by JS -->
        <div style="display:flex;gap:20px;margin-bottom:20px;flex-wrap:wrap;">
            <div style="background:var(--card);padding:15px 20px;border-radius:8px;flex:1;min-width:150px;">
                <div style="font-size:24px;font-weight:bold;" id="statItems">-</div>
                <div style="color:var(--text-muted);font-size:13px;">Items</div>
            </div>
            <div style="background:var(--card);padding:15px 20px;border-radius:8px;flex:1;min-width:150px;">
                <div style="font-size:24px;font-weight:bold;" id="statValue">-</div>
                <div style="color:var(--text-muted);font-size:13px;">Stock Value</div>
            </div>
            <div style="background:var(--card);padding:15px 20px;border-radius:8px;flex:1;min-width:150px;" id="lowStockBox">
                <div style="font-size:24px;font-weight:bold;" id="statLow">-</div>
                <div style="color:var(--text-muted);font-size:13px;">Low Stock</div>
            </div>
        </div>
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;flex-wrap:wrap;gap:10px;">
                <h3 class="card-title" style="margin:0;">Stock (<span id="stockCount">-</span>)</h3>
                <div style="display:flex;gap:10px;flex-wrap:wrap;">
                    <input type="text" id="stockSearch" placeholder="🔍 Search..." 
                        oninput="filterStock()" 
                        style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card-bg);color:var(--text);width:200px;">
                    <select id="categoryFilter" onchange="filterStock()" 
                        style="padding:8px 12px;border-radius:6px;border:1px solid var(--border);background:var(--card-bg);color:var(--text);">
                        <option value="">All Categories</option>
                    </select>
                    <a href="/fulltech" class="btn" style="background:#8b5cf6;">🔩 Bolt Pricer</a>
                    <a href="/stock/movements" class="btn btn-secondary">📋 Movements</a>
                    <button onclick="showStockManager()" class="btn" style="background:#f59e0b;">⚡ Stock Manager</button>
                    <a href="/stock/new" class="btn btn-primary">+ Add Stock</a>
                </div>
            </div>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Code</th><th>Description</th><th>Category</th>
                        <th style="text-align:right;">Qty</th><th>Unit</th>
                        <th style="text-align:right;">Cost</th>
                        <th style="text-align:right;">Price</th><th></th>
                    </tr>
                </thead>
                <tbody id="stockTableBody">
                    <tr><td colspan="8" style="text-align:center;padding:40px;color:var(--text-muted);">Loading...</td></tr>
                </tbody>
            </table>
        </div>
        
        <script>
        const CACHE_KEY = 'clickai_stock';
        const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
        
        // Check cache
        function getCache() {
            try {
                const cached = sessionStorage.getItem(CACHE_KEY);
                if (!cached) return null;
                const data = JSON.parse(cached);
                if (Date.now() - data.time > CACHE_TTL) return null;
                return data.items;
            } catch (e) { return null; }
        }
        
        // Save to cache
        function setCache(items) {
            try {
                sessionStorage.setItem(CACHE_KEY, JSON.stringify({items, time: Date.now()}));
            } catch (e) {}
        }
        
        // Render stock table
        function renderStock(items) {
            // Stats
            const total = items.length;
            const value = items.reduce((s, i) => s + (parseFloat(i.quantity||i.qty||0) * parseFloat(i.cost_price||i.cost||0)), 0);
            const low = items.filter(i => parseFloat(i.quantity||i.qty||0) < 5).length;
            
            document.getElementById('stockCount').textContent = total;
            document.getElementById('statItems').textContent = total;
            document.getElementById('statValue').textContent = 'R' + value.toFixed(2);
            document.getElementById('statLow').textContent = low;
            if (low > 0) {
                document.getElementById('lowStockBox').style.borderLeft = '3px solid var(--red)';
                document.getElementById('statLow').style.color = 'var(--red)';
            }
            
            // Categories dropdown
            const cats = [...new Set(items.map(i => i.category).filter(c => c))].sort();
            document.getElementById('categoryFilter').innerHTML = '<option value="">All Categories</option>' +
                cats.map(c => `<option value="${c}">${c}</option>`).join('');
            
            // Sort by category then description
            items.sort((a,b) => ((a.category||'ZZZ')+(a.description||'')).localeCompare((b.category||'ZZZ')+(b.description||'')));
            
            // Build rows
            let html = '';
            let curCat = null;
            items.forEach(s => {
                const cat = s.category || '';
                if (cat && cat !== curCat) {
                    curCat = cat;
                    html += `<tr class="cat-row" style="background:rgba(99,102,241,0.15);"><td colspan="8" style="padding:8px 10px;font-weight:bold;color:var(--primary);">${cat}</td></tr>`;
                }
                const qty = parseFloat(s.quantity||s.qty||0);
                const cost = parseFloat(s.cost_price||s.cost||0);
                const price = parseFloat(s.selling_price||s.price||0);
                const qtyStyle = qty < 5 ? 'color:var(--red);' : '';
                html += `<tr class="stock-row" data-search="${(s.code||'').toLowerCase()} ${(s.description||'').toLowerCase()}" data-cat="${(cat||'').toLowerCase()}" onclick="window.location='/stock/${s.id}'" style="cursor:pointer;">
                    <td><strong style="color:var(--primary);">${s.code||'-'}</strong></td>
                    <td>${s.description||'-'}</td>
                    <td style="color:var(--text-muted);font-size:11px;">${cat}</td>
                    <td style="text-align:right;${qtyStyle}">${qty.toFixed(0)}</td>
                    <td style="color:var(--text-muted);">${s.unit||''}</td>
                    <td style="text-align:right;">R${cost.toFixed(2)}</td>
                    <td style="text-align:right;">R${price.toFixed(2)}</td>
                    <td style="font-size:11px;color:var(--text-muted);">📜</td>
                </tr>`;
            });
            
            if (!html) {
                html = `<tr><td colspan="8" style="text-align:center;padding:40px;">
                    <div style="color:var(--text-muted);"><strong>No stock items</strong></div>
                    <div style="margin-top:10px;"><a href="/import" class="btn btn-primary">Import</a></div>
                </td></tr>`;
            }
            
            document.getElementById('stockTableBody').innerHTML = html;
        }
        
        // Filter (client-side, instant)
        function filterStock() {
            const raw = document.getElementById('stockSearch').value;
            const cat = document.getElementById('categoryFilter').value.toLowerCase();
            
            let search = raw.toLowerCase().trim();
            search = search.replace(/\s*[xX]\s*/g, 'x');  // "10 x 12" → "10x12"
            const terms = search.split(/\s+/).filter(t => t.length > 0);
            
            document.querySelectorAll('.stock-row').forEach(row => {
                let data = (row.dataset.search || '').replace(/\s*[xX]\s*/g, 'x');
                const matchSearch = terms.length === 0 || terms.every(t => data.includes(t));
                const matchCat = !cat || row.dataset.cat === cat;
                row.style.display = (matchSearch && matchCat) ? '' : 'none';
            });
            document.querySelectorAll('.cat-row').forEach(r => r.style.display = (search || cat) ? 'none' : '');
        }
        
        // Load data
        async function loadStock() {
            // Try cache first
            const cached = getCache();
            if (cached) {
                console.log('Stock: from cache');
                renderStock(cached);
                return;
            }
            
            // Fetch from server
            console.log('Stock: fetching from server...');
            try {
                const resp = await fetch('/api/stock/all');
                const data = await resp.json();
                if (data.success && data.items) {
                    setCache(data.items);
                    renderStock(data.items);
                } else {
                    document.getElementById('stockTableBody').innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--red);">Error loading stock</td></tr>';
                }
            } catch (e) {
                document.getElementById('stockTableBody').innerHTML = '<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--red);">Connection error</td></tr>';
            }
        }
        
        // Init
        loadStock();
        
        // ═══════════════════════════════════════════
        // STOCK MANAGER - Generate codes, markup, etc
        // ═══════════════════════════════════════════
        function showStockManager() {
            document.getElementById('stockManagerModal').style.display = 'flex';
        }
        
        function hideStockManager() {
            document.getElementById('stockManagerModal').style.display = 'none';
        }
        
        async function runStockCommand(command) {
            const btn = event.target;
            const origText = btn.textContent;
            btn.textContent = '⏳ Working...';
            btn.disabled = true;
            
            const resultDiv = document.getElementById('stockManagerResult');
            resultDiv.innerHTML = '<div style="color:var(--text-muted);">Processing...</div>';
            
            let offset = 0;
            let totalUpdated = 0;
            let totalProcessed = 0;
            let totalItems = 0;
            
            // Process in batches
            while (true) {
                try {
                    const response = await fetch('/api/stock/zane-edit', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({command: command, offset: offset, limit: 100})
                    });
                    const data = await response.json();
                    
                    if (!data.success) {
                        resultDiv.innerHTML = '<div style="color:var(--red);">❌ ' + (data.error || 'Failed') + '</div>';
                        break;
                    }
                    
                    totalUpdated += data.updated || 0;
                    totalProcessed += data.processed || 0;
                    totalItems = data.total || totalItems;
                    
                    resultDiv.innerHTML = '<div style="color:#22c55e;">✅ Updated ' + totalUpdated + ' of ' + totalItems + ' items (' + totalProcessed + ' processed)</div>';
                    
                    if (!data.hasMore) break;
                    offset += 100;
                } catch (e) {
                    resultDiv.innerHTML = '<div style="color:var(--red);">❌ Error: ' + e.message + '</div>';
                    break;
                }
            }
            
            btn.textContent = origText;
            btn.disabled = false;
            
            // Refresh stock list
            if (totalUpdated > 0) {
                sessionStorage.removeItem(CACHE_KEY);
                loadStock();
            }
        }
        
        function runCustomCommand() {
            const input = document.getElementById('customStockCommand');
            if (input.value.trim()) {
                runStockCommand(input.value.trim());
            }
        }
        </script>
        
        <!-- Stock Manager Modal -->
        <div id="stockManagerModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center;">
            <div style="background:var(--card);border-radius:12px;padding:30px;max-width:500px;width:90%;max-height:80vh;overflow-y:auto;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                    <h3 style="margin:0;">⚡ Stock Manager</h3>
                    <button onclick="hideStockManager()" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button>
                </div>
                
                <div style="display:flex;flex-direction:column;gap:12px;">
                    <button onclick="runStockCommand('generate smart codes')" class="btn" style="background:#8b5cf6;text-align:left;padding:12px 16px;">
                        🏷️ Generate Smart Stock Codes
                        <div style="font-size:11px;opacity:0.8;margin-top:2px;">Creates unique codes from descriptions (BLT-10X110-HT, SFT-BT-CHEL-9, etc)</div>
                    </button>
                    
                    <button onclick="runStockCommand('50% markup')" class="btn" style="background:#10b981;text-align:left;padding:12px 16px;">
                        💰 Apply 50% Markup
                        <div style="font-size:11px;opacity:0.8;margin-top:2px;">Set selling price = cost × 1.5 for all items</div>
                    </button>
                    
                    <button onclick="runStockCommand('assign categories')" class="btn" style="background:#3b82f6;text-align:left;padding:12px 16px;">
                        📂 Auto-Assign Categories
                        <div style="font-size:11px;opacity:0.8;margin-top:2px;">Bolts → Fasteners, Boots → PPE, Pipes → Pipes & Tubes, etc</div>
                    </button>
                    
                    <div style="border-top:1px solid var(--border);padding-top:12px;margin-top:4px;">
                        <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Custom Command</label>
                        <div style="display:flex;gap:8px;">
                            <input type="text" id="customStockCommand" placeholder="e.g. 'under R50 = 80% markup, rest 50%'" 
                                class="form-input" style="flex:1;" onkeydown="if(event.key==='Enter')runCustomCommand()">
                            <button onclick="runCustomCommand()" class="btn btn-primary">Run</button>
                        </div>
                    </div>
                </div>
                
                <div id="stockManagerResult" style="margin-top:15px;padding:10px;background:var(--bg);border-radius:6px;min-height:30px;"></div>
            </div>
        </div>
        '''
        
        # -- JARVIS: Stock HUD header --
        if has_reactor_hud():
            _hud = jarvis_hud_header(
                page_name="STOCK",
                page_count='<span id="jStockCount">LOADING...</span>',
                left_items=[
                    ("ITEMS", '<span id="jStatItems">-</span>', "c", "", ""),
                    ("STOCK VALUE", '<span id="jStatValue">-</span>', "g", "g", "g"),
                    ("LOW STOCK", '<span id="jStatLow">-</span>', "o", "o", "o"),
                    ("CATEGORIES", '<span id="jStatCat">-</span>', "p", "", ""),
                ],
                right_items=[
                    ("IN STOCK", '<span id="jStatIn">-</span>', "g", "g", ""),
                    ("OUT OF STOCK", '<span id="jStatOut">-</span>', "r", "r", "r"),
                    ("AVG COST", '<span id="jStatAvg">-</span>', "c", "", ""),
                    ("ZERO QTY", '<span id="jStatZero">-</span>', "o", "", ""),
                ],
                reactor_size="page",
                alert_html=""
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline("STOCK <b>LOADING</b>")
        
        return render_page("Stock", content, user, "stock")
        
    
    @app.route("/stock/movements")
    @login_required
    def stock_movements_page():
        """Stock movement history - full audit trail"""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get filter params
        stock_id = request.args.get("stock_id", "")
        move_type = request.args.get("type", "")  # in, out, or empty for all
        days = int(request.args.get("days", 30))
        
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # Fetch movements
        movements = db.get("stock_movements", {"business_id": biz_id}) if biz_id else []
        
        # Filter
        if stock_id:
            movements = [m for m in movements if m.get("stock_id") == stock_id]
        if move_type:
            movements = [m for m in movements if m.get("type") == move_type]
        movements = [m for m in movements if str(m.get("date") or m.get("created_at") or "")[:10] >= cutoff]
        
        # Sort newest first
        movements.sort(key=lambda m: str(m.get("date") or m.get("created_at") or ""), reverse=True)
        
        # Get all stock items for lookup
        all_stock = db.get_all_stock(biz_id) if biz_id else []
        stock_lookup = {s.get("id"): s for s in all_stock}
        
        # Build table rows
        rows_html = ""
        for m in movements[:500]:  # Limit to 500
            stock = stock_lookup.get(m.get("stock_id"), {})
            stock_desc = stock.get("description") or stock.get("name") or stock.get("code") or ""
            stock_code = stock.get("code", "")
            # If stock item not found in lookup, try to extract name from reference
            if not stock_desc:
                ref_str = str(m.get("reference") or "")
                # Reference format: "GRV-XXXX | PO-XXXXX | Supplier Name" - not helpful for item name
                # Just show "Unknown item" rather than a raw ID
                stock_desc = "Unknown item"
            m_type = m.get("type", "")
            qty = float(m.get("quantity") or 0)
            m_date = str(m.get("date") or m.get("created_at") or "")[:16].replace("T", " ")
            ref = safe_string(str(m.get("reference") or ""))
            
            type_badge = f'<span style="background:#10b981;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">IN +{qty}</span>' if m_type == "in" else f'<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:4px;font-size:12px;">OUT -{qty}</span>'
            
            rows_html += f'''
            <tr>
                <td style="white-space:nowrap;">{m_date}</td>
                <td><span style="color:var(--text-muted);font-size:11px;">{safe_string(stock_code)}</span> {safe_string(stock_desc)}</td>
                <td style="text-align:center;">{type_badge}</td>
                <td>{ref}</td>
            </tr>
            '''
        
        if not rows_html:
            rows_html = '<tr><td colspan="4" style="text-align:center;padding:40px;color:var(--text-muted);">No stock movements found for this period</td></tr>'
        
        # Stock filter dropdown
        stock_options = '<option value="">All Items</option>'
        for s in sorted(all_stock, key=lambda x: x.get("description") or ""):
            selected = "selected" if s.get("id") == stock_id else ""
            stock_options += f'<option value="{s.get("id")}" {selected}>{safe_string(s.get("code") or "")} - {safe_string(s.get("description") or "")}</option>'
        
        # Summary counts
        total_in = sum(float(m.get("quantity") or 0) for m in movements if m.get("type") == "in")
        total_out = sum(float(m.get("quantity") or 0) for m in movements if m.get("type") == "out")
        
        content = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <div>
                <h2 style="margin:0;">📦 Stock Movements</h2>
                <p style="color:var(--text-muted);margin:5px 0 0 0;">Full audit trail of stock in/out</p>
            </div>
            <a href="/stock" class="btn btn-secondary">← Back to Stock</a>
        </div>
        
        <!-- Summary Cards -->
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-bottom:20px;">
            <div class="card" style="text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#10b981;">+{total_in:.0f}</div>
                <div style="color:var(--text-muted);font-size:13px;">Total IN</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#ef4444;">-{total_out:.0f}</div>
                <div style="color:var(--text-muted);font-size:13px;">Total OUT</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:24px;font-weight:bold;">{len(movements)}</div>
                <div style="color:var(--text-muted);font-size:13px;">Movements</div>
            </div>
        </div>
        
        <!-- Filters -->
        <div class="card" style="margin-bottom:20px;">
            <form method="GET" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end;">
                <div style="flex:1;min-width:200px;">
                    <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Stock Item</label>
                    <select name="stock_id" class="form-input" onchange="this.form.submit()">{stock_options}</select>
                </div>
                <div>
                    <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Type</label>
                    <select name="type" class="form-input" onchange="this.form.submit()">
                        <option value="">All</option>
                        <option value="in" {"selected" if move_type == "in" else ""}>IN only</option>
                        <option value="out" {"selected" if move_type == "out" else ""}>OUT only</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:12px;color:var(--text-muted);display:block;margin-bottom:4px;">Period</label>
                    <select name="days" class="form-input" onchange="this.form.submit()">
                        <option value="7" {"selected" if days == 7 else ""}>Last 7 days</option>
                        <option value="30" {"selected" if days == 30 else ""}>Last 30 days</option>
                        <option value="90" {"selected" if days == 90 else ""}>Last 90 days</option>
                        <option value="365" {"selected" if days == 365 else ""}>Last year</option>
                    </select>
                </div>
            </form>
        </div>
        
        <!-- Movements Table -->
        <div class="card" style="overflow-x:auto;">
            <table style="width:100%;">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Item</th>
                        <th style="text-align:center;">Movement</th>
                        <th>Reference</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        '''
        
        return render_page("Stock Movements", content, user, "stock")
    
    
    @app.route("/stock/<stock_id>")
    @login_required
    def stock_detail(stock_id):
        """Stock Item Detail - EVERYTHING about one item in one place"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        currency = business.get("currency", "R") if business else "R"
        
        if not biz_id:
            return redirect("/stock")
        
        # Get the stock item
        item = db.get_one_stock(stock_id)
        if not item or item.get("business_id") != biz_id:
            flash("Stock item not found", "error")
            return redirect("/stock")
        
        code = item.get("code", "")
        desc = item.get("description", "Unknown")
        qty = float(item.get("quantity", 0) or 0)
        cost = float(item.get("cost_price", 0) or 0)
        price = float(item.get("selling_price", 0) or 0)
        category = item.get("category", "General")
        unit = item.get("unit", "each")
        reorder = int(item.get("reorder_level", 0) or 0)
        
        # Calculate stock value
        stock_value = qty * cost
        potential_revenue = qty * price
        potential_profit = potential_revenue - stock_value
        margin_pct = ((price - cost) / price * 100) if price > 0 else 0
        
        # === GATHER ALL HISTORY ===
        
        # 1. Stock Movements
        all_movements = db.get("stock_movements", {"business_id": biz_id}) or []
        movements = [m for m in all_movements if m.get("stock_id") == stock_id or str(m.get("item_code", "")).upper() == code.upper()]
        movements.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        # 2. Purchase History (from goods_received and supplier_invoices)
        purchases = []
        
        # From goods_received
        all_grn = db.get("goods_received", {"business_id": biz_id}) or []
        for grn in all_grn:
            items = grn.get("items", [])
            if not isinstance(items, list):
                continue
            for line in items:
                if not isinstance(line, dict):
                    continue
                if str(line.get("code", "")).upper() == code.upper() or str(line.get("stock_id", "")) == stock_id:
                    purchases.append({
                        "date": grn.get("date", ""),
                        "supplier": grn.get("supplier_name", "Unknown"),
                        "qty": float(line.get("qty", line.get("quantity", 0)) or 0),
                        "cost": float(line.get("cost", line.get("unit_cost", line.get("cost_price", 0))) or 0),
                        "total": float(line.get("total", line.get("line_total", 0)) or 0),
                        "ref": grn.get("grn_number", grn.get("reference", "")),
                        "type": "GRN"
                    })
        
        # From supplier_invoices
        all_bills = db.get("supplier_invoices", {"business_id": biz_id}) or []
        for bill in all_bills:
            items = bill.get("items", [])
            if not isinstance(items, list):
                continue
            for line in items:
                if not isinstance(line, dict):
                    continue
                if str(line.get("code", "")).upper() == code.upper():
                    purchases.append({
                        "date": bill.get("date", ""),
                        "supplier": bill.get("supplier_name", "Unknown"),
                        "qty": float(line.get("qty", line.get("quantity", 0)) or 0),
                        "cost": float(line.get("unit_price", line.get("cost", 0)) or 0),
                        "total": float(line.get("total", line.get("line_total", 0)) or 0),
                        "ref": bill.get("invoice_number", bill.get("number", "")),
                        "type": "Invoice"
                    })
        
        purchases.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        # 3. Sales History (from invoices and pos_sales)
        sales = []
        
        # From invoices
        all_invoices = db.get("invoices", {"business_id": biz_id}) or []
        for inv in all_invoices:
            items = inv.get("items", [])
            if not isinstance(items, list):
                continue
            for line in items:
                if not isinstance(line, dict):
                    continue
                if str(line.get("code", line.get("item_code", ""))).upper() == code.upper():
                    sales.append({
                        "date": inv.get("date", ""),
                        "customer": inv.get("customer_name", "Walk-in"),
                        "qty": float(line.get("qty", line.get("quantity", 0)) or 0),
                        "price": float(line.get("price", line.get("unit_price", 0)) or 0),
                        "total": float(line.get("total", line.get("line_total", 0)) or 0),
                        "ref": inv.get("invoice_number", ""),
                        "type": "Invoice"
                    })
        
        # From POS sales
        all_pos = db.get("pos_sales", {"business_id": biz_id}) or []
        for sale in all_pos:
            items = sale.get("items", [])
            if not isinstance(items, list):
                continue
            for line in items:
                if not isinstance(line, dict):
                    continue
                if str(line.get("code", line.get("item_code", ""))).upper() == code.upper():
                    sales.append({
                        "date": sale.get("date", ""),
                        "customer": sale.get("customer_name", "Walk-in"),
                        "qty": float(line.get("qty", line.get("quantity", 0)) or 0),
                        "price": float(line.get("price", line.get("unit_price", 0)) or 0),
                        "total": float(line.get("total", line.get("line_total", 0)) or 0),
                        "ref": sale.get("receipt_number", sale.get("sale_number", "")),
                        "type": "POS"
                    })
        
        sales.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        # 4. Job Usage (from job_materials)
        job_usage = []
        all_job_materials = db.get("job_materials", {"business_id": biz_id}) or []
        all_jobs = db.get("jobs", {"business_id": biz_id}) or []
        job_lookup = {j.get("id"): j for j in all_jobs}
        
        for jm in all_job_materials:
            if str(jm.get("item_code", jm.get("code", ""))).upper() == code.upper() or str(jm.get("stock_id", "")) == stock_id:
                job = job_lookup.get(jm.get("job_card_id", jm.get("job_id", "")), {})
                job_usage.append({
                    "date": jm.get("date", jm.get("created_at", ""))[:10],
                    "job_number": job.get("job_number", jm.get("job_card_id", "")[:8]),
                    "job_title": job.get("title", job.get("description", ""))[:40],
                    "customer": job.get("customer_name", ""),
                    "qty": float(jm.get("qty", jm.get("quantity", 0)) or 0),
                    "cost": float(jm.get("unit_cost", jm.get("cost", 0)) or 0)
                })
        
        job_usage.sort(key=lambda x: x.get("date", ""), reverse=True)
        
        # === CALCULATE STATS ===
        total_purchased = sum(p.get("qty", 0) for p in purchases)
        total_purchase_value = sum(p.get("total", 0) for p in purchases)
        avg_purchase_cost = total_purchase_value / total_purchased if total_purchased > 0 else 0
        
        total_sold = sum(s.get("qty", 0) for s in sales)
        total_sales_value = sum(s.get("total", 0) for s in sales)
        avg_sale_price = total_sales_value / total_sold if total_sold > 0 else 0
        
        total_job_usage = sum(j.get("qty", 0) for j in job_usage)
        
        # Unique suppliers
        unique_suppliers = list(set(p.get("supplier", "") for p in purchases if p.get("supplier")))
        
        # Last purchase info
        last_purchase = purchases[0] if purchases else None
        last_sale = sales[0] if sales else None
        
        # === GATHER DELIVERY NOTES & QUOTES ===
        
        # 5. Delivery Notes (item leaving the building)
        deliveries = []
        try:
            all_dn = db.get("delivery_notes", {"business_id": biz_id}) or []
            for dn in all_dn:
                dn_items = dn.get("items", [])
                if not isinstance(dn_items, list):
                    continue
                for line in dn_items:
                    if not isinstance(line, dict):
                        continue
                    if str(line.get("code", line.get("item_code", ""))).upper() == code.upper():
                        deliveries.append({
                            "date": dn.get("date", dn.get("delivery_date", "")),
                            "customer": dn.get("customer_name", ""),
                            "qty": float(line.get("qty", line.get("quantity", 0)) or 0),
                            "ref": dn.get("delivery_note_number", dn.get("dn_number", dn.get("reference", ""))),
                            "invoice_ref": dn.get("invoice_number", ""),
                            "status": dn.get("status", "delivered")
                        })
            deliveries.sort(key=lambda x: x.get("date", ""), reverse=True)
        except:
            deliveries = []
        
        # 6. Quotes that include this item
        quotes = []
        try:
            all_quotes = db.get("quotes", {"business_id": biz_id}) or []
            for q in all_quotes:
                q_items = q.get("items", [])
                if not isinstance(q_items, list):
                    continue
                for line in q_items:
                    if not isinstance(line, dict):
                        continue
                    if str(line.get("code", line.get("item_code", ""))).upper() == code.upper():
                        quotes.append({
                            "date": q.get("date", ""),
                            "customer": q.get("customer_name", ""),
                            "qty": float(line.get("qty", line.get("quantity", 0)) or 0),
                            "price": float(line.get("price", line.get("unit_price", 0)) or 0),
                            "total": float(line.get("total", line.get("line_total", 0)) or 0),
                            "ref": q.get("quote_number", ""),
                            "status": q.get("status", "draft")
                        })
            quotes.sort(key=lambda x: x.get("date", ""), reverse=True)
        except:
            quotes = []
        
        # === BUILD TIMELINE (Full lifecycle of the item) ===
        timeline_events = []
        
        # Add purchases to timeline
        for p in purchases:
            timeline_events.append({
                "date": p.get("date", ""),
                "icon": "🛒",
                "color": "#3b82f6",
                "title": f"Purchased from {safe_string(p.get('supplier', 'Unknown'))}",
                "detail": f"{p.get('qty', 0):.0f} x {currency}{p.get('cost', 0):,.2f} = {currency}{p.get('total', 0):,.2f}",
                "ref": p.get("ref", ""),
                "ref_type": p.get("type", ""),
                "sort": 1
            })
        
        # Add sales to timeline
        for s in sales:
            timeline_events.append({
                "date": s.get("date", ""),
                "icon": "💰",
                "color": "#10b981",
                "title": f"Sold to {safe_string(s.get('customer', 'Walk-in'))}",
                "detail": f"{s.get('qty', 0):.0f} x {currency}{s.get('price', 0):,.2f} = {currency}{s.get('total', 0):,.2f}",
                "ref": s.get("ref", ""),
                "ref_type": s.get("type", ""),
                "sort": 3
            })
        
        # Add deliveries to timeline
        for d in deliveries:
            timeline_events.append({
                "date": d.get("date", ""),
                "icon": "🚚",
                "color": "#8b5cf6",
                "title": f"Delivered to {safe_string(d.get('customer', ''))}",
                "detail": f"{d.get('qty', 0):.0f} units delivered",
                "ref": d.get("ref", ""),
                "ref_type": "Delivery Note",
                "sort": 4
            })
        
        # Add job usage to timeline
        for j in job_usage:
            timeline_events.append({
                "date": j.get("date", ""),
                "icon": "🔧",
                "color": "#f59e0b",
                "title": f"Used in Job {j.get('job_number', '')} - {safe_string(j.get('customer', ''))}",
                "detail": f"{j.get('qty', 0):.0f} units used | {safe_string(j.get('job_title', ''))}",
                "ref": j.get("job_number", ""),
                "ref_type": "Job Card",
                "sort": 3
            })
        
        # Add stock movements to timeline
        for m in movements:
            m_qty = float(m.get("quantity", 0) or 0)
            m_type = m.get("movement_type", m.get("type", "adjustment"))
            timeline_events.append({
                "date": str(m.get("created_at", m.get("date", "")))[:10],
                "icon": "📦" if m_qty > 0 else "📤",
                "color": "#10b981" if m_qty > 0 else "#ef4444",
                "title": f"Stock {m_type}: {m_qty:+.0f} units",
                "detail": m.get("reference", m.get("note", ""))[:50],
                "ref": "",
                "ref_type": "Movement",
                "sort": 2
            })
        
        # Add quotes to timeline
        for q in quotes:
            status_emoji = "✅" if q.get("status") == "accepted" else "⏳" if q.get("status") == "sent" else "📝"
            timeline_events.append({
                "date": q.get("date", ""),
                "icon": status_emoji,
                "color": "#6366f1",
                "title": f"Quoted to {safe_string(q.get('customer', ''))}",
                "detail": f"{q.get('qty', 0):.0f} x {currency}{q.get('price', 0):,.2f} = {currency}{q.get('total', 0):,.2f} ({q.get('status', 'draft')})",
                "ref": q.get("ref", ""),
                "ref_type": "Quote",
                "sort": 0
            })
        
        # Sort timeline by date (newest first), then by sort order
        timeline_events.sort(key=lambda x: (x.get("date", ""), x.get("sort", 0)), reverse=True)
        
        # Build timeline HTML
        timeline_html = ""
        for evt in timeline_events[:50]:
            ref_badge = f'<span style="background:rgba(255,255,255,0.1);padding:2px 8px;border-radius:4px;font-size:11px;margin-left:8px;">{evt["ref_type"]}: {evt["ref"]}</span>' if evt.get("ref") else ""
            timeline_html += f'''
            <div style="display:flex;gap:15px;padding:12px 0;border-bottom:1px solid var(--border);">
                <div style="width:40px;height:40px;border-radius:50%;background:{evt["color"]}22;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;">
                    {evt["icon"]}
                </div>
                <div style="flex:1;min-width:0;">
                    <div style="display:flex;align-items:center;flex-wrap:wrap;gap:5px;">
                        <strong style="color:{evt['color']};">{evt["title"]}</strong>
                        {ref_badge}
                    </div>
                    <div style="color:var(--text-muted);font-size:13px;margin-top:2px;">{evt["detail"]}</div>
                </div>
                <div style="color:var(--text-muted);font-size:12px;white-space:nowrap;">{evt["date"]}</div>
            </div>'''
        
        if not timeline_html:
            timeline_html = '<div style="text-align:center;color:var(--text-muted);padding:40px;">No history yet - this item has no recorded activity</div>'
        
        # === BUILD HTML ===
        
        # Movement rows
        movement_rows = ""
        for m in movements[:20]:
            m_type = m.get("movement_type", m.get("type", ""))
            m_qty = float(m.get("quantity", 0) or 0)
            m_date = str(m.get("created_at", m.get("date", "")))[:10]
            m_ref = m.get("reference", m.get("note", ""))[:30]
            color = "#10b981" if m_qty > 0 else "#ef4444"
            movement_rows += f'<tr><td>{m_date}</td><td>{m_type}</td><td style="color:{color};font-weight:bold;">{m_qty:+.0f}</td><td>{m_ref}</td></tr>'
        
        if not movement_rows:
            movement_rows = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:20px;">No movements recorded</td></tr>'
        
        # Purchase rows
        purchase_rows = ""
        for p in purchases[:15]:
            purchase_rows += f'''<tr>
                <td>{p.get("date", "-")}</td>
                <td><strong>{safe_string(p.get("supplier", ""))}</strong></td>
                <td style="text-align:right;">{p.get("qty", 0):.0f}</td>
                <td style="text-align:right;">{currency}{p.get("cost", 0):,.2f}</td>
                <td style="text-align:right;font-weight:bold;">{currency}{p.get("total", 0):,.2f}</td>
                <td><span style="background:rgba(59,130,246,0.15);color:#3b82f6;padding:2px 8px;border-radius:4px;font-size:12px;">{p.get("type", "")}</span> {p.get("ref", "")}</td>
            </tr>'''
        
        if not purchase_rows:
            purchase_rows = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">No purchase history</td></tr>'
        
        # Sales rows - enhanced with customer name prominent and invoice number
        sales_rows = ""
        for s in sales[:15]:
            type_color = "#10b981" if s.get("type") == "Invoice" else "#f59e0b"
            sales_rows += f'''<tr>
                <td>{s.get("date", "-")}</td>
                <td><strong style="font-size:14px;">{safe_string(s.get("customer", "Walk-in"))}</strong></td>
                <td><span style="background:rgba({("16,185,129" if s.get("type") == "Invoice" else "245,158,11")},0.15);color:{type_color};padding:2px 8px;border-radius:4px;font-size:12px;">{s.get("type", "")}</span> <strong>{s.get("ref", "")}</strong></td>
                <td style="text-align:right;">{s.get("qty", 0):.0f}</td>
                <td style="text-align:right;">{currency}{s.get("price", 0):,.2f}</td>
                <td style="text-align:right;font-weight:bold;color:#10b981;">{currency}{s.get("total", 0):,.2f}</td>
            </tr>'''
        
        if not sales_rows:
            sales_rows = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">No sales history</td></tr>'
        
        # Job usage rows
        job_rows = ""
        for j in job_usage[:10]:
            job_rows += f'''<tr>
                <td>{j.get("date", "-")}</td>
                <td><strong>{j.get("job_number", "")}</strong></td>
                <td>{safe_string(j.get("job_title", ""))}</td>
                <td>{safe_string(j.get("customer", ""))}</td>
                <td style="text-align:right;">{j.get("qty", 0):.0f}</td>
                <td style="text-align:right;">{currency}{j.get("cost", 0):,.2f}</td>
            </tr>'''
        
        if not job_rows:
            job_rows = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">Not used in any jobs</td></tr>'
        
        # Delivery rows
        delivery_rows = ""
        for d in deliveries[:10]:
            status_badge = '<span style="background:#10b981;color:white;padding:2px 8px;border-radius:4px;font-size:11px;">Delivered</span>' if d.get("status") == "delivered" else '<span style="background:#f59e0b;color:white;padding:2px 8px;border-radius:4px;font-size:11px;">Pending</span>'
            delivery_rows += f'''<tr>
                <td>{d.get("date", "-")}</td>
                <td><strong>{safe_string(d.get("customer", ""))}</strong></td>
                <td style="text-align:right;">{d.get("qty", 0):.0f}</td>
                <td>{d.get("ref", "")}</td>
                <td>{d.get("invoice_ref", "")}</td>
                <td>{status_badge}</td>
            </tr>'''
        
        if not delivery_rows:
            delivery_rows = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:20px;">No deliveries recorded</td></tr>'
        
        # Supplier chips
        supplier_chips = ""
        for sup in unique_suppliers[:5]:
            supplier_chips += f'<span style="background:var(--primary);color:white;padding:4px 10px;border-radius:12px;font-size:12px;margin:2px;">{safe_string(sup)}</span> '
        
        if not supplier_chips:
            supplier_chips = '<span style="color:var(--text-muted);">No suppliers on record</span>'
        
        # Stock status
        if qty <= 0:
            stock_status = '<span style="background:#ef4444;color:white;padding:4px 12px;border-radius:12px;">OUT OF STOCK</span>'
        elif qty <= reorder:
            stock_status = '<span style="background:#f59e0b;color:white;padding:4px 12px;border-radius:12px;">LOW STOCK</span>'
        else:
            stock_status = '<span style="background:#10b981;color:white;padding:4px 12px;border-radius:12px;">IN STOCK</span>'
        
        # Total events for timeline badge
        total_events = len(timeline_events)
        
        content = f'''
        <div style="margin-bottom:20px;">
            <a href="/stock" style="color:var(--primary);text-decoration:none;">← Back to Stock</a>
        </div>
        
        <!-- Item Header -->
        <div class="card" style="margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:15px;">
                <div>
                    <div style="display:flex;align-items:center;gap:15px;margin-bottom:10px;">
                        <h1 style="margin:0;font-size:28px;">{safe_string(desc)}</h1>
                        {stock_status}
                    </div>
                    <div style="color:var(--text-muted);font-size:14px;">
                        <strong>Code:</strong> {code or '-'} &nbsp;|&nbsp; 
                        <strong>Category:</strong> {category} &nbsp;|&nbsp;
                        <strong>Unit:</strong> {unit}
                    </div>
                </div>
                <div style="display:flex;gap:10px;">
                    <a href="/stock/edit/{stock_id}" class="btn btn-primary">✏️ Edit Item</a>
                    <button onclick="showAdjustModal()" class="btn btn-secondary">📦 Adjust Stock</button>
                </div>
            </div>
        </div>
        
        <!-- Key Numbers -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-bottom:20px;">
            <div class="card" style="text-align:center;padding:20px;">
                <div style="font-size:32px;font-weight:bold;color:var(--primary);">{qty:,.0f}</div>
                <div style="color:var(--text-muted);font-size:13px;">Quantity on Hand</div>
            </div>
            <div class="card" style="text-align:center;padding:20px;">
                <div style="font-size:32px;font-weight:bold;">{currency}{cost:,.2f}</div>
                <div style="color:var(--text-muted);font-size:13px;">Cost Price</div>
            </div>
            <div class="card" style="text-align:center;padding:20px;">
                <div style="font-size:32px;font-weight:bold;color:#10b981;">{currency}{price:,.2f}</div>
                <div style="color:var(--text-muted);font-size:13px;">Selling Price</div>
            </div>
            <div class="card" style="text-align:center;padding:20px;">
                <div style="font-size:32px;font-weight:bold;">{margin_pct:.1f}%</div>
                <div style="color:var(--text-muted);font-size:13px;">Margin</div>
            </div>
            <div class="card" style="text-align:center;padding:20px;">
                <div style="font-size:32px;font-weight:bold;">{currency}{stock_value:,.0f}</div>
                <div style="color:var(--text-muted);font-size:13px;">Stock Value</div>
            </div>
        </div>
        
        <!-- Quick Stats -->
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin-bottom:15px;">📊 Quick Stats</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;">
                <div>
                    <div style="color:var(--text-muted);font-size:12px;margin-bottom:3px;">Total Purchased</div>
                    <div style="font-size:18px;font-weight:bold;">{total_purchased:,.0f} units ({currency}{total_purchase_value:,.0f})</div>
                </div>
                <div>
                    <div style="color:var(--text-muted);font-size:12px;margin-bottom:3px;">Total Sold</div>
                    <div style="font-size:18px;font-weight:bold;color:#10b981;">{total_sold:,.0f} units ({currency}{total_sales_value:,.0f})</div>
                </div>
                <div>
                    <div style="color:var(--text-muted);font-size:12px;margin-bottom:3px;">Used in Jobs</div>
                    <div style="font-size:18px;font-weight:bold;">{total_job_usage:,.0f} units</div>
                </div>
                <div>
                    <div style="color:var(--text-muted);font-size:12px;margin-bottom:3px;">Avg Purchase Cost</div>
                    <div style="font-size:18px;font-weight:bold;">{currency}{avg_purchase_cost:,.2f}</div>
                </div>
                <div>
                    <div style="color:var(--text-muted);font-size:12px;margin-bottom:3px;">Avg Sale Price</div>
                    <div style="font-size:18px;font-weight:bold;">{currency}{avg_sale_price:,.2f}</div>
                </div>
                <div>
                    <div style="color:var(--text-muted);font-size:12px;margin-bottom:3px;">Reorder Level</div>
                    <div style="font-size:18px;font-weight:bold;">{reorder}</div>
                </div>
            </div>
        </div>
        
        <!-- Suppliers -->
        <div class="card" style="margin-bottom:20px;">
            <h3 style="margin-bottom:10px;">🏭 Suppliers</h3>
            <div style="display:flex;flex-wrap:wrap;gap:5px;">
                {supplier_chips}
            </div>
            {f'<div style="margin-top:10px;padding:10px;background:rgba(16,185,129,0.1);border-radius:8px;"><strong>Last purchased:</strong> {last_purchase.get("date", "")} from {last_purchase.get("supplier", "")} - {last_purchase.get("qty", 0):.0f} x {currency}{last_purchase.get("cost", 0):,.2f}</div>' if last_purchase else ''}
        </div>
        
        <!-- Tabs for History -->
        <div class="card">
            <div style="display:flex;gap:5px;border-bottom:1px solid var(--border);margin-bottom:15px;padding-bottom:10px;flex-wrap:wrap;">
                <button onclick="showTab('timeline')" class="tab-btn active" id="tab-timeline">📜 Timeline ({total_events})</button>
                <button onclick="showTab('purchases')" class="tab-btn" id="tab-purchases">🛒 Purchases ({len(purchases)})</button>
                <button onclick="showTab('sales')" class="tab-btn" id="tab-sales">💰 Sales ({len(sales)})</button>
                <button onclick="showTab('deliveries')" class="tab-btn" id="tab-deliveries">🚚 Deliveries ({len(deliveries)})</button>
                <button onclick="showTab('movements')" class="tab-btn" id="tab-movements">📦 Movements ({len(movements)})</button>
                <button onclick="showTab('jobs')" class="tab-btn" id="tab-jobs">🔧 Jobs ({len(job_usage)})</button>
            </div>
            
            <!-- Timeline Tab (DEFAULT - full lifecycle) -->
            <div id="panel-timeline" class="tab-panel">
                <div style="padding:0 5px;">
                    {timeline_html}
                </div>
            </div>
            
            <!-- Purchases Tab -->
            <div id="panel-purchases" class="tab-panel" style="display:none;">
                <table class="table">
                    <thead><tr><th>Date</th><th>Supplier</th><th style="text-align:right;">Qty</th><th style="text-align:right;">Cost</th><th style="text-align:right;">Total</th><th>Type / Ref</th></tr></thead>
                    <tbody>{purchase_rows}</tbody>
                </table>
            </div>
            
            <!-- Sales Tab -->
            <div id="panel-sales" class="tab-panel" style="display:none;">
                <table class="table">
                    <thead><tr><th>Date</th><th>Customer</th><th>Invoice / Receipt</th><th style="text-align:right;">Qty</th><th style="text-align:right;">Price</th><th style="text-align:right;">Total</th></tr></thead>
                    <tbody>{sales_rows}</tbody>
                </table>
            </div>
            
            <!-- Deliveries Tab -->
            <div id="panel-deliveries" class="tab-panel" style="display:none;">
                <table class="table">
                    <thead><tr><th>Date</th><th>Customer</th><th style="text-align:right;">Qty</th><th>DN #</th><th>Invoice Ref</th><th>Status</th></tr></thead>
                    <tbody>{delivery_rows}</tbody>
                </table>
            </div>
            
            <!-- Movements Tab -->
            <div id="panel-movements" class="tab-panel" style="display:none;">
                <table class="table">
                    <thead><tr><th>Date</th><th>Type</th><th>Qty</th><th>Reference</th></tr></thead>
                    <tbody>{movement_rows}</tbody>
                </table>
            </div>
            
            <!-- Jobs Tab -->
            <div id="panel-jobs" class="tab-panel" style="display:none;">
                <table class="table">
                    <thead><tr><th>Date</th><th>Job #</th><th>Description</th><th>Customer</th><th style="text-align:right;">Qty Used</th><th style="text-align:right;">Cost</th></tr></thead>
                    <tbody>{job_rows}</tbody>
                </table>
            </div>
        </div>
        
        <!-- Adjust Stock Modal -->
        <div id="adjustModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:1000;align-items:center;justify-content:center;">
            <div style="background:var(--card);padding:25px;border-radius:12px;max-width:400px;width:90%;">
                <h3 style="margin-bottom:15px;">📦 Adjust Stock</h3>
                <form method="POST" action="/api/stock/adjust">
                    <input type="hidden" name="stock_id" value="{stock_id}">
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;">Adjustment Type</label>
                        <select name="type" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);">
                            <option value="add">➕ Add Stock (received, found, correction)</option>
                            <option value="remove">➖ Remove Stock (damaged, lost, used)</option>
                            <option value="set">🔄 Set Exact Quantity (stocktake)</option>
                        </select>
                    </div>
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;">Quantity</label>
                        <input type="number" name="quantity" step="0.01" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);">
                    </div>
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;">Reason/Note</label>
                        <input type="text" name="note" placeholder="e.g., Stocktake adjustment" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text);">
                    </div>
                    <div style="display:flex;gap:10px;">
                        <button type="submit" class="btn btn-primary" style="flex:1;">Save Adjustment</button>
                        <button type="button" onclick="hideAdjustModal()" class="btn btn-secondary">Cancel</button>
                    </div>
                </form>
            </div>
        </div>
        
        <style>
            .tab-btn {{ padding:8px 16px;border:none;background:transparent;color:var(--text-muted);cursor:pointer;border-radius:6px;font-size:13px; }}
            .tab-btn:hover {{ background:var(--bg); }}
            .tab-btn.active {{ background:var(--primary);color:white; }}
        </style>
        
        <script>
            function showTab(name) {{
                document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.getElementById('panel-' + name).style.display = 'block';
                document.getElementById('tab-' + name).classList.add('active');
            }}
            
            function showAdjustModal() {{
                document.getElementById('adjustModal').style.display = 'flex';
            }}
            
            function hideAdjustModal() {{
                document.getElementById('adjustModal').style.display = 'none';
            }}
        </script>
        '''
        
        return render_page(f"Stock: {desc}", content, user, "stock")
    
    
    @app.route("/stock/new", methods=["GET", "POST"])
    @login_required
    def stock_new():
        """Add new stock item form"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get categories for dropdown
        all_stock = db.get_all_stock(biz_id)
        categories = sorted(set(s.get("category") or "General" for s in all_stock))
        
        if request.method == "POST":
            code = request.form.get("code", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "").strip()
            cost_price = request.form.get("cost_price", "0")
            selling_price = request.form.get("selling_price", "0")
            quantity = request.form.get("quantity", "0")
            
            try:
                cost_price = float(cost_price.replace(",", "").replace("R", "").strip() or 0)
                selling_price = float(selling_price.replace(",", "").replace("R", "").strip() or 0)
                quantity = float(quantity.replace(",", "").strip() or 0)
            except:
                cost_price, selling_price, quantity = 0, 0, 0
            
            if not description:
                flash("Description is required", "error")
            elif request.form.get("force_save") != "1":
                # DUPLICATE DETECTION: Check exact code match, exact desc match, and fuzzy word match
                dup_warnings = []
                
                if code:
                    existing_by_code = [s for s in all_stock if s.get("code", "").strip().upper() == code.upper()]
                    if existing_by_code:
                        e = existing_by_code[0]
                        dup_warnings.append(f"⚠️ Code <strong>{code}</strong> already exists: {safe_string(e.get('description', ''))} (Qty: {e.get('qty', e.get('quantity', 0))})")
                
                if description:
                    desc_lower = description.lower().strip()
                    desc_words = set(desc_lower.replace("-", " ").split())
                    
                    for s in all_stock:
                        s_desc = (s.get("description") or "").lower().strip()
                        s_code = (s.get("code") or "").lower().strip()
                        s_words = set(s_desc.replace("-", " ").split()) | set(s_code.replace("-", " ").split())
                        
                        # Exact description match
                        if s_desc == desc_lower:
                            dup_warnings.append(f"⚠️ Exact match: <strong>{safe_string(s.get('description', ''))}</strong> [{s.get('code', '')}] (Qty: {s.get('qty', s.get('quantity', 0))})")
                            continue
                        
                        # Word overlap: if 2+ words match (catches BOLT-TEST vs TEST-BOLT)
                        if len(desc_words) >= 2 and len(desc_words & s_words) >= 2:
                            dup_warnings.append(f"⚠️ Similar: <strong>{safe_string(s.get('description', ''))}</strong> [{s.get('code', '')}] (Qty: {s.get('qty', s.get('quantity', 0))})")
                        elif len(desc_words) == 1 and desc_words & s_words:
                            # Single word exact match in code or description
                            if desc_lower in s_desc or desc_lower in s_code:
                                dup_warnings.append(f"⚠️ Similar: <strong>{safe_string(s.get('description', ''))}</strong> [{s.get('code', '')}] (Qty: {s.get('qty', s.get('quantity', 0))})")
                        
                        if len(dup_warnings) >= 5:
                            break  # Don't show too many
                
                if dup_warnings:
                    warnings_html = "<br>".join(dup_warnings[:5])
                    # Show warning with "Save Anyway" button
                    flash(f"Possible duplicates found! Review below.", "error")
                    dup_form = f'''<div class="card">
                        <h3 style="color:var(--orange);margin-top:0;">⚠️ Possible Duplicates Found</h3>
                        <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px;padding:15px;margin-bottom:15px;">
                            {warnings_html}
                        </div>
                        <p>If this is a <strong>different item</strong>, click "Save Anyway":</p>
                        <form method="POST" style="display:flex;gap:10px;">
                            <input type="hidden" name="code" value="{safe_string(code)}">
                            <input type="hidden" name="description" value="{safe_string(description)}">
                            <input type="hidden" name="category" value="{safe_string(request.form.get('category', ''))}">
                            <input type="hidden" name="cost_price" value="{request.form.get('cost_price', '0')}">
                            <input type="hidden" name="selling_price" value="{request.form.get('selling_price', '0')}">
                            <input type="hidden" name="quantity" value="{request.form.get('quantity', '0')}">
                            <input type="hidden" name="force_save" value="1">
                            <button type="submit" class="btn btn-primary" style="background:var(--orange);">✓ Save Anyway — It's Different</button>
                            <a href="/stock" class="btn btn-secondary">✕ Cancel</a>
                        </form>
                    </div>'''
                    return render_page("Add Stock — Duplicate Warning", dup_form, user, "stock")
                
                # No duplicates found, proceed to save
                stock_id = generate_id()
                
                # Auto-generate code if not provided
                if not code:
                    words = description.upper().split()[:3]
                    code = "-".join(w[:4] for w in words if w)
                
                # Use RecordFactory.stock_item() for 'stock_items' table
                item = RecordFactory.stock_item(
                    business_id=biz_id,
                    description=description,
                    id=stock_id,
                    code=code,
                    category=category or "General",
                    cost_price=cost_price,
                    selling_price=selling_price,
                    quantity=quantity
                )
                
                success, err = db.save_stock(item)
                if success:
                    flash(f"Stock item '{description}' added", "success")
                    return redirect("/stock")
                else:
                    flash(f"Error adding item: {err}", "error")
            else:
                # force_save == "1" — user confirmed it's not a duplicate, save directly
                stock_id = generate_id()
                if not code:
                    words = description.upper().split()[:3]
                    code = "-".join(w[:4] for w in words if w)
                item = RecordFactory.stock_item(
                    business_id=biz_id,
                    description=description,
                    id=stock_id,
                    code=code,
                    category=request.form.get("category", "") or "General",
                    cost_price=cost_price,
                    selling_price=selling_price,
                    quantity=quantity
                )
                success, err = db.save_stock(item)
                if success:
                    flash(f"Stock item '{description}' added (confirmed not duplicate)", "success")
                    return redirect("/stock")
                else:
                    flash(f"Error adding item: {err}", "error")
        
        category_options = '<option value="">-- Select Category --</option>'
        for cat in categories:
            category_options += f'<option value="{cat}">{cat}</option>'
        category_options += '<option value="__new__">+ New Category</option>'
        
        content = f'''
        <div class="card" style="max-width: 600px;">
            <h2 style="margin-bottom: 20px;">Add Stock Item</h2>
            <form method="POST">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Code</label>
                        <input type="text" name="code" placeholder="Auto-generated if blank" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Category</label>
                        <select name="category" id="categorySelect" onchange="checkNewCategory()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                            {category_options}
                        </select>
                    </div>
                </div>
                <div style="margin-bottom: 15px;">
                    <label style="display:block;margin-bottom:5px;font-weight:500;">Description *</label>
                    <input type="text" name="description" required placeholder="e.g., HEX BOLT 16 X 50" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                </div>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;margin-bottom:20px;">
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Cost Price</label>
                        <input type="text" name="cost_price" placeholder="0.00" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Selling Price</label>
                        <input type="text" name="selling_price" placeholder="0.00" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                    <div>
                        <label style="display:block;margin-bottom:5px;font-weight:500;">Quantity</label>
                        <input type="text" name="quantity" placeholder="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">
                    </div>
                </div>
                <div style="display:flex;gap:10px;">
                    <button type="submit" class="btn btn-primary">Add Item</button>
                    <a href="/stock" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        
        <script>
        function checkNewCategory() {{
            const sel = document.getElementById('categorySelect');
            if (sel.value === '__new__') {{
                const newCat = prompt('Enter new category name:');
                if (newCat) {{
                    const opt = document.createElement('option');
                    opt.value = newCat;
                    opt.text = newCat;
                    opt.selected = true;
                    sel.insertBefore(opt, sel.lastElementChild);
                }} else {{
                    sel.value = '';
                }}
            }}
        }}
        </script>
        '''
        
        return render_page("Add Stock", content, user, "stock")
    
    
    # ═══════════════════════════════════════════════════════════════
    # FULLTECH TOOLS - Bolt Pricer (Type-aware, weight-based)
    # ═══════════════════════════════════════════════════════════════
    
    @app.route("/fulltech")
    @login_required
    def fulltech_tools():
        """Fulltech addon tools - type-aware bolt pricing with BoltPricer"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        
        content = f'''
        <div class="card" style="margin-bottom:20px;">
            <h2 style="margin:0 0 10px 0;">🔩 Fulltech Bolt Pricer</h2>
            <p style="color:#888;">v4 — Verified supplier rates (94% binne 20% akkuraatheid). Sets R24/kg, Caps R63/kg, Bolts R30/kg, Studs per-stuk.</p>
        </div>
        
        <!-- SINGLE ITEM CHECK -->
        <div class="card" style="margin-bottom:20px;">
            <h3>⚖️ Quick Price Check</h3>
            <p style="color:#888;margin-bottom:15px;">Type any description — pricer identifies type, material, size and calculates cost</p>
            <div style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
                <div style="flex:1;min-width:250px;">
                    <label style="display:block;margin-bottom:5px;color:#888;">Description</label>
                    <input type="text" id="checkDesc" class="form-control" placeholder="e.g. CAP SCREW M12X50 S/S" 
                        style="width:100%;padding:12px;font-size:15px;" 
                        onkeydown="if(event.key==='Enter')quickCheck()">
                </div>
                <button onclick="quickCheck()" class="btn btn-primary" style="padding:12px 24px;">Check Price</button>
            </div>
            <div id="quickResult" style="display:none;margin-top:15px;padding:15px;background:rgba(16,185,129,0.08);border-radius:8px;border:1px solid rgba(16,185,129,0.2);font-family:monospace;white-space:pre-line;font-size:14px;"></div>
        </div>
        
        <!-- BULK REPRICING -->
        <div class="card">
            <h3>🔄 Bulk Reprice All Stock</h3>
            <p style="color:#888;margin-bottom:20px;">Preview calculated costs for all fasteners, set markup %, then apply</p>
            
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:15px;margin-bottom:20px;">
                <div style="background:rgba(168,85,247,0.08);padding:15px;border-radius:8px;border:1px solid rgba(168,85,247,0.2);">
                    <label style="display:block;margin-bottom:5px;color:#a855f7;font-weight:bold;">Update Mode</label>
                    <select id="updateMode" class="form-control" style="width:100%;padding:10px;">
                        <option value="no_cost_only">A) No Cost Items Only</option>
                        <option value="all_items" selected>B) All Items (full reprice)</option>
                    </select>
                    <small style="color:#888;">A = safe, B = update all to supplier rates</small>
                </div>
                <div style="background:rgba(59,130,246,0.08);padding:15px;border-radius:8px;border:1px solid rgba(59,130,246,0.2);">
                    <label style="display:block;margin-bottom:5px;color:#3b82f6;font-weight:bold;">Markup %</label>
                    <input type="number" id="markupPct" class="form-control" value="30" step="5" min="0" max="200" style="width:100%;padding:10px;font-size:18px;font-weight:bold;text-align:center;">
                    <small style="color:#888;">30% = cost × 1.30</small>
                </div>
                <div style="background:rgba(16,185,129,0.08);padding:15px;border-radius:8px;border:1px solid rgba(16,185,129,0.2);">
                    <label style="display:block;margin-bottom:5px;color:#10b981;font-weight:bold;">Update What?</label>
                    <select id="updateTarget" class="form-control" style="width:100%;padding:10px;">
                        <option value="cost_only">Cost Price Only</option>
                        <option value="cost_and_sell" selected>Cost + Selling Price</option>
                        <option value="sell_only">Selling Price Only</option>
                    </select>
                </div>
                <div style="background:rgba(251,191,36,0.08);padding:15px;border-radius:8px;border:1px solid rgba(251,191,36,0.2);">
                    <label style="display:block;margin-bottom:5px;color:#fbbf24;font-weight:bold;">Max Change %</label>
                    <input type="number" id="maxChangePct" class="form-control" value="50" step="10" min="10" max="500" style="width:100%;padding:10px;font-size:18px;font-weight:bold;text-align:center;">
                    <small style="color:#888;">Skip items with bigger changes</small>
                </div>
            </div>
            
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;">
                <button onclick="loadPreview()" class="btn btn-primary" id="btnPreview">📊 Preview All Stock</button>
                <button onclick="applyAll()" class="btn" style="background:#22c55e;" id="btnApply" disabled>✅ Apply Changes</button>
                <span id="itemCount" style="color:#888;padding:10px;font-size:13px;"></span>
            </div>
            
            <div id="statusMsg" style="display:none;padding:12px;border-radius:8px;margin-bottom:15px;"></div>
            
            <!-- STATS -->
            <div id="statsRow" style="display:none;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:15px;"></div>
            
            <!-- FILTER -->
            <div id="filterRow" style="display:none;margin-bottom:10px;">
                <input type="text" id="searchBox" class="form-control" placeholder="Soek... (desc, code, type)" oninput="filterTable()" style="padding:10px;width:100%;max-width:400px;margin-bottom:8px;">
                <div style="display:flex;gap:6px;flex-wrap:wrap;">
                    <button class="btn btn-sm flt active" data-f="all" onclick="setFlt(this)">All</button>
                    <button class="btn btn-sm flt" data-f="needs" onclick="setFlt(this)">⭐ No Cost</button>
                    <button class="btn btn-sm flt" data-f="bigup" onclick="setFlt(this)">🔴 Big Up</button>
                    <button class="btn btn-sm flt" data-f="bigdown" onclick="setFlt(this)">🔵 Big Down</button>
                </div>
            </div>
            
            <!-- TABLE -->
            <div id="tableWrap" style="display:none;max-height:65vh;overflow-y:auto;border-radius:8px;border:1px solid #333;">
                <table style="width:100%;border-collapse:collapse;font-size:13px;">
                    <thead>
                        <tr style="background:#1e293b;position:sticky;top:0;">
                            <th style="padding:8px;text-align:left;cursor:pointer;" onclick="doSort('description')">Description</th>
                            <th style="padding:8px;text-align:left;cursor:pointer;" onclick="doSort('type_label')">Type</th>
                            <th style="padding:8px;cursor:pointer;" onclick="doSort('material')">Mat</th>
                            <th style="padding:8px;text-align:right;cursor:pointer;" onclick="doSort('weight_g')">Weight</th>
                            <th style="padding:8px;text-align:right;cursor:pointer;" onclick="doSort('rkg')">R/kg</th>
                            <th style="padding:8px;text-align:right;cursor:pointer;" onclick="doSort('old_cost')">Old Cost</th>
                            <th style="padding:8px;text-align:right;cursor:pointer;color:#10b981;" onclick="doSort('new_cost')">New Cost</th>
                            <th style="padding:8px;text-align:right;cursor:pointer;color:#fbbf24;" onclick="doSort('sell_price')">Sell Price</th>
                            <th style="padding:8px;text-align:right;cursor:pointer;" onclick="doSort('pct_change')">%</th>
                        </tr>
                    </thead>
                    <tbody id="tBody"></tbody>
                </table>
            </div>
        </div>
        
        <style>
            .flt {{ padding:4px 12px;border-radius:6px;border:1px solid #475569;background:transparent;color:#94a3b8;font-size:12px;cursor:pointer; }}
            .flt.active {{ background:#3b82f6;color:white;border-color:#3b82f6; }}
            .stat-box {{ padding:12px;border-radius:8px;background:#1e293b;text-align:center; }}
            .stat-box .num {{ font-size:22px;font-weight:700; }}
            .stat-box .lbl {{ font-size:11px;color:#94a3b8;text-transform:uppercase; }}
        </style>
        
        <script>
        let allData=[], curFilter='all', sortCol='pct_change', sortDir=-1;
        
        function showStatus(msg, ok) {{
            const el=document.getElementById('statusMsg');
            el.textContent=msg;
            el.style.display='block';
            el.style.background=ok?'rgba(16,185,129,0.15)':'rgba(59,130,246,0.15)';
            el.style.borderLeft=ok?'4px solid #10b981':'4px solid #3b82f6';
        }}
        
        async function quickCheck() {{
            const desc=document.getElementById('checkDesc').value.trim();
            if(!desc) return;
            const res=await fetch('/api/fulltech/bolt-check',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{description:desc}})}});
            const d=await res.json();
            const el=document.getElementById('quickResult');
            if(d.success) {{
                const markup=parseFloat(document.getElementById('markupPct').value)||30;
                const sell=d.cost*(1+markup/100);
                el.textContent=d.type_label+'  |  '+d.mat_label+'\\nSize: M'+d.m_size+(d.length?'x'+d.length:'')+'  |  Weight: '+d.weight_g+'g\\nR/kg: R'+d.rkg+'  |  Cost: R'+d.cost.toFixed(2)+'\\nMarkup '+markup+'%  →  Sell: R'+sell.toFixed(2);
            }} else {{
                el.textContent='❌ '+d.error;
            }}
            el.style.display='block';
        }}
        
        async function loadPreview() {{
            const btn=document.getElementById('btnPreview');
            btn.disabled=true; btn.textContent='⏳ Loading...';
            showStatus('Pulling stock and calculating prices...', false);
            
            try {{
                const res=await fetch('/api/fulltech/bolt-preview');
                const d=await res.json();
                if(!d.success) {{ showStatus('Error: '+(d.error||'Unknown'),false); btn.disabled=false; btn.textContent='📊 Preview'; return; }}
                
                allData=d.matched||[];
                const s=d.stats;
                
                document.getElementById('statsRow').style.display='grid';
                document.getElementById('statsRow').innerHTML=`
                    <div class="stat-box"><div class="num">${{s.total_stock}}</div><div class="lbl">Total Stock</div></div>
                    <div class="stat-box"><div class="num" style="color:#a78bfa">${{s.fasteners_matched}}</div><div class="lbl">Fasteners</div></div>
                    <div class="stat-box"><div class="num" style="color:#fbbf24">${{s.changes_needed}}</div><div class="lbl">Changes</div></div>
                    <div class="stat-box"><div class="num" style="color:#38bdf8">${{s.needs_cost_price}}</div><div class="lbl">No Cost Yet</div></div>
                    <div class="stat-box"><div class="num" style="color:#10b981">${{s.calibrated_from}}</div><div class="lbl">Verified Items</div></div>
                    <div class="stat-box"><div class="num">${{s.rate_groups}}</div><div class="lbl">Rate Groups</div></div>
                `;
                
                document.getElementById('btnApply').disabled=false;
                document.getElementById('filterRow').style.display='block';
                document.getElementById('tableWrap').style.display='block';
                renderTable();
                showStatus('✅ '+allData.length+' items ready. Adjust markup % and click Apply.', true);
            }} catch(e) {{ showStatus('Error: '+e.message, false); }}
            btn.disabled=false; btn.textContent='📊 Refresh';
        }}
        
        function getMarkup() {{ return parseFloat(document.getElementById('markupPct').value)||30; }}
        
        function renderTable() {{
            const markup=getMarkup();
            let items=[...allData];
            const q=document.getElementById('searchBox').value.toLowerCase();
            if(q) items=items.filter(i=>(i.description||'').toLowerCase().includes(q)||(i.code||'').toLowerCase().includes(q)||(i.type_label||'').toLowerCase().includes(q));
            if(curFilter==='needs') items=items.filter(i=>!i.has_cost);
            else if(curFilter==='bigup') items=items.filter(i=>i.pct_change>30);
            else if(curFilter==='bigdown') items=items.filter(i=>i.pct_change<-30);
            items.sort((a,b)=>{{ let va=a[sortCol],vb=b[sortCol]; if(typeof va==='string') return va.localeCompare(vb)*sortDir; return((va||0)-(vb||0))*sortDir; }});
            document.getElementById('itemCount').textContent=items.length+' items';
            
            document.getElementById('tBody').innerHTML=items.map(i=>{{
                const sell=i.new_cost*(1+markup/100);
                const dc=!i.has_cost?'color:#38bdf8':i.pct_change>25?'color:#ef4444':i.pct_change<-25?'color:#22c55e':'color:#888';
                const pctStr=i.has_cost?(i.pct_change>=0?'+':'')+i.pct_change.toFixed(0)+'%':'NEW';
                return `<tr style="border-bottom:1px solid #1e293b;">
                    <td style="padding:6px 8px;"><strong>${{i.description}}</strong></td>
                    <td style="padding:6px;font-size:11px;">${{i.type_label}}</td>
                    <td style="padding:6px;text-align:center;"><span style="padding:1px 6px;border-radius:3px;font-size:11px;background:#334155;">${{i.material}}</span></td>
                    <td style="padding:6px;text-align:right;">${{i.weight_g}}g</td>
                    <td style="padding:6px;text-align:right;color:#888;">R${{i.rkg}}</td>
                    <td style="padding:6px;text-align:right;">${{i.old_cost>0?'R'+i.old_cost.toFixed(2):'—'}}</td>
                    <td style="padding:6px;text-align:right;font-weight:700;color:#10b981;">R${{i.new_cost.toFixed(2)}}</td>
                    <td style="padding:6px;text-align:right;font-weight:700;color:#fbbf24;">R${{sell.toFixed(2)}}</td>
                    <td style="padding:6px;text-align:right;${{dc}};">${{pctStr}}</td>
                </tr>`;
            }}).join('');
        }}
        
        document.getElementById('markupPct').addEventListener('input', ()=>{{ if(allData.length) renderTable(); }});
        function filterTable() {{ renderTable(); }}
        function setFlt(btn) {{ document.querySelectorAll('.flt').forEach(b=>b.classList.remove('active')); btn.classList.add('active'); curFilter=btn.dataset.f; renderTable(); }}
        function doSort(col) {{ if(sortCol===col) sortDir*=-1; else {{ sortCol=col; sortDir=1; }} renderTable(); }}
        
        async function applyAll() {{
            const markup=getMarkup();
            const target=document.getElementById('updateTarget').value;
            const maxPct=parseFloat(document.getElementById('maxChangePct').value)||50;
            const mode=document.getElementById('updateMode').value;
            
            let toApply;
            if(mode==='no_cost_only') {{
                toApply=allData.filter(i=> !i.has_cost);
            }} else {{
                toApply=allData.filter(i=> !i.has_cost || Math.abs(i.pct_change)<=maxPct);
            }}
            const skipping=allData.length-toApply.length;
            const modeLabel=mode==='no_cost_only'?'NO COST ONLY':'ALL (max '+maxPct+'% change)';
            if(!confirm('Mode: '+modeLabel+'\\nApply '+toApply.length+' items (skip '+skipping+')\\nMarkup: '+markup+'%\\nTarget: '+target)) return;
            
            const btn=document.getElementById('btnApply');
            btn.disabled=true; btn.textContent='Applying...';
            showStatus('Writing to database...', false);
            
            const batchSize=50;
            let ok=0, fail=0;
            for(let i=0;i<toApply.length;i+=batchSize) {{
                const batch=toApply.slice(i,i+batchSize).map(it=>({{
                    id:it.id, new_cost:it.new_cost, sell_price:Math.round(it.new_cost*(1+markup/100)*100)/100
                }}));
                try {{
                    const res=await fetch('/api/fulltech/bolt-apply',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{items:batch,target:target}})}});
                    const d=await res.json();
                    ok+=(d.updated||0); fail+=(d.failed||0);
                }} catch(e) {{ fail+=batch.length; }}
            }}
            
            showStatus('✅ Done! '+ok+' updated'+(fail?' ('+fail+' failed)':''), fail===0);
            btn.disabled=false; btn.textContent='✅ Apply Changes';
        }}
        </script>
        '''
        
        return render_page("Fulltech Tools", content, user, "stock")
    
    
    @app.route("/api/fulltech/bolt-check", methods=["POST"])
    @login_required
    def api_fulltech_bolt_check():
        """Single item price check using BoltPricer v4 verified rates"""
        data = request.get_json() or {}
        desc = data.get("description", "")
        if not BoltPricer:
            return jsonify({"success": False, "error": "BoltPricer not loaded"})
        return jsonify(BoltPricer.price(desc))
    
    
    @app.route("/api/fulltech/bolt-preview")
    @login_required
    def api_fulltech_bolt_preview():
        """Preview bolt repricing using v4 verified supplier rates"""
        import time as _time
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        if not BoltPricer:
            return jsonify({"success": False, "error": "BoltPricer not loaded"})
        
        t0 = _time.time()
        all_stock = db.get_all_stock(biz_id)
        
        matched = []
        skipped = []
        no_change = []
        needs_cost = 0
        
        for item in all_stock:
            desc = item.get("description") or item.get("name") or ""
            r = BoltPricer.price(desc)
            if not r.get("success"):
                skipped.append({"id": item.get("id"), "description": desc, "reason": r.get("error", "")})
                continue
            
            old_cost = float(item.get("cost_price") or item.get("cost") or 0)
            new_cost = r["cost"]
            has_cost = old_cost > 0
            
            if not has_cost:
                needs_cost += 1
            
            # Check if change is meaningful (>2%)
            if has_cost and abs(new_cost - old_cost) / old_cost < 0.02:
                no_change.append({"id": item.get("id"), "description": desc})
                continue
            
            pct = ((new_cost - old_cost) / old_cost * 100) if has_cost and old_cost > 0 else 0
            
            matched.append({
                "id": item.get("id"),
                "code": item.get("code") or item.get("sku") or "",
                "description": desc,
                "item_type": r.get("item_type", ""),
                "type_label": r.get("type_label", ""),
                "material": r.get("material", ""),
                "weight_g": r.get("weight_g", 0),
                "rkg": r.get("rkg", 0),
                "old_cost": round(old_cost, 2),
                "new_cost": round(new_cost, 2),
                "has_cost": has_cost,
                "pct_change": round(pct, 1),
                "pricing_method": r.get("pricing_method", "weight_x_rkg"),
                "source": "verified",
            })
        
        matched.sort(key=lambda x: abs(x["pct_change"]), reverse=True)
        elapsed = round(_time.time() - t0, 2)
        
        return jsonify({
            "success": True,
            "stats": {
                "total_stock": len(all_stock),
                "fasteners_matched": len(matched) + len(no_change),
                "changes_needed": len(matched),
                "no_change": len(no_change),
                "not_fasteners": len(skipped),
                "needs_cost_price": needs_cost,
                "calibrated_from": 62,
                "rate_groups": len(BoltPricer.VERIFIED_RKG),
                "elapsed_seconds": elapsed,
            },
            "matched": matched,
            "skipped": skipped[:50],
        })
    
    
    @app.route("/api/fulltech/bolt-apply", methods=["POST"])
    @login_required
    def api_fulltech_bolt_apply():
        """Apply cost + selling price changes"""
        role = get_user_role()
        if role not in ("owner", "admin"):
            return jsonify({"success": False, "error": "Owner/Admin only"})
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        data = request.get_json() or {}
        items = data.get("items", [])
        target = data.get("target", "cost_and_sell")
        
        ok_count = 0
        fail_count = 0
        
        for item in items:
            item_id = item.get("id")
            new_cost = item.get("new_cost")
            sell_price = item.get("sell_price")
            if not item_id:
                fail_count += 1
                continue
            
            updates = {}
            if target in ("cost_only", "cost_and_sell") and new_cost is not None:
                updates["cost_price"] = round(float(new_cost), 2)
            if target in ("sell_only", "cost_and_sell") and sell_price is not None:
                updates["selling_price"] = round(float(sell_price), 2)
            
            if not updates:
                fail_count += 1
                continue
            
            try:
                success = db.update("stock_items", item_id, updates, business_id=biz_id)
                if not success:
                    # Try legacy table
                    legacy = {}
                    if "cost_price" in updates:
                        legacy["cost"] = updates["cost_price"]
                    if "selling_price" in updates:
                        legacy["price"] = updates["selling_price"]
                    success = db.update("stock", item_id, legacy, business_id=biz_id)
                if success:
                    ok_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(f"[FULLTECH] Bolt apply fail {item_id}: {e}")
                fail_count += 1
        
        return jsonify({"success": True, "updated": ok_count, "failed": fail_count})
    
    
    # Keep old endpoints as aliases for backward compatibility
    @app.route("/api/fulltech/calc-bolt")
    @login_required
    def api_fulltech_calc_bolt():
        """Legacy endpoint — redirects to BoltPricer"""
        item_type = request.args.get("type", "bolt")
        m_size = int(request.args.get("m_size", 6))
        length = int(request.args.get("length", 50)) if item_type == "bolt" else None
        rkg = float(request.args.get("rkg", 250))
        result = fulltech_addon.calc_bolt_price(m_size, length, rkg, item_type)
        return jsonify(result)
    
    # ═══════════════════════════════════════════════════════════════
    # STOCK SEARCH API - Server-side search and pagination for 7000+ items
    # ═══════════════════════════════════════════════════════════════
    
    @app.route("/api/stock/all")
    @login_required
    def api_stock_all():
        """Return all stock for listing page — lightweight fields only.
        Full item data loads on the detail page (/stock/<id>)."""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        # Cache stock list for 30 seconds per business (avoid hammering Supabase)
        cache_key = f"stock_list_{biz_id}"
        cached = _pulse_cache.get(cache_key)
        if cached and (time.time() - cached.get("ts", 0)) < 30:
            return jsonify(cached["data"])
        
        items = db.get_all_stock(biz_id)
        
        # Strip to only fields the listing page needs (was sending 6MB+ with full data)
        listing_fields = {"id", "code", "description", "category", "quantity", "qty", 
                          "cost_price", "cost", "selling_price", "price", "unit",
                          "reorder_level", "reorder_qty", "supplier_name", "barcode"}
        slim_items = []
        for item in items:
            slim = {k: v for k, v in item.items() if k in listing_fields}
            slim_items.append(slim)
        
        result = {"success": True, "items": slim_items}
        _pulse_cache[cache_key] = {"data": result, "ts": time.time()}
        return jsonify(result)
    
    
    @app.route("/api/customers/all")
    @login_required
    def api_customers_all():
        """Return all customers for caching"""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        items = db.get("customers", {"business_id": biz_id}) or []
        return jsonify({"success": True, "items": items})
    
    
    @app.route("/api/customers/bulk-email-statements", methods=["POST"])
    @login_required
    def api_customers_bulk_email_statements():
        """Email statements to customers - mode: 'all', 'debtors', or 'zero'"""
        try:
            data = request.get_json() or {}
            mode = data.get("mode", "debtors")  # default to debtors only
            
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            
            # Reload business fresh for accurate details
            if biz_id:
                business = db.get_one("businesses", biz_id) or business
            
            if not biz_id:
                return jsonify({"success": False, "error": "No business"})
            
            # Get all customers
            customers = db.get("customers", {"business_id": biz_id}) or []
            
            # Filter based on mode
            if mode == "all":
                # All customers (with email)
                target_customers = customers
            elif mode == "zero":
                # Only zero balance customers
                target_customers = [c for c in customers if float(c.get("balance", 0)) == 0]
            else:
                # Only debtors (balance > 0)
                target_customers = [c for c in customers if float(c.get("balance", 0)) > 0]
            
            if not target_customers:
                return jsonify({"success": True, "sent": 0, "skipped": 0, "failed": 0, "message": "No customers to email"})
            
            # Get all invoices for statement building
            all_invoices = db.get("invoices", {"business_id": biz_id}) or []
            
            sent = 0
            skipped = 0
            failed = 0
            
            for customer in target_customers:
                email = customer.get("email", "").strip()
                
                if not email or "@" not in email:
                    skipped += 1
                    continue
                
                # Get this customer's invoices
                cust_invoices = [inv for inv in all_invoices if inv.get("customer_id") == customer.get("id")]
                
                try:
                    success = Email.send_statement(customer, cust_invoices, business)
                    if success:
                        sent += 1
                        logger.info(f"[BULK-EMAIL] Statement sent to {customer.get('name')} ({email})")
                    else:
                        failed += 1
                        logger.error(f"[BULK-EMAIL] Failed to send to {customer.get('name')} ({email})")
                except Exception as e:
                    failed += 1
                    logger.error(f"[BULK-EMAIL] Error sending to {customer.get('name')}: {e}")
            
            # Update last sent timestamp
            try:
                user = Auth.get_current_user()
                user_id = user.get("id") if user else None
                settings = business.get("statement_settings", {})
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except:
                        settings = {}
                settings["last_sent"] = now()
                db.update_business(biz_id, user_id, {"statement_settings": json.dumps(settings)})
            except:
                pass
            
            logger.info(f"[BULK-EMAIL] Complete: mode={mode}, sent={sent}, skipped={skipped}, failed={failed}")
            
            return jsonify({
                "success": True,
                "sent": sent,
                "skipped": skipped,
                "failed": failed,
                "message": f"Statements sent to {sent} customers"
            })
            
        except Exception as e:
            logger.error(f"[BULK-EMAIL] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/suppliers/all")
    @login_required
    def api_suppliers_all():
        """Return all suppliers for caching"""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        items = db.get("suppliers", {"business_id": biz_id}) or []
        return jsonify({"success": True, "items": items})
    
    
    @app.route("/api/stock/adjust", methods=["POST"])
    @login_required
    def api_stock_adjust():
        """Adjust stock quantity - add, remove, or set exact"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            flash("No business selected", "error")
            return redirect("/stock")
        
        stock_id = request.form.get("stock_id", "")
        adj_type = request.form.get("type", "add")
        quantity = request.form.get("quantity", "0")
        note = request.form.get("note", "Manual adjustment")
        
        try:
            qty = float(quantity)
        except:
            flash("Invalid quantity", "error")
            return redirect(f"/stock/{stock_id}")
        
        # Get current stock item
        item = db.get_one_stock(stock_id)
        if not item or item.get("business_id") != biz_id:
            flash("Stock item not found", "error")
            return redirect("/stock")
        
        current_qty = float(item.get("quantity", 0) or 0)
        
        # Calculate new quantity
        if adj_type == "add":
            new_qty = current_qty + qty
            movement_qty = qty
            movement_type = "adjustment_in"
        elif adj_type == "remove":
            new_qty = current_qty - qty
            movement_qty = -qty
            movement_type = "adjustment_out"
        else:  # set
            new_qty = qty
            movement_qty = qty - current_qty
            movement_type = "stocktake"
        
        # Update stock
        result = db.update_stock(stock_id, {"quantity": new_qty}, biz_id)
        
        if result:
            # Record movement
            movement = RecordFactory.stock_movement(
                business_id=biz_id,
                stock_id=stock_id,
                movement_type=movement_type,
                quantity=movement_qty,
                reference=note,
                note=f"Previous: {current_qty}, New: {new_qty}",
                created_by=user.get("id", "") if user else ""
            )
            db.save("stock_movements", movement)
            
            # --- GL Journal Entry for stock adjustment ---
            # Use item cost_price to calculate GL value
            cost_price = float(item.get("cost_price", 0) or item.get("cost", 0) or 0)
            gl_amount = abs(movement_qty) * cost_price
            
            if gl_amount > 0:
                try:
                    stock_acc = gl(biz_id, "stock")
                    cogs_acc = gl(biz_id, "cogs")
                    item_name = item.get("name", item.get("description", "Stock item"))
                    item_code = item.get("code", "")
                    ref_label = f"Stock Adj: {item_code} - {item_name}" if item_code else f"Stock Adj: {item_name}"
                    
                    if movement_qty > 0:
                        # Stock IN: DR Stock (asset increases), CR COGS (cost reversal / adjustment)
                        gl_entries = [
                            {"account_code": stock_acc, "debit": gl_amount, "credit": 0},
                            {"account_code": cogs_acc, "debit": 0, "credit": gl_amount},
                        ]
                    else:
                        # Stock OUT: DR COGS (expense), CR Stock (asset decreases)
                        gl_entries = [
                            {"account_code": cogs_acc, "debit": gl_amount, "credit": 0},
                            {"account_code": stock_acc, "debit": 0, "credit": gl_amount},
                        ]
                    
                    create_journal_entry(biz_id, today(), f"{note or 'Stock adjustment'} ({current_qty} → {new_qty})", ref_label, gl_entries)
                    logger.info(f"[STOCK ADJ] GL posted: {ref_label} R{gl_amount:.2f} stock_acc={stock_acc} cogs_acc={cogs_acc}")
                except Exception as gl_err:
                    logger.error(f"[STOCK ADJ] GL entry failed (non-critical): {gl_err}")
            
            flash(f"Stock adjusted: {current_qty} → {new_qty}", "success")
        else:
            flash("Failed to adjust stock", "error")
        
        return redirect(f"/stock/{stock_id}")
    
    
    @app.route("/stock/edit/<stock_id>", methods=["GET", "POST"])
    @login_required
    def stock_edit(stock_id):
        """Edit stock item - redirect to detail page with edit capability"""
        # For now, redirect to detail page
        # The detail page has all the info, edit can be done inline or via modal
        return redirect(f"/stock/{stock_id}")
    
    
    @app.route("/api/stock/search")
    @login_required
    def api_stock_search():
        """Search stock items - handles 7000+ items efficiently"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        query = request.args.get("q", "").strip().lower()
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 100))
        category = request.args.get("category", "").strip()
        
        # Get all stock (cached in production, fast from Supabase)
        all_stock = db.get_all_stock(biz_id)
        
        # Filter by search query
        if query:
            filtered = []
            for s in all_stock:
                code = str(s.get("code", "")).lower()
                desc = str(s.get("description", "")).lower()
                cat = str(s.get("category", "")).lower()
                if query in code or query in desc or query in cat:
                    filtered.append(s)
            all_stock = filtered
        
        # Filter by category
        if category:
            all_stock = [s for s in all_stock if str(s.get("category", "")).lower() == category.lower()]
        
        # Sort by category then description
        all_stock = sorted(all_stock, key=lambda x: (x.get("category") or "ZZZ", x.get("description") or ""))
        
        total = len(all_stock)
        items = all_stock[offset:offset + limit]
        
        # Build HTML rows
        rows_html = ""
        for s in items:
            qty = float(s.get("qty") or s.get("quantity") or 0)
            cost = float(s.get("cost") or s.get("cost_price") or 0)
            price = float(s.get("price") or s.get("selling_price") or 0)
            unit = safe_string(s.get("unit", ""))
            total_value = qty * cost
            qty_class = "color: var(--red);" if qty < 5 else ""
            code = safe_string(s.get("code", "-"))
            desc = safe_string(s.get("description", "-"))
            desc_escaped = desc.replace("'", "&#39;")
            stock_id = s.get("id", "")
            cat = safe_string(s.get("category", ""))
            
            rows_html += f'''
            <tr class="stock-data-row" data-search="{code.lower()} {desc.lower()}" data-category="{cat}">
                <td><strong>{code}</strong></td>
                <td>{desc}</td>
                <td style="color:var(--text-muted);font-size:11px;">{cat}</td>
                <td style="{qty_class} text-align:right;">{qty:.0f}</td>
                <td style="text-align:center;color:var(--text-muted);">{unit}</td>
                <td style="text-align:right;">R{cost:,.2f}</td>
                <td style="text-align:right;color:var(--text-muted);">R{total_value:,.2f}</td>
                <td style="text-align:right;">R{price:,.2f}</td>
                <td><button class="btn btn-sm" style="background:#8b5cf6;color:white;padding:4px 8px;font-size:11px;" 
                    onclick="showIssueToJob('{stock_id}', '{code}', '{desc_escaped}', {qty}, {cost})">Issue</button></td>
            </tr>
            '''
        
        return jsonify({
            "success": True,
            "html": rows_html,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": (offset + limit) < total
        })
    
    
    @app.route("/api/stock/lookup")
    @login_required
    def api_stock_lookup():
        """Lightweight JSON stock search for invoice/quote typeahead."""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify([])
        query = request.args.get("q", "").strip().lower()
        if len(query) < 2:
            return jsonify([])
        all_stock = db.get_all_stock(biz_id)
        results = []
        for s in all_stock:
            c = str(s.get("code", "")).lower()
            d = str(s.get("description", "")).lower()
            if query in c or query in d:
                price = float(s.get("price") or s.get("selling_price") or 0)
                cs = s.get("code", "")
                ds = s.get("description", "")
                results.append({"id": s.get("id", ""), "label": (f"{cs} - {ds}" if cs else ds), "desc": ds, "code": cs, "price": price, "unit": s.get("unit", ""), "qty": float(s.get("qty") or s.get("quantity") or 0)})
                if len(results) >= 25:
                    break
        return jsonify(results)
    
    
    # Store pending edits temporarily
    _zane_pending_edits = {}
    
    
    @app.route("/api/stock/issue-to-job", methods=["POST"])
    @login_required
    def api_stock_issue_to_job():
        """Issue stock to a job card - updates stock qty and job card materials"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            data = request.get_json()
            stock_id = data.get("stock_id")
            job_id = data.get("job_id")
            qty = int(data.get("qty", 0))
            code = data.get("code", "")
            description = data.get("description", "")
            cost = float(data.get("cost", 0))
            
            if not stock_id or not job_id or qty <= 0:
                return jsonify({"success": False, "error": "Invalid data"})
            
            # Get stock item
            stock_item = db.get_one_stock(stock_id)
            if not stock_item:
                return jsonify({"success": False, "error": "Stock item not found"})
            
            # Get job card
            job = db.get_one("jobs", job_id)
            if not job:
                return jsonify({"success": False, "error": "Job card not found"})
            
            # Check available qty
            current_qty = float(stock_item.get("qty") or stock_item.get("quantity") or 0)
            if qty > current_qty:
                return jsonify({"success": False, "error": f"Not enough stock. Only {current_qty} available."})
            
            # Update stock quantity
            new_qty = current_qty - qty
            db.update_stock(stock_id, {"qty": new_qty, "quantity": new_qty}, biz_id)
            logger.info(f"[ISSUE TO JOB] Stock {code}: {current_qty} - {qty} = {new_qty}")
            
            # Update job card materials_issued
            try:
                materials_issued = json.loads(job.get("materials_issued", "[]"))
            except:
                materials_issued = []
            
            material_cost = qty * cost
            issue_entry = {
                "date": today(),
                "stock_id": stock_id,
                "code": code,
                "description": description,
                "qty": qty,
                "cost_each": cost,
                "total_cost": material_cost,
                "issued_by": user.get("name", user.get("email", "Unknown")),
                "timestamp": now()
            }
            materials_issued.append(issue_entry)
            
            # Update job totals
            current_material_cost = float(job.get("total_material_cost", 0))
            new_material_cost = current_material_cost + material_cost
            
            total_actual_cost = new_material_cost + float(job.get("total_labour_cost", 0)) + float(job.get("total_additional_cost", 0))
            quote_value = float(job.get("quote_value", 0))
            profit_loss = quote_value - total_actual_cost
            
            job_update = {
                "materials_issued": json.dumps(materials_issued),
                "total_material_cost": new_material_cost,
                "total_actual_cost": total_actual_cost,
                "profit_loss": profit_loss
            }
            
            # Auto-start job if not started
            if job.get("status") == "not_started":
                job_update["status"] = "in_progress"
                job_update["started_at"] = now()
            
            db.update("jobs", job_id, job_update, biz_id)
            
            AuditLog.log("UPDATE", "jobs", job_id, details=f"Stock issued: {qty}x {code} (R{material_cost:.2f})")
            logger.info(f"[ISSUE TO JOB] Issued {qty}x {code} to job {job.get('job_number')} - material cost R{material_cost:.2f}")
            
            return jsonify({
                "success": True,
                "job_number": job.get("job_number"),
                "new_stock_qty": new_qty,
                "material_cost": material_cost
            })
            
        except Exception as e:
            logger.error(f"[ISSUE TO JOB] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/stock/zane-edit", methods=["POST"])
    @login_required
    def api_stock_zane_edit():
        """Zane AI editing for stock - smart codes, pricing, categories - BATCH PROCESSING"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business selected"})
        
        try:
            data = request.get_json() or {}
        except:
            data = {}
        command = data.get("command", "").lower().strip()
        offset = data.get("offset", 0)
        limit = data.get("limit", 100)
        
        if not command:
            return jsonify({"success": False, "error": "No command provided"})
        
        # Get all stock (we need total count)
        all_stock = db.get_all_stock(biz_id)
        if not all_stock:
            return jsonify({"success": False, "error": "No stock items found"})
        
        total_count = len(all_stock)
        
        # Get batch to process
        stock_batch = all_stock[offset:offset + limit]
        has_more = (offset + limit) < total_count
        
        logger.info(f"[ZANE EDIT] Command: {command}, Batch: {offset}-{offset+len(stock_batch)} of {total_count}")
        
        updated = 0
        
        # 
        # SMART CODES - Generate codes like BLT-10X110-HT from "BOLT M10X110 HT"
        # 
        if "code" in command and ("smart" in command or "generate" in command or "create" in command or "make" in command):
            
            # Collect all existing codes for uniqueness
            existing_codes = set()
            for item in all_stock:
                c = str(item.get("code", "")).upper().strip()
                if c:
                    existing_codes.add(c)
            
            updates = []
            for item in stock_batch:
                desc = item.get("description", "").strip()
                if not desc:
                    continue
                
                new_code = smart_stock_code(desc, existing_codes)
                old_code = item.get("code", "")
                
                if new_code and new_code != old_code:
                    updates.append({"id": item["id"], "data": {"code": new_code}})
                    existing_codes.add(new_code.upper())
            
            # Batch update
            if updates:
                # Try both tables
                s1, f1 = db.update_many("stock_items", updates, biz_id)
                s2, f2 = db.update_many("stock", updates, biz_id)
                s, f = s1 + s2, f1 + f2
                updated = s
            
            return jsonify({
                "success": True,
                "total": total_count,
                "processed": len(stock_batch),
                "updated": updated,
                "hasMore": has_more
            })
        
        # 
        # SMART PRICING - Tiered markup based on cost and category
        # 
        elif "markup" in command or "price" in command or "pricing" in command:
            
            import re
            
            # Parse rules from command
            rules = []
            under_pattern = r'under\s*r?(\d+(?:\.\d+)?)\s*[=:]?\s*(\d+)%'
            for match in re.finditer(under_pattern, command):
                threshold = float(match.group(1))
                markup = float(match.group(2)) / 100
                rules.append({"type": "under", "threshold": threshold, "markup": markup})
            
            max_pattern = r'max\s*(\d+)%'
            max_match = re.search(max_pattern, command)
            max_markup = float(max_match.group(1)) / 100 if max_match else None
            
            generic_pattern = r'(\d+)%\s*markup|(\d+)%'
            generic_matches = re.findall(generic_pattern, command)
            default_markup = None
            for m in generic_matches:
                val = m[0] or m[1]
                if val:
                    default_markup = float(val) / 100
            
            rules.sort(key=lambda x: x.get("threshold", 999))
            
            updates = []
            for item in stock_batch:
                cost = float(item.get("cost") or item.get("cost_price") or 0)
                old_price = float(item.get("price") or item.get("selling_price") or 0)
                
                if cost <= 0:
                    continue
                
                markup = default_markup or 0.5
                for rule in rules:
                    if rule["type"] == "under" and cost < rule["threshold"]:
                        markup = rule["markup"]
                        break
                
                new_price = round(cost * (1 + markup), 2)
                
                if max_markup:
                    max_price = round(cost * (1 + max_markup), 2)
                    if old_price > max_price:
                        new_price = max_price
                    else:
                        continue
                
                if abs(new_price - old_price) > 0.01:
                    updates.append({"id": item["id"], "data": {"price": new_price}})
            
            if updates:
                # Try both tables
                s1, f1 = db.update_many("stock_items", updates, biz_id)
                s2, f2 = db.update_many("stock", updates, biz_id)
                s, f = s1 + s2, f1 + f2
                updated = s
            
            return jsonify({
                "success": True,
                "total": total_count,
                "processed": len(stock_batch),
                "updated": updated,
                "hasMore": has_more
            })
        
        # 
        # CATEGORIZE - Auto-assign categories based on description
        # 
        elif "categor" in command:
            
            category_rules = {
                "Fasteners": ["bolt", "nut", "washer", "screw", "set ", "cap screw", "stud", "rivet"],
                "Bearings & Seals": ["bearing", "seal", "circlip", "o-ring", "oring"],
                "Fittings": ["elbow", "tee", "reducer", "flange", "valve", "coupling", "nipple", "fitting"],
                "Pipe & Tube": ["pipe", "tube", "hose"],
                "Workwear": ["boot", "jacket", "overall", "conti", "glove", "shirt", "trouser", "jean", "goggle", "safety", "hard hat", "helmet"],
                "Tools": ["spanner", "wrench", "drill", "blade", "hammer", "plier", "screwdriver"],
                "Steel": ["flat bar", "round bar", "square", "angle", "channel", "sheet", "plate"],
                "Hardware": ["clamp", "bracket", "hinge", "handle", "lock", "chain"],
                "Abrasives": ["sandpaper", "grinding", "cutting disc", "flap disc"],
                "Electrical": ["cable", "wire", "switch", "plug", "socket"],
            }
            
            updates = []
            for item in stock_batch:
                desc = item.get("description", "").lower()
                old_cat = item.get("category") or ""
                new_cat = None
                
                for category, keywords in category_rules.items():
                    if any(kw in desc for kw in keywords):
                        new_cat = category
                        break
                
                if new_cat and new_cat != old_cat:
                    updates.append({"id": item["id"], "data": {"category": new_cat}})
            
            if updates:
                # Try both tables
                s1, f1 = db.update_many("stock_items", updates, biz_id)
                s2, f2 = db.update_many("stock", updates, biz_id)
                s, f = s1 + s2, f1 + f2
                updated = s
            
            return jsonify({
                "success": True,
                "total": total_count,
                "processed": len(stock_batch),
                "updated": updated,
                "hasMore": has_more
            })
        
        else:
            if "delete" in command:
                return jsonify({"success": False, "error": "Delete commands go in the main chat bar, not here."})
            
            return jsonify({"success": False, "error": "Try: 'generate smart codes', 'markup 50%', or 'categorize'."})
    
    
    @app.route("/api/stock/zane-edit/apply", methods=["POST"])
    @login_required
    def api_stock_zane_edit_apply():
        """Apply pending Zane edits"""
        
        data = request.get_json() or {}
        edit_id = data.get("edit_id")
        
        if not edit_id or edit_id not in _zane_pending_edits:
            return jsonify({"success": False, "error": "Edit session expired - please try again"})
        
        pending = _zane_pending_edits.pop(edit_id)
        changes = pending["changes"]
        biz_id = pending["biz_id"]
        
        # Apply changes
        updated = 0
        failed = 0
        for change in changes:
            try:
                item_id = change["id"]
                field = change["field"]
                new_value = change["new"]
                
                # Map field names to database columns
                db_field = field
                if field == "price":
                    db_field = "price"  # or "selling_price" depending on your schema
                
                if db.update_stock(item_id, {db_field: new_value}, biz_id):
                    updated += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"[ZANE EDIT] Failed to update {change.get('id')}: {e}")
                failed += 1
        
        logger.info(f"[ZANE EDIT] Applied {updated} changes, failed {failed}")
        
        return jsonify({"success": True, "count": updated})

    logger.info("[STOCK] All stock routes registered ✓")
