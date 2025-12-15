"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║   CLICK AI v6 - FRESH BUILD                                                   ║
║   Clean Code - All Features - No Embedded JSON                                ║
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
import requests

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gvmonstssdxncfkcjukr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_0msyFLKCiT4EXM-TGZIr6w_mpv5nNWD")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def js_safe(s):
    """Remove characters that break JavaScript"""
    if s is None: return ""
    s = str(s)
    s = re.sub(r'["\'\\\n\r\t]', ' ', s)
    s = re.sub(r'[^\x20-\x7E]', '', s)
    return s.strip()

def fmt_date(d):
    if not d: return ""
    try:
        return datetime.fromisoformat(d.replace('Z','+00:00')).strftime("%Y-%m-%d %H:%M")
    except:
        return str(d)[:16]

# ═══════════════════════════════════════════════════════════════════════════════
# SUPABASE CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class SupabaseClient:
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
    
    def select(self, table, filters=None, limit=1000):
        url = f"{self.url}/rest/v1/{table}?select=*"
        if filters:
            for k, v in filters.items():
                url += f"&{k}=eq.{v}"
        url += f"&limit={limit}"
        try:
            r = requests.get(url, headers=self.headers, timeout=30)
            return r.json() if r.status_code == 200 else []
        except:
            return []
    
    def insert(self, table, data):
        url = f"{self.url}/rest/v1/{table}"
        try:
            r = requests.post(url, headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 201]
        except:
            return False
    
    def update(self, table, id, data):
        url = f"{self.url}/rest/v1/{table}?id=eq.{id}"
        try:
            r = requests.patch(url, headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 204]
        except:
            return False
    
    def delete(self, table, filters):
        url = f"{self.url}/rest/v1/{table}?"
        url += "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
        try:
            r = requests.delete(url, headers=self.headers, timeout=30)
            return r.status_code in [200, 204]
        except:
            return False

db = SupabaseClient(SUPABASE_URL, SUPABASE_KEY)

# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLES
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """<style>
:root{--bg:#0a0a0f;--card:#12121a;--border:#1e1e2e;--text:#e0e0e0;--muted:#888;--blue:#3b82f6;--green:#10b981;--red:#ef4444;--purple:#8b5cf6;--orange:#f59e0b}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.nav{background:var(--card);border-bottom:1px solid var(--border);padding:10px 20px;display:flex;align-items:center;gap:15px;flex-wrap:wrap}
.nav-brand{font-size:20px;font-weight:700;color:var(--blue)}
.nav-links{display:flex;gap:5px;flex-wrap:wrap}
.nav-link{padding:8px 12px;border-radius:6px;text-decoration:none;color:var(--muted);font-size:13px;transition:all 0.2s}
.nav-link:hover,.nav-link.active{background:var(--blue);color:white}
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.card-title{font-size:16px;font-weight:600;margin-bottom:15px;display:flex;align-items:center;gap:8px}
.btn{padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:14px;transition:all 0.2s;display:inline-flex;align-items:center;gap:8px;background:var(--blue);color:white}
.btn:hover{opacity:0.9;transform:translateY(-1px)}
.btn-green{background:var(--green)}
.btn-red{background:var(--red)}
.btn-purple{background:var(--purple)}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-sm{padding:6px 12px;font-size:12px}
.input{width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px}
.input:focus{outline:none;border-color:var(--blue)}
.form-group{margin-bottom:15px}
.form-label{display:block;margin-bottom:5px;font-size:13px;color:var(--muted)}
.table{width:100%;border-collapse:collapse}
.table th,.table td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}
.table th{color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase}
.table tr:hover{background:rgba(59,130,246,0.05)}
.grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center}
.stat-value{font-size:28px;font-weight:700;color:var(--blue)}
.stat-label{color:var(--muted);font-size:13px;margin-top:5px}
.pos-grid{display:grid;grid-template-columns:1fr 350px;gap:20px}
@media(max-width:900px){.pos-grid{grid-template-columns:1fr}}
.stock-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;max-height:60vh;overflow-y:auto;padding:5px}
.stock-item{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px;cursor:pointer;transition:all 0.2s}
.stock-item:hover{border-color:var(--blue);transform:translateY(-2px)}
.stock-item-name{font-weight:600;font-size:12px;margin-bottom:5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.stock-item-price{color:var(--green);font-weight:600;font-size:14px}
.stock-item-qty{color:var(--muted);font-size:11px}
.cart{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.cart-items{min-height:200px;max-height:40vh;overflow-y:auto}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:10px;border-bottom:1px solid var(--border)}
.cart-total{font-size:24px;font-weight:700;color:var(--green);text-align:right;padding:15px 0}
.search-box{position:relative;margin-bottom:15px}
.search-box input{padding-left:40px}
.search-icon{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--muted)}
.cat-btn{padding:8px 16px;border-radius:20px;border:1px solid var(--border);background:transparent;color:var(--text);cursor:pointer;font-size:12px;margin:3px;transition:all 0.2s}
.cat-btn:hover,.cat-btn.active{background:var(--blue);border-color:var(--blue);color:white}
.cat-grid{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:15px}
.alert{padding:15px;border-radius:8px;margin-bottom:15px}
.alert-info{background:rgba(59,130,246,0.1);border:1px solid var(--blue);color:var(--blue)}
.alert-success{background:rgba(16,185,129,0.1);border:1px solid var(--green);color:var(--green)}
.alert-error{background:rgba(239,68,68,0.1);border:1px solid var(--red);color:var(--red)}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:1000;align-items:center;justify-content:center}
.modal.show{display:flex}
.modal-content{background:var(--card);border-radius:12px;padding:25px;max-width:500px;width:90%;max-height:90vh;overflow-y:auto}
.modal-title{font-size:18px;font-weight:600;margin-bottom:20px}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════

def header(bid, active=""):
    links = [
        ("home", "🏠 Home", f"/{bid}"),
        ("pos", "💰 POS", f"/{bid}/pos"),
        ("stock", "📦 Stock", f"/{bid}/stock"),
        ("customers", "👥 Customers", f"/{bid}/customers"),
        ("suppliers", "🚚 Suppliers", f"/{bid}/suppliers"),
        ("invoices", "📄 Invoices", f"/{bid}/invoices"),
        ("quotes", "📝 Quotes", f"/{bid}/quotes"),
        ("expenses", "💸 Expenses", f"/{bid}/expenses"),
        ("reports", "📊 Reports", f"/{bid}/reports"),
    ]
    nav = "".join([f'<a href="{url}" class="nav-link {"active" if k==active else ""}">{label}</a>' for k,label,url in links])
    return f'<nav class="nav"><div class="nav-brand">📱 Click AI</div><div class="nav-links">{nav}</div></nav>'

# ═══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Click AI</title>""" + CSS + """</head><body>
<div class="container" style="text-align:center;padding-top:100px">
<h1 style="font-size:48px;margin-bottom:20px">📱 Click AI</h1>
<p style="color:var(--muted);margin-bottom:40px">Business Management System</p>
<a href="/demo" class="btn" style="font-size:18px;padding:15px 40px">🚀 Enter Demo</a>
</div></body></html>"""

