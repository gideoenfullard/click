"""
ClickAI GL Analysis Module
============================
Upload a client's General Ledger (Sage AccountTransactionsReport CSV, Xero GL, Excel)
and get instant analysis: Trial Balance check, per-account summaries, anomaly detection,
duplicate detection, and Zane AI insights.

Lives under Smart Reports at /reports/gl-analysis
DB: No storage needed — all in-memory analysis

Formats supported:
- Sage Pastel: AccountTransactionsReport.csv
- Xero: General Ledger CSV
- Generic CSV/Excel with Account, Date, Debit, Credit columns
"""

import csv
import io
import json
import logging
import re
import traceback
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("clickai")


# ═══════════════════════════════════════════════════════════════════════════════
# SAGE GL PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_num(val):
    """Parse a number string, handling blanks, commas, R prefix."""
    if not val or not str(val).strip():
        return 0.0
    s = str(val).replace("R", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _parse_date(val):
    """Parse date from Sage format dd/mm/yyyy or yyyy-mm-dd."""
    if not val or not str(val).strip():
        return None
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_sage_gl(file_content, filename=""):
    """
    Parse a Sage Pastel AccountTransactionsReport CSV.

    Structure:
      - Account header row: col0 = account name, col1 = "Opening Balance as at: ..."
      - Transaction rows: col0 empty, col1 = date, col2 = party, col3 = ref, col4 = type, col5 = desc, col6 = debit, col7 = credit, col8 = balance
      - Closing row: col0 = account name, col1 = "Closing Balance as at: ..."
      - Movement row: col1 = "Movement for the period"

    Returns dict with accounts list and summary stats.
    """
    accounts = {}
    current_account = None
    order = []
    skipped = {"sep=,", "sep=", "Account Description"}

    reader = csv.reader(io.StringIO(file_content))
    for row in reader:
        if not row or all(c.strip() == "" for c in row):
            continue

        col0 = row[0].strip() if len(row) > 0 else ""
        col1 = row[1].strip() if len(row) > 1 else ""

        # Skip CSV header / separator
        if col0 in skipped or "Account Description" in col0:
            continue

        # Account header with opening balance
        if col0 and "Opening Balance" in col1:
            current_account = col0
            ob_dr = _parse_num(row[6] if len(row) > 6 else "0")
            ob_cr = _parse_num(row[7] if len(row) > 7 else "0")
            if current_account not in accounts:
                accounts[current_account] = {
                    "name": current_account,
                    "opening_debit": ob_dr,
                    "opening_credit": ob_cr,
                    "closing_debit": 0,
                    "closing_credit": 0,
                    "transactions": [],
                }
                order.append(current_account)
            continue

        # Special: Retained Income opening balance (different format)
        if col0 == "" and col1 == "" and len(row) > 4:
            ref = row[3].strip() if len(row) > 3 else ""
            txn_type = row[4].strip() if len(row) > 4 else ""
            if ref == "Retained Income" and txn_type == "Opening Balance":
                current_account = "Retained Income"
                ob_cr = _parse_num(row[7] if len(row) > 7 else "0")
                if current_account not in accounts:
                    accounts[current_account] = {
                        "name": current_account,
                        "opening_debit": 0,
                        "opening_credit": ob_cr,
                        "closing_debit": 0,
                        "closing_credit": ob_cr,
                        "transactions": [],
                    }
                    order.append(current_account)
                continue

        # Account section header (no opening balance — just the name)
        if col0 and not col1:
            if col0 not in skipped:
                current_account = col0
                if current_account not in accounts:
                    accounts[current_account] = {
                        "name": current_account,
                        "opening_debit": 0,
                        "opening_credit": 0,
                        "closing_debit": 0,
                        "closing_credit": 0,
                        "transactions": [],
                    }
                    order.append(current_account)
            continue

        # Closing balance row
        if col0 and "Closing Balance" in col1:
            if col0 in accounts:
                accounts[col0]["closing_debit"] = _parse_num(row[6] if len(row) > 6 else "0")
                accounts[col0]["closing_credit"] = _parse_num(row[7] if len(row) > 7 else "0")
            current_account = None
            continue

        # Movement row — skip
        if "Movement for" in col1:
            continue

        # Transaction row — col0 is empty, col1 has a date
        if not col0 and col1 and current_account and current_account in accounts:
            dt = _parse_date(col1)
            if dt:
                party = row[2].strip() if len(row) > 2 else ""
                ref = row[3].strip() if len(row) > 3 else ""
                txn_type = row[4].strip() if len(row) > 4 else ""
                desc = row[5].strip() if len(row) > 5 else ""
                debit = _parse_num(row[6] if len(row) > 6 else "0")
                credit = _parse_num(row[7] if len(row) > 7 else "0")

                accounts[current_account]["transactions"].append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "date_display": dt.strftime("%d %b %Y"),
                    "party": party,
                    "ref": ref,
                    "type": txn_type,
                    "desc": desc,
                    "debit": debit,
                    "credit": credit,
                })

    # Build ordered list, skip empty/invalid
    result = []
    for name in order:
        acc = accounts.get(name)
        if not acc:
            continue
        # Calculate movement
        total_dr = sum(t["debit"] for t in acc["transactions"])
        total_cr = sum(t["credit"] for t in acc["transactions"])
        acc["total_debit"] = round(total_dr, 2)
        acc["total_credit"] = round(total_cr, 2)
        acc["movement"] = round(total_dr - total_cr, 2)
        acc["transaction_count"] = len(acc["transactions"])

        # Closing balance (net) for TB
        acc["closing_net_debit"] = round(acc["closing_debit"], 2)
        acc["closing_net_credit"] = round(acc["closing_credit"], 2)

        result.append(acc)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# GENERIC CSV PARSER (fallback)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_generic_gl(file_content, filename=""):
    """
    Try to parse a generic GL CSV/TSV. Look for columns:
    Account, Date, Description, Debit, Credit
    """
    # Try to detect delimiter
    first_lines = file_content[:2000]
    if "\t" in first_lines and first_lines.count("\t") > first_lines.count(","):
        delimiter = "\t"
    else:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)
    if not reader.fieldnames:
        return []

    # Map column names (case-insensitive)
    field_map = {}
    for f in reader.fieldnames:
        fl = f.strip().lower()
        if "account" in fl and "desc" in fl:
            field_map["account"] = f
        elif "account" in fl and "name" in fl:
            field_map["account"] = f
        elif "account" in fl and "account" not in field_map:
            field_map["account"] = f
        elif "date" in fl and "date" not in field_map:
            field_map["date"] = f
        elif "debit" in fl and "debit" not in field_map:
            field_map["debit"] = f
        elif "credit" in fl and "credit" not in field_map:
            field_map["credit"] = f
        elif "desc" in fl and "desc" not in field_map:
            field_map["desc"] = f
        elif "ref" in fl and "ref" not in field_map:
            field_map["ref"] = f

    if "account" not in field_map or "debit" not in field_map:
        return []

    # Group by account
    grouped = defaultdict(list)
    for row in reader:
        acc_name = (row.get(field_map.get("account", ""), "") or "").strip()
        if not acc_name:
            continue
        dt = _parse_date(row.get(field_map.get("date", ""), ""))
        grouped[acc_name].append({
            "date": dt.strftime("%Y-%m-%d") if dt else "",
            "date_display": dt.strftime("%d %b %Y") if dt else "",
            "party": "",
            "ref": (row.get(field_map.get("ref", ""), "") or "").strip(),
            "type": "",
            "desc": (row.get(field_map.get("desc", ""), "") or "").strip(),
            "debit": _parse_num(row.get(field_map.get("debit", ""), "0")),
            "credit": _parse_num(row.get(field_map.get("credit", ""), "0")),
        })

    result = []
    for name, txns in grouped.items():
        total_dr = sum(t["debit"] for t in txns)
        total_cr = sum(t["credit"] for t in txns)
        result.append({
            "name": name,
            "opening_debit": 0, "opening_credit": 0,
            "closing_debit": total_dr, "closing_credit": total_cr,
            "closing_net_debit": round(total_dr, 2),
            "closing_net_credit": round(total_cr, 2),
            "total_debit": round(total_dr, 2),
            "total_credit": round(total_cr, 2),
            "movement": round(total_dr - total_cr, 2),
            "transaction_count": len(txns),
            "transactions": txns,
        })

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_account(name):
    """Classify account into category for grouping.
    
    Order matters: more specific patterns must check BEFORE generic ones.
    E.g. 'Income Tax Payable' must match Liabilities before 'income' matches Income.
    'Nedbank Current Account' must match Assets before 'bank charge' matches Expenses.
    'Accumulated Depreciation' must match Assets (contra) before 'depreciation' matches Expenses.
    """
    n = name.lower()

    # ── 1. Accumulated depreciation (contra-asset) — before Expenses catches "depreciation"
    if "acc" in n and "depr" in n:
        return "Assets"

    # ── 2. Liabilities — before Income catches "income tax payable" or "retained income"
    if any(k in n for k in ("trade payable", "vat payable", "income tax payable",
                             "emp201 payable", "sars emp", "creditor",
                             "paye payable", "uif payable", "sdl payable", "accrual")):
        return "Liabilities"

    # ── 3. Equity — before Income catches "retained income"
    if any(k in n for k in ("capital", "retained income", "retained earning",
                             "drawing", "shareholder loan", "member",
                             "balance control", "owner", "equity")):
        return "Equity"

    # ── 4. Assets — before Expenses catches "bank charge", "office expense", etc.
    #    Bank accounts, receivables, fixed assets, loans given, deposits
    if any(k in n for k in ("current account", "savings account", "savings",
                             "petty cash", "cash on hand", "cash float",
                             "receivable", "debtor",
                             "stock on hand", "inventory", "raw material",
                             "equipment @ cost", "furniture @ cost", "vehicle @ cost",
                             "office equipment @ cost",
                             "equipment loan",
                             "deposit paid", "deposits paid",
                             "loan:", "staff loan")):
        return "Assets"
    # Bank accounts by name (Nedbank, FNB, ABSA, etc.) — but NOT "bank charge"
    if any(k in n for k in ("nedbank", "fnb", "absa", "standard bank", "capitec",
                             "investec", "tymebank")) and "charge" not in n:
        return "Assets"

    # ── 5. Income
    if any(k in n for k in ("sales", "revenue", "interest received",
                             "discount received", "other income")):
        return "Income"

    # ── 6. Cost of Sales
    if any(k in n for k in ("purchase", "cost of sale", "cogs", "carriage",
                             "outsourced", "packaging", "freight")):
        return "Cost of Sales"

    # ── 7. Expenses (catch-all for operating costs)
    if any(k in n for k in ("expense", "fee", "charge", "rent", "salary", "wage",
                             "telephone", "internet", "insurance", "fuel",
                             "repair", "maintenance", "depreciation", "advertising",
                             "entertainment", "stationery", "printing",
                             "transport", "delivery", "training", "welfare",
                             "licence", "license", "software", "consulting",
                             "consumable", "workmens", "small tool", "royalt",
                             "office expense", "office cost", "lease",
                             "bank charge", "rounding", "it expense", "accounting")):
        return "Expenses"

    return "Other"


