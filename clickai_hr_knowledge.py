"""
ClickAI HR Knowledge Base — Zane's SA Human Resources Reference
Covers: BCEA detail, disciplinary codes, CCMA, contracts, leave, EE Act, OHS
"""

HR_CHUNKS = [
    {
        "keywords": ["contract", "employment contract", "kontrak", "permanent", "fixed term", "temporary", "casual", "independent contractor", "dienskontrak"],
        "title": "Employment Contract Types",
        "content": """Types of Employment in SA:

Permanent (Indefinite): No end date. Full benefits apply. Can only end by resignation, dismissal (fair reason + procedure), retrenchment, or retirement. Most common.

Fixed-Term: Has a specific end date. Cannot exceed 3 months for employees earning below BCEA threshold UNLESS justified reason (project-based, seasonal, genuine fixed task). If renewed repeatedly → deemed permanent (LRA Section 198B). Must give same benefits as permanent after 3 months.

Part-Time: Works fewer hours than full-time. MUST receive same hourly rate and pro-rata benefits as comparable full-time employee (no discrimination). E.g. if full-timers get medical aid, part-timers must get proportional contribution.

Casual/Temporary: Works less than 24 hours/month. Limited BCEA protection. No leave entitlement. Risky — SARS may reclassify as employee if criteria met.

Independent Contractor: NOT an employee. Issues invoices. Manages own tax (provisional). BUT: SARS uses "dominant impression" test. If you control WHEN, WHERE, HOW they work → they're likely an employee regardless of contract title. Misclassification → backdated PAYE, UIF, SDL plus penalties.

What MUST Be in an Employment Contract: Names of parties, place of work, job title/description, start date, working hours, remuneration (amount and frequency), leave entitlement, notice period, any probation terms, reference to disciplinary code. Provide within first day of employment."""
    },
    {
        "keywords": ["discipline", "misconduct", "code", "procedure", "warning", "hearing", "enquiry", "suspension", "sanction"],
        "title": "Disciplinary Code & Procedure",
        "content": """Building a Fair Disciplinary System:

Progressive Discipline Framework:
- Category 1 (Minor): Late arrival, untidy appearance, personal calls → Verbal warning → Written warning → Final warning → Dismissal
- Category 2 (Serious): Negligence, absence without leave, insubordination → Written warning → Final warning → Dismissal
- Category 3 (Gross): Theft, fraud, assault, intoxication on duty, sexual harassment → Immediate suspension (with pay) → Disciplinary hearing → Possible summary dismissal

Disciplinary Hearing Procedure:
1. Written notice (at least 48 hours before hearing)
2. Notice must state: charges, date/time/venue, right to representation (colleague or union rep — NOT attorney unless both agree), right to call witnesses
3. Hearing: employer presents case → employee responds → both call witnesses → chairperson decides
4. Chairperson must be impartial (not the complainant)
5. Sanction: verbal/written/final warning, suspension without pay (max amount = period of notice), demotion (if agreed), or dismissal
6. Written outcome within 5 working days
7. Right to appeal (usually to higher management or separate appeal body)

Key Principles: Consistent treatment (similar offences = similar sanctions). Consider: severity, circumstances, length of service, previous record, remorse. ALWAYS document everything — contemporaneous notes are gold at CCMA.

Suspension: With full pay pending investigation is standard. Without pay = a sanction (must follow hearing first). Max suspension without pay: equivalent to notice period."""
    },
    {
        "keywords": ["leave", "verlof", "annual", "sick", "maternity", "family", "absent", "afwesig", "how many days", "hoeveel dae"],
        "title": "Leave Management — Complete Guide",
        "content": """Leave Types and Management:

Annual Leave: 21 consecutive days per cycle (= 15 working days for 5-day week). Accrues monthly (1.25 days/month). Must take within 6 months of end of cycle. Employer can determine WHEN leave is taken (with agreement). Paid out on termination. Cannot be forfeited without agreement.

Sick Leave: 30 paid days per 36-month cycle. First 6 months: 1 day per 26 worked. Medical certificate required if absent more than 2 consecutive days, or more than twice in 8 weeks. Employer CAN require certificate for 1-2 day absence if pattern of Monday/Friday absences. Unused sick leave does NOT carry over and is NOT paid out.

Family Responsibility: 3 paid days per year. For: birth of child, illness of child, death of spouse/life partner/parent/adoptive parent/grandparent/child/grandchild/sibling. Employer can require proof (death certificate, medical note, birth certificate).

Maternity: 4 consecutive months (start anytime from 4 weeks before due date, or earlier if doctor orders). Unpaid by employer — claim from UIF (up to 66% of salary, capped). Must give 4 weeks written notice. Cannot be dismissed for pregnancy. Must return to same or equivalent position.

Parental Leave: 10 consecutive days on birth/adoption of child. Applies to ALL parents (father, same-sex partner, adoptive, commissioning parent in surrogacy). Unpaid by employer — claim from UIF.

Compassionate/Special: Not in BCEA but many employers offer 3-5 days for death of close family. Religious/cultural leave: accommodate if reasonable.

Leave Abuse: Pattern of Monday/Friday absences, frequent 1-2 day sick leave, extending long weekends. Address through: require medical certificates, counsel employee, progressive discipline if persists. Don't just dock pay without following process."""
    },
    {
        "keywords": ["equity", "employment equity", "ee", "affirmative", "designated", "transformation", "report", "plan"],
        "title": "Employment Equity Act (EE)",
        "content": """Employment Equity Act 55 of 1998:

Who Must Comply: Designated employers — those with 50+ employees OR annual turnover above threshold (varies by sector, ~R2m-R25m). If you're designated, you MUST have an EE plan and submit annual reports.

What's Required:
1. EE Plan: Analyse workforce profile. Identify barriers to diversity. Set numerical targets (NOT quotas). Develop measures to achieve targets. 3-5 year plan, reviewed annually.
2. Annual EE Report: Submit to Department of Employment & Labour. Due by 15 January (online) or 1 October (manual). Late filing → fine up to R1.5 million.
3. Senior Management Appointment (EEA12 form): When appointing someone in top management, must report to Director-General.
4. Income Differentials: Must report on pay gaps between designated/non-designated groups. If unjustified → must take steps to address.

Designated Groups: Black people (African, Coloured, Indian), women, persons with disabilities.

Penalties (amended 2024): Non-compliance fines substantially increased. Can be 1.5%-10% of annual turnover. DG Review can assess and impose compliance orders.

For Small Employers (under 50): Not designated unless above turnover threshold. No EE plan required. BUT: Still cannot discriminate (Section 6). Unfair discrimination complaints can still go to CCMA/Labour Court regardless of size.

Practical: If you have 50+ employees, get an EE consultant to help with your first plan. It's not as scary as it sounds — mostly documenting what you're already doing and setting reasonable targets."""
    },
    {
        "keywords": ["health", "safety", "ohs", "ohsa", "injury", "accident", "coida", "compensation", "iod", "gesondheid", "veiligheid"],
        "title": "Occupational Health & Safety (OHS Act)",
        "content": """OHS Act 85 of 1993 — Every employer must provide a safe workplace:

Key Obligations:
- Provide and maintain safe working environment
- Identify hazards and assess risks
- Appoint Health & Safety Representatives (1 per 20 employees in same workplace)
- Establish Health & Safety Committee (if 2+ reps appointed)
- Provide training on hazards and safety procedures
- Provide PPE (Personal Protective Equipment) at employer's cost
- Report certain incidents to Department of Labour

Section 16(1) Appointment: CEO/Owner must appoint someone to manage OHS (usually sign appointment letter making yourself the 16.1 appointee, then delegate 16.2 appointments to managers/supervisors).

Incidents to Report: Death, injury requiring medical treatment beyond first aid, major incident (explosion, structural collapse, dangerous substance leak). Report within 24 hours to provincial Department of Labour.

COIDA (Compensation for Occupational Injuries and Diseases):
- ALL employers must register (even if only 1 employee)
- Pay annual assessment based on industry category and wage bill
- Covers: medical costs, temporary disability pay (75% of earnings), permanent disability lump sum or pension, death benefits to dependents
- Employee CANNOT sue employer if covered by COIDA (quid pro quo)
- Employer must submit Return of Earnings by 31 March annually

Practical Minimum: Register for COIDA, do a basic risk assessment, provide necessary PPE, keep a first aid kit, have an incident register, put up safety signs. Don't overcomplicate it — just cover the basics and document everything."""
    },
    {
        "keywords": ["hire", "recruit", "interview", "probation", "onboard", "new employee", "aanstel", "nuwe werknemer", "cv", "reference"],
        "title": "Hiring & Onboarding Best Practices",
        "content": """Hiring Right — Legal and Practical:

Pre-Hiring Checklist:
1. Job description (responsibilities, requirements, reporting line)
2. Salary benchmarking (what's market rate for this role in your area)
3. Where to advertise (PNet, LinkedIn, Facebook groups, word of mouth, university career centres)
4. Interview questions prepared (consistent for all candidates — avoid discrimination)

Interview Don'ts (discrimination grounds): Don't ask about pregnancy/family plans, religion, political affiliation, HIV status, disability (unless relevant to job requirements), union membership, ethnicity.

Background Checks: Criminal record (with consent), credit check (only if financially relevant — National Credit Act applies), reference checks (previous employers), qualification verification. All require written consent from candidate.

Probation (Code of Good Practice): Reasonable period — typically 3 months (6 for complex roles). Purpose: assess suitability. Must: set clear performance standards, provide training/guidance, give feedback, allow reasonable time to improve. Can extend once if reasonable. Dismissal during probation: still need reason (unsuitability) and process (shorter, less formal — but still fair).

Onboarding Essentials — Day 1: Signed contract, SARS tax number (IT77 form), banking details, next of kin, copy of ID, copy of qualifications, UIF registration (U-filing), COIDA notification, company policies (disciplinary code, leave policy, IT usage), safety induction.

Employment Tax Registration: Register employee on eFiling for PAYE. Issue IRP5 at year-end. UIF contributions from month 1. SDL payable if total annual remuneration exceeds R500,000."""
    }
]


def get_relevant_hr_knowledge(user_message: str, max_chunks: int = 2) -> list:
    """Find HR knowledge chunks relevant to the user's question"""
    if not user_message:
        return []
    
    msg_lower = user_message.lower()
    scored = []
    
    for chunk in HR_CHUNKS:
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


def format_hr_knowledge(chunks: list) -> str:
    """Format HR chunks for injection into Zane's prompt"""
    if not chunks:
        return ""
    text = "\n\n=== HR KNOWLEDGE (SA Employment & Labour) ===\n"
    for c in chunks:
        text += f"\n### {c['title']}\n{c['content']}\n"
    return text
