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

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gvmonstssdxncfkcjukr.supabase.co")
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
    result = sb.table(table).insert(data)
    return result

def update_in_supabase(table, id, data):
    """Update data in Supabase"""
    result = sb.table(table).eq("id", id).update(data)
    return result

def delete_from_supabase(table, id):
    """Delete data from Supabase"""
    result = sb.table(table).eq("id", id).delete()
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
        <a href="/{bid}/import" class="nav-btn {"active" if active=="import" else ""}">📥 Import</a>
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
    
    # Get unique categories and build BIG buttons
    categories = sorted(list(set([s.get("category", "General") for s in stock])))
    cat_icons={"Bearings":"⚙️","Seals":"🔘","Circlips":"⭕","Bolts":"🔩","Cap Screws":"🔩","Nuts":"🔩","Washers":"⚙️","Imp Bolts":"🔩","Shoes":"👞","PPE":"🦺","Welding":"🔥","Shirts":"👕","Hardware":"🔧","General":"📦"}
    cat_btns = '<div class="cat-btn-big active" onclick="filterCat(\'All\')">🏪<br>All</div>'
    for cat in categories:
        icon = cat_icons.get(cat, "📦")
        cat_btns += f'<div class="cat-btn-big" onclick="filterCat(\'{cat}\')">{icon}<br>{cat}</div>'
    
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
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS - {name}</title>{CSS}
<style>
.cat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(85px,1fr));gap:10px;margin-bottom:20px}}
.cat-btn-big{{background:rgba(59,130,246,0.1);border:2px solid rgba(59,130,246,0.3);border-radius:12px;padding:12px 8px;text-align:center;cursor:pointer;font-size:11px;font-weight:600;transition:all 0.2s;line-height:1.3}}
.cat-btn-big:hover,.cat-btn-big.active{{background:var(--blue);border-color:var(--blue);color:white;transform:scale(1.05);box-shadow:0 0 20px rgba(59,130,246,0.4)}}
</style></head><body>
{get_header(bid, "pos")}
<div class="container">
    <div class="pos-grid">
        <!-- Stock Selection -->
        <div>
            <div class="card">
                <div class="cat-grid">{cat_btns}</div>
                <div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" id="search" placeholder="Search stock..." oninput="filterStock()"></div>
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
    document.querySelectorAll('.cat-btn-big').forEach(b=>b.classList.remove('active'));
    event.target.closest('.cat-btn-big').classList.add('active');
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
# ═══════════════════════════════════════════════════════════════════════════════
# CLICK AI v5 - PART 3 of 4
# Customers | Suppliers | Expenses | Quotes | Invoices | Credit Notes | Delivery Notes
# Paste below Part 2
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/customers")
def customers_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    settings = business.get("settings", {})
    if isinstance(settings, str):
        try: settings = json.loads(settings)
        except: settings = {}
    name = settings.get("company_name") or business.get("name", "Business")
    customers = sb.table("customers").select("*").eq("business_id", bid).order("name").execute()["data"] or []
    rows = ""
    total_debtors = 0
    for c in customers:
        bal = float(c.get("balance", 0) or 0)
        if bal > 0: total_debtors += bal
        bal_class = "color:var(--green)" if bal <= 0 else "color:var(--red)"
        rows += f'<tr><td>{c.get("code", "")}</td><td><strong>{c.get("name", "")}</strong></td><td>{c.get("phone", "")}</td><td>{c.get("email", "")}</td><td style="{bal_class};font-weight:700">R {bal:,.2f}</td><td><button class="btn btn-xs btn-outline" onclick="editCust(\'{c.get("id", "")}\')">Edit</button> <a href="/{bid}/customer/{c.get("id", "")}/statement" class="btn btn-xs btn-blue">Statement</a> <button class="btn btn-xs btn-green" onclick="receivePay(\'{c.get("id", "")}\',\'{c.get("name", "")}\',{bal})">Receive</button></td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No customers</td></tr>'
    cust_json = json.dumps([{"id":c.get("id",""),"code":c.get("code",""),"name":c.get("name",""),"phone":c.get("phone",""),"email":c.get("email",""),"address":c.get("address","")} for c in customers])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customers</title>{CSS}</head><body>
{get_header(bid, "customers")}
<div class="container">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px"><div><h1 style="font-size:24px">👥 Customers</h1><div style="color:var(--muted)">Total Owing: <strong style="color:var(--red)">R {total_debtors:,.2f}</strong></div></div><button class="btn" onclick="showAdd()">+ Add</button></div>
<div class="card"><div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" placeholder="Search..." oninput="filter(this.value)"></div><div class="table-container"><table id="tbl"><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div></div></div>
<div class="modal" id="modal"><div class="modal-content"><div class="modal-header"><div class="modal-title" id="mtitle">Add Customer</div><button class="modal-close" onclick="closeM()">×</button></div><input type="hidden" id="eid"><div class="form-row"><div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="fcode"></div><div class="form-group"><label class="form-label">Name *</label><input type="text" class="input" id="fname"></div></div><div class="form-row"><div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="fphone"></div><div class="form-group"><label class="form-label">Email</label><input type="email" class="input" id="femail"></div></div><div class="form-group"><label class="form-label">Address</label><textarea class="input" id="faddr" rows="2"></textarea></div><button class="btn" style="width:100%" onclick="save()">💾 Save</button></div></div>
<div class="modal" id="payM"><div class="modal-content" style="max-width:400px"><div class="modal-header"><div class="modal-title">Receive Payment</div><button class="modal-close" onclick="closePay()">×</button></div><input type="hidden" id="payId"><div style="text-align:center;margin-bottom:20px"><div id="payN" style="font-size:18px;font-weight:600"></div><div style="color:var(--muted)">Balance: R <span id="payB">0</span></div></div><div class="form-group"><label class="form-label">Amount</label><input type="number" class="input" id="payA" step="0.01" style="font-size:24px;text-align:center"></div><button class="btn btn-green" style="width:100%" onclick="savePay()">💰 Record</button></div></div>
<script>var cust={cust_json};function filter(s){{s=s.toLowerCase();document.querySelectorAll('#tbl tbody tr').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(s)?'':'none')}}function showAdd(){{document.getElementById('mtitle').textContent='Add Customer';document.getElementById('eid').value='';document.getElementById('fcode').value='C'+String(cust.length+1).padStart(3,'0');document.getElementById('fname').value='';document.getElementById('fphone').value='';document.getElementById('femail').value='';document.getElementById('faddr').value='';document.getElementById('modal').classList.add('show')}}function editCust(id){{var c=cust.find(x=>x.id===id);if(!c)return;document.getElementById('mtitle').textContent='Edit';document.getElementById('eid').value=id;document.getElementById('fcode').value=c.code;document.getElementById('fname').value=c.name;document.getElementById('fphone').value=c.phone;document.getElementById('femail').value=c.email;document.getElementById('faddr').value=c.address||'';document.getElementById('modal').classList.add('show')}}function closeM(){{document.getElementById('modal').classList.remove('show')}}function save(){{var d={{id:document.getElementById('eid').value||null,code:document.getElementById('fcode').value,name:document.getElementById('fname').value,phone:document.getElementById('fphone').value,email:document.getElementById('femail').value,address:document.getElementById('faddr').value}};if(!d.name)return alert('Name required');fetch('/api/{bid}/customer',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{if(x.success)location.reload()}})}}function receivePay(id,n,b){{document.getElementById('payId').value=id;document.getElementById('payN').textContent=n;document.getElementById('payB').textContent=b.toFixed(2);document.getElementById('payA').value=b>0?b.toFixed(2):'';document.getElementById('payM').classList.add('show')}}function closePay(){{document.getElementById('payM').classList.remove('show')}}function savePay(){{var d={{id:document.getElementById('payId').value,amount:parseFloat(document.getElementById('payA').value)||0}};if(d.amount<=0)return alert('Enter amount');fetch('/api/{bid}/customer/receive',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{if(x.success)location.reload()}})}}</script></body></html>'''

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    suppliers = sb.table("suppliers").select("*").eq("business_id", bid).order("name").execute()["data"] or []
    rows = ""
    total = 0
    for s in suppliers:
        bal = float(s.get("balance", 0) or 0)
        if bal > 0: total += bal
        bc = "color:var(--green)" if bal <= 0 else "color:var(--red)"
        rows += f'<tr><td>{s.get("code", "")}</td><td><strong>{s.get("name", "")}</strong></td><td>{s.get("phone", "")}</td><td style="{bc};font-weight:700">R {bal:,.2f}</td><td><button class="btn btn-xs btn-outline" onclick="edit(\'{s.get("id", "")}\')">Edit</button> <a href="/{bid}/supplier/{s.get("id", "")}/statement" class="btn btn-xs btn-blue">Statement</a> <button class="btn btn-xs btn-green" onclick="pay(\'{s.get("id", "")}\',\'{s.get("name", "")}\',{bal})">Pay</button></td></tr>'
    if not rows: rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:40px">No suppliers</td></tr>'
    supp_json = json.dumps([{"id":s.get("id",""),"code":s.get("code",""),"name":s.get("name",""),"phone":s.get("phone","")} for s in suppliers])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suppliers</title>{CSS}</head><body>
{get_header(bid, "suppliers")}
<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px"><div><h1 style="font-size:24px">🚚 Suppliers</h1><div style="color:var(--muted)">You Owe: <strong style="color:var(--red)">R {total:,.2f}</strong></div></div><button class="btn" onclick="showAdd()">+ Add</button></div>
<div class="card"><div class="table-container"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Balance</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div></div></div>
<div class="modal" id="modal"><div class="modal-content"><div class="modal-header"><div class="modal-title" id="mt">Add Supplier</div><button class="modal-close" onclick="closeM()">×</button></div><input type="hidden" id="eid"><div class="form-row"><div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="fc"></div><div class="form-group"><label class="form-label">Name *</label><input type="text" class="input" id="fn"></div></div><div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="fp"></div><button class="btn" style="width:100%" onclick="save()">💾 Save</button></div></div>
<div class="modal" id="payM"><div class="modal-content" style="max-width:400px"><div class="modal-header"><div class="modal-title">Pay Supplier</div><button class="modal-close" onclick="closePay()">×</button></div><input type="hidden" id="payId"><div style="text-align:center;margin-bottom:20px"><div id="payN" style="font-size:18px;font-weight:600"></div><div style="color:var(--muted)">Balance: R <span id="payB">0</span></div></div><div class="form-group"><label class="form-label">Amount</label><input type="number" class="input" id="payA" step="0.01" style="font-size:24px;text-align:center"></div><button class="btn btn-green" style="width:100%" onclick="savePay()">💸 Pay</button></div></div>
<script>var supp={supp_json};function showAdd(){{document.getElementById('mt').textContent='Add Supplier';document.getElementById('eid').value='';document.getElementById('fc').value='S'+String(supp.length+1).padStart(3,'0');document.getElementById('fn').value='';document.getElementById('fp').value='';document.getElementById('modal').classList.add('show')}}function edit(id){{var s=supp.find(x=>x.id===id);if(!s)return;document.getElementById('mt').textContent='Edit';document.getElementById('eid').value=id;document.getElementById('fc').value=s.code;document.getElementById('fn').value=s.name;document.getElementById('fp').value=s.phone;document.getElementById('modal').classList.add('show')}}function closeM(){{document.getElementById('modal').classList.remove('show')}}function save(){{var d={{id:document.getElementById('eid').value||null,code:document.getElementById('fc').value,name:document.getElementById('fn').value,phone:document.getElementById('fp').value}};if(!d.name)return alert('Name required');fetch('/api/{bid}/supplier',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{if(x.success)location.reload()}})}}function pay(id,n,b){{document.getElementById('payId').value=id;document.getElementById('payN').textContent=n;document.getElementById('payB').textContent=b.toFixed(2);document.getElementById('payA').value=b>0?b.toFixed(2):'';document.getElementById('payM').classList.add('show')}}function closePay(){{document.getElementById('payM').classList.remove('show')}}function savePay(){{var d={{id:document.getElementById('payId').value,amount:parseFloat(document.getElementById('payA').value)||0}};if(d.amount<=0)return alert('Enter amount');fetch('/api/{bid}/supplier/pay',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{if(x.success)location.reload()}})}}</script></body></html>'''

