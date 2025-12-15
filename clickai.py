"""
Click AI v9 - Complete Edition
All features, no emojis in JS, bulletproof
"""

from flask import Flask, jsonify, request, redirect
import json
import os
from datetime import datetime
import re
import uuid
import requests

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://gvmonstssdxncfkcjukr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_0msyFLKCiT4EXM-TGZIr6w_mpv5nNWD")

def js_safe(s):
    if s is None: return ""
    s = str(s)
    s = re.sub(r'["\'\\\n\r\t]', ' ', s)
    s = re.sub(r'[^\x20-\x7E]', '', s)
    return s.strip()

class DB:
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}
    
    def select(self, table, filters=None, limit=10000):
        url = f"{self.url}/rest/v1/{table}?select=*&limit={limit}"
        if filters:
            for k, v in filters.items():
                url += f"&{k}=eq.{v}"
        try:
            r = requests.get(url, headers=self.headers, timeout=60)
            return r.json() if r.status_code == 200 else []
        except:
            return []
    
    def insert(self, table, data):
        try:
            r = requests.post(f"{self.url}/rest/v1/{table}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 201]
        except:
            return False
    
    def update(self, table, id, data):
        try:
            r = requests.patch(f"{self.url}/rest/v1/{table}?id=eq.{id}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 204]
        except:
            return False

db = DB(SUPABASE_URL, SUPABASE_KEY)

CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh}
.nav{background:#12121a;border-bottom:1px solid #1e1e2e;padding:10px 20px;display:flex;align-items:center;gap:15px;flex-wrap:wrap}
.nav a{padding:8px 12px;border-radius:6px;text-decoration:none;color:#888;font-size:13px}
.nav a:hover,.nav a.on{background:#3b82f6;color:white}
.box{max-width:1400px;margin:0 auto;padding:20px}
.card{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:20px;margin-bottom:20px}
.btn{padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:14px;background:#3b82f6;color:white;text-decoration:none;display:inline-block}
.btn:hover{opacity:0.9}
.btn-green{background:#10b981}
.btn-red{background:#ef4444}
.btn-purple{background:#8b5cf6}
.btn-orange{background:#f59e0b}
.btn-sm{padding:6px 12px;font-size:12px}
input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid #1e1e2e;background:#0a0a0f;color:#e0e0e0;font-size:14px;margin-bottom:10px}
table{width:100%;border-collapse:collapse}
th,td{padding:12px;text-align:left;border-bottom:1px solid #1e1e2e}
th{color:#888;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;max-height:60vh;overflow-y:auto}
.item{background:#0a0a0f;border:1px solid #1e1e2e;border-radius:8px;padding:12px;cursor:pointer}
.item:hover{border-color:#3b82f6}
.msg{padding:15px;border-radius:8px;margin-bottom:15px;background:#1e3a5f;color:#60a5fa}
.msg-ok{background:#064e3b;color:#34d399}
.msg-err{background:#7f1d1d;color:#fca5a5}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center;z-index:1000}
.modal.show{display:flex}
.modal-box{background:#12121a;border-radius:12px;padding:25px;width:90%;max-width:500px;max-height:90vh;overflow-y:auto}
.stat{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:20px;text-align:center}
.stat-num{font-size:28px;font-weight:700;color:#3b82f6}
.stat-label{color:#888;font-size:13px;margin-top:5px}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:15px}
.cart{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:20px}
.total{font-size:24px;font-weight:700;color:#10b981;text-align:right;padding:15px 0}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:rgba(16,185,129,0.2);color:#10b981}
.badge-orange{background:rgba(245,158,11,0.2);color:#f59e0b}
.badge-red{background:rgba(239,68,68,0.2);color:#ef4444}
.report-card{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:25px;cursor:pointer;transition:all 0.2s;text-decoration:none;color:#e0e0e0;display:block}
.report-card:hover{border-color:#3b82f6;transform:translateY(-3px)}
</style>"""

def nav(bid, cur=""):
    items = [("Dashboard","/BID"),("POS","/BID/pos"),("Stock","/BID/stock"),("Customers","/BID/customers"),("Suppliers","/BID/suppliers"),("Invoices","/BID/invoices"),("Quotes","/BID/quotes"),("Expenses","/BID/expenses"),("Reports","/BID/reports"),("Import","/BID/import")]
    links = "".join([f'<a href="{u.replace("BID",bid)}" class="{"on" if n.lower()==cur else ""}">{n}</a>' for n,u in items])
    return f'<nav class="nav"><strong style="color:#3b82f6;font-size:18px">Click AI</strong>{links}</nav>'

# ============================================================================
# HOME & DASHBOARD
# ============================================================================

@app.route("/")
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}</head><body>
<div class="box" style="text-align:center;padding-top:100px">
<h1 style="font-size:48px;margin-bottom:20px">Click AI</h1>
<p style="color:#888;margin-bottom:40px">Complete Business Management System</p>
<a href="/demo" class="btn" style="font-size:18px;padding:15px 40px">Enter Demo</a>
</div></body></html>'''

@app.route("/demo")
def demo():
    return redirect("/5742fb2c-5fd8-4d44-9ddb-b73a3dd51da3")

@app.route("/<bid>")
def dashboard(bid):
    stock = db.select("stock", {"business_id": bid})
    customers = db.select("customers", {"business_id": bid})
    suppliers = db.select("suppliers", {"business_id": bid})
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    quotes = db.select("quotes", {"business_id": bid})
    
    stock_val = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    low_stock = len([s for s in stock if 0 < int(s.get("qty",0) or 0) <= 5])
    out_stock = len([s for s in stock if int(s.get("qty",0) or 0) <= 0])
    inv_total = sum(float(i.get("total",0) or 0) for i in invoices)
    exp_total = sum(float(e.get("amount",0) or 0) for e in expenses)
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dashboard</title>{CSS}</head><body>
{nav(bid,"dashboard")}
<div class="box">
<h1 style="margin-bottom:30px">Dashboard</h1>
<div class="row">
<div class="stat"><div class="stat-num">{len(stock)}</div><div class="stat-label">Stock Items</div></div>
<div class="stat"><div class="stat-num">R {stock_val:,.0f}</div><div class="stat-label">Stock Value</div></div>
<div class="stat"><div class="stat-num" style="color:#f59e0b">{low_stock}</div><div class="stat-label">Low Stock</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">{out_stock}</div><div class="stat-label">Out of Stock</div></div>
</div>
<div class="row">
<div class="stat"><div class="stat-num">{len(customers)}</div><div class="stat-label">Customers</div></div>
<div class="stat"><div class="stat-num">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div>
<div class="stat"><div class="stat-num" style="color:#10b981">R {inv_total:,.0f}</div><div class="stat-label">Sales</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {exp_total:,.0f}</div><div class="stat-label">Expenses</div></div>
</div>
<div class="card" style="margin-top:20px">
<h3 style="margin-bottom:15px">Quick Actions</h3>
<a href="/{bid}/pos" class="btn">New Sale</a>
<a href="/{bid}/invoices/new" class="btn btn-green" style="margin-left:10px">New Invoice</a>
<a href="/{bid}/quotes/new" class="btn btn-purple" style="margin-left:10px">New Quote</a>
<a href="/{bid}/stock" class="btn" style="margin-left:10px;background:#333">Manage Stock</a>
</div>
</div></body></html>'''

# ============================================================================
# POS
# ============================================================================

@app.route("/<bid>/pos")
def pos(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS</title>{CSS}</head><body>
{nav(bid,"pos")}
<div class="box">
<div id="msg" class="msg">Loading...</div>
<div style="display:grid;grid-template-columns:1fr 350px;gap:20px">
<div class="card">
<input type="text" id="q" placeholder="Search products... (showing first 100)" onkeyup="render()">
<div class="grid" id="items"></div>
</div>
<div class="cart">
<div style="display:flex;justify-content:space-between;margin-bottom:15px">
<h3>Cart</h3>
<button class="btn btn-sm" onclick="cart=[];renderCart()">Clear</button>
</div>
<select id="custSel"><option value="">Walk-in Customer</option></select>
<div id="cartList" style="min-height:200px;margin-top:10px"></div>
<div class="total">R <span id="tot">0.00</span></div>
<div class="row">
<button class="btn btn-green" onclick="pay('cash')">Cash</button>
<button class="btn" onclick="pay('card')">Card</button>
</div>
<button class="btn btn-purple" style="width:100%;margin-top:10px" onclick="pay('account')">On Account</button>
</div>
</div>
</div>
<script>
var stock=[],cart=[],customers=[],BID="{bid}";
function load(){{
document.getElementById("msg").innerHTML="Loading stock...";
fetch("/api/"+BID+"/stock").then(function(r){{return r.json()}}).then(function(d){{
stock=d||[];
document.getElementById("msg").innerHTML="Loading customers...";
fetch("/api/"+BID+"/customers").then(function(r){{return r.json()}}).then(function(c){{
customers=c||[];
var sel="<option value=''>Walk-in Customer</option>";
for(var i=0;i<customers.length;i++)sel+="<option value='"+customers[i].id+"'>"+customers[i].name+"</option>";
document.getElementById("custSel").innerHTML=sel;
document.getElementById("msg").innerHTML="Loaded "+stock.length+" items, "+customers.length+" customers";
document.getElementById("msg").className="msg msg-ok";
render();
}}).catch(function(e){{document.getElementById("msg").innerHTML="Error loading customers: "+e;document.getElementById("msg").className="msg msg-err";}});
}}).catch(function(e){{document.getElementById("msg").innerHTML="Error loading stock: "+e;document.getElementById("msg").className="msg msg-err";}});
}}
function render(){{
var q=document.getElementById("q").value.toLowerCase();
var h="";var count=0;
for(var i=0;i<stock.length;i++){{
var s=stock[i];
if(s.qty<=0)continue;
if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;
h+="<div class='item' onclick='add("+i+")'><div style='font-weight:600;font-size:12px'>"+s.desc+"</div><div style='color:#10b981'>R "+s.price.toFixed(2)+"</div><div style='color:#888;font-size:11px'>"+s.qty+" in stock</div></div>";
count++;
if(count>=100)break;
}}
document.getElementById("items").innerHTML=h||"<div style='padding:40px;text-align:center;color:#888'>No items found</div>";
}}
function add(i){{
var s=stock[i];
var found=false;
for(var j=0;j<cart.length;j++)if(cart[j].id==s.id){{cart[j].qty++;found=true;break;}}
if(!found)cart.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});
renderCart();
}}
function renderCart(){{
if(cart.length==0){{document.getElementById("cartList").innerHTML="<div style='text-align:center;color:#888;padding:40px'>Empty</div>";document.getElementById("tot").innerHTML="0.00";return;}}
var h="",tot=0;
for(var i=0;i<cart.length;i++){{var c=cart[i];var sub=c.price*c.qty;tot+=sub;
h+="<div style='display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #1e1e2e'><div><div style='font-weight:600'>"+c.desc+"</div><div style='color:#888;font-size:12px'>R "+c.price.toFixed(2)+" x "+c.qty+"</div></div><div style='display:flex;align-items:center;gap:10px'><span>R "+sub.toFixed(2)+"</span><button class='btn btn-sm btn-red' onclick='cart.splice("+i+",1);renderCart()'>X</button></div></div>";
}}
document.getElementById("cartList").innerHTML=h;
document.getElementById("tot").innerHTML=tot.toFixed(2);
}}
function pay(method){{
if(cart.length==0)return alert("Cart empty");
var tot=0;for(var i=0;i<cart.length;i++)tot+=cart[i].price*cart[i].qty;
var custId=document.getElementById("custSel").value;
fetch("/api/"+BID+"/sale",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{items:cart,total:tot,method:method,customer_id:custId}})}})
.then(function(r){{return r.json()}}).then(function(d){{
if(d.success){{alert("Sale complete! R "+tot.toFixed(2));cart=[];renderCart();load();}}
else alert("Error");
}});
}}
load();
</script>
</body></html>'''

# ============================================================================
# STOCK
# ============================================================================

@app.route("/<bid>/stock")
def stock_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stock</title>{CSS}</head><body>
{nav(bid,"stock")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:10px">
<h1>Stock Management</h1>
<div><a href="/{bid}/import" class="btn btn-orange">Import</a> <button class="btn" onclick="showAdd()">+ Add Item</button></div>
</div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<input type="text" id="q" placeholder="Search stock..." onkeyup="render()">
<div style="overflow-x:auto">
<table><thead><tr><th>Code</th><th>Description</th><th>Category</th><th>Qty</th><th>Cost</th><th>Price</th><th></th></tr></thead><tbody id="tbl"></tbody></table>
</div></div>
</div>
<div class="modal" id="modal">
<div class="modal-box">
<h3 id="mtitle" style="margin-bottom:20px">Add Item</h3>
<input type="hidden" id="eid">
<div class="row"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fcat" placeholder="Category" value="General"></div>
<input type="text" id="fdesc" placeholder="Description">
<div class="row">
<input type="number" id="fqty" placeholder="Qty" value="0">
<input type="number" id="fcost" placeholder="Cost" step="0.01" value="0">
<input type="number" id="fprice" placeholder="Sell Price" step="0.01" value="0">
</div>
<button class="btn" onclick="save()">Save</button>
<button class="btn" style="background:#333;margin-left:10px" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button>
</div>
</div>
<script>
var stock=[],BID="{bid}";
function load(){{
fetch("/api/"+BID+"/stock").then(function(r){{return r.json()}}).then(function(d){{
stock=d||[];
document.getElementById("msg").innerHTML="Loaded "+stock.length+" items";
document.getElementById("msg").className="msg msg-ok";
render();
}}).catch(function(e){{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err";}});
}}
function render(){{
var q=document.getElementById("q").value.toLowerCase();
var h="";
for(var i=0;i<stock.length;i++){{
var s=stock[i];
if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;
var qtyStyle=s.qty<=0?"color:#ef4444":s.qty<=5?"color:#f59e0b":"";
h+="<tr><td>"+s.code+"</td><td>"+s.desc+"</td><td>"+s.cat+"</td><td style='"+qtyStyle+"'>"+s.qty+"</td><td>R "+s.cost.toFixed(2)+"</td><td>R "+s.price.toFixed(2)+"</td><td><button class='btn btn-sm' onclick='edit("+i+")'>Edit</button></td></tr>";
}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='7' style='text-align:center;padding:40px;color:#888'>No items</td></tr>";
}}
function showAdd(){{
document.getElementById("mtitle").innerHTML="Add Item";
document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fdesc").value="";document.getElementById("fcat").value="General";document.getElementById("fqty").value="0";document.getElementById("fcost").value="0";document.getElementById("fprice").value="0";
document.getElementById("modal").classList.add("show");
}}
function edit(i){{
var s=stock[i];
document.getElementById("mtitle").innerHTML="Edit Item";
document.getElementById("eid").value=s.id;document.getElementById("fcode").value=s.code;document.getElementById("fdesc").value=s.desc;document.getElementById("fcat").value=s.cat;document.getElementById("fqty").value=s.qty;document.getElementById("fcost").value=s.cost;document.getElementById("fprice").value=s.price;
document.getElementById("modal").classList.add("show");
}}
function save(){{
var data={{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,description:document.getElementById("fdesc").value,category:document.getElementById("fcat").value||"General",qty:parseInt(document.getElementById("fqty").value)||0,cost:parseFloat(document.getElementById("fcost").value)||0,price:parseFloat(document.getElementById("fprice").value)||0}};
fetch("/api/"+BID+"/stock",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}}).then(function(r){{return r.json()}}).then(function(d){{if(d.success){{document.getElementById("modal").classList.remove("show");load();}}else alert("Error");}});
}}
load();
</script>
</body></html>'''

# ============================================================================
# CUSTOMERS
# ============================================================================

@app.route("/<bid>/customers")
def customers_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customers</title>{CSS}</head><body>
{nav(bid,"customers")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px"><h1>Customers</h1><button class="btn" onclick="showAdd()">+ Add Customer</button></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<input type="text" id="q" placeholder="Search..." onkeyup="render()">
<p style="color:#888;font-size:12px;margin-bottom:10px">Click a customer row to view transaction history</p>
<table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th></th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<div class="modal" id="modal">
<div class="modal-box">
<h3 id="mtitle" style="margin-bottom:20px">Add Customer</h3>
<input type="hidden" id="eid">
<div class="row"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div class="row"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<button class="btn" onclick="save()">Save</button>
<button class="btn" style="background:#333;margin-left:10px" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button>
</div>
</div>
<script>
var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/customers").then(function(r){{return r.json()}}).then(function(d){{items=d||[];document.getElementById("msg").innerHTML="Loaded "+items.length+" customers";document.getElementById("msg").className="msg msg-ok";render();}});}}
function render(){{
var q=document.getElementById("q").value.toLowerCase();var h="";
for(var i=0;i<items.length;i++){{var c=items[i];if(q&&c.name.toLowerCase().indexOf(q)<0&&c.code.toLowerCase().indexOf(q)<0)continue;
var balStyle=c.balance>0?"color:#ef4444":"";
h+="<tr style='cursor:pointer' onclick='viewHist(\""+c.id+"\")'><td>"+c.code+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td style='"+balStyle+"'>R "+c.balance.toFixed(2)+"</td><td><button class='btn btn-sm' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>";
}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='6' style='text-align:center;padding:40px;color:#888'>No customers</td></tr>";
}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add Customer";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show");}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit Customer";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code;document.getElementById("fname").value=c.name;document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show");}}
function save(){{var data={{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}};
fetch("/api/"+BID+"/customers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}}).then(function(r){{return r.json()}}).then(function(d){{if(d.success){{document.getElementById("modal").classList.remove("show");load();}}}});}}
function viewHist(id){{window.location.href="/"+BID+"/customers/"+id+"/history";}}
load();
</script>
</body></html>'''

@app.route("/<bid>/customers/<cid>/history")
def customer_history(bid, cid):
    customers = db.select("customers", {"id": cid})
    if not customers:
        return redirect(f"/{bid}/customers")
    cust = customers[0]
    invoices = db.select("invoices", {"business_id": bid})
    cust_invoices = [i for i in invoices if i.get("customer_id") == cid]
    total_sales = sum(float(i.get("total",0) or 0) for i in cust_invoices)
    total_paid = sum(float(i.get("total",0) or 0) for i in cust_invoices if i.get("status") == "paid")
    outstanding = total_sales - total_paid
    rows = ""
    for inv in sorted(cust_invoices, key=lambda x: x.get("date",""), reverse=True):
        status_class = "msg-ok" if inv.get("status") == "paid" else "msg"
        rows += f'<tr><td>{js_safe(inv.get("number",""))}</td><td>{str(inv.get("date",""))[:10]}</td><td>R {float(inv.get("total",0) or 0):,.2f}</td><td><span style="padding:4px 10px;border-radius:20px;font-size:11px" class="{status_class}">{inv.get("status","draft")}</span></td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customer History</title>{CSS}</head><body>
{nav(bid,"customers")}
<div class="box">
<a href="/{bid}/customers" class="btn" style="background:#333;margin-bottom:20px">Back to Customers</a>
<h1 style="margin-bottom:10px">{js_safe(cust.get("name",""))}</h1>
<p style="color:#888;margin-bottom:20px">Code: {js_safe(cust.get("code",""))} | Phone: {js_safe(cust.get("phone",""))} | Email: {js_safe(cust.get("email",""))}</p>
<div class="row">
<div class="stat"><div class="stat-num">{len(cust_invoices)}</div><div class="stat-label">Total Invoices</div></div>
<div class="stat"><div class="stat-num" style="color:#10b981">R {total_sales:,.0f}</div><div class="stat-label">Total Sales</div></div>
<div class="stat"><div class="stat-num" style="color:#3b82f6">R {total_paid:,.0f}</div><div class="stat-label">Total Paid</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {outstanding:,.0f}</div><div class="stat-label">Outstanding</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px">Transaction History</h3>
<table><thead><tr><th>Invoice #</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:#888'>No transactions</td></tr>"}</tbody></table></div>
</div></body></html>'''

# ============================================================================
# SUPPLIERS
# ============================================================================

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suppliers</title>{CSS}</head><body>
{nav(bid,"suppliers")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px"><h1>Suppliers</h1><button class="btn" onclick="showAdd()">+ Add Supplier</button></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<input type="text" id="q" placeholder="Search..." onkeyup="render()">
<p style="color:#888;font-size:12px;margin-bottom:10px">Click a supplier row to view purchase history</p>
<table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th></th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<div class="modal" id="modal">
<div class="modal-box">
<h3 id="mtitle" style="margin-bottom:20px">Add Supplier</h3>
<input type="hidden" id="eid">
<div class="row"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div class="row"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<button class="btn" onclick="save()">Save</button>
<button class="btn" style="background:#333;margin-left:10px" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button>
</div>
</div>
<script>
var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/suppliers").then(function(r){{return r.json()}}).then(function(d){{items=d||[];document.getElementById("msg").innerHTML="Loaded "+items.length+" suppliers";document.getElementById("msg").className="msg msg-ok";render();}});}}
function render(){{var h="";for(var i=0;i<items.length;i++){{var c=items[i];h+="<tr style='cursor:pointer' onclick='viewHist(\""+c.id+"\")'><td>"+c.code+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td><button class='btn btn-sm' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>";}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;padding:40px;color:#888'>No suppliers</td></tr>";}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add Supplier";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show");}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit Supplier";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code;document.getElementById("fname").value=c.name;document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show");}}
function save(){{var data={{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}};
fetch("/api/"+BID+"/suppliers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}}).then(function(r){{return r.json()}}).then(function(d){{if(d.success){{document.getElementById("modal").classList.remove("show");load();}}}});}}
function viewHist(id){{window.location.href="/"+BID+"/suppliers/"+id+"/history";}}
load();
</script>
</body></html>'''

@app.route("/<bid>/suppliers/<sid>/history")
def supplier_history(bid, sid):
    suppliers = db.select("suppliers", {"id": sid})
    if not suppliers:
        return redirect(f"/{bid}/suppliers")
    supp = suppliers[0]
    expenses = db.select("expenses", {"business_id": bid})
    supp_name = js_safe(supp.get("name","")).lower()
    supp_expenses = [e for e in expenses if js_safe(e.get("supplier","")).lower() == supp_name]
    total_spent = sum(float(e.get("amount",0) or 0) for e in supp_expenses)
    total_vat = sum(float(e.get("vat",0) or 0) for e in supp_expenses)
    rows = ""
    for exp in sorted(supp_expenses, key=lambda x: x.get("created_at",""), reverse=True):
        rows += f'<tr><td>{str(exp.get("created_at",""))[:10]}</td><td>{js_safe(exp.get("description",""))}</td><td>R {float(exp.get("amount",0) or 0):,.2f}</td><td>R {float(exp.get("vat",0) or 0):,.2f}</td></tr>'
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Supplier History</title>{CSS}</head><body>
{nav(bid,"suppliers")}
<div class="box">
<a href="/{bid}/suppliers" class="btn" style="background:#333;margin-bottom:20px">Back to Suppliers</a>
<h1 style="margin-bottom:10px">{js_safe(supp.get("name",""))}</h1>
<p style="color:#888;margin-bottom:20px">Code: {js_safe(supp.get("code",""))} | Phone: {js_safe(supp.get("phone",""))} | Email: {js_safe(supp.get("email",""))}</p>
<div class="row">
<div class="stat"><div class="stat-num">{len(supp_expenses)}</div><div class="stat-label">Total Purchases</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {total_spent:,.0f}</div><div class="stat-label">Total Spent</div></div>
<div class="stat"><div class="stat-num" style="color:#10b981">R {total_vat:,.0f}</div><div class="stat-label">VAT Claimed</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px">Purchase History</h3>
<table><thead><tr><th>Date</th><th>Description</th><th>Amount</th><th>VAT</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:#888'>No purchases recorded</td></tr>"}</tbody></table></div>
</div></body></html>'''

# ============================================================================
# INVOICES
# ============================================================================

@app.route("/<bid>/invoices")
def invoices_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Invoices</title>{CSS}</head><body>
{nav(bid,"invoices")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px"><h1>Invoices</h1><a href="/{bid}/invoices/new" class="btn btn-green">+ New Invoice</a></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<table><thead><tr><th>Invoice #</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<script>
var BID="{bid}";
fetch("/api/"+BID+"/invoices").then(function(r){{return r.json()}}).then(function(d){{
var items=d||[];
document.getElementById("msg").innerHTML="Loaded "+items.length+" invoices";
document.getElementById("msg").className="msg msg-ok";
var h="";
for(var i=0;i<items.length;i++){{var inv=items[i];
var badge=inv.status=="paid"?"badge-green":inv.status=="overdue"?"badge-red":"badge-orange";
h+="<tr><td>"+inv.number+"</td><td>"+inv.date+"</td><td>"+inv.customer_name+"</td><td>R "+inv.total.toFixed(2)+"</td><td><span class='badge "+badge+"'>"+inv.status+"</span></td></tr>";
}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;padding:40px;color:#888'>No invoices</td></tr>";
}});
</script>
</body></html>'''

@app.route("/<bid>/invoices/new")
def new_invoice(bid):
    return create_doc_page(bid, "Invoice", "INV", "invoices")

# ============================================================================
# QUOTES
# ============================================================================

@app.route("/<bid>/quotes")
def quotes_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quotes</title>{CSS}</head><body>
{nav(bid,"quotes")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px"><h1>Quotes</h1><a href="/{bid}/quotes/new" class="btn btn-purple">+ New Quote</a></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<table><thead><tr><th>Quote #</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<script>
var BID="{bid}";
fetch("/api/"+BID+"/quotes").then(function(r){{return r.json()}}).then(function(d){{
var items=d||[];
document.getElementById("msg").innerHTML="Loaded "+items.length+" quotes";
document.getElementById("msg").className="msg msg-ok";
var h="";
for(var i=0;i<items.length;i++){{var q=items[i];h+="<tr><td>"+q.number+"</td><td>"+q.date+"</td><td>"+q.customer_name+"</td><td>R "+q.total.toFixed(2)+"</td><td><span class='badge badge-orange'>"+q.status+"</span></td></tr>";}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;padding:40px;color:#888'>No quotes</td></tr>";
}});
</script>
</body></html>'''

@app.route("/<bid>/quotes/new")
def new_quote(bid):
    return create_doc_page(bid, "Quote", "QUO", "quotes")

def create_doc_page(bid, doc_type, prefix, table):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>New {doc_type}</title>{CSS}</head><body>
{nav(bid,"invoices" if doc_type=="Invoice" else "quotes")}
<div class="box">
<h1 style="margin-bottom:20px">New {doc_type}</h1>
<div class="row">
<div><label style="color:#888;font-size:12px">{doc_type} #</label><input type="text" id="docNum" value="{prefix}0001"></div>
<div><label style="color:#888;font-size:12px">Date</label><input type="date" id="docDate"></div>
<div><label style="color:#888;font-size:12px">Customer</label><select id="custSel"><option value="">Select customer</option></select></div>
</div>
<div class="card">
<h3 style="margin-bottom:15px">Add Items</h3>
<input type="text" id="q" placeholder="Search stock..." onkeyup="renderStock()">
<div class="grid" id="stockGrid" style="max-height:250px"></div>
</div>
<div class="card">
<h3 style="margin-bottom:15px">Line Items</h3>
<div id="lines"><div style="text-align:center;color:#888;padding:20px">Click items above to add</div></div>
<div style="text-align:right;margin-top:20px;font-size:20px;font-weight:700">Total: R <span id="total">0.00</span></div>
</div>
<button class="btn btn-green" style="width:100%" onclick="saveDoc()">Save {doc_type}</button>
</div>
<script>
var stock=[],lines=[],BID="{bid}",docType="{table}";
document.getElementById("docDate").value=new Date().toISOString().split("T")[0];
fetch("/api/"+BID+"/stock").then(function(r){{return r.json()}}).then(function(d){{stock=d||[];renderStock();}});
fetch("/api/"+BID+"/customers").then(function(r){{return r.json()}}).then(function(d){{
var h="<option value=''>Select customer</option>";
for(var i=0;i<(d||[]).length;i++)h+="<option value='"+d[i].id+"' data-name='"+d[i].name+"'>"+d[i].name+"</option>";
document.getElementById("custSel").innerHTML=h;
}});
function renderStock(){{
var q=document.getElementById("q").value.toLowerCase();var h="";
for(var i=0;i<stock.length;i++){{var s=stock[i];if(q&&s.desc.toLowerCase().indexOf(q)<0)continue;
h+="<div class='item' onclick='addLine("+i+")'><div style='font-weight:600;font-size:12px'>"+s.desc+"</div><div style='color:#10b981'>R "+s.price.toFixed(2)+"</div></div>";
}}
document.getElementById("stockGrid").innerHTML=h||"<div style='padding:20px;text-align:center;color:#888'>No items</div>";
}}
function addLine(i){{
var s=stock[i];var found=false;
for(var j=0;j<lines.length;j++)if(lines[j].id==s.id){{lines[j].qty++;found=true;break;}}
if(!found)lines.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});
renderLines();
}}
function renderLines(){{
if(lines.length==0){{document.getElementById("lines").innerHTML="<div style='text-align:center;color:#888;padding:20px'>Click items above to add</div>";document.getElementById("total").innerHTML="0.00";return;}}
var h="<table><thead><tr><th>Item</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr></thead><tbody>",tot=0;
for(var i=0;i<lines.length;i++){{var l=lines[i];var sub=l.price*l.qty;tot+=sub;
h+="<tr><td>"+l.desc+"</td><td>R "+l.price.toFixed(2)+"</td><td><input type='number' value='"+l.qty+"' min='1' style='width:60px' onchange='updateQty("+i+",this.value)'></td><td>R "+sub.toFixed(2)+"</td><td><button class='btn btn-sm btn-red' onclick='removeLine("+i+")'>X</button></td></tr>";
}}
h+="</tbody></table>";
document.getElementById("lines").innerHTML=h;
document.getElementById("total").innerHTML=tot.toFixed(2);
}}
function updateQty(i,v){{lines[i].qty=parseInt(v)||1;renderLines();}}
function removeLine(i){{lines.splice(i,1);renderLines();}}
function saveDoc(){{
var sel=document.getElementById("custSel");
var custName=sel.options[sel.selectedIndex]?sel.options[sel.selectedIndex].text:"Walk-in";
if(lines.length==0)return alert("Add at least one item");
var tot=0;for(var i=0;i<lines.length;i++)tot+=lines[i].price*lines[i].qty;
fetch("/api/"+BID+"/"+docType,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{
number:document.getElementById("docNum").value,date:document.getElementById("docDate").value,customer_id:sel.value,customer_name:custName,items:lines,total:tot
}})}}).then(function(r){{return r.json()}}).then(function(d){{
if(d.success){{alert("Saved!");location.href="/"+BID+"/"+docType;}}else alert("Error");
}});
}}
</script>
</body></html>'''

# ============================================================================
# EXPENSES
# ============================================================================

@app.route("/<bid>/expenses")
def expenses_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Expenses</title>{CSS}</head><body>
{nav(bid,"expenses")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:10px"><h1>Expenses</h1><div><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan Receipt</a> <button class="btn btn-red" onclick="showAdd()">+ Add Expense</button></div></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<table><thead><tr><th>Date</th><th>Supplier</th><th>Description</th><th>Amount</th><th>VAT</th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<div class="modal" id="modal">
<div class="modal-box">
<h3 style="margin-bottom:20px">Add Expense</h3>
<input type="text" id="fsupplier" placeholder="Supplier">
<input type="text" id="fdesc" placeholder="Description">
<input type="number" id="famount" placeholder="Amount (incl VAT)" step="0.01">
<label><input type="checkbox" id="fvat" checked> Includes 15% VAT</label>
<div style="margin-top:15px">
<button class="btn" onclick="save()">Save</button>
<button class="btn" style="background:#333;margin-left:10px" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button>
</div>
</div>
</div>
<script>
var items=[],BID="{bid}";
function load(){{
fetch("/api/"+BID+"/expenses").then(function(r){{return r.json()}}).then(function(d){{
items=d||[];
var tot=0;for(var i=0;i<items.length;i++)tot+=items[i].amount;
document.getElementById("msg").innerHTML="Loaded "+items.length+" expenses | Total: R "+tot.toFixed(2);
document.getElementById("msg").className="msg msg-ok";
render();
}});
}}
function render(){{
var h="";
for(var i=0;i<items.length;i++){{var e=items[i];h+="<tr><td>"+(e.date||"-")+"</td><td>"+e.supplier+"</td><td>"+e.description+"</td><td>R "+e.amount.toFixed(2)+"</td><td>R "+e.vat.toFixed(2)+"</td></tr>";}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;padding:40px;color:#888'>No expenses</td></tr>";
}}
function showAdd(){{document.getElementById("modal").classList.add("show");}}
function save(){{
var amt=parseFloat(document.getElementById("famount").value)||0;
var hasVat=document.getElementById("fvat").checked;
var vat=hasVat?amt*15/115:0;
fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{
supplier:document.getElementById("fsupplier").value,description:document.getElementById("fdesc").value,amount:amt,vat:vat
}})}}).then(function(r){{return r.json()}}).then(function(d){{if(d.success){{document.getElementById("modal").classList.remove("show");load();}}}});
}}
load();
</script>
</body></html>'''

@app.route("/<bid>/expenses/scan")
def scan_receipt(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Scan Receipt</title>{CSS}</head><body>
{nav(bid,"expenses")}
<div class="box">
<a href="/{bid}/expenses" class="btn" style="background:#333;margin-bottom:20px">Back to Expenses</a>
<h1 style="margin-bottom:20px">Scan Receipt</h1>
<div class="card">
<h3 style="margin-bottom:15px">Take Photo or Upload</h3>
<p style="color:#888;margin-bottom:15px">AI will automatically extract supplier, description and amount</p>
<div style="margin-bottom:15px">
<button class="btn btn-orange" onclick="startCamera()">Open Camera</button>
<span style="margin:0 10px;color:#888">or</span>
<input type="file" id="fileInput" accept="image/*" onchange="handleFile(this)" style="display:inline-block;width:auto">
</div>
<video id="video" autoplay playsinline style="display:none;width:100%;max-width:400px;border-radius:8px;background:#000"></video>
<button id="captureBtn" class="btn btn-green" style="display:none;margin-top:10px" onclick="capture()">Take Photo</button>
<canvas id="canvas" style="display:none"></canvas>
<img id="preview" style="display:none;max-width:100%;border-radius:8px;margin-top:10px">
<div id="processing" style="display:none;margin-top:15px" class="msg">AI is reading your receipt... please wait</div>
</div>
<div class="card" id="resultCard" style="display:none">
<h3 style="margin-bottom:15px">Extracted Details (edit if needed)</h3>
<label style="color:#888;font-size:12px">Supplier</label>
<input type="text" id="rSupplier" placeholder="Supplier">
<label style="color:#888;font-size:12px">Description</label>
<input type="text" id="rDesc" placeholder="Description">
<label style="color:#888;font-size:12px">Amount (incl VAT)</label>
<input type="number" id="rAmount" placeholder="Total Amount" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="rVat" checked> Includes 15% VAT</label>
<button class="btn btn-green" onclick="saveExpense()">Save Expense</button>
</div>
</div>
<script>
var BID="{bid}",stream=null;
function startCamera(){{
navigator.mediaDevices.getUserMedia({{video:{{facingMode:"environment"}}}}).then(function(s){{
stream=s;
document.getElementById("video").srcObject=s;
document.getElementById("video").style.display="block";
document.getElementById("captureBtn").style.display="inline-block";
}}).catch(function(e){{alert("Camera error: "+e.message);}});
}}
function capture(){{
var video=document.getElementById("video");
var canvas=document.getElementById("canvas");
canvas.width=video.videoWidth;
canvas.height=video.videoHeight;
canvas.getContext("2d").drawImage(video,0,0);
var dataUrl=canvas.toDataURL("image/jpeg",0.8);
if(stream){{stream.getTracks().forEach(function(t){{t.stop();}});}}
document.getElementById("video").style.display="none";
document.getElementById("captureBtn").style.display="none";
document.getElementById("preview").src=dataUrl;
document.getElementById("preview").style.display="block";
processWithAI(dataUrl);
}}
function handleFile(input){{
if(input.files&&input.files[0]){{
var reader=new FileReader();
reader.onload=function(e){{
document.getElementById("preview").src=e.target.result;
document.getElementById("preview").style.display="block";
processWithAI(e.target.result);
}};
reader.readAsDataURL(input.files[0]);
}}
}}
function processWithAI(dataUrl){{
document.getElementById("processing").style.display="block";
document.getElementById("resultCard").style.display="none";
fetch("/api/"+BID+"/scan-receipt",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{image:dataUrl}})}})
.then(function(r){{return r.json()}})
.then(function(d){{
document.getElementById("processing").style.display="none";
document.getElementById("resultCard").style.display="block";
if(d.supplier)document.getElementById("rSupplier").value=d.supplier;
if(d.description)document.getElementById("rDesc").value=d.description;
if(d.amount)document.getElementById("rAmount").value=d.amount;
if(d.error)alert("AI could not read receipt: "+d.error);
}}).catch(function(e){{
document.getElementById("processing").style.display="none";
document.getElementById("resultCard").style.display="block";
alert("Error processing: "+e);
}});
}}
function saveExpense(){{
var amt=parseFloat(document.getElementById("rAmount").value)||0;
var hasVat=document.getElementById("rVat").checked;
var vat=hasVat?amt*15/115:0;
if(!document.getElementById("rSupplier").value)return alert("Enter supplier name");
if(!amt)return alert("Enter amount");
fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{
supplier:document.getElementById("rSupplier").value,description:document.getElementById("rDesc").value||"Receipt",amount:amt,vat:vat
}})}}).then(function(r){{return r.json()}}).then(function(d){{
if(d.success){{alert("Expense saved!");location.href="/"+BID+"/expenses";}}else alert("Error saving");
}});
}}
</script>
</body></html>'''

# ============================================================================
# REPORTS
# ============================================================================

@app.route("/<bid>/reports")
def reports_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reports</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">Reports</h1>
<div class="row">
<a href="/{bid}/reports/sales" class="report-card"><h3>Sales Report</h3><p style="color:#888;margin-top:5px">Invoices, totals, paid vs outstanding</p></a>
<a href="/{bid}/reports/stock" class="report-card"><h3>Stock Report</h3><p style="color:#888;margin-top:5px">Levels, value, low stock alerts</p></a>
<a href="/{bid}/reports/customers" class="report-card"><h3>Customer Report</h3><p style="color:#888;margin-top:5px">Balances, outstanding amounts</p></a>
<a href="/{bid}/reports/suppliers" class="report-card"><h3>Supplier Report</h3><p style="color:#888;margin-top:5px">All suppliers, contact info</p></a>
<a href="/{bid}/reports/profit" class="report-card"><h3>Profit and Loss</h3><p style="color:#888;margin-top:5px">Income vs expenses</p></a>
<a href="/{bid}/reports/vat" class="report-card"><h3>VAT Report</h3><p style="color:#888;margin-top:5px">VAT collected vs paid</p></a>
</div>
</div></body></html>'''

@app.route("/<bid>/reports/sales")
def report_sales(bid):
    invoices = db.select("invoices", {"business_id": bid})
    total = sum(float(i.get("total",0) or 0) for i in invoices)
    paid = sum(float(i.get("total",0) or 0) for i in invoices if i.get("status")=="paid")
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>{js_safe(i.get("customer_name",""))}</td><td>R {float(i.get("total",0) or 0):,.2f}</td><td>{i.get("status","draft")}</td></tr>' for i in invoices[:20]])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sales Report</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">Sales Report</h1>
<div class="row">
<div class="stat"><div class="stat-num">{len(invoices)}</div><div class="stat-label">Total Invoices</div></div>
<div class="stat"><div class="stat-num" style="color:#10b981">R {total:,.0f}</div><div class="stat-label">Total Sales</div></div>
<div class="stat"><div class="stat-num" style="color:#3b82f6">R {paid:,.0f}</div><div class="stat-label">Paid</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {total-paid:,.0f}</div><div class="stat-label">Outstanding</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px">Recent Invoices</h3>
<table><thead><tr><th>Invoice</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan='5' style='text-align:center;color:#888'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn" style="margin-top:20px;background:#333">Back to Reports</a>
</div></body></html>'''

@app.route("/<bid>/reports/stock")
def report_stock(bid):
    stock = db.select("stock", {"business_id": bid})
    value = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    low = [s for s in stock if 0 < int(s.get("qty",0) or 0) <= 5]
    out = [s for s in stock if int(s.get("qty",0) or 0) <= 0]
    low_rows = "".join([f'<tr><td>{js_safe(s.get("code",""))}</td><td>{js_safe(s.get("description",""))}</td><td style="color:#f59e0b">{s.get("qty",0)}</td></tr>' for s in low[:15]])
    out_rows = "".join([f'<tr><td>{js_safe(s.get("code",""))}</td><td>{js_safe(s.get("description",""))}</td></tr>' for s in out[:15]])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stock Report</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">Stock Report</h1>
<div class="row">
<div class="stat"><div class="stat-num">{len(stock)}</div><div class="stat-label">Total Items</div></div>
<div class="stat"><div class="stat-num" style="color:#10b981">R {value:,.0f}</div><div class="stat-label">Total Value</div></div>
<div class="stat"><div class="stat-num" style="color:#f59e0b">{len(low)}</div><div class="stat-label">Low Stock</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">{len(out)}</div><div class="stat-label">Out of Stock</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px;color:#f59e0b">Low Stock Items</h3>
<table><thead><tr><th>Code</th><th>Description</th><th>Qty</th></tr></thead><tbody>{low_rows or "<tr><td colspan='3' style='text-align:center;color:#888'>None</td></tr>"}</tbody></table></div>
<div class="card"><h3 style="margin-bottom:15px;color:#ef4444">Out of Stock</h3>
<table><thead><tr><th>Code</th><th>Description</th></tr></thead><tbody>{out_rows or "<tr><td colspan='2' style='text-align:center;color:#888'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn" style="margin-top:20px;background:#333">Back to Reports</a>
</div></body></html>'''

@app.route("/<bid>/reports/customers")
def report_customers(bid):
    customers = db.select("customers", {"business_id": bid})
    total_bal = sum(float(c.get("balance",0) or 0) for c in customers)
    owing = sorted([c for c in customers if float(c.get("balance",0) or 0) > 0], key=lambda x: float(x.get("balance",0) or 0), reverse=True)
    rows = "".join([f'<tr><td>{js_safe(c.get("code",""))}</td><td>{js_safe(c.get("name",""))}</td><td>{js_safe(c.get("phone",""))}</td><td style="color:#ef4444">R {float(c.get("balance",0) or 0):,.2f}</td></tr>' for c in owing[:20]])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customer Report</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">Customer Report</h1>
<div class="row">
<div class="stat"><div class="stat-num">{len(customers)}</div><div class="stat-label">Total Customers</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {total_bal:,.0f}</div><div class="stat-label">Total Owing</div></div>
<div class="stat"><div class="stat-num" style="color:#f59e0b">{len(owing)}</div><div class="stat-label">With Balance</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px">Outstanding Balances</h3>
<table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Balance</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:#888'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn" style="margin-top:20px;background:#333">Back to Reports</a>
</div></body></html>'''

@app.route("/<bid>/reports/suppliers")
def report_suppliers(bid):
    suppliers = db.select("suppliers", {"business_id": bid})
    rows = "".join([f'<tr><td>{js_safe(s.get("code",""))}</td><td>{js_safe(s.get("name",""))}</td><td>{js_safe(s.get("phone",""))}</td><td>{js_safe(s.get("email",""))}</td></tr>' for s in suppliers[:30]])
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Supplier Report</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">Supplier Report</h1>
<div class="row">
<div class="stat"><div class="stat-num">{len(suppliers)}</div><div class="stat-label">Total Suppliers</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px">All Suppliers</h3>
<table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:#888'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn" style="margin-top:20px;background:#333">Back to Reports</a>
</div></body></html>'''

@app.route("/<bid>/reports/profit")
def report_profit(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    income = sum(float(i.get("total",0) or 0) for i in invoices)
    expense = sum(float(e.get("amount",0) or 0) for e in expenses)
    profit = income - expense
    margin = (profit/income*100) if income > 0 else 0
    pcolor = "#10b981" if profit >= 0 else "#ef4444"
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Profit and Loss</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">Profit and Loss</h1>
<div class="row">
<div class="stat"><div class="stat-num" style="color:#10b981">R {income:,.0f}</div><div class="stat-label">Total Income</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {expense:,.0f}</div><div class="stat-label">Total Expenses</div></div>
<div class="stat"><div class="stat-num" style="color:{pcolor}">R {profit:,.0f}</div><div class="stat-label">Net Profit</div></div>
<div class="stat"><div class="stat-num">{margin:.1f}%</div><div class="stat-label">Margin</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px">Summary</h3>
<table>
<tr><td>Sales Revenue</td><td style="text-align:right;color:#10b981">R {income:,.2f}</td></tr>
<tr><td>Less: Expenses</td><td style="text-align:right;color:#ef4444">(R {expense:,.2f})</td></tr>
<tr style="font-weight:700;font-size:18px"><td>Net Profit</td><td style="text-align:right;color:{pcolor}">R {profit:,.2f}</td></tr>
</table></div>
<a href="/{bid}/reports" class="btn" style="margin-top:20px;background:#333">Back to Reports</a>
</div></body></html>'''

@app.route("/<bid>/reports/vat")
def report_vat(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    sales = sum(float(i.get("total",0) or 0) for i in invoices)
    vat_out = sales * 15 / 115
    vat_in = sum(float(e.get("vat",0) or 0) for e in expenses)
    vat_due = vat_out - vat_in
    dcolor = "#ef4444" if vat_due > 0 else "#10b981"
    dlabel = "Payable to SARS" if vat_due > 0 else "Refund Due"
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VAT Report</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">VAT Report</h1>
<div class="row">
<div class="stat"><div class="stat-num" style="color:#3b82f6">R {vat_out:,.0f}</div><div class="stat-label">Output VAT (Sales)</div></div>
<div class="stat"><div class="stat-num" style="color:#10b981">R {vat_in:,.0f}</div><div class="stat-label">Input VAT (Purchases)</div></div>
<div class="stat"><div class="stat-num" style="color:{dcolor}">R {abs(vat_due):,.0f}</div><div class="stat-label">{dlabel}</div></div>
</div>
<div class="card" style="margin-top:20px"><h3 style="margin-bottom:15px">Calculation</h3>
<table>
<tr><td>Total Sales (incl VAT)</td><td style="text-align:right">R {sales:,.2f}</td></tr>
<tr><td>Output VAT @ 15%</td><td style="text-align:right">R {vat_out:,.2f}</td></tr>
<tr><td>Input VAT (from expenses)</td><td style="text-align:right">(R {vat_in:,.2f})</td></tr>
<tr style="font-weight:700"><td>{dlabel}</td><td style="text-align:right;color:{dcolor}">R {abs(vat_due):,.2f}</td></tr>
</table></div>
<a href="/{bid}/reports" class="btn" style="margin-top:20px;background:#333">Back to Reports</a>
</div></body></html>'''

# ============================================================================
# IMPORT
# ============================================================================

@app.route("/<bid>/import")
def import_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Import</title>{CSS}</head><body>
{nav(bid,"import")}
<div class="box">
<h1 style="margin-bottom:30px">Import Data</h1>
<div class="card">
<h3 style="margin-bottom:15px">Upload JSON File</h3>
<p style="color:#888;margin-bottom:15px">Upload your export file (fulltech.json etc)</p>
<input type="file" id="file" accept=".json">
<button class="btn" style="margin-top:10px" onclick="doImport()">Import</button>
<div id="msg" style="margin-top:15px"></div>
</div>
<div class="card">
<h3 style="margin-bottom:15px;color:#ef4444">Danger Zone - Delete All Data</h3>
<button class="btn btn-red" onclick="del('stock')">Delete Stock</button>
<button class="btn btn-red" style="margin-left:10px" onclick="del('customers')">Delete Customers</button>
<button class="btn btn-red" style="margin-left:10px" onclick="del('suppliers')">Delete Suppliers</button>
<button class="btn btn-red" style="margin-left:10px" onclick="del('invoices')">Delete Invoices</button>
<button class="btn btn-red" style="margin-left:10px" onclick="del('expenses')">Delete Expenses</button>
</div>
</div>
<script>
var BID="{bid}";
function doImport(){{
var f=document.getElementById("file").files[0];
if(!f)return alert("Select file");
var r=new FileReader();
r.onload=function(e){{
try{{
var d=JSON.parse(e.target.result);
document.getElementById("msg").innerHTML="<div class='msg'>Importing...</div>";
fetch("/api/"+BID+"/import",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(d)}})
.then(function(x){{return x.json()}})
.then(function(res){{
if(res.success)document.getElementById("msg").innerHTML="<div class='msg msg-ok'>Imported "+res.stock+" stock, "+res.customers+" customers, "+res.suppliers+" suppliers</div>";
else document.getElementById("msg").innerHTML="<div class='msg msg-err'>Error: "+res.error+"</div>";
}});
}}catch(err){{document.getElementById("msg").innerHTML="<div class='msg msg-err'>Invalid JSON</div>";}}
}};
r.readAsText(f);
}}
function del(t){{
if(!confirm("Delete ALL "+t+"? This cannot be undone!"))return;
fetch("/api/"+BID+"/delete/"+t,{{method:"POST"}}).then(function(x){{return x.json()}}).then(function(d){{alert(d.success?"Deleted!":"Error");location.reload();}});
}}
</script>
</body></html>'''

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route("/api/<bid>/stock", methods=["GET"])
def api_stock(bid):
    stock = db.select("stock", {"business_id": bid})
    return jsonify([{"id":s.get("id",""),"code":js_safe(s.get("code","")),"desc":js_safe(s.get("description","")),"cat":js_safe(s.get("category",""))or"General","qty":int(s.get("qty",0)or 0),"cost":float(s.get("cost",0)or 0),"price":float(s.get("price",0)or 0)} for s in stock])

@app.route("/api/<bid>/stock", methods=["POST"])
def api_stock_save(bid):
    d = request.get_json()
    item = {"business_id":bid,"code":d.get("code",""),"description":d.get("description",""),"category":d.get("category","General"),"qty":d.get("qty",0),"cost":d.get("cost",0),"price":d.get("price",0)}
    if d.get("id"):
        db.update("stock", d["id"], item)
    else:
        item["id"] = str(uuid.uuid4())
        db.insert("stock", item)
    return jsonify({"success":True})

@app.route("/api/<bid>/customers", methods=["GET"])
def api_customers(bid):
    customers = db.select("customers", {"business_id": bid})
    return jsonify([{"id":c.get("id",""),"code":js_safe(c.get("code","")),"name":js_safe(c.get("name","")),"phone":js_safe(c.get("phone","")),"email":js_safe(c.get("email","")),"balance":float(c.get("balance",0)or 0)} for c in customers])

@app.route("/api/<bid>/customers", methods=["POST"])
def api_customers_save(bid):
    d = request.get_json()
    item = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email",""),"balance":0}
    if d.get("id"):
        db.update("customers", d["id"], item)
    else:
        item["id"] = str(uuid.uuid4())
        db.insert("customers", item)
    return jsonify({"success":True})

@app.route("/api/<bid>/suppliers", methods=["GET"])
def api_suppliers(bid):
    suppliers = db.select("suppliers", {"business_id": bid})
    return jsonify([{"id":s.get("id",""),"code":js_safe(s.get("code","")),"name":js_safe(s.get("name","")),"phone":js_safe(s.get("phone","")),"email":js_safe(s.get("email","")),} for s in suppliers])

@app.route("/api/<bid>/suppliers", methods=["POST"])
def api_suppliers_save(bid):
    d = request.get_json()
    item = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        db.update("suppliers", d["id"], item)
    else:
        item["id"] = str(uuid.uuid4())
        db.insert("suppliers", item)
    return jsonify({"success":True})

@app.route("/api/<bid>/invoices", methods=["GET"])
def api_invoices(bid):
    invoices = db.select("invoices", {"business_id": bid})
    return jsonify([{"id":i.get("id",""),"number":js_safe(i.get("number","")),"date":str(i.get("date",""))[:10],"customer_name":js_safe(i.get("customer_name","")),"total":float(i.get("total",0)or 0),"status":i.get("status","draft")} for i in invoices])

@app.route("/api/<bid>/invoices", methods=["POST"])
def api_invoices_save(bid):
    d = request.get_json()
    item = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",datetime.now().isoformat()),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name","Walk-in"),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    db.insert("invoices", item)
    return jsonify({"success":True})

@app.route("/api/<bid>/quotes", methods=["GET"])
def api_quotes(bid):
    quotes = db.select("quotes", {"business_id": bid})
    return jsonify([{"id":q.get("id",""),"number":js_safe(q.get("number","")),"date":str(q.get("date",""))[:10],"customer_name":js_safe(q.get("customer_name","")),"total":float(q.get("total",0)or 0),"status":q.get("status","draft")} for q in quotes])

@app.route("/api/<bid>/quotes", methods=["POST"])
def api_quotes_save(bid):
    d = request.get_json()
    item = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",datetime.now().isoformat()),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    db.insert("quotes", item)
    return jsonify({"success":True})

@app.route("/api/<bid>/expenses", methods=["GET"])
def api_expenses(bid):
    expenses = db.select("expenses", {"business_id": bid})
    return jsonify([{"id":e.get("id",""),"date":str(e.get("created_at",""))[:10],"supplier":js_safe(e.get("supplier","")),"description":js_safe(e.get("description","")),"amount":float(e.get("amount",0)or 0),"vat":float(e.get("vat",0)or 0)} for e in expenses])

@app.route("/api/<bid>/expenses", methods=["POST"])
def api_expenses_save(bid):
    d = request.get_json()
    item = {"id":str(uuid.uuid4()),"business_id":bid,"supplier":d.get("supplier",""),"description":d.get("description",""),"amount":d.get("amount",0),"vat":d.get("vat",0)}
    db.insert("expenses", item)
    return jsonify({"success":True})

@app.route("/api/<bid>/scan-receipt", methods=["POST"])
def api_scan_receipt(bid):
    try:
        d = request.get_json()
        image_data = d.get("image", "")
        if not image_data:
            return jsonify({"error": "No image provided"})
        
        # Remove data URL prefix if present
        if "," in image_data:
            image_data = image_data.split(",")[1]
        
        # Call Claude API with vision
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return jsonify({"error": "API key not configured", "supplier": "", "description": "", "amount": ""})
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_data
                            }
                        },
                        {
                            "type": "text",
                            "text": "Extract from this receipt/invoice: 1) Supplier/store name, 2) Brief description of purchase, 3) Total amount in Rands. Reply ONLY in this exact JSON format, nothing else: {\"supplier\": \"name\", \"description\": \"what was bought\", \"amount\": 123.45}"
                        }
                    ]
                }]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("content", [{}])[0].get("text", "{}")
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^}]+\}', text)
            if json_match:
                data = json.loads(json_match.group())
                return jsonify({
                    "supplier": data.get("supplier", ""),
                    "description": data.get("description", ""),
                    "amount": float(data.get("amount", 0))
                })
        
        return jsonify({"error": "Could not parse receipt", "supplier": "", "description": "", "amount": ""})
    except Exception as e:
        return jsonify({"error": str(e), "supplier": "", "description": "", "amount": ""})

@app.route("/api/<bid>/sale", methods=["POST"])
def api_sale(bid):
    d = request.get_json()
    items = d.get("items", [])
    total = d.get("total", 0)
    inv_count = len(db.select("invoices", {"business_id": bid}))
    
    cust_name = "Walk-in"
    if d.get("customer_id"):
        custs = db.select("customers", {"id": d["customer_id"]})
        if custs:
            cust_name = custs[0].get("name", "Unknown")
    
    inv = {"id":str(uuid.uuid4()),"business_id":bid,"number":f"INV{inv_count+1:04d}","date":datetime.now().isoformat(),"customer_id":d.get("customer_id",""),"customer_name":cust_name,"items":json.dumps(items),"total":total,"status":"paid","payment_method":d.get("method","cash")}
    db.insert("invoices", inv)
    
    for item in items:
        sl = db.select("stock", {"id": item["id"]})
        if sl:
            new_qty = int(sl[0].get("qty", 0)) - int(item.get("qty", 1))
            db.update("stock", item["id"], {"qty": max(0, new_qty)})
    return jsonify({"success": True})

@app.route("/api/<bid>/import", methods=["POST"])
def api_import(bid):
    try:
        data = request.get_json()
        source = data.get("fulltech", data.get("hardware", data))
        if not source: source = data
        sc,cc,spc = 0,0,0
        for item in source.get("stock", []):
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"description":str(item.get("description",item.get("name","")))[:200],"category":str(item.get("category","General"))[:50],"qty":int(item.get("qty",0)or 0),"cost":float(item.get("cost",0)or 0),"price":float(item.get("price",item.get("sell",0))or 0)}
            if db.insert("stock",rec): sc+=1
        for item in source.get("customers", []):
            name=str(item.get("name","")).strip()
            if not name or "Address:" in name or len(name)<3: continue
            rec={"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",item.get("account","")))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100],"balance":float(item.get("balance",0)or 0)}
            if db.insert("customers",rec): cc+=1
        for item in source.get("suppliers", []):
            name=str(item.get("name","")).strip()
            if not name or "Address:" in name or len(name)<3: continue
            rec={"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",item.get("account","")))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100],"balance":float(item.get("balance",0)or 0)}
            if db.insert("suppliers",rec): spc+=1
        return jsonify({"success":True,"stock":sc,"customers":cc,"suppliers":spc})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/api/<bid>/delete/<table>", methods=["POST"])
def api_delete(bid, table):
    if table in ["stock","customers","suppliers","invoices","quotes","expenses"]:
        items = db.select(table, {"business_id": bid})
        for item in items:
            try:
                requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{item['id']}", headers=db.headers, timeout=30)
            except:
                pass
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "9"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
