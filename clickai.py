"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   ██████╗██╗     ██╗ ██████╗██╗  ██╗     █████╗ ██╗                          ║
║  ██╔════╝██║     ██║██╔════╝██║ ██╔╝    ██╔══██╗██║                          ║
║  ██║     ██║     ██║██║     █████╔╝     ███████║██║                          ║
║  ██║     ██║     ██║██║     ██╔═██╗     ██╔══██║██║                          ║
║  ╚██████╗███████╗██║╚██████╗██║  ██╗    ██║  ██║██║                          ║
║   ╚═════╝╚══════╝╚═╝ ╚═════╝╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝                          ║
║                                                                               ║
║   Fully Automated Accounting System                                           ║
║   From Invoice Photo → Trial Balance                                          ║
║   Complete Audit Trail + Supabase Storage                                     ║
║                                                                               ║
║   By: Deon & Claude                                                           ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, jsonify, request, redirect
import json
import os
from datetime import datetime
import re
import base64
import uuid
import csv
import io

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# SUPABASE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gvmonstsssdxncfkcjukr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd2bW9uc3Rzc2R4bmNma2NqdWtyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ5NDI5OTQsImV4cCI6MjA4MDUxODk5NH0.v03qjD4I0eZY5MKfkH3ONFimrHnZsy25wZfVk98UuJQ")

# Try to initialize Supabase
supabase = None
try:
    from supabase import create_client, Client
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase connected!")
except Exception as e:
    print(f"⚠️ Supabase not available: {e}")
    print("   Falling back to local JSON storage")

# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS POS CATEGORIES - Your 13 buttons per business
# ═══════════════════════════════════════════════════════════════════════════════

BUSINESS_POS_CATEGORIES = {
    # FullTech Hardware - Your 13 categories
    "fulltech": ["All", "Bearings", "Bolts", "Nuts", "Washers", "Screws", "Workwear", "Oil Seals", "V-Belts", "Freestyle", "Circlips", "Hardware", "Other"],
    "hardware": ["All", "Bearings", "Bolts", "Nuts", "Washers", "Screws", "Workwear", "Oil Seals", "V-Belts", "Freestyle", "Circlips", "Hardware", "Other"],
    
    # Pub & Grill
    "pub": ["All", "Drinks", "Food", "Spirits", "Beer", "Wine", "Ciders", "Soft Drinks", "Snacks", "Other"],
    
    # B&B
    "bnb": ["All", "Rooms", "Breakfast", "Extras", "Other"],
    
    # Stainless
    "stainless": ["All", "Sheets", "Tubes", "Fittings", "Welding", "Tools", "Other"],
    
    # Default for any business
    "default": ["All", "Category 1", "Category 2", "Category 3", "Category 4", "Category 5", "Other"]
}

def get_pos_categories(business_id):
    """Get POS categories for a business - checks business name for matches"""
    # First check direct match
    if business_id.lower() in BUSINESS_POS_CATEGORIES:
        return BUSINESS_POS_CATEGORIES[business_id.lower()]
    
    # Check if business name contains key words
    biz = get_business(business_id)
    name = biz.get("name", "").lower()
    
    if "hardware" in name or "fulltech" in name or "bearing" in name:
        return BUSINESS_POS_CATEGORIES["hardware"]
    elif "pub" in name or "grill" in name or "bar" in name or "restaurant" in name:
        return BUSINESS_POS_CATEGORIES["pub"]
    elif "b&b" in name or "bnb" in name or "guest" in name or "lodge" in name:
        return BUSINESS_POS_CATEGORIES["bnb"]
    elif "stainless" in name or "steel" in name or "metal" in name:
        return BUSINESS_POS_CATEGORIES["stainless"]
    
    # Default: return categories from stock data
    stock = biz.get("stock", [])
    categories = list(set(s.get("category", "General") for s in stock if s.get("category")))
    if categories:
        return ["All"] + sorted(categories)
    
    return BUSINESS_POS_CATEGORIES["default"]

# Fallback to local storage if Supabase not available
DATA_DIR = os.environ.get("DATA_DIR", ".")
DATA_FILE = os.path.join(DATA_DIR, "clickai_data.json")

# For persistent cloud storage, we'll use a simple file
# In production, you'd use a database like PostgreSQL

# API Key - from environment or settings
def get_api_key():
    """Get API key from environment variable or data file"""
    # First check environment variable
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        return env_key
    # Then check data file
    data = load_data()
    return data.get("settings", {}).get("api_key", "")

# ═══════════════════════════════════════════════════════════════════════════════
# CHART OF ACCOUNTS - South African Standard
# ═══════════════════════════════════════════════════════════════════════════════

CHART_OF_ACCOUNTS = {
    # ASSETS (1000-1999)
    "1000": {"name": "Bank", "type": "asset", "category": "current_asset"},
    "1100": {"name": "Petty Cash", "type": "asset", "category": "current_asset"},
    "1200": {"name": "Accounts Receivable (Debtors)", "type": "asset", "category": "current_asset"},
    "1300": {"name": "Stock / Inventory", "type": "asset", "category": "current_asset"},
    "1400": {"name": "Prepaid Expenses", "type": "asset", "category": "current_asset"},
    "1500": {"name": "Equipment", "type": "asset", "category": "fixed_asset"},
    "1510": {"name": "Accumulated Depreciation - Equipment", "type": "asset", "category": "fixed_asset"},
    "1600": {"name": "Vehicles", "type": "asset", "category": "fixed_asset"},
    "1610": {"name": "Accumulated Depreciation - Vehicles", "type": "asset", "category": "fixed_asset"},
    
    # LIABILITIES (2000-2999)
    "2000": {"name": "Accounts Payable (Creditors)", "type": "liability", "category": "current_liability"},
    "2100": {"name": "VAT Payable", "type": "liability", "category": "current_liability"},
    "2200": {"name": "PAYE Payable", "type": "liability", "category": "current_liability"},
    "2300": {"name": "UIF Payable", "type": "liability", "category": "current_liability"},
    "2400": {"name": "SDL Payable", "type": "liability", "category": "current_liability"},
    "2500": {"name": "Loans Payable", "type": "liability", "category": "long_term_liability"},
    
    # EQUITY (3000-3999)
    "3000": {"name": "Owner's Equity / Capital", "type": "equity", "category": "equity"},
    "3100": {"name": "Retained Earnings", "type": "equity", "category": "equity"},
    "3200": {"name": "Drawings", "type": "equity", "category": "equity"},
    
    # INCOME (4000-4999)
    "4000": {"name": "Sales Revenue", "type": "income", "category": "revenue"},
    "4100": {"name": "Service Revenue", "type": "income", "category": "revenue"},
    "4200": {"name": "Interest Income", "type": "income", "category": "other_income"},
    "4300": {"name": "Other Income", "type": "income", "category": "other_income"},
    
    # COST OF SALES (5000-5999)
    "5000": {"name": "Cost of Goods Sold", "type": "expense", "category": "cos"},
    "5100": {"name": "Purchases", "type": "expense", "category": "cos"},
    "5200": {"name": "Freight & Delivery Inward", "type": "expense", "category": "cos"},
    "5300": {"name": "Direct Labour", "type": "expense", "category": "cos"},
    
    # EXPENSES (6000-6999)
    "6000": {"name": "Salaries & Wages", "type": "expense", "category": "operating"},
    "6100": {"name": "Rent Expense", "type": "expense", "category": "operating"},
    "6200": {"name": "Utilities (Water & Electricity)", "type": "expense", "category": "operating"},
    "6300": {"name": "Telephone & Internet", "type": "expense", "category": "operating"},
    "6400": {"name": "Insurance", "type": "expense", "category": "operating"},
    "6500": {"name": "Repairs & Maintenance", "type": "expense", "category": "operating"},
    "6600": {"name": "Office Supplies", "type": "expense", "category": "operating"},
    "6700": {"name": "Bank Charges", "type": "expense", "category": "operating"},
    "6800": {"name": "Advertising & Marketing", "type": "expense", "category": "operating"},
    "6900": {"name": "Professional Fees", "type": "expense", "category": "operating"},
    "6910": {"name": "Travel & Entertainment", "type": "expense", "category": "operating"},
    "6920": {"name": "Depreciation Expense", "type": "expense", "category": "operating"},
    "6930": {"name": "Bad Debts", "type": "expense", "category": "operating"},
    "6999": {"name": "Miscellaneous Expense", "type": "expense", "category": "operating"},
}

# Expense categories for AI to recognize
EXPENSE_CATEGORIES = {
    "rent": "6100",
    "water": "6200",
    "electricity": "6200",
    "utilities": "6200",
    "phone": "6300",
    "telephone": "6300",
    "internet": "6300",
    "insurance": "6400",
    "repairs": "6500",
    "maintenance": "6500",
    "office": "6600",
    "stationery": "6600",
    "bank": "6700",
    "advertising": "6800",
    "marketing": "6800",
    "accounting": "6900",
    "legal": "6900",
    "travel": "6910",
    "fuel": "6910",
    "petrol": "6910",
}

# ═══════════════════════════════════════════════════════════════════════════════
# DATA MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def load_data():
    """Load data - from Supabase if available, else JSON file"""
    if supabase:
        try:
            # Load businesses from Supabase
            result = supabase.table("businesses").select("*").execute()
            businesses = {}
            for biz in result.data:
                biz_id = str(biz['id'])
                businesses[biz_id] = {
                    "id": biz_id,
                    "name": biz['name'],
                    "suppliers": [],
                    "customers": [],
                    "stock": [],
                    "ledger": [],
                    "documents": {
                        "supplier_invoices": [],
                        "expenses": [],
                        "quotes": [],
                        "invoices": [],
                        "delivery_notes": []
                    },
                    "created_at": biz.get('created_at', '')
                }
                
                # Load stock
                stock_result = supabase.table("stock").select("*").eq("business_id", biz['id']).execute()
                for s in stock_result.data:
                    businesses[biz_id]["stock"].append({
                        "id": str(s['id']),
                        "code": s.get('code', ''),
                        "description": s.get('description', ''),
                        "category": s.get('category', 'General'),
                        "qty": s.get('qty', 0),
                        "cost": float(s.get('cost', 0)),
                        "price": float(s.get('price', 0))
                    })
                
                # Load customers
                cust_result = supabase.table("customers").select("*").eq("business_id", biz['id']).execute()
                for c in cust_result.data:
                    businesses[biz_id]["customers"].append({
                        "id": str(c['id']),
                        "code": c.get('code', ''),
                        "name": c.get('name', ''),
                        "phone": c.get('phone', ''),
                        "email": c.get('email', ''),
                        "balance": float(c.get('balance', 0))
                    })
                
                # Load suppliers
                sup_result = supabase.table("suppliers").select("*").eq("business_id", biz['id']).execute()
                for s in sup_result.data:
                    businesses[biz_id]["suppliers"].append({
                        "id": str(s['id']),
                        "code": s.get('code', ''),
                        "name": s.get('name', ''),
                        "phone": s.get('phone', ''),
                        "email": s.get('email', ''),
                        "balance": float(s.get('balance', 0))
                    })
                
                # Load ledger
                ledger_result = supabase.table("ledger").select("*").eq("business_id", biz['id']).order("date", desc=True).execute()
                for l in ledger_result.data:
                    businesses[biz_id]["ledger"].append({
                        "id": str(l['id']),
                        "date": l.get('date', ''),
                        "doc_id": l.get('doc_id', ''),
                        "doc_type": l.get('doc_type', ''),
                        "account": l.get('account', ''),
                        "account_name": l.get('account_name', ''),
                        "description": l.get('description', ''),
                        "debit": float(l.get('debit', 0)),
                        "credit": float(l.get('credit', 0))
                    })
                
                # Load documents
                docs_result = supabase.table("documents").select("*").eq("business_id", biz['id']).execute()
                for d in docs_result.data:
                    doc_type = d.get('doc_type', 'supplier_invoices')
                    doc_data = d.get('data', {}) or {}
                    doc_entry = {
                        "id": d.get('doc_id', ''),
                        "date": d.get('date', ''),
                        "supplier": {"code": d.get('supplier_code', ''), "name": d.get('supplier_name', '')},
                        "customer": {"code": d.get('customer_code', ''), "name": d.get('customer_name', '')},
                        "invoice_number": d.get('invoice_number', ''),
                        "description": d.get('description', ''),
                        "category": d.get('category', ''),
                        "category_name": d.get('category_name', ''),
                        "amount_excl": float(d.get('amount_excl', 0)),
                        "vat": float(d.get('vat', 0)),
                        "amount_incl": float(d.get('amount_incl', 0)),
                        "total": float(d.get('amount_incl', 0)),
                        "status": d.get('status', 'unpaid'),
                        **doc_data
                    }
                    
                    if doc_type == 'expense':
                        businesses[biz_id]["documents"]["expenses"].append(doc_entry)
                    elif doc_type in businesses[biz_id]["documents"]:
                        businesses[biz_id]["documents"][doc_type].append(doc_entry)
            
            return {"settings": {"api_key": ""}, "businesses": businesses}
        except Exception as e:
            print(f"Supabase load error: {e}")
    
    # Fallback to JSON file
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        "settings": {"api_key": ""},
        "businesses": {},
        "current_business": None
    }

def save_data(data):
    """Save data - to Supabase if available, else JSON file"""
    if supabase:
        try:
            # For full sync we'd update Supabase here
            # But for now, individual operations handle their own saves
            pass
        except Exception as e:
            print(f"Supabase save error: {e}")
    
    # Always save to JSON as backup
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def save_business_to_supabase(business_id, biz_data):
    """Save or update a business in Supabase"""
    if not supabase:
        return None
    try:
        # Check if exists
        result = supabase.table("businesses").select("id").eq("id", business_id).execute()
        if result.data:
            # Update
            supabase.table("businesses").update({"name": biz_data.get("name", "Business")}).eq("id", business_id).execute()
        else:
            # Insert
            supabase.table("businesses").insert({"id": business_id, "name": biz_data.get("name", "Business")}).execute()
        return business_id
    except Exception as e:
        print(f"Error saving business to Supabase: {e}")
        return None


def save_stock_to_supabase(business_id, stock_item, stock_id=None):
    """Save stock item to Supabase"""
    if not supabase:
        return None
    try:
        data = {
            "business_id": business_id,
            "code": stock_item.get("code", ""),
            "description": stock_item.get("description", ""),
            "category": stock_item.get("category", "General"),
            "qty": stock_item.get("qty", 0),
            "cost": stock_item.get("cost", 0),
            "price": stock_item.get("price", 0)
        }
        if stock_id:
            supabase.table("stock").update(data).eq("id", stock_id).execute()
        else:
            result = supabase.table("stock").insert(data).execute()
            return result.data[0]['id'] if result.data else None
    except Exception as e:
        print(f"Error saving stock: {e}")
    return None


def save_customer_to_supabase(business_id, customer):
    """Save customer to Supabase"""
    if not supabase:
        return None
    try:
        data = {
            "business_id": business_id,
            "code": customer.get("code", ""),
            "name": customer.get("name", ""),
            "phone": customer.get("phone", ""),
            "email": customer.get("email", ""),
            "balance": customer.get("balance", 0)
        }
        result = supabase.table("customers").insert(data).execute()
        return result.data[0]['id'] if result.data else None
    except Exception as e:
        print(f"Error saving customer: {e}")
    return None


def save_supplier_to_supabase(business_id, supplier):
    """Save supplier to Supabase"""
    if not supabase:
        return None
    try:
        data = {
            "business_id": business_id,
            "code": supplier.get("code", ""),
            "name": supplier.get("name", ""),
            "phone": supplier.get("phone", ""),
            "email": supplier.get("email", ""),
            "balance": supplier.get("balance", 0)
        }
        result = supabase.table("suppliers").insert(data).execute()
        return result.data[0]['id'] if result.data else None
    except Exception as e:
        print(f"Error saving supplier: {e}")
    return None


def save_ledger_to_supabase(business_id, entry):
    """Save ledger entry to Supabase"""
    if not supabase:
        return None
    try:
        data = {
            "business_id": business_id,
            "date": entry.get("date", datetime.now().strftime("%Y-%m-%d")),
            "doc_id": entry.get("doc_id", ""),
            "doc_type": entry.get("doc_type", ""),
            "account": entry.get("account", ""),
            "account_name": entry.get("account_name", ""),
            "description": entry.get("description", ""),
            "debit": entry.get("debit", 0),
            "credit": entry.get("credit", 0)
        }
        result = supabase.table("ledger").insert(data).execute()
        return result.data[0]['id'] if result.data else None
    except Exception as e:
        print(f"Error saving ledger: {e}")
    return None


def save_document_to_supabase(business_id, doc, doc_type):
    """Save document to Supabase"""
    if not supabase:
        return None
    try:
        data = {
            "business_id": business_id,
            "doc_id": doc.get("id", ""),
            "doc_type": doc_type,
            "date": doc.get("date", ""),
            "supplier_code": doc.get("supplier", {}).get("code", ""),
            "supplier_name": doc.get("supplier", {}).get("name", ""),
            "customer_code": doc.get("customer", {}).get("code", ""),
            "customer_name": doc.get("customer", {}).get("name", ""),
            "invoice_number": doc.get("invoice_number", ""),
            "description": doc.get("description", ""),
            "category": doc.get("category", ""),
            "category_name": doc.get("category_name", ""),
            "amount_excl": doc.get("amount_excl", 0),
            "vat": doc.get("vat", 0),
            "amount_incl": doc.get("amount_incl", doc.get("total", 0)),
            "status": doc.get("status", "unpaid"),
            "data": json.dumps(doc)
        }
        result = supabase.table("documents").insert(data).execute()
        return result.data[0]['id'] if result.data else None
    except Exception as e:
        print(f"Error saving document: {e}")
    return None

def get_api_key():
    """Get API key from environment or data"""
    env_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if env_key:
        return env_key
    data = load_data()
    return data.get("settings", {}).get("api_key", "")


def get_business(business_id):
    """Get business data, create if not exists"""
    data = load_data()
    if business_id not in data["businesses"]:
        # Create new business
        new_biz = {
            "name": business_id.replace("_", " ").title(),
            "suppliers": [],
            "customers": [],
            "stock": [],
            "ledger": [],
            "documents": {
                "supplier_invoices": [],
                "expenses": [],
                "quotes": [],
                "invoices": [],
                "delivery_notes": [],
            },
            "created_at": datetime.now().isoformat()
        }
        data["businesses"][business_id] = new_biz
        save_data(data)
        
        # Also save to Supabase
        if supabase:
            try:
                supabase.table("businesses").insert({
                    "id": business_id,
                    "name": new_biz["name"]
                }).execute()
            except Exception as e:
                print(f"Error creating business in Supabase: {e}")
    
    return data["businesses"][business_id]

# ═══════════════════════════════════════════════════════════════════════════════
# SHARED CSS & COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """
:root {
    --bg: #0a0a0f;
    --card: #12121a;
    --border: #1e1e2e;
    --text: #fff;
    --text-muted: #8888aa;
    --primary: #3b82f6;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --purple: #8b5cf6;
    --cyan: #06b6d4;
    --glow-blue: rgba(59, 130, 246, 0.5);
    --glow-purple: rgba(139, 92, 246, 0.5);
    --glow-red: rgba(239, 68, 68, 0.4);
    --glow-cyan: rgba(6, 182, 212, 0.4);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding-top: 70px; /* Space for sticky header */
    padding-bottom: 100px;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* STICKY HEADER                                                                */
/* ═══════════════════════════════════════════════════════════════════════════ */

.header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 60px;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 15px;
    z-index: 1000;
}

.logo {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 900;
    font-size: 18px;
}

.logo-icon {
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--primary), var(--purple));
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
}

.nav-buttons {
    display: flex;
    gap: 8px;
}

.nav-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    border-radius: 8px;
    border: none;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.2s;
}

.nav-btn-home {
    background: rgba(255,255,255,0.1);
    color: #fff;
}

.nav-btn-home:hover {
    background: rgba(255,255,255,0.2);
}

.nav-btn-back {
    background: rgba(255,255,255,0.1);
    color: #fff;
}

.nav-btn-back:hover {
    background: rgba(239,68,68,0.3);
}

.nav-btn-next {
    background: var(--success);
    color: #fff;
}

.nav-btn-next:hover {
    background: #16a34a;
}

.nav-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* MAIN CONTENT                                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px 15px;
}

