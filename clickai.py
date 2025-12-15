"""
Click AI v8 - Bulletproof Edition
No emojis in JavaScript, simple clean code
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
.btn{padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:14px;background:#3b82f6;color:white}
.btn:hover{opacity:0.9}
.btn-green{background:#10b981}
.btn-red{background:#ef4444}
.btn-sm{padding:6px 12px;font-size:12px}
input,select{width:100%;padding:12px;border-radius:8px;border:1px solid #1e1e2e;background:#0a0a0f;color:#e0e0e0;font-size:14px;margin-bottom:10px}
table{width:100%;border-collapse:collapse}
th,td{padding:12px;text-align:left;border-bottom:1px solid #1e1e2e}
th{color:#888;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px;max-height:60vh;overflow-y:auto}
.item{background:#0a0a0f;border:1px solid #1e1e2e;border-radius:8px;padding:12px;cursor:pointer}
.item:hover{border-color:#3b82f6}
.msg{padding:15px;border-radius:8px;margin-bottom:15px;background:#1e3a5f;color:#60a5fa}
.msg-ok{background:#064e3b;color:#34d399}
.msg-err{background:#7f1d1d;color:#fca5a5}
.modal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);align-items:center;justify-content:center}
.modal.show{display:flex}
.modal-box{background:#12121a;border-radius:12px;padding:25px;width:90%;max-width:500px}
.stat{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:20px;text-align:center}
.stat-num{font-size:28px;font-weight:700;color:#3b82f6}
.stat-label{color:#888;font-size:13px;margin-top:5px}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px}
.cart{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:20px}
.total{font-size:24px;font-weight:700;color:#10b981;text-align:right;padding:15px 0}
</style>"""

def nav(bid, cur=""):
    items = [("Dashboard","/BID"),("POS","/BID/pos"),("Stock","/BID/stock"),("Customers","/BID/customers"),("Suppliers","/BID/suppliers"),("Invoices","/BID/invoices"),("Reports","/BID/reports"),("Import","/BID/import")]
    links = "".join([f'<a href="{u.replace("BID",bid)}" class="{"on" if n.lower()==cur else ""}">{n}</a>' for n,u in items])
    return f'<nav class="nav"><strong style="color:#3b82f6">Click AI</strong>{links}</nav>'