@app.route("/demo")
def demo_redirect():
    return redirect("/5742fb2c-5fd8-4d44-9ddb-b73a3dd51da3")

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>")
def dashboard(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    stock = db.select("stock", {"business_id": bid}, limit=10000)
    customers = db.select("customers", {"business_id": bid})
    suppliers = db.select("suppliers", {"business_id": bid})
    invoices = db.select("invoices", {"business_id": bid})
    
    stock_count = len(stock)
    stock_value = sum(float(s.get("cost", 0) or 0) * int(s.get("qty", 0) or 0) for s in stock)
    cust_count = len(customers)
    inv_total = sum(float(i.get("total", 0) or 0) for i in invoices)
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dashboard</title>{CSS}</head><body>
{header(bid, "home")}
<div class="container">
<h1 style="margin-bottom:30px">📊 Dashboard</h1>
<div class="grid-2">
<div class="stat-card"><div class="stat-value">{stock_count}</div><div class="stat-label">Stock Items</div></div>
<div class="stat-card"><div class="stat-value">R {stock_value:,.0f}</div><div class="stat-label">Stock Value</div></div>
<div class="stat-card"><div class="stat-value">{cust_count}</div><div class="stat-label">Customers</div></div>
<div class="stat-card"><div class="stat-value">R {inv_total:,.0f}</div><div class="stat-label">Invoice Total</div></div>
</div>
<div class="card" style="margin-top:30px">
<div class="card-title">⚡ Quick Actions</div>
<div style="display:flex;gap:10px;flex-wrap:wrap">
<a href="/{bid}/pos" class="btn">💰 New Sale</a>
<a href="/{bid}/invoices/new" class="btn btn-green">📄 New Invoice</a>
<a href="/{bid}/quotes/new" class="btn btn-purple">📝 New Quote</a>
<a href="/{bid}/stock" class="btn btn-outline">📦 Manage Stock</a>
</div>
</div>
</div></body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# POS - Point of Sale (ALL DATA VIA API)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/pos")
def pos_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS</title>{CSS}</head><body>
{header(bid, "pos")}
<div class="container">
<div id="status" class="alert alert-info">Loading...</div>
<div class="pos-grid">
<div class="card">
<div class="cat-grid" id="cats"><button class="cat-btn active" onclick="filterCat('All')">All</button></div>
<div class="search-box"><span class="search-icon">🔍</span><input type="text" class="input" id="search" placeholder="Search..." oninput="render()"></div>
<div class="stock-grid" id="grid"></div>
</div>
<div class="cart">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px">
<div class="card-title" style="margin:0">🛒 Cart</div>
<button class="btn btn-sm btn-outline" onclick="clearCart()">Clear</button>
</div>
<select class="input" id="cust" style="margin-bottom:15px"><option value="">Walk-in Customer</option></select>
<div class="cart-items" id="cartItems"><div style="text-align:center;color:var(--muted);padding:40px">Empty cart</div></div>
<div class="cart-total">R <span id="total">0.00</span></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
<button class="btn btn-green" onclick="pay('cash')">💵 Cash</button>
<button class="btn btn-blue" onclick="pay('card')">💳 Card</button>
</div>
<button class="btn btn-purple" style="width:100%;margin-top:10px" onclick="pay('account')">📋 On Account</button>
</div>
</div>
</div>
<script>
var stock=[],cart=[],cat='All',bid='{bid}';

function load(){{
    Promise.all([
        fetch('/api/'+bid+'/stock').then(r=>r.json()),
        fetch('/api/'+bid+'/customers').then(r=>r.json())
    ]).then(function(d){{
        stock=d[0]||[];
        var custs=d[1]||[];
        
        // Categories
        var cats={{}};
        stock.forEach(s=>cats[s.cat]=1);
        var h='<button class="cat-btn active" onclick="filterCat(\'All\')">All</button>';
        Object.keys(cats).sort().forEach(c=>{{
            h+='<button class="cat-btn" onclick="filterCat(this.textContent)">'+c+'</button>';
        }});
        document.getElementById('cats').innerHTML=h;
        
        // Customers
        var ch='<option value="">Walk-in Customer</option>';
        custs.forEach(c=>{{ch+='<option value="'+c.id+'">'+c.name+'</option>'}});
        document.getElementById('cust').innerHTML=ch;
        
        document.getElementById('status').innerHTML='✅ Loaded '+stock.length+' items';
        document.getElementById('status').className='alert alert-success';
        render();
    }}).catch(function(e){{
        document.getElementById('status').innerHTML='❌ Error: '+e;
        document.getElementById('status').className='alert alert-error';
    }});
}}

function render(){{
    var s=document.getElementById('search').value.toLowerCase();
    var h='';
    stock.forEach(function(item){{
        if(cat!='All'&&item.cat!=cat)return;
        if(s&&item.desc.toLowerCase().indexOf(s)<0&&item.code.toLowerCase().indexOf(s)<0)return;
        if(item.qty<=0)return;
        h+='<div class="stock-item" onclick="add(\''+item.id+'\')">';
        h+='<div class="stock-item-name">'+item.desc+'</div>';
        h+='<div class="stock-item-price">R '+item.price.toFixed(2)+'</div>';
        h+='<div class="stock-item-qty">'+item.qty+' in stock</div>';
        h+='</div>';
    }});
    document.getElementById('grid').innerHTML=h||'<div style="padding:40px;text-align:center;color:var(--muted)">No items</div>';
}}

function filterCat(c){{
    cat=c;
    document.querySelectorAll('.cat-btn').forEach(b=>b.classList.remove('active'));
    event.target.classList.add('active');
    render();
}}

function add(id){{
    var item=stock.find(s=>s.id==id);
    if(!item)return;
    var exist=cart.find(c=>c.id==id);
    if(exist)exist.qty++;
    else cart.push({{id:item.id,desc:item.desc,price:item.price,qty:1}});
    renderCart();
}}

function renderCart(){{
    if(cart.length==0){{
        document.getElementById('cartItems').innerHTML='<div style="text-align:center;color:var(--muted);padding:40px">Empty cart</div>';
        document.getElementById('total').textContent='0.00';
        return;
    }}
    var h='',tot=0;
    cart.forEach(function(c,i){{
        var sub=c.price*c.qty;
        tot+=sub;
        h+='<div class="cart-item">';
        h+='<div><div style="font-weight:600">'+c.desc+'</div><div style="color:var(--muted);font-size:12px">R '+c.price.toFixed(2)+' x '+c.qty+'</div></div>';
        h+='<div style="display:flex;align-items:center;gap:10px">';
        h+='<span style="font-weight:600">R '+sub.toFixed(2)+'</span>';
        h+='<button class="btn btn-sm btn-red" onclick="remove('+i+')">×</button>';
        h+='</div></div>';
    }});
    document.getElementById('cartItems').innerHTML=h;
    document.getElementById('total').textContent=tot.toFixed(2);
}}

function remove(i){{cart.splice(i,1);renderCart()}}
function clearCart(){{cart=[];renderCart()}}

function pay(method){{
    if(cart.length==0)return alert('Cart is empty');
    var total=cart.reduce((a,c)=>a+c.price*c.qty,0);
    var cust=document.getElementById('cust').value;
    fetch('/api/'+bid+'/sale',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{items:cart,total:total,method:method,customer_id:cust}})
    }}).then(r=>r.json()).then(d=>{{
        if(d.success){{
            alert('Sale complete! Total: R '+total.toFixed(2));
            cart=[];
            renderCart();
            load();
        }}else{{
            alert('Error: '+(d.error||'Unknown'));
        }}
    }});
}}

