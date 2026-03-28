# CLICKAI BLUEPRINT v2.1

## Master Architecture \& Development Reference

**Generated: 28 March 2026 — updated from v2.0 after GL code fix \& modularization**

\---

## 1\. WHAT IS CLICKAI

ClickAI is an AI-powered business management platform for South African SMEs. It is NOT an accounting app with AI bolted on — it's an AI that runs your business. Built as a Flask monolith deployed on Fly.io (Johannesburg region) with Supabase (PostgreSQL) as the database.

**Owner/Sole Developer:** Deon Fullard
**Live Test Business:** Fulltech Stainless Tube CC (hardware/steel supplier, \~7,000+ stock items)
**Staff:** Daphne (admin/bookkeeping), Isaac \& Piet (POS/cashier staff)
**AI Workers:** Zane (senior advisor/bookkeeper), Jacqo (OCR/scanning), Diane, Jayden

**Competitive Target:** Sage, Xero, QuickBooks — ClickAI's edge is AI intelligence + real SA business context.

\---

## 2\. TECH STACK

|Component|Technology|
|-|-|
|Backend|Python Flask (`clickai.py` \~54,000 lines + 9 route modules)|
|Database|Supabase (PostgreSQL via REST API)|
|AI Engine|Anthropic Claude API (claude-sonnet-4-6 for Zane + OCR scanning, claude-haiku-4-5 for briefings + category suggestions)|
|Hosting|Fly.io (Johannesburg region, port 8080)|
|Frontend|Server-rendered HTML with inline CSS/JS (no React/Vue)|
|Auth|Session-based with in-memory cache (`Auth` class, 5min TTL)|
|Email|SMTP (Gmail app passwords, per-business SMTP config)|
|Payments|PayFast integration (SA payment gateway)|
|Dev Environment|Windows, `DEPLOY.bat` → git push → Fly.io auto-deploy|
|Deploy Path|`C:\\\\\\\\\\\\\\\\Users\\\\\\\\\\\\\\\\deonf\\\\\\\\\\\\\\\\OneDrive\\\\\\\\\\\\\\\\Desktop\\\\\\\\\\\\\\\\click-main\\\\\\\\\\\\\\\\click-main`|
|Git Config|fullarddeon@gmail.com / "Deon Fullard"|

\---

## 3\. FILE ARCHITECTURE

### Main Application

```
clickai.py                    — \\\\\\\\\\\\\\\~54,000 lines, \\\\\\\\\\\\\\\~188 routes, core logic + GL resolver
```

### Route Modules (extracted from clickai.py, all try/except imported)

```
clickai\\\\\\\\\\\\\\\_pos.py                — POS system, builds own HTML (not render\\\\\\\\\\\\\\\_page())
clickai\\\\\\\\\\\\\\\_invoicing.py          — Invoices, quotes, credit notes, delivery notes
clickai\\\\\\\\\\\\\\\_purchases.py          — Supplier invoices, purchase orders, GRVs, supplier detail page
clickai\\\\\\\\\\\\\\\_reports.py            — GL report, Trial Balance, P\\\\\\\\\\\\\\\&L, Balance Sheet, VAT, aging
clickai\\\\\\\\\\\\\\\_banking.py            — Bank statement import, reconciliation (if exists)
clickai\\\\\\\\\\\\\\\_payroll.py            — Employee management, payslips, EMP201
clickai\\\\\\\\\\\\\\\_timesheets.py         — Timesheet capture and management
clickai\\\\\\\\\\\\\\\_settings.py           — Business settings, team, GL migrate endpoint
clickai\\\\\\\\\\\\\\\_allocation\\\\\\\\\\\\\\\_log.py     — "Place of Safety" transaction ledger (/ledger)
clickai\\\\\\\\\\\\\\\_cashup.py             — Blind cashup, X-Reading, Z-Reading, denomination counting
```

### External Feature Modules

