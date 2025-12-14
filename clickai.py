"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║   CLICK AI v5 - PART 1 of 4                                                   ║
║   Production Ready - Full Accounting System                                   ║
║   Core | Supabase | CSS | Data Models | Header                                ║
║   By: Deon & Claude | December 2025                                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, jsonify, request, redirect, Response
import json
import os
from datetime import datetime, timedelta
import re
import base64
import uuid
import csv
from io import StringIO
import requests

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CREDENTIALS
# ═══════════════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gvmonstsssdxncfkcjukr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd2bW9uc3Rzc2R4bmNma2NqdWtyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ5NDI5OTQsImV4cCI6MjA4MDUxODk5NH0.v03qjD4I0eZY5MKfkH3ONFimrHnZsy25wZfVk98UuJQ")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")

# ═══════════════════════════════════════════════════════════════════════════════
# SUPABASE CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class Supabase:
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def table(self, name):
        return SupabaseTable(self, name)

class SupabaseTable:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.url = f"{client.url}/rest/v1/{table}"
        self._filters = []
        self._select = "*"
        self._order = None
        self._limit = None
    
    def select(self, columns="*"):
        self._select = columns
        return self
    
    def eq(self, column, value):
        self._filters.append(f"{column}=eq.{value}")
        return self
    
    def order(self, column, desc=False):
        self._order = f"{column}.{'desc' if desc else 'asc'}"
        return self
    
    def limit(self, n):
        self._limit = n
        return self
    
    def execute(self):
        params = [f"select={self._select}"]
        params.extend(self._filters)
        if self._order:
            params.append(f"order={self._order}")
        if self._limit:
            params.append(f"limit={self._limit}")
        url = f"{self.url}?{'&'.join(params)}"
        try:
            r = requests.get(url, headers=self.client.headers, timeout=10)
            return {"data": r.json() if r.status_code == 200 else [], "error": None if r.status_code == 200 else r.text}
        except Exception as e:
            return {"data": [], "error": str(e)}
    
    def insert(self, data):
        try:
            r = requests.post(self.url, headers=self.client.headers, json=data, timeout=10)
            return {"data": r.json() if r.status_code in [200, 201] else None, "error": None if r.status_code in [200, 201] else r.text}
        except Exception as e:
            return {"data": None, "error": str(e)}
    
    def update(self, data):
        params = "&".join(self._filters)
        url = f"{self.url}?{params}" if params else self.url
        try:
            r = requests.patch(url, headers=self.client.headers, json=data, timeout=10)
            return {"data": r.json() if r.status_code == 200 else None, "error": None if r.status_code == 200 else r.text}
        except Exception as e:
            return {"data": None, "error": str(e)}
    
    def delete(self):
        params = "&".join(self._filters)
        url = f"{self.url}?{params}" if params else self.url
        try:
            r = requests.delete(url, headers=self.client.headers, timeout=10)
            return {"data": None, "error": None if r.status_code in [200, 204] else r.text}
        except Exception as e:
            return {"data": None, "error": str(e)}

# Initialize Supabase
sb = Supabase(SUPABASE_URL, SUPABASE_KEY)

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
    "6920": ("Food & Beverages", "Expense"),
    "6930": ("Liquor Purchases", "Expense"),
    "6999": ("Other Expenses", "Expense"),
    "7000": ("Wages & Salaries", "Expense"),
    "7100": ("Bank Charges", "Expense"),
    "8000": ("Depreciation", "Expense"),
}

# Accounts that DON'T have VAT
NO_VAT_ACCOUNTS = ["6400", "6910", "7000", "7100"]  # Insurance, Fuel, Wages, Bank Charges

# Default expense categories for dropdown
DEFAULT_EXPENSE_CATS = [
    {"code": "5000", "name": "Cost of Sales", "vat": True},
    {"code": "6100", "name": "Rent", "vat": True},
    {"code": "6200", "name": "Utilities", "vat": True},
    {"code": "6300", "name": "Telephone", "vat": True},
    {"code": "6400", "name": "Insurance", "vat": False},
    {"code": "6500", "name": "Repairs", "vat": True},
    {"code": "6600", "name": "Office Supplies", "vat": True},
    {"code": "6700", "name": "Marketing", "vat": True},
    {"code": "6910", "name": "Fuel", "vat": False},
    {"code": "6920", "name": "Food & Beverages", "vat": True},
    {"code": "6930", "name": "Liquor", "vat": True},
    {"code": "7000", "name": "Wages", "vat": False},
    {"code": "7100", "name": "Bank Charges", "vat": False},
    {"code": "6999", "name": "Other", "vat": True},
]

