"""
Click AI v10 - Lit Up Edition
Sticky glowing header, no duplicate titles, clean UI
"""

from flask import Flask, jsonify, request, redirect
import json, os, re, uuid, requests
from datetime import datetime

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
            for k, v in filters.items(): url += f"&{k}=eq.{v}"
        try:
            r = requests.get(url, headers=self.headers, timeout=60)
            return r.json() if r.status_code == 200 else []
        except: return []
    
    def insert(self, table, data):
        try:
            r = requests.post(f"{self.url}/rest/v1/{table}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 201]
        except: return False
    
    def update(self, table, id, data):
        try:
            r = requests.patch(f"{self.url}/rest/v1/{table}?id=eq.{id}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 204]
        except: return False

db = DB(SUPABASE_URL, SUPABASE_KEY)

def post_journal(bid, date, desc, account, debit, credit):
    return db.insert("journal", {"id": str(uuid.uuid4()), "business_id": bid, "date": date, "description": desc, "account": account, "debit": debit, "credit": credit})

CSS = """<style>
:root{--bg:#06060a;--card:#0d0d14;--border:#1a1a2e;--text:#e0e0e0;--muted:#666;--blue:#3b82f6;--purple:#8b5cf6;--green:#10b981;--red:#ef4444;--orange:#f59e0b;--glow:rgba(139,92,246,0.5)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{position:sticky;top:0;z-index:100;background:linear-gradient(180deg,#0d0d14,rgba(13,13,20,0.95));border-bottom:1px solid var(--border);padding:0 15px;height:52px;display:flex;align-items:center;gap:6px;backdrop-filter:blur(10px);overflow-x:auto}
.header::-webkit-scrollbar{height:0}
.logo{font-size:18px;font-weight:800;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-decoration:none;margin-right:10px;white-space:nowrap;animation:pulse 3s ease-in-out infinite}
@keyframes pulse{0%,100%{filter:brightness(1)}50%{filter:brightness(1.3)}}
.nav-item{padding:6px 12px;border-radius:6px;text-decoration:none;color:var(--muted);font-size:12px;font-weight:500;white-space:nowrap;transition:all 0.2s;border:1px solid transparent}
.nav-item:hover{color:var(--text);background:rgba(255,255,255,0.05)}
.nav-item.active{color:white;background:linear-gradient(135deg,rgba(139,92,246,0.3),rgba(59,130,246,0.3));border-color:rgba(139,92,246,0.5);box-shadow:0 0 15px rgba(139,92,246,0.2)}
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.btn{padding:10px 18px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:14px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:all 0.2s}
.btn-blue{background:var(--blue);color:white}.btn-green{background:var(--green);color:white}.btn-red{background:var(--red);color:white}.btn-purple{background:var(--purple);color:white}.btn-orange{background:var(--orange);color:black}.btn-ghost{background:rgba(255,255,255,0.05);color:var(--text);border:1px solid var(--border)}
.btn:hover{opacity:0.9;transform:translateY(-1px)}.btn-sm{padding:6px 12px;font-size:12px}
input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;margin-bottom:12px}
input:focus,select:focus{outline:none;border-color:var(--purple)}
table{width:100%;border-collapse:collapse}th,td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}th{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;text-align:center}
.stat-value{font-size:26px;font-weight:700;color:var(--blue)}.stat-label{color:var(--muted);font-size:11px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;max-height:55vh;overflow-y:auto;padding:4px}
.grid-item{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px;cursor:pointer;transition:all 0.2s}
.grid-item:hover{border-color:var(--purple);transform:translateY(-2px)}
.grid-item-name{font-weight:600;font-size:12px;margin-bottom:3px}.grid-item-price{color:var(--green);font-weight:700;font-size:13px}.grid-item-stock{color:var(--muted);font-size:10px}
.cart{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.cart-total{font-size:26px;font-weight:800;color:var(--green);text-align:right;padding:12px 0}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);align-items:center;justify-content:center;z-index:200}
.modal.show{display:flex}.modal-box{background:var(--card);border-radius:16px;padding:25px;width:90%;max-width:500px;max-height:90vh;overflow-y:auto}
.modal-title{font-size:18px;font-weight:700;margin-bottom:20px}
.msg{padding:12px 16px;border-radius:8px;margin-bottom:15px;font-size:13px}
.msg-info{background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);color:var(--blue)}
.msg-ok{background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);color:var(--green)}
.msg-err{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--red)}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:rgba(16,185,129,0.2);color:var(--green)}.badge-orange{background:rgba(245,158,11,0.2);color:var(--orange)}.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.report-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:15px}
.report-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;text-decoration:none;color:var(--text);transition:all 0.2s}
.report-card:hover{border-color:var(--purple);transform:translateY(-3px);box-shadow:0 10px 30px rgba(0,0,0,0.3)}
.report-card h3{margin-bottom:6px}.report-card p{color:var(--muted);font-size:12px}
@media(max-width:768px){.header{padding:0 10px;gap:4px}.logo{font-size:16px;margin-right:8px}.nav-item{padding:5px 8px;font-size:11px}.container{padding:15px}.pos-layout{grid-template-columns:1fr!important}.stats{grid-template-columns:repeat(2,1fr)}}
</style>"""

def header(bid, active=""):
    items = [("home","Home",f"/{bid}"),("pos","POS",f"/{bid}/pos"),("stock","Stock",f"/{bid}/stock"),("customers","Cust",f"/{bid}/customers"),("suppliers","Supp",f"/{bid}/suppliers"),("invoices","Inv",f"/{bid}/invoices"),("quotes","Quote",f"/{bid}/quotes"),("expenses","Exp",f"/{bid}/expenses"),("reports","Reports",f"/{bid}/reports"),("import","Import",f"/{bid}/import")]
    nav = "".join([f'<a href="{u}" class="nav-item{"  active" if k==active else ""}">{l}</a>' for k,l,u in items])
    return f'<div class="header"><a href="/{bid}" class="logo">Click AI</a>{nav}</div>'

def page(bid, active, title, content):
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{CSS}</head><body>{header(bid,active)}<div class="container">{content}</div></body></html>'

@app.route("/")
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}
<style>.landing{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:20px}}
.landing-logo{{font-size:60px;font-weight:900;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:glow 2s ease-in-out infinite}}
@keyframes glow{{0%,100%{{filter:drop-shadow(0 0 20px var(--glow))}}50%{{filter:drop-shadow(0 0 40px var(--glow))}}}}</style>
</head><body><div class="landing"><div class="landing-logo">Click AI</div><p style="color:var(--muted);margin:20px 0 40px">Business Management</p><a href="/demo" class="btn btn-purple" style="font-size:18px;padding:15px 40px">Enter</a></div></body></html>'''

@app.route("/demo")
def demo(): return redirect("/5742fb2c-5fd8-4d44-9ddb-b73a3dd51da3")

@app.route("/<bid>")
def dashboard(bid):
    stock = db.select("stock", {"business_id": bid})
    customers = db.select("customers", {"business_id": bid})
    suppliers = db.select("suppliers", {"business_id": bid})
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    stock_val = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    inv_total = sum(float(i.get("total",0) or 0) for i in invoices)
    exp_total = sum(float(e.get("amount",0) or 0) for e in expenses)
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Stock</div></div><div class="stat"><div class="stat-value">R{stock_val:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total:,.0f}</div><div class="stat-label">Sales</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{exp_total:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total-exp_total:,.0f}</div><div class="stat-label">Profit</div></div><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div></div>
<div class="card"><h3 style="margin-bottom:15px">Quick Actions</h3><div style="display:flex;flex-wrap:wrap;gap:10px"><a href="/{bid}/pos" class="btn btn-blue">New Sale</a><a href="/{bid}/invoices/new" class="btn btn-green">New Invoice</a><a href="/{bid}/quotes/new" class="btn btn-purple">New Quote</a><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan Receipt</a></div></div>'''
    return page(bid, "home", "Dashboard", content)

@app.route("/<bid>/pos")
def pos(bid):
    content = f'''<div id="msg" class="msg msg-info">Loading...</div>
<div class="pos-layout" style="display:grid;grid-template-columns:1fr 320px;gap:15px">
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div class="grid" id="items"></div></div>
<div class="cart"><div style="display:flex;justify-content:space-between;margin-bottom:10px"><h3>Cart</h3><button class="btn btn-sm btn-ghost" onclick="cart=[];renderCart()">Clear</button></div>
<select id="custSel" style="margin-bottom:10px"><option value="">Walk-in</option></select>
<div id="cartList" style="min-height:120px"></div><div class="cart-total">R <span id="tot">0.00</span></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><button class="btn btn-green" onclick="pay('cash')">Cash</button><button class="btn btn-blue" onclick="pay('card')">Card</button></div>
<button class="btn btn-purple" style="width:100%;margin-top:8px" onclick="pay('account')">Account</button></div></div>
<script>var stock=[],cart=[],customers=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];return fetch("/api/"+BID+"/customers")}}).then(r=>r.json()).then(c=>{{customers=c||[];var sel="<option value=''>Walk-in</option>";customers.forEach(cu=>{{sel+="<option value='"+cu.id+"'>"+cu.name+"</option>"}});document.getElementById("custSel").innerHTML=sel;document.getElementById("msg").innerHTML="Ready - "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="",c=0;for(var i=0;i<stock.length&&c<80;i++){{var s=stock[i];if(s.qty<=0)continue;if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;h+="<div class='grid-item' onclick='add("+i+")'><div class='grid-item-name'>"+s.desc+"</div><div class='grid-item-price'>R"+s.price.toFixed(2)+"</div><div class='grid-item-stock'>"+s.qty+" left</div></div>";c++}}document.getElementById("items").innerHTML=h||"<div style='padding:30px;text-align:center;color:var(--muted)'>No items</div>"}}
function add(i){{var s=stock[i];var f=cart.findIndex(c=>c.id==s.id);if(f>=0)cart[f].qty++;else cart.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});renderCart()}}
function renderCart(){{if(cart.length==0){{document.getElementById("cartList").innerHTML="<div style='text-align:center;color:var(--muted);padding:30px'>Empty</div>";document.getElementById("tot").innerHTML="0.00";return}}var h="",tot=0;cart.forEach((c,i)=>{{var sub=c.price*c.qty;tot+=sub;h+="<div class='cart-item'><div><div style='font-weight:600;font-size:13px'>"+c.desc+"</div><div style='color:var(--muted);font-size:11px'>R"+c.price.toFixed(2)+" x "+c.qty+"</div></div><div style='display:flex;align-items:center;gap:8px'><span style='font-weight:600'>R"+sub.toFixed(2)+"</span><button class='btn btn-sm btn-red' onclick='cart.splice("+i+",1);renderCart()'>X</button></div></div>"}});document.getElementById("cartList").innerHTML=h;document.getElementById("tot").innerHTML=tot.toFixed(2)}}
function pay(method){{if(cart.length==0)return alert("Cart empty");var tot=cart.reduce((a,c)=>a+c.price*c.qty,0);fetch("/api/"+BID+"/sale",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{items:cart,total:tot,method:method,customer_id:document.getElementById("custSel").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Done! R"+tot.toFixed(2));cart=[];renderCart();load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "pos", "POS", content)
# ═══════════════════════════════════════════════════════════════════════════════
# STOCK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/stock")
def stock_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/import" class="btn btn-orange">Import</a><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Description</th><th>Cat</th><th>Qty</th><th>Cost</th><th>Price</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Item</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fcat" placeholder="Category" value="General"></div>
<input type="text" id="fdesc" placeholder="Description">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px"><input type="number" id="fqty" placeholder="Qty" value="0"><input type="number" id="fcost" placeholder="Cost" step="0.01"><input type="number" id="fprice" placeholder="Price" step="0.01"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var stock=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];document.getElementById("msg").innerHTML="Loaded "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";stock.forEach((s,i)=>{{if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)return;var qs=s.qty<=0?"color:var(--red)":s.qty<=5?"color:var(--orange)":"";h+="<tr><td>"+s.code+"</td><td>"+s.desc+"</td><td>"+s.category+"</td><td style='"+qs+"'>"+s.qty+"</td><td>R"+s.cost.toFixed(2)+"</td><td>R"+s.price.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='7' style='text-align:center;color:var(--muted);padding:30px'>No items</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fcat").value="General";document.getElementById("fdesc").value="";document.getElementById("fqty").value="0";document.getElementById("fcost").value="";document.getElementById("fprice").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var s=stock[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=s.id;document.getElementById("fcode").value=s.code||"";document.getElementById("fcat").value=s.category||"General";document.getElementById("fdesc").value=s.desc||"";document.getElementById("fqty").value=s.qty||0;document.getElementById("fcost").value=s.cost||0;document.getElementById("fprice").value=s.price||0;document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/stock",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,category:document.getElementById("fcat").value,description:document.getElementById("fdesc").value,qty:parseInt(document.getElementById("fqty").value)||0,cost:parseFloat(document.getElementById("fcost").value)||0,price:parseFloat(document.getElementById("fprice").value)||0}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "stock", "Stock", content)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/customers")
def customers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Customer</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" customers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;var bal=c.balance||0;var bs=bal>0?"color:var(--red)":"";h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/customers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td style='"+bs+"'>R"+bal.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='6' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/customers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "customers", "Customers", content)

@app.route("/<bid>/customers/<cid>/history")
def customer_history(bid, cid):
    customers = db.select("customers", {"id": cid})
    if not customers: return redirect(f"/{bid}/customers")
    cust = customers[0]
    invoices = db.select("invoices", {"business_id": bid})
    cust_inv = [i for i in invoices if i.get("customer_id") == cid]
    total = sum(float(i.get("total",0) or 0) for i in cust_inv)
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>R{float(i.get("total",0)):,.2f}</td><td><span class="badge badge-{"green" if i.get("status")=="paid" else "orange"}">{i.get("status","")}</span></td></tr>' for i in cust_inv])
    content = f'''<a href="/{bid}/customers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(cust.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(cust.get("phone",""))} | {js_safe(cust.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(cust_inv)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{float(cust.get("balance",0)):,.0f}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Invoice</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "customers", cust.get("name","Customer"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Supplier</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/suppliers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" suppliers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/suppliers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/suppliers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "suppliers", "Suppliers", content)

@app.route("/<bid>/suppliers/<sid>/history")
def supplier_history(bid, sid):
    suppliers = db.select("suppliers", {"id": sid})
    if not suppliers: return redirect(f"/{bid}/suppliers")
    supp = suppliers[0]
    expenses = db.select("expenses", {"business_id": bid})
    supp_exp = [e for e in expenses if js_safe(e.get("supplier","")).lower() == js_safe(supp.get("name","")).lower()]
    total = sum(float(e.get("amount",0) or 0) for e in supp_exp)
    rows = "".join([f'<tr><td>{str(e.get("created_at",""))[:10]}</td><td>{js_safe(e.get("description",""))}</td><td>R{float(e.get("amount",0)):,.2f}</td></tr>' for e in supp_exp])
    content = f'''<a href="/{bid}/suppliers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(supp.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(supp.get("phone",""))} | {js_safe(supp.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(supp_exp)}</div><div class="stat-label">Purchases</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total:,.0f}</div><div class="stat-label">Total Spent</div></div></div>
<div class="card"><table><thead><tr><th>Date</th><th>Description</th><th>Amount</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "suppliers", supp.get("name","Supplier"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/invoices")
def invoices_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/invoices/new" class="btn btn-green">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/invoices").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" invoices";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(i=>{{var b=i.status=="paid"?"badge-green":i.status=="overdue"?"badge-red":"badge-orange";h+="<tr><td>"+i.number+"</td><td>"+(i.date||"").substring(0,10)+"</td><td>"+i.customer_name+"</td><td>R"+i.total.toFixed(2)+"</td><td><span class='badge "+b+"'>"+i.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "invoices", "Invoices", content)

@app.route("/<bid>/invoices/new")
def new_invoice(bid): return create_doc_page(bid, "Invoice", "INV", "invoices")

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/quotes")
def quotes_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/quotes/new" class="btn btn-purple">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/quotes").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" quotes";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(q=>{{h+="<tr><td>"+q.number+"</td><td>"+(q.date||"").substring(0,10)+"</td><td>"+q.customer_name+"</td><td>R"+q.total.toFixed(2)+"</td><td><span class='badge badge-orange'>"+q.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "quotes", "Quotes", content)

@app.route("/<bid>/quotes/new")
def new_quote(bid): return create_doc_page(bid, "Quote", "QUO", "quotes")

def create_doc_page(bid, doc_type, prefix, table):
    active = "invoices" if doc_type == "Invoice" else "quotes"
    today = datetime.now().strftime('%Y-%m-%d')
    content = f'''<div class="card">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:15px"><div><label style="color:var(--muted);font-size:11px">Number</label><input type="text" id="docNum" value="{prefix}001"></div><div><label style="color:var(--muted);font-size:11px">Date</label><input type="date" id="docDate" value="{today}"></div><div><label style="color:var(--muted);font-size:11px">Customer</label><select id="custSel"><option value="">Select...</option></select></div></div>