```
clickai\\\\\\\\\\\\\\\_business\\\\\\\\\\\\\\\_groups.py    — Cross-business insights and group management
clickai\\\\\\\\\\\\\\\_bolt\\\\\\\\\\\\\\\_pricer.py        — BoltPricer v4: weight-based fastener pricing (R/kg rates)
clickai\\\\\\\\\\\\\\\_bolt\\\\\\\\\\\\\\\_repricing.py     — Bulk bolt reprice preview + apply
clickai\\\\\\\\\\\\\\\_fraud\\\\\\\\\\\\\\\_guard.py        — Role-based invoice cancel/credit/delete restrictions + audit
clickai\\\\\\\\\\\\\\\_order\\\\\\\\\\\\\\\_scanner         — Order-to-Invoice pipeline (Jacqo OCR → Zane match → Jayden calc)
clickai\\\\\\\\\\\\\\\_whatsapp.py           — WhatsApp invoice/reminder sending
clickai\\\\\\\\\\\\\\\_safety\\\\\\\\\\\\\\\_file.py        — Safety file management
```

### RAG Knowledge Modules (keyword-matched, injected into Zane's prompt)

```
clickai\\\\\\\\\\\\\\\_knowledge\\\\\\\\\\\\\\\_base.py        — 32 chunks: General business/accounting guides
clickai\\\\\\\\\\\\\\\_pulse\\\\\\\\\\\\\\\_knowledge.py       — 37 chunks: Business strategy/analysis patterns
clickai\\\\\\\\\\\\\\\_banking\\\\\\\\\\\\\\\_knowledge.py     — 68 chunks: SA banking, reconciliation, statements
clickai\\\\\\\\\\\\\\\_sars\\\\\\\\\\\\\\\_knowledge.py        — 29 chunks: SARS eFiling, tax compliance
clickai\\\\\\\\\\\\\\\_industry\\\\\\\\\\\\\\\_knowledge.py    — 27 chunks: Industry benchmarks by business type
clickai\\\\\\\\\\\\\\\_bookkeeping\\\\\\\\\\\\\\\_knowledge.py — 24 chunks: Double-entry rules, journal patterns
clickai\\\\\\\\\\\\\\\_transport\\\\\\\\\\\\\\\_knowledge.py   — 21 chunks: Logistics, fleet, transport regulations
clickai\\\\\\\\\\\\\\\_insurance\\\\\\\\\\\\\\\_knowledge.py   — 7 chunks: SA business insurance
clickai\\\\\\\\\\\\\\\_tax\\\\\\\\\\\\\\\_strategy\\\\\\\\\\\\\\\_knowledge.py— 8 chunks: Tax planning, deductions, CGT
clickai\\\\\\\\\\\\\\\_legal\\\\\\\\\\\\\\\_knowledge.py       — Contracts, labour law, BEE, CIPC
clickai\\\\\\\\\\\\\\\_hr\\\\\\\\\\\\\\\_knowledge.py          — BCEA, discipline, leave, hiring
clickai\\\\\\\\\\\\\\\_financial\\\\\\\\\\\\\\\_advisor\\\\\\\\\\\\\\\_knowledge.py — Personal finance, budgeting, debt
```

**Total RAG chunks: \~280+ across 12 knowledge modules**

\---

## 4\. GL CODE SYSTEM (CRITICAL — Updated 28 March 2026)

### How GL Codes Work

ClickAI has a **dual GL system** that supports both new businesses (using ClickAI defaults) and imported businesses (using their own Sage/Xero chart of accounts).

#### For new businesses (no COA imported):

* 30 hardcoded `DEFAULT\\\\\\\\\\\\\\\_ACCOUNTS` (1000–7050) are auto-created
* `CLICKAI\\\\\\\\\\\\\\\_DEFAULTS` maps \~30 roles to these codes: `bank→1000`, `sales→4000`, etc.
* `BOOKING\\\\\\\\\\\\\\\_CATEGORIES` (\~100 ClickAI codes) used for AI expense categorization
* `gl(biz\\\\\\\\\\\\\\\_id, "bank")` returns `"1000"`

#### For imported businesses (Sage TB uploaded):