load();
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# STOCK PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/stock")
def stock_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stock</title>{CSS}</head><body>
{header(bid, "stock")}
<div class="container">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px">
<h1>📦 Stock Management</h1>
<button class="btn" onclick="showAdd()">+ Add Item</button>
</div>
<div id="status" class="alert alert-info">Loading...</div>
<div class="card">
<div class="search-box"><span class="search-icon">🔍</span><input type="text" class="input" id="search" placeholder="Search stock..." oninput="render()"></div>
<div style="overflow-x:auto"><table class="table" id="table"><thead><tr><th>Code</th><th>Description</th><th>Category</th><th>Qty</th><th>Cost</th><th>Price</th><th>Actions</th></tr></thead><tbody></tbody></table></div>
</div>
</div>

<div class="modal" id="modal">
<div class="modal-content">
<div class="modal-title" id="modalTitle">Add Stock Item</div>
<input type="hidden" id="editId">
<div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="code"></div>
<div class="form-group"><label class="form-label">Description</label><input type="text" class="input" id="desc"></div>
<div class="form-group"><label class="form-label">Category</label><input type="text" class="input" id="cat" value="General"></div>
<div class="form-group"><label class="form-label">Quantity</label><input type="number" class="input" id="qty" value="0"></div>
<div class="form-group"><label class="form-label">Cost Price</label><input type="number" class="input" id="cost" step="0.01" value="0"></div>
<div class="form-group"><label class="form-label">Sell Price</label><input type="number" class="input" id="price" step="0.01" value="0"></div>
<div style="display:flex;gap:10px">
<button class="btn" onclick="save()">Save</button>
<button class="btn btn-outline" onclick="hideModal()">Cancel</button>
</div>
</div>
</div>