@app.route("/")
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}</head><body>
<div class="box" style="text-align:center;padding-top:100px">
<h1 style="font-size:48px;margin-bottom:20px">Click AI</h1>
<p style="color:#888;margin-bottom:40px">Business Management System</p>
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
    stock_val = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dashboard</title>{CSS}</head><body>
{nav(bid,"dashboard")}
<div class="box">
<h1 style="margin-bottom:30px">Dashboard</h1>
<div class="row">
<div class="stat"><div class="stat-num">{len(stock)}</div><div class="stat-label">Stock Items</div></div>
<div class="stat"><div class="stat-num">R {stock_val:,.0f}</div><div class="stat-label">Stock Value</div></div>
<div class="stat"><div class="stat-num">{len(customers)}</div><div class="stat-label">Customers</div></div>
<div class="stat"><div class="stat-num">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div>
</div>
<div class="card" style="margin-top:30px">
<h3 style="margin-bottom:15px">Quick Actions</h3>
<a href="/{bid}/pos" class="btn">New Sale</a>
<a href="/{bid}/stock" class="btn" style="margin-left:10px">Stock</a>
<a href="/{bid}/import" class="btn" style="margin-left:10px;background:#f59e0b">Import</a>
</div>
</div></body></html>'''

@app.route("/<bid>/pos")
def pos(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>POS</title>{CSS}</head><body>
{nav(bid,"pos")}
<div class="box">
<div id="msg" class="msg">Loading...</div>
<div style="display:grid;grid-template-columns:1fr 350px;gap:20px">
<div class="card">
<input type="text" id="q" placeholder="Search..." onkeyup="render()">
<div class="grid" id="items"></div>
</div>
<div class="cart">
<div style="display:flex;justify-content:space-between;margin-bottom:15px"><h3>Cart</h3><button class="btn btn-sm" onclick="cart=[];renderCart()">Clear</button></div>
<div id="cartList" style="min-height:200px"></div>
<div class="total">R <span id="tot">0.00</span></div>
<button class="btn btn-green" style="width:100%" onclick="pay()">Pay</button>
</div>
</div>
</div>
<script>
var stock=[],cart=[],BID="{bid}";
function load(){{
fetch("/api/"+BID+"/stock").then(function(r){{return r.json()}}).then(function(d){{
stock=d||[];
document.getElementById("msg").innerHTML="Loaded "+stock.length+" items";
document.getElementById("msg").className="msg msg-ok";
render();
}}).catch(function(e){{
document.getElementById("msg").innerHTML="Error: "+e;
document.getElementById("msg").className="msg msg-err";
}});
}}
function render(){{
var q=document.getElementById("q").value.toLowerCase();
var h="";
for(var i=0;i<stock.length;i++){{
var s=stock[i];
if(s.qty<=0)continue;
if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;
h+="<div class='item' onclick='add("+i+")'><div style='font-weight:600;font-size:12px'>"+s.desc+"</div><div style='color:#10b981'>R "+s.price.toFixed(2)+"</div><div style='color:#888;font-size:11px'>"+s.qty+" in stock</div></div>";
}}
document.getElementById("items").innerHTML=h||"<div style='padding:40px;text-align:center;color:#888'>No items</div>";
}}
function add(i){{
var s=stock[i];
var found=false;
for(var j=0;j<cart.length;j++){{
if(cart[j].id==s.id){{cart[j].qty++;found=true;break;}}
}}
if(!found)cart.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});
renderCart();
}}
function renderCart(){{
if(cart.length==0){{
document.getElementById("cartList").innerHTML="<div style='text-align:center;color:#888;padding:40px'>Empty</div>";
document.getElementById("tot").innerHTML="0.00";
return;
}}
var h="",tot=0;
for(var i=0;i<cart.length;i++){{
var c=cart[i];
var sub=c.price*c.qty;
tot+=sub;
h+="<div style='display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #1e1e2e'><div><div style='font-weight:600'>"+c.desc+"</div><div style='color:#888;font-size:12px'>R "+c.price.toFixed(2)+" x "+c.qty+"</div></div><div style='display:flex;align-items:center;gap:10px'><span>R "+sub.toFixed(2)+"</span><button class='btn btn-sm btn-red' onclick='cart.splice("+i+",1);renderCart()'>X</button></div></div>";
}}
document.getElementById("cartList").innerHTML=h;
document.getElementById("tot").innerHTML=tot.toFixed(2);
}}
function pay(){{
if(cart.length==0)return alert("Cart empty");
var tot=0;
for(var i=0;i<cart.length;i++)tot+=cart[i].price*cart[i].qty;
fetch("/api/"+BID+"/sale",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{items:cart,total:tot}})}})
.then(function(r){{return r.json()}})
.then(function(d){{
if(d.success){{alert("Sale complete! R "+tot.toFixed(2));cart=[];renderCart();load();}}
else alert("Error");
}});
}}
load();
</script>
</body></html>'''

