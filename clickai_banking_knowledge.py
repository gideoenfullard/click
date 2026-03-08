"""
ClickAI Banking Knowledge — SA-specific transaction intelligence for Zane
═══════════════════════════════════════════════════════════════════════════
Gives Haiku smart context about SA companies/transactions so he asks 
better drill-down questions instead of saying "Not sure".

Each chunk = one company/pattern group with:
  - keywords: what to match in the bank description
  - context: what Haiku needs to know to ask the RIGHT question
  
Keep chunks SHORT — Haiku gets max 1-2 relevant chunks per transaction.
"""

BANKING_CHUNKS = [
    # ═══ TELECOMS & INTERNET ═══
    {
        "keywords": ["TELKOM", "TELKOM SA", "TELEPHONE ACCOUNT"],
        "context": "Telkom SA provides landlines, ADSL, fibre, email hosting, and fax lines. "
                   "Ask: Is this for the business telephone line, internet/fibre, email hosting, or fax? "
                   "Telephone line → Telephone — Landline. Internet → Internet / WiFi. Email hosting → Software Subscription."
    },
    {
        "keywords": ["VODACOM", "VODACOM SP"],
        "context": "Vodacom is an SA mobile network. Could be a cellphone contract, data SIM for card machine/alarm, "
                   "or a WiFi router. Ask: Business cellphone, data SIM for equipment, or mobile WiFi? "
                   "Cellphone → Cellphone / Mobile. Data SIM → Internet / WiFi."
    },
    {
        "keywords": ["MTN ", "MTN SP"],
        "context": "MTN is an SA mobile network. Same as Vodacom — could be cellphone, data SIM, or WiFi router. "
                   "Ask: Cellphone contract, data SIM, or WiFi? Cellphone → Cellphone / Mobile."
    },
    {
        "keywords": ["CELL C", "CELLC"],
        "context": "Cell C is an SA mobile network. Ask: Cellphone contract or data? Cellphone → Cellphone / Mobile."
    },
    {
        "keywords": ["RAIN ", "RAIN MOBILE"],
        "context": "Rain is a data-only SA network — usually internet/WiFi, not voice. → Internet / WiFi."
    },
    {
        "keywords": ["AFRIHOST", "AXXESS", "WEBAFRICA", "COOL IDEAS", "VUMATEL", "OPENSERVE", "FROGFOOT"],
        "context": "SA internet service providers. Almost always business internet/fibre. → Internet / WiFi."
    },
    
    # ═══ INSURANCE ═══
    {
        "keywords": ["HOLLARD"],
        "context": "Hollard is a major SA insurer covering business, vehicle, liability, and personal. "
                   "Ask: Business contents/building, vehicle, public liability, or life/key person insurance? "
                   "Match to the specific Insurance subcategory."
    },
    {
        "keywords": ["SANTAM"],
        "context": "Santam is SA's largest short-term insurer — usually business or vehicle insurance. "
                   "Ask: Business premises/contents, vehicle, or goods in transit?"
    },
    {
        "keywords": ["OUTSURANCE", "OUT SURANCE"],
        "context": "OUTsurance does business, vehicle, and building insurance in SA. "
                   "Ask: Business, vehicle, or building insurance?"
    },
    {
        "keywords": ["DISCOVERY"],
        "context": "Discovery is primarily medical aid and life insurance in SA. Could also be Vitality rewards. "
                   "Ask: Medical aid, life insurance, gap cover, or Vitality membership? "
                   "Medical aid for staff → Staff Welfare. Life → Insurance — Life / Key Person. "
                   "Membership → Membership & Subscriptions."
    },
    {
        "keywords": ["OLD MUTUAL", "OLDMUTUAL"],
        "context": "Old Mutual does life insurance, retirement/provident funds, and investments in SA. "
                   "Ask: Life insurance, provident/pension fund, or investment? "
                   "Life → Insurance — Life. Provident → Provident Fund Contribution."
    },
    {
        "keywords": ["SANLAM"],
        "context": "Sanlam does life insurance, retirement funds, and investments. "
                   "Ask: Life insurance, provident/pension fund, or investment?"
    },
    {
        "keywords": ["MOMENTUM", "MMI HOLDINGS"],
        "context": "Momentum/MMI does life insurance, retirement, and health insurance. "
                   "Ask: Life insurance, provident fund, or health/gap cover?"
    },
    {
        "keywords": ["LIBERTY", "LIBERTY LIFE"],
        "context": "Liberty is life insurance and retirement in SA. Ask: Life or provident fund?"
    },
    {
        "keywords": ["ALEXANDER FORBES", "AF INVESTMENTS"],
        "context": "Alexander Forbes manages provident/pension funds and employee benefits. "
                   "Almost always → Provident Fund Contribution."
    },
    
    # ═══ VEHICLE & TRACKING ═══
    {
        "keywords": ["CARTRACK", "NETSTAR", "TRACKER", "MATRIX"],
        "context": "Vehicle tracking company in SA. Ask: Is this for a business vehicle, delivery fleet, "
                   "or personal vehicle? Business → Software Subscription or Vehicle Insurance depending on contract. "
                   "Usually → Software Subscription (Monthly)."
    },
    {
        "keywords": ["AVIS", "HERTZ", "EUROPCAR", "TEMPEST"],
        "context": "Vehicle rental company. Ask: Business trip rental, temporary replacement vehicle, or long-term lease? "
                   "Short term → Travel — Local. Long term → Vehicle Lease / Finance."
    },
    {
        "keywords": ["AA ", "AUTOMOBILE ASSOCIATION"],
        "context": "AA is roadside assistance and vehicle-related services. → Membership & Subscriptions or Vehicle Insurance."
    },
    
    # ═══ FUEL ═══
    {
        "keywords": ["ENGEN", "SASOL ", "SHELL ", "BP ", "CALTEX", "TOTAL GARAGE", "TOTALENERGIES"],
        "context": "Fuel station purchase. IMPORTANT: Could be business vehicle, lawnmower/garden equipment, "
                   "or generator fuel. Ask: Business vehicle, garden equipment (mower/blower), or generator? "
                   "Vehicle → Fuel — Business Vehicle (NO VAT claim if private use). "
                   "Equipment → Fuel — Equipment (Mower, Generator, etc.). "
                   "SARS WARNING: No VAT claim on fuel for private/own use."
    },
    
    # ═══ MUNICIPALITIES & UTILITIES ═══
    {
        "keywords": ["ESKOM"],
        "context": "Eskom is SA's electricity provider. → Electricity. "
                   "If prepaid token, still Electricity."
    },
    {
        "keywords": ["CITY OF", "MUNICIPALITY", "MUNISIPALITEIT", "TSHWANE", "JOBURG", "CAPE TOWN", "EKURHULENI", "ETHEKWINI", "MOGALE"],
        "context": "Municipal account in SA usually combines rates, electricity, water, and refuse. "
                   "Ask: Is this for rates & taxes, electricity, water, or refuse/waste removal? "
                   "Or is it the full combined municipal account? If combined → Rates & Taxes — Municipal."
    },
    {
        "keywords": ["RAND WATER", "WATER BOARD"],
        "context": "Water supply account. → Water."
    },
    
    # ═══ SARS & TAX ═══
    {
        "keywords": ["SARS", "SA REVENUE"],
        "context": "Payment to South African Revenue Service. Ask: VAT payment, PAYE/UIF/SDL, "
                   "provisional tax, or penalties? VAT → VAT Payment to SARS. "
                   "PAYE/UIF/SDL → PAYE / UIF / SDL Payment. Provisional → Provisional Tax Payment. "
                   "Penalties → Penalties & Fines — SARS."
    },
    
    # ═══ BANKS & FEES ═══
    {
        "keywords": ["BANK CHARGES", "SERVICE FEE", "MONTHLY FEE", "ACCOUNT FEE", "ADMIN FEE"],
        "context": "Bank service fee. → Bank Charges. No drill-down needed."
    },
    {
        "keywords": ["CASH DEPOSIT FEE", "CASH HANDLING"],
        "context": "Bank fee for cash deposits. → Bank Charges."
    },
    {
        "keywords": ["OVERDRAFT", "OD INT", "DEBIT INTEREST"],
        "context": "Overdraft interest charged by the bank. → Interest Paid — Overdraft."
    },
    {
        "keywords": ["FNB GREENBACKS", "EBUCKS", "REWARDS"],
        "context": "Bank rewards/loyalty redemption. This is NOT income — it's a discount/offset. "
                   "Usually → Sundry Income if received as cash, or offset against Bank Charges."
    },
    
    # ═══ CARD MACHINES ═══
    {
        "keywords": ["EFTPOS", "SETTLEMENT"],
        "context": "EFTPOS/Settlement entries are card machine transactions. "
                   "CR (credit) = money IN from card sales → Sales — Card Machine. "
                   "DR (debit) = bank's processing fee → Card Machine Fees. "
                   "Always check CR vs DR in the description."
    },
    {
        "keywords": ["YOCO"],
        "context": "Yoco is a SA card machine provider. Payments IN → Sales — Card Machine. "
                   "Monthly fees → Card Machine Fees or Software Subscription."
    },
    {
        "keywords": ["IKHOKHA"],
        "context": "iKhokha is a SA card machine provider. Same as Yoco — IN = Sales, fees = Card Machine Fees."
    },
    {
        "keywords": ["SPEEDPOINT"],
        "context": "Speedpoint is a bank card terminal. Settlements → Sales — Card Machine. Fees → Card Machine Fees."
    },
    
    # ═══ PAYROLL RELATED ═══
    {
        "keywords": ["SALARY", "SALARIES", "SAL PAYMENT"],
        "context": "Staff salary payment. Ask: Management salary or general staff wages? "
                   "Management → Salaries — Management. Staff → Wages — Staff."
    },
    {
        "keywords": ["WAGE", "WAGES"],
        "context": "Staff wages. Ask: Permanent staff or casual/temp workers? "
                   "Permanent → Wages — Staff. Casual → Wages — Casual / Temp."
    },
    {
        "keywords": ["UIF", "SDL", "PAYE"],
        "context": "Statutory payroll payments to SARS. → PAYE / UIF / SDL Payment."
    },
    {
        "keywords": ["PROVIDENT", "PENSION", "RETIREMENT"],
        "context": "Retirement fund contribution. → Provident Fund Contribution."
    },
    
    # ═══ PROFESSIONAL SERVICES ═══
    {
        "keywords": ["AUDIT", "AUDITOR"],
        "context": "Audit services. → Audit Fees."
    },
    {
        "keywords": ["ATTORNEY", "ADVOCATE", "LEGAL"],
        "context": "Legal services. → Legal Fees. Could also be debt collection — ask if relevant."
    },
    {
        "keywords": ["ACCOUNTANT", "ACCOUNTING", "BOOKKEEP"],
        "context": "Accounting/bookkeeping services. Ask: Monthly bookkeeping or annual accounting/tax? "
                   "Bookkeeping → Bookkeeping Fees. Accounting/tax → Accounting Fees."
    },
    
    # ═══ SUBSCRIPTIONS & SOFTWARE ═══
    {
        "keywords": ["DSTV", "MULTICHOICE"],
        "context": "DStv/MultiChoice subscription. For a guesthouse/restaurant this is a business expense. "
                   "For an office it may be entertainment. → DSTV / Streaming."
    },
    {
        "keywords": ["NETFLIX", "SHOWMAX", "SPOTIFY", "YOUTUBE PREMIUM", "APPLE"],
        "context": "Streaming subscription. Ask: Is this for business (restaurant/guesthouse guests) or personal? "
                   "Business → DSTV / Streaming. Personal → Owner Drawings."
    },
    {
        "keywords": ["MICROSOFT", "OFFICE 365", "M365", "AZURE"],
        "context": "Microsoft subscription — Office 365, Azure cloud, or Teams. → Software Subscription (Monthly)."
    },
    {
        "keywords": ["GOOGLE", "WORKSPACE"],
        "context": "Google services — could be advertising (Google Ads) or workspace subscription. "
                   "Ask: Google Ads or Google Workspace/email? Ads → Advertising — Online. Workspace → Software Subscription."
    },
    {
        "keywords": ["XERO", "SAGE", "QUICKBOOKS", "PASTEL"],
        "context": "Accounting software subscription. → Software Subscription (Monthly)."
    },
    
    # ═══ RETAIL / SUPPLIERS ═══
    {
        "keywords": ["TAKEALOT"],
        "context": "Takealot is SA's biggest online retailer. Could be anything — office supplies, equipment, stock. "
                   "Ask: Office supplies, computer equipment, stock for resale, or cleaning supplies?"
    },
    {
        "keywords": ["MAKRO"],
        "context": "Makro is a bulk wholesaler. For a restaurant → Stock Purchases Food/Beverage. "
                   "For retail → Stock Purchases General. For office → Office Supplies. "
                   "Ask: Stock for resale, food & beverage, cleaning supplies, or office supplies?"
    },
    {
        "keywords": ["BUILDERS", "BUILDERS WAREHOUSE", "BUILD IT", "BUILDWARE"],
        "context": "Building/hardware supplier. Ask: Stock for resale (hardware business), "
                   "building repairs/maintenance, or tools? Resale → Stock Purchases — Hardware. "
                   "Repairs → Repairs & Maintenance — Building. Tools → Small Tools & Consumables."
    },
    {
        "keywords": ["CASHBUILD"],
        "context": "Building materials supplier. Same as Builders — ask: resale stock, repairs, or tools?"
    },
    {
        "keywords": ["SHOPRITE", "CHECKERS", "PICK N PAY", "PNP", "SPAR ", "WOOLWORTHS", "FOOD LOVERS"],
        "context": "Grocery/food retailer. For a restaurant/pub → Stock Purchases — Food & Beverage. "
                   "For an office → Meals — Business. For a B&B → Stock Purchases — Food & Beverage. "
                   "Ask: Food stock for the business (restaurant/B&B), office supplies, or cleaning supplies?"
    },
    {
        "keywords": ["GAME ", "GAME STORES", "INCREDIBLE"],
        "context": "Electronics/appliance retailer. Ask: Computer equipment, office equipment, or business appliance? "
                   "Computer → Computer Equipment & Repairs. Other → Office Supplies."
    },
    
    # ═══ SECURITY ═══
    {
        "keywords": ["ADT", "FIDELITY", "CHUBB", "G4S", "PROTEA COIN", "CSS TACTICAL", "BLUE SECURITY"],
        "context": "Security company. Ask: Armed response/alarm monitoring, guarding, or CCTV maintenance? "
                   "All typically → Security."
    },
    
    # ═══ TRANSPORT & DELIVERY ═══
    {
        "keywords": ["UBER", "BOLT"],
        "context": "Could be ride-hailing or food delivery (Uber Eats). "
                   "Ask: Business transport, Uber Eats for the business, or food delivery for staff? "
                   "Transport → Travel — Local. Food for business → Stock Purchases — Food & Beverage."
    },
    {
        "keywords": ["COURIER", "RAM ", "DAWN WING", "FASTWAY", "THE COURIER GUY", "POSTNET", "PUDO"],
        "context": "Courier/postal services. → Postage & Courier."
    },
    {
        "keywords": ["ARAMEX", "DHL", "FEDEX", "UPS"],
        "context": "International courier. Ask: Import/export delivery or local courier? "
                   "Import → Import Duties / Customs or Delivery / Freight Costs. Local → Postage & Courier."
    },
    
    # ═══ RENT & PROPERTY ═══
    {
        "keywords": ["RENT ", "RENTAL", "HUUR"],
        "context": "Rent payment. Ask: Business premises rent, equipment rental, or vehicle rental? "
                   "Premises → Rent — Business Premises. Equipment → Repairs — Equipment. Vehicle → Vehicle Lease / Finance."
    },
    {
        "keywords": ["RAWSON", "PAM GOLDING", "RE/MAX", "SEEFF", "JUST PROPERTY", "LEWA PROP"],
        "context": "Property management/estate agency — usually monthly rent for business premises. "
                   "→ Rent — Business Premises."
    },
    
    # ═══ ADVERTISING & MARKETING ═══
    {
        "keywords": ["FACEBOOK", "META ", "INSTAGRAM"],
        "context": "Social media advertising. → Advertising — Online / Social Media."
    },
    {
        "keywords": ["GOOGLE ADS", "ADWORDS"],
        "context": "Google advertising. → Advertising — Online / Social Media."
    },
    {
        "keywords": ["VISTAPRINT", "BANNERXPRESS"],
        "context": "Printing and signage. Ask: Business cards/brochures or signage? "
                   "Print → Advertising — Print. Signage → Signage & Branding."
    },
    
    # ═══ TRAVEL ═══
    {
        "keywords": ["FLYSAA", "SAA", "KULULA", "FLYSAFAIR", "AIRLINK", "MANGO"],
        "context": "SA airline. → Travel — Local. If international flight → Travel — International."
    },
    {
        "keywords": ["BOOKING.COM", "AIRBNB", "HOTELS.COM"],
        "context": "Accommodation booking. → Accommodation. Ask if business or personal travel."
    },
    {
        "keywords": ["ACSA", "AIRPORT"],
        "context": "ACSA is SA airports company — this is usually airport parking. → Tolls & Parking."
    },
    {
        "keywords": ["SANRAL", "E-TOLL", "ETOLL", "N1 TOLL", "N3 TOLL", "BAKWENA"],
        "context": "Highway tolls. → Tolls & Parking."
    },
    
    # ═══ ENTERTAINMENT & FOOD ═══
    {
        "keywords": ["WIMPY", "SPUR", "OCEAN BASKET", "NANDOS", "STEERS", "DEBONAIRS", "MCDONALDS", "KFC"],
        "context": "Restaurant/fast food. Ask: Business meeting/client entertainment, staff meal, or personal? "
                   "Client → Entertainment. Staff → Meals — Business. Personal → Owner Drawings. "
                   "SARS WARNING: Limited VAT deduction on entertainment."
    },
    
    # ═══ CLEANING & MAINTENANCE ═══
    {
        "keywords": ["BIDVEST STEINER", "RENTOKIL", "INITIAL HYGIENE"],
        "context": "Hygiene and cleaning services. → Cleaning & Hygiene."
    },
    {
        "keywords": ["PEST CONTROL", "RENTOKIL PEST", "FLICK"],
        "context": "Pest control services. → Pest Control."
    },
    
    # ═══ OWNER / PERSONAL ═══
    {
        "keywords": ["ATM CASH", "ATM WITHDRAWAL", "CASH WITHDRAWAL"],
        "context": "Cash withdrawal. Ask: Business cash (petty cash/float) or owner drawings? "
                   "Business → Transfer Between Accounts. Personal → Owner Drawings."
    },
    {
        "keywords": ["TRANSFER", "TRF ", "INTERACC"],
        "context": "Inter-account transfer. Ask: Between business accounts, to savings, or personal withdrawal? "
                   "Between business accounts → Transfer Between Accounts. Personal → Owner Drawings."
    },
]


def get_relevant_banking_knowledge(description: str, max_chunks: int = 2) -> list:
    """
    Find relevant banking knowledge chunks for a transaction description.
    Returns max_chunks most relevant chunks.
    """
    if not description:
        return []
    
    desc_upper = description.upper()
    matches = []
    
    for chunk in BANKING_CHUNKS:
        for keyword in chunk["keywords"]:
            if keyword.upper() in desc_upper:
                matches.append(chunk)
                break
    
    return matches[:max_chunks]


def format_banking_knowledge(chunks: list) -> str:
    """Format matched chunks for injection into Haiku prompt."""
    if not chunks:
        return ""
    
    lines = ["\nSA CONTEXT:"]
    for chunk in chunks:
        lines.append(chunk["context"])
    
    return "\n".join(lines)
