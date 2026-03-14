# CLICKAI BLUEPRINT v2.0
## Master Architecture & Development Reference
**Generated: 14 March 2026 — from live codebase analysis (v2.0.268-INTFIX)**

---

## 1. WHAT IS CLICKAI

ClickAI is an AI-powered business management platform for South African SMEs. It is NOT an accounting app with AI bolted on — it's an AI that runs your business. Built as a Flask monolith deployed on Fly.io (Johannesburg region) with Supabase (PostgreSQL) as the database.

**Owner/Sole Developer:** Deon Fullard
**Live Test Business:** Fulltech Stainless Tube CC (hardware/steel supplier, ~7,000+ stock items)
**Staff:** Daphne (admin/bookkeeping), Isaac & Piet (POS/cashier staff)
**AI Workers:** Zane (senior advisor/bookkeeper), Jacqo (OCR/scanning), Diane, Jayden

**Competitive Target:** Sage, Xero, QuickBooks — ClickAI's edge is AI intelligence + real SA business context.

---

## 2. TECH STACK

| Component | Technology |
|-----------|-----------|
| Backend | Python Flask (single `clickai.py` — 80,990 lines, 319 routes) |
| Database | Supabase (PostgreSQL via REST API) |
| AI Engine | Anthropic Claude API (claude-sonnet-4-6 for Zane) |
| Hosting | Fly.io (Johannesburg region, port 8080) |
| Frontend | Server-rendered HTML with inline CSS/JS (no React/Vue) |
| Auth | Session-based with in-memory cache (`Auth` class, 5min TTL) |
| Email | SMTP (Gmail app passwords, per-business SMTP config) |
| Payments | PayFast integration (SA payment gateway) |
| Dev Environment | Windows, `DEPLOY.bat` → git push → Fly.io auto-deploy |
| Deploy Path | `C:\Users\deonf\OneDrive\Desktop\click-main\click-main` |
| Git Config | fullarddeon@gmail.com / "Deon Fullard" |

---

## 3. FILE ARCHITECTURE

### Main Application
```
clickai.py                    — 80,990 lines, 319 routes, ALL core logic
```

### External Modules (all try/except imported)
```
clickai_allocation_log.py     — "Place of Safety" transaction ledger (/ledger)
clickai_cashup.py             — Blind cashup, X-Reading, Z-Reading, denomination counting
clickai_business_groups.py    — Cross-business insights and group management
clickai_bolt_pricer.py        — BoltPricer v4: weight-based fastener pricing (R/kg rates)
clickai_bolt_repricing.py     — Bulk bolt reprice preview + apply
clickai_fraud_guard.py        — Role-based invoice cancel/credit/delete restrictions + audit
clickai_order_scanner         — Order-to-Invoice pipeline (Jacqo OCR → Zane match → Jayden calc)
```

### RAG Knowledge Modules (keyword-matched, injected into Zane's prompt)
```
clickai_knowledge_base.py        — 32 chunks: General business/accounting guides
clickai_pulse_knowledge.py       — 37 chunks: Business strategy/analysis patterns
clickai_banking_knowledge.py     — 68 chunks: SA banking, reconciliation, statements
clickai_sars_knowledge.py        — 29 chunks: SARS eFiling, tax compliance
clickai_industry_knowledge.py    — 27 chunks: Industry benchmarks by business type
clickai_bookkeeping_knowledge.py — 24 chunks: Double-entry rules, journal patterns
clickai_transport_knowledge.py   — 21 chunks: Logistics, fleet, transport regulations
clickai_insurance_knowledge.py   — 7 chunks: SA business insurance (short-term, liability, fleet)
clickai_tax_strategy_knowledge.py— 8 chunks: Tax planning, deductions, CGT, entity structures
clickai_legal_knowledge.py       — (separate file) Contracts, labour law, BEE, CIPC
clickai_hr_knowledge.py          — (separate file) BCEA, discipline, leave, hiring
```
**Total RAG chunks: ~280+ across 11 knowledge modules**

---

## 4. KEY CODE LOCATIONS (line numbers in clickai.py)