.page-title {
    font-size: 28px;
    font-weight: 900;
    margin-bottom: 10px;
    background: linear-gradient(135deg, var(--primary), var(--purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.page-subtitle {
    color: var(--text-muted);
    margin-bottom: 30px;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* CARDS WITH HOVER LIFT                                                        */
/* ═══════════════════════════════════════════════════════════════════════════ */

.card {
    background: var(--card);
    border-radius: 16px;
    padding: 25px;
    margin-bottom: 20px;
    border: 1px solid var(--border);
    transition: all 0.2s ease;
}

.card:hover {
    transform: translateY(-2px);
    border-color: #333;
    box-shadow: 0 8px 30px rgba(0,0,0,0.4);
}

.card-title {
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* CLEAN BUTTONS WITH HOVER LIFT                                                */
/* ═══════════════════════════════════════════════════════════════════════════ */

.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 15px 30px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-decoration: none;
    width: 100%;
    border: 1px solid transparent;
}

.btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 20px rgba(0,0,0,0.4);
}

.btn-primary { 
    background: var(--primary); 
    color: #fff;
}
.btn-primary:hover { 
    background: #2563eb;
    box-shadow: 0 5px 25px rgba(59,130,246,0.4);
}

.btn-success { 
    background: var(--success); 
    color: #fff;
}
.btn-success:hover { 
    background: #059669;
    box-shadow: 0 5px 25px rgba(16,185,129,0.4);
}

.btn-warning { 
    background: var(--warning); 
    color: #fff;
}
.btn-warning:hover { 
    background: #d97706;
    box-shadow: 0 5px 25px rgba(245,158,11,0.4);
}

.btn-danger { 
    background: var(--danger); 
    color: #fff;
}
.btn-danger:hover { 
    background: #dc2626;
    box-shadow: 0 5px 25px rgba(239,68,68,0.4);
}

.btn-secondary { 
    background: #2a2a3a; 
    color: #fff;
    border: 1px solid var(--border);
}
.btn-secondary:hover { 
    background: #3a3a4a;
    border-color: var(--purple);
    box-shadow: 0 5px 25px rgba(139,92,246,0.3);
}

.btn-outline {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
}
.btn-outline:hover {
    border-color: var(--primary);
    background: rgba(59,130,246,0.1);
    box-shadow: 0 5px 25px rgba(59,130,246,0.2);
}

.btn-purple {
    background: var(--purple);
    color: #fff;
}
.btn-purple:hover {
    background: #7c3aed;
    box-shadow: 0 5px 25px rgba(139,92,246,0.4);
}

.btn-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 15px;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* FORMS                                                                        */
/* ═══════════════════════════════════════════════════════════════════════════ */

.form-group {
    margin-bottom: 20px;
}

.form-label {
    display: block;
    margin-bottom: 8px;
    color: var(--text-muted);
    font-size: 14px;
    font-weight: 600;
}

.form-input, .form-select {
    width: 100%;
    padding: 14px 16px;
    background: #1a1a2a;
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-size: 16px;
    transition: all 0.2s ease;
}

.form-input:focus, .form-select:focus {
    outline: none;
    border-color: var(--primary);
    background: #1e1e2e;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* TABLES                                                                       */
/* ═══════════════════════════════════════════════════════════════════════════ */

.table {
    width: 100%;
    border-collapse: collapse;
}

.table th {
    text-align: left;
    padding: 12px;
    background: #1a1a1a;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
}

.table td {
    padding: 12px;
    border-bottom: 1px solid var(--border);
}

.table tr:hover {
    background: rgba(255,255,255,0.02);
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* ACTION CARDS (for selection)                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */

.action-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 15px;
}

.action-card {
    background: var(--card);
    border: 2px solid var(--border);
    border-radius: 16px;
    padding: 30px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
}

.action-card:hover {
    border-color: var(--primary);
    transform: translateY(-2px);
}

.action-card.selected {
    border-color: var(--success);
    background: rgba(34,197,94,0.1);
}

.action-card-icon {
    font-size: 48px;
    margin-bottom: 15px;
}

.action-card-title {
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 8px;
}

.action-card-desc {
    color: var(--text-muted);
    font-size: 14px;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* STATUS BADGES                                                                */
/* ═══════════════════════════════════════════════════════════════════════════ */

.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

.badge-success { background: var(--success); color: #fff; }
.badge-warning { background: var(--warning); color: #fff; }
.badge-danger { background: var(--danger); color: #fff; }
.badge-info { background: var(--primary); color: #fff; }

/* ═══════════════════════════════════════════════════════════════════════════ */
/* AUDIT TRAIL                                                                  */
/* ═══════════════════════════════════════════════════════════════════════════ */

.audit-trail {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 15px;
    background: #1a1a1a;
    border-radius: 10px;
    margin-bottom: 20px;
    overflow-x: auto;
}

.audit-step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--card);
    border-radius: 8px;
    font-size: 13px;
    white-space: nowrap;
}

.audit-step.active {
    background: var(--primary);
}

.audit-step.complete {
    background: var(--success);
}

.audit-arrow {
    color: var(--text-muted);
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* UPLOAD AREA                                                                  */
/* ═══════════════════════════════════════════════════════════════════════════ */

.upload-area {
    border: 3px dashed var(--border);
    border-radius: 16px;
    padding: 40px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
}

.upload-area:hover {
    border-color: var(--primary);
    background: rgba(59,130,246,0.05);
}

.upload-icon {
    font-size: 64px;
    margin-bottom: 15px;
}

.upload-text {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
}

.upload-hint {
    color: var(--text-muted);
    font-size: 14px;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* LOADING & PROCESSING                                                         */
/* ═══════════════════════════════════════════════════════════════════════════ */

.processing {
    text-align: center;
    padding: 60px 20px;
}

.processing-spinner {
    width: 60px;
    height: 60px;
    border: 4px solid var(--border);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 20px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.processing-text {
    font-size: 18px;
    font-weight: 600;
}

.processing-sub {
    color: var(--text-muted);
    margin-top: 8px;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* TOTALS BOX                                                                   */
/* ═══════════════════════════════════════════════════════════════════════════ */

.totals-box {
    background: #1a1a1a;
    border-radius: 12px;
    padding: 20px;
    margin-top: 20px;
}

.totals-row {
    display: flex;
    justify-content: space-between;
    padding: 10px 0;
}

.totals-row.grand {
    border-top: 2px solid var(--border);
    margin-top: 10px;
    padding-top: 15px;
    font-size: 24px;
    font-weight: 900;
}

.totals-row.grand .amount {
    color: var(--success);
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* MOBILE RESPONSIVE                                                            */
/* ═══════════════════════════════════════════════════════════════════════════ */

@media (max-width: 600px) {
    .header {
        padding: 0 10px;
    }
    
    .logo span {
        display: none;
    }
    
    .nav-btn span {
        display: none;
    }
    
    .nav-btn {
        padding: 10px 12px;
    }
    
    .page-title {
        font-size: 24px;
    }
    
    .action-cards {
        grid-template-columns: 1fr;
    }
    
    .btn-row {
        grid-template-columns: 1fr;
    }
}

/* Print styles */
@media print {
    .header, .nav-buttons { display: none !important; }
    body { padding-top: 0; background: #fff; color: #000; }
    .card { border: 1px solid #ddd; }
}
"""

def render_header(title="", back_url=None, next_url=None, next_text="Next →"):
    """Render the sticky header"""
    back_btn = f'<a href="{back_url}" class="nav-btn nav-btn-back">← Back</a>' if back_url else '<button class="nav-btn nav-btn-back" disabled>← Back</button>'
    next_btn = f'<a href="{next_url}" class="nav-btn nav-btn-next">{next_text}</a>' if next_url else ''
    
    return f'''
    <div class="header">
        <div class="logo">
            <div class="logo-icon">⚡</div>
            <span>Click AI</span>
        </div>
        <div class="nav-buttons">
            <a href="/" class="nav-btn nav-btn-home">🏠 <span>Home</span></a>
            {back_btn}
            {next_btn}
        </div>
    </div>
    '''

def render_page(content, title="Click AI", back_url=None, next_url=None, next_text="Next →"):
    """Render a complete page"""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - Click AI</title>
    <style>{CSS}</style>
</head>
<body>
    {render_header(title, back_url, next_url, next_text)}
    {content}
</body>
</html>'''

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - HOME & SETUP
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    """Home page - Select or create business"""
    data = load_data()
    businesses = data.get("businesses", {})
    
    # Check for import message
    imported = request.args.get('imported', '')
    message = ''
    if imported:
        message = f'<div style="background:var(--success);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">✓ {imported}</div>'
    
    business_cards = ""
    for bid, biz in businesses.items():
        doc_count = sum(len(biz.get("documents", {}).get(k, [])) for k in ["supplier_invoices", "quotes", "invoices", "delivery_notes"])
        stock_count = len(biz.get("stock", []))
        cust_count = len(biz.get("customers", []))
        business_cards += f'''
        <a href="/business/{bid}" class="action-card" style="text-decoration:none;color:inherit">
            <div class="action-card-icon">🏢</div>
            <div class="action-card-title">{biz.get("name", bid)}</div>
            <div class="action-card-desc">{stock_count} stock | {cust_count} customers</div>
        </a>
        '''
    
    if not business_cards:
        business_cards = '''
        <div class="card" style="text-align:center;padding:60px 20px">
            <div style="font-size:64px;margin-bottom:20px">🏢</div>
            <div style="font-size:20px;font-weight:700;margin-bottom:10px">No businesses yet</div>
            <div style="color:var(--text-muted);margin-bottom:30px">Create your first business or import from ScanAI</div>
        </div>
        '''
    
    content = f'''
    <div class="container">
        <h1 class="page-title">⚡ Click AI</h1>
        <p class="page-subtitle">Fully Automated Accounting System</p>
        
        {message}
        
        <div class="card">
            <div class="card-title">🏢 Your Businesses</div>
            <div class="action-cards">
                {business_cards}
                <a href="/business/new" class="action-card" style="text-decoration:none;color:inherit;border-style:dashed">
                    <div class="action-card-icon">➕</div>
                    <div class="action-card-title">Add Business</div>
                    <div class="action-card-desc">Create new business</div>
                </a>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📤 Import from ScanAI</div>
            <p style="color:var(--text-muted);margin-bottom:15px">Have existing data from ScanAI? Upload your data file to import everything!</p>
            <button onclick="document.getElementById('importScanAI').style.display='flex'" class="btn btn-primary">
                📤 Import ScanAI Data
            </button>
        </div>
        
        <div class="card">
            <div class="card-title">⚙️ Quick Links</div>
            <div class="btn-row">
                <a href="/settings" class="btn btn-secondary">⚙️ Settings</a>
                <a href="/about" class="btn btn-secondary">ℹ️ About Click AI</a>
            </div>
        </div>
    </div>
    
    <!-- Import ScanAI Modal -->
    <div id="importScanAI" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div class="card" style="max-width:500px;width:100%">
            <h3 style="margin-bottom:20px">📤 Import from ScanAI</h3>
            <p style="color:var(--text-muted);margin-bottom:20px">
                Find your ScanAI data file. It's usually called:<br>
                <code style="background:#1a1a1a;padding:5px 10px;border-radius:4px;margin-top:10px;display:inline-block">fulltech_data.json</code><br><br>
                Or look for any <strong>.json</strong> file in your ScanAI folder.
            </p>
            <form action="/import-scanai" method="POST" enctype="multipart/form-data">
                <input type="file" name="file" accept=".json" required style="margin-bottom:20px;width:100%;padding:15px;background:#1a1a1a;border:2px dashed var(--border);border-radius:8px;color:#fff">
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">📤 Import</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('importScanAI').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    '''
    
    return render_page(content, "Home")


@app.route("/import-scanai", methods=["POST"])
def import_scanai():
    """Import data from ScanAI JSON file"""
    try:
        file = request.files['file']
        content = file.read().decode('utf-8-sig')
        scanai = json.loads(content)
        
        # Load current Click AI data
        data = load_data()
        
        # Copy API key if exists
        if scanai.get("api_key"):
            data["settings"]["api_key"] = scanai["api_key"]
        
        total_stock = 0
        total_customers = 0
        total_suppliers = 0
        businesses_imported = []
        
        # Business mapping
        business_names = {
            "hardware": "Hardware Store",
            "pub": "Bedrock Pub & Grill",
            "bnb": "B&B",
            "stainless": "Stainless Steel"
        }
        
        # Look for fulltech data structure
        fulltech = scanai.get("fulltech", scanai)  # Try fulltech key first, else assume root
        
        # Migrate each business found
        for biz_id in ["hardware", "pub", "bnb", "stainless"]:
            source = fulltech.get(biz_id, {})
            if not source:
                continue
            
            # Create business in Click AI
            if biz_id not in data["businesses"]:
                data["businesses"][biz_id] = {
                    "name": business_names.get(biz_id, biz_id.title()),
                    "suppliers": [],
                    "customers": [],
                    "stock": [],
                    "ledger": [],
                    "documents": {
                        "supplier_invoices": [],
                        "quotes": [],
                        "invoices": [],
                        "delivery_notes": [],
                    },
                    "created_at": datetime.now().isoformat()
                }
            
            dest = data["businesses"][biz_id]
            
            # Import Stock
            for item in source.get("stock", []):
                dest["stock"].append({
                    "code": item.get("code", ""),
                    "description": item.get("description", ""),
                    "category": item.get("category", "General"),
                    "qty": item.get("qty", 0),
                    "cost": item.get("cost", 0),
                    "price": item.get("price", 0),
                    "created_at": datetime.now().isoformat()
                })
                total_stock += 1
            
            # Import Customers
            for c in source.get("customers", []):
                dest["customers"].append({
                    "code": c.get("code", ""),
                    "name": c.get("name", ""),
                    "phone": c.get("phone", ""),
                    "email": c.get("email", ""),
                    "balance": c.get("balance", 0),
                    "created_at": datetime.now().isoformat()
                })
                total_customers += 1
            
            # Import Suppliers
            for s in source.get("suppliers", []):
                dest["suppliers"].append({
                    "code": s.get("code", ""),
                    "name": s.get("name", ""),
                    "phone": s.get("phone", ""),
                    "email": s.get("email", ""),
                    "balance": s.get("balance", 0),
                    "created_at": datetime.now().isoformat()
                })
                total_suppliers += 1
            
            if source.get("stock") or source.get("customers") or source.get("suppliers"):
                businesses_imported.append(biz_id)
        
        save_data(data)
        
        msg = f"Imported {len(businesses_imported)} businesses: {total_stock} stock, {total_customers} customers, {total_suppliers} suppliers"
        return redirect(f'/?imported={msg}')
        
    except Exception as e:
        return redirect(f'/?imported=Error: {str(e)}')

@app.route("/business/new", methods=["GET", "POST"])
def business_new():
    """Create new business"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            business_id = name.lower().replace(" ", "_").replace("-", "_")
            business_id = re.sub(r'[^a-z0-9_]', '', business_id)
            
            data = load_data()
            data["businesses"][business_id] = {
                "name": name,
                "suppliers": [],
                "customers": [],
                "stock": [],
                "ledger": [],
                "documents": {
                    "supplier_invoices": [],
                    "quotes": [],
                    "invoices": [],
                    "delivery_notes": [],
                },
                "created_at": datetime.now().isoformat()
            }
            save_data(data)
            return redirect(f"/business/{business_id}")
    
    content = '''
    <div class="container">
        <h1 class="page-title">➕ New Business</h1>
        <p class="page-subtitle">Create a new business to start tracking</p>
        
        <div class="card">
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">Business Name</label>
                    <input type="text" name="name" class="form-input" placeholder="e.g. Bedrock Pub & Grill" required autofocus>
                </div>
                <button type="submit" class="btn btn-success">✓ Create Business</button>
            </form>
        </div>
    </div>
    '''
    
    return render_page(content, "New Business", back_url="/")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    """Settings page - API key etc"""
    data = load_data()
    message = ""
    
    if request.method == "POST":
        api_key = request.form.get("api_key", "").strip()
        data["settings"]["api_key"] = api_key
        save_data(data)
        message = '<div style="background:var(--success);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">✓ Settings saved!</div>'
    
    current_key = data.get("settings", {}).get("api_key", "")
    key_status = "✓ API Key configured" if current_key else "⚠️ No API key set"
    key_color = "var(--success)" if current_key else "var(--warning)"
    
    content = f'''
    <div class="container">
        <h1 class="page-title">⚙️ Settings</h1>
        <p class="page-subtitle">Configure Click AI</p>
        
        {message}
        
        <div class="card">
            <div class="card-title">🔑 Anthropic API Key</div>
            <form method="POST">
                <div class="form-group">
                    <label class="form-label">API Key <span style="color:{key_color}">{key_status}</span></label>
                    <input type="password" name="api_key" class="form-input" value="{current_key}" placeholder="sk-ant-api03-...">
                </div>
                <p style="color:var(--text-muted);font-size:14px;margin-bottom:20px">
                    Get your API key from <a href="https://console.anthropic.com/settings/keys" target="_blank" style="color:var(--primary)">console.anthropic.com</a>
                </p>
                <button type="submit" class="btn btn-success">💾 Save Settings</button>
            </form>
        </div>
    </div>
    '''
    
    return render_page(content, "Settings", back_url="/")

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - BUSINESS DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>")
def business_dashboard(business_id):
    """Business dashboard - main menu"""
    biz = get_business(business_id)
    docs = biz.get("documents", {})
    
    # Mobile detection script - redirects phones to capture interface
    mobile_detect = f'''
    <script>
    (function() {{
        var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) || window.innerWidth < 768;
        if (isMobile && !sessionStorage.getItem('forceDesktop')) {{
            window.location.href = '/business/{business_id}/capture';
        }}
    }})();
    </script>
    '''
    
    content = f'''
    {mobile_detect}
    <div class="container">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:10px;margin-bottom:20px">
            <div>
                <h1 class="page-title" style="margin-bottom:5px">🏢 {biz.get("name", business_id)}</h1>
                <p class="page-subtitle" style="margin:0">What would you like to do?</p>
            </div>
            <div style="display:flex;gap:10px">
                <a href="/business/{business_id}/pos" class="btn btn-success" style="width:auto;font-size:18px;padding:15px 25px">🛒 POS</a>
                <a href="/business/{business_id}/settings" class="btn btn-outline" style="width:auto">⚙️ Settings</a>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📥 CAPTURE (Supplier Invoices)</div>
            <div class="action-cards">
                <a href="/business/{business_id}/supplier-invoice/new" class="action-card" style="text-decoration:none;color:inherit">
                    <div class="action-card-icon">📦</div>
                    <div class="action-card-title">Stock / Goods</div>
                    <div class="action-card-desc">Purchases for resale (Cost of Sales)</div>
                </a>
                <a href="/business/{business_id}/expense/new" class="action-card" style="text-decoration:none;color:inherit">
                    <div class="action-card-icon">💸</div>
                    <div class="action-card-title">Expenses</div>
                    <div class="action-card-desc">Rent, utilities, services, etc.</div>
                </a>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📤 SELL (Customer Documents)</div>
            <div class="action-cards">
                <a href="/business/{business_id}/quote/new" class="action-card" style="text-decoration:none;color:inherit">
                    <div class="action-card-icon">📝</div>
                    <div class="action-card-title">Quote</div>
                    <div class="action-card-desc">{len(docs.get("quotes", []))} quotes</div>
                </a>
                <a href="/business/{business_id}/invoice/new" class="action-card" style="text-decoration:none;color:inherit">
                    <div class="action-card-icon">🧾</div>
                    <div class="action-card-title">Invoice</div>
                    <div class="action-card-desc">{len(docs.get("invoices", []))} invoices</div>
                </a>
                <a href="/business/{business_id}/delivery-notes" class="action-card" style="text-decoration:none;color:inherit">
                    <div class="action-card-icon">🚚</div>
                    <div class="action-card-title">Delivery Note</div>
                    <div class="action-card-desc">{len(docs.get("delivery_notes", []))} notes</div>
                </a>
            </div>
            <div class="btn-row" style="margin-top:15px">
                <a href="/business/{business_id}/supplier-invoices" class="btn btn-outline">📋 Supplier Invoices</a>
                <a href="/business/{business_id}/expenses" class="btn btn-outline">📋 Expenses</a>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📊 REPORTS</div>
            <div class="btn-row">
                <a href="/business/{business_id}/ledger" class="btn btn-secondary">📒 Ledger</a>
                <a href="/business/{business_id}/trial-balance" class="btn btn-secondary">📊 Trial Balance</a>
            </div>
            <div class="btn-row">
                <a href="/business/{business_id}/profit-loss" class="btn btn-success">📈 Profit & Loss</a>
                <a href="/business/{business_id}/vat-report" class="btn btn-warning">🧾 VAT Report</a>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📁 MASTER DATA</div>
            <div class="btn-row">
                <a href="/business/{business_id}/stock" class="btn btn-outline">📦 Stock</a>
                <a href="/business/{business_id}/suppliers" class="btn btn-outline">👥 Suppliers</a>
            </div>
            <div class="btn-row">
                <a href="/business/{business_id}/customers" class="btn btn-outline">👤 Customers</a>
            </div>
        </div>
    </div>
    '''
    
    return render_page(content, biz.get("name", "Business"), back_url="/")


# ═══════════════════════════════════════════════════════════════════════════════
# MOBILE CAPTURE INTERFACE - Dead Simple Photo Capture
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/capture")
def mobile_capture(business_id):
    """Mobile-only capture interface - just photos, nothing else"""
    biz = get_business(business_id)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>📸 {biz.get("name", "Capture")}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #0a0a12 0%, #1a1a2e 100%);
    color: #fff;
    min-height: 100vh;
    min-height: -webkit-fill-available;
    overflow: hidden;
}}
html {{ height: -webkit-fill-available; }}

.app {{
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: -webkit-fill-available;
}}

/* Header */
.header {{
    padding: 15px 20px;
    background: rgba(0,0,0,0.3);
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}}
.biz-name {{
    font-size: 18px;
    font-weight: 800;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.desktop-link {{
    font-size: 12px;
    color: #666;
    text-decoration: none;
    padding: 8px 12px;
    border: 1px solid #333;
    border-radius: 6px;
}}

/* Main capture area */
.capture-area {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 20px;
}}

/* Mode selector */
.mode-selector {{
    display: flex;
    gap: 10px;
    margin-bottom: 40px;
}}
.mode-btn {{
    padding: 12px 24px;
    border-radius: 25px;
    border: 2px solid #333;
    background: transparent;
    color: #888;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
}}
.mode-btn.active {{
    border-color: #3b82f6;
    color: #3b82f6;
    background: rgba(59,130,246,0.1);
}}
.mode-btn.stock.active {{
    border-color: #8b5cf6;
    color: #8b5cf6;
    background: rgba(139,92,246,0.1);
}}
.mode-btn.expense.active {{
    border-color: #ef4444;
    color: #ef4444;
    background: rgba(239,68,68,0.1);
}}

/* Big camera button */
.camera-btn {{
    width: 160px;
    height: 160px;
    border-radius: 50%;
    border: 4px solid #3b82f6;
    background: rgba(59,130,246,0.1);
    color: #3b82f6;
    font-size: 60px;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
}}
.camera-btn:hover {{
    transform: scale(1.05);
    box-shadow: 0 0 40px rgba(59,130,246,0.4);
}}
.camera-btn.stock {{
    border-color: #8b5cf6;
    background: rgba(139,92,246,0.1);
    color: #8b5cf6;
}}
.camera-btn.stock:hover {{
    box-shadow: 0 0 40px rgba(139,92,246,0.4);
}}
.camera-btn.expense {{
    border-color: #ef4444;
    background: rgba(239,68,68,0.1);
    color: #ef4444;
}}
.camera-btn.expense:hover {{
    box-shadow: 0 0 40px rgba(239,68,68,0.4);
}}
.camera-btn-text {{
    position: absolute;
    bottom: -40px;
    font-size: 14px;
    font-weight: 600;
    color: #888;
}}

/* Hidden file input */
.file-input {{ display: none; }}

/* Processing overlay */
.processing {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.95);
    justify-content: center;
    align-items: center;
    flex-direction: column;
    z-index: 100;
}}
.processing.show {{ display: flex; }}
.spinner {{
    width: 60px;
    height: 60px;
    border: 4px solid #333;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.processing-text {{
    margin-top: 20px;
    font-size: 16px;
    color: #888;
}}

/* Success overlay */
.success {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.95);
    justify-content: center;
    align-items: center;
    flex-direction: column;
    padding: 20px;
    z-index: 100;
}}
.success.show {{ display: flex; }}
.success-icon {{
    font-size: 80px;
    margin-bottom: 20px;
}}
.success-title {{
    font-size: 24px;
    font-weight: 800;
    margin-bottom: 10px;
}}
.success-subtitle {{
    font-size: 14px;
    color: #888;
    margin-bottom: 30px;
}}

/* Ledger preview */
.ledger-preview {{
    width: 100%;
    max-width: 350px;
    background: #141420;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 30px;
}}
.ledger-header {{
    background: rgba(59,130,246,0.2);
    padding: 10px 15px;
    font-size: 12px;
    font-weight: 700;
    color: #3b82f6;
    border-bottom: 1px solid #222;
}}
.ledger-row {{
    display: flex;
    justify-content: space-between;
    padding: 12px 15px;
    border-bottom: 1px solid #1a1a2a;
    font-size: 13px;
}}
.ledger-row:last-child {{ border-bottom: none; }}
.ledger-account {{ color: #aaa; }}
.ledger-debit {{ color: #22c55e; }}
.ledger-credit {{ color: #ef4444; }}

.done-btn {{
    padding: 15px 50px;
    border-radius: 30px;
    border: none;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    color: #fff;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
}}

/* Footer stats */
.footer {{
    padding: 15px 20px;
    background: rgba(0,0,0,0.3);
    border-top: 1px solid rgba(255,255,255,0.1);
    display: flex;
    justify-content: space-around;
}}
.stat {{
    text-align: center;
}}
.stat-value {{
    font-size: 20px;
    font-weight: 800;
    color: #3b82f6;
}}
.stat-label {{
    font-size: 10px;
    color: #666;
    text-transform: uppercase;
}}
</style>
</head>
<body>
<div class="app">
    <div class="header">
        <div class="biz-name">📸 {biz.get("name", "Business")}</div>
        <a href="/business/{business_id}?desktop=1" class="desktop-link" onclick="sessionStorage.setItem('forceDesktop','1')">Desktop →</a>
    </div>
    
    <div class="capture-area">
        <div class="mode-selector">
            <button class="mode-btn stock active" onclick="setMode('stock')">📦 Stock</button>
            <button class="mode-btn expense" onclick="setMode('expense')">💸 Expense</button>
        </div>
        
        <button class="camera-btn stock" onclick="document.getElementById('fileInput').click()">
            📷
            <span class="camera-btn-text">Tap to capture</span>
        </button>
        <input type="file" id="fileInput" class="file-input" accept="image/*" capture="environment" onchange="handleCapture(this)">
    </div>
    
    <div class="footer">
        <div class="stat">
            <div class="stat-value" id="todayCount">0</div>
            <div class="stat-label">Today</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="stockCount">{len(biz.get("stock", []))}</div>
            <div class="stat-label">Stock Items</div>
        </div>
        <div class="stat">
            <div class="stat-value" id="expenseCount">{len(biz.get("documents", {{}}).get("supplier_invoices", []))}</div>
            <div class="stat-label">Invoices</div>
        </div>
    </div>
</div>

<!-- Processing Overlay -->
<div class="processing" id="processing">
    <div class="spinner"></div>
    <div class="processing-text">AI is reading your invoice...</div>
</div>

<!-- Success Overlay -->
<div class="success" id="success">
    <div class="success-icon">✅</div>
    <div class="success-title" id="successTitle">Posted!</div>
    <div class="success-subtitle" id="successSubtitle">Document ID: EXP0001</div>
    <div class="ledger-preview" id="ledgerPreview"></div>
    <button class="done-btn" onclick="closeSuccess()">📷 Capture Another</button>
</div>

<script>
var businessId = "{business_id}";
var currentMode = 'stock';
var todayCount = parseInt(localStorage.getItem('todayCount_' + businessId) || '0');
document.getElementById('todayCount').textContent = todayCount;

function setMode(mode) {{
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.mode-btn.' + mode).classList.add('active');
    
    var btn = document.querySelector('.camera-btn');
    btn.className = 'camera-btn ' + mode;
}}

function handleCapture(input) {{
    if (!input.files || !input.files[0]) return;
    
    var file = input.files[0];
    var reader = new FileReader();
    
    reader.onload = function(e) {{
        var base64 = e.target.result.split(',')[1];
        processImage(base64);
    }};
    
    reader.readAsDataURL(file);
    input.value = '';
}}

function processImage(base64) {{
    document.getElementById('processing').classList.add('show');
    
    var endpoint = currentMode === 'stock' 
        ? '/api/business/' + businessId + '/scan-supplier-invoice'
        : '/api/business/' + businessId + '/scan-expense';
    
    fetch(endpoint, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{image: base64}})
    }})
    .then(r => r.json())
    .then(data => {{
        document.getElementById('processing').classList.remove('show');
        
        if (data.success) {{
            // Auto-post without confirmation
            autoPost(data);
        }} else {{
            alert('Could not read invoice: ' + (data.error || 'Unknown error'));
        }}
    }})
    .catch(err => {{
        document.getElementById('processing').classList.remove('show');
        alert('Error: ' + err.message);
    }});
}}

function autoPost(scanData) {{
    document.getElementById('processing').classList.add('show');
    document.querySelector('.processing-text').textContent = 'Posting to ledger...';
    
    var endpoint = currentMode === 'stock'
        ? '/api/business/' + businessId + '/post-supplier-invoice'
        : '/api/business/' + businessId + '/post-expense';
    
    fetch(endpoint, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(scanData)
    }})
    .then(r => r.json())
    .then(data => {{
        document.getElementById('processing').classList.remove('show');
        document.querySelector('.processing-text').textContent = 'AI is reading your invoice...';
        
        if (data.success) {{
            showSuccess(data, scanData);
        }} else {{
            alert('Error posting: ' + (data.error || 'Unknown error'));
        }}
    }})
    .catch(err => {{
        document.getElementById('processing').classList.remove('show');
        alert('Error: ' + err.message);
    }});
}}

function showSuccess(postData, scanData) {{
    todayCount++;
    localStorage.setItem('todayCount_' + businessId, todayCount);
    document.getElementById('todayCount').textContent = todayCount;
    
    document.getElementById('successTitle').textContent = currentMode === 'stock' ? '📦 Stock Posted!' : '💸 Expense Posted!';
    document.getElementById('successSubtitle').textContent = 'Document: ' + postData.document_id + ' • ' + (scanData.supplier?.name || 'Unknown');
    
    // Build ledger preview
    var amtExcl = parseFloat(scanData.amount_excl || scanData.total_excl || 0).toFixed(2);
    var amtVat = parseFloat(scanData.vat || 0).toFixed(2);
    var amtIncl = parseFloat(scanData.amount_incl || scanData.total_incl || 0).toFixed(2);
    
    var html = '<div class="ledger-header">📒 LEDGER ENTRIES</div>';
    
    if (currentMode === 'stock') {{
        html += '<div class="ledger-row"><span class="ledger-account">5000 Cost of Sales</span><span class="ledger-debit">R ' + amtExcl + '</span></div>';
        html += '<div class="ledger-row"><span class="ledger-account">2100 VAT Input</span><span class="ledger-debit">R ' + amtVat + '</span></div>';
        html += '<div class="ledger-row"><span class="ledger-account">2000 Creditors</span><span class="ledger-credit">R ' + amtIncl + '</span></div>';
    }} else {{
        var catName = scanData.category_name || 'Expense';
        html += '<div class="ledger-row"><span class="ledger-account">' + catName + '</span><span class="ledger-debit">R ' + amtExcl + '</span></div>';
        html += '<div class="ledger-row"><span class="ledger-account">2100 VAT Input</span><span class="ledger-debit">R ' + amtVat + '</span></div>';
        html += '<div class="ledger-row"><span class="ledger-account">2000 Creditors</span><span class="ledger-credit">R ' + amtIncl + '</span></div>';
    }}
    
    document.getElementById('ledgerPreview').innerHTML = html;
    document.getElementById('success').classList.add('show');
}}

function closeSuccess() {{
    document.getElementById('success').classList.remove('show');
}}
</script>
</body>
</html>'''


@app.route("/business/<business_id>/pos")
def business_pos(business_id):
    """Point of Sale - Full featured POS system"""
    biz = get_business(business_id)
    stock = biz.get("stock", [])
    customers = biz.get("customers", [])
    
    # Build JSON data BEFORE f-string to avoid escaping issues
    # Check both "price" and "sell" fields for price
    stock_json = json.dumps([{
        "code": s.get("code", ""),
        "description": s.get("description", ""),
        "price": float(s.get("price", 0) or s.get("sell", 0) or 0),
        "qty": int(s.get("qty", 0) or 0),
        "category": s.get("category", "General")
    } for s in stock])
    
    customers_json = json.dumps([{
        "code": c.get("code", ""),
        "name": c.get("name", ""),
        "phone": c.get("phone", ""),
        "balance": float(c.get("balance", 0) or 0)
    } for c in customers])
    
    # Get FIXED categories for this business (your 13 buttons)
    categories = get_pos_categories(business_id)
    
    cat_buttons = ""
    for i, cat in enumerate(categories):
        active = " active" if i == 0 else ""
        data_cat = "all" if cat == "All" else cat
        cat_buttons += f'<button class="cat-btn{active}" data-cat="{data_cat}">{cat}</button>'
    
    return f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>POS - {biz.get("name", "Business")}</title>
<style>
:root{{--bg:#0a0a0a;--card:#141414;--green:#22c55e;--blue:#3b82f6;--purple:#8b5cf6;--red:#ef4444;--border:#222;--accent:#22c55e}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui;background:var(--bg);color:#fff;height:100vh;overflow:hidden}}
.header{{background:linear-gradient(135deg,#22c55e,#16a34a);padding:12px 20px;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-size:22px;font-weight:900}}
.back{{color:rgba(255,255,255,0.9);text-decoration:none;font-size:20px;margin-right:15px}}
.nav a{{background:rgba(255,255,255,0.15);padding:8px 15px;border-radius:6px;color:#fff;text-decoration:none;margin-left:8px;font-size:13px}}
.main{{display:flex;height:calc(100vh - 56px)}}
.left-panel{{flex:1;display:flex;flex-direction:column;border-right:1px solid var(--border);overflow:hidden}}
.search-box{{padding:10px}}
.search-input{{width:100%;padding:12px 15px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:#fff;font-size:15px}}
.search-input:focus{{outline:none;border-color:var(--accent)}}
.categories{{display:flex;flex-wrap:wrap;gap:6px;padding:0 10px 10px 10px}}
.cat-btn{{background:var(--card);border:1px solid var(--border);color:#888;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px;transition:all 0.15s}}
.cat-btn:hover,.cat-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.info-line{{padding:8px 15px;background:var(--card);font-size:12px;color:#666;border-bottom:1px solid var(--border)}}
.stock-scroll{{flex:1;overflow-y:auto;padding:10px}}
.results{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}}
.item{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;cursor:pointer;transition:all 0.15s}}
.item:hover{{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 5px 20px rgba(0,0,0,0.3)}}
.item-code{{font-weight:900;color:var(--accent);font-size:13px}}
.item-desc{{font-size:11px;color:#aaa;margin:5px 0;height:28px;overflow:hidden}}
.item-price{{font-weight:900;color:var(--green);font-size:16px}}
.item-stock{{font-size:10px;color:#666;margin-top:3px}}
.right-panel{{width:350px;min-width:350px;display:flex;flex-direction:column;background:var(--card)}}
.cart-header{{padding:15px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}}
.cart-title{{font-weight:900;font-size:18px}}
.cart-count{{background:var(--accent);padding:3px 10px;border-radius:20px;font-size:12px}}
.cart-scroll{{flex:1;overflow-y:auto;padding:10px}}
.cart-item{{background:var(--bg);border-radius:8px;padding:10px;margin-bottom:8px}}
.cart-item-top{{display:flex;justify-content:space-between;align-items:flex-start}}
.cart-item-code{{font-weight:700;color:var(--accent);font-size:12px}}
.cart-item-desc{{font-size:11px;color:#888;margin:3px 0}}
.cart-item-bottom{{display:flex;justify-content:space-between;align-items:center;margin-top:8px}}
.cart-item-qty{{display:flex;align-items:center;gap:8px}}
.cart-item-qty button{{width:28px;height:28px;border:1px solid var(--border);background:var(--card);color:#fff;border-radius:6px;cursor:pointer;font-weight:700}}
.cart-item-qty button:hover{{background:var(--accent);border-color:var(--accent)}}
.cart-item-qty span{{min-width:30px;text-align:center;font-weight:700}}
.cart-item-total{{font-weight:900;color:var(--green);font-size:14px}}
.cart-item-del{{background:transparent;border:none;color:var(--red);cursor:pointer;font-size:16px;padding:5px}}
.total-box{{padding:15px;border-top:1px solid var(--border);text-align:center}}
.total-label{{font-size:11px;color:#888}}
.total-amount{{font-size:36px;font-weight:900;color:var(--green)}}
.btn-box{{padding:15px;display:flex;flex-direction:column;gap:8px}}
.btn{{width:100%;padding:14px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;transition:all 0.15s}}
.btn:hover{{transform:translateY(-1px)}}
.btn-green{{background:var(--green);color:#fff}}
.btn-blue{{background:var(--blue);color:#fff}}
.btn-red{{background:var(--red);color:#fff}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);justify-content:center;align-items:center;z-index:1000}}
.modal.show{{display:flex}}
.modal-box{{background:var(--card);padding:25px;border-radius:16px;width:90%;max-width:400px}}
.modal-title{{font-size:20px;font-weight:900;margin-bottom:20px;text-align:center}}
.modal-input{{width:100%;padding:15px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:#fff;font-size:16px;margin-bottom:10px}}
.modal-input:focus{{outline:none;border-color:var(--accent)}}
.qty-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:15px 0}}
.qty-btn{{background:var(--bg);border:1px solid var(--border);color:#fff;padding:15px;border-radius:8px;cursor:pointer;font-weight:700;font-size:16px}}
.qty-btn:hover{{background:var(--accent);border-color:var(--accent)}}
.customer-list{{max-height:300px;overflow-y:auto;background:var(--bg);border-radius:8px;margin:10px 0}}
.customer-item{{padding:12px 15px;border-bottom:1px solid var(--border);cursor:pointer}}
.customer-item:hover{{background:var(--accent)}}
.empty-cart{{padding:40px;text-align:center;color:#666}}
.empty-cart-icon{{font-size:48px;margin-bottom:10px}}
</style>
</head>
<body>
<div class="header">
<div style="display:flex;align-items:center">
<a href="/business/{business_id}" class="back">←</a>
<div class="logo">🛒 {biz.get("name", "POS")}</div>
</div>
<div class="nav">
<a href="/business/{business_id}">🏠 Dashboard</a>
<a href="/business/{business_id}/stock">📦 Stock</a>
</div>
</div>

<div class="main">
<div class="left-panel">
<div class="search-box">
<input type="text" id="searchBox" class="search-input" placeholder="🔍 Search item by code or description..." autofocus>
</div>
<div class="categories">{cat_buttons}</div>
<div id="infoLine" class="info-line">Loading...</div>
<div class="stock-scroll">
<div id="results" class="results"></div>
</div>
</div>

<div class="right-panel">
<div class="cart-header">
<div class="cart-title">🛒 CART</div>
<div class="cart-count" id="cartCount">0 items</div>
</div>
<div id="cartScroll" class="cart-scroll">
<div class="empty-cart">
<div class="empty-cart-icon">🛒</div>
<div>Cart is empty</div>
</div>
</div>
<div class="total-box">
<div class="total-label">TOTAL</div>
<div class="total-amount" id="cartTotal">R 0.00</div>
</div>
<div class="btn-box">
<button class="btn btn-green" onclick="showCashModal()">💵 CASH</button>
<button class="btn btn-blue" onclick="showAccountModal()">👤 ACCOUNT</button>
<button class="btn btn-red" onclick="clearCart()">🗑️ CLEAR</button>
</div>
</div>
</div>

<!-- Quantity Modal -->
<div id="qtyModal" class="modal">
<div class="modal-box">
<div class="modal-title" style="color:var(--green)">How Many?</div>
<div style="background:var(--bg);padding:15px;border-radius:10px;margin-bottom:15px">
<div id="qtyItemCode" style="font-weight:900;color:var(--accent)"></div>
<div id="qtyItemDesc" style="color:#888;font-size:13px;margin-top:5px"></div>
<div id="qtyItemStock" style="color:#666;font-size:11px;margin-top:5px"></div>
</div>
<div class="qty-grid">
<button class="qty-btn" onclick="setQty(1)">1</button>
<button class="qty-btn" onclick="setQty(5)">5</button>
<button class="qty-btn" onclick="setQty(10)">10</button>
<button class="qty-btn" onclick="setQty(25)">25</button>
<button class="qty-btn" onclick="setQty(50)">50</button>
<button class="qty-btn" onclick="setQty(100)">100</button>
</div>
<input type="number" id="qtyInput" class="modal-input" placeholder="Or type quantity..." min="1" value="1">
<div style="display:flex;gap:10px">
<button class="btn btn-green" style="flex:1" onclick="addToCart()">✅ Add</button>
<button class="btn btn-red" style="flex:1" onclick="closeQtyModal()">Cancel</button>
</div>
</div>
</div>

<!-- Cash Modal -->
<div id="cashModal" class="modal">
<div class="modal-box">
<div class="modal-title" style="color:var(--green)">💵 Cash Sale</div>
<div id="cashTotal" style="font-size:32px;font-weight:900;color:var(--green);text-align:center;margin:20px 0">R 0.00</div>
<button class="btn btn-green" onclick="completeCashSale()">✅ Complete Sale</button>
<button class="btn btn-red" style="margin-top:10px" onclick="closeCashModal()">Cancel</button>
</div>
</div>

<!-- Account Modal -->
<div id="accountModal" class="modal">
<div class="modal-box" style="max-width:500px">
<div class="modal-title" style="color:var(--blue)">👤 Account Sale</div>
<div id="accountTotal" style="font-size:28px;font-weight:900;color:var(--blue);text-align:center;margin:15px 0">R 0.00</div>
<input type="text" id="customerSearch" class="modal-input" placeholder="🔍 Search customer..." oninput="filterCustomers()">
<div class="customer-list" id="customerList"></div>
<div id="selectedCustomerBox" style="display:none;background:var(--bg);padding:15px;border-radius:8px;margin:10px 0">
<div style="color:#888;font-size:12px">Selected:</div>
<div id="selectedCustomerName" style="font-weight:900;color:var(--blue);font-size:18px"></div>
</div>
<button class="btn btn-blue" id="completeAccountBtn" onclick="completeAccountSale()" disabled style="opacity:0.5">✅ Complete Account Sale</button>
<button class="btn btn-red" style="margin-top:10px" onclick="closeAccountModal()">Cancel</button>
</div>
</div>

<script>
var businessId = '{business_id}';
var stock = {stock_json};
var customers = {customers_json};
var cart = [];
var selectedItem = null;
var selectedCustomer = null;
var currentCat = 'all';

// Initialize
renderStock();
document.getElementById('infoLine').textContent = stock.length + ' items loaded';

// Search
document.getElementById('searchBox').addEventListener('input', renderStock);

// Categories
document.querySelectorAll('.cat-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
        document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        currentCat = this.dataset.cat;
        renderStock();
    }});
}});

function renderStock() {{
    var search = document.getElementById('searchBox').value.toLowerCase();
    var filtered = stock.filter(function(item) {{
        if (currentCat !== 'all' && item.category !== currentCat) return false;
        if (search && !item.code.toLowerCase().includes(search) && !item.description.toLowerCase().includes(search)) return false;
        return true;
    }});
    
    var html = '';
    filtered.slice(0, 100).forEach(function(item) {{
        html += '<div class="item" onclick="pickItem(\\'' + item.code.replace(/'/g, "\\\\'") + '\\')">';
        html += '<div class="item-code">' + item.code + '</div>';
        html += '<div class="item-desc">' + item.description.substring(0, 40) + '</div>';
        html += '<div class="item-price">R ' + item.price.toFixed(2) + '</div>';
        html += '<div class="item-stock">Stock: ' + item.qty + '</div>';
        html += '</div>';
    }});
    
    document.getElementById('results').innerHTML = html || '<div style="padding:40px;text-align:center;color:#666">No items found</div>';
    document.getElementById('infoLine').textContent = 'Showing ' + Math.min(filtered.length, 100) + ' of ' + filtered.length + ' items';
}}

function pickItem(code) {{
    selectedItem = stock.find(s => s.code === code);
    if (!selectedItem) return;
    document.getElementById('qtyItemCode').textContent = selectedItem.code;
    document.getElementById('qtyItemDesc').textContent = selectedItem.description;
    document.getElementById('qtyItemStock').textContent = 'In stock: ' + selectedItem.qty;
    document.getElementById('qtyInput').value = 1;
    document.getElementById('qtyModal').classList.add('show');
}}

function setQty(n) {{ document.getElementById('qtyInput').value = n; }}
function closeQtyModal() {{ document.getElementById('qtyModal').classList.remove('show'); }}

function addToCart() {{
    if (!selectedItem) return;
    var qty = parseInt(document.getElementById('qtyInput').value) || 1;
    var existing = cart.find(c => c.code === selectedItem.code);
    if (existing) {{ existing.qty += qty; }}
    else {{ cart.push({{code: selectedItem.code, description: selectedItem.description, price: selectedItem.price, qty: qty}}); }}
    closeQtyModal();
    renderCart();
}}

function renderCart() {{
    if (cart.length === 0) {{
        document.getElementById('cartScroll').innerHTML = '<div class="empty-cart"><div class="empty-cart-icon">🛒</div><div>Cart is empty</div></div>';
        document.getElementById('cartCount').textContent = '0 items';
        document.getElementById('cartTotal').textContent = 'R 0.00';
        return;
    }}
    var html = '';
    var total = 0;
    cart.forEach(function(item, i) {{
        var lineTotal = item.price * item.qty;
        total += lineTotal;
        html += '<div class="cart-item">';
        html += '<div class="cart-item-top"><div><div class="cart-item-code">' + item.code + '</div>';
        html += '<div class="cart-item-desc">' + item.description.substring(0, 25) + '</div></div>';
        html += '<button class="cart-item-del" onclick="removeFromCart(' + i + ')">🗑️</button></div>';
        html += '<div class="cart-item-bottom"><div class="cart-item-qty">';
        html += '<button onclick="changeQty(' + i + ', -1)">−</button><span>' + item.qty + '</span><button onclick="changeQty(' + i + ', 1)">+</button></div>';
        html += '<div class="cart-item-total">R ' + lineTotal.toFixed(2) + '</div></div></div>';
    }});
    document.getElementById('cartScroll').innerHTML = html;
    document.getElementById('cartCount').textContent = cart.length + ' items';
    document.getElementById('cartTotal').textContent = 'R ' + total.toFixed(2);
}}

function changeQty(i, d) {{ cart[i].qty += d; if (cart[i].qty <= 0) cart.splice(i, 1); renderCart(); }}
function removeFromCart(i) {{ cart.splice(i, 1); renderCart(); }}
function clearCart() {{ if (cart.length && confirm('Clear cart?')) {{ cart = []; renderCart(); }} }}

function showCashModal() {{
    if (cart.length === 0) {{ alert('Cart is empty'); return; }}
    var total = cart.reduce((s, i) => s + (i.price * i.qty), 0);
    document.getElementById('cashTotal').textContent = 'R ' + total.toFixed(2);
    document.getElementById('cashModal').classList.add('show');
}}
function closeCashModal() {{ document.getElementById('cashModal').classList.remove('show'); }}

function completeCashSale() {{
    fetch('/api/business/' + businessId + '/pos-sale', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{items: cart, type: 'cash'}})
    }}).then(r => r.json()).then(d => {{
        if (d.success) {{ alert('✅ Cash sale R ' + d.total.toFixed(2) + ' complete!'); cart = []; renderCart(); }}
        else {{ alert('Error: ' + d.error); }}
    }});
    closeCashModal();
}}

function showAccountModal() {{
    if (cart.length === 0) {{ alert('Cart is empty'); return; }}
    var total = cart.reduce((s, i) => s + (i.price * i.qty), 0);
    document.getElementById('accountTotal').textContent = 'R ' + total.toFixed(2);
    selectedCustomer = null;
    document.getElementById('selectedCustomerBox').style.display = 'none';
    document.getElementById('completeAccountBtn').disabled = true;
    document.getElementById('completeAccountBtn').style.opacity = '0.5';
    filterCustomers();
    document.getElementById('accountModal').classList.add('show');
}}
function closeAccountModal() {{ document.getElementById('accountModal').classList.remove('show'); }}

function filterCustomers() {{
    var search = (document.getElementById('customerSearch').value || '').toLowerCase();
    var filtered = customers.filter(c => c.name.toLowerCase().includes(search) || c.code.toLowerCase().includes(search));
    var html = '';
    filtered.forEach(function(c) {{
        html += '<div class="customer-item" onclick="selectCustomer(\\'' + c.code + '\\', \\'' + c.name.replace(/'/g, "\\\\'") + '\\')">';
        html += '<div style="font-weight:700">' + c.name + '</div>';
        html += '<div style="font-size:12px;color:#888">' + c.code + ' • Balance: R ' + c.balance.toFixed(2) + '</div></div>';
    }});
    document.getElementById('customerList').innerHTML = html || '<div style="padding:20px;text-align:center;color:#666">No customers</div>';
}}

function selectCustomer(code, name) {{
    selectedCustomer = {{code: code, name: name}};
    document.getElementById('selectedCustomerName').textContent = name + ' (' + code + ')';
    document.getElementById('selectedCustomerBox').style.display = 'block';
    document.getElementById('completeAccountBtn').disabled = false;
    document.getElementById('completeAccountBtn').style.opacity = '1';
}}

function completeAccountSale() {{
    if (!selectedCustomer) {{ alert('Select a customer'); return; }}
    fetch('/api/business/' + businessId + '/pos-sale', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{items: cart, type: 'account', customer_code: selectedCustomer.code, customer_name: selectedCustomer.name}})
    }}).then(r => r.json()).then(d => {{
        if (d.success) {{ alert('✅ Account sale for ' + selectedCustomer.name + ' complete!'); cart = []; renderCart(); }}
        else {{ alert('Error: ' + d.error); }}
    }});
    closeAccountModal();
}}
</script>
</body>
</html>'''


@app.route("/api/business/<business_id>/pos-sale", methods=["POST"])
def api_pos_sale(business_id):
    """Process a POS sale"""
    try:
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return jsonify({"success": False, "error": "Business not found"})
        
        req = request.get_json()
        items = req.get("items", [])
        sale_type = req.get("type", "cash")
        
        # Calculate total
        subtotal = sum(item.get("price", 0) * item.get("qty", 0) for item in items)
        vat = round(subtotal * 0.15, 2)
        total = round(subtotal + vat, 2)
        
        # Generate sale ID
        sale_id = f"SALE{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        timestamp = datetime.now().isoformat()
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        # Ledger entries
        # Debit: Cash/Debtors
        if sale_type == "cash":
            biz["ledger"].append({
                "id": str(uuid.uuid4())[:8],
                "date": date_str,
                "account": "1000",
                "account_name": "Bank/Cash",
                "description": f"Cash Sale {sale_id}",
                "debit": total,
                "credit": 0,
                "document_id": sale_id,
                "created_at": timestamp
            })
        else:
            cust_name = req.get("customer_name", "Customer")
            biz["ledger"].append({
                "id": str(uuid.uuid4())[:8],
                "date": date_str,
                "account": "1200",
                "account_name": "Accounts Receivable",
                "description": f"Account Sale {sale_id} - {cust_name}",
                "debit": total,
                "credit": 0,
                "document_id": sale_id,
                "created_at": timestamp
            })
            # Update customer balance
            cust_code = req.get("customer_code")
            for c in biz.get("customers", []):
                if c.get("code") == cust_code:
                    c["balance"] = c.get("balance", 0) + total
                    break
        
        # Credit: Sales
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": date_str,
            "account": "4000",
            "account_name": "Sales",
            "description": f"Sale {sale_id}",
            "debit": 0,
            "credit": subtotal,
            "document_id": sale_id,
            "created_at": timestamp
        })
        
        # Credit: VAT Output
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": date_str,
            "account": "2200",
            "account_name": "VAT Output",
            "description": f"VAT on Sale {sale_id}",
            "debit": 0,
            "credit": vat,
            "document_id": sale_id,
            "created_at": timestamp
        })
        
        # Update stock quantities
        for item in items:
            for s in biz.get("stock", []):
                if s.get("code") == item.get("code"):
                    s["qty"] = s.get("qty", 0) - item.get("qty", 0)
                    break
        
        save_data(data)
        
        return jsonify({"success": True, "sale_id": sale_id, "total": total})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/business/<business_id>/settings")
def business_settings(business_id):
    """Business settings page"""
    biz = get_business(business_id)
    
    content = f'''
    <div class="container">
        <h1 class="page-title">⚙️ Business Settings</h1>
        <p class="page-subtitle">{biz.get("name", business_id)}</p>
        
        <div class="card">
            <div class="card-title">✏️ Rename Business</div>
            <form action="/business/{business_id}/rename" method="POST">
                <div class="form-group">
                    <label class="form-label">Business Name</label>
                    <input type="text" name="name" class="form-input" value="{biz.get('name', '')}" required>
                </div>
                <button type="submit" class="btn btn-success">✓ Save Name</button>
            </form>
        </div>
        
        <div class="card" style="border:1px solid var(--danger)">
            <div class="card-title" style="color:var(--danger)">🗑️ Danger Zone</div>
            <p style="color:var(--text-muted);margin-bottom:15px">Delete this business and all its data. This cannot be undone!</p>
            <button onclick="confirmDelete()" class="btn" style="background:var(--danger);color:#fff">🗑️ Delete Business</button>
        </div>
    </div>
    
    <script>
    function confirmDelete() {{
        var name = prompt('Type the business name to confirm deletion:\\n{biz.get("name", business_id)}');
        if (name === '{biz.get("name", business_id)}') {{
            window.location.href = '/business/{business_id}/delete';
        }} else if (name !== null) {{
            alert('Name does not match. Deletion cancelled.');
        }}
    }}
    </script>
    '''
    
    return render_page(content, "Settings", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/rename", methods=["POST"])
def business_rename(business_id):
    """Rename a business"""
    data = load_data()
    if business_id in data["businesses"]:
        new_name = request.form.get("name", "").strip()
        if new_name:
            data["businesses"][business_id]["name"] = new_name
            save_data(data)
    return redirect(f"/business/{business_id}/settings")


@app.route("/business/<business_id>/delete")
def business_delete(business_id):
    """Delete a business"""
    data = load_data()
    if business_id in data["businesses"]:
        del data["businesses"][business_id]
        save_data(data)
    return redirect("/")

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - SUPPLIER INVOICE (STOCK/COS)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/supplier-invoice/new")
def supplier_invoice_new(business_id):
    """Step 1: Capture supplier invoice for stock/goods"""
    biz = get_business(business_id)
    
    content = f'''
    <div class="container">
        <h1 class="page-title">📦 Supplier Invoice</h1>
        <p class="page-subtitle">Capture invoice for Stock / Cost of Sales</p>
        
        <!-- Audit Trail -->
        <div class="audit-trail">
            <div class="audit-step active">📸 Capture</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">🤖 AI Read</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">✅ Confirm</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📒 Post</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📊 TB</div>
        </div>
        
        <div class="card">
            <div class="card-title">How do you want to capture?</div>
            <div id="captureInfo" style="background:rgba(59,130,246,0.1);padding:15px;border-radius:10px;margin-bottom:20px;text-align:center"></div>
            
            <div class="btn-row" id="captureButtons">
            </div>
            
            <input type="file" id="cameraInput" accept="image/*" capture="environment" style="display:none" onchange="handleCapture(this)">
            <input type="file" id="fileInput" accept="image/*,.pdf" style="display:none" onchange="handleCapture(this)">
            
            <div style="text-align:center;color:var(--text-muted);margin:20px 0">— or —</div>
            
            <a href="/business/{business_id}/supplier-invoice/manual" class="btn btn-outline">
                ✍️ Enter Manually
            </a>
        </div>
        
        <script>
        // Detect device and show appropriate buttons
        var isMobile = /mobile|android|iphone|ipad/i.test(navigator.userAgent);
        var info = document.getElementById('captureInfo');
        var btns = document.getElementById('captureButtons');
        
        if (isMobile) {{
            info.innerHTML = '📱 Tap to open camera and snap your invoice';
            btns.innerHTML = '<button onclick="document.getElementById(\\'cameraInput\\').click()" class="btn btn-primary" style="font-size:18px;padding:18px">📷 Take Photo</button>';
        }} else {{
            info.innerHTML = '💻 Upload an image, or use your phone at this URL to take photos';
            btns.innerHTML = '<button onclick="document.getElementById(\\'fileInput\\').click()" class="btn btn-primary">📁 Upload Image</button>';
        }}
        </script>
        
        <div id="processingArea" style="display:none">
            <div class="card">
                <div class="processing">
                    <div class="processing-spinner"></div>
                    <div class="processing-text">🤖 AI is reading your invoice...</div>
                    <div class="processing-sub">This may take a few seconds</div>
                </div>
            </div>
        </div>
        
        <div id="previewArea" style="display:none">
            <div class="card">
                <div class="card-title">📄 Preview</div>
                <img id="previewImage" style="max-width:100%;border-radius:10px;margin-bottom:15px">
                <div id="previewResult"></div>
            </div>
        </div>
    </div>
    
    <script>
    var imageData = null;
    var businessId = "{business_id}";
    
    function handleCapture(input) {{
        if (!input.files || !input.files[0]) return;
        
        var file = input.files[0];
        var reader = new FileReader();
        
        reader.onload = function(e) {{
            imageData = e.target.result;
            
            // Show preview
            document.getElementById('previewImage').src = imageData;
            document.getElementById('previewArea').style.display = 'block';
            document.getElementById('processingArea').style.display = 'block';
            
            // Send to AI
            processWithAI();
        }};
        
        reader.readAsDataURL(file);
    }}
    
    function processWithAI() {{
        fetch('/api/business/' + businessId + '/scan-supplier-invoice', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                image: imageData,
                type: 'stock'
            }})
        }})
        .then(r => r.json())
        .then(data => {{
            document.getElementById('processingArea').style.display = 'none';
            
            if (data.success) {{
                // Store result and redirect to confirmation
                sessionStorage.setItem('scannedInvoice', JSON.stringify(data));
                sessionStorage.setItem('invoiceImage', imageData);
                window.location.href = '/business/' + businessId + '/supplier-invoice/confirm';
            }} else {{
                document.getElementById('previewResult').innerHTML = 
                    '<div style="background:var(--danger);color:#fff;padding:15px;border-radius:10px">' +
                    '❌ ' + (data.error || 'Could not read invoice') + 
                    '</div>' +
                    '<a href="/business/' + businessId + '/supplier-invoice/manual" class="btn btn-warning" style="margin-top:15px">✍️ Enter Manually Instead</a>';
            }}
        }})
        .catch(err => {{
            document.getElementById('processingArea').style.display = 'none';
            document.getElementById('previewResult').innerHTML = 
                '<div style="background:var(--danger);color:#fff;padding:15px;border-radius:10px">' +
                '❌ Error: ' + err.message + 
                '</div>' +
                '<a href="/business/' + businessId + '/supplier-invoice/manual" class="btn btn-warning" style="margin-top:15px">✍️ Enter Manually Instead</a>';
        }});
    }}
    </script>
    '''
    
    return render_page(content, "Supplier Invoice", back_url=f"/business/{business_id}")

@app.route("/business/<business_id>/supplier-invoice/manual")
def supplier_invoice_manual(business_id):
    """Manual entry for supplier invoice"""
    biz = get_business(business_id)
    
    # Get suppliers for dropdown
    suppliers = biz.get("suppliers", [])
    supplier_options = '<option value="">-- Select Supplier --</option>'
    supplier_options += '<option value="NEW">➕ New Supplier</option>'
    for s in suppliers:
        supplier_options += f'<option value="{s.get("code", "")}">{s.get("name", "")}</option>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">✍️ Manual Entry</h1>
        <p class="page-subtitle">Enter supplier invoice details</p>
        
        <!-- Audit Trail -->
        <div class="audit-trail">
            <div class="audit-step complete">📸 Capture</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step active">✍️ Manual</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">✅ Confirm</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📒 Post</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📊 TB</div>
        </div>
        
        <div class="card">
            <div class="card-title">📋 Invoice Details</div>
            
            <div class="form-group">
                <label class="form-label">Supplier</label>
                <select id="supplierSelect" class="form-select" onchange="checkNewSupplier()">
                    {supplier_options}
                </select>
            </div>
            
            <div id="newSupplierFields" style="display:none;background:#1a1a1a;padding:15px;border-radius:10px;margin-bottom:20px">
                <div class="form-group" style="margin-bottom:10px">
                    <label class="form-label">Supplier Name</label>
                    <input type="text" id="newSupplierName" class="form-input" placeholder="Supplier name">
                </div>
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">Phone (optional)</label>
                    <input type="text" id="newSupplierPhone" class="form-input" placeholder="Phone number">
                </div>
            </div>
            
            <div class="btn-row">
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">Invoice Number</label>
                    <input type="text" id="invoiceNumber" class="form-input" placeholder="INV-001">
                </div>
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">Invoice Date</label>
                    <input type="date" id="invoiceDate" class="form-input" value="{datetime.now().strftime('%Y-%m-%d')}">
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📦 Line Items</div>
            
            <table class="table" id="itemsTable">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th style="width:80px">Qty</th>
                        <th style="width:100px">Price</th>
                        <th style="width:100px">Total</th>
                        <th style="width:50px"></th>
                    </tr>
                </thead>
                <tbody id="itemsBody">
                </tbody>
            </table>
            
            <button onclick="addItem()" class="btn btn-outline" style="margin-top:15px">
                ➕ Add Item
            </button>
            
            <div class="totals-box">
                <div class="totals-row">
                    <span>Subtotal (excl VAT):</span>
                    <span id="subtotal">R 0.00</span>
                </div>
                <div class="totals-row">
                    <span>VAT (15%):</span>
                    <span id="vatAmount">R 0.00</span>
                </div>
                <div class="totals-row grand">
                    <span>TOTAL:</span>
                    <span class="amount" id="grandTotal">R 0.00</span>
                </div>
            </div>
        </div>
        
        <div class="btn-row">
            <a href="/business/{business_id}/supplier-invoice/new" class="btn btn-secondary">← Back</a>
            <button onclick="proceedToConfirm()" class="btn btn-success">Confirm →</button>
        </div>
    </div>
    
    <script>
    var items = [];
    var businessId = "{business_id}";
    
    function checkNewSupplier() {{
        var sel = document.getElementById('supplierSelect');
        document.getElementById('newSupplierFields').style.display = sel.value === 'NEW' ? 'block' : 'none';
    }}
    
    function addItem() {{
        items.push({{description: '', qty: 1, price: 0}});
        renderItems();
    }}
    
    function removeItem(idx) {{
        items.splice(idx, 1);
        renderItems();
    }}
    
    function updateItem(idx, field, value) {{
        if (field === 'qty') items[idx].qty = parseInt(value) || 1;
        else if (field === 'price') items[idx].price = parseFloat(value) || 0;
        else items[idx][field] = value;
        renderItems();
    }}
    
    function renderItems() {{
        var html = '';
        var subtotal = 0;
        
        items.forEach(function(item, idx) {{
            var lineTotal = item.qty * item.price;
            subtotal += lineTotal;
            
            html += '<tr>' +
                '<td><input type="text" class="form-input" style="padding:8px" value="' + (item.description||'') + '" onchange="updateItem(' + idx + ', \\'description\\', this.value)" placeholder="Description"></td>' +
                '<td><input type="number" class="form-input" style="padding:8px;text-align:center" value="' + item.qty + '" onchange="updateItem(' + idx + ', \\'qty\\', this.value)" min="1"></td>' +
                '<td><input type="number" class="form-input" style="padding:8px;text-align:right" value="' + item.price.toFixed(2) + '" onchange="updateItem(' + idx + ', \\'price\\', this.value)" step="0.01"></td>' +
                '<td style="text-align:right;font-weight:700">R ' + lineTotal.toFixed(2) + '</td>' +
                '<td><button onclick="removeItem(' + idx + ')" style="background:var(--danger);color:#fff;border:none;padding:8px 12px;border-radius:6px;cursor:pointer">✕</button></td>' +
                '</tr>';
        }});
        
        if (items.length === 0) {{
            html = '<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--text-muted)">No items yet - click "Add Item" below</td></tr>';
        }}
        
        document.getElementById('itemsBody').innerHTML = html;
        
        var vat = subtotal * 0.15;
        document.getElementById('subtotal').textContent = 'R ' + subtotal.toFixed(2);
        document.getElementById('vatAmount').textContent = 'R ' + vat.toFixed(2);
        document.getElementById('grandTotal').textContent = 'R ' + (subtotal + vat).toFixed(2);
    }}
    
    function proceedToConfirm() {{
        var supplierSel = document.getElementById('supplierSelect');
        var supplier = {{}};
        
        if (supplierSel.value === 'NEW') {{
            supplier = {{
                code: 'NEW',
                name: document.getElementById('newSupplierName').value,
                phone: document.getElementById('newSupplierPhone').value
            }};
        }} else if (supplierSel.value) {{
            supplier = {{
                code: supplierSel.value,
                name: supplierSel.options[supplierSel.selectedIndex].text
            }};
        }} else {{
            alert('Please select a supplier');
            return;
        }}
        
        if (items.length === 0) {{
            alert('Please add at least one item');
            return;
        }}
        
        var invoiceData = {{
            supplier: supplier,
            invoice_number: document.getElementById('invoiceNumber').value,
            invoice_date: document.getElementById('invoiceDate').value,
            items: items,
            type: 'stock'
        }};
        
        sessionStorage.setItem('scannedInvoice', JSON.stringify({{
            success: true,
            supplier: supplier,
            invoice_number: invoiceData.invoice_number,
            date: invoiceData.invoice_date,
            items: items,
            manual_entry: true
        }}));
        
        window.location.href = '/business/' + businessId + '/supplier-invoice/confirm';
    }}
    
    // Start with one empty item
    addItem();
    </script>
    '''
    
    return render_page(content, "Manual Entry", back_url=f"/business/{business_id}/supplier-invoice/new")

@app.route("/business/<business_id>/supplier-invoice/confirm")
def supplier_invoice_confirm(business_id):
    """Step 2: Confirm scanned/entered invoice data"""
    biz = get_business(business_id)
    
    content = f'''
    <div class="container">
        <h1 class="page-title">✅ Confirm Invoice</h1>
        <p class="page-subtitle">Review and confirm the details</p>
        
        <!-- Audit Trail -->
        <div class="audit-trail">
            <div class="audit-step complete">📸 Capture</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step complete">🤖 AI Read</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step active">✅ Confirm</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📒 Post</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📊 TB</div>
        </div>
        
        <div id="loadingState">
            <div class="card">
                <div class="processing">
                    <div class="processing-spinner"></div>
                    <div class="processing-text">Loading invoice data...</div>
                </div>
            </div>
        </div>
        
        <div id="confirmContent" style="display:none">
            <!-- Filled by JavaScript -->
        </div>
    </div>
    
    <script>
    var businessId = "{business_id}";
    var invoiceData = null;
    
    function loadData() {{
        var stored = sessionStorage.getItem('scannedInvoice');
        if (!stored) {{
            alert('No invoice data found. Please start again.');
            window.location.href = '/business/' + businessId + '/supplier-invoice/new';
            return;
        }}
        
        invoiceData = JSON.parse(stored);
        
        var subtotal = 0;
        var itemsHtml = '';
        
        (invoiceData.items || []).forEach(function(item, idx) {{
            var lineTotal = (item.qty || 1) * (item.price || 0);
            subtotal += lineTotal;
            
            itemsHtml += '<tr>' +
                '<td>' + (item.code || item.description || 'Item ' + (idx+1)) + '</td>' +
                '<td>' + (item.description || '') + '</td>' +
                '<td style="text-align:center">' + (item.qty || 1) + '</td>' +
                '<td style="text-align:right">R ' + (item.price || 0).toFixed(2) + '</td>' +
                '<td style="text-align:right;font-weight:700">R ' + lineTotal.toFixed(2) + '</td>' +
                '</tr>';
        }});
        
        var vat = subtotal * 0.15;
        var total = subtotal + vat;
        
        var html = `
            <div class="card">
                <div class="card-title">👤 Supplier</div>
                <div style="font-size:20px;font-weight:700">${{invoiceData.supplier?.name || 'Unknown Supplier'}}</div>
                <div style="color:var(--text-muted)">Invoice: ${{invoiceData.invoice_number || 'N/A'}} | Date: ${{invoiceData.date || 'N/A'}}</div>
            </div>
            
            <div class="card">
                <div class="card-title">📦 Items</div>
                <table class="table">
                    <thead>
                        <tr><th>Code</th><th>Description</th><th style="text-align:center">Qty</th><th style="text-align:right">Price</th><th style="text-align:right">Total</th></tr>
                    </thead>
                    <tbody>${{itemsHtml}}</tbody>
                </table>
                
                <div class="totals-box">
                    <div class="totals-row">
                        <span>Subtotal (excl VAT):</span>
                        <span>R ${{subtotal.toFixed(2)}}</span>
                    </div>
                    <div class="totals-row">
                        <span>VAT (15%):</span>
                        <span>R ${{vat.toFixed(2)}}</span>
                    </div>
                    <div class="totals-row grand">
                        <span>TOTAL:</span>
                        <span class="amount">R ${{total.toFixed(2)}}</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">📒 This will post to:</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                    <div style="background:#1a1a1a;padding:15px;border-radius:10px">
                        <div style="color:var(--text-muted);font-size:12px">DEBIT</div>
                        <div style="font-weight:700">5100 - Purchases</div>
                        <div style="color:var(--success)">R ${{subtotal.toFixed(2)}}</div>
                    </div>
                    <div style="background:#1a1a1a;padding:15px;border-radius:10px">
                        <div style="color:var(--text-muted);font-size:12px">DEBIT</div>
                        <div style="font-weight:700">2100 - VAT Input</div>
                        <div style="color:var(--success)">R ${{vat.toFixed(2)}}</div>
                    </div>
                </div>
                <div style="background:#1a1a1a;padding:15px;border-radius:10px;margin-top:10px">
                    <div style="color:var(--text-muted);font-size:12px">CREDIT</div>
                    <div style="font-weight:700">2000 - Accounts Payable</div>
                    <div style="color:var(--danger)">R ${{total.toFixed(2)}}</div>
                </div>
            </div>
            
            <div class="btn-row">
                <a href="/business/${{businessId}}/supplier-invoice/new" class="btn btn-secondary">← Edit</a>
                <button onclick="postInvoice()" class="btn btn-success">✓ Post to Ledger</button>
            </div>
        `;
        
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('confirmContent').innerHTML = html;
        document.getElementById('confirmContent').style.display = 'block';
    }}
    
    function postInvoice() {{
        // Post to ledger
        fetch('/api/business/' + businessId + '/post-supplier-invoice', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify(invoiceData)
        }})
        .then(r => r.json())
        .then(data => {{
            if (data.success) {{
                sessionStorage.removeItem('scannedInvoice');
                sessionStorage.removeItem('invoiceImage');
                alert('✓ Invoice posted successfully!\\nDocument: ' + data.document_id);
                window.location.href = '/business/' + businessId + '/ledger';
            }} else {{
                alert('Error: ' + data.error);
            }}
        }});
    }}
    
    loadData();
    </script>
    '''
    
    return render_page(content, "Confirm Invoice", back_url=f"/business/{business_id}/supplier-invoice/manual")

# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/business/<business_id>/scan-supplier-invoice", methods=["POST"])
def api_scan_supplier_invoice(business_id):
    """AI reads supplier invoice image"""
    try:
        import anthropic
        
        api_key = get_api_key()
        if not api_key:
            return jsonify({"success": False, "error": "API key not configured. Go to Settings."})
        
        req = request.get_json()
        image_data = req.get('image', '')
        inv_type = req.get('type', 'stock')  # stock or expense
        
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        biz = get_business(business_id)
        
        prompt = f'''You are reading a supplier invoice for {biz.get("name", "a business")}.

Extract ALL information you can see:
1. Supplier name and details
2. Invoice number
3. Invoice date
4. All line items with quantities and prices
5. VAT amount if shown
6. Total amount

Return ONLY valid JSON:
{{
    "supplier": {{"name": "Supplier Name", "phone": "if visible"}},
    "invoice_number": "INV-123",
    "date": "YYYY-MM-DD",
    "items": [
        {{"code": "SKU or code", "description": "Item description", "qty": 1, "price": 99.99}}
    ],
    "vat": 0.00,
    "total": 0.00
}}

If any field is unclear, use your best guess or empty string.
Always return valid JSON, nothing else.'''
        
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        response_text = message.content[0].text
        
        # Parse JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            result["success"] = True
            return jsonify(result)
        
        return jsonify({"success": False, "error": "Could not parse invoice"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/business/<business_id>/post-supplier-invoice", methods=["POST"])
def api_post_supplier_invoice(business_id):
    """Post supplier invoice to ledger"""
    try:
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return jsonify({"success": False, "error": "Business not found"})
        
        req = request.get_json()
        
        # Calculate totals
        subtotal = sum((item.get("qty", 1) * item.get("price", 0)) for item in req.get("items", []))
        vat = subtotal * 0.15
        total = subtotal + vat
        
        # Generate document ID
        doc_count = len(biz["documents"]["supplier_invoices"]) + 1
        doc_id = f"SINV{doc_count:04d}"
        
        # Create document record
        document = {
            "id": doc_id,
            "type": "supplier_invoice",
            "supplier": req.get("supplier", {}),
            "invoice_number": req.get("invoice_number", ""),
            "date": req.get("date", datetime.now().strftime('%Y-%m-%d')),
            "items": req.get("items", []),
            "subtotal": subtotal,
            "vat": vat,
            "total": total,
            "posted": True,
            "created_at": datetime.now().isoformat()
        }
        
        biz["documents"]["supplier_invoices"].append(document)
        
        # Create ledger entries (double-entry bookkeeping)
        timestamp = datetime.now().isoformat()
        
        # Debit: Purchases (5100)
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": document["date"],
            "account": "5100",
            "account_name": "Purchases",
            "description": f"Supplier invoice {req.get('invoice_number', doc_id)} - {req.get('supplier', {}).get('name', 'Unknown')}",
            "debit": subtotal,
            "credit": 0,
            "document_id": doc_id,
            "created_at": timestamp
        })
        
        # Debit: VAT Input (we'll use 2100 as VAT account, negative for input)
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": document["date"],
            "account": "2100",
            "account_name": "VAT (Input)",
            "description": f"VAT on {req.get('invoice_number', doc_id)}",
            "debit": vat,
            "credit": 0,
            "document_id": doc_id,
            "created_at": timestamp
        })
        
        # Credit: Accounts Payable (2000)
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": document["date"],
            "account": "2000",
            "account_name": "Accounts Payable",
            "description": f"Creditor: {req.get('supplier', {}).get('name', 'Unknown')} - {req.get('invoice_number', doc_id)}",
            "debit": 0,
            "credit": total,
            "document_id": doc_id,
            "created_at": timestamp
        })
        
        # Add supplier if new
        supplier = req.get("supplier", {})
        if supplier.get("code") == "NEW" and supplier.get("name"):
            sup_code = f"SUP{len(biz['suppliers'])+1:03d}"
            biz["suppliers"].append({
                "code": sup_code,
                "name": supplier["name"],
                "phone": supplier.get("phone", ""),
                "created_at": timestamp
            })
        
        save_data(data)
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "total": total
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/business/<business_id>/scan-expense", methods=["POST"])
def api_scan_expense(business_id):
    """AI reads expense invoice image"""
    try:
        import anthropic
        
        api_key = get_api_key()
        if not api_key:
            return jsonify({"success": False, "error": "API key not configured. Go to Settings."})
        
        req = request.get_json()
        image_data = req.get('image', '')
        
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        biz = get_business(business_id)
        
        prompt = f'''You are reading an EXPENSE invoice (like electricity bill, rent, phone bill, etc.) for {biz.get("name", "a business")}.

Extract:
1. Supplier/Company name (who sent the invoice)
2. Invoice number
3. Invoice date
4. Description of what it's for
5. Amount excluding VAT
6. VAT amount
7. Total amount including VAT
8. What type of expense this is

Expense types (pick the best match):
- 6100 = Rent (has VAT)
- 6200 = Water & Electricity / Utilities (has VAT)
- 6300 = Phone & Internet / Telecommunications (has VAT)
- 6400 = Insurance (NO VAT - zero rated)
- 6500 = Repairs & Maintenance (has VAT)
- 6600 = Office Supplies / Stationery (has VAT)
- 6700 = Bank Charges (NO VAT - exempt)
- 6800 = Advertising & Marketing (has VAT)
- 6900 = Professional Fees (Accounting/Legal) (has VAT)
- 6910 = Fuel / Petrol / Diesel (NO VAT - zero rated in SA)
- 6920 = Vehicle Expenses excl Fuel (has VAT)
- 6999 = Other Expense (has VAT)

IMPORTANT: Fuel/Petrol/Diesel has NO VAT in South Africa! If this is a fuel slip, set vat to 0.

Return ONLY valid JSON:
{{
    "supplier": {{"name": "Company Name"}},
    "invoice_number": "INV-123",
    "date": "YYYY-MM-DD",
    "description": "What the invoice is for",
    "category": "6200",
    "category_name": "Water & Electricity",
    "amount_excl": 100.00,
    "vat": 15.00,
    "amount_incl": 115.00
}}

If VAT is not shown separately, calculate it (Total / 1.15 = excl, Total - excl = VAT).
Always return valid JSON, nothing else.'''
        
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        
        response_text = message.content[0].text
        
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            
            # MATH VERIFICATION - AI sometimes gets this wrong!
            amount_excl = float(result.get("amount_excl", 0))
            vat = float(result.get("vat", 0))
            amount_incl = float(result.get("amount_incl", 0))
            
            # Recalculate to verify
            correct_total = round(amount_excl + vat, 2)
            
            # If AI's total is wrong, fix it
            if abs(amount_incl - correct_total) > 0.10:
                print(f"⚠️ AI math error: {amount_excl} + {vat} = {correct_total}, not {amount_incl}")
                result["amount_incl"] = correct_total
            
            result["success"] = True
            return jsonify(result)
        
        return jsonify({"success": False, "error": "Could not parse invoice"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/business/<business_id>/post-expense", methods=["POST"])
def api_post_expense(business_id):
    """Post expense invoice to ledger"""
    try:
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return jsonify({"success": False, "error": "Business not found"})
        
        req = request.get_json()
        
        amount_excl = float(req.get("amount_excl", 0))
        vat = float(req.get("vat", 0))
        # Always recalculate to prevent math errors
        amount_incl = round(amount_excl + vat, 2)
        
        # Generate document ID
        expense_docs = [d for d in biz["documents"].get("supplier_invoices", []) if d.get("expense_type")]
        doc_count = len(expense_docs) + 1
        doc_id = f"EXP{doc_count:04d}"
        
        # Get expense account
        expense_account = req.get("category", "6999")
        category_name = req.get("category_name", "Expense")
        # Remove emoji prefix if present
        expense_name = re.sub(r'^[^\s]+\s+', '', category_name) if category_name else "Expense"
        
        # Create document record
        document = {
            "id": doc_id,
            "type": "expense",
            "expense_type": expense_account,
            "supplier": req.get("supplier", {}),
            "invoice_number": req.get("invoice_number", ""),
            "date": req.get("date", datetime.now().strftime('%Y-%m-%d')),
            "description": req.get("description", ""),
            "amount_excl": amount_excl,
            "vat": vat,
            "amount_incl": amount_incl,
            "posted": True,
            "created_at": datetime.now().isoformat()
        }
        
        if "supplier_invoices" not in biz["documents"]:
            biz["documents"]["supplier_invoices"] = []
        biz["documents"]["supplier_invoices"].append(document)
        
        # Create ledger entries
        timestamp = datetime.now().isoformat()
        supplier_name = req.get("supplier", {}).get("name", "Unknown")
        
        # Debit: Expense Account
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": document["date"],
            "account": expense_account,
            "account_name": req.get("category_name", "Expense"),
            "description": f"{req.get('description', '')} - {supplier_name}",
            "debit": amount_excl,
            "credit": 0,
            "document_id": doc_id,
            "created_at": timestamp
        })
        
        # Debit: VAT Input (if there is VAT)
        if vat > 0:
            biz["ledger"].append({
                "id": str(uuid.uuid4())[:8],
                "date": document["date"],
                "account": "2100",
                "account_name": "VAT (Input)",
                "description": f"VAT on {doc_id}",
                "debit": vat,
                "credit": 0,
                "document_id": doc_id,
                "created_at": timestamp
            })
        
        # Credit: Accounts Payable
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": document["date"],
            "account": "2000",
            "account_name": "Accounts Payable",
            "description": f"Creditor: {supplier_name} - {req.get('invoice_number', doc_id)}",
            "debit": 0,
            "credit": amount_incl,
            "document_id": doc_id,
            "created_at": timestamp
        })
        
        # Add supplier if new
        supplier = req.get("supplier", {})
        if supplier.get("code") == "NEW" and supplier.get("name"):
            sup_code = f"SUP{len(biz['suppliers'])+1:03d}"
            biz["suppliers"].append({
                "code": sup_code,
                "name": supplier["name"],
                "phone": supplier.get("phone", ""),
                "created_at": timestamp
            })
        
        save_data(data)
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "total": amount_incl
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# QUOTE / INVOICE / DELIVERY NOTE APIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/business/<business_id>/create-quote", methods=["POST"])
def api_create_quote(business_id):
    """Create a new quote"""
    try:
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return jsonify({"success": False, "error": "Business not found"})
        
        req = request.get_json()
        
        # Generate quote ID
        quotes = biz.get("documents", {}).get("quotes", [])
        quote_num = len(quotes) + 1
        quote_id = f"QUO{quote_num:04d}"
        
        # Calculate totals
        lines = req.get("lines", [])
        subtotal = sum(line.get("total", 0) for line in lines)
        vat = round(subtotal * 0.15, 2)
        total = round(subtotal + vat, 2)
        
        # Create quote document
        quote = {
            "id": quote_id,
            "type": "quote",
            "customer": req.get("customer", {}),
            "date": datetime.now().strftime('%Y-%m-%d'),
            "valid_until": (datetime.now().replace(day=datetime.now().day + 30)).strftime('%Y-%m-%d'),
            "lines": lines,
            "subtotal": subtotal,
            "vat": vat,
            "total": total,
            "status": "draft",
            "created_at": datetime.now().isoformat()
        }
        
        if "quotes" not in biz.get("documents", {}):
            biz["documents"]["quotes"] = []
        biz["documents"]["quotes"].append(quote)
        
        save_data(data)
        
        # Save to Supabase
        save_document_to_supabase(business_id, quote, "quote")
        
        return jsonify({"success": True, "quote_id": quote_id, "total": total})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/business/<business_id>/create-invoice", methods=["POST"])
def api_create_invoice(business_id):
    """Create invoice directly (without quote)"""
    try:
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return jsonify({"success": False, "error": "Business not found"})
        
        req = request.get_json()
        
        # Generate invoice ID
        invoices = biz.get("documents", {}).get("invoices", [])
        inv_num = len(invoices) + 1
        inv_id = f"INV{inv_num:04d}"
        
        # Calculate totals
        lines = req.get("lines", [])
        subtotal = sum(line.get("total", 0) for line in lines)
        vat = round(subtotal * 0.15, 2)
        total = round(subtotal + vat, 2)
        
        # Create invoice document
        invoice = {
            "id": inv_id,
            "type": "invoice",
            "customer": req.get("customer", {}),
            "date": datetime.now().strftime('%Y-%m-%d'),
            "due_date": (datetime.now().replace(day=datetime.now().day + 30)).strftime('%Y-%m-%d'),
            "lines": lines,
            "subtotal": subtotal,
            "vat": vat,
            "total": total,
            "status": "unpaid",
            "paid_amount": 0,
            "created_at": datetime.now().isoformat()
        }
        
        if "invoices" not in biz.get("documents", {}):
            biz["documents"]["invoices"] = []
        biz["documents"]["invoices"].append(invoice)
        
        # Post to ledger - Debit Debtors, Credit Sales & VAT
        timestamp = datetime.now().isoformat()
        cust_name = req.get("customer", {}).get("name", "Customer")
        
        # Debit: Accounts Receivable
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": invoice["date"],
            "account": "1200",
            "account_name": "Accounts Receivable",
            "description": f"Invoice {inv_id} - {cust_name}",
            "debit": total,
            "credit": 0,
            "document_id": inv_id,
            "created_at": timestamp
        })
        
        # Credit: Sales
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": invoice["date"],
            "account": "4000",
            "account_name": "Sales",
            "description": f"Invoice {inv_id} - {cust_name}",
            "debit": 0,
            "credit": subtotal,
            "document_id": inv_id,
            "created_at": timestamp
        })
        
        # Credit: VAT Output
        if vat > 0:
            biz["ledger"].append({
                "id": str(uuid.uuid4())[:8],
                "date": invoice["date"],
                "account": "2200",
                "account_name": "VAT Output",
                "description": f"VAT on Invoice {inv_id}",
                "debit": 0,
                "credit": vat,
                "document_id": inv_id,
                "created_at": timestamp
            })
        
        # Update customer balance
        for c in biz.get("customers", []):
            if c.get("code") == invoice.get("customer", {}).get("code"):
                c["balance"] = c.get("balance", 0) + total
                break
        
        save_data(data)
        save_document_to_supabase(business_id, invoice, "invoice")
        
        return jsonify({"success": True, "invoice_id": inv_id, "total": total})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/business/<business_id>/convert-to-invoice", methods=["POST"])
def api_convert_to_invoice(business_id):
    """Convert quote to invoice"""
    try:
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return jsonify({"success": False, "error": "Business not found"})
        
        req = request.get_json()
        quote_id = req.get("quote_id")
        
        # Find the quote
        quotes = biz.get("documents", {}).get("quotes", [])
        quote = next((q for q in quotes if q.get("id") == quote_id), None)
        
        if not quote:
            return jsonify({"success": False, "error": "Quote not found"})
        
        # Generate invoice ID
        invoices = biz.get("documents", {}).get("invoices", [])
        inv_num = len(invoices) + 1
        inv_id = f"INV{inv_num:04d}"
        
        # Create invoice from quote
        invoice = {
            "id": inv_id,
            "type": "invoice",
            "quote_id": quote_id,
            "customer": quote.get("customer", {}),
            "date": datetime.now().strftime('%Y-%m-%d'),
            "due_date": (datetime.now().replace(day=datetime.now().day + 30)).strftime('%Y-%m-%d'),
            "lines": quote.get("lines", []),
            "subtotal": quote.get("subtotal", 0),
            "vat": quote.get("vat", 0),
            "total": quote.get("total", 0),
            "status": "unpaid",
            "paid_amount": 0,
            "created_at": datetime.now().isoformat()
        }
        
        if "invoices" not in biz.get("documents", {}):
            biz["documents"]["invoices"] = []
        biz["documents"]["invoices"].append(invoice)
        
        # Mark quote as converted
        quote["status"] = "converted"
        quote["invoice_id"] = inv_id
        
        # Post to ledger - Debit Debtors, Credit Sales & VAT
        timestamp = datetime.now().isoformat()
        cust_name = quote.get("customer", {}).get("name", "Customer")
        
        # Debit: Accounts Receivable
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": invoice["date"],
            "account": "1200",
            "account_name": "Accounts Receivable",
            "description": f"Invoice {inv_id} - {cust_name}",
            "debit": invoice["total"],
            "credit": 0,
            "document_id": inv_id,
            "created_at": timestamp
        })
        
        # Credit: Sales
        biz["ledger"].append({
            "id": str(uuid.uuid4())[:8],
            "date": invoice["date"],
            "account": "4000",
            "account_name": "Sales",
            "description": f"Invoice {inv_id} - {cust_name}",
            "debit": 0,
            "credit": invoice["subtotal"],
            "document_id": inv_id,
            "created_at": timestamp
        })
        
        # Credit: VAT Output
        if invoice["vat"] > 0:
            biz["ledger"].append({
                "id": str(uuid.uuid4())[:8],
                "date": invoice["date"],
                "account": "2200",
                "account_name": "VAT Output",
                "description": f"VAT on Invoice {inv_id}",
                "debit": 0,
                "credit": invoice["vat"],
                "document_id": inv_id,
                "created_at": timestamp
            })
        
        # Update customer balance
        for c in biz.get("customers", []):
            if c.get("code") == invoice.get("customer", {}).get("code"):
                c["balance"] = c.get("balance", 0) + invoice["total"]
                break
        
        save_data(data)
        save_document_to_supabase(business_id, invoice, "invoice")
        
        return jsonify({"success": True, "invoice_id": inv_id, "total": invoice["total"]})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/business/<business_id>/create-delivery-note", methods=["POST"])
def api_create_delivery_note(business_id):
    """Create delivery note from invoice"""
    try:
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return jsonify({"success": False, "error": "Business not found"})
        
        req = request.get_json()
        invoice_id = req.get("invoice_id")
        
        # Find the invoice
        invoices = biz.get("documents", {}).get("invoices", [])
        invoice = next((i for i in invoices if i.get("id") == invoice_id), None)
        
        if not invoice:
            return jsonify({"success": False, "error": "Invoice not found"})
        
        # Generate DN ID
        dns = biz.get("documents", {}).get("delivery_notes", [])
        dn_num = len(dns) + 1
        dn_id = f"DN{dn_num:04d}"
        
        # Create delivery note
        dn = {
            "id": dn_id,
            "type": "delivery_note",
            "invoice_id": invoice_id,
            "customer": invoice.get("customer", {}),
            "date": datetime.now().strftime('%Y-%m-%d'),
            "lines": invoice.get("lines", []),
            "status": "pending",
            "delivered_at": None,
            "created_at": datetime.now().isoformat()
        }
        
        if "delivery_notes" not in biz.get("documents", {}):
            biz["documents"]["delivery_notes"] = []
        biz["documents"]["delivery_notes"].append(dn)
        
        # Mark invoice as DN created
        invoice["delivery_note_id"] = dn_id
        
        save_data(data)
        save_document_to_supabase(business_id, dn, "delivery_note")
        
        return jsonify({"success": True, "dn_id": dn_id})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - LEDGER & TRIAL BALANCE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/ledger")
def business_ledger(business_id):
    """View all ledger entries"""
    biz = get_business(business_id)
    ledger = biz.get("ledger", [])
    
    rows = ""
    for entry in reversed(ledger):  # Most recent first
        debit = f"R {entry.get('debit', 0):,.2f}" if entry.get('debit') else ""
        credit = f"R {entry.get('credit', 0):,.2f}" if entry.get('credit') else ""
        rows += f'''
        <tr>
            <td>{entry.get("date", "")}</td>
            <td><span class="badge badge-info">{entry.get("account", "")}</span></td>
            <td>{entry.get("account_name", "")}</td>
            <td>{entry.get("description", "")[:40]}</td>
            <td style="text-align:right;color:var(--success)">{debit}</td>
            <td style="text-align:right;color:var(--danger)">{credit}</td>
            <td><a href="/business/{business_id}/document/{entry.get('document_id', '')}" style="color:var(--primary)">{entry.get("document_id", "")}</a></td>
        </tr>
        '''
    
    if not rows:
        rows = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted)">No entries yet</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">📒 General Ledger</h1>
        <p class="page-subtitle">{biz.get("name", "Business")} - All transactions</p>
        
        <div class="card">
            <table class="table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Account</th>
                        <th>Name</th>
                        <th>Description</th>
                        <th style="text-align:right">Debit</th>
                        <th style="text-align:right">Credit</th>
                        <th>Doc</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>
    '''
    
    return render_page(content, "Ledger", back_url=f"/business/{business_id}")

@app.route("/business/<business_id>/trial-balance")
def business_trial_balance(business_id):
    """Trial Balance report"""
    biz = get_business(business_id)
    ledger = biz.get("ledger", [])
    
    # Aggregate by account
    accounts = {}
    for entry in ledger:
        acc = entry.get("account", "")
        if acc not in accounts:
            accounts[acc] = {
                "name": entry.get("account_name", CHART_OF_ACCOUNTS.get(acc, {}).get("name", "Unknown")),
                "debit": 0,
                "credit": 0
            }
        accounts[acc]["debit"] += entry.get("debit", 0)
        accounts[acc]["credit"] += entry.get("credit", 0)
    
    rows = ""
    total_debit = 0
    total_credit = 0
    
    for acc_code in sorted(accounts.keys()):
        acc = accounts[acc_code]
        balance_debit = acc["debit"] - acc["credit"] if acc["debit"] > acc["credit"] else 0
        balance_credit = acc["credit"] - acc["debit"] if acc["credit"] > acc["debit"] else 0
        total_debit += balance_debit
        total_credit += balance_credit
        
        rows += f'''
        <tr>
            <td><span class="badge badge-info">{acc_code}</span></td>
            <td>{acc["name"]}</td>
            <td style="text-align:right">{f"R {balance_debit:,.2f}" if balance_debit else ""}</td>
            <td style="text-align:right">{f"R {balance_credit:,.2f}" if balance_credit else ""}</td>
        </tr>
        '''
    
    if not rows:
        rows = '<tr><td colspan="4" style="text-align:center;padding:40px;color:var(--text-muted)">No entries yet</td></tr>'
    
    balance_check = "✓ Balanced" if abs(total_debit - total_credit) < 0.01 else "⚠️ Not Balanced"
    balance_color = "var(--success)" if abs(total_debit - total_credit) < 0.01 else "var(--danger)"
    
    content = f'''
    <div class="container">
        <h1 class="page-title">📊 Trial Balance</h1>
        <p class="page-subtitle">{biz.get("name", "Business")} - {datetime.now().strftime('%d %B %Y')}</p>
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
                <div class="card-title" style="margin:0">Account Balances</div>
                <div style="color:{balance_color};font-weight:700">{balance_check}</div>
            </div>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Code</th>
                        <th>Account Name</th>
                        <th style="text-align:right">Debit</th>
                        <th style="text-align:right">Credit</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
                <tfoot>
                    <tr style="background:#1a1a1a;font-weight:700">
                        <td colspan="2">TOTALS</td>
                        <td style="text-align:right;color:var(--success)">R {total_debit:,.2f}</td>
                        <td style="text-align:right;color:var(--danger)">R {total_credit:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    </div>
    '''
    
    return render_page(content, "Trial Balance", back_url=f"/business/{business_id}")

# ═══════════════════════════════════════════════════════════════════════════════
# PLACEHOLDER ROUTES (to be built)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/expense/new")
def expense_new(business_id):
    """Step 1: Capture expense invoice"""
    biz = get_business(business_id)
    
    content = f'''
    <div class="container">
        <h1 class="page-title">💸 Expense Invoice</h1>
        <p class="page-subtitle">Rent, Water, Electricity, Phone, Insurance, etc.</p>
        
        <!-- Audit Trail -->
        <div class="audit-trail">
            <div class="audit-step active">📸 Capture</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">🤖 AI Read</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">✅ Confirm</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📒 Post</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📊 TB</div>
        </div>
        
        <div class="card">
            <div class="card-title">How do you want to capture?</div>
            <div id="captureInfo" style="background:rgba(59,130,246,0.1);padding:15px;border-radius:10px;margin-bottom:20px;text-align:center"></div>
            
            <div class="btn-row" id="captureButtons">
            </div>
            
            <input type="file" id="cameraInput" accept="image/*" capture="environment" style="display:none" onchange="handleCapture(this)">
            <input type="file" id="fileInput" accept="image/*,.pdf" style="display:none" onchange="handleCapture(this)">
            
            <div style="text-align:center;color:var(--text-muted);margin:20px 0">— or —</div>
            
            <a href="/business/{business_id}/expense/manual" class="btn btn-outline">
                ✍️ Enter Manually
            </a>
        </div>
        
        <script>
        var isMobile = /mobile|android|iphone|ipad/i.test(navigator.userAgent);
        var info = document.getElementById('captureInfo');
        var btns = document.getElementById('captureButtons');
        
        if (isMobile) {{
            info.innerHTML = '📱 Tap to open camera and snap your receipt';
            btns.innerHTML = '<button onclick="document.getElementById(\\'cameraInput\\').click()" class="btn btn-primary" style="font-size:18px;padding:18px">📷 Take Photo</button>';
        }} else {{
            info.innerHTML = '💻 Upload an image, or use your phone at this URL to take photos';
            btns.innerHTML = '<button onclick="document.getElementById(\\'fileInput\\').click()" class="btn btn-primary">📁 Upload Image</button>';
        }}
        </script>
        
        <div id="processingArea" style="display:none">
            <div class="card">
                <div class="processing">
                    <div class="processing-spinner"></div>
                    <div class="processing-text">🤖 AI is reading your invoice...</div>
                    <div class="processing-sub">This may take a few seconds</div>
                </div>
            </div>
        </div>
        
        <div id="previewArea" style="display:none">
            <div class="card">
                <div class="card-title">📄 Preview</div>
                <img id="previewImage" style="max-width:100%;border-radius:10px;margin-bottom:15px">
                <div id="previewResult"></div>
            </div>
        </div>
    </div>
    
    <script>
    var imageData = null;
    var businessId = "{business_id}";
    
    function handleCapture(input) {{
        if (!input.files || !input.files[0]) return;
        
        var file = input.files[0];
        var reader = new FileReader();
        
        reader.onload = function(e) {{
            imageData = e.target.result;
            
            document.getElementById('previewImage').src = imageData;
            document.getElementById('previewArea').style.display = 'block';
            document.getElementById('processingArea').style.display = 'block';
            
            processWithAI();
        }};
        
        reader.readAsDataURL(file);
    }}
    
    function processWithAI() {{
        fetch('/api/business/' + businessId + '/scan-expense', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                image: imageData
            }})
        }})
        .then(r => r.json())
        .then(data => {{
            document.getElementById('processingArea').style.display = 'none';
            
            if (data.success) {{
                sessionStorage.setItem('scannedExpense', JSON.stringify(data));
                sessionStorage.setItem('expenseImage', imageData);
                window.location.href = '/business/' + businessId + '/expense/confirm';
            }} else {{
                document.getElementById('previewResult').innerHTML = 
                    '<div style="background:var(--danger);color:#fff;padding:15px;border-radius:10px">' +
                    '❌ ' + (data.error || 'Could not read invoice') + 
                    '</div>' +
                    '<a href="/business/' + businessId + '/expense/manual" class="btn btn-warning" style="margin-top:15px">✍️ Enter Manually Instead</a>';
            }}
        }})
        .catch(err => {{
            document.getElementById('processingArea').style.display = 'none';
            document.getElementById('previewResult').innerHTML = 
                '<div style="background:var(--danger);color:#fff;padding:15px;border-radius:10px">' +
                '❌ Error: ' + err.message + 
                '</div>' +
                '<a href="/business/' + businessId + '/expense/manual" class="btn btn-warning" style="margin-top:15px">✍️ Enter Manually Instead</a>';
        }});
    }}
    </script>
    '''
    
    return render_page(content, "Expense Invoice", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/expense/manual")
def expense_manual(business_id):
    """Manual entry for expense invoice"""
    biz = get_business(business_id)
    
    # Get suppliers for dropdown
    suppliers = biz.get("suppliers", [])
    supplier_options = '<option value="">-- Select Supplier --</option>'
    supplier_options += '<option value="NEW">➕ New Supplier</option>'
    for s in suppliers:
        supplier_options += f'<option value="{s.get("code", "")}" data-name="{s.get("name", "")}">{s.get("name", "")} ({s.get("code", "")})</option>'
    
    # Expense categories
    expense_categories = '''
        <option value="">-- Select Category --</option>
        <option value="6100" data-vat="yes">🏠 Rent</option>
        <option value="6200" data-vat="yes">💡 Water & Electricity</option>
        <option value="6300" data-vat="yes">📞 Phone & Internet</option>
        <option value="6400" data-vat="no">🛡️ Insurance (No VAT)</option>
        <option value="6500" data-vat="yes">🔧 Repairs & Maintenance</option>
        <option value="6600" data-vat="yes">📎 Office Supplies</option>
        <option value="6700" data-vat="no">🏦 Bank Charges (No VAT)</option>
        <option value="6800" data-vat="yes">📣 Advertising & Marketing</option>
        <option value="6900" data-vat="yes">👔 Professional Fees (Accounting/Legal)</option>
        <option value="6910" data-vat="no">⛽ Fuel (No VAT)</option>
        <option value="6920" data-vat="yes">🚗 Vehicle Expenses (excl Fuel)</option>
        <option value="6999" data-vat="yes">📦 Other Expense</option>
    '''
    
    content = f'''
    <div class="container">
        <h1 class="page-title">✍️ Manual Entry</h1>
        <p class="page-subtitle">Enter expense invoice details</p>
        
        <!-- Audit Trail -->
        <div class="audit-trail">
            <div class="audit-step complete">📸 Capture</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step active">✍️ Manual</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">✅ Confirm</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📒 Post</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📊 TB</div>
        </div>
        
        <div class="card">
            <div class="card-title">📋 Invoice Details</div>
            
            <div class="form-group">
                <label class="form-label">Supplier</label>
                <select id="supplierSelect" class="form-select" onchange="checkNewSupplier()">
                    {supplier_options}
                </select>
            </div>
            
            <div id="newSupplierFields" style="display:none;background:#1a1a1a;padding:15px;border-radius:10px;margin-bottom:20px">
                <div class="form-group" style="margin-bottom:10px">
                    <label class="form-label">Supplier Name</label>
                    <input type="text" id="newSupplierName" class="form-input" placeholder="e.g. City of Johannesburg">
                </div>
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">Phone (optional)</label>
                    <input type="text" id="newSupplierPhone" class="form-input" placeholder="Phone number">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Expense Category</label>
                <select id="expenseCategory" class="form-select" onchange="checkCategoryVat()">
                    {expense_categories}
                </select>
            </div>
            
            <div class="btn-row">
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">Invoice Number</label>
                    <input type="text" id="invoiceNumber" class="form-input" placeholder="INV-001">
                </div>
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">Invoice Date</label>
                    <input type="date" id="invoiceDate" class="form-input" value="{datetime.now().strftime('%Y-%m-%d')}">
                </div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">💰 Amount</div>
            
            <div class="form-group">
                <label class="form-label">Description</label>
                <input type="text" id="description" class="form-input" placeholder="e.g. Electricity for December 2025">
            </div>
            
            <div class="btn-row">
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">Amount (excl VAT)</label>
                    <input type="number" id="amountExcl" class="form-input" placeholder="0.00" step="0.01" oninput="calcTotals()">
                </div>
                <div class="form-group" style="margin-bottom:0">
                    <label class="form-label">VAT (15%)</label>
                    <input type="number" id="vatAmount" class="form-input" placeholder="0.00" step="0.01" oninput="calcFromVat()">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Total (incl VAT)</label>
                <input type="number" id="amountIncl" class="form-input" placeholder="0.00" step="0.01" style="font-size:24px;font-weight:700;color:var(--success)" oninput="calcFromTotal()">
            </div>
            
            <div style="background:#1a1a1a;padding:15px;border-radius:10px;margin-top:15px">
                <label style="display:flex;align-items:center;gap:10px;cursor:pointer">
                    <input type="checkbox" id="noVat" onchange="toggleVat()" style="width:20px;height:20px">
                    <span>No VAT (zero-rated or exempt)</span>
                </label>
            </div>
        </div>
        
        <div class="btn-row">
            <a href="/business/{business_id}/expense/new" class="btn btn-secondary">← Back</a>
            <button onclick="proceedToConfirm()" class="btn btn-success">Confirm →</button>
        </div>
    </div>
    
    <script>
    var businessId = "{business_id}";
    
    function checkNewSupplier() {{
        var sel = document.getElementById('supplierSelect');
        document.getElementById('newSupplierFields').style.display = sel.value === 'NEW' ? 'block' : 'none';
    }}
    
    function checkCategoryVat() {{
        var sel = document.getElementById('expenseCategory');
        var opt = sel.options[sel.selectedIndex];
        var hasVat = opt.dataset.vat !== 'no';
        document.getElementById('noVat').checked = !hasVat;
        toggleVat();
    }}
    
    function calcTotals() {{
        var excl = parseFloat(document.getElementById('amountExcl').value) || 0;
        var noVat = document.getElementById('noVat').checked;
        var vat = noVat ? 0 : excl * 0.15;
        document.getElementById('vatAmount').value = vat.toFixed(2);
        document.getElementById('amountIncl').value = (excl + vat).toFixed(2);
    }}
    
    function calcFromVat() {{
        var vat = parseFloat(document.getElementById('vatAmount').value) || 0;
        var excl = vat / 0.15;
        document.getElementById('amountExcl').value = excl.toFixed(2);
        document.getElementById('amountIncl').value = (excl + vat).toFixed(2);
    }}
    
    function calcFromTotal() {{
        var incl = parseFloat(document.getElementById('amountIncl').value) || 0;
        var noVat = document.getElementById('noVat').checked;
        var excl = noVat ? incl : incl / 1.15;
        var vat = noVat ? 0 : incl - excl;
        document.getElementById('amountExcl').value = excl.toFixed(2);
        document.getElementById('vatAmount').value = vat.toFixed(2);
    }}
    
    function toggleVat() {{
        calcFromTotal();
    }}
    
    function proceedToConfirm() {{
        var supplierSel = document.getElementById('supplierSelect');
        var supplier = {{}};
        
        if (supplierSel.value === 'NEW') {{
            supplier = {{
                code: 'NEW',
                name: document.getElementById('newSupplierName').value
            }};
            if (!supplier.name) {{
                alert('Please enter supplier name');
                return;
            }}
        }} else if (supplierSel.value) {{
            supplier = {{
                code: supplierSel.value,
                name: supplierSel.options[supplierSel.selectedIndex].dataset.name || supplierSel.value
            }};
        }} else {{
            alert('Please select a supplier');
            return;
        }}
        
        var category = document.getElementById('expenseCategory').value;
        if (!category) {{
            alert('Please select an expense category');
            return;
        }}
        
        var amountExcl = parseFloat(document.getElementById('amountExcl').value) || 0;
        if (amountExcl <= 0) {{
            alert('Please enter an amount');
            return;
        }}
        
        var expenseData = {{
            success: true,
            supplier: supplier,
            invoice_number: document.getElementById('invoiceNumber').value,
            date: document.getElementById('invoiceDate').value,
            category: category,
            category_name: document.getElementById('expenseCategory').options[document.getElementById('expenseCategory').selectedIndex].text,
            description: document.getElementById('description').value,
            amount_excl: amountExcl,
            vat: parseFloat(document.getElementById('vatAmount').value) || 0,
            amount_incl: parseFloat(document.getElementById('amountIncl').value) || 0,
            manual_entry: true
        }};
        
        sessionStorage.setItem('scannedExpense', JSON.stringify(expenseData));
        window.location.href = '/business/' + businessId + '/expense/confirm';
    }}
    
    // Load existing data from sessionStorage if editing
    function loadExistingData() {{
        var saved = sessionStorage.getItem('scannedExpense');
        if (saved) {{
            try {{
                var data = JSON.parse(saved);
                console.log('Loading saved expense data:', data);
                
                // Set supplier - handle both AI scan (name only) and manual entry (code + name)
                if (data.supplier) {{
                    if (data.supplier.code && data.supplier.code !== 'NEW') {{
                        // User selected from dropdown before
                        document.getElementById('supplierSelect').value = data.supplier.code;
                    }} else if (data.supplier.name) {{
                        // AI scanned - has name but no code, use NEW supplier
                        document.getElementById('supplierSelect').value = 'NEW';
                        document.getElementById('newSupplierFields').style.display = 'block';
                        document.getElementById('newSupplierName').value = data.supplier.name || '';
                    }}
                }}
                
                // Set category
                if (data.category) {{
                    document.getElementById('expenseCategory').value = data.category;
                    checkCategoryVat();
                }}
                
                // Set other fields
                if (data.invoice_number) document.getElementById('invoiceNumber').value = data.invoice_number;
                if (data.date) document.getElementById('invoiceDate').value = data.date;
                if (data.description) document.getElementById('description').value = data.description;
                
                // Handle amounts - could be numbers or strings
                var amtExcl = parseFloat(data.amount_excl) || 0;
                var amtVat = parseFloat(data.vat) || 0;
                var amtIncl = parseFloat(data.amount_incl) || 0;
                
                if (amtExcl > 0) document.getElementById('amountExcl').value = amtExcl.toFixed(2);
                if (amtVat >= 0) document.getElementById('vatAmount').value = amtVat.toFixed(2);
                if (amtIncl > 0) document.getElementById('amountIncl').value = amtIncl.toFixed(2);
                
                // Check if no VAT (fuel etc)
                if (amtVat === 0 && amtExcl > 0) {{
                    document.getElementById('noVat').checked = true;
                }}
                
                console.log('Expense data loaded successfully');
            }} catch(e) {{
                console.log('Could not load saved data:', e);
            }}
        }}
    }}
    
    // Auto-load on page ready
    loadExistingData();
    </script>
    '''
    
    return render_page(content, "Manual Entry", back_url=f"/business/{business_id}/expense/new")


@app.route("/business/<business_id>/expense/confirm")
def expense_confirm(business_id):
    """Step 2: Confirm expense invoice data"""
    biz = get_business(business_id)
    
    content = f'''
    <div class="container">
        <h1 class="page-title">✅ Confirm Expense</h1>
        <p class="page-subtitle">Review and confirm the details</p>
        
        <!-- Audit Trail -->
        <div class="audit-trail">
            <div class="audit-step complete">📸 Capture</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step complete">🤖 AI Read</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step active">✅ Confirm</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📒 Post</div>
            <div class="audit-arrow">→</div>
            <div class="audit-step">📊 TB</div>
        </div>
        
        <div id="loadingState">
            <div class="card">
                <div class="processing">
                    <div class="processing-spinner"></div>
                    <div class="processing-text">Loading expense data...</div>
                </div>
            </div>
        </div>
        
        <div id="confirmContent" style="display:none">
        </div>
    </div>
    
    <script>
    var businessId = "{business_id}";
    var expenseData = null;
    
    function loadData() {{
        var stored = sessionStorage.getItem('scannedExpense');
        if (!stored) {{
            alert('No expense data found. Please start again.');
            window.location.href = '/business/' + businessId + '/expense/new';
            return;
        }}
        
        expenseData = JSON.parse(stored);
        
        var categoryName = expenseData.category_name || 'Expense';
        var accountCode = expenseData.category || '6999';
        
        var html = `
            <div class="card">
                <div class="card-title">👤 Supplier</div>
                <div style="font-size:20px;font-weight:700">${{expenseData.supplier?.name || 'Unknown Supplier'}}</div>
                <div style="color:var(--text-muted)">Invoice: ${{expenseData.invoice_number || 'N/A'}} | Date: ${{expenseData.date || 'N/A'}}</div>
            </div>
            
            <div class="card">
                <div class="card-title">💸 Expense Details</div>
                <div style="background:#1a1a1a;padding:20px;border-radius:10px;margin-bottom:15px">
                    <div style="color:var(--text-muted);font-size:13px">Category</div>
                    <div style="font-size:20px;font-weight:700">${{categoryName}}</div>
                </div>
                <div style="background:#1a1a1a;padding:20px;border-radius:10px">
                    <div style="color:var(--text-muted);font-size:13px">Description</div>
                    <div style="font-size:18px">${{expenseData.description || 'No description'}}</div>
                </div>
                
                <div class="totals-box">
                    <div class="totals-row">
                        <span>Amount (excl VAT):</span>
                        <span>R ${{(expenseData.amount_excl || 0).toFixed(2)}}</span>
                    </div>
                    <div class="totals-row">
                        <span>VAT (15%):</span>
                        <span>R ${{(expenseData.vat || 0).toFixed(2)}}</span>
                    </div>
                    <div class="totals-row grand">
                        <span>TOTAL:</span>
                        <span class="amount">R ${{(expenseData.amount_incl || 0).toFixed(2)}}</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-title">📒 This will post to:</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                    <div style="background:#1a1a1a;padding:15px;border-radius:10px">
                        <div style="color:var(--text-muted);font-size:12px">DEBIT</div>
                        <div style="font-weight:700">${{accountCode}} - ${{categoryName.replace(/^[^\\s]+ /, '')}}</div>
                        <div style="color:var(--success)">R ${{(expenseData.amount_excl || 0).toFixed(2)}}</div>
                    </div>
                    <div style="background:#1a1a1a;padding:15px;border-radius:10px">
                        <div style="color:var(--text-muted);font-size:12px">DEBIT</div>
                        <div style="font-weight:700">2100 - VAT Input</div>
                        <div style="color:var(--success)">R ${{(expenseData.vat || 0).toFixed(2)}}</div>
                    </div>
                </div>
                <div style="background:#1a1a1a;padding:15px;border-radius:10px;margin-top:10px">
                    <div style="color:var(--text-muted);font-size:12px">CREDIT</div>
                    <div style="font-weight:700">2000 - Accounts Payable</div>
                    <div style="color:var(--danger)">R ${{(expenseData.amount_incl || 0).toFixed(2)}}</div>
                </div>
            </div>
            
            <div class="btn-row">
                <a href="/business/${{businessId}}/expense/manual" class="btn btn-secondary">← Edit</a>
                <button onclick="postExpense()" class="btn btn-success">✓ Post to Ledger</button>
            </div>
        `;
        
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('confirmContent').innerHTML = html;
        document.getElementById('confirmContent').style.display = 'block';
    }}
    
    function postExpense() {{
        fetch('/api/business/' + businessId + '/post-expense', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify(expenseData)
        }})
        .then(r => r.json())
        .then(data => {{
            if (data.success) {{
                sessionStorage.removeItem('scannedExpense');
                sessionStorage.removeItem('expenseImage');
                alert('✓ Expense posted successfully!\\nDocument: ' + data.document_id);
                window.location.href = '/business/' + businessId + '/ledger';
            }} else {{
                alert('Error: ' + data.error);
            }}
        }});
    }}
    
    loadData();
    </script>
    '''
    
    return render_page(content, "Confirm Expense", back_url=f"/business/{business_id}/expense/manual")


# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSE LIST
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/expenses")
def expenses_list(business_id):
    """List all expenses"""
    data = load_data()
    biz = data.get("businesses", {}).get(business_id, {})
    docs = biz.get("documents", {})
    
    # Get expenses from both lists
    expenses = docs.get("expenses", [])
    supplier_exp = [d for d in docs.get("supplier_invoices", []) if d.get("expense_type")]
    all_expenses = expenses + supplier_exp
    
    msg = request.args.get('msg', '')
    alert = f'<div style="background:var(--success);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px">{msg}</div>' if msg else ''
    
    # Category totals
    cat_totals = {}
    total = 0
    for exp in all_expenses:
        cat = exp.get("category_name", "Other")
        amt = exp.get("amount_incl", 0) or exp.get("total", 0)
        total += amt
        cat_totals[cat] = cat_totals.get(cat, 0) + amt
    
    # Table rows
    rows = ""
    for exp in sorted(all_expenses, key=lambda x: x.get("date", ""), reverse=True):
        amt = exp.get("amount_incl", 0) or exp.get("total", 0)
        rows += f'''<tr>
            <td>{exp.get("date", "")}</td>
            <td><a href="/business/{business_id}/document/{exp.get('id')}" style="color:var(--primary)">{exp.get("id", "")}</a></td>
            <td>{exp.get("supplier", {}).get("name", "")}</td>
            <td>{exp.get("category_name", "Other")}</td>
            <td style="text-align:right">R {amt:,.2f}</td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">No expenses yet</td></tr>'
    
    # Category summary
    cat_rows = ""
    for cat, amt in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True):
        cat_rows += f'<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)"><span>{cat}</span><span>R {amt:,.2f}</span></div>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">💸 Expenses</h1>
        <p class="page-subtitle">{len(all_expenses)} expenses • Total: R {total:,.2f}</p>
        
        {alert}
        
        <div class="btn-row" style="margin-bottom:20px">
            <a href="/business/{business_id}/expense/new" class="btn btn-success">➕ Capture Expense</a>
        </div>
        
        <div class="card">
            <div class="card-title">📊 By Category</div>
            {cat_rows if cat_rows else '<p style="color:var(--text-muted)">No expenses</p>'}
            <div style="display:flex;justify-content:space-between;padding:15px 0 0;margin-top:10px;border-top:2px solid var(--primary);font-weight:700;font-size:18px">
                <span>TOTAL</span><span style="color:var(--success)">R {total:,.2f}</span>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📋 All Expenses</div>
            <div style="overflow-x:auto">
                <table class="table">
                    <thead><tr><th>Date</th><th>Doc</th><th>Supplier</th><th>Category</th><th style="text-align:right">Amount</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>
    </div>
    '''
    return render_page(content, "Expenses", back_url=f"/business/{business_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIER INVOICE LIST
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/supplier-invoices")
def supplier_invoices_list(business_id):
    """List supplier invoices"""
    data = load_data()
    biz = data.get("businesses", {}).get(business_id, {})
    invoices = [d for d in biz.get("documents", {}).get("supplier_invoices", []) if not d.get("expense_type")]
    
    total = sum(inv.get("total", 0) for inv in invoices)
    
    rows = ""
    for inv in sorted(invoices, key=lambda x: x.get("date", ""), reverse=True):
        rows += f'''<tr>
            <td>{inv.get("date", "")}</td>
            <td><a href="/business/{business_id}/document/{inv.get('id')}" style="color:var(--primary)">{inv.get("id", "")}</a></td>
            <td>{inv.get("invoice_number", "")}</td>
            <td>{inv.get("supplier", {}).get("name", "")}</td>
            <td style="text-align:right">R {inv.get("total", 0):,.2f}</td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">No supplier invoices yet</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">📦 Supplier Invoices</h1>
        <p class="page-subtitle">{len(invoices)} invoices • Total: R {total:,.2f}</p>
        
        <div class="btn-row" style="margin-bottom:20px">
            <a href="/business/{business_id}/supplier-invoice/new" class="btn btn-success">➕ Capture Invoice</a>
        </div>
        
        <div class="card">
            <div style="overflow-x:auto">
                <table class="table">
                    <thead><tr><th>Date</th><th>Doc</th><th>Invoice #</th><th>Supplier</th><th style="text-align:right">Amount</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
        </div>
    </div>
    '''
    return render_page(content, "Supplier Invoices", back_url=f"/business/{business_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# PROFIT & LOSS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/profit-loss")
def profit_loss(business_id):
    """P&L Report"""
    data = load_data()
    biz = data.get("businesses", {}).get(business_id, {})
    ledger = biz.get("ledger", [])
    
    income, cos, expenses = 0, 0, 0
    
    for e in ledger:
        acc = e.get("account", "")
        dr, cr = e.get("debit", 0), e.get("credit", 0)
        if acc.startswith("4"): income += cr - dr
        elif acc.startswith("5"): cos += dr - cr
        elif acc.startswith("6"): expenses += dr - cr
    
    gross = income - cos
    net = gross - expenses
    
    content = f'''
    <div class="container">
        <h1 class="page-title">📈 Profit & Loss</h1>
        <p class="page-subtitle">{biz.get("name", "Business")}</p>
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid var(--border)">
                <span style="font-size:18px">Sales / Income</span>
                <span style="font-size:18px;color:var(--success)">R {income:,.2f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid var(--border)">
                <span>Less: Cost of Sales</span>
                <span style="color:var(--danger)">(R {cos:,.2f})</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:2px solid var(--primary);font-weight:700">
                <span>Gross Profit</span>
                <span style="color:{'var(--success)' if gross >= 0 else 'var(--danger)'}">R {gross:,.2f}</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:15px 0;border-bottom:1px solid var(--border)">
                <span>Less: Operating Expenses</span>
                <span style="color:var(--danger)">(R {expenses:,.2f})</span>
            </div>
            <div style="display:flex;justify-content:space-between;padding:20px 0;font-size:24px;font-weight:800;background:{'rgba(34,197,94,0.1)' if net >= 0 else 'rgba(239,68,68,0.1)'};margin:15px -25px -25px;padding:20px 25px;border-radius:0 0 16px 16px">
                <span>NET {'PROFIT' if net >= 0 else 'LOSS'}</span>
                <span style="color:{'var(--success)' if net >= 0 else 'var(--danger)'}">R {abs(net):,.2f}</span>
            </div>
        </div>
    </div>
    '''
    return render_page(content, "Profit & Loss", back_url=f"/business/{business_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# VAT REPORT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/business/<business_id>/vat-report")
def vat_report(business_id):
    """VAT Report"""
    data = load_data()
    biz = data.get("businesses", {}).get(business_id, {})
    ledger = biz.get("ledger", [])
    
    vat_in = sum(e.get("debit", 0) - e.get("credit", 0) for e in ledger if e.get("account") == "2100")
    vat_out = sum(e.get("credit", 0) - e.get("debit", 0) for e in ledger if e.get("account") == "2200")
    net = vat_out - vat_in
    
    content = f'''
    <div class="container">
        <h1 class="page-title">🧾 VAT Report</h1>
        <p class="page-subtitle">{biz.get("name", "Business")}</p>
        
        <div class="card">
            <div class="card-title">📥 VAT Input (Purchases)</div>
            <p style="color:var(--text-muted)">VAT you paid - claim back from SARS</p>
            <div style="font-size:32px;font-weight:800;color:var(--success)">R {vat_in:,.2f}</div>
        </div>
        
        <div class="card">
            <div class="card-title">📤 VAT Output (Sales)</div>
            <p style="color:var(--text-muted)">VAT you collected - owe to SARS</p>
            <div style="font-size:32px;font-weight:800;color:var(--danger)">R {vat_out:,.2f}</div>
        </div>
        
        <div class="card" style="background:{'rgba(239,68,68,0.1)' if net > 0 else 'rgba(34,197,94,0.1)'}">
            <div class="card-title">{'💰 Pay to SARS' if net > 0 else '💵 Refund from SARS'}</div>
            <div style="font-size:36px;font-weight:800;color:{'var(--danger)' if net > 0 else 'var(--success)'}">R {abs(net):,.2f}</div>
        </div>
    </div>
    '''
    return render_page(content, "VAT Report", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/quote/new")
def quote_new(business_id):
    """Create quote - POS Style"""
    return document_creator(business_id, "quote")


@app.route("/business/<business_id>/invoice/new")
def invoice_new(business_id):
    """Create invoice directly - POS Style"""
    return document_creator(business_id, "invoice")


def document_creator(business_id, doc_type):
    """POS-style document creator for quotes and invoices"""
    biz = get_business(business_id)
    stock = biz.get("stock", [])
    customers = biz.get("customers", [])
    
    # Build JSON data BEFORE f-string to avoid escaping issues
    # Check both "price" and "sell" fields for price
    stock_json = json.dumps([{
        "code": s.get("code", ""),
        "description": s.get("description", ""),
        "price": float(s.get("price", 0) or s.get("sell", 0) or 0),
        "qty": int(s.get("qty", 0) or 0),
        "category": s.get("category", "General")
    } for s in stock])
    
    customers_json = json.dumps([{
        "code": c.get("code", ""),
        "name": c.get("name", ""),
        "phone": c.get("phone", ""),
        "balance": float(c.get("balance", 0) or 0)
    } for c in customers])
    
    # Get FIXED categories for this business (your 13 buttons)
    categories = get_pos_categories(business_id)
    
    cat_buttons = ""
    for i, cat in enumerate(categories):
        active = " active" if i == 0 else ""
        data_cat = "all" if cat == "All" else cat
        cat_buttons += f'<button class="cat-btn{active}" data-cat="{data_cat}">{cat}</button>'
    
    title = "📝 New Quote" if doc_type == "quote" else "🧾 New Invoice"
    color = "#8b5cf6" if doc_type == "quote" else "#3b82f6"  # Purple for quote, blue for invoice
    
    return f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - {biz.get("name", "Business")}</title>
<style>
:root{{--bg:#0a0a0a;--card:#141414;--green:#22c55e;--blue:#3b82f6;--purple:#8b5cf6;--red:#ef4444;--border:#222;--accent:{color}}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:system-ui;background:var(--bg);color:#fff;height:100vh;overflow:hidden}}
.header{{background:var(--accent);padding:12px 20px;display:flex;justify-content:space-between;align-items:center}}
.logo{{font-size:22px;font-weight:900}}
.back{{color:rgba(255,255,255,0.9);text-decoration:none;font-size:20px;margin-right:15px}}
.nav a{{background:rgba(255,255,255,0.15);padding:8px 15px;border-radius:6px;color:#fff;text-decoration:none;margin-left:8px;font-size:13px}}
.main{{display:flex;height:calc(100vh - 56px)}}
.left-panel{{flex:1;display:flex;flex-direction:column;border-right:1px solid var(--border);overflow:hidden}}
.customer-bar{{padding:10px;background:var(--card);border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:center}}
.customer-bar input{{flex:1;padding:10px 15px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:#fff;font-size:14px}}
.customer-bar input:focus{{outline:none;border-color:var(--accent)}}
.selected-customer{{background:var(--accent);padding:8px 15px;border-radius:8px;font-weight:700;display:none;align-items:center;gap:10px}}
.selected-customer .remove{{cursor:pointer;opacity:0.7}}
.search-box{{padding:10px}}
.search-input{{width:100%;padding:12px 15px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:#fff;font-size:15px}}
.search-input:focus{{outline:none;border-color:var(--accent)}}
.categories{{display:flex;flex-wrap:wrap;gap:6px;padding:0 10px 10px 10px}}
.cat-btn{{background:var(--card);border:1px solid var(--border);color:#888;padding:6px 12px;border-radius:6px;cursor:pointer;font-size:12px;transition:all 0.15s}}
.cat-btn:hover,.cat-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.info-line{{padding:8px 15px;background:var(--card);font-size:12px;color:#666;border-bottom:1px solid var(--border)}}
.stock-scroll{{flex:1;overflow-y:auto;padding:10px}}
.results{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}}
.item{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;cursor:pointer;transition:all 0.15s}}
.item:hover{{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 5px 20px rgba(0,0,0,0.3)}}
.item-code{{font-weight:900;color:var(--accent);font-size:13px}}
.item-desc{{font-size:11px;color:#aaa;margin:5px 0;height:32px;overflow:hidden}}
.item-price{{font-weight:900;color:var(--green);font-size:16px}}
.item-stock{{font-size:10px;color:#666;margin-top:5px}}
.right-panel{{width:380px;min-width:380px;display:flex;flex-direction:column;background:var(--card)}}
.cart-header{{padding:15px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}}
.cart-title{{font-weight:900;font-size:18px}}
.cart-count{{background:var(--accent);padding:3px 10px;border-radius:20px;font-size:12px}}
.cart-scroll{{flex:1;overflow-y:auto;padding:10px}}
.cart-item{{background:var(--bg);border-radius:8px;padding:12px;margin-bottom:8px}}
.cart-item-top{{display:flex;justify-content:space-between;align-items:flex-start}}
.cart-item-code{{font-weight:700;color:var(--accent);font-size:13px}}
.cart-item-desc{{font-size:11px;color:#888;margin:3px 0}}
.cart-item-bottom{{display:flex;justify-content:space-between;align-items:center;margin-top:8px}}
.cart-item-qty{{display:flex;align-items:center;gap:8px}}
.cart-item-qty button{{width:28px;height:28px;border:1px solid var(--border);background:var(--card);color:#fff;border-radius:6px;cursor:pointer;font-weight:700}}
.cart-item-qty button:hover{{background:var(--accent);border-color:var(--accent)}}
.cart-item-qty span{{min-width:30px;text-align:center;font-weight:700}}
.cart-item-total{{font-weight:900;color:var(--green);font-size:15px}}
.cart-item-del{{background:transparent;border:none;color:var(--red);cursor:pointer;font-size:18px;padding:5px}}
.totals-box{{padding:15px;border-top:1px solid var(--border);background:var(--bg)}}
.totals-row{{display:flex;justify-content:space-between;padding:5px 0;color:#888}}
.totals-row.grand{{font-size:20px;font-weight:900;color:#fff;padding-top:10px;border-top:1px solid var(--border);margin-top:5px}}
.totals-row.grand span:last-child{{color:var(--green)}}
.btn-box{{padding:15px;display:flex;flex-direction:column;gap:8px}}
.btn{{width:100%;padding:14px;border:none;border-radius:8px;font-weight:700;cursor:pointer;font-size:14px;transition:all 0.15s}}
.btn:hover{{transform:translateY(-1px)}}
.btn-green{{background:var(--green);color:#fff}}
.btn-red{{background:var(--red);color:#fff}}
.btn-outline{{background:transparent;border:2px solid var(--border);color:#fff}}
.btn-outline:hover{{border-color:var(--accent)}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);justify-content:center;align-items:center;z-index:1000}}
.modal.show{{display:flex}}
.modal-box{{background:var(--card);padding:25px;border-radius:16px;width:90%;max-width:400px}}
.modal-title{{font-size:20px;font-weight:900;margin-bottom:20px;text-align:center}}
.modal-input{{width:100%;padding:15px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:#fff;font-size:16px;margin-bottom:10px}}
.modal-input:focus{{outline:none;border-color:var(--accent)}}
.qty-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:15px 0}}
.qty-btn{{background:var(--bg);border:1px solid var(--border);color:#fff;padding:15px;border-radius:8px;cursor:pointer;font-weight:700;font-size:16px}}
.qty-btn:hover{{background:var(--accent);border-color:var(--accent)}}
.customer-list{{max-height:300px;overflow-y:auto;background:var(--bg);border-radius:8px;margin:10px 0}}
.customer-item{{padding:12px 15px;border-bottom:1px solid var(--border);cursor:pointer}}
.customer-item:hover{{background:var(--accent)}}
.customer-item-name{{font-weight:700}}
.customer-item-info{{font-size:12px;color:#888}}
.empty-cart{{padding:40px;text-align:center;color:#666}}
.empty-cart-icon{{font-size:48px;margin-bottom:10px}}
</style>
</head>
<body>
<div class="header">
<div style="display:flex;align-items:center">
<a href="/business/{business_id}" class="back">←</a>
<div class="logo">{title}</div>
</div>
<div class="nav">
<a href="/business/{business_id}">🏠 Dashboard</a>
<a href="/business/{business_id}/quotes">📝 Quotes</a>
<a href="/business/{business_id}/invoices">🧾 Invoices</a>
</div>
</div>

<div class="main">
<div class="left-panel">
<div class="customer-bar">
<input type="text" id="customerSearch" placeholder="🔍 Search customer by name or code..." oninput="searchCustomers()">
<div class="selected-customer" id="selectedCustomerBox">
<span id="selectedCustomerName"></span>
<span class="remove" onclick="clearCustomer()">✕</span>
</div>
</div>
<div class="search-box">
<input type="text" id="searchBox" class="search-input" placeholder="🔍 Search item by code or description..." autofocus>
</div>
<div class="categories">{cat_buttons}</div>
<div id="infoLine" class="info-line">Loading items...</div>
<div class="stock-scroll">
<div id="results" class="results"></div>
</div>
</div>

<div class="right-panel">
<div class="cart-header">
<div class="cart-title">🛒 {"QUOTE" if doc_type == "quote" else "INVOICE"}</div>
<div class="cart-count" id="cartCount">0 items</div>
</div>
<div id="cartScroll" class="cart-scroll">
<div class="empty-cart">
<div class="empty-cart-icon">📦</div>
<div>Click items to add</div>
</div>
</div>
<div class="totals-box">
<div class="totals-row"><span>Subtotal:</span><span id="subtotal">R 0.00</span></div>
<div class="totals-row"><span>VAT (15%):</span><span id="vatTotal">R 0.00</span></div>
<div class="totals-row grand"><span>TOTAL:</span><span id="grandTotal">R 0.00</span></div>
</div>
<div class="btn-box">
<button class="btn btn-green" onclick="saveDocument()">✅ CREATE {"QUOTE" if doc_type == "quote" else "INVOICE"}</button>
<button class="btn btn-outline" onclick="clearCart()">🗑️ Clear All</button>
</div>
</div>
</div>

<!-- Quantity Modal -->
<div id="qtyModal" class="modal">
<div class="modal-box">
<div class="modal-title" style="color:var(--accent)">How Many?</div>
<div style="background:var(--bg);padding:15px;border-radius:10px;margin-bottom:15px">
<div id="qtyItemCode" style="font-weight:900;color:var(--accent)"></div>
<div id="qtyItemDesc" style="color:#888;font-size:13px;margin-top:5px"></div>
<div id="qtyItemPrice" style="color:var(--green);font-weight:700;margin-top:5px"></div>
</div>
<div class="qty-grid">
<button class="qty-btn" onclick="setQty(1)">1</button>
<button class="qty-btn" onclick="setQty(5)">5</button>
<button class="qty-btn" onclick="setQty(10)">10</button>
<button class="qty-btn" onclick="setQty(25)">25</button>
<button class="qty-btn" onclick="setQty(50)">50</button>
<button class="qty-btn" onclick="setQty(100)">100</button>
</div>
<input type="number" id="qtyInput" class="modal-input" placeholder="Or type quantity..." min="1" value="1">
<div style="display:flex;gap:10px">
<button class="btn btn-green" style="flex:1" onclick="addToCart()">✅ Add</button>
<button class="btn btn-red" style="flex:1" onclick="closeQtyModal()">Cancel</button>
</div>
</div>
</div>

<!-- Customer Search Modal -->
<div id="customerModal" class="modal">
<div class="modal-box">
<div class="modal-title">👤 Select Customer</div>
<input type="text" id="customerModalSearch" class="modal-input" placeholder="Search customer..." oninput="filterCustomerModal()">
<div class="customer-list" id="customerList"></div>
<button class="btn btn-red" onclick="closeCustomerModal()">Cancel</button>
</div>
</div>

<script>
var businessId = '{business_id}';
var docType = '{doc_type}';
var stock = {stock_json};
var customers = {customers_json};
var cart = [];
var selectedItem = null;
var selectedCustomer = null;
var currentCat = 'all';

// Initialize
renderStock();
document.getElementById('infoLine').textContent = stock.length + ' items loaded';

// Search box
document.getElementById('searchBox').addEventListener('input', renderStock);

// Category buttons
document.querySelectorAll('.cat-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
        document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        currentCat = this.dataset.cat;
        renderStock();
    }});
}});

function renderStock() {{
    var search = document.getElementById('searchBox').value.toLowerCase();
    var filtered = stock.filter(function(item) {{
        if (currentCat !== 'all' && item.category !== currentCat) return false;
        if (search && !item.code.toLowerCase().includes(search) && !item.description.toLowerCase().includes(search)) return false;
        return true;
    }});
    
    var html = '';
    filtered.slice(0, 100).forEach(function(item) {{
        html += '<div class="item" onclick="pickItem(\\'' + item.code.replace(/'/g, "\\\\'") + '\\')">';
        html += '<div class="item-code">' + item.code + '</div>';
        html += '<div class="item-desc">' + item.description.substring(0, 50) + '</div>';
        html += '<div class="item-price">R ' + item.price.toFixed(2) + '</div>';
        html += '<div class="item-stock">In stock: ' + item.qty + '</div>';
        html += '</div>';
    }});
    
    document.getElementById('results').innerHTML = html || '<div style="padding:40px;text-align:center;color:#666">No items found</div>';
    document.getElementById('infoLine').textContent = 'Showing ' + Math.min(filtered.length, 100) + ' of ' + filtered.length + ' items';
}}

function pickItem(code) {{
    selectedItem = stock.find(s => s.code === code);
    if (!selectedItem) return;
    
    document.getElementById('qtyItemCode').textContent = selectedItem.code;
    document.getElementById('qtyItemDesc').textContent = selectedItem.description;
    document.getElementById('qtyItemPrice').textContent = 'R ' + selectedItem.price.toFixed(2) + ' each';
    document.getElementById('qtyInput').value = 1;
    document.getElementById('qtyModal').classList.add('show');
}}

function setQty(n) {{ document.getElementById('qtyInput').value = n; }}

function closeQtyModal() {{
    document.getElementById('qtyModal').classList.remove('show');
    selectedItem = null;
}}

function addToCart() {{
    if (!selectedItem) return;
    var qty = parseInt(document.getElementById('qtyInput').value) || 1;
    
    var existing = cart.find(c => c.code === selectedItem.code);
    if (existing) {{
        existing.qty += qty;
    }} else {{
        cart.push({{
            code: selectedItem.code,
            description: selectedItem.description,
            price: selectedItem.price,
            qty: qty
        }});
    }}
    
    closeQtyModal();
    renderCart();
}}

function renderCart() {{
    if (cart.length === 0) {{
        document.getElementById('cartScroll').innerHTML = '<div class="empty-cart"><div class="empty-cart-icon">📦</div><div>Click items to add</div></div>';
        document.getElementById('cartCount').textContent = '0 items';
        document.getElementById('subtotal').textContent = 'R 0.00';
        document.getElementById('vatTotal').textContent = 'R 0.00';
        document.getElementById('grandTotal').textContent = 'R 0.00';
        return;
    }}
    
    var html = '';
    var subtotal = 0;
    
    cart.forEach(function(item, i) {{
        var lineTotal = item.price * item.qty;
        subtotal += lineTotal;
        
        html += '<div class="cart-item">';
        html += '<div class="cart-item-top">';
        html += '<div><div class="cart-item-code">' + item.code + '</div>';
        html += '<div class="cart-item-desc">' + item.description.substring(0, 30) + '</div></div>';
        html += '<button class="cart-item-del" onclick="removeFromCart(' + i + ')">🗑️</button>';
        html += '</div>';
        html += '<div class="cart-item-bottom">';
        html += '<div class="cart-item-qty">';
        html += '<button onclick="changeQty(' + i + ', -1)">−</button>';
        html += '<span>' + item.qty + '</span>';
        html += '<button onclick="changeQty(' + i + ', 1)">+</button>';
        html += '</div>';
        html += '<div class="cart-item-total">R ' + lineTotal.toFixed(2) + '</div>';
        html += '</div></div>';
    }});
    
    document.getElementById('cartScroll').innerHTML = html;
    document.getElementById('cartCount').textContent = cart.length + ' items';
    
    var vat = subtotal * 0.15;
    var total = subtotal + vat;
    
    document.getElementById('subtotal').textContent = 'R ' + subtotal.toFixed(2);
    document.getElementById('vatTotal').textContent = 'R ' + vat.toFixed(2);
    document.getElementById('grandTotal').textContent = 'R ' + total.toFixed(2);
}}

function changeQty(index, delta) {{
    cart[index].qty += delta;
    if (cart[index].qty <= 0) {{
        cart.splice(index, 1);
    }}
    renderCart();
}}

function removeFromCart(index) {{
    cart.splice(index, 1);
    renderCart();
}}

function clearCart() {{
    if (cart.length === 0) return;
    if (confirm('Clear all items?')) {{
        cart = [];
        renderCart();
    }}
}}

// Customer search
function searchCustomers() {{
    var search = document.getElementById('customerSearch').value.toLowerCase();
    if (search.length < 1) return;
    
    var matches = customers.filter(c => 
        c.name.toLowerCase().includes(search) || 
        c.code.toLowerCase().includes(search)
    );
    
    if (matches.length === 1) {{
        selectCustomer(matches[0]);
    }} else if (matches.length > 1) {{
        showCustomerModal(matches);
    }}
}}

function showCustomerModal(list) {{
    var html = '';
    list.forEach(function(c) {{
        html += '<div class="customer-item" onclick="selectCustomerFromModal(\\'' + c.code + '\\')">';
        html += '<div class="customer-item-name">' + c.name + '</div>';
        html += '<div class="customer-item-info">' + c.code + ' • Balance: R ' + c.balance.toFixed(2) + '</div>';
        html += '</div>';
    }});
    document.getElementById('customerList').innerHTML = html;
    document.getElementById('customerModal').classList.add('show');
}}

function selectCustomerFromModal(code) {{
    var customer = customers.find(c => c.code === code);
    if (customer) selectCustomer(customer);
    closeCustomerModal();
}}

function selectCustomer(customer) {{
    selectedCustomer = customer;
    document.getElementById('selectedCustomerName').textContent = customer.name + ' (' + customer.code + ')';
    document.getElementById('selectedCustomerBox').style.display = 'flex';
    document.getElementById('customerSearch').style.display = 'none';
}}

function clearCustomer() {{
    selectedCustomer = null;
    document.getElementById('selectedCustomerBox').style.display = 'none';
    document.getElementById('customerSearch').style.display = 'block';
    document.getElementById('customerSearch').value = '';
}}

function closeCustomerModal() {{
    document.getElementById('customerModal').classList.remove('show');
}}

function filterCustomerModal() {{
    var search = document.getElementById('customerModalSearch').value.toLowerCase();
    var filtered = customers.filter(c => 
        c.name.toLowerCase().includes(search) || 
        c.code.toLowerCase().includes(search)
    );
    
    var html = '';
    filtered.forEach(function(c) {{
        html += '<div class="customer-item" onclick="selectCustomerFromModal(\\'' + c.code + '\\')">';
        html += '<div class="customer-item-name">' + c.name + '</div>';
        html += '<div class="customer-item-info">' + c.code + ' • Balance: R ' + c.balance.toFixed(2) + '</div>';
        html += '</div>';
    }});
    document.getElementById('customerList').innerHTML = html || '<div style="padding:20px;text-align:center;color:#666">No customers found</div>';
}}

function saveDocument() {{
    if (!selectedCustomer) {{
        alert('Please select a customer first');
        document.getElementById('customerSearch').focus();
        return;
    }}
    
    if (cart.length === 0) {{
        alert('Please add at least one item');
        return;
    }}
    
    var lines = cart.map(function(item) {{
        return {{
            code: item.code,
            description: item.description,
            qty: item.qty,
            price: item.price,
            total: item.qty * item.price
        }};
    }});
    
    var endpoint = docType === 'quote' ? '/api/business/' + businessId + '/create-quote' : '/api/business/' + businessId + '/create-invoice';
    
    fetch(endpoint, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            customer: {{code: selectedCustomer.code, name: selectedCustomer.name}},
            lines: lines
        }})
    }})
    .then(r => r.json())
    .then(data => {{
        if (data.success) {{
            var docId = data.quote_id || data.invoice_id;
            alert((docType === 'quote' ? 'Quote ' : 'Invoice ') + docId + ' created successfully!');
            window.location.href = '/business/' + businessId + '/' + (docType === 'quote' ? 'quotes' : 'invoices');
        }} else {{
            alert('Error: ' + (data.error || 'Unknown error'));
        }}
    }})
    .catch(err => alert('Error: ' + err.message));
}}
</script>
</body>
</html>'''


@app.route("/business/<business_id>/quotes")
def quotes_list(business_id):
    """List all quotes"""
    biz = get_business(business_id)
    quotes = biz.get("documents", {}).get("quotes", [])
    
    rows = ""
    for q in reversed(quotes):
        status_badge = {
            "draft": '<span class="badge badge-info">Draft</span>',
            "sent": '<span class="badge badge-warning">Sent</span>',
            "converted": '<span class="badge badge-success">Converted</span>',
            "expired": '<span class="badge" style="background:rgba(255,255,255,0.1);color:var(--text-muted)">Expired</span>'
        }.get(q.get("status", "draft"), '<span class="badge badge-info">Draft</span>')
        
        convert_btn = ""
        if q.get("status") == "draft":
            convert_btn = f'<button onclick="convertToInvoice(\'{q.get("id")}\')" class="btn btn-success" style="width:auto;padding:8px 15px;font-size:12px">→ Invoice</button>'
        elif q.get("invoice_id"):
            convert_btn = f'<a href="/business/{business_id}/document/{q.get("invoice_id")}" style="color:var(--primary)">{q.get("invoice_id")}</a>'
        
        rows += f'''<tr>
            <td>{q.get("date", "")}</td>
            <td><a href="/business/{business_id}/document/{q.get('id')}" style="color:var(--primary)">{q.get("id", "")}</a></td>
            <td>{q.get("customer", {}).get("name", "")}</td>
            <td style="text-align:right">R {q.get("total", 0):,.2f}</td>
            <td>{status_badge}</td>
            <td>{convert_btn}</td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted)">No quotes yet</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">📝 Quotes</h1>
        <p class="page-subtitle">{len(quotes)} quotes</p>
        
        <div class="btn-row" style="margin-bottom:20px">
            <a href="/business/{business_id}/quote/new" class="btn btn-success">➕ New Quote</a>
        </div>
        
        <div class="card">
            <table class="table">
                <thead>
                    <tr><th>Date</th><th>Quote #</th><th>Customer</th><th style="text-align:right">Total</th><th>Status</th><th>Action</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>
    
    <script>
    function convertToInvoice(quoteId) {{
        if (!confirm('Convert this quote to an invoice?')) return;
        
        fetch('/api/business/{business_id}/convert-to-invoice', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{quote_id: quoteId}})
        }})
        .then(r => r.json())
        .then(data => {{
            if (data.success) {{
                alert('Invoice ' + data.invoice_id + ' created!');
                window.location.reload();
            }} else {{
                alert('Error: ' + data.error);
            }}
        }});
    }}
    </script>
    '''
    return render_page(content, "Quotes", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/invoices")
def invoices_list(business_id):
    """List all invoices"""
    biz = get_business(business_id)
    invoices = biz.get("documents", {}).get("invoices", [])
    
    rows = ""
    for inv in reversed(invoices):
        status_badge = '<span class="badge badge-success">Paid</span>' if inv.get("status") == "paid" else '<span class="badge badge-warning">Unpaid</span>'
        
        dn_btn = ""
        if not inv.get("delivery_note_id"):
            dn_btn = f'<button onclick="createDN(\'{inv.get("id")}\')" class="btn btn-primary" style="width:auto;padding:8px 15px;font-size:12px">→ DN</button>'
        else:
            dn_btn = f'<a href="/business/{business_id}/document/{inv.get("delivery_note_id")}" style="color:var(--primary)">{inv.get("delivery_note_id")}</a>'
        
        rows += f'''<tr>
            <td>{inv.get("date", "")}</td>
            <td><a href="/business/{business_id}/document/{inv.get('id')}" style="color:var(--primary)">{inv.get("id", "")}</a></td>
            <td>{inv.get("customer", {}).get("name", "")}</td>
            <td style="text-align:right">R {inv.get("total", 0):,.2f}</td>
            <td>{status_badge}</td>
            <td>{dn_btn}</td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--text-muted)">No invoices yet. Create a quote first!</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">🧾 Invoices</h1>
        <p class="page-subtitle">{len(invoices)} invoices</p>
        
        <div class="card">
            <table class="table">
                <thead>
                    <tr><th>Date</th><th>Invoice #</th><th>Customer</th><th style="text-align:right">Total</th><th>Status</th><th>Delivery</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>
    
    <script>
    function createDN(invoiceId) {{
        if (!confirm('Create delivery note for this invoice?')) return;
        
        fetch('/api/business/{business_id}/create-delivery-note', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{invoice_id: invoiceId}})
        }})
        .then(r => r.json())
        .then(data => {{
            if (data.success) {{
                alert('Delivery Note ' + data.dn_id + ' created!');
                window.location.href = '/business/{business_id}/delivery-notes';
            }} else {{
                alert('Error: ' + data.error);
            }}
        }});
    }}
    </script>
    '''
    return render_page(content, "Invoices", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/delivery-notes")
def delivery_notes_list(business_id):
    """List all delivery notes"""
    biz = get_business(business_id)
    dns = biz.get("documents", {}).get("delivery_notes", [])
    
    rows = ""
    for dn in reversed(dns):
        status_badge = '<span class="badge badge-success">Delivered</span>' if dn.get("status") == "delivered" else '<span class="badge badge-warning">Pending</span>'
        
        rows += f'''<tr>
            <td>{dn.get("date", "")}</td>
            <td><a href="/business/{business_id}/document/{dn.get('id')}" style="color:var(--primary)">{dn.get("id", "")}</a></td>
            <td>{dn.get("customer", {}).get("name", "")}</td>
            <td><a href="/business/{business_id}/document/{dn.get('invoice_id')}" style="color:var(--primary)">{dn.get("invoice_id", "")}</a></td>
            <td>{status_badge}</td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">No delivery notes yet. Create an invoice first!</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">🚚 Delivery Notes</h1>
        <p class="page-subtitle">{len(dns)} delivery notes</p>
        
        <div class="card">
            <table class="table">
                <thead>
                    <tr><th>Date</th><th>DN #</th><th>Customer</th><th>Invoice</th><th>Status</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>
    '''
    return render_page(content, "Delivery Notes", back_url=f"/business/{business_id}")

@app.route("/business/<business_id>/stock")
def stock_list(business_id):
    """List stock with import option"""
    biz = get_business(business_id)
    stock = biz.get("stock", [])
    
    # Check for import message
    imported = request.args.get('imported', '')
    error = request.args.get('error', '')
    message = ''
    if imported:
        message = f'<div style="background:var(--success);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">✓ Imported {imported} stock items!</div>'
    if error:
        message = f'<div style="background:var(--danger);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">Error: {error}</div>'
    
    rows = ""
    total_value = 0
    for i, s in enumerate(stock):
        qty = s.get("qty", 0)
        cost = s.get("cost", 0)
        price = s.get("price", 0)
        value = qty * cost
        total_value += value
        rows += f'''<tr>
            <td>{s.get("code","")}</td>
            <td>{s.get("description","")}</td>
            <td>{s.get("category","")}</td>
            <td style="text-align:center">{qty}</td>
            <td style="text-align:right">R {cost:,.2f}</td>
            <td style="text-align:right">R {price:,.2f}</td>
            <td>
                <a href="/business/{business_id}/stock/{i}/edit" style="color:var(--primary);text-decoration:none">✏️</a>
                <a href="/business/{business_id}/stock/{i}/delete" style="color:var(--danger);text-decoration:none;margin-left:10px" onclick="return confirm('Delete this item?')">🗑️</a>
            </td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--text-muted)">No stock yet. Import CSV or add manually.</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">📦 Stock</h1>
        <p class="page-subtitle">{biz.get("name", "Business")} - {len(stock)} items | Total Value: R {total_value:,.2f}</p>
        
        {message}
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
                <div class="card-title" style="margin:0">Stock List</div>
                <div style="display:flex;gap:10px">
                    <button onclick="document.getElementById('importModal').style.display='flex'" class="btn btn-primary" style="width:auto;padding:10px 20px">📤 Import CSV</button>
                    <button onclick="document.getElementById('addModal').style.display='flex'" class="btn btn-success" style="width:auto;padding:10px 20px">➕ Add</button>
                </div>
            </div>
            
            <div style="overflow-x:auto">
            <table class="table">
                <thead>
                    <tr><th>Code</th><th>Description</th><th>Category</th><th style="text-align:center">Qty</th><th style="text-align:right">Cost</th><th style="text-align:right">Price</th><th>Actions</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title">📋 CSV Format</div>
            <p style="color:var(--text-muted);margin-bottom:15px">Your CSV should have these columns:</p>
            <code style="background:#1a1a1a;padding:15px;border-radius:8px;display:block;font-size:13px">code,description,category,qty,cost,price</code>
            <p style="color:var(--text-muted);font-size:13px;margin-top:10px">Column names are flexible (Code/CODE/code, Description/desc/name all work)</p>
        </div>
    </div>
    
    <!-- Import Modal -->
    <div id="importModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div class="card" style="max-width:500px;width:100%">
            <h3 style="margin-bottom:20px">📤 Import Stock CSV</h3>
            <form action="/business/{business_id}/stock/import" method="POST" enctype="multipart/form-data">
                <input type="file" name="file" accept=".csv" required style="margin-bottom:20px;width:100%;padding:15px;background:#1a1a1a;border:2px dashed var(--border);border-radius:8px;color:#fff">
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">📤 Import</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('importModal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Add Modal -->
    <div id="addModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div class="card" style="max-width:500px;width:100%">
            <h3 style="margin-bottom:20px">➕ Add Stock Item</h3>
            <form action="/business/{business_id}/stock/add" method="POST">
                <div class="btn-row">
                    <div class="form-group" style="margin-bottom:10px">
                        <label class="form-label">Code</label>
                        <input type="text" name="code" class="form-input" placeholder="SKU001" required>
                    </div>
                    <div class="form-group" style="margin-bottom:10px">
                        <label class="form-label">Category</label>
                        <input type="text" name="category" class="form-input" placeholder="General">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <input type="text" name="description" class="form-input" placeholder="Item description" required>
                </div>
                <div class="btn-row">
                    <div class="form-group" style="margin-bottom:10px">
                        <label class="form-label">Qty</label>
                        <input type="number" name="qty" class="form-input" value="0" min="0">
                    </div>
                    <div class="form-group" style="margin-bottom:10px">
                        <label class="form-label">Cost</label>
                        <input type="number" name="cost" class="form-input" value="0" step="0.01" min="0">
                    </div>
                    <div class="form-group" style="margin-bottom:10px">
                        <label class="form-label">Price</label>
                        <input type="number" name="price" class="form-input" value="0" step="0.01" min="0">
                    </div>
                </div>
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">✓ Add</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('addModal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    '''
    return render_page(content, "Stock", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/stock/import", methods=["POST"])
def stock_import(business_id):
    """Import stock from CSV"""
    try:
        file = request.files['file']
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return redirect(f'/business/{business_id}/stock?error=Business not found')
        
        count = 0
        for row in reader:
            code = row.get('code') or row.get('Code') or row.get('CODE') or row.get('sku') or row.get('SKU') or ''
            desc = row.get('description') or row.get('Description') or row.get('DESCRIPTION') or row.get('desc') or row.get('name') or row.get('Name') or ''
            if code or desc:
                item = {
                    'code': code.strip(),
                    'description': desc.strip(),
                    'category': (row.get('category') or row.get('Category') or row.get('CATEGORY') or 'General').strip(),
                    'qty': int(float(row.get('qty') or row.get('Qty') or row.get('QTY') or row.get('quantity') or row.get('Quantity') or 0)),
                    'cost': float(row.get('cost') or row.get('Cost') or row.get('COST') or 0),
                    'price': float(row.get('price') or row.get('Price') or row.get('PRICE') or row.get('sell') or row.get('Sell') or 0),
                    'created_at': datetime.now().isoformat()
                }
                biz["stock"].append(item)
                count += 1
        
        save_data(data)
        return redirect(f'/business/{business_id}/stock?imported={count}')
    except Exception as e:
        return redirect(f'/business/{business_id}/stock?error={str(e)}')


@app.route("/business/<business_id>/stock/add", methods=["POST"])
def stock_add(business_id):
    """Add single stock item"""
    data = load_data()
    biz = data["businesses"].get(business_id)
    if biz:
        item = {
            'code': request.form.get('code', '').strip(),
            'description': request.form.get('description', '').strip(),
            'category': request.form.get('category', 'General').strip(),
            'qty': int(float(request.form.get('qty', 0) or 0)),
            'cost': float(request.form.get('cost', 0) or 0),
            'price': float(request.form.get('price', 0) or 0),
            'created_at': datetime.now().isoformat()
        }
        biz["stock"].append(item)
        save_data(data)
    return redirect(f'/business/{business_id}/stock')


@app.route("/business/<business_id>/stock/<int:index>/edit", methods=["GET", "POST"])
def stock_edit(business_id, index):
    """Edit stock item"""
    data = load_data()
    biz = data.get("businesses", {}).get(business_id, {})
    stock = biz.get("stock", [])
    
    if index >= len(stock):
        return redirect(f"/business/{business_id}/stock")
    
    item = stock[index]
    
    if request.method == "POST":
        item["code"] = request.form.get("code", "").strip()
        item["description"] = request.form.get("description", "").strip()
        item["category"] = request.form.get("category", "General").strip()
        item["qty"] = int(float(request.form.get("qty", 0) or 0))
        item["cost"] = float(request.form.get("cost", 0) or 0)
        item["price"] = float(request.form.get("price", 0) or 0)
        save_data(data)
        return redirect(f"/business/{business_id}/stock")
    
    content = f'''
    <div class="container">
        <h1 class="page-title">✏️ Edit Stock Item</h1>
        
        <div class="card">
            <form method="POST">
                <div class="btn-row">
                    <div class="form-group" style="flex:1">
                        <label class="form-label">Code</label>
                        <input type="text" name="code" class="form-input" value="{item.get('code', '')}">
                    </div>
                    <div class="form-group" style="flex:1">
                        <label class="form-label">Category</label>
                        <input type="text" name="category" class="form-input" value="{item.get('category', 'General')}">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Description</label>
                    <input type="text" name="description" class="form-input" value="{item.get('description', '')}" required>
                </div>
                <div class="btn-row">
                    <div class="form-group" style="flex:1">
                        <label class="form-label">Qty</label>
                        <input type="number" name="qty" class="form-input" value="{item.get('qty', 0)}">
                    </div>
                    <div class="form-group" style="flex:1">
                        <label class="form-label">Cost</label>
                        <input type="number" name="cost" class="form-input" step="0.01" value="{item.get('cost', 0)}">
                    </div>
                    <div class="form-group" style="flex:1">
                        <label class="form-label">Price</label>
                        <input type="number" name="price" class="form-input" step="0.01" value="{item.get('price', 0)}">
                    </div>
                </div>
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">✓ Save</button>
                    <a href="/business/{business_id}/stock" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
    </div>
    '''
    return render_page(content, "Edit Stock", back_url=f"/business/{business_id}/stock")


@app.route("/business/<business_id>/stock/<int:index>/delete")
def stock_delete(business_id, index):
    """Delete stock item"""
    data = load_data()
    biz = data.get("businesses", {}).get(business_id, {})
    stock = biz.get("stock", [])
    if index < len(stock):
        del stock[index]
        save_data(data)
    return redirect(f"/business/{business_id}/stock")


@app.route("/business/<business_id>/suppliers")
def suppliers_list(business_id):
    """List suppliers with import option"""
    biz = get_business(business_id)
    suppliers = biz.get("suppliers", [])
    
    # Check for import message
    imported = request.args.get('imported', '')
    error = request.args.get('error', '')
    message = ''
    if imported:
        message = f'<div style="background:var(--success);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">✓ Imported {imported} suppliers!</div>'
    if error:
        message = f'<div style="background:var(--danger);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">Error: {error}</div>'
    
    rows = ""
    for s in suppliers:
        rows += f'''<tr>
            <td>{s.get("code","")}</td>
            <td>{s.get("name","")}</td>
            <td>{s.get("phone","")}</td>
            <td>{s.get("email","")}</td>
            <td style="text-align:right">R {s.get("balance",0):,.2f}</td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">No suppliers yet. Import CSV or add manually.</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">👥 Suppliers</h1>
        <p class="page-subtitle">{biz.get("name", "Business")} - {len(suppliers)} suppliers</p>
        
        {message}
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
                <div class="card-title" style="margin:0">Supplier List</div>
                <div style="display:flex;gap:10px">
                    <button onclick="document.getElementById('importModal').style.display='flex'" class="btn btn-primary" style="width:auto;padding:10px 20px">📤 Import CSV</button>
                    <button onclick="document.getElementById('addModal').style.display='flex'" class="btn btn-success" style="width:auto;padding:10px 20px">➕ Add</button>
                </div>
            </div>
            
            <table class="table">
                <thead>
                    <tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th style="text-align:right">Balance</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        
        <div class="card">
            <div class="card-title">📋 CSV Format</div>
            <p style="color:var(--text-muted);margin-bottom:15px">Your CSV should have these columns:</p>
            <code style="background:#1a1a1a;padding:15px;border-radius:8px;display:block;font-size:13px">code,name,phone,email,balance</code>
            <p style="color:var(--text-muted);font-size:13px;margin-top:10px">Column names are flexible (Code/CODE/code all work)</p>
        </div>
    </div>
    
    <!-- Import Modal -->
    <div id="importModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div class="card" style="max-width:500px;width:100%">
            <h3 style="margin-bottom:20px">📤 Import Suppliers CSV</h3>
            <form action="/business/{business_id}/suppliers/import" method="POST" enctype="multipart/form-data">
                <input type="file" name="file" accept=".csv" required style="margin-bottom:20px;width:100%;padding:15px;background:#1a1a1a;border:2px dashed var(--border);border-radius:8px;color:#fff">
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">📤 Import</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('importModal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Add Modal -->
    <div id="addModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div class="card" style="max-width:500px;width:100%">
            <h3 style="margin-bottom:20px">➕ Add Supplier</h3>
            <form action="/business/{business_id}/suppliers/add" method="POST">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input" placeholder="SUP001" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Name</label>
                    <input type="text" name="name" class="form-input" placeholder="Supplier name" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="text" name="phone" class="form-input" placeholder="Phone number">
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input" placeholder="email@example.com">
                </div>
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">✓ Add</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('addModal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    '''
    return render_page(content, "Suppliers", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/suppliers/import", methods=["POST"])
def suppliers_import(business_id):
    """Import suppliers from CSV"""
    try:
        file = request.files['file']
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return redirect(f'/business/{business_id}/suppliers?error=Business not found')
        
        count = 0
        for row in reader:
            code = row.get('code') or row.get('Code') or row.get('CODE') or ''
            name = row.get('name') or row.get('Name') or row.get('NAME') or ''
            if code or name:
                supplier = {
                    'code': code.strip(),
                    'name': name.strip(),
                    'phone': (row.get('phone') or row.get('Phone') or row.get('PHONE') or '').strip(),
                    'email': (row.get('email') or row.get('Email') or row.get('EMAIL') or '').strip(),
                    'balance': float(row.get('balance') or row.get('Balance') or row.get('BALANCE') or 0),
                    'created_at': datetime.now().isoformat()
                }
                biz["suppliers"].append(supplier)
                count += 1
        
        save_data(data)
        return redirect(f'/business/{business_id}/suppliers?imported={count}')
    except Exception as e:
        return redirect(f'/business/{business_id}/suppliers?error={str(e)}')


@app.route("/business/<business_id>/suppliers/add", methods=["POST"])
def suppliers_add(business_id):
    """Add single supplier"""
    data = load_data()
    biz = data["businesses"].get(business_id)
    if biz:
        supplier = {
            'code': request.form.get('code', '').strip(),
            'name': request.form.get('name', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'balance': 0,
            'created_at': datetime.now().isoformat()
        }
        biz["suppliers"].append(supplier)
        save_data(data)
    return redirect(f'/business/{business_id}/suppliers')

@app.route("/business/<business_id>/customers")
def customers_list(business_id):
    """List customers with import option"""
    biz = get_business(business_id)
    customers = biz.get("customers", [])
    
    # Check for import message
    imported = request.args.get('imported', '')
    error = request.args.get('error', '')
    message = ''
    if imported:
        message = f'<div style="background:var(--success);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">✓ Imported {imported} customers!</div>'
    if error:
        message = f'<div style="background:var(--danger);color:#fff;padding:15px;border-radius:10px;margin-bottom:20px;text-align:center">Error: {error}</div>'
    
    rows = ""
    for c in customers:
        rows += f'''<tr>
            <td>{c.get("code","")}</td>
            <td>{c.get("name","")}</td>
            <td>{c.get("phone","")}</td>
            <td>{c.get("email","")}</td>
            <td style="text-align:right">R {c.get("balance",0):,.2f}</td>
        </tr>'''
    
    if not rows:
        rows = '<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--text-muted)">No customers yet. Import CSV or add manually.</td></tr>'
    
    content = f'''
    <div class="container">
        <h1 class="page-title">👤 Customers</h1>
        <p class="page-subtitle">{biz.get("name", "Business")} - {len(customers)} customers</p>
        
        {message}
        
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
                <div class="card-title" style="margin:0">Customer List</div>
                <div style="display:flex;gap:10px">
                    <button onclick="document.getElementById('importModal').style.display='flex'" class="btn btn-primary" style="width:auto;padding:10px 20px">📤 Import CSV</button>
                    <button onclick="document.getElementById('addModal').style.display='flex'" class="btn btn-success" style="width:auto;padding:10px 20px">➕ Add</button>
                </div>
            </div>
            
            <table class="table">
                <thead>
                    <tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th style="text-align:right">Balance</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        
        <div class="card">
            <div class="card-title">📋 CSV Format</div>
            <p style="color:var(--text-muted);margin-bottom:15px">Your CSV should have these columns:</p>
            <code style="background:#1a1a1a;padding:15px;border-radius:8px;display:block;font-size:13px">code,name,phone,email,balance</code>
            <p style="color:var(--text-muted);font-size:13px;margin-top:10px">Column names are flexible (Code/CODE/code all work)</p>
        </div>
    </div>
    
    <!-- Import Modal -->
    <div id="importModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div class="card" style="max-width:500px;width:100%">
            <h3 style="margin-bottom:20px">📤 Import Customers CSV</h3>
            <form action="/business/{business_id}/customers/import" method="POST" enctype="multipart/form-data">
                <input type="file" name="file" accept=".csv" required style="margin-bottom:20px;width:100%;padding:15px;background:#1a1a1a;border:2px dashed var(--border);border-radius:8px;color:#fff">
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">📤 Import</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('importModal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Add Modal -->
    <div id="addModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div class="card" style="max-width:500px;width:100%">
            <h3 style="margin-bottom:20px">➕ Add Customer</h3>
            <form action="/business/{business_id}/customers/add" method="POST">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input" placeholder="CUST001" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Name</label>
                    <input type="text" name="name" class="form-input" placeholder="Customer name" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="text" name="phone" class="form-input" placeholder="Phone number">
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input" placeholder="email@example.com">
                </div>
                <div class="btn-row">
                    <button type="submit" class="btn btn-success">✓ Add</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('addModal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    '''
    return render_page(content, "Customers", back_url=f"/business/{business_id}")


@app.route("/business/<business_id>/customers/import", methods=["POST"])
def customers_import(business_id):
    """Import customers from CSV"""
    try:
        file = request.files['file']
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        
        data = load_data()
        biz = data["businesses"].get(business_id)
        if not biz:
            return redirect(f'/business/{business_id}/customers?error=Business not found')
        
        count = 0
        for row in reader:
            code = row.get('code') or row.get('Code') or row.get('CODE') or ''
            name = row.get('name') or row.get('Name') or row.get('NAME') or ''
            if code or name:
                customer = {
                    'code': code.strip(),
                    'name': name.strip(),
                    'phone': (row.get('phone') or row.get('Phone') or row.get('PHONE') or '').strip(),
                    'email': (row.get('email') or row.get('Email') or row.get('EMAIL') or '').strip(),
                    'balance': float(row.get('balance') or row.get('Balance') or row.get('BALANCE') or 0),
                    'created_at': datetime.now().isoformat()
                }
                biz["customers"].append(customer)
                count += 1
        
        save_data(data)
        return redirect(f'/business/{business_id}/customers?imported={count}')
    except Exception as e:
        return redirect(f'/business/{business_id}/customers?error={str(e)}')


@app.route("/business/<business_id>/customers/add", methods=["POST"])
def customers_add(business_id):
    """Add single customer"""
    data = load_data()
    biz = data["businesses"].get(business_id)
    if biz:
        customer = {
            'code': request.form.get('code', '').strip(),
            'name': request.form.get('name', '').strip(),
            'phone': request.form.get('phone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'balance': 0,
            'created_at': datetime.now().isoformat()
        }
        biz["customers"].append(customer)
        save_data(data)
    return redirect(f'/business/{business_id}/customers')

@app.route("/trial-balance")
def global_trial_balance():
    """Global trial balance across all businesses"""
    return redirect("/")

@app.route("/about")
def about():
    """About Click AI"""
    content = '''
    <div class="container">
        <div style="text-align:center;padding:40px 20px">
            <div style="font-size:80px;margin-bottom:20px">⚡</div>
            <h1 style="font-size:48px;font-weight:900;margin-bottom:10px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Click AI</h1>
            <p style="font-size:20px;color:var(--text-muted);margin-bottom:40px">Fully Automated Accounting System</p>
            
            <div class="card" style="max-width:500px;margin:0 auto">
                <div style="font-size:18px;margin-bottom:20px">
                    From Invoice Photo → Trial Balance<br>
                    <span style="color:var(--success)">Complete Audit Trail</span>
                </div>
                
                <div style="border-top:1px solid var(--border);padding-top:20px;margin-top:20px">
                    <div style="color:var(--text-muted);font-size:14px;margin-bottom:10px">Created by</div>
                    <div style="font-size:24px;font-weight:700">Deon & Claude</div>
                    <div style="color:var(--text-muted);margin-top:5px">December 2025</div>
                </div>
                
                <div style="border-top:1px solid var(--border);padding-top:20px;margin-top:20px">
                    <div style="color:var(--text-muted);font-size:14px;margin-bottom:15px">Built for South African Small Business</div>
                    <div style="display:flex;justify-content:center;gap:15px;flex-wrap:wrap">
                        <span class="badge badge-success">VAT Ready</span>
                        <span class="badge badge-info">ZAR Currency</span>
                        <span class="badge" style="background:var(--purple)">AI Powered</span>
                    </div>
                </div>
            </div>
            
            <div style="margin-top:40px">
                <a href="/" class="btn btn-primary" style="width:auto;padding:15px 40px">🏠 Go to Home</a>
            </div>
            
            <div style="margin-top:60px;color:var(--text-muted);font-size:13px">
                "Making accounting click for everyone"
            </div>
        </div>
    </div>
    '''
    return render_page(content, "About")

@app.route("/business/<business_id>/document/<doc_id>")
def view_document(business_id, doc_id):
    """View any document by ID - for audit trail"""
    biz = get_business(business_id)
    
    # Search all document types
    for doc_type, docs in biz.get("documents", {}).items():
        for doc in docs:
            if doc.get("id") == doc_id:
                # Found it!
                items_html = ""
                for item in doc.get("items", []):
                    line_total = item.get("qty", 1) * item.get("price", 0)
                    items_html += f'''<tr>
                        <td>{item.get("code", "")}</td>
                        <td>{item.get("description", "")}</td>
                        <td style="text-align:center">{item.get("qty", 1)}</td>
                        <td style="text-align:right">R {item.get("price", 0):,.2f}</td>
                        <td style="text-align:right">R {line_total:,.2f}</td>
                    </tr>'''
                
                content = f'''
                <div class="container">
                    <h1 class="page-title">📄 {doc_id}</h1>
                    <p class="page-subtitle">Document Details - Full Audit Trail</p>
                    
                    <div class="card">
                        <div class="card-title">Document Info</div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px">
                            <div>
                                <div style="color:var(--text-muted);font-size:12px">Type</div>
                                <div style="font-weight:700">{doc_type.replace("_", " ").title()}</div>
                            </div>
                            <div>
                                <div style="color:var(--text-muted);font-size:12px">Date</div>
                                <div style="font-weight:700">{doc.get("date", "")}</div>
                            </div>
                            <div>
                                <div style="color:var(--text-muted);font-size:12px">Supplier/Customer</div>
                                <div style="font-weight:700">{doc.get("supplier", {}).get("name", doc.get("customer_name", "N/A"))}</div>
                            </div>
                            <div>
                                <div style="color:var(--text-muted);font-size:12px">Reference</div>
                                <div style="font-weight:700">{doc.get("invoice_number", doc_id)}</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-title">Line Items</div>
                        <table class="table">
                            <thead><tr><th>Code</th><th>Description</th><th>Qty</th><th>Price</th><th>Total</th></tr></thead>
                            <tbody>{items_html}</tbody>
                        </table>
                        
                        <div class="totals-box">
                            <div class="totals-row"><span>Subtotal:</span><span>R {doc.get("subtotal", 0):,.2f}</span></div>
                            <div class="totals-row"><span>VAT:</span><span>R {doc.get("vat", 0):,.2f}</span></div>
                            <div class="totals-row grand"><span>Total:</span><span class="amount">R {doc.get("total", 0):,.2f}</span></div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-title">📒 Ledger Entries</div>
                        <p style="color:var(--text-muted)">Entries linked to this document:</p>
                        <a href="/business/{business_id}/ledger" class="btn btn-outline" style="margin-top:15px">View in Ledger</a>
                    </div>
                </div>
                '''
                return render_page(content, doc_id, back_url=f"/business/{business_id}/ledger")
    
    return "Document not found", 404

# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("⚡ CLICK AI - Fully Automated Accounting")
    print("=" * 60)
    print("✅ Phase 1: Supplier Invoices → Stock/COS")
    print("🚧 Phase 2: Expenses (Coming)")
    print("🚧 Phase 3: Quotes → Invoices → Delivery Notes (Coming)")
    print("=" * 60)
    print("🌐 http://127.0.0.1:5000/")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
