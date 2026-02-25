"""
ClickAI Transport & Logistics Knowledge — Deep industry intelligence for Zane
══════════════════════════════════════════════════════════════════════════════
Comprehensive SA transport/trucking/logistics knowledge base.
Covers: loading, fuel, tyres, maintenance, compliance, driver management,
costing, insurance, cross-border, fleet management, common fraud patterns.

Each chunk = one topic area.
Zane gets max 2 chunks — matched by keywords in user query.
"""

TRANSPORT_CHUNKS = [
    # ═══ LOADING & WEIGHT MANAGEMENT ═══
    {
        "keywords": ["LOAD", "LOADING", "WEIGHT", "TON", "TONNAGE", "OVERLOAD", "UNDERLOAD", "PAYLOAD", "LAAI", "GEWIG", "OORLAAI"],
        "context": "Loading and weight management for SA transport. "
                   "CRITICAL ISSUE: Short-loading — customer orders 36 ton but driver only loads 34 ton. "
                   "This costs you money (paid for 36t capacity, delivering 34t). Causes: lazy loading, "
                   "poor load planning, driver rushing, faulty weighbridge readings, moisture loss in bulk goods. "
                   "CONTROLS: (1) Weigh LOADED at origin weighbridge — get a weighbridge ticket with date/time/reg/weight. "
                   "(2) Weigh EMPTY on return — calculate actual payload. (3) Compare ordered vs actual vs delivered. "
                   "(4) Track variance per driver — pattern of short-loading = disciplinary. "
                   "(5) Customer signs POD (proof of delivery) with weight received. "
                   "OVERLOADING: SA legal limits — Single axle: 8,000kg. Tandem axle: 16,000kg. Tridem axle: 21,000kg. "
                   "GVM for interlink: 56,000kg. Abnormal loads need permit from provincial road authority. "
                   "Overloading fines: R100-R150 per kg over limit (can be R50,000+ per offence). "
                   "NRCS/RTI inspections at weighbridges — truck can be impounded. "
                   "Overloading destroys roads, tyres, suspension, brakes — false economy. "
                   "LOAD SECURING: SANS 10187 standard. Cargo must be secured to withstand 0.8g forward, "
                   "0.5g sideways, 0.5g rearward forces. Use rated straps/chains, not wire or rope. "
                   "Flatbed: minimum 1 strap per 1.5m of cargo length. Curtain-siders: certified curtains only. "
                   "Driver is legally responsible for load security — can be charged for negligence."
    },

    # ═══ FUEL MANAGEMENT & ECONOMY ═══
    {
        "keywords": ["FUEL", "DIESEL", "PETROL", "CONSUMPTION", "ECONOMY", "BRANDSTOF", "VERBRUIK", "FUEL COST", "LITRES", "KM PER LITRE"],
        "context": "Fuel management — single biggest controllable cost in transport (30-40% of revenue). "
                   "SA BENCHMARKS: Long-haul truck (interlink): 2.0-2.8 km/litre. Rigid truck (8t): 4-6 km/l. "
                   "LDV delivery (2t): 8-12 km/l. These vary by load, terrain, driving style, tyre pressure. "
                   "FUEL THEFT/FRAUD — biggest risk: (1) Siphoning from tank (install lockable fuel caps + fuel sensors). "
                   "(2) Driver fills personal vehicle at company card. (3) Phantom fuel — receipt says 500L but only pumped 400L "
                   "(collusion with fuel attendant). (4) Detour to sell fuel. "
                   "CONTROLS: (1) GPS tracking with fuel level sensor — see exactly when/where fuel drops or fills. "
                   "(2) Fuel card system (e.g., Fleet Card, BP Fleet, Shell Fleet) — limits per vehicle per day. "
                   "(3) Track litres per 100km per truck — set target, flag deviations >15%. "
                   "(4) Reconcile fuel card transactions vs GPS location (was truck actually at that fuel station?). "
                   "(5) Monthly fuel efficiency report per driver — incentivise good drivers. "
                   "FUEL ECONOMY TIPS: Correct tyre pressure saves 3-5% fuel. Speed: 80km/h vs 100km/h saves ~20% fuel "
                   "on a truck. Avoid excessive idling (>3 min = switch off). Cruise control on flat highways. "
                   "Regular engine service (dirty air filters cost 5-10% fuel). Aerodynamic deflectors on cab. "
                   "Route planning — shortest not always cheapest (tolls vs fuel vs time). "
                   "DIESEL REBATE: SARS allows diesel refund for qualifying transport (80/20 road/off-road split). "
                   "Must keep detailed logbooks. Claim via VAT201 return."
    },

    # ═══ TYRE MANAGEMENT ═══
    {
        "keywords": ["TYRE", "TYRES", "TIRE", "BAND", "BANDE", "TYRE PRESSURE", "RETREADS", "BANDDRUCK"],
        "context": "Tyre management — second biggest cost after fuel for trucks. "
                   "COSTS: New truck tyre (steer): R4,000-R8,000. Drive tyre: R3,500-R7,000. Trailer tyre: R3,000-R5,500. "
                   "Retreads: R1,500-R3,000 (50-60% saving). A 22-wheel interlink = R80,000-R150,000 full set. "
                   "TYRE PRESSURE — most critical factor: "
                   "Under-inflation by 10% = 10% more fuel consumption + 15% less tyre life. "
                   "Over-inflation = uneven wear centre + blowout risk. "
                   "CHECK PRESSURE: Cold tyres only (morning before driving). Use calibrated gauge. "
                   "Steer axle: typically 800-900 kPa. Drive/trailer: 700-850 kPa (check manufacturer spec for your tyre). "
                   "TPMS (tyre pressure monitoring system) — R15,000-R30,000 investment but saves R100,000+/year in tyre costs. "
                   "TYRE ROTATION: Rotate every 40,000-50,000km. Steer tyres to drive position when 50% worn. "
                   "Drive tyres to trailer when worn. Retreads only on drive/trailer, NEVER on steer axle (illegal + dangerous). "
                   "ALIGNMENT: Check every 20,000km or after hitting pothole. Misalignment eats tyres fast — "
                   "one bad alignment can destroy R20,000 steer tyre in 10,000km. "
                   "TYRE TRACKING: Record every tyre — serial number, position, date fitted, km at fitment, date removed, "
                   "km at removal, reason (worn/damaged/retreaded). Calculate cost per km per tyre. "
                   "Target: steer >80,000km life, drive >100,000km (including retread), trailer >120,000km. "
                   "BLOWOUT PREVENTION: Check for cuts, bulges, exposed cord daily (pre-trip inspection). "
                   "Remove stones from treads. Don't run tyres below 3mm tread depth."
    },

    # ═══ VEHICLE MAINTENANCE & FLEET MANAGEMENT ═══
    {
        "keywords": ["MAINTENANCE", "SERVICE", "FLEET", "REPAIR", "BREAKDOWN", "ONDERHOUD", "DIENS", "VLOOT", "COF", "ROADWORTHY"],
        "context": "Vehicle maintenance and fleet management for SA transport. "
                   "PREVENTIVE MAINTENANCE SCHEDULE: Oil/filter change every 15,000-25,000km (check manufacturer). "
                   "Full service every 40,000-60,000km. Transmission service every 100,000km. "
                   "Brake inspection every 30,000km. Coolant change every 100,000km or 2 years. "
                   "BUDGET: Maintenance should be 10-15% of revenue. If >15%, fleet is too old or poorly maintained. "
                   "NEW vs USED vs LEASE: New truck warranty 2-3 years. Break-even age for replacement: typically 5-7 years "
                   "or 700,000-1,000,000km. Beyond this, maintenance costs exceed finance costs of newer vehicle. "
                   "COF (Certificate of Fitness): Required annually for all vehicles >3,500kg GVM. "
                   "Testing station checks: brakes, steering, lights, tyres, suspension, emissions. "
                   "Operating without valid COF: criminal offence + insurance void. Budget R2,000-R5,000 per COF including repairs. "
                   "PRE-TRIP INSPECTION: Driver must check DAILY before departure: "
                   "Tyres (pressure, damage), lights (all working), brakes (air pressure, leaks), "
                   "oil/coolant/hydraulic levels, load security, fire extinguisher (compulsory), "
                   "wheel nuts (torqued), mirrors, wipers, horn. Document on checklist — signed by driver. "
                   "BREAKDOWN PROTOCOL: Have 24/7 breakdown service contract (Breakdown24, RAC, etc.). "
                   "Triangles MUST be placed 50m behind vehicle (R2,500 fine if not). "
                   "Track breakdown frequency per vehicle — >2 per month = maintenance review needed. "
                   "FLEET TRACKING: GPS essential — Cartrack, Netstar, MiX Telematics, Ctrack. "
                   "Costs R200-R500/vehicle/month. Monitors: location, speed, idling, harsh braking, fuel, geofencing."
    },

    # ═══ DRIVER MANAGEMENT ═══
    {
        "keywords": ["DRIVER", "DRYWER", "BESTUURDER", "LICENCE", "LISENSIE", "PDP", "HOURS", "FATIGUE", "RUS"],
        "context": "Driver management for SA transport operations. "
                   "LICENSING: Code EC (articulated >16,000kg GVM) or Code C2 (rigid >16,000kg). "
                   "PrDP (Professional Driving Permit): Required for all goods vehicles >3,500kg. "
                   "PrDP categories: G (goods), P (passengers), D (dangerous goods). "
                   "Renewal every 2 years (5 years from 2024 amendment). Includes medical test + eye test. "
                   "DRIVING HOURS (NRSA): Maximum 9 hours driving per day (can extend to 10 hours twice per week). "
                   "Must rest 30 min after 5 hours continuous driving. Daily rest: minimum 11 consecutive hours. "
                   "Weekly rest: 24 consecutive hours (can defer to bi-weekly 45 hours). "
                   "Maximum 90 hours driving per fortnight. KEEP A LOGBOOK — fines up to R10,000 for violations. "
                   "FATIGUE: Biggest killer on SA roads. Signs: lane drifting, yawning, heavy eyelids. "
                   "Never drive between 02:00-06:00 if possible. Company liable for fatigue-related accidents "
                   "if they knew or should have known driver was fatigued (AARTO Act). "
                   "DRIVER COSTS: Base salary R12,000-R25,000/month (long-haul). Trip allowance R200-R500/day. "
                   "Night-out allowance R250-R450/night. Overtime at 1.5x after 45 hours/week. "
                   "DRIVER FRAUD: (1) Fuel theft (see fuel section). (2) Side-loading — picking up unauthorised freight. "
                   "(3) Odometer tampering. (4) Using company truck for personal moves. (5) Claiming false overtime. "
                   "(6) Selling cargo and reporting 'hijacking'. "
                   "CONTROLS: GPS tracking, dashcam (forward + cabin), breathalyser on ignition, "
                   "regular drug testing, trip sheet signed by sender AND receiver."
    },

    # ═══ TRANSPORT COSTING & PRICING ═══
    {
        "keywords": ["RATE", "COST", "PRICE", "TARIFF", "PER KM", "PER TON", "COSTING", "PRYS", "TARIEF", "KOSTE"],
        "context": "Transport costing and pricing in South Africa. "
                   "COST STRUCTURE (typical long-haul): Fuel 30-40%, Driver costs 15-20%, "
                   "Tyres 5-8%, Maintenance 10-15%, Insurance 3-5%, Finance/depreciation 10-15%, "
                   "Tolls 3-8%, Admin/overhead 5-8%. TARGET MARGIN: 15-25% net (tight industry). "
                   "PRICING MODELS: (1) Per km — R15-R30/km loaded (varies by route, cargo, vehicle). "
                   "(2) Per ton — R80-R200/ton (bulk commodities). (3) Per trip — fixed rate for regular routes. "
                   "(4) Per pallet — R200-R800/pallet (distribution). "
                   "CRITICAL: Calculate YOUR cost per km first: Total monthly costs / total km driven. "
                   "If your cost is R22/km and you charge R25/km = only R3/km profit = 12% margin (too thin). "
                   "EMPTY RUNNING (deadheading): Running empty = pure loss. Target: <30% empty km. "
                   "Use load boards (TimoCom, LoadStar, LoadX) to find backloads. "
                   "Even at 50% of normal rate, a backload beats running empty. "
                   "FUEL SURCHARGE: Standard practice — link pricing to diesel price. "
                   "Base rate set at diesel price of (e.g.) R22/litre. For every R1 increase, surcharge goes up X%. "
                   "Formula: ((current diesel - base diesel) / base diesel) x fuel % of rate. "
                   "Review monthly. Protects both parties from fuel volatility. "
                   "TOLL COSTS: Bakwena (N1/N4 Pretoria-Botswana border): R300-R600 per truck per trip. "
                   "SANRAL e-toll (Gauteng): R2-R4/km for trucks. N3 (Jhb-Durban): R800-R1,200 per truck. "
                   "Factor tolls into every quote — they add up fast."
    },

    # ═══ INSURANCE & RISK ═══
    {
        "keywords": ["INSURANCE", "CLAIM", "ACCIDENT", "HIJACK", "THEFT", "VERSEKERING", "ONGELUK", "KAPING", "DIEFSTAL", "LIABILITY"],
        "context": "Transport insurance and risk management in SA. "
                   "INSURANCE TYPES NEEDED: (1) Comprehensive vehicle — covers own vehicle damage, theft, hijack. "
                   "Premium: 3-6% of vehicle value per year. Excess: R10,000-R50,000 per claim. "
                   "(2) Goods-in-transit (GIT) — covers customer's cargo while you transport it. "
                   "CRITICAL — without this, YOU pay for lost/damaged cargo. Premium: 0.1-0.5% of cargo value per trip. "
                   "(3) Third-party liability — damage to other vehicles/property. "
                   "(4) Sasria — riot, strike, terrorism cover (compulsory add-on in SA). "
                   "(5) Credit shortfall — if vehicle is written off and insurance pays less than finance owing. "
                   "CLAIMS PROCESS: Report accident to insurer within 24-48 hours. Get police case number (SAPS). "
                   "Take photos of scene, damage, other vehicles, driver licences. Drug/alcohol test driver immediately. "
                   "If driver was over limit = claim rejected AND you're criminally liable. "
                   "HIJACK RISK: SA has highest truck hijack rate in world. High-risk corridors: "
                   "N3 KZN, N1 Limpopo, N4 Mpumalanga, N12 Gauteng. "
                   "Mitigations: GPS tracking with panic button, no stopping in known hotspots, "
                   "vary routes, no night driving in high-risk areas, armed escort for high-value loads. "
                   "CARGO THEFT: Chrome, copper, fuel, electronics, cigarettes most targeted. "
                   "Seals on all cargo openings — check at loading, random checks en route, check at delivery. "
                   "Broken seal = incident report immediately."
    },

    # ═══ COMPLIANCE & LEGAL ═══
    {
        "keywords": ["COMPLIANCE", "LEGAL", "PERMIT", "LICENCE", "NRCS", "RTQS", "CROSS BORDER", "DOT", "AARTO", "NAKOMING", "WETTIG", "PERMIT"],
        "context": "SA transport compliance and legal requirements. "
                   "OPERATOR REGISTRATION: All goods vehicles >3,500kg need operator registration (Road Traffic Act). "
                   "Display operator card and number on vehicle. Renewal annually. "
                   "RTQS (Road Transport Quality System) — grading system: A (good) to E (unroadworthy). "
                   "E-graded vehicle = off the road until fixed and re-inspected. "
                   "DOCUMENTATION PER TRIP: (1) Valid COF. (2) Vehicle licence disc. (3) Driver's licence + PrDP. "
                   "(4) Trip sheet/logbook. (5) Consignment note/waybill. (6) Dangerous goods documentation (if applicable). "
                   "(7) Cross-border permits (if applicable). (8) Oversize/overweight permit (if applicable). "
                   "DANGEROUS GOODS: SANS 10228 classification. Driver needs PrDP(D) + ADR training certificate. "
                   "Vehicle must display orange hazard diamonds. Must carry Tremcard (emergency procedures). "
                   "No parking in residential areas. Cannot use tunnels (some). "
                   "CROSS-BORDER: Need Cross-Border Road Transport Permit from C-BRTA. "
                   "Countries: Zimbabwe, Mozambique, Botswana, Namibia, Lesotho, Eswatini, Zambia, DRC, Tanzania, Malawi. "
                   "Each country has own permits, fees, insurance requirements. "
                   "Cabotage (carrying domestic freight in foreign country) is generally illegal — only cross-border loads. "
                   "FINES (AARTO demerit system from 2024): Speeding, overloading, unroadworthy vehicle, "
                   "no COF, expired licence, no PrDP, insecure load, worn tyres — all carry demerit points. "
                   "12 demerits = licence suspension. Company demerits can shut down operator licence."
    },

    # ═══ ROUTE PLANNING & OPERATIONS ═══
    {
        "keywords": ["ROUTE", "TRIP", "PLANNING", "SCHEDULE", "TURNAROUND", "DELIVERY", "DISPATCH", "ROETE", "BEPLANNING", "AFLEWERING"],
        "context": "Route planning and operational efficiency for SA transport. "
                   "KEY METRIC: Vehicle utilisation — target >85% of available days on the road. "
                   "Truck sitting in yard = money burning. Track: days loaded / days available. "
                   "TURNAROUND TIME: Jhb to Durban and back should be 2 days max (600km each way). "
                   "Jhb to Cape Town and back: 3-4 days. Jhb to Beitbridge (Zim border): 1 day. "
                   "If trips take longer than benchmarks = investigate (driver stops, loading delays, breakdowns). "
                   "LOADING/OFFLOADING DELAYS: Average SA warehouse wait time: 2-6 hours (major cost). "
                   "Demurrage: charge customer R500-R1,500 per hour after first 2 free hours. "
                   "Have clear terms in contract — waiting time is the customer's cost, not yours. "
                   "NIGHT DRIVING: Avoid if possible — higher accident risk, hijack risk, fatigue. "
                   "If necessary: two drivers, GPS monitored, pre-planned rest stops. "
                   "ROUTE SELECTION: N3 Jhb-Durban = tolls R800-R1,200 but good road. "
                   "Alternative via Harrismith/Bethlehem cheaper tolls but slower, more fuel. "
                   "N1 Jhb-CT: 1,400km, tolls R500-R800. N12/N10 alternative via Bloemfontein cheaper but longer. "
                   "FLEET SCHEDULING: Use dispatch board or software (Lightstone, FleetLogic, ClickAI Jobs). "
                   "Track: which truck, which driver, which route, loading date/time, expected delivery, actual delivery. "
                   "KPIs: on-time delivery rate (target >95%), km per truck per month, revenue per truck per month."
    },

    # ═══ FINANCIAL MANAGEMENT FOR TRANSPORT ═══
    {
        "keywords": ["FINANCE", "CASH FLOW", "INVOICE", "PAYMENT", "DEBTOR", "ACCOUNT", "REKENING", "BETALING", "KONTANTVLOEI"],
        "context": "Financial management specific to transport businesses. "
                   "CASH FLOW KILLER: Transport businesses fail on cash flow, not profitability. "
                   "Typical payment terms: 30-60 days from customer, but you pay fuel/tolls/drivers immediately. "
                   "You need 2-3 months operating cash reserve minimum. "
                   "INVOICING: Invoice IMMEDIATELY after delivery — every day delay = money you're lending the customer for free. "
                   "Attach POD (proof of delivery) to every invoice — customers use missing POD as excuse not to pay. "
                   "POD must have: date, time, receiver name + signature, vehicle reg, consignment details, "
                   "weight/quantity received, condition of goods, stamp/company stamp. "
                   "DEBTORS: 30-day terms is standard. Anything over 45 days = phone call. Over 60 days = stop loading. "
                   "Big corporate customers (mines, retailers) often pay 60-90 days — factor this into pricing. "
                   "COST TRACKING: Must track per trip: fuel litres + cost, tolls, driver allowance, "
                   "any on-road expenses. Monthly per vehicle: maintenance, tyres, insurance, finance, licence. "
                   "This gives you ACTUAL cost per km per vehicle — essential for pricing. "
                   "GL STRUCTURE: Revenue — Transport, Revenue — Backloads, Fuel — Business Vehicles, "
                   "Tyres, Vehicle Repairs & Service, Vehicle Insurance, Vehicle Finance, Tolls & Parking, "
                   "Driver Wages, Driver Allowances, Vehicle Licence & COF, GPS Tracking. "
                   "VAT: Transport is standard-rated at 15%. Fuel: can claim input VAT on diesel. "
                   "DIESEL REBATE: Additional refund for qualifying road transport — claim via SARS."
    },

    # ═══ VEHICLE TYPES & SPECIFICATIONS ═══
    {
        "keywords": ["TRUCK", "VEHICLE", "INTERLINK", "TRAILER", "RIGID", "TAUTLINER", "FLATBED", "TANKER", "VRAGMOTOR", "SLEEPWA"],
        "context": "Transport vehicle types and specifications for SA operations. "
                   "VEHICLE CLASSES: LDV/Bakkie (Code B, <3,500kg GVM): Local delivery. "
                   "Rigid 4-tonner (Code C1, 3,500-16,000kg): Urban distribution. "
                   "Rigid 8-tonner (Code C, >16,000kg): Medium haul, building materials. "
                   "Horse + trailer (Code EC, articulated >16,000kg): Long haul, interlinks. "
                   "TRAILER TYPES: (1) Tautliner/curtain-side — most versatile, side-loading, R300,000-R500,000. "
                   "(2) Flatbed — steel, timber, containers, R200,000-R400,000. "
                   "(3) Tipper — sand, stone, mining, R400,000-R800,000. "
                   "(4) Tanker — fuel, chemicals, milk, R500,000-R1,200,000 (specialised). "
                   "(5) Refrigerated (reefer) — food, pharma, R600,000-R1,000,000. "
                   "(6) Lowbed — machinery, abnormal loads, R400,000-R700,000. "
                   "(7) Side-tipper — bulk mining/agricultural, R350,000-R600,000. "
                   "(8) Interlink (tri-axle + tri-axle): Max payload ~34 tonnes, max GVM 56,000kg. "
                   "POPULAR TRUCK BRANDS SA: Mercedes-Benz Actros, Scania, MAN TGS/TGX, "
                   "Volvo FH, Iveco, UD Trucks (Nissan), FAW, CNHTC/Sinotruk (budget Chinese option). "
                   "NEW TRUCK COST: Entry-level horse: R1.2-R1.8M. Premium (Scania/Benz): R2.5-R4M. "
                   "USED: 3-5 year old horse: R800K-R1.8M. Finance: typically 20% deposit, 60 months, prime+2%. "
                   "DEPRECIATION: SARS allows 20% per year (5 years straight-line) for trucks."
    },

    # ═══ SAFETY & ACCIDENTS ═══
    {
        "keywords": ["SAFETY", "ACCIDENT", "CRASH", "VEILIGHEID", "ONGELUK", "DASHCAM", "SPEED", "SPOED"],
        "context": "Transport safety management in South Africa. "
                   "SA ROAD STATISTICS: ~14,000 road deaths/year. Trucks involved in ~12% of fatal crashes. "
                   "Main causes: fatigue, speeding, vehicle defects, drunk driving, poor road conditions. "
                   "SPEED LIMITS: Trucks >9,000kg: 80km/h on open road, 100km/h on highway (some 120km/h sections "
                   "but speed limiter required at 80km/h for heavy vehicles per NRSA). "
                   "SPEED LIMITERS: Compulsory for all goods vehicles >3,500kg. Set at 80km/h. "
                   "Tampering with speed limiter: criminal offence + R20,000 fine + vehicle impounded. "
                   "GPS tracking can verify — flag any speed over 85km/h. "
                   "DASHCAMS: Forward-facing minimum. Recommended: forward + driver-facing + rear. "
                   "Cost: R3,000-R8,000 per vehicle. Cloud storage: R200-R500/month. "
                   "ESSENTIAL for: accident evidence, insurance claims, driver behaviour monitoring, "
                   "armed robbery evidence, refuting false claims. "
                   "ACCIDENT PROCEDURE: (1) Check injuries — call ambulance if needed. "
                   "(2) Place triangles 50m behind vehicle. (3) Call police (10111). "
                   "(4) DO NOT move vehicles unless blocking traffic dangerously. "
                   "(5) Photos: scene, damage, number plates, driver licences, road conditions, weather. "
                   "(6) Drug/alcohol test driver immediately (urine test kit in truck, breathalyser). "
                   "(7) Report to insurance within 24 hours. (8) Report to operations/fleet manager immediately. "
                   "DRIVER TRAINING: Defensive driving course annually (R2,000-R5,000 per driver). "
                   "New drivers: supervised trips for first month. Track incidents per driver — "
                   "3 incidents in 6 months = retraining or dismissal."
    },

    # ═══ DIESEL PRICE & FUEL CARDS ═══
    {
        "keywords": ["DIESEL PRICE", "FUEL CARD", "FLEET CARD", "BRANDSTOFKAART", "PUMP", "FILLING STATION"],
        "context": "Diesel pricing and fuel card management for SA transport. "
                   "DIESEL PRICE SA (2025): R20-R23/litre (fluctuates monthly per DoE regulation). "
                   "Wholesale/bulk discount: 10-30c/litre off pump price for fleet accounts. "
                   "FUEL CARD OPTIONS: (1) BP Fleet Card — wide network, online portal, per-vehicle limits. "
                   "(2) Shell Fleet Card — similar features, 24/7 helpline. "
                   "(3) Engen Fleet Card — good in rural areas. "
                   "(4) Total/TotalEnergies Fleet Card. "
                   "(5) FNB/Absa/Nedbank fuel cards — linked to business account, consolidated statements. "
                   "(6) WesBank FleetCard — integrates with fleet management. "
                   "CONTROLS: Set daily/weekly litres limit per vehicle per card. "
                   "Only allow diesel (block petrol purchases). Block odd-hour transactions (02:00-05:00). "
                   "Reconcile card statement vs GPS data monthly — flag mismatches. "
                   "BULK FUEL: If you have >10 vehicles, consider on-site diesel tank (5,000-10,000L). "
                   "Cost to install: R50,000-R150,000 (tank + pump + containment). "
                   "Requires SABS compliance and environmental permit. "
                   "Saves 20-40c/litre vs retail + eliminates fraud risk. "
                   "FUEL MANAGEMENT SOFTWARE: FuelWise, Fleetio, ClickAI can track per-vehicle fuel costs. "
                   "Input every fill-up: date, vehicle, litres, odometer, cost. System calculates km/l trends."
    },

    # ═══ SUBCONTRACTORS & OWNER-DRIVERS ═══
    {
        "keywords": ["SUBCONTRACTOR", "OWNER DRIVER", "OWNER OPERATOR", "SUB", "CONTRACTOR", "EIENAAR DRYWER", "KONTRAKTEUR"],
        "context": "Managing subcontractors and owner-drivers in SA transport. "
                   "OWNER-DRIVER MODEL: You contract independent truckers to carry your loads. "
                   "Advantage: no vehicle cost, no maintenance, no insurance. Disadvantage: less control. "
                   "PRICING: Typically pay owner-driver 70-85% of client rate. You keep 15-30% margin for finding loads. "
                   "CONTRACTS: Written agreement essential — covers: rates, payment terms (7-14 days is fair), "
                   "insurance requirements (they must have their own GIT + comprehensive), "
                   "branding (your livery on their truck?), exclusivity, fuel responsibility, "
                   "who pays tolls, breakdown responsibility, liability for cargo damage. "
                   "TAX: Owner-drivers are independent contractors (NOT employees). "
                   "If they only work for you = SARS may reclassify as employee (section 200A of LRA). "
                   "They must have own VAT registration (if turnover >R1M). Invoice you with VAT. "
                   "You do NOT deduct PAYE/UIF/SDL — they handle their own tax. "
                   "RISKS: (1) Their truck breaks down — your customer is let down. Have backup plan. "
                   "(2) Their insurance lapses — YOU could be liable if they transport under your brand. "
                   "(3) Cargo theft/damage — their insurance must cover it, but client will blame you. "
                   "(4) BBBEE: Subcontractor spend counts as procurement, not payroll. "
                   "VETTING: Check PrDP, COF, insurance certificates, operator card, "
                   "previous employer references, credit check (ITC). Verify annually."
    },

    # ═══ ABNORMAL LOADS & SPECIALISED TRANSPORT ═══
    {
        "keywords": ["ABNORMAL", "OVERSIZED", "HEAVY HAUL", "LOWBED", "CRANE", "MACHINERY", "PERMIT", "ABNORMAAL", "OORGROOTTE"],
        "context": "Abnormal load transport in South Africa. "
                   "DEFINITION: Abnormal if exceeds: Length >22m, Width >2.5m, Height >4.3m, "
                   "or any single axle >8,000kg / GVM >56,000kg. "
                   "PERMIT APPLICATION: Apply to relevant provincial road authority (not national). "
                   "Processing time: 5-15 working days (plan ahead!). Cost: R500-R5,000 depending on load. "
                   "Permit specifies: exact route, times (often 09:00-15:00 or night-only), escort requirements. "
                   "ESCORTS: Width >3.5m or length >22m typically needs pilot vehicles (1 front, 1 rear). "
                   "Width >4.5m or length >30m may need traffic police escort. "
                   "Pilot vehicle cost: R8,000-R15,000 per trip. Police escort: R5,000-R20,000 per trip. "
                   "INSURANCE: Abnormal load insurance is separate/additional — standard fleet policy may exclude. "
                   "Get specific quote per load for high-value cargo (machinery >R5M). "
                   "PRICING: Premium transport — rates 3-5x normal per-km rates. "
                   "Lowbed hourly rate: R2,500-R5,000/hour including loading/offloading. "
                   "Crane truck: R3,000-R8,000/hour depending on tonnage. "
                   "RISK: Bridge height restrictions, power line clearance, road surface limitations, "
                   "turning circles in towns. Survey route BEFORE transport day."
    },

    # ═══ COMMON TRANSPORT SCAMS & FRAUD ═══
    {
        "keywords": ["FRAUD", "SCAM", "THEFT", "STEAL", "MISSING", "SHORTAGE", "BEDROG", "STEEL", "TEKORT", "DIEFSTAL"],
        "context": "Common fraud and theft patterns in SA transport — what to watch for. "
                   "DRIVER FRAUD: (1) FUEL THEFT — siphoning, phantom fills, detours. See fuel management section. "
                   "(2) CARGO PILFERAGE — driver takes small quantities from bulk load (grain, coal, cement). "
                   "Control: weigh at loading AND delivery. Variance >2% on bulk = investigate. "
                   "(3) SIDE-LOADING — driver picks up unauthorised cargo for personal income. "
                   "Control: GPS tracking + geofencing. Unexpected stops = alert. "
                   "(4) FAKE BREAKDOWNS — driver claims breakdown but was actually parked/sleeping/doing side job. "
                   "Control: GPS shows stationary. Require photo of breakdown + mechanic invoice. "
                   "(5) ODOMETER ROLLBACK — less km = less maintenance cost claimed but also hides fuel theft. "
                   "Control: GPS tracks actual km driven — compare with odometer. "
                   "OFFICE FRAUD: (1) PHANTOM TRIPS — trip sheet says truck went to Durban but it didn't. "
                   "Control: GPS confirms all trips. (2) INFLATED MAINTENANCE INVOICES — mechanic and fleet manager collude. "
                   "Control: get 3 quotes for any repair >R5,000. Verify parts prices online. "
                   "(3) KICKBACKS FROM SUBCONTRACTORS — dispatcher gives loads to specific sub in exchange for cash. "
                   "Control: rotate load allocation, audit subcontractor selection patterns. "
                   "CUSTOMER FRAUD: (1) Claim goods damaged/short when they weren't — POD with photos protects you. "
                   "(2) Refuse to pay after delivery — have signed contract before first load. "
                   "(3) Underdeclare value of goods to reduce your insurance requirements."
    },

    # ═══ BBBEE & TRANSFORMATION ═══
    {
        "keywords": ["BBBEE", "BEE", "TRANSFORMATION", "SCORECARD", "EMPOWERMENT", "TENDER", "GOVERNMENT"],
        "context": "BBBEE in SA transport — essential for winning contracts. "
                   "Transport sector has sector-specific code under Transport Charter. "
                   "MINIMUM REQUIREMENTS for government/SOE contracts: Level 1-4 BBBEE rating typically required. "
                   "Key elements: Ownership (25%+ black owned for Level 1), management control, "
                   "skills development, enterprise/supplier development, socio-economic development. "
                   "SMALL BUSINESS EXEMPTION: Turnover <R10M = Exempt Micro Enterprise (EME), "
                   "auto Level 4. Turnover R10M-R50M = Qualifying Small Enterprise (QSE), simplified scorecard. "
                   "If >51% black owned, EME/QSE can claim Level 1 or 2. "
                   "PRACTICAL IMPACT: Mining contracts (Anglo, BHP, Glencore) require Level 1-3. "
                   "Retail distribution (Shoprite, Pick n Pay) require Level 1-4. "
                   "Government (Transnet, SANRAL, provinces) require minimum Level 3. "
                   "Without BBBEE certification = locked out of 60-70% of transport contracts. "
                   "COST OF VERIFICATION: R5,000-R15,000 annually for EME/QSE certificate. "
                   "R15,000-R40,000 for full verification (>R50M turnover). "
                   "STRATEGY: If white-owned, consider 26%+ BEE partner, preferential procurement "
                   "from black-owned suppliers, skills development investment (driver training qualifies), "
                   "enterprise development (mentor small black-owned transporters)."
    },

    # ═══ COLD CHAIN / REFRIGERATED TRANSPORT ═══
    {
        "keywords": ["COLD CHAIN", "FRIDGE", "REFRIGERATED", "REEFER", "TEMPERATURE", "FROZEN", "FRESH", "KOELKETTING", "KOUE"],
        "context": "Cold chain/refrigerated transport in SA. "
                   "TEMPERATURE RANGES: Frozen: -18C to -25C. Chilled: 0C to 5C. "
                   "Ambient controlled: 15C to 25C (pharma, chocolate). "
                   "EQUIPMENT: Reefer unit (Thermo King, Carrier): R250,000-R500,000 new. "
                   "Fuel consumption: reefer unit burns 3-5 litres diesel/hour ON TOP of truck fuel. "
                   "Service: every 2,000 hours or 6 months. "
                   "COMPLIANCE: Foodstuffs, Cosmetics and Disinfectants Act requires temperature-controlled transport "
                   "for perishables. Health inspectors can stop and check. "
                   "TEMPERATURE LOGGING: Continuous temperature recorder COMPULSORY. "
                   "Must keep records for 2+ years. Digital loggers (TempTale, Escort) with GPS integration. "
                   "If temperature breaks cold chain = cargo rejected = YOUR loss if your equipment failed. "
                   "LOADING: Pre-cool trailer to required temp BEFORE loading (30-60 min). "
                   "Never load warm product into cold trailer. Stack for airflow — don't block evaporator. "
                   "Mixed temp loads need bulkhead/divider. "
                   "CLIENTS: Retailers (Woolworths, Pick n Pay, Spar) have strict receiving specs. "
                   "Product arriving above temp threshold = rejected at dock. Document everything. "
                   "PRICING: Premium 30-50% above dry freight rates to cover reefer costs + risk."
    },

    # ═══ TECHNOLOGY & SYSTEMS ═══
    {
        "keywords": ["TECHNOLOGY", "SYSTEM", "SOFTWARE", "GPS", "TRACKING", "DIGITAL", "TEGNOLOGIE", "STELSEL", "OPSPORING"],
        "context": "Technology and systems for modern SA transport operations. "
                   "FLEET MANAGEMENT SYSTEMS: (1) Cartrack — GPS + fuel + driver behaviour, from R200/vehicle/month. "
                   "(2) Netstar — tracking + recovery, from R250/month. (3) MiX Telematics — enterprise fleet management, "
                   "full telemetry. (4) Ctrack — real-time tracking + reports. (5) Geotab — OBD-based fleet analytics. "
                   "TRANSPORT MANAGEMENT SOFTWARE (TMS): Manages dispatch, PODs, invoicing, driver assignment. "
                   "Options: SAP TM (enterprise), Oracle TMS, FleetLogic (SA), Lightstone (SA), ClickAI (for SMEs). "
                   "ELECTRONIC LOGGING: Digital trip sheets replacing paper. GPS data = automatic hours tracking. "
                   "LOAD BOARDS: TimoCom, LoadStar, LoadX, Truckingnet — find loads/backloads online. "
                   "ELECTRONIC POD: Driver captures delivery confirmation on phone/tablet — "
                   "photo of goods, customer signature on screen, GPS location/time stamp. "
                   "Instantly available to office for invoicing. No waiting for paper PODs to arrive. "
                   "DASHCAMS WITH AI: New generation cameras detect fatigue (eye tracking), phone use, smoking, "
                   "lane departure, following distance. Cost: R5,000-R15,000/vehicle + R300-R800/month subscription. "
                   "FUEL SENSORS: Installed in diesel tank — measures level ±1%. "
                   "Alerts for sudden drops (siphoning) or fills that don't match fuel card transaction. "
                   "WEIGHBRIDGE INTEGRATION: Some systems link to public weighbridges for automated weight recording."
    },

    # ═══ ENVIRONMENTAL & EMISSIONS ═══
    {
        "keywords": ["EMISSIONS", "ENVIRONMENT", "CARBON", "GREEN", "ELECTRIC", "EMISSION", "OMGEWING", "UITLAAT"],
        "context": "Environmental considerations for SA transport. "
                   "CURRENT SA REGULATIONS: National Environmental Management Air Quality Act — "
                   "commercial vehicles must meet emission standards. Smoke opacity testing at COF. "
                   "CARBON TAX: Carbon tax applies to diesel (included in fuel levy since 2019). "
                   "Additional carbon tax reporting may be required for large fleets. "
                   "EURO STANDARDS: SA currently requires Euro II minimum for new trucks (behind Europe's Euro VI). "
                   "Newer Euro V/VI trucks: 10-15% better fuel economy + much lower emissions. "
                   "ESG REQUIREMENTS: Large corporate clients increasingly require carbon footprint reporting "
                   "from transport providers. Track: total diesel consumed, total km, calculate CO2 per ton-km. "
                   "GREEN FLEET STRATEGIES: (1) Newer, fuel-efficient trucks. (2) Driver eco-training. "
                   "(3) Tyre pressure management. (4) Route optimisation to reduce empty km. "
                   "(5) Speed reduction (80 vs 100 saves 20% fuel). (6) Aerodynamic additions. "
                   "ELECTRIC TRUCKS: Not yet viable for long-haul in SA (no charging infrastructure). "
                   "Short-range urban delivery EVs emerging: BYD, FUSO eCanter. Range: 200-300km. "
                   "Cost: 2-3x diesel equivalent. Battery life: 8-10 years. Running cost: 40-60% less than diesel. "
                   "Watch this space — SA will follow Europe in 3-5 years for urban delivery."
    },
]


def get_transport_chunks(query: str, max_chunks: int = 2) -> list:
    """Return relevant transport knowledge chunks based on keyword matching."""
    query_upper = query.upper()
    scored = []
    
    for chunk in TRANSPORT_CHUNKS:
        score = 0
        for kw in chunk["keywords"]:
            if kw in query_upper:
                score += 2
            # Partial match for compound words
            elif len(kw) > 4 and kw[:4] in query_upper:
                score += 1
        if score > 0:
            scored.append((score, chunk["context"]))
    
    scored.sort(reverse=True, key=lambda x: x[0])
    return [s[1] for s in scored[:max_chunks]]


# Standard RAG interface (same as other knowledge files)
def get_relevant_transport_knowledge(query: str, max_chunks: int = 2) -> list:
    """Standard RAG interface for transport knowledge."""
    return get_transport_chunks(query, max_chunks)


def format_transport_knowledge(chunks: list) -> str:
    """Format transport knowledge chunks for injection into Zane prompt."""
    if not chunks:
        return ""
    return "\n## TRANSPORT & LOGISTICS KNOWLEDGE\n" + "\n---\n".join(chunks)
