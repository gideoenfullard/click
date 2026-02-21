"""
ClickAI Business Groups Module
================================
Cross-business insights and group management.
Uses the existing DB class from clickai.py (raw REST calls to Supabase).

Import in clickai.py:
    try:
        from clickai_business_groups import BusinessGroupManager, register_group_routes
        BUSINESS_GROUPS_LOADED = True
    except ImportError:
        BUSINESS_GROUPS_LOADED = False

Then register routes:
    if BUSINESS_GROUPS_LOADED:
        register_group_routes(app, db, login_required)
"""

import logging
import uuid
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


def _gen_id():
    return str(uuid.uuid4())


def _now():
    return datetime.utcnow().isoformat() + "Z"


class BusinessGroupManager:
    """
    All methods take `db` (the global DB instance from clickai.py) as first argument.
    Uses db.save(), db.get(), db.delete(), db.update() and raw REST for complex queries.
    """

    # ============================================================
    # GROUP CRUD
    # ============================================================

    @staticmethod
    def create_group(db, owner_id, group_name):
        """Create a new business group."""
        try:
            data = {
                'id': _gen_id(),
                'name': group_name,
                'owner_id': owner_id,
                'created_at': _now(),
                'updated_at': _now()
            }
            success, result = db.save('business_groups', data)
            if success:
                logger.info(f"[BIZ-GROUP] Created group '{group_name}' for owner {owner_id}")
                return {'success': True, 'group': result if isinstance(result, dict) else data}
            return {'success': False, 'error': str(result)}
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error creating group: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_my_groups(db, owner_id):
        """Get all groups owned by this user."""
        try:
            groups = db.get('business_groups', {'owner_id': owner_id})
            for group in groups:
                members = db.get('business_group_members', {'group_id': group['id']})
                group['members'] = members or []
                group['business_count'] = len(group['members'])
            return groups
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error fetching groups: {e}")
            return []

    @staticmethod
    def update_group_name(db, group_id, owner_id, new_name):
        """Rename a group (with ownership check)."""
        try:
            groups = db.get('business_groups', {'id': group_id, 'owner_id': owner_id})
            if not groups:
                return {'success': False, 'error': 'Group not found or not owner'}
            success = db.update('business_groups', group_id, {
                'name': new_name,
                'updated_at': _now()
            })
            return {'success': success}
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error updating group: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def delete_group(db, group_id, owner_id):
        """Delete a group. Members auto-cascade in DB."""
        try:
            groups = db.get('business_groups', {'id': group_id, 'owner_id': owner_id})
            if not groups:
                return {'success': False, 'error': 'Group not found or not owner'}
            members = db.get('business_group_members', {'group_id': group_id})
            for m in (members or []):
                db.delete('business_group_members', m['id'])
            success = db.delete('business_groups', group_id)
            if success:
                logger.info(f"[BIZ-GROUP] Deleted group {group_id}")
            return {'success': success}
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error deleting group: {e}")
            return {'success': False, 'error': str(e)}

    # ============================================================
    # GROUP MEMBERS
    # ============================================================

    @staticmethod
    def add_business_to_group(db, group_id, business_id, owner_id):
        """Add a business to a group. User must own both group and business."""
        try:
            groups = db.get('business_groups', {'id': group_id, 'owner_id': owner_id})
            if not groups:
                return {'success': False, 'error': 'Group not found or not owner'}
            businesses = db.get('businesses', {'id': business_id, 'user_id': owner_id})
            if not businesses:
                return {'success': False, 'error': 'Business not found or not owner'}
            existing = db.get('business_group_members', {
                'group_id': group_id,
                'business_id': business_id
            })
            if existing:
                return {'success': False, 'error': 'Business already in this group'}
            data = {
                'id': _gen_id(),
                'group_id': group_id,
                'business_id': business_id,
                'added_at': _now()
            }
            success, result = db.save('business_group_members', data)
            if success:
                biz_name = businesses[0].get('name', business_id)
                logger.info(f"[BIZ-GROUP] Added '{biz_name}' to group {group_id}")
                return {'success': True, 'business_name': biz_name}
            return {'success': False, 'error': 'Failed to add business'}
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error adding business: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def remove_business_from_group(db, group_id, business_id, owner_id):
        """Remove a business from a group."""
        try:
            groups = db.get('business_groups', {'id': group_id, 'owner_id': owner_id})
            if not groups:
                return {'success': False, 'error': 'Group not found or not owner'}
            members = db.get('business_group_members', {
                'group_id': group_id,
                'business_id': business_id
            })
            if not members:
                return {'success': False, 'error': 'Business not in this group'}
            success = db.delete('business_group_members', members[0]['id'])
            return {'success': success}
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error removing business: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_group_businesses(db, group_id, owner_id):
        """Get all businesses in a group with details."""
        try:
            groups = db.get('business_groups', {'id': group_id, 'owner_id': owner_id})
            if not groups:
                return []
            members = db.get('business_group_members', {'group_id': group_id})
            if not members:
                return []
            businesses = []
            for m in members:
                biz = db.get('businesses', {'id': m['business_id']})
                if biz:
                    businesses.append(biz[0])
            return businesses
        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error fetching group businesses: {e}")
            return []

    # ============================================================
    # CROSS-BUSINESS DATA
    # ============================================================

    @staticmethod
    def get_group_overview(db, group_id, owner_id):
        """Get combined stats for all businesses in a group."""
        try:
            businesses = BusinessGroupManager.get_group_businesses(db, group_id, owner_id)
            if not businesses:
                return {'success': False, 'error': 'No businesses in group'}

            overview = {
                'businesses': [],
                'totals': {
                    'revenue_this_month': 0,
                    'total_debtors': 0,
                    'total_creditors': 0,
                    'total_stock_value': 0,
                    'total_bank_balance': 0,
                }
            }

            for biz in businesses:
                biz_id = biz['id']
                biz_stats = BusinessGroupManager._get_business_stats(db, biz_id)
                biz_stats['id'] = biz_id
                biz_stats['name'] = biz.get('name', 'Unknown')
                biz_stats['business_type'] = biz.get('business_type', '')
                biz_stats['industry'] = biz.get('industry', '')
                overview['businesses'].append(biz_stats)
                for key in overview['totals']:
                    overview['totals'][key] += biz_stats.get(key, 0)

            overview['success'] = True
            overview['business_count'] = len(businesses)
            groups = db.get('business_groups', {'id': group_id})
            if groups:
                overview['group_name'] = groups[0].get('name', '')
            return overview

        except Exception as e:
            logger.error(f"[BIZ-GROUP] Error getting group overview: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _get_business_stats(db, business_id):
        """Get summary stats for one business using raw REST queries."""
        stats = {
            'revenue_this_month': 0,
            'total_debtors': 0,
            'total_creditors': 0,
            'total_stock_value': 0,
            'total_bank_balance': 0,
        }

        try:
            first_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')

            # Revenue this month
            try:
                url = (f"{db.url}/rest/v1/invoices?select=total_amount"
                       f"&business_id=eq.{business_id}"
                       f"&status=eq.posted"
                       f"&invoice_date=gte.{first_of_month}"
                       f"&limit=10000")
                resp = requests.get(url, headers=db.headers, timeout=15)
                if resp.status_code == 200:
                    for inv in resp.json():
                        stats['revenue_this_month'] += float(inv.get('total_amount', 0) or 0)
            except Exception:
                pass

            # Debtors
            try:
                url = (f"{db.url}/rest/v1/invoices?select=balance_due"
                       f"&business_id=eq.{business_id}"
                       f"&balance_due=gt.0"
                       f"&limit=10000")
                resp = requests.get(url, headers=db.headers, timeout=15)
                if resp.status_code == 200:
                    for inv in resp.json():
                        stats['total_debtors'] += float(inv.get('balance_due', 0) or 0)
            except Exception:
                pass

            # Creditors
            try:
                url = (f"{db.url}/rest/v1/supplier_invoices?select=balance_due"
                       f"&business_id=eq.{business_id}"
                       f"&balance_due=gt.0"
                       f"&limit=10000")
                resp = requests.get(url, headers=db.headers, timeout=15)
                if resp.status_code == 200:
                    for inv in resp.json():
                        stats['total_creditors'] += float(inv.get('balance_due', 0) or 0)
            except Exception:
                pass

            # Stock Value
            try:
                url = (f"{db.url}/rest/v1/stock_items?select=qty_on_hand,cost_price"
                       f"&business_id=eq.{business_id}"
                       f"&qty_on_hand=gt.0"
                       f"&limit=10000")
                resp = requests.get(url, headers=db.headers, timeout=15)
                if resp.status_code == 200:
                    for s in resp.json():
                        qty = float(s.get('qty_on_hand', 0) or 0)
                        cost = float(s.get('cost_price', 0) or 0)
                        stats['total_stock_value'] += qty * cost
            except Exception:
                pass

            # Bank Balance
            try:
                url = (f"{db.url}/rest/v1/bank_accounts?select=current_balance"
                       f"&business_id=eq.{business_id}"
                       f"&limit=100")
                resp = requests.get(url, headers=db.headers, timeout=15)
                if resp.status_code == 200:
                    for b in resp.json():
                        stats['total_bank_balance'] += float(b.get('current_balance', 0) or 0)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"[BIZ-GROUP] Stats error for {business_id}: {e}")

        return stats

    # ============================================================
    # ZANE GROUP CONTEXT
    # ============================================================

    @staticmethod
    def build_group_context(db, group_id, owner_id):
        """Build context string for Zane when in Group View."""
        overview = BusinessGroupManager.get_group_overview(db, group_id, owner_id)
        if not overview.get('success'):
            return ""

        lines = []
        lines.append("\n\n## GROUP MODE - Cross-Business View")
        group_name = overview.get('group_name', 'My Businesses')
        lines.append(f"Group: {group_name} ({overview['business_count']} businesses)")
        lines.append("Compare performance across businesses. Find cross-business opportunities.\n")

        for biz in overview.get('businesses', []):
            name = biz.get('name', 'Unknown')
            btype = biz.get('business_type', '') or biz.get('industry', '')
            rev = biz.get('revenue_this_month', 0)
            deb = biz.get('total_debtors', 0)
            cred = biz.get('total_creditors', 0)
            stock = biz.get('total_stock_value', 0)
            bank = biz.get('total_bank_balance', 0)

            lines.append(f"**{name}** ({btype})")
            lines.append(f"  Revenue this month: R{rev:,.0f}")
            lines.append(f"  Debtors: R{deb:,.0f} | Creditors: R{cred:,.0f}")
            lines.append(f"  Stock value: R{stock:,.0f} | Bank: R{bank:,.0f}")
            if bank > 0 and cred > 0 and bank < cred * 0.5:
                lines.append(f"  >> ALERT: Cash below 50% of creditors!")
            if stock > 0 and rev > 0 and stock > rev * 6:
                lines.append(f"  >> ALERT: {stock/rev:.1f} months of stock on hand")
            lines.append("")

        t = overview.get('totals', {})
        lines.append(f"**GROUP TOTALS:**")
        lines.append(f"  Combined Revenue: R{t.get('revenue_this_month', 0):,.0f}")
        lines.append(f"  Combined Debtors: R{t.get('total_debtors', 0):,.0f}")
        lines.append(f"  Combined Creditors: R{t.get('total_creditors', 0):,.0f}")
        lines.append(f"  Combined Stock: R{t.get('total_stock_value', 0):,.0f}")
        lines.append(f"  Combined Bank: R{t.get('total_bank_balance', 0):,.0f}")
        lines.append("")
        lines.append("Analyze which businesses perform well vs struggling.")
        lines.append("Find opportunities: shared resources, space, staff, cross-selling, seasonal balancing.")

        return "\n".join(lines)

    # ============================================================
    # COMPARISON INSIGHTS
    # ============================================================

    @staticmethod
    def get_group_comparison(db, group_id, owner_id):
        """Generate comparison insights for Pulse dashboard cards."""
        overview = BusinessGroupManager.get_group_overview(db, group_id, owner_id)
        if not overview.get('success') or not overview.get('businesses'):
            return {'success': False, 'insights': []}

        businesses = overview['businesses']
        insights = []

        # Revenue comparison
        by_rev = sorted(businesses, key=lambda x: x.get('revenue_this_month', 0), reverse=True)
        if len(by_rev) >= 2:
            insights.append({
                'type': 'revenue_comparison', 'icon': '📊',
                'title': 'Revenue Ranking',
                'message': f"{by_rev[0]['name']} leads with R{by_rev[0]['revenue_this_month']:,.0f}. "
                          f"{by_rev[-1]['name']} lowest at R{by_rev[-1]['revenue_this_month']:,.0f}.",
                'severity': 'info'
            })

        # Who carries whom
        total_rev = sum(b.get('revenue_this_month', 0) for b in businesses)
        if total_rev > 0 and len(businesses) >= 2:
            for biz in businesses:
                pct = (biz.get('revenue_this_month', 0) / total_rev) * 100
                if pct > 65:
                    others = [b['name'] for b in businesses if b['id'] != biz['id']]
                    insights.append({
                        'type': 'revenue_dependency', 'icon': '🏋️',
                        'title': 'Revenue Concentration',
                        'message': f"{biz['name']} generates {pct:.0f}% of group revenue. "
                                  f"{', '.join(others)} are heavily dependent.",
                        'severity': 'warning'
                    })

        # Debtor concentration
        total_deb = sum(b.get('total_debtors', 0) for b in businesses)
        if total_deb > 0:
            for biz in businesses:
                d = biz.get('total_debtors', 0)
                if d > 0 and (d / total_deb) * 100 > 60:
                    insights.append({
                        'type': 'debtor_concentration', 'icon': '⚠️',
                        'title': 'Debtor Concentration',
                        'message': f"{biz['name']} has {(d/total_deb)*100:.0f}% of total debtors "
                                  f"(R{d:,.0f} of R{total_deb:,.0f}). Focus collections here.",
                        'severity': 'warning'
                    })

        # Overstock
        for biz in businesses:
            stock = biz.get('total_stock_value', 0)
            rev = biz.get('revenue_this_month', 0)
            if rev > 0 and stock > rev * 6:
                insights.append({
                    'type': 'overstock', 'icon': '📦',
                    'title': f"{biz['name']}: Overstock",
                    'message': f"R{stock:,.0f} stock vs R{rev:,.0f}/month = "
                              f"{stock/rev:.1f} months on hand. Target 2-3 months.",
                    'severity': 'warning'
                })

        # Cash crunch
        for biz in businesses:
            bank = biz.get('total_bank_balance', 0)
            cred = biz.get('total_creditors', 0)
            if cred > 0 and bank < cred * 0.5:
                insights.append({
                    'type': 'cash_warning', 'icon': '🔴',
                    'title': f"{biz['name']}: Cash Crunch",
                    'message': f"Bank R{bank:,.0f} vs creditors R{cred:,.0f}. "
                              f"Cannot cover outstanding supplier payments.",
                    'severity': 'critical'
                })

        return {
            'success': True,
            'insights': insights,
            'business_count': len(businesses),
            'totals': overview['totals']
        }


