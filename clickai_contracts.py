# -*- coding: utf-8 -*-
# CLICK AI - HR & EMPLOYMENT CONTRACTS MODULE
# Hub page at /hr, contracts at /contracts, HR docs at /hr-documents
# Registration: from clickai_contracts import register_contract_routes

import json, logging, uuid
from datetime import datetime, timedelta
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)

HR_DOC_TYPES = {
    "written_warning":       {"label":"Written Warning",          "icon":"⚠️","color":"#f59e0b","cat":"discipline"},
    "final_warning":         {"label":"Final Written Warning",    "icon":"🔴","color":"#ef4444","cat":"discipline"},
    "hearing_notice":        {"label":"Notice to Attend Hearing", "icon":"📋","color":"#3b82f6","cat":"discipline"},
    "suspension":            {"label":"Suspension Letter",        "icon":"⏸️","color":"#8b5cf6","cat":"discipline"},
    "hearing_outcome":       {"label":"Hearing Outcome",          "icon":"⚖️","color":"#0ea5e9","cat":"discipline"},
    "dismissal":             {"label":"Dismissal Letter",         "icon":"❌","color":"#dc2626","cat":"discipline"},
    "resignation_acceptance":{"label":"Resignation Acceptance",   "icon":"👋","color":"#6b7280","cat":"general"},
    "promotion":             {"label":"Promotion Letter",         "icon":"⬆️","color":"#10b981","cat":"general"},
    "salary_increase":       {"label":"Salary Increase Letter",   "icon":"💰","color":"#10b981","cat":"general"},
}

