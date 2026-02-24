"""
ClickAI SARS Knowledge — South African tax intelligence for Zane
═══════════════════════════════════════════════════════════════════
Gives Zane accurate, up-to-date SA tax knowledge so he can answer
"can I deduct this?" and "what are my tax obligations?" confidently.

Each chunk has keywords for RAG matching and concise, accurate content.
Zane gets max 2 chunks per query — keep them focused.

Last updated: Feb 2025 (2024/2025 tax year rates)
"""

SARS_CHUNKS = [
    # ═══ VAT BASICS ═══
    {
        "keywords": ["VAT", "VALUE ADDED TAX", "BTW", "15%", "REGISTRATION", "VAT NUMBER"],
        "context": "SA VAT rate is 15%. Registration is COMPULSORY if turnover exceeds R1 million in 12 months. "
                   "Voluntary registration allowed if turnover exceeds R50,000. VAT returns filed every 2 months "
                   "(Cat A), monthly (Cat B — turnover > R30m), or 6-monthly (Cat D — farming). "
                   "VAT201 return due by 25th of month following VAT period. Late submission = 10% penalty. "
                   "Keep ALL tax invoices for 5 years minimum."
    },
    {
        "keywords": ["VAT CLAIM", "INPUT VAT", "VAT DEDUCTION", "CLAIM VAT", "VAT BACK", "VAT REFUND"],
        "context": "You can ONLY claim input VAT if you have a valid tax invoice with the supplier's VAT number. "
                   "Invoice must show: supplier name, VAT number, date, description, VAT amount separately. "
                   "For purchases under R5,000 — abbreviated tax invoice is fine (less detail required). "
                   "Over R5,000 — full tax invoice required with buyer's name and VAT number. "
                   "NO input VAT claim on: entertainment, private use portion, membership fees, "
                   "motor vehicle purchase (limited to R&D vehicles), donations."
    },
    {
        "keywords": ["VAT FUEL", "PETROL VAT", "DIESEL VAT", "FUEL CLAIM", "FUEL DEDUCT", "FUEL TAX",
                     "BRANDSTOF", "PETROL", "DIESEL", "FUEL"],
        "context": "FUEL VAT RULES (important!): You CANNOT claim VAT on fuel used for private/own purposes. "
                   "Business vehicle fuel — can claim IF you can prove business use (logbook required). "
                   "Mixed use vehicle — must apportion based on business vs private km. "
                   "SARS requires a logbook showing: date, destination, purpose, km driven. "
                   "Diesel refund scheme available for farming, mining, and certain manufacturing — separate application."
    },
    {
        "keywords": ["VAT ENTERTAINMENT", "ENTERTAINMENT TAX", "ENTERTAINMENT DEDUCTION", "CLIENT ENTERTAINMENT"],
        "context": "Entertainment expenses: NO VAT input claim allowed — zero. This includes client meals, "
                   "staff parties, team lunches, gifts to clients. The full amount (VAT inclusive) is the expense. "
                   "However, entertainment IS deductible for income tax purposes (just not for VAT). "
                   "Exception: meals provided to employees as part of duties (e.g. long-haul drivers) — VAT claimable."
    },
    {
        "keywords": ["VAT EXEMPT", "ZERO RATED", "NO VAT", "VAT FREE"],
        "context": "Zero-rated (0% VAT, but still in VAT system): exports, basic foodstuffs (brown bread, milk, "
                   "eggs, rice, vegetables, fruit, cooking oil, maize meal, dried beans, tinned fish, lentils), "
                   "petrol/diesel (has fuel levy instead), municipal property rates, international transport. "
                   "EXEMPT (outside VAT system entirely): financial services, residential rental, public transport, "
                   "educational services, childcare. Exempt suppliers cannot claim input VAT."
    },
    {
        "keywords": ["VAT INVOICE", "TAX INVOICE", "INVOICE REQUIREMENTS", "VALID INVOICE"],
        "context": "A valid tax invoice MUST contain: the words 'Tax Invoice', supplier name and VAT number, "
                   "buyer name (if over R5,000), date, serial number, description of goods/services, "
                   "quantity, price excluding VAT, VAT rate, VAT amount, total including VAT. "
                   "Without a valid tax invoice, you CANNOT claim input VAT — even if you paid VAT. "
                   "Cash slips from shops are valid abbreviated tax invoices if under R5,000."
    },

    # ═══ INCOME TAX — COMPANIES & CC ═══
    {
        "keywords": ["COMPANY TAX", "CORPORATE TAX", "CC TAX", "BUSINESS TAX RATE", "MAATSKAPPY BELASTING"],
        "context": "Company/CC tax rate: 27% of taxable income (reduced from 28% from 2023). "
                   "Financial year end chosen by the company. Provisional tax payments required twice per year "
                   "(6 months after year end, and at year end). Third optional 'top-up' payment within 6 months "
                   "after year end to avoid interest. ITR14 return due 12 months after financial year end. "
                   "SBC (Small Business Corporation) rate: 0% on first R95,750, then 7% up to R365,000, "
                   "then 21% up to R550,000, then 27% above — IF qualifying (turnover < R20m, natural persons as shareholders)."
    },
    {
        "keywords": ["SOLE PROPRIETOR", "SOLE TRADER", "EENMANBESIGHEID", "PERSONAL TAX"],
        "context": "Sole proprietors pay personal income tax on business profits (not company tax). "
                   "2024/2025 rates: 0% up to R95,750, then 18% to R237,100, then 26% to R370,500, "
                   "then 31% to R512,800, then 36% to R673,000, then 39% to R857,900, then 41% to R1,817,000, "
                   "then 45% above R1,817,000. Tax threshold: under 65 = R95,750, 65-75 = R148,217, 75+ = R165,689. "
                   "Must register for provisional tax if income not from salary."
    },

    # ═══ PROVISIONAL TAX ═══
    {
        "keywords": ["PROVISIONAL TAX", "IRP6", "VOORLOPIGE BELASTING", "PROVISIONAL PAYMENT"],
        "context": "Provisional tax = pay-as-you-earn for self-employed/companies. Two compulsory payments: "
                   "1st payment: within 6 months of year start (based on estimate). "
                   "2nd payment: at year end (based on actual or better estimate). "
                   "Underestimation penalty: if you estimate less than 80% of actual taxable income on 2nd payment, "
                   "SARS charges 20% penalty on the shortfall. Always estimate conservatively (higher). "
                   "IRP6 form used for submission. Late payment = interest at prescribed rate."
    },

    # ═══ PAYE / UIF / SDL ═══
    {
        "keywords": ["PAYE", "PAY AS YOU EARN", "EMPLOYEE TAX", "SALARY TAX", "LOONBELASTING"],
        "context": "PAYE must be deducted from employee salaries and paid to SARS by the 7th of the following month. "
                   "Use SARS tax tables to calculate deduction based on annual equivalent. "
                   "EMP201 return due monthly by 7th. EMP501 reconciliation due twice per year "
                   "(interim in October, final in May/June). IRP5 certificates issued to employees. "
                   "Late payment penalty: 10% of amount due. Interest charged on outstanding amounts."
    },
    {
        "keywords": ["UIF", "UNEMPLOYMENT INSURANCE", "WVF"],
        "context": "UIF contribution: 1% from employee + 1% from employer = 2% total. "
                   "Maximum earnings ceiling: R17,712 per month (2024/2025). "
                   "Maximum contribution: R177.12 per employee per month (employee + employer combined R354.24). "
                   "Domestic workers included. Paid monthly with PAYE via EMP201. "
                   "Employers with 50+ employees must use uFiling."
    },
    {
        "keywords": ["SDL", "SKILLS DEVELOPMENT LEVY", "VAARDIGHEIDSHEFFING"],
        "context": "SDL: 1% of total payroll. Only payable if annual payroll exceeds R500,000. "
                   "Paid monthly with PAYE/UIF via EMP201. "
                   "Can claim back via SETA (Sector Education and Training Authority) for approved training. "
                   "Register with relevant SETA for your industry to claim training grants."
    },
    {
        "keywords": ["COIDA", "COMPENSATION FUND", "WORKMEN COMP", "WCA"],
        "context": "COIDA (Compensation for Occupational Injuries): ALL employers must register. "
                   "Annual assessment based on industry risk category and payroll amount. "
                   "Rate varies by industry: office work ~0.11%, retail ~0.53%, construction ~3.89%. "
                   "Return of Earnings (ROE) due by 31 March each year. "
                   "Covers workplace injuries and occupational diseases. Non-compliance = criminal offence."
    },

    # ═══ DEDUCTIONS ═══
    {
        "keywords": ["TAX DEDUCTION", "DEDUCT", "AFTREKKING", "WRITE OFF", "CLAIM EXPENSE", "ALLOWABLE",
                     "AFTREK", "CAN I CLAIM", "KAN EK AFTREK", "IS IT DEDUCTIBLE"],
        "context": "General rule: expense must be incurred 'in the production of income' and not capital in nature. "
                   "FULLY deductible: rent, salaries, stock purchases, accounting fees, advertising, insurance premiums, "
                   "bank charges, repairs & maintenance, stationery, telephone, electricity, security, cleaning. "
                   "PARTIALLY deductible: vehicle expenses (business portion only — need logbook), "
                   "home office (dedicated room only, based on floor area ratio). "
                   "NOT deductible: fines/penalties, donations (unless to approved PBO s18A), "
                   "private expenses, capital items (but depreciation is deductible)."
    },
    {
        "keywords": ["DEPRECIATION", "WEAR AND TEAR", "CAPITAL ALLOWANCE", "ASSET WRITE OFF", "WAARDEVERMINDERING"],
        "context": "Assets used in business can be depreciated over their useful life (wear and tear allowance). "
                   "SARS Interpretation Note 47 rates: computers/laptops 3 years (33.3%), "
                   "office furniture 6 years (16.67%), vehicles 5 years (20%), "
                   "machinery/equipment 4-10 years depending on type, buildings 5% (20 years). "
                   "Small business: assets under R7,000 can be written off immediately (100% year 1). "
                   "Section 12E: SBC can write off manufacturing assets 100% in year 1, others 50/30/20 over 3 years."
    },
    {
        "keywords": ["HOME OFFICE", "WORK FROM HOME", "TUISKANTOOR"],
        "context": "Home office deduction: STRICT requirements. Room must be used REGULARLY and EXCLUSIVELY for business. "
                   "Cannot be a spare room occasionally used — must be dedicated office. "
                   "Claim proportional to floor area: e.g. 15m² office / 150m² house = 10% of rent, "
                   "electricity, rates, insurance, repairs. If you OWN the home, can claim wear and tear "
                   "on the office portion. Salaried employees: very limited — must earn commission/variable income "
                   "and employer must not provide an office."
    },
    {
        "keywords": ["VEHICLE EXPENSE", "CAR EXPENSE", "TRAVEL ALLOWANCE", "LOGBOOK", "MOTOR AFTREKKING"],
        "context": "Vehicle deductions require a LOGBOOK — no logbook = no claim. "
                   "Log must show: date, destination, purpose of trip, opening & closing km. "
                   "Claim options: actual costs × business % (fuel, insurance, maintenance, finance), "
                   "OR SARS fixed cost table rate (based on vehicle value and km driven). "
                   "Cannot claim for travel between home and work (commuting). "
                   "Company car (fringe benefit): 3.25% of determined value per month added to taxable income."
    },
    {
        "keywords": ["BAD DEBT", "WRITE OFF DEBT", "SLEGTE SKULD", "UNCOLLECTABLE"],
        "context": "Bad debts can be written off as a deduction IF: the debt was previously included in income, "
                   "the debt has become irrecoverable (can prove collection attempts failed), "
                   "and you have written it off in your books. Keep proof of collection attempts "
                   "(demand letters, calls, handed to attorneys). Provision for doubtful debts: "
                   "25% of debts 120+ days overdue (allowance under s11(j)), must be specific not general."
    },

    # ═══ PENALTIES & INTEREST ═══
    {
        "keywords": ["PENALTY", "FINE", "SARS PENALTY", "LATE FILING", "BOETE", "ADMIN PENALTY"],
        "context": "SARS admin penalties for late filing (not late payment): "
                   "Based on assessed taxable income — R250/month (< R250k) up to R16,000/month (> R50m). "
                   "Fixed amount, charged monthly until outstanding return is filed, max 35 months. "
                   "Late PAYMENT penalty: 10% of unpaid tax. Interest: prescribed rate (currently ~11.75% p.a.). "
                   "Underestimation of provisional tax: 20% penalty if 2nd estimate < 80% of actual. "
                   "IMPORTANT: Penalties and fines are NOT tax deductible — you cannot claim them back."
    },

    # ═══ TAX DATES & DEADLINES ═══
    {
        "keywords": ["TAX DEADLINE", "DUE DATE", "FILING DATE", "WHEN TO PAY", "SARS DATE", "SUBMISSION"],
        "context": "Key SARS dates: "
                   "Monthly by 7th: EMP201 (PAYE/UIF/SDL), VAT201 (if monthly filer). "
                   "Every 2 months by 25th: VAT201 (Cat A — most businesses). "
                   "Bi-annually: IRP6 provisional tax (6 months after year start + at year end). "
                   "Annually: IT14/ITR14 company return (12 months after year end), "
                   "EMP501 reconciliation (October interim + May/June final), "
                   "COIDA Return of Earnings (31 March). "
                   "Personal tax season: usually July-November for eFiling, October-January for non-provisional. "
                   "TIP: Set calendar reminders — SARS penalties are automatic and expensive."
    },

    # ═══ TURNOVER TAX ═══
    {
        "keywords": ["TURNOVER TAX", "MICRO BUSINESS", "OMSETBELASTING", "SMALL BUSINESS TAX"],
        "context": "Turnover tax is a SIMPLIFIED tax option for micro businesses with turnover under R1 million. "
                   "Replaces income tax, VAT, provisional tax, capital gains, and dividends tax. "
                   "Rates (2024/2025): 0% up to R335,000, 1% on R335k-R500k, 2% on R500k-R750k, 3% on R750k-R1m. "
                   "Advantages: simple, one tax covers all, no VAT admin. "
                   "Disadvantages: cannot claim input VAT, no loss carry-forward, limited to R1m, "
                   "cannot have professional services income > R20%. "
                   "Good for: small retail, trades, services. Bad for: businesses with big input VAT claims."
    },

    # ═══ DIVIDENDS TAX ═══
    {
        "keywords": ["DIVIDEND", "DIVIDENDS TAX", "SHAREHOLDER", "DWT"],
        "context": "Dividends tax: 20% withheld by the company when paying dividends to shareholders. "
                   "Applies to companies (Pty Ltd), not sole proprietors or partnerships. "
                   "The COMPANY withholds and pays to SARS (not the shareholder). "
                   "Owner drawings from a CC/sole proprietor are NOT dividends — they're drawings against capital. "
                   "Important distinction: salary vs dividends planning — dividends avoid PAYE/UIF but have 20% DWT."
    },

    # ═══ RECORD KEEPING ═══
    {
        "keywords": ["RECORD KEEPING", "DOCUMENTS", "HOW LONG KEEP", "RETENTION", "BEWAAR"],
        "context": "SARS requires you to keep business records for 5 YEARS from date of submission of the return. "
                   "Records include: invoices (issued AND received), bank statements, receipts, "
                   "contracts, payroll records, asset registers, VAT invoices, logbooks, stock records. "
                   "Electronic records are acceptable IF they're: complete, accurate, accessible, "
                   "backed up, and can be printed. ClickAI stores everything in the cloud — this counts. "
                   "SARS can audit up to 5 years back (longer if fraud suspected)."
    },

    # ═══ COMMON MISTAKES ═══
    {
        "keywords": ["TAX MISTAKE", "COMMON ERROR", "TAX TIP", "AVOID PENALTY", "BELASTING FOUT"],
        "context": "Most common SA small business tax mistakes: "
                   "1. Not registering for VAT when over R1m threshold (automatic penalty). "
                   "2. Claiming VAT on entertainment (not allowed). "
                   "3. No logbook for vehicle claims (claim rejected entirely). "
                   "4. Mixing personal and business expenses (red flag for audit). "
                   "5. Not keeping tax invoices (can't claim input VAT without them). "
                   "6. Underestimating provisional tax (20% penalty). "
                   "7. Late EMP201 submissions (10% penalty + interest every month). "
                   "8. Not paying UIF for domestic workers (it's compulsory). "
                   "9. Claiming home office without exclusive use (SARS rejects it). "
                   "10. Not declaring all income including cash sales (evasion = criminal)."
    },

    # ═══ SARS eFILING ═══
    {
        "keywords": ["EFILING", "SARS ONLINE", "SARS LOGIN", "FILING"],
        "context": "SARS eFiling (www.sarsefiling.co.za) is the online platform for all submissions. "
                   "Register once, submit everything online: VAT201, EMP201, EMP501, IT14, IRP6. "
                   "Tax Practitioners must register separately and get client mandates via eFiling. "
                   "eFiling also used for: tax clearance certificates, dispute resolution, "
                   "payment arrangements, and account queries. "
                   "Mobile app available for basic functions. "
                   "TIP: Save eFiling login details securely — password reset requires visiting a SARS branch."
    },

    # ═══ DONATIONS ═══
    {
        "keywords": ["DONATION", "CHARITY", "PBO", "SECTION 18A", "SKENKING"],
        "context": "Donations to SARS-approved PBOs (Public Benefit Organisations) with s18A status "
                   "are deductible up to 10% of taxable income. Must have s18A receipt from the PBO. "
                   "Donations to non-approved organisations = NOT deductible. "
                   "Donations tax: separate from income tax — 20% on donations exceeding R100,000 per year "
                   "(to individuals/trusts, not PBOs). Companies: donations between group companies exempt."
    },

    # ═══ CAPITAL GAINS ═══
    {
        "keywords": ["CAPITAL GAIN", "CGT", "SELL ASSET", "SELL PROPERTY", "KAPITAALWINS"],
        "context": "Capital gains tax applies when selling business assets, property, or shares at a profit. "
                   "Companies: 80% of gain included in taxable income (effective rate: 21.6% at 27% corp tax). "
                   "Individuals: 40% inclusion (effective max rate: 18%). "
                   "Annual exclusion: R40,000 for individuals (R300,000 in year of death). "
                   "Base cost = original purchase price + improvements + transfer costs. "
                   "Primary residence exclusion: first R2 million gain exempt (individuals only). "
                   "Small business exclusion: R1.8m on disposal of active business assets if over 55 or ill."
    },

    # ═══ IMPORT/EXPORT ═══
    {
        "keywords": ["IMPORT", "EXPORT", "CUSTOMS", "DUTY", "INVOER", "UITVOER"],
        "context": "Imports: customs duty + 15% VAT on imported goods (paid at port of entry). "
                   "The import VAT is claimable as input VAT if you're VAT registered. "
                   "Customs duty rates vary by product — check SARS tariff book. "
                   "Exports: zero-rated for VAT (0%, not exempt). Must keep proof of export "
                   "(bill of lading, customs declaration). "
                   "Foreign currency transactions: use SARS exchange rate on date of transaction."
    },
]


def get_relevant_sars_knowledge(query: str, max_chunks: int = 2) -> list:
    """Find relevant SARS knowledge chunks for a user query."""
    if not query:
        return []
    
    query_upper = query.upper()
    scored = []
    
    for chunk in SARS_CHUNKS:
        score = 0
        for keyword in chunk["keywords"]:
            if keyword.upper() in query_upper:
                # Longer keyword matches are more specific/valuable
                score += len(keyword)
        if score > 0:
            scored.append((score, chunk))
    
    # Sort by relevance score, return top matches
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:max_chunks]]


def format_sars_knowledge(chunks: list) -> str:
    """Format matched chunks for injection into Zane's prompt."""
    if not chunks:
        return ""
    
    lines = ["\n\n📋 SARS TAX REFERENCE:"]
    for chunk in chunks:
        lines.append(chunk["context"])
    
    return "\n".join(lines)
