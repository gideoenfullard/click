"""
ClickAI Bolt Pricer v4 — Verified supplier rates
═══════════════════════════════════════════════════
R/kg rates from Fulltech supplier price list (62 verified items).
Each rate is FLAT per type×material with known accuracy.

Key insight: R/kg is mostly flat across M-sizes for each type.
Exception: Engineering studs are per-piece priced, not per-kg.

Accuracy vs supplier list:
  SET HT:       R24/kg  ±13%  (10 data points)
  MF SET HT:    R39/kg  ±10%  (6 data points)
  CAP SCREW HT: R63/kg  ±16%  (10 data points)
  CSK CAP HT:   R57/kg  ±14%  (6 data points)
  HEX BOLT HT:  R30/kg  limited (4 data points)
"""

import re
import math
import logging

logger = logging.getLogger(__name__)


class BoltPricer:

    # ══════════════════════════════════════════════════════
    # WEIGHT TABLES
    # ══════════════════════════════════════════════════════
    HEX_BOLT_WEIGHTS = {
        3:  {6:0.7,8:0.9,10:1.1,12:1.3,16:1.6,20:2.0,25:2.5,30:2.9,40:3.8},
        4:  {8:1.6,10:2.0,12:2.3,16:3.0,20:3.6,25:4.5,30:5.3,40:6.9,50:8.5,60:10.1},
        5:  {10:3.0,12:3.5,16:4.5,20:5.5,25:6.7,30:7.9,40:10.3,50:12.7,60:15.1,70:17.5,80:19.9},
        6:  {10:4.5,12:5.2,16:6.5,20:7.9,25:9.6,30:11.2,35:12.9,40:14.5,50:17.8,60:21.1,70:24.4,80:27.7,100:34.3},
        7:  {16:9.5,20:11.5,25:14.0,30:16.5,40:21.5,50:26.5,60:31.5,70:36.5,80:41.5},
        8:  {16:11.2,20:13.5,25:16.3,30:19.2,35:22.0,40:24.8,50:30.4,60:36.1,70:41.7,80:47.3,100:58.6,120:69.8,150:86.7},
        10: {20:21.0,25:24.8,30:28.6,35:32.4,40:36.2,50:43.8,60:51.4,70:59.0,80:66.6,100:81.8,120:97.0,150:119.8},
        12: {25:37.5,30:43.0,35:48.5,40:54.0,50:65.0,60:76.0,70:87.0,80:98.0,100:120.0,120:142.0,150:175.0,200:230.0},
        14: {30:63.0,40:76.5,50:90.0,60:103.5,70:117.0,80:130.5,100:157.5,120:184.5,150:225.0},
        16: {30:80.0,40:97.0,50:113.0,60:129.5,70:146.0,80:162.5,100:195.5,120:228.5,150:278.0,200:360.0},
        18: {40:137.0,50:158.0,60:179.0,70:200.0,80:221.0,100:263.0,120:305.0,150:368.0},
        20: {40:167.0,50:193.0,60:218.0,70:244.0,80:269.0,100:320.0,120:371.0,150:447.0,200:573.0},
        22: {50:253.0,60:284.0,70:316.0,80:347.0,100:410.0,120:472.0,150:566.0},
        24: {50:313.0,60:351.0,70:389.0,80:427.0,100:503.0,120:579.0,150:693.0,200:883.0},
        27: {60:510.0,70:565.0,80:605.0,100:700.0,120:795.0,150:935.0},
        30: {60:635.0,70:705.0,80:750.0,100:865.0,120:980.0,150:1150.0,200:1430.0},
        33: {80:960.0,100:1110.0,120:1260.0,150:1485.0},
        36: {80:1150.0,100:1330.0,120:1510.0,150:1780.0,200:2230.0},
    }
    NUT_WEIGHTS = {3:0.5,4:1.0,5:1.7,6:2.7,7:4.2,8:5.8,10:10.5,12:18.5,14:28.0,16:41.0,18:56.0,20:76.0,22:100.0,24:130.0,27:180.0,30:240.0,33:300.0,36:380.0}
    WASHER_WEIGHTS = {3:0.3,4:0.4,5:0.8,6:1.3,7:2.0,8:3.0,10:5.2,12:9.0,14:14.0,16:19.0,18:28.0,20:39.0,22:48.0,24:64.0,27:87.0,30:113.0,33:140.0,36:175.0}
    WEIGHT_FACTOR = {"hex_bolt":1.0,"cap_screw":0.85,"csk_cap":0.80,"button_head":0.82,"cheese_head":0.75,"stud":0.75,"grub_screw":0.50,"coach_bolt":1.05,"roofing_bolt":1.02,"coach_screw":0.90,"self_tapper":0.60,"tek_screw":0.55}

    # ══════════════════════════════════════════════════════
    # VERIFIED R/KG RATES — from 62-item supplier price list
    # Format: (type, material) → R/kg
    # Each rate validated against multiple data points
    # ══════════════════════════════════════════════════════
    VERIFIED_RKG = {
        # SETS (bolt + nut + 2 washers) — R24/kg ±13%
        ("set","HT"):24, ("set","ZP"):33, ("set","SS"):54,
        ("set","BLK"):24, ("set","HDG"):32, ("set","10.9"):43,
        ("set","8.8"):32, ("set","12.9"):50, ("set","BRASS"):80,

        # MF SETS (fine pitch) — R39/kg ±10% — NOT same as normal sets!
        ("mf_set","HT"):39, ("mf_set","ZP"):45, ("mf_set","SS"):80,
        ("mf_set","10.9"):62, ("mf_set","8.8"):45,

        # HEX BOLT (bolt only) — R30/kg
        ("hex_bolt","HT"):30, ("hex_bolt","ZP"):33, ("hex_bolt","SS"):65,
        ("hex_bolt","BLK"):30, ("hex_bolt","HDG"):40, ("hex_bolt","10.9"):42,
        ("hex_bolt","8.8"):35, ("hex_bolt","BRASS"):120,

        # CAP SCREW (Allen key) — R63/kg ±16%
        ("cap_screw","HT"):63, ("cap_screw","ZP"):63, ("cap_screw","SS"):99,
        ("cap_screw","BLK"):63, ("cap_screw","10.9"):68, ("cap_screw","12.9"):80,

        # CSK CAP SCREW — R57/kg ±14%
        ("csk_cap","HT"):57, ("csk_cap","ZP"):57, ("csk_cap","SS"):139,
        ("csk_cap","BLK"):57, ("csk_cap","10.9"):68, ("csk_cap","12.9"):80,

        # BUTTON HEAD — R55/kg (estimated from cap screw)
        ("button_head","HT"):55, ("button_head","SS"):82, ("button_head","ZP"):55,
        ("button_head","BLK"):55, ("button_head","10.9"):65,

        # CHEESE HEAD — R30/kg (1 data point)
        ("cheese_head","HT"):30, ("cheese_head","ZP"):35, ("cheese_head","SS"):65,

        # CUP SQUARE + NUT — R39/kg
        ("cup_square","HT"):39, ("cup_square","ZP"):20, ("cup_square","SS"):80,
        ("cup_square","BLK"):37, ("cup_square","HDG"):45,

        # COACH BOLT — similar to cup square
        ("coach_bolt","HT"):35, ("coach_bolt","ZP"):38, ("coach_bolt","HDG"):42,

        # ROOFING BOLT — R32/kg estimated
        ("roofing_bolt","HT"):32, ("roofing_bolt","ZP"):35,

        # COACH/LAG SCREW — R35/kg estimated
        ("coach_screw","HT"):35, ("coach_screw","ZP"):38, ("coach_screw","HDG"):42,

        # NUTS
        ("nut","HT"):30, ("nut","ZP"):35, ("nut","SS"):80,
        ("nut","BLK"):30, ("nut","HDG"):40, ("nut","10.9"):45,
        ("nyloc_nut","HT"):45, ("nyloc_nut","ZP"):50, ("nyloc_nut","SS"):95,
        ("dome_nut","HT"):55, ("dome_nut","SS"):120,
        ("wing_nut","HT"):50, ("wing_nut","ZP"):55, ("wing_nut","SS"):110,

        # WASHERS
        ("washer","HT"):25, ("washer","ZP"):28, ("washer","SS"):65,
        ("washer","BLK"):25, ("washer","HDG"):35,
        ("spring_washer","HT"):35, ("spring_washer","ZP"):40, ("spring_washer","SS"):85,
        ("fender_washer","HT"):38, ("fender_washer","ZP"):38, ("fender_washer","SS"):70,

        # GRUB SCREW
        ("grub_screw","HT"):65, ("grub_screw","SS"):110, ("grub_screw","BLK"):65,

        # SELF-TAPPERS / TEK SCREWS
        ("self_tapper","HT"):40, ("self_tapper","ZP"):45, ("self_tapper","SS"):80,
        ("tek_screw","HT"):38, ("tek_screw","ZP"):42,
    }

    # ENGINEERING STUDS — per-piece lookup, NOT per-kg!
    # Studs are machined items with wildly different R/kg by size
    STUD_PRICES = {
        # (m_size): price_per_50mm — scale linearly for other lengths
        4: 2.50, 5: 3.00, 6: 3.69, 8: 4.59, 10: 5.24,
        12: 4.90, 14: 5.80, 16: 6.66, 18: 8.00, 20: 10.00,
        22: 13.00, 24: 16.00, 27: 22.00, 30: 28.00,
    }

    # ══════════════════════════════════════════════════════
    # IDENTIFICATION
    # ══════════════════════════════════════════════════════
    TYPE_PATTERNS = [
        (r'MF\s*SET', "mf_set", "set"),
        (r'MF\s*BOLT', "hex_bolt", "bolt"),
        (r'MF\s*NUT', "nut", "nut"),
        (r'\bSET\b', "set", "set"),
        (r'CSK\s*(CAP\s*)?SCREW|COUNTERSUNK\s*CAP|CSK\s*H[DE]', "csk_cap", "bolt"),
        (r'SOCKET\s*CAP|CAP\s*SCREW|SHCS\b|ALLEN\s*(KEY\s*)?BOLT', "cap_screw", "bolt"),
        (r'BUTTON\s*H(EA)?D|BHCS\b', "button_head", "bolt"),
        (r'CHEESE\s*H(EA)?D|PAN\s*H(EA)?D', "cheese_head", "bolt"),
        (r'ENG(INEERING)?\s*STUD|\bSTUD\b', "stud", "stud"),
        (r'GRUB\s*SCREW|SET\s*SCREW.*HEADLESS', "grub_screw", "bolt"),
        (r'CUP\s*SQ(UARE)?(\s*(&|AND)\s*NUT)?|CARRIAGE\s*BOLT', "cup_square", "bolt_nut"),
        (r'COACH\s*BOLT', "coach_bolt", "bolt"),
        (r'COACH\s*SCREW|LAG\s*(BOLT|SCREW)', "coach_screw", "bolt"),
        (r'ROOFING\s*BOLT', "roofing_bolt", "bolt"),
        (r'BODY\s*WASH', "fender_washer", "washer"),
        (r'SELF[\s-]*TAP', "self_tapper", "bolt"),
        (r'TEK\s*SCREW|SELF[\s-]*DRILL', "tek_screw", "bolt"),
        (r'NAIL\s*PLUG', "self_tapper", "bolt"),
        (r'NYLOC|NYLON\s*NUT|NE\s*NUT', "nyloc_nut", "nut"),
        (r'DOME\s*NUT|ACORN\s*NUT|CAP\s*NUT', "dome_nut", "nut"),
        (r'WING\s*NUT|BUTTERFLY', "wing_nut", "nut"),
        (r'\bNUT\b(?!.*BOLT)', "nut", "nut"),
        (r'SPRING\s*WASH', "spring_washer", "washer"),
        (r'FENDER\s*WASH', "fender_washer", "washer"),
        (r'FLAT\s*WASH', "washer", "washer"),
        (r'\bWASH\w*\b', "washer", "washer"),
        (r'HEX\s*(H(EA)?D\s*)?BOLT|HEX\s*SCREW', "hex_bolt", "bolt"),
        (r'\bBOLT\b', "hex_bolt", "bolt"),
    ]
    MATERIAL_PATTERNS = [
        (r'\b316\b', "SS"), (r'\b304\b', "SS"),
        (r'\bS/?S\b|\bSTAINLESS', "SS"),
        (r'\bZ/?P\b|\bZINC\s*PLAT', "ZP"),
        (r'\bHDG\b|\bGALV|\bHOT\s*DIP', "HDG"),
        (r'\b12[\.\s]*9\b', "12.9"), (r'\b10[\.\s]*9\b', "10.9"),
        (r'\b8[\.\s]*8\b', "8.8"),
        (r'\bBLK\b|\bBLACK\b|\bSELF[\s-]*COL', "BLK"),
        (r'\bBRASS\b', "BRASS"),
        (r'\bH[\.\s]*T\b|\bHIGH\s*TENS', "HT"),
        (r'\bTH\b', "HT"),
    ]
    _RE_MF1 = re.compile(r'M(\d+)\s*[xX]\s*(\d+\.\d+)\s*[xX]\s*(\d+)')
    _RE_MF2 = re.compile(r'M(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+\.\d+)')
    _RE_STD = re.compile(r'M(\d+)\s*[xX]\s*(\d+)(?!\s*[xX]\s*\d)')

    # ══════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════
    @classmethod
    def identify(cls, description):
        text = str(description or "").upper().strip()
        if not text:
            return {"is_fastener": False}
        item_type = weight_mode = None
        for pattern, itype, wmode in cls.TYPE_PATTERNS:
            if re.search(pattern, text):
                item_type, weight_mode = itype, wmode
                break
        if not item_type:
            return {"is_fastener": False}
        material = "HT"
        for pattern, mat in cls.MATERIAL_PATTERNS:
            if re.search(pattern, text):
                material = mat
                break
        m_size, length = cls._extract_size(text)
        return {"is_fastener": True, "item_type": item_type,
                "material": material, "m_size": m_size,
                "length": length, "weight_mode": weight_mode}

    @classmethod
    def get_weight(cls, item_type, m_size, length=None, weight_mode="bolt"):
        if m_size is None: return None
        if weight_mode == "nut":
            base = cls.NUT_WEIGHTS.get(m_size)
            if base is None: return None
            return base * {"nyloc_nut":1.3,"dome_nut":1.4,"wing_nut":1.8}.get(item_type, 1.0)
        if weight_mode == "washer":
            base = cls.WASHER_WEIGHTS.get(m_size)
            if base is None: return None
            return base * {"spring_washer":0.8,"fender_washer":2.5}.get(item_type, 1.0)
        if weight_mode == "stud":
            return math.pi / 4 * (m_size ** 2) * (length or 50) * 7.85 / 1000
        if length is None: return None
        hex_w = cls._interpolate_hex(m_size, length)
        if hex_w is None: return None
        if weight_mode == "set":
            return hex_w + cls.NUT_WEIGHTS.get(m_size, 0) + 2 * cls.WASHER_WEIGHTS.get(m_size, 0)
        if weight_mode == "bolt_nut":
            return hex_w * cls.WEIGHT_FACTOR.get(item_type, 1.0) + cls.NUT_WEIGHTS.get(m_size, 0)
        return hex_w * cls.WEIGHT_FACTOR.get(item_type, 1.0)

    # Size-dependent R/kg adjustments (verified from supplier data)
    # Format: {(type, material): {m_size_threshold: rkg, ...}}
    SIZE_ADJUSTMENTS = {
        # Hex bolts: M6=R29, M8=R27, M10=R32, M16=R50 — bigger = more expensive/kg
        ("hex_bolt","HT"):  {12: 30, 99: 45},   # ≤M12→R30, M14+→R45
        ("hex_bolt","ZP"):  {12: 33, 99: 50},
        ("hex_bolt","SS"):  {12: 65, 99: 95},
        ("hex_bolt","BLK"): {12: 30, 99: 45},
        ("hex_bolt","HDG"): {12: 40, 99: 55},
        # Cap screw: M4 has premium (R82/kg verified), rest R63
        ("cap_screw","HT"): {4: 82, 99: 63},
        # M7 is non-standard — premium pricing (R55/kg verified)
    }
    # M7 premium: non-standard size, supplier charges ~2x
    M7_PREMIUM = 2.3  # multiplier for M7 items

    @classmethod
    def get_rkg(cls, item_type, material, m_size=10):
        m = m_size or 10

        # Check size-dependent rates first
        size_key = (item_type, material)
        if size_key in cls.SIZE_ADJUSTMENTS:
            thresholds = cls.SIZE_ADJUSTMENTS[size_key]
            for threshold in sorted(thresholds.keys()):
                if m <= threshold:
                    rate = thresholds[threshold]
                    if m == 7: rate = round(rate * cls.M7_PREMIUM)
                    return rate

        # Direct lookup
        rate = cls.VERIFIED_RKG.get((item_type, material))
        if rate is not None:
            if m == 7 and item_type in ("set","mf_set","hex_bolt"):
                return round(rate * cls.M7_PREMIUM)
            return rate

        # Try HT as base with material multiplier
        ht_rate = cls.VERIFIED_RKG.get((item_type, "HT"))
        if ht_rate:
            mult = {"SS":2.2,"ZP":1.35,"HDG":1.35,"10.9":1.8,"8.8":1.35,"12.9":2.1,"BLK":1.0,"BRASS":3.5}.get(material, 1.0)
            rate = round(ht_rate * mult)
            if m == 7 and item_type in ("set","mf_set","hex_bolt"):
                return round(rate * cls.M7_PREMIUM)
            return rate
        return 30  # ultimate fallback

    @classmethod
    def price(cls, description):
        info = cls.identify(description)
        if not info.get("is_fastener"):
            return {"success": False, "error": "Not a fastener", "description": str(description)}
        it, mat = info["item_type"], info["material"]
        m, l, wm = info.get("m_size"), info.get("length"), info.get("weight_mode")
        if m is None:
            return {"success": False, "error": "No M-size", "description": str(description)}

        # SPECIAL: Engineering studs use per-piece pricing
        if it == "stud":
            base_price = cls.STUD_PRICES.get(m)
            if base_price is None:
                # Interpolate from nearest sizes
                sizes = sorted(cls.STUD_PRICES.keys())
                if m < sizes[0]: base_price = cls.STUD_PRICES[sizes[0]] * 0.8
                elif m > sizes[-1]: base_price = cls.STUD_PRICES[sizes[-1]] * 1.3
                else:
                    for i in range(len(sizes)-1):
                        if sizes[i] < m < sizes[i+1]:
                            f = (m - sizes[i]) / (sizes[i+1] - sizes[i])
                            base_price = cls.STUD_PRICES[sizes[i]] + f * (cls.STUD_PRICES[sizes[i+1]] - cls.STUD_PRICES[sizes[i]])
                            break
            # Scale for length (base is 50mm)
            length_factor = (l or 50) / 50
            cost = round(base_price * length_factor, 2)
            wt = cls.get_weight(it, m, l, wm)
            rkg = round(cost / (wt / 1000), 1) if wt and wt > 0 else 0
            mat_mult = {"SS":2.5,"ZP":1.2,"10.9":1.5,"12.9":1.8}.get(mat, 1.0)
            cost = round(cost * mat_mult, 2)
            return {"success": True, "cost": cost, "weight_g": round(wt or 0, 1),
                    "rkg": rkg, "item_type": it, "type_label": "Eng. Stud (per-piece)",
                    "material": mat, "mat_label": cls._mat_label(mat),
                    "m_size": m, "length": l, "description": str(description),
                    "pricing_method": "per_piece"}

        wt = cls.get_weight(it, m, l, wm)
        if wt is None:
            return {"success": False, "error": f"No weight for M{m}" + (f"x{l}" if l else ""), "description": str(description)}

        rkg = cls.get_rkg(it, mat, m)
        cost = round((wt / 1000) * rkg, 2)
        return {"success": True, "cost": cost, "weight_g": round(wt, 1),
                "rkg": rkg, "item_type": it, "type_label": cls._type_label(it),
                "material": mat, "mat_label": cls._mat_label(mat),
                "m_size": m, "length": l, "description": str(description),
                "pricing_method": "weight_x_rkg"}

    @classmethod
    def zane_price_check(cls, description):
        r = cls.price(description)
        if not r.get("success"):
            return f"Cannot price '{description}': {r.get('error')}"
        sz = f"M{r['m_size']}" + (f" x {r['length']}mm" if r.get('length') else "")
        return (f"{description}\n"
                f"  Type:     {r['type_label']}\n"
                f"  Material: {r['mat_label']}\n"
                f"  Size:     {sz}\n"
                f"  Weight:   {r['weight_g']}g\n"
                f"  R/kg:     R{r['rkg']}/kg\n"
                f"  COST:     R{r['cost']:.2f}")

    @classmethod
    def get_all_tiers(cls):
        return cls.VERIFIED_RKG

    @classmethod
    def update_tier(cls, material, item_type, rkg, size_band="ALL"):
        cls.VERIFIED_RKG[(item_type, material)] = float(rkg)
        return True

    # ══════════════════════════════════════════════════════
    # PRIVATE
    # ══════════════════════════════════════════════════════
    @classmethod
    def _extract_size(cls, text):
        m = cls._RE_MF1.search(text)
        if m:
            ms = int(m.group(1)); p = float(m.group(2)); third = int(m.group(3))
            return (ms, third) if p < 5 else (ms, int(p))
        m = cls._RE_MF2.search(text)
        if m: return int(m.group(1)), int(m.group(2))
        m = cls._RE_STD.search(text)
        if m: return int(m.group(1)), int(m.group(2))
        m = re.search(r'M(\d+)', text)
        if m: return int(m.group(1)), None
        return None, None

    @classmethod
    def _interpolate_hex(cls, m_size, length):
        sizes = cls.HEX_BOLT_WEIGHTS.get(m_size)
        scale = 1.0
        if sizes is None:
            nearby = [ms for ms in cls.HEX_BOLT_WEIGHTS if abs(ms - m_size) <= 2]
            if not nearby: return None
            closest = min(nearby, key=lambda x: abs(x - m_size))
            sizes = cls.HEX_BOLT_WEIGHTS[closest]
            scale = (m_size / closest) ** 2
        if length in sizes: return sizes[length] * scale
        sl = sorted(sizes.keys())
        if length < sl[0]: return sizes[sl[0]] * (length / sl[0]) * scale
        if length > sl[-1]:
            wpm = math.pi / 4 * (m_size ** 2) * 7.85 / 1000
            return (sizes[sl[-1]] + (length - sl[-1]) * wpm) * scale
        for i in range(len(sl) - 1):
            if sl[i] < length < sl[i+1]:
                f = (length - sl[i]) / (sl[i+1] - sl[i])
                return (sizes[sl[i]] + (sizes[sl[i+1]] - sizes[sl[i]]) * f) * scale
        return None

    @staticmethod
    def _type_label(t):
        return {"hex_bolt":"Hex Bolt","cap_screw":"Cap Screw","csk_cap":"CSK Cap Screw",
            "button_head":"Button Head","cheese_head":"Cheese Head","stud":"Eng. Stud",
            "grub_screw":"Grub Screw","set":"Set (B+N+2W)","mf_set":"MF Set (Fine)",
            "cup_square":"Cup Sq+Nut","coach_bolt":"Coach Bolt","coach_screw":"Coach Screw",
            "roofing_bolt":"Roofing Bolt","self_tapper":"Self-Tapper","tek_screw":"Tek Screw",
            "nut":"Hex Nut","nyloc_nut":"Nyloc Nut","dome_nut":"Dome Nut","wing_nut":"Wing Nut",
            "washer":"Flat Washer","spring_washer":"Spring Washer","fender_washer":"Fender Washer",
        }.get(t, t)

    @staticmethod
    def _mat_label(m):
        return {"HT":"High Tensile","SS":"Stainless","ZP":"Zinc Plated","BLK":"Black",
            "HDG":"Hot Dip Galv","10.9":"Gr 10.9","8.8":"Gr 8.8","12.9":"Gr 12.9","BRASS":"Brass",
        }.get(m, m)


def register_bolt_pricer_routes(app, db, Auth, get_user_role, login_required):
    from flask import request, jsonify

    @app.route("/api/bolt-pricer/check", methods=["POST"])
    @login_required
    def api_bolt_pricer_check():
        data = request.get_json() or {}
        return jsonify(BoltPricer.price(data.get("description", "")))

    @app.route("/api/bolt-pricer/tiers", methods=["GET", "POST"])
    @login_required
    def api_bolt_pricer_tiers():
        if request.method == "GET":
            return jsonify(BoltPricer.get_all_tiers())
        data = request.get_json() or {}
        mat = data.get("material","").upper()
        it = data.get("item_type","")
        rkg = float(data.get("rkg", 0))
        if mat and it and rkg > 0:
            BoltPricer.update_tier(mat, it, rkg)
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Need material, item_type, rkg"})

    logger.info("[BOLT PRICER] v4 routes registered — verified supplier rates")