def register_contract_routes(app, db, login_required, Auth, render_page, generate_id, money, safe_string, now, today, RecordFactory):
    def _get_emps(biz_id):
        try: return db.get("employees",{"business_id":biz_id}) or [] if biz_id else []
        except: return []
    def _emp_opts(emps, sel=""):
        o='<option value="">-- Select Employee --</option>'
        for e in sorted(emps,key=lambda x:x.get("name","")):
            s="selected" if e.get("id")==sel else ""
            o+=f'<option value="{e.get("id")}" data-name="{safe_string(e.get("name",""))}" data-idnum="{safe_string(e.get("id_number",""))}" data-pos="{safe_string(e.get("position",""))}" data-sal="{e.get("basic_salary",0)}" data-addr="{safe_string(e.get("address",""))}" {s}>{safe_string(e.get("name",""))}</option>'
        return o
    _autofill_js='''<script>function fillFromEmp(){var s=document.getElementById('empSelect'),o=s.options[s.selectedIndex];if(!o||!o.value)return;var m=function(id,k){var el=document.getElementById(id);if(el)el.value=o.dataset[k]||'';};m('fldName','name');m('fldIdNum','idnum');m('fldPos','pos');m('fldSal','sal');m('fldAddr','addr');}</script>'''
    def _emp_json(emps):
        o={}
        for e in emps:
            o[e.get("id","")]={k:e.get(k,"") for k in ("name","id_number","position","address","phone","email")}
            o[e.get("id","")]["basic_salary"]=float(e.get("basic_salary",0))
            o[e.get("id","")]["hourly_rate"]=float(e.get("hourly_rate",0))
            o[e.get("id","")]["pay_type"]=e.get("pay_type","monthly")
        return json.dumps(o)

    # === HR HUB ===
    @app.route("/hr")
    @login_required
    def hr_hub():
        user=Auth.get_current_user();biz=Auth.get_current_business();biz_id=biz.get("id") if biz else None
        cc=0;dc=0
        try: cc=len(db.get("employment_contracts",{"business_id":biz_id}) or [])
        except: pass
        try: dc=len(db.get("hr_documents",{"business_id":biz_id}) or [])
        except: pass
        content=f'''
        <h2 style="margin-bottom:5px;">HR &amp; Documents</h2>
        <p style="color:var(--text-muted);margin-bottom:25px;">Employment contracts, disciplinary process, and staff admin</p>
        <h3 style="margin:20px 0 10px;color:var(--text-muted);">📝 Employment</h3>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer;border-left:4px solid #10b981;" onclick="window.location='/contracts'">
                <h3 style="margin:0 0 5px;font-size:16px;">📝 Employment Contracts</h3>
                <p style="color:var(--text-muted);font-size:13px;">{cc} contract{"s" if cc!=1 else ""}</p>
                <p style="color:var(--text-muted);font-size:12px;margin-top:8px;">Full SA BCEA-compliant contracts</p>
            </div>
            <div class="card" style="cursor:pointer;border-left:4px solid #10b981;" onclick="window.location='/contract/new'">
                <h3 style="margin:0 0 5px;font-size:16px;">+ New Contract</h3>
                <p style="color:var(--text-muted);font-size:12px;">Auto-fills from employee records</p>
            </div>
        </div>
        <h3 style="margin:30px 0 10px;color:var(--text-muted);">⚖️ Disciplinary Process</h3>
        <p style="color:var(--text-muted);font-size:12px;margin-bottom:12px;">Correct sequence: Warning → Final Warning → Hearing Notice → Hearing → Outcome</p>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer;border-left:4px solid #f59e0b;" onclick="window.location='/hr-document/new/written_warning'"><h3 style="margin:0;font-size:15px;">⚠️ Written Warning</h3><p style="color:var(--text-muted);font-size:12px;">First formal warning</p></div>
            <div class="card" style="cursor:pointer;border-left:4px solid #ef4444;" onclick="window.location='/hr-document/new/final_warning'"><h3 style="margin:0;font-size:15px;">🔴 Final Written Warning</h3><p style="color:var(--text-muted);font-size:12px;">Last chance before hearing</p></div>
            <div class="card" style="cursor:pointer;border-left:4px solid #3b82f6;" onclick="window.location='/hr-document/new/hearing_notice'"><h3 style="margin:0;font-size:15px;">📋 Notice to Attend Hearing</h3><p style="color:var(--text-muted);font-size:12px;">Formal charges &amp; rights</p></div>
            <div class="card" style="cursor:pointer;border-left:4px solid #8b5cf6;" onclick="window.location='/hr-document/new/suspension'"><h3 style="margin:0;font-size:15px;">⏸️ Suspension Letter</h3><p style="color:var(--text-muted);font-size:12px;">With or without pay</p></div>
            <div class="card" style="cursor:pointer;border-left:4px solid #0ea5e9;" onclick="window.location='/hr-document/new/hearing_outcome'"><h3 style="margin:0;font-size:15px;">⚖️ Hearing Outcome</h3><p style="color:var(--text-muted);font-size:12px;">Finding, sanction, appeal</p></div>
            <div class="card" style="cursor:pointer;border-left:4px solid #dc2626;" onclick="window.location='/hr-document/new/dismissal'"><h3 style="margin:0;font-size:15px;">❌ Dismissal Letter</h3><p style="color:var(--text-muted);font-size:12px;">After hearing or gross misconduct</p></div>
        </div>
        <h3 style="margin:30px 0 10px;color:var(--text-muted);">📄 General HR</h3>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer;border-left:4px solid #6b7280;" onclick="window.location='/hr-document/new/resignation_acceptance'"><h3 style="margin:0;font-size:15px;">👋 Resignation Acceptance</h3><p style="color:var(--text-muted);font-size:12px;">Acknowledge resignation</p></div>
            <div class="card" style="cursor:pointer;border-left:4px solid #10b981;" onclick="window.location='/hr-document/new/promotion'"><h3 style="margin:0;font-size:15px;">⬆️ Promotion Letter</h3><p style="color:var(--text-muted);font-size:12px;">New role &amp; salary</p></div>
            <div class="card" style="cursor:pointer;border-left:4px solid #10b981;" onclick="window.location='/hr-document/new/salary_increase'"><h3 style="margin:0;font-size:15px;">💰 Salary Increase</h3><p style="color:var(--text-muted);font-size:12px;">Annual or performance</p></div>
        </div>
        <h3 style="margin:30px 0 10px;color:var(--text-muted);">🗂️ All HR Documents ({dc})</h3>
        <div class="card" style="padding:0;"><a href="/hr-documents" style="display:block;padding:15px;color:var(--primary);text-decoration:none;font-weight:600;">View All HR Documents →</a></div>
        '''
        return render_page("HR & Documents",content,user,"hr")

    # === HR DOCUMENTS LIST ===
    @app.route("/hr-documents")
    @login_required
    def hr_docs_list():
        user=Auth.get_current_user();biz=Auth.get_current_business();biz_id=biz.get("id") if biz else None
        try: docs=sorted(db.get("hr_documents",{"business_id":biz_id}) or [],key=lambda x:x.get("created_at",""),reverse=True)
        except: docs=[]
        rows=""
        for d in docs:
            dt=HR_DOC_TYPES.get(d.get("doc_type",""),{})
            rows+=f'<tr style="cursor:pointer;" onclick="window.location=\'/hr-document/{d.get("id")}\'"><td>{dt.get("icon","📄")} {dt.get("label",d.get("doc_type","-"))}</td><td><strong>{safe_string(d.get("employee_name","-"))}</strong></td><td>{d.get("document_date","-")}</td><td>{safe_string((d.get("subject","") or "")[:60])}</td></tr>'
        content=f'''<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;">All HR Documents ({len(docs)})</h3><a href="/hr" class="btn btn-secondary">← HR Hub</a></div>
        <div style="margin-bottom:15px;"><input type="text" id="shr" placeholder="Search..." oninput="filterTable('shr','ht')" style="width:100%;padding:10px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);"></div>
        <table class="table" id="ht"><thead><tr><th>Type</th><th>Employee</th><th>Date</th><th>Subject</th></tr></thead><tbody>{rows or "<tr><td colspan='4' style='text-align:center;color:var(--text-muted)'>No documents yet</td></tr>"}</tbody></table></div>'''
        return render_page("HR Documents",content,user,"hr")

    # === NEW HR DOCUMENT ===
    @app.route("/hr-document/new/<doc_type>",methods=["GET","POST"])
    @login_required
    def hr_doc_new(doc_type):
        if doc_type not in HR_DOC_TYPES: return redirect("/hr")
        user=Auth.get_current_user();biz=Auth.get_current_business();biz_id=biz.get("id") if biz else None
        dt=HR_DOC_TYPES[doc_type]
        if request.method=="POST": return _save_hr_doc(db,biz_id,user,doc_type,now)
        emps=_get_emps(biz_id); eo=_emp_opts(emps)
        bn=biz.get("name","") if biz else ""; ba=biz.get("address","") if biz else ""
        ff=_form_fields(doc_type,{},safe_string,today)
        content=f'''{_autofill_js}<div class="card"><div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;"><span style="font-size:30px;">{dt["icon"]}</span><div><h3 style="margin:0;">New {dt["label"]}</h3><p style="color:var(--text-muted);margin:3px 0 0;font-size:13px;">Fill in details, save, then print from view page.</p></div></div>
        <form method="POST"><input type="hidden" name="employer_name" value="{safe_string(bn)}"><input type="hidden" name="employer_address" value="{safe_string(ba)}">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;margin-bottom:20px;">
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Employee</label><select id="empSelect" name="employee_id" onchange="fillFromEmp()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">{eo}</select></div>
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Employee Name *</label><input type="text" name="employee_name" id="fldName" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Position</label><input type="text" name="position" id="fldPos" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;">
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Date</label><input type="date" name="document_date" value="{today()}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Subject</label><input type="text" name="subject" placeholder="Brief reference..." style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
        </div><hr style="border:none;border-top:1px solid var(--border);margin:20px 0;">{ff}
        <div style="display:flex;gap:10px;margin-top:25px;"><button type="submit" class="btn btn-primary" style="flex:1;padding:14px;">Create {dt["label"]}</button><a href="/hr" class="btn btn-secondary" style="padding:14px;">Cancel</a></div></form></div>'''
        return render_page(f"New {dt['label']}",content,user,"hr")

    # === VIEW HR DOCUMENT ===
    @app.route("/hr-document/<doc_id>")
    @login_required
    def hr_doc_view(doc_id):
        user=Auth.get_current_user();doc=db.get_one("hr_documents",doc_id)
        if not doc: return redirect("/hr-documents")
        dt=HR_DOC_TYPES.get(doc.get("doc_type",""),{"label":"Document","icon":"📄","color":"#666"})
        bn=safe_string(doc.get("employer_name",""));ba=safe_string(doc.get("employer_address",""))
        en=safe_string(doc.get("employee_name",""));pos=safe_string(doc.get("position",""))
        dd=doc.get("document_date","");subj=safe_string(doc.get("subject",""))
        body=_letter_body(doc,safe_string,money)
        content=f'''
        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <a href="/hr-documents" style="color:var(--text-muted);">← HR Documents</a>
            <div style="display:flex;gap:10px;"><a href="/hr-document/{doc_id}/edit" class="btn btn-secondary">✏️ Edit</a><button class="btn btn-secondary" onclick="prt()">🖨️ Print</button><button class="btn btn-secondary" style="color:var(--red);" onclick="del_()">🗑️</button></div>
        </div>
        <div class="card" id="pa" style="background:white;color:#333;padding:0;overflow:hidden;">
            <div style="background:{dt["color"]};color:white;padding:12px 30px;text-align:center;"><h1 style="margin:0;font-size:18px;font-weight:700;letter-spacing:1px;">{dt["label"].upper()}</h1></div>
            <div style="padding:25px 30px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:20px;"><div><p style="font-size:14px;font-weight:700;margin:0;">{bn}</p>{f'<p style="font-size:11px;color:#666;margin:3px 0;">{ba}</p>' if ba else ''}</div><div style="text-align:right;"><p style="font-size:12px;color:#666;margin:0;">Date: <strong>{dd}</strong></p>{f'<p style="font-size:11px;color:#666;">Ref: {subj}</p>' if subj else ''}</div></div>
                <div style="background:#f8fafc;padding:12px 15px;border-radius:8px;margin-bottom:25px;border-left:4px solid {dt["color"]};"><p style="margin:0;font-size:12px;color:#666;">Employee:</p><p style="margin:3px 0 0;font-size:14px;font-weight:700;">{en}</p>{f'<p style="margin:3px 0 0;font-size:12px;color:#555;">Position: {pos}</p>' if pos else ''}</div>
                {body}
                <div style="margin-top:40px;padding-top:20px;border-top:2px solid #e5e7eb;"><div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;"><div><div style="border-bottom:1px solid #333;margin-top:50px;"></div><p style="font-size:11px;color:#666;margin:2px 0;">Employer Signature &amp; Date</p></div><div><div style="border-bottom:1px solid #333;margin-top:50px;"></div><p style="font-size:11px;color:#666;margin:2px 0;">Employee Signature &amp; Date</p></div></div><div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:25px;"><div><div style="border-bottom:1px solid #333;margin-top:30px;"></div><p style="font-size:11px;color:#666;">Witness 1</p></div><div><div style="border-bottom:1px solid #333;margin-top:30px;"></div><p style="font-size:11px;color:#666;">Witness 2</p></div></div></div>
            </div>
        </div>
        <script>
        function prt(){{var c=document.getElementById('pa').innerHTML;var w=window.open('','_blank');w.document.write('<!DOCTYPE html><html><head><title>{dt["label"]}</title><style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{font-family:Arial,sans-serif;color:#333;}}@media print{{@page{{size:A4;margin:15mm 18mm;}}}}</style></head><body>'+c+'</body></html>');w.document.close();w.focus();setTimeout(()=>{{w.print();w.close();}},300);}}
        async function del_(){{if(!confirm('Delete this document?'))return;var r=await fetch('/api/hr-document/{doc_id}/delete',{{method:'POST'}});var d=await r.json();if(d.success)window.location='/hr-documents';else alert(d.error);}}
        </script>'''
        return render_page(f"{dt['label']} — {en}",content,user,"hr")

    # === EDIT HR DOCUMENT ===
    @app.route("/hr-document/<doc_id>/edit",methods=["GET","POST"])
    @login_required
    def hr_doc_edit(doc_id):
        user=Auth.get_current_user();biz=Auth.get_current_business();biz_id=biz.get("id") if biz else None
        doc=db.get_one("hr_documents",doc_id)
        if not doc: return redirect("/hr-documents")
        doc_type=doc.get("doc_type","");dt=HR_DOC_TYPES.get(doc_type,{"label":"Document","icon":"📄"})
        if request.method=="POST": return _save_hr_doc(db,biz_id,user,doc_type,now,doc_id=doc_id)
        emps=_get_emps(biz_id);eo=_emp_opts(emps,doc.get("employee_id",""))
        ff=_form_fields(doc_type,doc,safe_string,today)
        content=f'''{_autofill_js}<div class="card"><h3 style="margin:0 0 20px;">{dt["icon"]} Edit {dt["label"]}</h3>
        <form method="POST"><input type="hidden" name="employer_name" value="{safe_string(doc.get('employer_name',''))}"><input type="hidden" name="employer_address" value="{safe_string(doc.get('employer_address',''))}">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;margin-bottom:20px;">
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Employee</label><select id="empSelect" name="employee_id" onchange="fillFromEmp()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">{eo}</select></div>
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Name *</label><input type="text" name="employee_name" id="fldName" value="{safe_string(doc.get('employee_name',''))}" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Position</label><input type="text" name="position" id="fldPos" value="{safe_string(doc.get('position',''))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:20px;">
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Date</label><input type="date" name="document_date" value="{doc.get('document_date',today())}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
            <div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Subject</label><input type="text" name="subject" value="{safe_string(doc.get('subject',''))}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div>
        </div><hr style="border:none;border-top:1px solid var(--border);margin:20px 0;">{ff}
        <div style="display:flex;gap:10px;margin-top:25px;"><button type="submit" class="btn btn-primary" style="flex:1;padding:14px;">Save Changes</button><a href="/hr-document/{doc_id}" class="btn btn-secondary" style="padding:14px;">Cancel</a></div></form></div>'''
        return render_page(f"Edit {dt['label']}",content,user,"hr")

    @app.route("/api/hr-document/<doc_id>/delete",methods=["POST"])
    @login_required
    def api_hr_del(doc_id):
        try: db.delete("hr_documents",doc_id); return jsonify({"success":True})
        except Exception as e: return jsonify({"success":False,"error":str(e)})

    # ======= CONTRACTS ROUTES (kept from v1) =======
    @app.route("/contracts")
    @login_required
    def contracts_page():
        user=Auth.get_current_user();biz=Auth.get_current_business();biz_id=biz.get("id") if biz else None
        try: contracts=sorted(db.get("employment_contracts",{"business_id":biz_id}) or [],key=lambda x:x.get("created_at",""),reverse=True)
        except: contracts=[]
        rows=""
        for c in contracts:
            st=c.get("status","draft");sc={"draft":"var(--orange)","active":"var(--green)","terminated":"var(--red)","expired":"var(--text-muted)"}
            rows+=f'<tr style="cursor:pointer;" onclick="window.location=\'/contract/{c.get("id")}\'"><td><strong>{safe_string(c.get("employee_name","-"))}</strong></td><td>{safe_string(c.get("position","-"))}</td><td>{c.get("start_date","-")}</td><td>{c.get("end_date","Permanent")}</td><td style="color:{sc.get(st,"var(--text-muted)")}">{st.title()}</td></tr>'
        content=f'''<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;">Employment Contracts ({len(contracts)})</h3><div style="display:flex;gap:10px;"><a href="/hr" class="btn btn-secondary">← HR Hub</a><a href="/contract/new" class="btn btn-primary">+ New Contract</a></div></div>
        <table class="table"><thead><tr><th>Employee</th><th>Position</th><th>Start</th><th>End</th><th>Status</th></tr></thead><tbody>{rows or "<tr><td colspan='5' style='text-align:center;color:var(--text-muted)'>No contracts yet</td></tr>"}</tbody></table></div>'''
        return render_page("Employment Contracts",content,user,"hr")

    @app.route("/contract/new",methods=["GET","POST"])
    @login_required
    def contract_new():
        user=Auth.get_current_user();biz=Auth.get_current_business();biz_id=biz.get("id") if biz else None
        if request.method=="POST": return _save_contract(db,biz_id,user,safe_string,now,today)
        emps=_get_emps(biz_id)
        content=_contract_form("New Employment Contract","/contract/new",_emp_opts(emps),_emp_json(emps),biz.get("name","") if biz else "",biz.get("address","") if biz else "",biz.get("registration_number","") if biz else "",{},"/contracts","Create Contract",safe_string,today)
        return render_page("New Contract",content,user,"hr")

    @app.route("/contract/<cid>/edit",methods=["GET","POST"])
    @login_required
    def contract_edit(cid):
        user=Auth.get_current_user();biz=Auth.get_current_business();biz_id=biz.get("id") if biz else None
        c=db.get_one("employment_contracts",cid)
        if not c: return redirect("/contracts")
        if request.method=="POST": return _save_contract(db,biz_id,user,safe_string,now,today,False,cid)
        emps=_get_emps(biz_id)
        content=_contract_form(f"Edit Contract",f"/contract/{cid}/edit",_emp_opts(emps,c.get("employee_id","")),_emp_json(emps),biz.get("name","") if biz else "",biz.get("address","") if biz else "",biz.get("registration_number","") if biz else "",c,f"/contract/{cid}","Save Changes",safe_string,today)
        return render_page("Edit Contract",content,user,"hr")

    @app.route("/contract/<cid>")
    @login_required
    def contract_view(cid):
        user=Auth.get_current_user();biz=Auth.get_current_business()
        c=db.get_one("employment_contracts",cid)
        if not c: return redirect("/contracts")
        content=_contract_view(c,cid,biz,safe_string,money)
        return render_page(f"Contract — {safe_string(c.get('employee_name',''))}",content,user,"hr")

    @app.route("/api/contract/<cid>/status",methods=["POST"])
    @login_required
    def api_ctr_status(cid):
        try:
            s=request.get_json().get("status","")
            if s not in ("draft","active","terminated","expired"): return jsonify({"success":False,"error":"Invalid"})
            db.update("employment_contracts",cid,{"status":s,"updated_at":now()});return jsonify({"success":True})
        except Exception as e: return jsonify({"success":False,"error":str(e)})

    logger.info("[HR/CONTRACTS] All routes registered")

