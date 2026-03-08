"""
FULLTECH STAINLESS STEEL CALCULATOR
From actual Fulltech price lists 2024/2025
"""

import math

# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT FACTORS (kg/dm³)
# ═══════════════════════════════════════════════════════════════════════════════

WEIGHT_FACTORS = {
    "304": 8.07,
    "316": 8.07,
    "430": 8.0,
    "409": 8.0,
    "441": 8.0,
    "3CR12": 8.0,
    "3CR12 3mm+": 8.2,
    "4.5": 8.2,
    "Bennox": 8.3,
    "4509": 7.9,
    "Aluminium": 2.7,
}

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET & COIL FINISHING - Per SQM
# Coils up to 2mm = same as cold rolled sheet prices
# ═══════════════════════════════════════════════════════════════════════════════

# Cold rolled (up to 3mm thickness)
FINISH_COLD = {
    "N4 + PVC": 34.08,
    "N4 LASER PVC": 34.08,
    "LASER PVC": 28.78,
    "PVC ONLY": 28.78,
    "PLAIN PVC": 27.36,
    "N4 ONLY": 9.84,
    "N4": 9.84,
    "0.5MM N4": 25.76,
    "SATIN": 18.91,
    "3CR12": 38.23,
    "409": 38.23,
    "80#": 38.23,
    "ALUMINIUM": 19.50,
    "COLD ROLLED NO PVC": 136.00,
}

# Hot rolled (above 3mm thickness)
FINISH_HOT = {
    "N4 ONLY": 325.40,
    "N4": 325.40,
    "6MM N4 PVC": 371.56,
    "8MM N4 PVC": 378.54,
    "10MM N4 PVC": 385.50,
}

# Large plates (6000x1500) - fixed prices per sheet
LARGE_PLATES = {
    "6000x1500x3.0": 146.59,
    "6000x1500x4.5": 463.05,
    "6000x1500x8.0": 1477.96,
}

# Berrick small coils
COIL_FINISH = {
    "N4 + PVC": 58.53,
    "N4 PVC": 58.53,
    "PVC ONLY": 31.35,
    "LASER PVC": 31.35,
    "N4 ONLY": 29.00,
    "N4": 29.00,
}

MIN_CHARGE_JOB = 145.00
MIN_CHARGE_PIECE = 222.52

# ═══════════════════════════════════════════════════════════════════════════════
# SHEET/PLATE PIECE PRICES - Per SQM
# Standard sheet: 2500 x 1250mm
# Pieces smaller than standard: +40% if >= 1sqm, +60% if < 1sqm
# ═══════════════════════════════════════════════════════════════════════════════

STANDARD_SHEET = (2500, 1250)  # L x W in mm

# Cold rolled (up to 3mm) - per sqm
SHEET_COLD = {
    "N4 + PVC": 34.08,
    "LASER PVC": 28.78,
    "PLAIN PVC": 27.36,
    "N4 ONLY": 9.84,
    "SATIN": 18.91,
    "3CR12/409": 38.23,
    "ALUMINIUM": 19.50,
}

# Hot rolled (above 3mm) - per sqm
# 4.5mm and 6mm same price
SHEET_HOT = {
    "4.5": {"N4 ONLY": 325.40, "N4 + PVC": 371.56},
    "6": {"N4 ONLY": 325.40, "N4 + PVC": 371.56},
    "8": {"N4 ONLY": 325.40, "N4 + PVC": 378.54},
    "10": {"N4 ONLY": 325.40, "N4 + PVC": 385.50},
}