# ============================================================
# FLASK ROUTE REGISTRATION
# ============================================================

def register_group_routes(app, db, login_required):
    """
    Register all business group API routes.
    Call from clickai.py:
        if BUSINESS_GROUPS_LOADED:
            register_group_routes(app, db, login_required)
    """
    from flask import request, jsonify, session

    mgr = BusinessGroupManager

    @app.route('/api/business-groups', methods=['GET'])
    @login_required
    def api_get_business_groups():
        owner_id = session.get('user_id')
        groups = mgr.get_my_groups(db, owner_id)
        return jsonify({'success': True, 'groups': groups})

    @app.route('/api/business-groups', methods=['POST'])
    @login_required
    def api_create_business_group():
        owner_id = session.get('user_id')
        data = request.get_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Group name required'}), 400
        result = mgr.create_group(db, owner_id, name)
        return jsonify(result)

    @app.route('/api/business-groups/<group_id>', methods=['PUT'])
    @login_required
    def api_update_business_group(group_id):
        owner_id = session.get('user_id')
        data = request.get_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Group name required'}), 400
        result = mgr.update_group_name(db, group_id, owner_id, name)
        return jsonify(result)

    @app.route('/api/business-groups/<group_id>', methods=['DELETE'])
    @login_required
    def api_delete_business_group(group_id):
        owner_id = session.get('user_id')
        result = mgr.delete_group(db, group_id, owner_id)
        return jsonify(result)

    @app.route('/api/business-groups/<group_id>/add', methods=['POST'])
    @login_required
    def api_add_to_group(group_id):
        owner_id = session.get('user_id')
        data = request.get_json()
        business_id = data.get('business_id')
        if not business_id:
            return jsonify({'success': False, 'error': 'business_id required'}), 400
        result = mgr.add_business_to_group(db, group_id, business_id, owner_id)
        return jsonify(result)

    @app.route('/api/business-groups/<group_id>/remove/<business_id>', methods=['DELETE'])
    @login_required
    def api_remove_from_group(group_id, business_id):
        owner_id = session.get('user_id')
        result = mgr.remove_business_from_group(db, group_id, business_id, owner_id)
        return jsonify(result)

    @app.route('/api/business-groups/<group_id>/overview', methods=['GET'])
    @login_required
    def api_group_overview(group_id):
        owner_id = session.get('user_id')
        return jsonify(mgr.get_group_overview(db, group_id, owner_id))

    @app.route('/api/business-groups/<group_id>/comparison', methods=['GET'])
    @login_required
    def api_group_comparison(group_id):
        owner_id = session.get('user_id')
        return jsonify(mgr.get_group_comparison(db, group_id, owner_id))

    @app.route('/api/business-groups/<group_id>/businesses', methods=['GET'])
    @login_required
    def api_group_businesses(group_id):
        owner_id = session.get('user_id')
        businesses = mgr.get_group_businesses(db, group_id, owner_id)
        return jsonify({'success': True, 'businesses': businesses})

    @app.route('/api/business-groups/my-businesses', methods=['GET'])
    @login_required
    def api_my_businesses_for_groups():
        """List all businesses owned by current user (for the add-to-group dropdown)."""
        owner_id = session.get('user_id')
        try:
            businesses = db.get('businesses', {'user_id': owner_id})
            result = [{'id': b.get('id'), 'name': b.get('name', 'Unknown')} for b in (businesses or [])]
            return jsonify({'success': True, 'businesses': result})
        except Exception as e:
            return jsonify({'success': True, 'businesses': []})

    logger.info("[BIZ-GROUP] Routes registered successfully")