* TB CSV imported via Settings → Import → stores in `chart\\\\\\\\\\\\\\\_of\\\\\\\\\\\\\\\_accounts` table
* `build\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_map()` scans COA records with **keyword + category matching**
* Maps \~23 system-critical roles to the business's own codes
* `gl(biz\\\\\\\\\\\\\\\_id, "bank")` returns `"8400/000"` (the actual Sage bank code)
* AI (Haiku) receives the real COA account list, not hardcoded BOOKING\_CATEGORIES
* `get\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_code()` checks COA first, falls back to BOOKING\_CATEGORIES

#### Category-aware keyword matching (v2.1 fix):

```python
COA\\\\\\\\\\\\\\\_KEYWORD\\\\\\\\\\\\\\\_MAP = \\\\\\\\\\\\\\\[
    # (keywords, role, required\\\\\\\\\\\\\\\_categories\\\\\\\\\\\\\\\_or\\\\\\\\\\\\\\\_None)
    (\\\\\\\\\\\\\\\["standard bank", "fnb ", "absa "], "bank", \\\\\\\\\\\\\\\["current assets", "bank account"]),
    (\\\\\\\\\\\\\\\["trade payable"], "creditors", \\\\\\\\\\\\\\\["current liabilities"]),
    (\\\\\\\\\\\\\\\["salary", "wages"], "salaries", None),  # None = match any category
    ...
]
```

The `required\\\\\\\\\\\\\\\_categories` field prevents wrong matches like "bank" matching "Bank Charges" (an expense) instead of the actual bank account (a current asset).

#### Key functions (in clickai.py):

|Function|Line|Purpose|
|-|-|-|
|`CLICKAI\\\\\\\\\\\\\\\_DEFAULTS`|\~29584|Role→default code mapping|
|`COA\\\\\\\\\\\\\\\_KEYWORD\\\\\\\\\\\\\\\_MAP`|\~29601|Keywords + category constraints for role matching|
|`build\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_map()`|\~29648|Builds role→code map from business's COA|
|`gl()`|\~29699|Returns GL code for a role (COA first, then defaults)|
|`build\\\\\\\\\\\\\\\_category\\\\\\\\\\\\\\\_list\\\\\\\\\\\\\\\_for\\\\\\\\\\\\\\\_ai()`|\~15023|Sends real COA to Haiku (or BOOKING\_CATEGORIES fallback)|
|`get\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_code()`|\~15071|Looks up GL code by category name (COA first, then BOOKING\_CATEGORIES)|
|`BOOKING\\\\\\\\\\\\\\\_CATEGORIES`|\~14823|\~100 hardcoded ClickAI expense categories|

#### Important: `get\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_code()` and `build\\\\\\\\\\\\\\\_category\\\\\\\\\\\\\\\_list\\\\\\\\\\\\\\\_for\\\\\\\\\\\\\\\_ai()` accept `business\\\\\\\\\\\\\\\_id` parameter

All callers must pass `business\\\\\\\\\\\\\\\_id=biz\\\\\\\\\\\\\\\_id` so the functions can check the real COA. Without it, they fall back to hardcoded BOOKING\_CATEGORIES.

\---

## 5\. KEY CODE LOCATIONS (line numbers in clickai.py — approximate, may shift)

