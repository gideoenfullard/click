# -*- coding: utf-8 -*-
# ==============================================================================
# CLICK AI - BANKING MODULE
# ==============================================================================
# Extracted from clickai.py for maintainability
# Contains: Banking page, Bank import, Categorize, Zane suggest, Delete all
# ==============================================================================

import os
import re
import io
import csv
import json
import logging
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from flask import request, jsonify, session, redirect, flash

logger = logging.getLogger(__name__)


def register_banking_routes(app, db, login_required, Auth, render_page,
                            generate_id, money, safe_string, now, today,
                            gl, create_journal_entry, log_allocation,
                            has_reactor_hud, jarvis_hud_header, jarvis_techline,
                            extract_json_from_text,
                            BankLearning, IndustryKnowledge, InvoiceMatch, RecordFactory,
                            JARVIS_HUD_CSS, THEME_REACTOR_SKINS,
                            BANKING_KNOWLEDGE_LOADED,
                            get_relevant_banking_knowledge, format_banking_knowledge):
    """Register all Banking routes with the Flask app."""

    @app.route("/banking")
    @login_required
    def banking_page():
        """Bank Reconciliation - Smart Dashboard"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        # Get ALL transactions, not just unmatched
        all_transactions = db.get("bank_transactions", {"business_id": biz_id}) if biz_id else []
        all_transactions = sorted(all_transactions, key=lambda x: x.get("date", ""), reverse=True)
        
        # NOTE: InvoiceMatch.match_all_transactions removed from page load — was causing 6+ second delays
        # Matching now happens at IMPORT time (see api_banking_import) and on-demand via Zane
        
        auto_matched = [t for t in all_transactions if (t.get("auto_matched") or t.get("invoice_matched")) and not t.get("manually_reviewed")]
        suggested = [t for t in all_transactions if t.get("suggested_category") and not t.get("matched") and t.get("suggestion_confidence", 0) < 0.85]
        needs_attention = [t for t in all_transactions if not t.get("matched") and not t.get("suggested_category")]
        already_done = [t for t in all_transactions if t.get("matched")]
        
        # Get expense categories
        expense_categories = IndustryKnowledge.get_expense_categories(biz_id) if biz_id else ["General Expenses"]
        category_options = "".join([f'<option value="{c}">{c}</option>' for c in expense_categories])
        
        # Add common categories
        extra_cats = ["Customer Payment", "Supplier Payment", "POS Deposit", "Owner Drawings", "Owner Capital Introduced", "Loan", "Loan Repayment", "Refund", "Transfer", "Ignore"]
        for cat in extra_cats:
            if cat not in expense_categories:
                category_options += f'<option value="{cat}">{cat}</option>'
        
        # Stats
        total_count = len(all_transactions)
        auto_count = len(auto_matched)
        suggested_count = len(suggested)
        needs_count = len(needs_attention)
        done_count = len(already_done)
        
        # Calculate totals for unmatched
        unmatched = [t for t in all_transactions if not t.get("matched")]
        total_debit = sum(float(t.get("debit", 0)) for t in unmatched)
        total_credit = sum(float(t.get("credit", 0)) for t in unmatched)
        
        # Build rows for each section
        def build_row(txn, show_approve=False, show_suggestion=True):
            txn_id = txn.get("id", "")
            debit = float(txn.get("debit", 0))
            credit = float(txn.get("credit", 0))
            desc = safe_string(txn.get("description", "-"))
            suggested_cat = txn.get("suggested_category", "")
            confidence = txn.get("suggestion_confidence", 0)
            match_ref = txn.get("match_reference", "")
            match_type = txn.get("match_type", "")
            
            # Suggestion display
            suggestion_html = ""
            if show_suggestion and suggested_cat:
                conf_pct = int(confidence * 100)
                if match_type == "invoice":
                    suggestion_html = f'<div style="font-size:11px;color:#22d3ee;margin-top:3px;">Invoice match: {suggested_cat}</div>'
                    if match_ref:
                        suggestion_html += f'<div style="font-size:10px;color:var(--text-muted);">{match_ref}</div>'
                elif confidence >= 0.85:
                    suggestion_html = f'<div style="font-size:11px;color:var(--green);margin-top:3px;">{suggested_cat} ({conf_pct}%)</div>'
                elif confidence >= 0.6:
                    suggestion_html = f'<div style="font-size:11px;color:var(--yellow);margin-top:3px;">{suggested_cat}? ({conf_pct}%)</div>'
                else:
                    suggestion_html = f'<div style="font-size:11px;color:var(--text-muted);margin-top:3px;">Maybe {suggested_cat}?</div>'
                
                if match_ref and match_type != "invoice":
                    suggestion_html += f'<div style="font-size:10px;color:var(--text-muted);">{match_ref}</div>'
            # Action buttons
            txn_date = txn.get("date", "")
            safe_desc = desc.replace("'", "\\'").replace('"', '&quot;')
            if show_approve and suggested_cat and confidence >= 0.6:
                action_html = f'''
                <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center;">
                    <button onclick="approveMatch('{txn_id}', '{suggested_cat}')" class="btn" style="padding:5px 10px;font-size:11px;background:var(--green);border:none;color:white;border-radius:6px;">GOOD: {suggested_cat}</button>
                    <button onclick="askZaneBank('{txn_id}', '{safe_desc}', {debit}, {credit}, '{txn_date}')" class="btn" style="padding:5px 10px;font-size:11px;background:var(--primary);border:none;color:white;border-radius:6px;">Ask Zane</button>
                </div>
                '''
            else:
                action_html = f'''
                <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center;">
                    <button onclick="askZaneBank('{txn_id}', '{safe_desc}', {debit}, {credit}, '{txn_date}')" class="btn" style="padding:7px 14px;font-size:12px;background:var(--primary);border:none;color:white;border-radius:6px;font-weight:600;">Ask Zane</button>
                    <select class="form-input" style="width:120px;padding:4px;font-size:11px;" onchange="categorizeTransaction('{txn_id}', this.value, '{safe_desc}')">
                        <option value="">Manual...</option>
                        {category_options}
                    </select>
                </div>
                '''
            
            return f'''
            <tr data-id="{txn_id}">
                <td style="white-space:nowrap;">{txn.get("date", "-")}</td>
                <td>
                    <div style="max-width:300px;">{desc}</div>
                    {suggestion_html}
                </td>
                <td style="text-align:right;color:var(--red);white-space:nowrap;">{money(debit) if debit > 0 else "-"}</td>
                <td style="text-align:right;color:var(--green);white-space:nowrap;">{money(credit) if credit > 0 else "-"}</td>
                <td>{action_html}</td>
            </tr>
            '''
        
        # Build sections
        auto_rows = "".join([build_row(t, show_approve=True) for t in auto_matched[:100]])
        suggested_rows = "".join([build_row(t, show_approve=True) for t in suggested[:100]])
        needs_rows = "".join([build_row(t, show_approve=False, show_suggestion=False) for t in needs_attention[:100]])
        
        # Build done rows - show allocated transactions so they're traceable
        done_rows_html = ""
        for t in already_done[:200]:
            txn_id = t.get("id", "")
            debit = float(t.get("debit", 0))
            credit = float(t.get("credit", 0))
            desc = safe_string(t.get("description", "-"))
            cat = t.get("category", t.get("suggested_category", ""))
            matched_at = str(t.get("matched_at", ""))[:10]
            done_rows_html += f'''
            <tr data-id="{txn_id}">
                <td style="white-space:nowrap;">{t.get("date", "-")}</td>
                <td><div style="max-width:300px;">{desc}</div></td>
                <td style="text-align:right;color:var(--red);white-space:nowrap;">{money(debit) if debit > 0 else "-"}</td>
                <td style="text-align:right;color:var(--green);white-space:nowrap;">{money(credit) if credit > 0 else "-"}</td>
                <td><span style="background:var(--green);color:white;padding:4px 10px;border-radius:4px;font-size:12px;">{cat}</span>
                    <div style="font-size:10px;color:var(--text-muted);margin-top:3px;">{matched_at}</div></td>
            </tr>
            '''
        
        content = f'''
        <style>
        .recon-tabs {{ display: flex; gap: 5px; margin-bottom: 20px; flex-wrap: wrap; }}
        .recon-tab {{ padding: 12px 20px; border-radius: 8px; cursor: pointer; background: var(--card); border: 1px solid var(--border); transition: all 0.2s; }}
        .recon-tab:hover {{ background: rgba(139,92,246,0.1); }}
        .recon-tab.active {{ background: var(--primary); color: white; border-color: var(--primary); }}
        .recon-tab .count {{ background: rgba(255,255,255,0.2); padding: 2px 8px; border-radius: 10px; margin-left: 8px; font-size: 12px; }}
        .recon-section {{ display: none; }}
        .recon-section.active {{ display: block; }}
        .bulk-bar {{ background: linear-gradient(135deg, rgba(16,185,129,0.2), rgba(16,185,129,0.1)); padding: 15px; border-radius: 8px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
        </style>
        
        <!-- HEADER -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;flex-wrap:wrap;gap:10px;">
            <h2 style="margin:0;">🏦 Bank Reconciliation</h2>
            <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <a href="/subscriptions" class="btn btn-secondary">📦 Recurring Expenses</a>
                <button class="btn btn-secondary" style="background:rgba(239,68,68,0.15);border-color:#ef4444;color:#ef4444;" onclick="deleteAllTransactions()">🗑️ Delete All</button>
                <label class="btn btn-primary" style="cursor:pointer;">
                    📥 Import Statement
                    <input type="file" accept=".csv,.pdf" style="display:none;" onchange="uploadStatement(this.files[0])">
                </label>
            </div>
        </div>
        
        <!-- SUMMARY CARDS -->
        <div class="stats-grid" style="margin-bottom:20px;">
            <div class="stat-card" style="background:rgba(16,185,129,0.1);border-color:var(--green);cursor:pointer;" onclick="showTab('auto')">
                <div class="stat-value" style="color:var(--green);">{auto_count}</div>
                <div class="stat-label">✅ Auto-Matched</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">High confidence - just approve</div>
            </div>
            <div class="stat-card" style="background:rgba(245,158,11,0.1);border-color:var(--yellow);cursor:pointer;" onclick="showTab('suggested')">
                <div class="stat-value" style="color:var(--yellow);">{suggested_count}</div>
                <div class="stat-label">🤖 AI Suggested</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">Review suggestions</div>
            </div>
            <div class="stat-card" style="background:rgba(239,68,68,0.1);border-color:var(--red);cursor:pointer;" onclick="showTab('needs')">
                <div class="stat-value" style="color:var(--red);">{needs_count}</div>
                <div class="stat-label">❓ Needs You</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">No suggestion - you decide</div>
            </div>
            <div class="stat-card" style="cursor:pointer;" onclick="showTab('done')">
                <div class="stat-value">{done_count}</div>
                <div class="stat-label">GOOD: Done</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:5px;">Already categorized</div>
            </div>
        </div>
        
        <!-- TABS -->
        <div class="recon-tabs">
            <div class="recon-tab active" onclick="showTab('auto')">✅ Auto-Matched <span class="count">{auto_count}</span></div>
            <div class="recon-tab" onclick="showTab('suggested')">🤖 Suggested <span class="count">{suggested_count}</span></div>
            <div class="recon-tab" onclick="showTab('needs')">❓ Needs You <span class="count">{needs_count}</span></div>
            <div class="recon-tab" onclick="showTab('done')">✅ Done <span class="count">{done_count}</span></div>
        </div>
        
        <!-- AUTO-MATCHED SECTION -->
        <div id="section-auto" class="recon-section active">
            {f"""
            <div class="bulk-bar">
                <div>
                    <strong>🎉 Zane matched {auto_count} transactions automatically!</strong><br>
                    <span style="font-size:13px;color:var(--text-muted);">These are high-confidence matches. Approve all or review individually.</span>
                </div>
                <button onclick="bulkApprove()" class="btn btn-primary" style="background:var(--green);">GOOD: Approve All ({auto_count})</button>
            </div>
            """ if auto_count > 0 else ""}
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="width:180px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {auto_rows or "<tr><td colspan='5' style='text-align:center;padding:40px;color:var(--text-muted);'>🎉 No auto-matched transactions waiting for approval!</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- SUGGESTED SECTION -->
        <div id="section-suggested" class="recon-section">
            <div class="card" style="margin-bottom:15px;background:rgba(245,158,11,0.1);">
                <p style="margin:0;"><strong>🤖 AI Suggestions</strong> - Zane thinks these might be correct, but confidence is lower. Please verify.</p>
            </div>
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="width:180px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {suggested_rows or "<tr><td colspan='5' style='text-align:center;padding:40px;color:var(--text-muted);'>No suggestions pending</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- NEEDS ATTENTION SECTION -->
        <div id="section-needs" class="recon-section">
            <div class="card" style="margin-bottom:15px;background:rgba(239,68,68,0.1);">
                <p style="margin:0;"><strong>❓ These need your help</strong> - Zane couldn't figure these out. Select a category to teach him!</p>
            </div>
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="width:180px;">Category</th>
                        </tr>
                    </thead>
                    <tbody>
                        {needs_rows or "<tr><td colspan='5' style='text-align:center;padding:40px;color:var(--green);'>🎉 Nothing needs your attention!</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- DONE / HISTORY SECTION -->
        <div id="section-done" class="recon-section">
            <div class="card" style="margin-bottom:15px;background:rgba(16,185,129,0.1);">
                <p style="margin:0;"><strong>Allocated Transactions</strong> - These have been categorized and recorded in your books.</p>
            </div>
            
            <div class="card">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width:100px;">Date</th>
                            <th>Description</th>
                            <th style="text-align:right;width:100px;">Out</th>
                            <th style="text-align:right;width:100px;">In</th>
                            <th style="width:150px;">Category</th>
                        </tr>
                    </thead>
                    <tbody>
                        {done_rows_html or "<tr><td colspan='5' style='text-align:center;padding:40px;color:var(--text-muted);'>No allocated transactions yet. Categorize transactions above and they will appear here.</td></tr>"}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- TIPS -->
        <div class="card" style="margin-top:20px;background:linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.05));">
            <h4 style="margin-top:0;">💡 How Zane Learns</h4>
            <p style="color:var(--text-muted);margin:0;">
                Every time you categorize a transaction, Zane remembers the pattern. Next time he sees "TELKOM", he'll know it's Telephone. 
                The more you teach him, the faster reconciliation becomes!
            </p>
        </div>
        
        <script>
        function showTab(tab) {{
            // Hide all sections
            document.querySelectorAll('.recon-section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.recon-tab').forEach(t => t.classList.remove('active'));
            
            // Show selected
            document.getElementById('section-' + tab).classList.add('active');
            event.target.closest('.recon-tab')?.classList.add('active');
        }}
        
        async function categorizeTransaction(id, category, description) {{
            if (!category) return;
            
            try {{
                const response = await fetch('/api/banking/categorize', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{id, category, description}})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    // Show what it was allocated to before removing
                    const row = document.querySelector(`tr[data-id="${{id}}"]`);
                    if (row) {{
                        // Replace the action column with the allocation result
                        const cells = row.querySelectorAll('td');
                        const lastCell = cells[cells.length - 1];
                        lastCell.innerHTML = `<span style="background:var(--green);color:white;padding:4px 10px;border-radius:4px;font-size:12px;font-weight:bold;">GOOD: ${{category}}</span>`;
                        row.style.background = 'rgba(16,185,129,0.15)';
                        row.style.transition = 'opacity 0.5s';
                        
                        // Fade out after 2 seconds so user can see where it went
                        setTimeout(() => {{
                            row.style.opacity = '0.4';
                        }}, 2000);
                        setTimeout(() => row.remove(), 3000);
                    }}
                    
                    // Update counts (simple decrement)
                    updateCounts();
                }} else {{
                    alert('Error: ' + data.error);
                }}
            }} catch (err) {{
                alert('Failed to categorize');
            }}
        }}
        
        async function approveMatch(id, category) {{
            await categorizeTransaction(id, category, '');
        }}
        
        // ═══════════════════════════════════════════════════════════
        // ASK ZANE - Collaborative bank transaction allocation
        // Uses dedicated lightweight AI endpoint (not full Zane brain)
        // ═══════════════════════════════════════════════════════════
        async function askZaneBank(txnId, description, debit, credit, date, clarificationAnswer) {{
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            // User chose "let me pick" — show dropdown
            if (clarificationAnswer === 'manual') {{
                showAllCategories(txnId, description, window._allCategories || [], 'No problem — pick the category:');
                return;
            }}
            
            // Show thinking state
            actionCell.innerHTML = `
                <div style="padding:8px;text-align:center;">
                    <div style="color:var(--primary);font-size:13px;font-weight:600;">Zane is checking...</div>
                </div>`;
            
            try {{
                const payload = {{ description, debit, credit, date }};
                if (clarificationAnswer) payload.clarification_answer = clarificationAnswer;
                
                const response = await fetch('/api/banking/zane-suggest', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(payload)
                }});
                
                const data = await response.json();
                
                // Store categories globally
                if (data.all_categories) window._allCategories = data.all_categories;
                
                // Zane asks with clickable plain-language options
                if (data.success && data.needs_clarification && data.options) {{
                    let optionsHtml = '';
                    const safeDesc = description.replace(/'/g, "\\\\'");
                    data.options.forEach(opt => {{
                        if (opt.value === 'manual') {{
                            // "None of these" -> show full dropdown
                            optionsHtml += `
                                <button onclick="showAllCategories('${{txnId}}','${{safeDesc}}',window._allCategories||[],'Pick the category:')"
                                        style="padding:8px 14px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;cursor:pointer;font-size:12px;margin:3px;">
                                    ${{opt.label}}
                                </button>`;
                        }} else {{
                            // Plain language option -> send back to Zane to map to GL category
                            optionsHtml += `
                                <button onclick="askZaneBank('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}', '${{opt.label}}')"
                                        style="padding:8px 14px;background:var(--primary);color:white;border:none;border-radius:6px;cursor:pointer;font-size:12px;margin:3px;">
                                    ${{opt.label}}
                                </button>`;
                        }}
                    }});
                    
                    actionCell.innerHTML = `
                        <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:260px;position:relative;">
                            <button onclick="resetAskZane('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                                    style="position:absolute;top:6px;right:8px;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:4px;line-height:1;" 
                                    title="Close">✕</button>
                            <div style="font-size:14px;font-weight:600;color:#8b5cf6;margin-bottom:10px;padding-right:20px;">
                                ${{data.question}}
                            </div>
                            <div style="display:flex;gap:4px;flex-wrap:wrap;">
                                ${{optionsHtml}}
                            </div>
                        </div>`;
                    return;
                }}
                
                // Safety: if clarification but no options came through, show dropdown
                if (data.success && data.needs_clarification) {{
                    showAllCategories(txnId, description, data.all_categories || [], data.question || 'Pick the category:');
                    return;
                }}
                
                // CASE 3: Zane knows the answer — show confirm
                if (data.success && data.category) {{
                    const confText = data.confidence >= 0.85 ? 'High confidence' : data.confidence >= 0.6 ? 'Medium' : 'Low';
                    const learnedBadge = data.source === 'learned' ? ' <span style="background:var(--green);color:white;padding:2px 6px;border-radius:3px;font-size:10px;">Learned</span>' : data.source === 'invoice_match' ? ' <span style="background:#22d3ee;color:black;padding:2px 6px;border-radius:3px;font-size:10px;">Invoice Match</span>' : '';
                    const vatWarning = data.vat_warning ? `<div style="background:#fef3c7;border-left:3px solid #f59e0b;padding:6px 8px;border-radius:4px;font-size:11px;color:#000;margin-top:8px;">${{data.vat_warning}}</div>` : '';
                    
                    actionCell.innerHTML = `
                        <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:260px;position:relative;">
                            <button onclick="resetAskZane('${{txnId}}', '${{description.replace(/'/g, "\\\\'")}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                                    style="position:absolute;top:6px;right:8px;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:4px;line-height:1;" 
                                    title="Close">✕</button>
                            <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px;">${{confText}}${{learnedBadge}}</div>
                            <div style="font-size:14px;font-weight:700;color:var(--text);margin-bottom:4px;">${{data.category}}</div>
                            <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;line-height:1.4;">${{data.reason}}</div>
                            ${{vatWarning}}
                            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;">
                                <button onclick="categorizeTransaction('${{txnId}}', '${{data.category}}', '${{description.replace(/'/g, "\\\\'")}}')" 
                                        style="padding:7px 16px;font-size:12px;background:var(--green);border:none;color:white;border-radius:6px;cursor:pointer;font-weight:600;">
                                    Yes, Allocate
                                </button>
                                <button onclick="showAllCategories('${{txnId}}', '${{description.replace(/'/g, "\\\\'")}}')" 
                                        style="padding:7px 16px;font-size:12px;background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;cursor:pointer;">
                                    Different category
                                </button>
                            </div>
                        </div>`;
                    row.dataset.categories = JSON.stringify(data.all_categories || []);
                }} else {{
                    showAllCategories(txnId, description, data.all_categories, data.reason || 'Not sure — please pick from the list.');
                }}
                
            }} catch (err) {{
                const safeDesc = description.replace(/'/g, "\\'");
                actionCell.innerHTML = `<div style="color:var(--red);font-size:12px;position:relative;padding-right:22px;">
                    <button onclick="resetAskZane('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}')" 
                            style="position:absolute;top:-2px;right:0;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:14px;line-height:1;" title="Close">✕</button>
                    Could not analyze — <a href="#" onclick="askZaneBank('${{txnId}}','${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}');return false;" style="color:var(--primary);">try again</a></div>`;
            }}
        }}
        
        // Reset Ask Zane popup back to original buttons
        function resetAskZane(txnId, description, debit, credit, date) {{
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            const safeDesc = description.replace(/'/g, "\\'");
            const catOptions = (window._allCategories || []).map(c => `<option value="${{c}}">${{c}}</option>`).join('');
            actionCell.innerHTML = `
                <div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center;">
                    <button onclick="askZaneBank('${{txnId}}', '${{safeDesc}}', ${{debit}}, ${{credit}}, '${{date}}')" class="btn" style="padding:7px 14px;font-size:12px;background:var(--primary);border:none;color:white;border-radius:6px;font-weight:600;">Ask Zane</button>
                    <select class="form-input" style="width:120px;padding:4px;font-size:11px;" onchange="categorizeTransaction('${{txnId}}', this.value, '${{safeDesc}}')">
                        <option value="">Manual...</option>
                        ${{catOptions}}
                    </select>
                </div>`;
        }}
        
        function showSearchableCategories(txnId, description, cats, hint) {{
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const actionCell = row ? row.querySelectorAll('td')[row.querySelectorAll('td').length - 1] : null;
            if (!actionCell) return;
            
            if (!cats || !cats.length) cats = window._allCategories || [];
            const safeDesc = description.replace(/'/g, "\\\\'");
            const uid = 'sc_' + txnId;
            
            // Get debit/credit from the row for resetAskZane
            const tds = row.querySelectorAll('td');
            const debitText = tds[2]?.textContent?.replace(/[^0-9.]/g, '') || '0';
            const creditText = tds[3]?.textContent?.replace(/[^0-9.]/g, '') || '0';
            const dateText = tds[0]?.textContent?.trim() || '';
            
            actionCell.innerHTML = `
                <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.25);border-radius:10px;padding:12px;min-width:220px;max-width:350px;position:relative;">
                    <button onclick="resetAskZane('${{txnId}}', '${{safeDesc}}', ${{debitText}}, ${{creditText}}, '${{dateText}}')" 
                            style="position:absolute;top:6px;right:8px;background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;padding:2px 6px;border-radius:4px;line-height:1;z-index:1;" 
                            title="Close">✕</button>
                    ${{hint ? `<div style="font-size:12px;color:#8b5cf6;margin-bottom:8px;line-height:1.4;padding-right:20px;">${{hint}}</div>` : ''}}
                    <input type="text" id="${{uid}}_search" placeholder="Type to search categories..." 
                        style="width:100%;padding:8px 12px;border-radius:6px;border:2px solid rgba(139,92,246,0.3);background:var(--input-bg);color:var(--text);font-size:13px;box-sizing:border-box;margin-bottom:6px;"
                        oninput="filterCats('${{uid}}')">
                    <div id="${{uid}}_list" style="max-height:200px;overflow-y:auto;border:1px solid var(--border);border-radius:6px;background:var(--card);">
                    </div>
                </div>`;
            
            // Populate list
            const listEl = document.getElementById(uid + '_list');
            window['_cats_' + uid] = cats;
            renderCatList(uid, cats, txnId, safeDesc);
            
            setTimeout(() => document.getElementById(uid + '_search')?.focus(), 100);
        }}
        
        function renderCatList(uid, cats, txnId, safeDesc) {{
            const listEl = document.getElementById(uid + '_list');
            if (!listEl) return;
            listEl.innerHTML = cats.map(c => 
                `<div onclick="categorizeTransaction('${{txnId}}', '${{c.replace(/'/g, "\\\\'")}}', '${{safeDesc}}')" 
                      style="padding:8px 12px;cursor:pointer;font-size:13px;border-bottom:1px solid var(--border);color:var(--text);transition:background 0.15s;"
                      onmouseover="this.style.background='rgba(139,92,246,0.15)'" 
                      onmouseout="this.style.background='transparent'">${{c}}</div>`
            ).join('');
            if (!cats.length) listEl.innerHTML = '<div style="padding:12px;color:var(--text-muted);font-size:12px;text-align:center;">No matching categories</div>';
        }}
        
        function filterCats(uid) {{
            const search = document.getElementById(uid + '_search')?.value.toLowerCase() || '';
            const allCats = window['_cats_' + uid] || [];
            const filtered = search ? allCats.filter(c => c.toLowerCase().includes(search)) : allCats;
            const txnId = uid.replace('sc_', '');
            const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
            const desc = row?.querySelector('td:nth-child(2)')?.textContent?.trim() || '';
            renderCatList(uid, filtered, txnId, desc.replace(/'/g, "\\\\'"));
        }}
        
        function showAllCategories(txnId, description, categoriesFromApi, message) {{
            let cats = categoriesFromApi;
            if (!cats || !cats.length) {{
                const row = document.querySelector(`tr[data-id="${{txnId}}"]`);
                if (row && row.dataset.categories) {{
                    try {{ cats = JSON.parse(row.dataset.categories); }} catch(e) {{}}
                }}
            }}
            if (!cats || !cats.length) cats = window._allCategories || [];
            showSearchableCategories(txnId, description, cats, message || '');
        }}
        
        async function bulkApprove() {{
            if (!confirm('Approve all {auto_count} auto-matched transactions?')) return;
            
            const rows = document.querySelectorAll('#section-auto tbody tr[data-id]');
            let approved = 0;
            
            for (const row of rows) {{
                const id = row.dataset.id;
                const btn = row.querySelector('button');
                if (btn) {{
                    const category = btn.onclick.toString().match(/approveMatch\\('.*?',\\s*'(.*?)'\\)/)?.[1];
                    if (category) {{
                        try {{
                            await fetch('/api/banking/categorize', {{
                                method: 'POST',
                                headers: {{'Content-Type': 'application/json'}},
                                body: JSON.stringify({{id, category, description: ''}})
                            }});
                            approved++;
                            row.style.display = 'none';
                        }} catch(e) {{}}
                    }}
                }}
            }}
            
            alert(`✅ Approved ${{approved}} transactions!`);
            location.reload();
        }}
        
        function updateCounts() {{
            // Simple reload after a few categorizations
            // Could be smarter but this works
        }}
        
        async function deleteAllTransactions() {{
            const count = {len(all_transactions)};
            if (!confirm(`⚠️ Delete ALL ${{count}} bank transactions?\\n\\nThis cannot be undone. You can re-import after.`)) return;
            if (!confirm(`Are you sure? This will delete ${{count}} transactions permanently.`)) return;
            
            try {{
                const response = await fetch('/api/banking/delete-all', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }});
                const data = await response.json();
                if (data.success) {{
                    alert(`✅ ${{data.message}}`);
                    location.reload();
                }} else {{
                    alert('❌ ' + data.error);
                }}
            }} catch (err) {{
                alert('❌ Delete failed: ' + err.message);
            }}
        }}
    
        async function uploadStatement(file) {{
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            // Show loading
            const btn = event.target.closest('label');
            const originalText = btn.innerHTML;
            const isPDF = file.name.toLowerCase().endsWith('.pdf');
            btn.innerHTML = isPDF ? '🤖 AI Reading PDF... (30-60s)' : '⏳ Importing...';
            
            try {{
                const response = await fetch('/api/banking/import', {{
                    method: 'POST',
                    body: formData
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    const stats = data.stats || {{}};
                    alert(`✅ Imported ${{stats.total || 0}} transactions!\\n\\n` +
                          `🤖 Auto-matched: ${{stats.auto_matched || 0}}\\n` +
                          `💡 Suggested: ${{stats.suggested || 0}}\\n` +
                          `❓ Needs you: ${{stats.needs_attention || 0}}`);
                    location.reload();
                }} else {{
                    alert('❌ ' + data.error);
                }}
            }} catch (err) {{
                alert('❌ Upload failed');
            }} finally {{
                btn.innerHTML = originalText;
            }}
        }}
        </script>
        '''
        
        # -- JARVIS: Banking HUD header --
        if has_reactor_hud():
            _match_pct = int((done_count / max(total_count, 1)) * 100)
            _j_alert = ""
            if needs_count > 0:
                _j_alert = f'<div class="j-ticker"><b>&#9888; RECONCILE</b><span class="jt-msg">{needs_count} transactions need attention &mdash; {money(total_debit)} debits, {money(total_credit)} credits unmatched</span><a href="#needsSection" class="jt-act">REVIEW NOW &rarr;</a></div>'
            
            _hud = jarvis_hud_header(
                page_name="BANKING",
                page_count=f"{total_count} TRANSACTIONS",
                left_items=[
                    ("TRANSACTIONS", str(total_count), "c", "", ""),
                    ("RECONCILED", str(done_count), "g", "g", "g"),
                    ("AUTO MATCHED", str(auto_count), "c", "", ""),
                    ("SUGGESTED", str(suggested_count), "o", "o", ""),
                ],
                right_items=[
                    ("NEEDS REVIEW", str(needs_count), "r", "r", "r"),
                    ("UNMATCHED DR", money(total_debit), "o", "o", "o"),
                    ("UNMATCHED CR", money(total_credit), "g", "g", "g"),
                    ("MATCH RATE", f"{_match_pct}%", "c", "", ""),
                ],
                reactor_size="page",
                alert_html=_j_alert
            )
            content = JARVIS_HUD_CSS + THEME_REACTOR_SKINS + _hud + content + jarvis_techline(f"BANKING <b>{total_count} TXN</b>")
        
        return render_page("Banking", content, user, "banking")
    
    
    @app.route("/api/banking/import", methods=["POST"])
    @login_required
    def api_banking_import():
        """Import bank statement CSV or PDF with SMART AUTO-MATCHING"""
        
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        try:
            file = request.files.get("file")
            if not file:
                return jsonify({"success": False, "error": "No file uploaded"})
            
            filename = file.filename.lower()
            
            # ═══════════════════════════════════════════════════════════════
            # PDF PARSING - Standard Bank, ABSA, FNB, Nedbank, Capitec
            # ═══════════════════════════════════════════════════════════════
            if filename.endswith('.pdf'):
                try:
                    import subprocess, tempfile, os
                    
                    # Save PDF to temp file
                    pdf_bytes = file.read()
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        tmp.write(pdf_bytes)
                        tmp_path = tmp.name
                    
                    # First try text extraction
                    pdf_text = ""
                    try:
                        result = subprocess.run(['pdftotext', '-layout', tmp_path, '-'], capture_output=True, text=True, timeout=30)
                        pdf_text = result.stdout.strip()
                        logger.info(f"[BANK IMPORT] pdftotext extracted {len(pdf_text)} chars")
                    except Exception as pdftotext_err:
                        logger.warning(f"[BANK IMPORT] pdftotext failed: {pdftotext_err}")
                    
                    if not pdf_text:
                        try:
                            import pdfplumber
                            with pdfplumber.open(tmp_path) as pdf_doc:
                                for page in pdf_doc.pages:
                                    page_text = page.extract_text()
                                    if page_text:
                                        pdf_text += page_text + "\n"
                            logger.info(f"[BANK IMPORT] pdfplumber extracted {len(pdf_text)} chars")
                        except Exception as plumber_err:
                            logger.warning(f"[BANK IMPORT] pdfplumber failed: {plumber_err}")
                    
                    # If text extraction failed (scanned PDF), use Claude AI via images
                    if not pdf_text or len(pdf_text) < 50:
                        logger.info(f"[BANK IMPORT] Scanned PDF detected (text={len(pdf_text) if pdf_text else 0} chars) - using AI to read")
                        
                        try:
                            import base64
                            from PIL import Image as PILImage
                            import io as _io
                            all_transactions = []
                            
                            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
                            if not api_key:
                                os.unlink(tmp_path)
                                return jsonify({"success": False, "error": "AI API key not configured"})
                            
                            # Convert PDF pages to images — 150 DPI is enough for bank statements
                            page_images = []
                            try:
                                from pdf2image import convert_from_path
                                pil_images = convert_from_path(tmp_path, dpi=150)
                                for img in pil_images:
                                    buf = _io.BytesIO()
                                    img.convert('RGB').save(buf, format='JPEG', quality=75)
                                    page_images.append(buf.getvalue())
                                logger.info(f"[BANK IMPORT] pdf2image converted {len(page_images)} pages at 150dpi")
                            except Exception as img_err:
                                logger.warning(f"[BANK IMPORT] pdf2image failed ({img_err}), trying pdfplumber")
                                page_images = []
                                try:
                                    import pdfplumber as _plumber
                                    with _plumber.open(tmp_path) as pdf_doc:
                                        for page in pdf_doc.pages:
                                            try:
                                                page_img = page.to_image(resolution=150)
                                                pil_img = page_img.annotated if hasattr(page_img, 'annotated') else page_img.original
                                                # Force RGB - handles mode P, RGBA, LA, L etc
                                                if pil_img.mode != 'RGB':
                                                    pil_img = pil_img.convert('RGBA').convert('RGB')
                                                buf = _io.BytesIO()
                                                pil_img.save(buf, format='JPEG', quality=75)
                                                page_images.append(buf.getvalue())
                                            except Exception as page_err:
                                                logger.warning(f"[BANK IMPORT] pdfplumber page {page.page_number} error: {page_err}")
                                                # Try alternative: render without annotations
                                                try:
                                                    pil_img = page_img.original
                                                    if pil_img.mode != 'RGB':
                                                        pil_img = pil_img.convert('RGBA').convert('RGB')
                                                    buf = _io.BytesIO()
                                                    pil_img.save(buf, format='JPEG', quality=75)
                                                    page_images.append(buf.getvalue())
                                                except Exception as page_err2:
                                                    logger.error(f"[BANK IMPORT] pdfplumber page {page.page_number} total failure: {page_err2}")
                                    logger.info(f"[BANK IMPORT] pdfplumber converted {len(page_images)} pages at 150dpi")
                                except Exception as plumber_img_err:
                                    logger.error(f"[BANK IMPORT] pdfplumber image conversion failed: {plumber_img_err}")
                            
                            # Prepare all page images — compress large ones
                            prepared_images = []
                            for page_num, img_bytes in enumerate(page_images):
                                try:
                                    _test_img = PILImage.open(_io.BytesIO(img_bytes))
                                    if _test_img.mode != 'RGB':
                                        _test_img = _test_img.convert('RGB')
                                        buf = _io.BytesIO()
                                        _test_img.save(buf, format='JPEG', quality=75)
                                        img_bytes = buf.getvalue()
                                except Exception:
                                    pass
                                
                                # Compress if over 2MB
                                if len(img_bytes) > 2000000:
                                    img = PILImage.open(_io.BytesIO(img_bytes))
                                    img = img.convert('RGB')
                                    w, h = img.size
                                    if max(w, h) > 1400:
                                        ratio = 1400 / max(w, h)
                                        img = img.resize((int(w*ratio), int(h*ratio)), PILImage.LANCZOS)
                                    buf = _io.BytesIO()
                                    img.save(buf, format='JPEG', quality=65)
                                    img_bytes = buf.getvalue()
                                
                                prepared_images.append(img_bytes)
                            
                            # ═══════════════════════════════════════════════════════════
                            # BATCH PAGES INTO GROUPS — send multiple pages per API call
                            # Each image ~200-600KB at 150dpi, API limit ~20MB
                            # Batch 4 pages per call to stay safe and fast
                            # Uses Haiku for OCR — 10x cheaper, just as accurate for data extraction
                            # ═══════════════════════════════════════════════════════════
                            PAGES_PER_BATCH = 4
                            batches = []
                            for i in range(0, len(prepared_images), PAGES_PER_BATCH):
                                batches.append(prepared_images[i:i + PAGES_PER_BATCH])
                            
                            logger.info(f"[BANK IMPORT] Processing {len(prepared_images)} pages in {len(batches)} batch(es)")
                            
                            prompt = """Extract ALL bank transactions from these bank statement page(s).
    
    Return ONLY a valid JSON array, no other text. Each transaction must have:
    - "date": "YYYY-MM-DD" format
    - "description": the FULL transaction description including ALL detail lines (see below)
    - "debit": amount as number (money going OUT, positive number) or 0
    - "credit": amount as number (money coming IN, positive number) or 0
    - "balance": the running balance after this transaction
    
    CRITICAL - DESCRIPTIONS:
    - Each transaction may span MULTIPLE LINES. The first line has the transaction type (e.g. "ELECTRONIC BANKING PAYMENT TO") and the next line(s) have the beneficiary/reference details (e.g. "MAR20 M FULLARD ERY5310:21")
    - You MUST combine ALL lines of a transaction into ONE description string
    - Example: if you see "CREDIT TRANSFER" on one line and "KHUPHUKANI" on the next, the description must be "CREDIT TRANSFER KHUPHUKANI"
    - Example: "ELECTRONIC BANKING PAYMENT TO" + "PRE10 PRESIDENT BOL ERY5310:21" = "ELECTRONIC BANKING PAYMENT TO PRE10 PRESIDENT BOL ERY5310:21"
    - NEVER use generic text like "Transaction" — always use the actual text from the statement
    
    RULES:
    - Payments OUT (debits, purchases, fees) go in "debit" field as POSITIVE numbers
    - Money IN (credits, deposits, settlements) go in "credit" field as POSITIVE numbers
    - Skip "BALANCE BROUGHT FORWARD" and "CLOSING BALANCE" rows
    - Read EVERY transaction row on EVERY page, do not skip any
    - Extract amounts exactly as shown on the statement
    - Include service fees, bank charges etc as debits
    - The "Page" column number is NOT the date — dates are in the "Date" column in YYYYMMDD format"""
                            
                            import requests as req
                            
                            def process_batch(batch_info):
                                """Process a batch of page images in a single API call"""
                                batch_idx, batch_imgs = batch_info
                                batch_txns = []
                                
                                # Build content array with all page images + prompt
                                content_parts = []
                                for img_bytes in batch_imgs:
                                    b64_img = base64.b64encode(img_bytes).decode('utf-8')
                                    content_parts.append({
                                        "type": "image",
                                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64_img}
                                    })
                                content_parts.append({"type": "text", "text": prompt})
                                
                                try:
                                    resp = req.post(
                                        "https://api.anthropic.com/v1/messages",
                                        headers={
                                            "x-api-key": api_key,
                                            "anthropic-version": "2023-06-01",
                                            "content-type": "application/json"
                                        },
                                        json={
                                            "model": "claude-haiku-4-5-20251001",
                                            "max_tokens": 16000,
                                            "messages": [{"role": "user", "content": content_parts}]
                                        },
                                        timeout=90
                                    )
                                    
                                    if resp.status_code != 200:
                                        logger.error(f"[BANK IMPORT] Batch {batch_idx+1} API error: {resp.status_code} - {resp.text[:500]}")
                                        return batch_txns
                                    
                                    ai_result = resp.json()
                                    ai_text = ""
                                    for block in ai_result.get("content", []):
                                        if block.get("type") == "text":
                                            ai_text += block["text"]
                                    
                                    logger.info(f"[BANK IMPORT] Batch {batch_idx+1} AI response: {len(ai_text)} chars, first 200: {ai_text[:200]}")
                                    
                                    import re as _re
                                    json_match = _re.search(r'\[.*\]', ai_text, _re.DOTALL)
                                    if json_match:
                                        try:
                                            batch_txns = json.loads(json_match.group(0))
                                            logger.info(f"[BANK IMPORT] Batch {batch_idx+1}: {len(batch_txns)} transactions from {len(batch_imgs)} pages")
                                        except json.JSONDecodeError as jde:
                                            logger.error(f"[BANK IMPORT] Batch {batch_idx+1} JSON decode error: {jde} - text around error: {ai_text[max(0,jde.pos-50):jde.pos+50]}")
                                    else:
                                        logger.error(f"[BANK IMPORT] Batch {batch_idx+1}: No JSON array found in AI response. Full text: {ai_text[:1000]}")
                                except Exception as batch_err:
                                    logger.error(f"[BANK IMPORT] Batch {batch_idx+1} error: {batch_err}")
                                
                                return batch_txns
                            
                            # Process batches concurrently if multiple
                            if len(batches) > 1:
                                from concurrent.futures import ThreadPoolExecutor as _TPE
                                with _TPE(max_workers=min(len(batches), 3)) as executor:
                                    results = list(executor.map(process_batch, enumerate(batches)))
                                for batch_txns in results:
                                    all_transactions.extend(batch_txns)
                            else:
                                # Single batch — just call directly
                                all_transactions.extend(process_batch((0, batches[0])))
                            
                            
                            os.unlink(tmp_path)
                            
                            if not all_transactions:
                                logger.error(f"[BANK IMPORT] AI returned 0 transactions from {len(prepared_images)} pages in {len(batches)} batches")
                                return jsonify({"success": False, "error": "AI could not read any transactions from the PDF — check logs for details"})
                            
                            # Convert to standard format
                            data_rows = []
                            for tx in all_transactions:
                                data_rows.append([
                                    str(tx.get("date", "")),
                                    str(tx.get("description", "")),
                                    str(tx.get("debit", 0)),
                                    str(tx.get("credit", 0)),
                                    str(tx.get("balance", 0))
                                ])
                            
                            date_col = 0
                            desc_col = 1
                            debit_col = 2
                            credit_col = 3
                            amount_col = None
                            
                            logger.info(f"[BANK IMPORT] AI extracted {len(data_rows)} total transactions from PDF")
                            
                        except Exception as ai_err:
                            os.unlink(tmp_path)
                            logger.error(f"[BANK IMPORT] AI PDF error: {ai_err}")
                            return jsonify({"success": False, "error": f"Failed to read scanned PDF: {str(ai_err)}"})
                    
                    else:
                        os.unlink(tmp_path)
                        # Text-based PDF parsing
                        import re
                        
                        transactions = []
                        lines = pdf_text.split('\n')
                        
                        logger.info(f"[BANK IMPORT] Text PDF: {len(lines)} lines")
                        
                        date_pattern = re.compile(r'(20\d{6})')
                        amount_pattern = re.compile(r'-?[\d,]+\.\d{2}')
                        
                        i = 0
                        while i < len(lines):
                            line = lines[i].strip()
                            if not line:
                                i += 1
                                continue
                            
                            if any(skip in line.upper() for skip in ['PAGE', 'DETAILS', 'SERVICE FEE', 'CURRENT ACCOUNT', 'STATEMENT', 'STANDARD BANK', 'COMPUTER GENERATED', 'END OF REPORT', 'BRANCH', 'VAT REGISTRATION', 'CLOSING BALANCE', 'BALANCE BROUGHT']):
                                i += 1
                                continue
                            
                            date_match = date_pattern.search(line)
                            if date_match:
                                raw_date = date_match.group(1)
                                tx_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                                
                                numbers = amount_pattern.findall(line)
                                
                                if len(numbers) >= 2:
                                    first_num_pos = line.find(numbers[0])
                                    description = line[:first_num_pos].strip()
                                    description = re.sub(r'^\d+\s+', '', description).strip()
                                    
                                    if not description:
                                        i += 1
                                        continue
                                    
                                    clean_nums = [float(n.replace(',', '')) for n in numbers]
                                    balance = clean_nums[-1]
                                    debit = 0.0
                                    credit = 0.0
                                    for n in clean_nums[:-1]:
                                        if n < 0:
                                            debit = abs(n)
                                        elif n > 0:
                                            credit = n
                                    
                                    if debit == 0 and credit == 0:
                                        i += 1
                                        continue
                                    
                                    transactions.append({
                                        "date": tx_date,
                                        "description": description,
                                        "debit": round(debit, 2),
                                        "credit": round(credit, 2),
                                        "balance": round(balance, 2)
                                    })
                            i += 1
                        
                        data_rows = []
                        for tx in transactions:
                            data_rows.append([tx["date"], tx["description"], tx["debit"], tx["credit"], tx["balance"]])
                        
                        date_col = 0
                        desc_col = 1
                        debit_col = 2
                        credit_col = 3
                        amount_col = None
                        
                        if not data_rows:
                            return jsonify({"success": False, "error": "Could not parse transactions from PDF text"})
                    
                except Exception as pdf_err:
                    logger.error(f"[BANK IMPORT] PDF parse error: {pdf_err}")
                    return jsonify({"success": False, "error": f"PDF parse error: {str(pdf_err)}"})
            
            else:
                # CSV PARSING (existing logic)
                content = file.read().decode('utf-8', errors='ignore')
                reader = csv.reader(io.StringIO(content))
                rows = list(reader)
            
                if len(rows) < 2:
                    return jsonify({"success": False, "error": "File is empty"})
                
                headers = [str(h).lower() if not isinstance(h, list) else str(h[0]).lower() for h in rows[0]]
                data_rows = rows[1:]
            
            def cell_str(cell):
                if cell is None:
                    return ""
                if isinstance(cell, (list, tuple)):
                    while isinstance(cell, (list, tuple)) and cell:
                        cell = cell[0]
                    return str(cell).strip() if cell is not None else ""
                return str(cell).strip()
            
            # For CSV: clean data and find columns
            if not filename.endswith('.pdf'):
                data_rows = [[cell_str(cell) for cell in row] for row in data_rows]
                
                # Find columns
                date_col = desc_col = amount_col = debit_col = credit_col = None
                
                for i, h in enumerate(headers):
                    if "date" in h:
                        date_col = i
                    elif "desc" in h or "narr" in h or "particular" in h:
                        desc_col = i
                    elif "amount" in h:
                        amount_col = i
                    elif "debit" in h:
                        debit_col = i
                    elif "credit" in h:
                        credit_col = i
            
            # ═══════════════════════════════════════════════════════════════
            # GET DATA FOR SMART MATCHING
            # ═══════════════════════════════════════════════════════════════
            
            # POS daily totals for matching deposits
            sales = db.get("sales", {"business_id": biz_id}) or []
            pos_daily = {}
            for s in sales:
                d = str(s.get("date", ""))[:10]
                if d not in pos_daily:
                    pos_daily[d] = 0
                pos_daily[d] += float(s.get("total", 0))
            
            # Outstanding invoices for matching customer payments
            invoices = db.get("invoices", {"business_id": biz_id}) or []
            outstanding = [i for i in invoices if i.get("status") != "paid"]
            
            # Customers for name matching
            customers = db.get("customers", {"business_id": biz_id}) or []
            customer_names = {c.get("name", "").upper(): c for c in customers if c.get("name")}
            
            # Known expense keywords
            expense_keywords = {
                "SARS": "Tax",
                "TELKOM": "Telephone",
                "VODACOM": "Telephone",
                "MTN": "Telephone",
                "CELL C": "Telephone",
                "ESKOM": "Electricity",
                "CITY POWER": "Electricity",
                "MUNICIPAL": "Municipal Charges",
                "ENGEN": "Fuel",
                "SHELL": "Fuel",
                "SASOL": "Fuel",
                "CALTEX": "Fuel",
                "BP ": "Fuel",
                "TOTAL ": "Fuel",
                "MAKRO": "Stock Purchase",
                "BUILDERS": "Stock Purchase",
                "CASHBUILD": "Stock Purchase",
                "TAKEALOT": "General Expenses",
                "AMAZON": "General Expenses",
                "PAYROLL": "Salaries",
                "SALARY": "Salaries",
                "WAGES": "Salaries",
                "INSURANCE": "Insurance",
                "OUTSURANCE": "Insurance",
                "SANTAM": "Insurance",
                "DISCOVERY": "Insurance",
                "RENT": "Rent",
                "LEASE": "Rent",
                "BANK CHARGE": "Bank Charges",
                "SERVICE FEE": "Bank Charges",
                "INTEREST": "Interest",
            }
            
            imported = 0
            auto_matched = 0
            suggested = 0
            
            for row in data_rows:
                try:
                    txn_date = row[date_col] if date_col is not None else today()
                    description = row[desc_col] if desc_col is not None else ""
                    
                    if amount_col is not None:
                        amt_str = row[amount_col].replace(",", "").replace("R", "").replace(" ", "").strip()
                        amount = float(amt_str or 0)
                        debit = abs(amount) if amount < 0 else 0
                        credit = amount if amount > 0 else 0
                    elif debit_col is not None and credit_col is not None:
                        deb_str = row[debit_col].replace(",", "").replace("R", "").replace(" ", "").strip()
                        cred_str = row[credit_col].replace(",", "").replace("R", "").replace(" ", "").strip()
                        debit = float(deb_str or 0)
                        credit = float(cred_str or 0)
                        amount = credit - debit
                    else:
                        continue
                    
                    if not description:
                        continue
                    
                    desc_upper = description.upper()
                    
                    # Skip non-transaction rows (balance lines, headers, etc)
                    skip_phrases = ['BALANCE BROUGHT', 'BROUGHT FORWARD', 'OPENING BALANCE', 
                                   'CLOSING BALANCE', 'BALANCE CARRIED', 'CARRIED FORWARD',
                                   'B/F', 'C/F', 'STATEMENT BALANCE']
                    if any(skip in desc_upper for skip in skip_phrases):
                        logger.info(f"[BANK] Skipping non-transaction row: {description[:60]}")
                        continue
                    
                    # Also skip rows with zero amount (just balance lines)
                    if debit == 0 and credit == 0 and amount == 0:
                        continue
                    
                    # ═══════════════════════════════════════════════════════════════
                    # SMART MATCHING LOGIC
                    # ═══════════════════════════════════════════════════════════════
                    
                    match_type = None
                    match_category = None
                    match_confidence = 0
                    match_reference = None
                    
                    # 1. TRY: Match credit to POS daily total
                    if credit > 0:
                        # Normalize date for comparison
                        txn_date_str = str(txn_date)[:10]
                        if txn_date_str in pos_daily:
                            pos_total = pos_daily[txn_date_str]
                            # Allow 1% tolerance for bank fees
                            if abs(credit - pos_total) < (pos_total * 0.01 + 1):
                                match_type = "pos_deposit"
                                match_category = "POS Deposit"
                                match_confidence = 0.95
                                match_reference = f"POS {txn_date_str}"
                                auto_matched += 1
                    
                    # 2. TRY: Match credit to outstanding invoice
                    if credit > 0 and not match_type:
                        for inv in outstanding:
                            inv_total = float(inv.get("total", 0))
                            cust_name = (inv.get("customer_name") or "").upper()
                            
                            # Exact amount match + customer name in description
                            if abs(credit - inv_total) < 1 and cust_name and cust_name[:5] in desc_upper:
                                match_type = "customer_payment"
                                match_category = "Customer Payment"
                                match_confidence = 0.9
                                match_reference = f"{inv.get('invoice_number')} - {inv.get('customer_name')}"
                                auto_matched += 1
                                break
                            # Just amount match
                            elif abs(credit - inv_total) < 1:
                                match_type = "possible_payment"
                                match_category = "Customer Payment?"
                                match_confidence = 0.6
                                match_reference = f"Maybe {inv.get('invoice_number')}?"
                    
                    # 3. TRY: Match debit to known expense keywords
                    if debit > 0 and not match_type:
                        for keyword, category in expense_keywords.items():
                            if keyword in desc_upper:
                                match_type = "expense_keyword"
                                match_category = category
                                match_confidence = 0.85
                                suggested += 1
                                break
                    
                    # 4. TRY: Check learned patterns
                    if not match_type:
                        pattern_match = BankLearning.suggest_category(biz_id, description)
                        if pattern_match.get("confidence", 0) > 0.5:
                            match_type = "learned_pattern"
                            match_category = pattern_match.get("category")
                            match_confidence = pattern_match.get("confidence", 0)
                            if match_confidence >= 0.8:
                                auto_matched += 1
                            else:
                                suggested += 1
                    
                    txn = {
                        "id": generate_id(),
                        "business_id": biz_id,
                        "date": txn_date,
                        "description": description,
                        "amount": amount,
                        "debit": debit,
                        "credit": credit,
                        "match_type": match_type,
                        "suggested_category": match_category,
                        "suggestion_confidence": match_confidence,
                        "match_reference": match_reference,
                        "matched": match_confidence >= 0.85,  # Auto-approve high confidence
                        "auto_matched": match_confidence >= 0.85,
                        "created_at": now()
                    }
                    
                    db.save("bank_transactions", txn)
                    imported += 1
                    
                except Exception as row_err:
                    logger.warning(f"[BANK] Row error: {row_err}")
                    continue
            
            # Run invoice matching on imported transactions (was previously on every page load)
            try:
                all_txns = db.get("bank_transactions", {"business_id": biz_id}) or []
                unmatched = [t for t in all_txns if not t.get("matched") and not t.get("invoice_matched")]
                if unmatched:
                    InvoiceMatch.match_all_transactions(biz_id, unmatched)
                    # Save matched results
                    for t in unmatched:
                        if t.get("invoice_matched"):
                            db.save("bank_transactions", t)
                    logger.info(f"[BANK IMPORT] Invoice matching completed on {len(unmatched)} transactions")
            except Exception as match_err:
                logger.warning(f"[BANK IMPORT] Invoice matching failed (non-critical): {match_err}")
            
            needs_attention = imported - auto_matched - suggested
            
            return jsonify({
                "success": True, 
                "message": f"Imported {imported} transactions",
                "stats": {
                    "total": imported,
                    "auto_matched": auto_matched,
                    "suggested": suggested,
                    "needs_attention": max(0, needs_attention)
                }
            })
            
        except Exception as e:
            logger.error(f"[BANK] Import error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/banking/categorize", methods=["POST"])
    @login_required
    def api_banking_categorize():
        """Categorize a bank transaction and learn from it"""
        
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        try:
            data = request.get_json()
            txn_id = data.get("id")
            category = data.get("category")
            description = data.get("description", "")
            
            if not txn_id or not category:
                return jsonify({"success": False, "error": "Missing data"})
            
            # Get transaction
            txn = db.get_one("bank_transactions", txn_id)
            if not txn:
                return jsonify({"success": False, "error": "Transaction not found"})
            
            # Use transaction description if none provided
            if not description:
                description = txn.get("description", "")
            
            # Mark as matched and save category
            txn["matched"] = True
            txn["manually_reviewed"] = True
            txn["category"] = category
            txn["matched_at"] = now()
            db.save("bank_transactions", txn)
            
            # LEARN from this categorization!
            if description:
                BankLearning.learn_from_categorization(biz_id, description, category)
            
            # Handle based on category type
            debit = float(txn.get("debit", 0))
            credit = float(txn.get("credit", 0))
            amount = float(txn.get("amount", 0))
            
            # Get GL code from comprehensive lookup
            gl_code = IndustryKnowledge.get_gl_code(category)
            
            # SARS: No VAT claim on fuel or entertainment
            no_vat_cats = ["fuel", "entertainment", "meals", "membership"]
            is_no_vat = any(nv in category.lower() for nv in no_vat_cats)
            
            # === SPECIAL CATEGORIES with custom GL logic ===
            # These need specific double-entry treatment, not generic expense/income
            
            special_categories = {
                # Money IN specials
                "Customer Payment",      # Debit Bank, Credit Debtors (1200)
                "POS Deposit",           # Debit Bank, Credit Petty Cash (1100)
                "Supplier Payment",      # Money OUT: Debit Creditors (2000), Credit Bank
                "VAT Payment to SARS",   # Debit VAT Output (2100), Credit Bank - paying liability
                "Owner Drawings",        # Debit Drawings (3200), Credit Bank
                "Owner Capital Introduced",  # Debit Bank, Credit Capital (3000)
                "Loan",                  # IN: Debit Bank, Credit Loan (2300). OUT: Debit Loan (2300), Credit Bank
                "Loan Repayment",        # Debit Loan (2300), Credit Bank
                "Transfer Between Accounts",  # No journal - need both accounts
                "Ignore",               # No journal
            }
            
            txn_date = txn.get("date", today())
            ref = f"BNK-{txn_id[:8]}"
            desc_short = description[:50]
            
            # Determine if money out (expense) or money in (income/payment)
            if debit > 0 or amount < 0:
                expense_amount = debit if debit > 0 else abs(amount)
                expense_rounded = round(expense_amount, 2)
                
                if category in special_categories:
                    # --- SPECIAL MONEY OUT HANDLING ---
                    if category == "Owner Drawings":
                        create_journal_entry(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "drawings"), "debit": expense_rounded, "credit": 0},  # Drawings
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "Loan Repayment":
                        create_journal_entry(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "uif"), "debit": expense_rounded, "credit": 0},  # Loan liability down
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "Loan":
                        # Money OUT as Loan = repaying loan principal
                        create_journal_entry(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "uif"), "debit": expense_rounded, "credit": 0},  # Loan liability down
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "Customer Payment":
                        # Money OUT to customer = refund from bank
                        create_journal_entry(biz_id, txn_date, f"Customer refund: {desc_short}", ref, [
                            {"account_code": gl(biz_id, "sales"), "debit": expense_rounded, "credit": 0},   # Sales reversed
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},    # Bank out
                        ])
                    elif category == "Supplier Payment":
                        logger.info(f"[BANK] === Supplier Payment R{expense_amount} — starting processing ===")
                        create_journal_entry(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "creditors"), "debit": expense_rounded, "credit": 0},
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},
                        ])
                        
                        _matched_supplier = None
                        try:
                            match_ref = txn.get("match_reference", "")
                            if match_ref:
                                inv_num = match_ref.split(" - ")[0] if " - " in match_ref else match_ref
                                if inv_num:
                                    s_invoices = db.get("supplier_invoices", {"business_id": biz_id, "invoice_number": inv_num})
                                    if s_invoices:
                                        s_inv = s_invoices[0]
                                        s_inv["status"] = "paid"
                                        s_inv["paid_date"] = txn_date
                                        db.save("supplier_invoices", s_inv)
                                        if s_inv.get("supplier_id"):
                                            _matched_supplier = db.get_one("suppliers", s_inv["supplier_id"])
                            if not _matched_supplier:
                                _desc_upper = (txn.get("description") or "").upper()
                                _all_suppliers = db.get("suppliers", {"business_id": biz_id}) or []
                                for _s in _all_suppliers:
                                    _sname = (_s.get("name") or "").upper().strip()
                                    if _sname and len(_sname) >= 3 and _sname[:6] in _desc_upper:
                                        _matched_supplier = _s
                                        break
                            if _matched_supplier:
                                _old_bal = float(_matched_supplier.get("balance", 0))
                                _new_bal = max(0, _old_bal - expense_amount)
                                db.update("suppliers", _matched_supplier["id"], {"balance": _new_bal})
                        except Exception as e:
                            logger.error(f"[BANK] Supplier matching error (payment still created): {e}")
                        
                        # === SUPPLIER PAYMENT — ALWAYS RUNS ===
                        try:
                            logger.info(f"[BANK] Creating supplier payment...")
                            _sp = {
                                "id": generate_id(),
                                "business_id": biz_id,
                                "supplier_id": _matched_supplier.get("id", "") if _matched_supplier else "",
                                "supplier_name": _matched_supplier.get("name", description[:60]) if _matched_supplier else description[:60],
                                "amount": float(expense_amount),
                                "date": txn_date,
                                "method": "eft",
                                "reference": ref,
                                "source": "banking_recon",
                                "created_at": now()
                            }
                            _sps, _spe = db.save("supplier_payments", _sp)
                            logger.info(f"[BANK] Supplier payment save result: success={_sps}")
                        except Exception as e:
                            logger.error(f"[BANK] Supplier payment CRASHED: {e}")
                    elif category == "VAT Payment to SARS":
                        # Paying VAT liability - NOT an expense!
                        create_journal_entry(biz_id, txn_date, desc_short, ref, [
                            {"account_code": gl(biz_id, "vat_output"), "debit": expense_rounded, "credit": 0},  # VAT Output liability down
                            {"account_code": gl(biz_id, "bank"), "debit": 0, "credit": expense_rounded},   # Bank
                        ])
                    elif category == "POS Deposit":
                        # POS Deposit as money OUT doesn't apply - skip
                        pass
                    # Transfer/Ignore = no journal entry
                    
                else:
                    # --- REGULAR EXPENSE ---
                    expense = RecordFactory.expense(
                        business_id=biz_id,
                        description=description,
                        amount=expense_amount,
                        date=txn_date,
                        category=category,
                        category_code=gl_code,
                        reference=f"Bank: {txn_id[:8]}"
                    )
                    db.save("expenses", expense)
                    
                    # Create journal entry with proper GL code
                    vat_amount = round(expense_amount * 15 / 115, 2) if not is_no_vat else 0
                    net_amount = round(expense_amount - vat_amount, 2)
                    
                    journal_entries = [
                        {"account_code": gl_code, "debit": net_amount, "credit": 0},
                    ]
                    if vat_amount > 0:
                        journal_entries.append({"account_code": gl(biz_id, "vat_input"), "debit": vat_amount, "credit": 0})
                    journal_entries.append({"account_code": gl(biz_id, "bank"), "debit": 0, "credit": round(expense_amount, 2)})
                    
                    create_journal_entry(biz_id, txn_date, desc_short, ref, journal_entries)
                    logger.info(f"[BANK] Created expense: {category} GL={gl_code} R{expense_amount}")
            
            elif credit > 0 or amount > 0:
                income_amount = credit if credit > 0 else amount
                income_rounded = round(income_amount, 2)
                
                if category == "Customer Payment":
                    logger.info(f"[BANK] === Customer Payment R{income_amount} — starting processing ===")
                    # Customer paying their account - reduce debtors
                    create_journal_entry(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "debtors"), "debit": 0, "credit": income_rounded},    # Debtors down
                    ])
                    
                    # Try to mark invoice as paid — in its own try/except so receipt ALWAYS runs
                    matched_invoice = None
                    matched_customer = None
                    try:
                        match_ref = txn.get("match_reference", "")
                        if match_ref:
                            inv_num = match_ref.split(" - ")[0] if " - " in match_ref else match_ref
                            inv_num = inv_num.replace("Maybe ", "").replace("?", "").strip()
                            if inv_num.startswith("INV"):
                                invoices = db.get("invoices", {"business_id": biz_id, "invoice_number": inv_num})
                                if invoices:
                                    matched_invoice = invoices[0]
                        
                        outstanding_inv = []
                        if not matched_invoice:
                            outstanding_inv = db.get("invoices", {"business_id": biz_id}) or []
                            outstanding_inv = [i for i in outstanding_inv if i.get("status") not in ("paid", "credited")]
                            desc_upper = (txn.get("description") or "").upper()
                            for inv in outstanding_inv:
                                inv_total = float(inv.get("total", 0))
                                cust_name = (inv.get("customer_name") or "").upper().strip()
                                if abs(income_amount - inv_total) < 1 and cust_name and len(cust_name) >= 3 and cust_name[:6] in desc_upper:
                                    matched_invoice = inv
                                    break
                        
                        if not matched_invoice and outstanding_inv:
                            amount_matches = [i for i in outstanding_inv if abs(income_amount - float(i.get("total", 0))) < 1]
                            if len(amount_matches) == 1:
                                matched_invoice = amount_matches[0]
                        
                        if matched_invoice:
                            matched_invoice["status"] = "paid"
                            matched_invoice["paid_date"] = txn_date
                            matched_invoice["paid_amount"] = income_amount
                            matched_invoice["paid_via"] = "banking_recon"
                            db.save("invoices", matched_invoice)
                            logger.info(f"[BANK] Marked {matched_invoice.get('invoice_number','?')} as PAID")
                            cust_id = matched_invoice.get("customer_id")
                            if cust_id:
                                try:
                                    customer = db.get_one("customers", cust_id)
                                    if customer:
                                        new_bal = max(0, float(customer.get("balance", 0)) - income_amount)
                                        db.update("customers", cust_id, {"balance": new_bal})
                                except: pass
                        else:
                            desc_upper = (txn.get("description") or "").upper()
                            all_customers = db.get("customers", {"business_id": biz_id}) or []
                            for c in all_customers:
                                cname = (c.get("name") or "").upper().strip()
                                if cname and len(cname) >= 3 and cname[:6] in desc_upper:
                                    matched_customer = c
                                    break
                            if matched_customer:
                                try:
                                    old_bal = float(matched_customer.get("balance", 0))
                                    new_bal = max(0, old_bal - income_amount)
                                    db.update("customers", matched_customer["id"], {"balance": new_bal})
                                except: pass
                    except Exception as e:
                        logger.error(f"[BANK] Invoice matching error (receipt still created): {e}")
                    
                    # === RECEIPT — ALWAYS RUNS ===
                    try:
                        logger.info(f"[BANK] Creating receipt...")
                        _rcid = ""
                        _rcname = description[:60]
                        if matched_invoice:
                            _rcid = matched_invoice.get("customer_id", "")
                            _rcname = matched_invoice.get("customer_name", description[:60])
                        elif matched_customer:
                            _rcid = matched_customer.get("id", "")
                            _rcname = matched_customer.get("name", description[:60])
                        _receipt = {
                            "id": generate_id(),
                            "business_id": biz_id,
                            "customer_id": _rcid,
                            "customer_name": _rcname,
                            "amount": float(income_amount),
                            "date": txn_date,
                            "method": "eft",
                            "reference": ref,
                            "source": "banking_recon",
                            "created_at": now()
                        }
                        _rs, _re = db.save("receipts", _receipt)
                        logger.info(f"[BANK] Receipt save result: success={_rs}")
                    except Exception as e:
                        logger.error(f"[BANK] Receipt CRASHED: {e}")
                                
                elif category == "POS Deposit":
                    # POS cash deposited into bank
                    create_journal_entry(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "cash"), "debit": 0, "credit": income_rounded},    # Cash On Hand down
                    ])
                    
                elif category == "Owner Capital Introduced":
                    create_journal_entry(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "capital"), "debit": 0, "credit": income_rounded},    # Capital up
                    ])
                    
                elif category == "Loan":
                    # Receiving loan funds
                    create_journal_entry(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": gl(biz_id, "uif"), "debit": 0, "credit": income_rounded},    # Loan liability up
                    ])
                    
                elif category == "Refund":
                    # Refund received - credit original expense
                    create_journal_entry(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},   # Bank up
                        {"account_code": "7900", "debit": 0, "credit": income_rounded},    # Sundry expenses reversed
                    ])
                    
                elif category in ["Transfer Between Accounts", "Ignore"]:
                    pass  # No journal entry
                    
                else:
                    # Regular income
                    create_journal_entry(biz_id, txn_date, desc_short, ref, [
                        {"account_code": gl(biz_id, "bank"), "debit": income_rounded, "credit": 0},
                        {"account_code": gl_code, "debit": 0, "credit": income_rounded},
                    ])
            
            # === ALLOCATION LOG ===
            try:
                if log_allocation:
                    _is_expense = debit > 0 or amount < 0
                    log_allocation(
                        business_id=biz_id, allocation_type="bank_categorize", source_table="bank_transactions", source_id=txn_id,
                        description=f"Bank: {description[:100]} → {category}",
                        amount=float(debit if debit > 0 else credit if credit > 0 else abs(amount)),
                        category=category, category_code=gl_code,
                        ai_reasoning=f"Bank transaction categorized as '{category}' (GL {gl_code}). {'Auto-matched' if txn.get('auto_categorized') else 'Manual review'}. Original desc: {description[:100]}",
                        ai_confidence="HIGH" if txn.get("auto_categorized") else "",
                        ai_worker="BankLearning" if txn.get("auto_categorized") else "",
                        supplier_name=txn.get("supplier_name", "") or description.split()[0][:30] if description else "",
                        payment_method="eft", reference=f"BNK-{txn_id[:8]}",
                        transaction_date=txn_date,
                        created_by=session.get("user_id", ""), created_by_name=""
                    )
            except Exception:
                pass
            
            return jsonify({"success": True, "message": f"Categorized as {category}"})
            
        except Exception as e:
            logger.error(f"[BANK] Categorize failed: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    
    @app.route("/api/banking/zane-suggest", methods=["POST"])
    @login_required
    def api_banking_zane_suggest():
        """
        Zane analyzes a bank transaction and suggests allocation.
        NOW WITH CLARIFICATION — Zane asks smart follow-up questions when needed!
        Returns: suggested category, reason, confidence, clarification if needed.
        """
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        biz_name = business.get("name", "Business") if business else "Business"
        
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})
        
        try:
            data = request.get_json()
            description = data.get("description", "")
            debit = float(data.get("debit", 0))
            credit = float(data.get("credit", 0))
            date = data.get("date", "")
            user_answer = data.get("clarification_answer", "")
            
            if not description:
                return jsonify({"success": False, "error": "No description"})
            
            # Get all available categories — comprehensive list
            all_category_names = IndustryKnowledge.get_all_category_names()
            
            # ═══ PRIORITY 1: SCANNED INVOICE MATCH — user already scanned this, trust it ═══
            if not user_answer:
                amount = debit if debit > 0 else credit
                direction = "out" if debit > 0 else "in"
                inv_match = InvoiceMatch.find_match(biz_id, description, amount, date, direction)
                if inv_match and inv_match.get("confidence", 0) >= 0.5:
                    logger.info(f"[BANK ZANE] Invoice match: '{description[:30]}' → {inv_match.get('category', '')}")
                    return jsonify({
                        "success": True,
                        "category": inv_match.get("category", ""),
                        "reason": inv_match.get("reason", "Matched to scanned invoice"),
                        "confidence": inv_match.get("confidence", 0.8),
                        "source": "invoice_match",
                        "needs_clarification": False,
                        "vat_warning": "",
                        "match_reference": inv_match.get("reference", ""),
                        "all_categories": all_category_names
                    })
            
            # ═══ PRIORITY 2: BANKLEARNING — user already categorized this type before ═══
            existing = BankLearning.suggest_category(biz_id, description)
            if existing and existing.get("confidence", 0) >= 0.85 and not user_answer:
                return jsonify({
                    "success": True,
                    "category": existing.get("category", ""),
                    "reason": f"I've seen this type of transaction {existing.get('times_seen', 1)} times before — always {existing.get('category')}.",
                    "confidence": existing.get("confidence", 0.85),
                    "source": "learned",
                    "needs_clarification": False,
                    "all_categories": all_category_names
                })
            
            # ═══ PRIORITY 3: KNOWN PATTERNS — obvious matches, still go through AI drill-down ═══
            if not user_answer:
                desc_upper = description.upper()
                
                # For EFTPOS: trust the CR/DR in the description, not the column
                if "EFTPOS" in desc_upper or "SETTLEMENT" in desc_upper:
                    if "SETTLEMENT CR" in desc_upper or " CR " in desc_upper:
                        logger.info(f"[BANK ZANE] EFTPOS CR: '{description[:40]}' → Sales — Card Machine")
                        return jsonify({
                            "success": True, "category": "Sales — Card Machine",
                            "reason": "Card machine settlement — money received from card sales.",
                            "confidence": 0.9, "source": "known_pattern",
                            "needs_clarification": False, "all_categories": all_category_names
                        })
                    elif "SETTLEMENT DR" in desc_upper or " DR " in desc_upper:
                        logger.info(f"[BANK ZANE] EFTPOS DR: '{description[:40]}' → Card Machine Fees")
                        return jsonify({
                            "success": True, "category": "Card Machine Fees",
                            "reason": "EFTPOS settlement fee charged by the bank.",
                            "confidence": 0.9, "source": "known_pattern",
                            "needs_clarification": False, "all_categories": all_category_names
                        })
                
                is_income = credit > 0
                
                # Map obvious descriptions to exact category names
                KNOWN_EXPENSE = {
                    "TELKOM": ("Telephone — Landline", "Telkom is your landline provider."),
                    "VODACOM": ("Cellphone / Mobile", "Vodacom mobile account."),
                    "MTN": ("Cellphone / Mobile", "MTN mobile account."),
                    "CELL C": ("Cellphone / Mobile", "Cell C mobile account."),
                    "RAIN ": ("Internet / WiFi", "Rain internet/data provider."),
                    "ESKOM": ("Electricity", "Eskom electricity account."),
                    "PREPAID ELEC": ("Electricity", "Prepaid electricity purchase."),
                    "BANK CHARGES": ("Bank Charges", "Monthly bank service fees."),
                    "SERVICE FEE": ("Bank Charges", "Bank service fee."),
                    "MONTHLY FEE": ("Bank Charges", "Monthly bank fee."),
                    "CASH DEPOSIT FEE": ("Bank Charges", "Bank cash deposit fee."),
                    "SARS": ("VAT Payment to SARS", "SARS tax payment."),
                    "SANTAM": ("Insurance — Business / Contents", "Santam insurance premium."),
                    "OUTSURANCE": ("Insurance — Business / Contents", "OUTsurance premium."),
                    "DISCOVERY": ("Insurance — Life / Key Person", "Discovery insurance/medical."),
                    "ENGEN": ("Fuel — Business Vehicle", "Fuel purchase at Engen."),
                    "SASOL ": ("Fuel — Business Vehicle", "Fuel purchase at Sasol."),
                    "SHELL ": ("Fuel — Business Vehicle", "Fuel purchase at Shell."),
                    "BP ": ("Fuel — Business Vehicle", "Fuel purchase at BP."),
                    "CALTEX": ("Fuel — Business Vehicle", "Fuel purchase at Caltex."),
                    "TOTAL GARAGE": ("Fuel — Business Vehicle", "Fuel purchase."),
                    "TAKEALOT": ("Office Supplies", "Online purchase from Takealot."),
                    "MAKRO": ("Stock Purchases — General", "Makro bulk purchase."),
                    "BUILDERS": ("Stock Purchases — Hardware", "Builders Warehouse hardware."),
                    "CASHBUILD": ("Stock Purchases — Hardware", "Cashbuild building materials."),
                    "GAME ": ("Office Supplies", "Game store purchase."),
                    "DSTV": ("DSTV / Streaming", "DStv subscription."),
                    "MULTICHOICE": ("DSTV / Streaming", "MultiChoice subscription."),
                    "NETFLIX": ("DSTV / Streaming", "Netflix streaming subscription."),
                    "UBER": ("Travel — Local", "Uber transport."),
                }
                
                KNOWN_INCOME = {
                    "SPEEDPOINT": ("Sales — Card Machine", "Speedpoint card machine settlement."),
                    "YOCO": ("Sales — Card Machine", "Yoco card payment settlement."),
                    "IKHOKHA": ("Sales — Card Machine", "iKhokha card payment settlement."),
                    "POS DEP": ("POS Deposit", "Point of sale deposit."),
                }
                
                # Check expense patterns (also catch credits/refunds from known expense providers)
                for keyword, (cat, reason) in KNOWN_EXPENSE.items():
                    if keyword in desc_upper:
                        if is_income:
                            reason = f"Credit/refund from {keyword.strip()} — verify if this should be {cat}."
                        logger.info(f"[BANK ZANE] Instant match: '{description[:30]}' → {cat}")
                        return jsonify({
                            "success": True, "category": cat, "reason": reason,
                            "confidence": 0.85 if is_income else 0.9, "source": "known_pattern",
                            "needs_clarification": False, "all_categories": all_category_names
                        })
                
                # Check income patterns  
                if is_income:
                    for keyword, (cat, reason) in KNOWN_INCOME.items():
                        if re.search(keyword, desc_upper):
                            logger.info(f"[BANK ZANE] Instant match: '{description[:30]}' → {cat}")
                            return jsonify({
                                "success": True, "category": cat, "reason": reason,
                                "confidence": 0.9, "source": "known_pattern",
                                "needs_clarification": False, "all_categories": all_category_names
                            })
            
            # ═══ PRIORITY 4: AI (Haiku) — smart drill-down for everything else ═══
            # Get recent learned patterns for context
            patterns = db.get("bank_patterns", {"business_id": biz_id}) or []
            pattern_examples = ""
            if patterns:
                recent = sorted(patterns, key=lambda p: p.get("times_seen", 0), reverse=True)[:10]
                pattern_examples = "\n".join([f"- {p.get('original_description', p.get('pattern', ''))} → {p.get('category', '')}" for p in recent])
            
            # Build focused AI prompt with comprehensive categories
            direction = "Payment out (expense)" if debit > 0 else "Payment in (income)"
            amount = debit if debit > 0 else credit
            all_categories_for_ai = IndustryKnowledge.build_category_list_for_ai()
            
            # Get SA-specific context for this transaction
            banking_context = ""
            if BANKING_KNOWLEDGE_LOADED:
                try:
                    bk_chunks = get_relevant_banking_knowledge(description, max_chunks=1)
                    if bk_chunks:
                        banking_context = format_banking_knowledge(bk_chunks)
                        logger.info(f"[BANK ZANE] Knowledge hit for '{description[:30]}'")
                except Exception:
                    pass
            
            prompt = f"""You are Zane, a bookkeeper. Pick a category for this bank transaction. Be direct — no filler, no emojis.
    {banking_context}
    
    DIRECTION: {"MONEY IN — this is income/deposit/payment received" if credit > 0 else "MONEY OUT — this is an expense/payment made"}
    Transaction: "{description}", {date}, R{amount:,.2f}
    {"THE USER SAYS THIS IS FOR: " + user_answer if user_answer else ""}
    
    Categories:
    {all_categories_for_ai}
    
    {f"Learned patterns from this business:{chr(10)}{pattern_examples}" if pattern_examples else ""}
    
    Two paths:
    1. You KNOW (Telkom=Telephone, Engen=Fuel, bank fees, etc): say it directly
    2. You DON'T KNOW: give 3-5 plain-language options. User clicks one, you map to the right category.
    
    {"If their answer '" + user_answer + "' is specific enough to pick ONE exact category, give the final answer. If still ambiguous, drill deeper with more options. Example: user says 'Fuel' — ask 'Business vehicle, garden equipment, or generator?'" if user_answer else ""}
    
    Example: "ACCOUNT PAYMENT CARTRACK" options: "Vehicle tracking subscription", "Fleet management fee", "Refund from Cartrack"
    ALWAYS include "None of these" as the last option.
    Fuel: warn no VAT claim on own use. Never use "General Expenses".
    
    JSON only — pick ONE:
    Know it: {{"needs_clarification":false,"category":"[exact]","reason":"[1 sentence]","confidence":"high","vat_warning":""}}
    Need more info: {{"needs_clarification":true,"question":"[plain question]","options":[{{"label":"[plain language]","value":"[short]"}},{{"label":"None of these","value":"manual"}}],"confidence":"medium","reason":""}}"""
    
            # Haiku — fast, cheap, smart enough for category matching
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 300,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=15
            )
            
            if resp.status_code != 200:
                logger.error(f"[BANK ZANE] API error: {resp.status_code} — {resp.text[:300]}")
                return jsonify({"success": False, "error": "AI unavailable", "all_categories": all_category_names})
            
            ai_text = resp.json().get("content", [{}])[0].get("text", "")
            logger.info(f"[BANK ZANE] Raw AI response for '{description[:30]}': {ai_text[:200]}")
            
            # Try to parse as JSON first (new format)
            suggestion = extract_json_from_text(ai_text)
            
            if suggestion and suggestion.get("needs_clarification"):
                # Zane needs to ask a question
                logger.info(f"[BANK ZANE] Asking clarification for '{description[:30]}'")
                return jsonify({
                    "success": True,
                    "needs_clarification": True,
                    "question": suggestion.get("question", ""),
                    "options": suggestion.get("options", []),
                    "reason": suggestion.get("reason", ""),
                    "confidence": {"hoog": 0.9, "high": 0.9, "medium": 0.7, "laag": 0.4, "low": 0.4}.get(str(suggestion.get("confidence", "medium")), 0.7),
                    "source": "ai",
                    "all_categories": all_category_names
                })
            
            if suggestion and suggestion.get("category"):
                category = suggestion["category"]
                reason = suggestion.get("reason", "")
                confidence = str(suggestion.get("confidence", "medium"))
                vat_warning = suggestion.get("vat_warning", "")
            else:
                # Fallback: parse old text format
                category = ""
                reason = ""
                confidence = "medium"
                vat_warning = ""
                
                for line in ai_text.strip().split("\n"):
                    line = line.strip()
                    if line.upper().startswith("CATEGORY:"):
                        category = line.split(":", 1)[1].strip()
                    elif line.upper().startswith("REASON:"):
                        reason = line.split(":", 1)[1].strip()
                    elif line.upper().startswith("CONFIDENCE:"):
                        confidence = line.split(":", 1)[1].strip().lower()
            
            # Validate category against available list — with SMART fuzzy matching
            valid = False
            
            # Try 1: Exact match
            for c in all_category_names:
                if c.lower() == category.lower():
                    category = c
                    valid = True
                    break
            
            # Try 2: Partial/contains match
            if not valid and category:
                for c in all_category_names:
                    if category.lower() in c.lower() or c.lower() in category.lower():
                        category = c
                        valid = True
                        break
            
            # Try 3: Word overlap match (e.g. "Telephone" matches "Telephone — Landline")
            if not valid and category:
                cat_words = set(category.lower().replace("—", "").replace("-", "").split())
                best_match = None
                best_overlap = 0
                for c in all_category_names:
                    c_words = set(c.lower().replace("—", "").replace("-", "").split())
                    overlap = len(cat_words & c_words)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = c
                if best_match and best_overlap >= 1:
                    category = best_match
                    valid = True
                    logger.info(f"[BANK ZANE] Fuzzy matched '{suggestion.get('category', category)}' → {category}")
            
            if not valid:
                logger.warning(f"[BANK ZANE] No valid category match for AI response: '{category}' from '{ai_text[:100]}'")
            
            conf_score = {"hoog": 0.9, "high": 0.9, "medium": 0.7, "laag": 0.4, "low": 0.4}.get(confidence, 0.7)
            
            logger.info(f"[BANK ZANE] '{description[:30]}' → {category} ({confidence})")
            
            return jsonify({
                "success": True,
                "category": category if valid else "",
                "reason": reason or "Not sure about this one — pick from the dropdown and I'll learn for next time.",
                "confidence": conf_score,
                "source": "ai",
                "needs_clarification": False,
                "vat_warning": vat_warning,
                "all_categories": all_category_names
            })
            
        except Exception as e:
            logger.error(f"[BANK ZANE] Error: {e}")
            try:
                cats = IndustryKnowledge.get_all_category_names()
            except:
                cats = ["General Expenses"]
            return jsonify({"success": False, "error": str(e), "all_categories": cats})
    
    
    @app.route("/api/banking/delete-all", methods=["POST"])
    @login_required
    def api_banking_delete_all():
        """Delete ALL bank transactions for current business — for re-import"""
        try:
            user = Auth.get_current_user()
            if not user:
                return jsonify({"success": False, "error": "Not logged in"})
            business = Auth.get_current_business()
            biz_id = business.get("id") if business else None
            if not biz_id:
                return jsonify({"success": False, "error": "No business selected"})
            
            # Get all transaction IDs
            all_txns = db.get("bank_transactions", {"business_id": biz_id}) or []
            if not all_txns:
                return jsonify({"success": True, "deleted": 0, "message": "No transactions to delete"})
            
            ids = [t["id"] for t in all_txns if "id" in t]
            success_count, failed_count = db.delete_many("bank_transactions", ids, business_id=biz_id)
            
            logger.info(f"[BANK DELETE ALL] Deleted {success_count} transactions for business {biz_id} ({failed_count} failed)")
            
            return jsonify({
                "success": True, 
                "deleted": success_count, 
                "failed": failed_count,
                "message": f"Deleted {success_count} bank transactions"
            })
        except Exception as e:
            logger.error(f"[BANK DELETE ALL] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    

    logger.info("[BANKING] All banking routes registered ✓")