# === FORM FIELDS PER DOC TYPE ===
def _fld(lbl,name,val="",ft="text",ph="",req=False,rows=4):
    v=str(val).replace('"','&quot;') if val else ""
    r="required" if req else ""
    s="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:14px;box-sizing:border-box;"
    if ft=="textarea": return f'<div style="margin-bottom:15px;"><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">{lbl}</label><textarea name="{name}" rows="{rows}" placeholder="{ph}" {r} style="{s}min-height:{rows*25}px;resize:vertical;">{v}</textarea></div>'
    elif ft=="date": return f'<div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">{lbl}</label><input type="date" name="{name}" value="{v}" {r} style="{s}"></div>'
    elif ft=="yesno":
        y="selected" if v.lower() in ("yes","true","1") else "";n="selected" if v.lower() in ("no","false","0") else ""
        return f'<div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">{lbl}</label><select name="{name}" style="{s}"><option value="Yes" {y}>Yes</option><option value="No" {n}>No</option></select></div>'
    return f'<div><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">{lbl}</label><input type="{ft}" name="{name}" value="{v}" placeholder="{ph}" {r} style="{s}"></div>'

def _form_fields(dt,v,ss,td):
    g=lambda k,d="": ss(str(v.get(k,d))) if v.get(k) else d
    if dt=="written_warning":
        return f'<h4 style="margin:0 0 15px;">Details of Offence</h4>{_fld("Nature of Offence *","offence",g("offence"),"text","e.g. Late arrival",True)}<div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">{_fld("Date of Offence","date_of_offence",g("date_of_offence",td()),"date")}{_fld("Previous Verbal Warnings","previous_warnings",g("previous_warnings","0"),"number")}</div>{_fld("Full Description","details",g("details"),"textarea","Describe what happened...",rows=5)}{_fld("Corrective Action Required","corrective_action",g("corrective_action"),"textarea","What must change...",rows=3)}{_fld("Review Period","review_period",g("review_period","3 months"))}<div style="background:rgba(245,158,11,0.1);border-left:4px solid #f59e0b;padding:12px;border-radius:6px;"><p style="margin:0;font-size:12px;"><strong>Note:</strong> Valid for 6 months. Repeat offence → Final Written Warning.</p></div>'
    elif dt=="final_warning":
        return f'<h4 style="margin:0 0 15px;">Details</h4>{_fld("Nature of Offence *","offence",g("offence"),"text","",True)}<div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">{_fld("Date of Offence","date_of_offence",g("date_of_offence",td()),"date")}{_fld("Previous Written Warnings","previous_warnings",g("previous_warnings","1"),"number")}</div>{_fld("Full Description","details",g("details"),"textarea","",rows=5)}{_fld("Corrective Action","corrective_action",g("corrective_action"),"textarea","",rows=3)}{_fld("Review Period","review_period",g("review_period","6 months"))}{_fld("Consequence","consequence",g("consequence","A disciplinary hearing will be convened which may result in dismissal."),"textarea","",rows=2)}<div style="background:rgba(239,68,68,0.1);border-left:4px solid #ef4444;padding:12px;border-radius:6px;"><p style="margin:0;font-size:12px;"><strong>FINAL:</strong> Further offence → disciplinary hearing → possible dismissal.</p></div>'
    elif dt=="hearing_notice":
        return f'<h4 style="margin:0 0 15px;">Hearing Details</h4>{_fld("Charges *","charges",g("charges"),"textarea","List each charge...",True,rows=6)}<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;">{_fld("Hearing Date *","hearing_date",g("hearing_date"),"date",req=True)}{_fld("Time","hearing_time",g("hearing_time","10:00"))}{_fld("Venue","hearing_venue",g("hearing_venue","Company boardroom"))}</div>{_fld("Chairperson","chairperson",g("chairperson"))}{_fld("Company Witnesses","witnesses",g("witnesses"),"textarea","",rows=3)}<div style="background:rgba(59,130,246,0.1);border-left:4px solid #3b82f6;padding:12px;border-radius:6px;"><p style="margin:0;font-size:12px;"><strong>Rights:</strong> Representation by colleague/shop steward, call witnesses, cross-examine, present mitigation. Absence without reason → hearing proceeds.</p></div>'
    elif dt=="suspension":
        return f'<h4 style="margin:0 0 15px;">Suspension</h4>{_fld("Reason *","reason",g("reason"),"textarea","",True,rows=4)}<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;">{_fld("Start Date","suspension_start",g("suspension_start",td()),"date")}{_fld("End Date","suspension_end",g("suspension_end"),"date")}{_fld("With Pay?","with_pay",g("with_pay","Yes"),"yesno")}</div>{_fld("Conditions","conditions",g("conditions","Remain available; no access to premises without arrangement."),"textarea","",rows=3)}{_fld("Return/Hearing Date","return_date",g("return_date"),"date")}'
    elif dt=="hearing_outcome":
        return f'<h4 style="margin:0 0 15px;">Outcome</h4>{_fld("Charges","charges",g("charges"),"textarea","",rows=4)}{_fld("Finding *","finding",g("finding"),"textarea","Guilty/Not guilty...",True,rows=3)}{_fld("Sanction *","sanction",g("sanction"),"textarea","Warning/Dismissal/Demotion...",True,rows=2)}{_fld("Mitigating Factors","mitigating_factors",g("mitigating_factors"),"textarea","",rows=3)}{_fld("Aggravating Factors","aggravating_factors",g("aggravating_factors"),"textarea","",rows=3)}{_fld("Appeal Rights","appeal_rights",g("appeal_rights","Appeal in writing within 5 days to MD. CCMA referral within 30 days."),"textarea","",rows=3)}'
    elif dt=="dismissal":
        return f'<h4 style="margin:0 0 15px;">Dismissal</h4>{_fld("Reason *","reason",g("reason"),"textarea","",True,rows=5)}{_fld("Effective Date","effective_date",g("effective_date",td()),"date")}{_fld("Hearing Reference","hearing_reference",g("hearing_reference"))}{_fld("Final Pay","final_pay_details",g("final_pay_details"),"textarea","",rows=3)}{_fld("Property to Return","return_property",g("return_property","Keys, uniform, tools, phone, laptop, access cards"),"textarea","",rows=2)}{_fld("Appeal Rights","appeal_rights",g("appeal_rights","CCMA referral within 30 days (Section 191, LRA)."),"textarea","",rows=3)}'
    elif dt=="resignation_acceptance":
        return f'<h4 style="margin:0 0 15px;">Resignation</h4><div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">{_fld("Resignation Date","resignation_date",g("resignation_date",td()),"date")}{_fld("Last Working Day","last_working_day",g("last_working_day"),"date")}</div>{_fld("Notice Served?","notice_served",g("notice_served","Yes"),"yesno")}{_fld("Handover","handover_requirements",g("handover_requirements"),"textarea","",rows=3)}{_fld("Final Pay","final_pay_details",g("final_pay_details"),"textarea","",rows=3)}'
    elif dt=="promotion":
        return f'<h4 style="margin:0 0 15px;">Promotion</h4><div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">{_fld("New Position *","new_position",g("new_position"),"text","",True)}{_fld("New Department","new_department",g("new_department"))}</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">{_fld("Effective Date","effective_date",g("effective_date",td()),"date")}{_fld("New Salary","new_salary",g("new_salary"),"number")}</div>{_fld("Responsibilities","new_responsibilities",g("new_responsibilities"),"textarea","",rows=4)}'
    elif dt=="salary_increase":
        return f'<h4 style="margin:0 0 15px;">Salary Increase</h4><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;">{_fld("Current Salary","current_salary",g("current_salary"),"number")}{_fld("New Salary","new_salary",g("new_salary"),"number")}{_fld("Effective Date","effective_date",g("effective_date",td()),"date")}</div>{_fld("Reason","increase_reason",g("increase_reason"),"textarea","",rows=3)}'
    return ""

