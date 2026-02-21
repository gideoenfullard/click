"""
ClickAI Pulse Intelligence Knowledge Base
==========================================
Teaches Zane HOW to analyze business data and generate strategic insights.
Uses same RAG approach as clickai_knowledge_base.py — small focused chunks,
only relevant ones injected per analysis.

Used by the Pulse scheduler (nightly/weekly) and when user asks Zane
for business advice, strategy, or "hoe lyk dinge?"

Categories: stock_analysis, cash_flow, customer_intel, supplier_intel,
  cross_business, market_strategy, financial_health, staff_productivity,
  risk_alerts, growth_opportunities
"""

PULSE_KNOWLEDGE = {

    # ============================================================
    # DEAD STOCK & SLOW MOVERS
    # ============================================================

    "dead_stock_detection": {
        "keywords": ["dead stock", "slow moving", "dooie stock", "nie verkoop", "sitting", "collecting dust", 
                     "not selling", "old stock", "lê", "stagnant", "obsolete", "surplus"],
        "title": "Dead Stock Detection & Action Plan",
        "content": """How to identify and handle dead stock:

**Detection Rules:**
- DEAD: Zero sales in 90+ days AND quantity on hand > 0
- SLOW: Less than 3 units sold in 90 days AND quantity > 10
- OVER-ORDERED: Current stock > 6 months of average monthly sales
- SEASONAL DEAD: No sales in current season but sold in opposite season

**Analysis Query Pattern:**
1. Get all stock items with qty > 0
2. Check last_sale_date for each item
3. Calculate days_since_last_sale = today - last_sale_date
4. Calculate monthly_run_rate = total sold last 6 months / 6
5. Calculate months_of_stock = qty_on_hand / monthly_run_rate
6. Flag items where months_of_stock > 6

**What to calculate:**
- Total VALUE of dead stock (qty × cost_price)
- Floor SPACE it occupies (if available)
- Opportunity cost: "This R50k in dead stock could be R50k in fast sellers"
- Holding cost: insurance, space, depreciation

**Recommendations by severity:**
- Dead 90-180 days: Run 20% discount sale, push on social media
- Dead 180-365 days: Run 40-50% clearance sale, offer bulk deals
- Dead 365+ days: Write off, donate (get tax benefit), or scrap
- Overstock but selling: Stop reordering, let levels drop naturally

**Smart Insight Examples:**
"R42,000 vas in 156 items wat laas in Julie verkoop het. As jy 'n 30% sale hou,
kry jy ~R29k cash terug EN maak 15m² vloerspace oop."

"Isaac het weer 50x Widget-A bestel, maar jy het nog 200 op rak met net 
5 per maand verkope. Dis 40 maande se stock! Cancel die bestelling."

**Cross-business opportunity:**
Dead stock space → convert to rental/B&B rooms
Dead stock space → sublet to another business
Dead stock → bundle with fast sellers as "combo deals"
Dead stock → trade with other businesses for stock you need"""
    },

    "stock_reorder_intelligence": {
        "keywords": ["reorder", "herbestel", "running low", "out of stock", "stock out", "min level",
                     "when to order", "forecast", "demand", "reorder point"],
        "title": "Smart Reorder Intelligence",
        "content": """Intelligent reorder analysis goes beyond simple min levels:

**Smart Reorder Formula:**
reorder_point = (avg_daily_sales × lead_time_days) + safety_stock
safety_stock = avg_daily_sales × lead_time_days × 0.3 (30% buffer)

**Analysis Pattern:**
1. Calculate avg daily sales for each item (last 90 days)
2. Know supplier lead time (how long delivery takes)
3. Calculate reorder point
4. Compare current qty to reorder point
5. Factor in open POs (already ordered, not yet received)

**What to report:**
- CRITICAL: Items below reorder point with 0 on order → "Jy gaan stockout!"
- WARNING: Items reaching reorder point in next 7 days
- SMART: Items that sell MORE on certain days/seasons

**Revenue impact:**
"M10 SS Hex Bolts: Jy verkoop gemiddeld 30/dag maar het net 45 oor. 
Dit gaan oor 1.5 dae op wees. Elke dag sonder stock = ~R2,400 verlore sales.
Lead time van supplier is 3 dae. JY MOET VANDAG BESTEL."

**Seasonal adjustment:**
- Check same month last year for seasonal items
- December: hardware slows, B&B peaks
- Winter: gas/heating up, outdoor furniture down
- Construction season: bolts/nuts/steel peak Aug-Nov

**Supplier performance tracking:**
- Which supplier delivers fastest?
- Which supplier's prices are increasing?
- Alternative suppliers for critical items?"""
    },

    "margin_analysis": {
        "keywords": ["margin", "markup", "profit", "wins", "verlies", "cost", "selling price", 
                     "onderprys", "under price", "loss", "profitability", "gross profit"],
        "title": "Margin & Profitability Analysis",
        "content": """How to analyze margins and spot profit leaks:

**Key Calculations:**
- Gross Margin % = (selling_price - cost_price) / selling_price × 100
- Markup % = (selling_price - cost_price) / cost_price × 100
- Contribution Margin = selling_price - variable_costs

**Detection Rules:**
- DANGER: Items selling BELOW cost (negative margin) → immediate price fix
- WARNING: Items with margin < 10% → barely covering overhead
- HEALTHY: Items with margin 25-45% (depends on industry)
- PREMIUM: Items with margin > 50% → protect these, push sales

**Industry Benchmarks (SA):**
- Hardware/Steel: 25-40% markup typical
- Fasteners (bolts/nuts): 30-50% markup
- Retail clothing: 100-200% markup (keystone+)
- Pub/Restaurant food: 60-70% markup (30-40% food cost)
- Pub/Restaurant drinks: 200-300% markup (25-30% pour cost)
- B&B accommodation: 60-80% margin typical
- Professional services: 50-70% margin

**Analysis to generate:**
1. Top 10 highest margin items (push these harder!)
2. Top 10 lowest margin items (fix pricing or stop stocking)
3. Items where cost increased but selling price didn't
4. Average margin per category
5. Margin trend: is overall margin improving or declining?

**Smart Insight Examples:**
"Jou gemiddelde markup op bolts is 35%, maar M16 range is net 12% — 
dit lyk of die cost price opdateer het met die laaste GRV maar jy het 
nie die selling price aangepas nie. Verloor ~R800/maand daarop."

"Jou pub se drank margin is 55% maar jou food margin is net 22%. 
Industrie norm vir food is 30-40%. Check portion sizes en food waste."

**Action triggers:**
- Cost increased > 10% on GRV → flag for price review
- Margin dropped below category average → alert
- Selling at loss → IMMEDIATE alert with suggested price"""
    },

    # ============================================================
    # CASH FLOW INTELLIGENCE
    # ============================================================

    "cash_flow_forecast": {
        "keywords": ["cash flow", "kontantvloei", "money coming in", "money going out", "afford",
                     "cash crunch", "liquidity", "tight", "genoeg geld", "forecast cash"],
        "title": "Cash Flow Forecasting & Alerts",
        "content": """How to predict and manage cash flow:

**30-Day Cash Flow Forecast Formula:**
expected_in = scheduled_debtor_payments + recurring_income + avg_daily_cash_sales × 30
expected_out = supplier_payments_due + payroll + rent + loan_repayments + VAT_due + SARS_due
forecast_balance = current_bank_balance + expected_in - expected_out

**What to track INCOMING:**
1. Debtors aging: When are they expected to pay?
   - On terms (30 day): expect payment ~day 35-40 (allow buffer)
   - Overdue 60+: only expect 50% to pay without action
   - Overdue 90+: expect 25% without legal action
2. Recurring income (rent, subscriptions)
3. Average daily POS/cash sales (use last 30 day average)

**What to track OUTGOING:**
1. Supplier invoices due (by due date)
2. Payroll (fixed monthly commitment)
3. Rent/lease payments
4. Loan repayments
5. SARS: EMP201 (7th monthly), VAT (25th bi-monthly), provisional tax
6. Insurance, subscriptions, recurring expenses
7. COIDA annual assessment

**Alert Levels:**
- GREEN: 30+ days of cash cover
- YELLOW: 14-30 days cash cover → "Start collecting from debtors"
- ORANGE: 7-14 days → "Delay non-critical payments, push collections hard"
- RED: <7 days → "Cash crisis! Prioritize payroll and SARS. Negotiate with suppliers"

**Smart Insight Examples:**
"Volgende week het jy R85k wat uitgestaan, maar net R30k verwag in. 
Plus payroll van R45k is die 25ste. Jy gaan R100k kort hê. 
Prioritize: Collect van ABC Hardware (R35k overdue) en Botha (R28k overdue)."

"Goeie nuus: Die volgende 2 weke lyk gesond — R120k in, R80k uit. 
Maar week 3 het VAT return (±R25k) EN kwartaallikse versekering (R18k)."

**Strategic recommendations:**
- Offer 5% discount for early payment (2% is industry standard)
- Move suppliers to 60-day terms where possible
- Build 2-month cash reserve as buffer
- Consider invoice factoring for large outstanding amounts"""
    },

    "debtor_risk_analysis": {
        "keywords": ["debtor", "debiteur", "owe", "skuld", "overdue", "outstanding", "late payment",
                     "collection", "bad debt", "invorder", "age analysis", "ageing"],
        "title": "Debtor Risk Analysis & Collection Strategy",
        "content": """How to analyze debtor risk and prioritize collections:

**Age Category Risk Levels:**
- Current (0-30 days): Normal, 95% collection probability
- 30-60 days: Monitor, 85% collection probability
- 60-90 days: Concern, 65% collection probability
- 90-120 days: High risk, 40% collection probability
- 120+ days: Critical, 20% probability → consider write-off

**Customer Risk Scoring:**
Score each customer 1-10 based on:
- Payment history (average days to pay)
- Number of overdue invoices in last 12 months
- Total outstanding as % of their credit limit
- How long they've been a customer
- Trend: getting better or worse?

**Concentration Risk:**
"Jou top 3 kliënte maak 55% van jou omset uit. As EEN van hulle nie betaal 
nie, is jy in die moeilikheid. Diversifiseer jou kliëntebasis."

DANGER: Any single customer > 20% of revenue
WARNING: Top 5 customers > 60% of revenue
HEALTHY: Top 5 customers < 40% of revenue

**Collection Priority Matrix:**
Priority = Amount × Risk Level × Age
Focus on: Large amounts that are aging but still recoverable (60-90 days)
Don't waste time on: Small amounts overdue (cost of collection > value)

**Smart Insight Examples:**
"R180k outstanding in totaal. Maar R45k daarvan is 90+ dae oud van 3 kliënte.
As jy net daai 3 collect, verbeter jou cash flow met 25%."

"ABC Hardware betaal altyd 15 dae laat. Dis nie 'n probleem nie — dis hulle patroon.
Maar DEF Construction het van 30 dae na 75 dae versleg — DIS 'n rooi vlag."

**Collection Actions by Age:**
- 30 days: Friendly statement reminder (auto)
- 45 days: Phone call / WhatsApp message
- 60 days: Formal letter, suspend further credit
- 90 days: Final demand, hand to collections/attorney
- 120+ days: Write off (get tax deduction), or sell debt"""
    },

    # ============================================================
    # SUPPLIER INTELLIGENCE
    # ============================================================

    "supplier_analysis": {
        "keywords": ["supplier", "verskaffer", "buying", "purchase", "procurement", "price increase",
                     "best price", "alternative supplier", "compare supplier"],
        "title": "Supplier Intelligence & Procurement Strategy",
        "content": """How to analyze supplier performance and optimize purchasing:

**Supplier Scorecard:**
Rate each supplier on:
- Price competitiveness (compare same items across suppliers)
- Delivery reliability (on time % from GRV dates vs PO dates)
- Quality (return rate, complaints)
- Payment terms offered (30/60/90 days)
- Communication & service

**Price Trend Analysis:**
Track cost prices over time per item per supplier:
- Cost increased > 10% in 6 months → flag, seek alternatives
- Cost increased > CPI (inflation ~5%) → acceptable
- Cost decreased → good, but check quality hasn't dropped

**Smart Insights:**
"Supplier A se pryse het 18% gestyg in 6 maande, maar Supplier B 
verkoop dieselfde items vir 12% minder. Oorweeg om te switch op 45 items."

"Jy koop van 8 verskillende bolt suppliers. As jy konsolideer na 3, 
kan jy beter volume discounts negotiate. Estimated saving: R8k/maand."

"Supplier C het die laaste 4 bestellings laat afgelewer (gemiddeld 5 dae laat).
Dis hoekom jy stockouts gehad het op M12 bolts."

**Procurement Strategies:**
- Consolidate suppliers for volume discounts
- Compare prices quarterly across suppliers
- Negotiate extended payment terms (30→60 days = free cash flow)
- Bulk buy fast movers when price is right (but don't overstock!)
- Keep backup supplier for critical items
- Request price locks for 6-12 months on key items"""
    },

    # ============================================================
    # CUSTOMER INTELLIGENCE
    # ============================================================

    "customer_behavior": {
        "keywords": ["customer", "klient", "buying pattern", "lost customer", "churn", "loyalty",
                     "repeat", "top customer", "best customer", "customer value", "frequency"],
        "title": "Customer Behavior Analysis",
        "content": """How to analyze customer patterns and prevent churn:

**Customer Value Segments:**
- PLATINUM: Top 10% by revenue (VIP treatment, personal service)
- GOLD: Next 20% by revenue (loyalty rewards, priority service)
- SILVER: Next 30% (standard service, growth potential)
- BRONZE: Bottom 40% (efficient service, upsell opportunities)

**Churn Detection (Lost Customer Alert):**
Calculate average purchase frequency per customer:
- avg_days_between_orders from last 12 months
- If current gap > 2× average → CHURN WARNING
- If current gap > 3× average → LIKELY LOST

"ABC Hardware het elke 2 weke bestel vir die laaste jaar, maar het 
nou 6 weke laas georder. Iets is fout — bel hulle!"

**Purchase Pattern Analysis:**
- What does each customer typically buy? (product affinity)
- When do they buy? (day of week, time of month)
- Are they buying MORE or LESS over time? (trend)
- Do they buy on account or cash? (credit risk)

**Cross-sell Opportunities:**
"Kliënte wat M10 hex bolts koop, koop gewoonlik ook flat washers en nuts.
Customer X koop altyd bolts maar NOOIT washers — suggest dit!"

**Customer Lifetime Value (CLV):**
CLV = avg_monthly_spend × expected_months_as_customer
A R5k/month customer for 3 years = R180k CLV
Investing R500 to keep them happy = massive ROI

**Smart Insights:**
"Jou top 5 kliënte se bestedingspatroon:
1. NDE Engineering: R45k/m (↑12% vs vorige jaar) ✅ 
2. ABC Hardware: R38k/m (↓25% vs vorige jaar) ⚠️ INVESTIGATE
3. Botha: R22k/m but 90 days overdue ⚠️ COLLECT
4. Smith Plumbing: R18k/m (stable) ✅
5. XYZ Construction: NEW - R15k/m and growing ✅ NURTURE"

**Retention Actions:**
- Lost customer: Call within 48 hours, offer incentive
- Declining customer: Understand why, match competitor pricing if needed
- Loyal customer: Reward with discounts, priority delivery, personal service"""
    },

    # ============================================================
    # CROSS-BUSINESS STRATEGY
    # ============================================================

    "cross_business_opportunities": {
        "keywords": ["cross business", "between businesses", "synergy", "opportunity", "expand",
                     "convert", "space", "room", "b&b", "pub", "hardware", "rental", "multi business"],
        "title": "Cross-Business Strategic Opportunities",
        "content": """How to find opportunities ACROSS multiple businesses:

**Space Optimization Analysis:**
For each business, calculate revenue per square meter:
- revenue_per_m2 = annual_revenue / floor_space_m2
- Compare across businesses and across areas within a business

"Hardware store: R2,500/m² per year (bolts section)
Hardware store: R200/m² per year (dead stock display area)  ← PROBLEM
B&B rooms: R18,000/m² per year ← OPPORTUNITY
Converting 20m² dead stock area to 1 B&B room = R30k/month extra income"

**Cross-Selling Between Businesses:**
- B&B guests → direct to pub for meals/drinks
- Pub customers → advertise B&B for out-of-town friends
- Hardware customers doing renovations → offer B&B to workers
- B&B guests from construction → sell hardware supplies

**Shared Resources:**
- Same staff across businesses (peak times differ)
- Shared delivery vehicle
- Bulk purchasing across businesses (combined volume)
- One bookkeeper/accountant for all entities (ClickAI handles this!)

**Seasonal Balancing:**
"Hardware is quiet in Dec/Jan but B&B is peak season.
Move staff from hardware to B&B for cleaning/service.
Pub is busy every Friday/Saturday year-round — consistent base."

**Strategic Questions to Ask:**
1. Which business has the highest revenue per m²? (expand this)
2. Which has unused capacity? (convert or sublet)
3. Where do customer bases overlap? (cross-promote)
4. Which business is growing fastest? (invest more here)
5. Which has declining margins? (fix or phase out)

**New Revenue Stream Ideas:**
- Empty wall space → advertising for local businesses
- Parking area off-peak → weekend market stalls
- Roof space → solar panels (reduce electricity cost for all businesses)
- Workshop area → paid DIY workshops on weekends
- Dead stock area → pop-up shop space for other vendors"""
    },

    # ============================================================
    # FINANCIAL HEALTH
    # ============================================================

    "financial_ratios": {
        "keywords": ["ratio", "current ratio", "quick ratio", "financial health", "gesondheid",
                     "benchmark", "performance", "kpi", "indicator", "measure"],
        "title": "Financial Health Ratios & KPIs",
        "content": """Key ratios to calculate and what they mean:

**Liquidity (Can you pay your bills?):**
- Current Ratio = Current Assets / Current Liabilities
  → Above 2.0: Healthy | 1.0-2.0: OK | Below 1.0: DANGER
- Quick Ratio = (Current Assets - Stock) / Current Liabilities
  → Above 1.0: Good | Below 1.0: Depends on how fast stock sells

**Profitability (Are you making money?):**
- Gross Profit Margin = Gross Profit / Revenue × 100
  → Hardware: 25-35% | Pub: 60-65% | B&B: 70-80%
- Net Profit Margin = Net Profit / Revenue × 100
  → Healthy: 10-20% | Surviving: 5-10% | Danger: Below 5%
- Return on Assets = Net Profit / Total Assets × 100

**Efficiency (How well do you use resources?):**
- Stock Turnover = Cost of Sales / Average Stock Value
  → How many times stock "turns" per year (higher = better)
  → Hardware: 4-8x | Pub: 12-24x | Fast food: 30-50x
- Debtor Days = (Debtors / Revenue) × 365
  → How many days customers take to pay
  → 30 days: Great | 45 days: OK | 60+: Problem
- Creditor Days = (Creditors / Purchases) × 365
  → How many days YOU take to pay suppliers

**Growth:**
- Revenue growth: This month vs same month last year
- Customer growth: New customers vs lost customers
- Basket size: Average invoice value trend

**Smart Insight Example:**
"Quick Health Check vir Fulltech:
✅ Current Ratio: 2.3 (Healthy - can pay bills 2x over)
⚠️ Debtor Days: 52 (Customers taking too long - target 30 days)
✅ Gross Margin: 32% (On target for hardware)
❌ Stock Turnover: 2.8x (Stock sitting too long - target 6x)
💡 Action: Focus on collections and clearing dead stock"

**Monthly Trend:**
Track these ratios monthly. Plot trend over 12 months.
DIRECTION matters more than absolute number — improving or declining?"""
    },

    # ============================================================
    # PAYROLL & STAFF INTELLIGENCE
    # ============================================================

    "staff_cost_analysis": {
        "keywords": ["staff cost", "payroll cost", "salary", "employee", "werknemer", "labour",
                     "personnel", "cost to company", "produktiwiteit", "productivity", "efficiency"],
        "title": "Staff Cost & Productivity Analysis",
        "content": """How to analyze staff costs and productivity:

**Revenue Per Employee:**
revenue_per_employee = total_revenue / number_of_employees
Compare monthly. Is it increasing (good) or decreasing (concern)?

**Payroll as % of Revenue:**
payroll_ratio = total_payroll_cost / total_revenue × 100
- Hardware/Retail: 12-20% is healthy
- Restaurant/Pub: 25-35% is healthy
- B&B/Guesthouse: 20-30% is healthy
- Professional Services: 35-50% is healthy

**Cost to Company per Employee:**
Don't forget to include:
- Basic salary
- UIF employer contribution (1%)
- SDL (1%)
- COIDA assessment
- Medical aid contribution
- Provident/pension fund
- Leave provision (accrued leave = liability!)

**Overtime Analysis:**
"Overtime was 15% van totale payroll hierdie maand. Dis duurder as om 
'n deeltydse werker aan te stel as dit konsekwent is."

**Smart Insights:**
"Revenue per employee het van R85k/m na R72k/m gedaal oor 3 maande,
maar jy het 2 nuwe mense aangestel. Dit neem tyd om productive te word,
maar monitor dit — teen maand 3 moet dit verbeter."

"Die pub se payroll is 38% van revenue — bietjie hoog. Saterdag het 
6 staff maar Dinsdag ook 5. Oorweeg om Dins-Woe na 3 staff te reduce."

**Leave Management:**
- Track leave balances — high balances = future cash liability
- Employees with 30+ days accrued leave → force to take leave
- Provision for leave on balance sheet = leave_days × daily_rate

**Absenteeism:**
Track sick leave patterns. If someone takes sick leave every Monday 
or every payday Friday, that's a pattern worth flagging."""
    },

    # ============================================================
    # PUB & RESTAURANT SPECIFIC
    # ============================================================

    "pub_restaurant_intel": {
        "keywords": ["pub", "restaurant", "bar", "kroeg", "food cost", "pour cost", "beverage",
                     "drank", "kos", "kitchen", "waste", "menu", "happy hour"],
        "title": "Pub & Restaurant Intelligence",
        "content": """Specific intelligence for pub/restaurant/bar operations:

**Cost of Goods Sold (COGS) Targets:**
- Food cost: 28-35% of food revenue
- Beverage cost: 20-28% of beverage revenue
- Overall COGS: 25-32% of total revenue

**If food cost is too high (>35%):**
- Portion sizes too big
- Menu prices too low
- Food waste/spoilage
- Theft (common in kitchens)
- Supplier prices increased without menu adjustment
- Too many menu items (complexity = waste)

**If pour cost is too high (>28%):**
- Over-pouring (no jiggers/measured shots)
- Theft (free drinks to friends)
- Breakage/spillage not tracked
- Happy hour discounting too aggressively
- Free tastings not accounted for

**Analysis Pattern:**
1. Calculate food cost % per month (Food purchases / Food revenue × 100)
2. Calculate pour cost % per month
3. Compare actual vs standard (recipe cost) per dish
4. Track waste log (what gets thrown away and why)

**Smart Insights:**
"Jou food cost was 42% hierdie maand — dis 10% bo target. 
Top 3 oorsake: Steak dish (62% food cost — prys moet op),
Burger special (giving away too much), Salad wastage on quiet days."

"Drank revenue is R80k maar purchases was R28k = 35% pour cost.
Industrie norm is 25%. Dis ±R8k per maand wat 'verdwyn'. 
Install pour spouts en check variance per bottle."

**Profitable Decisions:**
- Engineer menu: push high-margin items (usually chicken, pasta, pizza)
- Limit low-margin items or increase prices
- Daily specials to use stock before it expires
- Happy hour should drive TRAFFIC, not give away margin
- Track best-selling items and make sure they're high-margin"""
    },

    # ============================================================
    # B&B / GUESTHOUSE SPECIFIC
    # ============================================================

    "bnb_guesthouse_intel": {
        "keywords": ["b&b", "bnb", "guesthouse", "gastehuis", "accommodation", "occupancy", "room",
                     "kamer", "booking", "revpar", "rate", "tarief", "accommodation"],
        "title": "B&B & Guesthouse Intelligence",
        "content": """Specific intelligence for B&B/guesthouse operations:

**Key Metrics:**
- Occupancy Rate = rooms_sold / rooms_available × 100
  → Target: 65-80% annually (seasonal variation expected)
- ADR (Average Daily Rate) = room_revenue / rooms_sold
- RevPAR (Revenue Per Available Room) = room_revenue / rooms_available
  → THE most important metric — combines occupancy AND rate

**Analysis Pattern:**
1. Calculate occupancy by day of week
2. Calculate occupancy by month/season
3. Compare ADR to competitors
4. Track direct bookings vs OTA (Booking.com, Airbnb) bookings

**Seasonal Patterns (typical SA):**
- Peak: Dec/Jan (holidays), Easter, school holidays
- Shoulder: Feb/Mar, Oct/Nov (good weekends)
- Low: May-Aug (winter, except ski/mountain areas)
- Events: Local festivals, conferences = spikes

**Pricing Strategy:**
"Jou weekday occupancy is 25% maar weekend is 90%.
Drop weekday rate by 20% to attract business travellers.
Even at lower rate, a filled room > empty room."

"Jou ADR is R650 maar the guesthouse down the road charges R850 
for similar quality. You're leaving R200/night on the table. 
At 70% occupancy that's R4,200/month per room."

**Smart Insights:**
"Room 3 het 45% occupancy terwyl Room 1 het 85%. Check wat anders is.
Is dit die view? Die bed size? Die noise level? Fix Room 3 issues."

"Jou Airbnb commission is 15% = R12k/maand. As jy 30% van daai 
bookings direk kan kry (own website, Google), spaar jy R3.6k/maand."

**Cost Management:**
- Cleaning cost per room (track consumables)
- Laundry cost per room
- Breakfast cost per guest
- Municipal charges (water/electricity per room)
- Maintenance reserve: budget 5% of revenue

**Revenue Boosters:**
- Airport/activity transfers (markup)
- Breakfast upsell for room-only bookings  
- Mini-bar / honesty bar in rooms
- Late checkout fee
- Partnerships with local activities/restaurants
- Corporate rates for repeat business travellers"""
    },

    # ============================================================
    # HARDWARE STORE SPECIFIC
    # ============================================================

    "hardware_store_intel": {
        "keywords": ["hardware", "steel", "stainless", "bolts", "fastener", "nuts", "workshop",
                     "construction", "building", "contractor", "trade"],
        "title": "Hardware & Steel Supplier Intelligence",
        "content": """Specific intelligence for hardware/steel/fastener businesses:

**Key Metrics:**
- Stock Turnover by category (fasteners should turn 6-10x/year)
- Margin by category (stainless vs HDG vs zinc plated)
- Average invoice value (higher = more profitable per transaction)
- Cut/waste ratio (steel cutting → track offcuts and waste)

**Stainless Steel Market Intelligence:**
- Track nickel price (drives SS304/316 pricing)
- When nickel rises → buy extra stock at current prices
- When nickel falls → don't overstock, prices will drop
- SA import dependency: most SS comes from China/India
- Rand weakness → SS prices increase (imported)

**Customer Segmentation:**
- Walk-in (cash/small): Quick service, don't over-service
- Account (regular trade): Relationship, pricing, delivery
- Project (large orders): Competitive pricing, bulk deals
- Contractor (repeat): Loyalty program, credit terms

**Smart Insights:**
"Jou gemiddelde faktuur is R2,800 maar 60% van transaksies is onder R500.
Daai klein transaksies vat dieselfde tyd as groot een. 
Oorweeg minimum order amounts of delivery charges vir klein orders."

"M10 SS Hex Bolts is jou #1 seller (R45k/m). Maar jou margin is net 22%.
Dis 'n 'traffic driver' — mense kom in vir bolts en koop ander items ook.
As jy die margin verhoog verloor jy dalk die traffic. Keep it competitive
maar PUSH high-margin accessories (washers, nuts, thread lock)."

**Workshop Intelligence:**
If you have a cutting/fabrication workshop:
- Track job profitability (materials + labour vs charge-out)
- Most profitable: custom cutting, threading, fabrication
- Least profitable: small cuts, advice without purchase
- Workshop utilization: % of time machine is running vs idle

**Construction Season Preparation:**
Aug-Nov = peak construction = peak demand:
- Pre-order bulk fasteners in June/July (better prices)
- Ensure popular sizes are stocked deep
- Temporary extra staff for busy period
- Extend operating hours if demand warrants it"""
    },

    # ============================================================
    # RISK ALERTS
    # ============================================================

    "business_risk_alerts": {
        "keywords": ["risk", "risiko", "warning", "danger", "gevaar", "problem", "alert",
                     "concern", "watch out", "red flag", "threat"],
        "title": "Business Risk Detection & Alerts",
        "content": """Critical business risks to monitor and flag:

**Financial Risks:**
- Cash reserve < 1 month expenses → "Bou 'n buffer op!"
- Single customer > 25% of revenue → "Diversifiseer"
- Gross margin declining 3 months in a row → "Pricing problem"
- Expenses growing faster than revenue → "Cost creep"
- SARS payments late/missed → "Penalties incoming"

**Operational Risks:**
- Key supplier dependency (>50% of purchases from 1 supplier)
- Stock concentration (>40% of value in 1 category)
- No backup for critical staff member
- Equipment maintenance overdue
- Insurance coverage gaps

**Compliance Risks:**
- EMP201 not submitted by 7th → immediate penalty
- VAT return overdue → 10% penalty on amount due
- Employee contracts missing or outdated
- COIDA registration lapsed
- Leave records not maintained

**Fraud/Theft Indicators:**
- Cash sales declining while stock reduces → theft
- Void/refund transactions unusual → POS fraud
- Purchase prices above market → kickback
- Ghost employees on payroll
- Stock adjustments without explanation

**Smart Alert Examples:**
"⚠️ ROOI VLAG: Jou void rate op POS is 8% — industrie norm is 1-2%.
Dis R12k aan voided sales hierdie maand. Investigate."

"⚠️ RISIKO: 68% van jou aankope is van een verskaffer. As hulle 
close of hul pryse verhoog, het jy geen alternatief nie."

"⚠️ COMPLIANCE: EMP201 is more as 3 dae oor die deadline. 
SARS penalty = interest + administrative fine. Submit VANDAG."

**Risk Priority Matrix:**
CRITICAL (Act today): SARS deadlines, cash < 7 days, fraud indicators
HIGH (Act this week): Lost key customer, margin collapse, compliance gaps
MEDIUM (Act this month): Supplier dependency, dead stock growing
LOW (Monitor): Market changes, seasonal patterns, competitor activity"""
    },

    # ============================================================
    # GROWTH & OPPORTUNITY
    # ============================================================

    "growth_opportunities": {
        "keywords": ["grow", "groei", "expand", "opportunity", "geleentheid", "scale", "increase",
                     "more revenue", "meer omset", "new market", "idea", "strategy", "plan"],
        "title": "Growth Opportunities & Strategic Planning",
        "content": """How to identify and evaluate growth opportunities:

**Revenue Growth Levers (easiest to hardest):**
1. PRICE: Increase prices 5-10% (many customers won't notice)
2. FREQUENCY: Get existing customers to buy more often
3. BASKET SIZE: Upsell/cross-sell more per transaction
4. NEW CUSTOMERS: Marketing, referrals, new channels
5. NEW PRODUCTS: Add complementary product lines
6. NEW MARKETS: Online sales, new geographic area, export
7. NEW BUSINESS: B&B, pub, rentals (what Deon does!)

**Pricing Power Test:**
"Jou gemiddelde prysverhoging laaste jaar was 3%, maar inflasie was 5.5%.
Jy het effektief 2.5% goedkoper geword. Verhoog pryse met 5% — 
op R2m omset is dit R100k ekstra wins per jaar."

**Expansion Analysis:**
Before expanding, calculate:
- Cost of expansion (capex)
- Expected monthly revenue
- Expected monthly costs
- Break-even months = capex / (monthly revenue - monthly costs)
- If break-even > 24 months → risky. < 12 months → good bet.

**Smart Insights:**
"Jou B&B maak R18k/m² per jaar. Jou dead stock area maak R200/m² per jaar.
Converting 30m² to one B&B room: Cost ±R150k to convert.
Expected revenue: R15k/month. Break-even: 10 months. DO IT."

"Online sales is R0 terwyl jou kompetisie doen 30% van omset online.
'n Basic Shopify store + jou top 100 items = R20-30k extra per maand.
Setup cost: R10k. Break-even: Month 1."

**Monthly Strategic Review Prompt:**
Ask these 5 questions every month:
1. What's my #1 profit driver right now? (protect it)
2. What's my #1 cost that's too high? (fix it)
3. Which customer should I focus on? (grow or collect)
4. What opportunity am I ignoring? (act on it)
5. What risk could hurt me? (mitigate it)"""
    },

    # ============================================================
    # SEASONAL & MARKET INTELLIGENCE
    # ============================================================

    "seasonal_market_intel": {
        "keywords": ["season", "seisoen", "market", "mark", "trend", "weather", "weer", "holiday",
                     "vakansie", "december", "winter", "summer", "christmas", "black friday"],
        "title": "Seasonal & Market Intelligence",
        "content": """How to use seasonal and market data for planning:

**SA Retail Calendar (plan 1 month ahead):**
- January: Quiet, back-to-school, New Year resolutions
- February: Valentine's (pub), quiet for hardware
- March: Easter prep, autumn starts, financial year-end (many companies)
- April: Easter (B&B peak), school holidays, Freedom Day
- May: Quiet month, Mother's Day (pub/restaurant)
- June: Winter starts, gas/heating demand, school holidays
- July: Quiet, deep winter, school holidays
- August: Women's Day, spring starts, construction picks up
- September: Heritage Day braais, spring = renovation season starts
- October: Construction peak, pre-December prep
- November: BLACK FRIDAY (huge for retail), Year-end parties (pub)
- December: PEAK B&B, holiday hardware (DIY projects), pub busy

**Market Intelligence to Track:**
- Steel/metal prices (global markets affect SA prices 6-8 weeks later)
- Rand/Dollar exchange rate (affects all imported goods)
- Interest rate changes (affects construction, property, affordability)
- Fuel price (affects delivery costs and customer spending)
- Load shedding schedule (affects operations, generator costs)
- Municipal rates increases (usually July - affects rental properties)

**Smart Insights:**
"November is oor 3 weke — Black Friday prep: 
1. Identify slow stock for massive discounts (clear dead stock!)
2. Stock up on popular items (they'll sell MORE at full price during rush)
3. Prepare POS for high volume
4. Schedule extra staff for Fri-Sun"

"Steel pryse het 8% gestyg hierdie kwartaal internasionaal.
Dis nog nie in jou supplier pryse nie — dit kom oor 4-6 weke.
Oorweeg om 2 maande se stock te koop teen huidige pryse."

**Weather-based alerts:**
- Heatwave coming → B&B pool/aircon ready? Cold drinks stocked?
- Cold snap → Heating stock? B&B blankets? Pub comfort food?
- Rain → Construction delays → less hardware demand
- Load shedding → Generator fuel, gas stock, candles"""
    },

    # ============================================================
    # EXPENSE MANAGEMENT
    # ============================================================

    "expense_optimization": {
        "keywords": ["expense", "uitgawe", "cost cutting", "save money", "spaar", "reduce cost",
                     "overhead", "running cost", "operational cost", "waste", "vermorsing"],
        "title": "Expense Optimization Intelligence",
        "content": """How to find and reduce unnecessary expenses:

**Expense Analysis Method:**
1. List ALL expenses for last 12 months
2. Categorize: Essential vs Nice-to-have vs Waste
3. Benchmark each against industry norms
4. Track month-over-month trend
5. Identify top 5 expenses that grew fastest

**Common Cost Savings (SA businesses):**
- Electricity: Solar + battery (pays back in 3-4 years, no more load shedding)
- Insurance: Shop around annually (most people overpay 15-25%)
- Telecoms: Switch to fibre + VoIP (cut phone costs 50%+)
- Banking: Compare bank charges (some banks charge 3x more)
- Subscriptions: Audit all subscriptions monthly (zombie subscriptions)
- Printing: Go paperless where possible (ClickAI helps!)
- Fuel: Optimize delivery routes, combine trips

**Smart Insights:**
"Jou elektrisiteit koste het 35% gestyg in 12 maande maar verbruik 
het net 10% gestyg — die tarief verhogings kill jou. Solar investment:
R180k installed. Saving: R5k/month. Payback: 3 years. Net daarna = pure savings."

"Jy betaal R8k/m vir versekering oor 4 besighede. Konsolideer onder 
een broker vir multi-policy discount — typical saving 15-20% = R1.2k-1.6k/m."

**Expense Ratios to Monitor:**
- Rent as % of revenue: < 10% ideal
- Payroll as % of revenue: depends on industry (see staff analysis)
- Marketing as % of revenue: 2-5% for established businesses
- Total overhead as % of revenue: < 35% leaves healthy margin

**Monthly Expense Review:**
Flag any expense that:
- Increased > 10% from last month (why?)
- Is new and wasn't budgeted
- Hasn't been reviewed in 12+ months (negotiate better rate)
- Has a cheaper alternative available"""
    },

    # ============================================================
    # TAX PLANNING
    # ============================================================

    "tax_planning_strategy": {
        "keywords": ["tax planning", "belasting beplanning", "save tax", "tax deduction", "aftrekking",
                     "reduce tax", "section 12", "depreciation", "wear and tear", "tax benefit"],
        "title": "Tax Planning & Optimization Strategy",
        "content": """Legal tax saving strategies for SA businesses:

**Depreciation / Wear & Tear:**
Claim Section 11(e) wear and tear on business assets:
- Computers/electronics: 3 years (33.3% per year)
- Vehicles: 5 years (20% per year)
- Furniture: 6 years (16.7% per year)
- Machinery: 4-10 years depending on type
- Buildings: 5% per year (20 years)

"Jy het vir R120k toerusting gekoop hierdie jaar maar het nie die 
wear & tear gecliam nie. Dis R40k aftrekking = ±R10.8k minder belasting (at 27%)."

**Section 12C (Manufacturing):**
If you have a workshop/manufacturing:
- New manufacturing equipment: 40/20/20/20 (40% year 1!)
- Can accelerate depreciation significantly

**Small Business Corporation (SBC) Benefits:**
If you qualify (turnover < R20m):
- First R95,750 taxable income = ZERO tax
- Next R269,250 at only 7%
- Much better than 27% flat company rate

**Deductions Often Missed:**
- Home office (if applicable)
- Vehicle expenses (logbook method)
- Bad debts written off
- Donations to PBOs (Section 18A) - up to 10% of taxable income
- Training costs (also counts for SDL/SETA)
- Medical expenses above credits

**VAT Planning:**
- Timing purchases before VAT period end to claim input VAT earlier
- Ensure ALL purchase invoices have supplier VAT number
- Claim VAT on capital items (new equipment, vehicles)
- Entertainment: only 50% of VAT claimable — structure correctly

**Year-End Planning (do 2-3 months before year end):**
1. Check estimated profit → any room to buy needed equipment?
2. Write off bad debts before year end
3. Ensure all depreciation is up to date
4. Prepay annual expenses if beneficial
5. Bonuses: pay before year end to deduct in current year
6. Review SBC qualification — still qualifying?

**Smart Insight:**
"Jou jaar-einde is oor 2 maande. Geskatte wins: R650k. By 27% = R175k belasting.
As jy daai R180k solar stelsel NOU installeer: 
- Section 12B: 100% aftrekking in jaar 1
- Tax saving: R48.6k
- PLUS R5k/m elektrisiteit saving
- Net cost after tax benefit: R131.4k. No brainer."
"""
    },
    # ============================================================
    # RETAIL / CLOTHING / FASHION
    # ============================================================

    "retail_clothing_intel": {
        "keywords": ["retail", "clothing", "fashion", "klere", "mode", "boutique", "shop", "winkel",
                     "apparel", "shoes", "skoene", "accessories"],
        "title": "Retail & Clothing Store Intelligence",
        "content": """Specific intelligence for retail/clothing/fashion businesses:

**Key Metrics:**
- Sales per m² = total_revenue / floor_space (benchmark: R3k-R8k/m²/month)
- Sell-through rate = units_sold / units_bought × 100 (target: 65-80%)
- Average transaction value (ATV) — track trend, push upselling
- Conversion rate = transactions / foot_traffic (if tracked)
- Stock turn: Fashion should turn 4-6x per year

**Seasonal Calendar:**
- Jan: Sale season (clear summer stock), back-to-school
- Mar/Apr: Autumn collection launch, Easter
- May: Mother's Day, winter stock arriving
- Jun-Aug: Winter clearance mid-season
- Sep: Spring launch, new arrivals
- Nov: Black Friday (biggest revenue day), festive season prep
- Dec: Peak sales, gift buying, holiday wear

**Margin Targets:**
- Standard markup: 100-200% (keystone = 100%)
- Sale items: Try to maintain 30%+ margin even on sale
- Accessories: Highest margin (200-400%) — always upsell!

**Dead Stock Strategy:**
Fashion has a SHORT lifecycle — if it hasn't sold in 60-90 days:
- Mark down 20-30% immediately
- 120+ days: 50% clearance or donate (get tax deduction S18A)
- NEVER carry last season's stock into new season
- Bundle slow movers with fast sellers

**Smart Insights:**
"Jou sell-through rate is 52% — dis onder target (65%). Jy koop te veel 
of jou pricing is te hoog. Focus op minder styles, dieper sizes."

"Accessories maak net 8% van sales maar 22% van margin. Push accessories 
harder — train staff to suggest a belt/scarf/bag with every outfit."

**Growth Tactics:**
- Instagram/TikTok presence (fashion is visual)
- Personal shopping service for VIP customers
- WhatsApp groups for new arrival announcements
- Loyalty program (buy 10 get 1 free)
- Pop-up events and fashion shows"""
    },

    # ============================================================
    # AUTO / MOTOR / MECHANIC / PARTS
    # ============================================================

    "auto_motor_intel": {
        "keywords": ["auto", "motor", "car", "vehicle", "mechanic", "workshop", "garage", "panel beater",
                     "parts", "spares", "onderdele", "voertuig", "werktuigkundige", "tyre", "tire",
                     "service", "fitment", "oil change"],
        "title": "Auto, Motor & Workshop Intelligence",
        "content": """Specific intelligence for auto workshops, parts, and motor businesses:

**Key Metrics:**
- Labour utilization = billed_hours / available_hours × 100 (target: 75-85%)
- Effective labour rate = labour_revenue / billed_hours
- Parts margin: 25-40% on standard parts, 50%+ on accessories
- Average repair order value (track trend)
- Come-back rate: repairs that need redo (target: <3%)

**Workshop Efficiency:**
- Track time per job type (service, brakes, engine, electrical)
- Compare quoted time vs actual time (are techs efficient?)
- Bay utilization: how many hours per day is each bay occupied?
- Idle time = money lost

**Parts Management:**
- Fast movers: Oil filters, brake pads, spark plugs — always in stock
- Slow movers: Specific model parts — order on demand
- Obsolete: Old model parts — discount or return to supplier
- Markup: OEM parts 25-35%, aftermarket 40-60%, consumables 50-100%

**Seasonal Patterns:**
- Dec/Jan: Road trip prep (services, tyres, batteries)
- Mar: After-holiday repairs
- Jun: Winter battery failures, headlight issues
- Sep: Pre-summer aircon services
- Monthly: Payday week = more walk-ins

**Smart Insights:**
"Jou meganieker Jan het 65% utilization maar Pieter het 82%. 
Jan se gemiddelde job neem 30% langer as quoted. Training needed?"

"Brake pad jobs: Jy charge R1,200 maar die job cost (parts+labour) is R950.
Margin is net R250 (21%). Increase labour rate of parts markup."

"Jy het R85k in parts op die rak wat ouer as 12 maande is. 
Return to supplier or sell at 50% — daai geld is beter in fast movers."

**Revenue Boosters:**
- Service plans / maintenance contracts (recurring revenue!)
- Fleet maintenance contracts with businesses
- Courtesy car service (differentiator)
- SMS/WhatsApp service reminders based on km/date
- Tyre storage service (seasonal swaps)"""
    },

    # ============================================================
    # CONSTRUCTION / BUILDING
    # ============================================================

    "construction_building_intel": {
        "keywords": ["construction", "building", "contractor", "kontrakteur", "bou", "builder",
                     "project", "projek", "site", "tender", "civil", "plumbing", "electrical",
                     "renovation", "opknapping", "paint", "verf"],
        "title": "Construction & Building Contractor Intelligence",
        "content": """Specific intelligence for construction and building businesses:

**Key Metrics:**
- Job profitability = (revenue - materials - labour - subcontractors) / revenue × 100
- Target margin: 15-25% on residential, 10-15% on commercial/tender
- Variation/extras as % of original quote (too high = bad quoting)
- On-time completion rate (impacts reputation + penalty clauses)

**Job Costing (CRITICAL):**
Track per job:
- Materials (with wastage factor: add 10-15% to material estimates)
- Direct labour (hours × rate per trade)
- Subcontractor costs
- Plant/equipment hire
- Transport to site
- Supervision time
- Defects/rework cost

**Cash Flow Management (biggest killer in construction):**
- Progress billing: Invoice as milestones are reached (don't wait for completion)
- Retention: Budget for 5-10% retention holdback
- Material pre-purchase: Get deposits upfront to fund materials
- Don't start without deposit: 30-50% upfront is standard

**Quoting Intelligence:**
"Jou laaste 10 jobs: 6 was winsgewend, 4 was verliesgewend. 
Die 4 verliese was almal bathroom renovations — jou plumbing 
subcontractor is te duur. Get alternative quotes."

"Jou variation rate is 35% — dit beteken jou oorspronklike quotes 
mis 'n derde van die werk. Improve your site inspection checklist."

**Risk Management:**
- Weather delays (build buffer into timeline)
- Material price increases mid-project (lock prices or add escalation clause)
- Subcontractor no-show (have backup list)
- Client changes (document EVERYTHING in writing)
- Cash flow gap between paying suppliers and getting paid

**CIDB Grading:**
SA contractors need CIDB grading for government work:
- Grade 1-3: Small works (< R4m)
- Grade 4-6: Medium works (R4m-R40m)
- Grade 7-9: Large works (R40m+)
Higher grade = bigger projects = more revenue potential"""
    },

    # ============================================================
    # PROFESSIONAL SERVICES
    # ============================================================

    "professional_services_intel": {
        "keywords": ["professional", "consultant", "lawyer", "attorney", "accountant", "rekenmeester",
                     "prokureur", "engineer", "ingenieur", "architect", "argitek", "advisor",
                     "consulting", "firm", "practice", "firma", "praktyk", "hourly rate"],
        "title": "Professional Services Intelligence",
        "content": """Specific intelligence for professional service firms:

**Key Metrics:**
- Utilization rate = billable_hours / available_hours × 100
  → Target: 65-75% for senior, 80-85% for junior
- Effective hourly rate = total_revenue / total_billed_hours
- Revenue per employee (benchmark against industry)
- WIP (Work in Progress) aging — unbilled work is risk
- Collection rate = collected / billed × 100 (target: >95%)

**Billing Models:**
- Time-based: Track EVERY hour, bill at agreed rate
- Fixed fee: Quote upfront, manage scope tightly
- Retainer: Monthly fixed fee for ongoing work (best for cash flow!)
- Success fee: % of outcome (legal, consulting)
- Value-based: Price based on value delivered, not time spent

**WIP Management (biggest profit leak):**
"Jy het R180k in unbilled WIP ouer as 30 dae. Dis werk wat klaar 
gedoen is maar nog nie gefaktureer is nie. Bill dit VANDAG."

**Staff Leverage:**
The leverage model drives profitability:
- Senior does 1 hour of high-value work (billed at R2,000/hr)
- Junior does 5 hours of support work (billed at R600/hr)
- Total billed: R5,000. Cost: R1,200. Margin: 76%
If senior does ALL work: billed R5,000 but took 4 hours = R8,000 cost

**Smart Insights:**
"Jou top 3 kliënte genereer 65% van revenue maar vat 80% van jou tyd.
Kliënt B betaal R200/hr effektief (baie tyd in meetings) terwyl 
Kliënt D betaal R850/hr effektief. Grow more Kliënt-D-types."

**Growth Strategies:**
- Productize services (fixed price packages)
- Create templates and systems to reduce time per engagement
- Hire junior staff to leverage your expertise
- Recurring retainers > once-off projects (predictable revenue)
- Thought leadership: blog, LinkedIn, speaking (marketing is free)"""
    },

    # ============================================================
    # AGRICULTURE / FARMING
    # ============================================================

    "agriculture_farming_intel": {
        "keywords": ["farm", "farming", "agriculture", "plaas", "boerdery", "crop", "livestock",
                     "cattle", "bees", "vee", "oes", "harvest", "irrigation", "besproeiing",
                     "feed", "voer", "fertilizer", "kunsmis", "tractor"],
        "title": "Agriculture & Farming Intelligence",
        "content": """Specific intelligence for agricultural businesses:

**Key Metrics:**
- Yield per hectare (compare to regional averages)
- Cost per kg/ton produced
- Feed conversion ratio (livestock: kg feed per kg weight gain)
- Water usage per hectare (efficiency)
- Input cost as % of revenue (seed, fertilizer, chemicals, feed)

**Cost Categories to Track:**
- Seeds/plants/livestock purchases
- Fertilizer and chemicals
- Feed and supplements
- Fuel and diesel
- Water/irrigation
- Labour (permanent + seasonal)
- Equipment maintenance and depreciation
- Insurance (crop, livestock, equipment)
- Transport to market
- Land lease/bond repayment

**Seasonal Cash Flow (crop farming):**
Big expense months: planting season (inputs), harvest (labour, transport)
Revenue months: post-harvest (often 1-2 concentrated months)
GAP: 6-8 months between planting expense and harvest revenue
Solution: Production loans, forward contracts, diversify crops

**Livestock Specific:**
- Track cost per animal (purchase + feed + vet = total investment)
- Know break-even weight/age for selling
- Mortality rate (target: <3% cattle, <5% sheep, <8% poultry)
- Reproduction rate (calf % per cow per year)

**Smart Insights:**
"Jou mielies yield 4.2 ton/ha maar die streek gemiddeld is 5.8 ton/ha.
Moontlike oorsake: grond pH, besproeiing timing, saad variëteit.
By huidige pryse = R16k/ha verlore inkomste."

"Voerkoste het 22% gestyg in 6 maande. Oorweeg: 
eie voer meng (spaar 15-20%), bulk aankope, alternatiewe grondstowwe."

**Tax Benefits for Farmers:**
- Development expenditure (dams, fences, boreholes): Section 11(a)
- Soil conservation: tax deductible
- Drought relief: special provisions
- Livestock: special valuation rules
- Fuel rebate: claim back diesel levies"""
    },

    # ============================================================
    # MANUFACTURING
    # ============================================================

    "manufacturing_intel": {
        "keywords": ["manufacturing", "factory", "fabriek", "production", "produksie", "assembly",
                     "vervaardiging", "output", "machine", "masjien", "production line", "OEE",
                     "quality", "kwaliteit", "reject", "defect"],
        "title": "Manufacturing Intelligence",
        "content": """Specific intelligence for manufacturing businesses:

**Key Metrics:**
- OEE (Overall Equipment Effectiveness) = Availability × Performance × Quality
  → World class: >85% | Good: 70-85% | Needs work: <70%
- Production cost per unit
- Defect/reject rate (target: <2%)
- Lead time: order to delivery
- Capacity utilization = actual_output / max_possible_output × 100

**Cost Structure:**
- Raw materials: typically 40-60% of cost
- Direct labour: 15-25%
- Overhead (rent, electricity, depreciation): 15-25%
- Packaging and logistics: 5-10%

**Efficiency Analysis:**
"Machine A het 45 minute downtime per dag vir setup changes. 
By R800/uur production value = R600/dag verlore. Invest R15k in 
quick-change tooling → payback in 25 dae."

"Reject rate op Line 2 het van 1.5% na 4.2% gestyg hierdie maand.
Dis R28k aan vermorsde materiaal. Check: tool wear, raw material 
quality change, new operator training."

**Inventory Management:**
- Raw materials: JIT (Just in Time) where possible
- WIP (Work in Progress): minimize — faster throughput = less WIP
- Finished goods: make to order > make to stock (less risk)
- Safety stock on critical raw materials (especially imported)

**Load Shedding Impact (SA specific):**
- Generator fuel cost per hour of load shedding
- Production loss per hour
- Solution: Solar + battery for continuous production
- Some manufacturers shift to night production (lower tariffs)

**Growth Strategies:**
- Contract manufacturing for other brands
- Export (weak Rand = competitive advantage)
- Automation of repetitive tasks
- Vertical integration (make your own inputs)"""
    },

    # ============================================================
    # MEDICAL / HEALTH / PHARMACY
    # ============================================================

    "medical_health_intel": {
        "keywords": ["medical", "doctor", "dokter", "dentist", "tandarts", "pharmacy", "apteek",
                     "health", "gesondheid", "clinic", "kliniek", "practice", "patient", "pasiënt",
                     "dispensing", "optometrist", "physio", "chiro", "vet", "veearts"],
        "title": "Medical Practice & Health Business Intelligence",
        "content": """Specific intelligence for medical/health businesses:

**Key Metrics:**
- Revenue per patient visit
- Patients per day per practitioner
- New vs returning patient ratio (target: 70%+ returning)
- No-show rate (target: <10%, industry avg 15-20%)
- Average debtor days (medical aids typically 30-45 days)

**Medical Aid Billing:**
- Track claim rejection rate (target: <5%)
- Days to payment by medical aid scheme
- Gap payments vs medical aid rates
- Top rejection reasons (fix these to improve cash flow!)

**Practice Efficiency:**
"Dr. van Niekerk sien 18 pasiënte per dag, Dr. Smith sien 12. 
Both work same hours. Is Smith spending more time per patient 
(good for quality) or is there scheduling inefficiency?"

"Jou no-show rate is 22% — dis R35k/maand in verlore inkomste.
Implement: SMS reminders (48hr + 2hr before), cancellation fee policy,
waiting list to fill cancellations."

**Pharmacy Specific:**
- Script vs OTC ratio (scripts = steady, OTC = impulse)
- Generic vs branded dispensing ratio (generics = higher margin)
- SEP (Single Exit Price) compliance
- Schedule 0-6 stock management and compliance
- Expiry date tracking (write off expired stock)

**Cost Management:**
- Staff: typically 35-45% of revenue (receptionist, nurses, admin)
- Consumables: track per procedure
- Rent: medical rooms at premium rates
- Equipment: depreciation + maintenance contracts
- Compliance costs: HPCSA, pharmacy council, radiation control

**Growth Strategies:**
- Extended hours / Saturday practice
- Allied health services (physio, dietician, psychologist = more revenue per patient)
- Chronic medication management programs
- Telemedicine/virtual consultations
- Wellness packages for corporates"""
    },

    # ============================================================
    # BEAUTY / SALON / SPA
    # ============================================================

    "beauty_salon_intel": {
        "keywords": ["salon", "beauty", "hair", "hairdresser", "spa", "nails", "naels",
                     "skoonheid", "massage", "facial", "barber", "barbier", "treatment",
                     "stylist", "wax", "lash", "brow", "makeup"],
        "title": "Beauty Salon & Spa Intelligence",
        "content": """Specific intelligence for beauty/salon/spa businesses:

**Key Metrics:**
- Revenue per stylist/therapist per day
- Chair/bed utilization = booked_hours / available_hours × 100 (target: 75-85%)
- Average ticket value (push add-on services)
- Retail as % of total revenue (target: 15-25%)
- Client retention rate (target: >70%)
- Rebooking rate at checkout (target: >50%)

**Service Mix Optimization:**
Track profitability per service type:
- Time taken vs price charged = effective hourly rate
- Product cost per service
- Which services have waiting lists? (increase price)
- Which are always empty? (promote or drop)

**Staff Models:**
- Commission: 30-50% of service revenue to stylist (SA norm: 35-45%)
- Chair rental: Fixed rent, stylist keeps 100% (less risk for owner)
- Salary + bonus: Fixed base + % for hitting targets

**Retail Sales (often ignored gold mine):**
"Jou retail is net 6% van revenue — target is 20%. 
Every client who gets a hair treatment should leave with 
the RIGHT shampoo/conditioner. Train staff to recommend, not sell."

**Smart Insights:**
"Saturday is 100% booked but Wednesday is 40%. Offer 20% off 
weekday appointments → fills chairs that otherwise earn R0."

"Jou top stylist generates R85k/month but jou bottom stylist R22k. 
Cost is similar. Invest in training for bottom performers, 
or restructure their commission to incentivize."

**Client Retention:**
- Birthday specials (auto-message)
- "We miss you" after 6 weeks no visit
- Loyalty card (every 10th visit = free treatment)
- Referral discount (friend gets 15% off, you get R100 credit)
- Before/after photos (with permission) for social media

**Growth Strategies:**
- Online booking system (reduces phone time + no-shows)
- Package deals (buy 5 treatments, get 6th free)
- Bridal/event packages
- Product subscription boxes
- Collaborate with local businesses (gym, boutique)"""
    },

    # ============================================================
    # FOOD / BAKERY / CATERING
    # ============================================================

    "food_bakery_catering_intel": {
        "keywords": ["bakery", "bakkery", "catering", "spyseniering", "food production", "cake",
                     "koek", "deli", "takeaway", "wegneem", "coffee shop", "koffiewinkel",
                     "fast food", "food truck", "meals", "lunch"],
        "title": "Food Production, Bakery & Catering Intelligence",
        "content": """Specific intelligence for food production/bakery/catering:

**Key Metrics:**
- Food cost %: Target 28-35% for prepared food
- Revenue per labour hour
- Waste % of purchases (target: <5%)
- Average order value
- Orders per day (track daily trend)

**Recipe Costing (ESSENTIAL):**
For every item you sell, know:
- Exact ingredient cost per portion
- Labour time to prepare
- Packaging cost
- Total cost vs selling price = margin
- Update when ingredient prices change!

**Waste Management:**
Track 3 types of waste:
1. Over-production (made too much) → forecast better
2. Spoilage (expired before use) → order fresh, more often
3. Trim waste (peels, bones) → can you use them? Stock, compost?

"Jy gooi gemiddeld R4k per week aan kos weg. Dis R16k/maand!
Top waste items: bread (overbake by 20%), salad (spoils by Wednesday).
Reduce bread batch by 20%, make salad to order."

**Catering Specific:**
- Quote per head (know your minimum to cover costs)
- Equipment hire vs own (break-even at X events per month)
- Staff: permanent core team + casual for events
- Transport cost per event (distance, vehicle)
- Deposit policy: 50% upfront, balance before event

**Bakery Specific:**
- Batch costing: cost per batch ÷ items per batch = cost per item
- Optimal bake schedule (most popular items fresh for morning rush)
- Day-old discount strategy (sell at 50% vs throw away)
- Seasonal items (hot cross buns, Christmas cakes = high margin)

**Growth Strategies:**
- Corporate lunch delivery contracts (daily recurring revenue!)
- Wedding/event cake portfolio
- Online ordering for collection
- Wholesale to local shops/restaurants
- Subscription boxes (weekly bread/treat delivery)
- Cooking classes/workshops (extra revenue + marketing)"""
    },

    # ============================================================
    # WHOLESALE / DISTRIBUTION
    # ============================================================

    "wholesale_distribution_intel": {
        "keywords": ["wholesale", "groothandel", "distribution", "verspreiding", "distributor",
                     "bulk", "trade", "reseller", "supply chain", "warehouse", "pakhuis"],
        "title": "Wholesale & Distribution Intelligence",
        "content": """Specific intelligence for wholesale and distribution:

**Key Metrics:**
- Gross margin: typically 10-25% (lower than retail, higher volume)
- Inventory turnover: target 8-12x per year (stock must MOVE)
- Fill rate = orders_fulfilled_complete / total_orders × 100 (target: >95%)
- Delivery accuracy and on-time rate
- Average order value (bigger orders = more efficient)
- Warehouse space utilization

**Margin Management:**
Wholesale margins are thin — every % matters:
- Volume-based pricing tiers (buy more = cheaper per unit)
- Mix management: push higher-margin products
- Drop unprofitable lines (if margin < 8% and low volume = cut it)
- Negotiate better buy prices as YOUR volumes grow

**Warehouse Efficiency:**
- ABC analysis: A items (top 20% by revenue) in easiest access spots
- Pick-pack time per order (track and optimize)
- Returns processing time and cost
- Damaged goods rate (handling, storage issues)

**Smart Insights:**
"Jou top 50 products maak 75% van revenue. But jy hou 2,000 SKUs.
Die bottom 1,000 SKUs maak net 5% van revenue maar vat 40% van 
warehouse space. Prune aggressively."

"Delivery cost per order: R180. Minimum order: R500. 
Margin on R500 order: R75. You're LOSING R105 per small order!
Set minimum order at R1,500 or add delivery fee for small orders."

**Distribution Strategies:**
- Route optimization (deliver by area, not by order time)
- Minimum order values (protect margin)
- Pre-order system (know tomorrow's deliveries today)
- Hub model: central warehouse + regional mini-depots
- Cross-docking: receive and ship same day (no storage needed)"""
    },

    # ============================================================
    # TRANSPORT / LOGISTICS
    # ============================================================

    "transport_logistics_intel": {
        "keywords": ["transport", "logistics", "logistiek", "trucking", "vragmotor", "delivery",
                     "aflewering", "fleet", "vloot", "courier", "koerier", "freight", "vrag",
                     "driver", "bestuurder", "fuel", "brandstof", "route"],
        "title": "Transport & Logistics Intelligence",
        "content": """Specific intelligence for transport and logistics:

**Key Metrics:**
- Revenue per km (must exceed cost per km!)
- Cost per km = (fuel + tyres + maintenance + insurance + depreciation + driver cost) / total km
- Vehicle utilization = loaded_km / total_km × 100 (target: >70%)
- On-time delivery rate (target: >95%)
- Fuel consumption: litres per 100km per vehicle

**Cost Breakdown (typical heavy vehicle):**
- Fuel: 35-40% of total cost
- Driver: 20-25%
- Tyres: 8-12%
- Maintenance: 10-15%
- Insurance: 5-8%
- Depreciation: 10-15%
- Tolls and permits: 3-5%

**Fuel Management (biggest controllable cost):**
- Track litres per 100km per vehicle per driver
- Variance between drivers = driving style/route choice
- Fuel card reconciliation (detect fraud)
- Optimal speed: 80-85km/h vs 100km/h saves 15-20% fuel

**Smart Insights:**
"Vragmotor 3 gebruik 42L/100km maar die vloot gemiddeld is 35L/100km.
By R24/liter en 15,000km/maand = R25k ekstra brandstof per maand.
Check: engine condition, tyre pressure, driving behaviour, routes."

"Jou voertuie ry 30% leeg terug. Dis 'deadhead' kilometres.
Vind return loads — selfs teen lae tarief is dit beter as leeg ry."

**Fleet Management:**
- Service schedules: track by km, not just time
- Tyre management: rotation schedule, retread vs new analysis
- Vehicle replacement: when maintenance cost > replacement financing
- Driver performance: fuel, speed, idle time, on-time
- Load optimization: maximize payload per trip

**Compliance:**
- Roadworthy certificates
- Operating permits (cross-border)
- Driver hours (fatigue management)
- Overload monitoring (fines are massive)
- e-Toll / toll management"""
    },

    # ============================================================
    # IT / TECH SERVICES
    # ============================================================

    "it_tech_services_intel": {
        "keywords": ["it", "tech", "technology", "software", "developer", "ontwikkelaar",
                     "msp", "managed service", "support", "web", "app", "hosting",
                     "cybersecurity", "network", "netwerk", "computer", "rekenaar"],
        "title": "IT & Tech Services Intelligence",
        "content": """Specific intelligence for IT and tech service businesses:

**Key Metrics:**
- MRR (Monthly Recurring Revenue) — most important! Target: >60% of total revenue
- Churn rate = customers_lost / total_customers per month (target: <3%)
- Revenue per employee (benchmark: R80k-R150k/month)
- Support ticket resolution time
- Customer satisfaction score
- Utilization rate for billable staff

**Revenue Models (best to worst for cash flow):**
1. Managed Services (monthly retainer) ★★★★★
2. SaaS/Hosting subscriptions ★★★★★
3. Retainer agreements ★★★★
4. Project-based work ★★★
5. Break-fix (call when broken) ★★ (worst — unpredictable)

**Smart Insights:**
"65% van jou revenue is project-based (unpredictable). Shift to 
managed services: convert jou top 20 clients to R3-5k/m contracts.
R80k in nuwe MRR = guaranteed income elke maand."

"Jou gemiddelde support ticket neem 45 minute. Die top 5 repeat 
issues maak 40% van tickets. Create self-service KB/FAQ → reduce 
ticket volume by 30% → free up staff for billable work."

**Pricing Strategies:**
- Per user per month (scalable with client growth)
- Tiered packages (Bronze/Silver/Gold)
- Base + usage model
- Include hardware lifecycle management
- Quarterly business reviews as value-add

**Growth Strategies:**
- Cybersecurity services (every business needs it, high margin)
- Cloud migration services
- Compliance consulting (POPIA, ISO)
- Training and workshops
- White-label services for other IT companies"""
    },

    # ============================================================
    # GYM / FITNESS
    # ============================================================

    "gym_fitness_intel": {
        "keywords": ["gym", "fitness", "exercise", "oefening", "crossfit", "yoga", "pilates",
                     "personal trainer", "membership", "lidmaatskap", "studio", "martial arts",
                     "swimming", "sport"],
        "title": "Gym & Fitness Business Intelligence",
        "content": """Specific intelligence for gym and fitness businesses:

**Key Metrics:**
- Member retention rate (target: >75% annual)
- Revenue per m² (benchmark your space productivity)
- Average revenue per member per month
- Utilization: peak vs off-peak capacity
- New member acquisition cost
- Attrition rate = cancellations / total_members per month (target: <5%)

**Revenue Streams:**
1. Memberships (core — target 70% of revenue)
2. Personal training sessions (high margin)
3. Group classes (efficient — 1 trainer, 20 members)
4. Retail (supplements, apparel, gear)
5. Smoothie/juice bar
6. Equipment hire/short courses

**Membership Optimization:**
"Jy het 450 lede maar gym peak capacity is 80 mense. 
Monday 6pm: 75 mense (94% capacity — uncomfortable)
Tuesday 2pm: 12 mense (15% capacity — wasted space)
Off-peak membership at 30% discount would fill dead hours."

**Retention (waar die geld REGTIG is):**
Getting a new member costs 5-7x more than keeping one.
- Track members who haven't visited in 2+ weeks → contact them
- 30-day check-in for new members (most quit in first 60 days)
- Community building (group challenges, social events)
- Milestone celebrations (100th visit, 1 year anniversary)

**Smart Insights:**
"Jy verloor gemiddeld 25 lede per maand maar kry 30 nuwe lede.
Net growth is 5, maar those 25 lost members = R37k/month lost revenue.
As jy retention verbeter van 72% na 82%, dis R120k extra per jaar."

**Seasonal Patterns:**
- January: BIGGEST signup month (New Year resolutions)
- Feb-Mar: 40% of Jan signups cancel (normal attrition)
- Sep-Oct: Second wave (pre-summer body)
- Dec: Quiet month (holidays)
- Key: Lock members into annual contracts in Jan/Sep"""
    },

    # ============================================================
    # EDUCATION / TRAINING
    # ============================================================

    "education_training_intel": {
        "keywords": ["school", "skool", "training", "opleiding", "education", "onderwys", "tutor",
                     "course", "kursus", "crèche", "creche", "daycare", "pre-school", "college",
                     "academy", "akademie", "driving school", "ryskoool"],
        "title": "Education & Training Business Intelligence",
        "content": """Specific intelligence for education/training businesses:

**Key Metrics:**
- Enrollment rate = enrolled / capacity × 100 (target: >85%)
- Revenue per student per month
- Student retention / completion rate
- Teacher to student ratio
- Cost per student (total costs / enrolled students)
- Dropout rate (and at which point they drop — fix that point)

**Revenue Models:**
- Term fees (quarterly, paid upfront)
- Monthly fees (debit order — best for cash flow)
- Course fees (once-off per course)
- Registration/admin fee (once-off, contributes to fixed costs)
- Extra: transport, meals, aftercare, extra-murals

**Cash Flow Challenge:**
Education is seasonal:
- Revenue: Consistent during school term, drops in holidays
- Expenses: Staff salaries continue during holidays
- Solution: Annual fees divided by 12 (include holidays)
- NEVER let parents fall behind — strict debit order policy

**Smart Insights:**
"Jy het 180 kinders maar capacity is 220. Dis 18% leë plekke = 
R66k/maand verlore revenue. Marketing push needed — open day, 
referral discount (each parent who refers = 1 month free)."

"6 ouers is 3+ maande agterstallig = R54k outstanding.
By 90+ days is collection probability 40%. Act NOW — 
suspend childcare until arrangements are made."

**Cost Management:**
- Staff: 55-65% of revenue (biggest cost)
- Rent/facilities: 10-15%
- Educational materials: 5-8%
- Food/catering: 8-12% (if meals provided)
- Insurance and compliance: 3-5%

**Growth Strategies:**
- Holiday programs (revenue during quiet periods)
- After-school care (parents need it, recurring revenue)
- Online/hybrid courses (scale without space)
- Corporate training contracts
- SETA-accredited courses (employer-funded via SDL)"""
    },

    # ============================================================
    # PROPERTY / ESTATE AGENT
    # ============================================================

    "property_estate_intel": {
        "keywords": ["property", "eiendom", "estate agent", "real estate", "makelaars", "rental agent",
                     "letting", "verhuring", "commission", "kommissie", "listing", "mandate",
                     "bond", "mortgage", "transfer"],
        "title": "Property & Estate Agency Intelligence",
        "content": """Specific intelligence for property/estate agency businesses:

**Key Metrics:**
- Listings to sales conversion rate (target: 60-70%)
- Average days on market (lower = better pricing/marketing)
- Commission per agent per month
- Rental portfolio size and management fee income
- Average sale price (track trend — indicates market)
- Lead to listing conversion

**Revenue Streams:**
1. Sales commission: 5-7.5% of sale price (split with agency)
   - Agent typically gets 40-60% of commission
2. Rental management: 8-12% of monthly rent (recurring!)
3. Letting fee: 1 month's rent (once-off per new tenant)
4. Admin fees
5. BEE compliance consulting for property investors

**Sales vs Rental Balance:**
"Jou revenue is 85% from sales, 15% from rentals. 
Sales are feast-or-famine. Grow rental portfolio to 40% — 
gives you predictable base income while sales fluctuate."

**Agent Performance:**
"Agent Janine: 4 sales this month (R180k commission earned)
Agent Marco: 1 sale (R35k commission earned)
Both have 12 listings. Janine converts 33%, Marco 8%.
Marco needs training on closing or better lead quality."

**Rental Portfolio Intelligence:**
- Track tenant payment performance (by property)
- Arrears aging (30/60/90)
- Vacancy rate: target <5% (every empty month = lost income)
- Maintenance cost as % of rental income (target: <10%)
- Lease renewal rate (target: >75%)

**Market Intelligence:**
- Track average price per m² in your area
- Days on market trending up = cooling market → adjust pricing
- New developments in area = competition but also activity
- Interest rate changes directly affect buyer affordability
- Transfer duty rates affect total cost for buyers

**Growth Strategies:**
- Build rental portfolio (annuity income)
- Property management (not just finding tenants — full management)
- Development consulting
- BEE property investment consulting
- Airbnb management for property owners"""
    },

    # ============================================================
    # E-COMMERCE / ONLINE STORE
    # ============================================================

    "ecommerce_online_intel": {
        "keywords": ["ecommerce", "online", "aanlyn", "website", "webwerf", "shopify", "woocommerce",
                     "online store", "digital", "social media", "facebook", "instagram", "marketplace",
                     "takealot", "shipping", "versending"],
        "title": "E-Commerce & Online Business Intelligence",
        "content": """Specific intelligence for e-commerce and online businesses:

**Key Metrics:**
- Conversion rate = orders / website_visitors × 100 (target: 2-4%)
- Average order value (AOV)
- Customer acquisition cost (CAC) = marketing_spend / new_customers
- Customer lifetime value (CLV) — must be > 3× CAC to be sustainable
- Cart abandonment rate (industry avg: 70% — reduce this!)
- Return rate (target: <10%)

**Cost Structure:**
- Product cost: 40-50%
- Shipping/delivery: 8-15%
- Payment processing (credit card): 2.5-3.5%
- Platform fees (Takealot 15%, Shopify R500+/m)
- Marketing/ads: 10-20%
- Returns processing: 3-5%
- Packaging: 2-5%

**Channel Strategy (SA):**
1. Own website (best margin, you own the data)
2. Takealot (biggest traffic, 15% commission)
3. Facebook/Instagram Shop (social selling)
4. WhatsApp Business (catalogue + chat to sell)
5. Bob Shop, Loot, Superbalist (category-specific)

**Smart Insights:**
"Jou conversion rate is 1.2% — onder die 2-4% target.
Top reasons visitors leave: slow site (3+ seconds load),
no free shipping option, complicated checkout. Fix these 3 things
and double your revenue without more traffic."

"You spend R15k/month on Facebook ads getting 100 customers.
CAC = R150. Average first order = R350, margin R105.
Dis 'n verlies van R45 per nuwe kliënt. BUT if they reorder 
3+ times, CLV = R1,050 margin. Focus on repeat purchase rate."

**Delivery (SA specific):**
- Courier Guy / Pudo / Aramex / DSV (compare rates by zone)
- Free shipping threshold (e.g., free over R500 — increases AOV)
- Collection points reduce last-mile cost
- Same-day delivery in metro areas (competitive advantage)

**Growth Strategies:**
- Email marketing (cheapest channel, best ROI)
- Loyalty/points program
- Subscription boxes (recurring!)
- Bundle deals (increase AOV)
- Influencer partnerships
- SEO for organic Google traffic (free long-term)"""
    },

    # ============================================================
    # CLEANING / SECURITY / FACILITIES
    # ============================================================

    "cleaning_security_facilities_intel": {
        "keywords": ["cleaning", "skoonmaak", "security", "sekuriteit", "facilities", "janitorial",
                     "guard", "wag", "pest control", "plaagbeheer", "garden", "tuin", "landscaping",
                     "maintenance", "onderhoud", "hygiene"],
        "title": "Cleaning, Security & Facilities Intelligence",
        "content": """Specific intelligence for cleaning/security/facilities businesses:

**Key Metrics:**
- Revenue per contract per month
- Labour cost as % of contract value (target: 55-65%)
- Gross margin per contract (target: 25-35%)
- Contract retention rate (target: >90%)
- Staff turnover rate (high turnover = costly retraining)
- Client satisfaction score

**Pricing Models:**
- Monthly contract (best — predictable, recurring)
- Per clean/per visit (less predictable)
- Per m² (transparent, easy to scale)
- Time and materials (emergency/ad-hoc)

**Labour Management (biggest challenge):**
"Die skoonmaak industrie het ±40% staff turnover per jaar.
Elke replacement cost: R3k-R5k (recruitment, training, uniform).
50 staff × 40% turnover = 20 replacements = R80k/jaar!
Invest in better wages/conditions → reduce turnover → save money."

**Contract Profitability Analysis:**
"Kontrak A: R25k/maand maar 8 staff nodig = R18k labour = 28% margin ✅
Kontrak B: R15k/maand maar 6 staff nodig = R13k labour = 13% margin ❌
Renegotiate Kontrak B of let it expire."

**Security Specific:**
- Guard costs: salary + equipment + transport + supervision
- Technology supplement: CCTV, access control, alarm monitoring
- Response time tracking (SLA compliance)
- Incident reporting and trending

**Growth Strategies:**
- Bundle services (cleaning + security + garden = full facilities package)
- Specialization: biohazard, industrial, post-construction cleaning
- Technology: GPS tracking, electronic check-in at sites
- Government tenders (need BEE compliance)
- Contract escalation clauses (annual CPI increase)"""
    },

}