@app.route("/<bid>/expenses")
def expenses_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    ledger = sb.table("ledger").select("*").eq("business_id", bid).order("created_at", desc=True).limit(100).execute()["data"] or []
    expenses = [e for e in ledger if e.get("account", "").startswith(("5", "6", "7")) and float(e.get("debit", 0)) > 0]
    rows = ""
    for e in expenses[:50]:
        acc = e.get("account", "")
        acc_name = ACCOUNTS.get(acc, ("Other",))[0]
        rows += f'<tr><td>{e.get("date", "")[:10]}</td><td><span class="badge badge-blue">{e.get("ref", "")}</span></td><td><span class="badge badge-purple">{acc_name}</span></td><td>{e.get("description", "")[:40]}</td><td style="color:var(--red);font-weight:600">R {float(e.get("debit", 0)):,.2f}</td></tr>'
    if not rows: rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:40px">No expenses</td></tr>'
    cat_opts = "".join([f'<option value="{c["code"]}">{c["name"]}</option>' for c in DEFAULT_EXPENSE_CATS])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Expenses</title>{CSS}</head><body>
{get_header(bid, "expenses")}
<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"><h1 style="font-size:24px">💸 Expenses</h1><button class="btn" onclick="showAdd()">+ Add Expense</button></div>
<div class="card"><div class="table-container"><table><thead><tr><th>Date</th><th>Ref</th><th>Category</th><th>Description</th><th>Amount</th></tr></thead><tbody>{rows}</tbody></table></div></div></div>
<div class="modal" id="modal"><div class="modal-content"><div class="modal-header"><div class="modal-title">Add Expense</div><button class="modal-close" onclick="closeM()">×</button></div><div class="form-row"><div class="form-group"><label class="form-label">Category</label><select class="input" id="fcat">{cat_opts}</select></div><div class="form-group"><label class="form-label">Date</label><input type="date" class="input" id="fdate"></div></div><div class="form-group"><label class="form-label">Description</label><input type="text" class="input" id="fdesc"></div><div class="form-row"><div class="form-group"><label class="form-label">Amount (incl VAT)</label><input type="number" class="input" id="famt" step="0.01"></div><div class="form-group"><label class="form-label">Supplier</label><input type="text" class="input" id="fsupp"></div></div><button class="btn" style="width:100%" onclick="save()">💾 Save</button></div></div>
<script>document.getElementById('fdate').value=new Date().toISOString().split('T')[0];function showAdd(){{document.getElementById('modal').classList.add('show')}}function closeM(){{document.getElementById('modal').classList.remove('show')}}function save(){{var d={{category:document.getElementById('fcat').value,date:document.getElementById('fdate').value,description:document.getElementById('fdesc').value,amount:parseFloat(document.getElementById('famt').value)||0,supplier:document.getElementById('fsupp').value}};if(d.amount<=0)return alert('Enter amount');fetch('/api/{bid}/expense',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{if(x.success)location.reload()}})}}</script></body></html>'''

@app.route("/<bid>/quotes")
def quotes_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    quotes = sb.table("quotes").select("*").eq("business_id", bid).order("created_at", desc=True).limit(50).execute()["data"] or []
    rows = ""
    for q in quotes:
        st = q.get("status", "Pending")
        sc = "badge-green" if st == "Accepted" else "badge-orange" if st == "Pending" else "badge-red"
        rows += f'<tr><td><span class="badge badge-blue">{q.get("number", "")}</span></td><td>{q.get("date", "")[:10]}</td><td>{q.get("customer_name", "")}</td><td style="font-weight:600">R {float(q.get("total", 0)):,.2f}</td><td><span class="badge {sc}">{st}</span></td><td><a href="/{bid}/quotes/{q.get("id", "")}" class="btn btn-xs btn-outline">View</a> <button class="btn btn-xs btn-green" onclick="convert(\'{q.get("id", "")}\')">→ Invoice</button></td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No quotes</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quotes</title>{CSS}</head><body>
{get_header(bid, "docs")}
<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"><h1 style="font-size:24px">📝 Quotes</h1><a href="/{bid}/quotes/new" class="btn">+ New Quote</a></div>
<div class="card"><div class="table-container"><table><thead><tr><th>Number</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div></div></div>
<script>function convert(id){{if(!confirm('Convert to invoice?'))return;fetch('/api/{bid}/quote/'+id+'/convert',{{method:'POST'}}).then(r=>r.json()).then(x=>{{if(x.success)location.href='/{bid}/invoices'}})}}</script></body></html>'''

@app.route("/<bid>/invoices")
def invoices_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    invoices = sb.table("invoices").select("*").eq("business_id", bid).order("created_at", desc=True).limit(50).execute()["data"] or []
    rows = ""
    for inv in invoices:
        paid = float(inv.get("paid", 0) or 0)
        total = float(inv.get("total", 0) or 0)
        st = "Paid" if paid >= total else "Partial" if paid > 0 else "Unpaid"
        sc = "badge-green" if st == "Paid" else "badge-orange" if st == "Partial" else "badge-red"
        rows += f'<tr><td><span class="badge badge-blue">{inv.get("number", "")}</span></td><td>{inv.get("date", "")[:10]}</td><td>{inv.get("customer_name", "")}</td><td style="font-weight:600">R {total:,.2f}</td><td>R {paid:,.2f}</td><td><span class="badge {sc}">{st}</span></td><td><a href="/{bid}/invoices/{inv.get("id", "")}" class="btn btn-xs btn-outline">View</a></td></tr>'
    if not rows: rows = '<tr><td colspan="7" style="text-align:center;color:var(--muted);padding:40px">No invoices</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Invoices</title>{CSS}</head><body>
{get_header(bid, "docs")}
<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"><h1 style="font-size:24px">📃 Invoices</h1><a href="/{bid}/invoices/new" class="btn">+ New Invoice</a></div>
<div class="card"><div class="table-container"><table><thead><tr><th>Number</th><th>Date</th><th>Customer</th><th>Total</th><th>Paid</th><th>Status</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