# Default stock categories
DEFAULT_STOCK_CATS = ["General", "Food", "Beverages", "Alcohol", "Hardware", "Tools", "Parts", "Other"]

# Default business settings
DEFAULT_SETTINGS = {
    "company_name": "",
    "trading_as": "",
    "reg_number": "",
    "vat_number": "",
    "address": "",
    "phone": "",
    "email": "",
    "logo": "",
    "bank_name": "",
    "bank_account": "",
    "bank_branch": "",
    "bank_type": "Cheque",
    "vat_rate": 15,
    "currency": "R",
    "invoice_prefix": "INV",
    "quote_prefix": "QT",
    "credit_note_prefix": "CN",
    "delivery_note_prefix": "DN",
    "po_prefix": "PO",
    "invoice_terms": "Payment due within 30 days",
    "quote_validity": "Valid for 14 days",
    "low_stock_threshold": 5,
    "default_markup": 50,
}

# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL DATA CACHE (Fallback if Supabase fails)
# ═══════════════════════════════════════════════════════════════════════════════

LOCAL_CACHE = {}

def get_business(bid):
    """Get business data - tries Supabase first, falls back to cache"""
    # Try Supabase
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if result["data"] and len(result["data"]) > 0:
        return result["data"][0]
    
    # Try cache
    if bid in LOCAL_CACHE:
        return LOCAL_CACHE[bid]
    
    return None

def get_business_data(bid, table):
    """Get related data for a business"""
    result = sb.table(table).select("*").eq("business_id", bid).order("created_at", desc=True).execute()
    return result["data"] if result["data"] else []

def save_to_supabase(table, data):
    """Save data to Supabase"""
    result = sb.table(table).insert(data).execute()
    return result

def update_in_supabase(table, id, data):
    """Update data in Supabase"""
    result = sb.table(table).eq("id", id).update(data).execute()
    return result

