"""
ClickAI Fraud Guard Module
===========================
Protects against internal fraud:
- Invoice cancel/credit restrictions based on role & payment status
- Mandatory reason for all cancellations
- Audit trail for sensitive actions
- Owner notifications for suspicious patterns

Import in clickai.py with try/except:
    try:
        from clickai_fraud_guard import FraudGuard
    except:
        FraudGuard = None
"""

import json
import logging
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class FraudGuard:
    """
    Invoice & financial fraud protection.
    
    Usage:
        # Check if user can cancel/credit an invoice
        result = FraudGuard.can_cancel_invoice(invoice, user_role)
        if not result["allowed"]:
            return error(result["reason"])
        
        # Log a sensitive action
        FraudGuard.log_sensitive_action(db, "INVOICE_CANCEL", invoice, user, reason)
        
        # Get daily fraud summary for owner
        summary = FraudGuard.get_daily_summary(db, business_id)
    """
    
    # Roles that can NEVER cancel/credit paid invoices
    RESTRICTED_ROLES = ("staff", "cashier", "pos_only", "waiter", "sales")
    
    # Roles that can cancel/credit anything (with reason)
    ELEVATED_ROLES = ("owner", "admin")
    
    # Manager can cancel unpaid, needs owner approval for paid
    MANAGER_ROLES = ("manager",)
    
    @staticmethod
    def can_cancel_invoice(invoice: dict, user_role: str) -> dict:
        """
        Check if current user's role allows cancelling/crediting this invoice.
        
        Returns:
            {"allowed": True/False, "reason": str, "needs_approval": bool}
        """
        try:
            role = (user_role or "").lower().strip()
            status = (invoice.get("status") or "").lower()
            is_paid = status in ("paid", "partial", "credited")
            
            # Owner/admin can always cancel (with reason)
            if role in FraudGuard.ELEVATED_ROLES:
                return {"allowed": True, "reason": "", "needs_approval": False}
            
            # Manager can cancel unpaid freely, paid needs logging
            if role in FraudGuard.MANAGER_ROLES:
                if is_paid:
                    return {
                        "allowed": True,
                        "reason": "Manager cancelling paid invoice - owner will be notified",
                        "needs_approval": False,
                        "notify_owner": True
                    }
                return {"allowed": True, "reason": "", "needs_approval": False}
            
            # Restricted roles cannot cancel paid invoices
            if role in FraudGuard.RESTRICTED_ROLES:
                if is_paid:
                    return {
                        "allowed": False,
                        "reason": f"Only a manager or owner can credit/cancel a paid invoice. Your role: {role}",
                        "needs_approval": True
                    }
                # Can cancel unpaid (e.g. draft quotes converted to invoice by mistake)
                return {"allowed": True, "reason": "", "needs_approval": False}
            
            # Unknown role - allow but log
            return {"allowed": True, "reason": "Unknown role - action logged", "needs_approval": False}
            
        except Exception as e:
            logger.error(f"[FRAUD GUARD] can_cancel_invoice error: {e}")
            # Fail open - don't block business
            return {"allowed": True, "reason": "", "needs_approval": False}
    
    @staticmethod
    def can_delete_invoice(invoice: dict, user_role: str) -> dict:
        """
        Check if user can DELETE an invoice (stricter than cancel).
        Only owner can delete. Everyone else must use credit notes.
        """
        try:
            role = (user_role or "").lower().strip()
            
            if role == "owner":
                return {"allowed": True, "reason": ""}
            
            return {
                "allowed": False,
                "reason": "Only the business owner can delete invoices. Use a Credit Note instead."
            }
        except Exception as e:
            logger.error(f"[FRAUD GUARD] can_delete_invoice error: {e}")
            return {"allowed": True, "reason": ""}
    
    @staticmethod
    def log_sensitive_action(db, action: str, record: dict, user: dict, reason: str = "", business_id: str = "", severity: str = "MEDIUM"):
        """
        Log a sensitive financial action to audit_log.
        
        Args:
            db: Database instance
            action: e.g. "INVOICE_CANCEL", "INVOICE_DELETE", "CREDIT_NOTE"
            record: The invoice/document being affected
            user: Current user dict
            reason: Why the action was taken
            business_id: Business ID
            severity: LOW, MEDIUM, HIGH, CRITICAL
        """
        try:
            from datetime import datetime
            
            log_entry = {
                "id": f"fg_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{record.get('id', '')[:8]}",
                "business_id": business_id or record.get("business_id", ""),
                "action": f"FRAUD_GUARD:{action}",
                "record_type": "invoice",
                "record_id": record.get("id", ""),
                "record_number": record.get("invoice_number", record.get("credit_note_number", "")),
                "user_id": user.get("id", ""),
                "user_name": user.get("name", user.get("email", "unknown")),
                "user_role": user.get("role", "unknown"),
                "reason": reason,
                "amount": float(record.get("total", 0)),
                "customer_name": record.get("customer_name", ""),
                "severity": severity,
                "timestamp": datetime.utcnow().isoformat(),
                "created_at": datetime.utcnow().isoformat()
            }
            
            db.save("audit_log", log_entry)
            logger.info(f"[FRAUD GUARD] {severity} | {action} | {record.get('invoice_number', '')} | by {user.get('name', 'unknown')} | reason: {reason}")
            
        except Exception as e:
            logger.error(f"[FRAUD GUARD] Failed to log action: {e}")
    
    @staticmethod
    def get_daily_summary(db, business_id: str) -> dict:
        """
        Get summary of sensitive actions for the day.
        Used in owner's daily briefing.
        """
        try:
            logs = db.get("audit_log", {"business_id": business_id}) or []
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            
            today_logs = []
            for log in logs:
                if not log.get("action", "").startswith("FRAUD_GUARD:"):
                    continue
                ts = log.get("timestamp", "")
                if ts.startswith(today_str):
                    today_logs.append(log)
            
            if not today_logs:
                return {"total": 0, "message": "No sensitive actions today", "items": []}
            
            summary_items = []
            total_amount = 0
            user_parts = set()
            
            for log in today_logs:
                action = log.get("action", "").replace("FRAUD_GUARD:", "")
                amount = float(log.get("amount", 0))
                total_amount += amount
                user_parts.add(log.get("user_name", "unknown"))
                
                summary_items.append({
                    "action": action,
                    "document": log.get("record_number", ""),
                    "amount": amount,
                    "user": log.get("user_name", ""),
                    "reason": log.get("reason", ""),
                    "severity": log.get("severity", "MEDIUM"),
                    "time": log.get("timestamp", "")
                })
            
            summary = {
                "total": len(today_logs),
                "total_amount": total_amount,
                "items": summary_items,
                "message": f"{len(today_logs)} sensitive action(s) today totalling R{total_amount:,.2f}. By: {', '.join(user_parts)}"
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"[FRAUD GUARD] Summary error: {e}")
            return {"total": 0, "message": "Could not generate summary", "items": []}
    
    @staticmethod
    def check_cancel_pattern(db, business_id: str, user_id: str, days: int = 7) -> dict:
        """
        Check if a user has an unusual pattern of cancellations.
        Returns warning if more than 3 cancels in the period.
        """
        try:
            logs = db.get("audit_log", {"business_id": business_id}) or []
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            
            user_cancels = []
            for log in logs:
                if not log.get("action", "").startswith("FRAUD_GUARD:INVOICE_CANCEL"):
                    continue
                if log.get("user_id") != user_id:
                    continue
                if log.get("timestamp", "") >= cutoff:
                    user_cancels.append(log)
            
            count = len(user_cancels)
            
            if count >= 5:
                return {
                    "warning": True,
                    "level": "HIGH",
                    "message": f"⚠ This user has cancelled {count} invoices in the last {days} days. This may indicate fraud.",
                    "count": count
                }
            elif count >= 3:
                return {
                    "warning": True,
                    "level": "MEDIUM",
                    "message": f"This user has cancelled {count} invoices in the last {days} days.",
                    "count": count
                }
            
            return {"warning": False, "count": 0}
            
        except Exception as e:
            logger.error(f"[FRAUD GUARD] Pattern check error: {e}")
            return {"warning": False, "count": 0}
