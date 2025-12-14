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
# ═══════════════════════════════════════════════════════════════════════════════
# CLICK AI v4 - PART 2 of 3
# Desktop Pages: POS, Stock, Customers, Suppliers, Expenses, Quotes, Invoices, Settings
# Paste below Part 1
# ═══════════════════════════════════════════════════════════════════════════════

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
    customers = b.get("customers", [])
    
    cat_btns = '<button class="cat-btn active" onclick="filterCat(\'All\')">All</button>'
    for cat in categories:
        if cat != "All": cat_btns += f'<button class="cat-btn" onclick="filterCat(\'{cat}\')">{cat}</button>'
    
    stock_json = json.dumps([{"code": s.get("code", ""), "desc": s.get("description", ""), "cat": s.get("category", "General"), "price": float(s.get("price", 0) or 0), "qty": int(s.get("qty", 0) or 0)} for s in stock])
    cust_json = json.dumps([{"code": c.get("code", ""), "name": c.get("name", "")} for c in customers])
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS - {name}</title>{CSS}</head><body>
{get_header(bid, "pos")}
<div class="container">
    <div class="pos-grid">
        <div>
            <div class="card">
                <div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" id="search" placeholder="Search stock..." oninput="filterStock()"></div>
                <div class="cat-filter">{cat_btns}</div>
                <div class="pos-items" id="posItems"></div>
            </div>
        </div>
        <div class="cart">
            <div class="card-title">🛒 Cart</div>
            <div style="margin-bottom:15px">
                <select class="input" id="custSelect" style="font-size:13px">
                    <option value="">-- Walk-in Customer --</option>
                </select>
            </div>
            <div class="cart-items" id="cartItems"><div style="text-align:center;color:var(--muted);padding:40px">Empty cart</div></div>
            <div class="cart-total"><div style="font-size:12px;color:var(--muted)">Total (incl VAT)</div><div id="cartTotal">{currency} 0.00</div></div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:15px">
                <button class="btn btn-green" onclick="checkout('cash')">💵 Cash</button>
                <button class="btn btn-blue" onclick="checkout('card')">💳 Card</button>
            </div>
            <button class="btn btn-outline" style="width:100%;margin-top:10px" onclick="clearCart()">Clear Cart</button>
        </div>
    </div>
