"""
clickai_financial_advisor_knowledge.py
=======================================
RAG knowledge module: Personal + Business Financial Advisory
Covers: scenario planning, debt restructuring, asset disposal, cash flow
forecasting, owner drawings vs salary, CGT, working capital management.

Pattern: identical to all other clickai_*_knowledge.py modules.
Import in clickai.py + inject in build_zane_core_prompt().
"""

FINANCIAL_ADVISOR_CHUNKS = [

    {
        "id": "fa_001",
        "title": "Personal vs business finances — separation principle",
        "keywords": [
            "persoonlike skuld", "personal debt", "huis", "motor", "verband",
            "bond", "house", "car", "personal loan", "drawing", "loan account",
            "direkteur lening", "director loan", "eie rekening", "my geld",
            "loan to owner", "owner loan"
        ],
        "content": """
PERSONAL VS BUSINESS FINANCES — SA SME CONTEXT

Many SA SME owners blur personal and business finances. Key rules:

OWNER LOAN ACCOUNT (Director's Loan):
- Money you put INTO the business = loan to company (liability for business, asset for you)
- Money you take OUT = drawings or loan repayment
- Keep a running balance — SARS scrutinises this
- Interest must be charged at SARS official rate (currently 8.25%) if formal loan exists
- CC members can draw from members' interest; (Pty)Ltd directors take salary or dividends

WHAT BELONGS IN BUSINESS P&L vs NOT:
- House bond repayments: NOT a business expense (unless home office — only the %age)
- Personal car: only business-use portion is deductible (logbook required)
- Medical aid: CAN be structured as a fringe benefit via payroll (saves tax)
- Spouse salary/consulting fees: MUST be market-related or SARS will query it
- Life insurance: only if business is beneficiary (key-man policy)

COMMON MISPOSTINGS TO WATCH:
- "Royalties" sometimes used to mask owner drawings — restructure properly
- Consulting fees to spouse need an invoice + employment contract or consulting agreement
- If the business pays personal expenses, post to Director's Loan Account, not expenses

CORRECT STRUCTURE FOR OWNER REMUNERATION (SA):
1. Salary via payroll (PAYE deducted) — most common
2. Dividends (tax at 20% dividends tax) — efficient if business profitable
3. Loan repayment (if you put money in) — tax-free
4. Combination of above — optimise each year with your tax practitioner
"""
    },

    {
        "id": "fa_002",
        "title": "Asset disposal and CGT — selling property or vehicles",
        "keywords": [
            "verkoop perseel", "sell property", "cgt", "kapitaalwinsbelasting",
            "capital gains", "basiskoste", "base cost", "disposal", "verkoop bate",
            "sell building", "sell asset", "property sale", "verband aflos",
            "eighth schedule", "inclusion rate", "annual exclusion"
        ],
        "content": """
CGT — CAPITAL GAINS TAX ON ASSET DISPOSAL (SA)

When you sell a capital asset (property, vehicles, investments):

CALCULATION:
1. Proceeds (selling price) minus Base Cost (what you paid + improvements + selling costs)
2. = Capital Gain
3. Minus Annual Exclusion: R40,000 for individuals (R300,000 in year of death)
4. x Inclusion Rate: 40% for individuals, 80% for companies/CCs
5. = Taxable capital gain — added to your normal taxable income
6. Taxed at your marginal rate

EXAMPLE (individual, marginal rate 45%):
- Selling price: R2,000,000
- Base cost: R270,000
- Capital gain: R1,730,000
- Less annual exclusion: R40,000
- Net capital gain: R1,690,000
- x 40% inclusion = R676,000 taxable
- x 45% marginal rate = R304,200 CGT payable

IMPORTANT TIMING:
- CGT is triggered in the tax year the sale is concluded (date of agreement, not transfer)
- For a Feb year-end business: sale in March = only payable Feb next year
- This gives you ~11 months to plan and accumulate the cash

PRIMARY RESIDENCE EXCLUSION:
- First R2,000,000 of gain on primary home is excluded
- Only applies if it is genuinely your primary residence

BUSINESS PROPERTY:
- No primary residence exclusion
- BUT selling costs (agent fees, legal fees, bond cancellation) reduce the gain
- Improvements over the years increase base cost — keep all invoices

VAT ON PROPERTY:
- If seller is VAT vendor and property used in enterprise: sale is subject to VAT (15%)
- Buyer may claim the VAT back if also a vendor
- Get specialist advice — incorrect VAT treatment is common and costly
"""
    },

    {
        "id": "fa_003",
        "title": "Debt restructuring — paying off OD, bonds, vehicle finance",
        "keywords": [
            "aftbetaal skuld", "pay off debt", "overdraft", "OD", "oortrokke",
            "verband", "bond", "voertuig finansiering", "vehicle finance",
            "debt restructure", "skuld herstruktureer", "cash flow", "rente spaar",
            "interest saving", "wat eerste", "which debt first", "settle"
        ],
        "content": """
DEBT RESTRUCTURING — WHICH DEBT TO PAY FIRST (SA SME)

PRIORITY ORDER (highest interest first — "avalanche method"):
1. Overdraft / revolving credit: typically prime + 2-4% = 13-15% p.a.
2. Credit cards: 18-22% p.a.
3. Vehicle finance: typically prime + 1-3% = 12-14% p.a.
4. Home bond: typically prime - 0.5 to prime = 11-11.5% p.a.
5. SARS debt: interest + penalties — prioritise if penalties accumulating

OVERDRAFT CONSIDERATIONS:
- OD is a facility, not a fixed loan — interest only on amount used
- Paying it off saves the daily interest but loses the facility
- Keep OD facility open even after paying it off — it's your emergency buffer
- Rebuilding an OD facility takes months; paying it down takes days

VEHICLE FINANCE EARLY SETTLEMENT:
- Request a settlement figure (includes early termination fee if applicable)
- NCA (National Credit Act) limits early settlement penalties
- Compare: interest saving vs any penalties
- Balloon payment vehicles: settling early means paying the balloon now

BOND (HOME LOAN) STRATEGY:
- Once a bond is paid off, the bank will NOT automatically release the funds
- You need to formally cancel the bond (attorney costs ~R8,000-R15,000)
- OR keep it as an access bond (redraw facility) — useful as emergency capital
- Interest saving on R1.2m bond at 11.5% = R138,000/year = R11,500/month

WORKING CAPITAL WARNING:
- Never pay off all debt if it leaves you with < 2 months operating expenses in cash
- For a business with R130k/month COGS, keep minimum R260k-R400k accessible
- Better to pay R6,000/month OD interest than run out of stock-buying cash
"""
    },

    {
        "id": "fa_004",
        "title": "Rental income — tax treatment and strategy",
        "keywords": [
            "huur inkomste", "rental income", "verhuur", "huurder", "tenant",
            "huurkontrak", "lease", "verhuurder", "landlord", "rental property",
            "perseel verhuur", "R25000 huur", "huur verloor", "huur kry"
        ],
        "content": """
RENTAL INCOME — SA TAX TREATMENT

INDIVIDUAL LANDLORD:
- Rental income is fully taxable at your marginal rate
- Deductible expenses: rates & taxes, insurance, repairs & maintenance, bond interest,
  agent fees, levies, wear & tear on fixtures (not structure)
- NOT deductible: capital improvements, bond capital repayments
- Net rental income added to your other income (salary, drawings, etc.)

RENTAL INCOME IN A COMPANY/CC:
- Taxed at 27% corporate rate (more efficient if you're in 41-45% personal bracket)
- BUT then dividends tax (20%) applies when you extract the money
- Effective rate: 27% + 20% of remainder = ~41.6% — similar to high marginal rate
- Consult your tax practitioner for optimal structure

LOSING RENTAL INCOME (selling to tenants):
- The rental income stream has a capital value (typically 8-12x annual rent)
- R25,000/month rental = R300,000/year = worth R2.4m-R3.6m capitalised
- Getting R2m for the property itself means you're selling below income value
- BUT: clean exit, no maintenance, no tenant risk, no vacancy risk

LONG-TERM TENANT CONSIDERATION:
- Tenants of 6+ years have strong rights under RHA (Rental Housing Act)
- Selling to them avoids RHA complications
- Consider their loyalty when pricing — but don't undersell significantly

SECTION 12H LEARNERSHIP ALLOWANCE: Not applicable to rental income.
"""
    },

    {
        "id": "fa_005",
        "title": "Cash flow forecasting and scenario planning",
        "keywords": [
            "scenario", "wat as", "what if", "projeksie", "projection",
            "vooruitskatting", "forecast", "kontantvloei", "cash flow",
            "verlies projeksie", "loss projection", "breakevenl", "break even",
            "gelykbreek", "monthly expenses", "maandelikse kostes",
            "fixed costs", "vaste kostes", "variable costs", "wisselende kostes"
        ],
        "content": """
CASH FLOW FORECASTING — SA SME PRACTICAL GUIDE

BREAK-EVEN CALCULATION:
Break-even revenue = Fixed Costs / Gross Margin %
Example: Fixed costs R291,000/month, Gross margin 69.7%
Break-even = R291,000 / 0.697 = R417,500/month revenue needed

SCENARIO PLANNING — THREE SCENARIOS:
1. Base case: current trend continues
2. Downside: 20% revenue drop — can you survive 3 months?
3. Upside: 20% revenue increase — do you have capacity/stock?

FIXED vs VARIABLE COSTS (SA SME):
Fixed (same every month regardless of sales):
- Salaries and wages
- Rent / rates / municipal
- Insurance
- Bond/vehicle payments
- Subscriptions
- Accounting fees

Variable (move with sales volume):
- Cost of goods sold / purchases
- Petrol (delivery-related)
- Packaging
- Commission

CASH FLOW vs PROFIT:
- A business can be profitable but cash-flow negative
- Timing: you invoice R500k but collect R300k this month = cash flow problem
- Debtors outstanding > 60 days = cash tied up, not working
- Stock that doesn't move = dead capital

SURVIVAL METRIC:
Cash runway = Available cash / Monthly cash burn
If you have R800k cash and burn R291k/month = 2.75 months runway
Minimum safe runway for an SME: 3 months
"""
    },

    {
        "id": "fa_006",
        "title": "Working capital management — stock, debtors, creditors",
        "keywords": [
            "werkende kapitaal", "working capital", "dooie voorraad", "dead stock",
            "slow moving", "stadige voorraad", "debiteure", "debtors aging",
            "ouderdomsanalise", "kredieteure", "creditors", "kash flow",
            "cash flow", "voorraad waarde", "stock value", "collect debt",
            "invorder skuld", "120 dae", "90 dae", "60 dae"
        ],
        "content": """
WORKING CAPITAL MANAGEMENT — PRACTICAL SA SME GUIDE

WORKING CAPITAL = Current Assets - Current Liabilities
Healthy ratio: at least 1.5:1 (R1.50 assets for every R1 liability)
Danger zone: below 1:1 — you cannot pay short-term obligations

STOCK MANAGEMENT:
- Dead stock (no movement 6+ months) = cash trapped in warehouse
- Calculate: dead stock value / monthly COGS = months of dead capital
- Options for dead stock:
  a) Sell at cost (get cash, lose no more)
  b) Bundle with fast-moving stock (add-on deal)
  c) Donate (Section 18A deduction if registered NPO)
  d) Scrap and write off (reduces taxable income)
- Never hold dead stock hoping price will recover — the cost of capital exceeds any gain

DEBTORS MANAGEMENT:
- 30 days = normal trading terms
- 60 days = send statement + phone call
- 90 days = formal demand letter (LBA — Letter Before Action)
- 120+ days = hand to attorney OR write off as bad debt
- Bad debt write-off: deductible for income tax IF you can prove it's irrecoverable
- VAT adjustment: claim back output VAT on bad debts written off (4-year limit)

CREDITORS STRATEGY:
- Stretch creditors to 45-60 days if your terms allow (free financing)
- Never go beyond terms without communication — damages supplier relationship
- Negotiate extended terms when cash is tight — most suppliers prefer this to bad debt

CASH CONVERSION CYCLE:
Days inventory outstanding + Days sales outstanding - Days payable outstanding
= How many days cash is tied up in operations
Lower is better. Target: under 60 days for a trading business.
"""
    },

    {
        "id": "fa_007",
        "title": "Owner salary, drawings and tax efficiency for SA SMEs",
        "keywords": [
            "salaris", "salary", "tekening", "drawings", "lone", "wages",
                "belasting effektief", "tax efficient", "dividende", "dividends",
            "provisional tax", "voorlopige belasting", "iti", "it14",
            "small business corporation", "SBC", "micro business", "turnover tax"
        ],
        "content": """
OWNER REMUNERATION — TAX EFFICIENT STRUCTURES (SA)

SMALL BUSINESS CORPORATION (SBC) TAX RATES (2025/26):
- R0 - R95,750: 0%
- R95,751 - R365,000: 7% of amount above R95,750
- R365,001 - R550,000: R18,848 + 21% above R365,000
- Above R550,000: R57,698 + 27% above R550,000
Qualification: turnover < R20m, all shareholders natural persons, no investment income

INDIVIDUAL TAX RATES (2025/26):
- R0 - R237,100: 18%
- Up to R370,500: 26%
- Up to R512,800: 31%
- Up to R673,000: 36%
- Up to R857,900: 39%
- Up to R1,817,000: 41%
- Above R1,817,000: 45%
Primary rebate: R17,235

OPTIMAL STRATEGY FOR CC/PTY OWNER:
1. Pay yourself a salary up to the point where marginal personal rate = corporate rate
2. Leave surplus in company at 27% (vs your 41-45%)
3. Pay dividends in low-income years (20% dividends tax)
4. Use company to fund: medical aid (fringe benefit), travel allowance, cell phone

MEDICAL AID STRUCTURED VIA COMPANY:
- Company pays medical aid as employer contribution
- Taxed as fringe benefit on employee — but medical tax credit offsets most of it
- Net effect: company gets deduction, employee pays less than if paying personally

PROVISIONAL TAX:
- Due: August (first payment) and February (second payment)
- Avoid penalties: pay at least basic amount (last year's assessment)
- Top-up in February if business had a good year
"""
    },

    {
        "id": "fa_008",
        "title": "Buying vs renting business premises — financial analysis",
        "keywords": [
            "perseel koop", "buy premises", "eiendom koop", "property purchase",
            "huur vs koop", "rent vs buy", "erf belasting", "rates", "municipal",
            "munisipaal", "commercial property", "sakeperseel", "industrial property",
            "nywerheidsperseel", "besigheid perseel"
        ],
        "content": """
BUYING vs RENTING BUSINESS PREMISES (SA ANALYSIS)

COST OF OWNERSHIP (monthly, R2m property example):
- Bond at 11.5% on R2m over 20 years: ≈R21,000/month
- Rates & taxes: R3,000-R8,000/month depending on value and municipality
- Insurance: R1,500-R3,000/month
- Maintenance reserve (1% of value/year): ≈R1,667/month
- Total cost of ownership: ≈R27,000-R34,000/month

COST OF RENTING (equivalent premises):
- Commercial/industrial: typically 8-10% of property value per year
- R2m property: R160,000-R200,000/year = R13,333-R16,667/month
- Escalation: typically 7-10% per year

BREAK-EVEN: ownership usually cheaper after 5-7 years if property appreciates

BENEFITS OF OWNING:
- Appreciation (commercial property: 6-10% p.a. historically)
- Bond is forced savings
- Stability — no landlord risk
- Can rent out surplus space
- Bond interest is tax deductible (as business expense)

RISKS OF OWNING:
- Capital tied up (opportunity cost)
- Maintenance your responsibility
- Illiquid — can't quickly convert to cash

EIENDOMSBELASTING (MUNICIPAL RATES):
- Calculated on municipal valuation (General Valuation Roll — updated every 4 years)
- Rate in rand per R1 of value (varies by municipality)
- Typically 0.3%-0.8% of value per year for commercial
- B&B/guesthouse: often rated as commercial — can appeal if primary residence
- Industrial: often higher rate than residential
"""
    },

]


def get_relevant_financial_advisor_knowledge(user_message: str, max_chunks: int = 2) -> list:
    """
    Return the most relevant financial advisor knowledge chunks for a given message.
    Keyword matching — same pattern as all other knowledge modules.
    """
    if not user_message:
        return []

    msg_lower = user_message.lower()
    scored = []

    for chunk in FINANCIAL_ADVISOR_CHUNKS:
        score = 0
        for keyword in chunk.get("keywords", []):
            if keyword.lower() in msg_lower:
                score += 1
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:max_chunks]]


def format_financial_advisor_knowledge(chunks: list) -> str:
    """Format chunks for injection into Zane's system prompt."""
    if not chunks:
        return ""

    sections = ["\n\n## FINANCIAL ADVISOR KNOWLEDGE\n"]
    for chunk in chunks:
        sections.append(f"### {chunk['title']}\n{chunk['content'].strip()}\n")

    return "\n".join(sections)
