"""
Click AI v2 - Clean Build | Phone=Camera, Desktop=Full System | By Deon & Claude
"""
from flask import Flask, jsonify, request
import json, os, re, uuid
from datetime import datetime

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════════════════════
DATA = {"businesses": {}}

def save():
    try:
        with open("data.json", "w") as f: json.dump(DATA, f)
    except: pass

def load():
    global DATA
    try:
        with open("data.json", "r") as f: DATA = json.load(f)
    except: DATA = {"businesses": {}}

load()

def biz(bid):
    if bid not in DATA["businesses"]:
        DATA["businesses"][bid] = {"name": bid, "stock": [], "customers": [], "suppliers": [], "ledger": [], "documents": {"quotes": [], "invoices": []}}
    return DATA["businesses"][bid]

ACCOUNTS = {"1000": "Bank", "1200": "Debtors", "2000": "Creditors", "2100": "VAT Input", "2200": "VAT Output", "4000": "Sales", "5000": "Cost of Sales", "6100": "Rent", "6200": "Utilities", "6300": "Phone", "6910": "Fuel", "6999": "Other Expense"}

CATEGORIES = ["All", "Bearings", "Bolts", "Nuts", "Washers", "Screws", "Workwear", "Oil Seals", "V-Belts", "Freestyle", "Circlips", "Hardware", "Other"]

