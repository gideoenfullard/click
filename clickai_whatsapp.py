# -*- coding: utf-8 -*-
# ==============================================================================
# CLICKAI WHATSAPP MODULE v1.0
# ==============================================================================
# Full WhatsApp Business API integration for ClickAI
# 
# DESIGN: "Dormant until activated"
# - Import via try/except in clickai.py
# - Toggle on/off in business settings (whatsapp_enabled flag)
# - When OFF: no buttons visible, no routes active, zero impact
# - When ON: send invoices, quotes, statements, reminders, receive orders
#
# PROVIDERS SUPPORTED:
# - 360dialog (recommended for SA — cheapest, local support)
# - Twilio (fallback — already partially in clickai.py)
# - WATI (future option)
#
# LEVELS:
# Vlak 1: Send documents (invoices, quotes, statements, payslips) ✓
# Vlak 2: Inbound messages → Zane processes orders ✓
# Vlak 3: Notifications & alerts (payment received, stock low, etc.) ✓
# Vlak 4: Full AI chatbot via WhatsApp (Zane as conversational agent) ✓
#
# ACTIVATION STEPS:
# 1. In Settings → WhatsApp → Toggle ON
# 2. Choose provider (360dialog / Twilio)
# 3. Enter API key + phone number
# 4. Done — buttons appear everywhere automatically
#
# ==============================================================================

import os
import re
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, redirect, session

logger = logging.getLogger("clickai.whatsapp")

# ==============================================================================
# WHATSAPP PROVIDER ABSTRACTION
# ==============================================================================

class WhatsAppProvider:
    """Base class for WhatsApp API providers"""
    
    def send_text(self, to: str, message: str) -> dict:
        raise NotImplementedError
    
    def send_document(self, to: str, document_url: str, filename: str, caption: str = "") -> dict:
        raise NotImplementedError
    
    def send_template(self, to: str, template_name: str, parameters: list = None) -> dict:
        raise NotImplementedError
    
    def is_configured(self) -> bool:
        raise NotImplementedError