@app.route("/<bid>/quotes/new")
@app.route("/<bid>/invoices/new")
def new_doc_page(bid):
    is_quote = "quotes" in request.path
    doc_type = "Quote" if is_quote else "Invoice"
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    settings = business.get("settings", {})
    if isinstance(settings, str):
        try: settings = json.loads(settings)
        except: settings = {}
    vat_rate = settings.get("vat_rate", 15)
    prefix = settings.get("quote_prefix", "QT") if is_quote else settings.get("invoice_prefix", "INV")
    existing = sb.table("quotes" if is_quote else "invoices").select("id").eq("business_id", bid).execute()["data"] or []
    doc_num = f"{prefix}{len(existing)+1:04d}"
    customers = sb.table("customers").select("*").eq("business_id", bid).execute()["data"] or []
    stock = sb.table("stock").select("*").eq("business_id", bid).execute()["data"] or []
    cust_opts = '<option value="">-- Select Customer --</option>'+"".join([f'<option value="{c.get("id","")}" data-name="{c.get("name","")}" data-code="{c.get("code","")}">{c.get("name","")} ({c.get("code","")})</option>' for c in customers])
    stock_json = json.dumps([{"id":s.get("id",""),"code":s.get("code",""),"desc":s.get("description",""),"price":float(s.get("price",0)or 0),"qty":int(s.get("qty",0)or 0),"cat":s.get("category","General")} for s in stock])
    cats = sorted(list(set([s.get("category","General") for s in stock])))
    cat_btns = '<button class="cat-btn active" onclick="filterCat(\'All\')">All</button>'+"".join([f'<button class="cat-btn" onclick="filterCat(\'{c}\')">{c}</button>' for c in cats])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>New {doc_type}</title>{CSS}</head><body>
{get_header(bid, "docs")}
<div class="container"><h1 style="font-size:24px;margin-bottom:20px">📝 New {doc_type}</h1>
<div class="form-row" style="margin-bottom:20px"><div class="form-group" style="margin:0"><label class="form-label">{doc_type} #</label><input type="text" class="input" id="docNum" value="{doc_num}"></div><div class="form-group" style="margin:0"><label class="form-label">Date</label><input type="date" class="input" id="docDate"></div><div class="form-group" style="margin:0;flex:2"><label class="form-label">Customer *</label><select class="input" id="custSel">{cust_opts}</select></div></div>
<div class="card"><div class="card-title">📦 Select Items</div><div class="search-box"><span class="search-icon">🔍</span><input type="text" class="search-input" id="search" placeholder="Search..." oninput="filterStock()"></div><div class="cat-filter">{cat_btns}</div><div class="stock-grid" id="stockGrid"></div></div>
<div class="card"><div class="card-title">📋 Line Items</div><div id="lines"><div style="text-align:center;color:var(--muted);padding:20px">Click items above to add</div></div></div>
<div class="card"><div style="text-align:right"><div class="cart-row"><span>Subtotal</span><span id="subtot">R 0.00</span></div><div class="cart-row"><span>VAT ({vat_rate}%)</span><span id="vatamt">R 0.00</span></div><div class="cart-row total"><span>TOTAL</span><span id="total">R 0.00</span></div></div></div>
<button class="btn" style="width:100%" onclick="saveDoc()">💾 Save {doc_type}</button></div>
<script>
var stock={stock_json};var lines=[];var vatRate={vat_rate};var isQuote={'true' if is_quote else 'false'};var curCat='All';
document.getElementById('docDate').value=new Date().toISOString().split('T')[0];
function filterCat(c){{curCat=c;document.querySelectorAll('.cat-btn').forEach(b=>b.classList.remove('active'));event.target.classList.add('active');renderStock()}}
function filterStock(){{renderStock()}}
function renderStock(){{var s=document.getElementById('search').value.toLowerCase();var h='';stock.forEach(function(i){{if(curCat!=='All'&&i.cat!==curCat)return;if(s&&!i.desc.toLowerCase().includes(s)&&!i.code.toLowerCase().includes(s))return;h+='<div class="stock-block" onclick="addLine(\''+i.id+'\')"><div class="stock-name">'+i.desc+'</div><div class="stock-price">R '+i.price.toFixed(2)+'</div><div class="stock-qty">'+i.qty+' avail</div></div>'}});document.getElementById('stockGrid').innerHTML=h||'<div style="text-align:center;color:var(--muted);padding:30px;grid-column:1/-1">No items</div>'}}
function addLine(id){{var i=stock.find(x=>x.id===id);if(!i)return;var ex=lines.find(x=>x.id===id);if(ex)ex.qty++;else lines.push({{id:i.id,code:i.code,desc:i.desc,price:i.price,qty:1}});renderLines()}}
function updQty(id,d){{var l=lines.find(x=>x.id===id);if(!l)return;l.qty+=d;if(l.qty<=0)lines=lines.filter(x=>x.id!==id);renderLines()}}
function renderLines(){{if(!lines.length){{document.getElementById('lines').innerHTML='<div style="text-align:center;color:var(--muted);padding:20px">Click items above to add</div>';calc();return}}var h='<table style="width:100%"><thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th><th></th></tr></thead><tbody>';lines.forEach(function(l){{h+='<tr><td>'+l.desc+'</td><td style="width:100px"><div style="display:flex;align-items:center;gap:5px"><button class="qty-btn minus" onclick="updQty(\''+l.id+'\',-1)">−</button><span>'+l.qty+'</span><button class="qty-btn plus" onclick="updQty(\''+l.id+'\',1)">+</button></div></td><td>R '+l.price.toFixed(2)+'</td><td style="font-weight:600">R '+(l.price*l.qty).toFixed(2)+'</td><td><button class="btn btn-xs btn-red" onclick="lines=lines.filter(x=>x.id!==\''+l.id+'\');renderLines()">×</button></td></tr>'}});h+='</tbody></table>';document.getElementById('lines').innerHTML=h;calc()}}
function calc(){{var sub=lines.reduce((s,l)=>s+l.price*l.qty,0);var vat=sub*vatRate/100;document.getElementById('subtot').textContent='R '+sub.toFixed(2);document.getElementById('vatamt').textContent='R '+vat.toFixed(2);document.getElementById('total').textContent='R '+(sub+vat).toFixed(2)}}
function saveDoc(){{var cs=document.getElementById('custSel');if(!cs.value)return alert('Select customer');if(!lines.length)return alert('Add items');var d={{number:document.getElementById('docNum').value,date:document.getElementById('docDate').value,customer_id:cs.value,customer_name:cs.options[cs.selectedIndex].dataset.name,customer_code:cs.options[cs.selectedIndex].dataset.code,lines:lines,vat_rate:vatRate}};fetch('/api/{bid}/'+(isQuote?'quote':'invoice'),{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{if(x.success)location.href='/{bid}/'+(isQuote?'quotes':'invoices');else alert(x.error||'Error')}})}}
renderStock();
</script></body></html>'''

@app.route("/<bid>/credit-notes")
def credit_notes_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    notes = sb.table("credit_notes").select("*").eq("business_id", bid).order("created_at", desc=True).execute()["data"] or []
    rows = ""
    for n in notes:
        rows += f'<tr><td><span class="badge badge-purple">{n.get("number", "")}</span></td><td>{n.get("date", "")[:10]}</td><td>{n.get("invoice_number", "")}</td><td>{n.get("customer_name", "")}</td><td style="color:var(--green);font-weight:600">R {float(n.get("total", 0)):,.2f}</td><td>{n.get("reason", "")[:30]}</td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No credit notes</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Credit Notes</title>{CSS}</head><body>
{get_header(bid, "docs")}
<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"><h1 style="font-size:24px">↩️ Credit Notes</h1><a href="/{bid}/credit-notes/new" class="btn">+ New Credit Note</a></div>
<div class="card"><div class="table-container"><table><thead><tr><th>Number</th><th>Date</th><th>Invoice</th><th>Customer</th><th>Amount</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

@app.route("/<bid>/delivery-notes")
def delivery_notes_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    notes = sb.table("delivery_notes").select("*").eq("business_id", bid).order("created_at", desc=True).execute()["data"] or []
    rows = ""
    for n in notes:
        rows += f'<tr><td><span class="badge badge-orange">{n.get("number", "")}</span></td><td>{n.get("date", "")[:10]}</td><td>{n.get("invoice_number", "")}</td><td>{n.get("customer_name", "")}</td><td>{n.get("delivery_address", "")[:40]}</td><td><span class="badge {"badge-green" if n.get("delivered") else "badge-orange"}">{"Delivered" if n.get("delivered") else "Pending"}</span></td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No delivery notes</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Delivery Notes</title>{CSS}</head><body>
{get_header(bid, "docs")}
<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px"><h1 style="font-size:24px">🚚 Delivery Notes</h1></div>
<div class="card"><div class="table-container"><table><thead><tr><th>Number</th><th>Date</th><th>Invoice</th><th>Customer</th><th>Address</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT PAGE - CSV Import for Stock, Customers, Suppliers
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/import")
def import_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    s = business.get("settings", {})
    if isinstance(s, str):
        try: s = json.loads(s)
        except: s = {}
    name = s.get("company_name") or business.get("name", "Business")
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Import - {name}</title>{CSS}</head><body>
{get_header(bid, "import")}
<div class="container">
<h1 style="font-size:24px;margin-bottom:20px">📥 Import Data</h1>

<div class="card">
<div class="card-title">📦 Import Stock</div>
<p style="color:var(--muted);margin-bottom:15px">CSV format: code, description, category, qty, cost, price<br>Use comma or semicolon as separator</p>
<textarea id="stockCsv" class="input" rows="6" placeholder="SKU001,Castle Lager,Alcohol,24,15.00,25.00
SKU002,Coke 500ml,Beverages,48,8.00,15.00
SKU003,Chicken Burger,Food,0,25.00,55.00"></textarea>
<button class="btn" style="margin-top:10px" onclick="importStock()">📦 Import Stock</button>
<div id="stockResult" style="margin-top:10px"></div>
</div>

<div class="card">
<div class="card-title">👥 Import Customers</div>
<p style="color:var(--muted);margin-bottom:15px">CSV format: code, name, phone, email, address</p>
<textarea id="custCsv" class="input" rows="6" placeholder="C001,John Smith,0821234567,john@email.com,123 Main St
C002,Jane Doe,0839876543,jane@email.com,456 Oak Ave"></textarea>
<button class="btn" style="margin-top:10px" onclick="importCust()">👥 Import Customers</button>
<div id="custResult" style="margin-top:10px"></div>
</div>

<div class="card">
<div class="card-title">🚚 Import Suppliers</div>
<p style="color:var(--muted);margin-bottom:15px">CSV format: code, name, phone</p>
<textarea id="suppCsv" class="input" rows="6" placeholder="S001,ABC Distributors,0115551234
S002,XYZ Wholesalers,0125559876"></textarea>
<button class="btn" style="margin-top:10px" onclick="importSupp()">🚚 Import Suppliers</button>
<div id="suppResult" style="margin-top:10px"></div>
</div>

<div class="card">
<div class="card-title">📁 Upload CSV File</div>
<input type="file" id="csvFile" accept=".csv,.txt" class="input" onchange="loadFile()">
<select id="fileType" class="input" style="margin-top:10px">
<option value="stock">Stock</option>
<option value="customers">Customers</option>
<option value="suppliers">Suppliers</option>
</select>
<button class="btn" style="margin-top:10px" onclick="importFile()">📁 Import File</button>
</div>

<div class="card" style="border:2px solid var(--danger)">
<div class="card-title" style="color:var(--danger)">🗑️ CLEAR DATA (Delete Before Import)</div>
<p style="color:var(--muted);margin-bottom:15px">Delete existing data before importing fresh data</p>
<div style="display:flex;flex-wrap:wrap;gap:10px">
<button class="btn" style="background:var(--danger)" onclick="deleteAllStock()">🗑️ Delete All Stock</button>
<button class="btn" style="background:var(--danger)" onclick="deleteAllCustomers()">🗑️ Delete All Customers</button>
<button class="btn" style="background:var(--danger)" onclick="deleteAllSuppliers()">🗑️ Delete All Suppliers</button>
<button class="btn" style="background:#8b0000" onclick="deleteAllData()">💀 DELETE EVERYTHING</button>
</div>
<div id="deleteResult" style="margin-top:10px"></div>
</div>

<div class="card" style="border:2px solid var(--blue)">
<div class="card-title">🚀 BULK JSON IMPORT (All Data)</div>
<p style="color:var(--muted);margin-bottom:15px">Upload or paste your JSON file with stock, customers, suppliers, quotes, invoices</p>
<input type="file" id="jsonFile" accept=".json,.txt" class="input" onchange="loadJSONFile()" style="margin-bottom:10px">
<textarea id="jsonBulk" class="input" rows="10" placeholder='{{"stock":[...],"customers":[...],"suppliers":[...],"quotes":[...],"invoices":[...]}}'></textarea>
<button class="btn btn-primary" style="margin-top:10px;background:var(--blue)" onclick="importBulkJSON()">🚀 Import All Data</button>
<div id="bulkResult" style="margin-top:10px"></div>
</div>
</div>

<script>
function deleteAllStock(){{
    if(!confirm('DELETE ALL STOCK? This cannot be undone!'))return;
    fetch('/api/{bid}/delete/stock',{{method:'POST'}}).then(r=>r.json()).then(d=>{{
        document.getElementById('deleteResult').innerHTML=d.success?'<span style="color:var(--green)">✅ All stock deleted</span>':'<span style="color:var(--danger)">❌ '+d.error+'</span>';
    }});
}}
function deleteAllCustomers(){{
    if(!confirm('DELETE ALL CUSTOMERS? This cannot be undone!'))return;
    fetch('/api/{bid}/delete/customers',{{method:'POST'}}).then(r=>r.json()).then(d=>{{
        document.getElementById('deleteResult').innerHTML=d.success?'<span style="color:var(--green)">✅ All customers deleted</span>':'<span style="color:var(--danger)">❌ '+d.error+'</span>';
    }});
}}
function deleteAllSuppliers(){{
    if(!confirm('DELETE ALL SUPPLIERS? This cannot be undone!'))return;
    fetch('/api/{bid}/delete/suppliers',{{method:'POST'}}).then(r=>r.json()).then(d=>{{
        document.getElementById('deleteResult').innerHTML=d.success?'<span style="color:var(--green)">✅ All suppliers deleted</span>':'<span style="color:var(--danger)">❌ '+d.error+'</span>';
    }});
}}
function deleteAllData(){{
    if(!confirm('DELETE EVERYTHING? Stock, Customers, Suppliers, Quotes, Invoices, Ledger - ALL GONE!'))return;
    if(!confirm('ARE YOU SURE? Type business name to confirm: {bid}'))return;
    fetch('/api/{bid}/delete/all',{{method:'POST'}}).then(r=>r.json()).then(d=>{{
        document.getElementById('deleteResult').innerHTML=d.success?'<span style="color:var(--green)">✅ Everything deleted - ready for fresh import</span>':'<span style="color:var(--danger)">❌ '+d.error+'</span>';
    }});
}}
function parseCSV(text){{
    var lines=text.trim().split('\\n');
    return lines.map(function(line){{
        var result=[];var cell='';var inQuotes=false;
        for(var i=0;i<line.length;i++){{
            var c=line[i];
            if(c==='"')inQuotes=!inQuotes;
            else if((c===','||c===';')&&!inQuotes){{result.push(cell.trim());cell='';}}
            else cell+=c;
        }}
        result.push(cell.trim());
        return result;
    }});
}}

function importStock(){{
    var csv=document.getElementById('stockCsv').value;
    var rows=parseCSV(csv);
    var items=rows.filter(r=>r.length>=6&&r[0]).map(function(r){{
        return {{code:r[0],description:r[1],category:r[2]||'General',qty:parseInt(r[3])||0,cost:parseFloat(r[4])||0,price:parseFloat(r[5])||0}};
    }});
    if(!items.length)return alert('No valid rows found');
    document.getElementById('stockResult').innerHTML='<span style="color:var(--blue)">⏳ Importing...</span>';
    fetch('/api/{bid}/stock/import',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{items:items}})}})
    .then(r=>r.json()).then(d=>{{
        document.getElementById('stockResult').innerHTML='<span style="color:var(--green)">✅ Imported '+d.count+' items</span>';
    }});
}}

function importCust(){{
    var csv=document.getElementById('custCsv').value;
    var rows=parseCSV(csv);
    var items=rows.filter(r=>r.length>=2&&r[1]).map(function(r){{
        return {{code:r[0]||'',name:r[1]||'',phone:r[2]||'',email:r[3]||'',address:r[4]||''}};
    }});
    if(!items.length)return alert('No valid rows');
    document.getElementById('custResult').innerHTML='<span style="color:var(--blue)">⏳ Importing...</span>';
    fetch('/api/{bid}/customer/import',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{items:items}})}})
    .then(r=>r.json()).then(d=>{{
        document.getElementById('custResult').innerHTML='<span style="color:var(--green)">✅ Imported '+d.count+' customers</span>';
    }});
}}

function importSupp(){{
    var csv=document.getElementById('suppCsv').value;
    var rows=parseCSV(csv);
    var items=rows.filter(r=>r.length>=2&&r[1]).map(function(r){{
        return {{code:r[0]||'',name:r[1]||'',phone:r[2]||''}};
    }});
    if(!items.length)return alert('No valid rows');
    document.getElementById('suppResult').innerHTML='<span style="color:var(--blue)">⏳ Importing...</span>';
    fetch('/api/{bid}/supplier/import',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{items:items}})}})
    .then(r=>r.json()).then(d=>{{
        document.getElementById('suppResult').innerHTML='<span style="color:var(--green)">✅ Imported '+d.count+' suppliers</span>';
    }});
}}

var fileContent='';
function loadFile(){{
    var file=document.getElementById('csvFile').files[0];
    if(!file)return;
    var reader=new FileReader();
    reader.onload=function(e){{fileContent=e.target.result;}};
    reader.readAsText(file);
}}

function importFile(){{
    if(!fileContent)return alert('Select a file first');
    var type=document.getElementById('fileType').value;
    if(type==='stock'){{document.getElementById('stockCsv').value=fileContent;importStock();}}
    else if(type==='customers'){{document.getElementById('custCsv').value=fileContent;importCust();}}
    else{{document.getElementById('suppCsv').value=fileContent;importSupp();}}
}}

function importBulkJSON(){{
    var json=document.getElementById('jsonBulk').value;
    if(!json)return alert('Paste JSON data first');
    try{{JSON.parse(json);}}catch(e){{return alert('Invalid JSON: '+e.message);}}
    document.getElementById('bulkResult').innerHTML='<span style="color:var(--blue)">⏳ Importing all data...</span>';
    fetch('/api/{bid}/import/all',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:json}})
    .then(r=>r.json()).then(d=>{{
        if(d.error){{document.getElementById('bulkResult').innerHTML='<span style="color:var(--red)">❌ '+d.error+'</span>';return;}}
        var msg='<span style="color:var(--green)">✅ Import Complete:<br>';
        msg+='📦 Stock: '+d.stock+'<br>';
        msg+='👥 Customers: '+d.customers+'<br>';
        msg+='🚚 Suppliers: '+d.suppliers+'<br>';
        msg+='📋 Quotes: '+d.quotes+'<br>';
        msg+='🧾 Invoices: '+d.invoices+'</span>';
        document.getElementById('bulkResult').innerHTML=msg;
    }}).catch(e=>{{document.getElementById('bulkResult').innerHTML='<span style="color:var(--red)">❌ Error: '+e+'</span>';}});
}}

function loadJSONFile(){{
    var file=document.getElementById('jsonFile').files[0];
    if(!file)return;
    var reader=new FileReader();
    reader.onload=function(e){{
        document.getElementById('jsonBulk').value=e.target.result;
        document.getElementById('bulkResult').innerHTML='<span style="color:var(--green)">✅ File loaded - click Import All Data</span>';
    }};
    reader.readAsText(file);
}}
</script>
</body></html>'''