| What | Line(s) | Notes |
|------|---------|-------|
| Imports + module loading | 1–160 | All try/except, flags like `CASHUP_LOADED` |
| `fulltech_addon` class | 166–848 | Embedded steel calculator + bolt weight tables |
| Flask app setup + middleware | 849–920 | `_start_timer`, `_enforce_role_access`, `_log_request_time` |
| Environment variables | 923–940 | `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, SMTP |
| Helper functions | 1023–2040 | `safe()`, `extract_json_from_text()`, `preprocess_image_for_ocr()`, `generate_id()`, `smart_stock_code()`, `next_document_number()`, `money()`, `safe_string()` |
| `EmailScanner` class | 1170–1670 | IMAP email checking, scan-to-email processing |
| `Email` class | 2079–2345 | SMTP sending, per-business SMTP config |
| `DB` class | 2347–3095 | Supabase REST wrapper: `get()`, `save()`, `delete()`, `get_one()`, `get_all_stock()`, `get_business_users()` |
| `RecordFactory` class | 3096–3700 | Schema-correct record builders for all entities |
| `ZaneMemory` class | 3705–3815 | Zane's cross-conversation memory system |
| `PayrollSettings` class | 3817–3995 | SA tax tables, UIF, SDL calculations |
| `ZANE_TOOLS` definition | 4004–4430 | 37 tool definitions for Claude function calling |
| Accounting knowledge base | 4436–5800 | Inline guides (chart of accounts, VAT, payroll, etc.) |
| `ZaneToolHandler` class | 5803–7760 | Executes all 37 Zane tools against DB |
| `build_zane_core_prompt()` | 7768–8270 | **THE prompt builder** — personality, rules, RAG injection |
| `call_zane_with_tools()` | 8275–8345 | Tool loop: max 8 turns, claude-sonnet-4-6, 90s timeout |
| `Brain` class | 8346–10645 | Opus-level report generation, briefings |
| `Actions` class | 10650–13000 | Executes Zane actions (CREATE_INVOICE, RECORD_PAYMENT, etc.) |
| `Context` class | 13010–13375 | Builds business context for Zane |
| `DailyBriefing` class | 13380–13900 | Morning briefing generation |
| `ReportEngine` class | 13905–14215 | Smart reports with AI analysis |
| `IndustryKnowledge` class | 14218–14740 | Industry-specific benchmarks |
| `ScannerMemory` class | 14742–14870 | Remembers supplier invoice formats |
| `CustomerIntelligence` class | 14871–15040 | Payment pattern analysis |
| `StockForecasting` class | 15043–15195 | Reorder prediction |
| `BankLearning` class | 15200–15425 | 80+ keyword rules, 30+ supplier rules for expense categorization |
| `InvoiceMatch` class | 15429–15715 | Auto-match bank transactions to invoices |
| `BusinessIntelligence` class | 15718–15760 | Consolidated intelligence |
| `TaxSaver` class | 15763–16345 | Travel log, asset register, tax deduction tracking |
| `Auth` class | 16349–16600 | Authentication, in-memory cache, login/logout |
| Module route registration | 16606–16760 | `register_group_routes`, `register_bolt_pricer_routes`, `register_cashup_routes`, `register_ledger_routes` |
| CSS Theme System | 17000–18790 | 7 themes: midnight, cyber, emerald, sunset, slate, jarvis, light |
| Jarvis HUD CSS + Builder | 17078–17400, 22422–23075 | Reactor interface, flanking stats, HUD panels |
| `render_page()` function | 18793–22400 | Master page renderer (nav, themes, Zane chat, help, offline) |
| Dashboard route | 23077–23420 | Jarvis HUD dashboard with parallelized data |
| **POS route** | 44703–49575 | **Builds own HTML** (not `render_page()`), own theme via `_pos_theme` cookie |
| POS sale API | 50420–50630 | `/api/pos/sale` — processes sales, GL entries |
| Smart Import | 51817–54350 | CSV/Sage import with AI cleaning |
| Banking / Reconciliation | 59652–61615 | Bank statement import, Zane-assisted categorization |
| Job Cards | 61618–63580 | Manufacturing/workshop management |
| Login/Register/Invite | 63581–64600 | Auth routes, team invites, password reset |
| Scan & Process | 70308–74700 | AI document scanning (Jacqo), supplier invoice processing |
| Settings | 74878–76635 | Business config, team, categories, invoice templates |
| Mobile scanner `/m` | 76634–77450 | "Tap • Snap • Done" mobile workflow |
| SARS module | 77931–78250 | VAT201, EMP201, EMP501 generation |
| WhatsApp | 78291–78525 | Invoice/reminder sending via WhatsApp |
| Collections | 78527–78910 | Automated debt recovery |
| CashFlow forecasting | 78912–79090 | AI-powered cash flow predictions |
| Customer Portal | 79096–79690 | Self-service invoice viewing + PayFast payment |
| Bank Import | 79690–79930 | CSV bank statement upload |
| Audit Trail | 80116–80475 | Complete change history |
| Intelligence Dashboard | 80187–80475 | AI-calculated business health scores |
| `RecurringInvoices` class | 80477–80835 | Auto-generated invoices on schedule |
| `NightlyScheduler` class | 80836–80990 | 2am SAST background AI calculations |

---

## 5. DATABASE TABLES (Supabase)

### Core Business
`businesses`, `users`, `team_members`

### Customers & Suppliers
`customers`, `suppliers`

### Sales & Invoicing
`invoices`, `quotes`, `credit_notes`, `delivery_notes`, `pos_sales`, `sales`, `recurring_invoices`

### Purchasing
`purchase_orders`, `goods_received`, `supplier_invoices`, `supplier_payments`

### Stock / Inventory
`stock` (legacy: uuid ids, qty/cost/price), `stock_items` (newer: text ids, quantity/cost_price/selling_price), `stock_movements`, `stock_categories`

### Financial / Accounting
`expenses`, `payments`, `receipts`, `journals`, `journal_entries`, `gl_entries`, `gl_transactions`, `chart_of_accounts`, `accounts`, `year_ends`, `budgets`

### Banking
`bank_transactions`, `bank_patterns`, `staged_transactions`

### Payroll
`employees`, `payslips`, `timesheets`, `timesheet_entries`, `timesheet_batches`

### Scanning & Documents
`scan_inbox`, `scan_queue`, `scanned_documents`, `scanner_memory`

### Property & Subscriptions
`rentals`, `subscriptions`

### Jobs
`jobs`, `job_materials`

### AI & Intelligence
`zane_memories`, `zane_memory`, `notes`, `reminders`, `todos`, `daily_briefings`, `pulse_views`

### Other
`bar_tabs`, `travel_log`, `assets`, `audit_log`

**Total: ~60 tables**

---

## 6. ZANE — AI ADVISOR ENGINE

### Architecture
- Model: `claude-sonnet-4-6` (via Anthropic API, direct REST calls)
- Tool loop: max 8 turns, 90-second timeout per API call
- System prompt built dynamically by `build_zane_core_prompt()` (~line 7768)
- RAG knowledge injected based on keyword matching against user message
- Chat history: last 20 messages maintained in session
- Memory: persistent `zane_memories` table, top 30 loaded per conversation

### 37 Tools
**Data retrieval:** `search_customers`, `search_suppliers`, `get_debtors`, `get_creditors`, `get_invoices`, `get_quotes`, `get_sales_summary`, `get_expenses`, `get_financial_overview`, `get_employees`, `get_jobs`, `get_purchase_orders`, `get_goods_received`, `get_delivery_notes`, `get_credit_notes`, `get_payments`, `get_journal_entries`, `get_scan_queue`, `get_recurring_invoices`, `get_rentals`, `get_timesheets`, `get_payslips`, `get_receipts`, `get_subscriptions`, `get_business_health_check`

**Knowledge:** `get_accounting_help`

**Actions:** `create_reminder`, `create_note`, `create_todo`, `manage_tasks`

**Memory:** `save_memory`, `recall_memories`, `list_memories`, `forget_memory`

**Business Groups:** `get_group_overview`, `get_group_insights`, `get_group_analysis`

### Response Format
Zane returns JSON with: `action`, `response`, `data`, `suggestions`, `insight`

### Valid Actions
`QUERY`, `CREATE_INVOICE`, `CREATE_QUOTE`, `CREATE_CUSTOMER`, `CREATE_SUPPLIER`, `NAVIGATE`, `SEND_STATEMENT`, `SEND_INVOICE`, `RECORD_PAYMENT`, `ADD_EXPENSE`, `GENERATE_CODES`, `ADD_STOCK_ITEM`, `BOOK_STOCK_IN`, `CREATE_PO`, `RECORD_SUPPLIER_INVOICE`, `CREATE_JOB`, `RUN_PAYROLL`, `POS_SALE`, `CONVERT_QUOTE`, `DELETE_CUSTOMER`, `DELETE_SUPPLIER`, `DELETE_STOCK`

### Key Rules in Zane's Prompt
1. NO EMOJIS — ever (professional software)
2. NEVER ask unnecessary questions — use tools first
3. ALWAYS use tools before responding with data
4. Stock/price questions → redirect to /stock page (NAVIGATE action)
5. How-to questions → redirect to ? help button on each page
6. Bilingual: responds in user's language (English/Afrikaans)
7. Give COMPLETE answers with actual numbers
8. Default to action, not clarification

---

## 7. CHART OF ACCOUNTS (Standard SA SME)

### Assets (1000-1999)
1000 Bank - Current Account | 1010 Bank - Savings | **1050 Cash On Hand** (POS cash sales) | 1100 Petty Cash | 1200 Accounts Receivable | 1300 Stock/Inventory | 1400 Prepaid Expenses | 1500 Equipment | 1510 Vehicles | 1520 Furniture | 1550 Accumulated Depreciation

### Liabilities (2000-2999)
2000 Accounts Payable | 2100 VAT Output | 2110 VAT Input | 2200 PAYE Payable | 2210 UIF Payable | 2220 SDL Payable | 2300 Loan - Bank | 2400 Tenant Deposits | 2500 Credit Cards

### Equity (3000-3999)
3000 Owner's Capital | 3100 Retained Earnings | 3200 Drawings

### Income (4000-4999)
4000 Sales Revenue | 4100 Service Income | 4200 Rental Income | 4300 Recovery Income | 4400 Interest Received | 4500 Discount Received

### Cost of Sales (5000-5999)
5000 Cost of Goods Sold | 5100 Direct Labour | 5200 Freight/Delivery

### Expenses (6000-6999)
6000 Salaries | 6010 UIF | 6020 SDL | 6100 Rent | 6200 Electricity | 6210 Water | 6220 Rates | 6300 Telephone | 6400 Insurance | 6500 Motor Vehicle | 6510 Fuel | 6600 Repairs | 6700 Office Supplies | 6800 Advertising | 6900 Professional Fees | 6910 Bank Charges | 6920 Depreciation | 6950 Bad Debts

**CRITICAL:** POS cash sales post to account **1050** (Cash On Hand), NOT 1100 (Petty Cash).

---

## 8. THEME SYSTEM

7 themes via `clickai_theme` cookie:
- **midnight** (default) — purple/indigo dark
- **cyber** — cyan/electric dark
- **emerald** — green dark
- **sunset** — amber/orange dark
- **slate** — blue dark
- **jarvis** — Iron Man HUD holographic (full reactor interface)
- **light** — light mode

**Jarvis/Reactor HUD:** All dark themes get the reactor HUD header with flanking stats and Zane extension chat. The HUD is built by `_jarvis_global_hud()` (~line 23009) using `JARVIS_HUD_CSS` + `THEME_REACTOR_SKINS`.

**POS Exception:** POS page builds its own HTML (not `render_page()`) and handles themes independently via `_pos_theme` cookie.

---

## 9. MODULE INTEGRATION PATTERN

All external modules follow this pattern:

```python
# In clickai.py — import with try/except
try:
    from clickai_cashup import register_cashup_routes
    CASHUP_LOADED = True