<script>
var stock=[],bid='{bid}';

function load(){{
    fetch('/api/'+bid+'/stock').then(r=>r.json()).then(d=>{{
        stock=d||[];
        document.getElementById('status').innerHTML='✅ '+stock.length+' items loaded';
        document.getElementById('status').className='alert alert-success';
        render();
    }});
}}

function render(){{
    var s=document.getElementById('search').value.toLowerCase();
    var h='';
    stock.forEach(function(item){{
        if(s&&item.desc.toLowerCase().indexOf(s)<0&&item.code.toLowerCase().indexOf(s)<0)return;
        h+='<tr>';
        h+='<td>'+item.code+'</td>';
        h+='<td>'+item.desc+'</td>';
        h+='<td>'+item.cat+'</td>';
        h+='<td>'+item.qty+'</td>';
        h+='<td>R '+item.cost.toFixed(2)+'</td>';
        h+='<td>R '+item.price.toFixed(2)+'</td>';
        h+='<td><button class="btn btn-sm btn-outline" onclick="edit(\''+item.id+'\')">Edit</button></td>';
        h+='</tr>';
    }});
    document.querySelector('#table tbody').innerHTML=h||'<tr><td colspan="7" style="text-align:center;padding:40px;color:var(--muted)">No stock items</td></tr>';
}}

function showAdd(){{
    document.getElementById('modalTitle').textContent='Add Stock Item';
    document.getElementById('editId').value='';
    document.getElementById('code').value='';
    document.getElementById('desc').value='';
    document.getElementById('cat').value='General';
    document.getElementById('qty').value='0';
    document.getElementById('cost').value='0';
    document.getElementById('price').value='0';
    document.getElementById('modal').classList.add('show');
}}

function edit(id){{
    var item=stock.find(s=>s.id==id);
    if(!item)return;
    document.getElementById('modalTitle').textContent='Edit Stock Item';
    document.getElementById('editId').value=id;
    document.getElementById('code').value=item.code;
    document.getElementById('desc').value=item.desc;
    document.getElementById('cat').value=item.cat;
    document.getElementById('qty').value=item.qty;
    document.getElementById('cost').value=item.cost;
    document.getElementById('price').value=item.price;
    document.getElementById('modal').classList.add('show');
}}

function hideModal(){{document.getElementById('modal').classList.remove('show')}}

function save(){{
    var data={{
        id:document.getElementById('editId').value||null,
        code:document.getElementById('code').value,
        description:document.getElementById('desc').value,
        category:document.getElementById('cat').value,
        qty:parseInt(document.getElementById('qty').value)||0,
        cost:parseFloat(document.getElementById('cost').value)||0,
        price:parseFloat(document.getElementById('price').value)||0
    }};
    fetch('/api/'+bid+'/stock',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify(data)
    }}).then(r=>r.json()).then(d=>{{
        if(d.success){{hideModal();load();}}
        else alert('Error: '+(d.error||'Unknown'));
    }});
}}

