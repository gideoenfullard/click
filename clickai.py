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
# ═══════════════════════════════════════════════════════════════════════════════
# CLICK AI v5 - PART 2 of 4
# Home | Dashboard | POS | Stock
# Paste below Part 1
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE - Business Selection with Glowing Logo
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    # Get all businesses from Supabase
    result = sb.table("businesses").select("*").order("created_at", desc=True).execute()
    businesses = result["data"] if result["data"] else []
    
    cards = ""
    for b in businesses:
        bid = b.get("id", "")
        settings = b.get("settings", {})
        if isinstance(settings, str):
            try: settings = json.loads(settings)
            except: settings = {}
        name = settings.get("company_name") or b.get("name", "Business")
        cards += f'''<a href="/{bid}" class="quick-btn">
            <div class="quick-icon">🏢</div>
            <div class="quick-label">{name}</div>
        </a>'''
    
    if not cards:
        cards = '<div style="text-align:center;padding:40px;color:var(--muted)">No businesses yet. Create one below!</div>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}</head><body>
<div class="container" style="padding-top:30px">
    <div style="text-align:center;margin-bottom:40px">
        <div class="glow-logo">⚡ Click AI</div>
        <div class="cheeky-text">Come on... I can see you want to Click me 😏</div>
    </div>
    <div class="card">
        <div class="card-title">🏢 Your Businesses</div>
        <div class="quick-actions" style="margin-bottom:20px">{cards}</div>
        <div style="border-top:1px solid var(--border);padding-top:20px;margin-top:10px">
            <div style="display:flex;gap:10px;flex-wrap:wrap">
                <input type="text" id="newBiz" class="input" placeholder="New business name..." style="flex:1;min-width:200px">
                <button class="btn" onclick="createBiz()">+ Create Business</button>
            </div>
        </div>
    </div>
    <div class="card">
        <div class="card-title">🔌 System Status</div>
        <div id="status" style="color:var(--muted)">Checking connections...</div>
    </div>
