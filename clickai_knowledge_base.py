"""
ClickAI Knowledge Base for Zane RAG System
===========================================
Each chunk is small and focused. The RAG system matches user queries
to keywords and injects ONLY the relevant chunk(s) into Zane's prompt.

Structure:
- Each entry has: keywords (for matching), title, content (the knowledge)
- Max 2-3 chunks injected per query to keep prompt small and focused
- Categories: system_nav, stock, invoicing, pos, scanning, payroll, 
  accounting, ai_team, setup, reports, banking, customers, suppliers,
  rentals, troubleshooting, sars_compliance, tax, payroll_tax
"""

CLICKAI_KNOWLEDGE = {

    # ============================================================
    # AI TEAM - Who does what
    # ============================================================
    
    "ai_team_overview": {
        "keywords": ["zane", "diane", "jayden", "jacqo", "ai team", "wie doen wat", "which ai", "assistants"],
        "title": "ClickAI's AI Team - Who Does What",
        "content": """ClickAI has 4 specialized AI workers, each with a specific role:

**ZANE** (Business Assistant - You):
- Chat interface for users to interact with
- Answers questions about the business, stock, customers, finances
- Can search data, create quotes/invoices, run reports
- Helps with accounting setup and how-to guides
- Manages stock: delete duplicates, assign smart codes, clean up items
- Sends scanned documents to inbox for human verification
- Processes payroll for human review before posting
- Bilingual: English and Afrikaans

**JACQO** (The Reader):
- Reads and extracts data from scanned documents (invoices, receipts, delivery notes)
- Uses OCR (Google Document AI) to read text from images/PDFs
- Extracts: supplier name, invoice number, date, line items, amounts, VAT
- Passes extracted data to Zane for processing

**DIANE** (The Analyst):
- Deep thinking and analysis
- Trial Balance analysis - identifies problems and anomalies
- Financial reports and insights
- Cash flow forecasting
- Business performance analysis
- Ratio analysis and benchmarking
- Does NOT read scans - she analyzes data

**JAYDEN** (The Calculator):
- All mathematical calculations
- NOT AI - uses precise math functions for accuracy
- VAT calculations (15% SA standard)
- Markup/margin calculations
- Payroll deductions (PAYE, UIF, SDL)
- Invoice totals, discounts, credit notes
- Ensures numbers are always 100% accurate (AI can make math errors)

IMPORTANT: Zane coordinates the team. When a user scans a document, 
Jacqo reads it → Jayden calculates totals → Zane presents it for review."""
    },

    # ============================================================
    # SYSTEM NAVIGATION
    # ============================================================
    
    "nav_main_menu": {
        "keywords": ["menu", "navigate", "where is", "find", "hoe kom ek by", "waar is", "how to get to", "header", "nav"],
        "title": "ClickAI Navigation - Main Menu",
        "content": """The main navigation is in the header bar at the top. Menu items:

- **Dashboard** - Overview of your business (sales today, debtors, creditors, quick stats)
- **Stock** - Manage inventory items, prices, categories, stock codes
- **Customers** - Customer database, contact info, transaction history
- **Suppliers** - Supplier database, contact info, purchase history
- **Sales** - Invoices, quotes, credit notes, delivery notes, receipts
- **Purchases** - Purchase orders, goods received vouchers (GRVs), supplier invoices
- **Banking** - Bank accounts, transactions, reconciliation
- **Accounting** - General Ledger, Trial Balance, journal entries, chart of accounts
- **Payroll** - Employees, payslips, PAYE, UIF, leave management
- **POS** - Point of Sale for retail/pub/restaurant operations
- **Reports** - Financial reports, sales reports, stock reports, aged analysis
- **Scanner** - Scan invoices/receipts, review queue, auto-posting
- **Settings** - Business setup, users, permissions, preferences

On mobile: Swipe left/right anywhere on screen to scroll the header menu.
The business switcher (top right) lets you switch between multiple businesses."""
    },

    "nav_quick_actions": {
        "keywords": ["quick", "shortcut", "fast", "vinnig", "how do i quickly"],
        "title": "Quick Actions in ClickAI",
        "content": """Quick ways to do common tasks:

- **New Invoice**: Sales → + New Invoice (or ask Zane: "invoice for [customer]")
- **New Quote**: Sales → + New Quote (or ask Zane: "quote for [customer]")
- **Check Stock**: Ask Zane "do we have [item]?" or go to Stock page
- **Customer Balance**: Ask Zane "how much does [customer] owe?"
- **Today's Sales**: Dashboard shows today's total, or ask Zane
- **Scan Invoice**: Scanner → Upload or use phone camera
- **POS Sale**: POS → select items → checkout
- **Run Report**: Reports → select report type → date range → generate

Pro tip: Zane can do most things faster than navigating menus. 
Just type what you want in natural language."""
    },

    # ============================================================
    # STOCK MANAGEMENT
    # ============================================================
    
    "stock_basics": {
        "keywords": ["stock", "inventory", "voorraad", "items", "products", "add stock", "new item", "add item"],
        "title": "Stock Management Basics",
        "content": """How stock works in ClickAI:

**Adding Stock Items:**
1. Go to Stock → + New Item
2. Fill in: Item description, stock code, category, cost price, selling price
3. Set: Reorder level, preferred supplier, tax type (VAT/No VAT)
4. Save

**Stock Codes:**
ClickAI generates smart stock codes based on the item description:
- HB = Hex Bolt, CSK = Countersunk, FL = Flat, NUT = Nut
- Size is encoded: M8, M10, M12 etc.
- Material suffix: /SS = Stainless Steel, /HDG = Hot Dip Galvanized, /BZ = Bronze
- Example: HB-M10-30/SS = Hex Bolt M10x30mm Stainless Steel

**Bulk Operations (via Zane):**
- "Clean duplicate stock" - finds and merges duplicate items
- "Regenerate stock codes" - assigns smart codes to all items
- "Assign categories" - auto-categorizes items based on description
- "Update all markups to 40%" - bulk price updates

**Stock Valuation:**
- Uses weighted average cost method
- Stock value shows on dashboard
- GRVs (goods received) update cost prices automatically"""
    },

    "stock_codes_system": {
        "keywords": ["stock code", "item code", "kode", "smart code", "regenerate codes", "coding system"],
        "title": "Smart Stock Code System",
        "content": """ClickAI's smart stock code system encodes item information into the code:

**Prefix = Item Type:**
HB = Hex Bolt | CSK = Countersunk Screw | SC = Cap Screw | FL = Flat Washer
SPW = Spring Washer | NUT = Nut | STD = Studding | TB = Tek/Bolt
CPN = Coupling Nut | ANC = Anchor Bolt | RB = Rawl Bolt | SS = Set Screw
EYB = Eye Bolt | UBT = U-Bolt | JBT = J-Bolt | HKB = Hook Bolt

**Middle = Size:**
M6, M8, M10, M12, M16, M20 (metric diameter)
Length after dash: 30, 50, 75, 100 (mm)

**Suffix = Material:**
/SS = Stainless Steel | /HDG = Hot Dip Galvanized | /BZ = Bronze
/BR = Brass | /ZP = Zinc Plated | /BLK = Black (plain)

**Examples:**
- HB-M10-30/SS → Hex Bolt M10 x 30mm Stainless Steel
- NUT-M12/HDG → Nut M12 Hot Dip Galvanized  
- FL-M8/SS → Flat Washer M8 Stainless Steel

Zane can regenerate all codes: "regenerate stock codes" 
Zane learns supplier codes and maps them to ClickAI codes on scanned invoices."""
    },

    "stock_categories": {
        "keywords": ["category", "categories", "kategorie", "group", "classify", "sort stock"],
        "title": "Stock Categories",
        "content": """Stock categories help organize inventory and filter in POS/reports:

**Setting up categories:**
1. Stock → Categories (or Settings → Stock Categories)
2. Add category name (e.g., "Bolts & Nuts", "Plumbing", "Electrical")
3. Assign items to categories

**Auto-categorization:**
Ask Zane: "assign categories to all stock" - he'll analyze descriptions 
and auto-assign based on keywords.

**Category uses:**
- POS: Filter items by category for quick finding
- Reports: Sales by category, stock value by category
- Ordering: Reorder reports by category
- Price lists: Generate category-specific price lists

**Industry templates:**
ClickAI has templates for: Hardware, Restaurant/Pub, Retail, B&B/Guesthouse
Each template pre-loads relevant categories and GL accounts."""
    },

    # ============================================================
    # INVOICING & QUOTES
    # ============================================================
    
    "invoicing_basics": {
        "keywords": ["invoice", "faktuur", "bill", "create invoice", "new invoice", "maak faktuur"],
        "title": "Creating Invoices",
        "content": """How to create invoices in ClickAI:

**Manual Method:**
1. Sales → Invoices → + New Invoice
2. Select customer (or create new)
3. Add line items: search stock or type description
4. Quantities and prices auto-populate from stock
5. VAT calculates automatically (Jayden handles the math)
6. Add notes/payment terms if needed
7. Save → Print/Email/WhatsApp to customer

**Via Zane (faster):**
"Invoice ABC Hardware for 10x M10 hex bolts and 5x M12 nuts"
Zane searches stock, finds prices, creates the invoice.

**From Quote:**
Convert any quote to invoice with one click: Quote → Convert to Invoice

**Invoice Numbering:**
Auto-sequential: INV-00001, INV-00002, etc.
Prefix customizable per business in Settings.

**Payment Terms:**
Set default terms in Settings (e.g., 30 days)
Override per customer or per invoice.

**Posting:**
Invoice automatically posts to:
- Debtors (customer account)
- Sales (income GL)
- VAT Output (if applicable)"""
    },

    "quotes_system": {
        "keywords": ["quote", "quotation", "kwotasie", "estimate", "price list", "create quote"],
        "title": "Quotes & Quotations",
        "content": """Creating and managing quotes:

**Create Quote:**
1. Sales → Quotes → + New Quote
2. Same process as invoices
3. Quotes DON'T post to accounting - they're just proposals
4. Valid for X days (configurable)

**Via Zane:**
"Quote for NDE Engineering: 100x M10 hex bolts SS"

**Quote → Invoice:**
Once accepted, click "Convert to Invoice" - copies all details.

**Buyout Items:**
Add non-stock items to quotes/invoices as "buyout items"
- Type description and price manually
- Useful for special orders or once-off items
- Won't affect stock levels

**Email/WhatsApp:**
Send quotes directly from ClickAI via email or WhatsApp link.
Professional PDF format with your business logo and details."""
    },

    # ============================================================
    # POINT OF SALE (POS)
    # ============================================================
    
    "pos_system": {
        "keywords": ["pos", "point of sale", "till", "register", "cash register", "sell", "retail", "kasregister"],
        "title": "Point of Sale (POS) System",
        "content": """ClickAI's POS for retail, pub, restaurant, and hardware stores:

**Opening POS:**
1. Click POS in main menu
2. Select items by category tabs or search
3. Items add to cart on the right
4. Adjust quantities with +/- buttons
5. Apply discounts if needed
6. Checkout → select payment method

**Payment Methods:**
- Cash (calculates change)
- Card
- EFT
- Split payment (part cash, part card)
- Account (charge to customer account)

**Category Filtering:**
POS shows category tabs at top to quickly filter items.
Tap category → see only those items. Much faster than scrolling.

**POS Features:**
- Barcode scanning (if hardware connected)
- Quick search by name or stock code
- Hold sale (park and resume later)
- Refunds / returns
- Daily Z-report (end of day summary)
- Shift management
- Cash-up at end of shift

**For Pubs/Restaurants:**
- Table management
- Tab system (open tab, add items, close tab)
- Kitchen/bar printer integration
- Happy hour pricing

**Stock Impact:**
Every POS sale automatically reduces stock quantities in real-time."""
    },

    # ============================================================
    # SCANNING & OCR
    # ============================================================
    
    "scanning_invoices": {
        "keywords": ["scan", "scanner", "ocr", "upload", "skandeer", "photo", "camera", "receipt", "read invoice"],
        "title": "Scanning Invoices & Documents",
        "content": """ClickAI's AI-powered document scanning system:

**How it works:**
1. Scan/photograph a supplier invoice, receipt, or delivery note
2. Upload via Scanner page or email to your scan inbox
3. Jacqo (AI Reader) extracts all data using Google Document AI
4. Data appears in Review Queue for human verification
5. Approve → auto-posts to accounting with correct GL codes

**Upload Methods:**
- **Scanner page**: Click Scanner → Upload → select file(s)
- **Phone camera**: Take photo → upload directly
- **Email**: Forward invoices to your scan-to-email address
- **Bulk upload**: Select multiple files at once

**What Jacqo Extracts:**
- Supplier name (matches to your supplier database)
- Invoice number & date
- Line items with descriptions, quantities, prices
- VAT amount
- Total amount
- Payment terms

**Review Queue:**
Every scanned document goes to review first - NOTHING posts automatically 
without human approval. This is a safety feature.
- Green = matches perfectly, quick approve
- Yellow = needs checking (price difference, new supplier)
- Red = problem detected (duplicate invoice, amount mismatch)

**Duplicate Detection:**
System checks invoice numbers to prevent double-posting.
Normalized matching: INV001 = INV-001 = INV 001

**Auto-matching:**
Zane learns supplier item codes over time and auto-maps them 
to your stock codes for future invoices."""
    },

    "scan_to_email": {
        "keywords": ["scan inbox", "email scan", "scan-to-email", "forward invoice", "imap", "email setup"],
        "title": "Scan-to-Email Setup",
        "content": """Set up email scanning so suppliers can email invoices directly:

**Setup (Settings → Scanner → Email):**
1. Create a dedicated email: e.g., scans@yourbusiness.co.za
2. Enter IMAP settings:
   - Server: imap.gmail.com (or your provider)
   - Port: 993
   - Email: your-scan-email@gmail.com
   - Password: App Password (NOT your regular password!)
3. Test connection
4. Enable auto-check interval (e.g., every 5 minutes)

**Gmail App Password:**
1. Go to myaccount.google.com
2. Security → 2-Step Verification (enable if not already)
3. App passwords → Generate
4. Copy the 16-character password
5. Use this in ClickAI (not your Gmail password)

**How it works:**
- System checks inbox periodically
- New emails with PDF/image attachments get processed
- Jacqo reads the documents
- They appear in your Review Queue
- Original emails are marked as read

**Tip:** Give this email to all suppliers. Tell them to email invoices 
to this address. Saves you from manually scanning paper invoices."""
    },

    # ============================================================
    # PAYROLL
    # ============================================================
    
    "payroll_system": {
        "keywords": ["payroll", "salary", "salaris", "paye", "uif", "employee", "werknemer", "payslip", "betaalstaat", "loon"],
        "title": "Payroll System",
        "content": """ClickAI's SARS-compliant payroll system:

**Setup Employees:**
1. Payroll → Employees → + New Employee
2. Enter: Name, ID number, tax number, start date
3. Set: Basic salary, payment frequency (weekly/monthly)
4. Configure: Medical aid, provident fund, other deductions
5. Set tax bracket (auto-calculated from salary)

**Running Payroll:**
1. Payroll → Run Payroll
2. Select period (month/week)
3. Review each employee:
   - Basic salary
   - Overtime (if applicable)
   - Commission/bonus
   - Leave taken
4. Jayden calculates ALL deductions automatically:
   - PAYE (per SARS tax tables)
   - UIF (1% employee + 1% employer)
   - SDL (1% employer)
   - Medical aid
   - Provident/pension fund
   - Cash advances (deducted from pay)
5. Review payslips → Approve → Post

**Payslip includes:**
- Gross salary
- All deductions itemized
- Net pay
- Year-to-date totals
- Leave balance

**SARS Compliance:**
- EMP201 monthly submission data
- IRP5 year-end certificates
- Tax tables updated annually
- UIF declarations

**Cash Advances:**
Payroll → Cash Advance → enter amount → deducts from next payslip automatically.

**Important:** Payroll always goes through review before posting. 
Zane prepares it, you verify, then approve."""
    },

    # ============================================================
    # BANKING & RECONCILIATION
    # ============================================================
    
    "bank_reconciliation": {
        "keywords": ["bank", "reconcile", "rekon", "bank statement", "match", "reconciliation", "bank transactions"],
        "title": "Bank Reconciliation",
        "content": """Bank reconciliation in ClickAI matches your bank statement to your books:

**Import Bank Statement:**
1. Banking → Import Statement
2. Upload CSV/OFX file from your bank
3. ClickAI reads and lists all transactions

**Auto-Matching:**
The AI tries to match bank transactions to:
- Invoices paid (by amount and reference)
- Supplier invoices (by amount and reference)
- Recurring payments (rent, subscriptions)
- Previously seen transactions (learns patterns)

**Manual Matching:**
For unmatched items:
1. Click the transaction
2. Select: Match to existing entry, or Create new entry
3. Assign GL account
4. Approve

**Month-End Process:**
Traditional: Hours of work matching transactions manually.
With ClickAI: Most transactions auto-match. You only handle exceptions.
This is the KILLER FEATURE - reduces month-end from hours to minutes.

**Reconciliation Report:**
Shows: Bank balance vs Book balance, Outstanding deposits, 
Outstanding payments, Unmatched items.

**Tip:** The more you use the system, the smarter it gets at matching.
It learns your patterns - same supplier, same amount = auto-match."""
    },

    # ============================================================
    # ACCOUNTING
    # ============================================================
    
    "chart_of_accounts": {
        "keywords": ["chart of accounts", "gl", "general ledger", "grootboek", "rekeningkaart", "account codes", "ledger accounts"],
        "title": "Chart of Accounts & General Ledger",
        "content": """ClickAI's Chart of Accounts follows SA standards:

**Account Structure:**
- 1000-1999: Assets (Bank, Debtors, Stock, Equipment)
- 2000-2999: Liabilities (Creditors, VAT, Loans, Provisions)
- 3000-3999: Equity (Capital, Retained Earnings)
- 4000-4999: Income (Sales, Interest, Other Income)
- 5000-5999: Cost of Sales (Purchases, Direct Costs)
- 6000-6999: Expenses (Rent, Salaries, Electricity, etc.)

**Pre-loaded Templates:**
Based on business type, ClickAI pre-loads relevant GL accounts:
- Hardware store: Stock accounts per category, workshop expenses
- Restaurant/Pub: Food cost, beverage cost, entertainment
- B&B: Room revenue, cleaning, laundry, breakfast costs
- General: Standard SA small business accounts

**Adding Custom Accounts:**
Accounting → Chart of Accounts → + New Account
Enter: Account number, name, type (Asset/Liability/Income/Expense)

**How Posting Works:**
Every transaction in ClickAI (invoice, payment, journal) automatically 
creates double-entry GL entries. You don't need to manually post to the ledger.

Example: Creating an invoice posts:
- DEBIT Debtors (Asset increases)
- CREDIT Sales (Income increases)
- CREDIT VAT Output (Liability increases)"""
    },

    "vat_returns": {
        "keywords": ["vat", "btw", "tax return", "sars", "vat201", "output", "input", "vat return"],
        "title": "VAT Returns & SARS",
        "content": """VAT handling in ClickAI (South Africa - 15%):

**Automatic VAT Tracking:**
Every invoice/expense automatically calculates and tracks VAT:
- Sales invoices → VAT Output (you owe SARS)
- Purchase invoices → VAT Input (SARS owes you)
- Difference = VAT payable or refundable

**VAT Return (VAT201):**
1. Reports → VAT Return
2. Select period (usually 2 months for SA)
3. System calculates:
   - Total sales (incl & excl VAT)
   - Total purchases (incl & excl VAT)
   - VAT Output - VAT Input = Amount due/refundable
4. Review and submit to SARS eFiling

**VAT on Invoices:**
- Standard rated (15%): Most goods and services
- Zero rated (0%): Exports, basic foodstuffs
- Exempt: Financial services, residential rent
- Set per item in stock setup

**Important:**
- ClickAI tracks VAT in real-time, not just at return time
- Dashboard shows current VAT liability
- Jayden does all VAT math (no AI rounding errors)
- Keep all scanned invoices as proof for SARS audits"""
    },

    "journal_entries": {
        "keywords": ["journal", "joernaal", "entry", "inskrywing", "debit", "credit", "adjustment", "correction"],
        "title": "Journal Entries",
        "content": """Manual journal entries for adjustments and corrections:

**When to use:**
- Correcting errors
- Year-end adjustments
- Depreciation entries
- Accruals and provisions
- Opening balances
- Intercompany transfers

**Creating a Journal:**
1. Accounting → Journal Entries → + New
2. Enter date and description
3. Add lines: Account | Debit | Credit
4. MUST balance (total debits = total credits)
5. Jayden verifies the math
6. Post

**Common Journals:**
Depreciation: DEBIT Depreciation Expense / CREDIT Accumulated Depreciation
Bad Debt: DEBIT Bad Debt Expense / CREDIT Debtors
Accrual: DEBIT Expense / CREDIT Accruals
Correction: Reverse original entry, then post correct one

**Tip:** Always add a clear description so you know why the journal 
was posted when you look at it later. Include reference numbers."""
    },

    "trial_balance": {
        "keywords": ["trial balance", "tb", "proefbalans", "balances", "accounts balance"],
        "title": "Trial Balance",
        "content": """The Trial Balance (TB) shows all GL accounts with their balances:

**Viewing TB:**
Accounting → Trial Balance
Select period → Generate

**What to check:**
- Total Debits = Total Credits (must balance!)
- Debtors balance matches aged debtors total
- Creditors balance matches aged creditors total
- Bank balance matches bank statement (after reconciliation)
- VAT accounts are correct
- No unusual balances (negative assets, positive expenses in wrong direction)

**Diane's TB Analysis:**
Ask Diane to analyze your TB - she'll identify:
- Accounts with unusual balances
- Potential errors or mispostings
- Cash flow concerns
- Profitability insights
- Year-over-year comparisons
- Suggestions for improvement

**Month-End Process:**
1. Complete all bank reconciliation
2. Post all supplier invoices from scan queue
3. Run depreciation journals
4. Review TB
5. Ask Diane to analyze
6. Fix any issues
7. TB is now ready for financial statements"""
    },

    # ============================================================
    # REPORTS
    # ============================================================
    
    "reports_overview": {
        "keywords": ["report", "reports", "verslag", "analysis", "print", "export", "financial statements"],
        "title": "Reports Available in ClickAI",
        "content": """Reports available in ClickAI:

**Financial Reports:**
- Trial Balance
- Income Statement (Profit & Loss)
- Balance Sheet
- Cash Flow Statement
- VAT Return (VAT201)
- General Ledger Detail

**Sales Reports:**
- Sales by Customer
- Sales by Item/Category
- Sales by Period (daily/weekly/monthly)
- Outstanding Invoices (aged debtors)
- Quotes converted vs pending

**Purchase Reports:**
- Purchases by Supplier
- Outstanding Bills (aged creditors)
- GRV Register

**Stock Reports:**
- Stock Valuation
- Stock Movement (in/out history)
- Reorder Report (items below minimum)
- Stock Take Variance
- Slow Moving Stock

**Payroll Reports:**
- Payslip Register
- PAYE Summary
- UIF Declaration
- Leave Balance Report
- Cost to Company

**POS Reports:**
- Daily Z-Report
- Sales by Cashier
- Payment Method Summary
- Shift Report

All reports can be exported to PDF or Excel.
Ask Zane: "email me the debtors report" or "show me sales for this month"."""
    },

    # ============================================================
    # CUSTOMER MANAGEMENT
    # ============================================================
    
    "customer_management": {
        "keywords": ["customer", "client", "klient", "debtor", "debiteur", "add customer", "customer account"],
        "title": "Customer Management",
        "content": """Managing customers in ClickAI:

**Adding Customers:**
1. Customers → + New Customer
2. Enter: Business name, contact person, email, phone
3. Set: Payment terms (e.g., 30 days), credit limit
4. Optional: VAT number, physical address, delivery address

**Customer Features:**
- Full transaction history (invoices, payments, credit notes)
- Statement generation and emailing
- Aged analysis (30/60/90/120+ days outstanding)
- Credit limit warnings
- Notes and communication log

**Collections:**
- Aged Debtors report shows who owes what and how long
- Send automated statement reminders
- Flag overdue accounts
- Block further sales to overdue customers

**Ask Zane:**
- "How much does [customer] owe?"
- "Show me [customer]'s last 5 invoices"
- "Send statement to [customer]"
- "Who are my top 10 customers?"
- "Which customers are overdue?"

**Customer Import:**
Upload a CSV file to bulk-import customers when migrating from 
another system (Sage, Xero, QuickBooks)."""
    },

    # ============================================================
    # SUPPLIER MANAGEMENT
    # ============================================================
    
    "supplier_management": {
        "keywords": ["supplier", "vendor", "verskaffer", "creditor", "krediteur", "add supplier"],
        "title": "Supplier Management",
        "content": """Managing suppliers in ClickAI:

**Adding Suppliers:**
1. Suppliers → + New Supplier
2. Enter: Business name, contact person, email, phone
3. Set: Payment terms, bank details (for EFT payments)
4. Optional: VAT number, BEE rating

**Auto-Creation from Scans:**
When Jacqo reads a new supplier invoice, if the supplier doesn't exist,
ClickAI auto-creates the supplier record. You just verify the details.

**Supplier Features:**
- Full purchase history
- Outstanding balance (what you owe)
- Aged creditors analysis
- Supplier item code mapping (learns over time)
- Bank details for payment runs

**Purchase Orders:**
Create POs to suppliers → when goods arrive → do GRV → matches to PO

**Ask Zane:**
- "How much do we owe [supplier]?"
- "What did we last pay for [item] from [supplier]?"
- "Show [supplier]'s outstanding invoices"
- "When is [supplier]'s next payment due?"  """
    },

    # ============================================================
    # RENTAL PROPERTY MANAGEMENT
    # ============================================================
    
    "rental_management": {
        "keywords": ["rental", "rent", "huur", "tenant", "huurder", "property", "eiendom", "lease", "b&b", "guesthouse"],
        "title": "Rental & Property Management",
        "content": """ClickAI handles rental properties and B&B/guesthouse management:

**Setting Up Rentals:**
1. Rentals → + New Property/Unit
2. Enter: Unit name/number, address, monthly rent
3. Add tenant: Name, contact, lease start/end dates
4. Set: Deposit amount, escalation %, included services

**Monthly Invoicing:**
- Auto-generates rent invoices on the 1st (or your chosen date)
- Includes: Base rent, municipal charges passed through, other charges
- Tenants get automatic statements

**Municipal Charges:**
Post municipal account as expense, then re-invoice to tenant:
- Water, electricity, sewage, refuse
- Split proportionally across units if needed

**B&B/Guesthouse:**
- Room booking management
- Nightly rate vs monthly rate
- Occupancy tracking
- Revenue per room reporting

**Accounting Treatment:**
- Rental income GL account (separate from sales)
- Deposit held in liability account
- Municipal recharges as pass-through
- Maintenance expenses per property

**Ask Zane:**
- "Which tenants are in arrears?"
- "Generate rent invoices for this month"
- "Show me rental income for the year"  """
    },

    # ============================================================
    # BUSINESS SETUP
    # ============================================================
    
    "business_setup": {
        "keywords": ["setup", "start", "begin", "new business", "configure", "opset", "first time", "getting started"],
        "title": "Setting Up a New Business in ClickAI",
        "content": """Step-by-step to get your business running on ClickAI:

**Step 1: Business Details (Settings)**
- Business name, registration number
- VAT number (if registered)
- Physical and postal address
- Contact details, logo upload
- Financial year end (usually Feb or Dec for SA)

**Step 2: Choose Business Type**
- Hardware Store, Retail, Restaurant/Pub, B&B, Professional Services, etc.
- This pre-loads relevant GL accounts, categories, and templates

**Step 3: Chart of Accounts**
- Review pre-loaded accounts
- Add any custom accounts you need
- Set up bank accounts (match to your actual bank accounts)

**Step 4: Opening Balances**
If migrating from another system:
- Enter opening balances via journal entry
- Import customer/supplier balances
- Import stock with quantities and values

**Step 5: Add Users & Permissions**
- Settings → Users → Invite
- Set roles: Owner, Manager, Cashier, Accountant, Viewer
- Permissions control what each user can see and do

**Step 6: Stock Setup**
- Import stock from CSV or add manually
- Set categories, prices, reorder levels
- Ask Zane to assign smart codes and categories

**Step 7: Customers & Suppliers**
- Import from CSV or add as you go
- Supplier invoices from scanning auto-create suppliers

**Step 8: Scanner Setup**
- Configure scan-to-email (see scanner setup guide)
- Test with a sample invoice

You're ready to go! Start with daily operations and the system learns your patterns."""
    },

    "multi_business": {
        "keywords": ["multi business", "multiple business", "switch business", "meer besighede", "second business", "franchise"],
        "title": "Multi-Business Management",
        "content": """ClickAI supports unlimited businesses under one account:

**Adding a Business:**
Settings → Businesses → + Add Business
Each business has completely separate:
- Stock, customers, suppliers
- GL accounts and financials
- Users and permissions
- Reports and data

**Switching:**
Click the business name in top-right header → select another business.
Instant switch, no logout needed.

**Cross-Business Features:**
- Dashboard can show all businesses overview
- Consolidated reporting (coming)
- Intercompany transactions
- Same staff can work across businesses with different roles

**Use Case Examples:**
- Deon: Fulltech Workwear + Hardware Store + Pub + B&B (all separate books)
- Franchise: Same system, each franchisee gets their own business
- Group: Holding company + subsidiaries

**Pricing:**
Unlimited businesses included in subscription. No per-business charges.
This is a MAJOR advantage over Sage/Xero which charge per entity."""
    },

    # ============================================================
    # USER ROLES & PERMISSIONS
    # ============================================================
    
    "user_permissions": {
        "keywords": ["user", "permission", "role", "access", "staff", "cashier", "manager", "toestemming", "gebruiker"],
        "title": "User Roles & Permissions",
        "content": """ClickAI role-based access control:

**Roles:**
- **Owner**: Full access to everything, can manage users
- **Manager**: Most access, can approve transactions, view reports
- **Accountant**: Accounting, banking, reports, journals, payroll
- **Salesperson**: Invoices, quotes, customers, stock (view only)
- **Cashier**: POS only, basic stock viewing
- **Viewer**: Read-only access to reports and data

**What each role controls:**
- Can they see costs/margins? (Cashiers: No)
- Can they approve scanned invoices? (Managers+: Yes)
- Can they process payroll? (Owner/Accountant: Yes)
- Can they do journals? (Accountant+: Yes)
- Can they change settings? (Owner: Yes)
- Can they see other businesses? (Per-business assignment)

**Adding Users:**
1. Settings → Users → Invite
2. Enter email address
3. Select role
4. Select which business(es) they can access
5. Send invite → they create password and login

**Audit Trail:**
All actions are logged: who did what, when.
Owner can review the audit log in Settings."""
    },

    # ============================================================
    # MIGRATION FROM OTHER SYSTEMS
    # ============================================================
    
    "migration": {
        "keywords": ["migrate", "import", "sage", "xero", "quickbooks", "pastel", "switch", "convert", "oorskakel", "move from"],
        "title": "Migrating from Sage, Xero, QuickBooks",
        "content": """Moving to ClickAI from another accounting system:

**What to Import:**
1. Chart of Accounts (if customized)
2. Customer list with balances
3. Supplier list with balances
4. Stock items with quantities and values
5. Opening balances (TB at switch date)

**CSV Import:**
ClickAI accepts CSV files for:
- Stock: Code, Description, Category, Cost, Selling Price, Qty
- Customers: Name, Email, Phone, Balance
- Suppliers: Name, Email, Phone, Balance
- Opening Balances: Account, Debit, Credit

**Step-by-step:**
1. Export data from old system as CSV
2. In ClickAI: Settings → Import Data → select type
3. Upload CSV → map columns → preview → import
4. Verify totals match
5. Enter opening balances journal to balance the books

**Why Switch to ClickAI:**
- Sage: R500+/month per company, no AI scanning, complex
- Xero: R600+/month, limited SA features, no scan-to-post
- QuickBooks: Expensive, leaving SA market concerns
- ClickAI: Fraction of the cost, AI-powered, SA-specific, scan-to-post magic

**Transition Period:**
Run both systems parallel for one month to verify everything matches.
Then switch fully to ClickAI."""
    },

    # ============================================================
    # TROUBLESHOOTING
    # ============================================================
    
    "troubleshooting_common": {
        "keywords": ["error", "problem", "issue", "bug", "fout", "werk nie", "not working", "help", "broken", "crash"],
        "title": "Common Issues & Troubleshooting",
        "content": """Common issues and how to fix them:

**"Page not loading":**
- Check internet connection
- Try refresh (Ctrl+F5 for hard refresh)
- Clear browser cache
- Try different browser (Chrome recommended)

**"Login not working":**
- Check email/password spelling
- Use "Forgot Password" to reset
- Check if account is active

**"Invoice totals wrong":**
- Jayden handles math, so check line items
- VAT inclusive vs exclusive setting
- Discount applied correctly?
- Check rounding (ClickAI rounds to 2 decimal places)

**"Scan not reading correctly":**
- Better photo quality = better reading
- Ensure document is flat, well-lit, not blurry
- PDF works better than photos for emailed invoices
- Jacqo works best with clear, printed invoices

**"Stock quantities wrong":**
- Check: Did a GRV post? Did returns process?
- Stock movements report shows all in/out
- Do a stock take to correct (Stock → Stock Take)

**"Can't see a feature":**
- Check your user role/permissions
- Some features only show for Owner/Manager
- Check if feature is enabled in Settings

**"Slow performance":**
- Close unused browser tabs
- Large reports may take longer
- Check internet speed
- Try during off-peak hours

**Still stuck?** Ask Zane - describe your problem in plain language 
and he'll help troubleshoot step by step."""
    },

    # ============================================================
    # COMPETITIVE ADVANTAGES
    # ============================================================
    
    "why_clickai": {
        "keywords": ["why clickai", "better than", "advantage", "compared to", "vs sage", "vs xero", "competitor", "voordeel"],
        "title": "Why ClickAI - Competitive Advantages",
        "content": """What makes ClickAI different from Sage, Xero, QuickBooks:

**1. AI-Powered Scan-to-Post (KILLER FEATURE)**
Scan a supplier invoice → AI reads it → posts to books automatically.
No other SA accounting software does this with AI.

**2. 4 AI Workers, Not Just 1 Chatbot**
Zane (assistant), Jacqo (reader), Diane (analyst), Jayden (calculator)
Each specialized. AI doesn't do math - Jayden does. No rounding errors.

**3. Built for South Africa**
- SARS compliant (PAYE tables, VAT201, IRP5)
- Rand-based, SA accounting standards
- Understands SA business (municipal charges, BEE, COIDA)
- Bilingual: English and Afrikaans

**4. Unlimited Businesses**
One subscription = unlimited businesses. Sage charges per company.

**5. Bank Reconciliation AI**
Learns your patterns. Month-end goes from hours to minutes.

**6. Way Cheaper**
Fraction of the cost of Sage/Xero/QuickBooks.

**7. All-in-One**
Accounting + Stock + POS + Payroll + Scanning + CRM + Rentals + Jobs
No need for separate systems or add-ons.

**8. Mobile-First**
Works on any phone. Scan invoices from phone camera.
POS works on tablet. Swipe navigation.

**9. Always Learning**
The more you use it, the smarter it gets at matching 
bank transactions, reading supplier codes, suggesting categories."""
    },

    # ============================================================
    # GOODS RECEIVED VOUCHERS (GRV)
    # ============================================================
    
    "grv_system": {
        "keywords": ["grv", "goods received", "receive stock", "book in", "ontvang", "delivery", "aflewering"],
        "title": "Goods Received Vouchers (GRV)",
        "content": """GRVs are how you book stock into the system when goods arrive:

**From Scanned Invoice:**
Most GRVs happen automatically:
1. Scan supplier invoice (or it arrives via email)
2. Jacqo reads line items and quantities
3. Review shows matched stock items
4. Approve → stock quantities increase → supplier account credited

**Manual GRV:**
1. Purchases → GRV → + New
2. Select supplier
3. Add items received: stock item, quantity, cost price
4. If linked to PO: match against purchase order
5. Save → stock updates immediately

**GRV vs Invoice:**
- GRV = physical goods received (updates stock)
- Supplier Invoice = financial document (creates liability)
- In ClickAI, a scanned invoice can do BOTH at once

**Cost Price Updates:**
When GRV price differs from current cost:
- Weighted average recalculates automatically
- Selling prices can auto-adjust if markup % is set

**Partial Deliveries:**
If you ordered 100 but received 80:
- GRV for 80 received
- PO stays open for remaining 20
- Next delivery closes the PO"""
    },

    # ============================================================
    # JOB CARDS
    # ============================================================
    
    "job_cards": {
        "keywords": ["job", "job card", "werk", "project", "werkkaart", "task", "service job"],
        "title": "Job Cards / Project Management",
        "content": """Job cards track work, materials, and costs per project/job:

**Creating a Job:**
1. Jobs → + New Job
2. Enter: Job name, customer, description
3. Set: Quoted amount, deadline, assigned staff

**Tracking on a Job:**
- **Materials**: Allocate stock items used (reduces stock, adds to job cost)
- **Labour**: Log hours worked by employee
- **Expenses**: Attach any direct expenses
- **Subcontractors**: Record outsourced work costs

**Job Costing:**
System automatically calculates:
- Total materials cost
- Total labour cost
- Total expenses
- Total cost vs quoted price
- Profit/loss per job

**Invoicing from Job:**
When job is complete: Job → Create Invoice
Automatically includes all items and labour on the invoice.

**Use Cases:**
- Workshop repairs (hardware store)
- Installation jobs
- Maintenance contracts
- Project-based work
- Construction/renovation

**Reports:**
- Job profitability report
- Work in progress (WIP)
- Jobs by status (open/complete/overdue)"""
    },

    # ============================================================
    # CREDIT NOTES & RETURNS
    # ============================================================
    
    "credit_notes": {
        "keywords": ["credit note", "return", "refund", "terugbetaling", "kredietnota", "cancel invoice"],
        "title": "Credit Notes & Returns",
        "content": """Handling returns and credit notes:

**Customer Returns (Credit Note):**
1. Sales → Credit Notes → + New
2. Link to original invoice (or standalone)
3. Add items being returned with quantities
4. Reason for return
5. Post → reverses the original entries:
   - Debtor balance decreases
   - Sales decrease
   - Stock quantity increases (if physical return)

**Supplier Returns:**
1. Purchases → Debit Note → + New
2. Link to original supplier invoice
3. Add items being returned
4. Post → reverses:
   - Creditor balance decreases
   - Purchases decrease
   - Stock quantity decreases

**POS Refunds:**
In POS → Refund → select original sale → process return
Cash refund or credit to account.

**Partial Credit:**
Don't have to credit the whole invoice - can credit specific lines 
or partial quantities.

**Tip:** Always link credit notes to original invoices for proper audit trail."""
    },

    # ============================================================
    # RECURRING INVOICES
    # ============================================================
    
    "recurring_invoices": {
        "keywords": ["recurring", "repeat", "monthly invoice", "subscription", "herhalend", "auto invoice"],
        "title": "Recurring Invoices",
        "content": """Set up invoices that auto-generate on a schedule:

**Setup:**
1. Sales → Recurring → + New Template
2. Create invoice as normal (customer, items, amounts)
3. Set frequency: Weekly, Monthly, Quarterly, Annually
4. Set: Start date, end date (or ongoing)
5. Enable: Auto-send to customer (optional)

**Use Cases:**
- Monthly rent invoices to tenants
- Retainer fees to clients
- Subscription billing
- Regular service charges
- Lease payments

**How it works:**
On the scheduled date, ClickAI automatically:
1. Creates the invoice from the template
2. Posts to accounting
3. Sends to customer (if enabled)
4. Appears on dashboard as new invoice

**Management:**
- Pause/resume any recurring invoice
- Edit template for future invoices
- View history of all generated invoices
- Skip a period if needed"""
    },

    # ============================================================
    # SARS & SA COMPLIANCE (Tax Tables, UIF, SDL, COIDA, B-BBEE)
    # ============================================================


    # ============================================================
    # PAYE TAX TABLES
    # ============================================================
    
    "sars_paye_tables": {
        "keywords": ["paye", "tax table", "tax bracket", "belasting", "income tax", "tax rate", "pay as you earn", "tax tables"],
        "title": "SARS PAYE Tax Tables 2025/2026",
        "content": """PAYE Tax Tables for 2025/2026 tax year (1 March 2025 - 28 Feb 2026):
NO CHANGES from previous year.

**Tax Brackets (Annual Income):**
| Taxable Income (R) | Rate |
|---|---|
| 1 - 237,100 | 18% |
| 237,101 - 370,500 | R42,678 + 26% above R237,100 |
| 370,501 - 512,800 | R77,362 + 31% above R370,500 |
| 512,801 - 673,000 | R121,475 + 36% above R512,800 |
| 673,001 - 857,900 | R179,147 + 39% above R673,000 |
| 857,901 - 1,817,000 | R251,258 + 41% above R857,900 |
| 1,817,001+ | R644,489 + 45% above R1,817,000 |

**Tax Rebates (Annual):**
- Primary (all taxpayers): R17,235
- Secondary (65+): R9,444
- Tertiary (75+): R3,145

**Tax Thresholds (below this = no tax):**
- Under 65: R95,750/year (R7,979/month)
- 65-74: R148,217/year
- 75+: R165,689/year

**Medical Tax Credits (Monthly):**
- Main member: R364
- First dependent: R364
- Each additional dependent: R246

Jayden uses these exact tables for payroll calculations - no rounding errors."""
    },

    # ============================================================
    # UIF
    # ============================================================
    
    "sars_uif": {
        "keywords": ["uif", "unemployment", "werkloosheid", "unemployment insurance", "uif contribution", "uif rate"],
        "title": "UIF - Unemployment Insurance Fund",
        "content": """UIF Requirements for 2025/2026:

**Contribution Rate:** 2% total
- Employee pays: 1% (deducted from salary)
- Employer pays: 1% (additional cost to company)

**Maximum Earnings Ceiling:** R17,712 per month (R212,544/year)
- Max employee contribution: R177.12/month
- Max employer contribution: R177.12/month
- Total max: R354.24/month
- If employee earns MORE than R17,712, UIF is STILL only calculated on R17,712

**Who must register:**
- ALL employers with 1 or more employees
- Includes part-time and temporary workers
- Excludes: Independent contractors, workers working less than 24 hours/month

**What UIF covers for employees:**
- Unemployment benefits (up to 365 days)
- Maternity leave benefits
- Adoption leave benefits
- Illness benefits (if can't work)
- Death benefits (dependants)

**How to pay:**
UIF is included in the monthly EMP201 return to SARS.
ClickAI calculates UIF automatically on each payslip.

**Important:** Employer MUST pay over UIF even if they didn't deduct from employee.
Failure = criminal offence, fine or up to 2 years imprisonment."""
    },

    # ============================================================
    # SDL
    # ============================================================
    
    "sars_sdl": {
        "keywords": ["sdl", "skills development", "levy", "training levy", "vaardigheidsheffing"],
        "title": "SDL - Skills Development Levy",
        "content": """SDL Requirements for 2025/2026:

**Rate:** 1% of total payroll
- Paid by EMPLOYER only (not deducted from employee)
- Calculated on total remuneration (including benefits, bonuses, commission)

**Exemption:**
- Employers with annual payroll UNDER R500,000 are EXEMPT from SDL
- But may still need to declare R0 on EMP201 to stay compliant
- If payroll crosses R500,000 mid-year, SDL applies retroactively

**How to pay:**
Included in monthly EMP201 return to SARS.
ClickAI calculates SDL automatically.

**SETA Claim-back:**
- 20% of SDL can be claimed back as Mandatory Grant
- Must submit Workplace Skills Plan (WSP) to your SETA
- Additional 49.5% available as Discretionary Grant
- Deadline: Usually 30 April each year

**Which SETA?**
Depends on your industry:
- Retail: W&RSETA
- Manufacturing: merSETA
- Construction: CETA
- Services: Services SETA
- Agriculture: AgriSETA"""
    },

    # ============================================================
    # EMP201 & EMP501
    # ============================================================
    
    "sars_emp201_emp501": {
        "keywords": ["emp201", "emp501", "monthly return", "employer return", "reconciliation", "filing", "submit", "sars return", "employer declaration"],
        "title": "EMP201 & EMP501 - Employer Returns",
        "content": """SARS Employer Filing Requirements:

**EMP201 (Monthly):**
- Submit by 7th of the following month (or last business day before)
- Declares: PAYE + UIF + SDL amounts for that month
- Payment must accompany the declaration
- A unique Payment Reference Number (PRN) links payment to declaration
- ClickAI generates the EMP201 data from payroll

**EMP501 (Reconciliation - Twice per year):**
1. Interim: Sep-Oct (covers Mar-Aug)
   - 22 September to 31 October
2. Annual: Apr-May (covers full tax year Mar-Feb)
   - 1 April to 31 May

**What EMP501 reconciles:**
- Monthly EMP201 declarations submitted
- Payments made to SARS
- IRP5/IT3(a) certificates generated for employees
- ALL THREE must balance!

**How to submit:**
- <50 employees: SARS eFiling or e@syFile
- 50+ employees: e@syFile Employer (mandatory)

**Penalties for non-compliance:**
- Late EMP501: 1% of annual PAYE liability per month (max 10%)
- Failure to submit: Criminal offence, fine or up to 2 years imprisonment
- Late EMP201 payment: Interest + penalties

**From Feb 2026:** All employees MUST have valid Income Tax numbers on IRP5 certificates.

**Keep records for 5 years!** SARS can audit any time."""
    },

    # ============================================================
    # IRP5 CERTIFICATES
    # ============================================================
    
    "sars_irp5": {
        "keywords": ["irp5", "it3a", "tax certificate", "employee certificate", "sertifikaat", "tax year end"],
        "title": "IRP5 / IT3(a) Tax Certificates",
        "content": """Employee Tax Certificates:

**IRP5:** Issued to employees who had PAYE deducted
**IT3(a):** Issued to employees/directors with NO PAYE deducted (below threshold)

**What it contains:**
- Employee details (name, ID, tax number)
- Employer details
- Total income earned (gross)
- PAYE deducted
- UIF contributions
- Medical aid contributions
- Retirement fund contributions
- Travel allowance details
- All source codes per SARS BRS

**When to issue:**
- Within 60 days after end of tax year (28 Feb)
- Within 14 days if employee leaves during the year
- Must also be submitted to SARS via EMP501

**Source Codes (common):**
- 3601: Basic salary
- 3605: Annual bonus
- 3701: Commission
- 3702: Overtime
- 4001: PAYE deducted
- 4003: UIF employee contribution
- 4006: Medical scheme contribution

**ClickAI generates IRP5 data** from payroll records automatically.
Export format compatible with e@syFile for SARS submission."""
    },

    # ============================================================
    # VAT REGISTRATION & COMPLIANCE
    # ============================================================
    
    "sars_vat_registration": {
        "keywords": ["vat registration", "vat register", "btw registrasie", "vat vendor", "r1 million", "when to register vat", "vat threshold"],
        "title": "VAT Registration Requirements",
        "content": """VAT Registration Rules in South Africa:

**Compulsory Registration:**
- Turnover EXCEEDS R1 million in any 12-month period
- Must register within 21 days of exceeding threshold
- Effective from start of the month in which threshold was exceeded

**Voluntary Registration:**
- Turnover exceeds R50,000 in 12 months
- Useful to claim input VAT on purchases/startup costs
- Must maintain proper records

**VAT Rate:** 15% (since 1 April 2018)

**Filing Periods:**
- Category A: Monthly (turnover >R30 million)
- Category B: Every 2 months (most businesses) — Jan/Feb, Mar/Apr, etc.
- Category C: Every 6 months (turnover <R1.5 million, application required)

**VAT201 Return:**
- Due by 25th of the month following end of tax period
- Declare: Output VAT (sales) - Input VAT (purchases) = Amount payable/refundable
- Submit via SARS eFiling

**What you can claim Input VAT on:**
- Business expenses with valid tax invoices
- Must have supplier's VAT number on invoice
- Invoice must be in your business name
- Keep invoices for 5 years

**What you CANNOT claim:**
- Entertainment expenses (50% disallowed)
- Motor cars (some restrictions)
- Club subscriptions
- Personal expenses

**ClickAI tracks all VAT automatically** - output and input.
VAT return data available at click of a button."""
    },

    # ============================================================
    # PROVISIONAL TAX
    # ============================================================
    
    "sars_provisional_tax": {
        "keywords": ["provisional tax", "voorlopige belasting", "itr6", "provisional", "estimated tax", "top up"],
        "title": "Provisional Tax",
        "content": """Provisional Tax for businesses and self-employed:

**Who must pay:**
- Any person who earns income NOT subject to PAYE
- Sole proprietors, partnerships, companies, trusts
- Employees with additional income (freelance, rental, investment)

**Payment Schedule (2 compulsory + 1 optional):**
1. First payment: Within 6 months after start of tax year
   - Due: 31 August (for Feb year-end)
   - Based on estimated taxable income for the full year
   - Must pay at least 50% of estimated tax

2. Second payment: At end of tax year
   - Due: 28/29 February
   - Top up to full estimated tax liability
   - Estimate must be within 90% of actual (or face penalties)

3. Third payment (optional/top-up):
   - Due: 7 months after year-end (30 September)
   - Only if you want to reduce interest on underpayment

**Penalties:**
- Underestimation: 20% penalty if estimate is <90% of actual
- Late payment: Interest at prescribed rate (repo rate + 100 basis points)

**How ClickAI helps:**
- Track all income and expenses in real-time
- Diane can estimate your provisional tax liability
- Generate profit projection for accurate estimates"""
    },

    # ============================================================
    # COIDA
    # ============================================================
    
    "sars_coida": {
        "keywords": ["coida", "compensation fund", "workmen's comp", "workplace injury", "besering", "kompensasiefonds", "occupational injury"],
        "title": "COIDA - Compensation for Occupational Injuries",
        "content": """COIDA (Compensation for Occupational Injuries and Diseases Act):

**What is it?**
Insurance that covers employees for workplace injuries and diseases.
Employer-funded, NOT deducted from employee salary.

**Earnings Threshold 2025/2026:** R633,168 per year
- Only calculate on earnings up to this threshold
- Even if employee earns more

**Registration:**
- ALL employers must register with the Compensation Fund
- Register at Department of Employment & Labour
- Or online at compensation.labour.gov.za

**Assessment Rate:**
- Varies by industry (risk-based)
- Hardware/retail: typically 0.53% - 1.5%
- Office/admin: typically 0.11% - 0.25%
- Construction: typically 2% - 7%

**Annual Return of Earnings (ROE):**
- Submit by 31 March each year
- Declares total earnings paid to ALL employees
- Assessment calculated on total earnings

**What it covers:**
- Medical expenses for workplace injuries
- Temporary disability (75% of earnings)
- Permanent disability (lump sum or pension)
- Death benefits for dependants
- Occupational diseases

**Important:**
- Must report ALL workplace injuries within 7 days
- Employee can claim even if injury was their own fault
- Does NOT cover injuries during personal activities
- Letter of Good Standing needed for tenders/contracts

ClickAI tracks COIDA as an employer expense in payroll."""
    },

    # ============================================================
    # EMPLOYER TAX DEADLINES CALENDAR
    # ============================================================
    
    "sars_deadlines": {
        "keywords": ["deadline", "due date", "when", "calendar", "dates", "sperdatum", "wanneer moet ek", "filing date", "tax date"],
        "title": "SARS Employer Tax Deadlines Calendar",
        "content": """Key SARS deadlines for employers:

**MONTHLY:**
- 7th: EMP201 submission + payment (PAYE, UIF, SDL)
  (Last business day before 7th if it's weekend/holiday)

**ANNUALLY (Tax year: 1 Mar - 28 Feb):**

| When | What | Details |
|---|---|---|
| 31 March | COIDA Return of Earnings | Annual assessment |
| 1 Apr - 31 May | EMP501 Annual Reconciliation | Full year Mar-Feb |
| 30 April | SETA WSP Submission | Skills plan for SDL claim-back |
| 31 May | EMP501 deadline | Final date for annual |
| 31 August | Provisional Tax 1st payment | Based on estimated income |
| 22 Sep - 31 Oct | EMP501 Interim | Covers Mar-Aug |
| 28/29 Feb | Provisional Tax 2nd payment | Year-end top-up |
| Within 60 days | IRP5 to employees | After tax year end |

**VAT (Category B - bi-monthly):**
- 25th of month after period end
- Periods: Jan/Feb, Mar/Apr, May/Jun, Jul/Aug, Sep/Oct, Nov/Dec

**Penalties for late filing:**
- EMP201 late: Interest + administrative penalties
- EMP501 late: 1% of PAYE liability per month (max 10%)
- VAT late: 10% penalty on amount due
- Provisional tax under-estimate: 20% penalty

**ClickAI helps by:**
- Tracking all payroll data for EMP201/EMP501
- Generating VAT return data
- Reminding of upcoming deadlines
- Keeping 5-year audit trail as required by SARS"""
    },

    # ============================================================
    # EMPLOYMENT TAX INCENTIVE (ETI)
    # ============================================================
    
    "sars_eti": {
        "keywords": ["eti", "employment tax incentive", "youth employment", "incentive", "young worker", "first job"],
        "title": "ETI - Employment Tax Incentive",
        "content": """Employment Tax Incentive (ETI) - Hiring young workers:

**What is it?**
Tax incentive that encourages employers to hire young workers.
Reduces the amount of PAYE you pay to SARS (NOT a deduction from employee).

**Qualifying Criteria:**
Employee must:
- Be 18 to 29 years old
- Have a valid SA ID or asylum permit
- NOT be a domestic worker in a private household
- Earn between national minimum wage and R6,500/month
- NOT be a connected person (family member)

Employer must:
- Be registered for PAYE
- Be tax compliant (no outstanding returns/debt)
- Pay at least the national minimum wage (R28.79/hour for 2025)

**Incentive Amount (per qualifying employee per month):**
| Monthly Salary | First 12 months | Next 12 months |
|---|---|---|
| R0 - R2,000 | 50% of salary | 25% of salary |
| R2,001 - R4,500 | R1,000 | R500 |
| R4,501 - R6,500 | Sliding scale | Sliding scale |
| Above R6,500 | R0 | R0 |

**How to claim:**
- Declare on EMP201 monthly return
- Reduces PAYE payment to SARS
- Must be included in EMP501 reconciliation
- If ETI exceeds PAYE, excess carries forward

**ClickAI calculates ETI** for qualifying employees automatically on payroll."""
    },

    # ============================================================
    # NATIONAL MINIMUM WAGE
    # ============================================================
    
    "sa_minimum_wage": {
        "keywords": ["minimum wage", "minimum loon", "minimum pay", "hourly rate", "nmw", "national minimum"],
        "title": "National Minimum Wage 2025/2026",
        "content": """National Minimum Wage (NMW) - effective 1 March 2025:

**Standard rate:** R28.79 per hour

**Sector variations:**
- Expanded Public Works Programme (EPWP): R15.16/hour
- Farmworkers: R28.79/hour (now aligned with standard)
- Domestic workers: R28.79/hour (now aligned with standard)

**Calculating monthly from hourly:**
- R28.79 × 8 hours × 21.67 working days = ~R4,990.85/month
- For 45-hour week: R28.79 × 195 hours/month = ~R5,614.05/month

**BCEA Earnings Threshold:** R241,110.59 per year (R20,092.55/month)
- Employees earning ABOVE this are excluded from:
  - Overtime pay requirements
  - Sunday pay premium
  - Night shift allowance
  - Mandatory rest breaks

**Overtime:**
- 1.5x normal rate for overtime hours
- 2x normal rate for Sundays and public holidays
- Maximum 10 hours overtime per week
- Employee can agree to time-off instead of payment

**ClickAI's payroll system validates** that no employee is paid below NMW.
Warnings appear if you try to create a payslip below minimum."""
    },

    # ============================================================
    # RECORD KEEPING REQUIREMENTS
    # ============================================================
    
    "sars_record_keeping": {
        "keywords": ["record keeping", "records", "retain", "keep", "audit", "bewaar", "rekords", "5 year", "documentation"],
        "title": "SARS Record Keeping Requirements",
        "content": """Legal record keeping requirements for SA businesses:

**General Rule: Keep ALL records for 5 years** from date of submission.

**What to keep:**
- All invoices (sales and purchase)
- Bank statements
- Receipts and proof of payment
- Payroll records and payslips
- Tax returns (VAT, PAYE, Income Tax)
- IRP5 certificates
- Contracts of employment
- Leave records
- Stock records and valuations
- Fixed asset register
- General ledger and journals
- Trial balances and financial statements

**Format:**
- Can be electronic (PDF, scanned images, accounting software backups)
- Must be in official language (English or Afrikaans for SA)
- Must be accessible on request by SARS

**Penalties for non-compliance:**
- Not keeping records: Fine or imprisonment up to 2 years
- SARS can estimate your tax liability if no records available
- Burden of proof shifts to taxpayer

**How ClickAI helps:**
- ALL transactions stored digitally in Supabase cloud database
- Scanned invoices stored as proof
- Automatic audit trail (who did what, when)
- Data backed up and secure
- Can export any records for SARS audit at any time
- This alone is worth the subscription - your paper trail is automated!"""
    },

    # ============================================================
    # COMPANY TAX
    # ============================================================
    
    "sars_company_tax": {
        "keywords": ["company tax", "corporate tax", "maatskappy belasting", "pty ltd", "close corporation", "cc tax", "sbc", "small business corporation"],
        "title": "Company & Small Business Tax Rates",
        "content": """Company Tax Rates for 2025/2026:

**Standard Company Tax Rate:** 27% of taxable income
(Reduced from 28% effective for years ending on or after 31 March 2023)

**Small Business Corporation (SBC) Tax Rates:**
Qualifying companies get reduced rates:
| Taxable Income | Rate |
|---|---|
| R0 - R95,750 | 0% (No tax!) |
| R95,751 - R365,000 | 7% of amount above R95,750 |
| R365,001 - R550,000 | R18,848 + 21% above R365,000 |
| R550,001+ | R57,698 + 27% above R550,000 |

**SBC Qualification (ALL must apply):**
- Close Corporation, Co-operative, or Private Company (Pty Ltd)
- All shareholders/members are natural persons (no companies)
- Gross income does not exceed R20 million per year
- Not more than 20% of income from investment income
- No member holds shares in another company (exceptions apply)

**Turnover Tax (Alternative for micro businesses):**
For businesses with turnover under R1 million:
| Turnover | Rate |
|---|---|
| R0 - R335,000 | 0% |
| R335,001 - R500,000 | 1% above R335,000 |
| R500,001 - R750,000 | R1,650 + 2% above R500,000 |
| R750,001 - R1,000,000 | R6,650 + 3% above R750,000 |

**Provisional Tax:**
Companies must pay provisional tax twice yearly (see provisional tax guide).

**Dividends Tax:** 20% withholding tax on dividends declared."""
    },

    # ============================================================
    # BEE / B-BBEE
    # ============================================================
    
    "sa_bee": {
        "keywords": ["bee", "b-bbee", "bbbee", "broad based", "empowerment", "scorecard", "level", "bee level", "bee certificate"],
        "title": "B-BBEE (Broad-Based Black Economic Empowerment)",
        "content": """B-BBEE Overview for SA businesses:

**What is B-BBEE?**
Government policy to increase participation of black South Africans in the economy.
Measured by a scorecard system, Level 1 (best) to Level 8 (minimum) or Non-compliant.

**Why it matters:**
- Required for government tenders
- Large companies prefer BEE-compliant suppliers
- Better BEE level = procurement advantage
- Some industries require minimum BEE levels

**Scorecard Elements (Generic):**
| Element | Weighting |
|---|---|
| Ownership | 25 points |
| Management Control | 19 points |
| Skills Development | 20 points |
| Enterprise & Supplier Development | 40 points |
| Socio-Economic Development | 15 points |

**EME (Exempted Micro Enterprise):**
- Turnover R10 million or less
- Automatic Level 4 (or Level 1 if >51% black owned)
- Only need sworn affidavit, no verification needed
- Most ClickAI clients will be EME level

**QSE (Qualifying Small Enterprise):**
- Turnover R10 million - R50 million
- Choose any 4 of the 5 scorecard elements
- Need verification by approved agency

**How ClickAI helps:**
- Track supplier BEE levels
- Record BEE certificates
- Skills Development tracking (for SDL/SETA submissions)
- Supplier reports showing BEE-compliant vs non-compliant spend"""
    },

}