load();
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/customers")
def customers_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customers</title>{CSS}</head><body>
{header(bid, "customers")}
<div class="container">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
<h1>👥 Customers</h1>
<button class="btn" onclick="showAdd()">+ Add Customer</button>
</div>
<div id="status" class="alert alert-info">Loading...</div>
<div class="card">
<div class="search-box"><span class="search-icon">🔍</span><input type="text" class="input" id="search" placeholder="Search..." oninput="render()"></div>
<table class="table" id="table"><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th>Actions</th></tr></thead><tbody></tbody></table>
</div>
</div>

<div class="modal" id="modal">
<div class="modal-content">
<div class="modal-title" id="modalTitle">Add Customer</div>
<input type="hidden" id="editId">
<div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="code"></div>
<div class="form-group"><label class="form-label">Name</label><input type="text" class="input" id="name"></div>
<div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="phone"></div>
<div class="form-group"><label class="form-label">Email</label><input type="email" class="input" id="email"></div>
<div style="display:flex;gap:10px">
<button class="btn" onclick="save()">Save</button>
<button class="btn btn-outline" onclick="hideModal()">Cancel</button>
</div>
</div>
</div>

<script>
var items=[],bid='{bid}';

function load(){{
    fetch('/api/'+bid+'/customers').then(r=>r.json()).then(d=>{{
        items=d||[];
        document.getElementById('status').innerHTML='✅ '+items.length+' customers';
        document.getElementById('status').className='alert alert-success';
        render();
    }});
}}

function render(){{
    var s=document.getElementById('search').value.toLowerCase();
    var h='';
    items.forEach(function(c){{
        if(s&&c.name.toLowerCase().indexOf(s)<0&&c.code.toLowerCase().indexOf(s)<0)return;
        h+='<tr><td>'+c.code+'</td><td>'+c.name+'</td><td>'+(c.phone||'-')+'</td><td>'+(c.email||'-')+'</td><td>R '+(c.balance||0).toFixed(2)+'</td>';
        h+='<td><button class="btn btn-sm btn-outline" onclick="edit(\''+c.id+'\')">Edit</button></td></tr>';
    }});
    document.querySelector('#table tbody').innerHTML=h||'<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--muted)">No customers</td></tr>';
}}

function showAdd(){{
    document.getElementById('modalTitle').textContent='Add Customer';
    document.getElementById('editId').value='';
    document.getElementById('code').value='';
    document.getElementById('name').value='';
    document.getElementById('phone').value='';
    document.getElementById('email').value='';
    document.getElementById('modal').classList.add('show');
}}

function edit(id){{
    var c=items.find(x=>x.id==id);
    if(!c)return;
    document.getElementById('modalTitle').textContent='Edit Customer';
    document.getElementById('editId').value=id;
    document.getElementById('code').value=c.code;
    document.getElementById('name').value=c.name;
    document.getElementById('phone').value=c.phone||'';
    document.getElementById('email').value=c.email||'';
    document.getElementById('modal').classList.add('show');
}}

function hideModal(){{document.getElementById('modal').classList.remove('show')}}

function save(){{
    var data={{
        id:document.getElementById('editId').value||null,
        code:document.getElementById('code').value,
        name:document.getElementById('name').value,
        phone:document.getElementById('phone').value,
        email:document.getElementById('email').value
    }};
    fetch('/api/'+bid+'/customers',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify(data)
    }}).then(r=>r.json()).then(d=>{{
        if(d.success){{hideModal();load();}}
        else alert('Error');
    }});
}}

load();
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suppliers</title>{CSS}</head><body>
{header(bid, "suppliers")}
<div class="container">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
<h1>🚚 Suppliers</h1>
<button class="btn" onclick="showAdd()">+ Add Supplier</button>
</div>
<div id="status" class="alert alert-info">Loading...</div>
<div class="card">
<table class="table" id="table"><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th>Actions</th></tr></thead><tbody></tbody></table>
</div>
</div>

<div class="modal" id="modal">
<div class="modal-content">
<div class="modal-title" id="modalTitle">Add Supplier</div>
<input type="hidden" id="editId">
<div class="form-group"><label class="form-label">Code</label><input type="text" class="input" id="code"></div>
<div class="form-group"><label class="form-label">Name</label><input type="text" class="input" id="name"></div>
<div class="form-group"><label class="form-label">Phone</label><input type="text" class="input" id="phone"></div>
<div class="form-group"><label class="form-label">Email</label><input type="email" class="input" id="email"></div>
<div style="display:flex;gap:10px">
<button class="btn" onclick="save()">Save</button>
<button class="btn btn-outline" onclick="hideModal()">Cancel</button>
</div>
</div>
</div>

<script>
var items=[],bid='{bid}';

function load(){{
    fetch('/api/'+bid+'/suppliers').then(r=>r.json()).then(d=>{{
        items=d||[];
        document.getElementById('status').innerHTML='✅ '+items.length+' suppliers';
        document.getElementById('status').className='alert alert-success';
        render();
    }});
}}