# === LETTER BODY FOR VIEW/PRINT ===
def _letter_body(d,ss,money):
    dt=d.get("doc_type","")
    g=lambda k:ss(str(d.get(k,""))) if d.get(k) else ""
    nl=lambda t:t.replace("\n","<br>") if t else ""
    p='style="font-size:12px;line-height:1.7;color:#333;margin-bottom:12px;text-align:justify;"'
    h='style="font-size:13px;font-weight:700;color:#1e3a5f;margin:20px 0 8px;"'

    if dt=="written_warning":
        prev = " | Previous warnings: " + g("previous_warnings") if g("previous_warnings") else ""
        return '<h3 '+h+'>Nature of Offence</h3><p '+p+'><strong>'+g("offence")+'</strong></p><p '+p+'>Date: <strong>'+g("date_of_offence")+'</strong>'+prev+'</p><h3 '+h+'>Details</h3><p '+p+'>'+nl(g("details"))+'</p><h3 '+h+'>Corrective Action</h3><p '+p+'>'+nl(g("corrective_action"))+'</p><p '+p+'>Review period: <strong>'+g("review_period")+'</strong></p><div style="background:#fff7ed;border-left:4px solid #f59e0b;padding:10px 14px;border-radius:6px;margin-top:15px;"><p style="margin:0;font-size:11px;">Valid for <strong>6 months</strong>. Repeat offence may lead to Final Written Warning.</p></div>'

    elif dt=="final_warning":
        return '<h3 '+h+'>Nature of Offence</h3><p '+p+'><strong>'+g("offence")+'</strong></p><p '+p+'>Date: <strong>'+g("date_of_offence")+'</strong> | Previous warnings: <strong>'+g("previous_warnings")+'</strong></p><h3 '+h+'>Details</h3><p '+p+'>'+nl(g("details"))+'</p><h3 '+h+'>Corrective Action</h3><p '+p+'>'+nl(g("corrective_action"))+'</p><p '+p+'>Review: <strong>'+g("review_period")+'</strong></p><h3 '+h+'>Consequence</h3><p '+p+'>'+nl(g("consequence"))+'</p><div style="background:#fef2f2;border-left:4px solid #ef4444;padding:10px 14px;border-radius:6px;margin-top:15px;"><p style="margin:0;font-size:11px;"><strong>FINAL WARNING:</strong> Further misconduct within review period - disciplinary hearing - possible dismissal.</p></div>'

    elif dt=="hearing_notice":
        wit = '<h3 '+h+'>Witnesses</h3><p '+p+'>'+nl(g("witnesses"))+'</p>' if g("witnesses") else ""
        return '<p '+p+'>You are hereby notified to attend a <strong>Disciplinary Hearing</strong>:</p><table style="width:100%;font-size:12px;margin:15px 0;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;width:150px;">Date:</td><td style="padding:8px 0;font-weight:600;">'+g("hearing_date")+'</td></tr><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;">Time:</td><td style="padding:8px 0;">'+g("hearing_time")+'</td></tr><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;">Venue:</td><td style="padding:8px 0;">'+g("hearing_venue")+'</td></tr></table><h3 '+h+'>Charges</h3><p '+p+'>'+nl(g("charges"))+'</p>'+wit+'<div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:10px 14px;border-radius:6px;margin-top:15px;"><p style="margin:0;font-size:11px;"><strong>YOUR RIGHTS:</strong> Representation by colleague/shop steward; call witnesses; cross-examine; present mitigation. Non-attendance without valid reason - hearing proceeds in absence.</p></div>'

    elif dt=="suspension":
        pw="with full pay" if str(d.get("with_pay","")).lower() in ("yes","true","1") else "without pay"
        end_row = '<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;">End:</td><td style="padding:8px 0;">'+g("suspension_end")+'</td></tr>' if g("suspension_end") else ""
        return '<p '+p+'>You are hereby suspended <strong>'+pw+'</strong> with immediate effect.</p><h3 '+h+'>Reason</h3><p '+p+'>'+nl(g("reason"))+'</p><table style="width:100%;font-size:12px;margin:15px 0;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;width:180px;">Start:</td><td style="padding:8px 0;font-weight:600;">'+g("suspension_start")+'</td></tr>'+end_row+'</table><h3 '+h+'>Conditions</h3><p '+p+'>'+nl(g("conditions"))+'</p><div style="background:#f5f3ff;border-left:4px solid #8b5cf6;padding:10px 14px;border-radius:6px;margin-top:15px;"><p style="margin:0;font-size:11px;">Precautionary measure - does not imply guilt. LRA rights preserved.</p></div>'

    elif dt=="hearing_outcome":
        mit = '<h3 '+h+'>Mitigating</h3><p '+p+'>'+nl(g("mitigating_factors"))+'</p>' if g("mitigating_factors") else ""
        agg = '<h3 '+h+'>Aggravating</h3><p '+p+'>'+nl(g("aggravating_factors"))+'</p>' if g("aggravating_factors") else ""
        return '<h3 '+h+'>Charges</h3><p '+p+'>'+nl(g("charges"))+'</p><h3 '+h+'>Finding</h3><p '+p+'>'+nl(g("finding"))+'</p><h3 '+h+'>Sanction</h3><p '+p+' style="font-weight:700;">'+nl(g("sanction"))+'</p>'+mit+agg+'<h3 '+h+'>Appeal</h3><p '+p+'>'+nl(g("appeal_rights"))+'</p>'

    elif dt=="dismissal":
        fp = '<h3 '+h+'>Final Pay</h3><p '+p+'>'+nl(g("final_pay_details"))+'</p>' if g("final_pay_details") else ""
        rp = '<h3 '+h+'>Return Property</h3><p '+p+'>'+nl(g("return_property"))+'</p>' if g("return_property") else ""
        return '<p '+p+'>Your employment is <strong>terminated with immediate effect</strong>.</p><h3 '+h+'>Reason</h3><p '+p+'>'+nl(g("reason"))+'</p><table style="width:100%;font-size:12px;margin:15px 0;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;width:180px;">Effective date:</td><td style="padding:8px 0;font-weight:600;">'+g("effective_date")+'</td></tr></table>'+fp+rp+'<h3 '+h+'>Appeal</h3><p '+p+'>'+nl(g("appeal_rights"))+'</p><div style="background:#fef2f2;border-left:4px solid #dc2626;padding:10px 14px;border-radius:6px;margin-top:15px;"><p style="margin:0;font-size:11px;">CCMA referral within 30 days (Section 191, LRA 66 of 1995).</p></div>'

    elif dt=="resignation_acceptance":
        ns="with" if str(d.get("notice_served","")).lower() in ("yes","true","1") else "without"
        ho = '<h3 '+h+'>Handover</h3><p '+p+'>'+nl(g("handover_requirements"))+'</p>' if g("handover_requirements") else ""
        fp = '<h3 '+h+'>Final Pay</h3><p '+p+'>'+nl(g("final_pay_details"))+'</p>' if g("final_pay_details") else ""
        return '<p '+p+'>We acknowledge your resignation dated <strong>'+g("resignation_date")+'</strong>, accepted '+ns+' notice.</p><p '+p+'>Last working day: <strong>'+g("last_working_day")+'</strong></p>'+ho+fp+'<p '+p+'>Thank you for your service. We wish you well.</p>'

    elif dt=="promotion":
        dep_row = '<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;">Department:</td><td style="padding:8px 0;">'+g("new_department")+'</td></tr>' if g("new_department") else ""
        sal_val = float(d.get("new_salary",0))
        sal_row = '<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;">New salary:</td><td style="padding:8px 0;font-weight:600;">R{:,.2f}/month</td></tr>'.format(sal_val) if d.get("new_salary") else ""
        resp_html = '<h3 '+h+'>Responsibilities</h3><p '+p+'>'+nl(g("new_responsibilities"))+'</p>' if g("new_responsibilities") else ""
        return '<p '+p+'>We are pleased to confirm your promotion, effective <strong>'+g("effective_date")+'</strong>.</p><table style="width:100%;font-size:12px;margin:15px 0;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;width:180px;">New position:</td><td style="padding:8px 0;font-weight:600;">'+g("new_position")+'</td></tr>'+dep_row+sal_row+'</table>'+resp_html+'<p '+p+'>Congratulations. All other terms remain unchanged.</p>'

    elif dt=="salary_increase":
        cur=float(d.get("current_salary",0));nw=float(d.get("new_salary",0));pct=round((nw-cur)/cur*100,1) if cur>0 else 0
        reason_html = '<p '+p+'><strong>Reason:</strong> '+nl(g("increase_reason"))+'</p>' if g("increase_reason") else ""
        return '<p '+p+'>Your salary has been revised effective <strong>'+g("effective_date")+'</strong>.</p><table style="width:100%;font-size:12px;margin:15px 0;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;width:180px;">Current:</td><td style="padding:8px 0;">R{:,.2f}/month</td></tr><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;">New:</td><td style="padding:8px 0;font-weight:700;color:#10b981;">R{:,.2f}/month</td></tr><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:8px 0;color:#666;">Increase:</td><td style="padding:8px 0;font-weight:600;">{}%</td></tr></table>'.format(cur,nw,pct)+reason_html+'<p '+p+'>All other terms unchanged.</p>'

    return ""