|What|Line(s)|Notes|
|-|-|-|
|Imports + module loading|1–200|All try/except, flags like `CASHUP\\\\\\\\\\\\\\\_LOADED`|
|`fulltech\\\\\\\\\\\\\\\_addon` class|\~166–848|Embedded steel calculator + bolt weight tables|
|Flask app setup + middleware|\~849–920|`\\\\\\\\\\\\\\\_start\\\\\\\\\\\\\\\_timer`, `\\\\\\\\\\\\\\\_enforce\\\\\\\\\\\\\\\_role\\\\\\\\\\\\\\\_access`|
|Environment variables|\~923–940|`ANTHROPIC\\\\\\\\\\\\\\\_API\\\\\\\\\\\\\\\_KEY`, `SUPABASE\\\\\\\\\\\\\\\_URL`, `SUPABASE\\\\\\\\\\\\\\\_KEY`|
|Helper functions|\~1023–2040|`safe()`, `generate\\\\\\\\\\\\\\\_id()`, `money()`, `safe\\\\\\\\\\\\\\\_string()`|
|`DB` class|\~2347–3095|Supabase REST wrapper|
|`RecordFactory` class|\~3096–3700|Schema-correct record builders|
|`ZANE\\\\\\\\\\\\\\\_TOOLS` definition|\~4004–4430|37 tool definitions|
|`ZaneToolHandler` class|\~5803–7760|Executes all 37 Zane tools|
|`build\\\\\\\\\\\\\\\_zane\\\\\\\\\\\\\\\_core\\\\\\\\\\\\\\\_prompt()`|\~7768–8270|THE prompt builder|
|`call\\\\\\\\\\\\\\\_zane\\\\\\\\\\\\\\\_with\\\\\\\\\\\\\\\_tools()`|\~8275–8345|Tool loop: max 8 turns|
|`IndustryKnowledge` class|\~14218–15200|Industry benchmarks + BOOKING\_CATEGORIES + GL code lookup|
|`Auth` class|\~16349–16600|Authentication, login/logout|
|CSS Theme System|\~17000–18790|7 themes|
|`render\\\\\\\\\\\\\\\_page()` function|\~18793–22400|Master page renderer|
|Dashboard route|\~23077–23420|Jarvis HUD dashboard|
|`CLICKAI\\\\\\\\\\\\\\\_DEFAULTS`|\~29584|Default GL code mapping|
|`COA\\\\\\\\\\\\\\\_KEYWORD\\\\\\\\\\\\\\\_MAP`|\~29601|Category-aware keyword matching|
|`build\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_map()` / `gl()`|\~29648–29720|GL code resolver|
|Smart Import|\~31800–34350|CSV/Sage import with AI cleaning|
|Scan \& Process|\~48900–49350|AI document scanning, Haiku categorization|
|Module route registration|\~53900–54100|All register\_\*\_routes() calls|

**Note:** Line numbers shift when code is modified. Use function/class names to search.

\---

## 6\. DATABASE TABLES (Supabase)

### Core Business

`businesses`, `users`, `team\\\\\\\\\\\\\\\_members`

### Customers \& Suppliers

`customers`, `suppliers`

### Sales \& Invoicing

`invoices`, `quotes`, `credit\\\\\\\\\\\\\\\_notes`, `delivery\\\\\\\\\\\\\\\_notes`, `pos\\\\\\\\\\\\\\\_sales`, `sales`, `recurring\\\\\\\\\\\\\\\_invoices`

### Purchasing

`purchase\\\\\\\\\\\\\\\_orders`, `goods\\\\\\\\\\\\\\\_received`, `supplier\\\\\\\\\\\\\\\_invoices`, `supplier\\\\\\\\\\\\\\\_payments`

### Stock / Inventory

`stock` (legacy), `stock\\\\\\\\\\\\\\\_items` (newer), `stock\\\\\\\\\\\\\\\_movements`, `stock\\\\\\\\\\\\\\\_categories`

### Financial / Accounting

`expenses`, `payments`, `receipts`, `journals`, `journal\\\\\\\\\\\\\\\_entries`, `chart\\\\\\\\\\\\\\\_of\\\\\\\\\\\\\\\_accounts`, `accounts`, `year\\\\\\\\\\\\\\\_ends`, `budgets`

### Banking

`bank\\\\\\\\\\\\\\\_transactions`, `bank\\\\\\\\\\\\\\\_patterns`, `staged\\\\\\\\\\\\\\\_transactions`

### Payroll

`employees`, `payslips`, `timesheets`, `timesheet\\\\\\\\\\\\\\\_entries`, `timesheet\\\\\\\\\\\\\\\_batches`

### Scanning \& Documents

`scan\\\\\\\\\\\\\\\_inbox`, `scan\\\\\\\\\\\\\\\_queue`, `scanned\\\\\\\\\\\\\\\_documents`, `scanner\\\\\\\\\\\\\\\_memory`

### Other

`jobs`, `job\\\\\\\\\\\\\\\_materials`, `rentals`, `subscriptions`, `bar\\\\\\\\\\\\\\\_tabs`, `travel\\\\\\\\\\\\\\\_log`, `assets`, `audit\\\\\\\\\\\\\\\_log`, `zane\\\\\\\\\\\\\\\_memories`, `daily\\\\\\\\\\\\\\\_briefings`, `allocation\\\\\\\\\\\\\\\_log`