<h3 style="margin-bottom:10px">Items</h3><input type="text" id="q" placeholder="Search to add..." oninput="searchStock()"><div id="searchResults" style="max-height:150px;overflow-y:auto;margin-bottom:10px"></div><div id="lines"></div>
<div style="text-align:right;font-size:22px;font-weight:700;color:var(--green);padding:10px 0">Total: R <span id="total">0.00</span></div>
<button class="btn btn-green" onclick="saveDoc()">Save</button></div>
<script>var stock=[],customers=[],lines=[],BID="{bid}",docType="{table}";
fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[]}});
fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{customers=d||[];var sel="<option value=''>Select...</option>";customers.forEach(c=>{{sel+="<option value='"+c.id+"'>"+c.name+"</option>"}});document.getElementById("custSel").innerHTML=sel}});
function searchStock(){{var q=document.getElementById("q").value.toLowerCase();if(q.length<2){{document.getElementById("searchResults").innerHTML="";return}}var h="";stock.forEach((s,i)=>{{if(s.desc.toLowerCase().indexOf(q)>=0||s.code.toLowerCase().indexOf(q)>=0)h+="<div class='grid-item' style='margin-bottom:5px' onclick='addLine("+i+")'>"+s.desc+" - R"+s.price.toFixed(2)+"</div>"}});document.getElementById("searchResults").innerHTML=h||"<div style='color:var(--muted)'>No matches</div>"}}
function addLine(i){{var s=stock[i];lines.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});document.getElementById("q").value="";document.getElementById("searchResults").innerHTML="";renderLines()}}
function renderLines(){{var h="<table><thead><tr><th>Item</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr></thead><tbody>";var tot=0;lines.forEach((l,i)=>{{var sub=l.price*l.qty;tot+=sub;h+="<tr><td>"+l.desc+"</td><td>R"+l.price.toFixed(2)+"</td><td><input type='number' value='"+l.qty+"' min='1' style='width:60px' onchange='updateQty("+i+",this.value)'></td><td>R"+sub.toFixed(2)+"</td><td><button class='btn btn-sm btn-red' onclick='lines.splice("+i+",1);renderLines()'>X</button></td></tr>"}});h+="</tbody></table>";document.getElementById("lines").innerHTML=lines.length?h:"<div style='color:var(--muted);text-align:center;padding:30px'>No items</div>";document.getElementById("total").innerHTML=tot.toFixed(2)}}
function updateQty(i,v){{lines[i].qty=parseInt(v)||1;renderLines()}}
function saveDoc(){{var sel=document.getElementById("custSel");var cn=sel.options[sel.selectedIndex]?sel.options[sel.selectedIndex].text:"Walk-in";if(lines.length==0)return alert("Add items");var tot=lines.reduce((a,l)=>a+l.price*l.qty,0);fetch("/api/"+BID+"/"+docType,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{number:document.getElementById("docNum").value,date:document.getElementById("docDate").value,customer_id:sel.value,customer_name:cn,items:lines,total:tot}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/"+docType}}else alert("Error")}})}}
renderLines();</script>'''
    return page(bid, active, f"New {doc_type}", content)
# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/expenses")
def expenses_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan</a><button class="btn btn-red" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>Date</th><th>Supplier</th><th>Description</th><th>Amount</th><th>VAT</th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title">Add Expense</div>
<input type="text" id="fsupplier" placeholder="Supplier"><input type="text" id="fdesc" placeholder="Description"><input type="number" id="famount" placeholder="Amount (incl VAT)" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="fvat" checked> Includes 15% VAT</label>
<div style="display:flex;gap:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/expenses").then(r=>r.json()).then(d=>{{items=d||[];var tot=items.reduce((a,e)=>a+e.amount,0);document.getElementById("msg").innerHTML=items.length+" expenses | R"+tot.toFixed(2);document.getElementById("msg").className="msg msg-ok";render()}})}}
function render(){{var h="";items.forEach(e=>{{h+="<tr><td>"+(e.date||"-")+"</td><td>"+e.supplier+"</td><td>"+e.description+"</td><td>R"+e.amount.toFixed(2)+"</td><td>R"+e.vat.toFixed(2)+"</td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("modal").classList.add("show")}}
function save(){{var amt=parseFloat(document.getElementById("famount").value)||0;var vat=document.getElementById("fvat").checked?amt*15/115:0;fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("fsupplier").value,description:document.getElementById("fdesc").value,amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "expenses", "Expenses", content)

@app.route("/<bid>/expenses/scan")
def scan_receipt(bid):
    content = f'''<a href="/{bid}/expenses" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<div class="card"><h3 style="margin-bottom:10px">Scan Receipt</h3><p style="color:var(--muted);margin-bottom:15px">AI extracts supplier, description, amount</p>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px"><button class="btn btn-orange" onclick="startCamera()">Camera</button><span style="color:var(--muted);align-self:center">or</span><input type="file" id="fileInput" accept="image/*" onchange="handleFile(this)"></div>
<video id="video" autoplay playsinline style="display:none;width:100%;max-width:350px;border-radius:10px;background:#000"></video>
<button id="captureBtn" class="btn btn-green" style="display:none;margin-top:10px" onclick="capture()">Snap</button>
<canvas id="canvas" style="display:none"></canvas><img id="preview" style="display:none;max-width:100%;border-radius:10px;margin-top:10px">
<div id="processing" class="msg msg-info" style="display:none;margin-top:10px">Reading...</div></div>
<div class="card" id="resultCard" style="display:none"><h3 style="margin-bottom:10px">Details</h3>
<input type="text" id="rSupplier" placeholder="Supplier"><input type="text" id="rDesc" placeholder="Description"><input type="number" id="rAmount" placeholder="Amount" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="rVat" checked> 15% VAT</label>
<button class="btn btn-green" onclick="saveExpense()">Save</button></div>
<script>var BID="{bid}",stream=null;
function startCamera(){{navigator.mediaDevices.getUserMedia({{video:{{facingMode:"environment"}}}}).then(s=>{{stream=s;document.getElementById("video").srcObject=s;document.getElementById("video").style.display="block";document.getElementById("captureBtn").style.display="inline-block"}}).catch(e=>alert("Camera: "+e.message))}}
function capture(){{var v=document.getElementById("video"),c=document.getElementById("canvas");c.width=v.videoWidth;c.height=v.videoHeight;c.getContext("2d").drawImage(v,0,0);var d=c.toDataURL("image/jpeg",0.8);if(stream)stream.getTracks().forEach(t=>t.stop());document.getElementById("video").style.display="none";document.getElementById("captureBtn").style.display="none";document.getElementById("preview").src=d;document.getElementById("preview").style.display="block";processAI(d)}}
function handleFile(input){{if(input.files&&input.files[0]){{var r=new FileReader();r.onload=e=>{{document.getElementById("preview").src=e.target.result;document.getElementById("preview").style.display="block";processAI(e.target.result)}};r.readAsDataURL(input.files[0])}}}}
function processAI(d){{document.getElementById("processing").style.display="block";document.getElementById("resultCard").style.display="none";fetch("/api/"+BID+"/scan-receipt",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{image:d}})}}).then(r=>r.json()).then(x=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";if(x.supplier)document.getElementById("rSupplier").value=x.supplier;if(x.description)document.getElementById("rDesc").value=x.description;if(x.amount)document.getElementById("rAmount").value=x.amount;if(x.error)alert(x.error)}}).catch(e=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";alert("Error: "+e)}})}}
function saveExpense(){{var amt=parseFloat(document.getElementById("rAmount").value)||0;var vat=document.getElementById("rVat").checked?amt*15/115:0;if(!document.getElementById("rSupplier").value)return alert("Supplier?");if(!amt)return alert("Amount?");fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("rSupplier").value,description:document.getElementById("rDesc").value||"Receipt",amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/expenses"}}else alert("Error")}})}}</script>'''
    return page(bid, "expenses", "Scan Receipt", content)

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/reports")
def reports_page(bid):
    content = '''<div class="report-grid">
<a href="/{0}/reports/sales" class="report-card"><h3>Sales</h3><p>Invoices & totals</p></a>
<a href="/{0}/reports/stock" class="report-card"><h3>Stock</h3><p>Levels & alerts</p></a>
<a href="/{0}/reports/customers" class="report-card"><h3>Customers</h3><p>Balances</p></a>
<a href="/{0}/reports/suppliers" class="report-card"><h3>Suppliers</h3><p>Contact list</p></a>
<a href="/{0}/reports/profit" class="report-card"><h3>P&L</h3><p>Income vs expenses</p></a>
<a href="/{0}/reports/vat" class="report-card"><h3>VAT</h3><p>In vs out</p></a>
<a href="/{0}/reports/tb" class="report-card"><h3>Trial Balance</h3><p>All accounts</p></a></div>'''.format(bid)
    return page(bid, "reports", "Reports", content)

@app.route("/<bid>/reports/sales")
def report_sales(bid):
    invoices = db.select("invoices", {"business_id": bid})
    total = sum(float(i.get("total",0) or 0) for i in invoices)
    paid = sum(float(i.get("total",0) or 0) for i in invoices if i.get("status")=="paid")
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>{js_safe(i.get("customer_name",""))}</td><td>R{float(i.get("total",0)):,.2f}</td></tr>' for i in invoices[:20]])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{paid:,.0f}</div><div class="stat-label">Paid</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total-paid:,.0f}</div><div class="stat-label">Outstanding</div></div></div>
<div class="card"><table><thead><tr><th>Inv</th><th>Date</th><th>Customer</th><th>Total</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Sales Report", content)

@app.route("/<bid>/reports/stock")
def report_stock(bid):
    stock = db.select("stock", {"business_id": bid})
    value = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    low = [s for s in stock if 0 < int(s.get("qty",0) or 0) <= 5]
    out = [s for s in stock if int(s.get("qty",0) or 0) <= 0]
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Items</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{value:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{len(low)}</div><div class="stat-label">Low</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">{len(out)}</div><div class="stat-label">Out</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Stock Report", content)

@app.route("/<bid>/reports/customers")
def report_customers(bid):
    customers = db.select("customers", {"business_id": bid})
    total_bal = sum(float(c.get("balance",0) or 0) for c in customers)
    owing = len([c for c in customers if float(c.get("balance",0) or 0) > 0])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total_bal:,.0f}</div><div class="stat-label">Total Owing</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{owing}</div><div class="stat-label">With Balance</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Customer Report", content)

@app.route("/<bid>/reports/suppliers")
def report_suppliers(bid):
    suppliers = db.select("suppliers", {"business_id": bid})
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Supplier Report", content)

@app.route("/<bid>/reports/profit")
def report_profit(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    income = sum(float(i.get("total",0) or 0) for i in invoices)
    expense = sum(float(e.get("amount",0) or 0) for e in expenses)
    profit = income - expense
    pc = "var(--green)" if profit >= 0 else "var(--red)"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{income:,.0f}</div><div class="stat-label">Income</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{expense:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:{pc}">R{profit:,.0f}</div><div class="stat-label">Profit</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Profit & Loss", content)

@app.route("/<bid>/reports/vat")
def report_vat(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    sales = sum(float(i.get("total",0) or 0) for i in invoices)
    vat_out = sales * 15 / 115
    vat_in = sum(float(e.get("vat",0) or 0) for e in expenses)
    vat_due = vat_out - vat_in
    dc = "var(--red)" if vat_due > 0 else "var(--green)"
    dl = "Pay SARS" if vat_due > 0 else "Refund"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--blue)">R{vat_out:,.0f}</div><div class="stat-label">Output</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{vat_in:,.0f}</div><div class="stat-label">Input</div></div><div class="stat"><div class="stat-value" style="color:{dc}">R{abs(vat_due):,.0f}</div><div class="stat-label">{dl}</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "VAT Report", content)

@app.route("/<bid>/reports/tb")
def report_tb(bid):
    journal = db.select("journal", {"business_id": bid})
    accounts = {}
    for j in journal:
        acc = j.get("account", "Unknown")
        if acc not in accounts: accounts[acc] = {"dr": 0, "cr": 0}
        accounts[acc]["dr"] += float(j.get("debit", 0) or 0)
        accounts[acc]["cr"] += float(j.get("credit", 0) or 0)
    total_dr = sum(a["dr"] for a in accounts.values())
    total_cr = sum(a["cr"] for a in accounts.values())
    rows = "".join([f'<tr><td>{acc}</td><td style="text-align:right">{"R"+str(int(v["dr"])) if v["dr"] else "-"}</td><td style="text-align:right">{"R"+str(int(v["cr"])) if v["cr"] else "-"}</td></tr>' for acc, v in sorted(accounts.items())])
    balanced = abs(total_dr - total_cr) < 0.01
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(accounts)}</div><div class="stat-label">Accounts</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{total_dr:,.0f}</div><div class="stat-label">Debits</div></div><div class="stat"><div class="stat-value" style="color:var(--purple)">R{total_cr:,.0f}</div><div class="stat-label">Credits</div></div><div class="stat"><div class="stat-value" style="color:{"var(--green)" if balanced else "var(--red)"}">{"OK" if balanced else "ERR"}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Account</th><th style="text-align:right">Debit</th><th style="text-align:right">Credit</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Trial Balance", content)

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/import")
def import_page(bid):
    content = f'''<div class="card"><h3 style="margin-bottom:15px">Import Data</h3><p style="color:var(--muted);margin-bottom:15px">Paste JSON with stock, customers, suppliers arrays</p>
<textarea id="jsonData" rows="10" placeholder='{{"stock":[...],"customers":[...],"suppliers":[...]}}'></textarea>
<button class="btn btn-blue" onclick="doImport()">Import</button><div id="result" style="margin-top:15px"></div></div>
<script>var BID="{bid}";function doImport(){{try{{var d=JSON.parse(document.getElementById("jsonData").value);fetch("/api/"+BID+"/import",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{document.getElementById("result").innerHTML="<div class='msg msg-ok'>Imported: "+x.stock+" stock, "+x.customers+" customers, "+x.suppliers+" suppliers</div>"}})}catch(e){{document.getElementById("result").innerHTML="<div class='msg msg-err'>Invalid JSON</div>"}}}}</script>'''
    return page(bid, "import", "Import", content)

# ═══════════════════════════════════════════════════════════════════════════════
# APIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/<bid>/stock", methods=["GET"])
def api_get_stock(bid):
    items = db.select("stock", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"desc":s.get("description",""),"category":s.get("category",""),"qty":int(s.get("qty",0) or 0),"cost":float(s.get("cost",0) or 0),"price":float(s.get("price",0) or 0)} for s in items])

@app.route("/api/<bid>/stock", methods=["POST"])
def api_post_stock(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"description":d.get("description",""),"category":d.get("category","General"),"qty":d.get("qty",0),"cost":d.get("cost",0),"price":d.get("price",0)}
    if d.get("id"):
        return jsonify({"success": db.update("stock", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("stock", rec)})

@app.route("/api/<bid>/customers", methods=["GET"])
def api_get_customers(bid):
    items = db.select("customers", {"business_id": bid})
    return jsonify([{"id":c["id"],"code":c.get("code",""),"name":c.get("name",""),"phone":c.get("phone",""),"email":c.get("email",""),"balance":float(c.get("balance",0) or 0)} for c in items])

@app.route("/api/<bid>/customers", methods=["POST"])
def api_post_customers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("customers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    rec["balance"] = 0
    return jsonify({"success": db.insert("customers", rec)})

@app.route("/api/<bid>/suppliers", methods=["GET"])
def api_get_suppliers(bid):
    items = db.select("suppliers", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"name":s.get("name",""),"phone":s.get("phone",""),"email":s.get("email","")} for s in items])

@app.route("/api/<bid>/suppliers", methods=["POST"])
def api_post_suppliers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("suppliers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("suppliers", rec)})

@app.route("/api/<bid>/invoices", methods=["GET"])
def api_get_invoices(bid):
    items = db.select("invoices", {"business_id": bid})
    return jsonify([{"id":i["id"],"number":i.get("number",""),"date":i.get("date",""),"customer_id":i.get("customer_id",""),"customer_name":i.get("customer_name",""),"total":float(i.get("total",0) or 0),"status":i.get("status","draft")} for i in items])

@app.route("/api/<bid>/invoices", methods=["POST"])
def api_post_invoices(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("invoices", rec)})

@app.route("/api/<bid>/quotes", methods=["GET"])
def api_get_quotes(bid):
    items = db.select("quotes", {"business_id": bid})
    return jsonify([{"id":q["id"],"number":q.get("number",""),"date":q.get("date",""),"customer_id":q.get("customer_id",""),"customer_name":q.get("customer_name",""),"total":float(q.get("total",0) or 0),"status":q.get("status","draft")} for q in items])

@app.route("/api/<bid>/quotes", methods=["POST"])
def api_post_quotes(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("quotes", rec)})

@app.route("/api/<bid>/expenses", methods=["GET"])
def api_get_expenses(bid):
    items = db.select("expenses", {"business_id": bid})
    return jsonify([{"id":e["id"],"date":e.get("date",e.get("created_at",""))[:10],"supplier":e.get("supplier",""),"description":e.get("description",""),"amount":float(e.get("amount",0) or 0),"vat":float(e.get("vat",0) or 0)} for e in items])

@app.route("/api/<bid>/expenses", methods=["POST"])
def api_post_expenses(bid):
    d = request.get_json()
    today = datetime.now().isoformat()[:10]
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"date":today,"supplier":d.get("supplier",""),"description":d.get("description",""),"amount":d.get("amount",0),"vat":d.get("vat",0),"category":d.get("category","Expenses")}
    if db.insert("expenses", rec):
        amt, vat = float(d.get("amount",0)), float(d.get("vat",0))
        net = amt - vat
        desc = f"Expense: {d.get('supplier','')} - {d.get('description','')}"
        post_journal(bid, today, desc, d.get("category","Expenses"), net, 0)
        post_journal(bid, today, desc, "VAT Input", vat, 0)
        post_journal(bid, today, desc, "Cash/Bank", 0, amt)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/api/<bid>/sale", methods=["POST"])
def api_sale(bid):
    d = request.get_json()
    items = d.get("items", [])
    total = d.get("total", 0)
    method = d.get("method", "cash")
    inv_count = len(db.select("invoices", {"business_id": bid}))
    cust_id = d.get("customer_id", "")
    cust_name = "Walk-in"
    if cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs: cust_name = custs[0].get("name", "Unknown")
    inv = {"id":str(uuid.uuid4()),"business_id":bid,"number":f"INV{inv_count+1:04d}","date":datetime.now().isoformat(),"customer_id":cust_id,"customer_name":cust_name,"items":json.dumps(items),"total":total,"status":"paid","payment_method":method}
    db.insert("invoices", inv)
    for item in items:
        sl = db.select("stock", {"id": item["id"]})
        if sl:
            new_qty = int(sl[0].get("qty", 0)) - int(item.get("qty", 1))
            db.update("stock", item["id"], {"qty": max(0, new_qty)})
    if method == "account" and cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs:
            new_bal = float(custs[0].get("balance", 0)) + total
            db.update("customers", cust_id, {"balance": new_bal})
    today = datetime.now().isoformat()[:10]
    vat = total * 15 / 115
    net = total - vat
    desc = f"Sale {inv['number']} - {cust_name}"
    if method == "account":
        post_journal(bid, today, desc, "Debtors", total, 0)
    else:
        post_journal(bid, today, desc, "Cash/Bank", total, 0)
    post_journal(bid, today, desc, "Sales", 0, net)
    post_journal(bid, today, desc, "VAT Output", 0, vat)
    return jsonify({"success": True})

@app.route("/api/<bid>/scan-receipt", methods=["POST"])
def api_scan_receipt(bid):
    try:
        d = request.get_json()
        image_data = d.get("image", "")
        if not image_data: return jsonify({"error": "No image"})
        if "," in image_data: image_data = image_data.split(",")[1]
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key: return jsonify({"error": "No API key", "supplier": "", "description": "", "amount": ""})
        response = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}, json={"model": "claude-sonnet-4-20250514", "max_tokens": 500, "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}}, {"type": "text", "text": "Extract: 1) Supplier name, 2) Brief description, 3) Total in Rands. Reply ONLY JSON: {\"supplier\": \"name\", \"description\": \"what\", \"amount\": 123.45}"}]}]}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            text = result.get("content", [{}])[0].get("text", "{}")
            match = re.search(r'\{[^}]+\}', text)
            if match:
                data = json.loads(match.group())
                return jsonify({"supplier": data.get("supplier", ""), "description": data.get("description", ""), "amount": float(data.get("amount", 0))})
        return jsonify({"error": "Could not parse", "supplier": "", "description": "", "amount": ""})
    except Exception as e:
        return jsonify({"error": str(e), "supplier": "", "description": "", "amount": ""})

@app.route("/api/<bid>/import", methods=["POST"])
def api_import(bid):
    try:
        data = request.get_json()
        source = data.get("fulltech", data.get("hardware", data))
        if not source: source = data
        sc, cc, spc = 0, 0, 0
        for item in source.get("stock", []):
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"description":str(item.get("description",item.get("name","")))[:200],"category":str(item.get("category","General"))[:50],"qty":int(item.get("qty",0) or 0),"cost":float(item.get("cost",0) or 0),"price":float(item.get("price",item.get("sell",0)) or 0)}
            if db.insert("stock", rec): sc += 1
        for item in source.get("customers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100],"balance":float(item.get("balance",0) or 0)}
            if db.insert("customers", rec): cc += 1
        for item in source.get("suppliers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100]}
            if db.insert("suppliers", rec): spc += 1
        return jsonify({"success":True,"stock":sc,"customers":cc,"suppliers":spc})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "10"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
"""
Click AI v10 - Lit Up Edition
Sticky glowing header, no duplicate titles, clean UI
"""

from flask import Flask, jsonify, request, redirect
import json, os, re, uuid, requests
from datetime import datetime

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
            for k, v in filters.items(): url += f"&{k}=eq.{v}"
        try:
            r = requests.get(url, headers=self.headers, timeout=60)
            return r.json() if r.status_code == 200 else []
        except: return []
    
    def insert(self, table, data):
        try:
            r = requests.post(f"{self.url}/rest/v1/{table}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 201]
        except: return False
    
    def update(self, table, id, data):
        try:
            r = requests.patch(f"{self.url}/rest/v1/{table}?id=eq.{id}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 204]
        except: return False

db = DB(SUPABASE_URL, SUPABASE_KEY)

def post_journal(bid, date, desc, account, debit, credit):
    return db.insert("journal", {"id": str(uuid.uuid4()), "business_id": bid, "date": date, "description": desc, "account": account, "debit": debit, "credit": credit})

CSS = """<style>
:root{--bg:#06060a;--card:#0d0d14;--border:#1a1a2e;--text:#e0e0e0;--muted:#666;--blue:#3b82f6;--purple:#8b5cf6;--green:#10b981;--red:#ef4444;--orange:#f59e0b;--glow:rgba(139,92,246,0.5)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{position:sticky;top:0;z-index:100;background:linear-gradient(180deg,#0d0d14,rgba(13,13,20,0.95));border-bottom:1px solid var(--border);padding:0 15px;height:52px;display:flex;align-items:center;gap:6px;backdrop-filter:blur(10px);overflow-x:auto}
.header::-webkit-scrollbar{height:0}
.logo{font-size:18px;font-weight:800;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-decoration:none;margin-right:10px;white-space:nowrap;animation:pulse 3s ease-in-out infinite}
@keyframes pulse{0%,100%{filter:brightness(1)}50%{filter:brightness(1.3)}}
.nav-item{padding:6px 12px;border-radius:6px;text-decoration:none;color:var(--muted);font-size:12px;font-weight:500;white-space:nowrap;transition:all 0.2s;border:1px solid transparent}
.nav-item:hover{color:var(--text);background:rgba(255,255,255,0.05)}
.nav-item.active{color:white;background:linear-gradient(135deg,rgba(139,92,246,0.3),rgba(59,130,246,0.3));border-color:rgba(139,92,246,0.5);box-shadow:0 0 15px rgba(139,92,246,0.2)}
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.btn{padding:10px 18px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:14px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:all 0.2s}
.btn-blue{background:var(--blue);color:white}.btn-green{background:var(--green);color:white}.btn-red{background:var(--red);color:white}.btn-purple{background:var(--purple);color:white}.btn-orange{background:var(--orange);color:black}.btn-ghost{background:rgba(255,255,255,0.05);color:var(--text);border:1px solid var(--border)}
.btn:hover{opacity:0.9;transform:translateY(-1px)}.btn-sm{padding:6px 12px;font-size:12px}
input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;margin-bottom:12px}
input:focus,select:focus{outline:none;border-color:var(--purple)}
table{width:100%;border-collapse:collapse}th,td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}th{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;text-align:center}
.stat-value{font-size:26px;font-weight:700;color:var(--blue)}.stat-label{color:var(--muted);font-size:11px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;max-height:55vh;overflow-y:auto;padding:4px}
.grid-item{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px;cursor:pointer;transition:all 0.2s}
.grid-item:hover{border-color:var(--purple);transform:translateY(-2px)}
.grid-item-name{font-weight:600;font-size:12px;margin-bottom:3px}.grid-item-price{color:var(--green);font-weight:700;font-size:13px}.grid-item-stock{color:var(--muted);font-size:10px}
.cart{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.cart-total{font-size:26px;font-weight:800;color:var(--green);text-align:right;padding:12px 0}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);align-items:center;justify-content:center;z-index:200}
.modal.show{display:flex}.modal-box{background:var(--card);border-radius:16px;padding:25px;width:90%;max-width:500px;max-height:90vh;overflow-y:auto}
.modal-title{font-size:18px;font-weight:700;margin-bottom:20px}
.msg{padding:12px 16px;border-radius:8px;margin-bottom:15px;font-size:13px}
.msg-info{background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);color:var(--blue)}
.msg-ok{background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);color:var(--green)}
.msg-err{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--red)}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:rgba(16,185,129,0.2);color:var(--green)}.badge-orange{background:rgba(245,158,11,0.2);color:var(--orange)}.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.report-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:15px}
.report-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;text-decoration:none;color:var(--text);transition:all 0.2s}
.report-card:hover{border-color:var(--purple);transform:translateY(-3px);box-shadow:0 10px 30px rgba(0,0,0,0.3)}
.report-card h3{margin-bottom:6px}.report-card p{color:var(--muted);font-size:12px}
@media(max-width:768px){.header{padding:0 10px;gap:4px}.logo{font-size:16px;margin-right:8px}.nav-item{padding:5px 8px;font-size:11px}.container{padding:15px}.pos-layout{grid-template-columns:1fr!important}.stats{grid-template-columns:repeat(2,1fr)}}
</style>"""

def header(bid, active=""):
    items = [("home","Home",f"/{bid}"),("pos","POS",f"/{bid}/pos"),("stock","Stock",f"/{bid}/stock"),("customers","Cust",f"/{bid}/customers"),("suppliers","Supp",f"/{bid}/suppliers"),("invoices","Inv",f"/{bid}/invoices"),("quotes","Quote",f"/{bid}/quotes"),("expenses","Exp",f"/{bid}/expenses"),("reports","Reports",f"/{bid}/reports"),("import","Import",f"/{bid}/import")]
    nav = "".join([f'<a href="{u}" class="nav-item{"  active" if k==active else ""}">{l}</a>' for k,l,u in items])
    return f'<div class="header"><a href="/{bid}" class="logo">Click AI</a>{nav}</div>'

def page(bid, active, title, content):
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{CSS}</head><body>{header(bid,active)}<div class="container">{content}</div></body></html>'

@app.route("/")
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}
<style>.landing{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:20px}}
.landing-logo{{font-size:60px;font-weight:900;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:glow 2s ease-in-out infinite}}
@keyframes glow{{0%,100%{{filter:drop-shadow(0 0 20px var(--glow))}}50%{{filter:drop-shadow(0 0 40px var(--glow))}}}}</style>
</head><body><div class="landing"><div class="landing-logo">Click AI</div><p style="color:var(--muted);margin:20px 0 40px">Business Management</p><a href="/demo" class="btn btn-purple" style="font-size:18px;padding:15px 40px">Enter</a></div></body></html>'''

@app.route("/demo")
def demo(): return redirect("/5742fb2c-5fd8-4d44-9ddb-b73a3dd51da3")

@app.route("/<bid>")
def dashboard(bid):
    stock = db.select("stock", {"business_id": bid})
    customers = db.select("customers", {"business_id": bid})
    suppliers = db.select("suppliers", {"business_id": bid})
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    stock_val = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    inv_total = sum(float(i.get("total",0) or 0) for i in invoices)
    exp_total = sum(float(e.get("amount",0) or 0) for e in expenses)
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Stock</div></div><div class="stat"><div class="stat-value">R{stock_val:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total:,.0f}</div><div class="stat-label">Sales</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{exp_total:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total-exp_total:,.0f}</div><div class="stat-label">Profit</div></div><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div></div>
<div class="card"><h3 style="margin-bottom:15px">Quick Actions</h3><div style="display:flex;flex-wrap:wrap;gap:10px"><a href="/{bid}/pos" class="btn btn-blue">New Sale</a><a href="/{bid}/invoices/new" class="btn btn-green">New Invoice</a><a href="/{bid}/quotes/new" class="btn btn-purple">New Quote</a><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan Receipt</a></div></div>'''
    return page(bid, "home", "Dashboard", content)

@app.route("/<bid>/pos")
def pos(bid):
    content = f'''<div id="msg" class="msg msg-info">Loading...</div>
<div class="pos-layout" style="display:grid;grid-template-columns:1fr 320px;gap:15px">
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div class="grid" id="items"></div></div>
<div class="cart"><div style="display:flex;justify-content:space-between;margin-bottom:10px"><h3>Cart</h3><button class="btn btn-sm btn-ghost" onclick="cart=[];renderCart()">Clear</button></div>
<select id="custSel" style="margin-bottom:10px"><option value="">Walk-in</option></select>
<div id="cartList" style="min-height:120px"></div><div class="cart-total">R <span id="tot">0.00</span></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><button class="btn btn-green" onclick="pay('cash')">Cash</button><button class="btn btn-blue" onclick="pay('card')">Card</button></div>
<button class="btn btn-purple" style="width:100%;margin-top:8px" onclick="pay('account')">Account</button></div></div>
<script>var stock=[],cart=[],customers=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];return fetch("/api/"+BID+"/customers")}}).then(r=>r.json()).then(c=>{{customers=c||[];var sel="<option value=''>Walk-in</option>";customers.forEach(cu=>{{sel+="<option value='"+cu.id+"'>"+cu.name+"</option>"}});document.getElementById("custSel").innerHTML=sel;document.getElementById("msg").innerHTML="Ready - "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="",c=0;for(var i=0;i<stock.length&&c<80;i++){{var s=stock[i];if(s.qty<=0)continue;if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;h+="<div class='grid-item' onclick='add("+i+")'><div class='grid-item-name'>"+s.desc+"</div><div class='grid-item-price'>R"+s.price.toFixed(2)+"</div><div class='grid-item-stock'>"+s.qty+" left</div></div>";c++}}document.getElementById("items").innerHTML=h||"<div style='padding:30px;text-align:center;color:var(--muted)'>No items</div>"}}
function add(i){{var s=stock[i];var f=cart.findIndex(c=>c.id==s.id);if(f>=0)cart[f].qty++;else cart.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});renderCart()}}
function renderCart(){{if(cart.length==0){{document.getElementById("cartList").innerHTML="<div style='text-align:center;color:var(--muted);padding:30px'>Empty</div>";document.getElementById("tot").innerHTML="0.00";return}}var h="",tot=0;cart.forEach((c,i)=>{{var sub=c.price*c.qty;tot+=sub;h+="<div class='cart-item'><div><div style='font-weight:600;font-size:13px'>"+c.desc+"</div><div style='color:var(--muted);font-size:11px'>R"+c.price.toFixed(2)+" x "+c.qty+"</div></div><div style='display:flex;align-items:center;gap:8px'><span style='font-weight:600'>R"+sub.toFixed(2)+"</span><button class='btn btn-sm btn-red' onclick='cart.splice("+i+",1);renderCart()'>X</button></div></div>"}});document.getElementById("cartList").innerHTML=h;document.getElementById("tot").innerHTML=tot.toFixed(2)}}
function pay(method){{if(cart.length==0)return alert("Cart empty");var tot=cart.reduce((a,c)=>a+c.price*c.qty,0);fetch("/api/"+BID+"/sale",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{items:cart,total:tot,method:method,customer_id:document.getElementById("custSel").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Done! R"+tot.toFixed(2));cart=[];renderCart();load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "pos", "POS", content)
# ═══════════════════════════════════════════════════════════════════════════════
# STOCK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/stock")
def stock_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/import" class="btn btn-orange">Import</a><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Description</th><th>Cat</th><th>Qty</th><th>Cost</th><th>Price</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Item</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fcat" placeholder="Category" value="General"></div>
<input type="text" id="fdesc" placeholder="Description">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px"><input type="number" id="fqty" placeholder="Qty" value="0"><input type="number" id="fcost" placeholder="Cost" step="0.01"><input type="number" id="fprice" placeholder="Price" step="0.01"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var stock=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];document.getElementById("msg").innerHTML="Loaded "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";stock.forEach((s,i)=>{{if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)return;var qs=s.qty<=0?"color:var(--red)":s.qty<=5?"color:var(--orange)":"";h+="<tr><td>"+s.code+"</td><td>"+s.desc+"</td><td>"+s.category+"</td><td style='"+qs+"'>"+s.qty+"</td><td>R"+s.cost.toFixed(2)+"</td><td>R"+s.price.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='7' style='text-align:center;color:var(--muted);padding:30px'>No items</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fcat").value="General";document.getElementById("fdesc").value="";document.getElementById("fqty").value="0";document.getElementById("fcost").value="";document.getElementById("fprice").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var s=stock[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=s.id;document.getElementById("fcode").value=s.code||"";document.getElementById("fcat").value=s.category||"General";document.getElementById("fdesc").value=s.desc||"";document.getElementById("fqty").value=s.qty||0;document.getElementById("fcost").value=s.cost||0;document.getElementById("fprice").value=s.price||0;document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/stock",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,category:document.getElementById("fcat").value,description:document.getElementById("fdesc").value,qty:parseInt(document.getElementById("fqty").value)||0,cost:parseFloat(document.getElementById("fcost").value)||0,price:parseFloat(document.getElementById("fprice").value)||0}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "stock", "Stock", content)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/customers")
def customers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Customer</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" customers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;var bal=c.balance||0;var bs=bal>0?"color:var(--red)":"";h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/customers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td style='"+bs+"'>R"+bal.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='6' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/customers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "customers", "Customers", content)

@app.route("/<bid>/customers/<cid>/history")
def customer_history(bid, cid):
    customers = db.select("customers", {"id": cid})
    if not customers: return redirect(f"/{bid}/customers")
    cust = customers[0]
    invoices = db.select("invoices", {"business_id": bid})
    cust_inv = [i for i in invoices if i.get("customer_id") == cid]
    total = sum(float(i.get("total",0) or 0) for i in cust_inv)
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>R{float(i.get("total",0)):,.2f}</td><td><span class="badge badge-{"green" if i.get("status")=="paid" else "orange"}">{i.get("status","")}</span></td></tr>' for i in cust_inv])
    content = f'''<a href="/{bid}/customers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(cust.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(cust.get("phone",""))} | {js_safe(cust.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(cust_inv)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{float(cust.get("balance",0)):,.0f}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Invoice</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "customers", cust.get("name","Customer"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Supplier</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/suppliers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" suppliers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/suppliers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/suppliers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "suppliers", "Suppliers", content)

@app.route("/<bid>/suppliers/<sid>/history")
def supplier_history(bid, sid):
    suppliers = db.select("suppliers", {"id": sid})
    if not suppliers: return redirect(f"/{bid}/suppliers")
    supp = suppliers[0]
    expenses = db.select("expenses", {"business_id": bid})
    supp_exp = [e for e in expenses if js_safe(e.get("supplier","")).lower() == js_safe(supp.get("name","")).lower()]
    total = sum(float(e.get("amount",0) or 0) for e in supp_exp)
    rows = "".join([f'<tr><td>{str(e.get("created_at",""))[:10]}</td><td>{js_safe(e.get("description",""))}</td><td>R{float(e.get("amount",0)):,.2f}</td></tr>' for e in supp_exp])
    content = f'''<a href="/{bid}/suppliers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(supp.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(supp.get("phone",""))} | {js_safe(supp.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(supp_exp)}</div><div class="stat-label">Purchases</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total:,.0f}</div><div class="stat-label">Total Spent</div></div></div>
<div class="card"><table><thead><tr><th>Date</th><th>Description</th><th>Amount</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "suppliers", supp.get("name","Supplier"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/invoices")
def invoices_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/invoices/new" class="btn btn-green">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/invoices").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" invoices";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(i=>{{var b=i.status=="paid"?"badge-green":i.status=="overdue"?"badge-red":"badge-orange";h+="<tr><td>"+i.number+"</td><td>"+(i.date||"").substring(0,10)+"</td><td>"+i.customer_name+"</td><td>R"+i.total.toFixed(2)+"</td><td><span class='badge "+b+"'>"+i.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "invoices", "Invoices", content)

@app.route("/<bid>/invoices/new")
def new_invoice(bid): return create_doc_page(bid, "Invoice", "INV", "invoices")

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/quotes")
def quotes_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/quotes/new" class="btn btn-purple">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/quotes").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" quotes";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(q=>{{h+="<tr><td>"+q.number+"</td><td>"+(q.date||"").substring(0,10)+"</td><td>"+q.customer_name+"</td><td>R"+q.total.toFixed(2)+"</td><td><span class='badge badge-orange'>"+q.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "quotes", "Quotes", content)

@app.route("/<bid>/quotes/new")
def new_quote(bid): return create_doc_page(bid, "Quote", "QUO", "quotes")

def create_doc_page(bid, doc_type, prefix, table):
    active = "invoices" if doc_type == "Invoice" else "quotes"
    today = datetime.now().strftime('%Y-%m-%d')
    content = f'''<div class="card">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:15px"><div><label style="color:var(--muted);font-size:11px">Number</label><input type="text" id="docNum" value="{prefix}001"></div><div><label style="color:var(--muted);font-size:11px">Date</label><input type="date" id="docDate" value="{today}"></div><div><label style="color:var(--muted);font-size:11px">Customer</label><select id="custSel"><option value="">Select...</option></select></div></div>
<h3 style="margin-bottom:10px">Items</h3><input type="text" id="q" placeholder="Search to add..." oninput="searchStock()"><div id="searchResults" style="max-height:150px;overflow-y:auto;margin-bottom:10px"></div><div id="lines"></div>
<div style="text-align:right;font-size:22px;font-weight:700;color:var(--green);padding:10px 0">Total: R <span id="total">0.00</span></div>
<button class="btn btn-green" onclick="saveDoc()">Save</button></div>
<script>var stock=[],customers=[],lines=[],BID="{bid}",docType="{table}";
fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[]}});
fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{customers=d||[];var sel="<option value=''>Select...</option>";customers.forEach(c=>{{sel+="<option value='"+c.id+"'>"+c.name+"</option>"}});document.getElementById("custSel").innerHTML=sel}});
function searchStock(){{var q=document.getElementById("q").value.toLowerCase();if(q.length<2){{document.getElementById("searchResults").innerHTML="";return}}var h="";stock.forEach((s,i)=>{{if(s.desc.toLowerCase().indexOf(q)>=0||s.code.toLowerCase().indexOf(q)>=0)h+="<div class='grid-item' style='margin-bottom:5px' onclick='addLine("+i+")'>"+s.desc+" - R"+s.price.toFixed(2)+"</div>"}});document.getElementById("searchResults").innerHTML=h||"<div style='color:var(--muted)'>No matches</div>"}}
function addLine(i){{var s=stock[i];lines.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});document.getElementById("q").value="";document.getElementById("searchResults").innerHTML="";renderLines()}}
function renderLines(){{var h="<table><thead><tr><th>Item</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr></thead><tbody>";var tot=0;lines.forEach((l,i)=>{{var sub=l.price*l.qty;tot+=sub;h+="<tr><td>"+l.desc+"</td><td>R"+l.price.toFixed(2)+"</td><td><input type='number' value='"+l.qty+"' min='1' style='width:60px' onchange='updateQty("+i+",this.value)'></td><td>R"+sub.toFixed(2)+"</td><td><button class='btn btn-sm btn-red' onclick='lines.splice("+i+",1);renderLines()'>X</button></td></tr>"}});h+="</tbody></table>";document.getElementById("lines").innerHTML=lines.length?h:"<div style='color:var(--muted);text-align:center;padding:30px'>No items</div>";document.getElementById("total").innerHTML=tot.toFixed(2)}}
function updateQty(i,v){{lines[i].qty=parseInt(v)||1;renderLines()}}
function saveDoc(){{var sel=document.getElementById("custSel");var cn=sel.options[sel.selectedIndex]?sel.options[sel.selectedIndex].text:"Walk-in";if(lines.length==0)return alert("Add items");var tot=lines.reduce((a,l)=>a+l.price*l.qty,0);fetch("/api/"+BID+"/"+docType,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{number:document.getElementById("docNum").value,date:document.getElementById("docDate").value,customer_id:sel.value,customer_name:cn,items:lines,total:tot}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/"+docType}}else alert("Error")}})}}
renderLines();</script>'''
    return page(bid, active, f"New {doc_type}", content)
# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/expenses")
def expenses_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan</a><button class="btn btn-red" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>Date</th><th>Supplier</th><th>Description</th><th>Amount</th><th>VAT</th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title">Add Expense</div>
<input type="text" id="fsupplier" placeholder="Supplier"><input type="text" id="fdesc" placeholder="Description"><input type="number" id="famount" placeholder="Amount (incl VAT)" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="fvat" checked> Includes 15% VAT</label>
<div style="display:flex;gap:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/expenses").then(r=>r.json()).then(d=>{{items=d||[];var tot=items.reduce((a,e)=>a+e.amount,0);document.getElementById("msg").innerHTML=items.length+" expenses | R"+tot.toFixed(2);document.getElementById("msg").className="msg msg-ok";render()}})}}
function render(){{var h="";items.forEach(e=>{{h+="<tr><td>"+(e.date||"-")+"</td><td>"+e.supplier+"</td><td>"+e.description+"</td><td>R"+e.amount.toFixed(2)+"</td><td>R"+e.vat.toFixed(2)+"</td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("modal").classList.add("show")}}
function save(){{var amt=parseFloat(document.getElementById("famount").value)||0;var vat=document.getElementById("fvat").checked?amt*15/115:0;fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("fsupplier").value,description:document.getElementById("fdesc").value,amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "expenses", "Expenses", content)

@app.route("/<bid>/expenses/scan")
def scan_receipt(bid):
    content = f'''<a href="/{bid}/expenses" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<div class="card"><h3 style="margin-bottom:10px">Scan Receipt</h3><p style="color:var(--muted);margin-bottom:15px">AI extracts supplier, description, amount</p>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px"><button class="btn btn-orange" onclick="startCamera()">Camera</button><span style="color:var(--muted);align-self:center">or</span><input type="file" id="fileInput" accept="image/*" onchange="handleFile(this)"></div>
<video id="video" autoplay playsinline style="display:none;width:100%;max-width:350px;border-radius:10px;background:#000"></video>
<button id="captureBtn" class="btn btn-green" style="display:none;margin-top:10px" onclick="capture()">Snap</button>
<canvas id="canvas" style="display:none"></canvas><img id="preview" style="display:none;max-width:100%;border-radius:10px;margin-top:10px">
<div id="processing" class="msg msg-info" style="display:none;margin-top:10px">Reading...</div></div>
<div class="card" id="resultCard" style="display:none"><h3 style="margin-bottom:10px">Details</h3>
<input type="text" id="rSupplier" placeholder="Supplier"><input type="text" id="rDesc" placeholder="Description"><input type="number" id="rAmount" placeholder="Amount" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="rVat" checked> 15% VAT</label>
<button class="btn btn-green" onclick="saveExpense()">Save</button></div>
<script>var BID="{bid}",stream=null;
function startCamera(){{navigator.mediaDevices.getUserMedia({{video:{{facingMode:"environment"}}}}).then(s=>{{stream=s;document.getElementById("video").srcObject=s;document.getElementById("video").style.display="block";document.getElementById("captureBtn").style.display="inline-block"}}).catch(e=>alert("Camera: "+e.message))}}
function capture(){{var v=document.getElementById("video"),c=document.getElementById("canvas");c.width=v.videoWidth;c.height=v.videoHeight;c.getContext("2d").drawImage(v,0,0);var d=c.toDataURL("image/jpeg",0.8);if(stream)stream.getTracks().forEach(t=>t.stop());document.getElementById("video").style.display="none";document.getElementById("captureBtn").style.display="none";document.getElementById("preview").src=d;document.getElementById("preview").style.display="block";processAI(d)}}
function handleFile(input){{if(input.files&&input.files[0]){{var r=new FileReader();r.onload=e=>{{document.getElementById("preview").src=e.target.result;document.getElementById("preview").style.display="block";processAI(e.target.result)}};r.readAsDataURL(input.files[0])}}}}
function processAI(d){{document.getElementById("processing").style.display="block";document.getElementById("resultCard").style.display="none";fetch("/api/"+BID+"/scan-receipt",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{image:d}})}}).then(r=>r.json()).then(x=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";if(x.supplier)document.getElementById("rSupplier").value=x.supplier;if(x.description)document.getElementById("rDesc").value=x.description;if(x.amount)document.getElementById("rAmount").value=x.amount;if(x.error)alert(x.error)}}).catch(e=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";alert("Error: "+e)}})}}
function saveExpense(){{var amt=parseFloat(document.getElementById("rAmount").value)||0;var vat=document.getElementById("rVat").checked?amt*15/115:0;if(!document.getElementById("rSupplier").value)return alert("Supplier?");if(!amt)return alert("Amount?");fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("rSupplier").value,description:document.getElementById("rDesc").value||"Receipt",amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/expenses"}}else alert("Error")}})}}</script>'''
    return page(bid, "expenses", "Scan Receipt", content)

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/reports")
def reports_page(bid):
    content = '''<div class="report-grid">
<a href="/{0}/reports/sales" class="report-card"><h3>Sales</h3><p>Invoices & totals</p></a>
<a href="/{0}/reports/stock" class="report-card"><h3>Stock</h3><p>Levels & alerts</p></a>
<a href="/{0}/reports/customers" class="report-card"><h3>Customers</h3><p>Balances</p></a>
<a href="/{0}/reports/suppliers" class="report-card"><h3>Suppliers</h3><p>Contact list</p></a>
<a href="/{0}/reports/profit" class="report-card"><h3>P&L</h3><p>Income vs expenses</p></a>
<a href="/{0}/reports/vat" class="report-card"><h3>VAT</h3><p>In vs out</p></a>
<a href="/{0}/reports/tb" class="report-card"><h3>Trial Balance</h3><p>All accounts</p></a></div>'''.format(bid)
    return page(bid, "reports", "Reports", content)

@app.route("/<bid>/reports/sales")
def report_sales(bid):
    invoices = db.select("invoices", {"business_id": bid})
    total = sum(float(i.get("total",0) or 0) for i in invoices)
    paid = sum(float(i.get("total",0) or 0) for i in invoices if i.get("status")=="paid")
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>{js_safe(i.get("customer_name",""))}</td><td>R{float(i.get("total",0)):,.2f}</td></tr>' for i in invoices[:20]])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{paid:,.0f}</div><div class="stat-label">Paid</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total-paid:,.0f}</div><div class="stat-label">Outstanding</div></div></div>
<div class="card"><table><thead><tr><th>Inv</th><th>Date</th><th>Customer</th><th>Total</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Sales Report", content)

@app.route("/<bid>/reports/stock")
def report_stock(bid):
    stock = db.select("stock", {"business_id": bid})
    value = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    low = [s for s in stock if 0 < int(s.get("qty",0) or 0) <= 5]
    out = [s for s in stock if int(s.get("qty",0) or 0) <= 0]
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Items</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{value:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{len(low)}</div><div class="stat-label">Low</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">{len(out)}</div><div class="stat-label">Out</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Stock Report", content)

@app.route("/<bid>/reports/customers")
def report_customers(bid):
    customers = db.select("customers", {"business_id": bid})
    total_bal = sum(float(c.get("balance",0) or 0) for c in customers)
    owing = len([c for c in customers if float(c.get("balance",0) or 0) > 0])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total_bal:,.0f}</div><div class="stat-label">Total Owing</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{owing}</div><div class="stat-label">With Balance</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Customer Report", content)

@app.route("/<bid>/reports/suppliers")
def report_suppliers(bid):
    suppliers = db.select("suppliers", {"business_id": bid})
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Supplier Report", content)

@app.route("/<bid>/reports/profit")
def report_profit(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    income = sum(float(i.get("total",0) or 0) for i in invoices)
    expense = sum(float(e.get("amount",0) or 0) for e in expenses)
    profit = income - expense
    pc = "var(--green)" if profit >= 0 else "var(--red)"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{income:,.0f}</div><div class="stat-label">Income</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{expense:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:{pc}">R{profit:,.0f}</div><div class="stat-label">Profit</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Profit & Loss", content)

@app.route("/<bid>/reports/vat")
def report_vat(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    sales = sum(float(i.get("total",0) or 0) for i in invoices)
    vat_out = sales * 15 / 115
    vat_in = sum(float(e.get("vat",0) or 0) for e in expenses)
    vat_due = vat_out - vat_in
    dc = "var(--red)" if vat_due > 0 else "var(--green)"
    dl = "Pay SARS" if vat_due > 0 else "Refund"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--blue)">R{vat_out:,.0f}</div><div class="stat-label">Output</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{vat_in:,.0f}</div><div class="stat-label">Input</div></div><div class="stat"><div class="stat-value" style="color:{dc}">R{abs(vat_due):,.0f}</div><div class="stat-label">{dl}</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "VAT Report", content)

@app.route("/<bid>/reports/tb")
def report_tb(bid):
    journal = db.select("journal", {"business_id": bid})
    accounts = {}
    for j in journal:
        acc = j.get("account", "Unknown")
        if acc not in accounts: accounts[acc] = {"dr": 0, "cr": 0}
        accounts[acc]["dr"] += float(j.get("debit", 0) or 0)
        accounts[acc]["cr"] += float(j.get("credit", 0) or 0)
    total_dr = sum(a["dr"] for a in accounts.values())
    total_cr = sum(a["cr"] for a in accounts.values())
    rows = "".join([f'<tr><td>{acc}</td><td style="text-align:right">{"R"+str(int(v["dr"])) if v["dr"] else "-"}</td><td style="text-align:right">{"R"+str(int(v["cr"])) if v["cr"] else "-"}</td></tr>' for acc, v in sorted(accounts.items())])
    balanced = abs(total_dr - total_cr) < 0.01
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(accounts)}</div><div class="stat-label">Accounts</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{total_dr:,.0f}</div><div class="stat-label">Debits</div></div><div class="stat"><div class="stat-value" style="color:var(--purple)">R{total_cr:,.0f}</div><div class="stat-label">Credits</div></div><div class="stat"><div class="stat-value" style="color:{"var(--green)" if balanced else "var(--red)"}">{"OK" if balanced else "ERR"}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Account</th><th style="text-align:right">Debit</th><th style="text-align:right">Credit</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Trial Balance", content)

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/import")
def import_page(bid):
    content = f'''<div class="card"><h3 style="margin-bottom:15px">Import Data</h3><p style="color:var(--muted);margin-bottom:15px">Paste JSON with stock, customers, suppliers arrays</p>
<textarea id="jsonData" rows="10" placeholder='{{"stock":[...],"customers":[...],"suppliers":[...]}}'></textarea>
<button class="btn btn-blue" onclick="doImport()">Import</button><div id="result" style="margin-top:15px"></div></div>
<script>var BID="{bid}";function doImport(){{try{{var d=JSON.parse(document.getElementById("jsonData").value);fetch("/api/"+BID+"/import",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{document.getElementById("result").innerHTML="<div class='msg msg-ok'>Imported: "+x.stock+" stock, "+x.customers+" customers, "+x.suppliers+" suppliers</div>"}})}catch(e){{document.getElementById("result").innerHTML="<div class='msg msg-err'>Invalid JSON</div>"}}}}</script>'''
    return page(bid, "import", "Import", content)

# ═══════════════════════════════════════════════════════════════════════════════
# APIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/<bid>/stock", methods=["GET"])
def api_get_stock(bid):
    items = db.select("stock", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"desc":s.get("description",""),"category":s.get("category",""),"qty":int(s.get("qty",0) or 0),"cost":float(s.get("cost",0) or 0),"price":float(s.get("price",0) or 0)} for s in items])

@app.route("/api/<bid>/stock", methods=["POST"])
def api_post_stock(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"description":d.get("description",""),"category":d.get("category","General"),"qty":d.get("qty",0),"cost":d.get("cost",0),"price":d.get("price",0)}
    if d.get("id"):
        return jsonify({"success": db.update("stock", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("stock", rec)})

@app.route("/api/<bid>/customers", methods=["GET"])
def api_get_customers(bid):
    items = db.select("customers", {"business_id": bid})
    return jsonify([{"id":c["id"],"code":c.get("code",""),"name":c.get("name",""),"phone":c.get("phone",""),"email":c.get("email",""),"balance":float(c.get("balance",0) or 0)} for c in items])

@app.route("/api/<bid>/customers", methods=["POST"])
def api_post_customers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("customers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    rec["balance"] = 0
    return jsonify({"success": db.insert("customers", rec)})

@app.route("/api/<bid>/suppliers", methods=["GET"])
def api_get_suppliers(bid):
    items = db.select("suppliers", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"name":s.get("name",""),"phone":s.get("phone",""),"email":s.get("email","")} for s in items])

@app.route("/api/<bid>/suppliers", methods=["POST"])
def api_post_suppliers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("suppliers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("suppliers", rec)})

@app.route("/api/<bid>/invoices", methods=["GET"])
def api_get_invoices(bid):
    items = db.select("invoices", {"business_id": bid})
    return jsonify([{"id":i["id"],"number":i.get("number",""),"date":i.get("date",""),"customer_id":i.get("customer_id",""),"customer_name":i.get("customer_name",""),"total":float(i.get("total",0) or 0),"status":i.get("status","draft")} for i in items])

@app.route("/api/<bid>/invoices", methods=["POST"])
def api_post_invoices(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("invoices", rec)})

@app.route("/api/<bid>/quotes", methods=["GET"])
def api_get_quotes(bid):
    items = db.select("quotes", {"business_id": bid})
    return jsonify([{"id":q["id"],"number":q.get("number",""),"date":q.get("date",""),"customer_id":q.get("customer_id",""),"customer_name":q.get("customer_name",""),"total":float(q.get("total",0) or 0),"status":q.get("status","draft")} for q in items])

@app.route("/api/<bid>/quotes", methods=["POST"])
def api_post_quotes(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("quotes", rec)})

@app.route("/api/<bid>/expenses", methods=["GET"])
def api_get_expenses(bid):
    items = db.select("expenses", {"business_id": bid})
    return jsonify([{"id":e["id"],"date":e.get("date",e.get("created_at",""))[:10],"supplier":e.get("supplier",""),"description":e.get("description",""),"amount":float(e.get("amount",0) or 0),"vat":float(e.get("vat",0) or 0)} for e in items])

@app.route("/api/<bid>/expenses", methods=["POST"])
def api_post_expenses(bid):
    d = request.get_json()
    today = datetime.now().isoformat()[:10]
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"date":today,"supplier":d.get("supplier",""),"description":d.get("description",""),"amount":d.get("amount",0),"vat":d.get("vat",0),"category":d.get("category","Expenses")}
    if db.insert("expenses", rec):
        amt, vat = float(d.get("amount",0)), float(d.get("vat",0))
        net = amt - vat
        desc = f"Expense: {d.get('supplier','')} - {d.get('description','')}"
        post_journal(bid, today, desc, d.get("category","Expenses"), net, 0)
        post_journal(bid, today, desc, "VAT Input", vat, 0)
        post_journal(bid, today, desc, "Cash/Bank", 0, amt)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/api/<bid>/sale", methods=["POST"])
def api_sale(bid):
    d = request.get_json()
    items = d.get("items", [])
    total = d.get("total", 0)
    method = d.get("method", "cash")
    inv_count = len(db.select("invoices", {"business_id": bid}))
    cust_id = d.get("customer_id", "")
    cust_name = "Walk-in"
    if cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs: cust_name = custs[0].get("name", "Unknown")
    inv = {"id":str(uuid.uuid4()),"business_id":bid,"number":f"INV{inv_count+1:04d}","date":datetime.now().isoformat(),"customer_id":cust_id,"customer_name":cust_name,"items":json.dumps(items),"total":total,"status":"paid","payment_method":method}
    db.insert("invoices", inv)
    for item in items:
        sl = db.select("stock", {"id": item["id"]})
        if sl:
            new_qty = int(sl[0].get("qty", 0)) - int(item.get("qty", 1))
            db.update("stock", item["id"], {"qty": max(0, new_qty)})
    if method == "account" and cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs:
            new_bal = float(custs[0].get("balance", 0)) + total
            db.update("customers", cust_id, {"balance": new_bal})
    today = datetime.now().isoformat()[:10]
    vat = total * 15 / 115
    net = total - vat
    desc = f"Sale {inv['number']} - {cust_name}"
    if method == "account":
        post_journal(bid, today, desc, "Debtors", total, 0)
    else:
        post_journal(bid, today, desc, "Cash/Bank", total, 0)
    post_journal(bid, today, desc, "Sales", 0, net)
    post_journal(bid, today, desc, "VAT Output", 0, vat)
    return jsonify({"success": True})

@app.route("/api/<bid>/scan-receipt", methods=["POST"])
def api_scan_receipt(bid):
    try:
        d = request.get_json()
        image_data = d.get("image", "")
        if not image_data: return jsonify({"error": "No image"})
        if "," in image_data: image_data = image_data.split(",")[1]
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key: return jsonify({"error": "No API key", "supplier": "", "description": "", "amount": ""})
        response = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}, json={"model": "claude-sonnet-4-20250514", "max_tokens": 500, "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}}, {"type": "text", "text": "Extract: 1) Supplier name, 2) Brief description, 3) Total in Rands. Reply ONLY JSON: {\"supplier\": \"name\", \"description\": \"what\", \"amount\": 123.45}"}]}]}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            text = result.get("content", [{}])[0].get("text", "{}")
            match = re.search(r'\{[^}]+\}', text)
            if match:
                data = json.loads(match.group())
                return jsonify({"supplier": data.get("supplier", ""), "description": data.get("description", ""), "amount": float(data.get("amount", 0))})
        return jsonify({"error": "Could not parse", "supplier": "", "description": "", "amount": ""})
    except Exception as e:
        return jsonify({"error": str(e), "supplier": "", "description": "", "amount": ""})

@app.route("/api/<bid>/import", methods=["POST"])
def api_import(bid):
    try:
        data = request.get_json()
        source = data.get("fulltech", data.get("hardware", data))
        if not source: source = data
        sc, cc, spc = 0, 0, 0
        for item in source.get("stock", []):
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"description":str(item.get("description",item.get("name","")))[:200],"category":str(item.get("category","General"))[:50],"qty":int(item.get("qty",0) or 0),"cost":float(item.get("cost",0) or 0),"price":float(item.get("price",item.get("sell",0)) or 0)}
            if db.insert("stock", rec): sc += 1
        for item in source.get("customers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100],"balance":float(item.get("balance",0) or 0)}
            if db.insert("customers", rec): cc += 1
        for item in source.get("suppliers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100]}
            if db.insert("suppliers", rec): spc += 1
        return jsonify({"success":True,"stock":sc,"customers":cc,"suppliers":spc})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "10"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
"""
Click AI v10 - Lit Up Edition
Sticky glowing header, no duplicate titles, clean UI
"""

from flask import Flask, jsonify, request, redirect
import json, os, re, uuid, requests
from datetime import datetime

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
            for k, v in filters.items(): url += f"&{k}=eq.{v}"
        try:
            r = requests.get(url, headers=self.headers, timeout=60)
            return r.json() if r.status_code == 200 else []
        except: return []
    
    def insert(self, table, data):
        try:
            r = requests.post(f"{self.url}/rest/v1/{table}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 201]
        except: return False
    
    def update(self, table, id, data):
        try:
            r = requests.patch(f"{self.url}/rest/v1/{table}?id=eq.{id}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 204]
        except: return False

db = DB(SUPABASE_URL, SUPABASE_KEY)

def post_journal(bid, date, desc, account, debit, credit):
    return db.insert("journal", {"id": str(uuid.uuid4()), "business_id": bid, "date": date, "description": desc, "account": account, "debit": debit, "credit": credit})

CSS = """<style>
:root{--bg:#06060a;--card:#0d0d14;--border:#1a1a2e;--text:#e0e0e0;--muted:#666;--blue:#3b82f6;--purple:#8b5cf6;--green:#10b981;--red:#ef4444;--orange:#f59e0b;--glow:rgba(139,92,246,0.5)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{position:sticky;top:0;z-index:100;background:linear-gradient(180deg,#0d0d14,rgba(13,13,20,0.95));border-bottom:1px solid var(--border);padding:0 15px;height:52px;display:flex;align-items:center;gap:6px;backdrop-filter:blur(10px);overflow-x:auto}
.header::-webkit-scrollbar{height:0}
.logo{font-size:18px;font-weight:800;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-decoration:none;margin-right:10px;white-space:nowrap;animation:pulse 3s ease-in-out infinite}
@keyframes pulse{0%,100%{filter:brightness(1)}50%{filter:brightness(1.3)}}
.nav-item{padding:6px 12px;border-radius:6px;text-decoration:none;color:var(--muted);font-size:12px;font-weight:500;white-space:nowrap;transition:all 0.2s;border:1px solid transparent}
.nav-item:hover{color:var(--text);background:rgba(255,255,255,0.05)}
.nav-item.active{color:white;background:linear-gradient(135deg,rgba(139,92,246,0.3),rgba(59,130,246,0.3));border-color:rgba(139,92,246,0.5);box-shadow:0 0 15px rgba(139,92,246,0.2)}
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.btn{padding:10px 18px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:14px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:all 0.2s}
.btn-blue{background:var(--blue);color:white}.btn-green{background:var(--green);color:white}.btn-red{background:var(--red);color:white}.btn-purple{background:var(--purple);color:white}.btn-orange{background:var(--orange);color:black}.btn-ghost{background:rgba(255,255,255,0.05);color:var(--text);border:1px solid var(--border)}
.btn:hover{opacity:0.9;transform:translateY(-1px)}.btn-sm{padding:6px 12px;font-size:12px}
input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;margin-bottom:12px}
input:focus,select:focus{outline:none;border-color:var(--purple)}
table{width:100%;border-collapse:collapse}th,td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}th{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;text-align:center}
.stat-value{font-size:26px;font-weight:700;color:var(--blue)}.stat-label{color:var(--muted);font-size:11px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;max-height:55vh;overflow-y:auto;padding:4px}
.grid-item{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px;cursor:pointer;transition:all 0.2s}
.grid-item:hover{border-color:var(--purple);transform:translateY(-2px)}
.grid-item-name{font-weight:600;font-size:12px;margin-bottom:3px}.grid-item-price{color:var(--green);font-weight:700;font-size:13px}.grid-item-stock{color:var(--muted);font-size:10px}
.cart{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.cart-total{font-size:26px;font-weight:800;color:var(--green);text-align:right;padding:12px 0}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);align-items:center;justify-content:center;z-index:200}
.modal.show{display:flex}.modal-box{background:var(--card);border-radius:16px;padding:25px;width:90%;max-width:500px;max-height:90vh;overflow-y:auto}
.modal-title{font-size:18px;font-weight:700;margin-bottom:20px}
.msg{padding:12px 16px;border-radius:8px;margin-bottom:15px;font-size:13px}
.msg-info{background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);color:var(--blue)}
.msg-ok{background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);color:var(--green)}
.msg-err{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--red)}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:rgba(16,185,129,0.2);color:var(--green)}.badge-orange{background:rgba(245,158,11,0.2);color:var(--orange)}.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.report-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:15px}
.report-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;text-decoration:none;color:var(--text);transition:all 0.2s}
.report-card:hover{border-color:var(--purple);transform:translateY(-3px);box-shadow:0 10px 30px rgba(0,0,0,0.3)}
.report-card h3{margin-bottom:6px}.report-card p{color:var(--muted);font-size:12px}
@media(max-width:768px){.header{padding:0 10px;gap:4px}.logo{font-size:16px;margin-right:8px}.nav-item{padding:5px 8px;font-size:11px}.container{padding:15px}.pos-layout{grid-template-columns:1fr!important}.stats{grid-template-columns:repeat(2,1fr)}}
</style>"""

def header(bid, active=""):
    items = [("home","Home",f"/{bid}"),("pos","POS",f"/{bid}/pos"),("stock","Stock",f"/{bid}/stock"),("customers","Cust",f"/{bid}/customers"),("suppliers","Supp",f"/{bid}/suppliers"),("invoices","Inv",f"/{bid}/invoices"),("quotes","Quote",f"/{bid}/quotes"),("expenses","Exp",f"/{bid}/expenses"),("reports","Reports",f"/{bid}/reports"),("import","Import",f"/{bid}/import")]
    nav = "".join([f'<a href="{u}" class="nav-item{"  active" if k==active else ""}">{l}</a>' for k,l,u in items])
    return f'<div class="header"><a href="/{bid}" class="logo">Click AI</a>{nav}</div>'

def page(bid, active, title, content):
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{CSS}</head><body>{header(bid,active)}<div class="container">{content}</div></body></html>'

@app.route("/")
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}
<style>.landing{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:20px}}
.landing-logo{{font-size:60px;font-weight:900;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:glow 2s ease-in-out infinite}}
@keyframes glow{{0%,100%{{filter:drop-shadow(0 0 20px var(--glow))}}50%{{filter:drop-shadow(0 0 40px var(--glow))}}}}</style>
</head><body><div class="landing"><div class="landing-logo">Click AI</div><p style="color:var(--muted);margin:20px 0 40px">Business Management</p><a href="/demo" class="btn btn-purple" style="font-size:18px;padding:15px 40px">Enter</a></div></body></html>'''

@app.route("/demo")
def demo(): return redirect("/5742fb2c-5fd8-4d44-9ddb-b73a3dd51da3")

@app.route("/<bid>")
def dashboard(bid):
    stock = db.select("stock", {"business_id": bid})
    customers = db.select("customers", {"business_id": bid})
    suppliers = db.select("suppliers", {"business_id": bid})
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    stock_val = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    inv_total = sum(float(i.get("total",0) or 0) for i in invoices)
    exp_total = sum(float(e.get("amount",0) or 0) for e in expenses)
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Stock</div></div><div class="stat"><div class="stat-value">R{stock_val:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total:,.0f}</div><div class="stat-label">Sales</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{exp_total:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total-exp_total:,.0f}</div><div class="stat-label">Profit</div></div><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div></div>
<div class="card"><h3 style="margin-bottom:15px">Quick Actions</h3><div style="display:flex;flex-wrap:wrap;gap:10px"><a href="/{bid}/pos" class="btn btn-blue">New Sale</a><a href="/{bid}/invoices/new" class="btn btn-green">New Invoice</a><a href="/{bid}/quotes/new" class="btn btn-purple">New Quote</a><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan Receipt</a></div></div>'''
    return page(bid, "home", "Dashboard", content)

@app.route("/<bid>/pos")
def pos(bid):
    content = f'''<div id="msg" class="msg msg-info">Loading...</div>
<div class="pos-layout" style="display:grid;grid-template-columns:1fr 320px;gap:15px">
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div class="grid" id="items"></div></div>
<div class="cart"><div style="display:flex;justify-content:space-between;margin-bottom:10px"><h3>Cart</h3><button class="btn btn-sm btn-ghost" onclick="cart=[];renderCart()">Clear</button></div>
<select id="custSel" style="margin-bottom:10px"><option value="">Walk-in</option></select>
<div id="cartList" style="min-height:120px"></div><div class="cart-total">R <span id="tot">0.00</span></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><button class="btn btn-green" onclick="pay('cash')">Cash</button><button class="btn btn-blue" onclick="pay('card')">Card</button></div>
<button class="btn btn-purple" style="width:100%;margin-top:8px" onclick="pay('account')">Account</button></div></div>
<script>var stock=[],cart=[],customers=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];return fetch("/api/"+BID+"/customers")}}).then(r=>r.json()).then(c=>{{customers=c||[];var sel="<option value=''>Walk-in</option>";customers.forEach(cu=>{{sel+="<option value='"+cu.id+"'>"+cu.name+"</option>"}});document.getElementById("custSel").innerHTML=sel;document.getElementById("msg").innerHTML="Ready - "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="",c=0;for(var i=0;i<stock.length&&c<80;i++){{var s=stock[i];if(s.qty<=0)continue;if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;h+="<div class='grid-item' onclick='add("+i+")'><div class='grid-item-name'>"+s.desc+"</div><div class='grid-item-price'>R"+s.price.toFixed(2)+"</div><div class='grid-item-stock'>"+s.qty+" left</div></div>";c++}}document.getElementById("items").innerHTML=h||"<div style='padding:30px;text-align:center;color:var(--muted)'>No items</div>"}}
function add(i){{var s=stock[i];var f=cart.findIndex(c=>c.id==s.id);if(f>=0)cart[f].qty++;else cart.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});renderCart()}}
function renderCart(){{if(cart.length==0){{document.getElementById("cartList").innerHTML="<div style='text-align:center;color:var(--muted);padding:30px'>Empty</div>";document.getElementById("tot").innerHTML="0.00";return}}var h="",tot=0;cart.forEach((c,i)=>{{var sub=c.price*c.qty;tot+=sub;h+="<div class='cart-item'><div><div style='font-weight:600;font-size:13px'>"+c.desc+"</div><div style='color:var(--muted);font-size:11px'>R"+c.price.toFixed(2)+" x "+c.qty+"</div></div><div style='display:flex;align-items:center;gap:8px'><span style='font-weight:600'>R"+sub.toFixed(2)+"</span><button class='btn btn-sm btn-red' onclick='cart.splice("+i+",1);renderCart()'>X</button></div></div>"}});document.getElementById("cartList").innerHTML=h;document.getElementById("tot").innerHTML=tot.toFixed(2)}}
function pay(method){{if(cart.length==0)return alert("Cart empty");var tot=cart.reduce((a,c)=>a+c.price*c.qty,0);fetch("/api/"+BID+"/sale",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{items:cart,total:tot,method:method,customer_id:document.getElementById("custSel").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Done! R"+tot.toFixed(2));cart=[];renderCart();load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "pos", "POS", content)
# ═══════════════════════════════════════════════════════════════════════════════
# STOCK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/stock")
def stock_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/import" class="btn btn-orange">Import</a><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Description</th><th>Cat</th><th>Qty</th><th>Cost</th><th>Price</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Item</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fcat" placeholder="Category" value="General"></div>
<input type="text" id="fdesc" placeholder="Description">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px"><input type="number" id="fqty" placeholder="Qty" value="0"><input type="number" id="fcost" placeholder="Cost" step="0.01"><input type="number" id="fprice" placeholder="Price" step="0.01"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var stock=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];document.getElementById("msg").innerHTML="Loaded "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";stock.forEach((s,i)=>{{if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)return;var qs=s.qty<=0?"color:var(--red)":s.qty<=5?"color:var(--orange)":"";h+="<tr><td>"+s.code+"</td><td>"+s.desc+"</td><td>"+s.category+"</td><td style='"+qs+"'>"+s.qty+"</td><td>R"+s.cost.toFixed(2)+"</td><td>R"+s.price.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='7' style='text-align:center;color:var(--muted);padding:30px'>No items</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fcat").value="General";document.getElementById("fdesc").value="";document.getElementById("fqty").value="0";document.getElementById("fcost").value="";document.getElementById("fprice").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var s=stock[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=s.id;document.getElementById("fcode").value=s.code||"";document.getElementById("fcat").value=s.category||"General";document.getElementById("fdesc").value=s.desc||"";document.getElementById("fqty").value=s.qty||0;document.getElementById("fcost").value=s.cost||0;document.getElementById("fprice").value=s.price||0;document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/stock",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,category:document.getElementById("fcat").value,description:document.getElementById("fdesc").value,qty:parseInt(document.getElementById("fqty").value)||0,cost:parseFloat(document.getElementById("fcost").value)||0,price:parseFloat(document.getElementById("fprice").value)||0}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "stock", "Stock", content)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/customers")
def customers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Customer</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" customers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;var bal=c.balance||0;var bs=bal>0?"color:var(--red)":"";h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/customers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td style='"+bs+"'>R"+bal.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='6' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/customers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "customers", "Customers", content)

@app.route("/<bid>/customers/<cid>/history")
def customer_history(bid, cid):
    customers = db.select("customers", {"id": cid})
    if not customers: return redirect(f"/{bid}/customers")
    cust = customers[0]
    invoices = db.select("invoices", {"business_id": bid})
    cust_inv = [i for i in invoices if i.get("customer_id") == cid]
    total = sum(float(i.get("total",0) or 0) for i in cust_inv)
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>R{float(i.get("total",0)):,.2f}</td><td><span class="badge badge-{"green" if i.get("status")=="paid" else "orange"}">{i.get("status","")}</span></td></tr>' for i in cust_inv])
    content = f'''<a href="/{bid}/customers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(cust.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(cust.get("phone",""))} | {js_safe(cust.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(cust_inv)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{float(cust.get("balance",0)):,.0f}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Invoice</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "customers", cust.get("name","Customer"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Supplier</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/suppliers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" suppliers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/suppliers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/suppliers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "suppliers", "Suppliers", content)

@app.route("/<bid>/suppliers/<sid>/history")
def supplier_history(bid, sid):
    suppliers = db.select("suppliers", {"id": sid})
    if not suppliers: return redirect(f"/{bid}/suppliers")
    supp = suppliers[0]
    expenses = db.select("expenses", {"business_id": bid})
    supp_exp = [e for e in expenses if js_safe(e.get("supplier","")).lower() == js_safe(supp.get("name","")).lower()]
    total = sum(float(e.get("amount",0) or 0) for e in supp_exp)
    rows = "".join([f'<tr><td>{str(e.get("created_at",""))[:10]}</td><td>{js_safe(e.get("description",""))}</td><td>R{float(e.get("amount",0)):,.2f}</td></tr>' for e in supp_exp])
    content = f'''<a href="/{bid}/suppliers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(supp.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(supp.get("phone",""))} | {js_safe(supp.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(supp_exp)}</div><div class="stat-label">Purchases</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total:,.0f}</div><div class="stat-label">Total Spent</div></div></div>
<div class="card"><table><thead><tr><th>Date</th><th>Description</th><th>Amount</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "suppliers", supp.get("name","Supplier"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/invoices")
def invoices_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/invoices/new" class="btn btn-green">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/invoices").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" invoices";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(i=>{{var b=i.status=="paid"?"badge-green":i.status=="overdue"?"badge-red":"badge-orange";h+="<tr><td>"+i.number+"</td><td>"+(i.date||"").substring(0,10)+"</td><td>"+i.customer_name+"</td><td>R"+i.total.toFixed(2)+"</td><td><span class='badge "+b+"'>"+i.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "invoices", "Invoices", content)

@app.route("/<bid>/invoices/new")
def new_invoice(bid): return create_doc_page(bid, "Invoice", "INV", "invoices")

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/quotes")
def quotes_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/quotes/new" class="btn btn-purple">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/quotes").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" quotes";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(q=>{{h+="<tr><td>"+q.number+"</td><td>"+(q.date||"").substring(0,10)+"</td><td>"+q.customer_name+"</td><td>R"+q.total.toFixed(2)+"</td><td><span class='badge badge-orange'>"+q.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "quotes", "Quotes", content)

@app.route("/<bid>/quotes/new")
def new_quote(bid): return create_doc_page(bid, "Quote", "QUO", "quotes")

def create_doc_page(bid, doc_type, prefix, table):
    active = "invoices" if doc_type == "Invoice" else "quotes"
    today = datetime.now().strftime('%Y-%m-%d')
    content = f'''<div class="card">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:15px"><div><label style="color:var(--muted);font-size:11px">Number</label><input type="text" id="docNum" value="{prefix}001"></div><div><label style="color:var(--muted);font-size:11px">Date</label><input type="date" id="docDate" value="{today}"></div><div><label style="color:var(--muted);font-size:11px">Customer</label><select id="custSel"><option value="">Select...</option></select></div></div>
<h3 style="margin-bottom:10px">Items</h3><input type="text" id="q" placeholder="Search to add..." oninput="searchStock()"><div id="searchResults" style="max-height:150px;overflow-y:auto;margin-bottom:10px"></div><div id="lines"></div>
<div style="text-align:right;font-size:22px;font-weight:700;color:var(--green);padding:10px 0">Total: R <span id="total">0.00</span></div>
<button class="btn btn-green" onclick="saveDoc()">Save</button></div>
<script>var stock=[],customers=[],lines=[],BID="{bid}",docType="{table}";
fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[]}});
fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{customers=d||[];var sel="<option value=''>Select...</option>";customers.forEach(c=>{{sel+="<option value='"+c.id+"'>"+c.name+"</option>"}});document.getElementById("custSel").innerHTML=sel}});
function searchStock(){{var q=document.getElementById("q").value.toLowerCase();if(q.length<2){{document.getElementById("searchResults").innerHTML="";return}}var h="";stock.forEach((s,i)=>{{if(s.desc.toLowerCase().indexOf(q)>=0||s.code.toLowerCase().indexOf(q)>=0)h+="<div class='grid-item' style='margin-bottom:5px' onclick='addLine("+i+")'>"+s.desc+" - R"+s.price.toFixed(2)+"</div>"}});document.getElementById("searchResults").innerHTML=h||"<div style='color:var(--muted)'>No matches</div>"}}
function addLine(i){{var s=stock[i];lines.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});document.getElementById("q").value="";document.getElementById("searchResults").innerHTML="";renderLines()}}
function renderLines(){{var h="<table><thead><tr><th>Item</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr></thead><tbody>";var tot=0;lines.forEach((l,i)=>{{var sub=l.price*l.qty;tot+=sub;h+="<tr><td>"+l.desc+"</td><td>R"+l.price.toFixed(2)+"</td><td><input type='number' value='"+l.qty+"' min='1' style='width:60px' onchange='updateQty("+i+",this.value)'></td><td>R"+sub.toFixed(2)+"</td><td><button class='btn btn-sm btn-red' onclick='lines.splice("+i+",1);renderLines()'>X</button></td></tr>"}});h+="</tbody></table>";document.getElementById("lines").innerHTML=lines.length?h:"<div style='color:var(--muted);text-align:center;padding:30px'>No items</div>";document.getElementById("total").innerHTML=tot.toFixed(2)}}
function updateQty(i,v){{lines[i].qty=parseInt(v)||1;renderLines()}}
function saveDoc(){{var sel=document.getElementById("custSel");var cn=sel.options[sel.selectedIndex]?sel.options[sel.selectedIndex].text:"Walk-in";if(lines.length==0)return alert("Add items");var tot=lines.reduce((a,l)=>a+l.price*l.qty,0);fetch("/api/"+BID+"/"+docType,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{number:document.getElementById("docNum").value,date:document.getElementById("docDate").value,customer_id:sel.value,customer_name:cn,items:lines,total:tot}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/"+docType}}else alert("Error")}})}}
renderLines();</script>'''
    return page(bid, active, f"New {doc_type}", content)
# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/expenses")
def expenses_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan</a><button class="btn btn-red" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>Date</th><th>Supplier</th><th>Description</th><th>Amount</th><th>VAT</th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title">Add Expense</div>
<input type="text" id="fsupplier" placeholder="Supplier"><input type="text" id="fdesc" placeholder="Description"><input type="number" id="famount" placeholder="Amount (incl VAT)" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="fvat" checked> Includes 15% VAT</label>
<div style="display:flex;gap:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/expenses").then(r=>r.json()).then(d=>{{items=d||[];var tot=items.reduce((a,e)=>a+e.amount,0);document.getElementById("msg").innerHTML=items.length+" expenses | R"+tot.toFixed(2);document.getElementById("msg").className="msg msg-ok";render()}})}}
function render(){{var h="";items.forEach(e=>{{h+="<tr><td>"+(e.date||"-")+"</td><td>"+e.supplier+"</td><td>"+e.description+"</td><td>R"+e.amount.toFixed(2)+"</td><td>R"+e.vat.toFixed(2)+"</td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("modal").classList.add("show")}}
function save(){{var amt=parseFloat(document.getElementById("famount").value)||0;var vat=document.getElementById("fvat").checked?amt*15/115:0;fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("fsupplier").value,description:document.getElementById("fdesc").value,amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "expenses", "Expenses", content)

@app.route("/<bid>/expenses/scan")
def scan_receipt(bid):
    content = f'''<a href="/{bid}/expenses" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<div class="card"><h3 style="margin-bottom:10px">Scan Receipt</h3><p style="color:var(--muted);margin-bottom:15px">AI extracts supplier, description, amount</p>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px"><button class="btn btn-orange" onclick="startCamera()">Camera</button><span style="color:var(--muted);align-self:center">or</span><input type="file" id="fileInput" accept="image/*" onchange="handleFile(this)"></div>
<video id="video" autoplay playsinline style="display:none;width:100%;max-width:350px;border-radius:10px;background:#000"></video>
<button id="captureBtn" class="btn btn-green" style="display:none;margin-top:10px" onclick="capture()">Snap</button>
<canvas id="canvas" style="display:none"></canvas><img id="preview" style="display:none;max-width:100%;border-radius:10px;margin-top:10px">
<div id="processing" class="msg msg-info" style="display:none;margin-top:10px">Reading...</div></div>
<div class="card" id="resultCard" style="display:none"><h3 style="margin-bottom:10px">Details</h3>
<input type="text" id="rSupplier" placeholder="Supplier"><input type="text" id="rDesc" placeholder="Description"><input type="number" id="rAmount" placeholder="Amount" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="rVat" checked> 15% VAT</label>
<button class="btn btn-green" onclick="saveExpense()">Save</button></div>
<script>var BID="{bid}",stream=null;
function startCamera(){{navigator.mediaDevices.getUserMedia({{video:{{facingMode:"environment"}}}}).then(s=>{{stream=s;document.getElementById("video").srcObject=s;document.getElementById("video").style.display="block";document.getElementById("captureBtn").style.display="inline-block"}}).catch(e=>alert("Camera: "+e.message))}}
function capture(){{var v=document.getElementById("video"),c=document.getElementById("canvas");c.width=v.videoWidth;c.height=v.videoHeight;c.getContext("2d").drawImage(v,0,0);var d=c.toDataURL("image/jpeg",0.8);if(stream)stream.getTracks().forEach(t=>t.stop());document.getElementById("video").style.display="none";document.getElementById("captureBtn").style.display="none";document.getElementById("preview").src=d;document.getElementById("preview").style.display="block";processAI(d)}}
function handleFile(input){{if(input.files&&input.files[0]){{var r=new FileReader();r.onload=e=>{{document.getElementById("preview").src=e.target.result;document.getElementById("preview").style.display="block";processAI(e.target.result)}};r.readAsDataURL(input.files[0])}}}}
function processAI(d){{document.getElementById("processing").style.display="block";document.getElementById("resultCard").style.display="none";fetch("/api/"+BID+"/scan-receipt",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{image:d}})}}).then(r=>r.json()).then(x=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";if(x.supplier)document.getElementById("rSupplier").value=x.supplier;if(x.description)document.getElementById("rDesc").value=x.description;if(x.amount)document.getElementById("rAmount").value=x.amount;if(x.error)alert(x.error)}}).catch(e=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";alert("Error: "+e)}})}}
function saveExpense(){{var amt=parseFloat(document.getElementById("rAmount").value)||0;var vat=document.getElementById("rVat").checked?amt*15/115:0;if(!document.getElementById("rSupplier").value)return alert("Supplier?");if(!amt)return alert("Amount?");fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("rSupplier").value,description:document.getElementById("rDesc").value||"Receipt",amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/expenses"}}else alert("Error")}})}}</script>'''
    return page(bid, "expenses", "Scan Receipt", content)

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/reports")
def reports_page(bid):
    content = '''<div class="report-grid">
<a href="/{0}/reports/sales" class="report-card"><h3>Sales</h3><p>Invoices & totals</p></a>
<a href="/{0}/reports/stock" class="report-card"><h3>Stock</h3><p>Levels & alerts</p></a>
<a href="/{0}/reports/customers" class="report-card"><h3>Customers</h3><p>Balances</p></a>
<a href="/{0}/reports/suppliers" class="report-card"><h3>Suppliers</h3><p>Contact list</p></a>
<a href="/{0}/reports/profit" class="report-card"><h3>P&L</h3><p>Income vs expenses</p></a>
<a href="/{0}/reports/vat" class="report-card"><h3>VAT</h3><p>In vs out</p></a>
<a href="/{0}/reports/tb" class="report-card"><h3>Trial Balance</h3><p>All accounts</p></a></div>'''.format(bid)
    return page(bid, "reports", "Reports", content)

@app.route("/<bid>/reports/sales")
def report_sales(bid):
    invoices = db.select("invoices", {"business_id": bid})
    total = sum(float(i.get("total",0) or 0) for i in invoices)
    paid = sum(float(i.get("total",0) or 0) for i in invoices if i.get("status")=="paid")
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>{js_safe(i.get("customer_name",""))}</td><td>R{float(i.get("total",0)):,.2f}</td></tr>' for i in invoices[:20]])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{paid:,.0f}</div><div class="stat-label">Paid</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total-paid:,.0f}</div><div class="stat-label">Outstanding</div></div></div>
<div class="card"><table><thead><tr><th>Inv</th><th>Date</th><th>Customer</th><th>Total</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Sales Report", content)

@app.route("/<bid>/reports/stock")
def report_stock(bid):
    stock = db.select("stock", {"business_id": bid})
    value = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    low = [s for s in stock if 0 < int(s.get("qty",0) or 0) <= 5]
    out = [s for s in stock if int(s.get("qty",0) or 0) <= 0]
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Items</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{value:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{len(low)}</div><div class="stat-label">Low</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">{len(out)}</div><div class="stat-label">Out</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Stock Report", content)

@app.route("/<bid>/reports/customers")
def report_customers(bid):
    customers = db.select("customers", {"business_id": bid})
    total_bal = sum(float(c.get("balance",0) or 0) for c in customers)
    owing = len([c for c in customers if float(c.get("balance",0) or 0) > 0])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total_bal:,.0f}</div><div class="stat-label">Total Owing</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{owing}</div><div class="stat-label">With Balance</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Customer Report", content)

@app.route("/<bid>/reports/suppliers")
def report_suppliers(bid):
    suppliers = db.select("suppliers", {"business_id": bid})
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Supplier Report", content)

@app.route("/<bid>/reports/profit")
def report_profit(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    income = sum(float(i.get("total",0) or 0) for i in invoices)
    expense = sum(float(e.get("amount",0) or 0) for e in expenses)
    profit = income - expense
    pc = "var(--green)" if profit >= 0 else "var(--red)"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{income:,.0f}</div><div class="stat-label">Income</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{expense:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:{pc}">R{profit:,.0f}</div><div class="stat-label">Profit</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Profit & Loss", content)

@app.route("/<bid>/reports/vat")
def report_vat(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    sales = sum(float(i.get("total",0) or 0) for i in invoices)
    vat_out = sales * 15 / 115
    vat_in = sum(float(e.get("vat",0) or 0) for e in expenses)
    vat_due = vat_out - vat_in
    dc = "var(--red)" if vat_due > 0 else "var(--green)"
    dl = "Pay SARS" if vat_due > 0 else "Refund"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--blue)">R{vat_out:,.0f}</div><div class="stat-label">Output</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{vat_in:,.0f}</div><div class="stat-label">Input</div></div><div class="stat"><div class="stat-value" style="color:{dc}">R{abs(vat_due):,.0f}</div><div class="stat-label">{dl}</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "VAT Report", content)

@app.route("/<bid>/reports/tb")
def report_tb(bid):
    journal = db.select("journal", {"business_id": bid})
    accounts = {}
    for j in journal:
        acc = j.get("account", "Unknown")
        if acc not in accounts: accounts[acc] = {"dr": 0, "cr": 0}
        accounts[acc]["dr"] += float(j.get("debit", 0) or 0)
        accounts[acc]["cr"] += float(j.get("credit", 0) or 0)
    total_dr = sum(a["dr"] for a in accounts.values())
    total_cr = sum(a["cr"] for a in accounts.values())
    rows = "".join([f'<tr><td>{acc}</td><td style="text-align:right">{"R"+str(int(v["dr"])) if v["dr"] else "-"}</td><td style="text-align:right">{"R"+str(int(v["cr"])) if v["cr"] else "-"}</td></tr>' for acc, v in sorted(accounts.items())])
    balanced = abs(total_dr - total_cr) < 0.01
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(accounts)}</div><div class="stat-label">Accounts</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{total_dr:,.0f}</div><div class="stat-label">Debits</div></div><div class="stat"><div class="stat-value" style="color:var(--purple)">R{total_cr:,.0f}</div><div class="stat-label">Credits</div></div><div class="stat"><div class="stat-value" style="color:{"var(--green)" if balanced else "var(--red)"}">{"OK" if balanced else "ERR"}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Account</th><th style="text-align:right">Debit</th><th style="text-align:right">Credit</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Trial Balance", content)

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/import")
def import_page(bid):
    content = f'''<div class="card"><h3 style="margin-bottom:15px">Import Data</h3><p style="color:var(--muted);margin-bottom:15px">Paste JSON with stock, customers, suppliers arrays</p>
<textarea id="jsonData" rows="10" placeholder='{{"stock":[...],"customers":[...],"suppliers":[...]}}'></textarea>
<button class="btn btn-blue" onclick="doImport()">Import</button><div id="result" style="margin-top:15px"></div></div>
<script>var BID="{bid}";function doImport(){{try{{var d=JSON.parse(document.getElementById("jsonData").value);fetch("/api/"+BID+"/import",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{document.getElementById("result").innerHTML="<div class='msg msg-ok'>Imported: "+x.stock+" stock, "+x.customers+" customers, "+x.suppliers+" suppliers</div>"}})}catch(e){{document.getElementById("result").innerHTML="<div class='msg msg-err'>Invalid JSON</div>"}}}}</script>'''
    return page(bid, "import", "Import", content)

# ═══════════════════════════════════════════════════════════════════════════════
# APIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/<bid>/stock", methods=["GET"])
def api_get_stock(bid):
    items = db.select("stock", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"desc":s.get("description",""),"category":s.get("category",""),"qty":int(s.get("qty",0) or 0),"cost":float(s.get("cost",0) or 0),"price":float(s.get("price",0) or 0)} for s in items])

@app.route("/api/<bid>/stock", methods=["POST"])
def api_post_stock(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"description":d.get("description",""),"category":d.get("category","General"),"qty":d.get("qty",0),"cost":d.get("cost",0),"price":d.get("price",0)}
    if d.get("id"):
        return jsonify({"success": db.update("stock", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("stock", rec)})

@app.route("/api/<bid>/customers", methods=["GET"])
def api_get_customers(bid):
    items = db.select("customers", {"business_id": bid})
    return jsonify([{"id":c["id"],"code":c.get("code",""),"name":c.get("name",""),"phone":c.get("phone",""),"email":c.get("email",""),"balance":float(c.get("balance",0) or 0)} for c in items])

@app.route("/api/<bid>/customers", methods=["POST"])
def api_post_customers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("customers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    rec["balance"] = 0
    return jsonify({"success": db.insert("customers", rec)})

@app.route("/api/<bid>/suppliers", methods=["GET"])
def api_get_suppliers(bid):
    items = db.select("suppliers", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"name":s.get("name",""),"phone":s.get("phone",""),"email":s.get("email","")} for s in items])

@app.route("/api/<bid>/suppliers", methods=["POST"])
def api_post_suppliers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("suppliers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("suppliers", rec)})

@app.route("/api/<bid>/invoices", methods=["GET"])
def api_get_invoices(bid):
    items = db.select("invoices", {"business_id": bid})
    return jsonify([{"id":i["id"],"number":i.get("number",""),"date":i.get("date",""),"customer_id":i.get("customer_id",""),"customer_name":i.get("customer_name",""),"total":float(i.get("total",0) or 0),"status":i.get("status","draft")} for i in items])

@app.route("/api/<bid>/invoices", methods=["POST"])
def api_post_invoices(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("invoices", rec)})

@app.route("/api/<bid>/quotes", methods=["GET"])
def api_get_quotes(bid):
    items = db.select("quotes", {"business_id": bid})
    return jsonify([{"id":q["id"],"number":q.get("number",""),"date":q.get("date",""),"customer_id":q.get("customer_id",""),"customer_name":q.get("customer_name",""),"total":float(q.get("total",0) or 0),"status":q.get("status","draft")} for q in items])

@app.route("/api/<bid>/quotes", methods=["POST"])
def api_post_quotes(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("quotes", rec)})

@app.route("/api/<bid>/expenses", methods=["GET"])
def api_get_expenses(bid):
    items = db.select("expenses", {"business_id": bid})
    return jsonify([{"id":e["id"],"date":e.get("date",e.get("created_at",""))[:10],"supplier":e.get("supplier",""),"description":e.get("description",""),"amount":float(e.get("amount",0) or 0),"vat":float(e.get("vat",0) or 0)} for e in items])

@app.route("/api/<bid>/expenses", methods=["POST"])
def api_post_expenses(bid):
    d = request.get_json()
    today = datetime.now().isoformat()[:10]
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"date":today,"supplier":d.get("supplier",""),"description":d.get("description",""),"amount":d.get("amount",0),"vat":d.get("vat",0),"category":d.get("category","Expenses")}
    if db.insert("expenses", rec):
        amt, vat = float(d.get("amount",0)), float(d.get("vat",0))
        net = amt - vat
        desc = f"Expense: {d.get('supplier','')} - {d.get('description','')}"
        post_journal(bid, today, desc, d.get("category","Expenses"), net, 0)
        post_journal(bid, today, desc, "VAT Input", vat, 0)
        post_journal(bid, today, desc, "Cash/Bank", 0, amt)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/api/<bid>/sale", methods=["POST"])
def api_sale(bid):
    d = request.get_json()
    items = d.get("items", [])
    total = d.get("total", 0)
    method = d.get("method", "cash")
    inv_count = len(db.select("invoices", {"business_id": bid}))
    cust_id = d.get("customer_id", "")
    cust_name = "Walk-in"
    if cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs: cust_name = custs[0].get("name", "Unknown")
    inv = {"id":str(uuid.uuid4()),"business_id":bid,"number":f"INV{inv_count+1:04d}","date":datetime.now().isoformat(),"customer_id":cust_id,"customer_name":cust_name,"items":json.dumps(items),"total":total,"status":"paid","payment_method":method}
    db.insert("invoices", inv)
    for item in items:
        sl = db.select("stock", {"id": item["id"]})
        if sl:
            new_qty = int(sl[0].get("qty", 0)) - int(item.get("qty", 1))
            db.update("stock", item["id"], {"qty": max(0, new_qty)})
    if method == "account" and cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs:
            new_bal = float(custs[0].get("balance", 0)) + total
            db.update("customers", cust_id, {"balance": new_bal})
    today = datetime.now().isoformat()[:10]
    vat = total * 15 / 115
    net = total - vat
    desc = f"Sale {inv['number']} - {cust_name}"
    if method == "account":
        post_journal(bid, today, desc, "Debtors", total, 0)
    else:
        post_journal(bid, today, desc, "Cash/Bank", total, 0)
    post_journal(bid, today, desc, "Sales", 0, net)
    post_journal(bid, today, desc, "VAT Output", 0, vat)
    return jsonify({"success": True})

@app.route("/api/<bid>/scan-receipt", methods=["POST"])
def api_scan_receipt(bid):
    try:
        d = request.get_json()
        image_data = d.get("image", "")
        if not image_data: return jsonify({"error": "No image"})
        if "," in image_data: image_data = image_data.split(",")[1]
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key: return jsonify({"error": "No API key", "supplier": "", "description": "", "amount": ""})
        response = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}, json={"model": "claude-sonnet-4-20250514", "max_tokens": 500, "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}}, {"type": "text", "text": "Extract: 1) Supplier name, 2) Brief description, 3) Total in Rands. Reply ONLY JSON: {\"supplier\": \"name\", \"description\": \"what\", \"amount\": 123.45}"}]}]}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            text = result.get("content", [{}])[0].get("text", "{}")
            match = re.search(r'\{[^}]+\}', text)
            if match:
                data = json.loads(match.group())
                return jsonify({"supplier": data.get("supplier", ""), "description": data.get("description", ""), "amount": float(data.get("amount", 0))})
        return jsonify({"error": "Could not parse", "supplier": "", "description": "", "amount": ""})
    except Exception as e:
        return jsonify({"error": str(e), "supplier": "", "description": "", "amount": ""})

@app.route("/api/<bid>/import", methods=["POST"])
def api_import(bid):
    try:
        data = request.get_json()
        source = data.get("fulltech", data.get("hardware", data))
        if not source: source = data
        sc, cc, spc = 0, 0, 0
        for item in source.get("stock", []):
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"description":str(item.get("description",item.get("name","")))[:200],"category":str(item.get("category","General"))[:50],"qty":int(item.get("qty",0) or 0),"cost":float(item.get("cost",0) or 0),"price":float(item.get("price",item.get("sell",0)) or 0)}
            if db.insert("stock", rec): sc += 1
        for item in source.get("customers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100],"balance":float(item.get("balance",0) or 0)}
            if db.insert("customers", rec): cc += 1
        for item in source.get("suppliers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100]}
            if db.insert("suppliers", rec): spc += 1
        return jsonify({"success":True,"stock":sc,"customers":cc,"suppliers":spc})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "10"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
"""
Click AI v10 - Lit Up Edition
Sticky glowing header, no duplicate titles, clean UI
"""

from flask import Flask, jsonify, request, redirect
import json, os, re, uuid, requests
from datetime import datetime

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
            for k, v in filters.items(): url += f"&{k}=eq.{v}"
        try:
            r = requests.get(url, headers=self.headers, timeout=60)
            return r.json() if r.status_code == 200 else []
        except: return []
    
    def insert(self, table, data):
        try:
            r = requests.post(f"{self.url}/rest/v1/{table}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 201]
        except: return False
    
    def update(self, table, id, data):
        try:
            r = requests.patch(f"{self.url}/rest/v1/{table}?id=eq.{id}", headers=self.headers, json=data, timeout=30)
            return r.status_code in [200, 204]
        except: return False

db = DB(SUPABASE_URL, SUPABASE_KEY)

def post_journal(bid, date, desc, account, debit, credit):
    return db.insert("journal", {"id": str(uuid.uuid4()), "business_id": bid, "date": date, "description": desc, "account": account, "debit": debit, "credit": credit})

CSS = """<style>
:root{--bg:#06060a;--card:#0d0d14;--border:#1a1a2e;--text:#e0e0e0;--muted:#666;--blue:#3b82f6;--purple:#8b5cf6;--green:#10b981;--red:#ef4444;--orange:#f59e0b;--glow:rgba(139,92,246,0.5)}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
.header{position:sticky;top:0;z-index:100;background:linear-gradient(180deg,#0d0d14,rgba(13,13,20,0.95));border-bottom:1px solid var(--border);padding:0 15px;height:52px;display:flex;align-items:center;gap:6px;backdrop-filter:blur(10px);overflow-x:auto}
.header::-webkit-scrollbar{height:0}
.logo{font-size:18px;font-weight:800;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-decoration:none;margin-right:10px;white-space:nowrap;animation:pulse 3s ease-in-out infinite}
@keyframes pulse{0%,100%{filter:brightness(1)}50%{filter:brightness(1.3)}}
.nav-item{padding:6px 12px;border-radius:6px;text-decoration:none;color:var(--muted);font-size:12px;font-weight:500;white-space:nowrap;transition:all 0.2s;border:1px solid transparent}
.nav-item:hover{color:var(--text);background:rgba(255,255,255,0.05)}
.nav-item.active{color:white;background:linear-gradient(135deg,rgba(139,92,246,0.3),rgba(59,130,246,0.3));border-color:rgba(139,92,246,0.5);box-shadow:0 0 15px rgba(139,92,246,0.2)}
.container{max-width:1400px;margin:0 auto;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}
.btn{padding:10px 18px;border-radius:8px;border:none;cursor:pointer;font-weight:600;font-size:14px;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:all 0.2s}
.btn-blue{background:var(--blue);color:white}.btn-green{background:var(--green);color:white}.btn-red{background:var(--red);color:white}.btn-purple{background:var(--purple);color:white}.btn-orange{background:var(--orange);color:black}.btn-ghost{background:rgba(255,255,255,0.05);color:var(--text);border:1px solid var(--border)}
.btn:hover{opacity:0.9;transform:translateY(-1px)}.btn-sm{padding:6px 12px;font-size:12px}
input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;margin-bottom:12px}
input:focus,select:focus{outline:none;border-color:var(--purple)}
table{width:100%;border-collapse:collapse}th,td{padding:12px;text-align:left;border-bottom:1px solid var(--border)}th{color:var(--muted);font-size:11px;font-weight:600;text-transform:uppercase}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px;text-align:center}
.stat-value{font-size:26px;font-weight:700;color:var(--blue)}.stat-label{color:var(--muted);font-size:11px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;max-height:55vh;overflow-y:auto;padding:4px}
.grid-item{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:10px;cursor:pointer;transition:all 0.2s}
.grid-item:hover{border-color:var(--purple);transform:translateY(-2px)}
.grid-item-name{font-weight:600;font-size:12px;margin-bottom:3px}.grid-item-price{color:var(--green);font-weight:700;font-size:13px}.grid-item-stock{color:var(--muted);font-size:10px}
.cart{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.cart-item{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.cart-total{font-size:26px;font-weight:800;color:var(--green);text-align:right;padding:12px 0}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.85);align-items:center;justify-content:center;z-index:200}
.modal.show{display:flex}.modal-box{background:var(--card);border-radius:16px;padding:25px;width:90%;max-width:500px;max-height:90vh;overflow-y:auto}
.modal-title{font-size:18px;font-weight:700;margin-bottom:20px}
.msg{padding:12px 16px;border-radius:8px;margin-bottom:15px;font-size:13px}
.msg-info{background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3);color:var(--blue)}
.msg-ok{background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);color:var(--green)}
.msg-err{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:var(--red)}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600}
.badge-green{background:rgba(16,185,129,0.2);color:var(--green)}.badge-orange{background:rgba(245,158,11,0.2);color:var(--orange)}.badge-red{background:rgba(239,68,68,0.2);color:var(--red)}
.report-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:15px}
.report-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;text-decoration:none;color:var(--text);transition:all 0.2s}
.report-card:hover{border-color:var(--purple);transform:translateY(-3px);box-shadow:0 10px 30px rgba(0,0,0,0.3)}
.report-card h3{margin-bottom:6px}.report-card p{color:var(--muted);font-size:12px}
@media(max-width:768px){.header{padding:0 10px;gap:4px}.logo{font-size:16px;margin-right:8px}.nav-item{padding:5px 8px;font-size:11px}.container{padding:15px}.pos-layout{grid-template-columns:1fr!important}.stats{grid-template-columns:repeat(2,1fr)}}
</style>"""

def header(bid, active=""):
    items = [("home","Home",f"/{bid}"),("pos","POS",f"/{bid}/pos"),("stock","Stock",f"/{bid}/stock"),("customers","Cust",f"/{bid}/customers"),("suppliers","Supp",f"/{bid}/suppliers"),("invoices","Inv",f"/{bid}/invoices"),("quotes","Quote",f"/{bid}/quotes"),("expenses","Exp",f"/{bid}/expenses"),("reports","Reports",f"/{bid}/reports"),("import","Import",f"/{bid}/import")]
    nav = "".join([f'<a href="{u}" class="nav-item{"  active" if k==active else ""}">{l}</a>' for k,l,u in items])
    return f'<div class="header"><a href="/{bid}" class="logo">Click AI</a>{nav}</div>'

def page(bid, active, title, content):
    return f'<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{CSS}</head><body>{header(bid,active)}<div class="container">{content}</div></body></html>'

@app.route("/")
def home():
    return f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Click AI</title>{CSS}
<style>.landing{{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;text-align:center;padding:20px}}
.landing-logo{{font-size:60px;font-weight:900;background:linear-gradient(135deg,var(--purple),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:glow 2s ease-in-out infinite}}
@keyframes glow{{0%,100%{{filter:drop-shadow(0 0 20px var(--glow))}}50%{{filter:drop-shadow(0 0 40px var(--glow))}}}}</style>
</head><body><div class="landing"><div class="landing-logo">Click AI</div><p style="color:var(--muted);margin:20px 0 40px">Business Management</p><a href="/demo" class="btn btn-purple" style="font-size:18px;padding:15px 40px">Enter</a></div></body></html>'''

@app.route("/demo")
def demo(): return redirect("/5742fb2c-5fd8-4d44-9ddb-b73a3dd51da3")

@app.route("/<bid>")
def dashboard(bid):
    stock = db.select("stock", {"business_id": bid})
    customers = db.select("customers", {"business_id": bid})
    suppliers = db.select("suppliers", {"business_id": bid})
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    stock_val = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    inv_total = sum(float(i.get("total",0) or 0) for i in invoices)
    exp_total = sum(float(e.get("amount",0) or 0) for e in expenses)
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Stock</div></div><div class="stat"><div class="stat-value">R{stock_val:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total:,.0f}</div><div class="stat-label">Sales</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{exp_total:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{inv_total-exp_total:,.0f}</div><div class="stat-label">Profit</div></div><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div></div>
<div class="card"><h3 style="margin-bottom:15px">Quick Actions</h3><div style="display:flex;flex-wrap:wrap;gap:10px"><a href="/{bid}/pos" class="btn btn-blue">New Sale</a><a href="/{bid}/invoices/new" class="btn btn-green">New Invoice</a><a href="/{bid}/quotes/new" class="btn btn-purple">New Quote</a><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan Receipt</a></div></div>'''
    return page(bid, "home", "Dashboard", content)

@app.route("/<bid>/pos")
def pos(bid):
    content = f'''<div id="msg" class="msg msg-info">Loading...</div>
<div class="pos-layout" style="display:grid;grid-template-columns:1fr 320px;gap:15px">
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div class="grid" id="items"></div></div>
<div class="cart"><div style="display:flex;justify-content:space-between;margin-bottom:10px"><h3>Cart</h3><button class="btn btn-sm btn-ghost" onclick="cart=[];renderCart()">Clear</button></div>
<select id="custSel" style="margin-bottom:10px"><option value="">Walk-in</option></select>
<div id="cartList" style="min-height:120px"></div><div class="cart-total">R <span id="tot">0.00</span></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><button class="btn btn-green" onclick="pay('cash')">Cash</button><button class="btn btn-blue" onclick="pay('card')">Card</button></div>
<button class="btn btn-purple" style="width:100%;margin-top:8px" onclick="pay('account')">Account</button></div></div>
<script>var stock=[],cart=[],customers=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];return fetch("/api/"+BID+"/customers")}}).then(r=>r.json()).then(c=>{{customers=c||[];var sel="<option value=''>Walk-in</option>";customers.forEach(cu=>{{sel+="<option value='"+cu.id+"'>"+cu.name+"</option>"}});document.getElementById("custSel").innerHTML=sel;document.getElementById("msg").innerHTML="Ready - "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="",c=0;for(var i=0;i<stock.length&&c<80;i++){{var s=stock[i];if(s.qty<=0)continue;if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)continue;h+="<div class='grid-item' onclick='add("+i+")'><div class='grid-item-name'>"+s.desc+"</div><div class='grid-item-price'>R"+s.price.toFixed(2)+"</div><div class='grid-item-stock'>"+s.qty+" left</div></div>";c++}}document.getElementById("items").innerHTML=h||"<div style='padding:30px;text-align:center;color:var(--muted)'>No items</div>"}}
function add(i){{var s=stock[i];var f=cart.findIndex(c=>c.id==s.id);if(f>=0)cart[f].qty++;else cart.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});renderCart()}}
function renderCart(){{if(cart.length==0){{document.getElementById("cartList").innerHTML="<div style='text-align:center;color:var(--muted);padding:30px'>Empty</div>";document.getElementById("tot").innerHTML="0.00";return}}var h="",tot=0;cart.forEach((c,i)=>{{var sub=c.price*c.qty;tot+=sub;h+="<div class='cart-item'><div><div style='font-weight:600;font-size:13px'>"+c.desc+"</div><div style='color:var(--muted);font-size:11px'>R"+c.price.toFixed(2)+" x "+c.qty+"</div></div><div style='display:flex;align-items:center;gap:8px'><span style='font-weight:600'>R"+sub.toFixed(2)+"</span><button class='btn btn-sm btn-red' onclick='cart.splice("+i+",1);renderCart()'>X</button></div></div>"}});document.getElementById("cartList").innerHTML=h;document.getElementById("tot").innerHTML=tot.toFixed(2)}}
function pay(method){{if(cart.length==0)return alert("Cart empty");var tot=cart.reduce((a,c)=>a+c.price*c.qty,0);fetch("/api/"+BID+"/sale",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{items:cart,total:tot,method:method,customer_id:document.getElementById("custSel").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Done! R"+tot.toFixed(2));cart=[];renderCart();load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "pos", "POS", content)
# ═══════════════════════════════════════════════════════════════════════════════
# STOCK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/stock")
def stock_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/import" class="btn btn-orange">Import</a><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><div style="overflow-x:auto"><table><thead><tr><th>Code</th><th>Description</th><th>Cat</th><th>Qty</th><th>Cost</th><th>Price</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Item</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fcat" placeholder="Category" value="General"></div>
<input type="text" id="fdesc" placeholder="Description">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px"><input type="number" id="fqty" placeholder="Qty" value="0"><input type="number" id="fcost" placeholder="Cost" step="0.01"><input type="number" id="fprice" placeholder="Price" step="0.01"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var stock=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[];document.getElementById("msg").innerHTML="Loaded "+stock.length+" items";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error: "+e;document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";stock.forEach((s,i)=>{{if(q&&s.desc.toLowerCase().indexOf(q)<0&&s.code.toLowerCase().indexOf(q)<0)return;var qs=s.qty<=0?"color:var(--red)":s.qty<=5?"color:var(--orange)":"";h+="<tr><td>"+s.code+"</td><td>"+s.desc+"</td><td>"+s.category+"</td><td style='"+qs+"'>"+s.qty+"</td><td>R"+s.cost.toFixed(2)+"</td><td>R"+s.price.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='7' style='text-align:center;color:var(--muted);padding:30px'>No items</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fcat").value="General";document.getElementById("fdesc").value="";document.getElementById("fqty").value="0";document.getElementById("fcost").value="";document.getElementById("fprice").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var s=stock[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=s.id;document.getElementById("fcode").value=s.code||"";document.getElementById("fcat").value=s.category||"General";document.getElementById("fdesc").value=s.desc||"";document.getElementById("fqty").value=s.qty||0;document.getElementById("fcost").value=s.cost||0;document.getElementById("fprice").value=s.price||0;document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/stock",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,category:document.getElementById("fcat").value,description:document.getElementById("fdesc").value,qty:parseInt(document.getElementById("fqty").value)||0,cost:parseFloat(document.getElementById("fcost").value)||0,price:parseFloat(document.getElementById("fprice").value)||0}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}else alert("Error")}})}}
load();</script>'''
    return page(bid, "stock", "Stock", content)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/customers")
def customers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th>Balance</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Customer</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" customers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;var bal=c.balance||0;var bs=bal>0?"color:var(--red)":"";h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/customers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td style='"+bs+"'>R"+bal.toFixed(2)+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='6' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/customers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "customers", "Customers", content)

@app.route("/<bid>/customers/<cid>/history")
def customer_history(bid, cid):
    customers = db.select("customers", {"id": cid})
    if not customers: return redirect(f"/{bid}/customers")
    cust = customers[0]
    invoices = db.select("invoices", {"business_id": bid})
    cust_inv = [i for i in invoices if i.get("customer_id") == cid]
    total = sum(float(i.get("total",0) or 0) for i in cust_inv)
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>R{float(i.get("total",0)):,.2f}</td><td><span class="badge badge-{"green" if i.get("status")=="paid" else "orange"}">{i.get("status","")}</span></td></tr>' for i in cust_inv])
    content = f'''<a href="/{bid}/customers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(cust.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(cust.get("phone",""))} | {js_safe(cust.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(cust_inv)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{float(cust.get("balance",0)):,.0f}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Invoice</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "customers", cust.get("name","Customer"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/suppliers")
def suppliers_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><button class="btn btn-blue" onclick="showAdd()">+ Add</button></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><input type="text" id="q" placeholder="Search..." oninput="render()" style="margin-bottom:10px"><table><thead><tr><th>Code</th><th>Name</th><th>Phone</th><th>Email</th><th></th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title" id="mtitle">Add Supplier</div><input type="hidden" id="eid">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fcode" placeholder="Code"><input type="text" id="fname" placeholder="Name"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px"><input type="text" id="fphone" placeholder="Phone"><input type="email" id="femail" placeholder="Email"></div>
<div style="display:flex;gap:10px;margin-top:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/suppliers").then(r=>r.json()).then(d=>{{items=d||[];document.getElementById("msg").innerHTML=items.length+" suppliers";document.getElementById("msg").className="msg msg-ok";render()}}).catch(e=>{{document.getElementById("msg").innerHTML="Error";document.getElementById("msg").className="msg msg-err"}})}}
function render(){{var q=document.getElementById("q").value.toLowerCase();var h="";items.forEach((c,i)=>{{if(q&&c.name.toLowerCase().indexOf(q)<0)return;h+="<tr style='cursor:pointer' onclick='location.href=\"/"+BID+"/suppliers/"+c.id+"/history\"'><td>"+(c.code||"-")+"</td><td>"+c.name+"</td><td>"+(c.phone||"-")+"</td><td>"+(c.email||"-")+"</td><td><button class='btn btn-sm btn-ghost' onclick='event.stopPropagation();edit("+i+")'>Edit</button></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("mtitle").innerHTML="Add";document.getElementById("eid").value="";document.getElementById("fcode").value="";document.getElementById("fname").value="";document.getElementById("fphone").value="";document.getElementById("femail").value="";document.getElementById("modal").classList.add("show")}}
function edit(i){{var c=items[i];document.getElementById("mtitle").innerHTML="Edit";document.getElementById("eid").value=c.id;document.getElementById("fcode").value=c.code||"";document.getElementById("fname").value=c.name||"";document.getElementById("fphone").value=c.phone||"";document.getElementById("femail").value=c.email||"";document.getElementById("modal").classList.add("show")}}
function save(){{fetch("/api/"+BID+"/suppliers",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{id:document.getElementById("eid").value||null,code:document.getElementById("fcode").value,name:document.getElementById("fname").value,phone:document.getElementById("fphone").value,email:document.getElementById("femail").value}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "suppliers", "Suppliers", content)

@app.route("/<bid>/suppliers/<sid>/history")
def supplier_history(bid, sid):
    suppliers = db.select("suppliers", {"id": sid})
    if not suppliers: return redirect(f"/{bid}/suppliers")
    supp = suppliers[0]
    expenses = db.select("expenses", {"business_id": bid})
    supp_exp = [e for e in expenses if js_safe(e.get("supplier","")).lower() == js_safe(supp.get("name","")).lower()]
    total = sum(float(e.get("amount",0) or 0) for e in supp_exp)
    rows = "".join([f'<tr><td>{str(e.get("created_at",""))[:10]}</td><td>{js_safe(e.get("description",""))}</td><td>R{float(e.get("amount",0)):,.2f}</td></tr>' for e in supp_exp])
    content = f'''<a href="/{bid}/suppliers" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<h2 style="margin-bottom:5px">{js_safe(supp.get("name",""))}</h2><p style="color:var(--muted);margin-bottom:15px">{js_safe(supp.get("phone",""))} | {js_safe(supp.get("email",""))}</p>
<div class="stats"><div class="stat"><div class="stat-value">{len(supp_exp)}</div><div class="stat-label">Purchases</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total:,.0f}</div><div class="stat-label">Total Spent</div></div></div>
<div class="card"><table><thead><tr><th>Date</th><th>Description</th><th>Amount</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>'''
    return page(bid, "suppliers", supp.get("name","Supplier"), content)

# ═══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/invoices")
def invoices_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/invoices/new" class="btn btn-green">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/invoices").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" invoices";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(i=>{{var b=i.status=="paid"?"badge-green":i.status=="overdue"?"badge-red":"badge-orange";h+="<tr><td>"+i.number+"</td><td>"+(i.date||"").substring(0,10)+"</td><td>"+i.customer_name+"</td><td>R"+i.total.toFixed(2)+"</td><td><span class='badge "+b+"'>"+i.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "invoices", "Invoices", content)

@app.route("/<bid>/invoices/new")
def new_invoice(bid): return create_doc_page(bid, "Invoice", "INV", "invoices")

# ═══════════════════════════════════════════════════════════════════════════════
# QUOTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/quotes")
def quotes_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px"><div></div><a href="/{bid}/quotes/new" class="btn btn-purple">+ New</a></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>#</th><th>Date</th><th>Customer</th><th>Total</th><th>Status</th></tr></thead><tbody id="tbl"></tbody></table></div>
<script>var BID="{bid}";fetch("/api/"+BID+"/quotes").then(r=>r.json()).then(d=>{{var items=d||[];document.getElementById("msg").innerHTML=items.length+" quotes";document.getElementById("msg").className="msg msg-ok";var h="";items.forEach(q=>{{h+="<tr><td>"+q.number+"</td><td>"+(q.date||"").substring(0,10)+"</td><td>"+q.customer_name+"</td><td>R"+q.total.toFixed(2)+"</td><td><span class='badge badge-orange'>"+q.status+"</span></td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}});</script>'''
    return page(bid, "quotes", "Quotes", content)

@app.route("/<bid>/quotes/new")
def new_quote(bid): return create_doc_page(bid, "Quote", "QUO", "quotes")

def create_doc_page(bid, doc_type, prefix, table):
    active = "invoices" if doc_type == "Invoice" else "quotes"
    today = datetime.now().strftime('%Y-%m-%d')
    content = f'''<div class="card">
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:15px"><div><label style="color:var(--muted);font-size:11px">Number</label><input type="text" id="docNum" value="{prefix}001"></div><div><label style="color:var(--muted);font-size:11px">Date</label><input type="date" id="docDate" value="{today}"></div><div><label style="color:var(--muted);font-size:11px">Customer</label><select id="custSel"><option value="">Select...</option></select></div></div>
<h3 style="margin-bottom:10px">Items</h3><input type="text" id="q" placeholder="Search to add..." oninput="searchStock()"><div id="searchResults" style="max-height:150px;overflow-y:auto;margin-bottom:10px"></div><div id="lines"></div>
<div style="text-align:right;font-size:22px;font-weight:700;color:var(--green);padding:10px 0">Total: R <span id="total">0.00</span></div>
<button class="btn btn-green" onclick="saveDoc()">Save</button></div>
<script>var stock=[],customers=[],lines=[],BID="{bid}",docType="{table}";
fetch("/api/"+BID+"/stock").then(r=>r.json()).then(d=>{{stock=d||[]}});
fetch("/api/"+BID+"/customers").then(r=>r.json()).then(d=>{{customers=d||[];var sel="<option value=''>Select...</option>";customers.forEach(c=>{{sel+="<option value='"+c.id+"'>"+c.name+"</option>"}});document.getElementById("custSel").innerHTML=sel}});
function searchStock(){{var q=document.getElementById("q").value.toLowerCase();if(q.length<2){{document.getElementById("searchResults").innerHTML="";return}}var h="";stock.forEach((s,i)=>{{if(s.desc.toLowerCase().indexOf(q)>=0||s.code.toLowerCase().indexOf(q)>=0)h+="<div class='grid-item' style='margin-bottom:5px' onclick='addLine("+i+")'>"+s.desc+" - R"+s.price.toFixed(2)+"</div>"}});document.getElementById("searchResults").innerHTML=h||"<div style='color:var(--muted)'>No matches</div>"}}
function addLine(i){{var s=stock[i];lines.push({{id:s.id,desc:s.desc,price:s.price,qty:1}});document.getElementById("q").value="";document.getElementById("searchResults").innerHTML="";renderLines()}}
function renderLines(){{var h="<table><thead><tr><th>Item</th><th>Price</th><th>Qty</th><th>Total</th><th></th></tr></thead><tbody>";var tot=0;lines.forEach((l,i)=>{{var sub=l.price*l.qty;tot+=sub;h+="<tr><td>"+l.desc+"</td><td>R"+l.price.toFixed(2)+"</td><td><input type='number' value='"+l.qty+"' min='1' style='width:60px' onchange='updateQty("+i+",this.value)'></td><td>R"+sub.toFixed(2)+"</td><td><button class='btn btn-sm btn-red' onclick='lines.splice("+i+",1);renderLines()'>X</button></td></tr>"}});h+="</tbody></table>";document.getElementById("lines").innerHTML=lines.length?h:"<div style='color:var(--muted);text-align:center;padding:30px'>No items</div>";document.getElementById("total").innerHTML=tot.toFixed(2)}}
function updateQty(i,v){{lines[i].qty=parseInt(v)||1;renderLines()}}
function saveDoc(){{var sel=document.getElementById("custSel");var cn=sel.options[sel.selectedIndex]?sel.options[sel.selectedIndex].text:"Walk-in";if(lines.length==0)return alert("Add items");var tot=lines.reduce((a,l)=>a+l.price*l.qty,0);fetch("/api/"+BID+"/"+docType,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{number:document.getElementById("docNum").value,date:document.getElementById("docDate").value,customer_id:sel.value,customer_name:cn,items:lines,total:tot}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/"+docType}}else alert("Error")}})}}
renderLines();</script>'''
    return page(bid, active, f"New {doc_type}", content)
# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/expenses")
def expenses_page(bid):
    content = f'''<div style="display:flex;justify-content:space-between;margin-bottom:15px;flex-wrap:wrap;gap:10px"><div></div><div style="display:flex;gap:10px"><a href="/{bid}/expenses/scan" class="btn btn-orange">Scan</a><button class="btn btn-red" onclick="showAdd()">+ Add</button></div></div>
<div id="msg" class="msg msg-info">Loading...</div>
<div class="card"><table><thead><tr><th>Date</th><th>Supplier</th><th>Description</th><th>Amount</th><th>VAT</th></tr></thead><tbody id="tbl"></tbody></table></div>
<div class="modal" id="modal"><div class="modal-box"><div class="modal-title">Add Expense</div>
<input type="text" id="fsupplier" placeholder="Supplier"><input type="text" id="fdesc" placeholder="Description"><input type="number" id="famount" placeholder="Amount (incl VAT)" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="fvat" checked> Includes 15% VAT</label>
<div style="display:flex;gap:10px"><button class="btn btn-blue" onclick="save()">Save</button><button class="btn btn-ghost" onclick="document.getElementById('modal').classList.remove('show')">Cancel</button></div></div></div>
<script>var items=[],BID="{bid}";
function load(){{fetch("/api/"+BID+"/expenses").then(r=>r.json()).then(d=>{{items=d||[];var tot=items.reduce((a,e)=>a+e.amount,0);document.getElementById("msg").innerHTML=items.length+" expenses | R"+tot.toFixed(2);document.getElementById("msg").className="msg msg-ok";render()}})}}
function render(){{var h="";items.forEach(e=>{{h+="<tr><td>"+(e.date||"-")+"</td><td>"+e.supplier+"</td><td>"+e.description+"</td><td>R"+e.amount.toFixed(2)+"</td><td>R"+e.vat.toFixed(2)+"</td></tr>"}});document.getElementById("tbl").innerHTML=h||"<tr><td colspan='5' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}}
function showAdd(){{document.getElementById("modal").classList.add("show")}}
function save(){{var amt=parseFloat(document.getElementById("famount").value)||0;var vat=document.getElementById("fvat").checked?amt*15/115:0;fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("fsupplier").value,description:document.getElementById("fdesc").value,amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{document.getElementById("modal").classList.remove("show");load()}}}})}}
load();</script>'''
    return page(bid, "expenses", "Expenses", content)

@app.route("/<bid>/expenses/scan")
def scan_receipt(bid):
    content = f'''<a href="/{bid}/expenses" class="btn btn-ghost" style="margin-bottom:15px">← Back</a>
<div class="card"><h3 style="margin-bottom:10px">Scan Receipt</h3><p style="color:var(--muted);margin-bottom:15px">AI extracts supplier, description, amount</p>
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:15px"><button class="btn btn-orange" onclick="startCamera()">Camera</button><span style="color:var(--muted);align-self:center">or</span><input type="file" id="fileInput" accept="image/*" onchange="handleFile(this)"></div>
<video id="video" autoplay playsinline style="display:none;width:100%;max-width:350px;border-radius:10px;background:#000"></video>
<button id="captureBtn" class="btn btn-green" style="display:none;margin-top:10px" onclick="capture()">Snap</button>
<canvas id="canvas" style="display:none"></canvas><img id="preview" style="display:none;max-width:100%;border-radius:10px;margin-top:10px">
<div id="processing" class="msg msg-info" style="display:none;margin-top:10px">Reading...</div></div>
<div class="card" id="resultCard" style="display:none"><h3 style="margin-bottom:10px">Details</h3>
<input type="text" id="rSupplier" placeholder="Supplier"><input type="text" id="rDesc" placeholder="Description"><input type="number" id="rAmount" placeholder="Amount" step="0.01">
<label style="display:block;margin:10px 0"><input type="checkbox" id="rVat" checked> 15% VAT</label>
<button class="btn btn-green" onclick="saveExpense()">Save</button></div>
<script>var BID="{bid}",stream=null;
function startCamera(){{navigator.mediaDevices.getUserMedia({{video:{{facingMode:"environment"}}}}).then(s=>{{stream=s;document.getElementById("video").srcObject=s;document.getElementById("video").style.display="block";document.getElementById("captureBtn").style.display="inline-block"}}).catch(e=>alert("Camera: "+e.message))}}
function capture(){{var v=document.getElementById("video"),c=document.getElementById("canvas");c.width=v.videoWidth;c.height=v.videoHeight;c.getContext("2d").drawImage(v,0,0);var d=c.toDataURL("image/jpeg",0.8);if(stream)stream.getTracks().forEach(t=>t.stop());document.getElementById("video").style.display="none";document.getElementById("captureBtn").style.display="none";document.getElementById("preview").src=d;document.getElementById("preview").style.display="block";processAI(d)}}
function handleFile(input){{if(input.files&&input.files[0]){{var r=new FileReader();r.onload=e=>{{document.getElementById("preview").src=e.target.result;document.getElementById("preview").style.display="block";processAI(e.target.result)}};r.readAsDataURL(input.files[0])}}}}
function processAI(d){{document.getElementById("processing").style.display="block";document.getElementById("resultCard").style.display="none";fetch("/api/"+BID+"/scan-receipt",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{image:d}})}}).then(r=>r.json()).then(x=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";if(x.supplier)document.getElementById("rSupplier").value=x.supplier;if(x.description)document.getElementById("rDesc").value=x.description;if(x.amount)document.getElementById("rAmount").value=x.amount;if(x.error)alert(x.error)}}).catch(e=>{{document.getElementById("processing").style.display="none";document.getElementById("resultCard").style.display="block";alert("Error: "+e)}})}}
function saveExpense(){{var amt=parseFloat(document.getElementById("rAmount").value)||0;var vat=document.getElementById("rVat").checked?amt*15/115:0;if(!document.getElementById("rSupplier").value)return alert("Supplier?");if(!amt)return alert("Amount?");fetch("/api/"+BID+"/expenses",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{supplier:document.getElementById("rSupplier").value,description:document.getElementById("rDesc").value||"Receipt",amount:amt,vat:vat}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert("Saved!");location.href="/"+BID+"/expenses"}}else alert("Error")}})}}</script>'''
    return page(bid, "expenses", "Scan Receipt", content)

# ═══════════════════════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/reports")
def reports_page(bid):
    content = '''<div class="report-grid">
<a href="/{0}/reports/sales" class="report-card"><h3>Sales</h3><p>Invoices & totals</p></a>
<a href="/{0}/reports/stock" class="report-card"><h3>Stock</h3><p>Levels & alerts</p></a>
<a href="/{0}/reports/customers" class="report-card"><h3>Customers</h3><p>Balances</p></a>
<a href="/{0}/reports/suppliers" class="report-card"><h3>Suppliers</h3><p>Contact list</p></a>
<a href="/{0}/reports/profit" class="report-card"><h3>P&L</h3><p>Income vs expenses</p></a>
<a href="/{0}/reports/vat" class="report-card"><h3>VAT</h3><p>In vs out</p></a>
<a href="/{0}/reports/tb" class="report-card"><h3>Trial Balance</h3><p>All accounts</p></a></div>'''.format(bid)
    return page(bid, "reports", "Reports", content)

@app.route("/<bid>/reports/sales")
def report_sales(bid):
    invoices = db.select("invoices", {"business_id": bid})
    total = sum(float(i.get("total",0) or 0) for i in invoices)
    paid = sum(float(i.get("total",0) or 0) for i in invoices if i.get("status")=="paid")
    rows = "".join([f'<tr><td>{js_safe(i.get("number",""))}</td><td>{str(i.get("date",""))[:10]}</td><td>{js_safe(i.get("customer_name",""))}</td><td>R{float(i.get("total",0)):,.2f}</td></tr>' for i in invoices[:20]])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{total:,.0f}</div><div class="stat-label">Total</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{paid:,.0f}</div><div class="stat-label">Paid</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total-paid:,.0f}</div><div class="stat-label">Outstanding</div></div></div>
<div class="card"><table><thead><tr><th>Inv</th><th>Date</th><th>Customer</th><th>Total</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Sales Report", content)

@app.route("/<bid>/reports/stock")
def report_stock(bid):
    stock = db.select("stock", {"business_id": bid})
    value = sum(float(s.get("cost",0) or 0) * int(s.get("qty",0) or 0) for s in stock)
    low = [s for s in stock if 0 < int(s.get("qty",0) or 0) <= 5]
    out = [s for s in stock if int(s.get("qty",0) or 0) <= 0]
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(stock)}</div><div class="stat-label">Items</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{value:,.0f}</div><div class="stat-label">Value</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{len(low)}</div><div class="stat-label">Low</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">{len(out)}</div><div class="stat-label">Out</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Stock Report", content)

@app.route("/<bid>/reports/customers")
def report_customers(bid):
    customers = db.select("customers", {"business_id": bid})
    total_bal = sum(float(c.get("balance",0) or 0) for c in customers)
    owing = len([c for c in customers if float(c.get("balance",0) or 0) > 0])
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(customers)}</div><div class="stat-label">Customers</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{total_bal:,.0f}</div><div class="stat-label">Total Owing</div></div><div class="stat"><div class="stat-value" style="color:var(--orange)">{owing}</div><div class="stat-label">With Balance</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Customer Report", content)

@app.route("/<bid>/reports/suppliers")
def report_suppliers(bid):
    suppliers = db.select("suppliers", {"business_id": bid})
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(suppliers)}</div><div class="stat-label">Suppliers</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Supplier Report", content)

@app.route("/<bid>/reports/profit")
def report_profit(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    income = sum(float(i.get("total",0) or 0) for i in invoices)
    expense = sum(float(e.get("amount",0) or 0) for e in expenses)
    profit = income - expense
    pc = "var(--green)" if profit >= 0 else "var(--red)"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--green)">R{income:,.0f}</div><div class="stat-label">Income</div></div><div class="stat"><div class="stat-value" style="color:var(--red)">R{expense:,.0f}</div><div class="stat-label">Expenses</div></div><div class="stat"><div class="stat-value" style="color:{pc}">R{profit:,.0f}</div><div class="stat-label">Profit</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Profit & Loss", content)

@app.route("/<bid>/reports/vat")
def report_vat(bid):
    invoices = db.select("invoices", {"business_id": bid})
    expenses = db.select("expenses", {"business_id": bid})
    sales = sum(float(i.get("total",0) or 0) for i in invoices)
    vat_out = sales * 15 / 115
    vat_in = sum(float(e.get("vat",0) or 0) for e in expenses)
    vat_due = vat_out - vat_in
    dc = "var(--red)" if vat_due > 0 else "var(--green)"
    dl = "Pay SARS" if vat_due > 0 else "Refund"
    content = f'''<div class="stats"><div class="stat"><div class="stat-value" style="color:var(--blue)">R{vat_out:,.0f}</div><div class="stat-label">Output</div></div><div class="stat"><div class="stat-value" style="color:var(--green)">R{vat_in:,.0f}</div><div class="stat-label">Input</div></div><div class="stat"><div class="stat-value" style="color:{dc}">R{abs(vat_due):,.0f}</div><div class="stat-label">{dl}</div></div></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "VAT Report", content)

@app.route("/<bid>/reports/tb")
def report_tb(bid):
    journal = db.select("journal", {"business_id": bid})
    accounts = {}
    for j in journal:
        acc = j.get("account", "Unknown")
        if acc not in accounts: accounts[acc] = {"dr": 0, "cr": 0}
        accounts[acc]["dr"] += float(j.get("debit", 0) or 0)
        accounts[acc]["cr"] += float(j.get("credit", 0) or 0)
    total_dr = sum(a["dr"] for a in accounts.values())
    total_cr = sum(a["cr"] for a in accounts.values())
    rows = "".join([f'<tr><td>{acc}</td><td style="text-align:right">{"R"+str(int(v["dr"])) if v["dr"] else "-"}</td><td style="text-align:right">{"R"+str(int(v["cr"])) if v["cr"] else "-"}</td></tr>' for acc, v in sorted(accounts.items())])
    balanced = abs(total_dr - total_cr) < 0.01
    content = f'''<div class="stats"><div class="stat"><div class="stat-value">{len(accounts)}</div><div class="stat-label">Accounts</div></div><div class="stat"><div class="stat-value" style="color:var(--blue)">R{total_dr:,.0f}</div><div class="stat-label">Debits</div></div><div class="stat"><div class="stat-value" style="color:var(--purple)">R{total_cr:,.0f}</div><div class="stat-label">Credits</div></div><div class="stat"><div class="stat-value" style="color:{"var(--green)" if balanced else "var(--red)"}">{"OK" if balanced else "ERR"}</div><div class="stat-label">Balance</div></div></div>
<div class="card"><table><thead><tr><th>Account</th><th style="text-align:right">Debit</th><th style="text-align:right">Credit</th></tr></thead><tbody>{rows or "<tr><td colspan='3' style='text-align:center;color:var(--muted);padding:30px'>None</td></tr>"}</tbody></table></div>
<a href="/{bid}/reports" class="btn btn-ghost" style="margin-top:15px">← Back</a>'''
    return page(bid, "reports", "Trial Balance", content)

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/<bid>/import")
def import_page(bid):
    content = f'''<div class="card"><h3 style="margin-bottom:15px">Import Data</h3><p style="color:var(--muted);margin-bottom:15px">Paste JSON with stock, customers, suppliers arrays</p>
<textarea id="jsonData" rows="10" placeholder='{{"stock":[...],"customers":[...],"suppliers":[...]}}'></textarea>
<button class="btn btn-blue" onclick="doImport()">Import</button><div id="result" style="margin-top:15px"></div></div>
<script>var BID="{bid}";function doImport(){{try{{var d=JSON.parse(document.getElementById("jsonData").value);fetch("/api/"+BID+"/import",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(d)}}).then(r=>r.json()).then(x=>{{document.getElementById("result").innerHTML="<div class='msg msg-ok'>Imported: "+x.stock+" stock, "+x.customers+" customers, "+x.suppliers+" suppliers</div>"}})}catch(e){{document.getElementById("result").innerHTML="<div class='msg msg-err'>Invalid JSON</div>"}}}}</script>'''
    return page(bid, "import", "Import", content)

# ═══════════════════════════════════════════════════════════════════════════════
# APIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/<bid>/stock", methods=["GET"])
def api_get_stock(bid):
    items = db.select("stock", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"desc":s.get("description",""),"category":s.get("category",""),"qty":int(s.get("qty",0) or 0),"cost":float(s.get("cost",0) or 0),"price":float(s.get("price",0) or 0)} for s in items])

@app.route("/api/<bid>/stock", methods=["POST"])
def api_post_stock(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"description":d.get("description",""),"category":d.get("category","General"),"qty":d.get("qty",0),"cost":d.get("cost",0),"price":d.get("price",0)}
    if d.get("id"):
        return jsonify({"success": db.update("stock", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("stock", rec)})

@app.route("/api/<bid>/customers", methods=["GET"])
def api_get_customers(bid):
    items = db.select("customers", {"business_id": bid})
    return jsonify([{"id":c["id"],"code":c.get("code",""),"name":c.get("name",""),"phone":c.get("phone",""),"email":c.get("email",""),"balance":float(c.get("balance",0) or 0)} for c in items])

@app.route("/api/<bid>/customers", methods=["POST"])
def api_post_customers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("customers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    rec["balance"] = 0
    return jsonify({"success": db.insert("customers", rec)})

@app.route("/api/<bid>/suppliers", methods=["GET"])
def api_get_suppliers(bid):
    items = db.select("suppliers", {"business_id": bid})
    return jsonify([{"id":s["id"],"code":s.get("code",""),"name":s.get("name",""),"phone":s.get("phone",""),"email":s.get("email","")} for s in items])

@app.route("/api/<bid>/suppliers", methods=["POST"])
def api_post_suppliers(bid):
    d = request.get_json()
    rec = {"business_id":bid,"code":d.get("code",""),"name":d.get("name",""),"phone":d.get("phone",""),"email":d.get("email","")}
    if d.get("id"):
        return jsonify({"success": db.update("suppliers", d["id"], rec)})
    rec["id"] = str(uuid.uuid4())
    return jsonify({"success": db.insert("suppliers", rec)})

@app.route("/api/<bid>/invoices", methods=["GET"])
def api_get_invoices(bid):
    items = db.select("invoices", {"business_id": bid})
    return jsonify([{"id":i["id"],"number":i.get("number",""),"date":i.get("date",""),"customer_id":i.get("customer_id",""),"customer_name":i.get("customer_name",""),"total":float(i.get("total",0) or 0),"status":i.get("status","draft")} for i in items])

@app.route("/api/<bid>/invoices", methods=["POST"])
def api_post_invoices(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("invoices", rec)})

@app.route("/api/<bid>/quotes", methods=["GET"])
def api_get_quotes(bid):
    items = db.select("quotes", {"business_id": bid})
    return jsonify([{"id":q["id"],"number":q.get("number",""),"date":q.get("date",""),"customer_id":q.get("customer_id",""),"customer_name":q.get("customer_name",""),"total":float(q.get("total",0) or 0),"status":q.get("status","draft")} for q in items])

@app.route("/api/<bid>/quotes", methods=["POST"])
def api_post_quotes(bid):
    d = request.get_json()
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"number":d.get("number",""),"date":d.get("date",""),"customer_id":d.get("customer_id",""),"customer_name":d.get("customer_name",""),"items":json.dumps(d.get("items",[])),"total":d.get("total",0),"status":"draft"}
    return jsonify({"success": db.insert("quotes", rec)})

@app.route("/api/<bid>/expenses", methods=["GET"])
def api_get_expenses(bid):
    items = db.select("expenses", {"business_id": bid})
    return jsonify([{"id":e["id"],"date":e.get("date",e.get("created_at",""))[:10],"supplier":e.get("supplier",""),"description":e.get("description",""),"amount":float(e.get("amount",0) or 0),"vat":float(e.get("vat",0) or 0)} for e in items])

@app.route("/api/<bid>/expenses", methods=["POST"])
def api_post_expenses(bid):
    d = request.get_json()
    today = datetime.now().isoformat()[:10]
    rec = {"id":str(uuid.uuid4()),"business_id":bid,"date":today,"supplier":d.get("supplier",""),"description":d.get("description",""),"amount":d.get("amount",0),"vat":d.get("vat",0),"category":d.get("category","Expenses")}
    if db.insert("expenses", rec):
        amt, vat = float(d.get("amount",0)), float(d.get("vat",0))
        net = amt - vat
        desc = f"Expense: {d.get('supplier','')} - {d.get('description','')}"
        post_journal(bid, today, desc, d.get("category","Expenses"), net, 0)
        post_journal(bid, today, desc, "VAT Input", vat, 0)
        post_journal(bid, today, desc, "Cash/Bank", 0, amt)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route("/api/<bid>/sale", methods=["POST"])
def api_sale(bid):
    d = request.get_json()
    items = d.get("items", [])
    total = d.get("total", 0)
    method = d.get("method", "cash")
    inv_count = len(db.select("invoices", {"business_id": bid}))
    cust_id = d.get("customer_id", "")
    cust_name = "Walk-in"
    if cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs: cust_name = custs[0].get("name", "Unknown")
    inv = {"id":str(uuid.uuid4()),"business_id":bid,"number":f"INV{inv_count+1:04d}","date":datetime.now().isoformat(),"customer_id":cust_id,"customer_name":cust_name,"items":json.dumps(items),"total":total,"status":"paid","payment_method":method}
    db.insert("invoices", inv)
    for item in items:
        sl = db.select("stock", {"id": item["id"]})
        if sl:
            new_qty = int(sl[0].get("qty", 0)) - int(item.get("qty", 1))
            db.update("stock", item["id"], {"qty": max(0, new_qty)})
    if method == "account" and cust_id:
        custs = db.select("customers", {"id": cust_id})
        if custs:
            new_bal = float(custs[0].get("balance", 0)) + total
            db.update("customers", cust_id, {"balance": new_bal})
    today = datetime.now().isoformat()[:10]
    vat = total * 15 / 115
    net = total - vat
    desc = f"Sale {inv['number']} - {cust_name}"
    if method == "account":
        post_journal(bid, today, desc, "Debtors", total, 0)
    else:
        post_journal(bid, today, desc, "Cash/Bank", total, 0)
    post_journal(bid, today, desc, "Sales", 0, net)
    post_journal(bid, today, desc, "VAT Output", 0, vat)
    return jsonify({"success": True})

@app.route("/api/<bid>/scan-receipt", methods=["POST"])
def api_scan_receipt(bid):
    try:
        d = request.get_json()
        image_data = d.get("image", "")
        if not image_data: return jsonify({"error": "No image"})
        if "," in image_data: image_data = image_data.split(",")[1]
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key: return jsonify({"error": "No API key", "supplier": "", "description": "", "amount": ""})
        response = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": api_key, "content-type": "application/json", "anthropic-version": "2023-06-01"}, json={"model": "claude-sonnet-4-20250514", "max_tokens": 500, "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_data}}, {"type": "text", "text": "Extract: 1) Supplier name, 2) Brief description, 3) Total in Rands. Reply ONLY JSON: {\"supplier\": \"name\", \"description\": \"what\", \"amount\": 123.45}"}]}]}, timeout=30)
        if response.status_code == 200:
            result = response.json()
            text = result.get("content", [{}])[0].get("text", "{}")
            match = re.search(r'\{[^}]+\}', text)
            if match:
                data = json.loads(match.group())
                return jsonify({"supplier": data.get("supplier", ""), "description": data.get("description", ""), "amount": float(data.get("amount", 0))})
        return jsonify({"error": "Could not parse", "supplier": "", "description": "", "amount": ""})
    except Exception as e:
        return jsonify({"error": str(e), "supplier": "", "description": "", "amount": ""})

@app.route("/api/<bid>/import", methods=["POST"])
def api_import(bid):
    try:
        data = request.get_json()
        source = data.get("fulltech", data.get("hardware", data))
        if not source: source = data
        sc, cc, spc = 0, 0, 0
        for item in source.get("stock", []):
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"description":str(item.get("description",item.get("name","")))[:200],"category":str(item.get("category","General"))[:50],"qty":int(item.get("qty",0) or 0),"cost":float(item.get("cost",0) or 0),"price":float(item.get("price",item.get("sell",0)) or 0)}
            if db.insert("stock", rec): sc += 1
        for item in source.get("customers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100],"balance":float(item.get("balance",0) or 0)}
            if db.insert("customers", rec): cc += 1
        for item in source.get("suppliers", []):
            name = str(item.get("name","")).strip()
            if not name or len(name) < 3: continue
            rec = {"id":str(uuid.uuid4()),"business_id":bid,"code":str(item.get("code",""))[:50],"name":name[:100],"phone":str(item.get("phone",""))[:20],"email":str(item.get("email",""))[:100]}
            if db.insert("suppliers", rec): spc += 1
        return jsonify({"success":True,"stock":sc,"customers":cc,"suppliers":spc})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "version": "10"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