# === SAVE HR DOC ===
def _save_hr_doc(db,biz_id,user,doc_type,now_fn,doc_id=None):
    f=request.form;data={"business_id":biz_id,"doc_type":doc_type,"employee_id":f.get("employee_id",""),"employee_name":f.get("employee_name","").strip(),"position":f.get("position","").strip(),"document_date":f.get("document_date",""),"subject":f.get("subject","").strip(),"employer_name":f.get("employer_name","").strip(),"employer_address":f.get("employer_address","").strip(),"updated_at":now_fn()}
    skip=set(data.keys())|{"employee_id"}
    for k in f.keys():
        if k not in skip: data[k]=f.get(k,"").strip()
    if not data["employee_name"]: return redirect(f"/hr-document/{'new/'+doc_type if not doc_id else doc_id+'/edit'}?error=Name+required")
    try:
        if doc_id: db.update("hr_documents",doc_id,data); return redirect(f"/hr-document/{doc_id}")
        else: data["id"]=str(uuid.uuid4());data["created_at"]=data["updated_at"];data["created_by"]=user.get("id") if user else None;data["created_by_name"]=user.get("name","") if user else "";db.save("hr_documents",data); return redirect(f"/hr-document/{data['id']}")
    except Exception as e: logger.error(f"[HR] Save error: {e}"); return redirect(f"/hr-document/{'new/'+doc_type if not doc_id else doc_id+'/edit'}?error=Save+failed")

