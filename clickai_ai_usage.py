"""
clickai_ai_usage.py — AI Usage Tracking & Billing
==================================================

Tracks every Anthropic API call per business:
- Live Supabase logging to ai_usage_log
- In-memory cache for fast meter reads (app._usage_cache)
- Month-to-date credit consumption tracking
- Admin page to view usage per business

Integration:
1. register_ai_usage_routes(app, db, login_required, Auth) in clickai.py
2. Wrap API calls with AIUsageTracker.track(business_id, tool, model) context manager
3. Header meter renders via get_usage_meter_html(business_id)
"""

import time
import logging
import traceback
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# PRICING (Anthropic official USD prices as of 2026-04)
# Update these when Anthropic changes their pricing.
# Prices are per 1 million tokens.
# ═══════════════════════════════════════════════════════════════════
PRICING_USD_PER_M_TOKENS = {
    # Sonnet family
    "claude-sonnet-4-6":          {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-5":          {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-20250514":   {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    # Haiku family
    "claude-haiku-4-5-20251001":  {"input": 1.00, "output": 5.00,  "cache_read": 0.10, "cache_write": 1.25},
    "claude-haiku-4-5":           {"input": 1.00, "output": 5.00,  "cache_read": 0.10, "cache_write": 1.25},
    "claude-3-5-haiku-20241022":  {"input": 0.80, "output": 4.00,  "cache_read": 0.08, "cache_write": 1.00},
    # Opus (fallback)
    "claude-opus-4-7":            {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
}

# Fallback for unknown models — assume Sonnet-level pricing
DEFAULT_PRICING = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}

# USD to ZAR conversion rate. Update periodically or fetch from API later.
USD_TO_ZAR = 19.50

# ═══════════════════════════════════════════════════════════════════
# CREDIT SYSTEM
# 1 credit = $0.001 raw API cost (≈R0.02 before markup)
# Markup applied separately at billing time.
# ═══════════════════════════════════════════════════════════════════
COST_PER_CREDIT_USD = 0.001

# Plan defaults — used when business has no explicit ai_plan set
DEFAULT_PLANS = {
    "starter":  {"included_credits": 500,   "price_zar": 99},
    "growth":   {"included_credits": 3000,  "price_zar": 349},
    "business": {"included_credits": 10000, "price_zar": 799},
}


# ═══════════════════════════════════════════════════════════════════
# COST CALCULATION
# ═══════════════════════════════════════════════════════════════════
def calculate_cost_usd(model: str, input_tokens: int, output_tokens: int,
                        cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> float:
    """Calculate raw USD cost from token counts."""
    pricing = PRICING_USD_PER_M_TOKENS.get(model, DEFAULT_PRICING)
    cost = (
        (input_tokens / 1_000_000) * pricing["input"] +
        (output_tokens / 1_000_000) * pricing["output"] +
        (cache_read_tokens / 1_000_000) * pricing["cache_read"] +
        (cache_write_tokens / 1_000_000) * pricing["cache_write"]
    )
    return round(cost, 6)


def calculate_credits(cost_usd: float) -> int:
    """Convert raw USD cost to credits (our billing unit)."""
    # Minimum 1 credit per request even for tiny calls — prevents free rides
    credits = max(1, int(round(cost_usd / COST_PER_CREDIT_USD)))
    return credits


# ═══════════════════════════════════════════════════════════════════
# AI USAGE TRACKER — the main class
# ═══════════════════════════════════════════════════════════════════
class AIUsageTracker:
    """
    Central usage tracker. All Anthropic API calls should go through .track()
    or manually call .log_usage() after the call completes.

    Uses app._usage_cache for fast meter reads (no Supabase hit on every page load).
    """

    _cache_key = "_usage_cache"  # attribute name on the app object

    def __init__(self, app, db):
        self.app = app
        self.db = db
        # Ensure cache exists on app
        if not hasattr(app, self._cache_key):
            setattr(app, self._cache_key, {})

    # ────────────────────────────────────────────────────────────
    # Context manager for easy wrapping of API calls
    # Usage:
    #   with tracker.track(biz_id, "scan_bank") as t:
    #       response = client.messages.create(...)
    #       t.record_response(response)
    # ────────────────────────────────────────────────────────────
    @contextmanager
    def track(self, business_id: str, tool: str, user_id: Optional[str] = None,
              metadata: Optional[dict] = None):
        tracking = _TrackingContext(
            tracker=self,
            business_id=business_id,
            tool=tool,
            user_id=user_id,
            metadata=metadata or {}
        )
        try:
            yield tracking
        except Exception as e:
            tracking.mark_error(str(e))
            raise
        finally:
            tracking.finalize()

    # ────────────────────────────────────────────────────────────
    # Direct logging (use when context manager doesn't fit)
    # ────────────────────────────────────────────────────────────
    def log_usage(self, business_id: str, tool: str, model: str,
                   input_tokens: int = 0, output_tokens: int = 0,
                   cache_read_tokens: int = 0, cache_write_tokens: int = 0,
                   duration_ms: int = 0, success: bool = True,
                   user_id: Optional[str] = None,
                   metadata: Optional[dict] = None) -> int:
        """
        Log one usage event. Writes to Supabase + updates in-memory cache.
        Returns credits_used for this call.
        """
        try:
            cost_usd = calculate_cost_usd(model, input_tokens, output_tokens,
                                           cache_read_tokens, cache_write_tokens)
            cost_zar = round(cost_usd * USD_TO_ZAR, 4)
            credits = calculate_credits(cost_usd)

            # Write to Supabase (non-blocking — best-effort)
            record = {
                "business_id": business_id,
                "user_id": user_id,
                "tool": tool,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_read_tokens": cache_read_tokens,
                "cache_write_tokens": cache_write_tokens,
                "cost_usd": cost_usd,
                "cost_zar": cost_zar,
                "credits_used": credits,
                "duration_ms": duration_ms,
                "success": success,
                "metadata": metadata or {},
            }
            try:
                self.db.save("ai_usage_log", record)
            except Exception as db_err:
                logger.error(f"[AI-USAGE] Supabase log failed: {db_err}")
                # Don't raise — failing to log should not break the user's action

            # Update in-memory cache
            self._bump_cache(business_id, credits, cost_zar)

            logger.info(f"[AI-USAGE] biz={business_id[:8]} tool={tool} model={model} "
                        f"in={input_tokens} out={output_tokens} credits={credits} "
                        f"cost_zar=R{cost_zar}")
            return credits

        except Exception as e:
            logger.error(f"[AI-USAGE] log_usage failed: {e}\n{traceback.format_exc()}")
            return 0

    # ────────────────────────────────────────────────────────────
    # Cache management
    # ────────────────────────────────────────────────────────────
    def _get_cache_entry(self, business_id: str) -> dict:
        cache = getattr(self.app, self._cache_key)
        if business_id not in cache:
            cache[business_id] = self._build_cache_entry(business_id)
        return cache[business_id]

    def _build_cache_entry(self, business_id: str) -> dict:
        """Hydrate cache from Supabase for a business (month-to-date)."""
        try:
            # Get plan info from businesses table
            biz_rows = self.db.get("businesses", {"id": business_id}, limit=1)
            biz = biz_rows[0] if biz_rows else {}
            included = int(biz.get("ai_credits_included") or 500)
            topup = int(biz.get("ai_credits_topup") or 0)
            plan = biz.get("ai_plan") or "starter"

            # Calculate month-to-date credits from usage_log
            today = date.today()
            month_start = today.replace(day=1).isoformat()

            # Simple count via Supabase — filtered by business_id and created_at
            # Note: using db.get with filter, then sum in Python for accuracy
            try:
                rows = self.db.get("ai_usage_log",
                                    {"business_id": business_id},
                                    limit=10000)
                mtd_credits = 0
                mtd_cost_zar = 0.0
                for r in rows:
                    created = str(r.get("created_at", ""))
                    if created >= month_start:
                        mtd_credits += int(r.get("credits_used") or 0)
                        mtd_cost_zar += float(r.get("cost_zar") or 0)
            except Exception as e:
                logger.error(f"[AI-USAGE] cache hydrate query failed: {e}")
                mtd_credits = 0
                mtd_cost_zar = 0.0

            return {
                "business_id": business_id,
                "plan": plan,
                "credits_included": included,
                "credits_topup": topup,
                "credits_used_mtd": mtd_credits,
                "cost_zar_mtd": round(mtd_cost_zar, 2),
                "hydrated_at": time.time(),
            }
        except Exception as e:
            logger.error(f"[AI-USAGE] build_cache_entry failed: {e}")
            return {
                "business_id": business_id,
                "plan": "starter",
                "credits_included": 500,
                "credits_topup": 0,
                "credits_used_mtd": 0,
                "cost_zar_mtd": 0.0,
                "hydrated_at": time.time(),
            }

    def _bump_cache(self, business_id: str, credits: int, cost_zar: float):
        entry = self._get_cache_entry(business_id)
        entry["credits_used_mtd"] = entry.get("credits_used_mtd", 0) + credits
        entry["cost_zar_mtd"] = round(entry.get("cost_zar_mtd", 0.0) + cost_zar, 2)

    def invalidate_cache(self, business_id: Optional[str] = None):
        """Force cache rebuild — call this at start of each month or on manual reset."""
        cache = getattr(self.app, self._cache_key)
        if business_id:
            cache.pop(business_id, None)
        else:
            cache.clear()

    # ────────────────────────────────────────────────────────────
    # Public read API
    # ────────────────────────────────────────────────────────────
    def get_status(self, business_id: str) -> dict:
        """Returns everything needed to render a usage meter."""
        entry = self._get_cache_entry(business_id)
        included = entry.get("credits_included", 500)
        topup = entry.get("credits_topup", 0)
        used = entry.get("credits_used_mtd", 0)
        total_available = included + topup
        remaining = max(0, total_available - used)
        pct_used = min(100, int(round((used / total_available * 100))) if total_available > 0 else 0)

        if pct_used >= 90:
            status_color = "red"
            status_msg = "Nearly depleted"
        elif pct_used >= 70:
            status_color = "yellow"
            status_msg = "Getting low"
        else:
            status_color = "green"
            status_msg = "Healthy"

        return {
            "plan": entry.get("plan", "starter"),
            "credits_included": included,
            "credits_topup": topup,
            "credits_total": total_available,
            "credits_used": used,
            "credits_remaining": remaining,
            "pct_used": pct_used,
            "status_color": status_color,
            "status_msg": status_msg,
            "cost_zar_mtd": entry.get("cost_zar_mtd", 0.0),
        }


# ═══════════════════════════════════════════════════════════════════
# Context manager helper class
# ═══════════════════════════════════════════════════════════════════
class _TrackingContext:
    """Returned by tracker.track() — used as the `t` in `with tracker.track(...) as t`."""

    def __init__(self, tracker, business_id, tool, user_id, metadata):
        self.tracker = tracker
        self.business_id = business_id
        self.tool = tool
        self.user_id = user_id
        self.metadata = dict(metadata)
        self.start_ts = time.time()
        self.model = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.success = True
        self.error_msg = None
        self._finalized = False

    def record_response(self, response, model: Optional[str] = None):
        """
        Extract token counts from an Anthropic response object or dict.
        Handles both SDK objects (response.usage.input_tokens) and raw JSON dicts.
        """
        try:
            # Determine model
            if model:
                self.model = model
            else:
                self.model = getattr(response, "model", None) or \
                              (response.get("model") if isinstance(response, dict) else None) or \
                              "unknown"

            # Extract usage block
            usage = None
            if hasattr(response, "usage"):
                usage = response.usage
                self.input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
                self.output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
                self.cache_read_tokens = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
                self.cache_write_tokens = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
            elif isinstance(response, dict):
                usage = response.get("usage", {}) or {}
                self.input_tokens = int(usage.get("input_tokens", 0) or 0)
                self.output_tokens = int(usage.get("output_tokens", 0) or 0)
                self.cache_read_tokens = int(usage.get("cache_read_input_tokens", 0) or 0)
                self.cache_write_tokens = int(usage.get("cache_creation_input_tokens", 0) or 0)
        except Exception as e:
            logger.error(f"[AI-USAGE] record_response parse failed: {e}")

    def record_tokens(self, model: str, input_tokens: int, output_tokens: int,
                       cache_read_tokens: int = 0, cache_write_tokens: int = 0):
        """Manual fallback when response object isn't available."""
        self.model = model
        self.input_tokens = int(input_tokens or 0)
        self.output_tokens = int(output_tokens or 0)
        self.cache_read_tokens = int(cache_read_tokens or 0)
        self.cache_write_tokens = int(cache_write_tokens or 0)

    def mark_error(self, error_msg: str):
        self.success = False
        self.error_msg = error_msg
        self.metadata["error"] = error_msg[:500]

    def finalize(self):
        if self._finalized:
            return
        self._finalized = True
        duration_ms = int((time.time() - self.start_ts) * 1000)

        # If no token data captured (e.g. call failed before response), still log the attempt
        model = self.model or "unknown"

        self.tracker.log_usage(
            business_id=self.business_id,
            tool=self.tool,
            model=model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_read_tokens=self.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens,
            duration_ms=duration_ms,
            success=self.success,
            user_id=self.user_id,
            metadata=self.metadata,
        )


# ═══════════════════════════════════════════════════════════════════
# HEADER METER HTML
# Drop this in the header template where the credit indicator should sit.
# ═══════════════════════════════════════════════════════════════════
def get_usage_meter_html(tracker: AIUsageTracker, business_id: str) -> str:
    """Returns a compact HTML usage meter for the page header."""
    if not business_id:
        return ""
    try:
        status = tracker.get_status(business_id)
    except Exception as e:
        logger.error(f"[AI-USAGE] meter render failed: {e}")
        return ""

    used = status["credits_used"]
    total = status["credits_total"]
    pct = status["pct_used"]
    color = status["status_color"]
    remaining = status["credits_remaining"]

    # Color tokens
    fill_color = {
        "green":  "#10b981",
        "yellow": "#f59e0b",
        "red":    "#ef4444",
    }.get(color, "#10b981")
    bg_color = "rgba(255,255,255,0.08)"

    # Tooltip with full detail
    tooltip = (f"AI Credits: {used:,} of {total:,} used ({pct}%)\n"
               f"Remaining: {remaining:,}\n"
               f"This month cost: R{status['cost_zar_mtd']:.2f}\n"
               f"Plan: {status['plan'].title()}\n"
               f"Click for details")

    html = f'''
    <a href="/settings/ai-usage" class="ai-usage-meter" title="{tooltip}"
       style="display:inline-flex;align-items:center;gap:8px;padding:6px 12px;
              background:{bg_color};border-radius:20px;text-decoration:none;
              color:var(--text,#fff);font-size:12px;font-weight:500;
              border:1px solid rgba(255,255,255,0.1);transition:all 0.2s;">
        <span style="font-size:14px;">⚡</span>
        <span style="white-space:nowrap;">{remaining:,} credits</span>
        <span style="display:inline-block;width:50px;height:6px;background:rgba(255,255,255,0.15);
                     border-radius:3px;overflow:hidden;">
            <span style="display:block;width:{pct}%;height:100%;background:{fill_color};
                         transition:width 0.3s;"></span>
        </span>
    </a>
    '''
    return html


# ═══════════════════════════════════════════════════════════════════
# ROUTES — admin + user-visible usage page
# ═══════════════════════════════════════════════════════════════════
def register_ai_usage_routes(app, db, login_required, Auth, render_page=None):
    """Register Flask routes for AI usage tracking."""
    from flask import jsonify, request

    tracker = AIUsageTracker(app, db)
    # Expose tracker on app object so other modules can reach it
    app._ai_usage_tracker = tracker

    @app.route("/settings/ai-usage")
    @login_required
    def ai_usage_page():
        """User-visible page showing their AI usage this month."""
        user = Auth.get_current_user()
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None

        if not biz_id:
            return "No business selected", 400

        status = tracker.get_status(biz_id)

        # Get recent usage rows for the table
        try:
            recent = db.get("ai_usage_log", {"business_id": biz_id}, limit=50) or []
            # Sort newest first
            recent.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        except Exception:
            recent = []

        # Build breakdown by tool
        tool_breakdown = {}
        for r in recent:
            t = r.get("tool", "unknown")
            tool_breakdown[t] = tool_breakdown.get(t, 0) + int(r.get("credits_used") or 0)

        # Render HTML
        color_map = {"green": "#10b981", "yellow": "#f59e0b", "red": "#ef4444"}
        fill_color = color_map.get(status["status_color"], "#10b981")

        rows_html = ""
        for r in recent[:30]:
            created = str(r.get("created_at", ""))[:16].replace("T", " ")
            tool = r.get("tool", "—")
            model = (r.get("model") or "—").replace("claude-", "")
            credits = r.get("credits_used", 0)
            cost_zar = float(r.get("cost_zar") or 0)
            status_icon = "✓" if r.get("success", True) else "✗"
            rows_html += f'''
            <tr>
                <td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);">{created}</td>
                <td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);">{tool}</td>
                <td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);font-size:11px;color:#888;">{model}</td>
                <td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);text-align:right;">{credits:,}</td>
                <td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);text-align:right;">R{cost_zar:.3f}</td>
                <td style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);text-align:center;">{status_icon}</td>
            </tr>
            '''
        if not rows_html:
            rows_html = '<tr><td colspan="6" style="padding:20px;text-align:center;color:#888;">No AI usage yet this month.</td></tr>'

        tool_breakdown_html = ""
        for t, c in sorted(tool_breakdown.items(), key=lambda x: -x[1]):
            tool_breakdown_html += f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);"><span>{t}</span><span>{c:,} credits</span></div>'
        if not tool_breakdown_html:
            tool_breakdown_html = '<div style="color:#888;padding:10px;">No usage yet.</div>'

        content = f'''
        <div style="max-width:1100px;margin:0 auto;padding:20px;">
            <div style="margin-bottom:20px;">
                <h1 style="margin:0 0 5px 0;">AI Credit Usage</h1>
                <p style="color:#888;margin:0;">Track your monthly AI consumption. Credits reset on the 1st of each month.</p>
            </div>

            <!-- Main meter card -->
            <div class="card" style="padding:24px;margin-bottom:20px;">
                <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:15px;">
                    <div>
                        <div style="font-size:13px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">This Month</div>
                        <div style="font-size:32px;font-weight:600;margin-top:4px;">{status["credits_used"]:,} / {status["credits_total"]:,}</div>
                        <div style="font-size:13px;color:#888;margin-top:2px;">credits used</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:13px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Remaining</div>
                        <div style="font-size:32px;font-weight:600;margin-top:4px;color:{fill_color};">{status["credits_remaining"]:,}</div>
                        <div style="font-size:13px;color:#888;margin-top:2px;">{status["status_msg"]}</div>
                    </div>
                </div>
                <div style="height:12px;background:rgba(255,255,255,0.08);border-radius:6px;overflow:hidden;">
                    <div style="width:{status["pct_used"]}%;height:100%;background:{fill_color};transition:width 0.5s;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:10px;font-size:12px;color:#888;">
                    <span>Plan: <strong style="color:var(--text,#fff);">{status["plan"].title()}</strong></span>
                    <span>Included: {status["credits_included"]:,}{f' + Top-up: {status["credits_topup"]:,}' if status["credits_topup"] else ''}</span>
                    <span>Approx raw cost: R{status["cost_zar_mtd"]:.2f}</span>
                </div>
            </div>

            <!-- Two-column grid -->
            <div style="display:grid;grid-template-columns:1fr 2fr;gap:20px;">
                <div class="card" style="padding:20px;">
                    <h3 style="margin:0 0 15px 0;">Usage by Tool</h3>
                    {tool_breakdown_html}
                </div>

                <div class="card" style="padding:20px;">
                    <h3 style="margin:0 0 15px 0;">Recent Activity</h3>
                    <div style="max-height:500px;overflow-y:auto;">
                        <table style="width:100%;border-collapse:collapse;font-size:13px;">
                            <thead>
                                <tr style="text-align:left;">
                                    <th style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">When</th>
                                    <th style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">Tool</th>
                                    <th style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);">Model</th>
                                    <th style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);text-align:right;">Credits</th>
                                    <th style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);text-align:right;">Cost</th>
                                    <th style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.1);text-align:center;">OK</th>
                                </tr>
                            </thead>
                            <tbody>{rows_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div style="margin-top:30px;padding:15px;background:rgba(255,255,255,0.03);border-radius:8px;font-size:13px;color:#888;">
                <strong style="color:var(--text,#fff);">How credits work:</strong><br>
                1 credit ≈ $0.001 of raw AI cost. A simple Zane chat message costs 2-5 credits.
                A full PDF bank statement scan costs 40-80 credits.
                Credits reset on the 1st of each month. Purchase top-up credits anytime if you run low.
            </div>
        </div>
        '''

        if render_page:
            return render_page("AI Usage", content, user, "settings")
        return content

    @app.route("/api/ai-usage/status")
    @login_required
    def ai_usage_status_api():
        """JSON endpoint for meter polling (frontend refresh without page reload)."""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if not biz_id:
            return jsonify({"success": False, "error": "No business"}), 400
        return jsonify({"success": True, "status": tracker.get_status(biz_id)})

    @app.route("/api/ai-usage/refresh", methods=["POST"])
    @login_required
    def ai_usage_refresh_api():
        """Force cache rebuild for current business (dev/debug)."""
        business = Auth.get_current_business()
        biz_id = business.get("id") if business else None
        if biz_id:
            tracker.invalidate_cache(biz_id)
        return jsonify({"success": True})

    logger.info("[AI-USAGE] Routes registered: /settings/ai-usage, /api/ai-usage/status, /api/ai-usage/refresh")
    return tracker