def delete_from_supabase(table, id):
    """Delete data from Supabase"""
    result = sb.table(table).eq("id", id).delete().execute()
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def gs(business, key):
    """Get setting from business"""
    settings = business.get("settings", {}) if business else {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except:
            settings = {}
    return settings.get(key, DEFAULT_SETTINGS.get(key, ""))

def calc_vat(amount_incl, vat_rate=15, has_vat=True):
    """Calculate VAT from inclusive amount"""
    if not has_vat:
        return {"excl": amount_incl, "vat": 0, "incl": amount_incl}
    excl = amount_incl / (1 + vat_rate / 100)
    vat = amount_incl - excl
    return {"excl": round(excl, 2), "vat": round(vat, 2), "incl": round(amount_incl, 2)}

def calc_markup(cost, markup_pct):
    """Calculate sell price from cost and markup %"""
    return round(cost * (1 + markup_pct / 100), 2)

def gen_ref(prefix, count):
    """Generate reference number"""
    return f"{prefix}{count+1:04d}"

def now_iso():
    """Current datetime as ISO string"""
    return datetime.now().isoformat()

def today_iso():
    """Current date as ISO string"""
    return datetime.now().strftime("%Y-%m-%d")

# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLES - Dark Mode, Blue Theme, Click Dropdowns
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """<style>
:root{
    --bg:#050508;
    --card:#0d0d14;
    --card-hover:#12121c;
    --border:#1a1a2f;
    --text:#fff;
    --muted:#6b7280;
    --blue:#3b82f6;
    --blue-glow:rgba(59,130,246,0.4);
    --purple:#8b5cf6;
    --green:#10b981;
    --red:#ef4444;
    --orange:#f59e0b;
    --gradient:linear-gradient(135deg,#3b82f6,#8b5cf6);
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* HEADER - STICKY WITH CLICK DROPDOWNS                                        */
/* ═══════════════════════════════════════════════════════════════════════════ */
.header{position:sticky;top:0;z-index:1000;background:rgba(13,13,20,0.95);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:10px 15px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.logo{font-size:20px;font-weight:900;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;text-decoration:none;margin-right:15px;white-space:nowrap}
.nav{display:flex;gap:6px;flex-wrap:wrap;align-items:center;flex:1}
.nav-btn{background:rgba(255,255,255,0.05);border:1px solid var(--border);color:var(--text);padding:8px 14px;border-radius:8px;cursor:pointer;font-size:12px;font-weight:600;text-decoration:none;transition:all 0.2s;white-space:nowrap}
.nav-btn:hover{background:rgba(59,130,246,0.2);border-color:var(--blue)}
.nav-btn.active{background:var(--gradient);border-color:transparent}
.nav-sep{width:1px;height:24px;background:var(--border);margin:0 5px}

/* CLICK DROPDOWN - Not hover! */
.dropdown{position:relative}
.dropdown-content{display:none;position:absolute;top:100%;left:0;background:var(--card);border:1px solid var(--border);border-radius:10px;min-width:200px;padding:8px;z-index:1001;margin-top:5px;box-shadow:0 10px 40px rgba(0,0,0,0.5)}
.dropdown.open .dropdown-content{display:block}
.dropdown-item{display:block;padding:12px 16px;color:var(--text);text-decoration:none;border-radius:6px;font-size:13px;transition:all 0.2s}
.dropdown-item:hover{background:rgba(59,130,246,0.2)}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* CONTAINER & CARDS                                                           */
/* ═══════════════════════════════════════════════════════════════════════════ */
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:20px}
.card-title{font-size:18px;font-weight:700;margin-bottom:20px;display:flex;align-items:center;gap:10px}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* STATS GRID                                                                  */
/* ═══════════════════════════════════════════════════════════════════════════ */
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:15px;margin-bottom:20px}
.stat-card{background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.3);border-radius:12px;padding:20px;text-align:center}
.stat-card.alert{background:rgba(239,68,68,0.1);border-color:rgba(239,68,68,0.3)}
.stat-card.alert .stat-value{background:linear-gradient(135deg,#ef4444,#f59e0b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-value{font-size:24px;font-weight:900;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-label{color:var(--muted);font-size:12px;margin-top:5px}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* TABLES                                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */
.table-container{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th,td{padding:12px 15px;text-align:left;border-bottom:1px solid var(--border)}
th{background:rgba(59,130,246,0.1);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:0.5px;color:var(--muted)}
tr:hover{background:rgba(255,255,255,0.02)}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* BUTTONS                                                                     */
/* ═══════════════════════════════════════════════════════════════════════════ */
.btn{background:var(--gradient);color:white;border:none;padding:12px 24px;border-radius:10px;cursor:pointer;font-weight:700;font-size:14px;transition:all 0.2s;text-decoration:none;display:inline-block}
.btn:hover{transform:translateY(-2px);box-shadow:0 5px 20px rgba(59,130,246,0.4)}
.btn-sm{padding:8px 14px;font-size:12px}
.btn-xs{padding:5px 10px;font-size:11px}
.btn-green{background:var(--green)}.btn-red{background:var(--red)}.btn-blue{background:var(--blue)}.btn-orange{background:var(--orange)}.btn-purple{background:var(--purple)}
.btn-outline{background:transparent;border:2px solid var(--blue);color:var(--blue)}
.btn-outline:hover{background:rgba(59,130,246,0.1)}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* FORMS                                                                       */
/* ═══════════════════════════════════════════════════════════════════════════ */
.form-group{margin-bottom:20px}
.form-label{display:block;font-size:13px;font-weight:600;color:var(--muted);margin-bottom:8px}
.input,select,textarea{width:100%;padding:12px 16px;background:rgba(255,255,255,0.05);border:2px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;transition:all 0.2s}
.input:focus,select:focus,textarea:focus{outline:none;border-color:var(--blue);background:rgba(59,130,246,0.1)}
select option{background:var(--card);color:var(--text)}
.form-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px}
.form-row-3{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}
.form-row-4{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* MODAL                                                                       */
/* ═══════════════════════════════════════════════════════════════════════════ */
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);z-index:2000;align-items:center;justify-content:center;padding:20px}
.modal.show{display:flex}
.modal-content{background:var(--card);border:1px solid var(--border);border-radius:20px;max-width:700px;width:100%;max-height:90vh;overflow-y:auto;padding:30px}
.modal-lg{max-width:900px}
.modal-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px}
.modal-title{font-size:20px;font-weight:700}
.modal-close{background:none;border:none;color:var(--muted);font-size:28px;cursor:pointer;line-height:1}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* BADGES                                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700}
.badge-green{background:rgba(16,185,129,0.2);color:var(--green)}
.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.badge-blue{background:rgba(59,130,246,0.2);color:var(--blue)}
.badge-orange{background:rgba(245,158,11,0.2);color:var(--orange)}
.badge-purple{background:rgba(139,92,246,0.2);color:var(--purple)}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* SEARCH                                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */
.search-box{position:relative;margin-bottom:20px}
.search-input{width:100%;padding:12px 16px 12px 45px;background:rgba(255,255,255,0.05);border:2px solid var(--border);border-radius:10px;color:var(--text);font-size:14px}
.search-input:focus{border-color:var(--blue)}
.search-icon{position:absolute;left:15px;top:50%;transform:translateY(-50%);color:var(--muted)}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* CATEGORY FILTER                                                             */
/* ═══════════════════════════════════════════════════════════════════════════ */
.cat-filter{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;padding-bottom:15px;border-bottom:1px solid var(--border)}
.cat-btn{padding:8px 16px;background:rgba(255,255,255,0.05);border:1px solid var(--border);border-radius:20px;color:var(--muted);cursor:pointer;font-size:12px;font-weight:600;transition:all 0.2s}
.cat-btn:hover,.cat-btn.active{background:var(--blue);border-color:var(--blue);color:white}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* STOCK SELECTOR - Blue Ambient Glow Blocks                                   */
/* ═══════════════════════════════════════════════════════════════════════════ */
.stock-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;max-height:50vh;overflow-y:auto;padding:5px}
.stock-block{background:var(--card-hover);border:2px solid var(--border);border-radius:12px;padding:15px;text-align:center;cursor:pointer;transition:all 0.3s;position:relative;overflow:hidden}
.stock-block:hover{border-color:var(--blue);transform:translateY(-3px);box-shadow:0 0 20px var(--blue-glow),0 0 40px var(--blue-glow)}
.stock-block.selected{border-color:var(--blue);background:rgba(59,130,246,0.15);box-shadow:0 0 25px var(--blue-glow)}
.stock-block::before{content:'';position:absolute;inset:-2px;background:linear-gradient(135deg,var(--blue),var(--purple));opacity:0;transition:opacity 0.3s;z-index:-1;border-radius:12px}
.stock-block:hover::before{opacity:0.1}
.stock-name{font-size:13px;font-weight:600;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.stock-price{color:var(--blue);font-weight:800;font-size:16px}
.stock-qty{color:var(--muted);font-size:11px;margin-top:4px}
.stock-low{color:var(--orange)}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* POS LAYOUT                                                                  */
/* ═══════════════════════════════════════════════════════════════════════════ */
.pos-grid{display:grid;grid-template-columns:1fr 380px;gap:20px}
.cart{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;display:flex;flex-direction:column;max-height:85vh}
.cart-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;padding-bottom:15px;border-bottom:1px solid var(--border)}
.cart-items{flex:1;overflow-y:auto;margin-bottom:15px}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)}
.cart-item-info{flex:1}
.cart-item-name{font-weight:600;font-size:14px}
.cart-item-price{color:var(--muted);font-size:12px}
.cart-item-controls{display:flex;align-items:center;gap:8px}
.qty-btn{background:var(--card-hover);border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:6px;cursor:pointer;font-weight:700;font-size:14px}
.qty-btn:hover{border-color:var(--blue)}
.qty-btn.minus{background:rgba(239,68,68,0.2);border-color:var(--red);color:var(--red)}
.qty-btn.plus{background:rgba(16,185,129,0.2);border-color:var(--green);color:var(--green)}
.cart-totals{border-top:2px solid var(--blue);padding-top:15px}
.cart-row{display:flex;justify-content:space-between;padding:8px 0;font-size:14px}
.cart-row.total{font-size:22px;font-weight:900;color:var(--blue)}
.cart-buttons{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:15px}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* QUICK ACTIONS                                                               */
/* ═══════════════════════════════════════════════════════════════════════════ */
.quick-actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}
.quick-btn{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px 15px;text-align:center;cursor:pointer;transition:all 0.2s;text-decoration:none;color:var(--text)}
.quick-btn:hover{background:var(--card-hover);border-color:var(--blue);transform:translateY(-3px);box-shadow:0 5px 20px rgba(59,130,246,0.2)}
.quick-icon{font-size:28px;margin-bottom:8px}
.quick-label{font-size:13px;font-weight:600}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* GLOWING LOGO                                                                */
/* ═══════════════════════════════════════════════════════════════════════════ */
@keyframes glow{
    0%,100%{text-shadow:0 0 20px var(--blue-glow),0 0 40px var(--blue-glow),0 0 60px var(--blue-glow)}
    50%{text-shadow:0 0 40px var(--blue-glow),0 0 80px var(--blue-glow),0 0 100px var(--blue-glow)}
}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.03)}}
.glow-logo{font-size:72px;font-weight:900;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:glow 2s ease-in-out infinite,pulse 3s ease-in-out infinite;cursor:pointer}
.cheeky-text{color:var(--muted);font-size:16px;margin-top:15px;font-style:italic}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* ALERTS                                                                      */
/* ═══════════════════════════════════════════════════════════════════════════ */
.alert{padding:15px 20px;border-radius:10px;margin-bottom:20px;display:flex;align-items:center;gap:12px}
.alert-warning{background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.3);color:var(--orange)}
.alert-danger{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--red)}
.alert-info{background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);color:var(--blue)}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* RESPONSIVE                                                                  */
/* ═══════════════════════════════════════════════════════════════════════════ */
@media(max-width:768px){
    .header{display:none}
    .container{padding:15px}
    .pos-grid{grid-template-columns:1fr}
    .form-row,.form-row-3,.form-row-4{grid-template-columns:1fr}
    .stock-grid{grid-template-columns:repeat(auto-fill,minmax(100px,1fr))}
}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# JAVASCRIPT FOR CLICK DROPDOWNS
# ═══════════════════════════════════════════════════════════════════════════════

DROPDOWN_JS = """<script>
document.addEventListener('DOMContentLoaded', function() {
    // Click dropdown toggle
    document.querySelectorAll('.dropdown > .nav-btn').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var dropdown = this.parentElement;
            var wasOpen = dropdown.classList.contains('open');
            // Close all dropdowns
            document.querySelectorAll('.dropdown').forEach(function(d) {
                d.classList.remove('open');
            });
            // Toggle this one
            if (!wasOpen) {
                dropdown.classList.add('open');
            }
        });
    });
    // Click outside to close
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown').forEach(function(d) {
                d.classList.remove('open');
            });
        }
    });
});
</script>"""

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER HTML FUNCTION - Used on ALL pages
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
        <div class="dropdown">
            <button class="nav-btn {"active" if active=="docs" else ""}">📄 Documents ▾</button>
            <div class="dropdown-content">
                <a href="/{bid}/quotes" class="dropdown-item">📝 Quotes</a>
                <a href="/{bid}/invoices" class="dropdown-item">📃 Invoices</a>
                <a href="/{bid}/credit-notes" class="dropdown-item">↩️ Credit Notes</a>
                <a href="/{bid}/delivery-notes" class="dropdown-item">🚚 Delivery Notes</a>
            </div>
        </div>
        <div class="dropdown">
            <button class="nav-btn {"active" if active=="reports" else ""}">📊 Reports ▾</button>
            <div class="dropdown-content">
                <a href="/{bid}/report/ledger" class="dropdown-item">📒 General Ledger</a>
                <a href="/{bid}/report/pnl" class="dropdown-item">📈 Profit & Loss</a>
                <a href="/{bid}/report/vat" class="dropdown-item">🏛️ VAT Report</a>
                <a href="/{bid}/report/debtors" class="dropdown-item">💰 Debtors Age</a>
                <a href="/{bid}/report/creditors" class="dropdown-item">💸 Creditors Age</a>
                <div style="border-top:1px solid var(--border);margin:8px 0"></div>
                <a href="/{bid}/export/csv" class="dropdown-item">📥 Export CSV</a>
            </div>
        </div>
        <a href="/{bid}/settings" class="nav-btn {"active" if active=="settings" else ""}">⚙️</a>
    </div>
</div>{DROPDOWN_JS}'''


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PART 1 - Paste Part 2 below this line
# ═══════════════════════════════════════════════════════════════════════════════
