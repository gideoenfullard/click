# -*- coding: utf-8 -*-
# ==============================================================================
# CLICKAI SAFETY FILE MODULE v1.0
# ==============================================================================
# AI-Powered OHS Act Safety File Generator for South African businesses
#
# DESIGN: "Dormant until activated" (same pattern as clickai_whatsapp.py)
# - Import via try/except in clickai.py
# - Available as addon feature in business settings
# - When OFF: no menu items, no routes active, zero impact
# - When ON: full safety file wizard, document generation, annual reminders
#
# WHAT IT GENERATES:
# - Generic/Office Safety File (annual, per business)
# - Site-Specific Safety File (per project/client)
#
# DOCUMENTS INCLUDED:
# Section A: OHS Policy
# Section B: Company Details, Emergency Numbers, Organogram
# Section C: Legal Appointments (Section 16.1, 16.2, First Aider, etc.)
# Section D: Training Records / Competencies
# Section E: Risk Assessments (Baseline + Task-specific)
# Section F: Safe Work Procedures / Method Statements
# Section G: Emergency Procedures (Evacuation, Fire, First Aid)
# Section H: PPE Register
# Section I: Incident Register & Reporting
# Section J: Equipment Registers / Inspection Checklists
# Section K: Toolbox Talk Templates & Register
# Section L: COIDA / Letter of Good Standing
# Section M: Contractor Management (Section 37.2 Agreements)
# Section N: MSDS (Material Safety Data Sheets) Register
#
# SUPPORTED INDUSTRIES:
# Construction, Plumbing, Electrical, Manufacturing, Mechanical/Engineering,
# Restaurant/Hospitality, Retail, Cleaning, Security, Landscaping,
# Mining/Quarrying, Agriculture, Transport/Logistics, Office/General
#
# ACTIVATION:
# 1. In Settings → Safety Files → Toggle ON
# 2. Complete business wizard (industry, employees, equipment)
# 3. Generate files on demand
#
# IMPORT IN clickai.py:
#   try:
#       from clickai_safety_file import register_safety_file_routes
#       SAFETY_FILE_MODULE_LOADED = True
#   except ImportError:
#       SAFETY_FILE_MODULE_LOADED = False
#
# REGISTRATION IN clickai.py (after app, db, etc. are defined):
#   try:
#       if SAFETY_FILE_MODULE_LOADED:
#           register_safety_file_routes(app, db, login_required, Auth, generate_id, render_page)
#           logger.info("[SAFETY FILE] Routes registered ✓")
#   except Exception as e:
#       logger.error(f"[SAFETY FILE] Failed to register routes: {e}")
#
# ==============================================================================

import os
import json
import logging
from datetime import datetime, timedelta
from flask import request, jsonify, redirect, session

logger = logging.getLogger("clickai.safety_file")

# ==============================================================================
# INDUSTRY DEFINITIONS — Hazards, PPE, Appointments per industry
# ==============================================================================