</div>
<script>
function createBiz(){{
    var name=document.getElementById('newBiz').value.trim();
    if(!name)return alert('Enter a business name');
    fetch('/api/business',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:name}})}})
    .then(r=>r.json()).then(d=>{{if(d.success)location.href='/'+d.id;else alert(d.error||'Error')}});
}}
// Check system status
fetch('/api/status').then(r=>r.json()).then(d=>{{
    var html='<div style="display:grid;gap:10px">';
    html+='<div>✅ Flask Backend: Running</div>';
    html+=d.supabase?'<div>✅ Supabase: Connected</div>':'<div>❌ Supabase: Not connected</div>';
    html+=d.anthropic?'<div>✅ Claude AI: Ready</div>':'<div>⚠️ Claude AI: No API key</div>';
    html+='</div>';
    document.getElementById('status').innerHTML=html;
}});
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD - Stats, Alerts, Quick Actions
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>")
def dashboard(bid):
    if bid in ["api", "favicon.ico", "m"]: return "", 404
    
    # Get business
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]:
        return redirect("/")
    business = result["data"][0]
    settings = business.get("settings", {})
    if isinstance(settings, str):
        try: settings = json.loads(settings)
        except: settings = {}
    name = settings.get("company_name") or business.get("name", "Business")
    
    # Mobile redirect
    mobile_check = f'<script>if(/iPhone|iPad|Android/i.test(navigator.userAgent)&&!sessionStorage.getItem("desktop"))location.href="/m/{bid}"</script>'
    
    # Get data
    stock = sb.table("stock").select("*").eq("business_id", bid).execute()["data"] or []
    customers = sb.table("customers").select("*").eq("business_id", bid).execute()["data"] or []
    suppliers = sb.table("suppliers").select("*").eq("business_id", bid).execute()["data"] or []
    ledger = sb.table("ledger").select("*").eq("business_id", bid).order("created_at", desc=True).limit(10).execute()["data"] or []
    
    # Calculate stats
    stock_count = len(stock)
    stock_value = sum(float(s.get("cost", 0) or 0) * int(s.get("qty", 0) or 0) for s in stock)
    low_stock_threshold = settings.get("low_stock_threshold", 5)
    low_stock = [s for s in stock if int(s.get("qty", 0) or 0) <= low_stock_threshold and int(s.get("qty", 0) or 0) > 0]
    out_of_stock = [s for s in stock if int(s.get("qty", 0) or 0) <= 0]
    
    debtors = sum(float(c.get("balance", 0) or 0) for c in customers if float(c.get("balance", 0) or 0) > 0)
    creditors = sum(float(s.get("balance", 0) or 0) for s in suppliers if float(s.get("balance", 0) or 0) > 0)
    
    # Low stock alerts
    alerts_html = ""
    if out_of_stock:
        items = ", ".join([s.get("description", s.get("code", ""))[:20] for s in out_of_stock[:5]])
        alerts_html += f'<div class="alert alert-danger">⚠️ <strong>Out of Stock:</strong> {items}{"..." if len(out_of_stock)>5 else ""}</div>'
    if low_stock:
        items = ", ".join([f'{s.get("description", s.get("code", ""))[:15]} ({s.get("qty")})' for s in low_stock[:5]])
        alerts_html += f'<div class="alert alert-warning">📦 <strong>Low Stock:</strong> {items}{"..." if len(low_stock)>5 else ""}</div>'
    
    # Recent transactions
    ledger_rows = ""
    for e in ledger:
        acc = e.get("account", "")
        acc_name = ACCOUNTS.get(acc, ("",))[0]
        ledger_rows += f'<tr><td>{e.get("date", "")[:10]}</td><td><span class="badge badge-blue">{e.get("ref", "")}</span></td><td>{e.get("description", "")[:35]}</td><td style="color:var(--green)">R {float(e.get("debit", 0)):,.2f}</td><td style="color:var(--red)">R {float(e.get("credit", 0)):,.2f}</td></tr>'
    if not ledger_rows:
        ledger_rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:30px">No transactions yet - make a sale!</td></tr>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{name} - Click AI</title>{CSS}{mobile_check}</head><body>
{get_header(bid, "home")}
<div class="container">
    <!-- Glowing Logo -->
    <div style="text-align:center;padding:25px 0">
        <div class="glow-logo" onclick="document.getElementById('actions').scrollIntoView({{behavior:'smooth'}})">⚡</div>
        <div style="font-size:26px;font-weight:700;margin-top:10px">{name}</div>
        <div class="cheeky-text">Come on... I can see you want to Click me 😏</div>
    </div>
    
    <!-- Alerts -->
    {alerts_html}
    
    <!-- Stats -->
    <div class="stats-grid">
        <div class="stat-card"><div class="stat-value">{stock_count}</div><div class="stat-label">Stock Items</div></div>
        <div class="stat-card"><div class="stat-value">R {stock_value:,.0f}</div><div class="stat-label">Stock Value</div></div>
        <div class="stat-card {"alert" if debtors > 0 else ""}"><div class="stat-value">R {debtors:,.0f}</div><div class="stat-label">Debtors Owe You</div></div>
        <div class="stat-card {"alert" if creditors > 0 else ""}"><div class="stat-value">R {creditors:,.0f}</div><div class="stat-label">You Owe Suppliers</div></div>
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
# POS - Full Point of Sale with Blue Stock Blocks
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/pos")
def pos_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    settings = business.get("settings", {})
    if isinstance(settings, str):
        try: settings = json.loads(settings)
        except: settings = {}
    name = settings.get("company_name") or business.get("name", "Business")
    vat_rate = settings.get("vat_rate", 15)
    currency = settings.get("currency", "R")
    
    # Get stock and customers
    stock = sb.table("stock").select("*").eq("business_id", bid).execute()["data"] or []
    customers = sb.table("customers").select("*").eq("business_id", bid).execute()["data"] or []
    
    # Get unique categories
    categories = list(set([s.get("category", "General") for s in stock]))
    categories.sort()
    cat_btns = '<button class="cat-btn active" onclick="filterCat(\'All\')">All</button>'
    for cat in categories:
        cat_btns += f'<button class="cat-btn" onclick="filterCat(\'{cat}\')">{cat}</button>'
    
    stock_json = json.dumps([{
        "id": s.get("id", ""),
        "code": s.get("code", ""),
        "desc": s.get("description", ""),
        "cat": s.get("category", "General"),
        "price": float(s.get("price", 0) or 0),
        "qty": int(s.get("qty", 0) or 0)
    } for s in stock])
    
    cust_options = '<option value="">Walk-in Customer</option>'
    for c in customers:
        cust_options += f'<option value="{c.get("id", "")}" data-name="{c.get("name", "")}">{c.get("name", "")} ({c.get("code", "")})</option>'
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS - {name}</title>{CSS}</head><body>
{get_header(bid, "pos")}
<div class="container">
    <div class="pos-grid">
        <!-- Stock Selection -->
        <div>
            <div class="card">
                <div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" id="search" placeholder="Search stock..." oninput="filterStock()"></div>
                <div class="cat-filter">{cat_btns}</div>
                <div class="stock-grid" id="stockGrid"></div>
            </div>
        </div>
        
        <!-- Cart -->
        <div class="cart">
            <div class="cart-header">
                <div class="card-title" style="margin:0">🛒 Cart</div>
                <button class="btn btn-sm btn-outline" onclick="clearCart()">Clear</button>
            </div>
            <div class="form-group" style="margin-bottom:15px">
                <select class="input" id="custSelect">{cust_options}</select>
            </div>
            <div class="cart-items" id="cartItems">
                <div style="text-align:center;color:var(--muted);padding:40px">Tap items to add to cart</div>
            </div>
            <div class="cart-totals">
                <div class="cart-row"><span>Subtotal</span><span id="subtotal">{currency} 0.00</span></div>
                <div class="cart-row"><span>VAT ({vat_rate}%)</span><span id="vatAmt">{currency} 0.00</span></div>
                <div class="cart-row total"><span>TOTAL</span><span id="cartTotal">{currency} 0.00</span></div>
            </div>
            <div class="cart-buttons">
                <button class="btn btn-green" onclick="checkout('cash')">💵 Cash</button>
                <button class="btn btn-blue" onclick="checkout('card')">💳 Card</button>
            </div>
            <button class="btn btn-purple" style="width:100%;margin-top:10px" onclick="checkout('account')">📋 On Account</button>
        </div>
    </div>