function render(){{
    var h='';
    items.forEach(function(c){{
        h+='<tr><td>'+c.code+'</td><td>'+c.name+'</td><td>'+(c.phone||'-')+'</td><td>'+(c.email||'-')+'</td><td>R '+(c.balance||0).toFixed(2)+'</td>';
        h+='<td><button class="btn btn-sm btn-outline" onclick="edit(\''+c.id+'\')">Edit</button></td></tr>';
    }});
    document.querySelector('#table tbody').innerHTML=h||'<tr><td colspan="6" style="text-align:center;padding:40px;color:var(--muted)">No suppliers</td></tr>';
}}

function showAdd(){{
    document.getElementById('modalTitle').textContent='Add Supplier';
    document.getElementById('editId').value='';
    document.getElementById('code').value='';
    document.getElementById('name').value='';
    document.getElementById('phone').value='';
    document.getElementById('email').value='';
    document.getElementById('modal').classList.add('show');
}}

function edit(id){{
    var c=items.find(x=>x.id==id);
    if(!c)return;
    document.getElementById('modalTitle').textContent='Edit Supplier';
    document.getElementById('editId').value=id;
    document.getElementById('code').value=c.code;
    document.getElementById('name').value=c.name;
    document.getElementById('phone').value=c.phone||'';
    document.getElementById('email').value=c.email||'';
    document.getElementById('modal').classList.add('show');
}}

function hideModal(){{document.getElementById('modal').classList.remove('show')}}

function save(){{
    var data={{
        id:document.getElementById('editId').value||null,
        code:document.getElementById('code').value,
        name:document.getElementById('name').value,
        phone:document.getElementById('phone').value,
        email:document.getElementById('email').value
    }};
    fetch('/api/'+bid+'/suppliers',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify(data)
    }}).then(r=>r.json()).then(d=>{{
        if(d.success){{hideModal();load();}}
        else alert('Error');
    }});
}}

load();
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# INVOICES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/invoices")
def invoices_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Invoices</title>{CSS}</head><body>
{header(bid, "invoices")}
<div class="container">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
<h1>📄 Invoices</h1>
<a href="/{bid}/invoices/new" class="btn">+ New Invoice</a>
</div>
<div id="status" class="alert alert-info">Loading...</div>
<div class="card">
<table class="table" id="table"><thead><tr><th>Invoice #</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody></tbody></table>
</div>
</div>
<script>
var bid='{bid}';
fetch('/api/'+bid+'/invoices').then(r=>r.json()).then(d=>{{
    var items=d||[];
    document.getElementById('status').innerHTML='✅ '+items.length+' invoices';
    document.getElementById('status').className='alert alert-success';
    var h='';
    items.forEach(function(i){{
        h+='<tr><td>'+i.number+'</td><td>'+i.date+'</td><td>'+i.customer_name+'</td><td>R '+i.total.toFixed(2)+'</td><td>'+(i.status||'draft')+'</td></tr>';
    }});
    document.querySelector('#table tbody').innerHTML=h||'<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--muted)">No invoices</td></tr>';
}});
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/quotes")
def quotes_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quotes</title>{CSS}</head><body>
{header(bid, "quotes")}
<div class="container">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
<h1>📝 Quotes</h1>
<a href="/{bid}/quotes/new" class="btn">+ New Quote</a>
</div>
<div id="status" class="alert alert-info">Loading...</div>
<div class="card">
<table class="table" id="table"><thead><tr><th>Quote #</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody></tbody></table>
</div>
</div>
<script>
var bid='{bid}';
fetch('/api/'+bid+'/quotes').then(r=>r.json()).then(d=>{{
    var items=d||[];
    document.getElementById('status').innerHTML='✅ '+items.length+' quotes';
    document.getElementById('status').className='alert alert-success';
    var h='';
    items.forEach(function(i){{
        h+='<tr><td>'+i.number+'</td><td>'+i.date+'</td><td>'+i.customer_name+'</td><td>R '+i.total.toFixed(2)+'</td><td>'+(i.status||'draft')+'</td></tr>';
    }});
    document.querySelector('#table tbody').innerHTML=h||'<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--muted)">No quotes</td></tr>';
}});
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSES PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/expenses")
def expenses_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Expenses</title>{CSS}</head><body>
{header(bid, "expenses")}
<div class="container">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
<h1>💸 Expenses</h1>
<button class="btn" onclick="showAdd()">+ Add Expense</button>
</div>
<div id="status" class="alert alert-info">Loading...</div>
<div class="card">
<table class="table" id="table"><thead><tr><th>Date</th><th>Supplier</th><th>Description</th><th>Amount</th><th>VAT</th></tr></thead><tbody></tbody></table>
</div>
</div>

