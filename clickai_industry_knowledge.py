"""
ClickAI Industry Knowledge — Business-type intelligence for Zane
═════════════════════════════════════════════════════════════════
When a user registers and says "I'm a salon" or "I run a guesthouse",
Zane immediately knows: typical costs, expected margins, red flags,
GL categories they'll use most, and seasonal patterns.

Each chunk = one industry/business type.
Zane gets max 2 chunks — matched to the business type or user query.
"""

INDUSTRY_CHUNKS = [
    # ═══ RETAIL & TRADE ═══
    {
        "keywords": ["HARDWARE", "HARDWARE STORE", "BUILDING SUPPLIES", "BOUMATERIAAL", "STEEL", "STAINLESS"],
        "context": "Hardware/building supply store. Target gross margin: 25-35%. "
                   "Biggest costs: stock (60-70% of revenue), rent, staff, delivery vehicle. "
                   "Key GL categories: Stock Purchases — Hardware, Delivery/Freight, Vehicle expenses. "
                   "Watch for: slow-moving stock (steel rusts!), credit sales aging > 30 days, "
                   "theft/shrinkage (high-value small items). Seasonal peak: Sept-Dec (building season). "
                   "Tip: track stock turnover — hardware should turn every 45-60 days. "
                   "Cash flow killer: large orders on credit while waiting for customer payment."
    },
    {
        "keywords": ["GENERAL DEALER", "SPAZA", "TUCK SHOP", "MINI MARKET", "CONVENIENCE STORE"],
        "context": "General dealer/convenience store. Target gross margin: 20-30%. "
                   "Biggest costs: stock (70-80%), rent, electricity (fridges run 24/7). "
                   "Key GL: Stock Purchases — General, Electricity, Rent. "
                   "Watch for: expired stock write-offs, cash handling (theft), electricity costs eating margin. "
                   "Tip: bread/milk/eggs are loss-leaders — profit is on cold drinks, snacks, airtime. "
                   "Stock daily, don't overbuy perishables. Cash sales dominant — reconcile daily."
    },
    {
        "keywords": ["CLOTHING", "FASHION", "BOUTIQUE", "KLERE"],
        "context": "Clothing/fashion retail. Target gross margin: 50-65% (keystone markup). "
                   "Biggest costs: stock (40-50%), rent (prime location essential), staff. "
                   "Key GL: Stock Purchases — General, Rent, Advertising — Online/Social Media. "
                   "Watch for: seasonal stock that doesn't sell (markdowns destroy margin), "
                   "high rent in malls, returns policy costs. Peak: Nov-Dec, Easter. "
                   "Tip: track sell-through rate per item. If it hasn't sold in 60 days, mark it down."
    },

    # ═══ FOOD & BEVERAGE ═══
    {
        "keywords": ["RESTAURANT", "PUB", "BAR", "TAVERN", "EETPLEK", "KROEG"],
        "context": "Restaurant/pub. Target food cost: 28-35% of revenue. Liquor cost: 25-30%. "
                   "Target overall margin: 60-70% gross. "
                   "Biggest costs: stock — food & beverage (30-35%), staff (25-30%), rent, electricity. "
                   "Key GL: Stock Purchases — Food & Beverage, Stock Purchases — Liquor, Wages — Staff, "
                   "Electricity, Cleaning & Hygiene, DSTV/Streaming, Entertainment licence. "
                   "Watch for: food waste (track daily), overpouring on drinks, staff meals not recorded, "
                   "cash sales not rung up. DSTV is deductible for restaurants/pubs. "
                   "Tip: do weekly stock takes on liquor — biggest leakage point. "
                   "Licence: need liquor licence from provincial authority — non-compliance = criminal."
    },
    {
        "keywords": ["TAKEAWAY", "FAST FOOD", "FOOD TRUCK", "COFFEE SHOP", "CAFE", "BAKERY"],
        "context": "Takeaway/fast food/coffee shop. Target food cost: 25-32%. "
                   "Target gross margin: 65-75%. "
                   "Biggest costs: ingredients, packaging, rent, staff, electricity (fryers/ovens). "
                   "Key GL: Stock Purchases — Food & Beverage, Packaging Materials, Electricity, Wages. "
                   "Watch for: portion control (biggest profit leak), packaging costs creeping up, "
                   "Uber Eats/Mr D commissions eating margin (15-30%!). "
                   "Tip: delivery app commissions are a cost of sale — track separately. "
                   "Health certificate required from municipality — budget for annual renewal."
    },
    {
        "keywords": ["CATERING", "EVENTS", "FUNCTION", "SPYSENIERING"],
        "context": "Catering business. Target food cost: 25-30% per event. Target margin: 40-60%. "
                   "Biggest costs: ingredients (per event), casual staff, transport, equipment rental. "
                   "Key GL: Stock Purchases — Food & Beverage, Wages — Casual/Temp, Travel — Local, "
                   "Repairs — Equipment. Watch for: underquoting (include ALL costs: staff, transport, "
                   "setup, waste), deposit management (get 50% upfront). "
                   "Seasonal: Dec functions, Easter, corporate year-end. "
                   "Tip: track actual cost vs quoted cost per event to improve quoting accuracy."
    },

    # ═══ ACCOMMODATION ═══
    {
        "keywords": ["GUESTHOUSE", "B&B", "BED AND BREAKFAST", "GASTEHUIS", "LODGE", "AIRBNB"],
        "context": "Guesthouse/B&B. Target occupancy: 55-70% to break even, 70%+ profitable. "
                   "Target margin per room: 60-75% after cleaning & breakfast. "
                   "Biggest costs: rates & electricity (24/7), cleaning staff, breakfast food, "
                   "linen/laundry, DSTV (per room), WiFi, maintenance. "
                   "Key GL: Electricity, Water, Cleaning & Hygiene, Stock Purchases — Food, "
                   "DSTV/Streaming, Internet/WiFi, Garden & Grounds, Repairs — Building. "
                   "Watch for: electricity costs in winter (heating), maintenance backlog, "
                   "Booking.com commission (15-18%), seasonal lows (May-Aug in most areas). "
                   "TOURISM LEVY: register with tourism authority. Municipality may require zoning approval."
    },
    {
        "keywords": ["HOTEL", "HOSPITALITY", "ACCOMMODATION"],
        "context": "Hotel/large accommodation. Target occupancy: 60-75%. RevPAR (revenue per available room) "
                   "is the key metric — not just room rate. "
                   "Biggest costs: staff (40-45% of revenue — biggest cost!), rates, electricity, maintenance. "
                   "Key GL: Salaries, Wages, Electricity, Rates, Repairs — Building, Cleaning, "
                   "Laundry, Marketing. Watch for: staff costs exceeding 45%, maintenance backlog, "
                   "OTA commissions (Booking.com 15-18%). "
                   "Tip: direct bookings save 15% commission — invest in your own website and Google presence."
    },

    # ═══ SERVICES ═══
    {
        "keywords": ["SALON", "HAIR SALON", "BEAUTY", "HAIRDRESSER", "NAIL", "SPA", "SKOONHEID"],
        "context": "Hair/beauty salon. Target product cost: 10-15% of service revenue. "
                   "Target gross margin on products sold: 50-60%. Service margin: 70-85%. "
                   "Biggest costs: rent (location is everything), staff wages/commission, "
                   "stock (colour, products), electricity (dryers, ovens). "
                   "Key GL: Stock Purchases — General (colour/products), Rent, Wages — Staff, "
                   "Electricity, Advertising — Social Media. "
                   "Watch for: staff using products for non-paying clients, product expiry, "
                   "chair rental vs employment (SARS treats regular chair renters as employees). "
                   "Tip: retail product sales should be 15-20% of total revenue — push retail."
    },
    {
        "keywords": ["MECHANIC", "AUTO", "WORKSHOP", "PANEL BEATER", "MOTOR WERKTUIGKUNDIGE", "GARAGE"],
        "context": "Auto mechanic/workshop. Target parts markup: 25-40%. Labour rate: R450-R800/hour (2024). "
                   "Target gross margin: 50-65%. "
                   "Biggest costs: parts/stock, staff (qualified mechanics are expensive), "
                   "rent, tools & equipment, insurance (public liability critical). "
                   "Key GL: Stock Purchases — General (parts), Wages — Staff, Rent, "
                   "Small Tools & Consumables, Insurance — Public Liability. "
                   "Watch for: parts given to wrong jobs, warranty claims eating margin, "
                   "jobs taking longer than quoted (track hours per job). "
                   "Must register with MIOSA. Need proper waste disposal for oil/fluids."
    },
    {
        "keywords": ["PLUMBER", "PLUMBING", "LOODGIETER"],
        "context": "Plumbing business. Target callout margin: 55-70%. "
                   "Biggest costs: materials, vehicle (fuel, maintenance), tools, insurance. "
                   "Key GL: Stock Purchases — Plumbing, Fuel — Business Vehicle, Vehicle Repairs, "
                   "Small Tools, Insurance — Public Liability. "
                   "Watch for: underquoting emergency calls, vehicle costs eating profit, "
                   "stock on van not tracked (materials walk!). "
                   "Must be registered with IOPSA. Tip: charge for callout separately from materials."
    },
    {
        "keywords": ["ELECTRICIAN", "ELECTRICAL", "ELEKTRISIËN"],
        "context": "Electrical contractor. Target margin: 45-65%. "
                   "Biggest costs: materials (cable, DBs), vehicle, tools, compliance (COCs). "
                   "Key GL: Stock Purchases — Electrical, Fuel, Vehicle, Tools, Insurance, "
                   "Licence Fees (wireman's licence). "
                   "Watch for: copper price fluctuations affecting quotes, COC liability, "
                   "Eskom connection delays on new installations. "
                   "MUST have wireman's licence. COC (Certificate of Compliance) required — carries legal liability."
    },
    {
        "keywords": ["CONSTRUCTION", "BUILDING", "CONTRACTOR", "BOUWERK", "BUILDER"],
        "context": "Building/construction. Target margin: 15-25% on contract value. "
                   "Biggest costs: materials (50-60%), subcontractors (20-30%), labour, equipment hire. "
                   "Key GL: Stock Purchases — Hardware, Direct Labour, Wages — Casual/Temp, "
                   "Delivery/Freight, Small Tools, Insurance — Public Liability. "
                   "Watch for: underquoting (include waste factor 5-10%), payment delays from clients "
                   "(30-60 day wait is normal), subcontractor quality. "
                   "NHBRC registration required for residential builders. CIDB grading for government work. "
                   "Retention: clients hold back 5-10% for defects period — budget for this cash flow gap."
    },
    {
        "keywords": ["CLEANING", "CLEANING SERVICE", "SCHOONMAAK", "JANITORIAL"],
        "context": "Cleaning services. Target margin: 35-50%. "
                   "Biggest costs: staff (60-70%), chemicals/supplies, transport, equipment. "
                   "Key GL: Wages — Staff, Wages — Casual/Temp, Stock Purchases — Cleaning Supplies, "
                   "Fuel, Vehicle, Protective Clothing. "
                   "Watch for: staff reliability, chemical costs, transport between sites. "
                   "Tip: contract cleaning (monthly) is more stable than once-off. "
                   "UIF and COIDA compulsory for all cleaning staff — even part-time."
    },
    {
        "keywords": ["SECURITY", "GUARDING", "ARMED RESPONSE", "SEKURITEIT"],
        "context": "Security company. Target margin: 20-35% on guarding, 40-50% on installations. "
                   "Biggest costs: staff wages (70%+ for guarding), uniforms, radios, vehicle patrol costs. "
                   "Key GL: Wages — Staff, Protective Clothing/Uniforms, Vehicle expenses, "
                   "Insurance, Cellphone/Mobile (radios). "
                   "PSIRA registration COMPULSORY — both company and individual guards. "
                   "Watch for: overtime costs (security = long shifts), staff turnover, firearm licence compliance. "
                   "SARS: security uniforms are deductible for the employer."
    },

    # ═══ PROFESSIONAL SERVICES ═══
    {
        "keywords": ["ACCOUNTING", "BOOKKEEPING", "TAX PRACTITIONER", "REKENMEESTER"],
        "context": "Accounting/bookkeeping practice. Target margin: 60-75% (low overheads). "
                   "Biggest costs: staff (qualified staff expensive), software subscriptions, "
                   "professional body fees, PI insurance. "
                   "Key GL: Salaries, Software Subscription, Professional Body Membership, "
                   "Insurance — Public Liability (PI insurance), Training. "
                   "Watch for: fee creep (doing more work than quoted), debtors (clients delay paying), "
                   "CPD compliance costs. "
                   "Tax practitioner: must register with SARS as tax practitioner. Controlled by Tax Admin Act."
    },
    {
        "keywords": ["CONSULTANT", "CONSULTING", "FREELANCE", "VRYSKUT"],
        "context": "Consulting/freelance. Target margin: 65-85% (mostly time = money). "
                   "Biggest costs: mostly your time, plus laptop, cellphone, travel, PI insurance. "
                   "Key GL: Travel, Cellphone, Computer Equipment, Software Subscription, "
                   "Consulting Fees (if subcontracting). "
                   "Watch for: scope creep (track hours per project), irregular income (feast/famine), "
                   "not setting aside tax (provisional tax can be a shock). "
                   "Tip: provisional tax = save 30% of every invoice for tax. "
                   "If earning > R1m, must register for VAT."
    },
    {
        "keywords": ["ATTORNEY", "LEGAL PRACTICE", "LAW FIRM", "PROKUREUR"],
        "context": "Legal practice. Target billable rate: R1,500-R4,000/hour depending on seniority. "
                   "Target margin: 50-70%. Biggest costs: staff, rent (prestigious address), "
                   "professional insurance, trust account compliance. "
                   "Key GL: Salaries, Rent, Insurance — Public Liability, Professional Body Membership (LPC), "
                   "Legal research subscriptions. "
                   "Fidelity Fund certificate required annually. Trust account (s78 Banking Act) if handling client money. "
                   "Watch for: unbilled time, WIP (work in progress) aging, debtors exceeding 30 days."
    },
    {
        "keywords": ["MEDICAL", "DOCTOR", "DENTIST", "PRACTICE", "PHYSIOTHERAPIST", "DOKTER"],
        "context": "Medical/dental practice. Target margin: 50-65%. "
                   "Biggest costs: rent (good location), staff (receptionist, nurse), equipment (expensive!), "
                   "consumables, professional insurance, medical aid admin. "
                   "Key GL: Salaries, Rent, Stock Purchases (consumables), Computer Equipment, "
                   "Insurance — Public Liability (malpractice), Professional Body Membership (HPCSA). "
                   "Watch for: medical aid payment delays (60-90 days!), practice management software costs, "
                   "equipment depreciation (dental chairs, X-ray machines = R200k+). "
                   "HPCSA registration compulsory. Cannot advertise prices (ethical rules)."
    },

    # ═══ AGRICULTURE ═══
    {
        "keywords": ["FARM", "FARMING", "AGRICULTURE", "BOERDERY", "PLAAS", "CROP", "LIVESTOCK"],
        "context": "Farming/agriculture. Margins vary hugely by type: crops 15-30%, livestock 20-40%, "
                   "game farming 30-50%, citrus/fruit 25-40%. "
                   "Biggest costs: labour, fuel/diesel, fertiliser/feed, electricity (irrigation), equipment. "
                   "Key GL: Direct Labour, Fuel — Equipment, Stock Purchases — General (seed/feed/fertiliser), "
                   "Electricity, Repairs — Equipment/Machinery, Water. "
                   "Special tax rules: farming income can be spread over years (averaging), "
                   "development expenditure deductible (clearing, fencing, dams). "
                   "Diesel rebate available for farming vehicles/equipment. "
                   "VAT: farming is Category D (6-monthly filing). Livestock counted as trading stock."
    },

    # ═══ TRANSPORT & LOGISTICS ═══
    {
        "keywords": ["TRANSPORT", "TRUCKING", "LOGISTICS", "DELIVERY", "COURIER", "VERVOER", "HAULAGE", "FREIGHT"],
        "context": "Transport/logistics. Target margin: 15-25% (tight margins, high costs). "
                   "Biggest costs: fuel (30-40%), vehicle maintenance/tyres (15-20%), drivers (15-20%), insurance (3-5%). "
                   "Key GL: Fuel — Business Vehicle, Vehicle Repairs & Service, Tyres, "
                   "Vehicle Insurance, Wages — Staff (drivers), Tolls & Parking, Vehicle Licence. "
                   "Watch for: fuel theft/misuse, short-loading (ordered 36t, loaded 34t), tyre costs (R5k-R15k per truck tyre), "
                   "maintenance scheduling (breakdowns = lost revenue), overloading fines (R100-R150 per kg over). "
                   "Must have: COF annually, PrDP for drivers, operator registration, GPS tracking. "
                   "Cross-border: need C-BRTA permits per country. "
                   "Critical KPIs: fuel consumption per km per vehicle, empty running % (<30% target), "
                   "on-time delivery rate (>95%), vehicle utilisation (>85% of available days). "
                   "Tip: fuel is biggest controllable cost — track consumption per km per vehicle."
    },

    # ═══ TECHNOLOGY ═══
    {
        "keywords": ["IT", "SOFTWARE", "TECH", "DEVELOPMENT", "APP", "WEBSITE", "DIGITAL"],
        "context": "IT/software business. Target margin: 70-85% (low cost of goods). "
                   "Biggest costs: developer salaries (80% of costs), cloud hosting, software tools. "
                   "Key GL: Salaries — Management (developers), Software Subscription (AWS/Azure/tools), "
                   "Computer Equipment, Internet/WiFi, Advertising — Online. "
                   "Watch for: scope creep on projects, hosting costs growing with users, "
                   "SaaS revenue recognition (monthly vs annual). "
                   "R&D tax incentive: 150% deduction on qualifying R&D expenditure (s11D). "
                   "Tip: recurring revenue (SaaS) valued much higher than project revenue."
    },

    # ═══ MANUFACTURING ═══
    {
        "keywords": ["MANUFACTURING", "FACTORY", "PRODUCTION", "VERVAARDIGING", "FABRIEK"],
        "context": "Manufacturing. Target gross margin: 30-45% depending on product. "
                   "Biggest costs: raw materials (40-60%), labour, electricity, equipment maintenance. "
                   "Key GL: Stock Purchases (raw materials), Direct Labour, Electricity, "
                   "Repairs — Equipment/Machinery, Packaging Materials, Delivery/Freight. "
                   "Watch for: raw material waste (track input vs output), electricity costs "
                   "(load shedding = generator costs), equipment downtime, quality rejects. "
                   "Section 12C: manufacturing equipment 40/20/20/20 depreciation, "
                   "or SBC 100% write-off in year 1. Industrial Development Zone benefits if applicable."
    },

    # ═══ EDUCATION & CHILDCARE ═══
    {
        "keywords": ["SCHOOL", "CRECHE", "DAYCARE", "NURSERY", "TUTOR", "TRAINING", "SKOOL", "KLEUTERSKOOL"],
        "context": "Crèche/daycare/training. Target margin: 25-40%. "
                   "Biggest costs: staff (50-60%), rent/property, food, educational materials, insurance. "
                   "Key GL: Salaries, Wages, Rent, Stock Purchases — Food, Stationery, "
                   "Insurance — Public Liability, Toys/Educational Materials. "
                   "DSD (Department of Social Development) registration required for childcare. "
                   "Must comply with Children's Act. Norms and standards for ECD centres. "
                   "VAT: educational services are EXEMPT — you DON'T charge VAT but also can't claim input VAT. "
                   "Watch for: compliance costs, staff ratios (regulated), safety requirements."
    },

    # ═══ REAL ESTATE ═══
    {
        "keywords": ["ESTATE AGENT", "PROPERTY", "REAL ESTATE", "RENTAL AGENT", "EIENDOM"],
        "context": "Estate agency/rental management. Commission: 5-7.5% on sales, 8-12% on rental management. "
                   "Target margin: 40-60%. Mostly commission-based income. "
                   "Biggest costs: agent commissions (50-60% of earned commission), office rent, "
                   "advertising (portals), vehicle costs. "
                   "Key GL: Commission paid (sub-agents), Rent, Advertising — Online, "
                   "Vehicle expenses, Cellphone, Software (PropTech tools). "
                   "EAAB (Estate Agency Affairs Board) registration compulsory. Fidelity Fund certificate. "
                   "Trust account required if handling rental deposits/rent collection."
    },

    # ═══ FITNESS & RECREATION ═══
    {
        "keywords": ["GYM", "FITNESS", "CROSSFIT", "YOGA", "PILATES", "SPORT"],
        "context": "Gym/fitness studio. Target margin: 50-65% on memberships. "
                   "Biggest costs: rent (large space), equipment (R500k-R2m+), electricity, staff. "
                   "Key GL: Rent, Repairs — Equipment, Electricity, Salaries, Insurance — Public Liability, "
                   "Marketing, Cleaning & Hygiene. "
                   "Watch for: member churn (industry average 30-40% annual), equipment maintenance costs, "
                   "debit order failures (5-10% monthly). "
                   "Tip: personal training and group classes have highest margin — push these. "
                   "Public liability insurance essential — one injury claim can close you."
    },
]


def get_relevant_industry_knowledge(query: str, business_type: str = "", max_chunks: int = 2) -> list:
    """
    Find relevant industry knowledge chunks.
    Matches against both the user query AND the business type if provided.
    """
    if not query and not business_type:
        return []
    
    search_text = f"{query} {business_type}".upper()
    scored = []
    
    for chunk in INDUSTRY_CHUNKS:
        score = 0
        for keyword in chunk["keywords"]:
            if keyword.upper() in search_text:
                score += len(keyword)
        if score > 0:
            scored.append((score, chunk))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:max_chunks]]


def format_industry_knowledge(chunks: list) -> str:
    """Format matched chunks for Zane's prompt."""
    if not chunks:
        return ""
    
    lines = ["\n\n📊 INDUSTRY INSIGHT:"]
    for chunk in chunks:
        lines.append(chunk["context"])
    
    return "\n".join(lines)