</div>
<script>
var stock={stock_json};
var cart=[];
var currentCat='All';
var currency='{currency}';
var vatRate={vat_rate};

function renderStock(){{
    var search=document.getElementById('search').value.toLowerCase();
    var html='';
    stock.forEach(function(item){{
        if(currentCat!=='All'&&item.cat!==currentCat)return;
        if(search&&!item.desc.toLowerCase().includes(search)&&!item.code.toLowerCase().includes(search))return;
        var qtyClass=item.qty<=0?'stock-low':item.qty<=5?'stock-low':'';
        var qtyText=item.qty<=0?'OUT OF STOCK':item.qty+' avail';
        if(item.qty<=0)return; // Hide out of stock in POS
        html+='<div class="stock-block" onclick="addToCart(\''+item.id+'\')">';
        html+='<div class="stock-name">'+item.desc+'</div>';
        html+='<div class="stock-price">'+currency+' '+item.price.toFixed(2)+'</div>';
        html+='<div class="stock-qty '+qtyClass+'">'+qtyText+'</div>';
        html+='</div>';
    }});
    document.getElementById('stockGrid').innerHTML=html||'<div style="text-align:center;padding:40px;color:var(--muted);grid-column:1/-1">No items found</div>';
}}

function filterCat(cat){{
    currentCat=cat;
    document.querySelectorAll('.cat-btn').forEach(b=>b.classList.remove('active'));
    event.target.classList.add('active');
    renderStock();
}}

function filterStock(){{renderStock()}}

function addToCart(id){{
    var item=stock.find(s=>s.id===id);
    if(!item||item.qty<=0)return;
    var existing=cart.find(c=>c.id===id);
    if(existing){{
        if(existing.qty>=item.qty)return alert('Not enough stock!');
        existing.qty++;
    }}else{{
        cart.push({{id:item.id,code:item.code,desc:item.desc,price:item.price,qty:1,maxQty:item.qty}});
    }}
    renderCart();
}}

function updateQty(id,delta){{
    var item=cart.find(c=>c.id===id);
    if(!item)return;
    item.qty+=delta;
    if(item.qty<=0)cart=cart.filter(c=>c.id!==id);
    else if(item.qty>item.maxQty)item.qty=item.maxQty;
    renderCart();
}}