</div>
<script>
var stock={stock_json};var customers={cust_json};var cart=[];var currentCat='All';var currency='{currency}';
customers.forEach(c=>{{var opt=document.createElement('option');opt.value=c.code;opt.textContent=c.name;document.getElementById('custSelect').appendChild(opt)}});
function renderStock(){{var search=document.getElementById('search').value.toLowerCase();var html='';stock.forEach(function(item,idx){{if(currentCat!=='All'&&item.cat!==currentCat)return;if(search&&!item.desc.toLowerCase().includes(search)&&!item.code.toLowerCase().includes(search))return;if(item.qty<=0)return;html+='<div class="pos-item" onclick="addToCart('+idx+')"><div class="pos-item-name">'+item.desc+'</div><div class="pos-item-price">'+currency+' '+item.price.toFixed(2)+'</div><div style="color:var(--muted);font-size:10px">'+item.qty+' avail</div></div>'}});document.getElementById('posItems').innerHTML=html||'<div style="text-align:center;padding:40px;color:var(--muted)">No items</div>'}}
function filterCat(cat){{currentCat=cat;document.querySelectorAll('.cat-btn').forEach(btn=>{{btn.classList.remove('active');if(btn.textContent===cat)btn.classList.add('active')}});renderStock()}}
function filterStock(){{renderStock()}}
function addToCart(idx){{var item=stock[idx];var existing=cart.find(c=>c.code===item.code);if(existing){{if(existing.qty>=item.qty)return alert('Not enough stock');existing.qty++}}else{{cart.push({{code:item.code,desc:item.desc,price:item.price,qty:1,stockQty:item.qty}})}}renderCart()}}
function changeQty(code,delta){{var item=cart.find(c=>c.code===code);if(!item)return;item.qty+=delta;if(item.qty<=0)cart=cart.filter(c=>c.code!==code);else if(item.qty>item.stockQty)item.qty=item.stockQty;renderCart()}}
function renderCart(){{if(cart.length===0){{document.getElementById('cartItems').innerHTML='<div style="text-align:center;color:var(--muted);padding:40px">Empty cart</div>';document.getElementById('cartTotal').textContent=currency+' 0.00';return}}var html='';var total=0;cart.forEach(item=>{{var lineTotal=item.price*item.qty;total+=lineTotal;html+='<div class="cart-item"><div><div style="font-weight:600;font-size:13px">'+item.desc+'</div><div style="color:var(--muted);font-size:11px">'+currency+' '+item.price.toFixed(2)+' × '+item.qty+'</div></div><div style="display:flex;align-items:center;gap:6px"><button onclick="changeQty(\''+item.code+'\',-1)" style="background:var(--red);color:#fff;border:none;width:22px;height:22px;border-radius:4px;cursor:pointer;font-weight:700">-</button><span style="font-size:13px">'+item.qty+'</span><button onclick="changeQty(\''+item.code+'\',1)" style="background:var(--green);color:#fff;border:none;width:22px;height:22px;border-radius:4px;cursor:pointer;font-weight:700">+</button></div></div>'}});document.getElementById('cartItems').innerHTML=html;document.getElementById('cartTotal').textContent=currency+' '+total.toFixed(2)}}
function clearCart(){{cart=[];renderCart()}}
function checkout(method){{if(cart.length===0)return alert('Cart is empty');var custCode=document.getElementById('custSelect').value;fetch('/api/{bid}/pos',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{items:cart,method:method,customer:custCode}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert('Sale complete! Ref: '+d.ref);location.reload()}}else alert(d.error||'Error')}})}}
renderStock();
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# STOCK PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/stock")
def stock_page(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    stock = b.get("stock", [])
    categories = b.get("stock_categories", DEFAULT_CATEGORIES)
    
    cat_btns = '<button class="cat-btn active" onclick="filterCat(\'All\')">All</button>'
    for cat in categories:
        if cat != "All": cat_btns += f'<button class="cat-btn" onclick="filterCat(\'{cat}\')">{cat}</button>'
    
    rows = ""
    for idx, s in enumerate(stock):
        qty = int(s.get("qty", 0) or 0)
        qty_class = "badge-red" if qty <= 0 else "badge-orange" if qty < 5 else "badge-green"
        rows += f'<tr data-cat="{s.get("category", "General")}"><td>{s.get("code", "")}</td><td>{s.get("description", "")}</td><td><span class="badge badge-blue">{s.get("category", "General")}</span></td><td><span class="badge {qty_class}">{qty}</span></td><td>R {float(s.get("cost", 0) or 0):,.2f}</td><td>R {float(s.get("price", 0) or 0):,.2f}</td><td><button class="btn btn-sm btn-outline" onclick="editStock({idx})">Edit</button> <button class="btn btn-sm btn-red" onclick="deleteStock({idx})">×</button></td></tr>'
    if not rows: rows = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:40px">No stock items</td></tr>'
    cat_options = "".join([f'<option value="{c}">{c}</option>' for c in categories])
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stock - {name}</title>{CSS}</head><body>
{get_header(bid, "stock")}
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
        <h1 style="font-size:24px">📦 Stock</h1>
        <button class="btn" onclick="showAddModal()">+ Add Stock</button>
    </div>
    <div class="card">
        <div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" id="search" placeholder="Search..." oninput="filterTable()"></div>
        <div class="cat-filter">{cat_btns}</div>
        <div class="table-container"><table id="stockTable"><thead><tr><th>Code</th><th>Description</th><th>Category</th><th>Qty</th><th>Cost</th><th>Price</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div>
    </div>
</div>
<div class="modal" id="stockModal"><div class="modal-content"><div class="modal-header"><div class="modal-title" id="modalTitle">Add Stock</div><button class="modal-close" onclick="closeModal()">×</button></div>
<input type="hidden" id="editIdx" value="-1">
<div class="form-row"><div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="sCode"></div><div class="form-group"><label class="form-label">Category</label><select class="input" id="sCat">{cat_options}</select></div></div>
<div class="form-group"><label class="form-label">Description</label><input type="text" class="input" id="sDesc"></div>
<div class="form-row"><div class="form-group"><label class="form-label">Qty</label><input type="number" class="input" id="sQty" value="0"></div><div class="form-group"><label class="form-label">Cost</label><input type="number" class="input" id="sCost" step="0.01" value="0"></div><div class="form-group"><label class="form-label">Price</label><input type="number" class="input" id="sPrice" step="0.01" value="0"></div></div>
<button class="btn" style="width:100%" onclick="saveStock()">Save</button></div></div>
<script>
var currentCat='All';var stock={json.dumps([dict(s) for s in stock])};
function filterCat(cat){{currentCat=cat;document.querySelectorAll('.cat-btn').forEach(btn=>{{btn.classList.remove('active');if(btn.textContent===cat)btn.classList.add('active')}});filterTable()}}
function filterTable(){{var search=document.getElementById('search').value.toLowerCase();document.querySelectorAll('#stockTable tbody tr').forEach(row=>{{var text=row.textContent.toLowerCase();var cat=row.getAttribute('data-cat')||'';row.style.display=(currentCat==='All'||cat===currentCat)&&(!search||text.includes(search))?'':'none'}})}}
function showAddModal(){{document.getElementById('modalTitle').textContent='Add Stock';document.getElementById('editIdx').value=-1;document.getElementById('sCode').value='';document.getElementById('sDesc').value='';document.getElementById('sCat').value='General';document.getElementById('sQty').value=0;document.getElementById('sCost').value=0;document.getElementById('sPrice').value=0;document.getElementById('stockModal').classList.add('show')}}
function editStock(idx){{var item=stock[idx];document.getElementById('modalTitle').textContent='Edit Stock';document.getElementById('editIdx').value=idx;document.getElementById('sCode').value=item.code||'';document.getElementById('sDesc').value=item.description||'';document.getElementById('sCat').value=item.category||'General';document.getElementById('sQty').value=item.qty||0;document.getElementById('sCost').value=item.cost||0;document.getElementById('sPrice').value=item.price||0;document.getElementById('stockModal').classList.add('show')}}
function closeModal(){{document.getElementById('stockModal').classList.remove('show')}}
function saveStock(){{var data={{idx:parseInt(document.getElementById('editIdx').value),code:document.getElementById('sCode').value,description:document.getElementById('sDesc').value,category:document.getElementById('sCat').value,qty:parseInt(document.getElementById('sQty').value)||0,cost:parseFloat(document.getElementById('sCost').value)||0,price:parseFloat(document.getElementById('sPrice').value)||0}};fetch('/api/{bid}/stock',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload();else alert(d.error||'Error')}})}}
function deleteStock(idx){{if(!confirm('Delete this item?'))return;fetch('/api/{bid}/stock/'+idx,{{method:'DELETE'}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload()}})}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/customers")
def customers_page(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    customers = b.get("customers", [])
    
    rows = ""
    for idx, c in enumerate(customers):
        balance = float(c.get("balance", 0) or 0)
        bal_class = "color:var(--green)" if balance <= 0 else "color:var(--red)"
        rows += f'<tr><td>{c.get("code", "")}</td><td><strong>{c.get("name", "")}</strong></td><td>{c.get("phone", "")}</td><td>{c.get("email", "")}</td><td style="{bal_class};font-weight:700">R {balance:,.2f}</td><td><button class="btn btn-sm btn-outline" onclick="editCust({idx})">Edit</button> <a href="/{bid}/customer/{idx}/statement" class="btn btn-sm btn-blue">Statement</a> <button class="btn btn-sm btn-green" onclick="receivePay({idx})">Receive</button></td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No customers</td></tr>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customers - {name}</title>{CSS}</head><body>
{get_header(bid, "customers")}
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
        <h1 style="font-size:24px">👥 Customers</h1>
        <button class="btn" onclick="showModal()">+ Add Customer</button>
    </div>
    <div class="card">
        <div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" placeholder="Search..." oninput="filterTable(this.value)"></div>
        <div class="table-container"><table id="custTable"><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div>
    </div>
</div>
<div class="modal" id="custModal"><div class="modal-content"><div class="modal-header"><div class="modal-title" id="modalTitle">Add Customer</div><button class="modal-close" onclick="closeModal()">×</button></div>
<input type="hidden" id="editIdx" value="-1">
<div class="form-row"><div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="cCode"></div><div class="form-group"><label class="form-label">Name</label><input type="text" class="input" id="cName"></div></div>
<div class="form-row"><div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="cPhone"></div><div class="form-group"><label class="form-label">Email</label><input type="email" class="input" id="cEmail"></div></div>
<div class="form-group"><label class="form-label">Address</label><textarea class="input" id="cAddress" rows="2"></textarea></div>
<button class="btn" style="width:100%" onclick="saveCust()">Save</button></div></div>
<script>
var customers={json.dumps(customers)};
function filterTable(s){{s=s.toLowerCase();document.querySelectorAll('#custTable tbody tr').forEach(r=>{{r.style.display=r.textContent.toLowerCase().includes(s)?'':'none'}})}}
function showModal(){{document.getElementById('modalTitle').textContent='Add Customer';document.getElementById('editIdx').value=-1;document.getElementById('cCode').value='CUST'+String(customers.length+1).padStart(3,'0');document.getElementById('cName').value='';document.getElementById('cPhone').value='';document.getElementById('cEmail').value='';document.getElementById('cAddress').value='';document.getElementById('custModal').classList.add('show')}}
function editCust(idx){{var c=customers[idx];document.getElementById('modalTitle').textContent='Edit Customer';document.getElementById('editIdx').value=idx;document.getElementById('cCode').value=c.code||'';document.getElementById('cName').value=c.name||'';document.getElementById('cPhone').value=c.phone||'';document.getElementById('cEmail').value=c.email||'';document.getElementById('cAddress').value=c.address||'';document.getElementById('custModal').classList.add('show')}}
function closeModal(){{document.getElementById('custModal').classList.remove('show')}}
function saveCust(){{var data={{idx:parseInt(document.getElementById('editIdx').value),code:document.getElementById('cCode').value,name:document.getElementById('cName').value,phone:document.getElementById('cPhone').value,email:document.getElementById('cEmail').value,address:document.getElementById('cAddress').value}};fetch('/api/{bid}/customer',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload()}})}}
function receivePay(idx){{var amount=prompt('Enter payment amount received:');if(!amount)return;fetch('/api/{bid}/customer/'+idx+'/receive',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{amount:parseFloat(amount)}})}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload()}})}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    suppliers = b.get("suppliers", [])
    
    rows = ""
    for idx, s in enumerate(suppliers):
        balance = float(s.get("balance", 0) or 0)
        bal_class = "color:var(--green)" if balance <= 0 else "color:var(--red)"
        rows += f'<tr><td>{s.get("code", "")}</td><td><strong>{s.get("name", "")}</strong></td><td>{s.get("phone", "")}</td><td style="{bal_class};font-weight:700">R {balance:,.2f}</td><td><button class="btn btn-sm btn-outline" onclick="editSupp({idx})">Edit</button> <a href="/{bid}/supplier/{idx}/statement" class="btn btn-sm btn-blue">Statement</a> <button class="btn btn-sm btn-green" onclick="paySupp({idx})">Pay</button></td></tr>'
    if not rows: rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:40px">No suppliers</td></tr>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suppliers - {name}</title>{CSS}</head><body>
{get_header(bid, "suppliers")}
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
        <h1 style="font-size:24px">🚚 Suppliers</h1>
        <button class="btn" onclick="showModal()">+ Add Supplier</button>
    </div>
    <div class="card">
        <div class="table-container"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Balance</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div>
    </div>