@app.route("/<bid>/settings")
def settings_page(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    s = business.get("settings", {})
    if isinstance(s, str):
        try: s = json.loads(s)
        except: s = {}
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Settings</title>{CSS}</head><body>
{get_header(bid, "settings")}
<div class="container"><h1 style="font-size:24px;margin-bottom:20px">⚙️ Settings</h1>
<div class="card"><div class="card-title">🏢 Company</div><div class="form-row"><div class="form-group"><label class="form-label">Company Name</label><input type="text" class="input" id="company_name" value="{s.get('company_name','')}"></div><div class="form-group"><label class="form-label">Trading As</label><input type="text" class="input" id="trading_as" value="{s.get('trading_as','')}"></div></div><div class="form-row"><div class="form-group"><label class="form-label">Reg Number</label><input type="text" class="input" id="reg_number" value="{s.get('reg_number','')}"></div><div class="form-group"><label class="form-label">VAT Number</label><input type="text" class="input" id="vat_number" value="{s.get('vat_number','')}"></div></div><div class="form-group"><label class="form-label">Address</label><textarea class="input" id="address" rows="2">{s.get('address','')}</textarea></div><div class="form-row"><div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="phone" value="{s.get('phone','')}"></div><div class="form-group"><label class="form-label">Email</label><input type="email" class="input" id="email" value="{s.get('email','')}"></div></div></div>
<div class="card"><div class="card-title">🏦 Banking</div><div class="form-row"><div class="form-group"><label class="form-label">Bank</label><input type="text" class="input" id="bank_name" value="{s.get('bank_name','')}"></div><div class="form-group"><label class="form-label">Account</label><input type="text" class="input" id="bank_account" value="{s.get('bank_account','')}"></div><div class="form-group"><label class="form-label">Branch</label><input type="text" class="input" id="bank_branch" value="{s.get('bank_branch','')}"></div></div></div>
<div class="card"><div class="card-title">📋 Defaults</div><div class="form-row-4"><div class="form-group"><label class="form-label">VAT %</label><input type="number" class="input" id="vat_rate" value="{s.get('vat_rate',15)}"></div><div class="form-group"><label class="form-label">Markup %</label><input type="number" class="input" id="default_markup" value="{s.get('default_markup',50)}"></div><div class="form-group"><label class="form-label">Low Stock</label><input type="number" class="input" id="low_stock_threshold" value="{s.get('low_stock_threshold',5)}"></div><div class="form-group"><label class="form-label">Currency</label><input type="text" class="input" id="currency" value="{s.get('currency','R')}"></div></div><div class="form-row-4"><div class="form-group"><label class="form-label">Invoice Prefix</label><input type="text" class="input" id="invoice_prefix" value="{s.get('invoice_prefix','INV')}"></div><div class="form-group"><label class="form-label">Quote Prefix</label><input type="text" class="input" id="quote_prefix" value="{s.get('quote_prefix','QT')}"></div><div class="form-group"><label class="form-label">CN Prefix</label><input type="text" class="input" id="credit_note_prefix" value="{s.get('credit_note_prefix','CN')}"></div><div class="form-group"><label class="form-label">DN Prefix</label><input type="text" class="input" id="delivery_note_prefix" value="{s.get('delivery_note_prefix','DN')}"></div></div></div>
<button class="btn" style="width:100%;margin-bottom:20px" onclick="save()">💾 Save Settings</button>
<div class="card" style="border-color:var(--red)"><div class="card-title" style="color:var(--red)">⚠️ Danger</div><button class="btn btn-red" onclick="del()">Delete Business</button></div></div>
<script>function save(){{var d={{company_name:document.getElementById('company_name').value,trading_as:document.getElementById('trading_as').value,reg_number:document.getElementById('reg_number').value,vat_number:document.getElementById('vat_number').value,address:document.getElementById('address').value,phone:document.getElementById('phone').value,email:document.getElementById('email').value,bank_name:document.getElementById('bank_name').value,bank_account:document.getElementById('bank_account').value,bank_branch:document.getElementById('bank_branch').value,vat_rate:parseInt(document.getElementById('vat_rate').value)||15,default_markup:parseInt(document.getElementById('default_markup').value)||50,low_stock_threshold:parseInt(document.getElementById('low_stock_threshold').value)||5,currency:document.getElementById('currency').value||'R',invoice_prefix:document.getElementById('invoice_prefix').value,quote_prefix:document.getElementById('quote_prefix').value,credit_note_prefix:document.getElementById('credit_note_prefix').value,delivery_note_prefix:document.getElementById('delivery_note_prefix').value}};fetch('/api/{bid}/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{if(x.success)alert('Saved!')}})}}function del(){{if(!confirm('DELETE BUSINESS?'))return;fetch('/api/{bid}',{{method:'DELETE'}}).then(r=>r.json()).then(x=>{{if(x.success)location.href='/'}})}}</script></body></html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# END OF PART 3 - Paste Part 4 below this line
# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# CLICK AI v5 - PART 4 of 4 (FINAL)
# Mobile | Reports | Statements | ALL APIs | Export | Run
# Paste below Part 3
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/m/<bid>")
def mobile(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    business = result["data"][0]
    s = business.get("settings", {})
    if isinstance(s, str):
        try: s = json.loads(s)
        except: s = {}
    name = s.get("company_name") or business.get("name", "Business")
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><title>Click AI</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,sans-serif;background:#050508;color:#fff;min-height:100vh;display:flex;flex-direction:column}}.top{{padding:20px;text-align:center;border-bottom:1px solid #1a1a2f}}.logo{{font-size:28px;font-weight:900;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}.bn{{color:#6b7280;font-size:16px;margin-top:8px}}.main{{flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;gap:18px;padding:20px}}.big{{width:85%;max-width:300px;padding:30px 20px;border-radius:20px;display:flex;flex-direction:column;align-items:center;gap:10px;cursor:pointer;font-weight:800;font-size:20px;transition:all 0.2s}}.stock{{background:rgba(59,130,246,0.15);border:3px solid rgba(59,130,246,0.5);color:#3b82f6}}.expense{{background:rgba(239,68,68,0.15);border:3px solid rgba(239,68,68,0.5);color:#ef4444}}.cos{{background:rgba(245,158,11,0.15);border:3px solid rgba(245,158,11,0.5);color:#f59e0b}}.big:active{{transform:scale(0.95)}}.icon{{font-size:50px}}.sub{{font-size:13px;font-weight:400;color:#6b7280}}input[type=file]{{display:none}}.ov{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.95);z-index:100;flex-direction:column;align-items:center;justify-content:center;padding:25px}}.ov.show{{display:flex}}.spin{{width:50px;height:50px;border:4px solid #333;border-top-color:#3b82f6;border-radius:50%;animation:spin 1s linear infinite}}@keyframes spin{{to{{transform:rotate(360deg)}}}}.rbox{{background:#0d0d14;border:1px solid #1a1a2f;border-radius:16px;padding:20px;width:100%;max-width:340px}}.rrow{{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #1a1a2f;font-size:15px}}.rrow:last-child{{border:none}}.inp{{width:100%;padding:14px;background:rgba(255,255,255,0.05);border:2px solid #1a1a2f;border-radius:10px;color:#fff;font-size:16px;margin-bottom:12px}}.btnr{{display:flex;gap:12px;margin-top:20px;width:100%;max-width:340px}}.abtn{{flex:1;padding:16px;border-radius:12px;font-size:17px;font-weight:700;cursor:pointer;border:none}}.ebtn{{background:#3b82f6;color:#fff}}.sbtn{{background:#10b981;color:#fff}}.cbtn{{background:#6b7280;color:#fff}}.vmod{{background:#0d0d14;border:1px solid #1a1a2f;border-radius:20px;padding:25px;width:90%;max-width:340px;text-align:center}}.vbtn{{width:100%;padding:18px;margin:8px 0;border-radius:12px;font-size:18px;font-weight:700;cursor:pointer;border:none}}.vy{{background:#10b981;color:#fff}}.vn{{background:#ef4444;color:#fff}}.dlink{{position:fixed;bottom:15px;color:#6b7280;font-size:13px;text-decoration:none}}</style></head><body>
<div class="top"><div class="logo">⚡ Click AI</div><div class="bn">{name}</div></div>
<div class="main"><div class="big stock" onclick="cap('stock')"><div class="icon">📦</div><div>STOCK</div><div class="sub">Supplier Invoice</div></div><div class="big expense" onclick="cap('expense')"><div class="icon">💸</div><div>EXPENSE</div><div class="sub">Receipt</div></div><div class="big cos" onclick="cap('cos')"><div class="icon">🏷️</div><div>COS</div><div class="sub">Cost of Sales</div></div></div>
<input type="file" id="cam" accept="image/*" capture="environment" onchange="proc(this)">
<div class="ov" id="load"><div class="spin"></div><div style="margin-top:20px;color:#6b7280">AI Processing...</div></div>
<div class="ov" id="vat"><div class="vmod"><div style="font-size:22px;margin-bottom:15px">🏛️ VAT?</div><div style="color:#6b7280;margin-bottom:20px">Does this include VAT?</div><button class="vbtn vy" onclick="setVat(true)">✓ YES</button><button class="vbtn vn" onclick="setVat(false)">✗ NO</button></div></div>
<div class="ov" id="result"><div style="font-size:50px;margin-bottom:15px" id="ricon">✅</div><div style="font-size:24px;font-weight:700;margin-bottom:20px">Captured!</div><div class="rbox" id="rbox"></div><div class="btnr"><button class="abtn ebtn" onclick="showEdit()">✏️ Edit</button><button class="abtn sbtn" onclick="submit()">✓ Submit</button></div></div>
<div class="ov" id="edit"><div class="vmod" style="text-align:left"><div style="font-size:20px;font-weight:700;margin-bottom:20px;text-align:center">✏️ Edit</div><label style="color:#6b7280;font-size:13px">Supplier</label><input class="inp" id="eSupp"><label style="color:#6b7280;font-size:13px">Description</label><input class="inp" id="eDesc"><label style="color:#6b7280;font-size:13px">Amount</label><input class="inp" type="number" step="0.01" id="eAmt"><div class="btnr"><button class="abtn cbtn" onclick="hideEdit()">Cancel</button><button class="abtn sbtn" onclick="saveEdit()">Save</button></div></div></div>
<div class="ov" id="done"><div style="font-size:60px">✅</div><div style="font-size:24px;font-weight:700;margin:20px 0">Posted!</div><button class="abtn sbtn" style="width:200px" onclick="reset()">Done</button></div>
<a href="/{bid}?desktop=1" class="dlink">Desktop →</a>
<script>var mode='',pending=null,hasVat=true;function cap(m){{mode=m;document.getElementById('cam').click()}}function proc(inp){{if(!inp.files[0])return;show('load');var r=new FileReader();r.onload=function(e){{var b64=e.target.result.split(',')[1];fetch('/api/{bid}/mobile/scan',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{image:b64,mode:mode}})}}).then(x=>x.json()).then(d=>{{hide('load');if(d.success){{pending=d;showResult()}}else alert(d.error||'Error')}}).catch(()=>{{hide('load');alert('Error')}})}};r.readAsDataURL(inp.files[0])}}function showResult(){{document.getElementById('ricon').textContent=mode==='stock'?'📦':mode==='cos'?'🏷️':'💸';var h='<div class="rrow"><span>Supplier</span><span>'+(pending.supplier||'—')+'</span></div><div class="rrow"><span>Description</span><span>'+(pending.description||'—')+'</span></div><div class="rrow"><span>Amount</span><span>R '+(pending.amount||0).toFixed(2)+'</span></div>';document.getElementById('rbox').innerHTML=h;if(pending.ask_vat)show('vat');else show('result')}}function setVat(v){{hasVat=v;hide('vat');show('result')}}function showEdit(){{document.getElementById('eSupp').value=pending.supplier||'';document.getElementById('eDesc').value=pending.description||'';document.getElementById('eAmt').value=pending.amount||0;show('edit')}}function hideEdit(){{hide('edit')}}function saveEdit(){{pending.supplier=document.getElementById('eSupp').value;pending.description=document.getElementById('eDesc').value;pending.amount=parseFloat(document.getElementById('eAmt').value)||0;hide('edit');showResult()}}function submit(){{hide('result');show('load');fetch('/api/{bid}/mobile/post',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{mode:mode,supplier:pending.supplier,description:pending.description,amount:pending.amount,has_vat:hasVat}})}}).then(x=>x.json()).then(d=>{{hide('load');if(d.success)show('done');else alert(d.error||'Error')}})}}function reset(){{hide('done');pending=null;hasVat=true;document.getElementById('cam').value=''}}function show(id){{document.getElementById(id).classList.add('show')}}function hide(id){{document.getElementById(id).classList.remove('show')}}</script></body></html>'''

@app.route("/<bid>/report/pnl")
def report_pnl(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    ledger = sb.table("ledger").select("*").eq("business_id", bid).execute()["data"] or []
    income = sum(float(e.get("credit", 0)) for e in ledger if e.get("account", "").startswith("4"))
    cos = sum(float(e.get("debit", 0)) for e in ledger if e.get("account", "").startswith("5"))
    exp = sum(float(e.get("debit", 0)) for e in ledger if e.get("account", "").startswith(("6", "7")))
    gross = income - cos
    net = gross - exp
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>P&L</title>{CSS}</head><body>{get_header(bid, "reports")}<div class="container"><h1 style="font-size:24px;margin-bottom:20px">📈 Profit & Loss</h1><div class="card"><table><tr><td style="font-weight:700;font-size:16px">Sales</td><td style="text-align:right;color:var(--green);font-size:16px">R {income:,.2f}</td></tr><tr><td>Cost of Sales</td><td style="text-align:right;color:var(--red)">R {cos:,.2f}</td></tr><tr style="border-top:2px solid var(--blue)"><td style="font-weight:700">Gross Profit</td><td style="text-align:right;font-weight:700">R {gross:,.2f}</td></tr><tr><td>Expenses</td><td style="text-align:right;color:var(--red)">R {exp:,.2f}</td></tr><tr style="border-top:2px solid var(--blue);background:rgba(59,130,246,0.1)"><td style="font-weight:900;font-size:20px">Net Profit</td><td style="text-align:right;font-weight:900;font-size:20px;color:{'var(--green)' if net>=0 else 'var(--red)'}">R {net:,.2f}</td></tr></table></div></div></body></html>'''