def get_relevant_knowledge(user_message: str, max_chunks: int = 2) -> list:
    """
    RAG function: Match user message to relevant knowledge chunks.
    Returns max_chunks most relevant entries.
    """
    if not user_message:
        return []
    
    msg_lower = user_message.lower()
    scored = []
    
    for key, entry in CLICKAI_KNOWLEDGE.items():
        score = 0
        for keyword in entry["keywords"]:
            if keyword.lower() in msg_lower:
                # Longer keyword matches are more specific/valuable
                score += len(keyword.split())
        
        if score > 0:
            scored.append((score, key, entry))
    
    # Sort by score (highest first) and return top N
    scored.sort(key=lambda x: x[0], reverse=True)
    
    results = []
    for score, key, entry in scored[:max_chunks]:
        results.append({
            "title": entry["title"],
            "content": entry["content"]
        })
    
    return results


def format_knowledge_for_prompt(chunks: list) -> str:
    """Format knowledge chunks for injection into Zane's system prompt."""
    if not chunks:
        return ""
    
    sections = []
    for chunk in chunks:
        sections.append(f"### {chunk['title']}\n{chunk['content']}")
    
    return "\n\n---\n\n## RELEVANT KNOWLEDGE\n" + "\n\n".join(sections)


# Quick test
if __name__ == "__main__":
    test_queries = [
        "how do I scan an invoice?",
        "wie is Diane en wat doen sy?",
        "help me set up a new business",
        "what makes ClickAI better than Sage?",
        "how does the POS work?",
        "I need to do bank reconciliation",
        "create an invoice for ABC Hardware",
        "how do I add a new employee for payroll?",
        "what reports can I run?",
        "my stock codes are wrong",
    ]
    
    for q in test_queries:
        chunks = get_relevant_knowledge(q)
        titles = [c["title"] for c in chunks]
        print(f"Q: {q}")
        print(f"  → {titles}")
        print()