except ImportError:
    CASHUP_LOADED = False

# Later — register routes (after app, db, Auth are defined)
if CASHUP_LOADED:
    register_cashup_routes(app, db, login_required, Auth, generate_id, now, today)
```

Modules receive core dependencies as parameters: `app`, `db`, `login_required`, `Auth`, `generate_id`, `now`, `today`, and optionally `render_page`.

**RULE:** Never modify existing `clickai.py` code in bulk. Add new features as separate files/modules. Always use try/except imports so failures don't break the app.

---

## 10. KEY FUNCTIONS & PATTERNS

### Document Numbering
```python
next_document_number(prefix, existing_docs, field="invoice_number")
```
**NEVER use `len(existing) + 1`** — always use `next_document_number()`.

### Stock Code Generation
```python
smart_stock_code(description, existing_codes=None)  # Line 1770
smart_stock_category()  # 16 categories
```

### Database Operations
```python
db.get(table, filters, limit=10000)      # Get records
db.save(table, record)                    # Upsert (PGRST204 self-healing)
db.delete(table, record_id)              # Delete
db.get_one(table, record_id)             # Single record
db.get_all_stock(business_id)            # Merged stock + stock_items
db.get_business_users(business_id)       # Team members + owner
```

### POS Sale Naming Convention
```python
# Countersale naming: "Countersale Cash - Piet" / "Countersale Card - Isaac"
default_name = {"cash": "Countersale Cash", "card": "Countersale Card", "account": "Countersale Account"}.get(pm, "Countersale")
```

### Allocation Logging
```python
if log_allocation:
    log_allocation(db, business_id, entry_type, record, gl_entries, ...)
