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
  rentals, troubleshooting
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