@app.route("/<bid>/stock")
def stock_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stock</title>{CSS}</head><body>
{nav(bid,"stock")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px"><h1>Stock</h1><button class="btn" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<input type="text" id="q" placeholder="Search..." onkeyup="render()">
<table><thead><tr><th>Code</th><th>Description</th><th>Cat</th><th>Qty</th><th>Cost</th><th>Price</th><th></th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<div class="modal" id="modal">
<div class="modal-box">
<h3 id="mtitle" style="margin-bottom:20px">Add Item</h3>
<input type="hidden" id="eid">
<input type="text" id="fcode" placeholder="Code">
<input type="text" id="fdesc" placeholder="Description">
<input type="text" id="fcat" placeholder="Category" value="General">
<div class="row">
<input type="number" id="fqty" placeholder="Qty" value="0">
<input type="number" id="fcost" placeholder="Cost" step="0.01" value="0">
<input type="number" id="fprice" placeholder="Price" step="0.01" value="0">
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
}}).catch(function(e){{
document.getElementById("msg").innerHTML="Error: "+e;
document.getElementById("msg").className="msg msg-err";
}});
}}
function render(){{
var q=document.getElementById("q").value.toLowerCase();
var h="";
for(var i=0;i<stock.length;i++){{
var s=stock[i];
if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;
h+="<tr><td>"+s.code+"</td><td>"+s.desc+"</td><td>"+s.cat+"</td><td>"+s.qty+"</td><td>R "+s.cost.toFixed(2)+"</td><td>R "+s.price.toFixed(2)+"</td><td><button class='btn btn-sm' onclick='edit("+i+")'>Edit</button></td></tr>";
}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='7' style='text-align:center;padding:40px;color:#888'>No items</td></tr>";
}}
function showAdd(){{
document.getElementById("mtitle").innerHTML="Add Item";
document.getElementById("eid").value="";
document.getElementById("fcode").value="";
document.getElementById("fdesc").value="";
document.getElementById("fcat").value="General";
document.getElementById("fqty").value="0";
document.getElementById("fcost").value="0";
document.getElementById("fprice").value="0";
document.getElementById("modal").classList.add("show");
}}
function edit(i){{
var s=stock[i];
document.getElementById("mtitle").innerHTML="Edit Item";
document.getElementById("eid").value=s.id;
document.getElementById("fcode").value=s.code;
document.getElementById("fdesc").value=s.desc;
document.getElementById("fcat").value=s.cat;
document.getElementById("fqty").value=s.qty;
document.getElementById("fcost").value=s.cost;
document.getElementById("fprice").value=s.price;
document.getElementById("modal").classList.add("show");
}}
function save(){{
var data={{
id:document.getElementById("eid").value||null,
code:document.getElementById("fcode").value,
description:document.getElementById("fdesc").value,
category:document.getElementById("fcat").value||"General",
qty:parseInt(document.getElementById("fqty").value)||0,
cost:parseFloat(document.getElementById("fcost").value)||0,
price:parseFloat(document.getElementById("fprice").value)||0
}};
fetch("/api/"+BID+"/stock",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}})
.then(function(r){{return r.json()}})
.then(function(d){{
if(d.success){{document.getElementById("modal").classList.remove("show");load();}}
else alert("Error");
}});
}}
load();
</script>
</body></html>'''

@app.route("/<bid>/customers")
def customers_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Customers</title>{CSS}</head><body>
{nav(bid,"customers")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px"><h1>Customers</h1><button class="btn" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<input type="text" id="q" placeholder="Search..." onkeyup="render()">
<table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th></th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<div class="modal" id="modal">
<div class="modal-box">
<h3 id="mtitle" style="margin-bottom:20px">Add Customer</h3>
<input type="hidden" id="eid">
<input type="text" id="fcode" placeholder="Code">
<input type="text" id="fname" placeholder="Name">
<input type="text" id="fphone" placeholder="Phone">
<input type="text" id="femail" placeholder="Email">
<button class="btn" onclick="save()">Save</button>
<button class="btn" style="background:#333;margin-left:10px" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button>
</div>
</div>
<script>
var items=[],BID="{bid}";
function load(){{
fetch("/api/"+BID+"/customers").then(function(r){{return r.json()}}).then(function(d){{
items=d||[];
document.getElementById("msg").innerHTML="Loaded "+items.length+" customers";
document.getElementById("msg").className="msg msg-ok";
render();
}});
}}
function render(){{
var q=document.getElementById("q").value.toLowerCase();
var h="";
for(var i=0;i<items.length;i++){{
var c=items[i];
if(q&&c.name.toLowerCase().indexOf(q)<0&&c.code.toLowerCase().indexOf(q)<0)continue;
h+="<tr><td>"+c.code+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td>R "+c.balance.toFixed(2)+"</td><td><button class='btn btn-sm' onclick='edit("+i+")'>Edit</button></td></tr>";
}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='6' style='text-align:center;padding:40px;color:#888'>No customers</td></tr>";
}}
function showAdd(){{
document.getElementById("mtitle").innerHTML="Add Customer";
document.getElementById("eid").value="";
document.getElementById("fcode").value="";
document.getElementById("fname").value="";
document.getElementById("fphone").value="";
document.getElementById("femail").value="";
document.getElementById("modal").classList.add("show");
}}
function edit(i){{
var c=items[i];
document.getElementById("mtitle").innerHTML="Edit Customer";
document.getElementById("eid").value=c.id;
document.getElementById("fcode").value=c.code;
document.getElementById("fname").value=c.name;
document.getElementById("fphone").value=c.phone||"";
document.getElementById("femail").value=c.email||"";
document.getElementById("modal").classList.add("show");
}}
function save(){{
var data={{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}};
fetch("/api/"+BID+"/customers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}})
.then(function(r){{return r.json()}})
.then(function(d){{if(d.success){{document.getElementById("modal").classList.remove("show");load();}}}});
}}
load();
</script>
</body></html>'''

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suppliers</title>{CSS}</head><body>
{nav(bid,"suppliers")}
<div class="box">
<div style="display:flex;justify-content:space-between;margin-bottom:20px"><h1>Suppliers</h1><button class="btn" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th></th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<div class="modal" id="modal">
<div class="modal-box">
<h3 id="mtitle" style="margin-bottom:20px">Add Supplier</h3>
<input type="hidden" id="eid">
<input type="text" id="fcode" placeholder="Code">
<input type="text" id="fname" placeholder="Name">
<input type="text" id="fphone" placeholder="Phone">
<input type="text" id="femail" placeholder="Email">
<button class="btn" onclick="save()">Save</button>
<button class="btn" style="background:#333;margin-left:10px" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button>
</div>
</div>
<script>
var items=[],BID="{bid}";
function load(){{
fetch("/api/"+BID+"/suppliers").then(function(r){{return r.json()}}).then(function(d){{
items=d||[];
document.getElementById("msg").innerHTML="Loaded "+items.length+" suppliers";
document.getElementById("msg").className="msg msg-ok";
render();
}});
}}
function render(){{
var h="";
for(var i=0;i<items.length;i++){{
var c=items[i];
h+="<tr><td>"+c.code+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td><button class='btn btn-sm' onclick='edit("+i+")'>Edit</button></td></tr>";
}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;padding:40px;color:#888'>No suppliers</td></tr>";
}}
function showAdd(){{
document.getElementById("mtitle").innerHTML="Add Supplier";
document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";
document.getElementById("modal").classList.add("show");
}}
function edit(i){{
var c=items[i];
document.getElementById("mtitle").innerHTML="Edit Supplier";
document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code;document.getElementById("fname").value=c.name;document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";
document.getElementById("modal").classList.add("show");
}}
function save(){{
var data={{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}};
fetch("/api/"+BID+"/suppliers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}})
.then(function(r){{return r.json()}})
.then(function(d){{if(d.success){{document.getElementById("modal").classList.remove("show");load();}}}});
}}
load();
</script>
</body></html>'''

@app.route("/<bid>/invoices")
def invoices_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Invoices</title>{CSS}</head><body>
{nav(bid,"invoices")}
<div class="box">
<h1 style="margin-bottom:20px">Invoices</h1>
<div id="msg" class="msg">Loading...</div>
<div class="card">
<table><thead><tr><th>Invoice</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table>
</div>
</div>
<script>
var BID="{bid}";
fetch("/api/"+BID+"/invoices").then(function(r){{return r.json()}}).then(function(d){{
var items=d||[];
document.getElementById("msg").innerHTML="Loaded "+items.length+" invoices";
document.getElementById("msg").className="msg msg-ok";
var h="";
for(var i=0;i<items.length;i++){{
var inv=items[i];
h+="<tr><td>"+inv.number+"</td><td>"+inv.date+"</td><td>"+inv.customer_name+"</td><td>R "+inv.total.toFixed(2)+"</td><td>"+inv.status+"</td></tr>";
}}
document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;padding:40px;color:#888'>No invoices</td></tr>";
}});
</script>
</body></html>'''

@app.route("/<bid>/reports")
def reports_page(bid):
    stock = db.select("stock", {"business_id": bid})
    customers = db.select("customers", {"business_id": bid})
    suppliers = db.select("suppliers", {"business_id": bid})
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    
    stock_val = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    low = len([s for s in stock if 0 < int(s.get("qty",0) or 0) <= 5])
    out = len([s for s in stock if int(s.get("qty",0) or 0) <= 0])
    cust_bal = sum(float(c.get("balance",0) or 0) for c in customers)
    income = sum(float(i.get("total",0) or 0) for i in invoices)
    expense = sum(float(e.get("amount",0) or 0) for e in expenses)
    profit = income - expense
    vat_out = income * 15 / 115
    vat_in = sum(float(e.get("vat",0) or 0) for e in expenses)
    
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reports</title>{CSS}</head><body>
{nav(bid,"reports")}
<div class="box">
<h1 style="margin-bottom:30px">Reports</h1>

<div class="card"><h3 style="margin-bottom:15px">Stock Report</h3>
<div class="row">
<div class="stat"><div class="stat-num">{len(stock)}</div><div class="stat-label">Total Items</div></div>
<div class="stat"><div class="stat-num">R {stock_val:,.0f}</div><div class="stat-label">Stock Value</div></div>
<div class="stat"><div class="stat-num" style="color:#f59e0b">{low}</div><div class="stat-label">Low Stock</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">{out}</div><div class="stat-label">Out of Stock</div></div>
</div></div>

<div class="card"><h3 style="margin-bottom:15px">Customer Report</h3>
<div class="row">
<div class="stat"><div class="stat-num">{len(customers)}</div><div class="stat-label">Customers</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {cust_bal:,.0f}</div><div class="stat-label">Total Owing</div></div>
</div></div>

<div class="card"><h3 style="margin-bottom:15px">Supplier Report</h3>
<div class="row">
<div class="stat"><div class="stat-num">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div>
</div></div>

<div class="card"><h3 style="margin-bottom:15px">Profit and Loss</h3>
<div class="row">
<div class="stat"><div class="stat-num" style="color:#10b981">R {income:,.0f}</div><div class="stat-label">Income</div></div>
<div class="stat"><div class="stat-num" style="color:#ef4444">R {expense:,.0f}</div><div class="stat-label">Expenses</div></div>
<div class="stat"><div class="stat-num" style="color:{"#10b981" if profit>=0 else "#ef4444"}">R {profit:,.0f}</div><div class="stat-label">Profit</div></div>
</div></div>

<div class="card"><h3 style="margin-bottom:15px">VAT Report</h3>
<div class="row">
<div class="stat"><div class="stat-num">R {vat_out:,.0f}</div><div class="stat-label">Output VAT</div></div>
<div class="stat"><div class="stat-num">R {vat_in:,.0f}</div><div class="stat-label">Input VAT</div></div>
<div class="stat"><div class="stat-num" style="color:{"#ef4444" if vat_out-vat_in>0 else "#10b981"}">R {abs(vat_out-vat_in):,.0f}</div><div class="stat-label">{"Payable" if vat_out-vat_in>0 else "Refund"}</div></div>
</div></div>

</div></body></html>'''

@app.route("/<bid>/import")
def import_page(bid):
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Import</title>{CSS}</head><body>
{nav(bid,"import")}
<div class="box">
<h1 style="margin-bottom:30px">Import Data</h1>
<div class="card">
<h3 style="margin-bottom:15px">Upload JSON</h3>
<input type="file" id="file" accept=".json">
<button class="btn" style="margin-top:10px" onclick="doImport()">Import</button>
<div id="msg" style="margin-top:15px"></div>
</div>
<div class="card">
<h3 style="margin-bottom:15px;color:#ef4444">Delete All Data</h3>
<button class="btn btn-red" onclick="del('stock')">Delete Stock</button>
<button class="btn btn-red" style="margin-left:10px" onclick="del('customers')">Delete Customers</button>
<button class="btn btn-red" style="margin-left:10px" onclick="del('suppliers')">Delete Suppliers</button>
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
if(!confirm("Delete ALL "+t+"?"))return;
fetch("/api/"+BID+"/delete/"+t,{{method:"POST"}}).then(function(x){{return x.json()}}).then(function(d){{alert(d.success?"Deleted":"Error")}});
}}
</script>
</body></html>'''

# API ENDPOINTS
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

@app.route("/api/<bid>/expenses", methods=["GET"])
def api_expenses(bid):
    expenses = db.select("expenses", {"business_id": bid})
    return jsonify([{"id":e.get("id",""),"supplier":js_safe(e.get("supplier","")),"description":js_safe(e.get("description","")),"amount":float(e.get("amount",0)or 0),"vat":float(e.get("vat",0)or 0)} for e in expenses])

@app.route("/api/<bid>/sale", methods=["POST"])
def api_sale(bid):
    d = request.get_json()
    items = d.get("items", [])
    total = d.get("total", 0)
    inv_count = len(db.select("invoices", {"business_id": bid}))
    inv = {"id":str(uuid.uuid4()),"business_id":bid,"number":f"INV{inv_count+1:04d}","date":datetime.now().isoformat(),"customer_name":"Walk-in","items":json.dumps(items),"total":total,"status":"paid"}
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
    if table in ["stock","customers","suppliers","invoices","expenses"]:
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
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
