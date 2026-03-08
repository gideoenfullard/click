"""
ClickAI Bolt Bulk Repricing Module
═══════════════════════════════════
Admin page + API to bulk recalculate ALL fastener cost prices.
Uses BoltPricer to identify items by description and set correct
weight-based cost prices.

Routes:
  GET  /admin/bolt-reprice          → Admin page with preview + apply
  GET  /api/bolt-reprice/preview    → JSON preview of all changes
  POST /api/bolt-reprice/apply      → Write changes to DB
  POST /api/bolt-reprice/apply-one  → Write single item to DB

Place in same directory as clickai.py. Import with try/except.
"""

import logging
import time
import json

logger = logging.getLogger(__name__)


def register_bolt_reprice_routes(app, db, Auth, get_user_role, login_required):
    """Register bolt repricing admin routes."""
    from flask import request, jsonify, render_template_string

    # Import BoltPricer — should already be loaded
    try:
        from clickai_bolt_pricer import BoltPricer
    except ImportError:
        logger.error("[BOLT REPRICE] clickai_bolt_pricer.py not found!")
        return

    @app.route("/admin/bolt-reprice")
    @login_required
    def admin_bolt_reprice():
        """Admin page for bulk bolt repricing."""
        role = get_user_role()
        if role not in ("owner", "admin"):
            return "Access denied", 403
        return render_template_string(REPRICE_HTML)

    @app.route("/api/bolt-reprice/preview")
    @login_required
    def api_bolt_reprice_preview():
        """Pull all stock, run pricer, return preview JSON."""
        role = get_user_role()
        if role not in ("owner", "admin"):
            return jsonify({"success": False, "error": "Owner/Admin only"})

        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False, "error": "No business selected"})

        t0 = time.time()

        # Pull ALL stock
        all_stock = db.get_all_stock(biz_id)
        total_items = len(all_stock)

        matched = []
        skipped = []
        no_change = []

        for item in all_stock:
            desc = item.get("description") or item.get("code") or ""
            item_id = item.get("id", "")
            code = item.get("code", "")
            old_cost = float(item.get("cost_price") or item.get("cost") or 0)
            old_sell = float(item.get("selling_price") or item.get("price") or 0)

            result = BoltPricer.price(desc)

            if not result.get("success"):
                skipped.append({
                    "id": item_id,
                    "code": code,
                    "description": desc,
                    "old_cost": old_cost,
                    "old_sell": old_sell,
                    "reason": result.get("error", "Not a fastener"),
                })
                continue

            new_cost = result["cost"]
            diff = round(new_cost - old_cost, 2)
            pct = round((diff / old_cost * 100), 1) if old_cost > 0 else (999 if new_cost > 0 else 0)

            entry = {
                "id": item_id,
                "code": code,
                "description": desc,
                "item_type": result["item_type"],
                "type_label": result["type_label"],
                "material": result["material"],
                "mat_label": result["mat_label"],
                "m_size": result["m_size"],
                "length": result.get("length"),
                "weight_g": result["weight_g"],
                "rkg": result["rkg"],
                "old_cost": old_cost,
                "new_cost": new_cost,
                "old_sell": old_sell,
                "difference": diff,
                "pct_change": pct,
                "has_cost": old_cost > 0,
            }

            if abs(pct) < 1 and old_cost > 0:
                no_change.append(entry)
            else:
                matched.append(entry)

        # Sort: biggest changes first
        matched.sort(key=lambda x: abs(x["pct_change"]), reverse=True)

        elapsed = round(time.time() - t0, 2)

        # Stats
        needs_cost = [m for m in matched if not m["has_cost"]]
        price_up = [m for m in matched if m["difference"] > 0.01 and m["has_cost"]]
        price_down = [m for m in matched if m["difference"] < -0.01 and m["has_cost"]]

        total_old = sum(m["old_cost"] for m in matched)
        total_new = sum(m["new_cost"] for m in matched)

        return jsonify({
            "success": True,
            "stats": {
                "total_stock": total_items,
                "fasteners_matched": len(matched) + len(no_change),
                "changes_needed": len(matched),
                "no_change": len(no_change),
                "not_fasteners": len(skipped),
                "needs_cost_price": len(needs_cost),
                "price_going_up": len(price_up),
                "price_going_down": len(price_down),
                "total_old_cost": round(total_old, 2),
                "total_new_cost": round(total_new, 2),
                "net_difference": round(total_new - total_old, 2),
                "elapsed_seconds": elapsed,
            },
            "matched": matched,
            "no_change": no_change,
            "skipped": skipped[:100],  # Limit skipped to first 100
            "tiers": BoltPricer.get_all_tiers(),
        })

    @app.route("/api/bolt-reprice/apply", methods=["POST"])
    @login_required
    def api_bolt_reprice_apply():
        """Apply cost price changes to DB. Expects JSON with item list."""
        role = get_user_role()
        if role not in ("owner", "admin"):
            return jsonify({"success": False, "error": "Owner/Admin only"})

        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})

        data = request.get_json() or {}
        items = data.get("items", [])

        if not items:
            return jsonify({"success": False, "error": "No items to update"})

        success_count = 0
        fail_count = 0
        errors = []

        for item in items:
            item_id = item.get("id")
            new_cost = item.get("new_cost")

            if not item_id or new_cost is None:
                fail_count += 1
                continue

            try:
                # Update cost_price in stock_items
                ok = db.update("stock_items", item_id,
                               {"cost_price": round(float(new_cost), 2)},
                               business_id=biz_id)
                if ok:
                    success_count += 1
                else:
                    # Try legacy table
                    ok2 = db.update("stock", item_id,
                                    {"cost": round(float(new_cost), 2)},
                                    business_id=biz_id)
                    if ok2:
                        success_count += 1
                    else:
                        fail_count += 1
                        errors.append(f"{item_id}: update returned false")
            except Exception as e:
                fail_count += 1
                errors.append(f"{item_id}: {str(e)[:80]}")

        return jsonify({
            "success": True,
            "updated": success_count,
            "failed": fail_count,
            "errors": errors[:20],  # First 20 errors
        })

    @app.route("/api/bolt-reprice/apply-one", methods=["POST"])
    @login_required
    def api_bolt_reprice_apply_one():
        """Update a single item's cost price."""
        role = get_user_role()
        if role not in ("owner", "admin"):
            return jsonify({"success": False, "error": "Owner/Admin only"})

        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        data = request.get_json() or {}
        item_id = data.get("id")
        new_cost = data.get("new_cost")

        if not item_id or new_cost is None:
            return jsonify({"success": False, "error": "Need id and new_cost"})

        try:
            ok = db.update("stock_items", item_id,
                           {"cost_price": round(float(new_cost), 2)},
                           business_id=biz_id)
            if not ok:
                ok = db.update("stock", item_id,
                               {"cost": round(float(new_cost), 2)},
                               business_id=biz_id)
            return jsonify({"success": ok})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)[:100]})

    logger.info("[BOLT REPRICE] Routes registered ✓")