def get_relevant_pulse_knowledge(analysis_type: str, business_data: dict = None, max_chunks: int = 3) -> list:
    """
    RAG function for Pulse Intelligence.
    
    analysis_type: What kind of analysis is needed
    business_data: Optional dict with business context for smarter matching
    max_chunks: Max number of knowledge chunks to return
    """
    if not analysis_type:
        return []
    
    msg_lower = analysis_type.lower()
    scored = []
    
    for key, entry in PULSE_KNOWLEDGE.items():
        score = 0
        for keyword in entry["keywords"]:
            if keyword.lower() in msg_lower:
                score += len(keyword.split())
        
        if score > 0:
            scored.append((score, key, entry))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    
    results = []
    for score, key, entry in scored[:max_chunks]:
        results.append({
            "title": entry["title"],
            "content": entry["content"]
        })
    
    return results


def format_pulse_knowledge(chunks: list) -> str:
    """Format Pulse knowledge chunks for injection into analysis prompt."""
    if not chunks:
        return ""
    
    sections = []
    for chunk in chunks:
        sections.append(f"### {chunk['title']}\n{chunk['content']}")
    
    return "\n\n---\n\n## ANALYSIS METHODOLOGY\n" + "\n\n".join(sections)


def get_full_pulse_scan_knowledge() -> list:
    """
    For nightly/weekly full business scan, return the KEY chunks needed.
    Not all chunks - just the ones for automated scanning.
    """
    scan_keys = [
        "dead_stock_detection",
        "cash_flow_forecast", 
        "debtor_risk_analysis",
        "margin_analysis",
        "business_risk_alerts",
        "stock_reorder_intelligence",
    ]
    
    results = []
    for key in scan_keys:
        if key in PULSE_KNOWLEDGE:
            entry = PULSE_KNOWLEDGE[key]
            results.append({
                "title": entry["title"],
                "content": entry["content"]
            })
    
    return results


# Quick test
if __name__ == "__main__":
    print(f"Total Pulse knowledge chunks: {len(PULSE_KNOWLEDGE)}")
    total_words = sum(len(v['content'].split()) for v in PULSE_KNOWLEDGE.values())
    avg = total_words // len(PULSE_KNOWLEDGE)
    print(f"Total words: {total_words}")
    print(f"Avg per chunk: {avg}")
    print(f"3 chunks per analysis: ~{3*avg} words (vs full {total_words})")
    print(f"RAG saves: {100 - (3*avg*100//total_words)}% prompt space")
    print()
    
    test_queries = [
        "dead stock analysis",
        "hoe lyk my cash flow?",
        "which customers are we losing?",
        "is my pub food cost too high?",
        "B&B occupancy is low",
        "wat is my risk areas?",
        "how can I grow the business?",
        "supplier prices going up",
        "staff costs too high",
        "hardware store margins",
        "tax planning before year end",
        "December seasonal preparation",
        "dooie stock en space vir B&B kamers",
    ]
    
    for q in test_queries:
        chunks = get_relevant_pulse_knowledge(q, max_chunks=2)
        titles = [c['title'] for c in chunks]
        print(f"Q: {q}")
        print(f"  → {titles}")
        print()