# === CONTRACT SAVE ===
def _save_contract(db,biz_id,user,ss,now_fn,today_fn,is_new=True,cid=None):
    f=request.form;data={}
    for k in f.keys():
        v=f.get(k,"").strip()
        if k in ("basic_salary","hourly_rate"):
            try: v=float(v or 0)
            except: v=0
        elif k in ("probation_months","annual_leave","sick_leave","family_leave","maternity_leave","restraint_months"):
            try: v=int(v or 0)
            except: v=0
        data[k]=v
    data["business_id"]=biz_id;data["updated_at"]=now_fn()
    if not data.get("employee_name"): return redirect(f"/contract/{'new' if is_new else cid+'/edit'}?error=Name+required")
    try:
        if is_new: data["id"]=str(uuid.uuid4());data["status"]="draft";data["created_at"]=data["updated_at"];data["created_by"]=user.get("id") if user else None;data["created_by_name"]=user.get("name","") if user else "";db.save("employment_contracts",data);return redirect(f"/contract/{data['id']}")
        else: db.update("employment_contracts",cid,data);return redirect(f"/contract/{cid}")
    except Exception as e: logger.error(f"[CONTRACT] {e}");return redirect(f"/contract/{'new' if is_new else cid+'/edit'}?error=Failed")

# === CONTRACT VIEW ===
def _contract_view(c,cid,biz,ss,money):
    st=c.get("status","draft");bn=ss(c.get("employer_name",""));ba=ss(c.get("employer_address","")).replace("\n","<br>");br_=ss(c.get("employer_reg",""))
    en=ss(c.get("employee_name",""));eid=ss(c.get("employee_id_number",""));ea=ss(c.get("employee_address","")).replace("\n","<br>")
    pos=ss(c.get("position",""));dep=ss(c.get("department",""));sd=c.get("start_date","");ed=c.get("end_date","")
    ct=c.get("contract_type","permanent");prob=c.get("probation_months",3)
    sal=f"R{float(c.get('hourly_rate',0)):.2f}/hr" if c.get("pay_type")=="hourly" else f"R{float(c.get('basic_salary',0)):,.2f}/month"
    ctl={"permanent":"Permanent","fixed_term":"Fixed Term","temporary":"Temporary","part_time":"Part-Time"}.get(ct,ct.title())
    edc=f"Terminates on <strong>{ed}</strong>." if ed and ct!="permanent" else "Permanent — no fixed end."
    p='style="font-size:12px;line-height:1.6;color:#333;text-align:justify;"'
    h='style="margin:25px 0 10px;font-size:13px;font-weight:700;color:#1e3a5f;"'
    rh=""
    cn=14
    rm=c.get("restraint_months",0)
    if rm and rm>0:
        ra=ss(c.get("restraint_area",""));rh=f'<h3 {h}>14. RESTRAINT OF TRADE</h3><p {p}>For {rm} months after termination, no competing business{f" in {ra}" if ra else ""}.</p>';cn=15
    sp=ss(c.get("special_conditions","")).replace("\n","<br>")
    sh=f'<h3 {h}>{cn}. SPECIAL CONDITIONS</h3><p {p}>{sp}</p>' if sp else ""
    sn=cn+(1 if sp else 0)
    return f'''
    <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
        <a href="/contracts" style="color:var(--text-muted);">← Contracts</a>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <a href="/contract/{cid}/edit" class="btn btn-secondary">✏️ Edit</a>
            <select onchange="ucs(this.value)" style="padding:8px 12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:14px;"><option value="draft" {"selected" if st=="draft" else ""}>Draft</option><option value="active" {"selected" if st=="active" else ""}>Active</option><option value="terminated" {"selected" if st=="terminated" else ""}>Terminated</option><option value="expired" {"selected" if st=="expired" else ""}>Expired</option></select>
            <button class="btn btn-secondary" onclick="pc()">🖨️ Print</button>
        </div>
    </div>
    <div class="card" id="pa" style="background:white;color:#333;padding:0;overflow:hidden;">
        <div style="background:#1e3a5f;color:white;padding:15px 30px;text-align:center;"><h1 style="margin:0;font-size:18px;letter-spacing:1px;">EMPLOYMENT CONTRACT</h1><p style="margin:5px 0 0;font-size:11px;opacity:0.8;">Basic Conditions of Employment Act 75/1997</p></div>
        <div style="padding:25px 30px;">
            <h3 {h}>1. PARTIES</h3><table style="width:100%;font-size:12px;"><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:6px 0;color:#666;width:180px;">Employer:</td><td style="padding:6px 0;font-weight:600;">{bn}</td></tr>{f'<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:6px 0;color:#666;">Reg:</td><td>{br_}</td></tr>' if br_ else ''}{f'<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:6px 0;color:#666;">Address:</td><td>{ba}</td></tr>' if ba else ''}<tr><td colspan="2" style="height:8px;"></td></tr><tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:6px 0;color:#666;">Employee:</td><td style="font-weight:600;">{en}</td></tr>{f'<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:6px 0;color:#666;">ID:</td><td>{eid}</td></tr>' if eid else ''}{f'<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:6px 0;color:#666;">Address:</td><td>{ea}</td></tr>' if ea else ''}</table>
            <h3 {h}>2. COMMENCEMENT</h3><p {p}>Start: <strong>{sd}</strong>. Type: <strong>{ctl}</strong>. {edc} Probation: <strong>{prob} months</strong>.</p>
            <h3 {h}>3. JOB DESCRIPTION</h3><p {p}>Position: <strong>{pos}</strong>{f" ({dep})" if dep else ""}.</p>
            <h3 {h}>4. PLACE OF WORK</h3><p {p}>{ba or "Employer premises"}.</p>
            <h3 {h}>5. REMUNERATION</h3><p {p}>{sal}. Paid on <strong>{c.get("pay_day","25th")}</strong> by <strong>{c.get("pay_method","EFT")}</strong>. PAYE/UIF/SDL apply.</p>
            <h3 {h}>6. HOURS</h3><p {p}>{c.get("work_hours","08:00-17:00")}, {c.get("work_days","Mon-Fri")}. Lunch: {c.get("lunch_break","1hr")}. OT: 1.5×/2×. Max 45+10hrs/wk.</p>
            <h3 {h}>7. LEAVE</h3><p {p}>Annual: {c.get("annual_leave",15)}d. Sick: {c.get("sick_leave",30)}d/3yr. Family: {c.get("family_leave",3)}d. Maternity: {c.get("maternity_leave",4)}m.</p>
            <h3 {h}>8. CONDUCT</h3><p {p}>Diligent, comply with policies, no outside employment, maintain confidentiality.</p>
            <h3 {h}>9. TERMINATION</h3><p {p}>Notice: <strong>{c.get("notice_period","1 month")}</strong>. Probation: 1 week. Summary dismissal for gross misconduct.</p>
            <h3 {h}>10. DISCIPLINARY</h3><p {p}>Fair hearing per LRA.</p>
            <h3 {h}>11. CONFIDENTIALITY</h3><p {p}>During and after employment.</p>
            <h3 {h}>12. DEDUCTIONS</h3><p {p}>Statutory + agreed (pension, medical, union, loans).</p>
            <h3 {h}>13. GENERAL</h3><p {p}>Entire agreement. Written amendments only. SA law.</p>
            {rh}{sh}
            <div style="margin-top:40px;padding-top:20px;border-top:2px solid #1e3a5f;"><h3 style="margin:0 0 25px;font-size:13px;font-weight:700;color:#1e3a5f;">{sn}. SIGNATURES</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;"><div><p style="font-size:12px;font-weight:600;margin-bottom:50px;">EMPLOYER</p><div style="border-bottom:1px solid #333;"></div><p style="font-size:11px;color:#666;">Signature &amp; Date</p></div><div><p style="font-size:12px;font-weight:600;margin-bottom:50px;">EMPLOYEE</p><div style="border-bottom:1px solid #333;"></div><p style="font-size:11px;color:#666;">Signature &amp; Date</p></div></div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:25px;"><div><p style="font-size:11px;color:#666;margin-bottom:30px;">Witness 1:</p><div style="border-bottom:1px solid #333;"></div></div><div><p style="font-size:11px;color:#666;margin-bottom:30px;">Witness 2:</p><div style="border-bottom:1px solid #333;"></div></div></div>
            </div>
        </div>
    </div>
    <script>
    async function ucs(s){{var r=await fetch('/api/contract/{cid}/status',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{status:s}})}});var d=await r.json();if(d.success)location.reload();else alert(d.error);}}
    function pc(){{var c=document.getElementById('pa').innerHTML;var w=window.open('','_blank');w.document.write('<!DOCTYPE html><html><head><title>Contract</title><style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{font-family:Arial,sans-serif;color:#333;}}@media print{{@page{{size:A4;margin:15mm 18mm;}}}}</style></head><body>'+c+'</body></html>');w.document.close();w.focus();setTimeout(()=>{{w.print();w.close();}},300);}}
    </script>'''