# ═══════════════════════════════════════════════════════════════
# ADMIN HTML PAGE
# ═══════════════════════════════════════════════════════════════

REPRICE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bolt Repricing — ClickAI</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#0f172a; color:#e2e8f0; }

.header { background:linear-gradient(135deg,#1e293b,#334155); padding:20px 30px; border-bottom:1px solid #475569; }
.header h1 { font-size:24px; color:#f8fafc; }
.header p { color:#94a3b8; margin-top:4px; font-size:14px; }

.container { max-width:1400px; margin:0 auto; padding:20px; }

.stats-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr)); gap:12px; margin:20px 0; }
.stat-card { background:#1e293b; border-radius:10px; padding:16px; border:1px solid #334155; }
.stat-card .num { font-size:28px; font-weight:700; color:#38bdf8; }
.stat-card .label { font-size:12px; color:#94a3b8; margin-top:2px; text-transform:uppercase; }
.stat-card.green .num { color:#4ade80; }
.stat-card.red .num { color:#f87171; }
.stat-card.yellow .num { color:#fbbf24; }
.stat-card.purple .num { color:#a78bfa; }

.controls { display:flex; gap:12px; margin:20px 0; flex-wrap:wrap; align-items:center; }
.btn { padding:10px 24px; border-radius:8px; border:none; font-size:14px; font-weight:600; cursor:pointer; transition:all .2s; }
.btn-primary { background:#3b82f6; color:white; }
.btn-primary:hover { background:#2563eb; }
.btn-success { background:#22c55e; color:white; }
.btn-success:hover { background:#16a34a; }
.btn-danger { background:#ef4444; color:white; }
.btn-danger:hover { background:#dc2626; }
.btn:disabled { opacity:.5; cursor:not-allowed; }

.filter-bar { display:flex; gap:8px; margin:10px 0; flex-wrap:wrap; }
.filter-btn { padding:6px 14px; border-radius:6px; border:1px solid #475569; background:transparent; color:#94a3b8; font-size:12px; cursor:pointer; }
.filter-btn.active { background:#3b82f6; color:white; border-color:#3b82f6; }

.search-box { padding:8px 14px; border-radius:8px; border:1px solid #475569; background:#1e293b; color:#e2e8f0; font-size:14px; width:300px; }

table { width:100%; border-collapse:collapse; margin:10px 0; font-size:13px; }
thead th { background:#1e293b; color:#94a3b8; padding:10px 8px; text-align:left; position:sticky; top:0; border-bottom:2px solid #475569; font-size:11px; text-transform:uppercase; cursor:pointer; }
thead th:hover { color:#e2e8f0; }
tbody td { padding:8px; border-bottom:1px solid #1e293b; }
tbody tr { transition: background .15s; }
tbody tr:hover { background:#1e293b; }
tbody tr.new-cost { background:rgba(34,197,94,.08); }
tbody tr.big-up { background:rgba(251,191,36,.08); }
tbody tr.big-down { background:rgba(248,113,113,.08); }

.tag { padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; display:inline-block; }
.tag-ht { background:#334155; color:#94a3b8; }
.tag-ss { background:#1e3a5f; color:#38bdf8; }
.tag-zp { background:#3f3f1e; color:#fbbf24; }
.tag-blk { background:#292524; color:#a8a29e; }
.tag-hdg { background:#1a2e1a; color:#4ade80; }
.tag-109 { background:#3b1e1e; color:#f87171; }

.diff-pos { color:#4ade80; }
.diff-neg { color:#f87171; }
.diff-new { color:#38bdf8; font-weight:700; }

.progress-bar { height:4px; background:#334155; border-radius:2px; margin:10px 0; overflow:hidden; }
.progress-fill { height:100%; background:#3b82f6; border-radius:2px; transition:width .3s; }

#status { padding:12px; border-radius:8px; margin:10px 0; display:none; }
#status.info { display:block; background:#1e3a5f; border:1px solid #2563eb; color:#93c5fd; }
#status.success { display:block; background:#14532d; border:1px solid #22c55e; color:#86efac; }
#status.error { display:block; background:#450a0a; border:1px solid #ef4444; color:#fca5a5; }

.table-wrap { max-height:70vh; overflow-y:auto; border-radius:8px; border:1px solid #334155; }

.checkbox-all { margin-right:6px; }

@media (max-width:768px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .search-box { width:100%; }
}
</style>
</head>
<body>

<div class="header">
    <h1>🔩 Bolt Repricing</h1>
    <p>Weight-based cost price recalculation — Preview changes, then apply</p>
</div>

<div class="container">
    <div class="controls">
        <button class="btn btn-primary" id="btnPreview" onclick="loadPreview()">
            📊 Load & Preview All Stock
        </button>
        <button class="btn btn-success" id="btnApply" onclick="applySelected()" disabled>
            ✅ Apply Selected Changes
        </button>
        <button class="btn btn-danger" id="btnApplyAll" onclick="applyAll()" disabled>
            ⚡ Apply ALL Changes
        </button>
        <span id="itemCount" style="color:#94a3b8; font-size:13px;"></span>
    </div>

    <div id="status"></div>
    <div class="progress-bar"><div class="progress-fill" id="progress" style="width:0%"></div></div>

    <div class="stats-grid" id="statsGrid" style="display:none;"></div>

    <div class="filter-bar" id="filterBar" style="display:none;">
        <input type="text" class="search-box" id="searchBox" placeholder="Soek... (description, code, M-size)" oninput="filterTable()">
        <button class="filter-btn active" data-filter="all" onclick="setFilter(this)">All</button>
        <button class="filter-btn" data-filter="needs-cost" onclick="setFilter(this)">⭐ Needs Cost</button>
        <button class="filter-btn" data-filter="big-change" onclick="setFilter(this)">⚠️ Big Change (>25%)</button>
        <button class="filter-btn" data-filter="up" onclick="setFilter(this)">📈 Going Up</button>
        <button class="filter-btn" data-filter="down" onclick="setFilter(this)">📉 Going Down</button>
    </div>

    <div class="table-wrap" id="tableWrap" style="display:none;">
        <table>
            <thead>
                <tr>
                    <th><input type="checkbox" class="checkbox-all" onchange="toggleAll(this)" checked></th>
                    <th onclick="sortTable('code')">Code</th>
                    <th onclick="sortTable('description')">Description</th>
                    <th onclick="sortTable('type_label')">Type</th>
                    <th onclick="sortTable('material')">Mat</th>
                    <th onclick="sortTable('m_size')">Size</th>
                    <th onclick="sortTable('weight_g')" style="text-align:right">Weight</th>
                    <th onclick="sortTable('rkg')" style="text-align:right">R/kg</th>
                    <th onclick="sortTable('old_cost')" style="text-align:right">Old Cost</th>
                    <th onclick="sortTable('new_cost')" style="text-align:right">New Cost</th>
                    <th onclick="sortTable('difference')" style="text-align:right">Diff</th>
                    <th onclick="sortTable('pct_change')" style="text-align:right">%</th>
                </tr>
            </thead>
            <tbody id="tableBody"></tbody>
        </table>
    </div>
</div>

<script>
let allData = [];
let currentFilter = 'all';
let sortCol = 'pct_change';
let sortDir = -1;

function setStatus(msg, type='info') {
    const el = document.getElementById('status');
    el.textContent = msg;
    el.className = type;
}

function setProgress(pct) {
    document.getElementById('progress').style.width = pct + '%';
}

async function loadPreview() {
    const btn = document.getElementById('btnPreview');
    btn.disabled = true;
    btn.textContent = '⏳ Loading...';
    setStatus('Pulling all stock from database and calculating prices...', 'info');
    setProgress(30);

    try {
        const resp = await fetch('/api/bolt-reprice/preview');
        const data = await resp.json();
        setProgress(100);

        if (!data.success) {
            setStatus('Error: ' + (data.error || 'Unknown'), 'error');
            btn.disabled = false;
            btn.textContent = '📊 Load & Preview All Stock';
            return;
        }

        allData = data.matched || [];
        const s = data.stats;

        // Stats
        document.getElementById('statsGrid').style.display = 'grid';
        document.getElementById('statsGrid').innerHTML = `
            <div class="stat-card"><div class="num">${s.total_stock}</div><div class="label">Total Stock Items</div></div>
            <div class="stat-card purple"><div class="num">${s.fasteners_matched}</div><div class="label">Fasteners Found</div></div>
            <div class="stat-card yellow"><div class="num">${s.changes_needed}</div><div class="label">Changes Needed</div></div>
            <div class="stat-card"><div class="num">${s.needs_cost_price}</div><div class="label">⭐ Needs Cost Price</div></div>
            <div class="stat-card green"><div class="num">${s.price_going_up}</div><div class="label">📈 Price Going Up</div></div>
            <div class="stat-card red"><div class="num">${s.price_going_down}</div><div class="label">📉 Price Going Down</div></div>
            <div class="stat-card"><div class="num">R${s.total_old_cost.toLocaleString()}</div><div class="label">Total Old Cost</div></div>
            <div class="stat-card green"><div class="num">R${s.total_new_cost.toLocaleString()}</div><div class="label">Total New Cost</div></div>
            <div class="stat-card ${s.net_difference >= 0 ? 'green' : 'red'}"><div class="num">R${s.net_difference >= 0 ? '+' : ''}${s.net_difference.toLocaleString()}</div><div class="label">Net Difference</div></div>
            <div class="stat-card"><div class="num">${s.not_fasteners}</div><div class="label">Not Fasteners (skipped)</div></div>
            <div class="stat-card"><div class="num">${s.no_change}</div><div class="label">No Change Needed</div></div>
            <div class="stat-card"><div class="num">${s.elapsed_seconds}s</div><div class="label">Processing Time</div></div>
        `;

        // Enable buttons
        document.getElementById('btnApply').disabled = false;
        document.getElementById('btnApplyAll').disabled = false;
        document.getElementById('filterBar').style.display = 'flex';
        document.getElementById('tableWrap').style.display = 'block';

        renderTable();
        setStatus(`✅ Preview ready — ${allData.length} items need changes. Review and click Apply.`, 'success');

    } catch(e) {
        setStatus('Network error: ' + e.message, 'error');
    }

    btn.disabled = false;
    btn.textContent = '📊 Refresh Preview';
}

function matTag(mat) {
    const cls = {'HT':'ht','SS':'ss','ZP':'zp','BLK':'blk','HDG':'hdg','10.9':'109','8.8':'109','12.9':'109'}[mat] || 'ht';
    return `<span class="tag tag-${cls}">${mat}</span>`;
}

function renderTable() {
    let items = [...allData];

    // Filter
    const search = document.getElementById('searchBox').value.toLowerCase();
    if (search) {
        items = items.filter(i =>
            (i.description||'').toLowerCase().includes(search) ||
            (i.code||'').toLowerCase().includes(search) ||
            ('m'+i.m_size).includes(search)
        );
    }

    if (currentFilter === 'needs-cost') items = items.filter(i => !i.has_cost);
    else if (currentFilter === 'big-change') items = items.filter(i => Math.abs(i.pct_change) > 25);
    else if (currentFilter === 'up') items = items.filter(i => i.difference > 0.01);
    else if (currentFilter === 'down') items = items.filter(i => i.difference < -0.01);

    // Sort
    items.sort((a, b) => {
        let va = a[sortCol], vb = b[sortCol];
        if (typeof va === 'string') return va.localeCompare(vb) * sortDir;
        return ((va||0) - (vb||0)) * sortDir;
    });

    document.getElementById('itemCount').textContent = `${items.length} items shown`;

    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = items.map(i => {
        let cls = '';
        if (!i.has_cost) cls = 'new-cost';
        else if (i.pct_change > 25) cls = 'big-up';
        else if (i.pct_change < -25) cls = 'big-down';

        const diffCls = !i.has_cost ? 'diff-new' : (i.difference >= 0 ? 'diff-pos' : 'diff-neg');
        const sz = i.length ? `M${i.m_size}×${i.length}` : `M${i.m_size}`;

        return `<tr class="${cls}" data-id="${i.id}">
            <td><input type="checkbox" class="row-check" checked data-id="${i.id}"></td>
            <td style="font-size:11px;color:#64748b">${i.code||''}</td>
            <td><strong>${i.description}</strong></td>
            <td style="font-size:11px">${i.type_label}</td>
            <td>${matTag(i.material)}</td>
            <td>${sz}</td>
            <td style="text-align:right">${i.weight_g}g</td>
            <td style="text-align:right">R${i.rkg}</td>
            <td style="text-align:right">${i.old_cost > 0 ? 'R'+i.old_cost.toFixed(2) : '<span class="diff-new">—</span>'}</td>
            <td style="text-align:right;font-weight:700">R${i.new_cost.toFixed(2)}</td>
            <td style="text-align:right" class="${diffCls}">${i.has_cost ? 'R'+(i.difference>=0?'+':'')+i.difference.toFixed(2) : 'NEW'}</td>
            <td style="text-align:right" class="${diffCls}">${i.has_cost ? (i.pct_change>=0?'+':'')+i.pct_change.toFixed(0)+'%' : '⭐'}</td>
        </tr>`;
    }).join('');
}

function filterTable() { renderTable(); }

function setFilter(btn) {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    renderTable();
}

function sortTable(col) {
    if (sortCol === col) sortDir *= -1;
    else { sortCol = col; sortDir = 1; }
    renderTable();
}

function toggleAll(cb) {
    document.querySelectorAll('.row-check').forEach(c => c.checked = cb.checked);
}

function getSelected() {
    const checked = document.querySelectorAll('.row-check:checked');
    const ids = new Set([...checked].map(c => c.dataset.id));
    return allData.filter(i => ids.has(i.id));
}

async function applyBatch(items, label) {
    setStatus(`⏳ Applying ${items.length} ${label}...`, 'info');
    setProgress(10);

    // Send in batches of 50
    const batchSize = 50;
    let totalOk = 0, totalFail = 0;

    for (let i = 0; i < items.length; i += batchSize) {
        const batch = items.slice(i, i + batchSize).map(it => ({
            id: it.id,
            new_cost: it.new_cost
        }));

        try {
            const resp = await fetch('/api/bolt-reprice/apply', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({items: batch})
            });
            const data = await resp.json();
            totalOk += (data.updated || 0);
            totalFail += (data.failed || 0);
        } catch(e) {
            totalFail += batch.length;
        }

        setProgress(Math.round(((i + batchSize) / items.length) * 100));
    }

    setProgress(100);

    if (totalFail === 0) {
        setStatus(`✅ Done! ${totalOk} cost prices updated successfully.`, 'success');
    } else {
        setStatus(`⚠️ ${totalOk} updated, ${totalFail} failed. Check logs.`, 'error');
    }
}

async function applySelected() {
    const items = getSelected();
    if (!items.length) { setStatus('No items selected', 'error'); return; }
    if (!confirm(`Apply cost price changes to ${items.length} items?`)) return;
    await applyBatch(items, 'selected items');
}

async function applyAll() {
    if (!confirm(`Apply ALL ${allData.length} cost price changes?\\n\\nThis will update every matched fastener in your database.`)) return;
    await applyBatch(allData, 'items');
}
</script>
</body>
</html>
"""