INDUSTRY_PROFILES = {
    "construction": {
        "label": "Construction / Building",
        "icon": "🏗️",
        "hazards": [
            "Working at heights / Falls from ladders, scaffolding, roofs",
            "Struck by falling objects or materials",
            "Excavation collapse / Cave-ins",
            "Electrical contact (overhead lines, temporary installations)",
            "Moving machinery and vehicles on site",
            "Manual handling / Heavy lifting injuries",
            "Exposure to cement dust, silica, asbestos",
            "Noise exposure from power tools and machinery",
            "Fire and explosion (hot work, flammable materials)",
            "Structural collapse during demolition",
            "Slip, trip and fall hazards on uneven surfaces",
            "Welding fumes and UV radiation"
        ],
        "ppe": [
            "Hard hat / Safety helmet",
            "Safety boots (steel toe cap)",
            "High-visibility vest/jacket",
            "Safety harness and lanyard (work at heights)",
            "Safety goggles / Face shield",
            "Dust mask / Respirator",
            "Ear plugs / Ear muffs",
            "Gloves (leather/rubber depending on task)",
            "Reflective clothing"
        ],
        "appointments": [
            {"role": "CEO / Managing Director", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS in the organisation"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated day-to-day OHS management"},
            {"role": "Construction Manager", "regulation": "Construction Reg 8(1)", "description": "Manages construction work safety on site"},
            {"role": "Construction Supervisor", "regulation": "Construction Reg 8(7)", "description": "Supervises construction activities and workers"},
            {"role": "Construction Safety Officer", "regulation": "Construction Reg 8(5)", "description": "Full/part-time safety officer for the site"},
            {"role": "Risk Assessor", "regulation": "Construction Reg 9(1)", "description": "Conducts risk assessments for construction activities"},
            {"role": "Fall Protection Plan Compiler", "regulation": "Construction Reg 10(1)", "description": "Compiles fall protection plan (IWH registered)"},
            {"role": "Scaffolding Supervisor", "regulation": "Construction Reg 16(1)", "description": "Supervises erection and use of scaffolding"},
            {"role": "Excavation Supervisor", "regulation": "Construction Reg 13(1)(a)", "description": "Supervises all excavation work"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Portable Electrical Tools Inspector", "regulation": "EMR 10(4)", "description": "Inspects portable electrical equipment"},
            {"role": "Lifting Equipment Inspector", "regulation": "DMR 18(11)", "description": "Inspects lifting tackle and equipment"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters (1 per 20 workers)"},
            {"role": "Stacking & Storage Supervisor", "regulation": "GSR 8", "description": "Supervises safe stacking and storage of materials"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Working at Heights", "Scaffolding Erection and Dismantling", "Excavation and Trenching",
            "Concrete Work", "Demolition", "Bricklaying and Plastering", "Roofing",
            "Steel Erection", "Hot Work (Welding, Cutting, Grinding)", "Electrical Installation",
            "Painting at Heights", "Crane Operations", "Manual Handling of Materials",
            "Use of Power Tools", "Working Near Overhead Power Lines"
        ],
        "regulations": ["Construction Regulations 2014", "General Safety Regulations", "Driven Machinery Regulations",
                         "Electrical Machinery Regulations", "Environmental Regulations for Workplaces",
                         "General Administrative Regulations", "Facilities Regulations"]
    },
    "plumbing": {
        "label": "Plumbing",
        "icon": "🔧",
        "hazards": [
            "Working in confined spaces (manholes, crawl spaces)",
            "Exposure to sewage and biological hazards",
            "Burns from soldering / brazing / hot water systems",
            "Slip, trip and fall on wet surfaces",
            "Working at heights (roof plumbing, geyser installation)",
            "Electrical contact (electric geysers, submersible pumps)",
            "Manual handling / Heavy lifting (pipes, geysers, baths)",
            "Chemical exposure (PVC solvent cement, drain cleaners)",
            "Noise from pipe cutting and grinding equipment",
            "Working in excavations / trenches"
        ],
        "ppe": [
            "Safety boots (steel toe cap, waterproof)",
            "Safety goggles / Face shield",
            "Chemical-resistant gloves",
            "Leather gloves (soldering work)",
            "Dust mask / Respirator (confined spaces)",
            "Ear plugs (grinding/cutting)",
            "High-visibility vest (roadside work)",
            "Hard hat (construction sites)",
            "Safety harness (roof work)",
            "Rubber boots / Waders (sewage work)"
        ],
        "appointments": [
            {"role": "CEO / Managing Director", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated day-to-day OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Portable Electrical Tools Inspector", "regulation": "EMR 10(4)", "description": "Inspects portable electrical equipment"},
            {"role": "Confined Space Supervisor", "regulation": "GSR 5", "description": "Supervises work in confined spaces"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Soldering and Brazing", "PVC Pipe Installation", "Geyser Installation",
            "Working in Confined Spaces (Manholes)", "Drain Cleaning",
            "Excavation for Pipe Installation", "Working at Heights (Roof Plumbing)",
            "Hot Water System Installation", "Use of Power Tools (Pipe Cutting, Grinding)"
        ],
        "regulations": ["General Safety Regulations", "Electrical Machinery Regulations",
                         "Environmental Regulations for Workplaces", "Facilities Regulations",
                         "General Administrative Regulations"]
    },
    "electrical": {
        "label": "Electrical Contracting",
        "icon": "⚡",
        "hazards": [
            "Electrocution / Electrical shock",
            "Arc flash and arc blast",
            "Working at heights (cable trays, electrical panels on walls)",
            "Burns from electrical short circuits",
            "Fire from faulty wiring or overloaded circuits",
            "Working in confined spaces (cable ducts, risers)",
            "Manual handling of heavy switchgear and cable drums",
            "Exposure to hazardous substances (cable jointing compounds)",
            "Slip, trip and fall hazards (cables on floors)",
            "Noise from drilling and cutting equipment"
        ],
        "ppe": [
            "Safety boots (steel toe, electrical-resistant soles)",
            "Insulated gloves (voltage-rated)",
            "Safety goggles / Face shield",
            "Hard hat (construction sites)",
            "High-visibility vest",
            "Arc flash suit / Fire-resistant clothing",
            "Ear plugs (drilling/cutting)",
            "Dust mask (chasing walls)",
            "Safety harness (work at heights)"
        ],
        "appointments": [
            {"role": "CEO / Managing Director", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated day-to-day OHS management"},
            {"role": "Installation Electrician", "regulation": "Electrical Installation Reg", "description": "Registered electrician for installations"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Portable Electrical Tools Inspector", "regulation": "EMR 10(4)", "description": "Inspects portable electrical equipment"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Lockout/Tagout Coordinator", "regulation": "GSR", "description": "Manages isolation procedures"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Electrical Installation and Wiring", "Working on Live Equipment (Prohibited — procedure for emergency only)",
            "Lockout/Tagout/Isolation Procedures", "Cable Pulling and Termination",
            "Distribution Board Installation", "Working at Heights (Cable Trays)",
            "Testing and Commissioning", "Use of Power Tools",
            "Working in Confined Spaces (Cable Risers)"
        ],
        "regulations": ["Electrical Installation Regulations", "Electrical Machinery Regulations",
                         "General Safety Regulations", "General Administrative Regulations",
                         "Facilities Regulations"]
    },
    "manufacturing": {
        "label": "Manufacturing / Factory",
        "icon": "🏭",
        "hazards": [
            "Caught in or between machinery / Moving parts",
            "Noise exposure exceeding 85 dB(A)",
            "Manual handling / Repetitive strain injuries",
            "Slip, trip and fall on factory floor",
            "Exposure to hazardous chemicals / Fumes",
            "Fire and explosion (flammable materials, dust)",
            "Forklift and vehicle movement in work areas",
            "Electrical hazards from machinery",
            "Burns from hot surfaces or processes",
            "Falling objects from shelving and storage",
            "Inadequate ventilation / Air quality",
            "Vibration exposure from tools and machinery"
        ],
        "ppe": [
            "Safety boots (steel toe cap)",
            "Safety goggles / Face shield",
            "Ear plugs / Ear muffs",
            "Dust mask / Respirator",
            "Gloves (appropriate to hazard)",
            "Hard hat (where overhead hazards exist)",
            "High-visibility vest",
            "Apron / Protective clothing",
            "Hair net / Head covering (near rotating machinery)"
        ],
        "appointments": [
            {"role": "CEO / Managing Director", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated day-to-day OHS management"},
            {"role": "General Machinery Supervisor", "regulation": "GMR 2(1)", "description": "Supervises operation of machinery"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Stacking & Storage Supervisor", "regulation": "GSR 8", "description": "Supervises safe stacking and storage"},
            {"role": "Portable Electrical Tools Inspector", "regulation": "EMR 10(4)", "description": "Inspects portable electrical equipment"},
            {"role": "Hazardous Chemical Substances Controller", "regulation": "HCS Reg 3(3)", "description": "Manages hazardous chemicals"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"},
            {"role": "PPE Inspector", "regulation": "GSR 2", "description": "Inspects PPE condition and issue"}
        ],
        "method_statements": [
            "Machine Operation (General)", "Forklift Operation",
            "Manual Handling of Heavy Items", "Hot Work (Welding, Cutting, Grinding)",
            "Chemical Handling and Storage", "Lockout/Tagout Procedures",
            "Housekeeping and Cleaning", "Working at Heights (Maintenance)",
            "Confined Space Entry", "Use of Compressed Air/Gas"
        ],
        "regulations": ["General Machinery Regulations", "Driven Machinery Regulations",
                         "Electrical Machinery Regulations", "General Safety Regulations",
                         "Hazardous Chemical Substances Regulations",
                         "Environmental Regulations for Workplaces", "Noise-Induced Hearing Loss Regulations",
                         "Facilities Regulations"]
    },
    "restaurant": {
        "label": "Restaurant / Hospitality / Food Service",
        "icon": "🍽️",
        "hazards": [
            "Burns and scalds from hot surfaces, oil, steam",
            "Slip, trip and fall on wet/greasy kitchen floors",
            "Cuts and lacerations from knives and equipment",
            "Fire (cooking oil, gas appliances)",
            "Manual handling of heavy pots, supplies, gas cylinders",
            "Exposure to cleaning chemicals",
            "Electrical hazards from kitchen appliances",
            "Ergonomic strain from prolonged standing",
            "Food allergen cross-contamination",
            "Gas leak from stoves and heaters"
        ],
        "ppe": [
            "Non-slip safety shoes",
            "Heat-resistant gloves / Oven mitts",
            "Cut-resistant gloves (food preparation)",
            "Apron",
            "Hair net / Chef hat",
            "Chemical-resistant gloves (cleaning)",
            "Safety goggles (deep frying)"
        ],
        "appointments": [
            {"role": "CEO / Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated day-to-day OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Evacuation Controller", "regulation": "GSR", "description": "Manages emergency evacuation"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Deep Frying Procedure", "Knife Handling and Storage",
            "Manual Handling of Gas Cylinders", "Chemical Cleaning Procedures",
            "Fire Suppression System Operation", "Kitchen Equipment Operation",
            "Hot Oil / Grease Handling"
        ],
        "regulations": ["General Safety Regulations", "Environmental Regulations for Workplaces",
                         "Facilities Regulations", "General Administrative Regulations",
                         "Hazardous Chemical Substances Regulations"]
    },
    "retail": {
        "label": "Retail / Shop / Warehouse",
        "icon": "🏪",
        "hazards": [
            "Slip, trip and fall on shop floor",
            "Manual handling of stock and merchandise",
            "Falling objects from shelving / Racking collapse",
            "Robbery / Armed robbery / Violence",
            "Electrical hazards from shop equipment",
            "Fire (stock, electrical, arson)",
            "Ergonomic strain from prolonged standing / Repetitive tasks",
            "Forklift/vehicle movement in loading areas",
            "Cash handling risks",
            "Customer injuries on premises"
        ],
        "ppe": [
            "Safety boots (warehouse staff)",
            "Non-slip shoes (shop floor)",
            "Gloves (stock handling)",
            "High-visibility vest (loading bay)",
            "Hard hat (warehouse/loading bay)"
        ],
        "appointments": [
            {"role": "CEO / Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated day-to-day OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Stacking & Storage Supervisor", "regulation": "GSR 8", "description": "Supervises safe stacking and storage"},
            {"role": "Evacuation Controller", "regulation": "GSR", "description": "Manages emergency evacuation"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Manual Handling and Lifting", "Safe Stacking of Shelves and Racking",
            "Cash Handling Procedure", "Emergency Robbery Procedure",
            "Forklift Operation in Loading Bay", "Cleaning and Housekeeping"
        ],
        "regulations": ["General Safety Regulations", "Environmental Regulations for Workplaces",
                         "Facilities Regulations", "General Administrative Regulations"]
    },
    "cleaning": {
        "label": "Cleaning / Hygiene Services",
        "icon": "🧹",
        "hazards": [
            "Slip, trip and fall on wet surfaces",
            "Chemical exposure (cleaning agents, disinfectants)",
            "Biological hazards (blood, bodily fluids)",
            "Ergonomic strain from repetitive movements",
            "Electrical hazards from cleaning equipment",
            "Working at heights (window cleaning)",
            "Manual handling of equipment and supplies",
            "Needlestick injuries (healthcare environments)"
        ],
        "ppe": [
            "Non-slip safety shoes / Rubber boots",
            "Chemical-resistant gloves",
            "Safety goggles",
            "Dust mask / Respirator",
            "Apron / Protective clothing",
            "Knee pads",
            "Safety harness (window cleaning at heights)"
        ],
        "appointments": [
            {"role": "CEO / Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Hazardous Chemical Substances Controller", "regulation": "HCS Reg 3(3)", "description": "Manages chemical handling"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Chemical Mixing and Handling", "Wet Floor Cleaning Procedure",
            "Window Cleaning at Heights", "Biohazard Cleaning",
            "Machine Cleaning (Floor Scrubber, Carpet Cleaner)",
            "Waste Disposal Procedure"
        ],
        "regulations": ["General Safety Regulations", "Hazardous Chemical Substances Regulations",
                         "Environmental Regulations for Workplaces", "Facilities Regulations"]
    },
    "security": {
        "label": "Security Services",
        "icon": "🛡️",
        "hazards": [
            "Violence and assault from intruders/criminals",
            "Working alone / Lone worker risks",
            "Fatigue from long shifts / Night work",
            "Exposure to extreme weather (outdoor posts)",
            "Slip, trip and fall during patrols",
            "Dog handling injuries",
            "Vehicle accidents (response vehicles)",
            "Stress and psychological trauma (incidents)"
        ],
        "ppe": [
            "Safety boots",
            "High-visibility vest (traffic/parking duties)",
            "Raincoat / Weatherproof jacket",
            "Torch / Flashlight",
            "Protective body armour (armed response)",
            "Gloves (search duties)"
        ],
        "appointments": [
            {"role": "CEO / Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Patrol Procedure", "Access Control Procedure",
            "Armed Response Procedure", "Incident Response and Reporting",
            "Vehicle Operation", "Working Alone / Lone Worker Procedure"
        ],
        "regulations": ["General Safety Regulations", "Facilities Regulations",
                         "General Administrative Regulations"]
    },
    "transport": {
        "label": "Transport / Logistics / Delivery",
        "icon": "🚛",
        "hazards": [
            "Vehicle accidents / Road traffic incidents",
            "Loading/offloading injuries",
            "Manual handling of heavy goods",
            "Fatigue from long driving hours",
            "Forklift accidents in warehouse/depot",
            "Falling objects from vehicles/trailers",
            "Fuel handling and fire risk",
            "Hijacking and robbery",
            "Hazardous goods spills (if applicable)"
        ],
        "ppe": [
            "Safety boots (steel toe cap)",
            "High-visibility vest/jacket",
            "Gloves (loading/unloading)",
            "Hard hat (loading zones)",
            "Ear plugs (noisy environments)"
        ],
        "appointments": [
            {"role": "CEO / Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Stacking & Storage Supervisor", "regulation": "GSR 8", "description": "Supervises safe loading and stacking"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Vehicle Pre-Trip Inspection", "Loading and Offloading Procedure",
            "Forklift Operation", "Manual Handling of Goods",
            "Fuel Handling Procedure", "Long-Distance Driving Procedure",
            "Hijack Response Procedure"
        ],
        "regulations": ["General Safety Regulations", "Driven Machinery Regulations",
                         "Facilities Regulations", "General Administrative Regulations"]
    },
    "office": {
        "label": "Office / General / Professional Services",
        "icon": "🏢",
        "hazards": [
            "Ergonomic strain from prolonged computer use",
            "Slip, trip and fall (cables, wet floors, stairs)",
            "Fire (electrical, kitchen appliances)",
            "Electrical hazards from office equipment",
            "Stress and psychological hazards",
            "Poor indoor air quality / Ventilation",
            "Violence / Robbery",
            "Manual handling of office supplies"
        ],
        "ppe": [
            "Non-slip shoes (wet areas only)",
            "Ergonomic equipment (wrist rest, monitor stand)"
        ],
        "appointments": [
            {"role": "CEO / Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Evacuation Controller", "regulation": "GSR", "description": "Manages emergency evacuation"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Ergonomic Workstation Setup", "Emergency Evacuation Procedure",
            "Fire Extinguisher Use", "First Aid Procedure",
            "Housekeeping and Office Cleaning"
        ],
        "regulations": ["General Safety Regulations", "Environmental Regulations for Workplaces",
                         "Facilities Regulations", "General Administrative Regulations"]
    },
    "mechanical": {
        "label": "Mechanical / Engineering / Workshop",
        "icon": "🔩",
        "hazards": [
            "Caught in or between machinery / Moving parts",
            "Burns from welding, cutting, grinding, hot metal",
            "Noise exposure from equipment and tools",
            "Inhalation of welding fumes, metal dust, solvents",
            "Eye injuries from sparks, grinding debris, UV light",
            "Electrical hazards from workshop equipment",
            "Manual handling of heavy components",
            "Slip, trip and fall on oily/wet workshop floors",
            "Fire and explosion (flammable materials, gas cylinders)",
            "Compressed air/gas hazards",
            "Vehicle movement in workshop"
        ],
        "ppe": [
            "Safety boots (steel toe cap)",
            "Safety goggles / Welding helmet",
            "Ear plugs / Ear muffs",
            "Welding gloves / Leather gloves",
            "Dust mask / Welding respirator",
            "Apron / Fire-resistant clothing",
            "Face shield (grinding)",
            "Hard hat (overhead work)"
        ],
        "appointments": [
            {"role": "CEO / Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated OHS management"},
            {"role": "General Machinery Supervisor", "regulation": "GMR 2(1)", "description": "Supervises operation of machinery"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Portable Electrical Tools Inspector", "regulation": "EMR 10(4)", "description": "Inspects portable electrical equipment"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Welding (MIG, TIG, Arc)", "Grinding and Cutting",
            "Lathe Operation", "Drill Press Operation",
            "Use of Compressed Air", "Gas Cylinder Handling and Storage",
            "Vehicle Lifting (Jacks, Hoists)", "Manual Handling of Heavy Components",
            "Lockout/Tagout Procedure"
        ],
        "regulations": ["General Machinery Regulations", "Driven Machinery Regulations",
                         "Electrical Machinery Regulations", "General Safety Regulations",
                         "Environmental Regulations for Workplaces", "Facilities Regulations",
                         "Noise-Induced Hearing Loss Regulations"]
    },
    "agriculture": {
        "label": "Agriculture / Farming",
        "icon": "🌾",
        "hazards": [
            "Tractor/vehicle rollover and accidents",
            "PTO shaft entanglement",
            "Chemical exposure (pesticides, herbicides, fertilizers)",
            "Animal handling injuries (kicks, bites, crushing)",
            "Heat stress and dehydration",
            "Snake and insect bites",
            "Manual handling of heavy loads (feed, produce)",
            "Machinery entanglement (harvesters, balers)",
            "Electrical hazards (electric fencing, irrigation pumps)",
            "Dam/water drowning risk"
        ],
        "ppe": [
            "Safety boots / Gumboots",
            "Sun hat / Hard hat",
            "Chemical-resistant gloves and coveralls (spraying)",
            "Respirator / Chemical mask (spraying)",
            "Safety goggles",
            "Ear plugs (tractor/machinery)",
            "High-visibility vest",
            "Sunscreen"
        ],
        "appointments": [
            {"role": "Farm Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Hazardous Chemical Substances Controller", "regulation": "HCS Reg 3(3)", "description": "Manages pesticides and chemicals"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Tractor Operation", "Pesticide/Herbicide Application",
            "Animal Handling", "Irrigation System Maintenance",
            "Harvesting Operations", "Chainsaw / Brush Cutter Use",
            "Manual Handling of Produce and Feed"
        ],
        "regulations": ["General Safety Regulations", "Driven Machinery Regulations",
                         "Hazardous Chemical Substances Regulations",
                         "Environmental Regulations for Workplaces", "Facilities Regulations"]
    },
    "landscaping": {
        "label": "Landscaping / Gardening / Tree Felling",
        "icon": "🌳",
        "hazards": [
            "Chainsaw injuries / Kickback",
            "Falling branches and trees",
            "Working at heights (tree climbing)",
            "Noise from machinery (chainsaws, mowers, blowers)",
            "Chemical exposure (herbicides, pesticides)",
            "Manual handling of heavy materials",
            "Heat stress and dehydration",
            "Insect stings and bites",
            "Struck by vehicles on roadside work",
            "Power tool injuries (brush cutters, hedge trimmers)"
        ],
        "ppe": [
            "Safety boots (steel toe cap)",
            "Safety goggles / Face shield",
            "Ear plugs / Ear muffs",
            "Chainsaw chaps / Leg protection",
            "Hard hat with face shield and ear muffs",
            "Gloves (leather/chemical-resistant)",
            "High-visibility vest (roadside work)",
            "Safety harness (tree climbing)",
            "Sunscreen / Sun hat"
        ],
        "appointments": [
            {"role": "Owner / Manager", "regulation": "OHS Act Section 16(1)", "description": "Overall responsibility for OHS"},
            {"role": "Appointed Responsible Person", "regulation": "OHS Act Section 16(2)", "description": "Delegated OHS management"},
            {"role": "First Aider", "regulation": "GSR 3(4)", "description": "Provides first aid treatment"},
            {"role": "Fire Fighter / Marshall", "regulation": "GSR 4", "description": "Fire prevention and emergency response"},
            {"role": "Health & Safety Representative", "regulation": "OHS Act Section 17(1)", "description": "Represents workers on OHS matters"},
            {"role": "Incident Investigator", "regulation": "GAR 9(2)", "description": "Investigates workplace incidents"}
        ],
        "method_statements": [
            "Chainsaw Operation", "Tree Felling Procedure",
            "Brush Cutter / Line Trimmer Use", "Herbicide Application",
            "Working at Heights (Tree Climbing)", "Roadside Work Procedure",
            "Manual Handling of Materials"
        ],
        "regulations": ["General Safety Regulations", "Driven Machinery Regulations",
                         "Environmental Regulations for Workplaces", "Facilities Regulations"]
    }
}

# Emergency numbers (South Africa)
SA_EMERGENCY_NUMBERS = {
    "Police (SAPS)": "10111",
    "Ambulance / Paramedics": "10177",
    "Fire Department": "10177",
    "ER24 Private Ambulance": "084 124",
    "Netcare 911": "082 911",
    "Poison Information Centre": "0861 555 777",
    "Department of Labour": "012 309 4000",
    "Eskom (Electrical Emergency)": "0860 037 566",
    "COIDA (Compensation Commissioner)": "012 319 9000"
}


# ==============================================================================
# SAFETY FILE ENGINE — Core logic
# ==============================================================================

class SafetyFileEngine:
    """
    Core engine for generating OHS-compliant safety files.
    Uses AI (Claude) to generate customised content where needed.
    """

    def __init__(self, db):
        self.db = db

    def get_config(self, business: dict) -> dict:
        """Get safety file config from business settings"""
        try:
            config = business.get("safety_file_config") or {}
            if isinstance(config, str):
                config = json.loads(config)
            return config
        except Exception:
            return {}

    def is_enabled(self, business: dict) -> bool:
        """Check if safety file feature is enabled"""
        config = self.get_config(business)
        return bool(config.get("enabled", False))

    def save_config(self, business_id: str, config: dict):
        """Save safety file config to business"""
        try:
            self.db.update("businesses", business_id, {
                "safety_file_config": json.dumps(config) if isinstance(config, dict) else config
            })
            return True
        except Exception as e:
            logger.error(f"[SAFETY] Config save failed: {e}")
            return False

    def get_industry_profile(self, industry_key: str) -> dict:
        """Get the industry profile with hazards, PPE, appointments etc."""
        return INDUSTRY_PROFILES.get(industry_key, INDUSTRY_PROFILES["office"])

    def get_safety_files(self, business_id: str) -> list:
        """Get all generated safety files for a business"""
        try:
            files = self.db.get("safety_files", {"business_id": business_id}) or []
            files.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return files
        except Exception:
            return []

    def get_safety_file(self, file_id: str) -> dict:
        """Get a single safety file by ID"""
        try:
            return self.db.get_one("safety_files", file_id) or {}
        except Exception:
            return {}

    def generate_file_data(self, business: dict, config: dict, file_type: str = "generic",
                           site_info: dict = None, team_members: list = None) -> dict:
        """
        Generate all safety file data (not the document itself — just the structured data).
        The actual document (PDF/DOCX) is generated separately from this data.
        """
        biz_name = business.get("company_name") or business.get("name", "")
        biz_address = business.get("address", "")
        biz_phone = business.get("phone", "")
        biz_email = business.get("email", "")
        biz_reg = business.get("reg_number", "")
        biz_vat = business.get("vat_number", "")
        industry_key = config.get("industry", "office")
        profile = self.get_industry_profile(industry_key)
        today_str = datetime.now().strftime("%Y-%m-%d")
        year = datetime.now().strftime("%Y")
        expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

        # Get number of employees
        num_employees = config.get("num_employees", 1)
        # H&S reps needed: 1 per 20 employees in same workplace
        num_hs_reps = max(1, num_employees // 20) if num_employees >= 20 else 0
        needs_hs_committee = num_hs_reps >= 2

        # Build employee list for appointments
        employees = team_members or []
        if not employees:
            try:
                employees = self.db.get("team_members", {"business_id": business.get("id")}) or []
            except Exception:
                employees = []

        # CEO/Owner for Section 16(1)
        ceo_name = config.get("ceo_name") or business.get("owner_name", "")
        if not ceo_name and employees:
            # Try to find owner/admin
            for emp in employees:
                if emp.get("role") in ("owner", "admin", "manager"):
                    ceo_name = emp.get("name", "")
                    break
            if not ceo_name:
                ceo_name = employees[0].get("name", "") if employees else ""

        # Site-specific info
        site_name = ""
        site_address = ""
        client_name = ""
        project_description = ""
        if file_type == "site_specific" and site_info:
            site_name = site_info.get("site_name", "")
            site_address = site_info.get("site_address", "")
            client_name = site_info.get("client_name", "")
            project_description = site_info.get("project_description", "")

        # Equipment from config
        equipment = config.get("equipment", [])
        chemicals = config.get("chemicals", [])
        additional_hazards = config.get("additional_hazards", [])

        # Combine hazards
        all_hazards = list(profile["hazards"])
        if additional_hazards:
            all_hazards.extend(additional_hazards)

        # Build the complete safety file data structure
        file_data = {
            "meta": {
                "file_type": file_type,
                "industry": industry_key,
                "industry_label": profile["label"],
                "generated_date": today_str,
                "valid_until": expiry,
                "year": year,
                "version": "1.0"
            },
            "company": {
                "name": biz_name,
                "trading_as": business.get("trading_as", ""),
                "reg_number": biz_reg,
                "vat_number": biz_vat,
                "address": biz_address,
                "phone": biz_phone,
                "email": biz_email,
                "ceo_name": ceo_name,
                "num_employees": num_employees,
                "coida_registration": config.get("coida_number", ""),
                "coida_letter_of_good_standing": config.get("has_coida_log", False)
            },
            "site": {
                "name": site_name,
                "address": site_address,
                "client_name": client_name,
                "project_description": project_description
            } if file_type == "site_specific" else None,
            "emergency_numbers": SA_EMERGENCY_NUMBERS.copy(),
            "nearest_hospital": config.get("nearest_hospital", ""),
            "nearest_hospital_phone": config.get("nearest_hospital_phone", ""),
            "nearest_hospital_address": config.get("nearest_hospital_address", ""),
            "policy": {
                "title": f"Occupational Health and Safety Policy — {biz_name}",
                "commitment": f"{biz_name} is committed to providing a safe and healthy working environment for all employees, contractors, visitors and members of the public who may be affected by our activities, in compliance with the Occupational Health and Safety Act 85 of 1993 and all applicable regulations.",
                "objectives": [
                    "Comply with the OHS Act 85 of 1993 and all applicable regulations",
                    "Identify, assess and control all workplace hazards",
                    "Provide adequate training, information and supervision to all employees",
                    "Provide and maintain safe plant, equipment and systems of work",
                    "Provide appropriate Personal Protective Equipment (PPE) at no cost to employees",
                    "Investigate all incidents and implement corrective actions",
                    "Maintain emergency procedures and ensure all employees are trained",
                    "Consult with employees on matters affecting their health and safety",
                    "Review and update this policy annually or when significant changes occur"
                ],
                "signed_by": ceo_name,
                "date": today_str
            },
            "appointments": profile["appointments"],
            "employees": [{"name": e.get("name", ""), "role": e.get("role", ""), "id_number": ""} for e in employees],
            "hazards": all_hazards,
            "ppe_requirements": profile["ppe"],
            "method_statements": profile["method_statements"],
            "equipment": equipment,
            "chemicals": chemicals,
            "applicable_regulations": profile["regulations"],
            "num_hs_reps_required": num_hs_reps,
            "needs_hs_committee": needs_hs_committee,
            "registers": [
                "Attendance / Site Entry Register",
                "PPE Issue Register",
                "Toolbox Talk Register",
                "Equipment Inspection Register",
                "Ladder Inspection Register",
                "First Aid Register",
                "Incident / Accident Register",
                "Fire Equipment Inspection Register",
                "Chemical Register (MSDS)",
                "Training Register",
                "Visitor Register"
            ]
        }

        return file_data


# ==============================================================================
# ROUTE REGISTRATION — Same pattern as clickai_whatsapp.py
# ==============================================================================

def register_safety_file_routes(app, db, login_required, Auth, generate_id, render_page=None):
    """
    Register all Safety File routes.
    Called from clickai.py after app and db are defined.

    This creates:
    - Settings page for Safety File config
    - Wizard for business profile setup
    - Safety file generation endpoint
    - Safety file listing and view pages
    - PDF/DOCX download endpoints
    """

    engine = SafetyFileEngine(db)

    # ------------------------------------------------------------------
    # SETTINGS PAGE
    # ------------------------------------------------------------------

    @app.route("/settings/safety-files")
    @login_required
    def safety_file_settings():
        """Safety File feature settings and business profile"""
        business = Auth.get_current_business()
        if not business:
            return redirect("/settings")

        user = Auth.get_current_user()
        config = engine.get_config(business)
        enabled = config.get("enabled", False)
        industry = config.get("industry", "")
        completed_setup = config.get("setup_complete", False)

        # Build industry options
        industry_options = ""
        for key, prof in INDUSTRY_PROFILES.items():
            sel = "selected" if key == industry else ""
            industry_options += f'<option value="{key}" {sel}>{prof["icon"]} {prof["label"]}</option>'

        # Equipment list
        equipment_list = config.get("equipment", [])
        equipment_tags = "".join(f'<span class="tag" onclick="removeEquip(this)">{e} ✕</span>' for e in equipment_list)

        # Pre-build disabled style (Python 3.11 f-string compat)
        disabled_style = "pointer-events:none;opacity:0.5;" if not enabled else ""
        toggle_bg = "rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3)" if enabled else "rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1)"
        toggle_label = "Active ✅" if enabled else "Inactive"
        toggle_desc = "Generate safety files from the Safety Files menu" if enabled else "Complete setup below to activate"
        toggle_checked = "checked" if enabled else ""
        toggle_knob_bg = "var(--green)" if enabled else "#555"
        toggle_knob_left = "26px" if enabled else "3px"
        setup_display = "block" if enabled else "none"
        preview_display = "block" if industry else "none"

        # Chemical list
        chemical_list = config.get("chemicals", [])
        chemical_tags = "".join(f'<span class="tag" onclick="removeChem(this)">{c} ✕</span>' for c in chemical_list)

        content = f'''
        <div class="card" style="max-width:800px;">
            <h2 style="margin-bottom:5px;">🛡️ AI Safety File Generator</h2>
            <p style="color:var(--text-muted);margin-bottom:25px;">
                Generate OHS Act-compliant safety files for your business — customised by AI for your specific industry and operations.
            </p>

            <form id="sfForm">
                <!-- MASTER TOGGLE -->
                <div style="display:flex;align-items:center;justify-content:space-between;
                            padding:15px;border-radius:10px;margin-bottom:20px;
                            background:{toggle_bg};\"">
                    <div>
                        <strong>Safety Files {toggle_label}</strong><br>
                        <small style="color:var(--text-muted);">
                            {toggle_desc}
                        </small>
                    </div>
                    <label style="position:relative;display:inline-block;width:50px;height:26px;cursor:pointer;">
                        <input type="checkbox" id="sfEnabled" name="enabled"
                               {toggle_checked}
                               style="opacity:0;width:0;height:0;"
                               onchange="document.getElementById('setupSection').style.display=this.checked?'block':'none'">
                        <span style="position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;
                                     background:{toggle_knob_bg};border-radius:26px;transition:.3s;">
                        </span>
                        <span style="position:absolute;height:20px;width:20px;left:{toggle_knob_left};
                                     bottom:3px;background:white;border-radius:50%;transition:.3s;">
                        </span>
                    </label>
                </div>

                <!-- SETUP SECTION -->
                <div id="setupSection" style="display:{setup_display};">

                    <!-- INDUSTRY -->
                    <div class="form-group">
                        <label class="form-label">Industry / Type of Work *</label>
                        <select id="sfIndustry" class="form-input" onchange="updateIndustryPreview()">
                            <option value="">— Select your industry —</option>
                            {industry_options}
                        </select>
                    </div>

                    <!-- EMPLOYEES -->
                    <div class="form-group">
                        <label class="form-label">Number of Employees *</label>
                        <input type="number" id="sfEmployees" class="form-input" min="1" max="9999"
                               value="{config.get('num_employees', 1)}" placeholder="e.g. 5">
                        <small style="color:var(--text-muted);">H&S Reps required from 20+ employees</small>
                    </div>

                    <!-- CEO / OWNER NAME -->
                    <div class="form-group">
                        <label class="form-label">CEO / Owner / Director Name (for Section 16.1 appointment) *</label>
                        <input type="text" id="sfCeo" class="form-input"
                               value="{config.get('ceo_name', '')}" placeholder="e.g. Deon Fullard">
                    </div>

                    <!-- COIDA -->
                    <div class="form-group">
                        <label class="form-label">COIDA Registration Number</label>
                        <input type="text" id="sfCoida" class="form-input"
                               value="{config.get('coida_number', '')}" placeholder="e.g. W123456789">
                        <small style="color:var(--text-muted);">From Compensation Commissioner</small>
                    </div>

                    <!-- NEAREST HOSPITAL -->
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <div class="form-group">
                            <label class="form-label">Nearest Hospital / Clinic</label>
                            <input type="text" id="sfHospital" class="form-input"
                                   value="{config.get('nearest_hospital', '')}" placeholder="e.g. Milpark Hospital">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Hospital Phone</label>
                            <input type="text" id="sfHospitalPhone" class="form-input"
                                   value="{config.get('nearest_hospital_phone', '')}" placeholder="e.g. 011 480 5600">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Hospital Address</label>
                        <input type="text" id="sfHospitalAddr" class="form-input"
                               value="{config.get('nearest_hospital_address', '')}" placeholder="e.g. 9 Guild Rd, Parktown">
                    </div>

                    <!-- EQUIPMENT -->
                    <div class="form-group">
                        <label class="form-label">Equipment / Machinery Used</label>
                        <div style="display:flex;gap:8px;margin-bottom:8px;">
                            <input type="text" id="sfEquipInput" class="form-input" placeholder="e.g. Angle grinder"
                                   onkeydown="if(event.key==='Enter'){{event.preventDefault();addEquip();}}">
                            <button type="button" class="btn btn-secondary" onclick="addEquip()" style="white-space:nowrap;">+ Add</button>
                        </div>
                        <div id="equipList" style="display:flex;flex-wrap:wrap;gap:6px;">{equipment_tags}</div>
                    </div>

                    <!-- CHEMICALS -->
                    <div class="form-group">
                        <label class="form-label">Chemicals / Hazardous Substances Used</label>
                        <div style="display:flex;gap:8px;margin-bottom:8px;">
                            <input type="text" id="sfChemInput" class="form-input" placeholder="e.g. PVC solvent cement"
                                   onkeydown="if(event.key==='Enter'){{event.preventDefault();addChem();}}">
                            <button type="button" class="btn btn-secondary" onclick="addChem()" style="white-space:nowrap;">+ Add</button>
                        </div>
                        <div id="chemList" style="display:flex;flex-wrap:wrap;gap:6px;">{chemical_tags}</div>
                    </div>

                    <!-- INDUSTRY PREVIEW -->
                    <div id="industryPreview" style="display:{preview_display};margin-top:20px;
                                padding:15px;border-radius:10px;background:rgba(139,92,246,0.1);border:1px solid rgba(139,92,246,0.3);">
                        <strong>Industry Profile Preview</strong>
                        <div id="previewContent" style="margin-top:10px;font-size:0.9em;color:var(--text-muted);">
                            Select an industry to see what will be generated.
                        </div>
                    </div>

                    <!-- SAVE -->
                    <button type="button" class="btn btn-primary" onclick="saveSafetyConfig()" style="width:100%;margin-top:20px;">
                        💾 Save Safety File Configuration
                    </button>
                </div>
            </form>
        </div>

        <!-- GENERATED FILES LIST -->
        <div class="card" style="max-width:800px;margin-top:20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3>📄 Generated Safety Files</h3>
                <div style="display:flex;gap:8px;">
                    <a href="/safety-files/generate?type=generic" class="btn btn-primary" style="{disabled_style}">
                        🏢 Generate Office File
                    </a>
                    <a href="/safety-files/generate?type=site_specific" class="btn btn-secondary" style="{disabled_style}">
                        🏗️ Generate Site File
                    </a>
                </div>
            </div>
            <div id="filesList">Loading...</div>
        </div>

        <style>
            .tag {{
                display:inline-block; padding:4px 10px; border-radius:15px;
                background:rgba(139,92,246,0.15); color:var(--text); font-size:0.85em;
                cursor:pointer; border:1px solid rgba(139,92,246,0.3);
            }}
            .tag:hover {{ background:rgba(239,68,68,0.2); border-color:rgba(239,68,68,0.4); }}
        </style>

        <script>
        const industryProfiles = {json.dumps({k: {"label": v["label"], "hazards": v["hazards"][:5], "ppe": v["ppe"][:4], "appointments_count": len(v["appointments"]), "method_statements_count": len(v["method_statements"])} for k, v in INDUSTRY_PROFILES.items()})};

        function updateIndustryPreview() {{
            const sel = document.getElementById('sfIndustry').value;
            const prev = document.getElementById('industryPreview');
            const content = document.getElementById('previewContent');
            if (!sel || !industryProfiles[sel]) {{ prev.style.display = 'none'; return; }}
            const p = industryProfiles[sel];
            prev.style.display = 'block';
            content.innerHTML = '<strong>' + p.label + '</strong><br>' +
                '<br><strong>Top hazards:</strong> ' + p.hazards.join(', ') +
                '<br><br><strong>PPE required:</strong> ' + p.ppe.join(', ') +
                '<br><br><strong>Legal appointments:</strong> ' + p.appointments_count + ' positions' +
                '<br><strong>Method statements:</strong> ' + p.method_statements_count + ' procedures' +
                '<br><br><em>Full list will be in your generated safety file.</em>';
        }}

        function getEquipList() {{
            return Array.from(document.querySelectorAll('#equipList .tag')).map(t => t.textContent.replace(' ✕','').trim());
        }}
        function getChemList() {{
            return Array.from(document.querySelectorAll('#chemList .tag')).map(t => t.textContent.replace(' ✕','').trim());
        }}

        function addEquip() {{
            const input = document.getElementById('sfEquipInput');
            const val = input.value.trim();
            if (!val) return;
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.textContent = val + ' ✕';
            tag.onclick = function() {{ this.remove(); }};
            document.getElementById('equipList').appendChild(tag);
            input.value = '';
            input.focus();
        }}

        function addChem() {{
            const input = document.getElementById('sfChemInput');
            const val = input.value.trim();
            if (!val) return;
            const tag = document.createElement('span');
            tag.className = 'tag';
            tag.textContent = val + ' ✕';
            tag.onclick = function() {{ this.remove(); }};
            document.getElementById('chemList').appendChild(tag);
            input.value = '';
            input.focus();
        }}

        function removeEquip(el) {{ el.remove(); }}
        function removeChem(el) {{ el.remove(); }}

        async function saveSafetyConfig() {{
            const data = {{
                enabled: document.getElementById('sfEnabled').checked,
                industry: document.getElementById('sfIndustry').value,
                num_employees: parseInt(document.getElementById('sfEmployees').value) || 1,
                ceo_name: document.getElementById('sfCeo').value,
                coida_number: document.getElementById('sfCoida').value,
                nearest_hospital: document.getElementById('sfHospital').value,
                nearest_hospital_phone: document.getElementById('sfHospitalPhone').value,
                nearest_hospital_address: document.getElementById('sfHospitalAddr').value,
                equipment: getEquipList(),
                chemicals: getChemList()
            }};

            if (data.enabled && !data.industry) {{
                alert('Please select your industry');
                return;
            }}

            try {{
                const resp = await fetch('/api/safety-files/config', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(data)
                }});
                const result = await resp.json();
                if (result.success) {{
                    alert('Safety File settings saved!');
                    location.reload();
                }} else {{
                    alert('Error: ' + (result.error || 'Unknown'));
                }}
            }} catch (err) {{
                alert('Network error: ' + err.message);
            }}
        }}

        // Load existing files
        async function loadFiles() {{
            try {{
                const resp = await fetch('/api/safety-files/list');
                const result = await resp.json();
                const container = document.getElementById('filesList');
                if (!result.files || result.files.length === 0) {{
                    container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px;">No safety files generated yet. Click "Generate" above to create your first file.</p>';
                    return;
                }}
                let html = '<table class="table" style="width:100%;font-size:0.9em;"><thead><tr><th>Date</th><th>Type</th><th>Industry</th><th>Valid Until</th><th>Actions</th></tr></thead><tbody>';
                result.files.forEach(f => {{
                    const typeLabel = f.file_type === 'site_specific' ? '🏗️ Site: ' + (f.site_name || 'Unknown') : '🏢 Office / Generic';
                    html += '<tr>' +
                        '<td>' + (f.created_at || '').substring(0,10) + '</td>' +
                        '<td>' + typeLabel + '</td>' +
                        '<td>' + (f.industry_label || '') + '</td>' +
                        '<td>' + (f.valid_until || '') + '</td>' +
                        '<td>' +
                            '<a href="/safety-files/view/' + f.id + '" class="btn btn-sm" style="margin-right:4px;">👁️ View</a>' +
                            '<a href="/api/safety-files/download/' + f.id + '" class="btn btn-sm btn-primary">📥 Download</a>' +
                        '</td></tr>';
                }});
                html += '</tbody></table>';
                container.innerHTML = html;
            }} catch (err) {{
                document.getElementById('filesList').innerHTML = '<p style="color:var(--red);">Error loading files</p>';
            }}
        }}
        loadFiles();

        // Auto-show preview
        if (document.getElementById('sfIndustry').value) updateIndustryPreview();
        </script>
        '''

        if render_page:
            return render_page("Safety File Settings", content, user, "safety_files")
        return content

    # ------------------------------------------------------------------
    # API: Save Config
    # ------------------------------------------------------------------

    @app.route("/api/safety-files/config", methods=["POST"])
    @login_required
    def api_safety_file_config():
        """Save safety file configuration"""
        business = Auth.get_current_business()
        if not business:
            return jsonify({"success": False, "error": "No business"})

        try:
            data = request.get_json()
            config = engine.get_config(business)
            config.update({
                "enabled": data.get("enabled", False),
                "industry": data.get("industry", ""),
                "num_employees": data.get("num_employees", 1),
                "ceo_name": data.get("ceo_name", ""),
                "coida_number": data.get("coida_number", ""),
                "nearest_hospital": data.get("nearest_hospital", ""),
                "nearest_hospital_phone": data.get("nearest_hospital_phone", ""),
                "nearest_hospital_address": data.get("nearest_hospital_address", ""),
                "equipment": data.get("equipment", []),
                "chemicals": data.get("chemicals", []),
                "setup_complete": bool(data.get("industry")),
                "updated_at": datetime.now().isoformat()
            })

            success = engine.save_config(business.get("id"), config)
            return jsonify({"success": success})
        except Exception as e:
            logger.error(f"[SAFETY] Config save error: {e}")
            return jsonify({"success": False, "error": str(e)})

    # ------------------------------------------------------------------
    # API: List Files
    # ------------------------------------------------------------------

    @app.route("/api/safety-files/list")
    @login_required
    def api_safety_file_list():
        """List all generated safety files"""
        business = Auth.get_current_business()
        if not business:
            return jsonify({"files": []})

        files = engine.get_safety_files(business.get("id"))
        return jsonify({"files": [
            {
                "id": f.get("id"),
                "file_type": f.get("file_type", "generic"),
                "site_name": f.get("site_name", ""),
                "industry_label": f.get("industry_label", ""),
                "valid_until": f.get("valid_until", ""),
                "created_at": f.get("created_at", "")
            } for f in files
        ]})

    # ------------------------------------------------------------------
    # GENERATE PAGE — Wizard for site-specific or confirm for generic
    # ------------------------------------------------------------------

    @app.route("/safety-files/generate")
    @login_required
    def safety_file_generate_page():
        """Safety file generation wizard"""
        business = Auth.get_current_business()
        if not business:
            return redirect("/settings/safety-files")

        user = Auth.get_current_user()
        config = engine.get_config(business)

        if not config.get("enabled") or not config.get("industry"):
            return redirect("/settings/safety-files")

        file_type = request.args.get("type", "generic")
        profile = engine.get_industry_profile(config.get("industry", "office"))
        biz_name = business.get("company_name") or business.get("name", "")

        if file_type == "site_specific":
            # Show site-specific wizard
            content = f'''
            <div class="card" style="max-width:700px;">
                <h2>🏗️ Generate Site-Specific Safety File</h2>
                <p style="color:var(--text-muted);margin-bottom:20px;">
                    For: <strong>{biz_name}</strong> ({profile["icon"]} {profile["label"]})
                </p>

                <div class="form-group">
                    <label class="form-label">Site / Project Name *</label>
                    <input type="text" id="siteName" class="form-input" placeholder="e.g. Sandton City Phase 2">
                </div>

                <div class="form-group">
                    <label class="form-label">Site Address *</label>
                    <input type="text" id="siteAddress" class="form-input" placeholder="e.g. 83 Rivonia Rd, Sandton">
                </div>

                <div class="form-group">
                    <label class="form-label">Client / Principal Contractor Name</label>
                    <input type="text" id="clientName" class="form-input" placeholder="e.g. Murray & Roberts">
                </div>

                <div class="form-group">
                    <label class="form-label">Project Description</label>
                    <textarea id="projectDesc" class="form-input" rows="3"
                              placeholder="e.g. Installation of plumbing systems for 3-storey commercial building"></textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">Additional Site-Specific Hazards</label>
                    <textarea id="siteHazards" class="form-input" rows="2"
                              placeholder="e.g. Asbestos in old building, confined space work in basement"></textarea>
                </div>

                <button class="btn btn-primary" onclick="generateFile('site_specific')" style="width:100%;">
                    🛡️ Generate Site-Specific Safety File
                </button>
            </div>

            <script>
            async function generateFile(fileType) {{
                const btn = event.target;
                btn.disabled = true;
                btn.textContent = 'Generating... (this may take 30-60 seconds)';

                const data = {{
                    file_type: fileType,
                    site_name: document.getElementById('siteName').value,
                    site_address: document.getElementById('siteAddress').value,
                    client_name: document.getElementById('clientName').value,
                    project_description: document.getElementById('projectDesc').value,
                    additional_hazards: document.getElementById('siteHazards').value
                }};

                if (!data.site_name || !data.site_address) {{
                    alert('Please fill in Site Name and Address');
                    btn.disabled = false;
                    btn.textContent = '🛡️ Generate Site-Specific Safety File';
                    return;
                }}

                try {{
                    const resp = await fetch('/api/safety-files/generate', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(data)
                    }});
                    const result = await resp.json();
                    if (result.success) {{
                        window.location = '/safety-files/view/' + result.file_id;
                    }} else {{
                        alert('Error: ' + (result.error || 'Generation failed'));
                        btn.disabled = false;
                        btn.textContent = '🛡️ Generate Site-Specific Safety File';
                    }}
                }} catch (err) {{
                    alert('Network error: ' + err.message);
                    btn.disabled = false;
                    btn.textContent = '🛡️ Generate Site-Specific Safety File';
                }}
            }}
            </script>
            '''
        else:
            # Generic — confirm and generate
            content = f'''
            <div class="card" style="max-width:700px;">
                <h2>🏢 Generate Generic / Office Safety File</h2>
                <p style="color:var(--text-muted);margin-bottom:20px;">
                    Annual safety file for <strong>{biz_name}</strong>
                </p>

                <div style="background:rgba(139,92,246,0.1);padding:15px;border-radius:10px;margin-bottom:20px;">
                    <strong>{profile["icon"]} {profile["label"]}</strong><br>
                    <small style="color:var(--text-muted);">
                        {len(profile["hazards"])} hazards identified •
                        {len(profile["appointments"])} legal appointments •
                        {len(profile["method_statements"])} method statements •
                        {len(profile["ppe"])} PPE items
                    </small>
                </div>

                <p>This will generate a complete safety file containing:</p>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:15px 0;font-size:0.9em;">
                    <div>✅ OHS Policy</div>
                    <div>✅ Emergency Procedures</div>
                    <div>✅ Legal Appointment Letters</div>
                    <div>✅ PPE Register Template</div>
                    <div>✅ Risk Assessments</div>
                    <div>✅ Incident Register Template</div>
                    <div>✅ Method Statements</div>
                    <div>✅ Toolbox Talk Templates</div>
                    <div>✅ Emergency Numbers</div>
                    <div>✅ Equipment Registers</div>
                    <div>✅ Company Organogram</div>
                    <div>✅ MSDS Register</div>
                </div>

                <button class="btn btn-primary" onclick="generateGeneric()" style="width:100%;" id="genBtn">
                    🛡️ Generate Safety File Now
                </button>
            </div>

            <script>
            async function generateGeneric() {{
                const btn = document.getElementById('genBtn');
                btn.disabled = true;
                btn.textContent = 'Generating... (this may take 30-60 seconds)';

                try {{
                    const resp = await fetch('/api/safety-files/generate', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ file_type: 'generic' }})
                    }});
                    const result = await resp.json();
                    if (result.success) {{
                        window.location = '/safety-files/view/' + result.file_id;
                    }} else {{
                        alert('Error: ' + (result.error || 'Generation failed'));
                        btn.disabled = false;
                        btn.textContent = '🛡️ Generate Safety File Now';
                    }}
                }} catch (err) {{
                    alert('Network error: ' + err.message);
                    btn.disabled = false;
                    btn.textContent = '🛡️ Generate Safety File Now';
                }}
            }}
            </script>
            '''

        if render_page:
            return render_page("Generate Safety File", content, user, "safety_files")
        return content

    # ------------------------------------------------------------------
    # API: Generate Safety File
    # ------------------------------------------------------------------

    @app.route("/api/safety-files/generate", methods=["POST"])
    @login_required
    def api_safety_file_generate():
        """Generate a safety file and save to database"""
        business = Auth.get_current_business()
        if not business:
            return jsonify({"success": False, "error": "No business"})

        biz_id = business.get("id")
        config = engine.get_config(business)

        if not config.get("enabled") or not config.get("industry"):
            return jsonify({"success": False, "error": "Please complete Safety File setup first"})

        try:
            data = request.get_json() or {}
            file_type = data.get("file_type", "generic")

            site_info = None
            if file_type == "site_specific":
                additional = data.get("additional_hazards", "")
                site_info = {
                    "site_name": data.get("site_name", ""),
                    "site_address": data.get("site_address", ""),
                    "client_name": data.get("client_name", ""),
                    "project_description": data.get("project_description", "")
                }
                # Add additional hazards to config temporarily
                if additional:
                    config["additional_hazards"] = [h.strip() for h in additional.split(",") if h.strip()]

            # Generate the file data
            file_data = engine.generate_file_data(
                business=business,
                config=config,
                file_type=file_type,
                site_info=site_info
            )

            # Save to database
            file_id = generate_id()
            record = {
                "id": file_id,
                "business_id": biz_id,
                "file_type": file_type,
                "industry": config.get("industry", ""),
                "industry_label": file_data["meta"]["industry_label"],
                "site_name": site_info.get("site_name", "") if site_info else "",
                "site_address": site_info.get("site_address", "") if site_info else "",
                "client_name": site_info.get("client_name", "") if site_info else "",
                "valid_until": file_data["meta"]["valid_until"],
                "file_data": json.dumps(file_data),
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "created_by": session.get("user_id", "")
            }

            success, err = db.save("safety_files", record)
            if not success:
                return jsonify({"success": False, "error": f"Save failed: {err}"})

            logger.info(f"[SAFETY] Generated {file_type} file {file_id} for business {biz_id}")
            return jsonify({"success": True, "file_id": file_id})

        except Exception as e:
            logger.error(f"[SAFETY] Generate error: {e}")
            return jsonify({"success": False, "error": str(e)})

    # ------------------------------------------------------------------
    # VIEW: Safety File Detail
    # ------------------------------------------------------------------

    @app.route("/safety-files/view/<file_id>")
    @login_required
    def safety_file_view(file_id):
        """View a generated safety file"""
        business = Auth.get_current_business()
        if not business:
            return redirect("/")

        user = Auth.get_current_user()
        sf = engine.get_safety_file(file_id)
        if not sf:
            return redirect("/settings/safety-files")

        try:
            file_data = json.loads(sf.get("file_data", "{}")) if isinstance(sf.get("file_data"), str) else sf.get("file_data", {})
        except Exception:
            file_data = {}

        meta = file_data.get("meta", {})
        company = file_data.get("company", {})
        policy = file_data.get("policy", {})
        site = file_data.get("site")
        hazards = file_data.get("hazards", [])
        ppe = file_data.get("ppe_requirements", [])
        appointments = file_data.get("appointments", [])
        method_statements = file_data.get("method_statements", [])
        emergency_numbers = file_data.get("emergency_numbers", {})
        registers = file_data.get("registers", [])
        regulations = file_data.get("applicable_regulations", [])

        # Build the view HTML
        type_label = "🏗️ Site-Specific" if sf.get("file_type") == "site_specific" else "🏢 Generic / Office"

        # Site info section
        site_html = ""
        if site:
            site_html = f'''
            <div class="section">
                <h3>📍 Site Information</h3>
                <table class="table" style="width:100%;">
                    <tr><td style="width:200px;font-weight:bold;">Site Name</td><td>{site.get("name", "")}</td></tr>
                    <tr><td style="font-weight:bold;">Site Address</td><td>{site.get("address", "")}</td></tr>
                    <tr><td style="font-weight:bold;">Client</td><td>{site.get("client_name", "")}</td></tr>
                    <tr><td style="font-weight:bold;">Project Description</td><td>{site.get("project_description", "")}</td></tr>
                </table>
            </div>
            '''

        # Emergency numbers
        emerg_rows = "".join(f'<tr><td>{name}</td><td style="font-weight:bold;">{num}</td></tr>' for name, num in emergency_numbers.items())
        nearest = file_data.get("nearest_hospital", "")
        nearest_phone = file_data.get("nearest_hospital_phone", "")
        nearest_addr = file_data.get("nearest_hospital_address", "")
        if nearest:
            emerg_rows += f'<tr style="background:rgba(239,68,68,0.1);"><td><strong>🏥 Nearest Hospital: {nearest}</strong></td><td style="font-weight:bold;">{nearest_phone}<br><small>{nearest_addr}</small></td></tr>'

        # Appointments
        appt_rows = ""
        for i, appt in enumerate(appointments):
            appt_rows += f'''<tr>
                <td>{i+1}</td>
                <td>{appt.get("role", "")}</td>
                <td><small>{appt.get("regulation", "")}</small></td>
                <td><small>{appt.get("description", "")}</small></td>
                <td style="border-bottom:1px dotted var(--border);min-width:150px;"> </td>
                <td style="border-bottom:1px dotted var(--border);min-width:100px;"> </td>
            </tr>'''

        # Hazards
        hazard_rows = "".join(f'<tr><td>{i+1}</td><td>{h}</td><td style="border-bottom:1px dotted var(--border);"> </td><td style="border-bottom:1px dotted var(--border);"> </td></tr>' for i, h in enumerate(hazards))

        # PPE
        ppe_rows = "".join(f'<tr><td>{p}</td><td style="text-align:center;">☐</td><td style="border-bottom:1px dotted var(--border);"> </td></tr>' for p in ppe)

        # Method Statements
        ms_rows = "".join(f'<tr><td>{i+1}</td><td>{ms}</td><td style="border-bottom:1px dotted var(--border);"> </td></tr>' for i, ms in enumerate(method_statements))

        # Registers
        reg_rows = "".join(f'<tr><td>{r}</td><td>☐ In place</td><td>☐ Updated</td></tr>' for r in registers)

        # Regulations
        regs_html = "".join(f'<tr><td>☐</td><td>{r}</td></tr>' for r in regulations)

        # Policy objectives
        objectives_html = "".join(f'<li style="margin-bottom:5px;">{obj}</li>' for obj in policy.get("objectives", []))

        content = f'''
        <style>
            .section {{ margin-bottom:25px; padding:20px; background:rgba(255,255,255,0.03); border-radius:10px; border:1px solid rgba(255,255,255,0.08); }}
            .section h3 {{ margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid rgba(139,92,246,0.3); }}
            .table {{ width:100%; border-collapse:collapse; font-size:0.9em; }}
            .table th, .table td {{ padding:8px 10px; text-align:left; border-bottom:1px solid rgba(255,255,255,0.08); }}
            .table th {{ background:rgba(139,92,246,0.1); font-weight:600; }}
            @media print {{ .no-print {{ display:none !important; }} body {{ background:white; color:black; }} .section {{ border:1px solid #ddd; }} }}
        </style>

        <div class="no-print" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <div>
                <h2 style="margin:0;">🛡️ Safety File — {company.get("name", "")}</h2>
                <small style="color:var(--text-muted);">{type_label} • {meta.get("industry_label", "")} • Generated {meta.get("generated_date", "")} • Valid until {meta.get("valid_until", "")}</small>
            </div>
            <div style="display:flex;gap:8px;">
                <a href="/api/safety-files/download/{file_id}" class="btn btn-primary">📥 Download PDF</a>
                <button class="btn btn-secondary" onclick="window.print()">🖨️ Print</button>
                <a href="/settings/safety-files" class="btn btn-secondary">← Back</a>
            </div>
        </div>

        <!-- COVER PAGE -->
        <div class="section" style="text-align:center;padding:40px;">
            <h1 style="font-size:2em;margin-bottom:10px;">HEALTH AND SAFETY FILE</h1>
            <h2 style="color:var(--primary);margin-bottom:20px;">{company.get("name", "")}</h2>
            {f'<h3>{site.get("name", "")}</h3><p>{site.get("address", "")}</p>' if site else f'<p>{company.get("address", "")}</p>'}
            <p style="margin-top:20px;">In compliance with the<br><strong>Occupational Health and Safety Act 85 of 1993</strong></p>
            <p style="margin-top:20px;">
                <strong>Date:</strong> {meta.get("generated_date", "")}<br>
                <strong>Valid Until:</strong> {meta.get("valid_until", "")}<br>
                <strong>Revision:</strong> {meta.get("version", "1.0")}
            </p>
        </div>

        <!-- SECTION A: OHS POLICY -->
        <div class="section">
            <h3>Section A: Occupational Health and Safety Policy</h3>
            <h4>{policy.get("title", "")}</h4>
            <p>{policy.get("commitment", "")}</p>
            <h4 style="margin-top:15px;">Objectives:</h4>
            <ol>{objectives_html}</ol>
            <div style="margin-top:25px;display:flex;justify-content:space-between;">
                <div>
                    <strong>Signed:</strong> ________________________<br>
                    <small>{policy.get("signed_by", "")}</small><br>
                    <small>CEO / Managing Director</small>
                </div>
                <div>
                    <strong>Date:</strong> ________________________<br>
                    <small>{policy.get("date", "")}</small>
                </div>
            </div>
        </div>

        <!-- SECTION B: COMPANY DETAILS & EMERGENCY NUMBERS -->
        <div class="section">
            <h3>Section B: Company Details & Emergency Numbers</h3>
            <table class="table">
                <tr><td style="width:200px;font-weight:bold;">Company Name</td><td>{company.get("name", "")}</td></tr>
                <tr><td style="font-weight:bold;">Trading As</td><td>{company.get("trading_as", "")}</td></tr>
                <tr><td style="font-weight:bold;">Registration Number</td><td>{company.get("reg_number", "")}</td></tr>
                <tr><td style="font-weight:bold;">VAT Number</td><td>{company.get("vat_number", "")}</td></tr>
                <tr><td style="font-weight:bold;">Address</td><td>{company.get("address", "")}</td></tr>
                <tr><td style="font-weight:bold;">Phone</td><td>{company.get("phone", "")}</td></tr>
                <tr><td style="font-weight:bold;">Email</td><td>{company.get("email", "")}</td></tr>
                <tr><td style="font-weight:bold;">CEO / Director</td><td>{company.get("ceo_name", "")}</td></tr>
                <tr><td style="font-weight:bold;">Number of Employees</td><td>{company.get("num_employees", "")}</td></tr>
                <tr><td style="font-weight:bold;">COIDA Registration</td><td>{company.get("coida_registration", "") or "Not provided"}</td></tr>
            </table>

            <h4 style="margin-top:20px;">Emergency Contact Numbers</h4>
            <table class="table">
                <thead><tr><th>Service</th><th>Number</th></tr></thead>
                <tbody>{emerg_rows}</tbody>
            </table>
        </div>

        {site_html}

        <!-- SECTION C: LEGAL APPOINTMENTS -->
        <div class="section">
            <h3>Section C: Legal Appointments</h3>
            <p style="color:var(--text-muted);margin-bottom:10px;">The following persons are appointed in terms of the OHS Act and applicable regulations.</p>
            <table class="table">
                <thead><tr><th>#</th><th>Role / Position</th><th>Regulation</th><th>Description</th><th>Name</th><th>Signature</th></tr></thead>
                <tbody>{appt_rows}</tbody>
            </table>
            <p style="color:var(--text-muted);margin-top:10px;font-size:0.85em;">
                <strong>Note:</strong> H&S Representatives required: {file_data.get("num_hs_reps_required", 0)} (1 per 20 employees).
                H&S Committee required: {'Yes' if file_data.get("needs_hs_committee") else 'No'} (required when 2+ H&S Reps appointed).
            </p>
        </div>

        <!-- SECTION D: RISK ASSESSMENT -->
        <div class="section">
            <h3>Section D: Risk Assessment</h3>
            <p style="color:var(--text-muted);margin-bottom:10px;">Identified hazards for {meta.get("industry_label", "")} operations.</p>
            <table class="table">
                <thead><tr><th>#</th><th>Hazard</th><th>Control Measures</th><th>Responsible Person</th></tr></thead>
                <tbody>{hazard_rows}</tbody>
            </table>
        </div>

        <!-- SECTION E: PPE REGISTER -->
        <div class="section">
            <h3>Section E: PPE Requirements & Issue Register</h3>
            <table class="table">
                <thead><tr><th>PPE Item</th><th>Required</th><th>Issued To / Date</th></tr></thead>
                <tbody>{ppe_rows}</tbody>
            </table>
        </div>

        <!-- SECTION F: METHOD STATEMENTS -->
        <div class="section">
            <h3>Section F: Safe Work Procedures / Method Statements</h3>
            <p style="color:var(--text-muted);margin-bottom:10px;">The following safe work procedures apply to our operations.</p>
            <table class="table">
                <thead><tr><th>#</th><th>Procedure</th><th>Reviewed By / Date</th></tr></thead>
                <tbody>{ms_rows}</tbody>
            </table>
        </div>

        <!-- SECTION G: EMERGENCY PROCEDURES -->
        <div class="section">
            <h3>Section G: Emergency Procedures</h3>
            <h4>Fire Emergency</h4>
            <ol style="margin-bottom:15px;">
                <li>Raise the alarm — shout "FIRE!" and activate nearest fire alarm (if available)</li>
                <li>Call the fire department: <strong>10177</strong></li>
                <li>Evacuate all persons from the area via designated emergency exits</li>
                <li>If safe to do so and trained, attempt to extinguish the fire using appropriate fire extinguisher</li>
                <li>Assemble at the designated assembly point</li>
                <li>Account for all employees, visitors and contractors</li>
                <li>Do NOT re-enter the building until cleared by fire department</li>
            </ol>

            <h4>Medical Emergency / Injury on Duty</h4>
            <ol style="margin-bottom:15px;">
                <li>Ensure the scene is safe before approaching the injured person</li>
                <li>Call the appointed First Aider immediately</li>
                <li>If serious, call emergency services: <strong>10177</strong> or <strong>082 911</strong> (Netcare)</li>
                <li>Administer first aid within your level of training</li>
                <li>Do NOT move the injured person unless in immediate danger</li>
                <li>Record the incident in the Incident Register (Section 24 OHS Act)</li>
                <li>Report to Department of Labour if required (death, injury requiring medical treatment beyond first aid)</li>
                <li>Complete COIDA WCL1/WCL2 forms if applicable</li>
            </ol>

            <h4>Evacuation Procedure</h4>
            <ol>
                <li>On hearing the evacuation alarm, stop all work immediately</li>
                <li>Switch off all machinery and equipment (if safe to do so)</li>
                <li>Leave the building/site via the nearest emergency exit</li>
                <li>Do NOT use lifts/elevators</li>
                <li>Proceed to the designated assembly point</li>
                <li>Report to the Evacuation Controller for head count</li>
                <li>Remain at the assembly point until given the all-clear</li>
            </ol>
        </div>

        <!-- SECTION H: REGISTERS -->
        <div class="section">
            <h3>Section H: Registers & Checklists</h3>
            <p style="color:var(--text-muted);margin-bottom:10px;">The following registers must be maintained and kept up to date.</p>
            <table class="table">
                <thead><tr><th>Register</th><th>In Place</th><th>Up to Date</th></tr></thead>
                <tbody>{reg_rows}</tbody>
            </table>
        </div>

        <!-- SECTION I: APPLICABLE REGULATIONS -->
        <div class="section">
            <h3>Section I: Applicable Legislation & Regulations</h3>
            <table class="table">
                <thead><tr><th>Available</th><th>Regulation</th></tr></thead>
                <tbody>
                    <tr><td>☐</td><td><strong>Occupational Health and Safety Act 85 of 1993</strong></td></tr>
                    {regs_html}
                </tbody>
            </table>
        </div>

        <!-- SECTION J: DECLARATION -->
        <div class="section" style="text-align:center;">
            <h3>Declaration</h3>
            <p>I, the undersigned, hereby declare that this Health and Safety File has been compiled in accordance with the requirements of the Occupational Health and Safety Act 85 of 1993 and all applicable regulations.</p>
            <p>All information contained herein is accurate to the best of my knowledge.</p>
            <div style="margin-top:30px;display:flex;justify-content:space-around;">
                <div>
                    <strong>Signed:</strong> ________________________<br><br>
                    <strong>Name:</strong> {company.get("ceo_name", "")}<br>
                    <strong>Designation:</strong> CEO / Managing Director<br>
                    <strong>Date:</strong> ________________________
                </div>
            </div>
        </div>
        '''

        if render_page:
            return render_page(f"Safety File — {company.get('name', '')}", content, user, "safety_files")
        return content

    # ------------------------------------------------------------------
    # API: Download as PDF
    # ------------------------------------------------------------------

    @app.route("/api/safety-files/download/<file_id>")
    @login_required
    def api_safety_file_download(file_id):
        """Download safety file as PDF (using print-to-PDF fallback)"""
        # For now, redirect to view page with print instruction
        # Full PDF generation can be added later using weasyprint/pdfkit
        return redirect(f"/safety-files/view/{file_id}?print=1")

    # ------------------------------------------------------------------
    # SAFETY FILES MAIN PAGE
    # ------------------------------------------------------------------

    @app.route("/safety-files")
    @login_required
    def safety_files_page():
        """Main safety files page — redirect to settings"""
        return redirect("/settings/safety-files")

    # ------------------------------------------------------------------
    # Expose engine
    # ------------------------------------------------------------------
    app.safety_file_engine = engine

    logger.info("[SAFETY FILE] Module loaded and routes registered ✓")

    return engine


# ==============================================================================
# SQL: Database table creation (run once in Supabase)
# ==============================================================================

SAFETY_FILES_SQL = """
CREATE TABLE IF NOT EXISTS safety_files (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    file_type TEXT DEFAULT 'generic',
    industry TEXT,
    industry_label TEXT,
    site_name TEXT DEFAULT '',
    site_address TEXT DEFAULT '',
    client_name TEXT DEFAULT '',
    valid_until TEXT,
    file_data JSONB DEFAULT '{}',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_safety_files_business ON safety_files(business_id);
CREATE INDEX IF NOT EXISTS idx_safety_files_type ON safety_files(file_type);
CREATE INDEX IF NOT EXISTS idx_safety_files_created ON safety_files(created_at DESC);
"""

# ==============================================================================
# BUSINESS TABLE: Add safety_file_config column (run once)
# ==============================================================================

SAFETY_FILE_CONFIG_SQL = """
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS safety_file_config JSONB DEFAULT '{}';
"""