@app.route("/<bid>/report/vat")
def report_vat(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    ledger = sb.table("ledger").select("*").eq("business_id", bid).execute()["data"] or []
    vo = sum(float(e.get("credit", 0)) for e in ledger if e.get("account") == "2200")
    vi = sum(float(e.get("debit", 0)) for e in ledger if e.get("account") == "2100")
    net = vo - vi
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>VAT</title>{CSS}</head><body>{get_header(bid, "reports")}<div class="container"><h1 style="font-size:24px;margin-bottom:20px">🏛️ VAT Report</h1><div class="card"><table><tr><td style="font-weight:700">VAT Output (Sales)</td><td style="text-align:right;color:var(--green);font-size:16px">R {vo:,.2f}</td></tr><tr><td style="font-weight:700">VAT Input (Purchases)</td><td style="text-align:right;color:var(--red);font-size:16px">R {vi:,.2f}</td></tr><tr style="border-top:2px solid var(--blue);background:rgba(59,130,246,0.1)"><td style="font-weight:900;font-size:18px">{'Payable to SARS' if net>0 else 'Refund'}</td><td style="text-align:right;font-weight:900;font-size:20px;color:{'var(--red)' if net>0 else 'var(--green)'}">R {abs(net):,.2f}</td></tr></table></div></div></body></html>'''

@app.route("/<bid>/report/ledger")
def report_ledger(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    ledger = sb.table("ledger").select("*").eq("business_id", bid).order("created_at", desc=True).limit(200).execute()["data"] or []
    rows = ""
    for e in ledger:
        acc = e.get("account", "")
        rows += f'<tr><td>{e.get("date", "")[:10]}</td><td><span class="badge badge-blue">{e.get("ref", "")}</span></td><td><span class="badge badge-purple">{acc}</span> {ACCOUNTS.get(acc, ("",))[0]}</td><td>{e.get("description", "")[:35]}</td><td style="color:var(--green)">R {float(e.get("debit", 0)):,.2f}</td><td style="color:var(--red)">R {float(e.get("credit", 0)):,.2f}</td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No transactions</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Ledger</title>{CSS}</head><body>{get_header(bid, "reports")}<div class="container"><h1 style="font-size:24px;margin-bottom:20px">📒 General Ledger</h1><div class="card"><div class="table-container"><table><thead><tr><th>Date</th><th>Ref</th><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

@app.route("/<bid>/report/debtors")
def report_debtors(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    customers = sb.table("customers").select("*").eq("business_id", bid).execute()["data"] or []
    rows = ""
    total = 0
    for c in customers:
        bal = float(c.get("balance", 0) or 0)
        if bal > 0:
            total += bal
            rows += f'<tr><td>{c.get("code","")}</td><td><strong>{c.get("name","")}</strong></td><td>{c.get("phone","")}</td><td style="color:var(--red);font-weight:700">R {bal:,.2f}</td><td><a href="/{bid}/customer/{c.get("id","")}/statement" class="btn btn-xs btn-blue">Statement</a></td></tr>'
    if not rows: rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:40px">No debtors</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Debtors</title>{CSS}</head><body>{get_header(bid, "reports")}<div class="container"><h1 style="font-size:24px;margin-bottom:20px">💰 Debtors Age</h1><div class="stats-grid"><div class="stat-card alert"><div class="stat-value">R {total:,.2f}</div><div class="stat-label">Total Owing</div></div></div><div class="card"><div class="table-container"><table><thead><tr><th>Code</th><th>Customer</th><th>Phone</th><th>Balance</th><th></th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

@app.route("/<bid>/report/creditors")
def report_creditors(bid):
    result = sb.table("businesses").select("*").eq("id", bid).execute()
    if not result["data"]: return redirect("/")
    suppliers = sb.table("suppliers").select("*").eq("business_id", bid).execute()["data"] or []
    rows = ""
    total = 0
    for s in suppliers:
        bal = float(s.get("balance", 0) or 0)
        if bal > 0:
            total += bal
            rows += f'<tr><td>{s.get("code","")}</td><td><strong>{s.get("name","")}</strong></td><td>{s.get("phone","")}</td><td style="color:var(--red);font-weight:700">R {bal:,.2f}</td><td><a href="/{bid}/supplier/{s.get("id","")}/statement" class="btn btn-xs btn-blue">Statement</a></td></tr>'
    if not rows: rows = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:40px">No creditors</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Creditors</title>{CSS}</head><body>{get_header(bid, "reports")}<div class="container"><h1 style="font-size:24px;margin-bottom:20px">💸 Creditors Age</h1><div class="stats-grid"><div class="stat-card alert"><div class="stat-value">R {total:,.2f}</div><div class="stat-label">You Owe</div></div></div><div class="card"><div class="table-container"><table><thead><tr><th>Code</th><th>Supplier</th><th>Phone</th><th>Balance</th><th></th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

@app.route("/<bid>/customer/<cid>/statement")
def customer_statement(bid, cid):
    cust = sb.table("customers").select("*").eq("id", cid).execute()["data"]
    if not cust: return redirect(f"/{bid}/customers")
    c = cust[0]
    invoices = sb.table("invoices").select("*").eq("business_id", bid).eq("customer_id", cid).order("created_at").execute()["data"] or []
    ledger = sb.table("ledger").select("*").eq("business_id", bid).order("created_at").execute()["data"] or []
    rows = ""
    bal = 0
    for inv in invoices:
        amt = float(inv.get("total", 0))
        bal += amt
        rows += f'<tr><td>{inv.get("date","")[:10]}</td><td>{inv.get("number","")}</td><td>Invoice</td><td style="color:var(--red)">R {amt:,.2f}</td><td></td><td>R {bal:,.2f}</td></tr>'
    for e in ledger:
        if c.get("name","") in e.get("description","") and e.get("account")=="1000" and float(e.get("debit",0))>0:
            amt = float(e.get("debit", 0))
            bal -= amt
            rows += f'<tr><td>{e.get("date","")[:10]}</td><td>{e.get("ref","")}</td><td>Payment</td><td></td><td style="color:var(--green)">R {amt:,.2f}</td><td>R {bal:,.2f}</td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No transactions</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Statement</title>{CSS}</head><body>{get_header(bid, "customers")}<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px"><div><h1 style="font-size:24px">📄 Statement</h1><div style="color:var(--muted)">{c.get("name","")} ({c.get("code","")})</div></div><div class="stat-card" style="margin:0"><div class="stat-value">R {float(c.get("balance",0)):,.2f}</div><div class="stat-label">Balance</div></div></div><div class="card"><div class="table-container"><table><thead><tr><th>Date</th><th>Ref</th><th>Type</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

@app.route("/<bid>/supplier/<sid>/statement")
def supplier_statement(bid, sid):
    supp = sb.table("suppliers").select("*").eq("id", sid).execute()["data"]
    if not supp: return redirect(f"/{bid}/suppliers")
    s = supp[0]
    ledger = sb.table("ledger").select("*").eq("business_id", bid).order("created_at").execute()["data"] or []
    rows = ""
    bal = 0
    for e in ledger:
        if s.get("name","").lower() in e.get("description","").lower() and e.get("account")=="2000":
            if float(e.get("credit",0))>0:
                amt = float(e.get("credit",0))
                bal += amt
                rows += f'<tr><td>{e.get("date","")[:10]}</td><td>{e.get("ref","")}</td><td>Purchase</td><td style="color:var(--red)">R {amt:,.2f}</td><td></td><td>R {bal:,.2f}</td></tr>'
            elif float(e.get("debit",0))>0:
                amt = float(e.get("debit",0))
                bal -= amt
                rows += f'<tr><td>{e.get("date","")[:10]}</td><td>{e.get("ref","")}</td><td>Payment</td><td></td><td style="color:var(--green)">R {amt:,.2f}</td><td>R {bal:,.2f}</td></tr>'
    if not rows: rows = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:40px">No transactions</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Statement</title>{CSS}</head><body>{get_header(bid, "suppliers")}<div class="container"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px"><div><h1 style="font-size:24px">📄 Statement</h1><div style="color:var(--muted)">{s.get("name","")} ({s.get("code","")})</div></div><div class="stat-card" style="margin:0"><div class="stat-value">R {float(s.get("balance",0)):,.2f}</div><div class="stat-label">Balance</div></div></div><div class="card"><div class="table-container"><table><thead><tr><th>Date</th><th>Ref</th><th>Type</th><th>Debit</th><th>Credit</th><th>Balance</th></tr></thead><tbody>{rows}</tbody></table></div></div></div></body></html>'''

@app.route("/<bid>/export/csv")
def export_csv(bid):
    ledger = sb.table("ledger").select("*").eq("business_id", bid).order("created_at").execute()["data"] or []
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date","Ref","Account","Description","Debit","Credit"])
    for e in ledger:
        writer.writerow([e.get("date","")[:10],e.get("ref",""),e.get("account",""),e.get("description",""),e.get("debit",0),e.get("credit",0)])
    return Response(output.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment;filename=ledger_{bid}.csv"})

# ═══════════════════════════════════════════════════════════════════════════════
# ALL APIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/status")
def api_status():
    sb_ok=False
    err=""
    try:
        r=sb.table("businesses").select("id").limit(1).execute()
        sb_ok=r["error"]is None
        if r["error"]:err=str(r["error"])[:100]
    except Exception as e:
        err=str(e)[:100]
    return jsonify({"supabase":sb_ok,"url":SUPABASE_URL,"error":err,"anthropic":bool(ANTHROPIC_API_KEY)})

@app.route("/api/business",methods=["POST"])
def api_create_business():
    d=request.get_json();name=d.get("name","").strip()
    if not name:return jsonify({"success":False,"error":"Name required"})
    bid=str(uuid.uuid4())
    sb.table("businesses").insert({"id":bid,"name":name,"settings":json.dumps({"company_name":name})}).execute()
    return jsonify({"success":True,"id":bid})

@app.route("/api/<bid>/settings",methods=["POST"])
def api_settings(bid):
    sb.table("businesses").eq("id",bid).update({"settings":json.dumps(request.get_json())}).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>",methods=["DELETE"])
def api_del_biz(bid):
    for t in["ledger","stock","customers","suppliers","invoices","quotes"]:sb.table(t).eq("business_id",bid).delete().execute()
    sb.table("businesses").eq("id",bid).delete().execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/stock",methods=["POST"])
def api_stock(bid):
    d=request.get_json()
    item={"business_id":bid,"code":d.get("code",""),"description":d.get("description",""),"category":d.get("category","General"),"qty":d.get("qty",0),"cost":d.get("cost",0),"price":d.get("price",0)}
    if d.get("id"):sb.table("stock").eq("id",d["id"]).update(item).execute()
    else:item["id"]=str(uuid.uuid4());sb.table("stock").insert(item).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/stock/adjust",methods=["POST"])
def api_stock_adj(bid):
    d=request.get_json();stock=sb.table("stock").select("*").eq("id",d["id"]).execute()["data"]
    if stock:
        nq=int(stock[0].get("qty",0))+int(d.get("adjustment",0))
        sb.table("stock").eq("id",d["id"]).update({"qty":nq}).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/stock/import",methods=["POST"])
def api_stock_import(bid):
    d=request.get_json()
    items=d.get("items",[])
    count=0
    for item in items:
        item["id"]=str(uuid.uuid4())
        item["business_id"]=bid
        item["qty"]=int(item.get("qty",0))
        item["cost"]=float(item.get("cost",0))
        item["price"]=float(item.get("price",0))
        r=sb.table("stock").insert(item).execute()
        if not r.get("error"):count+=1
    return jsonify({"success":True,"count":count})

@app.route("/api/<bid>/customer/import",methods=["POST"])
def api_customer_import(bid):
    d=request.get_json()
    items=d.get("items",[])
    count=0
    for item in items:
        item["id"]=str(uuid.uuid4())
        item["business_id"]=bid
        item["balance"]=0
        r=sb.table("customers").insert(item).execute()
        if not r.get("error"):count+=1
    return jsonify({"success":True,"count":count})

@app.route("/api/<bid>/supplier/import",methods=["POST"])
def api_supplier_import(bid):
    d=request.get_json()
    items=d.get("items",[])
    count=0
    for item in items:
        item["id"]=str(uuid.uuid4())
        item["business_id"]=bid
        item["balance"]=0
        r=sb.table("suppliers").insert(item).execute()
        if not r.get("error"):count+=1
    return jsonify({"success":True,"count":count})

# ═══════════════════════════════════════════════════════════════════════════════
# DELETE ALL DATA - Clear tables for fresh import
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/<bid>/delete/stock",methods=["POST"])
def api_delete_all_stock(bid):
    """Delete ALL stock for this business"""
    try:
        # Delete all stock where business_id matches
        r = sb.table("stock").eq("business_id", bid).delete()
        return jsonify({"success": True, "message": "All stock deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/<bid>/delete/customers",methods=["POST"])
def api_delete_all_customers(bid):
    """Delete ALL customers for this business"""
    try:
        r = sb.table("customers").eq("business_id", bid).delete()
        return jsonify({"success": True, "message": "All customers deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/<bid>/delete/suppliers",methods=["POST"])
def api_delete_all_suppliers(bid):
    """Delete ALL suppliers for this business"""
    try:
        r = sb.table("suppliers").eq("business_id", bid).delete()
        return jsonify({"success": True, "message": "All suppliers deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/<bid>/delete/all",methods=["POST"])
def api_delete_all_data(bid):
    """Delete ALL data for this business (stock, customers, suppliers)"""
    try:
        sb.table("stock").eq("business_id", bid).delete()
        sb.table("customers").eq("business_id", bid).delete()
        sb.table("suppliers").eq("business_id", bid).delete()
        sb.table("quotes").eq("business_id", bid).delete()
        sb.table("invoices").eq("business_id", bid).delete()
        sb.table("ledger").eq("business_id", bid).delete()
        return jsonify({"success": True, "message": "All data deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ═══════════════════════════════════════════════════════════════════════════════
# BULK JSON IMPORT - ALL DATA IN ONE GO
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/api/<bid>/import/all",methods=["POST"])
def api_import_all(bid):
    try:
        d=request.get_json()
        counts={"stock":0,"customers":0,"suppliers":0,"quotes":0,"invoices":0}
        
        # Handle nested format: {"hardware": {"stock":[], ...}, "pub": {...}}
        # Find the right source data
        source = d
        if not isinstance(d.get("stock"), list) and not isinstance(d.get("customers"), list):
            # Not flat format - look for nested business data
            for key in [bid, "hardware", "pub", "bnb", "stainless", "fulltech"]:
                if key in d and isinstance(d[key], dict):
                    if "stock" in d[key] or "customers" in d[key] or "suppliers" in d[key]:
                        source = d[key]
                        break
            # If still not found, try first dict that has stock/customers
            if source == d:
                for key, val in d.items():
                    if isinstance(val, dict) and ("stock" in val or "customers" in val):
                        source = val
                        break
        
        # Import Stock (handle both 'price' and 'sell' field names)
        for item in source.get("stock",[]):
            price = item.get("price", 0) or item.get("sell", 0) or 0
            rec={"id":str(uuid.uuid4()),"business_id":bid,"code":item.get("code",""),"description":item.get("description",""),"category":item.get("category","General"),"qty":int(item.get("qty",0) or 0),"cost":float(item.get("cost",0) or 0),"price":float(price)}
            r=sb.table("stock").insert(rec)
            if not r.get("error"):counts["stock"]+=1
        
        # Import Customers
        for item in source.get("customers",[]):
            rec={"id":str(uuid.uuid4()),"business_id":bid,"code":item.get("code",""),"name":item.get("name",""),"phone":item.get("phone",""),"email":item.get("email",""),"address":item.get("address",""),"balance":0}
            r=sb.table("customers").insert(rec)
            if not r.get("error"):counts["customers"]+=1
        
        # Import Suppliers
        for item in source.get("suppliers",[]):
            rec={"id":str(uuid.uuid4()),"business_id":bid,"code":item.get("code",""),"name":item.get("name",""),"phone":item.get("phone",""),"balance":0}
            r=sb.table("suppliers").insert(rec)
            if not r.get("error"):counts["suppliers"]+=1
        
        # Import Quotes
        for item in source.get("quotes",[]):
            rec={"id":str(uuid.uuid4()),"business_id":bid,"number":item.get("number",""),"customer_code":item.get("customer_code",""),"customer_name":item.get("customer_name",""),"customer_phone":item.get("customer_phone",""),"items":item.get("items",[]),"subtotal":float(item.get("subtotal",0)),"vat":float(item.get("vat",0)),"total":float(item.get("total",0)),"date":item.get("date",today_iso()),"status":item.get("status","draft"),"converted_to":item.get("converted_to",""),"created_at":item.get("created_at",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
            r=sb.table("quotes").insert(rec).execute()
            if not r.get("error"):counts["quotes"]+=1
        
        # Import Invoices
        for item in source.get("invoices",[]):
            rec={"id":str(uuid.uuid4()),"business_id":bid,"number":item.get("number",""),"customer_code":item.get("customer_code",""),"customer_name":item.get("customer_name",""),"customer_phone":item.get("customer_phone",""),"items":item.get("items",[]),"subtotal":float(item.get("subtotal",0)),"vat":float(item.get("vat",0)),"total":float(item.get("total",0)),"date":item.get("date",today_iso()),"status":item.get("status","unpaid"),"from_quote":item.get("from_quote",""),"paid_date":item.get("paid_date",""),"created_at":item.get("created_at",datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}
            r=sb.table("invoices").insert(rec).execute()
            if not r.get("error"):counts["invoices"]+=1
        
        return jsonify(counts)
    except Exception as e:
        return jsonify({"error":str(e)})

@app.route("/api/<bid>/customer",methods=["POST"])
def api_cust(bid):
    d=request.get_json()
    item={"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email",""),"address":d.get("address","")}
    if d.get("id"):sb.table("customers").eq("id",d["id"]).update(item).execute()
    else:item["id"]=str(uuid.uuid4());item["balance"]=0;sb.table("customers").insert(item).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/customer/receive",methods=["POST"])
def api_cust_rec(bid):
    d=request.get_json();cust=sb.table("customers").select("*").eq("id",d["id"]).execute()["data"]
    if cust:
        c=cust[0];amt=float(d.get("amount",0));nb=float(c.get("balance",0))-amt
        sb.table("customers").eq("id",d["id"]).update({"balance":nb}).execute()
        ref=f"REC{uuid.uuid4().hex[:6].upper()}"
        sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"1000","description":f"Payment from {c.get('name','')}","debit":amt,"credit":0}).execute()
        sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"1200","description":f"Payment from {c.get('name','')}","debit":0,"credit":amt}).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/supplier",methods=["POST"])
def api_supp(bid):
    d=request.get_json()
    item={"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone","")}
    if d.get("id"):sb.table("suppliers").eq("id",d["id"]).update(item).execute()
    else:item["id"]=str(uuid.uuid4());item["balance"]=0;sb.table("suppliers").insert(item).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/supplier/pay",methods=["POST"])
def api_supp_pay(bid):
    d=request.get_json();supp=sb.table("suppliers").select("*").eq("id",d["id"]).execute()["data"]
    if supp:
        s=supp[0];amt=float(d.get("amount",0));nb=float(s.get("balance",0))-amt
        sb.table("suppliers").eq("id",d["id"]).update({"balance":nb}).execute()
        ref=f"PAY{uuid.uuid4().hex[:6].upper()}"
        sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"2000","description":f"Payment to {s.get('name','')}","debit":amt,"credit":0}).execute()
        sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"1000","description":f"Payment to {s.get('name','')}","debit":0,"credit":amt}).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/expense",methods=["POST"])
