"""
ClickAI Bolt Pricer — Weight-based COST pricing for fasteners
═══════════════════════════════════════════════════════════════
Identifies item type + material from description, looks up
ISO/DIN correct weight, applies R/kg tier per type+material,
returns cost price (inkoop prys).

R/kg tiers derived from Fulltech actual cost prices (2024/2025).
Weights from ISO 4017 (hex bolts), ISO 4032 (nuts), ISO 7089 (washers).

Usage:
    from clickai_bolt_pricer import BoltPricer

    result = BoltPricer.price("CAP SCREW M12X50 S/S")
    # -> {'cost': 5.85, 'weight_g': 65.0, 'rkg': 90, ...}

    BoltPricer.zane_price_check("SET M16X50 HT")
    # -> formatted string for Zane

    results = BoltPricer.bulk_recalc(stock_items)
"""

import re
import math
import logging

logger = logging.getLogger(__name__)


class BoltPricer:
    """Weight-based fastener cost pricing with type-specific R/kg tiers."""

    # ══════════════════════════════════════════════════════════════
    # ISO 4017 / DIN 933 — HEX BOLT weights in GRAMS
    # Full-thread hex bolts. All other types derive from these.
    # ══════════════════════════════════════════════════════════════
    HEX_BOLT_WEIGHTS = {
        3:  {6:0.7, 8:0.9, 10:1.1, 12:1.3, 16:1.6, 20:2.0, 25:2.5, 30:2.9, 40:3.8},
        4:  {8:1.6, 10:2.0, 12:2.3, 16:3.0, 20:3.6, 25:4.5, 30:5.3, 40:6.9, 50:8.5, 60:10.1},
        5:  {10:3.0, 12:3.5, 16:4.5, 20:5.5, 25:6.7, 30:7.9, 40:10.3, 50:12.7, 60:15.1, 70:17.5, 80:19.9},
        6:  {10:4.5, 12:5.2, 16:6.5, 20:7.9, 25:9.6, 30:11.2, 35:12.9, 40:14.5, 50:17.8, 60:21.1, 70:24.4, 80:27.7, 100:34.3},
        7:  {16:9.5, 20:11.5, 25:14.0, 30:16.5, 40:21.5, 50:26.5, 60:31.5, 70:36.5, 80:41.5},
        8:  {16:11.2, 20:13.5, 25:16.3, 30:19.2, 35:22.0, 40:24.8, 50:30.4, 60:36.1, 70:41.7, 80:47.3, 100:58.6, 120:69.8, 150:86.7},
        10: {20:21.0, 25:24.8, 30:28.6, 35:32.4, 40:36.2, 50:43.8, 60:51.4, 70:59.0, 80:66.6, 100:81.8, 120:97.0, 150:119.8},
        12: {25:37.5, 30:43.0, 35:48.5, 40:54.0, 50:65.0, 60:76.0, 70:87.0, 80:98.0, 100:120.0, 120:142.0, 150:175.0, 200:230.0},
        14: {30:63.0, 40:76.5, 50:90.0, 60:103.5, 70:117.0, 80:130.5, 100:157.5, 120:184.5, 150:225.0},
        16: {30:80.0, 40:97.0, 50:113.0, 60:129.5, 70:146.0, 80:162.5, 100:195.5, 120:228.5, 150:278.0, 200:360.0},
        18: {40:137.0, 50:158.0, 60:179.0, 70:200.0, 80:221.0, 100:263.0, 120:305.0, 150:368.0},
        20: {40:167.0, 50:193.0, 60:218.0, 70:244.0, 80:269.0, 100:320.0, 120:371.0, 150:447.0, 200:573.0},
        22: {50:253.0, 60:284.0, 70:316.0, 80:347.0, 100:410.0, 120:472.0, 150:566.0},
        24: {50:313.0, 60:351.0, 70:389.0, 80:427.0, 100:503.0, 120:579.0, 150:693.0, 200:883.0},
        27: {60:510.0, 70:565.0, 80:605.0, 100:700.0, 120:795.0, 150:935.0},
        30: {60:635.0, 70:705.0, 80:750.0, 100:865.0, 120:980.0, 150:1150.0, 200:1430.0},
        33: {80:960.0, 100:1110.0, 120:1260.0, 150:1485.0},
        36: {80:1150.0, 100:1330.0, 120:1510.0, 150:1780.0, 200:2230.0},
    }

    # ISO 4032 — HEX NUT weights (grams)
    NUT_WEIGHTS = {
        3:0.5, 4:1.0, 5:1.7, 6:2.7, 7:4.2, 8:5.8, 10:10.5, 12:18.5,
        14:28.0, 16:41.0, 18:56.0, 20:76.0, 22:100.0, 24:130.0,
        27:180.0, 30:240.0, 33:300.0, 36:380.0,
    }

    # ISO 7089 — FLAT WASHER weights (grams)
    WASHER_WEIGHTS = {
        3:0.3, 4:0.4, 5:0.8, 6:1.3, 7:2.0, 8:3.0, 10:5.2, 12:9.0,
        14:14.0, 16:19.0, 18:28.0, 20:39.0, 22:48.0, 24:64.0,
        27:87.0, 30:113.0, 33:140.0, 36:175.0,
    }

    # ══════════════════════════════════════════════════════════════
    # WEIGHT FACTORS — ratio vs standard hex bolt
    # ══════════════════════════════════════════════════════════════
    WEIGHT_FACTOR = {
        "hex_bolt": 1.00, "cap_screw": 0.85, "csk_cap": 0.80,
        "button_head": 0.82, "cheese_head": 0.75, "stud": 0.75,
        "grub_screw": 0.50, "coach_bolt": 1.05, "roofing_bolt": 1.02,
        "coach_screw": 0.90, "self_tapper": 0.60, "tek_screw": 0.55,
    }

    # ══════════════════════════════════════════════════════════════
    # R/kg COST TIERS — per type x material
    # Derived from Fulltech actual cost prices (2024/2025)
    #
    # Data source (ISO weights used):
    #   hex_bolt HT:   R30/kg  (median R30, range R27-49, 4 items)
    #   cap_screw HT:  R52/kg  (median R52, range R45-69, 10 items)
    #   csk_cap HT:    R50/kg  (median R48, range R37-52, 6 items)
    #   set HT:        R25/kg  (median R24, range R21-31, 10 items)
    #   mf_set HT:     R40/kg  (median R40, range R33-43, 6 items)
    #   cup_square HT: R38/kg  (2 items)
    #   stud HT:       R80/kg  (inconsistent data - verify!)
    #   set ZP:        R35/kg  (median R34, 5 items)
    #   set SS:        R55/kg  (median R55, 2 items)
    #   cap_screw SS:  R90/kg  (2 items)
    #   csk_cap SS:    R110/kg (2 items)
    #   set 10.9:      R39/kg  (1 item)
    #   cup_sq BLK:    R36/kg  (1 item)
    # ══════════════════════════════════════════════════════════════

    COST_RKG = {
        "HT": {
            "hex_bolt": 30, "cap_screw": 52, "csk_cap": 50,
            "button_head": 50, "cheese_head": 30, "set": 25,
            "mf_set": 40, "cup_square": 38, "stud": 80,
            "grub_screw": 65, "coach_bolt": 32, "roofing_bolt": 32,
            "coach_screw": 35, "nut": 30, "nyloc_nut": 45,
            "dome_nut": 55, "wing_nut": 50, "washer": 25,
            "spring_washer": 35, "fender_washer": 30,
        },
        "SS": {
            "hex_bolt": 75, "cap_screw": 90, "csk_cap": 110,
            "button_head": 85, "cheese_head": 75, "set": 55,
            "mf_set": 70, "cup_square": 80, "stud": 100,
            "grub_screw": 110, "nut": 80, "nyloc_nut": 100,
            "dome_nut": 120, "wing_nut": 110, "washer": 65,
            "spring_washer": 85, "fender_washer": 75,
        },
        "ZP": {
            "hex_bolt": 33, "cap_screw": 58, "csk_cap": 55,
            "button_head": 55, "set": 35, "mf_set": 42,
            "cup_square": 40, "stud": 85, "nut": 33,
            "nyloc_nut": 48, "washer": 28, "fender_washer": 33,
        },
        "BLK": {
            "hex_bolt": 30, "cap_screw": 52, "csk_cap": 50,
            "set": 25, "cup_square": 36, "stud": 80,
            "nut": 30, "washer": 25,
        },
        "HDG": {
            "hex_bolt": 40, "cap_screw": 65, "set": 38,
            "cup_square": 42, "nut": 40, "washer": 35,
        },
        "10.9": {
            "hex_bolt": 42, "cap_screw": 68, "csk_cap": 68,
            "set": 39, "mf_set": 48, "stud": 90, "nut": 45,
        },
        "8.8": {
            "hex_bolt": 35, "cap_screw": 58, "set": 32, "nut": 38,
        },
        "12.9": {
            "hex_bolt": 52, "cap_screw": 80, "csk_cap": 80, "set": 50,
        },
        "BRASS": {
            "hex_bolt": 120, "cap_screw": 140, "nut": 130, "washer": 110,
        },
    }

    COST_RKG_DEFAULTS = {
        "HT": 35, "SS": 80, "ZP": 36, "BLK": 35, "HDG": 40,
        "10.9": 45, "8.8": 38, "12.9": 55, "BRASS": 130,
    }

    # ══════════════════════════════════════════════════════════════
    # IDENTIFICATION PATTERNS — first match wins
    # ══════════════════════════════════════════════════════════════
    TYPE_PATTERNS = [
        # Sets first
        (r'MF\s*SET', "mf_set", "set"),
        (r'\bSET\b', "set", "set"),
        # Specific bolt types
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
        # Nuts
        (r'NYLOC|NYLON\s*NUT|NE\s*NUT', "nyloc_nut", "nut"),
        (r'DOME\s*NUT|ACORN\s*NUT|CAP\s*NUT', "dome_nut", "nut"),
        (r'WING\s*NUT|BUTTERFLY', "wing_nut", "nut"),
        (r'\bNUT\b(?!.*BOLT)', "nut", "nut"),
        # Washers
        (r'SPRING\s*WASH', "spring_washer", "washer"),
        (r'FENDER\s*WASH', "fender_washer", "washer"),
        (r'FLAT\s*WASH', "washer", "washer"),
        (r'\bWASH\w*\b', "washer", "washer"),
        # Generic bolts last
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

    # Size regexes
    _RE_MF1 = re.compile(r'M(\d+)\s*[xX]\s*(\d+\.\d+)\s*[xX]\s*(\d+)')
    _RE_MF2 = re.compile(r'M(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+\.\d+)')
    _RE_STD = re.compile(r'M(\d+)\s*[xX]\s*(\d+)(?!\s*[xX]\s*\d)')

    # ══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════

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
    def get_rkg(cls, item_type, material):
        return cls.COST_RKG.get(material, {}).get(
            item_type, cls.COST_RKG_DEFAULTS.get(material, 35))

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

        rkg = cls.get_rkg(it, mat)
        cost = round((wt / 1000) * rkg, 2)

        return {"success": True, "cost": cost, "weight_g": round(wt, 1),
                "rkg": rkg, "item_type": it, "type_label": cls._type_label(it),
                "material": mat, "mat_label": cls._mat_label(mat),
                "m_size": m, "length": l, "description": description}

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
    def bulk_recalc(cls, stock_items, custom_rkg=None):
        if custom_rkg:
            for mat, tiers in custom_rkg.items():
                cls.COST_RKG.setdefault(mat, {}).update(tiers)

        updated, skipped = [], []
        t_old = t_new = 0.0

        for item in stock_items:
            desc = item.get("description") or item.get("code") or ""
            iid = item.get("id", "")
            old = float(item.get("cost_price") or item.get("cost") or 0)

            r = cls.price(desc)
            if not r.get("success"):
                skipped.append({"id": iid, "description": desc,
                                "reason": r.get("error","?"), "old_cost": old})
                continue

            nc = r["cost"]
            diff = round(nc - old, 2)
            pct = round((diff / old * 100), 1) if old > 0 else 0.0
            t_old += old; t_new += nc

            updated.append({"id": iid, "description": desc,
                "item_type": r["item_type"], "type_label": r["type_label"],
                "material": r["material"], "m_size": r["m_size"],
                "length": r.get("length"), "weight_g": r["weight_g"],
                "rkg": r["rkg"], "old_cost": old, "new_cost": nc,
                "difference": diff, "pct_change": pct})

        return {"updated": updated, "skipped": skipped,
                "stats": {"total": len(stock_items),
                    "updated_count": len(updated), "skipped_count": len(skipped),
                    "total_old_cost": round(t_old, 2), "total_new_cost": round(t_new, 2),
                    "difference": round(t_new - t_old, 2)}}

    @classmethod
    def get_all_tiers(cls):
        return {"tiers": cls.COST_RKG, "defaults": cls.COST_RKG_DEFAULTS}

    @classmethod
    def update_tier(cls, material, item_type, new_rkg):
        cls.COST_RKG.setdefault(material.upper(), {})[item_type] = new_rkg
        return True

    # ══════════════════════════════════════════════════════════════
    # PRIVATE
    # ══════════════════════════════════════════════════════════════

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

        # Nut/washer might just have M-size: "NUT M12"
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
        return {"hex_bolt":"Hex Bolt", "cap_screw":"Socket Cap Screw (Allen)",
            "csk_cap":"Countersunk Cap Screw", "button_head":"Button Head",
            "cheese_head":"Cheese Head", "stud":"Engineering Stud",
            "grub_screw":"Grub/Set Screw", "set":"Set (Bolt+Nut+2Wash)",
            "mf_set":"MF Set (Fine+Nut+2Wash)", "cup_square":"Cup Square+Nut",
            "coach_bolt":"Coach Bolt", "coach_screw":"Coach/Lag Screw",
            "roofing_bolt":"Roofing Bolt", "self_tapper":"Self-Tapper",
            "tek_screw":"Tek/Self-Drill", "nut":"Hex Nut",
            "nyloc_nut":"Nyloc Nut", "dome_nut":"Dome Nut",
            "wing_nut":"Wing Nut", "washer":"Flat Washer",
            "spring_washer":"Spring Washer", "fender_washer":"Fender Washer",
        }.get(t, t)

    @staticmethod
    def _mat_label(m):
        return {"HT":"High Tensile", "SS":"Stainless Steel 304",
            "ZP":"Zinc Plated", "BLK":"Black/Plain",
            "HDG":"Hot Dip Galvanised", "10.9":"Grade 10.9",
            "8.8":"Grade 8.8", "12.9":"Grade 12.9", "BRASS":"Brass",
        }.get(m, m)


def register_bolt_pricer_routes(app, db, Auth, get_user_role, login_required):
    from flask import request, jsonify

    @app.route("/api/bolt-pricer/check", methods=["POST"])
    @login_required
    def api_bolt_pricer_check():
        data = request.get_json() or {}
        return jsonify(BoltPricer.price(data.get("description", "")))

    @app.route("/api/bolt-pricer/bulk", methods=["POST"])
    @login_required
    def api_bolt_pricer_bulk():
        if get_user_role() not in ("owner", "admin"):
            return jsonify({"success": False, "error": "Owner/Admin only"})
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False, "error": "No business"})

        data = request.get_json() or {}
        stock = db.get_all_stock(biz_id)
        results = BoltPricer.bulk_recalc(stock, data.get("custom_rkg"))

        if data.get("apply") and results["updated"]:
            cnt = 0
            for it in results["updated"]:
                try:
                    db.update("stock_items", it["id"], {"cost_price": it["new_cost"]})
                    cnt += 1
                except Exception as e:
                    logger.error(f"[BOLT PRICER] DB fail {it['id']}: {e}")
            results["stats"]["db_updated"] = cnt

        return jsonify({"success": True, **results})

    @app.route("/api/bolt-pricer/tiers", methods=["GET", "POST"])
    @login_required
    def api_bolt_pricer_tiers():
        if request.method == "GET":
            return jsonify(BoltPricer.get_all_tiers())
        data = request.get_json() or {}
        mat, it, rkg = data.get("material","").upper(), data.get("item_type",""), float(data.get("rkg",0))
        if mat and it and rkg > 0:
            BoltPricer.update_tier(mat, it, rkg)
            return jsonify({"success": True, "message": f"{mat}/{it} -> R{rkg}/kg"})
        return jsonify({"success": False, "error": "Need material, item_type, rkg"})

    logger.info("[BOLT PRICER] Routes registered")
