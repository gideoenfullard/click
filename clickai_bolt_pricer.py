"""
ClickAI Bolt Pricer v3 — Self-calibrating from actual DB prices
════════════════════════════════════════════════════════════════
1. Identifies fasteners by description (type, material, M-size, length)
2. Calculates weight from ISO tables
3. For items WITH cost → calculates their implied R/kg (learns from data)
4. For items WITHOUT cost → applies learned R/kg from similar items
5. Falls back to conservative defaults only when no data exists

Usage:
    from clickai_bolt_pricer import BoltPricer
    result = BoltPricer.price("CAP SCREW M12X50 S/S")
    # For bulk: first calibrate, then price
    BoltPricer.calibrate(stock_items_with_costs)
    result = BoltPricer.price("SET M10X30 HT")  # uses learned rates
"""

import re
import math
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class BoltPricer:

    # ══════════════════════════════════════════════════════
    # ISO 4017 HEX BOLT weights (grams)
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

    NUT_WEIGHTS = {
        3:0.5,4:1.0,5:1.7,6:2.7,7:4.2,8:5.8,10:10.5,12:18.5,
        14:28.0,16:41.0,18:56.0,20:76.0,22:100.0,24:130.0,
        27:180.0,30:240.0,33:300.0,36:380.0,
    }

    WASHER_WEIGHTS = {
        3:0.3,4:0.4,5:0.8,6:1.3,7:2.0,8:3.0,10:5.2,12:9.0,
        14:14.0,16:19.0,18:28.0,20:39.0,22:48.0,24:64.0,
        27:87.0,30:113.0,33:140.0,36:175.0,
    }

    WEIGHT_FACTOR = {
        "hex_bolt": 1.00, "cap_screw": 0.85, "csk_cap": 0.80,
        "button_head": 0.82, "cheese_head": 0.75, "stud": 0.75,
        "grub_screw": 0.50, "coach_bolt": 1.05, "roofing_bolt": 1.02,
        "coach_screw": 0.90, "self_tapper": 0.60, "tek_screw": 0.55,
    }

    # ══════════════════════════════════════════════════════
    # FALLBACK R/kg — only used when NO calibration data
    # Conservative (low) to avoid overpricing
    # ══════════════════════════════════════════════════════
    FALLBACK_RKG = {
        "HT": {"set": 10, "mf_set": 18, "hex_bolt": 14, "cap_screw": 25,
                "csk_cap": 22, "button_head": 25, "cheese_head": 14,
                "cup_square": 16, "stud": 35, "grub_screw": 30,
                "coach_bolt": 15, "roofing_bolt": 15, "coach_screw": 16,
                "nut": 16, "nyloc_nut": 22, "dome_nut": 28, "wing_nut": 24,
                "washer": 12, "spring_washer": 18, "fender_washer": 14,
                "self_tapper": 20, "tek_screw": 18},
        "SS": {"set": 25, "mf_set": 35, "hex_bolt": 35, "cap_screw": 42,
               "csk_cap": 50, "button_head": 42, "cheese_head": 35,
               "cup_square": 38, "stud": 50, "grub_screw": 50,
               "nut": 38, "nyloc_nut": 48, "dome_nut": 55, "wing_nut": 50,
               "washer": 30, "spring_washer": 40, "fender_washer": 35},
        "ZP": {"set": 14, "mf_set": 20, "hex_bolt": 14, "cap_screw": 26,
               "csk_cap": 24, "button_head": 26, "cup_square": 16,
               "stud": 38, "nut": 16, "nyloc_nut": 24, "washer": 13,
               "fender_washer": 15},
        "BLK": {"set": 10, "hex_bolt": 14, "cap_screw": 24, "csk_cap": 24,
                "cup_square": 16, "stud": 35, "nut": 14, "washer": 12},
        "HDG": {"set": 15, "hex_bolt": 20, "cap_screw": 30, "cup_square": 20,
                "nut": 20, "washer": 16},
        "10.9": {"set": 18, "mf_set": 22, "hex_bolt": 20, "cap_screw": 32,
                 "csk_cap": 32, "stud": 42, "nut": 22},
        "8.8": {"set": 15, "hex_bolt": 16, "cap_screw": 28, "nut": 18},
        "12.9": {"set": 24, "hex_bolt": 25, "cap_screw": 38, "csk_cap": 38},
        "BRASS": {"hex_bolt": 55, "cap_screw": 65, "nut": 60, "washer": 50},
    }

    # Learned rates from calibration: {(type, material, size_band): [r/kg values]}
    _learned_rkg = {}
    # Median per group after calibration
    _calibrated_rkg = {}
    _is_calibrated = False

    # ══════════════════════════════════════════════════════
    # IDENTIFICATION PATTERNS
    # ══════════════════════════════════════════════════════
    TYPE_PATTERNS = [
        (r'MF\s*SET', "mf_set", "set"),
        (r'\bSET\b', "set", "set"),
        (r'CSK\s*(CAP\s*)?SCREW|COUNTERSUNK\s*CAP|CSK\s*H[DE]', "csk_cap", "bolt"),
        (r'SOCKET\s*CAP|CAP\s*SCREW|SHCS\b|ALLEN\s*(KEY\s*)?BOLT', "cap_screw", "bolt"),
        (r'BUTTON\s*H(EA)?D|BHCS\b', "button_head", "bolt"),
        (r'CHEESE\s*H(EA)?D|PAN\s*H(EA)?D', "cheese_head", "bolt"),
        (r'ENG(INEERING)?\s*STUD|\bSTUD\b', "stud", "bolt"),
        (r'GRUB\s*SCREW|SET\s*SCREW.*HEADLESS', "grub_screw", "bolt"),
        (r'CUP\s*SQ(UARE)?|CARRIAGE\s*BOLT', "cup_square", "bolt_nut"),
        (r'COACH\s*BOLT', "coach_bolt", "bolt"),
        (r'COACH\s*SCREW|LAG\s*(BOLT|SCREW)', "coach_screw", "bolt"),
        (r'ROOFING\s*BOLT', "roofing_bolt", "bolt"),
        (r'SELF[\s-]*TAP', "self_tapper", "bolt"),
        (r'TEK\s*SCREW|SELF[\s-]*DRILL', "tek_screw", "bolt"),
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
    ]

    _RE_MF1 = re.compile(r'M(\d+)\s*[xX]\s*(\d+\.\d+)\s*[xX]\s*(\d+)')
    _RE_MF2 = re.compile(r'M(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+\.\d+)')
    _RE_STD = re.compile(r'M(\d+)\s*[xX]\s*(\d+)(?!\s*[xX]\s*\d)')

    # ══════════════════════════════════════════════════════
    # SIZE BANDS for grouping
    # ══════════════════════════════════════════════════════
    @staticmethod
    def _size_band(m):
        if m is None: return "unknown"
        if m <= 6: return "small"      # M3-M6
        if m <= 12: return "medium"    # M7-M12
        if m <= 20: return "large"     # M13-M20
        return "xl"                     # M21+

    # ══════════════════════════════════════════════════════
    # CALIBRATION — learn from existing prices
    # ══════════════════════════════════════════════════════
    @classmethod
    def calibrate(cls, stock_items):
        """
        Learn R/kg rates from items that have cost prices.
        Groups by (item_type, material, size_band) and finds median R/kg.
        
        After calibration, price() uses learned rates for all items.
        Items without matches fall back to FALLBACK_RKG.
        """
        cls._learned_rkg = defaultdict(list)
        count = 0

        for item in stock_items:
            desc = item.get("description") or item.get("code") or ""
            cost = float(item.get("cost_price") or item.get("cost") or 0)
            if cost <= 0:
                continue

            info = cls.identify(desc)
            if not info.get("is_fastener"):
                continue

            it = info["item_type"]
            mat = info["material"]
            m = info.get("m_size")
            l = info.get("length")
            wm = info.get("weight_mode")

            wt = cls.get_weight(it, m, l, wm)
            if not wt or wt < 0.5:
                continue

            implied_rkg = cost / (wt / 1000)

            # Sanity check: R/kg should be R5-R500
            if implied_rkg < 5 or implied_rkg > 500:
                continue

            band = cls._size_band(m)

            # Store at multiple levels for fallback
            cls._learned_rkg[(it, mat, band)].append(implied_rkg)
            cls._learned_rkg[(it, mat, "ALL")].append(implied_rkg)
            cls._learned_rkg[(it, "ALL", band)].append(implied_rkg)
            cls._learned_rkg[(it, "ALL", "ALL")].append(implied_rkg)
            count += 1

        # Calculate 25th percentile (Q1) — more representative of actual buying prices
        # Median gets skewed by supplier list prices; Q1 matches bulk buying rates
        cls._calibrated_rkg = {}
        for key, values in cls._learned_rkg.items():
            if len(values) >= 1:
                sorted_vals = sorted(values)
                # Use 25th percentile for groups with enough data
                if len(sorted_vals) >= 4:
                    q1_idx = len(sorted_vals) // 4
                    rate = sorted_vals[q1_idx]
                elif len(sorted_vals) >= 2:
                    # Small groups: use lower of the two middle values
                    rate = sorted_vals[0] if len(sorted_vals) == 2 else sorted_vals[len(sorted_vals)//3]
                else:
                    rate = sorted_vals[0]
                cls._calibrated_rkg[key] = round(rate, 1)

        cls._is_calibrated = True
        logger.info(f"[BOLT PRICER] Calibrated from {count} items → {len(cls._calibrated_rkg)} rate groups")
        return {"items_used": count, "groups": len(cls._calibrated_rkg)}

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
        if m_size is None:
            return None

        if weight_mode == "nut":
            base = cls.NUT_WEIGHTS.get(m_size)
            if base is None: return None
            mult = {"nyloc_nut": 1.3, "dome_nut": 1.4, "wing_nut": 1.8}.get(item_type, 1.0)
            return base * mult

        if weight_mode == "washer":
            base = cls.WASHER_WEIGHTS.get(m_size)
            if base is None: return None
            mult = {"spring_washer": 0.8, "fender_washer": 2.5}.get(item_type, 1.0)
            return base * mult

        if length is None:
            return None

        hex_w = cls._interpolate_hex(m_size, length)
        if hex_w is None:
            return None

        if weight_mode == "set":
            return hex_w + cls.NUT_WEIGHTS.get(m_size, 0) + 2 * cls.WASHER_WEIGHTS.get(m_size, 0)

        if weight_mode == "bolt_nut":
            factor = cls.WEIGHT_FACTOR.get(item_type, 1.0)
            return (hex_w * factor) + cls.NUT_WEIGHTS.get(m_size, 0)

        return hex_w * cls.WEIGHT_FACTOR.get(item_type, 1.0)

    @classmethod
    def get_rkg(cls, item_type, material, m_size=10):
        """
        Get R/kg with cascade:
        1. Calibrated: exact (type, material, size_band)
        2. Calibrated: (type, material, ALL sizes)
        3. Calibrated: (type, ALL materials, size_band)
        4. Calibrated: (type, ALL, ALL)
        5. Fallback table
        6. Default R30/kg
        """
        band = cls._size_band(m_size)

        if cls._is_calibrated:
            # Try increasingly broad matches
            for key in [
                (item_type, material, band),       # exact match
                (item_type, material, "ALL"),       # any size this type+mat
                (item_type, "ALL", band),           # any material this type+size
                (item_type, "ALL", "ALL"),           # any this type
            ]:
                if key in cls._calibrated_rkg:
                    return cls._calibrated_rkg[key]

        # Fallback to hardcoded
        mat_rates = cls.FALLBACK_RKG.get(material, cls.FALLBACK_RKG.get("HT", {}))
        rate = mat_rates.get(item_type)
        if rate:
            return rate

        # Ultimate fallback
        defaults = {"HT": 12, "SS": 35, "ZP": 15, "BLK": 12,
                    "HDG": 18, "10.9": 20, "8.8": 16, "12.9": 26, "BRASS": 55}
        return defaults.get(material, 12)

    @classmethod
    def price(cls, description):
        info = cls.identify(description)
        if not info.get("is_fastener"):
            return {"success": False, "error": "Not a fastener", "description": description}

        it, mat = info["item_type"], info["material"]
        m, l, wm = info.get("m_size"), info.get("length"), info.get("weight_mode")

        if m is None:
            return {"success": False, "error": "No M-size", "description": description}

        wt = cls.get_weight(it, m, l, wm)
        if wt is None:
            sz = f"M{m}" + (f"x{l}" if l else "")
            return {"success": False, "error": f"No weight for {sz}", "description": description}

        rkg = cls.get_rkg(it, mat, m)
        cost = round((wt / 1000) * rkg, 2)

        band = cls._size_band(m)
        source = "calibrated" if cls._is_calibrated and (it, mat, band) in cls._calibrated_rkg else \
                 "calibrated-broad" if cls._is_calibrated and (it, mat, "ALL") in cls._calibrated_rkg else \
                 "fallback"

        return {"success": True, "cost": cost, "weight_g": round(wt, 1),
                "rkg": rkg, "item_type": it, "type_label": cls._type_label(it),
                "material": mat, "mat_label": cls._mat_label(mat),
                "m_size": m, "length": l, "description": description,
                "source": source, "size_band": band}

    @classmethod
    def zane_price_check(cls, description):
        r = cls.price(description)
        if not r.get("success"):
            return f"Cannot price '{description}': {r.get('error')}"
        sz = f"M{r['m_size']}" + (f" x {r['length']}mm" if r.get('length') else "")
        src = r.get('source', 'fallback')
        return (f"{description}\n"
                f"  Type:     {r['type_label']}\n"
                f"  Material: {r['mat_label']}\n"
                f"  Size:     {sz}\n"
                f"  Weight:   {r['weight_g']}g\n"
                f"  R/kg:     R{r['rkg']}/kg ({src})\n"
                f"  COST:     R{r['cost']:.2f}")

    @classmethod
    def bulk_recalc(cls, stock_items, custom_rkg=None, markup=1.0):
        """
        Smart bulk recalc:
        1. First calibrate from items WITH costs
        2. Then price ALL items (including those without costs)
        """
        # Step 1: Calibrate from existing data
        cal = cls.calibrate(stock_items)

        updated, skipped, no_change = [], [], []
        t_old = t_new = 0.0

        for item in stock_items:
            desc = item.get("description") or item.get("code") or ""
            iid = item.get("id", "")
            code = item.get("code", "")
            old_cost = float(item.get("cost_price") or item.get("cost") or 0)
            old_sell = float(item.get("selling_price") or item.get("price") or 0)

            r = cls.price(desc)
            if not r.get("success"):
                skipped.append({"id": iid, "code": code, "description": desc,
                                "reason": r.get("error","?"), "old_cost": old_cost})
                continue

            nc = r["cost"]
            diff = round(nc - old_cost, 2)
            pct = round((diff / old_cost * 100), 1) if old_cost > 0 else (999 if nc > 0 else 0)
            t_old += old_cost; t_new += nc

            entry = {"id": iid, "code": code, "description": desc,
                "item_type": r["item_type"], "type_label": r["type_label"],
                "material": r["material"], "mat_label": r["mat_label"],
                "m_size": r["m_size"], "length": r.get("length"),
                "weight_g": r["weight_g"], "rkg": r["rkg"],
                "old_cost": old_cost, "new_cost": nc, "old_sell": old_sell,
                "difference": diff, "pct_change": pct,
                "has_cost": old_cost > 0, "source": r.get("source", "?")}

            if abs(pct) < 2 and old_cost > 0:
                no_change.append(entry)
            else:
                updated.append(entry)

        return {"updated": updated, "skipped": skipped, "no_change": no_change,
                "calibration": cal,
                "learned_rates": {f"{k[0]}|{k[1]}|{k[2]}": v 
                                  for k, v in cls._calibrated_rkg.items()
                                  if k[1] != "ALL" and k[2] != "ALL"},
                "stats": {"total": len(stock_items),
                    "updated_count": len(updated), "skipped_count": len(skipped),
                    "no_change_count": len(no_change),
                    "total_old_cost": round(t_old, 2), "total_new_cost": round(t_new, 2),
                    "difference": round(t_new - t_old, 2)}}

    @classmethod
    def get_all_tiers(cls):
        """Return calibrated rates for display."""
        if cls._is_calibrated:
            result = {}
            for (it, mat, band), rkg in sorted(cls._calibrated_rkg.items()):
                if mat == "ALL" or band == "ALL":
                    continue
                key = f"{mat}"
                if key not in result:
                    result[key] = {}
                if it not in result[key]:
                    result[key][it] = {}
                result[key][it][band] = rkg
            return result
        return cls.FALLBACK_RKG

    @classmethod
    def update_tier(cls, material, item_type, rkg, size_band="ALL"):
        """Manual override for a rate."""
        key = (item_type, material, size_band)
        cls._calibrated_rkg[key] = float(rkg)
        cls._is_calibrated = True
        return True

    # ══════════════════════════════════════════════════════
    # PRIVATE
    # ══════════════════════════════════════════════════════

    @classmethod
    def _extract_size(cls, text):
        m = cls._RE_MF1.search(text)
        if m:
            ms = int(m.group(1))
            p = float(m.group(2))
            third = int(m.group(3))
            return (ms, third) if p < 5 else (ms, int(p))

        m = cls._RE_MF2.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))

        m = cls._RE_STD.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))

        m = re.search(r'M(\d+)', text)
        if m:
            return int(m.group(1)), None

        return None, None

    @classmethod
    def _interpolate_hex(cls, m_size, length):
        sizes = cls.HEX_BOLT_WEIGHTS.get(m_size)
        scale = 1.0

        if sizes is None:
            nearby = [m for m in cls.HEX_BOLT_WEIGHTS if abs(m - m_size) <= 2]
            if not nearby: return None
            closest = min(nearby, key=lambda x: abs(x - m_size))
            sizes = cls.HEX_BOLT_WEIGHTS[closest]
            scale = (m_size / closest) ** 2

        if length in sizes:
            return sizes[length] * scale

        sl = sorted(sizes.keys())

        if length < sl[0]:
            return sizes[sl[0]] * (length / sl[0]) * scale
        if length > sl[-1]:
            w_per_mm = math.pi / 4 * (m_size ** 2) * 7.85 / 1000
            return (sizes[sl[-1]] + (length - sl[-1]) * w_per_mm) * scale

        for i in range(len(sl) - 1):
            if sl[i] < length < sl[i+1]:
                f = (length - sl[i]) / (sl[i+1] - sl[i])
                return (sizes[sl[i]] + (sizes[sl[i+1]] - sizes[sl[i]]) * f) * scale
        return None

    @staticmethod
    def _type_label(t):
        return {"hex_bolt":"Hex Bolt","cap_screw":"Cap Screw (Allen)",
            "csk_cap":"CSK Cap Screw","button_head":"Button Head",
            "cheese_head":"Cheese Head","stud":"Engineering Stud",
            "grub_screw":"Grub/Set Screw","set":"Set (B+N+2W)",
            "mf_set":"MF Set (Fine+N+2W)","cup_square":"Cup Square+Nut",
            "coach_bolt":"Coach Bolt","coach_screw":"Coach/Lag Screw",
            "roofing_bolt":"Roofing Bolt","self_tapper":"Self-Tapper",
            "tek_screw":"Tek/Self-Drill","nut":"Hex Nut",
            "nyloc_nut":"Nyloc Nut","dome_nut":"Dome Nut",
            "wing_nut":"Wing Nut","washer":"Flat Washer",
            "spring_washer":"Spring Washer","fender_washer":"Fender Washer",
        }.get(t, t)

    @staticmethod
    def _mat_label(m):
        return {"HT":"High Tensile","SS":"Stainless Steel",
            "ZP":"Zinc Plated","BLK":"Black/Plain",
            "HDG":"Hot Dip Galv","10.9":"Grade 10.9",
            "8.8":"Grade 8.8","12.9":"Grade 12.9","BRASS":"Brass",
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
        band = data.get("size_band", "ALL")
        if mat and it and rkg > 0:
            BoltPricer.update_tier(mat, it, rkg, band)
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Need material, item_type, rkg"})

    logger.info("[BOLT PRICER] Routes registered")