```

---

## 11. KNOWN BUGS & ISSUES

1. **`{_safe_uname}` literal text bug:** Cashier name renders as literal `{_safe_uname}` in POS sale allocation entries (allocation log shows the template string instead of the resolved name).

2. **Git/GitHub sync:** `DEPLOY.bat` pushes sometimes fail silently. Verify push success manually.

---

## 12. DEVELOPMENT RULES

1. **Never bulk-modify clickai.py** — add features as separate module files
2. **Always try/except imports** — one broken module must not crash the app
3. **Test after each change** — Deon tests on live Fulltech data
4. **Use `next_document_number()`** — never `len() + 1` for doc numbering
5. **POS cash → account 1050** (Cash On Hand), not 1100
6. **POS builds its own HTML** — don't use `render_page()` for POS
7. **Zane prompt at ~line 7768** — `build_zane_core_prompt()`
8. **Tool loop at ~line 8275** — `call_zane_with_tools()`
9. **Session cookies overflow at 4KB** — keep session data lean, use `Auth._mem` cache
10. **All dark themes get reactor HUD** — Jarvis CSS applies globally

---

## 13. SA-SPECIFIC FEATURES

- **VAT:** 15% standard rate, R1m registration threshold
- **Tax Year:** March – February (SA financial year)
- **SARS eFiling:** VAT201, EMP201, EMP501 generation from actual data
- **Payroll:** PAYE progressive (18-45%), UIF (1%+1%, max R177.12), SDL (1%)
- **Multi-Currency:** 8 currencies supported, ZAR base for GL
- **Banking:** FNB, ABSA, Standard Bank, Nedbank, Capitec CSV import
- **WhatsApp:** Invoice and reminder sending
- **PayFast:** Online payment portal for customers
- **Bilingual:** English/Afrikaans throughout (Zane responds in user's language)

---

## 14. AI WORKERS

| Worker | Role | Implementation |
|--------|------|---------------|
| **Zane** | Senior business advisor, head bookkeeper. 37 tools, memory, bilingual. | `build_zane_core_prompt()`, `call_zane_with_tools()`, `ZaneToolHandler` |
| **Jacqo** | OCR/scanning specialist. Reads supplier invoices, receipts, bank statements. | `clickai_order_scanner`, scan routes (~line 70308+) |
| **Diane** | (Listed on meet-the-team page) | Role TBD |
| **Jayden** | Calculations in order pipeline. | `clickai_order_scanner` pipeline |

---

## 15. FULLTECH-SPECIFIC

- **BoltPricer v4:** Weight-based pricing using R/kg rates by category (SET HT, MF SET HT, CAP SCREW HT, etc.)
- **Bolt weight tables:** Embedded in `fulltech_addon` class (M3–M30, hex bolts, nuts, washers)
- **Steel calculator:** Tube/sheet weight calculations with SA grade factors (304, 316, 3CR12, etc.)
- **Coil calculator, tube prices, sheet pieces:** `/tools/*` routes
- **Smart Quote:** AI-powered quote generation for steel/fastener orders
- **~7,000+ stock items:** Predominantly fasteners, used as live test data

---

## 16. PROVIDING THIS BLUEPRINT TO CLAUDE

When starting a new Claude session for ClickAI development:
1. Upload this `CLICKAI_BLUEPRINT.md` file
2. Upload the specific module file(s) you're working on
3. Paste the relevant code section from `clickai.py` if needed
4. Describe what you want: expected vs actual behavior, error messages
5. Let Claude read the blueprint first, then work on the specific task

This blueprint gives Claude the full architectural context without needing to process 80,990 lines every time.

---

*Blueprint generated by analyzing the full ClickAI codebase (clickai.py + 16 module files). Last updated: 14 March 2026.*