# === CONTRACT FORM ===
def _contract_form(title,action,eo,ej,bn,ba,br,v,cancel,submit,ss,td):
    g=lambda k,d="":ss(str(v.get(k,d))) if v.get(k) else d
    return f'''<div class="card"><h3 style="margin:0 0 20px;">{title}</h3><form method="POST" action="{action}">
    <div style="background:rgba(0,0,0,0.1);padding:20px;border-radius:10px;margin-bottom:20px;"><h4 style="margin:0 0 15px;">👤 Employee</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Select Employee</label><select id="empSelect" onchange="fe()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);">{eo}</select></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Full Name *</label><input type="text" name="employee_name" id="en" value="{g('employee_name')}" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">ID Number</label><input type="text" name="employee_id_number" id="ei" value="{g('employee_id_number')}" maxlength="13" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Address</label><input type="text" name="employee_address" id="ea" value="{g('employee_address')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
        <input type="hidden" name="employee_id" id="eid" value="{g('employee_id')}">
    </div>
    <div style="background:rgba(0,0,0,0.1);padding:20px;border-radius:10px;margin-bottom:20px;"><h4 style="margin:0 0 15px;">🏢 Employer</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Company</label><input type="text" name="employer_name" value="{g('employer_name') or ss(bn)}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Reg</label><input type="text" name="employer_reg" value="{g('employer_reg') or ss(br)}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Address</label><input type="text" name="employer_address" value="{g('employer_address') or ss(ba)}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
    </div>
    <div style="background:rgba(0,0,0,0.1);padding:20px;border-radius:10px;margin-bottom:20px;"><h4 style="margin:0 0 15px;">💼 Job</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Position *</label><input type="text" name="position" id="ep" value="{g('position')}" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Department</label><input type="text" name="department" value="{g('department')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Type</label><select name="contract_type" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"><option value="permanent" {"selected" if g('contract_type','permanent')=='permanent' else ""}>Permanent</option><option value="fixed_term" {"selected" if g('contract_type')=='fixed_term' else ""}>Fixed Term</option><option value="temporary" {"selected" if g('contract_type')=='temporary' else ""}>Temporary</option><option value="part_time" {"selected" if g('contract_type')=='part_time' else ""}>Part-Time</option></select></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Probation (m)</label><input type="number" name="probation_months" value="{g('probation_months','3')}" min="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Start Date *</label><input type="date" name="start_date" value="{g('start_date',td())}" required style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">End Date</label><input type="date" name="end_date" value="{g('end_date')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
    </div>
    <div style="background:rgba(0,0,0,0.1);padding:20px;border-radius:10px;margin-bottom:20px;"><h4 style="margin:0 0 15px;">💰 Pay</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Type</label><select name="pay_type" id="ept" onchange="tp()" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"><option value="monthly" {"selected" if g('pay_type','monthly')=='monthly' else ""}>Monthly</option><option value="hourly" {"selected" if g('pay_type')=='hourly' else ""}>Hourly</option></select></div><div id="fm"><label style="display:block;margin-bottom:5px;font-size:13px;">Salary</label><input type="number" name="basic_salary" id="es" step="0.01" value="{g('basic_salary','0')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div id="fh" style="display:none;"><label style="display:block;margin-bottom:5px;font-size:13px;">Hourly</label><input type="number" name="hourly_rate" id="eh" step="0.01" value="{g('hourly_rate','0')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Pay Day</label><input type="text" name="pay_day" value="{g('pay_day','25th')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Method</label><select name="pay_method" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"><option value="Electronic transfer" {"selected" if g('pay_method','Electronic transfer')=='Electronic transfer' else ""}>EFT</option><option value="Cash" {"selected" if g('pay_method')=='Cash' else ""}>Cash</option></select></div></div>
    </div>
    <div style="background:rgba(0,0,0,0.1);padding:20px;border-radius:10px;margin-bottom:20px;"><h4 style="margin:0 0 15px;">🕐 Hours &amp; Leave</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Hours</label><input type="text" name="work_hours" value="{g('work_hours','08:00 – 17:00')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Days</label><input type="text" name="work_days" value="{g('work_days','Monday to Friday')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Lunch</label><input type="text" name="lunch_break" value="{g('lunch_break','1 hour')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:15px;margin-top:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Annual (d)</label><input type="number" name="annual_leave" value="{g('annual_leave','15')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Sick (d/3yr)</label><input type="number" name="sick_leave" value="{g('sick_leave','30')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Family (d)</label><input type="number" name="family_leave" value="{g('family_leave','3')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Maternity (m)</label><input type="number" name="maternity_leave" value="{g('maternity_leave','4')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
    </div>
    <div style="background:rgba(0,0,0,0.1);padding:20px;border-radius:10px;margin-bottom:20px;"><h4 style="margin:0 0 15px;">📋 Termination</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:15px;"><div><label style="display:block;margin-bottom:5px;font-size:13px;">Notice</label><select name="notice_period" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"><option value="1 week" {"selected" if g('notice_period')=='1 week' else ""}>1 Week</option><option value="2 weeks" {"selected" if g('notice_period')=='2 weeks' else ""}>2 Weeks</option><option value="1 month" {"selected" if g('notice_period','1 month')=='1 month' else ""}>1 Month</option><option value="2 months" {"selected" if g('notice_period')=='2 months' else ""}>2 Months</option><option value="3 months" {"selected" if g('notice_period')=='3 months' else ""}>3 Months</option></select></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Restraint (m)</label><input type="number" name="restraint_months" value="{g('restraint_months','0')}" min="0" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div><div><label style="display:block;margin-bottom:5px;font-size:13px;">Restraint Area</label><input type="text" name="restraint_area" value="{g('restraint_area')}" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);"></div></div>
    </div>
    <div style="margin-bottom:20px;"><label style="display:block;margin-bottom:5px;font-size:13px;font-weight:600;">Special Conditions</label><textarea name="special_conditions" rows="3" style="width:100%;padding:10px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);resize:vertical;box-sizing:border-box;">{g('special_conditions')}</textarea></div>
    <div style="display:flex;gap:10px;"><button type="submit" class="btn btn-primary" style="flex:1;padding:14px;">{submit}</button><a href="{cancel}" class="btn btn-secondary" style="padding:14px;">Cancel</a></div>
    </form></div>
    <script>var ed={ej};function fe(){{var s=document.getElementById('empSelect'),e=ed[s.value];if(!e)return;document.getElementById('eid').value=s.value;document.getElementById('en').value=e.name||'';var i=document.getElementById('ei');if(i)i.value=e.id_number||'';var p=document.getElementById('ep');if(p)p.value=e.position||'';var a=document.getElementById('ea');if(a)a.value=e.address||'';if(e.pay_type){{document.getElementById('ept').value=e.pay_type;tp();}}if(e.basic_salary)document.getElementById('es').value=e.basic_salary;if(e.hourly_rate)document.getElementById('eh').value=e.hourly_rate;}}function tp(){{var t=document.getElementById('ept').value;document.getElementById('fm').style.display=t==='monthly'?'':'none';document.getElementById('fh').style.display=t==='hourly'?'':'none';}}tp();</script>'''