function renderCart(){{
    if(cart.length===0){{
        document.getElementById('cartItems').innerHTML='<div style="text-align:center;color:var(--muted);padding:40px">Tap items to add to cart</div>';
        document.getElementById('subtotal').textContent=currency+' 0.00';
        document.getElementById('vatAmt').textContent=currency+' 0.00';
        document.getElementById('cartTotal').textContent=currency+' 0.00';
        return;
    }}
    var html='';
    var total=0;
    cart.forEach(function(item){{
        var lineTotal=item.price*item.qty;
        total+=lineTotal;
        html+='<div class="cart-item">';
        html+='<div class="cart-item-info"><div class="cart-item-name">'+item.desc+'</div><div class="cart-item-price">'+currency+' '+item.price.toFixed(2)+' × '+item.qty+' = '+currency+' '+lineTotal.toFixed(2)+'</div></div>';
        html+='<div class="cart-item-controls"><button class="qty-btn minus" onclick="updateQty(\''+item.id+'\',-1)">−</button><span style="min-width:25px;text-align:center">'+item.qty+'</span><button class="qty-btn plus" onclick="updateQty(\''+item.id+'\',1)">+</button></div>';
        html+='</div>';
    }});
    document.getElementById('cartItems').innerHTML=html;
    var vat=total*vatRate/(100+vatRate);
    var excl=total-vat;
    document.getElementById('subtotal').textContent=currency+' '+excl.toFixed(2);
    document.getElementById('vatAmt').textContent=currency+' '+vat.toFixed(2);
    document.getElementById('cartTotal').textContent=currency+' '+total.toFixed(2);
}}

function clearCart(){{cart=[];renderCart()}}

function checkout(method){{
    if(cart.length===0)return alert('Cart is empty!');
    var custId=document.getElementById('custSelect').value;
    if(method==='account'&&!custId)return alert('Select a customer for account sales');
    fetch('/api/{bid}/pos',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{items:cart,method:method,customer_id:custId}})
    }}).then(r=>r.json()).then(d=>{{
        if(d.success){{
            alert('✅ Sale Complete!\\nRef: '+d.ref+'\\nTotal: '+currency+' '+d.total.toFixed(2));
            cart=[];
            location.reload();
        }}else alert(d.error||'Error');
    }});
}}

renderStock();
</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# STOCK - Full Management with Markup Calculator
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/stock")
def stock_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    settings = business.get("settings", {})
    if isinstance(settings, str):
        try: settings = json.loads(settings)
        except: settings = {}
    name = settings.get("company_name") or business.get("name", "Business")
    default_markup = settings.get("default_markup", 50)
    low_stock_threshold = settings.get("low_stock_threshold", 5)
    
    stock = sb.table("stock").select("*").eq("business_id", bid).order("description").execute()["data"] or []
    
    # Categories
    categories = list(set([s.get("category", "General") for s in stock] + DEFAULT_STOCK_CATS))
    categories = sorted(list(set(categories)))
    cat_btns = '<button class="cat-btn active" onclick="filterCat(\'All\')">All</button>'
    for cat in categories:
        cat_btns += f'<button class="cat-btn" onclick="filterCat(\'{cat}\')">{cat}</button>'
    cat_options = "".join([f'<option value="{c}">{c}</option>' for c in categories])
    
    # Build rows
    rows = ""
    for s in stock:
        qty = int(s.get("qty", 0) or 0)
        cost = float(s.get("cost", 0) or 0)
        price = float(s.get("price", 0) or 0)
        markup = ((price - cost) / cost * 100) if cost > 0 else 0
        qty_class = "badge-red" if qty <= 0 else "badge-orange" if qty <= low_stock_threshold else "badge-green"
        qty_text = "OUT" if qty <= 0 else str(qty)
        rows += f'''<tr data-cat="{s.get("category", "General")}" data-id="{s.get("id", "")}">
            <td>{s.get("code", "")}</td>
            <td><strong>{s.get("description", "")}</strong></td>
            <td><span class="badge badge-blue">{s.get("category", "General")}</span></td>
            <td><span class="badge {qty_class}">{qty_text}</span></td>
            <td>R {cost:,.2f}</td>
            <td>R {price:,.2f}</td>
            <td><span class="badge badge-purple">{markup:.0f}%</span></td>
            <td>
                <button class="btn btn-xs btn-outline" onclick="editStock('{s.get("id", "")}')">Edit</button>
                <button class="btn btn-xs btn-green" onclick="adjustQty('{s.get("id", "")}','{s.get("description", "")}',{qty})">±Qty</button>
            </td>
        </tr>'''
    if not rows:
        rows = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:40px">No stock items - add your first item!</td></tr>'
    
    stock_json = json.dumps([{
        "id": s.get("id", ""),
        "code": s.get("code", ""),
        "description": s.get("description", ""),
        "category": s.get("category", "General"),
        "qty": int(s.get("qty", 0) or 0),
        "cost": float(s.get("cost", 0) or 0),
        "price": float(s.get("price", 0) or 0)
    } for s in stock])
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stock - {name}</title>{CSS}</head><body>
{get_header(bid, "stock")}
<div class="container">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
        <h1 style="font-size:24px">📦 Stock Management</h1>
        <div style="display:flex;gap:10px">
            <button class="btn btn-outline" onclick="showBulkModal()">📥 Bulk Import</button>
            <button class="btn" onclick="showAddModal()">+ Add Item</button>
        </div>
    </div>
    <div class="card">
        <div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" id="search" placeholder="Search stock..." oninput="filterTable()"></div>
        <div class="cat-filter">{cat_btns}</div>
        <div class="table-container">
            <table id="stockTable">
                <thead><tr><th>Code</th><th>Description</th><th>Category</th><th>Qty</th><th>Cost</th><th>Price</th><th>Markup</th><th>Actions</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>