def calc_sheet_piece(length_mm, width_mm, thickness_mm, finish="N4 + PVC"):
    """
    Calculate sheet/plate piece price
    - Standard sheet: 2500 x 1250mm (3.125 sqm)
    - Full sheet or larger: base price
    - Piece >= 1 sqm: +40%
    - Piece < 1 sqm: +60%
    """
    # Calculate sqm
    sqm = (length_mm / 1000) * (width_mm / 1000)
    
    # Determine if it's a full sheet or a piece
    std_sqm = (STANDARD_SHEET[0] / 1000) * (STANDARD_SHEET[1] / 1000)  # 3.125
    
    # Check if piece fits within standard sheet (needs cutting)
    fits_standard = (length_mm <= STANDARD_SHEET[0] and width_mm <= STANDARD_SHEET[1]) or \
                    (length_mm <= STANDARD_SHEET[1] and width_mm <= STANDARD_SHEET[0])
    
    # Determine markup
    if sqm >= std_sqm * 0.95:  # Within 5% of full sheet = no markup
        markup = 0
        markup_text = "Full sheet"
    elif sqm >= 1.0:
        markup = 0.40
        markup_text = "+40% (piece ≥ 1m²)"
    else:
        markup = 0.60
        markup_text = "+60% (piece < 1m²)"
    
    # Get base price based on thickness
    thickness = float(thickness_mm)
    finish_upper = finish.upper().strip()
    
    if thickness > 3:
        # Hot rolled
        t_key = str(thickness).replace(".0", "")
        if t_key in SHEET_HOT:
            prices = SHEET_HOT[t_key]
            base_price = prices.get(finish_upper, prices.get("N4 ONLY", 325.40))
        else:
            base_price = 325.40  # Default hot rolled
    else:
        # Cold rolled
        base_price = SHEET_COLD.get(finish_upper, 34.08)
    
    # Calculate final price
    final_price_sqm = base_price * (1 + markup)
    subtotal = sqm * final_price_sqm
    total = max(subtotal, MIN_CHARGE_PIECE)
    
    return {
        "length_mm": length_mm,
        "width_mm": width_mm,
        "sqm": round(sqm, 3),
        "thickness": thickness_mm,
        "finish": finish,
        "base_price_sqm": round(base_price, 2),
        "markup": markup,
        "markup_text": markup_text,
        "final_price_sqm": round(final_price_sqm, 2),
        "subtotal": round(subtotal, 2),
        "total": round(total, 2),
        "min_applied": subtotal < MIN_CHARGE_PIECE,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# FISCHER POLISHING - Per Meter (2025)
# ═══════════════════════════════════════════════════════════════════════════════

POLISH_ROUND = {
    12.7: 3.05, 15.9: 3.05, 19.1: 3.14, 20: 3.14, 22.2: 3.42, 25: 3.77,
    28: 4.04, 37.1: 4.51, 34.9: 4.84, 35: 4.84, 38.1: 5.14, 40: 5.42,
    41.2: 5.50, 42.7: 5.70, 44.5: 5.70, 45: 5.98, 47.6: 6.36, 48.3: 6.36,
    48.6: 6.36, 50.8: 6.62, 52: 6.72, 53: 6.81, 54: 6.99, 55: 7.08,
    57: 7.36, 58: 7.45, 60: 7.56, 60.3: 7.72, 63.5: 8.11, 65: 8.29,
    70: 8.83, 76.2: 9.80,
}

POLISH_SQUARE = {
    "20x20": 7.33, "25x25": 7.88, "30x30": 8.42, "40x40": 9.91,
    "50x30": 9.66, "50x50": 11.30,
}

# ═══════════════════════════════════════════════════════════════════════════════
# ROUND TUBE BRUSHING - Per Meter (NDE Stainless 2024)
# ═══════════════════════════════════════════════════════════════════════════════

ROUND_180 = {
    12.7: 4.30, 15.9: 4.31, 19.1: 4.23, 20: 4.23, 22.2: 4.63, 25: 5.11,
    28: 6.11, 31.7: 6.11, 32: 6.50, 34.9: 6.50, 35: 7.01, 38.1: 7.01,
    40: 7.34, 41.2: 7.50, 42.7: 7.74, 44.5: 7.74, 45: 8.11, 47.6: 8.11,
    48.3: 8.11, 48.6: 8.60, 50.8: 8.99, 52: 9.13, 53: 9.57, 54: 9.50,
    55: 9.62, 57: 10.00, 58: 10.12, 60: 10.25, 60.3: 10.50,
    63.5: 11.02, 65: 11.25, 70: 12.00, 76.2: 12.88, 80: 13.25, 89.9: 13.75,
}

ROUND_400 = {
    12.7: 5.48, 15.9: 5.48, 19.1: 5.63, 20: 5.63, 22.2: 6.11, 25: 6.74,
    28: 7.38, 31.7: 7.38, 32: 8.11, 34.9: 8.11, 35: 7.89, 38.1: 8.14,
    40: 9.73, 41.2: 10.00, 42.7: 10.37, 44.5: 10.37, 45: 10.85, 47.6: 11.50,
    48.3: 11.50, 48.6: 11.50, 50.8: 12.00, 52: 12.25, 53: 12.38, 54: 12.74,
    55: 12.88, 57: 13.40, 58: 13.50, 60: 13.62, 60.3: 14.00,
    63.5: 14.65, 65: 15.00, 70: 16.00, 76.2: 17.18, 80: 17.64, 89.9: 18.42,
}

ROUND_MIRROR = {
    12.7: 8.25, 15.9: 8.25, 19.1: 8.51, 20: 8.51, 22.2: 8.75, 25: 10.25,
    28: 11.02, 31.7: 11.02, 32: 12.25, 34.9: 12.25, 35: 13.03, 38.1: 14.00,
    40: 14.34, 41.2: 15.00, 42.7: 15.51, 44.5: 15.51, 45: 16.25, 47.6: 17.25,
    48.3: 17.25, 48.6: 17.25, 50.8: 18.02, 52: 18.27, 53: 18.51, 54: 19.00,
    55: 19.28, 57: 20.00, 58: 20.29, 60: 20.52, 60.3: 21.06,
    63.5: 22.02, 65: 22.55, 70: 24.02, 76.2: 25.82, 80: 26.55, 89.9: 27.55,
}

# NDE Large Round (101mm+) - 180#, 400#, Mirror
LARGE_ROUND = {
    101: (20.15, 26.84, 40.34),
    104: (21.06, 28.08, 42.07),
    114: (22.55, 30.06, 45.10),
    127: (24.02, 32.04, 48.11),
    129: (24.57, 32.92, 49.10),
    154: (27.40, 36.60, 54.86),
}

JARO_PIPE = {125: 87.38, 129: 88.16, 205: 380.50}

# ═══════════════════════════════════════════════════════════════════════════════
# SQUARE TUBE BRUSHING - Per Meter (NDE) - 180#, 400#, 180-400#
# ═══════════════════════════════════════════════════════════════════════════════

SQUARE = {
    "20x20": (10.42, 17.76, 13.12),
    "25x25": (11.39, 19.28, 14.27),
    "30x30": (12.25, 20.77, 15.40),
    "40x40": (14.00, 23.64, 17.54),
    "50x50": (16.14, 27.19, 20.14),
    "60x60": (20.14, 33.94, 25.19),
    "70x70": (24.81, 41.98, 31.06),
    "80x40": (20.14, 33.94, 25.19),
    "80x80": (29.31, 51.15, 36.59),
    "58x58": (71.48, 0, 0),
}

# ═══════════════════════════════════════════════════════════════════════════════
# FLAT BAR - Per Meter - One Side, Both Sides, All Round
# ═══════════════════════════════════════════════════════════════════════════════

FLAT_CR = {
    20: (5.49, 11.13, 13.25),
    25: (6.00, 11.89, 14.37),
    30: (6.49, 12.88, 15.40),
    35: (6.86, 13.75, 16.00),
    40: (7.51, 14.65, 17.66),
    45: (7.87, 15.77, 18.89),
    50: (8.38, 16.91, 20.29),
    55: (9.00, 18.02, 21.68),
    60: (9.62, 19.02, 22.90),
    65: (10.12, 21.06, 25.19),
    70: (10.62, 21.30, 25.54),
    75: (11.25, 22.40, 26.82),
    80: (11.75, 23.54, 28.19),
}

FLAT_HR = {
    20: (11.13, 22.02, 26.43),
    25: (11.89, 23.90, 28.68),
    30: (12.88, 25.70, 30.82),
    35: (13.75, 27.55, 33.08),
    40: (14.65, 29.31, 35.18),
    45: (15.77, 31.58, 37.70),
    50: (16.91, 33.69, 40.48),
    55: (18.02, 35.95, 43.10),
    60: (19.01, 38.09, 43.10),
    65: (21.06, 40.34, 45.74),
    70: (21.30, 42.47, 47.86),
    75: (22.40, 44.60, 47.28),
    80: (23.54, 46.88, 56.26),
}

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULE PIPE - Per Meter (180#) - SCH10, SCH40
# ═══════════════════════════════════════════════════════════════════════════════

PIPE = {
    "1/4": (6.00, 6.62),
    "3/8": (9.00, 10.00),
    "1/2": (11.88, 13.03),
    "3/4": (14.00, 15.13),
    "1": (15.77, 17.39),
    "1 1/4": (19.76, 21.53),
    "1 1/2": (22.94, 25.70),
    "2": (26.92, 29.42),
    "2 1/2": (31.06, 34.07),
    "3": (35.18, 38.85),
    "3 1/2": (55.13, 60.67),
    "4": (69.91, 77.70),
    "5": (84.46, 153.93),
    "6": (222.95, 315.90),
    "8": (406.07, 0),
}

# ═══════════════════════════════════════════════════════════════════════════════
# ANGLE IRON - Per Meter - Both Sides, Inside/Outside
# ═══════════════════════════════════════════════════════════════════════════════

ANGLE_HR = {
    "20x20": (42.99, 21.24), "25x25": (45.90, 23.06), "30x30": (49.74, 24.77),
    "35x35": (53.14, 26.59), "40x40": (56.54, 28.27), "45x45": (60.88, 30.45),
    "50x50": (65.31, 32.49), "55x55": (69.57, 34.68), "60x60": (73.42, 36.74),
    "65x65": (81.27, 38.91), "70x70": (82.22, 40.96), "75x75": (86.46, 43.03),
    "80x80": (90.92, 45.22), "85x85": (96.61, 48.30), "90x90": (102.27, 51.12),
    "95x95": (107.96, 53.97), "100x100": (113.65, 56.81),
}

ANGLE_CR = {
    "20x20": (27.58, 13.97), "25x25": (30.19, 14.90), "30x30": (32.64, 16.14),
    "35x35": (34.52, 17.25), "40x40": (37.73, 18.37), "45x45": (39.54, 19.77),
    "50x50": (42.07, 21.23), "55x55": (45.17, 22.61), "60x60": (48.29, 23.84),
    "65x65": (50.82, 26.41), "70x70": (53.35, 26.69), "75x75": (56.48, 28.10),
    "80x80": (59.09, 29.54), "85x85": (62.77, 31.38), "90x90": (66.48, 33.23),
    "95x95": (70.18, 35.06), "100x100": (73.86, 36.92),
}


# ═══════════════════════════════════════════════════════════════════════════════
# COIL CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

def calc_coil(weight_kg=None, od_mm=None, id_mm=508, width_mm=0, thickness_mm=0, grade="304"):
    """
    Calculate coil from weight OR from OD
    - weight_kg + id_mm + width_mm + thickness_mm → get length, sqm, OD
    - od_mm + id_mm + width_mm + thickness_mm → get weight, length, sqm
    """
    if not width_mm or not thickness_mm:
        return {"error": "Need width and thickness"}
    
    density = WEIGHT_FACTORS.get(grade, 8.07)
    width_m = width_mm / 1000
    thickness_m = thickness_mm / 1000
    id_m = id_mm / 1000
    
    if weight_kg and weight_kg > 0:
        # From weight → get length, sqm, OD
        length_m = weight_kg / (width_m * thickness_m * density * 1000)
        sqm = length_m * width_m
        od_squared = (id_m ** 2) + (4 * length_m * thickness_m / math.pi)
        od_mm_calc = math.sqrt(od_squared) * 1000
        weight_kg_calc = weight_kg
    elif od_mm and od_mm > 0:
        # From OD → get weight, length, sqm
        od_m = od_mm / 1000
        length_m = math.pi * (od_m**2 - id_m**2) / (4 * thickness_m)
        sqm = length_m * width_m
        weight_kg_calc = length_m * width_m * thickness_m * density * 1000
        od_mm_calc = od_mm
    else:
        return {"error": "Need weight OR OD"}
    
    # Extra calculations
    kg_per_sqm = thickness_m * density * 1000
    sqm_per_ton = 1000 / kg_per_sqm if kg_per_sqm else 0
    sqm_per_kg = 1 / kg_per_sqm if kg_per_sqm else 0
    
    return {
        "weight_kg": round(weight_kg_calc, 2),
        "length_m": round(length_m, 2),
        "sqm": round(sqm, 2),
        "id_mm": round(id_mm, 1),
        "od_mm": round(od_mm_calc, 1),
        "width_mm": width_mm,
        "thickness_mm": thickness_mm,
        "grade": grade,
        "density": density,
        "kg_per_sqm": round(kg_per_sqm, 3),
        "sqm_per_ton": round(sqm_per_ton, 2),
        "sqm_per_kg": round(sqm_per_kg, 4),
    }


def calc_finish(sqm, finish="N4 + PVC", thickness_mm=0, is_coil=False):
    """
    Get finishing price
    - Coils up to 2mm: use FINISH_COLD (same as sheet prices)
    - Sheet ≤3mm: FINISH_COLD
    - Sheet >3mm: FINISH_HOT
    """
    key = finish.upper().strip()
    
    if thickness_mm > 3:
        # Hot rolled - thick sheets
        price = FINISH_HOT.get(key) or 325.40
    else:
        # Cold rolled - coils up to 2mm and sheets up to 3mm use same prices
        price = FINISH_COLD.get(key) or 34.08
    
    subtotal = sqm * price
    min_charge = MIN_CHARGE_JOB if is_coil else MIN_CHARGE_PIECE
    total = max(subtotal, min_charge)
    
    return {
        "sqm": round(sqm, 2),
        "finish": finish,
        "price_sqm": round(price, 2),
        "subtotal": round(subtotal, 2),
        "total": round(total, 2),
        "min_applied": subtotal < min_charge,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PRICE LOOKUPS
# ═══════════════════════════════════════════════════════════════════════════════

def _closest(size, prices):
    """Find closest size within 1mm tolerance"""
    if size in prices:
        return size
    for s in prices:
        if isinstance(s, (int, float)) and abs(s - size) <= 1:
            return s
    return None


def get_round(size_mm, finish="180"):
    """Round tube price per meter"""
    size = float(size_mm)
    f = str(finish).replace("#", "").lower()
    
    # Large tubes 101mm+
    if size >= 101:
        key = _closest(size, LARGE_ROUND)
        if key:
            prices = LARGE_ROUND[key]
            if "400" in f:
                return prices[1]
            elif "mirror" in f:
                return prices[2]
            return prices[0]
        # Jaro
        key = _closest(size, JARO_PIPE)
        if key:
            return JARO_PIPE[key]
        return 0
    
    # Standard tubes
    key = _closest(size, ROUND_180)
    if not key:
        return 0
    
    if "400" in f:
        return ROUND_400.get(key, 0)
    elif "mirror" in f:
        return ROUND_MIRROR.get(key, 0)
    elif "polish" in f:
        pk = _closest(size, POLISH_ROUND)
        return POLISH_ROUND.get(pk, 0) if pk else 0
    return ROUND_180.get(key, 0)


def get_square(size, finish="180"):
    """Square tube price per meter"""
    # Handle various input formats
    if isinstance(size, (int, float)):
        key = f"{int(size)}x{int(size)}"
    elif "x" in str(size).lower():
        key = str(size).replace(" ", "").lower()
    else:
        # Try to parse as number
        try:
            s = int(float(size))
            key = f"{s}x{s}"
        except:
            return 0
    
    if key not in SQUARE:
        return 0
    
    prices = SQUARE[key]
    f = str(finish).replace("#", "").lower()
    
    if "400" in f and "180" in f:
        return prices[2]
    elif "400" in f:
        return prices[1]
    elif "polish" in f:
        return POLISH_SQUARE.get(key, 0)
    return prices[0]


def get_flat(width_mm, rolled="cold", sides="one", finish="180"):
    """Flat bar price per meter"""
    # Handle string or float input
    try:
        width = int(float(width_mm))
    except:
        return 0
    
    table = FLAT_CR if rolled.lower() == "cold" else FLAT_HR
    
    if width not in table:
        return 0
    
    prices = table[width]
    s = sides.lower()
    
    if s == "all":
        price = prices[2]
    elif s == "both":
        price = prices[1]
    else:
        price = prices[0]
    
    # 400# = +30%
    if "400" in str(finish):
        price *= 1.30
    
    return round(price, 2)


def get_angle(size, rolled="hot", finish="both"):
    """Angle iron price per meter"""
    # Handle various input formats
    if isinstance(size, (int, float)):
        key = f"{int(size)}x{int(size)}"
    elif "x" in str(size).lower():
        key = str(size).replace(" ", "").lower()
    else:
        # Try to parse as number
        try:
            s = int(float(size))
            key = f"{s}x{s}"
        except:
            return 0
    
    table = ANGLE_HR if rolled.lower() == "hot" else ANGLE_CR
    
    if key not in table:
        return 0
    
    prices = table[key]
    
    if "inside" in finish.lower() or "io" in finish.lower() or "out" in finish.lower():
        return prices[1]
    return prices[0]


def get_pipe(size, schedule="SCH10"):
    """Schedule pipe price per meter"""
    if size not in PIPE:
        return 0
    
    prices = PIPE[size]
    
    if "40" in str(schedule).upper():
        return prices[1]
    return prices[0]


# ═══════════════════════════════════════════════════════════════════════════════
# SIZE LISTS FOR DROPDOWNS
# ═══════════════════════════════════════════════════════════════════════════════

def get_sizes(product):
    """Get available sizes for dropdowns"""
    if product == "round":
        return sorted(set(list(ROUND_180.keys()) + list(LARGE_ROUND.keys()) + list(JARO_PIPE.keys())))
    elif product == "square":
        return list(SQUARE.keys())
    elif product == "flat":
        return sorted(FLAT_CR.keys())
    elif product == "angle":
        return list(ANGLE_HR.keys())
    elif product == "pipe":
        return list(PIPE.keys())
    return []