**Total: \~60 tables**

\---

## 7\. ZANE — AI ADVISOR ENGINE

### Architecture

* Model: `claude-sonnet-4-6` (via Anthropic API, direct REST calls)
* Scan/briefing model: `claude-haiku-4-5-20251001` (fast, cheap)
* Tool loop: max 8 turns, 90-second timeout per API call
* System prompt built dynamically by `build\\\\\\\\\\\\\\\_zane\\\\\\\\\\\\\\\_core\\\\\\\\\\\\\\\_prompt()`
* RAG knowledge injected based on keyword matching against user message
* Chat history: last 20 messages maintained in session
* Memory: persistent `zane\\\\\\\\\\\\\\\_memories` table, top 30 loaded per conversation

### 37 Tools

**Data retrieval:** `search\\\\\\\\\\\\\\\_customers`, `search\\\\\\\\\\\\\\\_suppliers`, `get\\\\\\\\\\\\\\\_debtors`, `get\\\\\\\\\\\\\\\_creditors`, `get\\\\\\\\\\\\\\\_invoices`, `get\\\\\\\\\\\\\\\_quotes`, `get\\\\\\\\\\\\\\\_sales\\\\\\\\\\\\\\\_summary`, `get\\\\\\\\\\\\\\\_expenses`, `get\\\\\\\\\\\\\\\_financial\\\\\\\\\\\\\\\_overview`, `get\\\\\\\\\\\\\\\_employees`, `get\\\\\\\\\\\\\\\_jobs`, `get\\\\\\\\\\\\\\\_purchase\\\\\\\\\\\\\\\_orders`, `get\\\\\\\\\\\\\\\_goods\\\\\\\\\\\\\\\_received`, `get\\\\\\\\\\\\\\\_delivery\\\\\\\\\\\\\\\_notes`, `get\\\\\\\\\\\\\\\_credit\\\\\\\\\\\\\\\_notes`, `get\\\\\\\\\\\\\\\_payments`, `get\\\\\\\\\\\\\\\_journal\\\\\\\\\\\\\\\_entries`, `get\\\\\\\\\\\\\\\_scan\\\\\\\\\\\\\\\_queue`, `get\\\\\\\\\\\\\\\_recurring\\\\\\\\\\\\\\\_invoices`, `get\\\\\\\\\\\\\\\_rentals`, `get\\\\\\\\\\\\\\\_timesheets`, `get\\\\\\\\\\\\\\\_payslips`, `get\\\\\\\\\\\\\\\_receipts`, `get\\\\\\\\\\\\\\\_subscriptions`, `get\\\\\\\\\\\\\\\_business\\\\\\\\\\\\\\\_health\\\\\\\\\\\\\\\_check`

**Knowledge:** `get\\\\\\\\\\\\\\\_accounting\\\\\\\\\\\\\\\_help`

**Actions:** `create\\\\\\\\\\\\\\\_reminder`, `create\\\\\\\\\\\\\\\_note`, `create\\\\\\\\\\\\\\\_todo`, `manage\\\\\\\\\\\\\\\_tasks`

**Memory:** `save\\\\\\\\\\\\\\\_memory`, `recall\\\\\\\\\\\\\\\_memories`, `list\\\\\\\\\\\\\\\_memories`, `forget\\\\\\\\\\\\\\\_memory`

**Business Groups:** `get\\\\\\\\\\\\\\\_group\\\\\\\\\\\\\\\_overview`, `get\\\\\\\\\\\\\\\_group\\\\\\\\\\\\\\\_insights`, `get\\\\\\\\\\\\\\\_group\\\\\\\\\\\\\\\_analysis`

### Key Rules in Zane's Prompt

1. NO EMOJIS — ever
2. NEVER ask unnecessary questions — use tools first
3. ALWAYS use tools before responding with data
4. Bilingual: responds in user's language (English/Afrikaans)
5. Give COMPLETE answers with actual numbers