def api_exp(bid):
    d=request.get_json();biz=sb.table("businesses").select("settings").eq("id",bid).execute()["data"]
    settings={};
    if biz:
        settings=biz[0].get("settings",{})
        if isinstance(settings,str):
            try:settings=json.loads(settings)
            except:settings={}
    vr=settings.get("vat_rate",15);amt=float(d.get("amount",0));cat=d.get("category","6999")
    hv=cat not in NO_VAT_ACCOUNTS;v=calc_vat(amt,vr,hv);ref=f"EXP{uuid.uuid4().hex[:6].upper()}"
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":d.get("date",today_iso()),"ref":ref,"account":cat,"description":d.get("description",""),"debit":v["excl"],"credit":0}).execute()
    if v["vat"]>0:sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":d.get("date",today_iso()),"ref":ref,"account":"2100","description":"VAT Input","debit":v["vat"],"credit":0}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":d.get("date",today_iso()),"ref":ref,"account":"1000","description":d.get("description",""),"debit":0,"credit":amt}).execute()
    return jsonify({"success":True,"ref":ref})

@app.route("/api/<bid>/pos",methods=["POST"])
def api_pos(bid):
    d=request.get_json();biz=sb.table("businesses").select("settings").eq("id",bid).execute()["data"]
    settings={};
    if biz:
        settings=biz[0].get("settings",{})
        if isinstance(settings,str):
            try:settings=json.loads(settings)
            except:settings={}
    vr=settings.get("vat_rate",15);items=d.get("items",[]);method=d.get("method","cash");cid=d.get("customer_id","")
    total=sum(i["price"]*i["qty"]for i in items);v=calc_vat(total,vr,True);ref=f"POS{uuid.uuid4().hex[:6].upper()}"
    for i in items:
        st=sb.table("stock").select("*").eq("id",i["id"]).execute()["data"]
        if st:sb.table("stock").eq("id",i["id"]).update({"qty":int(st[0].get("qty",0))-i["qty"]}).execute()
    if method=="account"and cid:
        sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"1200","description":"Sale on account","debit":total,"credit":0}).execute()
        cu=sb.table("customers").select("*").eq("id",cid).execute()["data"]
        if cu:sb.table("customers").eq("id",cid).update({"balance":float(cu[0].get("balance",0))+total}).execute()
    else:sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"1000","description":f"POS ({method})","debit":total,"credit":0}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"4000","description":"Sales","debit":0,"credit":v["excl"]}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"2200","description":"VAT Output","debit":0,"credit":v["vat"]}).execute()
    return jsonify({"success":True,"ref":ref,"total":total})

