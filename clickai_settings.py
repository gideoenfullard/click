# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - SETTINGS MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Settings page, Business Groups settings, Invoice Template,
#           Business/PayFast/Email/Scan-inbox/WhatsApp settings APIs,
#           GL migrate, Debug GL, Switch/Create business
# ==============================================================================

import os
import json
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)

# Environment variables used by settings
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASS = os.environ.get("IMAP_PASS", "")
PAYFAST_MERCHANT_ID = os.environ.get("PAYFAST_MERCHANT_ID", "")
PAYFAST_SANDBOX = os.environ.get("PAYFAST_SANDBOX", "false").lower() == "true"


def register_settings_routes(app, db, login_required, Auth, render_page,
                              generate_id, safe_string, now,
                              gl, build_gl_map, CLICKAI_DEFAULTS,
                              has_reactor_hud, jarvis_hud_header, jarvis_techline,
                              JARVIS_HUD_CSS, THEME_REACTOR_SKINS):
    """Register all Settings routes with the Flask app."""

    @app.route("/settings")
    @login_required
    def settings_page():
        """Business Settings"""
        
        user = Auth.get_current_user()
        
        # ALWAYS clear cache and reload fresh from DB for settings page
        Auth.clear_cache()
        session.pop("_biz_cache", None)
        session.pop("businesses_cache", None)
        session.pop("business_name", None)
        
        # Get business DIRECTLY from DB (not cached)
        biz_id = session.get("business_id")
        business = None
        if biz_id:
            business = db.get_one("businesses", biz_id)
            logger.info(f"[SETTINGS PAGE] Loaded business from DB: id={biz_id}, name={business.get('name') if business else 'None'}")
        
        if not business:
            # Fallback to Auth method
            business = Auth.get_current_business()
            logger.info(f"[SETTINGS PAGE] Fallback to Auth: {business.get('name') if business else 'None'}")
        
        # Check if action=new to create new business
        if request.args.get("action") == "new":
            content = '''
            <div class="card">
                <h2 style="margin-bottom:20px;">Create New Business</h2>
                <p style="color:var(--text-muted);margin-bottom:20px;">Add another business to manage with Click AI</p>
                
                <form action="/api/settings/business" method="POST">
                    <input type="hidden" name="is_new" value="true">
                    
                    <div class="form-group">
                        <label class="form-label">Business Name *</label>
                        <input type="text" name="name" class="form-input" required placeholder="e.g. My Company (Pty) Ltd">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">Registration Number</label>
                        <input type="text" name="reg_number" class="form-input" placeholder="e.g. 2024/123456/07">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">VAT Number</label>
                        <input type="text" name="vat_number" class="form-input" placeholder="e.g. 4123456789">
                    </div>
                    
                    <div style="display:flex;gap:10px;">
                        <button type="submit" class="btn btn-primary">Create Business</button>
                        <a href="/settings" class="btn btn-secondary">Cancel</a>
                    </div>
                </form>
            </div>
            '''
            return render_page("New Business", content, user, "settings")
        
        # If no business, show setup page
        if not business:
            content = '''
            <div class="card" style="max-width:500px;margin:50px auto;text-align:center;">
                <h2 style="margin-bottom:20px;">Welcome to Click AI!</h2>
                <p style="color:var(--text-muted);margin-bottom:30px;">Let's set up your first business to get started.</p>
                
                <form action="/api/settings/business" method="POST">
                    <div class="form-group" style="text-align:left;">
                        <label class="form-label">Business Name *</label>
                        <input type="text" name="name" class="form-input" required placeholder="e.g. My Company (Pty) Ltd" autofocus>
                    </div>
                    
                    <div class="form-group" style="text-align:left;">
                        <label class="form-label">VAT Number (optional)</label>
                        <input type="text" name="vat_number" class="form-input" placeholder="e.g. 4123456789">
                    </div>
                    
                    <button type="submit" class="btn btn-primary" style="width:100%;padding:15px;font-size:16px;">
                        Create Business & Get Started
                    </button>
                </form>
            </div>
            '''
            return render_page("Setup", content, user, "settings")
        
        content = f'''
        <div class="card">
            <h2 style="margin-bottom:20px;">Business Settings</h2>
            
            {f'<div style="background:#10b981;color:white;padding:15px;border-radius:8px;margin-bottom:20px;font-weight:bold;">GOOD: Settings saved successfully!</div>' if request.args.get("saved") else ""}
            {f'<div style="background:#ef4444;color:white;padding:15px;border-radius:8px;margin-bottom:20px;">❌ Error saving: {safe_string(request.args.get("error", ""))}</div>' if request.args.get("error") else ""}
            
            <!-- DEBUG INFO -->
            <details style="background:var(--card);border:1px solid var(--border);padding:10px;border-radius:8px;margin-bottom:20px;">
                <summary style="cursor:pointer;font-weight:bold;color:var(--text-muted);">🔧 Debug Info (click to expand)</summary>
                <div style="margin-top:10px;font-size:12px;font-family:monospace;white-space:pre-wrap;">
    Business ID: {business.get("id") if business else "None"}
    Business Name: {business.get("name") if business else "None"}
    Session biz_id: {session.get("business_id")}
    VAT: {business.get("vat_number") if business else "None"}
    Phone: {business.get("phone") if business else "None"}
    Address: {business.get("address")[:50] if business and business.get("address") else "None"}
                </div>
            </details>
            
            <form action="/api/settings/business" method="POST">
                <div class="form-group">
                    <label class="form-label">Business Name</label>
                    <input type="text" name="name" class="form-input" value="{safe_string(business.get("name", "") if business else "")}" required>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Industry Type</label>
                    <select name="industry_type" class="form-input">
                        <option value="retail_general" {"selected" if business and business.get("industry_type") == "retail_general" else ""}>General Retail</option>
                        <option value="steel_supplier" {"selected" if business and business.get("industry_type") == "steel_supplier" else ""}>Steel & Metal Supplier</option>
                        <option value="hardware_store" {"selected" if business and business.get("industry_type") == "hardware_store" else ""}>Hardware Store</option>
                        <option value="restaurant" {"selected" if business and business.get("industry_type") == "restaurant" else ""}>Restaurant / Pub</option>
                        <option value="guest_house" {"selected" if business and business.get("industry_type") == "guest_house" else ""}>Guest House / B&B</option>
                        <option value="professional_services" {"selected" if business and business.get("industry_type") == "professional_services" else ""}>Professional Services</option>
                    </select>
                    <small style="color:var(--text-muted);">This helps Zane understand your business better - expense categories, terminology, and insights.</small>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Registration Number</label>
                    <input type="text" name="reg_number" class="form-input" value="{safe_string(business.get("reg_number", "") if business else "")}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">VAT Number</label>
                    <input type="text" name="vat_number" class="form-input" value="{safe_string(business.get("vat_number", "") if business else "")}" placeholder="4XXXXXXXXX">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="text" name="phone" class="form-input" value="{safe_string(business.get("phone", "") if business else "")}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input" value="{safe_string(business.get("email", "") if business else "")}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Address</label>
                    <textarea name="address" class="form-input" rows="3">{safe_string(business.get("address", "") if business else "")}</textarea>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Bank Name</label>
                    <input type="text" name="bank_name" class="form-input" value="{safe_string(business.get("bank_name", "") if business else "")}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Bank Account Number</label>
                    <input type="text" name="bank_account" class="form-input" value="{safe_string(business.get("bank_account", "") if business else "")}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">Bank Branch Code</label>
                    <input type="text" name="bank_branch" class="form-input" value="{safe_string(business.get("bank_branch", "") if business else "")}">
                </div>
                
                <button type="submit" class="btn btn-primary">Save Settings</button>
            </form>
        </div>
        
        <!-- EMAIL STATUS DIAGNOSTIC PANEL -->
        <div class="card" style="margin-top:20px; border-left: 4px solid {'var(--green)' if (business and business.get('smtp_user') and business.get('smtp_pass')) or (SMTP_USER and SMTP_PASS) else 'var(--red)'};">
            <h3 style="margin-bottom:15px;">👁️ Email Status - Diagnostic</h3>
            
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                <!-- SMTP (Outgoing) Status -->
                <div style="background:var(--card-bg); padding:15px; border-radius:8px; border:1px solid var(--border);">
                    <h4 style="margin:0 0 10px 0;">📤 SMTP (Uitgaande Email)</h4>
                    {'<p style="color:var(--green);font-weight:bold;">CONFIGURED</p>' if (business and business.get('smtp_user') and business.get('smtp_pass')) or (SMTP_USER and SMTP_PASS) else '<p style="color:var(--red);font-weight:bold;">NOT CONFIGURED</p>'}
                    
                    <table style="width:100%;font-size:13px;margin-top:10px;">
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">Bron:</td>
                            <td style="padding:3px 0;"><strong>{'Business Settings' if (business and business.get('smtp_user') and business.get('smtp_pass')) else ('Global Env Vars' if SMTP_USER and SMTP_PASS else 'GEEN')}</strong></td>
                        </tr>
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">Host:</td>
                            <td style="padding:3px 0;">{safe_string(business.get('smtp_host') if (business and business.get('smtp_host')) else SMTP_HOST) or '<span style="color:var(--red);">Nie gestel</span>'}</td>
                        </tr>
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">Port:</td>
                            <td style="padding:3px 0;">{safe_string(business.get('smtp_port') if (business and business.get('smtp_port')) else SMTP_PORT) or '587'}</td>
                        </tr>
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">User:</td>
                            <td style="padding:3px 0;">{safe_string(business.get('smtp_user') if (business and business.get('smtp_user')) else SMTP_USER) or '<span style="color:var(--red);">Nie gestel</span>'}</td>
                        </tr>
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">Password:</td>
                            <td style="padding:3px 0;">{'<span style="color:var(--green);">******* ✓</span>' if (business and business.get('smtp_pass')) or SMTP_PASS else '<span style="color:var(--red);">Nie gestel</span>'}</td>
                        </tr>
                    </table>
                </div>
                
                <!-- IMAP (Incoming) Status -->
                <div style="background:var(--card-bg); padding:15px; border-radius:8px; border:1px solid var(--border);">
                    <h4 style="margin:0 0 10px 0;">IMAP (Scanner Inbox)</h4>
                    {'<p style="color:var(--green);font-weight:bold;">CONFIGURED</p>' if (business and business.get('imap_user') and business.get('imap_pass')) or (IMAP_USER and IMAP_PASS) else '<p style="color:var(--text-muted);font-weight:bold;">Not configured (opsioneel)</p>'}
                    
                    <table style="width:100%;font-size:13px;margin-top:10px;">
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">Host:</td>
                            <td style="padding:3px 0;">{safe_string(business.get('imap_host') if (business and business.get('imap_host')) else IMAP_HOST) or 'imap.gmail.com'}</td>
                        </tr>
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">User:</td>
                            <td style="padding:3px 0;">{safe_string(business.get('imap_user') if (business and business.get('imap_user')) else IMAP_USER) or '<span style="color:var(--text-muted);">Nie gestel</span>'}</td>
                        </tr>
                        <tr>
                            <td style="color:var(--text-muted);padding:3px 0;">Password:</td>
                            <td style="padding:3px 0;">{'<span style="color:var(--green);">******* ✓</span>' if (business and business.get('imap_pass')) or IMAP_PASS else '<span style="color:var(--text-muted);">Nie gestel</span>'}</td>
                        </tr>
                    </table>
                </div>
            </div>
            
            <div style="margin-top:15px; padding:10px; background:var(--bg); border-radius:6px; font-size:12px; color:var(--text-muted);">
                <strong>Note:</strong> Invites, payment reminders, en invoice emails vereis SMTP. Scanner inbox (IMAP) is slegs nodig as jy dokumente per email wil scan.
                {'<br><span style="color:var(--orange);">Warning: SMTP is nie gekonfigureer nie - emails sal nie gestuur word nie!</span>' if not ((business and business.get('smtp_user') and business.get('smtp_pass')) or (SMTP_USER and SMTP_PASS)) else ''}
            </div>
        </div>
        
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">Email Settings</h3>
            <p style="color:var(--text-muted);margin-bottom:15px;">Configure SMTP to send emails to customers</p>
            
            <form action="/api/settings/email" method="POST">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                    <div class="form-group">
                        <label class="form-label">SMTP Host</label>
                        <input type="text" name="smtp_host" class="form-input" value="{safe_string(business.get("smtp_host", "smtp.gmail.com") if business else "smtp.gmail.com")}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">SMTP Port</label>
                        <input type="text" name="smtp_port" class="form-input" value="{safe_string(business.get("smtp_port", "587") if business else "587")}">
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">SMTP Username</label>
                    <input type="text" name="smtp_user" class="form-input" value="{safe_string(business.get("smtp_user", "") if business else "")}">
                </div>
                
                <div class="form-group">
                    <label class="form-label">SMTP Password</label>
                    <input type="password" name="smtp_pass" class="form-input" placeholder="App password">
                </div>
                
                <div style="display:flex;gap:10px;align-items:center;">
                    <button type="submit" class="btn btn-secondary"> Save Email Settings</button>
                    <button type="button" class="btn btn-primary" onclick="testSmtp()" id="testSmtpBtn">📧 Test SMTP</button>
                    <span id="smtpTestResult" style="margin-left:10px;"></span>
                </div>
            </form>
            
            <script>
            async function testSmtp() {{
                const btn = document.getElementById('testSmtpBtn');
                const result = document.getElementById('smtpTestResult');
                btn.disabled = true;
                btn.textContent = 'Testing...';
                result.innerHTML = '';
                
                try {{
                    const res = await fetch('/api/email/test-smtp', {{ method: 'POST' }});
                    const data = await res.json();
                    
                    if (data.success) {{
                        result.innerHTML = '<span style="color:var(--green);">data.message + '</span>';
                    }} else {{
                        result.innerHTML = '<span style="color:var(--red);">data.error + '</span>';
                    }}
                }} catch (e) {{
                    result.innerHTML = '<span style="color:var(--red);">Error: ' + e.message + '</span>';
                }}
                
                btn.disabled = false;
                btn.textContent = '📧 Test SMTP';
            }}
            </script>
        </div>
        
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">Scanner Inbox Settings</h3>
            <p style="color:var(--text-muted);margin-bottom:15px;">Set up an email address where your printer/scanner sends scanned documents. Click AI will automatically check this inbox and process invoices.</p>
            
            <form action="/api/settings/scan-inbox" method="POST">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;">
                    <div class="form-group">
                        <label class="form-label">IMAP Host</label>
                        <input type="text" name="imap_host" class="form-input" value="{safe_string(business.get("imap_host", "imap.gmail.com") if business else "imap.gmail.com")}" placeholder="imap.gmail.com">
                    </div>
                    <div class="form-group">
                        <label class="form-label">IMAP Port</label>
                        <input type="text" name="imap_port" class="form-input" value="{safe_string(business.get("imap_port", "993") if business else "993")}" placeholder="993">
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Scanner Email Address</label>
                    <input type="email" name="imap_user" class="form-input" value="{safe_string(business.get("imap_user", "") if business else "")}" placeholder="scanner@yourbusiness.com">
                    <small style="color:var(--text-muted);">Create a dedicated email for your scanner to send to</small>
                </div>
                
                <div class="form-group">
                    <label class="form-label">Email Password / App Password</label>
                    <input type="password" name="imap_pass" class="form-input" placeholder="{'••••••••' if business and business.get('imap_pass') else 'Enter app password'}">
                    <small style="color:var(--text-muted);">For Gmail, use an <a href="https://myaccount.google.com/apppasswords" target="_blank" style="color:var(--primary);">App Password</a></small>
                </div>
                
                <button type="submit" class="btn btn-secondary">💾 Save Scanner Inbox</button>
                <button type="button" class="btn btn-secondary" onclick="testScannerConnection()" style="margin-left:10px;">🔌 Test Connection</button>
                {f'<span id="scanner-status" style="color:var(--green);margin-left:15px;">GOOD: Connected</span>' if business and business.get('imap_user') else '<span id="scanner-status"></span>'}
            </form>
            
            <script>
            async function testScannerConnection() {{
                const status = document.getElementById('scanner-status');
                status.innerHTML = '<span style="color:var(--text-muted);">Testing...</span>';
                try {{
                    const res = await fetch('/api/email/test');
                    const data = await res.json();
                    if (data.success) {{
                        status.innerHTML = '<span style="color:var(--green);">GOOD: ' + data.message + '</span>';
                    }} else {{
                        status.innerHTML = '<span style="color:var(--red);">✗ ' + data.error + '</span>';
                    }}
                }} catch(e) {{
                    status.innerHTML = '<span style="color:var(--red);">✗ Connection failed</span>';
                }}
            }}
            </script>
        </div>
        
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">💬 WhatsApp Settings</h3>
            <p style="color:var(--text-muted);margin-bottom:15px;">Connect WhatsApp to send invoices and messages to customers</p>
            
            <form action="/api/settings/whatsapp" method="POST">
                <div class="form-group">
                    <label class="form-label">WhatsApp Business Phone Number</label>
                    <input type="text" name="whatsapp_phone" class="form-input" value="{safe_string(business.get("whatsapp_phone", "") if business else "")}" placeholder="+27821234567">
                </div>
                
                <div class="form-group">
                    <label class="form-label">WhatsApp API Token</label>
                    <input type="password" name="whatsapp_token" class="form-input" placeholder="{'••••••••' if business and business.get('whatsapp_token') else 'From Meta Business Suite'}">
                    <small style="color:var(--text-muted);">Get from <a href="https://business.facebook.com/settings/whatsapp-business-accounts" target="_blank" style="color:var(--primary);">Meta Business Suite</a></small>
                </div>
                
                <div class="form-group">
                    <label class="form-label">WhatsApp Business Account ID</label>
                    <input type="text" name="whatsapp_account_id" class="form-input" value="{safe_string(business.get("whatsapp_account_id", "") if business else "")}" placeholder="From Meta Business Suite">
                </div>
                
                <button type="submit" class="btn btn-secondary">💾 Save WhatsApp Settings</button>
                {f'<span style="color:var(--green);margin-left:15px;">GOOD: Connected</span>' if business and business.get('whatsapp_token') else ''}
            </form>
        </div>
        
        <!-- Safety File Settings -->
        <div class="card" style="margin-top:20px;border-left:4px solid var(--primary);">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <h3 style="margin-bottom:5px;">🛡️ AI Safety File Generator</h3>
                    <p style="color:var(--text-muted);margin:0;">Generate OHS Act-compliant safety files for your business</p>
                </div>
                <a href="/settings/safety-files" class="btn btn-primary">⚙️ Configure</a>
            </div>
        </div>
        
        <!-- POS Settings -->
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">🖨️ POS Print Settings</h3>
            <p style="color:var(--text-muted);margin-bottom:15px;">Configure how slips print at Point of Sale</p>
            
            <form action="/api/settings/pos" method="POST">
                <div style="display:grid;gap:15px;">
                    <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;background:var(--bg);border-radius:8px;">
                        <input type="checkbox" name="pos_auto_print" value="1" style="width:20px;height:20px;" {"checked" if business and business.get("pos_auto_print") else ""}>
                        <div>
                            <strong>Auto-print after sale</strong>
                            <div style="color:var(--text-muted);font-size:12px;">Automatically show print dialog when sale completes</div>
                        </div>
                    </label>
                    
                    <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:10px;background:var(--bg);border-radius:8px;">
                        <input type="checkbox" name="pos_print_duplicates" value="1" style="width:20px;height:20px;" {"checked" if business and business.get("pos_print_duplicates") else ""}>
                        <div>
                            <strong>🖨️ Print 2 copies (auto)</strong>
                            <div style="color:var(--text-muted);font-size:12px;">Automatically prints customer copy + store copy</div>
                        </div>
                    </label>
                    
                    <div class="form-group" style="margin-bottom:0;">
                        <label class="form-label">Default Print Format</label>
                        <select name="pos_print_format" class="form-input" style="max-width:300px;">
                            <option value="thermal" {"selected" if business and business.get("pos_print_format") == "thermal" else ""}>80mm Thermal (Receipt Printer)</option>
                            <option value="a4" {"selected" if business and business.get("pos_print_format") == "a4" else ""}>A4 (Standard Printer)</option>
                            <option value="ask" {"selected" if not business or not business.get("pos_print_format") or business.get("pos_print_format") == "ask" else ""}>Ask each time</option>
                        </select>
                    </div>
                    
                    <div class="form-group" style="margin-bottom:0;">
                        <label class="form-label">Business Footer on Slip</label>
                        <input type="text" name="pos_slip_footer" class="form-input" value="{safe_string(business.get("pos_slip_footer", "Thank you for your purchase!") if business else "Thank you for your purchase!")}" placeholder="e.g. Thank you! Visit again!">
                    </div>
                </div>
                
                <button type="submit" class="btn btn-secondary" style="margin-top:15px;">💾 Save POS Settings</button>
            </form>
        </div>
        
        <h3 style="margin:30px 0 15px 0;">More Settings</h3>
        <div class="stats-grid">
            <div class="card" style="cursor:pointer;border-left:4px solid var(--primary);" onclick="window.location='/settings/invoice-template'">
                <h3>Invoice Template</h3>
                <p style="color:var(--text-muted)">Customize your invoice look</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/setup'">
                <h3> Setup Wizard</h3>
                <p style="color:var(--text-muted)">Quick setup checklist</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/settings/opening-balances'">
                <h3>Opening Balances</h3>
                <p style="color:var(--text-muted)">Import historical balances</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/settings/team'">
                <h3>Team Members</h3>
                <p style="color:var(--text-muted)">Invite staff & set roles</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/settings/categories'">
                <h3>Stock Categories</h3>
                <p style="color:var(--text-muted)">Organize stock items</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/staging'">
                <h3>Review Queue</h3>
                <p style="color:var(--text-muted)">Approve scanned items</p>
            </div>
            <div class="card" style="cursor:pointer" onclick="window.location='/import'">
                <h3>Import Data</h3>
                <p style="color:var(--text-muted)">Import from CSV/Excel</p>
            </div>
            <div class="card" style="cursor:pointer;background:linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.1));" onclick="window.location='/welcome'">
                <h3>Meet the Team</h3>
                <p style="color:var(--text-muted)">Zane, Diane, Jayden & Jacqo</p>
            </div>
        </div>
        
        <!-- PayFast Online Payments Setup -->
        <div class="card" style="margin-top:20px;">
            <h3 style="margin-bottom:15px;">💳 Online Payments (PayFast)</h3>
            <p style="color:var(--text-muted);font-size:13px;margin-bottom:15px;">
                Enable "Pay Now" buttons on your invoices. Customers can pay with card, EFT, SnapScan, Zapper, or Capitec Pay.
                Register at <a href="https://www.payfast.co.za" target="_blank" style="color:#4F46E5;">payfast.co.za</a> to get your credentials.
            </p>
            ''' + (f'''
            <div style="padding:10px;background:rgba(16,185,129,0.1);border-radius:8px;margin-bottom:15px;">
                <strong style="color:var(--green);">✅ PayFast Configured</strong>
                <span style="color:var(--text-muted);font-size:12px;margin-left:10px;">{"SANDBOX MODE" if PAYFAST_SANDBOX else "LIVE"}</span>
            </div>
            ''' if (PAYFAST_MERCHANT_ID or (business and business.get("payfast_merchant_id"))) else '''
            <div style="padding:10px;background:rgba(239,68,68,0.1);border-radius:8px;margin-bottom:15px;">
                <strong style="color:var(--red);">Not configured</strong>
                <span style="color:var(--text-muted);font-size:12px;margin-left:10px;">Set up PayFast to enable online payments</span>
            </div>
            ''') + '''
            <form action="/api/settings/payfast" method="POST">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                    <div class="form-group">
                        <label class="form-label">Merchant ID</label>
                        <input type="text" name="payfast_merchant_id" class="form-input" 
                            value="''' + safe_string(business.get("payfast_merchant_id", "") if business else "") + '''"
                            placeholder="e.g. 10000100">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Merchant Key</label>
                        <input type="text" name="payfast_merchant_key" class="form-input" 
                            value="''' + safe_string(business.get("payfast_merchant_key", "") if business else "") + '''"
                            placeholder="e.g. 46f0cd694581a">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Passphrase <span style="color:var(--text-muted);font-size:12px;">(set this in your PayFast dashboard under Settings → Security)</span></label>
                    <input type="text" name="payfast_passphrase" class="form-input" 
                        value="''' + safe_string(business.get("payfast_passphrase", "") if business else "") + '''"
                        placeholder="Your PayFast passphrase">
                </div>
                <button type="submit" class="btn btn-primary">💳 Save PayFast Settings</button>
            </form>
        </div>
        
        <div class="card">
            <h2 style="margin-bottom:10px;">🏢 Business Groups</h2>
            <p style="color:var(--text-muted);margin-bottom:15px;">Link multiple businesses to see cross-business insights, comparisons, and find opportunities.</p>
            <a href="/settings/business-groups" class="btn btn-primary">Manage Business Groups →</a>
        </div>
        
        <!-- DANGER ZONE: Wipe all transactional data (owner only) -->
        ''' + ((f'''
        <div class="card" style="margin-top:20px;border:2px solid #ef4444;">
            <h2 style="margin-bottom:10px;color:#ef4444;">⚠️ Danger Zone</h2>
            <p style="color:var(--text-muted);margin-bottom:15px;">
                Wipe ALL transactional data for <strong>{safe_string(business.get("name", "this business"))}</strong>.
                This is intended for re-importing a clean dataset from Sage (or similar) after testing.
            </p>
            <div style="background:rgba(239,68,68,0.08);padding:15px;border-radius:8px;margin-bottom:15px;font-size:13px;">
                <div style="font-weight:bold;margin-bottom:8px;">Will be permanently deleted:</div>
                <div style="color:var(--text-muted);line-height:1.7;">
                    Invoices, sales, POS sales, quotes, credit notes, delivery notes, payments, receipts &bull;
                    Supplier invoices, supplier payments, purchase orders, GRVs &bull;
                    Expenses, scanned documents, scan inbox/queue &bull;
                    Bank transactions, bank patterns &bull;
                    Journal entries, allocation log &bull;
                    Stock movements &bull;
                    Cash-ups, bar tabs &bull;
                    Timesheets, payslips &bull;
                    Jobs, rentals, travel log &bull;
                    Daily briefings, reminders, todos, notes, Zane memory &bull;
                    Audit log, AI usage log, WhatsApp log &bull;
                    Assets, budgets, year-ends
                </div>
                <div style="font-weight:bold;margin-top:12px;margin-bottom:8px;color:#10b981;">Will be preserved:</div>
                <div style="color:var(--text-muted);line-height:1.7;">
                    Chart of accounts (GL codes) &bull;
                    Employees, employment contracts, HR documents &bull;
                    Bank account setup &bull;
                    Stock categories &bull;
                    Safety files &bull;
                    Business record, users, team members, subscriptions &bull;
                    All settings on this page
                </div>
            </div>
            <button onclick="confirmWipeBusinessData(event)" class="btn"
                style="background:#ef4444;color:white;font-weight:bold;">
                🗑️ Wipe All Transactional Data
            </button>
        </div>
        
        <script>
        async function confirmWipeBusinessData(ev) {{
            if (!confirm("⚠️ WIPE ALL TRANSACTIONAL DATA\\n\\n" +
                         "This will permanently delete EVERY invoice, sale, payment, " +
                         "expense, bank transaction, journal entry, timesheet, payslip, " +
                         "and related record for this business.\\n\\n" +
                         "Chart of accounts, employees, bank account setup, stock categories, " +
                         "and settings will be kept.\\n\\n" +
                         "This cannot be undone. Continue?")) return;
            
            const phrase = prompt("To confirm, type exactly: WIPE ALL DATA");
            if ((phrase || "").trim() !== "WIPE ALL DATA") {{
                alert("Confirmation phrase did not match. Nothing was deleted.");
                return;
            }}
            
            const btn = (ev && ev.target) ? ev.target : null;
            let oldText = "";
            if (btn) {{
                oldText = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = "⏳ Wiping... please wait";
            }}
            
            try {{
                const resp = await fetch("/api/business/wipe-transactions", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify({{confirm: "WIPE ALL DATA"}})
                }});
                const data = await resp.json();
                
                if (data.success) {{
                    let summary = "✅ Wipe complete.\\n\\n" +
                                  "Total records deleted: " + data.deleted + "\\n" +
                                  "Failed: " + (data.failed || 0) + "\\n\\n" +
                                  "Per-table breakdown:\\n";
                    if (data.tables) {{
                        for (const [tbl, info] of Object.entries(data.tables)) {{
                            if (info.before > 0) {{
                                summary += "  " + tbl + ": " + info.deleted + "/" + info.before;
                                if (info.failed) summary += " (failed " + info.failed + ")";
                                if (info.error) summary += " — error: " + info.error;
                                summary += "\\n";
                            }}
                        }}
                    }}
                    alert(summary);
                    window.location.href = "/dashboard";
                }} else {{
                    if (btn) {{
                        btn.disabled = false;
                        btn.innerHTML = oldText;
                    }}
                    alert("❌ " + (data.error || "Wipe failed"));
                }}
            }} catch (e) {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = oldText;
                }}
                alert("❌ Network error: " + e.message);
            }}
        }}
        </script>
        ''') if (business and user and business.get("user_id") == user.get("id")) else "") + '''
        '''
        
        # -- JARVIS: Settings HUD header --
        if has_reactor_hud():
            _hud = jarvis_hud_header(
                page_name="SETTINGS",
                page_count="SYSTEM CONFIGURATION",
                left_items=[
                    ("BUSINESS", "ACTIVE", "g", "g", ""),
                    ("TEAM", "MANAGE", "c", "", ""),
                    ("THEME", "JARVIS", "c", "", ""),
                    ("SECURITY", "ON", "g", "g", "g"),
                ],
                right_items=[
                    ("API", "CONNECTED", "g", "g", ""),
                    ("IMPORT", "READY", "c", "", ""),
                    ("EXPORT", "READY", "c", "", ""),
                    ("BACKUP", "AUTO", "p", "", ""),
                ],
                reactor_size="page",
                alert_html=""
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline("SETTINGS <b>LOADED</b>")
        
        return render_page("Settings", content, user, "settings")
    
    
    @app.route("/settings/business-groups")
    @login_required
    def settings_business_groups():
        """Business Groups - Cross-business management"""
        user = Auth.get_current_user()
        
        # === Build business list SERVER-SIDE (same source as business switcher) ===
        import json as _json
        user_id = user.get("id", "") if user else ""
        biz_list = []  # [{id, name}, ...]
        
        try:
            # STRATEGY: Read from the SAME cache render_page uses, or do full lookup
            _bc = Auth._mem.get(f"bizlist:{user_id}") if user_id else None
            businesses_raw = []
            
            if _bc and (time.time() - _bc.get("t", 0)) < 300:
                businesses_raw = _bc["d"]
                logger.info(f"[BIZ-GROUP] Using cached bizlist: {len(businesses_raw)}")
            else:
                # Full lookup — all 3 methods
                seen_ids = set()
                user_email = (user.get("email", "") or "").lower() if user else ""
                
                owned = db.get("businesses", {"user_id": user_id}) if user_id else []
                for b in (owned or []):
                    bid = b.get("id")
                    if bid and bid not in seen_ids:
                        seen_ids.add(bid)
                        businesses_raw.append(b)
                
                if user_email:
                    try:
                        for tm in (db.get("team_members", {"email": user_email}) or []):
                            mbid = tm.get("business_id")
                            if mbid and mbid not in seen_ids:
                                biz = db.get_one("businesses", mbid)
                                if biz:
                                    seen_ids.add(mbid)
                                    businesses_raw.append(biz)
                    except Exception:
                        pass
                
                if user_id:
                    try:
                        for tm in (db.get("team_members", {"user_id": user_id}) or []):
                            mbid = tm.get("business_id")
                            if mbid and mbid not in seen_ids:
                                biz = db.get_one("businesses", mbid)
                                if biz:
                                    seen_ids.add(mbid)
                                    businesses_raw.append(biz)
                    except Exception:
                        pass
                
                logger.info(f"[BIZ-GROUP] Fresh lookup: {len(businesses_raw)} businesses for {user_id}")
            
            for b in businesses_raw:
                bid = b.get("id")
                bname = b.get("name") or b.get("business_name", "Unknown")
                if bid:
                    biz_list.append({"id": bid, "name": bname})
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Biz fetch error: {e}")
        
        # Build <option> tags directly in Python
        biz_options_html = '<option value="">-- Select Business --</option>'
        for b in biz_list:
            safe_name = (b["name"] or "").replace("'", "&#39;").replace('"', "&quot;")
            biz_options_html += f'<option value="{b["id"]}">{safe_name}</option>'
        
        biz_json = _json.dumps(biz_list)
        logger.info(f"[BIZ-GROUP] Page: {len(biz_list)} businesses: {[b['name'] for b in biz_list]}")
        
        content = '''
        <script>var SERVER_BUSINESSES = ''' + biz_json + ''';</script>
        <div class="card" style="margin-bottom:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <div>
                    <h2 style="margin:0;">🏢 Business Groups</h2>
                    <p style="color:var(--text-muted);margin:5px 0 0;">Link your businesses together for cross-business insights</p>
                </div>
                <button onclick="showCreateGroup()" class="btn btn-primary">+ New Group</button>
            </div>
    
            <!-- Create Group Form (hidden by default) -->
            <div id="createGroupForm" style="display:none;background:var(--bg);padding:20px;border-radius:12px;border:1px solid var(--border);margin-bottom:20px;">
                <h3 style="margin:0 0 15px;">Create New Group</h3>
                <div style="display:flex;gap:10px;">
                    <input type="text" id="newGroupName" class="form-input" placeholder="e.g. My Businesses" style="flex:1;">
                    <button onclick="createGroup()" class="btn btn-primary">Create</button>
                    <button onclick="hideCreateGroup()" class="btn btn-secondary">Cancel</button>
                </div>
            </div>
    
            <!-- Groups List -->
            <div id="groupsList">
                <div style="text-align:center;padding:40px;color:var(--text-muted);">
                    Loading...
                </div>
            </div>
        </div>
    
        <!-- Group Detail Modal -->
        <div id="groupDetail" style="display:none;" class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <h2 id="groupDetailTitle" style="margin:0;">Group</h2>
                <button onclick="hideGroupDetail()" class="btn btn-secondary">← Back</button>
            </div>
            
            <!-- Add Business -->
            <div style="background:var(--bg);padding:15px;border-radius:12px;border:1px solid var(--border);margin-bottom:20px;">
                <h3 style="margin:0 0 10px;">Add Business to Group</h3>
                <div style="display:flex;gap:10px;">
                    <select id="addBizSelect" class="form-input" style="flex:1;">
                        ''' + biz_options_html + '''
                    </select>
                    <button onclick="addBizToGroup()" class="btn btn-primary">Add</button>
                </div>
            </div>
    
            <!-- Businesses in Group -->
            <div id="groupBusinesses" style="margin-bottom:20px;"></div>
            
            <!-- Cross-Business Overview -->
            <div id="groupOverview" style="margin-bottom:20px;"></div>
    
            <!-- Comparison Insights -->
            <div id="groupInsights"></div>
        </div>
    
        <style>
            .group-card {
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 12px;
                cursor: pointer;
                transition: all 0.2s;
            }
            .group-card:hover {
                border-color: var(--primary);
                transform: translateY(-1px);
            }
            .biz-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 8px;
                padding: 12px 16px;
                margin-bottom: 8px;
            }
            .stat-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 12px;
                margin-bottom: 20px;
            }
            .stat-box {
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 10px;
                padding: 16px;
                text-align: center;
            }
            .stat-box .stat-value {
                font-size: 1.5em;
                font-weight: 700;
                color: var(--text);
            }
            .stat-box .stat-label {
                font-size: 0.85em;
                color: var(--text-muted);
                margin-top: 4px;
            }
            .insight-card {
                background: var(--bg);
                border-left: 4px solid var(--primary);
                border-radius: 8px;
                padding: 14px 16px;
                margin-bottom: 10px;
            }
            .insight-card.critical { border-left-color: #ef4444; }
            .insight-card.warning { border-left-color: #f59e0b; }
            .insight-card.info { border-left-color: #3b82f6; }
            .biz-overview-card {
                background: var(--bg);
                border: 1px solid var(--border);
                border-radius: 10px;
                padding: 16px;
                margin-bottom: 10px;
            }
        </style>
    
        <script>
        let currentGroupId = null;
        let allBusinesses = [];
    
        // Load on page start
        document.addEventListener('DOMContentLoaded', async () => {
            await loadMyBusinesses();
            loadGroups();
        });
    
        async function loadMyBusinesses() {
            // Businesses already loaded server-side into SERVER_BUSINESSES and into the <select> options
            if (typeof SERVER_BUSINESSES !== 'undefined' && SERVER_BUSINESSES.length > 0) {
                allBusinesses = SERVER_BUSINESSES;
            } else {
                // Fallback: read from business switcher in nav
                const select = document.getElementById('businessSelect');
                if (select) {
                    for (let opt of select.options) {
                        if (opt.value) allBusinesses.push({ id: opt.value, name: opt.text });
                    }
                }
            }
            console.log('[BIZ-GROUP] allBusinesses:', allBusinesses.length, allBusinesses);
        }
    
        async function loadGroups() {
            try {
                const resp = await fetch('/api/business-groups');
                const data = await resp.json();
                
                if (!data.success) {
                    document.getElementById('groupsList').innerHTML = '<p style="color:#ef4444;">Error loading groups</p>';
                    return;
                }
    
                if (data.groups.length === 0) {
                    document.getElementById('groupsList').innerHTML = `
                        <div style="text-align:center;padding:40px;color:var(--text-muted);">
                            <div style="font-size:3em;margin-bottom:10px;">🏢</div>
                            <p>No business groups yet.</p>
                            <p>Create a group to link your businesses and see cross-business insights.</p>
                            <button onclick="showCreateGroup()" class="btn btn-primary" style="margin-top:15px;">+ Create First Group</button>
                        </div>`;
                    return;
                }
    
                let html = '';
                for (const group of data.groups) {
                    const count = group.business_count || 0;
                    html += `
                        <div class="group-card" onclick="openGroup('${group.id}', '${group.name.replace(/'/g, "\\'")}')">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <div>
                                    <h3 style="margin:0;">${group.name}</h3>
                                    <p style="color:var(--text-muted);margin:5px 0 0;">${count} business${count !== 1 ? 'es' : ''} linked</p>
                                </div>
                                <div style="display:flex;gap:8px;align-items:center;">
                                    <span style="font-size:1.5em;">→</span>
                                    <button onclick="event.stopPropagation();deleteGroup('${group.id}','${group.name.replace(/'/g, "\\'")}')" 
                                        class="btn btn-secondary" style="padding:6px 10px;font-size:12px;">🗑️</button>
                                </div>
                            </div>
                        </div>`;
                }
                document.getElementById('groupsList').innerHTML = html;
            } catch (e) {
                document.getElementById('groupsList').innerHTML = '<p style="color:#ef4444;">Error: ' + e.message + '</p>';
            }
        }
    
        function showCreateGroup() {
            document.getElementById('createGroupForm').style.display = 'block';
            document.getElementById('newGroupName').focus();
        }
    
        function hideCreateGroup() {
            document.getElementById('createGroupForm').style.display = 'none';
            document.getElementById('newGroupName').value = '';
        }
    
        async function createGroup() {
            const name = document.getElementById('newGroupName').value.trim();
            if (!name) return alert('Enter a group name');
    
            const resp = await fetch('/api/business-groups', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name })
            });
            const data = await resp.json();
            
            if (data.success) {
                hideCreateGroup();
                loadGroups();
            } else {
                alert('Error: ' + (data.error || 'Failed'));
            }
        }
    
        async function deleteGroup(id, name) {
            if (!confirm('Delete group "' + name + '"? This will unlink all businesses (businesses are NOT deleted).')) return;
            
            const resp = await fetch('/api/business-groups/' + id, { method: 'DELETE' });
            const data = await resp.json();
            
            if (data.success) {
                loadGroups();
                document.getElementById('groupDetail').style.display = 'none';
            } else {
                alert('Error: ' + (data.error || 'Failed'));
            }
        }
    
        async function openGroup(groupId, groupName) {
            currentGroupId = groupId;
            document.getElementById('groupDetailTitle').textContent = '📊 ' + groupName;
            document.getElementById('groupDetail').style.display = 'block';
            document.getElementById('groupsList').parentElement.querySelector('.card:first-child').style.display = 'none';
            
            // Populate add-business dropdown
            await loadGroupBusinesses(groupId);
            await loadGroupOverview(groupId);
            await loadGroupInsights(groupId);
        }
    
        function hideGroupDetail() {
            document.getElementById('groupDetail').style.display = 'none';
            document.getElementById('groupsList').parentElement.querySelector('.card:first-child').style.display = 'block';
            currentGroupId = null;
        }
    
        async function loadGroupBusinesses(groupId) {
            const resp = await fetch('/api/business-groups/' + groupId + '/businesses');
            const data = await resp.json();
            
            const inGroup = data.businesses || [];
            const inGroupIds = inGroup.map(b => b.id);
    
            // SAFETY: If allBusinesses is empty, recover from current <select> options or SERVER_BUSINESSES
            if (allBusinesses.length === 0) {
                // Try SERVER_BUSINESSES first
                if (typeof SERVER_BUSINESSES !== 'undefined' && SERVER_BUSINESSES.length > 0) {
                    allBusinesses = SERVER_BUSINESSES;
                } else {
                    // Read from the dropdown BEFORE we overwrite it
                    const sel = document.getElementById('addBizSelect');
                    if (sel) {
                        for (let opt of sel.options) {
                            if (opt.value) allBusinesses.push({ id: opt.value, name: opt.text });
                        }
                    }
                    // Last resort: read from business switcher in nav
                    if (allBusinesses.length === 0) {
                        const navSel = document.getElementById('businessSelect');
                        if (navSel) {
                            for (let opt of navSel.options) {
                                if (opt.value) allBusinesses.push({ id: opt.value, name: opt.text });
                            }
                        }
                    }
                }
                console.log('[BIZ-GROUP] Recovered allBusinesses:', allBusinesses.length, allBusinesses);
            }
    
            // Update add dropdown — only show businesses NOT already in the group
            let opts = '<option value="">-- Select Business --</option>';
            for (const biz of allBusinesses) {
                if (!inGroupIds.includes(biz.id)) {
                    opts += '<option value="' + biz.id + '">' + biz.name + '</option>';
                }
            }
            document.getElementById('addBizSelect').innerHTML = opts;
    
            // Show businesses in group
            if (inGroup.length === 0) {
                document.getElementById('groupBusinesses').innerHTML = `
                    <p style="color:var(--text-muted);text-align:center;padding:20px;">
                        No businesses linked yet. Add one above.
                    </p>`;
                return;
            }
    
            let html = '<h3>Linked Businesses</h3>';
            for (const biz of inGroup) {
                const btype = biz.business_type || biz.industry || '';
                html += `
                    <div class="biz-item">
                        <div>
                            <strong>${biz.name || 'Unknown'}</strong>
                            ${btype ? '<span style="color:var(--text-muted);margin-left:8px;">' + btype + '</span>' : ''}
                        </div>
                        <button onclick="removeBiz('${biz.id}','${(biz.name||'').replace(/'/g, "\\'")}')" 
                            class="btn btn-secondary" style="padding:5px 10px;font-size:12px;">Remove</button>
                    </div>`;
            }
            document.getElementById('groupBusinesses').innerHTML = html;
        }
    
        async function addBizToGroup() {
            const bizId = document.getElementById('addBizSelect').value;
            if (!bizId || !currentGroupId) return alert('Select a business');
    
            const resp = await fetch('/api/business-groups/' + currentGroupId + '/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ business_id: bizId })
            });
            const data = await resp.json();
            
            if (data.success) {
                await loadGroupBusinesses(currentGroupId);
                await loadGroupOverview(currentGroupId);
                await loadGroupInsights(currentGroupId);
            } else {
                alert('Error: ' + (data.error || 'Failed'));
            }
        }
    
        async function removeBiz(bizId, bizName) {
            if (!confirm('Remove "' + bizName + '" from this group?')) return;
            
            const resp = await fetch('/api/business-groups/' + currentGroupId + '/remove/' + bizId, {
                method: 'DELETE'
            });
            const data = await resp.json();
            
            if (data.success) {
                await loadGroupBusinesses(currentGroupId);
                await loadGroupOverview(currentGroupId);
                await loadGroupInsights(currentGroupId);
            } else {
                alert('Error: ' + (data.error || 'Failed'));
            }
        }
    
        async function loadGroupOverview(groupId) {
            document.getElementById('groupOverview').innerHTML = '<p style="color:var(--text-muted);">Loading overview...</p>';
            
            try {
                const resp = await fetch('/api/business-groups/' + groupId + '/overview');
                const data = await resp.json();
                
                if (!data.success || !data.businesses || data.businesses.length === 0) {
                    document.getElementById('groupOverview').innerHTML = '';
                    return;
                }
    
                const t = data.totals;
                const fmt = (n) => 'R ' + (n || 0).toLocaleString('en-ZA', {minimumFractionDigits: 0, maximumFractionDigits: 0});
    
                let html = '<h3>📊 Group Overview</h3>';
                
                // Totals grid
                html += '<div class="stat-grid">';
                html += `<div class="stat-box"><div class="stat-value">${fmt(t.revenue_this_month)}</div><div class="stat-label">Revenue (this month)</div></div>`;
                html += `<div class="stat-box"><div class="stat-value">${fmt(t.total_debtors)}</div><div class="stat-label">Total Debtors</div></div>`;
                html += `<div class="stat-box"><div class="stat-value">${fmt(t.total_creditors)}</div><div class="stat-label">Total Creditors</div></div>`;
                html += `<div class="stat-box"><div class="stat-value">${fmt(t.total_stock_value)}</div><div class="stat-label">Total Stock Value</div></div>`;
                html += `<div class="stat-box"><div class="stat-value">${fmt(t.total_bank_balance)}</div><div class="stat-label">Combined Bank</div></div>`;
                html += `<div class="stat-box"><div class="stat-value">${data.business_count}</div><div class="stat-label">Businesses</div></div>`;
                html += '</div>';
    
                // Per business breakdown
                html += '<h3>Per Business</h3>';
                for (const biz of data.businesses) {
                    const rev = biz.revenue_this_month || 0;
                    const totalRev = t.revenue_this_month || 1;
                    const pct = ((rev / totalRev) * 100).toFixed(0);
                    
                    html += `
                        <div class="biz-overview-card">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                                <strong>${biz.name}</strong>
                                <span style="color:var(--text-muted);">${pct}% of revenue</span>
                            </div>
                            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;font-size:0.85em;">
                                <div>Revenue<br><strong>${fmt(biz.revenue_this_month)}</strong></div>
                                <div>Debtors<br><strong>${fmt(biz.total_debtors)}</strong></div>
                                <div>Creditors<br><strong>${fmt(biz.total_creditors)}</strong></div>
                                <div>Stock<br><strong>${fmt(biz.total_stock_value)}</strong></div>
                            </div>
                            <div style="background:var(--border);border-radius:4px;height:6px;margin-top:10px;">
                                <div style="background:var(--primary);border-radius:4px;height:6px;width:${pct}%;"></div>
                            </div>
                        </div>`;
                }
    
                document.getElementById('groupOverview').innerHTML = html;
            } catch (e) {
                document.getElementById('groupOverview').innerHTML = '<p style="color:#ef4444;">Error loading overview</p>';
            }
        }
    
        async function loadGroupInsights(groupId) {
            document.getElementById('groupInsights').innerHTML = '';
            
            try {
                const resp = await fetch('/api/business-groups/' + groupId + '/comparison');
                const data = await resp.json();
                
                if (!data.success || !data.insights || data.insights.length === 0) {
                    return;
                }
    
                let html = '<h3>💡 Cross-Business Insights</h3>';
                for (const insight of data.insights) {
                    html += `
                        <div class="insight-card ${insight.severity || 'info'}">
                            <div style="display:flex;gap:8px;align-items:flex-start;">
                                <span style="font-size:1.3em;">${insight.icon || '💡'}</span>
                                <div>
                                    <strong>${insight.title}</strong>
                                    <p style="margin:4px 0 0;color:var(--text-muted);">${insight.message}</p>
                                </div>
                            </div>
                        </div>`;
                }
    
                document.getElementById('groupInsights').innerHTML = html;
            } catch (e) {
                // Silently fail
            }
        }
        </script>
        '''
        
        return render_page("Business Groups", content, user, "settings")
    
    
    @app.route("/settings/invoice-template", methods=["GET", "POST"])
    @login_required
    def settings_invoice_template():
        """Invoice Template Customization"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not business:
            flash("Please set up your business first", "error")
            return redirect("/settings")
        
        if request.method == "POST":
            # Save template settings
            template_settings = {
                "template_style": request.form.get("template_style", "modern"),
                "primary_color": request.form.get("primary_color", "#2563eb"),
                "show_logo": request.form.get("show_logo") == "on",
                "logo_url": request.form.get("logo_url", ""),
                "show_bank_details": request.form.get("show_bank_details") == "on",
                "show_payment_terms": request.form.get("show_payment_terms") == "on",
                "payment_terms": request.form.get("payment_terms", "Payment due within 30 days"),
                "footer_text": request.form.get("footer_text", ""),
                "show_vat_breakdown": request.form.get("show_vat_breakdown") == "on",
                "invoice_title": request.form.get("invoice_title", "INVOICE"),
                "quote_title": request.form.get("quote_title", "QUOTATION"),
            }
            
            business["invoice_template"] = json.dumps(template_settings)
            business["updated_at"] = now()
            db.save("businesses", business)
            
            flash("Invoice template updated!", "success")
            return redirect("/settings/invoice-template")
        
        # GET - Load existing settings
        try:
            template = json.loads(business.get("invoice_template", "{}"))
        except:
            template = {}
        
        # Default values
        template_style = template.get("template_style", "modern")
        primary_color = template.get("primary_color", "#2563eb")
        show_logo = template.get("show_logo", True)
        logo_url = template.get("logo_url", "")
        show_bank_details = template.get("show_bank_details", True)
        show_payment_terms = template.get("show_payment_terms", True)
        payment_terms = template.get("payment_terms", "Payment due within 30 days")
        footer_text = template.get("footer_text", "Thank you for your business!")
        show_vat_breakdown = template.get("show_vat_breakdown", True)
        invoice_title = template.get("invoice_title", "INVOICE")
        quote_title = template.get("quote_title", "QUOTATION")
        
        # Template style options with previews
        style_options = {
            "modern": {"name": "Modern", "desc": "Clean and minimal with accent colors"},
            "classic": {"name": "Classic", "desc": "Traditional professional look"},
            "bold": {"name": "Bold", "desc": "Strong headers with colored background"},
            "minimal": {"name": "Minimal", "desc": "Ultra-clean with lots of white space"},
        }
        
        style_html = ""
        for key, val in style_options.items():
            selected = "border-color: var(--primary); background: rgba(99,102,241,0.1);" if key == template_style else ""
            style_html += f'''
            <label style="cursor: pointer;">
                <input type="radio" name="template_style" value="{key}" {"checked" if key == template_style else ""} style="display: none;">
                <div style="border: 2px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; transition: all 0.2s; {selected}" 
                     onmouseover="this.style.borderColor='var(--primary)'" 
                     onmouseout="this.style.borderColor='{f"var(--primary)" if key == template_style else "var(--border)"}'">
                    <div style="font-size: 32px; margin-bottom: 10px;">📄</div>
                    <div style="font-weight: bold;">{val["name"]}</div>
                    <div style="font-size: 12px; color: var(--text-muted);">{val["desc"]}</div>
                </div>
            </label>
            '''
        
        content = f'''
        <div style="margin-bottom: 20px;">
            <a href="/settings" style="color:var(--text-muted);">← Back to Settings</a>
        </div>
        
        <div class="card" style="margin-bottom: 20px;">
            <h2 style="margin: 0 0 5px 0;">Invoice Template</h2>
            <p style="color: var(--text-muted); margin: 0;">Customize how your invoices and quotes look</p>
        </div>
        
        <form method="POST">
            <div class="card" style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 20px 0;">Template Style</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px;">
                    {style_html}
                </div>
            </div>
            
            <div class="card" style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 20px 0;">Branding</h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">Primary Color</label>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <input type="color" name="primary_color" value="{primary_color}" style="width: 60px; height: 40px; border: none; cursor: pointer;">
                            <input type="text" value="{primary_color}" class="form-input" style="width: 120px;" 
                                   onchange="this.previousElementSibling.value=this.value" readonly>
                        </div>
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">
                            <input type="checkbox" name="show_logo" {"checked" if show_logo else ""} style="margin-right: 8px;">
                            Show Logo
                        </label>
                        <input type="text" name="logo_url" class="form-input" value="{safe_string(logo_url)}" 
                               placeholder="https://yourdomain.com/logo.png">
                        <small style="color: var(--text-muted);">Enter URL to your logo image</small>
                    </div>
                </div>
            </div>
            
            <div class="card" style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 20px 0;">Document Titles</h3>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">Invoice Title</label>
                        <input type="text" name="invoice_title" class="form-input" value="{safe_string(invoice_title)}" 
                               placeholder="INVOICE">
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 5px; font-weight: 500;">Quote Title</label>
                        <input type="text" name="quote_title" class="form-input" value="{safe_string(quote_title)}" 
                               placeholder="QUOTATION">
                    </div>
                </div>
            </div>
            
            <div class="card" style="margin-bottom: 20px;">
                <h3 style="margin: 0 0 20px 0;">Content Options</h3>
                
                <div style="display: grid; gap: 15px;">
                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                        <input type="checkbox" name="show_bank_details" {"checked" if show_bank_details else ""} style="width: 18px; height: 18px;">
                        <span><strong>Show Bank Details</strong> - Display your banking info for EFT payments</span>
                    </label>
                    
                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                        <input type="checkbox" name="show_vat_breakdown" {"checked" if show_vat_breakdown else ""} style="width: 18px; height: 18px;">
                        <span><strong>Show VAT Breakdown</strong> - Display Subtotal, VAT, and Total separately</span>
                    </label>
                    
                    <label style="display: flex; align-items: center; gap: 10px; cursor: pointer;">
                        <input type="checkbox" name="show_payment_terms" {"checked" if show_payment_terms else ""} style="width: 18px; height: 18px;">
                        <span><strong>Show Payment Terms</strong> - Include payment due terms on invoice</span>
                    </label>
                </div>
                
                <div style="margin-top: 20px;">
                    <label style="display: block; margin-bottom: 5px; font-weight: 500;">Payment Terms Text</label>
                    <input type="text" name="payment_terms" class="form-input" value="{safe_string(payment_terms)}" 
                           placeholder="Payment due within 30 days">
                </div>
                
                <div style="margin-top: 15px;">
                    <label style="display: block; margin-bottom: 5px; font-weight: 500;">Footer Text</label>
                    <textarea name="footer_text" class="form-input" rows="2" 
                              placeholder="Thank you for your business!">{safe_string(footer_text)}</textarea>
                    <small style="color: var(--text-muted);">Appears at the bottom of every invoice</small>
                </div>
            </div>
            
            <div style="display: flex; gap: 10px;">
                <button type="submit" class="btn btn-primary" style="padding: 12px 30px;">GOOD: Save Template</button>
                <a href="/settings" class="btn btn-secondary">Cancel</a>
                <button type="button" class="btn btn-secondary" onclick="previewInvoice()" style="margin-left: auto;">👁️ Preview</button>
            </div>
        </form>
        
        <!-- Preview Modal -->
        <div id="previewModal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.8); z-index: 1000; align-items: center; justify-content: center; overflow-y: auto; padding: 20px;">
            <div style="background: white; max-width: 800px; width: 100%; border-radius: 12px; position: relative;">
                <button onclick="document.getElementById('previewModal').style.display='none'" 
                        style="position: absolute; top: 10px; right: 10px; background: #333; color: white; border: none; border-radius: 50%; width: 30px; height: 30px; cursor: pointer; font-size: 18px;">×</button>
                <div id="previewContent" style="padding: 40px;"></div>
            </div>
        </div>
        
        <script>
        // Update style selection visually
        document.querySelectorAll('input[name="template_style"]').forEach(radio => {{
            radio.addEventListener('change', function() {{
                document.querySelectorAll('input[name="template_style"]').forEach(r => {{
                    const div = r.parentElement.querySelector('div');
                    if (r.checked) {{
                        div.style.borderColor = 'var(--primary)';
                        div.style.background = 'rgba(99,102,241,0.1)';
                    }} else {{
                        div.style.borderColor = 'var(--border)';
                        div.style.background = 'transparent';
                    }}
                }});
            }});
        }});
        
        function previewInvoice() {{
            const style = document.querySelector('input[name="template_style"]:checked').value;
            const color = document.querySelector('input[name="primary_color"]').value;
            const showLogo = document.querySelector('input[name="show_logo"]').checked;
            const showBank = document.querySelector('input[name="show_bank_details"]').checked;
            const showVat = document.querySelector('input[name="show_vat_breakdown"]').checked;
            const showTerms = document.querySelector('input[name="show_payment_terms"]').checked;
            const terms = document.querySelector('input[name="payment_terms"]').value;
            const footer = document.querySelector('textarea[name="footer_text"]').value;
            const invTitle = document.querySelector('input[name="invoice_title"]').value || 'INVOICE';
            
            // Generate preview HTML
            const preview = generatePreview(style, color, showLogo, showBank, showVat, showTerms, terms, footer, invTitle);
            document.getElementById('previewContent').innerHTML = preview;
            document.getElementById('previewModal').style.display = 'flex';
        }}
        
        function generatePreview(style, color, showLogo, showBank, showVat, showTerms, terms, footer, invTitle) {{
            const biz = "{safe_string(business.get('name', 'Your Business'))}";
            const addr = "{safe_string(business.get('address', '123 Main Street'))}";
            const vat = "{safe_string(business.get('vat_number', ''))}";
            const bank = "{safe_string(business.get('bank_name', 'FNB'))}";
            const acc = "{safe_string(business.get('bank_account', '12345678'))}";
            const branch = "{safe_string(business.get('bank_branch', '250655'))}";
            
            let headerStyle = '';
            let titleStyle = '';
            
            if (style === 'modern') {{
                headerStyle = `border-left: 4px solid ${{color}}; padding-left: 20px;`;
                titleStyle = `color: ${{color}}; font-size: 32px;`;
            }} else if (style === 'classic') {{
                headerStyle = `border-bottom: 2px solid #333;`;
                titleStyle = `color: #333; font-size: 28px; font-family: Georgia, serif;`;
            }} else if (style === 'bold') {{
                headerStyle = `background: ${{color}}; color: white; padding: 20px; margin: -40px -40px 20px -40px; border-radius: 12px 12px 0 0;`;
                titleStyle = `color: white; font-size: 36px;`;
            }} else if (style === 'minimal') {{
                headerStyle = ``;
                titleStyle = `color: #333; font-size: 24px; font-weight: 300; letter-spacing: 4px;`;
            }}
            
            return `
                <div style="${{headerStyle}}">
                    <h1 style="${{titleStyle}}; margin: 0;">${{invTitle}}</h1>
                    <p style="color: #666; margin: 5px 0;">INV0001</p>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin: 30px 0;">
                    <div>
                        <h4 style="color: #888; margin: 0 0 5px 0; font-size: 12px;">FROM</h4>
                        <p style="margin: 0; font-weight: bold;">${{biz}}</p>
                        <p style="color: #666; margin: 5px 0;">${{addr}}</p>
                        ${{vat ? `<p style="color: #666; margin: 0;">VAT: ${{vat}}</p>` : ''}}
                    </div>
                    <div style="text-align: right;">
                        <h4 style="color: #888; margin: 0 0 5px 0; font-size: 12px;">TO</h4>
                        <p style="margin: 0; font-weight: bold;">Sample Customer</p>
                        <p style="color: #666; margin: 5px 0;">customer@email.com</p>
                        <p style="color: #666; margin: 0;">Date: ${{new Date().toLocaleDateString()}}</p>
                    </div>
                </div>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background: #f5f5f5;">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Description</th>
                            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #ddd;">Qty</th>
                            <th style="padding: 12px; text-align: right; border-bottom: 2px solid #ddd;">Price</th>
                            <th style="padding: 12px; text-align: right; border-bottom: 2px solid #ddd;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid #eee;">Sample Product</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #eee;">2</td>
                            <td style="padding: 12px; text-align: right; border-bottom: 1px solid #eee;">R500.00</td>
                            <td style="padding: 12px; text-align: right; border-bottom: 1px solid #eee;">R1,000.00</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border-bottom: 1px solid #eee;">Another Item</td>
                            <td style="padding: 12px; text-align: center; border-bottom: 1px solid #eee;">1</td>
                            <td style="padding: 12px; text-align: right; border-bottom: 1px solid #eee;">R750.00</td>
                            <td style="padding: 12px; text-align: right; border-bottom: 1px solid #eee;">R750.00</td>
                        </tr>
                    </tbody>
                </table>
                
                <div style="display: flex; justify-content: flex-end;">
                    <div style="width: 250px;">
                        ${{showVat ? `
                            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee;">
                                <span style="color: #666;">Subtotal</span>
                                <span>R1,750.00</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee;">
                                <span style="color: #666;">VAT (15%)</span>
                                <span>R262.50</span>
                            </div>
                        ` : ''}}
                        <div style="display: flex; justify-content: space-between; padding: 12px 0; font-size: 20px; font-weight: bold; color: ${{color}};">
                            <span>TOTAL</span>
                            <span>R2,012.50</span>
                        </div>
                    </div>
                </div>
                
                ${{showBank ? `
                    <div style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                        <h4 style="margin: 0 0 10px 0; font-size: 12px; color: #888;">BANK DETAILS</h4>
                        <p style="margin: 0; font-size: 14px;">
                            <strong>${{bank}}</strong> | Acc: ${{acc}} | Branch: ${{branch}}
                        </p>
                    </div>
                ` : ''}}
                
                ${{showTerms ? `<p style="margin-top: 20px; color: #666; font-size: 14px;"><strong>Terms:</strong> ${{terms}}</p>` : ''}}
                
                ${{footer ? `<p style="margin-top: 20px; text-align: center; color: #888; font-style: italic;">${{footer}}</p>` : ''}}
            `;
        }}
        
        // Close modal on outside click
        document.getElementById('previewModal').addEventListener('click', function(e) {{
            if (e.target === this) this.style.display = 'none';
        }});
        </script>
        '''
        
        return render_page("Invoice Template", content, user, "settings")
    
    
    @app.route("/api/settings/business", methods=["POST"])
    @login_required
    def api_settings_business():
        """Save business settings"""
        
        try:
            user = Auth.get_current_user()
            business = Auth.get_current_business()
            
            # Check if this is a NEW business creation (from ?action=new page)
            is_new = request.form.get("is_new", "") == "true" or request.referrer and "action=new" in request.referrer
            
            # CREATE NEW BUSINESS (for 2nd company)
            if is_new or not business:
                # LIMIT: Check how many businesses this user already has
                user_id = user.get("id")
                existing_businesses = db.get("businesses", {"user_id": user_id}) or []
                
                # MAXIMUM 2 BUSINESSES PER USER!
                if len(existing_businesses) >= 2:
                    # Return error - user already has 2 businesses
                    return f'''
                    <html>
                    <head>
                        <title>Limit Reached</title>
                        <style>
                            body {{ font-family: system-ui; max-width: 500px; margin: 100px auto; padding: 20px; text-align: center; }}
                            .card {{ background: #fee; border: 2px solid #f44; border-radius: 12px; padding: 30px; }}
                            h2 {{ color: #c00; margin-bottom: 20px; }}
                            p {{ color: #666; line-height: 1.6; }}
                            a {{ display: inline-block; margin-top: 20px; padding: 10px 20px; background: #6366f1; color: white; text-decoration: none; border-radius: 6px; }}
                        </style>
                    </head>
                    <body>
                        <div class="card">
                            <h2>[!] Business Limit Reached</h2>
                            <p>You can only create <strong>2 businesses</strong> per account.</p>
                            <p>You already have:</p>
                            <ul style="text-align:left;">
                                {"".join(f"<li>{b.get('business_name', b.get('name', 'Unnamed'))}</li>" for b in existing_businesses)}
                            </ul>
                            <p>If you need to manage more businesses, please contact support to upgrade your plan.</p>
                            <a href="/settings">← Back to Settings</a>
                        </div>
                    </body>
                    </html>
                    '''
                
                # Get user_id - CRITICAL for multi-tenant!
                user_id = user.get("id") if user else session.get("user_id")
                
                if not user_id:
                    app.logger.error("[BUSINESS] Cannot create business - no user_id!")
                    return redirect("/settings?error=no_user")
                
                new_biz = {
                    "id": generate_id(),
                    "name": request.form.get("name", "My Business"),
                    "industry_type": request.form.get("industry_type", "retail_general"),
                    "reg_number": request.form.get("reg_number", ""),
                    "vat_number": request.form.get("vat_number", ""),
                    "phone": request.form.get("phone", ""),
                    "email": request.form.get("email", ""),
                    "address": request.form.get("address", ""),
                    "bank_name": request.form.get("bank_name", ""),
                    "bank_account": request.form.get("bank_account", ""),
                    "bank_branch": request.form.get("bank_branch", ""),
                    "currency": "ZAR",
                    "tax_rate": 15,
                    "active": True,
                    "created_at": now(),
                    "user_id": user_id,
                    "owner_id": user_id,
                    "business_name": request.form.get("name", "My Business"),
                }
                
                success, result = db.save("businesses", new_biz)
                
                if not success:
                    app.logger.error(f"[BUSINESS] Failed to create: {result}")
                    return redirect("/settings?error=create_failed")
                
                # Switch to the new business
                session["business_id"] = new_biz["id"]
                
                flash_msg = f"GOOD: New business '{new_biz['name']}' created successfully!"
                return redirect("/settings")
            
            # UPDATE EXISTING BUSINESS
            biz_id = business.get("id") if business else None
            user_id = user.get("id") if user else session.get("user_id")
            
            # DEBUG: Log what we have
            logger.info(f"[SETTINGS DEBUG] business object: {business}")
            logger.info(f"[SETTINGS DEBUG] biz_id: {biz_id}")
            logger.info(f"[SETTINGS DEBUG] user_id: {user_id}")
            logger.info(f"[SETTINGS DEBUG] session business_id: {session.get('business_id')}")
            
            # If biz_id is None, try to get it from session
            if not biz_id:
                biz_id = session.get("business_id")
                logger.info(f"[SETTINGS DEBUG] Got biz_id from session: {biz_id}")
            
            if not biz_id:
                logger.error("[SETTINGS] No business ID found!")
                return redirect("/settings?error=No+business+ID+found")
            
            updates = {
                "name": request.form.get("name", ""),
                "industry_type": request.form.get("industry_type", "retail_general"),
                "reg_number": request.form.get("reg_number", ""),
                "vat_number": request.form.get("vat_number", ""),
                "phone": request.form.get("phone", ""),
                "email": request.form.get("email", ""),
                "address": request.form.get("address", ""),
                "bank_name": request.form.get("bank_name", ""),
                "bank_account": request.form.get("bank_account", ""),
                "bank_branch": request.form.get("bank_branch", ""),
            }
            
            logger.info(f"[SETTINGS] Saving business {biz_id} for user {user_id}")
            logger.info(f"[SETTINGS] Updates: {updates}")
            
            # START from the existing business record to preserve ALL columns
            # This prevents NOT NULL violations on columns we don't show in the form
            save_data = {}
            if business:
                save_data = {k: v for k, v in business.items() if v is not None}
            
            # Apply form updates on top
            save_data.update(updates)
            
            # Ensure id is set
            save_data["id"] = biz_id
            
            # Sync name ↔ business_name (DB might have either/both columns)
            biz_name_val = updates.get("name") or business.get("name") or business.get("business_name", "Business") if business else "Business"
            save_data["name"] = biz_name_val
            save_data["business_name"] = biz_name_val
            
            # Preserve critical fields
            if business:
                save_data["user_id"] = business.get("user_id", user_id)
                save_data["owner_id"] = business.get("owner_id", business.get("user_id", user_id))
                save_data["created_at"] = business.get("created_at", now())
            
            logger.info(f"[SETTINGS] Full upsert data keys: {list(save_data.keys())}")
            
            success, result = db.save("businesses", save_data)
            
            logger.info(f"[SETTINGS] Save result: success={success}, result={result}")
            
            if success:
                # CRITICAL: Clear ALL caches so next page load gets fresh data!
                Auth.clear_cache()
                session.pop("_biz_cache", None)
                session.pop("businesses_cache", None)
                session.pop("business_name", None)  # Also clear the name cache
                session["_biz_cache"] = None  # Explicitly set to None
                logger.info(f"[SETTINGS] Business '{updates.get('name')}' saved successfully - caches cleared")
                return redirect("/settings?saved=1")
            else:
                logger.error(f"[SETTINGS] Business save failed: {result}")
                import urllib.parse
                error_encoded = urllib.parse.quote(str(result)[:100])
                return redirect(f"/settings?error={error_encoded}")
            
        except Exception as e:
            logger.error(f"[SETTINGS] Business save error: {e}")
            import urllib.parse
            error_encoded = urllib.parse.quote(str(e)[:100])
            return redirect(f"/settings?error={error_encoded}")
    
    
    @app.route("/api/gl-migrate", methods=["GET", "POST"])
    @login_required
    def api_gl_migrate():
        """
        Migrate existing GL journals from ClickAI default codes to the business's
        actual COA codes (from Sage/Xero import).
        
        GET  = preview (shows what would change)
        POST = apply the migration
        """
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        user = Auth.get_current_user()
        
        if not biz_id:
            return jsonify({"error": "No business selected"})
        
        # Build the GL map from COA
        global _gl_map_cache
        _gl_map_cache = {}  # Clear cache
        gl_map = build_gl_map(biz_id)
        
        if not gl_map:
            return jsonify({"error": "No chart_of_accounts found for this business. Import a Sage/Xero COA first.", "gl_map": {}})
        
        # Build reverse map: ClickAI default code → Sage code
        # e.g. "1300" → "2100/005" (because gl_map has "stock" → "2100/005" and CLICKAI_DEFAULTS has "stock" → "1300")
        migration_map = {}  # old_code → new_code
        for role, sage_code in gl_map.items():
            default_code = CLICKAI_DEFAULTS.get(role)
            if default_code and default_code != sage_code:
                migration_map[default_code] = {"new_code": sage_code, "role": role}
        
        # Manual mappings for codes NOT in CLICKAI_DEFAULTS but clearly belong to a Sage range
        # e.g. "4400" was used for salaries before migration, Sage uses "4400/000"
        _manual_extras = {
            "4400": ("4400/000", "salaries_manual"),
            "4001": ("4000", "sales_other"),
            "4002": ("4000", "sales_services"),
            "4003": ("4000", "sales_misc"),
            "5002": ("5100", "purchases_other"),
        }
        # Only add if the target code actually exists in COA (validate)
        coa = db.get("chart_of_accounts", {"business_id": biz_id}) or []
        coa_codes = set(str(a.get("account_code", "") or a.get("code", "")).strip() for a in coa)
        for old_code, (new_code, role_label) in _manual_extras.items():
            if old_code not in migration_map and new_code in coa_codes:
                migration_map[old_code] = {"new_code": new_code, "role": role_label}
        
        if not migration_map:
            return jsonify({"message": "Nothing to migrate — COA codes match ClickAI defaults.", "gl_map": gl_map})
        
        # Get all journals for this business
        all_journals = db.get("journals", {"business_id": biz_id}) or []
        
        # Count what needs to change
        changes = []
        for j in all_journals:
            old_code = j.get("account_code", "")
            if old_code in migration_map:
                changes.append({
                    "journal_id": j.get("id"),
                    "date": j.get("date", ""),
                    "description": j.get("description", "")[:60],
                    "reference": j.get("reference", ""),
                    "old_code": old_code,
                    "new_code": migration_map[old_code]["new_code"],
                    "role": migration_map[old_code]["role"],
                    "debit": j.get("debit", 0),
                    "credit": j.get("credit", 0),
                })
        
        # Also check journal_entries (OB entries)
        all_je = db.get("journal_entries", {"business_id": biz_id}) or []
        je_changes = []
        for je in all_je:
            old_code = je.get("account_code", "")
            if old_code in migration_map:
                je_changes.append({
                    "je_id": je.get("id"),
                    "account": je.get("account", ""),
                    "old_code": old_code,
                    "new_code": migration_map[old_code]["new_code"],
                    "role": migration_map[old_code]["role"],
                })
        
        if request.method == "GET":
            # Preview mode
            summary = {}
            for c in changes:
                key = f"{c['old_code']} → {c['new_code']} ({c['role']})"
                summary[key] = summary.get(key, 0) + 1
            
            return jsonify({
                "mode": "PREVIEW — POST to this URL to apply",
                "business": business.get("name", "?"),
                "gl_map": gl_map,
                "migration_map": {k: v["new_code"] + f" ({v['role']})" for k, v in migration_map.items()},
                "journals_to_migrate": len(changes),
                "journal_entries_to_migrate": len(je_changes),
                "total_journals_in_db": len(all_journals),
                "summary": summary,
                "sample_changes": changes[:10],
            })
        
        # POST = Apply migration
        migrated = 0
        failed = 0
        
        for c in changes:
            try:
                success = db.update("journals", c["journal_id"], {"account_code": c["new_code"]}, biz_id)
                if success:
                    migrated += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"[GL MIGRATE] Failed journal {c['journal_id']}: {e}")
                failed += 1
        
        je_migrated = 0
        for jc in je_changes:
            try:
                success = db.update("journal_entries", jc["je_id"], {"account_code": jc["new_code"]}, biz_id)
                if success:
                    je_migrated += 1
            except:
                pass
        
        # Clear GL map cache so next request picks up fresh data
        _gl_map_cache = {}
        
        logger.info(f"[GL MIGRATE] Done: {migrated} journals migrated, {failed} failed, {je_migrated} OB entries migrated")
        
        return jsonify({
            "success": True,
            "message": f"Migration complete: {migrated} journals + {je_migrated} OB entries migrated to Sage codes",
            "journals_migrated": migrated,
            "journals_failed": failed,
            "je_migrated": je_migrated,
        })
    
    
    @app.route("/api/debug-gl")
    @login_required
    def api_debug_gl():
        """Shows GL map and COA for debugging"""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"error": "No business selected"})
        
        global _gl_map_cache
        _gl_map_cache = {}
        gl_map = build_gl_map(biz_id)
        
        coa = db.get("chart_of_accounts", {"business_id": biz_id}) or []
        coa_dump = [{"code": a.get("account_code","") or a.get("code",""),
                     "name": a.get("account_name","") or a.get("name",""),
                     "category": a.get("category","")} for a in coa]
        
        # Show what gl() returns for each role
        resolved = {}
        for role in CLICKAI_DEFAULTS:
            resolved[role] = gl(biz_id, role)
        
        return jsonify({
            "business": business.get("name", "?"),
            "coa_count": len(coa),
            "gl_map_from_coa": gl_map,
            "resolved_all_roles": resolved,
            "coa_all": coa_dump,
        })
    
    
    @app.route("/api/switch-business", methods=["POST"])
    @login_required
    def api_switch_business():
        """Switch to a different business"""
        
        try:
            data = request.get_json()
            business_id = data.get("business_id", "") if data else ""
            
            if business_id:
                session["business_id"] = business_id
                # Update business_name in session
                biz = db.get_one("businesses", business_id)
                if biz:
                    session["business_name"] = biz.get("name", "Business")
                # Clear cache so next request loads new business
                Auth.clear_cache()
                return jsonify({"success": True})
            
            return jsonify({"success": False, "error": "No business ID provided"})
        except Exception as e:
            logger.error(f"[SWITCH] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/create-business", methods=["POST"])
    @login_required
    def api_create_business():
        """Create a new business"""
        
        try:
            user = Auth.get_current_user()
            
            data = request.get_json() if request.is_json else request.form
            name = data.get("name", "New Business") if data else "New Business"
            
            new_biz = {
                "id": generate_id(),
                "name": name,
                "created_at": now(),
                "user_id": user.get("id") if user else None
            }
            
            ok, result = db.save("businesses", new_biz)
            
            if ok:
                session["business_id"] = new_biz["id"]
                return jsonify({"success": True, "business_id": new_biz["id"]})
            
            return jsonify({"success": False, "error": str(result)})
        except Exception as e:
            logger.error(f"[CREATE BIZ] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/settings/payfast", methods=["POST"])
    @login_required
    def api_settings_payfast():
        """Save PayFast payment settings"""
        try:
            business = Auth.get_current_business()
            if not business:
                flash("No business selected", "error")
                return redirect("/settings")
            
            update = {
                "id": business["id"],
                "payfast_merchant_id": request.form.get("payfast_merchant_id", "").strip(),
                "payfast_merchant_key": request.form.get("payfast_merchant_key", "").strip(),
                "payfast_passphrase": request.form.get("payfast_passphrase", "").strip()
            }
            
            success, _ = db.save("businesses", update)
            if success:
                flash("PayFast settings saved! Online payments are now enabled on your invoices.", "success")
            else:
                flash("Error saving PayFast settings", "error")
        except Exception as e:
            flash(f"Error: {str(e)}", "error")
        
        return redirect("/settings")
    
    
    @app.route("/api/settings/email", methods=["POST"])
    @login_required
    def api_settings_email():
        """Save email settings"""
        
        try:
            business = Auth.get_current_business()
            if not business:
                flash("No business selected", "error")
                return redirect("/settings")
            
            updates = {
                "id": business.get("id"),
                "smtp_host": request.form.get("smtp_host", ""),
                "smtp_port": request.form.get("smtp_port", ""),
                "smtp_user": request.form.get("smtp_user", ""),
                "smtp_pass": request.form.get("smtp_pass", ""),
            }
            
            # Only update password if provided
            if not updates["smtp_pass"]:
                del updates["smtp_pass"]
            
            db.save("businesses", updates)
            flash("Email settings saved", "success")
            
            return redirect("/settings")
        except Exception as e:
            logger.error(f"[SETTINGS EMAIL] Error: {e}")
            flash(f"Error saving email settings: {str(e)}", "error")
            return redirect("/settings")
    
    
    @app.route("/api/settings/scan-inbox", methods=["POST"])
    @login_required
    def api_settings_scan_inbox():
        """Save scanner inbox (IMAP) settings"""
        
        business = Auth.get_current_business()
        if not business:
            flash("No business found", "error")
            return redirect("/settings")
        
        imap_user = request.form.get("imap_user", "").strip()
        imap_pass = request.form.get("imap_pass", "").strip()
        imap_host = request.form.get("imap_host", "imap.gmail.com").strip()
        imap_port = request.form.get("imap_port", "993").strip()
        
        logger.info(f"[SCANNER] Saving scanner inbox for business {business.get('id')}: user={imap_user}, host={imap_host}")
        
        updates = {
            "id": business.get("id"),
            "imap_host": imap_host,
            "imap_port": imap_port,
            "imap_user": imap_user,
        }
        
        # Only update password if provided
        if imap_pass:
            updates["imap_pass"] = imap_pass
        
        success, result = db.save("businesses", updates)
        
        if success:
            logger.info(f"[SCANNER] Scanner inbox saved successfully: {imap_user}")
            flash(f"Scanner inbox saved: {imap_user}", "success")
        else:
            logger.error(f"[SCANNER] Failed to save scanner inbox: {result}")
            flash(f"Failed to save: {result}", "error")
        
        return redirect("/settings")
    
    
    @app.route("/api/settings/whatsapp", methods=["POST"])
    @login_required
    def api_settings_whatsapp():
        """Save WhatsApp settings"""
        
        business = Auth.get_current_business()
        if not business:
            return redirect("/settings")
        
        updates = {
            "id": business.get("id"),
            "whatsapp_phone": request.form.get("whatsapp_phone", ""),
            "whatsapp_token": request.form.get("whatsapp_token", ""),
            "whatsapp_account_id": request.form.get("whatsapp_account_id", ""),
        }
        
        # Only update token if provided
        if not updates["whatsapp_token"]:
            del updates["whatsapp_token"]
        
        db.save("businesses", updates)
        logger.info(f"[SETTINGS] WhatsApp saved for {business.get('name')}")
        
        return redirect("/settings")
    
    

    logger.info("[SETTINGS] All settings routes registered ✓")