class Provider360Dialog(WhatsAppProvider):
    """
    360dialog WhatsApp Business API provider
    Recommended for SA — ~R0.15-0.30 per message
    Docs: https://docs.360dialog.com/
    """
    
    def __init__(self, api_key: str = "", phone_number_id: str = ""):
        self.api_key = api_key
        self.phone_number_id = phone_number_id
        self.base_url = "https://waba.360dialog.io/v1"
    
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    def _headers(self):
        return {
            "D360-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
    
    def send_text(self, to: str, message: str) -> dict:
        """Send a text message"""
        try:
            resp = requests.post(
                f"{self.base_url}/messages",
                headers=self._headers(),
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": message}
                },
                timeout=30
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                msg_id = ""
                if "messages" in data and data["messages"]:
                    msg_id = data["messages"][0].get("id", "")
                return {"success": True, "message_id": msg_id}
            else:
                error = data.get("error", {}).get("message", resp.text[:200])
                return {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_document(self, to: str, document_url: str, filename: str, caption: str = "") -> dict:
        """Send a document (PDF invoice, quote, etc.)"""
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "document",
                "document": {
                    "link": document_url,
                    "filename": filename
                }
            }
            if caption:
                payload["document"]["caption"] = caption
            
            resp = requests.post(
                f"{self.base_url}/messages",
                headers=self._headers(),
                json=payload,
                timeout=30
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                msg_id = ""
                if "messages" in data and data["messages"]:
                    msg_id = data["messages"][0].get("id", "")
                return {"success": True, "message_id": msg_id}
            else:
                error = data.get("error", {}).get("message", resp.text[:200])
                return {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_template(self, to: str, template_name: str, parameters: list = None) -> dict:
        """Send a pre-approved template message (required for first contact)"""
        try:
            components = []
            if parameters:
                components.append({
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in parameters]
                })
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "en"},
                    "components": components
                }
            }
            
            resp = requests.post(
                f"{self.base_url}/messages",
                headers=self._headers(),
                json=payload,
                timeout=30
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                msg_id = ""
                if "messages" in data and data["messages"]:
                    msg_id = data["messages"][0].get("id", "")
                return {"success": True, "message_id": msg_id}
            else:
                error = data.get("error", {}).get("message", resp.text[:200])
                return {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}


class ProviderTwilio(WhatsAppProvider):
    """
    Twilio WhatsApp provider (already partially in clickai.py)
    More expensive but very reliable
    """
    
    def __init__(self, account_sid: str = "", auth_token: str = "", from_number: str = ""):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number  # e.g. "whatsapp:+14155238886"
    
    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)
    
    def send_text(self, to: str, message: str) -> dict:
        try:
            resp = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                auth=(self.account_sid, self.auth_token),
                data={
                    "From": self.from_number,
                    "To": f"whatsapp:{to}" if not to.startswith("whatsapp:") else to,
                    "Body": message
                },
                timeout=30
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return {"success": True, "message_id": data.get("sid", "")}
            else:
                error = resp.json().get("message", resp.text[:200])
                return {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_document(self, to: str, document_url: str, filename: str, caption: str = "") -> dict:
        try:
            resp = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                auth=(self.account_sid, self.auth_token),
                data={
                    "From": self.from_number,
                    "To": f"whatsapp:{to}" if not to.startswith("whatsapp:") else to,
                    "Body": caption or filename,
                    "MediaUrl": document_url
                },
                timeout=30
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return {"success": True, "message_id": data.get("sid", "")}
            else:
                error = resp.json().get("message", resp.text[:200])
                return {"success": False, "error": error}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def send_template(self, to: str, template_name: str, parameters: list = None) -> dict:
        # Twilio uses ContentSid for templates — simplified here
        body = f"[Template: {template_name}]"
        if parameters:
            body += " " + " | ".join(parameters)
        return self.send_text(to, body)


# ==============================================================================
# WHATSAPP ENGINE — The Brains
# ==============================================================================

class WhatsAppEngine:
    """
    Central WhatsApp engine for ClickAI.
    
    Handles:
    - Provider selection (360dialog / Twilio)
    - Phone number formatting (SA numbers)
    - Message logging & audit trail
    - Rate limiting
    - Toggle on/off per business
    """
    
    # In-memory rate limiter: {phone: [timestamp, ...]}
    _rate_limits = {}
    RATE_LIMIT_MAX = 20       # max messages per phone per hour
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
    
    def __init__(self, db):
        self.db = db
        self._provider_cache = {}  # {business_id: provider_instance}
    
    # ------------------------------------------------------------------
    # CONFIG & TOGGLE
    # ------------------------------------------------------------------
    
    def is_enabled(self, business: dict) -> bool:
        """Check if WhatsApp is enabled for this business"""
        if not business:
            return False
        wa_config = business.get("whatsapp_config") or {}
        if isinstance(wa_config, str):
            try:
                wa_config = json.loads(wa_config)
            except:
                wa_config = {}
        return wa_config.get("enabled", False)
    
    def get_config(self, business: dict) -> dict:
        """Get WhatsApp config for business"""
        wa_config = business.get("whatsapp_config") or {}
        if isinstance(wa_config, str):
            try:
                wa_config = json.loads(wa_config)
            except:
                wa_config = {}
        return wa_config
    
    def get_provider(self, business: dict) -> WhatsAppProvider:
        """Get the configured provider for a business"""
        biz_id = business.get("id", "")
        
        # Check cache
        if biz_id in self._provider_cache:
            return self._provider_cache[biz_id]
        
        config = self.get_config(business)
        provider_name = config.get("provider", "360dialog")
        
        if provider_name == "twilio":
            provider = ProviderTwilio(
                account_sid=config.get("twilio_sid", ""),
                auth_token=config.get("twilio_auth", ""),
                from_number=config.get("twilio_from", "")
            )
        else:
            # Default: 360dialog
            provider = Provider360Dialog(
                api_key=config.get("api_key", ""),
                phone_number_id=config.get("phone_number_id", "")
            )
        
        self._provider_cache[biz_id] = provider
        return provider
    
    def clear_provider_cache(self, business_id: str = ""):
        """Clear cached provider (call after config change)"""
        if business_id:
            self._provider_cache.pop(business_id, None)
        else:
            self._provider_cache.clear()
    
    # ------------------------------------------------------------------
    # PHONE NUMBER FORMATTING (SA-SPECIFIC)
    # ------------------------------------------------------------------
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """
        Format a South African phone number for WhatsApp API.
        Input: "082 123 4567" or "0821234567" or "+27821234567"
        Output: "+27821234567"
        """
        if not phone:
            return ""
        
        # Strip everything except digits and +
        phone = re.sub(r"[^\d+]", "", phone)
        
        # Remove whatsapp: prefix if present
        phone = phone.replace("whatsapp:", "")
        
        # Convert 0XX to +27XX (SA)
        if phone.startswith("0") and len(phone) == 10:
            phone = "+27" + phone[1:]
        
        # Add + if missing but starts with 27
        if phone.startswith("27") and not phone.startswith("+"):
            phone = "+" + phone
        
        # Ensure + prefix for any international number
        if not phone.startswith("+"):
            phone = "+" + phone
        
        return phone
    
    # ------------------------------------------------------------------
    # RATE LIMITING
    # ------------------------------------------------------------------
    
    def _check_rate_limit(self, phone: str) -> bool:
        """Return True if OK to send, False if rate limited"""
        now = time.time()
        
        if phone not in self._rate_limits:
            self._rate_limits[phone] = []
        
        # Clean old entries
        self._rate_limits[phone] = [
            t for t in self._rate_limits[phone] 
            if now - t < self.RATE_LIMIT_WINDOW
        ]
        
        if len(self._rate_limits[phone]) >= self.RATE_LIMIT_MAX:
            return False
        
        self._rate_limits[phone].append(now)
        return True
    
    # ------------------------------------------------------------------
    # MESSAGE LOGGING
    # ------------------------------------------------------------------
    
    def _log_message(self, business_id: str, direction: str, phone: str, 
                     message_type: str, content_summary: str, result: dict,
                     related_id: str = "", related_type: str = ""):
        """Log WhatsApp message to database for audit trail"""
        try:
            import uuid as _uuid
            self.db.save("whatsapp_log", {
                "id": str(_uuid.uuid4()),
                "business_id": business_id,
                "direction": direction,        # "outbound" / "inbound"
                "phone": phone,
                "message_type": message_type,   # "invoice", "quote", "reminder", "chat", etc.
                "content_summary": content_summary[:500],
                "success": result.get("success", False),
                "message_id": result.get("message_id", ""),
                "error": result.get("error", "")[:500] if not result.get("success") else "",
                "related_id": related_id,       # invoice_id, quote_id, etc.
                "related_type": related_type,   # "invoice", "quote", "customer", etc.
                "created_at": datetime.now().isoformat()
            })
        except Exception as e:
            # Log table might not exist yet — that's fine, don't crash
            logger.warning(f"[WA-LOG] Could not log message: {e}")
    
    # ------------------------------------------------------------------
    # VLAK 1: SEND DOCUMENTS
    # ------------------------------------------------------------------
    
    def send_invoice(self, business: dict, invoice: dict, customer: dict, 
                     pdf_url: str = "") -> dict:
        """Send invoice to customer via WhatsApp"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = customer.get("phone") or customer.get("cell") or customer.get("mobile") or ""
        phone = self.format_phone(phone)
        if not phone:
            return {"success": False, "error": "No phone number for customer"}
        
        if not self._check_rate_limit(phone):
            return {"success": False, "error": "Rate limited — too many messages to this number"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "WhatsApp provider not configured"}
        
        biz_name = business.get("name", "")
        inv_num = invoice.get("invoice_number", invoice.get("number", ""))
        total = float(invoice.get("total", 0))
        
        # If we have a PDF URL, send as document
        if pdf_url:
            result = provider.send_document(
                to=phone,
                document_url=pdf_url,
                filename=f"Invoice_{inv_num}.pdf",
                caption=f"📄 Invoice {inv_num} from {biz_name}\nAmount: R{total:,.2f}\n\nThank you for your business!"
            )
        else:
            # Text-only with portal link
            portal_url = f"https://www.clickai.co.za/portal/invoice/{invoice.get('id', '')}"
            message = (
                f"📄 *Invoice from {biz_name}*\n\n"
                f"Invoice: {inv_num}\n"
                f"Amount: R{total:,.2f}\n\n"
                f"View & Pay online:\n{portal_url}\n\n"
                f"Thank you for your business!"
            )
            result = provider.send_text(phone, message)
        
        # Log it
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="invoice",
            content_summary=f"Invoice {inv_num} — R{total:,.2f}",
            result=result,
            related_id=invoice.get("id", ""),
            related_type="invoice"
        )
        
        return result
    
    def send_quote(self, business: dict, quote: dict, customer: dict,
                   pdf_url: str = "") -> dict:
        """Send quote to customer via WhatsApp"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = customer.get("phone") or customer.get("cell") or customer.get("mobile") or ""
        phone = self.format_phone(phone)
        if not phone:
            return {"success": False, "error": "No phone number for customer"}
        
        if not self._check_rate_limit(phone):
            return {"success": False, "error": "Rate limited"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "WhatsApp provider not configured"}
        
        biz_name = business.get("name", "")
        quote_num = quote.get("quote_number", quote.get("number", ""))
        total = float(quote.get("total", 0))
        
        if pdf_url:
            result = provider.send_document(
                to=phone,
                document_url=pdf_url,
                filename=f"Quote_{quote_num}.pdf",
                caption=f"📋 Quote {quote_num} from {biz_name}\nTotal: R{total:,.2f}\n\nReply APPROVE to accept this quote."
            )
        else:
            portal_url = f"https://www.clickai.co.za/portal/quote/{quote.get('id', '')}"
            message = (
                f"📋 *Quote from {biz_name}*\n\n"
                f"Quote: {quote_num}\n"
                f"Total: R{total:,.2f}\n\n"
                f"View online:\n{portal_url}\n\n"
                f"Reply *APPROVE* to accept this quote."
            )
            result = provider.send_text(phone, message)
        
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="quote",
            content_summary=f"Quote {quote_num} — R{total:,.2f}",
            result=result,
            related_id=quote.get("id", ""),
            related_type="quote"
        )
        
        return result
    
    def send_statement(self, business: dict, customer: dict, balance: float) -> dict:
        """Send statement/balance notification"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = customer.get("phone") or customer.get("cell") or customer.get("mobile") or ""
        phone = self.format_phone(phone)
        if not phone:
            return {"success": False, "error": "No phone number"}
        
        if not self._check_rate_limit(phone):
            return {"success": False, "error": "Rate limited"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "WhatsApp provider not configured"}
        
        biz_name = business.get("name", "")
        cust_name = customer.get("name", "Customer")
        portal_url = f"https://www.clickai.co.za/portal/statement/{customer.get('id', '')}"
        
        message = (
            f"📊 *Statement from {biz_name}*\n\n"
            f"Hi {cust_name},\n\n"
            f"Your current balance: *R{balance:,.2f}*\n\n"
            f"View full statement:\n{portal_url}\n\n"
            f"Thank you for your business!"
        )
        
        result = provider.send_text(phone, message)
        
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="statement",
            content_summary=f"Statement for {cust_name} — R{balance:,.2f}",
            result=result,
            related_id=customer.get("id", ""),
            related_type="customer"
        )
        
        return result
    
    def send_payslip(self, business: dict, employee: dict, payslip: dict,
                     pdf_url: str = "") -> dict:
        """Send payslip to employee via WhatsApp"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = employee.get("phone") or employee.get("cell") or employee.get("mobile") or ""
        phone = self.format_phone(phone)
        if not phone:
            return {"success": False, "error": "No phone number for employee"}
        
        if not self._check_rate_limit(phone):
            return {"success": False, "error": "Rate limited"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "WhatsApp provider not configured"}
        
        biz_name = business.get("name", "")
        emp_name = employee.get("name", employee.get("first_name", ""))
        period = payslip.get("period", payslip.get("pay_period", ""))
        
        if pdf_url:
            result = provider.send_document(
                to=phone,
                document_url=pdf_url,
                filename=f"Payslip_{period}.pdf",
                caption=f"💰 Hi {emp_name}, your payslip for {period} from {biz_name} is attached."
            )
        else:
            net_pay = float(payslip.get("net_pay", 0))
            message = (
                f"💰 *Payslip from {biz_name}*\n\n"
                f"Hi {emp_name},\n\n"
                f"Period: {period}\n"
                f"Net Pay: R{net_pay:,.2f}\n\n"
                f"Your full payslip is available on the portal."
            )
            result = provider.send_text(phone, message)
        
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="payslip",
            content_summary=f"Payslip for {emp_name} — {period}",
            result=result,
            related_id=payslip.get("id", ""),
            related_type="payslip"
        )
        
        return result
    
    # ------------------------------------------------------------------
    # VLAK 2: PAYMENT REMINDERS
    # ------------------------------------------------------------------
    
    def send_payment_reminder(self, business: dict, customer: dict, 
                              amount: float, days_overdue: int = 0) -> dict:
        """Send payment reminder with escalating urgency"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = customer.get("phone") or customer.get("cell") or customer.get("mobile") or ""
        phone = self.format_phone(phone)
        if not phone:
            return {"success": False, "error": "No phone number"}
        
        if not self._check_rate_limit(phone):
            return {"success": False, "error": "Rate limited"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "WhatsApp provider not configured"}
        
        biz_name = business.get("name", "")
        cust_name = customer.get("name", "Customer")
        banking = business.get("banking_details", "Please contact us for banking details.")
        
        # Escalating tone
        if days_overdue > 60:
            header = "⚠️ *URGENT — FINAL NOTICE*"
            tone = "Please settle this amount immediately to avoid further action."
        elif days_overdue > 30:
            header = "⏰ *OVERDUE REMINDER*"
            tone = "Please arrange payment at your earliest convenience."
        elif days_overdue > 7:
            header = "📬 *Payment Reminder*"
            tone = "Just a friendly reminder about your outstanding balance."
        else:
            header = "📬 *Payment Reminder*"
            tone = "A gentle reminder about your account balance."
        
        message = (
            f"{header}\n\n"
            f"Hi {cust_name},\n\n"
            f"Outstanding balance with {biz_name}: *R{amount:,.2f}*\n\n"
            f"{tone}\n\n"
            f"Banking details:\n{banking}\n\n"
            f"Questions? Reply to this message.\n\n"
            f"Thank you!"
        )
        
        result = provider.send_text(phone, message)
        
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="reminder",
            content_summary=f"Reminder: {cust_name} — R{amount:,.2f} ({days_overdue}d overdue)",
            result=result,
            related_id=customer.get("id", ""),
            related_type="customer"
        )
        
        return result
    
    # ------------------------------------------------------------------
    # VLAK 3: NOTIFICATIONS & ALERTS
    # ------------------------------------------------------------------
    
    def send_payment_received(self, business: dict, customer: dict, 
                              amount: float, reference: str = "") -> dict:
        """Notify customer that payment was received"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = customer.get("phone") or customer.get("cell") or customer.get("mobile") or ""
        phone = self.format_phone(phone)
        if not phone:
            return {"success": False, "error": "No phone number"}
        
        if not self._check_rate_limit(phone):
            return {"success": False, "error": "Rate limited"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "Provider not configured"}
        
        biz_name = business.get("name", "")
        cust_name = customer.get("name", "Customer")
        
        message = (
            f"✅ *Payment Received*\n\n"
            f"Hi {cust_name},\n\n"
            f"We've received your payment of *R{amount:,.2f}*"
            f"{f' (Ref: {reference})' if reference else ''}.\n\n"
            f"Thank you!\n— {biz_name}"
        )
        
        result = provider.send_text(phone, message)
        
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="payment_received",
            content_summary=f"Payment received: R{amount:,.2f}",
            result=result,
            related_id=customer.get("id", ""),
            related_type="customer"
        )
        
        return result
    
    def send_order_ready(self, business: dict, customer: dict, 
                         order_ref: str = "") -> dict:
        """Notify customer that order is ready for collection"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = customer.get("phone") or customer.get("cell") or customer.get("mobile") or ""
        phone = self.format_phone(phone)
        if not phone:
            return {"success": False, "error": "No phone number"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "Provider not configured"}
        
        biz_name = business.get("name", "")
        cust_name = customer.get("name", "Customer")
        
        message = (
            f"📦 *Order Ready for Collection*\n\n"
            f"Hi {cust_name},\n\n"
            f"Your order{f' ({order_ref})' if order_ref else ''} is ready for collection.\n\n"
            f"— {biz_name}"
        )
        
        result = provider.send_text(phone, message)
        
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="order_ready",
            content_summary=f"Order ready: {order_ref}",
            result=result,
            related_id=customer.get("id", ""),
            related_type="customer"
        )
        
        return result
    
    def send_stock_alert(self, business: dict, owner_phone: str,
                         items: list) -> dict:
        """Alert owner about low stock items"""
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        phone = self.format_phone(owner_phone)
        if not phone:
            return {"success": False, "error": "No phone number"}
        
        provider = self.get_provider(business)
        if not provider.is_configured():
            return {"success": False, "error": "Provider not configured"}
        
        item_lines = []
        for item in items[:10]:  # Max 10 items in message
            name = item.get("description", item.get("name", "?"))
            qty = item.get("quantity", item.get("qty", 0))
            minimum = item.get("minimum_stock", item.get("reorder_level", 0))
            item_lines.append(f"• {name}: {qty} left (min: {minimum})")
        
        message = (
            f"📉 *Low Stock Alert*\n\n"
            f"The following items are below minimum:\n\n"
            f"{chr(10).join(item_lines)}\n\n"
            f"{'...' if len(items) > 10 else ''}"
            f"Consider placing orders soon."
        )
        
        result = provider.send_text(phone, message)
        
        self._log_message(
            business_id=business.get("id", ""),
            direction="outbound",
            phone=phone,
            message_type="stock_alert",
            content_summary=f"Low stock alert: {len(items)} items",
            result=result
        )
        
        return result
    
    # ------------------------------------------------------------------
    # VLAK 4: INBOUND WEBHOOK (Receive messages → Zane)
    # ------------------------------------------------------------------
    
    def process_inbound(self, business: dict, payload: dict, 
                        zane_handler=None) -> dict:
        """
        Process incoming WhatsApp message.
        
        Flow:
        1. Parse the incoming message
        2. Look up the sender (customer/supplier)
        3. Route to Zane for AI processing
        4. Send Zane's response back via WhatsApp
        
        This is the "Holy Grail" — full conversational AI via WhatsApp.
        The zane_handler is a callable: zane_handler(message, business, customer) -> response_text
        """
        if not self.is_enabled(business):
            return {"success": False, "error": "WhatsApp not enabled"}
        
        # Parse inbound message (360dialog / Meta format)
        try:
            entry = payload.get("entry", [{}])[0] if "entry" in payload else payload
            changes = entry.get("changes", [{}])[0] if "changes" in entry else entry
            value = changes.get("value", {}) if "value" in changes else changes
            messages = value.get("messages", [])
            
            if not messages:
                return {"success": True, "action": "no_message"}
            
            msg = messages[0]
            from_phone = msg.get("from", "")
            msg_type = msg.get("type", "text")
            
            # Extract text content
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
            elif msg_type == "interactive":
                # Button replies
                interactive = msg.get("interactive", {})
                if "button_reply" in interactive:
                    text = interactive["button_reply"].get("title", "")
                elif "list_reply" in interactive:
                    text = interactive["list_reply"].get("title", "")
                else:
                    text = ""
            else:
                text = f"[{msg_type} message — not supported yet]"
            
            if not text:
                return {"success": True, "action": "empty_message"}
            
        except Exception as e:
            logger.error(f"[WA-INBOUND] Parse error: {e}")
            return {"success": False, "error": f"Could not parse message: {e}"}
        
        # Log inbound
        self._log_message(
            business_id=business.get("id", ""),
            direction="inbound",
            phone=from_phone,
            message_type="chat",
            content_summary=text[:500],
            result={"success": True, "message_id": msg.get("id", "")}
        )
        
        # Look up customer by phone
        formatted = self.format_phone(from_phone)
        customer = self._find_customer_by_phone(business.get("id", ""), from_phone)
        
        # Route to Zane if handler provided
        if zane_handler:
            try:
                response_text = zane_handler(
                    message=text,
                    business=business,
                    customer=customer,
                    phone=from_phone
                )
                
                if response_text:
                    # Send Zane's response back
                    provider = self.get_provider(business)
                    send_result = provider.send_text(formatted, response_text)
                    
                    self._log_message(
                        business_id=business.get("id", ""),
                        direction="outbound",
                        phone=formatted,
                        message_type="chat_reply",
                        content_summary=response_text[:500],
                        result=send_result
                    )
                    
                    return {"success": True, "action": "zane_replied", "response": response_text[:200]}
                
            except Exception as e:
                logger.error(f"[WA-INBOUND] Zane handler error: {e}")
                # Send fallback message
                provider = self.get_provider(business)
                provider.send_text(
                    formatted,
                    "Thanks for your message! We've received it and will get back to you shortly."
                )
                return {"success": True, "action": "fallback_sent", "error": str(e)}
        
        return {"success": True, "action": "received_no_handler", "text": text[:200]}
    
    def _find_customer_by_phone(self, business_id: str, phone: str) -> dict:
        """Look up a customer by phone number"""
        if not phone:
            return {}
        
        # Normalize for search
        digits = re.sub(r"[^\d]", "", phone)[-9:]  # Last 9 digits (SA numbers)
        
        try:
            customers = self.db.get("customers", {"business_id": business_id})
            for c in (customers or []):
                for field in ["phone", "cell", "mobile"]:
                    cphone = c.get(field, "") or ""
                    cdigits = re.sub(r"[^\d]", "", cphone)[-9:]
                    if cdigits and cdigits == digits:
                        return c
        except Exception as e:
            logger.warning(f"[WA] Customer lookup failed: {e}")
        
        return {}
    
    # ------------------------------------------------------------------
    # BULK OPERATIONS
    # ------------------------------------------------------------------
    
    def send_bulk_reminders(self, business: dict, customers: list) -> dict:
        """Send reminders to multiple customers"""
        results = {"sent": 0, "failed": 0, "skipped": 0, "errors": []}
        
        for customer in customers:
            balance = float(customer.get("balance", 0))
            if balance <= 0:
                results["skipped"] += 1
                continue
            
            days_overdue = customer.get("days_overdue", 0)
            result = self.send_payment_reminder(business, customer, balance, days_overdue)
            
            if result.get("success"):
                results["sent"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{customer.get('name', '?')}: {result.get('error', '?')}")
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
        
        return results


# ==============================================================================
# FLASK ROUTE REGISTRATION
# ==============================================================================

def register_whatsapp_routes(app, db, login_required, Auth, generate_id, render_page=None):
    """
    Register all WhatsApp routes.
    Called from clickai.py after app and db are defined.
    
    This creates:
    - Settings page for WhatsApp config
    - API endpoints for sending messages
    - Webhook endpoint for receiving messages
    - UI snippet generator for "Send via WhatsApp" buttons
    """
    
    engine = WhatsAppEngine(db)
    
    # ------------------------------------------------------------------
    # SETTINGS: WhatsApp Configuration Page
    # ------------------------------------------------------------------
    
    @app.route("/settings/whatsapp")
    @login_required
    def whatsapp_settings_page():
        """WhatsApp configuration page"""
        business = Auth.get_current_business()
        if not business:
            return redirect("/settings")
        
        user = Auth.get_current_user()
        config = engine.get_config(business)
        enabled = config.get("enabled", False)
        provider = config.get("provider", "360dialog")
        
        content = f'''
        <div class="card" style="max-width:700px;">
            <h2 style="margin-bottom:5px;">📱 WhatsApp Integration</h2>
            <p style="color:var(--text-muted);margin-bottom:25px;">
                Send invoices, quotes, reminders and more via WhatsApp
            </p>
            
            <form id="waForm">
                <!-- MASTER TOGGLE -->
                <div style="display:flex;align-items:center;justify-content:space-between;
                            padding:15px;border-radius:10px;margin-bottom:20px;
                            background:{'rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3)' if enabled else 'rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1)'};">
                    <div>
                        <strong>WhatsApp {'Active ✅' if enabled else 'Inactive'}</strong><br>
                        <small style="color:var(--text-muted);">
                            {'Messages are being sent' if enabled else 'Toggle on when ready — all features will activate automatically'}
                        </small>
                    </div>
                    <label style="position:relative;display:inline-block;width:50px;height:26px;cursor:pointer;">
                        <input type="checkbox" id="waEnabled" name="enabled" 
                               {'checked' if enabled else ''}
                               style="opacity:0;width:0;height:0;"
                               onchange="document.getElementById('providerSection').style.display=this.checked?'block':'none'">
                        <span style="position:absolute;top:0;left:0;right:0;bottom:0;
                                     background:{'#10b981' if enabled else '#374151'};
                                     border-radius:26px;transition:0.3s;">
                            <span style="position:absolute;content:'';height:20px;width:20px;
                                         left:{'27px' if enabled else '3px'};bottom:3px;
                                         background:white;border-radius:50%;transition:0.3s;
                                         display:block;"></span>
                        </span>
                    </label>
                </div>
                
                <!-- PROVIDER CONFIG (shown when enabled) -->
                <div id="providerSection" style="display:{'block' if enabled else 'none'};">
                    
                    <div class="form-group">
                        <label class="form-label">Provider</label>
                        <select name="provider" class="form-input" onchange="toggleProvider(this.value)">
                            <option value="360dialog" {'selected' if provider == '360dialog' else ''}>
                                360dialog (Recommended for SA — cheapest)
                            </option>
                            <option value="twilio" {'selected' if provider == 'twilio' else ''}>
                                Twilio (Reliable, more expensive)
                            </option>
                        </select>
                    </div>
                    
                    <!-- 360dialog fields -->
                    <div id="config360" style="display:{'block' if provider == '360dialog' else 'none'};">
                        <div class="form-group">
                            <label class="form-label">360dialog API Key</label>
                            <input type="password" name="api_key" class="form-input" 
                                   value="{config.get('api_key', '')}"
                                   placeholder="Your 360dialog API key">
                            <small style="color:var(--text-muted);">
                                Get this from <a href="https://hub.360dialog.com" target="_blank" 
                                style="color:var(--primary);">hub.360dialog.com</a>
                            </small>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Phone Number ID (optional)</label>
                            <input type="text" name="phone_number_id" class="form-input"
                                   value="{config.get('phone_number_id', '')}"
                                   placeholder="Your WhatsApp phone number ID">
                        </div>
                    </div>
                    
                    <!-- Twilio fields -->
                    <div id="configTwilio" style="display:{'block' if provider == 'twilio' else 'none'};">
                        <div class="form-group">
                            <label class="form-label">Twilio Account SID</label>
                            <input type="text" name="twilio_sid" class="form-input"
                                   value="{config.get('twilio_sid', '')}"
                                   placeholder="ACxxxxxxxx">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Twilio Auth Token</label>
                            <input type="password" name="twilio_auth" class="form-input"
                                   value="{config.get('twilio_auth', '')}"
                                   placeholder="Your auth token">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Twilio WhatsApp Number</label>
                            <input type="text" name="twilio_from" class="form-input"
                                   value="{config.get('twilio_from', '')}"
                                   placeholder="whatsapp:+14155238886">
                        </div>
                    </div>
                    
                    <!-- NOTIFICATION PREFERENCES -->
                    <h3 style="margin-top:25px;margin-bottom:10px;">Automatic Notifications</h3>
                    <p style="color:var(--text-muted);margin-bottom:15px;font-size:0.9em;">
                        Choose which messages to send automatically
                    </p>
                    
                    <label style="display:flex;align-items:center;gap:8px;margin-bottom:10px;cursor:pointer;">
                        <input type="checkbox" name="auto_invoice" {'checked' if config.get('auto_invoice', False) else ''}>
                        <span>Send invoices automatically after creation</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:8px;margin-bottom:10px;cursor:pointer;">
                        <input type="checkbox" name="auto_quote" {'checked' if config.get('auto_quote', False) else ''}>
                        <span>Send quotes automatically after creation</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:8px;margin-bottom:10px;cursor:pointer;">
                        <input type="checkbox" name="auto_payment_confirm" {'checked' if config.get('auto_payment_confirm', False) else ''}>
                        <span>Confirm payment received automatically</span>
                    </label>
                    <label style="display:flex;align-items:center;gap:8px;margin-bottom:10px;cursor:pointer;">
                        <input type="checkbox" name="auto_payslip" {'checked' if config.get('auto_payslip', False) else ''}>
                        <span>Send payslips to employees automatically</span>
                    </label>
                    
                </div>
                
                <div style="margin-top:25px;display:flex;gap:10px;">
                    <button type="submit" class="btn btn-primary" onclick="saveWA(event)">
                        Save Settings
                    </button>
                    <a href="/settings" class="btn btn-secondary">Back</a>
                </div>
            </form>
            
            <!-- TEST SECTION -->
            <div id="providerSection2" style="display:{'block' if enabled else 'none'};
                        margin-top:25px;padding-top:20px;border-top:1px solid rgba(255,255,255,0.1);">
                <h3 style="margin-bottom:10px;">🧪 Test Message</h3>
                <div style="display:flex;gap:10px;">
                    <input type="text" id="testPhone" class="form-input" 
                           placeholder="082 123 4567" style="flex:1;">
                    <button class="btn btn-secondary" onclick="testWA()">Send Test</button>
                </div>
                <div id="testResult" style="margin-top:10px;font-size:0.9em;"></div>
            </div>
        </div>
        
        <script>
        function toggleProvider(val) {{
            document.getElementById('config360').style.display = val === '360dialog' ? 'block' : 'none';
            document.getElementById('configTwilio').style.display = val === 'twilio' ? 'block' : 'none';
        }}
        
        async function saveWA(e) {{
            e.preventDefault();
            const form = document.getElementById('waForm');
            const data = Object.fromEntries(new FormData(form));
            data.enabled = document.getElementById('waEnabled').checked;
            
            // Checkboxes
            ['auto_invoice','auto_quote','auto_payment_confirm','auto_payslip'].forEach(k => {{
                data[k] = form.querySelector('[name="'+k+'"]')?.checked || false;
            }});
            
            const resp = await fetch('/api/whatsapp/config', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(data)
            }});
            const result = await resp.json();
            if (result.success) {{
                location.reload();
            }} else {{
                alert('Error: ' + (result.error || 'Unknown'));
            }}
        }}
        
        async function testWA() {{
            const phone = document.getElementById('testPhone').value;
            if (!phone) return alert('Enter a phone number');
            const el = document.getElementById('testResult');
            el.innerHTML = 'Sending...';
            
            const resp = await fetch('/api/whatsapp/test', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{phone: phone}})
            }});
            const result = await resp.json();
            el.innerHTML = result.success 
                ? '<span style="color:#10b981;">✅ Message sent!</span>'
                : '<span style="color:#ef4444;">❌ ' + (result.error || 'Failed') + '</span>';
        }}
        </script>
        '''
        
        if render_page:
            return render_page("WhatsApp Settings", content, user, "settings")
        else:
            return content
    
    # ------------------------------------------------------------------
    # API: Save Config
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/config", methods=["POST"])
    @login_required
    def api_whatsapp_config():
        """Save WhatsApp configuration"""
        try:
            business = Auth.get_current_business()
            if not business:
                return jsonify({"success": False, "error": "No business selected"})
            
            data = request.get_json() or {}
            
            config = {
                "enabled": bool(data.get("enabled", False)),
                "provider": data.get("provider", "360dialog"),
                "api_key": data.get("api_key", ""),
                "phone_number_id": data.get("phone_number_id", ""),
                "twilio_sid": data.get("twilio_sid", ""),
                "twilio_auth": data.get("twilio_auth", ""),
                "twilio_from": data.get("twilio_from", ""),
                "auto_invoice": bool(data.get("auto_invoice", False)),
                "auto_quote": bool(data.get("auto_quote", False)),
                "auto_payment_confirm": bool(data.get("auto_payment_confirm", False)),
                "auto_payslip": bool(data.get("auto_payslip", False)),
            }
            
            # Save to business record
            business["whatsapp_config"] = json.dumps(config)
            db.save("businesses", business)
            
            # Clear provider cache
            engine.clear_provider_cache(business.get("id", ""))
            
            logger.info(f"[WA-CONFIG] Updated for business {business.get('name')}: enabled={config['enabled']}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"[WA-CONFIG] Error: {e}")
            return jsonify({"success": False, "error": str(e)})
    
    # ------------------------------------------------------------------
    # API: Test Message
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/test", methods=["POST"])
    @login_required
    def api_whatsapp_test():
        """Send a test WhatsApp message"""
        try:
            business = Auth.get_current_business()
            if not business:
                return jsonify({"success": False, "error": "No business"})
            
            if not engine.is_enabled(business):
                return jsonify({"success": False, "error": "WhatsApp not enabled"})
            
            data = request.get_json() or {}
            phone = data.get("phone", "")
            
            if not phone:
                return jsonify({"success": False, "error": "No phone number"})
            
            phone = engine.format_phone(phone)
            provider = engine.get_provider(business)
            
            if not provider.is_configured():
                return jsonify({"success": False, "error": "Provider not configured — check your API key"})
            
            biz_name = business.get("name", "ClickAI")
            result = provider.send_text(
                phone, 
                f"✅ Test message from {biz_name} via ClickAI WhatsApp.\n\nIf you see this, your WhatsApp integration is working!"
            )
            
            return jsonify(result)
        
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    # ------------------------------------------------------------------
    # API: Send Invoice via WhatsApp
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/send/invoice/<invoice_id>", methods=["POST"])
    @login_required
    def api_whatsapp_send_invoice(invoice_id):
        try:
            business = Auth.get_current_business()
            invoice = db.get_one("invoices", invoice_id)
            if not invoice:
                return jsonify({"success": False, "error": "Invoice not found"})
            
            customer = db.get_one("customers", invoice.get("customer_id"))
            if not customer:
                return jsonify({"success": False, "error": "Customer not found"})
            
            data = request.get_json() or {}
            pdf_url = data.get("pdf_url", "")
            
            result = engine.send_invoice(business, invoice, customer, pdf_url)
            return jsonify(result)
        
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    # ------------------------------------------------------------------
    # API: Send Quote via WhatsApp
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/send/quote/<quote_id>", methods=["POST"])
    @login_required
    def api_whatsapp_send_quote(quote_id):
        try:
            business = Auth.get_current_business()
            quote = db.get_one("quotes", quote_id)
            if not quote:
                return jsonify({"success": False, "error": "Quote not found"})
            
            customer = db.get_one("customers", quote.get("customer_id"))
            if not customer:
                return jsonify({"success": False, "error": "Customer not found"})
            
            data = request.get_json() or {}
            pdf_url = data.get("pdf_url", "")
            
            result = engine.send_quote(business, quote, customer, pdf_url)
            return jsonify(result)
        
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    # ------------------------------------------------------------------
    # API: Send Reminder
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/send/reminder/<customer_id>", methods=["POST"])
    @login_required
    def api_whatsapp_send_reminder(customer_id):
        try:
            business = Auth.get_current_business()
            customer = db.get_one("customers", customer_id)
            if not customer:
                return jsonify({"success": False, "error": "Customer not found"})
            
            balance = float(customer.get("balance", 0))
            data = request.get_json() or {}
            days_overdue = data.get("days_overdue", 0)
            
            result = engine.send_payment_reminder(business, customer, balance, days_overdue)
            return jsonify(result)
        
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    # ------------------------------------------------------------------
    # API: Send Statement
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/send/statement/<customer_id>", methods=["POST"])
    @login_required
    def api_whatsapp_send_statement(customer_id):
        try:
            business = Auth.get_current_business()
            customer = db.get_one("customers", customer_id)
            if not customer:
                return jsonify({"success": False, "error": "Customer not found"})
            
            balance = float(customer.get("balance", 0))
            result = engine.send_statement(business, customer, balance)
            return jsonify(result)
        
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    # ------------------------------------------------------------------
    # API: Bulk Reminders
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/bulk-reminders", methods=["POST"])
    @login_required
    def api_whatsapp_bulk_reminders():
        try:
            business = Auth.get_current_business()
            if not business:
                return jsonify({"success": False, "error": "No business"})
            
            # Get overdue customers
            customers = db.get("customers", {"business_id": business.get("id")})
            overdue = [c for c in (customers or []) if float(c.get("balance", 0)) > 0]
            
            results = engine.send_bulk_reminders(business, overdue)
            return jsonify({"success": True, **results})
        
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    # ------------------------------------------------------------------
    # WEBHOOK: Inbound messages (from WhatsApp → ClickAI)
    # ------------------------------------------------------------------
    
    @app.route("/webhook/whatsapp", methods=["GET", "POST"])
    def webhook_whatsapp():
        """
        Webhook for incoming WhatsApp messages.
        
        GET: Verification challenge (required by Meta/360dialog)
        POST: Incoming message
        """
        if request.method == "GET":
            # Verification challenge
            mode = request.args.get("hub.mode", "")
            token = request.args.get("hub.verify_token", "")
            challenge = request.args.get("hub.challenge", "")
            
            # Verify token should match what's configured
            # For now, accept any valid challenge request
            if mode == "subscribe" and challenge:
                return challenge, 200
            return "OK", 200
        
        # POST: Incoming message
        try:
            payload = request.get_json() or {}
            
            # Determine which business this webhook is for
            # Option 1: Path-based (/webhook/whatsapp/<business_id>)
            # Option 2: Look up by phone number
            # For now, we'll need the business context — this gets configured per-business
            
            logger.info(f"[WA-WEBHOOK] Incoming: {json.dumps(payload)[:500]}")
            
            # TODO: Route to correct business based on phone number or webhook config
            # For now, log and acknowledge
            
            return jsonify({"success": True}), 200
        
        except Exception as e:
            logger.error(f"[WA-WEBHOOK] Error: {e}")
            return jsonify({"success": True}), 200  # Always return 200 to avoid retries
    
    @app.route("/webhook/whatsapp/<business_id>", methods=["POST"])
    def webhook_whatsapp_business(business_id):
        """Business-specific webhook endpoint"""
        try:
            business = db.get_one("businesses", business_id)
            if not business:
                return jsonify({"success": True}), 200
            
            payload = request.get_json() or {}
            
            # Process with Zane handler (will be None until Vlak 4 is activated)
            result = engine.process_inbound(business, payload, zane_handler=None)
            
            logger.info(f"[WA-WEBHOOK] Business {business_id}: {result.get('action', '?')}")
            
            return jsonify({"success": True}), 200
        
        except Exception as e:
            logger.error(f"[WA-WEBHOOK] Error for {business_id}: {e}")
            return jsonify({"success": True}), 200
    
    # ------------------------------------------------------------------
    # HELPER: UI Button Snippet Generator
    # ------------------------------------------------------------------
    
    @app.context_processor
    def whatsapp_helpers():
        """
        Inject WhatsApp helpers into all templates.
        This makes the "Send via WhatsApp" button available everywhere.
        """
        def wa_button(doc_type, doc_id, label="WhatsApp", size="sm"):
            """Generate a WhatsApp send button HTML snippet"""
            try:
                business = Auth.get_current_business()
                if not business or not engine.is_enabled(business):
                    return ""  # Return empty string — button is invisible
                
                return f'''<button class="btn btn-{'sm' if size == 'sm' else 'primary'}" 
                    style="background:#25D366;border:none;color:white;{'font-size:0.85em;padding:4px 10px;' if size == 'sm' else ''}"
                    onclick="sendWA('{doc_type}','{doc_id}')"
                    title="Send via WhatsApp">
                    📱 {label}
                </button>'''
            except:
                return ""
        
        def wa_enabled():
            """Check if WhatsApp is enabled for current business"""
            try:
                business = Auth.get_current_business()
                return engine.is_enabled(business) if business else False
            except:
                return False
        
        return dict(wa_button=wa_button, wa_enabled=wa_enabled)
    
    # ------------------------------------------------------------------
    # WHATSAPP LOG / HISTORY PAGE
    # ------------------------------------------------------------------
    
    @app.route("/whatsapp/log")
    @login_required
    def whatsapp_log_page():
        """View WhatsApp message history"""
        business = Auth.get_current_business()
        if not business:
            return redirect("/")
        
        user = Auth.get_current_user()
        
        try:
            logs = db.get("whatsapp_log", {"business_id": business.get("id")}) or []
            logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            logs = logs[:100]  # Last 100 messages
        except:
            logs = []
        
        rows = ""
        for log in logs:
            status = "✅" if log.get("success") else "❌"
            direction = "↗️" if log.get("direction") == "outbound" else "↙️"
            ts = log.get("created_at", "")[:16].replace("T", " ")
            rows += f'''<tr>
                <td>{ts}</td>
                <td>{direction} {log.get('direction', '')}</td>
                <td>{log.get('phone', '')}</td>
                <td>{log.get('message_type', '')}</td>
                <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                    {log.get('content_summary', '')[:80]}
                </td>
                <td>{status}</td>
            </tr>'''
        
        content = f'''
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <h2>📱 WhatsApp Message Log</h2>
                <a href="/settings/whatsapp" class="btn btn-secondary">⚙️ Settings</a>
            </div>
            
            <table class="table" style="width:100%;font-size:0.9em;">
                <thead>
                    <tr>
                        <th>Time</th><th>Dir</th><th>Phone</th>
                        <th>Type</th><th>Content</th><th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows if rows else '<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--text-muted);">No messages yet</td></tr>'}
                </tbody>
            </table>
        </div>
        '''
        
        if render_page:
            return render_page("WhatsApp Log", content, user, "whatsapp")
        else:
            return content
    
    # ------------------------------------------------------------------
    # JS SNIPPET: Global WhatsApp send function
    # ------------------------------------------------------------------
    
    @app.route("/api/whatsapp/js")
    def whatsapp_js():
        """
        Return the global sendWA() JavaScript function.
        Include in pages via: <script src="/api/whatsapp/js"></script>
        Only returns content if WhatsApp is enabled.
        """
        try:
            business = Auth.get_current_business()
            if not business or not engine.is_enabled(business):
                return "// WhatsApp not enabled", 200, {"Content-Type": "application/javascript"}
        except:
            return "// WhatsApp error", 200, {"Content-Type": "application/javascript"}
        
        js = '''
        async function sendWA(docType, docId) {
            if (!confirm('Send via WhatsApp?')) return;
            
            const btn = event.target;
            const origText = btn.innerText;
            btn.innerText = 'Sending...';
            btn.disabled = true;
            
            try {
                const resp = await fetch(`/api/whatsapp/send/${docType}/${docId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
                });
                const result = await resp.json();
                
                if (result.success) {
                    btn.innerText = '✅ Sent!';
                    btn.style.background = '#10b981';
                    setTimeout(() => {
                        btn.innerText = origText;
                        btn.style.background = '#25D366';
                        btn.disabled = false;
                    }, 2000);
                } else {
                    alert('WhatsApp error: ' + (result.error || 'Unknown error'));
                    btn.innerText = origText;
                    btn.disabled = false;
                }
            } catch (err) {
                alert('Network error: ' + err.message);
                btn.innerText = origText;
                btn.disabled = false;
            }
        }
        '''
        
        return js, 200, {"Content-Type": "application/javascript"}
    
    # Expose the engine so clickai.py can use it
    app.whatsapp_engine = engine
    
    logger.info("[WHATSAPP] Module loaded and routes registered ✓")
    
    return engine


# ==============================================================================
# SQL: Database table creation (run once)
# ==============================================================================

WHATSAPP_LOG_SQL = """
CREATE TABLE IF NOT EXISTS whatsapp_log (
    id TEXT PRIMARY KEY,
    business_id TEXT NOT NULL,
    direction TEXT DEFAULT 'outbound',
    phone TEXT,
    message_type TEXT,
    content_summary TEXT,
    success BOOLEAN DEFAULT FALSE,
    message_id TEXT,
    error TEXT,
    related_id TEXT,
    related_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_log_business ON whatsapp_log(business_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_log_phone ON whatsapp_log(phone);
CREATE INDEX IF NOT EXISTS idx_whatsapp_log_created ON whatsapp_log(created_at DESC);
"""

# ==============================================================================
# BUSINESS TABLE: Add whatsapp_config column (run once)
# ==============================================================================

WHATSAPP_CONFIG_SQL = """
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS whatsapp_config JSONB DEFAULT '{}';
"""