</div>
<div class="modal" id="suppModal"><div class="modal-content"><div class="modal-header"><div class="modal-title" id="modalTitle">Add Supplier</div><button class="modal-close" onclick="closeModal()">×</button></div>
<input type="hidden" id="editIdx" value="-1">
<div class="form-row"><div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="sCode"></div><div class="form-group"><label class="form-label">Name</label><input type="text" class="input" id="sName"></div></div>
<div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="sPhone"></div>
<button class="btn" style="width:100%" onclick="saveSupp()">Save</button></div></div>
<script>
var suppliers={json.dumps(suppliers)};
function showModal(){{document.getElementById('modalTitle').textContent='Add Supplier';document.getElementById('editIdx').value=-1;document.getElementById('sCode').value='SUPP'+String(suppliers.length+1).padStart(3,'0');document.getElementById('sName').value='';document.getElementById('sPhone').value='';document.getElementById('suppModal').classList.add('show')}}
function editSupp(idx){{var s=suppliers[idx];document.getElementById('modalTitle').textContent='Edit Supplier';document.getElementById('editIdx').value=idx;document.getElementById('sCode').value=s.code||'';document.getElementById('sName').value=s.name||'';document.getElementById('sPhone').value=s.phone||'';document.getElementById('suppModal').classList.add('show')}}
function closeModal(){{document.getElementById('suppModal').classList.remove('show')}}
function saveSupp(){{var data={{idx:parseInt(document.getElementById('editIdx').value),code:document.getElementById('sCode').value,name:document.getElementById('sName').value,phone:document.getElementById('sPhone').value}};fetch('/api/{bid}/supplier',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload()}})}}
function paySupp(idx){{var amount=prompt('Enter payment amount:');if(!amount)return;fetch('/api/{bid}/supplier/'+idx+'/pay',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{amount:parseFloat(amount)}})}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload()}})}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/expenses")
def expenses_page(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    ledger = b.get("ledger", [])
    expenses = [e for e in ledger if e.get("account", "").startswith(("5", "6", "7"))]
    
    rows = ""
    for e in reversed(expenses[-50:]):
        acc_name = ACCOUNTS.get(e.get("account", ""), ("Unknown",))[0]
        rows += f'<tr><td>{e.get("date", "")[:10]}</td><td>{e.get("ref", "")}</td><td><span class="badge badge-purple">{acc_name}</span></td><td>{e.get("desc", "")[:40]}</td><td style="color:var(--red);font-weight:600">R {float(e.get("debit", 0)):,.2f}</td></tr>'
    if not rows: rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:40px">No expenses</td></tr>'
    
    expense_cats = b.get("expense_categories", DEFAULT_EXPENSE_CATS)
    cat_options = "".join([f'<option value="{c["code"]}">{c["name"]}</option>' for c in expense_cats])
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Expenses - {name}</title>{CSS}</head><body>
{get_header(bid, "expenses")}
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
        <h1 style="font-size:24px">💸 Expenses</h1>
        <button class="btn" onclick="showModal()">+ Add Expense</button>
    </div>
    <div class="card">
        <div class="table-container"><table><thead><tr><th>Date</th><th>Ref</th><th>Category</th><th>Description</th><th>Amount</th></tr></thead><tbody>{rows}</tbody></table></div>
    </div>
</div>
<div class="modal" id="expModal"><div class="modal-content"><div class="modal-header"><div class="modal-title">Add Expense</div><button class="modal-close" onclick="closeModal()">×</button></div>
<div class="form-row"><div class="form-group"><label class="form-label">Category</label><select class="input" id="eCat">{cat_options}</select></div><div class="form-group"><label class="form-label">Date</label><input type="date" class="input" id="eDate"></div></div>
<div class="form-group"><label class="form-label">Description</label><input type="text" class="input" id="eDesc"></div>
<div class="form-row"><div class="form-group"><label class="form-label">Amount (incl VAT)</label><input type="number" class="input" id="eAmount" step="0.01"></div><div class="form-group"><label class="form-label">Supplier</label><input type="text" class="input" id="eSupp"></div></div>
<button class="btn" style="width:100%" onclick="saveExpense()">Save</button></div></div>
<script>
document.getElementById('eDate').value=new Date().toISOString().split('T')[0];
function showModal(){{document.getElementById('expModal').classList.add('show')}}
function closeModal(){{document.getElementById('expModal').classList.remove('show')}}
function saveExpense(){{var data={{category:document.getElementById('eCat').value,date:document.getElementById('eDate').value,description:document.getElementById('eDesc').value,amount:parseFloat(document.getElementById('eAmount').value)||0,supplier:document.getElementById('eSupp').value}};fetch('/api/{bid}/expense',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}}).then(r=>r.json()).then(d=>{{if(d.success)location.reload()}})}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/quotes")
def quotes_page(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    quotes = b.get("documents", {}).get("quotes", [])
    
    rows = ""
    for idx, q in enumerate(reversed(quotes[-50:])):
        status_class = "badge-green" if q.get("status") == "Accepted" else "badge-orange" if q.get("status") == "Pending" else "badge-red"
        rows += f'<tr><td>{q.get("number", "")}</td><td>{q.get("date", "")[:10]}</td><td>{q.get("customer_name", "")}</td><td>R {float(q.get("total", 0)):,.2f}</td><td><span class="badge {status_class}">{q.get("status", "Pending")}</span></td><td><a href="/{bid}/quotes/{len(quotes)-1-idx}" class="btn btn-sm btn-outline">View</a> <button class="btn btn-sm btn-green" onclick="convertToInvoice({len(quotes)-1-idx})">→ Invoice</button></td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No quotes</td></tr>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quotes - {name}</title>{CSS}</head><body>
{get_header(bid, "quotes")}
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
        <h1 style="font-size:24px">📝 Quotes</h1>
        <a href="/{bid}/quotes/new" class="btn">+ New Quote</a>
    </div>
    <div class="card">
        <div class="table-container"><table><thead><tr><th>Number</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div>
    </div>
</div>
<script>
function convertToInvoice(idx){{if(!confirm('Convert this quote to an invoice?'))return;fetch('/api/{bid}/quote/'+idx+'/convert',{{method:'POST'}}).then(r=>r.json()).then(d=>{{if(d.success)location.href='/{bid}/invoices';}})}}
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# INVOICES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/invoices")
def invoices_page(bid):
    b = biz(bid)
    name = gs(b, "company_name") or b.get("name", bid)
    invoices = b.get("documents", {}).get("invoices", [])
    
    rows = ""
    for idx, inv in enumerate(reversed(invoices[-50:])):
        paid = float(inv.get("paid", 0) or 0)
        total = float(inv.get("total", 0) or 0)
        status = "Paid" if paid >= total else "Partial" if paid > 0 else "Unpaid"
        status_class = "badge-green" if status == "Paid" else "badge-orange" if status == "Partial" else "badge-red"
        rows += f'<tr><td>{inv.get("number", "")}</td><td>{inv.get("date", "")[:10]}</td><td>{inv.get("customer_name", "")}</td><td>R {total:,.2f}</td><td>R {paid:,.2f}</td><td><span class="badge {status_class}">{status}</span></td><td><a href="/{bid}/invoices/{len(invoices)-1-idx}" class="btn btn-sm btn-outline">View</a></td></tr>'
    if not rows: rows = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:40px">No invoices</td></tr>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Invoices - {name}</title>{CSS}</head><body>
{get_header(bid, "invoices")}
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
        <h1 style="font-size:24px">📃 Invoices</h1>
        <a href="/{bid}/invoices/new" class="btn">+ New Invoice</a>
    </div>
    <div class="card">
        <div class="table-container"><table><thead><tr><th>Number</th><th>Date</th><th>Customer</th><th>Total</th><th>Paid</th><th>Status</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div>
    </div>
</div></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# NEW QUOTE / INVOICE PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/quotes/new")
@app.route("/<bid>/invoices/new")
def new_document(bid):
    b = biz(bid)
    is_quote = "quotes" in request.path
    doc_type = "Quote" if is_quote else "Invoice"
    prefix_key = "quote_prefix" if is_quote else "invoice_prefix"
    doc_num = next_doc_num(b, "quotes" if is_quote else "invoices", prefix_key)
    
    customers = b.get("customers", [])
    stock = b.get("stock", [])
    vat_rate = gs(b, "vat_rate") or 15
    
    cust_options = '<option value="">-- Select Customer --</option>' + "".join([f'<option value="{c.get("code", "")}" data-name="{c.get("name", "")}">{c.get("name", "")}</option>' for c in customers])
    stock_json = json.dumps([{"code": s.get("code", ""), "desc": s.get("description", ""), "price": float(s.get("price", 0) or 0)} for s in stock])
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>New {doc_type}</title>{CSS}</head><body>
{get_header(bid, "quotes" if is_quote else "invoices")}
<div class="container">
    <h1 style="font-size:24px;margin-bottom:20px">📝 New {doc_type}</h1>
    <div class="card">
        <div class="form-row">
            <div class="form-group"><label class="form-label">{doc_type} Number</label><input type="text" class="input" id="docNum" value="{doc_num}"></div>
            <div class="form-group"><label class="form-label">Date</label><input type="date" class="input" id="docDate"></div>
        </div>
        <div class="form-group"><label class="form-label">Customer</label><select class="input" id="custSelect">{cust_options}</select></div>
    </div>
    <div class="card">
        <div class="card-title">Line Items</div>
        <div id="lineItems"></div>
        <button class="btn btn-outline" style="margin-top:15px" onclick="addLine()">+ Add Line</button>
    </div>
    <div class="card">
        <div style="text-align:right">
            <div style="margin-bottom:10px"><span style="color:var(--muted)">Subtotal:</span> <strong id="subtotal">R 0.00</strong></div>
            <div style="margin-bottom:10px"><span style="color:var(--muted)">VAT ({vat_rate}%):</span> <strong id="vatAmount">R 0.00</strong></div>
            <div style="font-size:24px;font-weight:900;color:var(--green)">Total: <span id="totalAmount">R 0.00</span></div>
        </div>
    </div>
    <button class="btn" style="width:100%" onclick="saveDoc()">💾 Save {doc_type}</button>
</div>
<script>
var stock={stock_json};var lines=[];var vatRate={vat_rate};var isQuote={'true' if is_quote else 'false'};
document.getElementById('docDate').value=new Date().toISOString().split('T')[0];
function addLine(){{lines.push({{code:'',desc:'',qty:1,price:0}});renderLines()}}
function removeLine(idx){{lines.splice(idx,1);renderLines();calcTotals()}}
function renderLines(){{var html='';lines.forEach((l,i)=>{{html+='<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr auto;gap:10px;margin-bottom:10px;align-items:end"><div><label class="form-label">Description</label><input type="text" class="input" value="'+l.desc+'" onchange="updateLine('+i+\',\\\'desc\\\',this.value)" list="stockList"></div><div><label class="form-label">Qty</label><input type="number" class="input" value="'+l.qty+'" onchange="updateLine('+i+\',\\\'qty\\\',this.value)"></div><div><label class="form-label">Price</label><input type="number" class="input" step="0.01" value="'+l.price+'" onchange="updateLine('+i+\',\\\'price\\\',this.value)"></div><div><label class="form-label">Total</label><div class="input" style="background:var(--card)">R '+(l.qty*l.price).toFixed(2)+'</div></div><button onclick="removeLine('+i+')" style="background:var(--red);color:#fff;border:none;width:36px;height:36px;border-radius:8px;cursor:pointer;margin-bottom:0">×</button></div>'}});html+='<datalist id="stockList">';stock.forEach(s=>{{html+='<option value="'+s.desc+'" data-price="'+s.price+'">'}});html+='</datalist>';document.getElementById('lineItems').innerHTML=html||'<div style="color:var(--muted);text-align:center;padding:20px">No line items</div>'}}
function updateLine(idx,field,val){{if(field==='qty')lines[idx].qty=parseInt(val)||0;else if(field==='price')lines[idx].price=parseFloat(val)||0;else{{lines[idx].desc=val;var match=stock.find(s=>s.desc===val);if(match)lines[idx].price=match.price}}renderLines();calcTotals()}}
function calcTotals(){{var subtotal=lines.reduce((sum,l)=>sum+l.qty*l.price,0);var vat=subtotal*vatRate/100;var total=subtotal+vat;document.getElementById('subtotal').textContent='R '+subtotal.toFixed(2);document.getElementById('vatAmount').textContent='R '+vat.toFixed(2);document.getElementById('totalAmount').textContent='R '+total.toFixed(2)}}
function saveDoc(){{var custSel=document.getElementById('custSelect');var data={{number:document.getElementById('docNum').value,date:document.getElementById('docDate').value,customer_code:custSel.value,customer_name:custSel.options[custSel.selectedIndex]?.dataset?.name||'',lines:lines,vat_rate:vatRate}};var endpoint=isQuote?'/api/{bid}/quote':'/api/{bid}/invoice';fetch(endpoint,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}}).then(r=>r.json()).then(d=>{{if(d.success)location.href='/{bid}/'+(isQuote?'quotes':'invoices');else alert(d.error||'Error')}})}}
addLine();
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/settings")
def settings_page(bid):
    b = biz(bid)
    settings = b.get("settings", DEFAULT_SETTINGS)
    name = settings.get("company_name") or b.get("name", bid)
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Settings - {name}</title>{CSS}</head><body>
{get_header(bid, "settings")}
<div class="container">
    <h1 style="font-size:24px;margin-bottom:20px">⚙️ Settings</h1>
    <div class="card">
        <div class="card-title">🏢 Company Details</div>
        <div class="form-row"><div class="form-group"><label class="form-label">Company Name</label><input type="text" class="input" id="company_name" value="{settings.get('company_name', '')}"></div><div class="form-group"><label class="form-label">Trading As</label><input type="text" class="input" id="trading_as" value="{settings.get('trading_as', '')}"></div></div>
        <div class="form-row"><div class="form-group"><label class="form-label">Reg Number</label><input type="text" class="input" id="reg_number" value="{settings.get('reg_number', '')}"></div><div class="form-group"><label class="form-label">VAT Number</label><input type="text" class="input" id="vat_number" value="{settings.get('vat_number', '')}"></div></div>
        <div class="form-group"><label class="form-label">Address</label><textarea class="input" id="address" rows="2">{settings.get('address', '')}</textarea></div>
        <div class="form-row"><div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="phone" value="{settings.get('phone', '')}"></div><div class="form-group"><label class="form-label">Email</label><input type="email" class="input" id="email" value="{settings.get('email', '')}"></div></div>
    </div>
    <div class="card">
        <div class="card-title">🏦 Banking Details</div>
        <div class="form-row"><div class="form-group"><label class="form-label">Bank</label><input type="text" class="input" id="bank_name" value="{settings.get('bank_name', '')}"></div><div class="form-group"><label class="form-label">Account</label><input type="text" class="input" id="bank_account" value="{settings.get('bank_account', '')}"></div><div class="form-group"><label class="form-label">Branch</label><input type="text" class="input" id="bank_branch" value="{settings.get('bank_branch', '')}"></div></div>
    </div>
    <div class="card">
        <div class="card-title">📋 Defaults</div>
        <div class="form-row"><div class="form-group"><label class="form-label">VAT Rate (%)</label><input type="number" class="input" id="vat_rate" value="{settings.get('vat_rate', 15)}"></div><div class="form-group"><label class="form-label">Invoice Prefix</label><input type="text" class="input" id="invoice_prefix" value="{settings.get('invoice_prefix', 'INV')}"></div><div class="form-group"><label class="form-label">Quote Prefix</label><input type="text" class="input" id="quote_prefix" value="{settings.get('quote_prefix', 'QT')}"></div></div>
        <div class="form-group"><label class="form-label">Invoice Terms</label><input type="text" class="input" id="invoice_terms" value="{settings.get('invoice_terms', '')}"></div>
    </div>
    <button class="btn" style="width:100%;margin-bottom:20px" onclick="saveSettings()">💾 Save Settings</button>
    <div class="card" style="border-color:var(--red)">
        <div class="card-title" style="color:var(--red)">⚠️ Danger Zone</div>
        <button class="btn btn-red" onclick="deleteBiz()">Delete Business</button>
    </div>
</div>
<script>
function saveSettings(){{var data={{company_name:document.getElementById('company_name').value,trading_as:document.getElementById('trading_as').value,reg_number:document.getElementById('reg_number').value,vat_number:document.getElementById('vat_number').value,address:document.getElementById('address').value,phone:document.getElementById('phone').value,email:document.getElementById('email').value,bank_name:document.getElementById('bank_name').value,bank_account:document.getElementById('bank_account').value,bank_branch:document.getElementById('bank_branch').value,vat_rate:parseInt(document.getElementById('vat_rate').value)||15,invoice_prefix:document.getElementById('invoice_prefix').value,quote_prefix:document.getElementById('quote_prefix').value,invoice_terms:document.getElementById('invoice_terms').value}};fetch('/api/{bid}/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}}).then(r=>r.json()).then(d=>{{if(d.success)alert('Saved!')}})}}
function deleteBiz(){{if(!confirm('DELETE THIS BUSINESS? Cannot undo!'))return;fetch('/api/{bid}',{{method:'DELETE'}}).then(r=>r.json()).then(d=>{{if(d.success)location.href='/'}})}}
</script></body></html>'''


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PART 2 - Paste Part 3 below this line
# ═══════════════════════════════════════════════════════════════════════════════
