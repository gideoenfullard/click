"""
ClickAI Tax Strategy Knowledge Base — Zane's SA Tax Planning Reference
Covers: Tax planning, deductions, provisional tax, entity structures, capital gains, wear & tear
"""

TAX_STRATEGY_CHUNKS = [
    {
        "keywords": ["tax", "belasting", "deduction", "aftrekking", "save tax", "bespaar", "claim", "write off", "afskryf", "allowance"],
        "title": "Common Tax Deductions for SA SMEs",
        "content": """Deductions every SA business should claim:

Operating Expenses (Section 11(a)): ALL expenses incurred in the production of income — rent, salaries, electricity, phone, internet, stationery, cleaning, security, insurance premiums, accounting fees, bank charges, advertising.

Home Office (Section 11(a) + 23(b)): If you have a dedicated room used EXCLUSIVELY for business — claim proportional rent/bond interest, electricity, rates, insurance. Calculate: room area / total house area x expense. SARS requires: separate room, regular and exclusive use, main income earned from home OR employer doesn't provide office.

Vehicle Expenses: Two methods — Actual costs (fuel, maintenance, insurance, finance — keep a logbook) OR Prescribed rate per km (SARS publishes annually — ~R4.69/km for 2025). Logbook is ESSENTIAL — record every business trip: date, destination, purpose, km.

Bad Debts (Section 11(i)): If a customer won't pay and you've exhausted reasonable steps to collect — write it off. Need evidence: demand letters, tracing attempts, age of debt. Write off reduces your taxable income.

Wear & Tear (Section 11(e)): Depreciation on business assets. Common rates: Computers 33.3% (3 years), Office furniture 16.67% (6 years), Vehicles 25% (4 years), Machinery 20% (5 years), Buildings 5% (20 years). Section 12C: Manufacturing equipment can be 40/20/20/20 or 50/30/20.

Staff Training (Section 12H): Learnership allowance — R40,000-R80,000 per learner per year. Plus Skills Development Levy can be claimed back (up to 70%) if you submit workplace skills plan.

Donations (Section 18A): Donations to approved PBOs — deduct up to 10% of taxable income. MUST have Section 18A receipt from the PBO.

Small Business Corporation (Section 12E): If qualifying (natural persons as shareholders, turnover under R20m), reduced tax rates: 0% on first R95,750, then 7% up to R365,000, then 21% up to R550,000, then 27% above."""
    },
    {
        "keywords": ["provisional", "voorlopig", "itr", "it14", "irp6", "tax return", "filing", "submit", "efiling"],
        "title": "Provisional Tax & Filing Deadlines",
        "content": """SA Tax Filing Calendar:

Provisional Tax (IRP6): Required if taxable income above R30,000 and not fully taxed via PAYE.
- First period: Due end of August (6 months into tax year)
- Second period: Due end of February (year end)
- Third (voluntary top-up): Due end of September following year end
Penalty for late/underpayment: 10% of difference between paid and actual.

Company Tax (IT14): Due 12 months after financial year end. E.g. Feb year-end → file by 28 Feb next year. But SARS often opens filing early — file as soon as possible.

VAT Returns (VAT201): Monthly (if turnover above R30m), bi-monthly (most businesses), or every 4-6 months (for small businesses). Due 25th of month following VAT period.

EMP201 (PAYE/UIF/SDL): Monthly. Due 7th of month following payment. Late penalty: 10% of amount due.

EMP501 (Annual Employer Reconciliation): Twice yearly — interim (October) and annual (May/June). Must reconcile all IRP5/IT3(a) certificates.

Annual Returns (CIPC): Not tax but often confused. Due within 30 days of company anniversary. ~R125.

Key Tip: ALWAYS pay provisional tax on time, even if estimated. Under-estimation penalties are 10% + interest. Better to overpay and get a refund than underpay and get penalties."""
    },
    {
        "keywords": ["pty", "cc", "sole", "entity", "structure", "company", "trust", "maatskappy", "incorporation", "liability"],
        "title": "Business Entity Structures — Tax Implications",
        "content": """Choosing the right structure:

Sole Proprietor: Taxed at personal rates (max 45%). No separation between personal and business. Unlimited personal liability. Simplest admin. Good for: very small, low-risk businesses, freelancers.

(Pty) Ltd: Flat 27% corporate tax (from 2023). Separate legal entity — limited liability. Can retain profits in company (tax deferral). Dividends taxed at 20% when paid out. Good for: any business with growth plans, multiple owners, or liability concerns.

Close Corporation (CC): Same 27% tax rate. Cannot register NEW CCs since 2011. Existing ones: simpler admin than Pty, similar tax treatment. If you have one, keep it — no need to convert unless you want to.

Trust: 45% flat rate on retained income (highest!). NOT recommended for trading businesses. Good for: asset protection, estate planning, holding property. Income distributed to beneficiaries taxed at their rates — this is the strategy.

Comparison Example (R1m profit):
- Sole Prop: ~R330,000 tax (33% effective)
- (Pty) Ltd: R270,000 corporate tax. If you take R730,000 as salary → additional PAYE. Or leave in company and pay 27% only.
- Trust: R450,000 if retained (45%!). But if distributed to 3 beneficiaries in low brackets → much less.

Practical Advice: Most SA SMEs should be (Pty) Ltd. The liability protection alone is worth it. Pay yourself a reasonable salary (reduces company profit, subject to PAYE) and leave excess in the company for growth. Only draw dividends when needed (20% DWT)."""
    },
    {
        "keywords": ["capital gains", "cgt", "asset", "sell", "property", "verkoop", "eiendom", "profit on sale", "bate"],
        "title": "Capital Gains Tax (CGT)",
        "content": """CGT applies when you sell assets for more than you paid:

How It Works: Capital gain = proceeds - base cost (purchase price + improvements + transfer costs). Only a portion is included in taxable income.

Inclusion Rates (2025): Individuals: 40% of gain included. Companies: 80%. Trusts: 80%.

Effective Rates: Individual at max bracket: 40% x 45% = 18% effective CGT. Company: 80% x 27% = 21.6%. Trust: 80% x 45% = 36%.

Annual Exclusion: Individuals get R40,000 per year excluded. On death: R300,000 exclusion.

Primary Residence Exclusion: First R2 million of gain on your primary residence is exempt. Above R2m: normal CGT rates. Must have lived there as primary residence.

Small Business Exclusion (para 57): If over 55 or retiring — up to R1.8 million lifetime exclusion on sale of active small business assets. Market value under R10m. Must have been actively involved for 5+ years.

Base Cost: Keep ALL records — purchase contracts, improvement receipts, agent commissions, transfer duty, legal fees. These all increase your base cost (reduce gain). SARS accepts valuation as at 1 October 2001 for assets held before CGT introduction.

Timing Strategy: If you have a capital gain this year and a capital loss next year — consider timing. Losses carry forward indefinitely but can only offset capital gains (not income). Can sell losing investments in same year to offset."""
    },
    {
        "keywords": ["vat", "register", "vendor", "input", "output", "voluntary", "threshold", "zero rate", "exempt"],
        "title": "VAT Strategy & Registration",
        "content": """VAT Registration and Strategy:

Compulsory: Turnover exceeds R1 million in 12 months → MUST register within 21 days.
Voluntary: Turnover above R50,000 → CAN register. Below R50,000 → cannot.

Why Register Voluntarily (even under R1m):
- Claim VAT back on purchases (14.29% saving on expenses)
- Look more professional to bigger clients (many large companies prefer VAT vendors)
- Recover VAT on startup costs and equipment purchases

Why NOT Register:
- Admin burden (bi-monthly returns)
- Cash flow timing (collect VAT from clients, hold it, pay SARS)
- If clients are consumers (not businesses) — you're effectively 15% more expensive

VAT Calculation Methods:
- Invoice basis (most businesses): Account for VAT when invoice issued, not when paid
- Payments basis (turnover under R2.5m): Account for VAT when actually paid/received — MUCH better for cash flow

Zero-Rated (0% VAT — still claim inputs): Exports, basic foods (brown bread, milk, eggs, rice, fruit, veg, pilchards, maize meal), petrol/diesel (levy instead), international transport.

Exempt (no VAT charged, CANNOT claim inputs): Financial services, residential rental, educational services, public transport.

Input Tax Denied: Entertainment, club subscriptions, motor cars (unless dealer). CAN claim on: double cabs (less than R700k), bakkies, delivery vehicles, commercial vehicles.

Key Tip: ALWAYS keep valid tax invoices (supplier name, VAT number, date, description, VAT amount shown separately). Without valid invoice → no input claim. For purchases under R5,000: abbreviated tax invoice is fine."""
    },
    {
        "keywords": ["depreciation", "wear and tear", "asset", "write off", "section 11", "section 12", "afskryf", "waardevermindering", "capex"],
        "title": "Wear & Tear / Depreciation Allowances",
        "content": """Claiming depreciation on business assets:

Section 11(e) — General Wear & Tear: Claim annual depreciation on assets used in business. SARS publishes interpretation note with rates. Must own the asset (not lease). Asset must be used in production of income.

Common SARS-Approved Rates:
- Computers, laptops, tablets: 33.3% (3 years)
- Printers, peripherals: 33.3% (3 years)
- Computer software: 50% (2 years)
- Office furniture (desks, chairs): 16.67% (6 years)
- Motor vehicles: 25% (4 years)
- Delivery vehicles, bakkies: 25% (4 years)
- Forklifts, warehouse equipment: 20% (5 years)
- Manufacturing machinery: 20% (5 years)
- Security equipment (cameras, alarms): 20% (5 years)
- Air conditioning: 16.67% (6 years)
- Signage: 16.67% (6 years)
- Tools (power tools): 33.3% (3 years)
- Shelving, racking: 10% (10 years)
- Buildings: 5% (20 years) — manufacturing only
- POS equipment, cash registers: 33.3% (3 years)
- Cellphones: 33.3% (3 years)

Section 12C — Manufacturing Assets: Accelerated depreciation. New/unused assets used in manufacturing: 40% year 1, 20% year 2, 20% year 3, 20% year 4. Much better than normal 5-year write-off.

Section 12E — Small Business Corporations: Assets used in manufacturing can be written off 100% in year 1! Non-manufacturing assets: same as normal but at slightly accelerated rates.

Important: Keep purchase invoices, delivery notes, and asset register updated. SARS can disallow claims without proof. Assets below R7,000 can be written off immediately (de minimis rule — check current threshold)."""
    },
    {
        "keywords": ["dividend", "dividende", "salary", "bonus", "director", "loan", "shareholder", "take money", "pay yourself", "onttrek"],
        "title": "How to Pay Yourself — Tax Efficient Extraction",
        "content": """Getting money out of your company tax-efficiently:

Option 1 — Salary/PAYE: Company deducts salary as expense (reduces 27% corp tax). You pay PAYE at personal rates (18-45%). Best for: R0-R800k/year — the lower tax brackets save more than 27%.

Option 2 — Dividends: Company pays 27% corp tax PLUS 20% dividends tax on distribution. Effective rate: 27% + (73% x 20%) = 41.6%. But NO PAYE, no UIF, no SDL on dividends. Best for: amounts above R800k/year where personal PAYE would exceed 41.6%.

Option 3 — Director's Loan: Take money as loan from company. NO tax on loans. BUT: SARS deems a fringe benefit if interest-free or below-market rate. Must charge at least official rate (repo + 1%). Must actually repay or SARS treats as salary. Useful for: temporary cash needs, bridge financing.

Option 4 — Travel Allowance: Company pays travel allowance. Claim actual business kms against it. Up to R102,133/year (2025) for fixed allowance — the first R102,133 is not taxed upfront but reconciled on assessment. Keep logbook! Can be tax efficient if high business km.

Optimal Strategy (example: R1.5m company profit):
- Pay yourself R750k salary → ~R175k PAYE (effective ~23%)
- Leave R750k in company → R202.5k corp tax (27%)
- Total tax: ~R377k on R1.5m = 25% effective
- vs Taking all as salary: ~R550k (37% effective)
- Saving: ~R173k by using the mix

Golden Rule: Don't leave too much in the company just for tax — if you need it to live, take it. Tax saving means nothing if you're borrowing at 20% interest to fund personal expenses. The goal is optimisation, not avoidance."""
    }
]


def get_relevant_tax_strategy(user_message: str, max_chunks: int = 2) -> list:
    """Find tax strategy chunks relevant to the user's question"""
    if not user_message:
        return []
    
    msg_lower = user_message.lower()
    scored = []
    
    for chunk in TAX_STRATEGY_CHUNKS:
        score = 0
        for kw in chunk["keywords"]:
            if kw in msg_lower:
                score += 3 if len(kw) > 5 else 2
        title_words = chunk["title"].lower().split()
        for tw in title_words:
            if tw in msg_lower and len(tw) > 3:
                score += 1
        if score > 0:
            scored.append((score, chunk))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:max_chunks]]


def format_tax_strategy(chunks: list) -> str:
    """Format tax strategy chunks for injection into Zane's prompt"""
    if not chunks:
        return ""
    text = "\n\n=== TAX STRATEGY KNOWLEDGE (SA Tax Planning) ===\n"
    for c in chunks:
        text += f"\n### {c['title']}\n{c['content']}\n"
    return text
