"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║   CLICK AI v4 - PART 1 of 3                                                   ║
║   Core Setup | CSS | Data | Home/Idle Page                                    ║
║   Paste Part 2 and Part 3 below this                                          ║
║   By: Deon & Claude | December 2025                                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, jsonify, request, redirect
import json
import os
from datetime import datetime, timedelta
import re
import base64
import uuid

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FILE = "clickai_data.json"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # Or paste your key here

# ═══════════════════════════════════════════════════════════════════════════════
# CHART OF ACCOUNTS - South African Standard
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

NO_VAT_ACCOUNTS = ["6400", "6910", "7100", "7000"]  # Insurance, Fuel, Bank Charges, Wages

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
    {"code": "5000", "name": "Cost of Sales", "vat": True},
    {"code": "6100", "name": "Rent", "vat": True},
    {"code": "6200", "name": "Utilities", "vat": True},
    {"code": "6300", "name": "Telephone", "vat": True},
    {"code": "6400", "name": "Insurance", "vat": False},
    {"code": "6500", "name": "Repairs", "vat": True},
    {"code": "6910", "name": "Fuel", "vat": False},
    {"code": "7000", "name": "Wages", "vat": False},
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
            "documents": {"quotes": [], "invoices": [], "supplier_invoices": []},
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
# CSS STYLES - Dark Mode with Full Header Navigation
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """<style>
:root{--bg:#050508;--card:#0d0d14;--card-hover:#12121c;--border:#1a1a2f;--text:#fff;--muted:#6b7280;--purple:#8b5cf6;--purple-glow:rgba(139,92,246,0.6);--blue:#3b82f6;--green:#10b981;--red:#ef4444;--orange:#f59e0b;--gradient:linear-gradient(135deg,#8b5cf6,#3b82f6)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* STICKY HEADER - ALL OPTIONS */
.header{position:sticky;top:0;z-index:1000;background:rgba(13,13,20,0.95);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:10px 15px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.logo{font-size:18px;font-weight:900;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;text-decoration:none;margin-right:10px}
.nav{display:flex;gap:6px;flex-wrap:wrap;align-items:center;flex:1}
.nav-btn{background:rgba(255,255,255,0.05);border:1px solid var(--border);color:var(--text);padding:8px 12px;border-radius:8px;cursor:pointer;font-size:12px;font-weight:600;text-decoration:none;transition:all 0.2s;white-space:nowrap}
.nav-btn:hover{background:rgba(139,92,246,0.2);border-color:var(--purple)}
.nav-btn.active{background:var(--gradient);border-color:transparent}
.nav-sep{width:1px;height:24px;background:var(--border);margin:0 5px}

/* DROPDOWN */
.dropdown{position:relative}
.dropdown-content{display:none;position:absolute;top:100%;left:0;background:var(--card);border:1px solid var(--border);border-radius:10px;min-width:180px;padding:8px;z-index:1001;margin-top:5px}
.dropdown:hover .dropdown-content{display:block}
.dropdown-item{display:block;padding:10px 14px;color:var(--text);text-decoration:none;border-radius:6px;font-size:13px}
.dropdown-item:hover{background:rgba(139,92,246,0.2)}

/* CONTAINER & CARDS */
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:20px}
.card-title{font-size:18px;font-weight:700;margin-bottom:20px;display:flex;align-items:center;gap:10px}

/* STATS */
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-bottom:20px}
.stat-card{background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);border-radius:12px;padding:20px;text-align:center}
.stat-value{font-size:26px;font-weight:900;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-label{color:var(--muted);font-size:12px;margin-top:5px}

/* TABLES */
.table-container{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 15px;text-align:left;border-bottom:1px solid var(--border)}
th{background:rgba(139,92,246,0.1);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:var(--muted)}
tr:hover{background:rgba(255,255,255,0.02)}

/* BUTTONS */
.btn{background:var(--gradient);color:white;border:none;padding:12px 24px;border-radius:10px;cursor:pointer;font-weight:700;font-size:14px;transition:all 0.2s;text-decoration:none;display:inline-block}
.btn:hover{transform:translateY(-2px);box-shadow:0 5px 20px rgba(139,92,246,0.4)}
.btn-sm{padding:8px 14px;font-size:12px}
.btn-green{background:var(--green)}.btn-red{background:var(--red)}.btn-blue{background:var(--blue)}.btn-orange{background:var(--orange)}
.btn-outline{background:transparent;border:2px solid var(--purple);color:var(--purple)}

/* FORMS */
.form-group{margin-bottom:20px}
.form-label{display:block;font-size:13px;font-weight:600;color:var(--muted);margin-bottom:8px}
.input,select,textarea{width:100%;padding:12px 16px;background:rgba(255,255,255,0.05);border:2px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;transition:all 0.2s}
.input:focus,select:focus,textarea:focus{outline:none;border-color:var(--purple);background:rgba(139,92,246,0.1)}
.form-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px}

/* MODAL */
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:2000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:var(--card);border:1px solid var(--border);border-radius:20px;max-width:600px;width:100%;max-height:90vh;overflow-y:auto;padding:30px}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px}
.modal-title{font-size:20px;font-weight:700}
.modal-close{background:none;border:none;color:var(--muted);font-size:28px;cursor:pointer;line-height:1}

/* BADGES */
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700}
.badge-green{background:rgba(16,185,129,0.2);color:var(--green)}
.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.badge-blue{background:rgba(59,130,246,0.2);color:var(--blue)}
.badge-orange{background:rgba(245,158,11,0.2);color:var(--orange)}
.badge-purple{background:rgba(139,92,246,0.2);color:var(--purple)}

/* SEARCH */
.search-box{position:relative;margin-bottom:20px}
.search-input{width:100%;padding:12px 16px 12px 45px;background:rgba(255,255,255,0.05);border:2px solid var(--border);border-radius:10px;color:var(--text);font-size:14px}
.search-icon{position:absolute;left:15px;top:50%;transform:translateY(-50%);color:var(--muted)}

/* CATEGORY FILTER */
.cat-filter{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;padding-bottom:15px;border-bottom:1px solid var(--border)}
.cat-btn{padding:8px 16px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:20px;color:var(--muted);cursor:pointer;font-size:12px;font-weight:600;transition:all 0.2s}
.cat-btn:hover,.cat-btn.active{background:var(--purple);border-color:var(--purple);color:white}

/* POS */
.pos-grid{display:grid;grid-template-columns:1fr 350px;gap:20px}
.pos-items{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px;max-height:60vh;overflow-y:auto}
.pos-item{background:var(--card-hover);border:1px solid var(--border);border-radius:10px;padding:12px 8px;text-align:center;cursor:pointer;transition:all 0.2s}
.pos-item:hover{border-color:var(--purple);transform:scale(1.02)}
.pos-item-name{font-size:11px;font-weight:600;margin-bottom:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pos-item-price{color:var(--green);font-weight:700;font-size:13px}
.cart{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;display:flex;flex-direction:column;max-height:80vh}
.cart-items{flex:1;overflow-y:auto;margin-bottom:15px}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.cart-total{font-size:24px;font-weight:900;text-align:right;padding:15px 0;border-top:2px solid var(--purple);color:var(--green)}

/* GLOWING LOGO ANIMATION */
@keyframes glow{
    0%,100%{text-shadow:0 0 20px var(--purple-glow),0 0 40px var(--purple-glow),0 0 60px var(--purple-glow)}
    50%{text-shadow:0 0 40px var(--purple-glow),0 0 80px var(--purple-glow),0 0 100px var(--purple-glow)}
}
@keyframes pulse{
    0%,100%{transform:scale(1)}
    50%{transform:scale(1.05)}
}
.glow-logo{
    font-size:80px;
    font-weight:900;
    background:var(--gradient);
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
    animation:glow 2s ease-in-out infinite,pulse 2s ease-in-out infinite;
    cursor:pointer;
    user-select:none;
}
.cheeky-text{
    color:var(--muted);
    font-size:18px;
    margin-top:20px;
    font-style:italic;
}

/* QUICK ACTIONS */
.quick-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.quick-btn{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px 15px;text-align:center;cursor:pointer;transition:all 0.2s;text-decoration:none;color:var(--text)}
.quick-btn:hover{background:var(--card-hover);border-color:var(--purple);transform:translateY(-3px)}
.quick-icon{font-size:28px;margin-bottom:8px}
.quick-label{font-size:13px;font-weight:600}

@media(max-width:768px){.header{display:none}.container{padding:15px}.pos-grid{grid-template-columns:1fr}}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER HTML - Used on ALL pages (direct links, no back button needed)
# ═══════════════════════════════════════════════════════════════════════════════

def get_header(bid, active=""):
    return f'''<div class="header">
    <a href="/{bid}" class="logo">⚡ Click AI</a>
    <div class="nav">
        <a href="/{bid}" class="nav-btn {"active" if active=="home" else ""}">🏠 Home</a>
        <a href="/{bid}/pos" class="nav-btn {"active" if active=="pos" else ""}">💰 POS</a>
        <a href="/{bid}/stock" class="nav-btn {"active" if active=="stock" else ""}">📦 Stock</a>
        <a href="/{bid}/customers" class="nav-btn {"active" if active=="customers" else ""}">👥 Customers</a>
        <a href="/{bid}/suppliers" class="nav-btn {"active" if active=="suppliers" else ""}">🚚 Suppliers</a>
        <a href="/{bid}/expenses" class="nav-btn {"active" if active=="expenses" else ""}">💸 Expenses</a>
        <div class="nav-sep"></div>
        <a href="/{bid}/quotes" class="nav-btn {"active" if active=="quotes" else ""}">📝 Quotes</a>
        <a href="/{bid}/invoices" class="nav-btn {"active" if active=="invoices" else ""}">📃 Invoices</a>
        <div class="nav-sep"></div>
        <div class="dropdown">
            <button class="nav-btn {"active" if active=="reports" else ""}">📊 Reports ▾</button>
            <div class="dropdown-content">
                <a href="/{bid}/report/ledger" class="dropdown-item">📒 General Ledger</a>
                <a href="/{bid}/report/pnl" class="dropdown-item">📈 Profit & Loss</a>
                <a href="/{bid}/report/vat" class="dropdown-item">🏛️ VAT Report</a>
                <a href="/{bid}/report/debtors" class="dropdown-item">💰 Debtors Age Analysis</a>
                <a href="/{bid}/report/creditors" class="dropdown-item">💸 Creditors Age Analysis</a>
            </div>
        </div>
        <a href="/{bid}/settings" class="nav-btn {"active" if active=="settings" else ""}">⚙️</a>
    </div>
</div>'''

# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE - Business Selection (No business selected yet)
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
        <div class="glow-logo">⚡ Click AI</div>
        <div class="cheeky-text">Come on... I can see you want to Click me 😏</div>
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
            <label class="form-label">Anthropic API Key (for AI invoice scanning)</label>
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
# DASHBOARD / IDLE PAGE - Glowing Logo with Stats
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>")
def dashboard(bid):
    if bid in ["api", "favicon.ico"]: return "", 404
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    
    # Mobile redirect
    mobile_check = f'<script>if(/iPhone|iPad|Android/i.test(navigator.userAgent)&&!sessionStorage.getItem("desktop"))location.href="/m/{bid}"</script>'
    
    # Stats
    stock_count = len(b.get("stock", []))
    stock_value = sum(float(s.get("cost", 0) or 0) * int(s.get("qty", 0) or 0) for s in b.get("stock", []))
    cust_count = len(b.get("customers", []))
    debtors = sum(float(c.get("balance", 0) or 0) for c in b.get("customers", []))
    supp_count = len(b.get("suppliers", []))
    creditors = sum(float(s.get("balance", 0) or 0) for s in b.get("suppliers", []))
    
    # Recent transactions
    ledger = b.get("ledger", [])[-10:]
    ledger_rows = ""
    for entry in reversed(ledger):
        ledger_rows += f'<tr><td>{entry.get("date", "")[:10]}</td><td>{entry.get("ref", "")}</td><td>{entry.get("desc", "")[:30]}</td><td style="color:var(--green)">R {float(entry.get("debit", 0)):,.2f}</td><td style="color:var(--red)">R {float(entry.get("credit", 0)):,.2f}</td></tr>'
    if not ledger_rows:
        ledger_rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:30px">No transactions yet</td></tr>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{name} - Click AI</title>{CSS}{mobile_check}</head><body>
{get_header(bid, "home")}
<div class="container">
    <!-- Glowing Logo Section -->
    <div style="text-align:center;padding:30px 0">
        <div class="glow-logo" onclick="document.getElementById('actions').scrollIntoView({{behavior:'smooth'}})">⚡</div>
        <div style="font-size:24px;font-weight:700;margin-top:10px">{name}</div>
        <div class="cheeky-text">Come on... I can see you want to Click me 😏</div>
    </div>
    
    <!-- Stats -->
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-value">{stock_count}</div><div class="stat-label">Stock Items</div></div>
        <div class="stat-card"><div class="stat-value">R {stock_value:,.0f}</div><div class="stat-label">Stock Value</div></div>
        <div class="stat-card"><div class="stat-value">R {debtors:,.0f}</div><div class="stat-label">Debtors ({cust_count})</div></div>
        <div class="stat-card"><div class="stat-value">R {creditors:,.0f}</div><div class="stat-label">Creditors ({supp_count})</div></div>
    </div>
    
    <!-- Quick Actions -->
    <div class="card" id="actions">
        <div class="card-title">⚡ Quick Actions</div>
        <div class="quick-actions">
            <a href="/{bid}/pos" class="quick-btn"><div class="quick-icon">💰</div><div class="quick-label">New Sale</div></a>
            <a href="/{bid}/quotes/new" class="quick-btn"><div class="quick-icon">📝</div><div class="quick-label">New Quote</div></a>
            <a href="/{bid}/invoices/new" class="quick-btn"><div class="quick-icon">📃</div><div class="quick-label">New Invoice</div></a>
            <a href="/{bid}/stock" class="quick-btn"><div class="quick-icon">📦</div><div class="quick-label">Stock</div></a>
            <a href="/{bid}/expenses" class="quick-btn"><div class="quick-icon">💸</div><div class="quick-label">Expenses</div></a>
            <a href="/m/{bid}" class="quick-btn"><div class="quick-icon">📱</div><div class="quick-label">Mobile Scan</div></a>
        </div>
    </div>
    
    <!-- Recent Transactions -->
    <div class="card">
        <div class="card-title">📒 Recent Transactions</div>
        <div class="table-container"><table><thead><tr><th>Date</th><th>Ref</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{ledger_rows}</tbody></table></div>
    </div>
</div></body></html>'''


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PART 1 - Paste Part 2 below this line
# ═══════════════════════════════════════════════════════════════════════════════