@app.route("/api/<bid>/quote",methods=["POST"])
def api_quote(bid):
    d=request.get_json();lines=d.get("lines",[]);sub=sum(l.get("qty",0)*l.get("price",0)for l in lines)
    vat=sub*d.get("vat_rate",15)/100;total=sub+vat
    q={"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",today_iso()),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"customer_code":d.get("customer_code",""),"lines":json.dumps(lines),"subtotal":sub,"vat":vat,"total":total,"status":"Pending"}
    sb.table("quotes").insert(q).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/quote/<qid>/convert",methods=["POST"])
def api_quote_conv(bid,qid):
    qt=sb.table("quotes").select("*").eq("id",qid).execute()["data"]
    if not qt:return jsonify({"success":False})
    q=qt[0];sb.table("quotes").eq("id",qid).update({"status":"Accepted"}).execute()
    biz=sb.table("businesses").select("settings").eq("id",bid).execute()["data"]
    settings={};
    if biz:
        settings=biz[0].get("settings",{})
        if isinstance(settings,str):
            try:settings=json.loads(settings)
            except:settings={}
    pfx=settings.get("invoice_prefix","INV");ex=sb.table("invoices").select("id").eq("business_id",bid).execute()["data"]or[]
    inum=f"{pfx}{len(ex)+1:04d}"
    inv={"id":str(uuid.uuid4()),"business_id":bid,"number":inum,"date":today_iso(),"customer_id":q.get("customer_id",""),"customer_name":q.get("customer_name",""),"customer_code":q.get("customer_code",""),"lines":q.get("lines","[]"),"subtotal":q.get("subtotal",0),"vat":q.get("vat",0),"total":q.get("total",0),"paid":0,"from_quote":q.get("number","")}
    sb.table("invoices").insert(inv).execute()
    if q.get("customer_id"):
        cu=sb.table("customers").select("*").eq("id",q["customer_id"]).execute()["data"]
        if cu:sb.table("customers").eq("id",q["customer_id"]).update({"balance":float(cu[0].get("balance",0))+float(q.get("total",0))}).execute()
    ref=inum
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"1200","description":f"Invoice {q.get('customer_name','')}","debit":q.get("total",0),"credit":0}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"4000","description":"Sales","debit":0,"credit":q.get("subtotal",0)}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"2200","description":"VAT Output","debit":0,"credit":q.get("vat",0)}).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/invoice",methods=["POST"])
def api_invoice(bid):
    d=request.get_json();lines=d.get("lines",[]);sub=sum(l.get("qty",0)*l.get("price",0)for l in lines)
    vat=sub*d.get("vat_rate",15)/100;total=sub+vat
    inv={"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",today_iso()),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"customer_code":d.get("customer_code",""),"lines":json.dumps(lines),"subtotal":sub,"vat":vat,"total":total,"paid":0}
    sb.table("invoices").insert(inv).execute()
    if d.get("customer_id"):
        cu=sb.table("customers").select("*").eq("id",d["customer_id"]).execute()["data"]
        if cu:sb.table("customers").eq("id",d["customer_id"]).update({"balance":float(cu[0].get("balance",0))+total}).execute()
    ref=d.get("number","")
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"1200","description":f"Invoice {d.get('customer_name','')}","debit":total,"credit":0}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"4000","description":"Sales","debit":0,"credit":sub}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"2200","description":"VAT Output","debit":0,"credit":vat}).execute()
    return jsonify({"success":True})