def run_gl_analysis(accounts):
    """
    Run comprehensive analysis on parsed GL accounts.
    Returns a dict with all analysis results.
    """
    if not accounts:
        return {"error": "No accounts to analyse"}

    total_txns = sum(a["transaction_count"] for a in accounts)

    # ── 1. Trial Balance Check ──
    total_closing_dr = sum(a["closing_net_debit"] for a in accounts)
    total_closing_cr = sum(a["closing_net_credit"] for a in accounts)
    tb_difference = round(total_closing_dr - total_closing_cr, 2)
    tb_balanced = abs(tb_difference) < 0.02

    # ── 2. Per-category summary ──
    categories = defaultdict(lambda: {"debit": 0, "credit": 0, "count": 0, "accounts": []})
    for a in accounts:
        cat = _classify_account(a["name"])
        categories[cat]["debit"] += a["total_debit"]
        categories[cat]["credit"] += a["total_credit"]
        categories[cat]["count"] += 1
        net = a["closing_net_debit"] - a["closing_net_credit"]
        categories[cat]["accounts"].append({
            "name": a["name"],
            "closing_debit": a["closing_net_debit"],
            "closing_credit": a["closing_net_credit"],
            "net": round(net, 2),
            "txn_count": a["transaction_count"],
        })

    # Round category totals
    for cat in categories:
        categories[cat]["debit"] = round(categories[cat]["debit"], 2)
        categories[cat]["credit"] = round(categories[cat]["credit"], 2)

    # ── 3. Key financial figures ──
    # Use NET figures: Income = credits - debits (credit notes reduce income)
    # COS = debits - credits, Expenses = debits - credits
    income = categories.get("Income", {})
    cos = categories.get("Cost of Sales", {})
    expenses = categories.get("Expenses", {})

    total_income = income.get("credit", 0) - income.get("debit", 0)  # Net of credit notes
    total_cos = cos.get("debit", 0) - cos.get("credit", 0)  # Net of purchase returns
    gross_profit = round(total_income - total_cos, 2)
    gp_margin = round((gross_profit / total_income * 100), 1) if total_income > 0 else 0
    total_expenses = expenses.get("debit", 0) - expenses.get("credit", 0)  # Net of refunds
    net_profit = round(gross_profit - total_expenses, 2)
    np_margin = round((net_profit / total_income * 100), 1) if total_income > 0 else 0

    # ── 4. Date range ──
    all_dates = []
    for a in accounts:
        for t in a["transactions"]:
            d = _parse_date(t["date"])
            if d:
                all_dates.append(d)
    date_from = min(all_dates).strftime("%d %b %Y") if all_dates else "?"
    date_to = max(all_dates).strftime("%d %b %Y") if all_dates else "?"
    months_span = 0
    if all_dates:
        d1, d2 = min(all_dates), max(all_dates)
        months_span = max(1, (d2.year - d1.year) * 12 + d2.month - d1.month + 1)

    # ── 5. Monthly revenue trend ──
    monthly_revenue = defaultdict(float)
    for a in accounts:
        if _classify_account(a["name"]) == "Income":
            for t in a["transactions"]:
                d = _parse_date(t["date"])
                if d:
                    key = d.strftime("%Y-%m")
                    monthly_revenue[key] += t["credit"]

    revenue_trend = [{"month": k, "amount": round(v, 2)} for k, v in sorted(monthly_revenue.items())]

    # ── 6. Top customers (from income accounts) ──
    customer_totals = defaultdict(float)
    for a in accounts:
        if _classify_account(a["name"]) == "Income":
            for t in a["transactions"]:
                if t["party"]:
                    customer_totals[t["party"]] += t["credit"]
    top_customers = sorted(
        [{"name": k, "total": round(v, 2)} for k, v in customer_totals.items()],
        key=lambda x: x["total"], reverse=True
    )[:10]

    # ── 7. Top suppliers (from COS/expense accounts + Trade Payables) ──
    supplier_totals = defaultdict(float)
    for a in accounts:
        cat = _classify_account(a["name"])
        if cat in ("Cost of Sales", "Expenses"):
            for t in a["transactions"]:
                if t["party"]:
                    supplier_totals[t["party"]] += t["debit"]
        # Also include Trade Payables credit side (supplier invoices booked)
        if "trade payable" in a["name"].lower():
            for t in a["transactions"]:
                if t["party"] and t["credit"] > 0:
                    supplier_totals[t["party"]] += t["credit"]
    # Filter out bank account names from supplier list
    _bank_keywords = ("nedbank", "fnb", "absa", "standard bank", "capitec",
                       "investec", "tymebank", "current account", "savings")
    top_suppliers = sorted(
        [{"name": k, "total": round(v, 2)} for k, v in supplier_totals.items()
         if not any(bk in k.lower() for bk in _bank_keywords)],
        key=lambda x: x["total"], reverse=True
    )[:10]

    # ── 8. Anomalies / Red flags ──
    anomalies = []

    # 8a. Large single transactions (> 20% of account total)
    for a in accounts:
        acc_total = a["total_debit"] + a["total_credit"]
        if acc_total < 100:
            continue
        for t in a["transactions"]:
            txn_val = max(t["debit"], t["credit"])
            if txn_val > acc_total * 0.20 and txn_val > 5000:
                anomalies.append({
                    "type": "large_transaction",
                    "severity": "warning",
                    "account": a["name"],
                    "amount": txn_val,
                    "date": t["date_display"],
                    "desc": t["desc"] or t["party"],
                    "detail": f"R{txn_val:,.2f} is {txn_val/acc_total*100:.0f}% of {a['name']} total"
                })

    # 8b. Possible duplicates (same account, same amount, same ref, close dates)
    for a in accounts:
        txns = a["transactions"]
        seen = {}
        for t in txns:
            key = (round(t["debit"] + t["credit"], 2), t["ref"] or t["desc"])
            if key[0] < 1:
                continue
            if key in seen:
                prev = seen[key]
                anomalies.append({
                    "type": "possible_duplicate",
                    "severity": "alert",
                    "account": a["name"],
                    "amount": key[0],
                    "date": t["date_display"],
                    "desc": f"Ref: {t['ref'] or t['desc']}",
                    "detail": f"Same amount R{key[0]:,.2f} & ref in {a['name']} on {prev['date_display']} and {t['date_display']}"
                })
            else:
                seen[key] = t

    # 8c. Rounding / suspense balances
    for a in accounts:
        n = a["name"].lower()
        if any(k in n for k in ("rounding", "suspense", "balance control", "clearing")):
            net = abs(a["closing_net_debit"] - a["closing_net_credit"])
            if net > 0.01:
                anomalies.append({
                    "type": "suspense_balance",
                    "severity": "alert",
                    "account": a["name"],
                    "amount": net,
                    "date": "",
                    "desc": f"Closing balance: R{net:,.2f}",
                    "detail": f"{a['name']} should normally be zero but has R{net:,.2f} balance"
                })

    # 8d. Accounts with no transactions
    empty_accounts = [a["name"] for a in accounts
                      if a["transaction_count"] == 0
                      and abs(a["closing_net_debit"] - a["closing_net_credit"]) < 0.01]

    # Sort anomalies by severity then amount
    sev_order = {"alert": 0, "warning": 1, "info": 2}
    anomalies.sort(key=lambda x: (sev_order.get(x["severity"], 9), -x["amount"]))

    # ── 9. Per-account summary table ──
    account_table = []
    for a in accounts:
        account_table.append({
            "name": a["name"],
            "category": _classify_account(a["name"]),
            "opening_dr": a["opening_debit"],
            "opening_cr": a["opening_credit"],
            "period_dr": a["total_debit"],
            "period_cr": a["total_credit"],
            "closing_dr": a["closing_net_debit"],
            "closing_cr": a["closing_net_credit"],
            "txn_count": a["transaction_count"],
        })

    return {
        "summary": {
            "account_count": len(accounts),
            "transaction_count": total_txns,
            "date_from": date_from,
            "date_to": date_to,
            "months": months_span,
            "tb_total_debit": round(total_closing_dr, 2),
            "tb_total_credit": round(total_closing_cr, 2),
            "tb_difference": tb_difference,
            "tb_balanced": tb_balanced,
            "total_income": round(total_income, 2),
            "total_cos": round(total_cos, 2),
            "gross_profit": gross_profit,
            "gp_margin": gp_margin,
            "total_expenses": round(total_expenses, 2),
            "net_profit": net_profit,
            "np_margin": np_margin,
        },
        "categories": {k: v for k, v in categories.items()},
        "revenue_trend": revenue_trend,
        "top_customers": top_customers,
        "top_suppliers": top_suppliers,
        "anomalies": anomalies[:30],  # Cap at 30
        "empty_accounts": empty_accounts,
        "account_table": account_table,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTE REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def register_gl_analysis_routes(app, db, login_required, Auth, render_page,
                                 now, today, _anthropic_client=None):
    """Register GL Analysis routes on the Flask app."""

    # ───────────────────────────────────────────────────────────
    # PAGE: /reports/gl-analysis
    # ───────────────────────────────────────────────────────────
    @app.route("/reports/gl-analysis")
    @login_required
    def gl_analysis_page():
        """GL Analysis — Upload & Analyze a General Ledger"""
        user = Auth.get_current_user()

        content = '''
        <div class="card" style="background:linear-gradient(135deg, rgba(16,185,129,0.15), rgba(99,102,241,0.1));border:1px solid rgba(16,185,129,0.3);margin-bottom:20px;">
            <div style="display:flex;align-items:center;gap:15px;">
                <span style="font-size:40px;">🔬</span>
                <div>
                    <h2 style="margin:0;">GL Analysis</h2>
                    <p style="color:var(--text-muted);margin:5px 0 0 0;">Upload a General Ledger from Sage, Xero or Excel — get instant financial analysis with AI insights</p>
                </div>
            </div>
        </div>

        <!-- UPLOAD ZONE -->
        <div class="card" id="uploadCard">
            <div id="uploadZone" style="border:2px dashed var(--border, #444);border-radius:10px;padding:40px 20px;text-align:center;cursor:pointer;transition:all 0.3s;"
                 onclick="document.getElementById('glFileInput').click()"
                 ondragover="event.preventDefault();this.style.borderColor='#6366f1';this.style.background='rgba(99,102,241,0.08)'"
                 ondragleave="this.style.borderColor='';this.style.background=''"
                 ondrop="event.preventDefault();this.style.borderColor='';this.style.background='';handleFileDrop(event)">
                <div style="font-size:2.5rem;margin-bottom:10px;">📄</div>
                <div style="font-size:1rem;font-weight:600;margin-bottom:6px;">Drop GL file here or click to upload</div>
                <div style="font-size:0.85rem;color:var(--text-muted);">Sage AccountTransactionsReport.csv &bull; Xero GL Export &bull; Excel (.xlsx)</div>
                <input type="file" id="glFileInput" accept=".csv,.xlsx,.xls,.tsv" style="display:none" onchange="handleFileSelect(this)">
            </div>
            <div id="uploadStatus" style="display:none;padding:16px 0;text-align:center;"></div>
        </div>

        <!-- RESULTS (hidden until upload) -->
        <div id="glResults" style="display:none;">

            <!-- ACTION BAR -->
            <div class="card" style="margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
                <h3 id="glReportTitle" style="margin:0;">GL Analysis Report</h3>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    <button class="btn btn-secondary" onclick="downloadFullReport()" style="font-size:12px;padding:6px 14px;">⬇️ Download</button>
                    <button class="btn btn-secondary" onclick="showGLEmailModal()" style="font-size:12px;padding:6px 14px;">📧 Email</button>
                    <button class="btn btn-secondary" onclick="window.print();" style="font-size:12px;padding:6px 14px;">🖨️ Print</button>
                </div>
            </div>

            <!-- SUMMARY CARDS -->
            <div class="stats-grid" id="summaryCards" style="margin-bottom:20px;"></div>

            <!-- TB CHECK -->
            <div class="card" id="tbCheckCard" style="margin-bottom:20px;"></div>

            <!-- P&L SNAPSHOT -->
            <div class="card" id="pnlCard" style="margin-bottom:20px;"></div>

            <!-- REVENUE TREND CHART -->
            <div class="card" id="trendCard" style="margin-bottom:20px;"></div>

            <!-- TOP CUSTOMERS & SUPPLIERS -->
            <div class="stats-grid" style="margin-bottom:20px;">
                <div class="card" id="customersCard"></div>
                <div class="card" id="suppliersCard"></div>
            </div>

            <!-- ANOMALIES / RED FLAGS -->
            <div class="card" id="anomalyCard" style="margin-bottom:20px;"></div>

            <!-- ACCOUNT TABLE -->
            <div class="card" id="accountTableCard" style="margin-bottom:20px;overflow-x:auto;"></div>

            <!-- ZANE AI INSIGHTS -->
            <div class="card" id="aiCard" style="margin-bottom:20px;background:linear-gradient(135deg, rgba(99,102,241,0.08), rgba(139,92,246,0.05));border:1px solid rgba(99,102,241,0.2);"></div>

        </div>

        <!-- EMAIL MODAL -->
        <div id="glEmailModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center;">
            <div style="background:var(--card, #1a1a2e);border:1px solid var(--border, #333);border-radius:12px;padding:25px;width:90%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                    <h3 style="margin:0;color:var(--primary, #6366f1);">Email GL Report</h3>
                    <button onclick="closeGLEmailModal()" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">✕</button>
                </div>
                <input type="email" id="glEmailTo" class="form-input" placeholder="email@example.com" style="width:100%;margin-bottom:10px;">
                <input type="text" id="glEmailSubject" class="form-input" placeholder="Subject (optional)" style="width:100%;margin-bottom:15px;">
                <div style="display:flex;gap:10px;justify-content:flex-end;">
                    <button class="btn btn-secondary" onclick="closeGLEmailModal()">Cancel</button>
                    <button class="btn btn-primary" id="glSendEmailBtn" onclick="sendGLReportEmail()">Send</button>
                </div>
                <p id="glEmailStatus" style="margin:10px 0 0 0;font-size:12px;display:none;"></p>
            </div>
        </div>

        <script>
        let glAnalysisData = null;

        function handleFileDrop(e) {
            const file = e.dataTransfer.files[0];
            if (file) uploadGL(file);
        }

        function handleFileSelect(input) {
            const file = input.files[0];
            if (file) uploadGL(file);
            input.value = '';
        }

        async function uploadGL(file) {
            const status = document.getElementById('uploadStatus');
            status.style.display = 'block';
            status.innerHTML = '<span style="color:#818cf8;">⏳ Parsing ' + file.name + ' (' + (file.size/1024).toFixed(0) + ' KB)...</span>';
            document.getElementById('glResults').style.display = 'none';

            const formData = new FormData();
            formData.append('file', file);

            try {
                const resp = await fetch('/api/reports/gl/upload', { method: 'POST', body: formData });
                const data = await resp.json();

                if (!data.success) {
                    status.innerHTML = '<span style="color:#ef4444;">❌ ' + (data.error || 'Upload failed') + '</span>';
                    return;
                }

                glAnalysisData = data;
                status.innerHTML = '<span style="color:#10b981;">✅ ' + file.name + ' — ' + data.summary.account_count + ' accounts, ' + data.summary.transaction_count + ' transactions (' + data.summary.date_from + ' to ' + data.summary.date_to + ')</span>';

                renderResults(data);
                document.getElementById('glResults').style.display = 'block';
                document.getElementById('glResults').scrollIntoView({behavior:'smooth'});

                // Fire async AI analysis
                fetchAIInsights(data);

            } catch(e) {
                status.innerHTML = '<span style="color:#ef4444;">❌ Error: ' + e.message + '</span>';
            }
        }

        function R(v) { return 'R' + Number(v||0).toLocaleString('en-ZA', {minimumFractionDigits:2, maximumFractionDigits:2}); }

        function renderResults(data) {
            const s = data.summary;

            // Summary cards
            document.getElementById('summaryCards').innerHTML = `
                <div class="card" style="text-align:center;">
                    <div style="color:var(--text-muted);font-size:12px;text-transform:uppercase;letter-spacing:1px;">Accounts</div>
                    <div style="font-size:1.8rem;font-weight:700;">${s.account_count}</div>
                </div>
                <div class="card" style="text-align:center;">
                    <div style="color:var(--text-muted);font-size:12px;text-transform:uppercase;letter-spacing:1px;">Transactions</div>
                    <div style="font-size:1.8rem;font-weight:700;">${s.transaction_count.toLocaleString()}</div>
                </div>
                <div class="card" style="text-align:center;">
                    <div style="color:var(--text-muted);font-size:12px;text-transform:uppercase;letter-spacing:1px;">Period</div>
                    <div style="font-size:1.2rem;font-weight:700;">${s.months} months</div>
                    <div style="font-size:11px;color:var(--text-muted);">${s.date_from} — ${s.date_to}</div>
                </div>
                <div class="card" style="text-align:center;">
                    <div style="color:var(--text-muted);font-size:12px;text-transform:uppercase;letter-spacing:1px;">TB Status</div>
                    <div style="font-size:1.5rem;font-weight:700;color:${s.tb_balanced ? '#10b981' : '#ef4444'};">${s.tb_balanced ? '✓ Balanced' : '✗ Unbalanced'}</div>
                    ${!s.tb_balanced ? '<div style="font-size:11px;color:#ef4444;">Diff: ' + R(s.tb_difference) + '</div>' : ''}
                </div>
            `;

            // TB Check
            document.getElementById('tbCheckCard').innerHTML = `
                <h3 style="margin:0 0 12px 0;">Trial Balance Check</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:400px;">
                    <div style="padding:12px;background:rgba(16,185,129,0.1);border-radius:8px;text-align:center;">
                        <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Total Debits</div>
                        <div style="font-size:1.2rem;font-weight:700;color:#10b981;">${R(s.tb_total_debit)}</div>
                    </div>
                    <div style="padding:12px;background:rgba(239,68,68,0.1);border-radius:8px;text-align:center;">
                        <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Total Credits</div>
                        <div style="font-size:1.2rem;font-weight:700;color:#ef4444;">${R(s.tb_total_credit)}</div>
                    </div>
                </div>
                ${!s.tb_balanced ? '<div style="margin-top:12px;padding:10px 14px;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:6px;color:#ef4444;font-weight:600;">⚠️ Trial Balance is off by ' + R(Math.abs(s.tb_difference)) + '</div>' : '<div style="margin-top:12px;padding:10px 14px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.3);border-radius:6px;color:#10b981;font-weight:600;">✅ Trial Balance is in balance</div>'}
            `;

            // P&L Snapshot
            document.getElementById('pnlCard').innerHTML = `
                <h3 style="margin:0 0 12px 0;">Profit & Loss Snapshot</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;">
                    <div style="padding:12px;border-radius:8px;background:rgba(16,185,129,0.08);">
                        <div style="font-size:11px;color:var(--text-muted);">Revenue</div>
                        <div style="font-size:1.1rem;font-weight:700;color:#10b981;">${R(s.total_income)}</div>
                    </div>
                    <div style="padding:12px;border-radius:8px;background:rgba(239,68,68,0.08);">
                        <div style="font-size:11px;color:var(--text-muted);">Cost of Sales</div>
                        <div style="font-size:1.1rem;font-weight:700;color:#ef4444;">${R(s.total_cos)}</div>
                    </div>
                    <div style="padding:12px;border-radius:8px;background:rgba(99,102,241,0.08);">
                        <div style="font-size:11px;color:var(--text-muted);">Gross Profit</div>
                        <div style="font-size:1.1rem;font-weight:700;">${R(s.gross_profit)}</div>
                        <div style="font-size:11px;color:var(--text-muted);">Margin: ${s.gp_margin}%</div>
                    </div>
                    <div style="padding:12px;border-radius:8px;background:rgba(245,158,11,0.08);">
                        <div style="font-size:11px;color:var(--text-muted);">Expenses</div>
                        <div style="font-size:1.1rem;font-weight:700;color:#f59e0b;">${R(s.total_expenses)}</div>
                    </div>
                    <div style="padding:12px;border-radius:8px;background:${s.net_profit >= 0 ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'};">
                        <div style="font-size:11px;color:var(--text-muted);">Net Profit</div>
                        <div style="font-size:1.2rem;font-weight:700;color:${s.net_profit >= 0 ? '#10b981' : '#ef4444'};">${R(s.net_profit)}</div>
                        <div style="font-size:11px;color:var(--text-muted);">Margin: ${s.np_margin}%</div>
                    </div>
                </div>
            `;

            // Revenue Trend
            const trend = data.revenue_trend || [];
            if (trend.length > 1) {
                const maxAmt = Math.max(...trend.map(t => t.amount));
                const bars = trend.map(t => {
                    const pct = maxAmt > 0 ? (t.amount / maxAmt * 100) : 0;
                    const label = t.month.substring(5);
                    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                    const mName = months[parseInt(label)-1] || label;
                    return `<div style="text-align:center;flex:1;min-width:40px;">
                        <div style="height:${Math.max(pct, 3)}px;background:linear-gradient(to top,#6366f1,#818cf8);border-radius:4px 4px 0 0;min-height:3px;transition:height 0.5s;"></div>
                        <div style="font-size:10px;color:var(--text-muted);margin-top:4px;">${mName}</div>
                        <div style="font-size:10px;color:var(--text-muted);">${(t.amount/1000).toFixed(0)}k</div>
                    </div>`;
                }).join('');
                document.getElementById('trendCard').innerHTML = `
                    <h3 style="margin:0 0 12px 0;">Monthly Revenue</h3>
                    <div style="display:flex;align-items:flex-end;gap:6px;height:120px;padding:0 4px;">${bars}</div>
                `;
            } else {
                document.getElementById('trendCard').style.display = 'none';
            }

            // Top Customers
            const tc = data.top_customers || [];
            document.getElementById('customersCard').innerHTML = `
                <h3 style="margin:0 0 10px 0;">Top Customers</h3>
                ${tc.length === 0 ? '<p style="color:var(--text-muted);">No customer data</p>' :
                tc.map((c,i) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border,rgba(255,255,255,0.06));font-size:13px;">
                    <span>${i+1}. ${c.name}</span><span style="font-weight:600;">${R(c.total)}</span>
                </div>`).join('')}
            `;

            // Top Suppliers
            const ts = data.top_suppliers || [];
            document.getElementById('suppliersCard').innerHTML = `
                <h3 style="margin:0 0 10px 0;">Top Suppliers</h3>
                ${ts.length === 0 ? '<p style="color:var(--text-muted);">No supplier data</p>' :
                ts.map((c,i) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border,rgba(255,255,255,0.06));font-size:13px;">
                    <span>${i+1}. ${c.name}</span><span style="font-weight:600;">${R(c.total)}</span>
                </div>`).join('')}
            `;

            // Anomalies
            const anomalies = data.anomalies || [];
            const emptyAccs = data.empty_accounts || [];
            let anomalyHtml = '<h3 style="margin:0 0 12px 0;">⚠️ Red Flags & Anomalies</h3>';
            if (anomalies.length === 0 && emptyAccs.length === 0) {
                anomalyHtml += '<p style="color:#10b981;font-weight:600;">✅ No anomalies detected — books look clean.</p>';
            } else {
                anomalies.forEach(a => {
                    const col = a.severity === 'alert' ? '#ef4444' : '#f59e0b';
                    const icon = a.severity === 'alert' ? '🔴' : '🟡';
                    const typeLabel = a.type === 'possible_duplicate' ? 'Possible Duplicate' : a.type === 'large_transaction' ? 'Large Transaction' : a.type === 'suspense_balance' ? 'Suspense Balance' : a.type;
                    anomalyHtml += `<div style="padding:10px 14px;margin-bottom:8px;border-left:3px solid ${col};background:rgba(0,0,0,0.15);border-radius:0 6px 6px 0;">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-weight:600;">${icon} ${typeLabel}</span>
                            <span style="font-weight:700;color:${col};">${R(a.amount)}</span>
                        </div>
                        <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">${a.detail}</div>
                    </div>`;
                });
                if (emptyAccs.length > 0) {
                    anomalyHtml += `<div style="padding:10px 14px;margin-top:8px;background:rgba(0,0,0,0.1);border-radius:6px;">
                        <span style="color:var(--text-muted);font-size:13px;">ℹ️ ${emptyAccs.length} account(s) with no transactions: ${emptyAccs.join(', ')}</span>
                    </div>`;
                }
            }
            document.getElementById('anomalyCard').innerHTML = anomalyHtml;

            // Account Table
            const accs = data.account_table || [];
            let tableHtml = `<h3 style="margin:0 0 12px 0;">Account Summary</h3>
                <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">
                    <input type="text" id="accFilter" class="form-input" placeholder="Filter accounts..." style="max-width:300px;padding:6px 10px;font-size:13px;" oninput="filterAccTable(this.value)">
                </div>
                <table style="width:100%;border-collapse:collapse;font-size:13px;" id="accTable">
                <thead><tr style="border-bottom:2px solid var(--border,#333);text-align:left;">
                    <th style="padding:8px 6px;">Account</th>
                    <th style="padding:8px 6px;">Category</th>
                    <th style="padding:8px 6px;text-align:right;">Period Dr</th>
                    <th style="padding:8px 6px;text-align:right;">Period Cr</th>
                    <th style="padding:8px 6px;text-align:right;">Closing Dr</th>
                    <th style="padding:8px 6px;text-align:right;">Closing Cr</th>
                    <th style="padding:8px 6px;text-align:right;">Txns</th>
                </tr></thead><tbody>`;
            accs.forEach(a => {
                const catCol = {Income:'#10b981','Cost of Sales':'#ef4444',Expenses:'#f59e0b',Assets:'#6366f1',Liabilities:'#ec4899',Equity:'#8b5cf6'}[a.category] || 'var(--text-muted)';
                tableHtml += `<tr class="acc-row" style="border-bottom:1px solid var(--border,rgba(255,255,255,0.05));">
                    <td style="padding:6px;">${a.name}</td>
                    <td style="padding:6px;"><span style="color:${catCol};font-size:11px;font-weight:600;">${a.category}</span></td>
                    <td style="padding:6px;text-align:right;">${a.period_dr ? R(a.period_dr) : '-'}</td>
                    <td style="padding:6px;text-align:right;">${a.period_cr ? R(a.period_cr) : '-'}</td>
                    <td style="padding:6px;text-align:right;font-weight:600;">${a.closing_dr ? R(a.closing_dr) : '-'}</td>
                    <td style="padding:6px;text-align:right;font-weight:600;">${a.closing_cr ? R(a.closing_cr) : '-'}</td>
                    <td style="padding:6px;text-align:right;">${a.txn_count}</td>
                </tr>`;
            });
            tableHtml += '</tbody></table>';
            document.getElementById('accountTableCard').innerHTML = tableHtml;

            // AI Card placeholder
            document.getElementById('aiCard').innerHTML = `
                <h3 style="margin:0 0 10px 0;">🤖 Zane AI Analysis</h3>
                <div id="aiInsights" style="color:var(--text-muted);">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <div class="spinner" style="width:20px;height:20px;border:2px solid rgba(99,102,241,0.3);border-top-color:#6366f1;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
                        <span>Zane is analysing the data...</span>
                    </div>
                </div>
                <style>@keyframes spin { to { transform: rotate(360deg); } }</style>
            `;
        }

        function filterAccTable(q) {
            const rows = document.querySelectorAll('#accTable .acc-row');
            const ql = q.toLowerCase();
            rows.forEach(r => {
                r.style.display = r.textContent.toLowerCase().includes(ql) ? '' : 'none';
            });
        }

        async function fetchAIInsights(data) {
            try {
                const resp = await fetch('/api/reports/gl/ai-analysis', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        summary: data.summary,
                        categories: data.categories,
                        anomalies: data.anomalies,
                        top_customers: data.top_customers,
                        top_suppliers: data.top_suppliers,
                        empty_accounts: data.empty_accounts,
                        revenue_trend: data.revenue_trend,
                    })
                });
                const result = await resp.json();
                const el = document.getElementById('aiInsights');
                if (result.success && result.analysis) {
                    el.innerHTML = '<div style="line-height:1.7;">' + result.analysis + '</div>';
                } else {
                    el.innerHTML = '<p style="color:#f59e0b;">AI analysis not available: ' + (result.error || 'Unknown error') + '</p><p style="color:var(--text-muted);font-size:12px;">The figures above are 100% accurate — only the AI commentary is unavailable.</p>';
                }
            } catch(e) {
                document.getElementById('aiInsights').innerHTML = '<p style="color:#f59e0b;">Could not load AI analysis. The figures above are still accurate.</p>';
            }
        }

        // ═══ BUILD FULL REPORT HTML (light theme for download/email) ═══
        function buildReportHTML() {
            const dateStr = new Date().toISOString().slice(0,10);
            const s = glAnalysisData.summary;
            const trend = glAnalysisData.revenue_trend || [];
            const tc = glAnalysisData.top_customers || [];
            const ts = glAnalysisData.top_suppliers || [];
            const anomalies = glAnalysisData.anomalies || [];
            const accs = glAnalysisData.account_table || [];
            const aiEl = document.getElementById('aiInsights');
            const aiHtml = (aiEl && !aiEl.querySelector('.spinner')) ? aiEl.innerHTML : '<p>AI analysis not yet available.</p>';

            return `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>GL Analysis Report</title>
<style>
body { font-family: Arial, Helvetica, sans-serif; max-width: 900px; margin: 30px auto; padding: 20px; color: #1a1a2e; line-height: 1.7; font-size: 14px; }
h1, h2, h3, h4 { color: #1a1a2e; }
h1 { color: #4f46e5; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; }
th { text-align: left; padding: 8px; border-bottom: 2px solid #e5e7eb; color: #6366f1; font-weight: 600; font-size: 12px; }
td { padding: 6px 8px; border-bottom: 1px solid #f3f4f6; font-size: 13px; }
.metric { display: inline-block; padding: 12px 18px; margin: 4px; border-radius: 8px; text-align: center; min-width: 120px; }
.metric .label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; }
.metric .value { font-size: 1.2rem; font-weight: 700; }
.green { color: #10b981; }
.red { color: #ef4444; }
.amber { color: #f59e0b; }
.purple { color: #6366f1; }
.flag { padding: 10px 14px; margin-bottom: 6px; border-left: 3px solid #ef4444; background: #fef2f2; border-radius: 0 6px 6px 0; }
.flag.warn { border-left-color: #f59e0b; background: #fffbeb; }
.section { margin: 30px 0; }
hr { border: none; border-top: 1px solid #e5e7eb; margin: 20px 0; }
@media print { body { margin: 0; } }
</style></head><body>
<h1>GL Analysis Report</h1>
<p style="color:#6b7280;font-size:12px;">Generated by ClickAI | ${dateStr} | Period: ${s.date_from} to ${s.date_to} (${s.months} months)</p>

<div class="section">
<h2>Summary</h2>
<div>
<span class="metric" style="background:#f0fdf4;"><span class="label">Accounts</span><br><span class="value">${s.account_count}</span></span>
<span class="metric" style="background:#f0f9ff;"><span class="label">Transactions</span><br><span class="value">${s.transaction_count.toLocaleString()}</span></span>
<span class="metric" style="background:${s.tb_balanced ? '#f0fdf4' : '#fef2f2'};"><span class="label">Trial Balance</span><br><span class="value ${s.tb_balanced ? 'green' : 'red'}">${s.tb_balanced ? '✓ Balanced' : '✗ Off by R' + Math.abs(s.tb_difference).toFixed(2)}</span></span>
</div>
</div>

<div class="section">
<h2>Trial Balance</h2>
<table><tr><th>Total Debits</th><th>Total Credits</th><th>Difference</th></tr>
<tr><td class="green" style="font-weight:700;font-size:1.1rem;">${R(s.tb_total_debit)}</td><td class="red" style="font-weight:700;font-size:1.1rem;">${R(s.tb_total_credit)}</td><td style="font-weight:700;font-size:1.1rem;color:${s.tb_balanced ? '#10b981' : '#ef4444'};">${R(s.tb_difference)}</td></tr></table>
</div>

<div class="section">
<h2>Profit & Loss</h2>
<table><tr><th>Revenue</th><th>Cost of Sales</th><th>Gross Profit</th><th>GP%</th><th>Expenses</th><th>Net Profit</th><th>NP%</th></tr>
<tr>
<td class="green" style="font-weight:700;">${R(s.total_income)}</td>
<td class="red">${R(s.total_cos)}</td>
<td style="font-weight:700;">${R(s.gross_profit)}</td>
<td>${s.gp_margin}%</td>
<td class="amber">${R(s.total_expenses)}</td>
<td style="font-weight:700;color:${s.net_profit >= 0 ? '#10b981' : '#ef4444'};">${R(s.net_profit)}</td>
<td>${s.np_margin}%</td>
</tr></table>
</div>

${trend.length > 1 ? '<div class="section"><h2>Monthly Revenue</h2><table><tr>' + trend.map(t => '<th style="text-align:center;">' + t.month.substring(5) + '</th>').join('') + '</tr><tr>' + trend.map(t => '<td style="text-align:center;font-weight:600;">' + R(t.amount) + '</td>').join('') + '</tr></table></div>' : ''}

${tc.length > 0 ? '<div class="section"><h2>Top Customers</h2><table><tr><th>#</th><th>Customer</th><th style="text-align:right;">Total</th></tr>' + tc.map((c,i) => '<tr><td>' + (i+1) + '</td><td>' + c.name + '</td><td style="text-align:right;font-weight:600;">' + R(c.total) + '</td></tr>').join('') + '</table></div>' : ''}

${ts.length > 0 ? '<div class="section"><h2>Top Suppliers</h2><table><tr><th>#</th><th>Supplier</th><th style="text-align:right;">Total</th></tr>' + ts.map((c,i) => '<tr><td>' + (i+1) + '</td><td>' + c.name + '</td><td style="text-align:right;font-weight:600;">' + R(c.total) + '</td></tr>').join('') + '</table></div>' : ''}

<div class="section">
<h2>Red Flags & Anomalies</h2>
${anomalies.length === 0 ? '<p class="green" style="font-weight:600;">✅ No anomalies detected.</p>' :
anomalies.map(a => {
    const cls = a.severity === 'alert' ? 'flag' : 'flag warn';
    const icon = a.severity === 'alert' ? '🔴' : '🟡';
    const typeLabel = a.type === 'possible_duplicate' ? 'Possible Duplicate' : a.type === 'large_transaction' ? 'Large Transaction' : a.type === 'suspense_balance' ? 'Suspense Balance' : a.type;
    return '<div class="' + cls + '"><strong>' + icon + ' ' + typeLabel + '</strong> — ' + R(a.amount) + '<br><span style="font-size:12px;color:#6b7280;">' + a.detail + '</span></div>';
}).join('')}
</div>

<div class="section">
<h2>Account Summary</h2>
<table><tr><th>Account</th><th>Category</th><th style="text-align:right;">Period Dr</th><th style="text-align:right;">Period Cr</th><th style="text-align:right;">Closing Dr</th><th style="text-align:right;">Closing Cr</th><th style="text-align:right;">Txns</th></tr>
${accs.map(a => '<tr><td>' + a.name + '</td><td style="color:#6366f1;font-size:11px;">' + a.category + '</td><td style="text-align:right;">' + (a.period_dr ? R(a.period_dr) : '-') + '</td><td style="text-align:right;">' + (a.period_cr ? R(a.period_cr) : '-') + '</td><td style="text-align:right;font-weight:600;">' + (a.closing_dr ? R(a.closing_dr) : '-') + '</td><td style="text-align:right;font-weight:600;">' + (a.closing_cr ? R(a.closing_cr) : '-') + '</td><td style="text-align:right;">' + a.txn_count + '</td></tr>').join('')}
</table>
</div>

<div class="section">
<h2>Zane AI Analysis</h2>
${aiHtml}
</div>

<hr><p style="color:#6b7280;font-size:11px;text-align:center;">Generated by <strong style="color:#6366f1;">ClickAI</strong> — AI-Powered Business Management | ${dateStr}</p>
</body></html>`;
        }

        // ═══ DOWNLOAD FULL REPORT ═══
        function downloadFullReport() {
            if (!glAnalysisData) { alert('No data loaded yet'); return; }
            const html = buildReportHTML();
            const dateStr = new Date().toISOString().slice(0,10);
            const blob = new Blob([html], {type: 'text/html'});
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'GL_Analysis_' + dateStr + '.html';
            a.click();
            URL.revokeObjectURL(a.href);
        }

        // ═══ EMAIL MODAL ═══
        function showGLEmailModal() {
            if (!glAnalysisData) { alert('No data loaded yet'); return; }
            document.getElementById('glEmailSubject').value = 'GL Analysis Report — ' + glAnalysisData.summary.date_from + ' to ' + glAnalysisData.summary.date_to;
            document.getElementById('glEmailStatus').style.display = 'none';
            document.getElementById('glEmailModal').style.display = 'flex';
            document.getElementById('glEmailTo').focus();
        }

        function closeGLEmailModal() {
            document.getElementById('glEmailModal').style.display = 'none';
        }

        async function sendGLReportEmail() {
            const to = document.getElementById('glEmailTo').value.trim();
            const subject = document.getElementById('glEmailSubject').value.trim() || 'GL Analysis Report';
            const status = document.getElementById('glEmailStatus');
            const btn = document.getElementById('glSendEmailBtn');

            if (!to || !to.includes('@')) {
                status.style.display = 'block';
                status.style.color = '#ef4444';
                status.textContent = 'Please enter a valid email address';
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Sending...';
            status.style.display = 'block';
            status.style.color = 'var(--text-muted)';
            status.textContent = 'Sending report...';

            try {
                const reportHtml = buildReportHTML();
                // Extract just the body content for the email
                const bodyMatch = reportHtml.match(/<body[^>]*>([\s\S]*)<\/body>/i);
                const bodyContent = bodyMatch ? bodyMatch[1] : reportHtml;

                const resp = await fetch('/api/reports/email', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        to_email: to,
                        subject: subject,
                        report_html: bodyContent,
                        report_title: 'GL Analysis Report'
                    })
                });
                const data = await resp.json();

                if (data.success) {
                    status.style.color = '#10b981';
                    status.textContent = '✅ ' + data.message;
                    setTimeout(() => closeGLEmailModal(), 2000);
                } else {
                    status.style.color = '#ef4444';
                    status.textContent = '✗ ' + (data.error || 'Failed to send');
                }
            } catch(err) {
                status.style.color = '#ef4444';
                status.textContent = '✗ Network error: ' + err.message;
            }
            btn.disabled = false;
            btn.textContent = 'Send';
        }
        </script>
        '''

        return render_page("GL Analysis", content, user, "reports")

    # ───────────────────────────────────────────────────────────
    # API: Upload & Parse GL
    # ───────────────────────────────────────────────────────────
    @app.route("/api/reports/gl/upload", methods=["POST"])
    @login_required
    def api_gl_upload():
        """Parse uploaded GL file and return analysis."""
        from flask import request, jsonify

        try:
            if "file" not in request.files:
                return jsonify({"success": False, "error": "No file uploaded"})

            file = request.files["file"]
            filename = file.filename or "unknown.csv"

            # Read file content
            raw = file.read()

            # Try UTF-8 first, then latin-1
            try:
                content = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = raw.decode("latin-1")

            if not content.strip():
                return jsonify({"success": False, "error": "File is empty"})

            # Excel files — convert to CSV with openpyxl
            if filename.lower().endswith((".xlsx", ".xls")):
                try:
                    import openpyxl
                    from io import BytesIO
                    wb = openpyxl.load_workbook(BytesIO(raw), read_only=True, data_only=True)
                    ws = wb.active
                    output = io.StringIO()
                    writer = csv.writer(output)
                    for row in ws.iter_rows(values_only=True):
                        writer.writerow([str(c) if c is not None else "" for c in row])
                    content = output.getvalue()
                except Exception as ex:
                    return jsonify({"success": False, "error": f"Could not read Excel file: {ex}"})

            # Detect format: Sage has "Opening Balance as at:" pattern
            is_sage = "Opening Balance as at:" in content or "Closing Balance as at:" in content

            if is_sage:
                accounts = parse_sage_gl(content, filename)
            else:
                accounts = parse_generic_gl(content, filename)

            if not accounts:
                return jsonify({"success": False, "error": "Could not parse any accounts. Check file format — expected Sage AccountTransactionsReport or CSV with Account/Date/Debit/Credit columns."})

            # Run analysis
            analysis = run_gl_analysis(accounts)

            return jsonify({
                "success": True,
                "filename": filename,
                **analysis,
            })

        except Exception as e:
            logger.error(f"[GL ANALYSIS] Upload error: {e}\n{traceback.format_exc()}")
            return jsonify({"success": False, "error": str(e)})

    # ───────────────────────────────────────────────────────────
    # API: Zane AI Analysis
    # ───────────────────────────────────────────────────────────
    @app.route("/api/reports/gl/ai-analysis", methods=["POST"])
    @login_required
    def api_gl_ai_analysis():
        """Send GL summary to Zane (Claude Haiku) for AI insights."""
        from flask import request, jsonify

        if not _anthropic_client:
            return jsonify({"success": False, "error": "AI not configured"})

        try:
            data = request.json
            summary = data.get("summary", {})
            categories = data.get("categories", {})
            anomalies = data.get("anomalies", [])
            top_customers = data.get("top_customers", [])
            top_suppliers = data.get("top_suppliers", [])
            empty_accounts = data.get("empty_accounts", [])
            revenue_trend = data.get("revenue_trend", [])

            # Build concise prompt for Haiku
            prompt = f"""You are Zane, a senior South African bookkeeper and financial analyst. Analyse this General Ledger data and provide actionable insights.

FINANCIAL SUMMARY:
- Period: {summary.get('date_from','?')} to {summary.get('date_to','?')} ({summary.get('months',0)} months)
- Accounts: {summary.get('account_count',0)}, Transactions: {summary.get('transaction_count',0)}
- TB Balanced: {'Yes' if summary.get('tb_balanced') else 'NO — difference of R' + str(summary.get('tb_difference',0))}
- Revenue: R{summary.get('total_income',0):,.2f}
- Cost of Sales: R{summary.get('total_cos',0):,.2f}
- Gross Profit: R{summary.get('gross_profit',0):,.2f} ({summary.get('gp_margin',0)}%)
- Operating Expenses: R{summary.get('total_expenses',0):,.2f}
- Net Profit: R{summary.get('net_profit',0):,.2f} ({summary.get('np_margin',0)}%)

CATEGORIES:
{json.dumps({k: {'debit': v['debit'], 'credit': v['credit'], 'accounts': len(v.get('accounts',[]))} for k,v in categories.items()}, indent=2)}

MONTHLY REVENUE TREND:
{json.dumps(revenue_trend)}

TOP CUSTOMERS: {json.dumps(top_customers[:5])}
TOP SUPPLIERS: {json.dumps(top_suppliers[:5])}

ANOMALIES DETECTED ({len(anomalies)}):
{json.dumps(anomalies[:15], indent=2) if anomalies else 'None'}

EMPTY ACCOUNTS: {', '.join(empty_accounts[:10]) if empty_accounts else 'None'}

Please provide your analysis as simple HTML fragments ONLY — just <h4>, <p>, <ul>, <li>, <strong>, <span> tags.
DO NOT include <!DOCTYPE>, <html>, <head>, <style>, <body> or any CSS. The output will be embedded in an existing page.
Use inline styles only where needed (e.g. color:red for negative numbers).

Include ALL of these sections (do not cut short):
1. <h4>Overall Health</h4> — Is this business in good shape? Any immediate concerns? Give a clear verdict.
2. <h4>Profitability Analysis</h4> — Comment on GP margin and NP margin. Are they healthy for a SA SME? What's driving the numbers? Compare to typical SA industry benchmarks.
3. <h4>Revenue Concentration Risk</h4> — Is revenue dangerously concentrated in few clients? Calculate % contribution of top 3. What happens if the biggest client leaves?
4. <h4>Cash Flow Observations</h4> — Comment on the monthly revenue pattern. Flag any seasonality, spikes, or concerning gaps. Note months with unusual activity.
5. <h4>Red Flags & Anomaly Review</h4> — Review each anomaly type. Which are genuinely concerning (investigate!) and which are likely benign (e.g. journal entries, split payments)? Be specific.
6. <h4>Recommendations</h4> — 5 specific, actionable recommendations numbered 1-5. Include concrete next steps. Think like a rekenmeester advising the business owner.

Keep it direct, practical, and thorough. Use South African business context (Rands, SARS, BEE, etc). This is a professional report that may be emailed to a client."""

            response = _anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            analysis_html = ""
            for block in response.content:
                if hasattr(block, "text"):
                    analysis_html += block.text

            # Strip any accidental full HTML document tags Haiku might return
            import re as _re
            analysis_html = _re.sub(r'<!DOCTYPE[^>]*>', '', analysis_html)
            analysis_html = _re.sub(r'</?html[^>]*>', '', analysis_html)
            analysis_html = _re.sub(r'<head>.*?</head>', '', analysis_html, flags=_re.DOTALL)
            analysis_html = _re.sub(r'</?body[^>]*>', '', analysis_html)
            analysis_html = _re.sub(r'<style[^>]*>.*?</style>', '', analysis_html, flags=_re.DOTALL)
            analysis_html = _re.sub(r'<meta[^>]*>', '', analysis_html)

            return jsonify({"success": True, "analysis": analysis_html})

        except Exception as e:
            logger.error(f"[GL ANALYSIS] AI error: {e}")
            return jsonify({"success": False, "error": str(e)})

    logger.info("[GL ANALYSIS] Module loaded — routes: /reports/gl-analysis, /api/reports/gl/upload, /api/reports/gl/ai-analysis")