<div class="modal" id="modal">
<div class="modal-content">
<div class="modal-title">Add Expense</div>
<div class="form-group"><label class="form-label">Supplier</label><input type="text" class="input" id="supplier"></div>
<div class="form-group"><label class="form-label">Description</label><input type="text" class="input" id="desc"></div>
<div class="form-group"><label class="form-label">Amount (incl VAT)</label><input type="number" class="input" id="amount" step="0.01"></div>
<div class="form-group"><label class="form-label"><input type="checkbox" id="hasVat" checked> Includes VAT</label></div>
<div style="display:flex;gap:10px">
<button class="btn" onclick="save()">Save</button>
<button class="btn btn-outline" onclick="hideModal()">Cancel</button>
</div>
</div>
</div>

<script>
var items=[],bid='{bid}';

function load(){{
    fetch('/api/'+bid+'/expenses').then(r=>r.json()).then(d=>{{
        items=d||[];
        document.getElementById('status').innerHTML='✅ '+items.length+' expenses';
        document.getElementById('status').className='alert alert-success';
        render();
    }});
}}

function render(){{
    var h='';
    items.forEach(function(e){{
        h+='<tr><td>'+e.date+'</td><td>'+e.supplier+'</td><td>'+e.description+'</td><td>R '+e.amount.toFixed(2)+'</td><td>R '+e.vat.toFixed(2)+'</td></tr>';
    }});
    document.querySelector('#table tbody').innerHTML=h||'<tr><td colspan="5" style="text-align:center;padding:40px;color:var(--muted)">No expenses</td></tr>';
}}

function showAdd(){{document.getElementById('modal').classList.add('show')}}
function hideModal(){{document.getElementById('modal').classList.remove('show')}}

function save(){{
    var amt=parseFloat(document.getElementById('amount').value)||0;
    var hasVat=document.getElementById('hasVat').checked;
    var vat=hasVat?amt*15/115:0;
    var data={{
        supplier:document.getElementById('supplier').value,
        description:document.getElementById('desc').value,
        amount:amt,
        vat:vat
    }};
    fetch('/api/'+bid+'/expenses',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify(data)
    }}).then(r=>r.json()).then(d=>{{
        if(d.success){{hideModal();load();}}
    }});
}}

load();
</script>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/reports")
def reports_page(bid):
    biz = db.select("businesses", {"id": bid})
    if not biz:
        return redirect("/")
    
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reports</title>{CSS}</head><body>
{header(bid, "reports")}
<div class="container">
<h1 style="margin-bottom:30px">📊 Reports</h1>
<div class="grid-2">
<div class="card" style="cursor:pointer" onclick="location.href='/{bid}/reports/sales'">
<div class="card-title">💰 Sales Report</div>
<p style="color:var(--muted)">Daily, weekly, monthly sales summary</p>
</div>
<div class="card" style="cursor:pointer" onclick="location.href='/{bid}/reports/stock'">
<div class="card-title">📦 Stock Report</div>
<p style="color:var(--muted)">Stock levels, value, low stock alerts</p>
</div>
<div class="card" style="cursor:pointer" onclick="location.href='/{bid}/reports/profit'">
<div class="card-title">📈 Profit & Loss</div>
<p style="color:var(--muted)">Income vs expenses</p>
</div>
<div class="card" style="cursor:pointer" onclick="location.href='/{bid}/reports/vat'">
<div class="card-title">🧾 VAT Report</div>
<p style="color:var(--muted)">VAT collected vs paid</p>
</div>
</div>
</div>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/<bid>/stock", methods=["GET"])
def api_get_stock(bid):
    stock = db.select("stock", {"business_id": bid}, limit=10000)
    result = []
    for s in stock:
        result.append({
            "id": s.get("id", ""),
            "code": js_safe(s.get("code", "")),
            "desc": js_safe(s.get("description", "")),
            "cat": js_safe(s.get("category", "")) or "General",
            "qty": int(s.get("qty", 0) or 0),
            "cost": float(s.get("cost", 0) or 0),
            "price": float(s.get("price", 0) or 0)
        })
    return jsonify(result)

@app.route("/api/<bid>/stock", methods=["POST"])
def api_save_stock(bid):
    d = request.get_json()
    item = {
        "business_id": bid,
        "code": d.get("code", ""),
        "description": d.get("description", ""),
        "category": d.get("category", "General"),
        "qty": d.get("qty", 0),
        "cost": d.get("cost", 0),
        "price": d.get("price", 0)
    }
    if d.get("id"):
        db.update("stock", d["id"], item)
    else:
        item["id"] = str(uuid.uuid4())
        db.insert("stock", item)
    return jsonify({"success": True})

@app.route("/api/<bid>/customers", methods=["GET"])
def api_get_customers(bid):
    customers = db.select("customers", {"business_id": bid})
    result = []
    for c in customers:
        result.append({
            "id": c.get("id", ""),
            "code": js_safe(c.get("code", "")),
            "name": js_safe(c.get("name", "")),
            "phone": js_safe(c.get("phone", "")),
            "email": js_safe(c.get("email", "")),
            "balance": float(c.get("balance", 0) or 0)
        })
    return jsonify(result)

