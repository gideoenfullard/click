"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║   CLICK AI v3 - PART 1 of 2                                                   ║
║   Paste Part 1 first, then Part 2 below it                                    ║
║   By: Deon & Claude | December 2025                                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, jsonify, request, redirect
import json
import os
from datetime import datetime
import re
import base64
import uuid

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FILE = "clickai_data.json"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ═══════════════════════════════════════════════════════════════════════════════
# CHART OF ACCOUNTS
# ═══════════════════════════════════════════════════════════════════════════════

ACCOUNTS = {
    "1000": ("Bank", "Asset"),
    "1100": ("Petty Cash", "Asset"),
    "1200": ("Debtors Control", "Asset"),
    "1300": ("Stock / Inventory", "Asset"),
    "2000": ("Creditors Control", "Liability"),
    "2100": ("VAT Input", "Liability"),
    "2200": ("VAT Output", "Liability"),
    "3000": ("Capital", "Equity"),
    "3100": ("Retained Earnings", "Equity"),
    "4000": ("Sales", "Income"),
    "4100": ("Other Income", "Income"),
    "5000": ("Cost of Sales", "Expense"),
    "6100": ("Rent", "Expense"),
    "6200": ("Utilities", "Expense"),
    "6300": ("Telephone", "Expense"),
    "6400": ("Insurance", "Expense"),
    "6500": ("Repairs & Maintenance", "Expense"),
    "6600": ("Office Supplies", "Expense"),
    "6700": ("Marketing", "Expense"),
    "6800": ("Professional Fees", "Expense"),
    "6900": ("Travel", "Expense"),
    "6910": ("Fuel", "Expense"),
    "6999": ("Other Expenses", "Expense"),
    "7000": ("Wages & Salaries", "Expense"),
    "7100": ("Bank Charges", "Expense"),
    "8000": ("Depreciation", "Expense"),
}

NO_VAT_ACCOUNTS = ["6400", "6910", "7100"]

DEFAULT_SETTINGS = {
    "company_name": "", "trading_as": "", "reg_number": "", "vat_number": "",
    "address": "", "phone": "", "email": "", "logo": "",
    "bank_name": "", "bank_account": "", "bank_branch": "", "bank_type": "Cheque",
    "vat_rate": 15, "financial_year_end": 2, "currency": "R",
    "invoice_prefix": "INV", "quote_prefix": "QT",
    "invoice_terms": "Payment due within 30 days", "quote_validity": "Valid for 14 days",
}

DEFAULT_CATEGORIES = ["General", "Bearings", "Bolts", "Nuts", "Washers", "Screws", "Hardware", "Tools", "Safety", "Other"]

DEFAULT_EXPENSE_CATS = [
    {"code": "6100", "name": "Rent", "vat": True},
    {"code": "6200", "name": "Utilities", "vat": True},
    {"code": "6300", "name": "Telephone", "vat": True},
    {"code": "6400", "name": "Insurance", "vat": False},
    {"code": "6500", "name": "Repairs", "vat": True},
    {"code": "6910", "name": "Fuel", "vat": False},
    {"code": "7100", "name": "Bank Charges", "vat": False},
    {"code": "6999", "name": "Other", "vat": True},
]

# ═══════════════════════════════════════════════════════════════════════════════
# DATA MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

DATA = {"businesses": {}, "api_key": ""}

def load_data():
    global DATA
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                DATA = json.load(f)
    except:
        DATA = {"businesses": {}, "api_key": ""}

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(DATA, f, indent=2)
    except Exception as e:
        print(f"Save error: {e}")

def biz(bid):
    if bid not in DATA["businesses"]:
        DATA["businesses"][bid] = {
            "name": bid,
            "settings": DEFAULT_SETTINGS.copy(),
            "stock": [],
            "customers": [],
            "suppliers": [],
            "ledger": [],
            "documents": {"quotes": [], "invoices": [], "supplier_invoices": [], "delivery_notes": []},
            "stock_categories": DEFAULT_CATEGORIES.copy(),
            "expense_categories": DEFAULT_EXPENSE_CATS.copy(),
        }
        save_data()
    return DATA["businesses"][bid]