</div>

<!-- Add/Edit Stock Modal -->
<div class="modal" id="stockModal">
    <div class="modal-content">
        <div class="modal-header">
            <div class="modal-title" id="modalTitle">Add Stock Item</div>
            <button class="modal-close" onclick="closeModal('stockModal')">×</button>
        </div>
        <input type="hidden" id="editId" value="">
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Code / SKU</label>
                <input type="text" class="input" id="sCode" placeholder="e.g. BRG001">
            </div>
            <div class="form-group">
                <label class="form-label">Category</label>
                <select class="input" id="sCat">{cat_options}</select>
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Description</label>
            <input type="text" class="input" id="sDesc" placeholder="Product name">
        </div>
        <div class="form-row-3">
            <div class="form-group">
                <label class="form-label">Quantity</label>
                <input type="number" class="input" id="sQty" value="0" min="0">
            </div>
            <div class="form-group">
                <label class="form-label">Cost Price (excl VAT)</label>
                <input type="number" class="input" id="sCost" step="0.01" value="0" oninput="calcPrice()">
            </div>
            <div class="form-group">
                <label class="form-label">Markup %</label>
                <input type="number" class="input" id="sMarkup" value="{default_markup}" oninput="calcPrice()">
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Sell Price (incl VAT)</label>
            <input type="number" class="input" id="sPrice" step="0.01" value="0" style="font-size:18px;font-weight:700;color:var(--blue)">
            <div style="color:var(--muted);font-size:12px;margin-top:5px">Calculated from cost + markup + 15% VAT</div>
        </div>
        <button class="btn" style="width:100%" onclick="saveStock()">💾 Save Item</button>
    </div>
</div>

<!-- Qty Adjust Modal -->
<div class="modal" id="qtyModal">
    <div class="modal-content" style="max-width:400px">
        <div class="modal-header">
            <div class="modal-title">Adjust Quantity</div>
            <button class="modal-close" onclick="closeModal('qtyModal')">×</button>
        </div>
        <input type="hidden" id="qtyId" value="">
        <div style="text-align:center;margin-bottom:20px">
            <div id="qtyItemName" style="font-size:18px;font-weight:600"></div>
            <div style="color:var(--muted)">Current: <span id="qtyCurrent">0</span></div>
        </div>
        <div class="form-group">
            <label class="form-label">Adjustment (+/-)</label>
            <input type="number" class="input" id="qtyAdj" value="0" style="text-align:center;font-size:24px">
            <div style="display:flex;gap:10px;margin-top:10px">
                <button class="btn btn-sm btn-red" style="flex:1" onclick="document.getElementById('qtyAdj').value=parseInt(document.getElementById('qtyAdj').value||0)-10">-10</button>
                <button class="btn btn-sm btn-red" style="flex:1" onclick="document.getElementById('qtyAdj').value=parseInt(document.getElementById('qtyAdj').value||0)-1">-1</button>
                <button class="btn btn-sm btn-green" style="flex:1" onclick="document.getElementById('qtyAdj').value=parseInt(document.getElementById('qtyAdj').value||0)+1">+1</button>
                <button class="btn btn-sm btn-green" style="flex:1" onclick="document.getElementById('qtyAdj').value=parseInt(document.getElementById('qtyAdj').value||0)+10">+10</button>
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Reason</label>
            <select class="input" id="qtyReason">
                <option value="count">Stock Count</option>
                <option value="received">Received Stock</option>
                <option value="damaged">Damaged/Write-off</option>
                <option value="return">Customer Return</option>
                <option value="other">Other</option>
            </select>
        </div>
        <button class="btn" style="width:100%" onclick="saveQtyAdj()">💾 Save Adjustment</button>
    </div>