\---

## 8\. CHART OF ACCOUNTS

### ClickAI Defaults (for new businesses without Sage import)

**Assets (1000-1700):** 1000 Bank | 1050 Cash On Hand | 1100 Petty Cash | 1200 Debtors | 1300 Stock | 1400 VAT Input | 1500 Equipment | 1600 Vehicles | 1700 Accumulated Depreciation

**Liabilities (2000-2400):** 2000 Creditors | 2100 VAT Output | 2200 PAYE | 2300 UIF | 2400 Loan

**Equity (3000-3200):** 3000 Capital | 3100 Retained Earnings | 3200 Drawings

**Income (4000-4300):** 4000 Sales | 4100 Services | 4200 Interest Received | 4300 Discount Received

**Cost of Sales (5000-5200):** 5000 COGS | 5100 Purchases | 5200 Carriage In

**Expenses (6000-7050):** 6000 Salaries | 6100 Rent | 6200 Electricity | 6300 Telephone | 6400 Insurance | 6500 Fuel | 6600 Repairs | 6700 Bank Charges | 6800 Advertising | 6900 Depreciation | 7000 General | 7050 Cash Over/Short

### Imported COA (Sage/Xero businesses)

When a business imports their Trial Balance from Sage, all accounts are stored with their original codes (e.g. `8400/000`, `3200/000`, `4400/001`). The `build\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_map()` function maps \~23 system-critical roles to these codes using category-aware keyword matching. All other accounts appear in dropdowns and reports by their original Sage code.