@app.route("/api/<bid>/customers", methods=["POST"])
def api_save_customer(bid):
    d = request.get_json()
    item = {
        "business_id": bid,
        "code": d.get("code", ""),
        "name": d.get("name", ""),
        "phone": d.get("phone", ""),
        "email": d.get("email", ""),
        "balance": 0
    }
    if d.get("id"):
        db.update("customers", d["id"], item)
    else:
        item["id"] = str(uuid.uuid4())
        db.insert("customers", item)
    return jsonify({"success": True})

@app.route("/api/<bid>/suppliers", methods=["GET"])
def api_get_suppliers(bid):
    suppliers = db.select("suppliers", {"business_id": bid})
    result = []
    for s in suppliers:
        result.append({
            "id": s.get("id", ""),
            "code": js_safe(s.get("code", "")),
            "name": js_safe(s.get("name", "")),
            "phone": js_safe(s.get("phone", "")),
            "email": js_safe(s.get("email", "")),
            "balance": float(s.get("balance", 0) or 0)
        })
    return jsonify(result)

@app.route("/api/<bid>/suppliers", methods=["POST"])
def api_save_supplier(bid):
    d = request.get_json()
    item = {
        "business_id": bid,
        "code": d.get("code", ""),
        "name": d.get("name", ""),
        "phone": d.get("phone", ""),
        "email": d.get("email", ""),
        "balance": 0
    }
    if d.get("id"):
        db.update("suppliers", d["id"], item)
    else:
        item["id"] = str(uuid.uuid4())
        db.insert("suppliers", item)
    return jsonify({"success": True})

@app.route("/api/<bid>/invoices", methods=["GET"])
def api_get_invoices(bid):
    invoices = db.select("invoices", {"business_id": bid})
    result = []
    for i in invoices:
        result.append({
            "id": i.get("id", ""),
            "number": js_safe(i.get("number", "")),
            "date": i.get("date", "")[:10] if i.get("date") else "",
            "customer_name": js_safe(i.get("customer_name", "")),
            "total": float(i.get("total", 0) or 0),
            "status": i.get("status", "draft")
        })
    return jsonify(result)

@app.route("/api/<bid>/quotes", methods=["GET"])
def api_get_quotes(bid):
    quotes = db.select("quotes", {"business_id": bid})
    result = []
    for q in quotes:
        result.append({
            "id": q.get("id", ""),
            "number": js_safe(q.get("number", "")),
            "date": q.get("date", "")[:10] if q.get("date") else "",
            "customer_name": js_safe(q.get("customer_name", "")),
            "total": float(q.get("total", 0) or 0),
            "status": q.get("status", "draft")
        })
    return jsonify(result)

@app.route("/api/<bid>/expenses", methods=["GET"])
def api_get_expenses(bid):
    expenses = db.select("expenses", {"business_id": bid})
    result = []
    for e in expenses:
        result.append({
            "id": e.get("id", ""),
            "date": e.get("created_at", "")[:10] if e.get("created_at") else "",
            "supplier": js_safe(e.get("supplier", "")),
            "description": js_safe(e.get("description", "")),
            "amount": float(e.get("amount", 0) or 0),
            "vat": float(e.get("vat", 0) or 0)
        })
    return jsonify(result)

@app.route("/api/<bid>/expenses", methods=["POST"])
def api_save_expense(bid):
    d = request.get_json()
    item = {
        "id": str(uuid.uuid4()),
        "business_id": bid,
        "supplier": d.get("supplier", ""),
        "description": d.get("description", ""),
        "amount": d.get("amount", 0),
        "vat": d.get("vat", 0)
    }
    db.insert("expenses", item)
    return jsonify({"success": True})

@app.route("/api/<bid>/sale", methods=["POST"])
def api_sale(bid):
    d = request.get_json()
    items = d.get("items", [])
    total = d.get("total", 0)
    method = d.get("method", "cash")
    
    # Create invoice
    inv_count = len(db.select("invoices", {"business_id": bid}))
    inv = {
        "id": str(uuid.uuid4()),
        "business_id": bid,
        "number": f"INV{inv_count+1:04d}",
        "customer_id": d.get("customer_id", ""),
        "customer_name": "Walk-in",
        "items": json.dumps(items),
        "total": total,
        "status": "paid",
        "payment_method": method,
        "date": datetime.now().isoformat()
    }
    
    # Get customer name if provided
    if d.get("customer_id"):
        custs = db.select("customers", {"id": d["customer_id"]})
        if custs:
            inv["customer_name"] = custs[0].get("name", "Unknown")
    
    db.insert("invoices", inv)
    
    # Update stock quantities
    for item in items:
        stock_list = db.select("stock", {"id": item["id"]})
        if stock_list:
            s = stock_list[0]
            new_qty = int(s.get("qty", 0)) - int(item.get("qty", 1))
            db.update("stock", item["id"], {"qty": max(0, new_qty)})
    
    return jsonify({"success": True})

# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})

# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 Click AI v6 Starting...")
    print(f"  📦 Supabase: {SUPABASE_URL}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