@app.route("/api/<bid>/mobile/scan",methods=["POST"])
def api_mob_scan(bid):
    d=request.get_json();mode=d.get("mode","expense");img=d.get("image","")
    if ANTHROPIC_API_KEY and img:
        try:
            r=requests.post("https://api.anthropic.com/v1/messages",headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},json={"model":"claude-sonnet-4-20250514","max_tokens":500,"messages":[{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":img}},{"type":"text","text":f'Extract: supplier name, total amount (Rands), description. Reply JSON only: {{"supplier":"name","amount":123.45,"description":"desc","has_vat":true}}'}]}]},timeout=30)
            if r.status_code==200:
                txt=r.json().get("content",[{}])[0].get("text","{}");m=re.search(r'\{[^}]+\}',txt)
                if m:
                    p=json.loads(m.group())
                    return jsonify({"success":True,"supplier":p.get("supplier",""),"amount":float(p.get("amount",0)),"description":p.get("description",""),"ask_vat":p.get("has_vat")is None})
        except:pass
    return jsonify({"success":True,"supplier":"","amount":0,"description":"","ask_vat":True})

@app.route("/api/<bid>/mobile/post",methods=["POST"])
def api_mob_post(bid):
    d=request.get_json();mode=d.get("mode","expense");amt=float(d.get("amount",0));hv=d.get("has_vat",True)
    biz=sb.table("businesses").select("settings").eq("id",bid).execute()["data"]
    settings={};
    if biz:
        settings=biz[0].get("settings",{})
        if isinstance(settings,str):
            try:settings=json.loads(settings)
            except:settings={}
    vr=settings.get("vat_rate",15);v=calc_vat(amt,vr,hv);acc="5000"if mode in["stock","cos"]else"6999"
    ref=f"MOB{uuid.uuid4().hex[:6].upper()}"
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":acc,"description":d.get("description",""),"debit":v["excl"],"credit":0}).execute()
    if v["vat"]>0:sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"2100","description":"VAT Input","debit":v["vat"],"credit":0}).execute()
    sb.table("ledger").insert({"id":str(uuid.uuid4()),"business_id":bid,"date":today_iso(),"ref":ref,"account":"2000","description":d.get("supplier",""),"debit":0,"credit":amt}).execute()
    supps=sb.table("suppliers").select("*").eq("business_id",bid).execute()["data"]or[]
    for s in supps:
        if d.get("supplier","").lower()in s.get("name","").lower():
            sb.table("suppliers").eq("id",s["id"]).update({"balance":float(s.get("balance",0))+amt}).execute();break
    return jsonify({"success":True,"ref":ref})

# ═══════════════════════════════════════════════════════════════════════════════
# RUN - First run the SQL below in Supabase!
# ═══════════════════════════════════════════════════════════════════════════════
"""
-- RUN THIS SQL IN SUPABASE SQL EDITOR FIRST!
CREATE TABLE IF NOT EXISTS businesses(id TEXT PRIMARY KEY,name TEXT,settings JSONB,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS stock(id TEXT PRIMARY KEY,business_id TEXT,code TEXT,description TEXT,category TEXT,qty INT DEFAULT 0,cost DECIMAL,price DECIMAL,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,business_id TEXT,code TEXT,name TEXT,phone TEXT,email TEXT,address TEXT,balance DECIMAL DEFAULT 0,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS suppliers(id TEXT PRIMARY KEY,business_id TEXT,code TEXT,name TEXT,phone TEXT,balance DECIMAL DEFAULT 0,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY,business_id TEXT,date TEXT,ref TEXT,account TEXT,description TEXT,debit DECIMAL DEFAULT 0,credit DECIMAL DEFAULT 0,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY,business_id TEXT,number TEXT,date TEXT,customer_id TEXT,customer_name TEXT,customer_code TEXT,lines JSONB,subtotal DECIMAL,vat DECIMAL,total DECIMAL,status TEXT,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS invoices(id TEXT PRIMARY KEY,business_id TEXT,number TEXT,date TEXT,customer_id TEXT,customer_name TEXT,customer_code TEXT,lines JSONB,subtotal DECIMAL,vat DECIMAL,total DECIMAL,paid DECIMAL DEFAULT 0,from_quote TEXT,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS credit_notes(id TEXT PRIMARY KEY,business_id TEXT,number TEXT,date TEXT,invoice_number TEXT,customer_name TEXT,total DECIMAL,reason TEXT,created_at TIMESTAMP DEFAULT NOW());
CREATE TABLE IF NOT EXISTS delivery_notes(id TEXT PRIMARY KEY,business_id TEXT,number TEXT,date TEXT,invoice_number TEXT,customer_name TEXT,delivery_address TEXT,delivered BOOLEAN DEFAULT FALSE,created_at TIMESTAMP DEFAULT NOW());
"""

if __name__=="__main__":
    print("\n"+"="*60)
    print("  ⚡ CLICK AI v5 - Production Ready")
    print("="*60)
    print(f"  📍 http://127.0.0.1:5000/")
    print(f"  🔌 Supabase: {'✅' if SUPABASE_URL else '❌'}")
    print(f"  🤖 Claude: {'✅' if ANTHROPIC_API_KEY else '⚠️'}")
    print("="*60+"\n")
    app.run(host="0.0.0.0",port=5000,debug=True)
