"""
ClickAI Bookkeeping Knowledge — Accounting rules & principles for Zane
══════════════════════════════════════════════════════════════════════════
When users ask "where do I book this?" or "is this an expense or asset?",
Zane needs to know proper accounting treatment.

Focused on SA small business bookkeeping — practical, not academic.
"""

BOOKKEEPING_CHUNKS = [
    # ═══ FUNDAMENTALS ═══
    {
        "keywords": ["DEBIT", "CREDIT", "DEBIT CREDIT", "LEFT RIGHT", "DEBIET", "KREDIET", "DOUBLE ENTRY"],
        "context": "Debit & Credit basics for SA small business: "
                   "DEBIT (left) INCREASES: assets (bank, stock, debtors, equipment), expenses (rent, fuel, wages). "
                   "CREDIT (right) INCREASES: liabilities (creditors, loans, VAT owing), income (sales, interest), equity (capital). "
                   "Every transaction has equal debits and credits. "
                   "Simple way to remember: money IN to bank = debit bank; money OUT of bank = credit bank. "
                   "Expense paid = debit expense, credit bank. Sale made = debit bank/debtor, credit sales."
    },
    {
        "keywords": ["ASSET", "EXPENSE", "CAPITALISE", "CAPITALIZE", "BATE", "UITGAWE"],
        "context": "Asset vs Expense — the R7,000 rule (SA): "
                   "If an item costs UNDER R7,000 and lasts less than a year → EXPENSE it immediately. "
                   "If it costs OVER R7,000 and will be used for more than 1 year → CAPITALISE as an asset and depreciate. "
                   "Examples: Laptop R15,000 → Asset, depreciate over 3 years. Keyboard R500 → Expense immediately. "
                   "Printer R6,500 → Expense (under R7k). Aircon R12,000 → Asset, depreciate over 6 years. "
                   "For SBCs (Small Business Corps): can write off ALL assets 50/30/20 over 3 years, "
                   "and manufacturing assets 100% in year 1. This is a tax benefit, not an accounting rule."
    },
    {
        "keywords": ["STOCK", "INVENTORY", "COST OF SALES", "COGS", "VOORRAAD", "KOSTE VAN VERKOPE"],
        "context": "Stock/inventory accounting: Stock purchased is an ASSET (not an expense) until sold. "
                   "When sold, it becomes Cost of Sales (expense). "
                   "Cost of Sales = Opening Stock + Purchases - Closing Stock. "
                   "Stock valuation methods: FIFO (first in first out — most common in SA), "
                   "weighted average, or specific identification. "
                   "SARS requires consistency — pick a method and stick with it. "
                   "Stock write-downs: if stock is damaged/obsolete, write down to net realisable value. "
                   "Stock take: do physical count at least annually (monthly for food/beverage)."
    },
    {
        "keywords": ["DEBTOR", "ACCOUNTS RECEIVABLE", "CREDIT SALES", "DEBITEURE", "OUTSTANDING"],
        "context": "Debtors/accounts receivable: When you sell on credit, debit Debtors, credit Sales. "
                   "When customer pays, debit Bank, credit Debtors. "
                   "Age analysis is critical: 0-30 days (current), 30-60 (overdue), 60-90 (concern), "
                   "90+ (action required — send to collections or write off). "
                   "SA average: aim for debtor days under 45 for retail, under 30 for services. "
                   "Bad debt provision: can provide for specific doubtful debts (SARS allows 25% of 120+ days). "
                   "Credit check customers before extending credit. Get signed credit agreements."
    },
    {
        "keywords": ["CREDITOR", "ACCOUNTS PAYABLE", "SUPPLIER", "KREDITEURE", "OUTSTANDING PAYMENT"],
        "context": "Creditors/accounts payable: When you buy on credit, debit Stock/Expense, credit Creditors. "
                   "When you pay, debit Creditors, credit Bank. "
                   "Manage creditor days strategically: pay on time but don't pay early (use the cash flow). "
                   "Normal terms: 30 days from statement. Some suppliers offer 2% discount for 7-day payment "
                   "— this is effectively 24% annual return, almost always worth taking. "
                   "Age analysis for creditors too: know who you owe and when. "
                   "Keep supplier statements and reconcile monthly."
    },

    # ═══ BANK RECONCILIATION ═══
    {
        "keywords": ["BANK RECONCILIATION", "BANK RECON", "RECONCILE", "BANK BALANCE", "BANKREKONSILIASIE"],
        "context": "Bank reconciliation: match your books to the bank statement EVERY month. "
                   "Differences come from: outstanding cheques (in your books, not yet presented at bank), "
                   "deposits in transit, bank charges not yet recorded, direct debits, "
                   "errors (yours or the bank's — yes, banks make mistakes). "
                   "Process: start with bank statement balance, add outstanding deposits, "
                   "subtract unpresented payments = should equal your book balance. "
                   "ClickAI automates most of this — but review the unmatched items. "
                   "Tip: reconcile within 5 days of receiving the statement. The longer you wait, the harder it gets."
    },

    # ═══ VAT ACCOUNTING ═══
    {
        "keywords": ["VAT ACCOUNTING", "VAT ENTRY", "VAT JOURNAL", "INPUT OUTPUT", "BTW INSKRYWING"],
        "context": "VAT accounting entries: "
                   "Purchase (expense) R1,150 incl VAT: Debit Expense R1,000 + Debit VAT Input R150, Credit Bank R1,150. "
                   "Sale R2,300 incl VAT: Debit Bank R2,300, Credit Sales R2,000 + Credit VAT Output R150. "
                   "VAT payment to SARS: Debit VAT Output, Credit VAT Input, difference = Debit/Credit Bank. "
                   "If Output > Input: you owe SARS (most businesses). "
                   "If Input > Output: SARS owes you a refund (e.g. exporter or new business with big purchases). "
                   "Refunds take 21 working days (SARS often takes longer — budget for this). "
                   "VAT is calculated as: Amount × 15/115 (to extract VAT from inclusive price)."
    },

    # ═══ PAYROLL ═══
    {
        "keywords": ["PAYROLL", "SALARY ENTRY", "WAGE JOURNAL", "PAYSLIP", "SALARIS INSKRYWING"],
        "context": "Payroll journal entries (simplified): "
                   "Gross salary R15,000: Debit Salaries Expense R15,000, "
                   "Credit PAYE Payable R2,000, Credit UIF Payable R150, "
                   "Credit Net Salary Payable R12,850. "
                   "Employer contributions: Debit UIF Expense (employer portion) R150, Credit UIF Payable R150. "
                   "Debit SDL Expense R150, Credit SDL Payable R150. "
                   "When paying SARS: Debit PAYE/UIF/SDL Payable, Credit Bank. "
                   "When paying employee: Debit Net Salary Payable, Credit Bank. "
                   "Issue IRP5 to each employee for their tax return. Keep payroll records for 5 years."
    },

    # ═══ YEAR END ═══
    {
        "keywords": ["YEAR END", "FINANCIAL YEAR", "ANNUAL", "CLOSE OFF", "JAAREINDE", "BOEKJAAR"],
        "context": "Year-end procedures: "
                   "1. Physical stock count (value at cost or NRV, whichever lower). "
                   "2. Debtor review — identify bad debts, make provisions. "
                   "3. Fixed asset review — additions, disposals, depreciation. "
                   "4. Accruals — expenses incurred but not yet invoiced (e.g. electricity for last month). "
                   "5. Prepayments — expenses paid in advance (e.g. insurance for next year). "
                   "6. Bank reconciliation — all months up to year end. "
                   "7. VAT reconciliation — ensure VAT returns match books. "
                   "8. Payroll reconciliation — EMP501 matches payroll records. "
                   "9. Trial Balance review — check all accounts look reasonable. "
                   "10. Calculate tax provision. "
                   "Companies Act requires AFS within 6 months. SARS return within 12 months."
    },

    # ═══ COMMON QUESTIONS ═══
    {
        "keywords": ["DEPOSIT", "ADVANCE PAYMENT", "DEPOSITO", "VOORUITBETALING", "PREPAID"],
        "context": "Deposits and advance payments: "
                   "Deposit RECEIVED from customer: Debit Bank, Credit Deposits Received (liability — you owe the service). "
                   "When you deliver: Debit Deposits Received, Credit Sales Revenue. "
                   "Deposit PAID to supplier: Debit Deposits Paid (asset — they owe you), Credit Bank. "
                   "When goods received: Debit Stock/Expense, Credit Deposits Paid. "
                   "IMPORTANT: A deposit received is NOT income until you deliver. It's a liability. "
                   "Prepaid expenses (e.g. insurance paid annually): Debit Prepaid Expense (asset), Credit Bank. "
                   "Each month: Debit Insurance Expense, Credit Prepaid Expense (1/12th)."
    },
    {
        "keywords": ["LOAN", "BORROW", "LENING", "FINANCE", "REPAYMENT", "AFBETALING"],
        "context": "Loan accounting: "
                   "Loan received: Debit Bank (asset up), Credit Loan (liability up). "
                   "Monthly repayment has TWO parts: capital and interest. "
                   "Capital portion: Debit Loan (liability down), Credit Bank. "
                   "Interest portion: Debit Interest Expense, Credit Bank. "
                   "Don't book the full repayment as an expense — only the interest is an expense! "
                   "The capital portion reduces the loan balance (liability), not an expense. "
                   "Vehicle finance, equipment finance, overdraft — all follow the same principle. "
                   "Tip: get an amortisation schedule from the bank showing the split per month."
    },
    {
        "keywords": ["OWNER DRAWING", "DRAWINGS", "PERSONAL", "EIENAAR ONTTREKKING", "PRIVATE"],
        "context": "Owner drawings: when the owner takes money from the business for personal use. "
                   "Entry: Debit Owner Drawings (equity reduction), Credit Bank. "
                   "Drawings are NOT an expense — they reduce the owner's equity in the business. "
                   "They do NOT reduce taxable income. "
                   "Sole proprietor/CC: drawings are the owner's 'salary' but are treated differently from employee salaries. "
                   "Company (Pty Ltd): owner should take a salary (with PAYE) or declare dividends (with DWT). "
                   "Taking money as 'loan from company' has tax consequences (fringe benefit rules). "
                   "Tip: set a fixed monthly drawing amount — don't just take money when needed."
    },
    {
        "keywords": ["PETTY CASH", "CASH FLOAT", "KLEINGELD", "KONTANT"],
        "context": "Petty cash management: "
                   "Set up float: Debit Petty Cash (asset), Credit Bank. "
                   "Expenses from petty cash: Debit relevant Expense, Credit Petty Cash. "
                   "Top up: Debit Petty Cash, Credit Bank (restore to original float amount). "
                   "Rules: set a maximum per transaction (e.g. R500), require receipts for EVERYTHING, "
                   "one person responsible (petty cash custodian), count weekly, reconcile monthly. "
                   "Keep all slips in an envelope with a summary sheet. "
                   "Without receipts, petty cash 'disappears' and you can't claim the expense."
    },
    {
        "keywords": ["JOURNAL ENTRY", "JOURNAL", "JOERNAAL", "CORRECTION", "ADJUSTMENT"],
        "context": "Journal entries — when to use: corrections, adjustments, non-cash transactions, "
                   "depreciation, provisions, accruals, prepayments, closing entries. "
                   "Every journal must have: date, description/narration, reference, "
                   "equal debits and credits. "
                   "Common adjusting journals: "
                   "Depreciation: Debit Depreciation Expense, Credit Accumulated Depreciation. "
                   "Bad debt write-off: Debit Bad Debts, Credit Debtors. "
                   "Accrued expense: Debit Expense, Credit Accrued Liabilities. "
                   "Always include a clear description — future you (or your accountant) will thank you."
    },
    {
        "keywords": ["TRIAL BALANCE", "TB", "PROEFBALANS", "BALANCE CHECK"],
        "context": "Trial Balance: a list of ALL accounts with their debit or credit balances. "
                   "Total debits MUST equal total credits — if not, there's an error. "
                   "TB doesn't prove books are correct — just that they balance. "
                   "Common TB issues: suspense account with balance (unresolved items), "
                   "negative balances where they shouldn't be (e.g. negative bank = overdraft, that's ok; "
                   "negative expense = wrong booking), unusual balances (electricity R500k for a small shop?). "
                   "Review TB monthly — don't wait for year end. ClickAI's TB analysis catches these automatically."
    },
    {
        "keywords": ["PROFIT LOSS", "INCOME STATEMENT", "P&L", "INKOMSTESTAAT", "WINS VERLIES"],
        "context": "Income Statement (Profit & Loss): shows performance over a PERIOD (month/year). "
                   "Structure: Revenue - Cost of Sales = Gross Profit. "
                   "Gross Profit - Operating Expenses = Operating Profit. "
                   "Operating Profit - Finance Costs = Net Profit Before Tax. "
                   "Key ratios: Gross Margin % = Gross Profit / Revenue × 100. "
                   "Net Margin % = Net Profit / Revenue × 100. "
                   "Compare month-on-month and year-on-year. Sudden changes need investigation. "
                   "Tip: if gross margin drops, it's a pricing or cost of sales problem. "
                   "If net margin drops but gross is ok, it's an overhead problem."
    },
    {
        "keywords": ["BALANCE SHEET", "STATEMENT OF POSITION", "BALANSSTAAT"],
        "context": "Balance Sheet: shows financial position at a POINT IN TIME. "
                   "Assets = Liabilities + Equity (must always balance). "
                   "Current assets: bank, debtors, stock, petty cash (convertible within 12 months). "
                   "Non-current assets: equipment, vehicles, property (long-term). "
                   "Current liabilities: creditors, SARS owing, overdraft (due within 12 months). "
                   "Non-current liabilities: long-term loans, vehicle finance. "
                   "Equity: capital + retained earnings - drawings. "
                   "Key check: current ratio = current assets / current liabilities. Should be > 1.5 for comfort."
    },
    {
        "keywords": ["CASH FLOW", "CASHFLOW", "KONTANTVLOEI", "CASH MANAGEMENT"],
        "context": "Cash flow management — profit ≠ cash! You can be profitable and still run out of cash. "
                   "Cash flow killers: debtors paying late, large stock purchases before sales, "
                   "loan repayments, tax payments (especially provisional tax), "
                   "seasonal dips, owner taking too much. "
                   "Cash flow helpers: get deposits upfront, offer early payment discounts, "
                   "negotiate longer supplier terms, reduce stock holding, invoice immediately. "
                   "Rule of thumb: keep 2-3 months operating expenses as cash reserve. "
                   "Cash flow forecast: project next 13 weeks — identify gaps before they happen."
    },

    # ═══ SPECIFIC SCENARIOS ═══
    {
        "keywords": ["REFUND", "RETURN", "CREDIT NOTE", "TERUGBETALING", "KREDIET NOTA"],
        "context": "Refunds and credit notes: "
                   "Customer return (you refund): Debit Sales Returns, Credit Bank/Debtors. "
                   "If stock returned to shelf: Debit Stock, Credit Cost of Sales. "
                   "Supplier credit note (they refund you): Debit Bank/Creditors, Credit Purchases. "
                   "VAT: credit note must reference original invoice. Output VAT reduces on customer refund, "
                   "Input VAT reduces on supplier credit. "
                   "Always issue a proper credit note — don't just reverse without documentation."
    },
    {
        "keywords": ["FOREIGN CURRENCY", "USD", "EUR", "EXCHANGE RATE", "BUITELANDSE VALUTA"],
        "context": "Foreign currency transactions: use the SARS exchange rate on the date of transaction. "
                   "If you receive a USD invoice: convert to ZAR at spot rate, book as expense. "
                   "When you pay (different date, different rate): the difference is forex gain/loss. "
                   "Forex gain: Credit Forex Gain (income). Forex loss: Debit Forex Loss (expense). "
                   "SARS publishes monthly average rates — acceptable for most transactions. "
                   "Tip: for regular foreign payments, consider a forex contract to fix the rate."
    },
    {
        "keywords": ["INSURANCE CLAIM", "CLAIM RECEIVED", "DAMAGE", "THEFT", "VERSEKERING EIS"],
        "context": "Insurance claims: "
                   "Asset damaged/stolen: Debit Accumulated Depreciation (remove) + Debit Loss on Disposal, "
                   "Credit Asset (remove from books). "
                   "Insurance payout received: Debit Bank, Credit Insurance Claim Recovery (income). "
                   "If payout > book value: it's a profit. If less: additional loss. "
                   "Excess/deductible paid: Debit Insurance Expense, Credit Bank. "
                   "Keep all documentation: police report (theft), photos (damage), claim forms, adjuster reports."
    },
    {
        "keywords": ["LEASE", "RENT TO OWN", "INSTALLMENT SALE", "HUURKOOP", "OPERATING LEASE"],
        "context": "Lease accounting (simplified for small business): "
                   "Operating lease (rent — you return it): Debit Rent Expense, Credit Bank. Monthly, simple. "
                   "Finance lease / installment sale (you own it at end): treat as asset purchase. "
                   "Debit Asset, Credit Finance Lease Liability. Monthly: split between capital and interest "
                   "(same as loan accounting). "
                   "Vehicle finance (balloon payment): asset on books, depreciate over useful life "
                   "(not over finance period). Balloon = remaining liability at end. "
                   "Tip: read the contract — 'rental' agreements are sometimes actually finance leases for tax."
    },
    {
        "keywords": ["GOODWILL", "BUY BUSINESS", "KLANDISIEWAARDE", "BUSINESS PURCHASE"],
        "context": "Buying a business: purchase price allocated to identifiable assets first "
                   "(stock, equipment, debtors, property). Remainder = goodwill. "
                   "Goodwill is a non-depreciable asset for accounting but SARS allows no deduction. "
                   "Stock taken over: value at cost (verify physically). "
                   "Debtors taken over: assess collectability — don't pay for bad debts. "
                   "Get a proper due diligence done — check for hidden liabilities (SARS, COIDA, staff claims)."
    },
]


def get_relevant_bookkeeping_knowledge(query: str, max_chunks: int = 2) -> list:
    """Find relevant bookkeeping knowledge chunks for a user query."""
    if not query:
        return []
    
    query_upper = query.upper()
    scored = []
    
    for chunk in BOOKKEEPING_CHUNKS:
        score = 0
        for keyword in chunk["keywords"]:
            if keyword.upper() in query_upper:
                score += len(keyword)
        if score > 0:
            scored.append((score, chunk))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:max_chunks]]


def format_bookkeeping_knowledge(chunks: list) -> str:
    """Format matched chunks for Zane's prompt."""
    if not chunks:
        return ""
    
    lines = ["\n\n📚 BOOKKEEPING REFERENCE:"]
    for chunk in chunks:
        lines.append(chunk["context"])
    
    return "\n".join(lines)