def gs(b, key):
    return b.get("settings", {}).get(key, DEFAULT_SETTINGS.get(key, ""))

def next_doc_num(b, doc_type, prefix_key):
    docs = b.get("documents", {}).get(doc_type, [])
    prefix = gs(b, prefix_key)
    num = len(docs) + 1
    return f"{prefix}{num:04d}"

load_data()

# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLES
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """<style>
:root{--bg:#050508;--card:#0d0d14;--card-hover:#12121c;--border:#1a1a2f;--text:#fff;--muted:#6b7280;--purple:#8b5cf6;--blue:#3b82f6;--green:#10b981;--red:#ef4444;--orange:#f59e0b;--gradient:linear-gradient(135deg,#8b5cf6,#3b82f6)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{position:sticky;top:0;z-index:1000;background:linear-gradient(135deg,rgba(139,92,246,0.15),rgba(59,130,246,0.15));backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:12px 20px;display:flex;align-items:center;justify-content:space-between;gap:15px}
.logo{font-size:20px;font-weight:900;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;white-space:nowrap}
.nav{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.nav-btn{background:rgba(255,255,255,0.05);border:1px solid var(--border);color:var(--text);padding:8px 14px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;text-decoration:none;transition:all 0.2s;display:flex;align-items:center;gap:6px}
.nav-btn:hover{background:rgba(139,92,246,0.2);border-color:var(--purple)}
.nav-btn.active{background:var(--gradient);border-color:transparent}
.dropdown{position:relative}
.dropdown-content{display:none;position:absolute;top:100%;left:0;background:var(--card);border:1px solid var(--border);border-radius:10px;min-width:180px;padding:8px;z-index:1001;margin-top:5px}
.dropdown:hover .dropdown-content{display:block}
.dropdown-item{display:block;padding:10px 14px;color:var(--text);text-decoration:none;border-radius:6px;font-size:13px}
.dropdown-item:hover{background:rgba(139,92,246,0.2)}
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:20px}
.card-title{font-size:18px;font-weight:700;margin-bottom:20px;display:flex;align-items:center;gap:10px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px}
.stat-card{background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);border-radius:12px;padding:20px;text-align:center}
.stat-value{font-size:28px;font-weight:900;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-label{color:var(--muted);font-size:13px;margin-top:5px}
.table-container{overflow-x:auto;margin:-10px;padding:10px}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 15px;text-align:left;border-bottom:1px solid var(--border)}
th{background:rgba(139,92,246,0.1);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;color:var(--muted)}
tr:hover{background:rgba(255,255,255,0.02)}
.btn{background:var(--gradient);color:white;border:none;padding:12px 24px;border-radius:10px;cursor:pointer;font-weight:700;font-size:14px;transition:all 0.2s}
.btn:hover{transform:translateY(-2px);box-shadow:0 5px 20px rgba(139,92,246,0.4)}
.btn-sm{padding:8px 16px;font-size:12px}
.btn-green{background:var(--green)}.btn-red{background:var(--red)}.btn-blue{background:var(--blue)}
.btn-outline{background:transparent;border:2px solid var(--purple);color:var(--purple)}
.form-group{margin-bottom:20px}
.form-label{display:block;font-size:13px;font-weight:600;color:var(--muted);margin-bottom:8px}
.input,select,textarea{width:100%;padding:12px 16px;background:rgba(255,255,255,0.05);border:2px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;transition:all 0.2s}
.input:focus,select:focus,textarea:focus{outline:none;border-color:var(--purple);background:rgba(139,92,246,0.1)}
.form-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px}
.quick-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
.quick-btn{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px 15px;text-align:center;cursor:pointer;transition:all 0.2s;text-decoration:none;color:var(--text)}
.quick-btn:hover{background:var(--card-hover);border-color:var(--purple);transform:translateY(-3px)}
.quick-icon{font-size:28px;margin-bottom:8px}
.quick-label{font-size:13px;font-weight:600}
.cat-filter{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;padding-bottom:15px;border-bottom:1px solid var(--border)}
.cat-btn{padding:8px 16px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:20px;color:var(--muted);cursor:pointer;font-size:12px;font-weight:600;transition:all 0.2s}
.cat-btn:hover,.cat-btn.active{background:var(--purple);border-color:var(--purple);color:white}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:2000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:var(--card);border:1px solid var(--border);border-radius:20px;max-width:600px;width:100%;max-height:90vh;overflow-y:auto;padding:30px}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px}
.modal-title{font-size:20px;font-weight:700}
.modal-close{background:none;border:none;color:var(--muted);font-size:24px;cursor:pointer}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700}
.badge-green{background:rgba(16,185,129,0.2);color:var(--green)}
.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.badge-blue{background:rgba(59,130,246,0.2);color:var(--blue)}
.badge-orange{background:rgba(245,158,11,0.2);color:var(--orange)}
.search-box{position:relative;margin-bottom:20px}
.search-input{width:100%;padding:12px 16px 12px 45px;background:rgba(255,255,255,0.05);border:2px solid var(--border);border-radius:10px;color:var(--text);font-size:14px}
.search-icon{position:absolute;left:15px;top:50%;transform:translateY(-50%);color:var(--muted)}
.pos-grid{display:grid;grid-template-columns:1fr 350px;gap:20px}
.pos-items{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px;max-height:60vh;overflow-y:auto;padding:5px}
.pos-item{background:var(--card-hover);border:1px solid var(--border);border-radius:10px;padding:15px 10px;text-align:center;cursor:pointer;transition:all 0.2s}
.pos-item:hover{border-color:var(--purple);transform:scale(1.02)}
.pos-item-name{font-size:12px;font-weight:600;margin-bottom:5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pos-item-price{color:var(--green);font-weight:700}
.cart{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;display:flex;flex-direction:column;height:fit-content;max-height:80vh}
.cart-items{flex:1;overflow-y:auto;margin-bottom:15px}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.cart-total{font-size:24px;font-weight:900;text-align:right;padding:15px 0;border-top:2px solid var(--purple);color:var(--green)}
@media(max-width:768px){.header{padding:10px 15px}.nav{display:none}.pos-grid{grid-template-columns:1fr}.container{padding:15px}}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    businesses = DATA.get("businesses", {})
    cards = ""
    for bid, b in businesses.items():
        name = gs(b, "company_name") or b.get("name", bid)
        stock_count = len(b.get("stock", []))
        cust_count = len(b.get("customers", []))
        cards += f'''<a href="/{bid}" class="quick-btn">
            <div class="quick-icon">🏢</div>
            <div class="quick-label">{name}</div>
            <div style="color:var(--muted);font-size:11px;margin-top:5px">{stock_count} stock • {cust_count} customers</div>
        </a>'''
    if not cards:
        cards = '<div style="text-align:center;padding:40px;color:var(--muted)">No businesses yet. Create one below!</div>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}</head><body>
<div class="container" style="padding-top:40px">
    <div style="text-align:center;margin-bottom:40px">
        <div class="logo" style="font-size:42px">⚡ Click AI</div>
        <div style="color:var(--muted);margin-top:10px">Fully Automated Accounting System</div>
    </div>
    <div class="card">
        <div class="card-title">🏢 Your Businesses</div>
        <div class="quick-actions" style="margin-bottom:20px">{cards}</div>
        <div style="border-top:1px solid var(--border);padding-top:20px;margin-top:10px">
            <div style="display:flex;gap:10px">
                <input type="text" id="newBiz" class="input" placeholder="New business name..." style="flex:1">
                <button class="btn" onclick="createBiz()">+ Create</button>
            </div>
        </div>
    </div>
    <div class="card">
        <div class="card-title">⚙️ API Settings</div>
        <div class="form-group">
            <label class="form-label">Anthropic API Key (for AI features)</label>
            <input type="password" id="apiKey" class="input" placeholder="sk-ant-..." value="{DATA.get('api_key', '')}">
        </div>
        <button class="btn btn-outline" onclick="saveApiKey()">Save API Key</button>
    </div>
</div>
<script>
function createBiz(){{var name=document.getElementById('newBiz').value.trim();if(!name)return alert('Enter a business name');fetch('/api/business',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name}})}}).then(r=>r.json()).then(d=>{{if(d.success)location.href='/'+d.id;else alert(d.error||'Error')}})}}
function saveApiKey(){{var key=document.getElementById('apiKey').value;fetch('/api/settings/apikey',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{key}})}}).then(r=>r.json()).then(d=>{{if(d.success)alert('API Key saved!')}})}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# MOBILE PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/m/<bid>")
def mobile(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    expense_cats = json.dumps(b.get("expense_categories", DEFAULT_EXPENSE_CATS))
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><title>Click AI Mobile</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:#050508;color:#fff;min-height:100vh;display:flex;flex-direction:column}}
.top{{padding:20px;text-align:center;border-bottom:1px solid #1a1a2f}}.logo{{font-size:24px;font-weight:900;background:linear-gradient(135deg,#8b5cf6,#3b82f6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}.biz-name{{color:#6b7280;font-size:14px;margin-top:5px}}
.main{{flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:25px;padding:30px}}
.big-btn{{width:80%;max-width:280px;aspect-ratio:1;border-radius:24px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px;cursor:pointer;font-weight:700;font-size:20px;transition:all 0.3s}}
.stock{{background:rgba(139,92,246,0.15);border:3px solid rgba(139,92,246,0.5);color:#8b5cf6}}.expense{{background:rgba(239,68,68,0.15);border:3px solid rgba(239,68,68,0.5);color:#ef4444}}
.big-btn:active{{transform:scale(0.95)}}.icon{{font-size:64px}}input[type=file]{{display:none}}
.overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.95);z-index:100;flex-direction:column;align-items:center;justify-content:center;padding:30px}}.overlay.show{{display:flex}}
.spinner{{width:60px;height:60px;border:4px solid #333;border-top-color:#8b5cf6;border-radius:50%;animation:spin 1s linear infinite}}@keyframes spin{{to{{transform:rotate(360deg)}}}}
.result-box{{background:#0d0d14;border:1px solid #1a1a2f;border-radius:16px;padding:20px;width:100%;max-width:350px}}.result-row{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #1a1a2f}}
.desktop-link{{position:fixed;bottom:20px;color:#6b7280;font-size:12px;text-decoration:none}}
</style></head><body>
<div class="top"><div class="logo">⚡ Click AI</div><div class="biz-name">{name}</div></div>
<div class="main">
    <div class="big-btn stock" onclick="capture('stock')"><div class="icon">📦</div><div>STOCK</div><div style="font-size:12px;font-weight:400;color:#6b7280">Supplier Invoice</div></div>
    <div class="big-btn expense" onclick="capture('expense')"><div class="icon">💸</div><div>EXPENSE</div><div style="font-size:12px;font-weight:400;color:#6b7280">Receipt / Slip</div></div>
</div>
<input type="file" id="camera" accept="image/*" capture="environment" onchange="process(this)">
<div class="overlay" id="loading"><div class="spinner"></div><div style="margin-top:20px;color:#6b7280">Processing...</div></div>
<div class="overlay" id="result">
    <div style="font-size:48px;margin-bottom:15px" id="resultIcon">✅</div>
    <div style="font-size:24px;font-weight:700;margin-bottom:20px" id="resultTitle">Posted!</div>
    <div class="result-box" id="resultBox"></div>
    <button onclick="reset()" style="margin-top:25px;background:linear-gradient(135deg,#8b5cf6,#3b82f6);color:#fff;border:none;padding:15px 50px;border-radius:30px;font-size:16px;font-weight:700;cursor:pointer">Done</button>
</div>
<a href="/{bid}?desktop=1" class="desktop-link">Switch to Desktop →</a>
<script>
var mode='stock';var expenseCats={expense_cats};
function capture(m){{mode=m;document.getElementById('camera').click()}}
function process(input){{if(!input.files[0])return;document.getElementById('loading').classList.add('show');var reader=new FileReader();reader.onload=function(e){{var base64=e.target.result.split(',')[1];fetch('/api/{bid}/mobile/'+mode,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{image:base64}})}}).then(r=>r.json()).then(d=>{{document.getElementById('loading').classList.remove('show');if(d.success)showResult(d);else alert(d.error||'Error')}}).catch(err=>{{document.getElementById('loading').classList.remove('show');alert('Error: '+err)}})}};reader.readAsDataURL(input.files[0])}}
function showResult(d){{document.getElementById('resultIcon').textContent=mode==='stock'?'📦':'💸';document.getElementById('resultTitle').textContent=(d.doc_id||'Item')+' Posted!';var html='<div class="result-row"><span>Supplier</span><span>'+(d.supplier||'-')+'</span></div>';html+='<div class="result-row"><span>Amount (incl)</span><span>R '+(d.amount_incl||0).toFixed(2)+'</span></div>';if(d.vat>0)html+='<div class="result-row"><span>VAT</span><span>R '+d.vat.toFixed(2)+'</span></div>';document.getElementById('resultBox').innerHTML=html;document.getElementById('result').classList.add('show')}}
function reset(){{document.getElementById('result').classList.remove('show');document.getElementById('camera').value=''}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>")
def dashboard(bid):
    if bid in ["api", "favicon.ico"]:
        return "", 404
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    mobile_redirect = "" if request.args.get("desktop") else f'<script>if(/iPhone|iPad|Android/i.test(navigator.userAgent)&&!sessionStorage.getItem("desktop"))location.href="/m/{bid}"</script>'
    
    stock_count = len(b.get("stock", []))
    stock_value = sum(float(s.get("cost", 0) or 0) * int(s.get("qty", 0) or 0) for s in b.get("stock", []))
    cust_count = len(b.get("customers", []))
    debtors = sum(float(c.get("balance", 0) or 0) for c in b.get("customers", []))
    supp_count = len(b.get("suppliers", []))
    creditors = sum(float(s.get("balance", 0) or 0) for s in b.get("suppliers", []))
    
    ledger = b.get("ledger", [])[-10:]
    ledger_rows = ""
    for entry in reversed(ledger):
        ledger_rows += f'<tr><td>{entry.get("date", "")[:10]}</td><td>{entry.get("ref", "")}</td><td>{entry.get("desc", "")}</td><td style="color:var(--green)">R {float(entry.get("debit", 0)):,.2f}</td><td style="color:var(--red)">R {float(entry.get("credit", 0)):,.2f}</td></tr>'
    if not ledger_rows:
        ledger_rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:30px">No transactions yet</td></tr>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{name} - Click AI</title>{CSS}{mobile_redirect}</head><body>
<div class="header">
    <a href="/" class="logo" style="text-decoration:none">⚡ Click AI</a>
    <div class="nav">
        <a href="/{bid}" class="nav-btn active">🏠 Home</a>
        <a href="/{bid}/pos" class="nav-btn">💰 POS</a>
        <a href="/{bid}/stock" class="nav-btn">📦 Stock</a>
        <a href="/{bid}/customers" class="nav-btn">👥 Customers</a>
        <a href="/{bid}/suppliers" class="nav-btn">🚚 Suppliers</a>
        <a href="/{bid}/expenses" class="nav-btn">💸 Expenses</a>
        <div class="dropdown"><button class="nav-btn">📄 Documents ▾</button><div class="dropdown-content">
            <a href="/{bid}/quotes" class="dropdown-item">📝 Quotes</a>
            <a href="/{bid}/invoices" class="dropdown-item">📃 Invoices</a>
            <a href="/{bid}/supplier-invoices" class="dropdown-item">📥 Supplier Invoices</a>
        </div></div>
        <div class="dropdown"><button class="nav-btn">📊 Reports ▾</button><div class="dropdown-content">
            <a href="/{bid}/report/ledger" class="dropdown-item">📒 Ledger</a>
            <a href="/{bid}/report/pnl" class="dropdown-item">📈 Profit & Loss</a>
            <a href="/{bid}/report/vat" class="dropdown-item">🏛️ VAT Report</a>
        </div></div>
        <a href="/{bid}/settings" class="nav-btn">⚙️</a>
    </div>
</div>
<div class="container">
    <h1 style="font-size:28px;margin-bottom:25px">{name}</h1>
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-value">{stock_count}</div><div class="stat-label">Stock Items</div></div>
        <div class="stat-card"><div class="stat-value">R {stock_value:,.0f}</div><div class="stat-label">Stock Value</div></div>
        <div class="stat-card"><div class="stat-value">R {debtors:,.0f}</div><div class="stat-label">Debtors ({cust_count})</div></div>
        <div class="stat-card"><div class="stat-value">R {creditors:,.0f}</div><div class="stat-label">Creditors ({supp_count})</div></div>
    </div>
    <div class="card">
        <div class="card-title">⚡ Quick Actions</div>
        <div class="quick-actions">
            <a href="/{bid}/pos" class="quick-btn"><div class="quick-icon">💰</div><div class="quick-label">New Sale</div></a>
            <a href="/{bid}/quotes/new" class="quick-btn"><div class="quick-icon">📝</div><div class="quick-label">New Quote</div></a>
            <a href="/{bid}/invoices/new" class="quick-btn"><div class="quick-icon">📃</div><div class="quick-label">New Invoice</div></a>
            <a href="/{bid}/stock" class="quick-btn"><div class="quick-icon">📦</div><div class="quick-label">Stock</div></a>
            <a href="/{bid}/expenses" class="quick-btn"><div class="quick-icon">💸</div><div class="quick-label">Expenses</div></a>
            <a href="/m/{bid}" class="quick-btn"><div class="quick-icon">📱</div><div class="quick-label">Mobile</div></a>
        </div>
    </div>
    <div class="card">
        <div class="card-title">📒 Recent Transactions</div>
        <div class="table-container"><table><thead><tr><th>Date</th><th>Ref</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{ledger_rows}</tbody></table></div>
    </div>
</div></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# POS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/pos")
def pos_page(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    vat_rate = gs(b, "vat_rate") or 15
    currency = gs(b, "currency") or "R"
    categories = b.get("stock_categories", DEFAULT_CATEGORIES)
    stock = b.get("stock", [])
    
    cat_btns = '<button class="cat-btn active" onclick="filterCat(\'All\')">All</button>'
    for cat in categories:
        if cat != "All":
            cat_btns += f'<button class="cat-btn" onclick="filterCat(\'{cat}\')">{cat}</button>'
    
    stock_json = json.dumps([{"code": s.get("code", ""), "desc": s.get("description", ""), "cat": s.get("category", "General"), "price": float(s.get("price", 0) or 0), "qty": int(s.get("qty", 0) or 0)} for s in stock])
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS - {name}</title>{CSS}</head><body>
<div class="header">
    <a href="/" class="logo" style="text-decoration:none">⚡ Click AI</a>
    <div class="nav">
        <a href="/{bid}" class="nav-btn">🏠 Home</a>
        <a href="/{bid}/pos" class="nav-btn active">💰 POS</a>
        <a href="/{bid}/stock" class="nav-btn">📦 Stock</a>
        <a href="/{bid}/customers" class="nav-btn">👥 Customers</a>
        <a href="/{bid}/suppliers" class="nav-btn">🚚 Suppliers</a>
    </div>
</div>
<div class="container">
    <div class="pos-grid">
        <div>
            <div class="card">
                <div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" id="search" placeholder="Search stock..." oninput="filterStock()"></div>
                <div class="cat-filter" id="catFilter">{cat_btns}</div>
                <div class="pos-items" id="posItems"></div>
            </div>
        </div>
        <div class="cart">
            <div class="card-title">🛒 Cart</div>
            <div class="cart-items" id="cartItems"><div style="text-align:center;color:var(--muted);padding:40px">No items in cart</div></div>
            <div class="cart-total"><div style="font-size:14px;color:var(--muted)">Total (incl VAT)</div><div id="cartTotal">{currency} 0.00</div></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:15px">
                <button class="btn btn-green" onclick="checkout('cash')">💵 Cash</button>
                <button class="btn btn-blue" onclick="checkout('card')">💳 Card</button>
            </div>
            <button class="btn btn-outline" style="width:100%;margin-top:10px" onclick="clearCart()">Clear</button>
        </div>
    </div>
</div>
<script>
var stock={stock_json};var cart=[];var currentCat='All';var vatRate={vat_rate};var currency='{currency}';
function renderStock(){{var search=document.getElementById('search').value.toLowerCase();var html='';stock.forEach(function(item,idx){{if(currentCat!=='All'&&item.cat!==currentCat)return;if(search&&!item.desc.toLowerCase().includes(search)&&!item.code.toLowerCase().includes(search))return;if(item.qty<=0)return;html+='<div class="pos-item" onclick="addToCart('+idx+')"><div class="pos-item-name">'+item.desc+'</div><div class="pos-item-price">'+currency+' '+item.price.toFixed(2)+'</div><div style="color:var(--muted);font-size:10px">'+item.qty+' in stock</div></div>'}});document.getElementById('posItems').innerHTML=html||'<div style="text-align:center;padding:40px;color:var(--muted)">No items found</div>'}}
function filterCat(cat){{currentCat=cat;document.querySelectorAll('.cat-btn').forEach(function(btn){{btn.classList.remove('active');if(btn.textContent===cat)btn.classList.add('active')}});renderStock()}}
function filterStock(){{renderStock()}}
function addToCart(idx){{var item=stock[idx];var existing=cart.find(function(c){{return c.code===item.code}});if(existing){{if(existing.qty>=item.qty)return alert('Not enough stock');existing.qty++}}else{{cart.push({{code:item.code,desc:item.desc,price:item.price,qty:1,stockQty:item.qty}})}}renderCart()}}
function removeFromCart(code){{cart=cart.filter(function(c){{return c.code!==code}});renderCart()}}
function changeQty(code,delta){{var item=cart.find(function(c){{return c.code===code}});if(!item)return;item.qty+=delta;if(item.qty<=0)removeFromCart(code);else if(item.qty>item.stockQty)item.qty=item.stockQty;renderCart()}}
function renderCart(){{if(cart.length===0){{document.getElementById('cartItems').innerHTML='<div style="text-align:center;color:var(--muted);padding:40px">No items in cart</div>';document.getElementById('cartTotal').textContent=currency+' 0.00';return}}var html='';var total=0;cart.forEach(function(item){{var lineTotal=item.price*item.qty;total+=lineTotal;html+='<div class="cart-item"><div><div style="font-weight:600">'+item.desc+'</div><div style="color:var(--muted);font-size:12px">'+currency+' '+item.price.toFixed(2)+' × '+item.qty+'</div></div><div style="display:flex;align-items:center;gap:8px"><button onclick="changeQty(\''+item.code+'\',-1)" style="background:var(--red);color:#fff;border:none;width:24px;height:24px;border-radius:4px;cursor:pointer">-</button><span>'+item.qty+'</span><button onclick="changeQty(\''+item.code+'\',1)" style="background:var(--green);color:#fff;border:none;width:24px;height:24px;border-radius:4px;cursor:pointer">+</button></div></div>'}});document.getElementById('cartItems').innerHTML=html;document.getElementById('cartTotal').textContent=currency+' '+total.toFixed(2)}}
function clearCart(){{cart=[];renderCart()}}
function checkout(method){{if(cart.length===0)return alert('Cart is empty');fetch('/api/{bid}/pos',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{items:cart,method:method}})}}).then(function(r){{return r.json()}}).then(function(d){{if(d.success){{alert('Sale complete! Ref: '+d.ref);cart=[];location.reload()}}else{{alert(d.error||'Error')}}}})}}
renderStock();
</script></body></html>'''


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PART 1 - PASTE PART 2 BELOW THIS LINE
# ═══════════════════════════════════════════════════════════════════════════════