# ═══════════════════════════════════════════════════════════════════════════════
# STYLES
# ═══════════════════════════════════════════════════════════════════════════════
CSS = """<style>
:root{--bg:#050508;--card:linear-gradient(145deg,#0d0d14,#12121f);--card-solid:#0d0d14;--border:#1a1a2f;--text:#fff;--muted:#6b7280;--blue:#3b82f6;--purple:#8b5cf6;--green:#10b981;--red:#ef4444;--orange:#f59e0b;--glow-purple:0 0 30px rgba(139,92,246,.3);--glow-blue:0 0 30px rgba(59,130,246,.3);--glow-green:0 0 30px rgba(16,185,129,.3)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--bg);background-image:radial-gradient(ellipse at top,#0f0f1a 0%,#050508 50%),radial-gradient(circle at bottom right,rgba(139,92,246,.05),transparent 40%);color:var(--text);min-height:100vh}
.container{max-width:1100px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:16px;backdrop-filter:blur(10px);transition:all .3s ease}
.card:hover{border-color:#2a2a4a;transform:translateY(-2px);box-shadow:0 10px 40px rgba(0,0,0,.4)}
.title{font-size:28px;font-weight:800;background:linear-gradient(135deg,#fff 0%,#a5b4fc 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:8px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:14px 24px;border-radius:12px;font-weight:700;cursor:pointer;transition:all .25s ease;text-decoration:none;border:none;font-size:14px;letter-spacing:.3px}
.btn:hover{transform:translateY(-3px)}
.btn-blue{background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;box-shadow:0 4px 15px rgba(59,130,246,.3)}.btn-blue:hover{box-shadow:var(--glow-blue)}
.btn-purple{background:linear-gradient(135deg,#8b5cf6,#7c3aed);color:#fff;box-shadow:0 4px 15px rgba(139,92,246,.3)}.btn-purple:hover{box-shadow:var(--glow-purple)}
.btn-green{background:linear-gradient(135deg,#10b981,#059669);color:#fff;box-shadow:0 4px 15px rgba(16,185,129,.3)}.btn-green:hover{box-shadow:var(--glow-green)}
.btn-red{background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;box-shadow:0 4px 15px rgba(239,68,68,.3)}.btn-red:hover{box-shadow:0 0 30px rgba(239,68,68,.3)}
.btn-dark{background:linear-gradient(145deg,#1a1a2a,#12121f);color:var(--text);border:1px solid var(--border);box-shadow:0 4px 12px rgba(0,0,0,.2)}.btn-dark:hover{border-color:var(--purple);box-shadow:var(--glow-purple)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.input{width:100%;padding:14px 16px;background:rgba(15,15,25,.8);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;transition:all .2s}
.input:focus{outline:none;border-color:var(--purple);box-shadow:0 0 0 3px rgba(139,92,246,.15)}
.table{width:100%;border-collapse:separate;border-spacing:0}.table th{text-align:left;padding:14px 16px;background:rgba(20,20,35,.8);font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}.table td{padding:14px 16px;border-bottom:1px solid var(--border);font-size:13px}
.table tr:hover td{background:rgba(139,92,246,.03)}
.header{background:linear-gradient(145deg,#0d0d18,#0a0a12);border-bottom:1px solid var(--border);padding:16px 24px;display:flex;justify-content:space-between;align-items:center;backdrop-filter:blur(10px)}
.logo{font-size:22px;font-weight:900;background:linear-gradient(135deg,#8b5cf6,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.dr{color:var(--green)}.cr{color:var(--red)}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# MOBILE CAPTURE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/m/<bid>")
def mobile(bid):
    b = biz(bid)
    return f'''<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>📸 Capture</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#050508;background-image:radial-gradient(ellipse at top center,rgba(139,92,246,.15) 0%,transparent 50%),radial-gradient(circle at bottom,rgba(59,130,246,.1) 0%,transparent 40%);color:#fff;height:100vh;height:-webkit-fill-available;display:flex;flex-direction:column;overflow:hidden}}
.header{{padding:20px 24px;display:flex;justify-content:space-between;align-items:center;background:linear-gradient(180deg,rgba(10,10,20,.9) 0%,transparent 100%)}}
.biz{{font-size:20px;font-weight:900;background:linear-gradient(135deg,#8b5cf6,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.desktop{{font-size:11px;color:#666;text-decoration:none;padding:10px 16px;border:1px solid #2a2a3a;border-radius:10px;background:rgba(20,20,35,.5);backdrop-filter:blur(10px);font-weight:600;letter-spacing:.3px;transition:all .2s}}
.desktop:hover{{border-color:#8b5cf6;color:#8b5cf6}}
.main{{flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:20px;position:relative}}
.main::before{{content:'';position:absolute;width:300px;height:300px;background:radial-gradient(circle,rgba(139,92,246,.1) 0%,transparent 70%);border-radius:50%;pointer-events:none}}
.modes{{display:flex;gap:12px;margin-bottom:50px;position:relative;z-index:1}}
.mode{{padding:14px 28px;border-radius:30px;border:2px solid #2a2a3a;background:rgba(20,20,35,.6);color:#888;font-size:14px;font-weight:700;cursor:pointer;backdrop-filter:blur(10px);transition:all .3s;letter-spacing:.3px}}
.mode.active{{border-color:#8b5cf6;color:#fff;background:linear-gradient(135deg,rgba(139,92,246,.2),rgba(139,92,246,.05));box-shadow:0 0 30px rgba(139,92,246,.2)}}
.mode.expense.active{{border-color:#ef4444;color:#fff;background:linear-gradient(135deg,rgba(239,68,68,.2),rgba(239,68,68,.05));box-shadow:0 0 30px rgba(239,68,68,.2)}}
.camera{{width:160px;height:160px;border-radius:50%;border:3px solid rgba(139,92,246,.5);background:linear-gradient(145deg,rgba(139,92,246,.1),rgba(139,92,246,.02));font-size:55px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all .4s;position:relative;z-index:1;box-shadow:0 0 60px rgba(139,92,246,.15),inset 0 0 30px rgba(139,92,246,.05)}}
.camera::after{{content:'';position:absolute;inset:-8px;border-radius:50%;border:1px solid rgba(139,92,246,.2);animation:pulse 2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{transform:scale(1);opacity:.5}}50%{{transform:scale(1.05);opacity:.2}}}}
.camera:active{{transform:scale(.95)}}
.camera.expense{{border-color:rgba(239,68,68,.5);background:linear-gradient(145deg,rgba(239,68,68,.1),rgba(239,68,68,.02));box-shadow:0 0 60px rgba(239,68,68,.15),inset 0 0 30px rgba(239,68,68,.05)}}
.camera.expense::after{{border-color:rgba(239,68,68,.2)}}
.label{{margin-top:20px;color:#666;font-size:13px;font-weight:500;letter-spacing:.5px}}
input[type=file]{{display:none}}
.footer{{padding:24px;background:linear-gradient(180deg,transparent 0%,rgba(10,10,20,.95) 100%);display:flex;justify-content:space-around;border-top:1px solid rgba(255,255,255,.03)}}
.stat{{text-align:center}}.stat-val{{font-size:24px;font-weight:900;background:linear-gradient(135deg,#8b5cf6,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}.stat-lbl{{font-size:9px;color:#555;font-weight:600;letter-spacing:1px;margin-top:4px}}
.overlay{{display:none;position:fixed;inset:0;background:rgba(5,5,10,.98);justify-content:center;align-items:center;flex-direction:column;z-index:100;backdrop-filter:blur(20px)}}.overlay.show{{display:flex}}
.spinner{{width:50px;height:50px;border:3px solid #1a1a2a;border-top-color:#8b5cf6;border-radius:50%;animation:spin .8s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.ledger-box{{background:#141420;border-radius:12px;width:90%;max-width:320px;overflow:hidden;margin:20px 0}}
.ledger-head{{background:rgba(139,92,246,.2);padding:10px 15px;font-size:12px;font-weight:700;color:#8b5cf6}}
.ledger-row{{display:flex;justify-content:space-between;padding:10px 15px;border-bottom:1px solid #222;font-size:13px}}.ledger-row:last-child{{border:none}}
.done-btn{{padding:15px 40px;border-radius:25px;border:none;background:linear-gradient(135deg,#3b82f6,#8b5cf6);color:#fff;font-size:16px;font-weight:700;cursor:pointer}}
</style></head><body>
<div class="header"><div class="biz">📸 {b.get("name",bid)}</div><a href="/{bid}" class="desktop">Desktop →</a></div>
<div class="main">
<div class="modes"><button class="mode active" onclick="setMode('stock')">📦 Stock</button><button class="mode expense" onclick="setMode('expense')">💸 Expense</button></div>
<div class="camera" onclick="document.getElementById('file').click()">📷</div>
<div class="label">Tap to capture</div>
<input type="file" id="file" accept="image/*" capture="environment" onchange="capture(this)">
</div>
<div class="footer">
<div class="stat"><div class="stat-val">{len(b.get("stock",[]))}</div><div class="stat-lbl">STOCK</div></div>
<div class="stat"><div class="stat-val">{len(b.get("ledger",[]))}</div><div class="stat-lbl">ENTRIES</div></div>
</div>
<div class="overlay" id="loading"><div class="spinner"></div><div style="margin-top:20px;color:#888">AI reading...</div></div>
<div class="overlay" id="success">
<div style="font-size:60px;margin-bottom:20px">✅</div>
<div id="successTitle" style="font-size:20px;font-weight:800">Posted!</div>
<div id="successSub" style="color:#888;margin-top:5px"></div>
<div class="ledger-box" id="ledgerBox"></div>
<button class="done-btn" onclick="document.getElementById('success').classList.remove('show')">📷 Next</button>
</div>
<script>
var mode='stock',bid='{bid}';
function setMode(m){{mode=m;document.querySelectorAll('.mode').forEach(b=>b.classList.remove('active'));document.querySelector('.mode'+(m==='expense'?'.expense':'')).classList.add('active');document.querySelector('.camera').className='camera'+(m==='expense'?' expense':'')}}
function capture(input){{if(!input.files[0])return;var r=new FileReader();r.onload=function(e){{process(e.target.result.split(',')[1])}};r.readAsDataURL(input.files[0]);input.value=''}}
function process(b64){{document.getElementById('loading').classList.add('show');fetch('/api/'+bid+'/'+(mode==='stock'?'scan-stock':'scan-expense'),{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{image:b64}})}}).then(r=>r.json()).then(d=>{{document.getElementById('loading').classList.remove('show');if(d.success)showSuccess(d);else alert(d.error||'Error')}}).catch(e=>{{document.getElementById('loading').classList.remove('show');alert(e.message)}})}}
function showSuccess(d){{document.getElementById('successTitle').textContent=mode==='stock'?'📦 Stock Posted!':'💸 Expense Posted!';document.getElementById('successSub').textContent=d.doc_id+' • '+(d.supplier||'');var h='<div class="ledger-head">📒 POSTED</div>';h+='<div class="ledger-row"><span>'+(mode==='stock'?'5000 Cost of Sales':d.category||'Expense')+'</span><span style="color:#10b981">R '+d.amount_excl.toFixed(2)+'</span></div>';h+='<div class="ledger-row"><span>2100 VAT</span><span style="color:#10b981">R '+d.vat.toFixed(2)+'</span></div>';h+='<div class="ledger-row"><span>2000 Creditors</span><span style="color:#ef4444">R '+d.amount_incl.toFixed(2)+'</span></div>';document.getElementById('ledgerBox').innerHTML=h;document.getElementById('success').classList.add('show')}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# HOME
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}</head><body>
<div class="container" style="padding-top:40px">
<div style="text-align:center;margin-bottom:40px"><div class="title" style="font-size:32px">⚡ Click AI</div><div style="color:#666">Snap → Post → Done</div></div>
<div class="card"><div style="font-weight:700;margin-bottom:15px">Your Businesses</div><div id="list"></div>
<div style="margin-top:15px;display:flex;gap:10px"><input type="text" id="newBiz" class="input" placeholder="New business..." style="flex:1"><button class="btn btn-purple" onclick="add()">+ Add</button></div></div>
</div>
<script>
var biz={json.dumps(list(DATA["businesses"].keys()))};
function render(){{var h='';biz.forEach(b=>{{h+='<a href="/'+b+'" style="display:block;padding:15px;background:#1a1a2a;border-radius:8px;margin-bottom:10px;text-decoration:none;color:#fff"><span style="font-weight:700">🏢 '+b+'</span></a>'}});document.getElementById('list').innerHTML=h||'<div style="color:#666;padding:20px;text-align:center">No businesses</div>'}}
function add(){{var n=document.getElementById('newBiz').value.trim();if(!n)return;fetch('/api/business',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:n}})}}).then(r=>r.json()).then(d=>{{if(d.success)window.location.href='/'+d.id}})}}
render();
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>")
def dashboard(bid):
    b = biz(bid)
    mobile_js = f'<script>if(/iPhone|iPad|Android/i.test(navigator.userAgent)&&!sessionStorage.desktop)window.location.href="/m/{bid}"</script>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{b.get("name",bid)}</title>{CSS}</head><body>{mobile_js}
<div class="header"><div class="logo">⚡ {b.get("name",bid)}</div><div style="display:flex;gap:10px"><a href="/{bid}/pos" class="btn btn-green">🛒 POS</a><a href="/{bid}/settings" class="btn btn-dark">⚙️</a><a href="/" class="btn btn-dark">🏠</a></div></div>
<div class="container">
<div class="grid2">
<div class="card"><div style="font-weight:700;margin-bottom:15px">📥 CAPTURE</div><div class="grid2"><a href="/{bid}/capture/stock" class="btn btn-purple">📦 Stock</a><a href="/{bid}/capture/expense" class="btn btn-red">💸 Expense</a></div></div>
<div class="card"><div style="font-weight:700;margin-bottom:15px">📤 SELL</div><div class="grid2"><a href="/{bid}/quote" class="btn btn-purple">📝 Quote</a><a href="/{bid}/invoice" class="btn btn-blue">🧾 Invoice</a></div></div>
</div>
<div class="card"><div style="font-weight:700;margin-bottom:15px">📊 REPORTS</div><div class="grid2" style="margin-bottom:10px"><a href="/{bid}/ledger" class="btn btn-dark">📒 Ledger</a><a href="/{bid}/tb" class="btn btn-dark">📊 Trial Balance</a></div><div class="grid2"><a href="/{bid}/pl" class="btn btn-green">📈 P&L</a><a href="/{bid}/vat" class="btn btn-purple">🧾 VAT</a></div></div>
<div class="card"><div style="font-weight:700;margin-bottom:15px">📁 DATA</div><div class="grid3"><a href="/{bid}/stock" class="btn btn-dark">📦 Stock ({len(b.get("stock",[]))})</a><a href="/{bid}/customers" class="btn btn-dark">👤 Customers</a><a href="/{bid}/suppliers" class="btn btn-dark">👥 Suppliers</a></div></div>
</div></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# POS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/pos")
def pos(bid):
    b = biz(bid)
    stock_js = json.dumps([{"c":s.get("code",""),"d":s.get("description",""),"p":float(s.get("price",0)or s.get("sell",0)or 0),"q":int(s.get("qty",0)or 0),"cat":s.get("category","General")} for s in b.get("stock",[])])
    cat_btns = "".join([f'<button class="cat{" active" if i==0 else ""}" data-cat="{c.lower() if c!="All" else "all"}">{c}</button>' for i,c in enumerate(CATEGORIES)])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#fff;height:100vh;overflow:hidden}}
.header{{background:linear-gradient(135deg,#8b5cf6,#6d28d9);padding:12px 20px;display:flex;justify-content:space-between;align-items:center}}.logo{{font-size:20px;font-weight:900}}.back{{color:#fff;text-decoration:none;margin-right:15px;font-size:18px}}
.main{{display:flex;height:calc(100vh - 52px)}}.left{{flex:1;display:flex;flex-direction:column;border-right:1px solid #1e1e2e}}
.search{{padding:10px}}.search input{{width:100%;padding:12px;background:#12121a;border:1px solid #1e1e2e;border-radius:8px;color:#fff;font-size:14px}}.search input:focus{{outline:none;border-color:#8b5cf6}}
.cats{{display:flex;flex-wrap:wrap;gap:6px;padding:0 10px 10px}}.cat{{background:#12121a;border:1px solid #1e1e2e;color:#888;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px}}.cat:hover,.cat.active{{background:#8b5cf6;color:#fff;border-color:#8b5cf6}}
.info{{padding:8px 15px;background:#12121a;font-size:11px;color:#666;border-bottom:1px solid #1e1e2e}}
.items{{flex:1;overflow-y:auto;padding:10px;display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;align-content:start}}
.item{{background:#12121a;border:1px solid #1e1e2e;border-radius:10px;padding:12px;cursor:pointer}}.item:hover{{border-color:#8b5cf6;transform:translateY(-2px)}}
.item-code{{font-weight:800;color:#8b5cf6;font-size:12px}}.item-desc{{font-size:11px;color:#888;margin:5px 0;height:28px;overflow:hidden}}.item-price{{font-weight:800;color:#10b981;font-size:15px}}.item-qty{{font-size:10px;color:#666}}
.right{{width:320px;display:flex;flex-direction:column;background:#12121a}}.cart-head{{padding:15px;border-bottom:1px solid #1e1e2e;font-weight:800}}.cart-items{{flex:1;overflow-y:auto;padding:10px}}
.cart-item{{background:#0a0a0f;border-radius:8px;padding:10px;margin-bottom:8px}}.cart-item-code{{font-weight:700;color:#8b5cf6;font-size:12px}}.cart-item-del{{background:none;border:none;color:#ef4444;cursor:pointer;font-size:14px}}
.cart-qty{{display:flex;align-items:center;gap:8px}}.cart-qty button{{width:28px;height:28px;border:1px solid #1e1e2e;background:#12121a;color:#fff;border-radius:6px;cursor:pointer;font-weight:700}}.cart-qty button:hover{{background:#8b5cf6;border-color:#8b5cf6}}
.cart-total{{font-weight:800;color:#10b981}}.totals{{padding:15px;border-top:1px solid #1e1e2e}}.total-row{{display:flex;justify-content:space-between;margin-bottom:5px;font-size:13px}}.total-row.big{{font-size:20px;font-weight:800;color:#10b981}}
.btns{{padding:15px;display:flex;flex-direction:column;gap:8px}}.btn{{width:100%;padding:14px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px}}.btn:hover{{transform:translateY(-1px)}}.btn-green{{background:#10b981;color:#fff}}.btn-blue{{background:#3b82f6;color:#fff}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);justify-content:center;align-items:center;z-index:100}}.modal.show{{display:flex}}.modal-box{{background:#12121a;padding:25px;border-radius:16px;width:90%;max-width:360px}}
.modal-title{{font-size:18px;font-weight:800;margin-bottom:15px;text-align:center}}.modal-input{{width:100%;padding:15px;background:#0a0a0f;border:1px solid #1e1e2e;border-radius:8px;color:#fff;font-size:16px;margin-bottom:10px;text-align:center}}
.qty-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:15px 0}}.qty-btn{{background:#0a0a0f;border:1px solid #1e1e2e;color:#fff;padding:15px;border-radius:8px;cursor:pointer;font-weight:700}}.qty-btn:hover{{background:#8b5cf6;border-color:#8b5cf6}}
.modal-btns{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:15px}}.empty{{padding:40px;text-align:center;color:#666}}
</style></head><body>
<div class="header"><div><a href="/{bid}" class="back">←</a><span class="logo">🛒 POS</span></div></div>
<div class="main">
<div class="left"><div class="search"><input type="text" id="search" placeholder="Search..." oninput="render()"></div><div class="cats">{cat_btns}</div><div class="info" id="info">0 items</div><div class="items" id="items"></div></div>
<div class="right"><div class="cart-head">🛒 Cart</div><div class="cart-items" id="cart"></div><div class="totals"><div class="total-row"><span>Subtotal</span><span id="sub">R 0.00</span></div><div class="total-row"><span>VAT 15%</span><span id="vat">R 0.00</span></div><div class="total-row big"><span>Total</span><span id="tot">R 0.00</span></div></div><div class="btns"><button class="btn btn-green" onclick="checkout('cash')">💵 Cash</button><button class="btn btn-blue" onclick="checkout('account')">📋 Account</button></div></div>
</div>
<div class="modal" id="qtyModal"><div class="modal-box"><div class="modal-title" id="qtyTitle">Add</div><div id="qtyInfo" style="text-align:center;color:#888;margin-bottom:10px"></div><input type="number" class="modal-input" id="qtyInput" value="1" min="1"><div class="qty-grid"><button class="qty-btn" onclick="setQ(1)">1</button><button class="qty-btn" onclick="setQ(5)">5</button><button class="qty-btn" onclick="setQ(10)">10</button><button class="qty-btn" onclick="setQ(25)">25</button><button class="qty-btn" onclick="setQ(50)">50</button><button class="qty-btn" onclick="setQ(100)">100</button></div><div class="modal-btns"><button class="btn" style="background:#333" onclick="closeQ()">Cancel</button><button class="btn btn-green" onclick="addQ()">Add</button></div></div></div>
<script>
var stock={stock_js},cart=[],currentCat='all',sel=null;
document.querySelectorAll('.cat').forEach(b=>{{b.onclick=function(){{document.querySelectorAll('.cat').forEach(x=>x.classList.remove('active'));this.classList.add('active');currentCat=this.dataset.cat;render()}}}});
function render(){{var s=document.getElementById('search').value.toLowerCase();var f=stock.filter(i=>{{if(currentCat!=='all'&&(i.cat||'').toLowerCase()!==currentCat)return false;if(s&&!i.c.toLowerCase().includes(s)&&!i.d.toLowerCase().includes(s))return false;return true}});var h='';f.slice(0,100).forEach(i=>{{h+='<div class="item" onclick="pick(\\''+i.c.replace(/'/g,"\\\\'")+'\\')"><div class="item-code">'+i.c+'</div><div class="item-desc">'+i.d.substring(0,40)+'</div><div class="item-price">R '+i.p.toFixed(2)+'</div><div class="item-qty">Stock: '+i.q+'</div></div>'}});document.getElementById('items').innerHTML=h||'<div class="empty">No items</div>';document.getElementById('info').textContent=f.length+' items'}}
function pick(c){{sel=stock.find(i=>i.c===c);if(!sel)return;document.getElementById('qtyTitle').textContent=sel.c;document.getElementById('qtyInfo').textContent=sel.d+' • R '+sel.p.toFixed(2);document.getElementById('qtyInput').value=1;document.getElementById('qtyModal').classList.add('show')}}
function setQ(n){{document.getElementById('qtyInput').value=n}}function closeQ(){{document.getElementById('qtyModal').classList.remove('show')}}
function addQ(){{if(!sel)return;var q=parseInt(document.getElementById('qtyInput').value)||1;var ex=cart.find(c=>c.c===sel.c);if(ex)ex.q+=q;else cart.push({{c:sel.c,d:sel.d,p:sel.p,q:q}});closeQ();renderCart()}}
function renderCart(){{if(cart.length===0){{document.getElementById('cart').innerHTML='<div class="empty">Empty</div>';document.getElementById('sub').textContent='R 0.00';document.getElementById('vat').textContent='R 0.00';document.getElementById('tot').textContent='R 0.00';return}}var h='',sub=0;cart.forEach((c,i)=>{{var l=c.p*c.q;sub+=l;h+='<div class="cart-item"><div style="display:flex;justify-content:space-between"><span class="cart-item-code">'+c.c+'</span><button class="cart-item-del" onclick="delC('+i+')">🗑️</button></div><div style="font-size:11px;color:#888">'+c.d.substring(0,30)+'</div><div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px"><div class="cart-qty"><button onclick="cQ('+i+',-1)">−</button><span>'+c.q+'</span><button onclick="cQ('+i+',1)">+</button></div><span class="cart-total">R '+l.toFixed(2)+'</span></div></div>'}});var v=sub*.15,t=sub+v;document.getElementById('cart').innerHTML=h;document.getElementById('sub').textContent='R '+sub.toFixed(2);document.getElementById('vat').textContent='R '+v.toFixed(2);document.getElementById('tot').textContent='R '+t.toFixed(2)}}
function cQ(i,d){{cart[i].q+=d;if(cart[i].q<=0)cart.splice(i,1);renderCart()}}function delC(i){{cart.splice(i,1);renderCart()}}
function checkout(t){{if(cart.length===0){{alert('Cart empty');return}}fetch('/api/{bid}/pos-sale',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{items:cart.map(c=>({{code:c.c,desc:c.d,price:c.p,qty:c.q}})),type:t}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert('✓ '+d.doc_id);cart=[];renderCart()}}else alert(d.error||'Error')}})}}
render();
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTE / INVOICE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/quote")
def quote(bid): return doc_page(bid,"quote")

@app.route("/<bid>/invoice")
def invoice(bid): return doc_page(bid,"invoice")

def doc_page(bid,dtype):
    b = biz(bid)
    stock_js = json.dumps([{"c":s.get("code",""),"d":s.get("description",""),"p":float(s.get("price",0)or s.get("sell",0)or 0),"q":int(s.get("qty",0)or 0),"cat":s.get("category","General")} for s in b.get("stock",[])])
    cust_js = json.dumps([c.get("name","") for c in b.get("customers",[])])
    cat_btns = "".join([f'<button class="cat{" active" if i==0 else ""}" data-cat="{c.lower() if c!="All" else "all"}">{c}</button>' for i,c in enumerate(CATEGORIES)])
    color = "#8b5cf6" if dtype=="quote" else "#3b82f6"
    title = "📝 Quote" if dtype=="quote" else "🧾 Invoice"
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#fff;height:100vh;overflow:hidden}}
.header{{background:linear-gradient(135deg,{color},#6d28d9);padding:12px 20px;display:flex;justify-content:space-between;align-items:center}}.logo{{font-size:20px;font-weight:900}}.back{{color:#fff;text-decoration:none;margin-right:15px;font-size:18px}}
.cust-bar{{padding:10px 20px;background:#12121a;border-bottom:1px solid #1e1e2e}}.cust-bar input{{width:100%;padding:12px;background:#0a0a0f;border:1px solid #1e1e2e;border-radius:8px;color:#fff}}
.main{{display:flex;height:calc(100vh - 110px)}}.left{{flex:1;display:flex;flex-direction:column;border-right:1px solid #1e1e2e}}
.search{{padding:10px}}.search input{{width:100%;padding:12px;background:#12121a;border:1px solid #1e1e2e;border-radius:8px;color:#fff;font-size:14px}}.search input:focus{{outline:none;border-color:{color}}}
.cats{{display:flex;flex-wrap:wrap;gap:6px;padding:0 10px 10px}}.cat{{background:#12121a;border:1px solid #1e1e2e;color:#888;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px}}.cat:hover,.cat.active{{background:{color};color:#fff;border-color:{color}}}
.info{{padding:8px 15px;background:#12121a;font-size:11px;color:#666;border-bottom:1px solid #1e1e2e}}
.items{{flex:1;overflow-y:auto;padding:10px;display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px;align-content:start}}
.item{{background:#12121a;border:1px solid #1e1e2e;border-radius:10px;padding:12px;cursor:pointer}}.item:hover{{border-color:{color};transform:translateY(-2px)}}
.item-code{{font-weight:800;color:{color};font-size:12px}}.item-desc{{font-size:11px;color:#888;margin:5px 0;height:28px;overflow:hidden}}.item-price{{font-weight:800;color:#10b981;font-size:15px}}.item-qty{{font-size:10px;color:#666}}
.right{{width:320px;display:flex;flex-direction:column;background:#12121a}}.cart-head{{padding:15px;border-bottom:1px solid #1e1e2e;font-weight:800}}.cart-items{{flex:1;overflow-y:auto;padding:10px}}
.cart-item{{background:#0a0a0f;border-radius:8px;padding:10px;margin-bottom:8px}}.cart-item-code{{font-weight:700;color:{color};font-size:12px}}.cart-item-del{{background:none;border:none;color:#ef4444;cursor:pointer;font-size:14px}}
.cart-qty{{display:flex;align-items:center;gap:8px}}.cart-qty button{{width:28px;height:28px;border:1px solid #1e1e2e;background:#12121a;color:#fff;border-radius:6px;cursor:pointer;font-weight:700}}.cart-qty button:hover{{background:{color};border-color:{color}}}
.cart-total{{font-weight:800;color:#10b981}}.totals{{padding:15px;border-top:1px solid #1e1e2e}}.total-row{{display:flex;justify-content:space-between;margin-bottom:5px;font-size:13px}}.total-row.big{{font-size:20px;font-weight:800;color:#10b981}}
.btns{{padding:15px}}.btn{{width:100%;padding:14px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;background:{color};color:#fff}}.btn:hover{{transform:translateY(-1px)}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);justify-content:center;align-items:center;z-index:100}}.modal.show{{display:flex}}.modal-box{{background:#12121a;padding:25px;border-radius:16px;width:90%;max-width:360px}}
.modal-title{{font-size:18px;font-weight:800;margin-bottom:15px;text-align:center}}.modal-input{{width:100%;padding:15px;background:#0a0a0f;border:1px solid #1e1e2e;border-radius:8px;color:#fff;font-size:16px;margin-bottom:10px;text-align:center}}
.qty-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:15px 0}}.qty-btn{{background:#0a0a0f;border:1px solid #1e1e2e;color:#fff;padding:15px;border-radius:8px;cursor:pointer;font-weight:700}}.qty-btn:hover{{background:{color};border-color:{color}}}
.modal-btns{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:15px}}.empty{{padding:40px;text-align:center;color:#666}}
</style></head><body>
<div class="header"><div><a href="/{bid}" class="back">←</a><span class="logo">{title}</span></div></div>
<div class="cust-bar"><input type="text" id="cust" placeholder="🔍 Customer name..." list="custList"><datalist id="custList">{"".join([f'<option value="{c.get("name","")}">' for c in b.get("customers",[])])}</datalist></div>
<div class="main">
<div class="left"><div class="search"><input type="text" id="search" placeholder="Search items..." oninput="render()"></div><div class="cats">{cat_btns}</div><div class="info" id="info">0 items</div><div class="items" id="items"></div></div>
<div class="right"><div class="cart-head">📋 Items</div><div class="cart-items" id="cart"></div><div class="totals"><div class="total-row"><span>Subtotal</span><span id="sub">R 0.00</span></div><div class="total-row"><span>VAT 15%</span><span id="vat">R 0.00</span></div><div class="total-row big"><span>Total</span><span id="tot">R 0.00</span></div></div><div class="btns"><button class="btn" onclick="create()">✓ Create {dtype.title()}</button></div></div>
</div>
<div class="modal" id="qtyModal"><div class="modal-box"><div class="modal-title" id="qtyTitle">Add</div><div id="qtyInfo" style="text-align:center;color:#888;margin-bottom:10px"></div><input type="number" class="modal-input" id="qtyInput" value="1" min="1"><div class="qty-grid"><button class="qty-btn" onclick="setQ(1)">1</button><button class="qty-btn" onclick="setQ(5)">5</button><button class="qty-btn" onclick="setQ(10)">10</button><button class="qty-btn" onclick="setQ(25)">25</button><button class="qty-btn" onclick="setQ(50)">50</button><button class="qty-btn" onclick="setQ(100)">100</button></div><div class="modal-btns"><button class="btn" style="background:#333" onclick="closeQ()">Cancel</button><button class="btn" onclick="addQ()">Add</button></div></div></div>
<script>
var stock={stock_js},cart=[],currentCat='all',sel=null,dtype='{dtype}';
document.querySelectorAll('.cat').forEach(b=>{{b.onclick=function(){{document.querySelectorAll('.cat').forEach(x=>x.classList.remove('active'));this.classList.add('active');currentCat=this.dataset.cat;render()}}}});
function render(){{var s=document.getElementById('search').value.toLowerCase();var f=stock.filter(i=>{{if(currentCat!=='all'&&(i.cat||'').toLowerCase()!==currentCat)return false;if(s&&!i.c.toLowerCase().includes(s)&&!i.d.toLowerCase().includes(s))return false;return true}});var h='';f.slice(0,100).forEach(i=>{{h+='<div class="item" onclick="pick(\\''+i.c.replace(/'/g,"\\\\'")+'\\')"><div class="item-code">'+i.c+'</div><div class="item-desc">'+i.d.substring(0,40)+'</div><div class="item-price">R '+i.p.toFixed(2)+'</div><div class="item-qty">Stock: '+i.q+'</div></div>'}});document.getElementById('items').innerHTML=h||'<div class="empty">No items</div>';document.getElementById('info').textContent=f.length+' items'}}
function pick(c){{sel=stock.find(i=>i.c===c);if(!sel)return;document.getElementById('qtyTitle').textContent=sel.c;document.getElementById('qtyInfo').textContent=sel.d+' • R '+sel.p.toFixed(2);document.getElementById('qtyInput').value=1;document.getElementById('qtyModal').classList.add('show')}}
function setQ(n){{document.getElementById('qtyInput').value=n}}function closeQ(){{document.getElementById('qtyModal').classList.remove('show')}}
function addQ(){{if(!sel)return;var q=parseInt(document.getElementById('qtyInput').value)||1;var ex=cart.find(c=>c.c===sel.c);if(ex)ex.q+=q;else cart.push({{c:sel.c,d:sel.d,p:sel.p,q:q}});closeQ();renderCart()}}
function renderCart(){{if(cart.length===0){{document.getElementById('cart').innerHTML='<div class="empty">No items</div>';document.getElementById('sub').textContent='R 0.00';document.getElementById('vat').textContent='R 0.00';document.getElementById('tot').textContent='R 0.00';return}}var h='',sub=0;cart.forEach((c,i)=>{{var l=c.p*c.q;sub+=l;h+='<div class="cart-item"><div style="display:flex;justify-content:space-between"><span class="cart-item-code">'+c.c+'</span><button class="cart-item-del" onclick="delC('+i+')">🗑️</button></div><div style="font-size:11px;color:#888">'+c.d.substring(0,30)+'</div><div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px"><div class="cart-qty"><button onclick="cQ('+i+',-1)">−</button><span>'+c.q+'</span><button onclick="cQ('+i+',1)">+</button></div><span class="cart-total">R '+l.toFixed(2)+'</span></div></div>'}});var v=sub*.15,t=sub+v;document.getElementById('cart').innerHTML=h;document.getElementById('sub').textContent='R '+sub.toFixed(2);document.getElementById('vat').textContent='R '+v.toFixed(2);document.getElementById('tot').textContent='R '+t.toFixed(2)}}
function cQ(i,d){{cart[i].q+=d;if(cart[i].q<=0)cart.splice(i,1);renderCart()}}function delC(i){{cart.splice(i,1);renderCart()}}
function mapCart(){{return cart.map(function(x){{return {{code:x.c,desc:x.d,price:x.p,qty:x.q}}}})}}
function create(){{if(cart.length===0){{alert('Add items');return}}var c=document.getElementById('cust').value;if(!c){{alert('Enter customer');return}}fetch('/api/{bid}/'+dtype,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{customer:c,items:mapCart()}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert('✓ '+d.doc_id);window.location.href='/{bid}'}}else alert(d.error||'Error')}})}}
render();
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# STOCK LIST
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/stock")
def stock_list(bid):
    b = biz(bid)
    stock = b.get("stock",[])
    tq = sum(int(s.get("qty",0)or 0) for s in stock)
    tv = sum(float(s.get("price",0)or s.get("sell",0)or 0)*int(s.get("qty",0)or 0) for s in stock)
    rows = "".join([f'<tr onclick="location.href=\'/{bid}/stock/{i}/edit\'" style="cursor:pointer"><td><strong>{s.get("code","")}</strong></td><td>{s.get("description","")[:40]}</td><td>{s.get("category","")}</td><td>R {float(s.get("price",0)or s.get("sell",0)or 0):.2f}</td><td>{int(s.get("qty",0)or 0)}</td><td>R {float(s.get("price",0)or s.get("sell",0)or 0)*int(s.get("qty",0)or 0):.2f}</td></tr>' for i,s in enumerate(stock[:100])])
    msg = ""
    if request.args.get("imported"): msg = f'<div style="background:#10b981;color:#fff;padding:12px;border-radius:8px;margin-bottom:15px">✓ Imported {request.args.get("imported")} items!</div>'
    if request.args.get("error"): msg = f'<div style="background:#ef4444;color:#fff;padding:12px;border-radius:8px;margin-bottom:15px">Error: {request.args.get("error")}</div>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stock</title>{CSS}</head><body>
<div class="header"><div class="logo">📦 Stock</div><div style="display:flex;gap:10px"><a href="/{bid}/stock/add" class="btn btn-purple">+ Add</a><a href="/{bid}" class="btn btn-dark">← Back</a></div></div>
<div class="container">{msg}
<div class="grid3" style="margin-bottom:20px">
<div class="card" style="text-align:center"><div style="font-size:24px;font-weight:800;color:#8b5cf6">{len(stock)}</div><div style="color:#666;font-size:12px">ITEMS</div></div>
<div class="card" style="text-align:center"><div style="font-size:24px;font-weight:800;color:#3b82f6">{tq:,}</div><div style="color:#666;font-size:12px">TOTAL QTY</div></div>
<div class="card" style="text-align:center"><div style="font-size:24px;font-weight:800;color:#10b981">R {tv:,.2f}</div><div style="color:#666;font-size:12px">VALUE</div></div>
</div>
<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px"><span style="font-weight:700">Import from CSV</span></div>
<form method="POST" action="/{bid}/stock/import" enctype="multipart/form-data" style="display:flex;gap:10px"><input type="file" name="file" accept=".csv" class="input" style="flex:1" required><button type="submit" class="btn btn-blue">📤 Import</button></form>
<div style="font-size:11px;color:#666;margin-top:8px">CSV columns: code, description, category, qty, cost, price</div>
</div>
<div class="card"><table class="table"><thead><tr><th>Code</th><th>Description</th><th>Category</th><th>Price</th><th>Qty</th><th>Value</th></tr></thead><tbody>{rows or '<tr><td colspan="6" style="text-align:center;color:#666">No stock - add items or import CSV</td></tr>'}</tbody></table></div>
</div></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/ledger")
def ledger(bid):
    b = biz(bid)
    rows = "".join([f'<tr><td>{e.get("date","")}</td><td>{e.get("doc_id","")}</td><td>{e.get("account","")} {e.get("account_name","")}</td><td>{e.get("description","")[:25]}</td><td class="dr">{"R "+f"{e.get('debit',0):.2f}" if e.get("debit",0)>0 else ""}</td><td class="cr">{"R "+f"{e.get('credit',0):.2f}" if e.get("credit",0)>0 else ""}</td></tr>' for e in reversed(b.get("ledger",[])[-100:])])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ledger</title>{CSS}</head><body>
<div class="header"><div class="logo">📒 Ledger</div><a href="/{bid}" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card"><table class="table"><thead><tr><th>Date</th><th>Doc</th><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{rows or '<tr><td colspan="6" style="text-align:center;color:#666">No entries</td></tr>'}</tbody></table></div></div></body></html>'''

@app.route("/<bid>/tb")
def tb(bid):
    b = biz(bid)
    bals = {}
    for e in b.get("ledger",[]):
        a = e.get("account","")
        if a not in bals: bals[a] = {"n":e.get("account_name",ACCOUNTS.get(a,a)),"d":0,"c":0}
        bals[a]["d"] += float(e.get("debit",0)or 0)
        bals[a]["c"] += float(e.get("credit",0)or 0)
    rows = ""
    td,tc = 0,0
    for a in sorted(bals.keys()):
        nd,nc = max(0,bals[a]["d"]-bals[a]["c"]),max(0,bals[a]["c"]-bals[a]["d"])
        if nd>0 or nc>0:
            td+=nd;tc+=nc
            rows += f'<tr><td>{a}</td><td>{bals[a]["n"]}</td><td class="dr">{"R "+f"{nd:.2f}" if nd>0 else ""}</td><td class="cr">{"R "+f"{nc:.2f}" if nc>0 else ""}</td></tr>'
    rows += f'<tr style="font-weight:800;border-top:2px solid #333"><td colspan="2">TOTAL</td><td class="dr">R {td:.2f}</td><td class="cr">R {tc:.2f}</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trial Balance</title>{CSS}</head><body>
<div class="header"><div class="logo">📊 Trial Balance</div><a href="/{bid}" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card"><table class="table"><thead><tr><th>Code</th><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{rows}</tbody></table></div></div></body></html>'''

@app.route("/<bid>/pl")
def pl(bid):
    b = biz(bid)
    inc,cos,exp = 0,0,0
    for e in b.get("ledger",[]):
        a,d,c = e.get("account",""),float(e.get("debit",0)or 0),float(e.get("credit",0)or 0)
        if a.startswith("4"): inc += c-d
        elif a.startswith("5"): cos += d-c
        elif a.startswith("6"): exp += d-c
    gp,np = inc-cos,inc-cos-exp
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>P&L</title>{CSS}</head><body>
<div class="header"><div class="logo">📈 Profit & Loss</div><a href="/{bid}" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card">
<div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid #1e1e2e"><span>Sales</span><span style="color:#10b981">R {inc:,.2f}</span></div>
<div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid #1e1e2e"><span>Cost of Sales</span><span style="color:#ef4444">(R {cos:,.2f})</span></div>
<div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid #1e1e2e;font-weight:700"><span>Gross Profit</span><span style="color:{'#10b981' if gp>=0 else '#ef4444'}">R {gp:,.2f}</span></div>
<div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid #1e1e2e"><span>Expenses</span><span style="color:#ef4444">(R {exp:,.2f})</span></div>
<div style="display:flex;justify-content:space-between;padding:20px 0;font-size:20px;font-weight:800"><span>Net Profit</span><span style="color:{'#10b981' if np>=0 else '#ef4444'}">R {np:,.2f}</span></div>
</div></div></body></html>'''

@app.route("/<bid>/vat")
def vat(bid):
    b = biz(bid)
    vi,vo = 0,0
    for e in b.get("ledger",[]):
        a,d,c = e.get("account",""),float(e.get("debit",0)or 0),float(e.get("credit",0)or 0)
        if a=="2100": vi += d-c
        elif a=="2200": vo += c-d
    net = vo-vi
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VAT</title>{CSS}</head><body>
<div class="header"><div class="logo">🧾 VAT Report</div><a href="/{bid}" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card">
<div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid #1e1e2e"><span>VAT Output (Sales)</span><span style="color:#ef4444">R {vo:,.2f}</span></div>
<div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid #1e1e2e"><span>VAT Input (Purchases)</span><span style="color:#10b981">(R {vi:,.2f})</span></div>
<div style="display:flex;justify-content:space-between;padding:20px 0;font-size:20px;font-weight:800"><span>{"VAT Payable" if net>=0 else "VAT Refund"}</span><span style="color:{'#ef4444' if net>=0 else '#10b981'}">R {abs(net):,.2f}</span></div>
</div></div></body></html>'''

@app.route("/<bid>/customers")
def customers(bid):
    b = biz(bid)
    rows = "".join([f'<tr><td><strong>{c.get("code","")}</strong></td><td>{c.get("name","")}</td><td>{c.get("phone","")}</td><td>{c.get("email","")}</td><td style="color:{"#ef4444" if float(c.get("balance",0)or 0)>0 else "#10b981"}">R {float(c.get("balance",0)or 0):.2f}</td></tr>' for c in b.get("customers",[])])
    msg = ""
    if request.args.get("imported"): msg = f'<div style="background:#10b981;color:#fff;padding:12px;border-radius:8px;margin-bottom:15px">✓ Imported {request.args.get("imported")} customers!</div>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customers</title>{CSS}</head><body>
<div class="header"><div class="logo">👤 Customers</div><div style="display:flex;gap:10px"><a href="/{bid}/customers/add" class="btn btn-purple">+ Add</a><a href="/{bid}" class="btn btn-dark">← Back</a></div></div>
<div class="container">{msg}
<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px"><span style="font-weight:700">Import from CSV</span></div>
<form method="POST" action="/{bid}/customers/import" enctype="multipart/form-data" style="display:flex;gap:10px"><input type="file" name="file" accept=".csv" class="input" style="flex:1" required><button type="submit" class="btn btn-blue">📤 Import</button></form>
<div style="font-size:11px;color:#666;margin-top:8px">CSV columns: code, name, phone, email, balance</div>
</div>
<div class="card"><table class="table"><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th></tr></thead><tbody>{rows or '<tr><td colspan="5" style="text-align:center;color:#666">No customers</td></tr>'}</tbody></table></div>
</div></body></html>'''

@app.route("/<bid>/suppliers")
def suppliers(bid):
    b = biz(bid)
    rows = "".join([f'<tr><td><strong>{s.get("code","")}</strong></td><td>{s.get("name","")}</td><td>{s.get("phone","")}</td><td>{s.get("email","")}</td><td style="color:{"#ef4444" if float(s.get("balance",0)or 0)>0 else "#10b981"}">R {float(s.get("balance",0)or 0):.2f}</td></tr>' for s in b.get("suppliers",[])])
    msg = ""
    if request.args.get("imported"): msg = f'<div style="background:#10b981;color:#fff;padding:12px;border-radius:8px;margin-bottom:15px">✓ Imported {request.args.get("imported")} suppliers!</div>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suppliers</title>{CSS}</head><body>
<div class="header"><div class="logo">👥 Suppliers</div><div style="display:flex;gap:10px"><a href="/{bid}/suppliers/add" class="btn btn-purple">+ Add</a><a href="/{bid}" class="btn btn-dark">← Back</a></div></div>
<div class="container">{msg}
<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px"><span style="font-weight:700">Import from CSV</span></div>
<form method="POST" action="/{bid}/suppliers/import" enctype="multipart/form-data" style="display:flex;gap:10px"><input type="file" name="file" accept=".csv" class="input" style="flex:1" required><button type="submit" class="btn btn-blue">📤 Import</button></form>
<div style="font-size:11px;color:#666;margin-top:8px">CSV columns: code, name, phone, email, balance</div>
</div>
<div class="card"><table class="table"><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th></tr></thead><tbody>{rows or '<tr><td colspan="5" style="text-align:center;color:#666">No suppliers</td></tr>'}</tbody></table></div>
</div></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# DESKTOP CAPTURE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/capture/stock")
def cap_stock(bid): return cap_page(bid,"stock")

@app.route("/<bid>/capture/expense")
def cap_expense(bid): return cap_page(bid,"expense")

def cap_page(bid,mode):
    b = biz(bid)
    color = "#8b5cf6" if mode=="stock" else "#ef4444"
    title = "📦 Stock Invoice" if mode=="stock" else "💸 Expense"
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{CSS}
<style>.upload{{border:2px dashed #333;border-radius:16px;padding:60px 40px;text-align:center;cursor:pointer;transition:all .2s}}.upload:hover{{border-color:{color};background:rgba(139,92,246,.05)}}.spinner{{width:40px;height:40px;border:4px solid #333;border-top-color:{color};border-radius:50%;animation:spin .8s linear infinite;margin:20px auto}}@keyframes spin{{to{{transform:rotate(360deg)}}}}</style>
</head><body>
<div class="header"><div class="logo">{title}</div><a href="/{bid}" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card">
<div class="upload" onclick="document.getElementById('file').click()"><div style="font-size:60px;margin-bottom:15px">📸</div><div style="color:#888">Click to upload invoice</div></div>
<input type="file" id="file" accept="image/*" style="display:none" onchange="preview(this)">
<div id="preview" style="display:none"><img id="img" style="max-width:100%;max-height:300px;border-radius:12px"><div style="margin-top:15px"><button class="btn btn-purple" onclick="process()" style="width:auto;padding:12px 30px">🤖 Process</button></div></div>
<div id="loading" style="display:none;text-align:center;padding:40px"><div class="spinner"></div><div style="color:#888">AI reading...</div></div>
<div id="result" style="display:none;margin-top:20px"></div>
</div></div>
<script>
var img=null,mode='{mode}',bid='{bid}';
function preview(i){{if(!i.files[0])return;var r=new FileReader();r.onload=function(e){{img=e.target.result.split(',')[1];document.getElementById('img').src=e.target.result;document.getElementById('preview').style.display='block'}};r.readAsDataURL(i.files[0])}}
function process(){{if(!img)return;document.getElementById('loading').style.display='block';document.getElementById('result').style.display='none';fetch('/api/'+bid+'/'+(mode==='stock'?'scan-stock':'scan-expense'),{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{image:img}})}}).then(r=>r.json()).then(d=>{{document.getElementById('loading').style.display='none';var h='';if(d.success){{h='<div style="background:#10b981;color:#fff;padding:15px;border-radius:8px;margin-bottom:15px">✅ Posted! '+d.doc_id+'</div><div style="background:#12121a;padding:15px;border-radius:8px"><div><strong>Supplier:</strong> '+(d.supplier||'')+'</div><div><strong>Amount:</strong> R '+(d.amount_incl||0).toFixed(2)+'</div></div><a href="/'+bid+'/ledger" class="btn btn-dark" style="margin-top:15px;width:auto">📒 Ledger</a>'}}else{{h='<div style="background:#ef4444;color:#fff;padding:15px;border-radius:8px">❌ '+(d.error||'Error')+'</div>'}}document.getElementById('result').innerHTML=h;document.getElementById('result').style.display='block'}}).catch(e=>{{document.getElementById('loading').style.display='none';document.getElementById('result').innerHTML='<div style="background:#ef4444;color:#fff;padding:15px;border-radius:8px">❌ '+e.message+'</div>';document.getElementById('result').style.display='block'}})}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/business", methods=["POST"])
def api_biz():
    d = request.get_json()
    n = d.get("name","").strip()
    if not n: return jsonify({"success":False,"error":"Name required"})
    bid = re.sub(r'[^a-z0-9-]','',n.lower().replace(" ","-"))
    DATA["businesses"][bid] = {"name":n,"stock":[],"customers":[],"suppliers":[],"ledger":[],"documents":{"quotes":[],"invoices":[]}}
    save()
    return jsonify({"success":True,"id":bid})

@app.route("/api/<bid>/scan-stock", methods=["POST"])
def api_scan_stock(bid):
    b = biz(bid)
    d = request.get_json()
    img = d.get("image","")
    if not img: return jsonify({"success":False,"error":"No image"})
    api_key = os.environ.get("ANTHROPIC_API_KEY","")
    if not api_key: return jsonify({"success":False,"error":"API key missing"})
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model="claude-sonnet-4-20250514",max_tokens=1024,messages=[{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":img}},{"type":"text","text":'Read invoice. Return JSON only: {"supplier":"Name","date":"YYYY-MM-DD","total_excl":100,"vat":15,"total_incl":115,"items":[{"code":"X","description":"Item","qty":1,"price":100}]}'}]}])
        txt = msg.content[0].text
        m = re.search(r'\{.*\}',txt,re.DOTALL)
        if not m: return jsonify({"success":False,"error":"Could not parse"})
        r = json.loads(m.group())
        doc_id = f"SINV{len(b['ledger'])//3+1:04d}"
        date = r.get("date",datetime.now().strftime("%Y-%m-%d"))
        excl,vat,incl = float(r.get("total_excl",0)),float(r.get("vat",0)),float(r.get("total_incl",0))
        if incl==0: incl=excl+vat
        sup = r.get("supplier","Unknown")
        b["ledger"].append({"date":date,"doc_id":doc_id,"account":"5000","account_name":"Cost of Sales","description":sup,"debit":excl,"credit":0})
        b["ledger"].append({"date":date,"doc_id":doc_id,"account":"2100","account_name":"VAT Input","description":sup,"debit":vat,"credit":0})
        b["ledger"].append({"date":date,"doc_id":doc_id,"account":"2000","account_name":"Creditors","description":sup,"debit":0,"credit":incl})
        for it in r.get("items",[]):
            ex = next((s for s in b["stock"] if s.get("code")==it.get("code")),None)
            if ex: ex["qty"]=int(ex.get("qty",0))+int(it.get("qty",0))
            else: b["stock"].append({"code":it.get("code",""),"description":it.get("description",""),"category":"General","qty":int(it.get("qty",0)),"cost":float(it.get("price",0)),"price":float(it.get("price",0))*1.3})
        save()
        return jsonify({"success":True,"doc_id":doc_id,"supplier":sup,"amount_excl":excl,"vat":vat,"amount_incl":incl})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/api/<bid>/scan-expense", methods=["POST"])
def api_scan_expense(bid):
    b = biz(bid)
    d = request.get_json()
    img = d.get("image","")
    if not img: return jsonify({"success":False,"error":"No image"})
    api_key = os.environ.get("ANTHROPIC_API_KEY","")
    if not api_key: return jsonify({"success":False,"error":"API key missing"})
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model="claude-sonnet-4-20250514",max_tokens=1024,messages=[{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":img}},{"type":"text","text":'Read expense. Return JSON: {"supplier":"Name","date":"YYYY-MM-DD","category":"6200","category_name":"Utilities","amount_excl":100,"vat":15,"amount_incl":115}. Categories: 6100=Rent,6200=Utilities,6300=Phone,6910=Fuel(NO VAT),6999=Other. Fuel has vat=0.'}]}])
        txt = msg.content[0].text
        m = re.search(r'\{.*\}',txt,re.DOTALL)
        if not m: return jsonify({"success":False,"error":"Could not parse"})
        r = json.loads(m.group())
        doc_id = f"EXP{len([e for e in b['ledger'] if 'EXP' in e.get('doc_id','')])//3+1:04d}"
        date = r.get("date",datetime.now().strftime("%Y-%m-%d"))
        excl,vat,incl = float(r.get("amount_excl",0)),float(r.get("vat",0)),float(r.get("amount_incl",0))
        if incl==0: incl=excl+vat
        sup,cat,catn = r.get("supplier","Unknown"),r.get("category","6999"),r.get("category_name","Other")
        b["ledger"].append({"date":date,"doc_id":doc_id,"account":cat,"account_name":catn,"description":sup,"debit":excl,"credit":0})
        if vat>0: b["ledger"].append({"date":date,"doc_id":doc_id,"account":"2100","account_name":"VAT Input","description":sup,"debit":vat,"credit":0})
        b["ledger"].append({"date":date,"doc_id":doc_id,"account":"2000","account_name":"Creditors","description":sup,"debit":0,"credit":incl})
        save()
        return jsonify({"success":True,"doc_id":doc_id,"supplier":sup,"category":catn,"amount_excl":excl,"vat":vat,"amount_incl":incl})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/api/<bid>/pos-sale", methods=["POST"])
def api_pos(bid):
    b = biz(bid)
    d = request.get_json()
    items,t = d.get("items",[]),d.get("type","cash")
    if not items: return jsonify({"success":False,"error":"No items"})
    sub = sum(i["price"]*i["qty"] for i in items)
    vat,tot = round(sub*.15,2),round(sub*1.15,2)
    doc_id = f"SALE{len([e for e in b['ledger'] if 'SALE' in e.get('doc_id','')])//3+1:04d}"
    date = datetime.now().strftime("%Y-%m-%d")
    if t=="cash": b["ledger"].append({"date":date,"doc_id":doc_id,"account":"1000","account_name":"Bank","description":"Cash Sale","debit":tot,"credit":0})
    else: b["ledger"].append({"date":date,"doc_id":doc_id,"account":"1200","account_name":"Debtors","description":"Account Sale","debit":tot,"credit":0})
    b["ledger"].append({"date":date,"doc_id":doc_id,"account":"4000","account_name":"Sales","description":"POS Sale","debit":0,"credit":sub})
    b["ledger"].append({"date":date,"doc_id":doc_id,"account":"2200","account_name":"VAT Output","description":"POS Sale","debit":0,"credit":vat})
    for i in items:
        s = next((x for x in b["stock"] if x.get("code")==i["code"]),None)
        if s: s["qty"]=max(0,int(s.get("qty",0))-i["qty"])
    save()
    return jsonify({"success":True,"doc_id":doc_id,"total":tot})

@app.route("/api/<bid>/quote", methods=["POST"])
def api_quote(bid):
    b = biz(bid)
    d = request.get_json()
    cust,items = d.get("customer",""),d.get("items",[])
    if not items: return jsonify({"success":False,"error":"No items"})
    sub = sum(i["price"]*i["qty"] for i in items)
    doc_id = f"QT{len(b['documents']['quotes'])+1:04d}"
    b["documents"]["quotes"].append({"id":doc_id,"date":datetime.now().strftime("%Y-%m-%d"),"customer":cust,"items":items,"subtotal":sub,"vat":round(sub*.15,2),"total":round(sub*1.15,2)})
    save()
    return jsonify({"success":True,"doc_id":doc_id})

@app.route("/api/<bid>/invoice", methods=["POST"])
def api_invoice(bid):
    b = biz(bid)
    d = request.get_json()
    cust,items = d.get("customer",""),d.get("items",[])
    if not items: return jsonify({"success":False,"error":"No items"})
    sub = sum(i["price"]*i["qty"] for i in items)
    vat,tot = round(sub*.15,2),round(sub*1.15,2)
    doc_id = f"INV{len(b['documents']['invoices'])+1:04d}"
    date = datetime.now().strftime("%Y-%m-%d")
    b["documents"]["invoices"].append({"id":doc_id,"date":date,"customer":cust,"items":items,"subtotal":sub,"vat":vat,"total":tot})
    b["ledger"].append({"date":date,"doc_id":doc_id,"account":"1200","account_name":"Debtors","description":cust,"debit":tot,"credit":0})
    b["ledger"].append({"date":date,"doc_id":doc_id,"account":"4000","account_name":"Sales","description":cust,"debit":0,"credit":sub})
    b["ledger"].append({"date":date,"doc_id":doc_id,"account":"2200","account_name":"VAT Output","description":cust,"debit":0,"credit":vat})
    for i in items:
        s = next((x for x in b["stock"] if x.get("code")==i["code"]),None)
        if s: s["qty"]=max(0,int(s.get("qty",0))-i["qty"])
    save()
    return jsonify({"success":True,"doc_id":doc_id})

# ═══════════════════════════════════════════════════════════════════════════════
# STOCK MANAGEMENT - Add, Edit, Import CSV
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/stock/add", methods=["GET","POST"])
def stock_add(bid):
    b = biz(bid)
    if request.method == "POST":
        b["stock"].append({"code":request.form.get("code","").strip(),"description":request.form.get("description","").strip(),"category":request.form.get("category","General").strip(),"qty":int(float(request.form.get("qty",0) or 0)),"cost":float(request.form.get("cost",0) or 0),"price":float(request.form.get("price",0) or 0)})
        save()
        return redirect(f"/{bid}/stock")
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Add Stock</title>{CSS}</head><body>
<div class="header"><div class="logo">📦 Add Stock Item</div><a href="/{bid}/stock" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card"><form method="POST">
<div class="grid2" style="margin-bottom:12px"><div><label style="font-size:12px;color:#888">Code</label><input name="code" class="input" required></div><div><label style="font-size:12px;color:#888">Category</label><input name="category" class="input" value="General"></div></div>
<div style="margin-bottom:12px"><label style="font-size:12px;color:#888">Description</label><input name="description" class="input" required></div>
<div class="grid3" style="margin-bottom:20px"><div><label style="font-size:12px;color:#888">Qty</label><input name="qty" type="number" class="input" value="0"></div><div><label style="font-size:12px;color:#888">Cost</label><input name="cost" type="number" step="0.01" class="input" value="0"></div><div><label style="font-size:12px;color:#888">Sell Price</label><input name="price" type="number" step="0.01" class="input" value="0"></div></div>
<button type="submit" class="btn btn-purple" style="width:100%">+ Add Item</button>
</form></div></div></body></html>'''

@app.route("/<bid>/stock/<int:idx>/edit", methods=["GET","POST"])
def stock_edit(bid,idx):
    b = biz(bid)
    if idx >= len(b["stock"]): return redirect(f"/{bid}/stock")
    item = b["stock"][idx]
    if request.method == "POST":
        item["code"] = request.form.get("code","").strip()
        item["description"] = request.form.get("description","").strip()
        item["category"] = request.form.get("category","General").strip()
        item["qty"] = int(float(request.form.get("qty",0) or 0))
        item["cost"] = float(request.form.get("cost",0) or 0)
        item["price"] = float(request.form.get("price",0) or 0)
        save()
        return redirect(f"/{bid}/stock")
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Edit Stock</title>{CSS}</head><body>
<div class="header"><div class="logo">📦 Edit Stock Item</div><a href="/{bid}/stock" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card"><form method="POST">
<div class="grid2" style="margin-bottom:12px"><div><label style="font-size:12px;color:#888">Code</label><input name="code" class="input" value="{item.get('code','')}" required></div><div><label style="font-size:12px;color:#888">Category</label><input name="category" class="input" value="{item.get('category','General')}"></div></div>
<div style="margin-bottom:12px"><label style="font-size:12px;color:#888">Description</label><input name="description" class="input" value="{item.get('description','')}" required></div>
<div class="grid3" style="margin-bottom:20px"><div><label style="font-size:12px;color:#888">Qty</label><input name="qty" type="number" class="input" value="{int(item.get('qty',0))}"></div><div><label style="font-size:12px;color:#888">Cost</label><input name="cost" type="number" step="0.01" class="input" value="{float(item.get('cost',0))}"></div><div><label style="font-size:12px;color:#888">Sell Price</label><input name="price" type="number" step="0.01" class="input" value="{float(item.get('price',0))}"></div></div>
<div class="grid2"><button type="submit" class="btn btn-green">✓ Save</button><a href="/{bid}/stock/{idx}/delete" class="btn btn-red" onclick="return confirm('Delete this item?')">🗑️ Delete</a></div>
</form></div></div></body></html>'''

@app.route("/<bid>/stock/<int:idx>/delete")
def stock_delete(bid,idx):
    b = biz(bid)
    if idx < len(b["stock"]): b["stock"].pop(idx)
    save()
    return redirect(f"/{bid}/stock")

@app.route("/<bid>/stock/import", methods=["POST"])
def stock_import(bid):
    b = biz(bid)
    try:
        f = request.files['file']
        content = f.read().decode('utf-8-sig')
        # Handle both comma and semicolon delimiters
        delim = ';' if ';' in content.split('\n')[0] else ','
        reader = csv.DictReader(io.StringIO(content), delimiter=delim)
        count = 0
        for row in reader:
            code = row.get('code') or row.get('Code') or row.get('CODE') or row.get('sku') or row.get('SKU') or ''
            desc = row.get('description') or row.get('Description') or row.get('name') or row.get('Name') or ''
            if code or desc:
                b["stock"].append({
                    'code': code.strip(),
                    'description': desc.strip(),
                    'category': (row.get('category') or row.get('Category') or 'General').strip(),
                    'qty': int(float(row.get('qty') or row.get('Qty') or row.get('quantity') or 0)),
                    'cost': float(row.get('cost') or row.get('Cost') or 0),
                    'price': float(row.get('price') or row.get('Price') or row.get('sell') or row.get('Sell') or 0)
                })
                count += 1
        save()
        return redirect(f"/{bid}/stock?imported={count}")
    except Exception as e:
        return redirect(f"/{bid}/stock?error={str(e)}")

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/customers/add", methods=["GET","POST"])
def customer_add(bid):
    b = biz(bid)
    if request.method == "POST":
        b["customers"].append({"code":request.form.get("code","").strip(),"name":request.form.get("name","").strip(),"phone":request.form.get("phone","").strip(),"email":request.form.get("email","").strip(),"balance":0})
        save()
        return redirect(f"/{bid}/customers")
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Add Customer</title>{CSS}</head><body>
<div class="header"><div class="logo">👤 Add Customer</div><a href="/{bid}/customers" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card"><form method="POST">
<div class="grid2" style="margin-bottom:12px"><div><label style="font-size:12px;color:#888">Code</label><input name="code" class="input" placeholder="C001"></div><div><label style="font-size:12px;color:#888">Name</label><input name="name" class="input" required></div></div>
<div class="grid2" style="margin-bottom:20px"><div><label style="font-size:12px;color:#888">Phone</label><input name="phone" class="input"></div><div><label style="font-size:12px;color:#888">Email</label><input name="email" type="email" class="input"></div></div>
<button type="submit" class="btn btn-purple" style="width:100%">+ Add Customer</button>
</form></div></div></body></html>'''

@app.route("/<bid>/customers/import", methods=["POST"])
def customer_import(bid):
    b = biz(bid)
    try:
        f = request.files['file']
        content = f.read().decode('utf-8-sig')
        delim = ';' if ';' in content.split('\n')[0] else ','
        reader = csv.DictReader(io.StringIO(content), delimiter=delim)
        count = 0
        for row in reader:
            name = row.get('name') or row.get('Name') or row.get('customer') or ''
            if name:
                b["customers"].append({
                    'code': (row.get('code') or row.get('Code') or f"C{len(b['customers'])+1:03d}").strip(),
                    'name': name.strip(),
                    'phone': (row.get('phone') or row.get('Phone') or row.get('tel') or '').strip(),
                    'email': (row.get('email') or row.get('Email') or '').strip(),
                    'balance': float(row.get('balance') or row.get('Balance') or 0)
                })
                count += 1
        save()
        return redirect(f"/{bid}/customers?imported={count}")
    except Exception as e:
        return redirect(f"/{bid}/customers?error={str(e)}")

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIER MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/suppliers/add", methods=["GET","POST"])
def supplier_add(bid):
    b = biz(bid)
    if request.method == "POST":
        b["suppliers"].append({"code":request.form.get("code","").strip(),"name":request.form.get("name","").strip(),"phone":request.form.get("phone","").strip(),"email":request.form.get("email","").strip(),"balance":0})
        save()
        return redirect(f"/{bid}/suppliers")
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Add Supplier</title>{CSS}</head><body>
<div class="header"><div class="logo">👥 Add Supplier</div><a href="/{bid}/suppliers" class="btn btn-dark">← Back</a></div>
<div class="container"><div class="card"><form method="POST">
<div class="grid2" style="margin-bottom:12px"><div><label style="font-size:12px;color:#888">Code</label><input name="code" class="input" placeholder="S001"></div><div><label style="font-size:12px;color:#888">Name</label><input name="name" class="input" required></div></div>
<div class="grid2" style="margin-bottom:20px"><div><label style="font-size:12px;color:#888">Phone</label><input name="phone" class="input"></div><div><label style="font-size:12px;color:#888">Email</label><input name="email" type="email" class="input"></div></div>
<button type="submit" class="btn btn-purple" style="width:100%">+ Add Supplier</button>
</form></div></div></body></html>'''

@app.route("/<bid>/suppliers/import", methods=["POST"])
def supplier_import(bid):
    b = biz(bid)
    try:
        f = request.files['file']
        content = f.read().decode('utf-8-sig')
        delim = ';' if ';' in content.split('\n')[0] else ','
        reader = csv.DictReader(io.StringIO(content), delimiter=delim)
        count = 0
        for row in reader:
            name = row.get('name') or row.get('Name') or row.get('supplier') or ''
            if name:
                b["suppliers"].append({
                    'code': (row.get('code') or row.get('Code') or f"S{len(b['suppliers'])+1:03d}").strip(),
                    'name': name.strip(),
                    'phone': (row.get('phone') or row.get('Phone') or row.get('tel') or '').strip(),
                    'email': (row.get('email') or row.get('Email') or '').strip(),
                    'balance': float(row.get('balance') or row.get('Balance') or 0)
                })
                count += 1
        save()
        return redirect(f"/{bid}/suppliers?imported={count}")
    except Exception as e:
        return redirect(f"/{bid}/suppliers?error={str(e)}")

# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/<bid>/settings", methods=["GET","POST"])
def settings(bid):
    b = biz(bid)
    if "settings" not in b: b["settings"] = {}
    if request.method == "POST":
        b["settings"]["company_name"] = request.form.get("company_name","").strip()
        b["settings"]["trading_as"] = request.form.get("trading_as","").strip()
        b["settings"]["reg_number"] = request.form.get("reg_number","").strip()
        b["settings"]["vat_number"] = request.form.get("vat_number","").strip()
        b["settings"]["address"] = request.form.get("address","").strip()
        b["settings"]["phone"] = request.form.get("phone","").strip()
        b["settings"]["email"] = request.form.get("email","").strip()
        b["settings"]["bank_name"] = request.form.get("bank_name","").strip()
        b["settings"]["bank_account"] = request.form.get("bank_account","").strip()
        b["settings"]["bank_branch"] = request.form.get("bank_branch","").strip()
        b["name"] = b["settings"]["company_name"] or b["name"]
        save()
        return redirect(f"/{bid}/settings?saved=1")
    s = b.get("settings",{})
    saved = '<div style="background:#10b981;color:#fff;padding:12px;border-radius:8px;margin-bottom:15px">✓ Settings saved!</div>' if request.args.get("saved") else ""
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Settings</title>{CSS}</head><body>
<div class="header"><div class="logo">⚙️ Business Settings</div><a href="/{bid}" class="btn btn-dark">← Back</a></div>
<div class="container">{saved}<form method="POST">
<div class="card"><div style="font-weight:700;margin-bottom:15px">🏢 Company Details</div>
<div class="grid2" style="margin-bottom:12px"><div><label style="font-size:12px;color:#888">Company Name (Pty Ltd)</label><input name="company_name" class="input" value="{s.get('company_name','')}"></div><div><label style="font-size:12px;color:#888">Trading As</label><input name="trading_as" class="input" value="{s.get('trading_as','')}"></div></div>
<div class="grid2" style="margin-bottom:12px"><div><label style="font-size:12px;color:#888">Registration Number</label><input name="reg_number" class="input" value="{s.get('reg_number','')}"></div><div><label style="font-size:12px;color:#888">VAT Number</label><input name="vat_number" class="input" value="{s.get('vat_number','')}"></div></div>
<div style="margin-bottom:12px"><label style="font-size:12px;color:#888">Address</label><textarea name="address" class="input" rows="2">{s.get('address','')}</textarea></div>
<div class="grid2"><div><label style="font-size:12px;color:#888">Phone</label><input name="phone" class="input" value="{s.get('phone','')}"></div><div><label style="font-size:12px;color:#888">Email</label><input name="email" type="email" class="input" value="{s.get('email','')}"></div></div>
</div>
<div class="card"><div style="font-weight:700;margin-bottom:15px">🏦 Banking Details</div>
<div class="grid3"><div><label style="font-size:12px;color:#888">Bank Name</label><input name="bank_name" class="input" value="{s.get('bank_name','')}"></div><div><label style="font-size:12px;color:#888">Account Number</label><input name="bank_account" class="input" value="{s.get('bank_account','')}"></div><div><label style="font-size:12px;color:#888">Branch Code</label><input name="bank_branch" class="input" value="{s.get('bank_branch','')}"></div></div>
</div>
<button type="submit" class="btn btn-green" style="width:100%">💾 Save Settings</button>
</form></div></body></html>'''

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