**CRITICAL:** POS cash sales post to `gl(biz\\\\\\\\\\\\\\\_id, "cash")` — returns `1050` (default) or `8100/000` (Fulltech's POS Cash Control).

\---

## 9\. MODULE INTEGRATION PATTERN

All external modules follow this pattern:

```python
# In clickai.py — import with try/except
try:
    from clickai\\\\\\\\\\\\\\\_cashup import register\\\\\\\\\\\\\\\_cashup\\\\\\\\\\\\\\\_routes
    CASHUP\\\\\\\\\\\\\\\_LOADED = True
except ImportError:
    CASHUP\\\\\\\\\\\\\\\_LOADED = False

# Later — register routes (after app, db, Auth are defined)
if CASHUP\\\\\\\\\\\\\\\_LOADED:
    register\\\\\\\\\\\\\\\_cashup\\\\\\\\\\\\\\\_routes(app, db, login\\\\\\\\\\\\\\\_required, Auth, generate\\\\\\\\\\\\\\\_id, now, today)
```

Modules receive core dependencies as parameters. Some modules also receive GL functions: `gl`, `build\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_map`, `CLICKAI\\\\\\\\\\\\\\\_DEFAULTS`, `create\\\\\\\\\\\\\\\_journal\\\\\\\\\\\\\\\_entry`.

**RULE:** Never modify existing `clickai.py` code in bulk. Add new features as separate files/modules. Always use try/except imports so failures don't break the app.

\---

## 10\. THEME SYSTEM

7 themes via `clickai\\\\\\\\\\\\\\\_theme` cookie:

* **midnight** (default) — purple/indigo dark
* **cyber** — cyan/electric dark
* **emerald** — green dark
* **sunset** — amber/orange dark
* **slate** — blue dark
* **jarvis** — Iron Man HUD holographic
* **light** — light mode

**POS Exception:** POS page builds its own HTML (not `render\\\\\\\\\\\\\\\_page()`) and handles themes independently via `\\\\\\\\\\\\\\\_pos\\\\\\\\\\\\\\\_theme` cookie.

\---

## 11\. KNOWN BUGS \& ISSUES

1. **`{\\\\\\\\\\\\\\\_safe\\\\\\\\\\\\\\\_uname}` literal text bug:** Cashier name renders as literal `{\\\\\\\\\\\\\\\_safe\\\\\\\\\\\\\\\_uname}` in some POS sale entries.
2. **Duplicate expense entries:** Some bank statement expenses were imported multiple times (visible in GL report — same description, same amount, multiple entries on same date).
3. **Old journals with ClickAI default codes:** Existing transactions (pre-GL-fix) use codes like `1000`, `6000` instead of Sage codes. These remain as-is; the Sage TB opening balances provide the correct starting point.

\---

## 12\. DEVELOPMENT RULES

1. **Never bulk-modify clickai.py** — add features as separate module files
2. **Always try/except imports** — one broken module must not crash the app
3. **Test after each change** — Deon tests on live Fulltech data
4. **Use `next\\\\\\\\\\\\\\\_document\\\\\\\\\\\\\\\_number()`** — never `len() + 1` for doc numbering
5. **POS cash → `gl(biz\\\\\\\\\\\\\\\_id, "cash")`** — not hardcoded `1050`
6. **POS builds its own HTML** — don't use `render\\\\\\\\\\\\\\\_page()` for POS
7. **Always pass `business\\\\\\\\\\\\\\\_id`** to `get\\\\\\\\\\\\\\\_gl\\\\\\\\\\\\\\\_code()` and `build\\\\\\\\\\\\\\\_category\\\\\\\\\\\\\\\_list\\\\\\\\\\\\\\\_for\\\\\\\\\\\\\\\_ai()`
8. **`log\\\\\\\\\\\\\\\_allocation` calls** must be included in all new transaction endpoints
9. **Session cookies overflow at 4KB** — keep session data lean
10. **Project files are read-only snapshots** — re-upload after deployments

\---

## 13\. SA-SPECIFIC FEATURES

* **VAT:** 15% standard rate, R1m registration threshold
* **Tax Year:** March – February (SA financial year)
* **SARS eFiling:** VAT201, EMP201, EMP501 generation from actual data
* **Payroll:** PAYE progressive (18-45%), UIF (1%+1%, max R177.12), SDL (1%)
* **Banking:** FNB, ABSA, Standard Bank, Nedbank, Capitec CSV import
* **WhatsApp:** Invoice and reminder sending
* **PayFast:** Online payment portal for customers
* **Bilingual:** English/Afrikaans throughout

\---

## 14\. AI WORKERS

|Worker|Role|Model|
|-|-|-|
|**Zane**|Senior business advisor, head bookkeeper. 37 tools, memory, bilingual.|claude-sonnet-4-6|
|**Jacqo**|OCR/scanning specialist. Reads supplier invoices, receipts, bank statements.|claude-sonnet-4-6 (needs vision)|
|**Diane**|Listed on meet-the-team page.|Role TBD|
|**Jayden**|Calculations in order pipeline.|claude-haiku-4-5|

**Haiku** is only used for: Daily Briefings (Pulse) and scan **category suggestion** (after OCR is done, Haiku decides "expense or stock purchase?"). All image OCR uses **Sonnet** because it needs vision capability.

\---

## 15\. FULLTECH-SPECIFIC

* **BoltPricer v4:** Weight-based pricing using R/kg rates
* **Steel calculator:** Tube/sheet weight calculations with SA grade factors
* **\~7,000+ stock items:** Predominantly fasteners, used as live test data
* **Sage TB imported:** 68 accounts (57 real + 11 system) balanced at R7,100,251.08
* **GL map verified:** 23 system roles correctly matched (bank→8400/000, creditors→Trade Payables, etc.)

\---

## 16\. PROVIDING THIS BLUEPRINT TO CLAUDE

When starting a new Claude session for ClickAI development:

1. Upload this `CLICKAI\\\\\\\\\\\\\\\_BLUEPRINT.md` file
2. Upload the specific module file(s) you're working on
3. Upload `clickai.py` only if the changes are in the main file
4. Describe what you want: expected vs actual behavior, error messages
5. Let Claude read the blueprint first, then work on the specific task

**Deon's working style:** He does not work inside the code himself. Always deliver complete, ready-to-deploy replacement files for copy-paste onto the server — never partial patches, diffs, or instructional guides.

This blueprint gives Claude the full architectural context without needing to process 54,000+ lines every time.

\---

*Blueprint v2.1 — Updated 28 March 2026 after GL code fix (category-aware matching), codebase modularization (\~54,000 lines down from \~81,000), and Fulltech TB verification.*