</div>

<script>
var stock={stock_json};
var currentCat='All';
var defaultMarkup={default_markup};

function filterCat(cat){{
    currentCat=cat;
    document.querySelectorAll('.cat-btn').forEach(b=>b.classList.remove('active'));
    event.target.classList.add('active');
    filterTable();
}}

function filterTable(){{
    var search=document.getElementById('search').value.toLowerCase();
    document.querySelectorAll('#stockTable tbody tr').forEach(function(row){{
        var text=row.textContent.toLowerCase();
        var cat=row.getAttribute('data-cat')||'';
        var showCat=currentCat==='All'||cat===currentCat;
        var showSearch=!search||text.includes(search);
        row.style.display=(showCat&&showSearch)?'':'none';
    }});
}}

function showAddModal(){{
    document.getElementById('modalTitle').textContent='Add Stock Item';
    document.getElementById('editId').value='';
    document.getElementById('sCode').value='';
    document.getElementById('sDesc').value='';
    document.getElementById('sCat').value='General';
    document.getElementById('sQty').value=0;
    document.getElementById('sCost').value=0;
    document.getElementById('sMarkup').value=defaultMarkup;
    document.getElementById('sPrice').value=0;
    document.getElementById('stockModal').classList.add('show');
}}

function editStock(id){{
    var item=stock.find(s=>s.id===id);
    if(!item)return;
    document.getElementById('modalTitle').textContent='Edit Stock Item';
    document.getElementById('editId').value=id;
    document.getElementById('sCode').value=item.code;
    document.getElementById('sDesc').value=item.description;
    document.getElementById('sCat').value=item.category;
    document.getElementById('sQty').value=item.qty;
    document.getElementById('sCost').value=item.cost;
    var markup=item.cost>0?((item.price/1.15-item.cost)/item.cost*100):defaultMarkup;
    document.getElementById('sMarkup').value=Math.round(markup);
    document.getElementById('sPrice').value=item.price;
    document.getElementById('stockModal').classList.add('show');
}}

function calcPrice(){{
    var cost=parseFloat(document.getElementById('sCost').value)||0;
    var markup=parseFloat(document.getElementById('sMarkup').value)||0;
    var priceExcl=cost*(1+markup/100);
    var priceIncl=priceExcl*1.15;
    document.getElementById('sPrice').value=priceIncl.toFixed(2);
}}

function closeModal(id){{document.getElementById(id).classList.remove('show')}}

function saveStock(){{
    var data={{
        id:document.getElementById('editId').value||null,
        code:document.getElementById('sCode').value,
        description:document.getElementById('sDesc').value,
        category:document.getElementById('sCat').value,
        qty:parseInt(document.getElementById('sQty').value)||0,
        cost:parseFloat(document.getElementById('sCost').value)||0,
        price:parseFloat(document.getElementById('sPrice').value)||0
    }};
    if(!data.description)return alert('Enter a description');
    fetch('/api/{bid}/stock',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify(data)
    }}).then(r=>r.json()).then(d=>{{
        if(d.success)location.reload();
        else alert(d.error||'Error');
    }});
}}

function adjustQty(id,name,current){{
    document.getElementById('qtyId').value=id;
    document.getElementById('qtyItemName').textContent=name;
    document.getElementById('qtyCurrent').textContent=current;
    document.getElementById('qtyAdj').value=0;
    document.getElementById('qtyModal').classList.add('show');
}}

function saveQtyAdj(){{
    var data={{
        id:document.getElementById('qtyId').value,
        adjustment:parseInt(document.getElementById('qtyAdj').value)||0,
        reason:document.getElementById('qtyReason').value
    }};
    if(data.adjustment===0)return alert('Enter an adjustment');
    fetch('/api/{bid}/stock/adjust',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify(data)
    }}).then(r=>r.json()).then(d=>{{
        if(d.success)location.reload();
        else alert(d.error||'Error');
    }});
}}

function showBulkModal(){{alert('Bulk import coming soon!')}}
</script></body></html>'''


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PART 2 - Paste Part 3 below this line
# ═══════════════════════════════════════════════════════════════════════════════
