"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 1: Core Foundation                                                    ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Flask application setup                                                   ║
║   - Database connection class (Supabase)                                      ║
║   - Helper functions                                                          ║
║   - VAT calculation logic (with zero-rated items)                            ║
║   - Date and currency formatting                                              ║
║   - User session management                                                   ║
║                                                                               ║
║   All calculations done by Flask - no JavaScript math                         ║
║   Opus AI advises, Flask executes                                             ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import Flask, jsonify, request, redirect, session, g
import json
import os
import re
import uuid
import requests
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

# ═══════════════════════════════════════════════════════════════════════════════
# FLASK APPLICATION SETUP
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "clickai-secret-key-change-in-production")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class Config:
    """Application configuration"""
    
    # Database
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    
    # AI
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    OPUS_MODEL = "claude-opus-4-20250514"
    SONNET_MODEL = "claude-sonnet-4-20250514"
    
    # Business Settings
    COMPANY_NAME = "FullTech"
    VAT_RATE = Decimal("0.15")  # 15% standard rate
    CURRENCY_SYMBOL = "R"
    
    # Financial Year (South African standard - March to February)
    FINANCIAL_YEAR_END_MONTH = 2  # February
    
    # Session timeout (minutes)
    SESSION_TIMEOUT = 480  # 8 hours


# ═══════════════════════════════════════════════════════════════════════════════
# VAT LOGIC - SOUTH AFRICAN RULES
# ═══════════════════════════════════════════════════════════════════════════════

class VAT:
    """
    South African VAT calculations
    
    Standard Rate: 15%
    Zero-Rated: 0% (fuel, basic foods, exports)
    Exempt: No VAT charged, no input VAT claimed
    """
    
    STANDARD_RATE = Decimal("0.15")
    ZERO_RATE = Decimal("0")
    
    # Keywords that indicate zero-rated items
    ZERO_RATED_KEYWORDS = [
        # Fuel
        'petrol', 'diesel', 'fuel', 'paraffin', 'illuminating paraffin',
        
        # Basic foods - grains
        'brown bread', 'maize meal', 'mealie meal', 'samp', 'rice', 
        'dried corn', 'mielie rice',
        
        # Basic foods - legumes
        'dried beans', 'lentils', 'dried peas', 'pilchards', 'sardines',
        
        # Basic foods - dairy & eggs
        'fresh milk', 'cultured milk', 'milk powder', 'eggs',
        
        # Basic foods - produce
        'vegetables', 'fruit', 'vegetable oil', 'cooking oil',
        
        # Other zero-rated
        'export', 'international transport',
    ]
    
    # Categories that are typically zero-rated
    ZERO_RATED_CATEGORIES = [
        'fuel', 'basic foods', 'exports'
    ]
    
    # Expense categories that are exempt (no VAT claim allowed)
    EXEMPT_CATEGORIES = [
        'financial services', 'bank charges', 'interest', 
        'insurance', 'residential rent', 'salaries', 'wages',
        'paye', 'uif', 'sdl'
    ]
    
    @classmethod
    def is_zero_rated(cls, description: str = "", category: str = "") -> bool:
        """
        Check if an item is zero-rated based on description or category
        
        Args:
            description: Item description
            category: Item category
            
        Returns:
            True if zero-rated, False if standard rated
        """
        description_lower = description.lower()
        category_lower = category.lower()
        
        # Check category first
        for exempt_cat in cls.ZERO_RATED_CATEGORIES:
            if exempt_cat in category_lower:
                return True
        
        # Check description keywords
        for keyword in cls.ZERO_RATED_KEYWORDS:
            if keyword in description_lower:
                return True
        
        return False
    
    @classmethod
    def is_exempt(cls, category: str = "") -> bool:
        """
        Check if a category is VAT exempt (no input VAT can be claimed)
        
        Args:
            category: Expense category
            
        Returns:
            True if exempt, False otherwise
        """
        category_lower = category.lower()
        
        for exempt_cat in cls.EXEMPT_CATEGORIES:
            if exempt_cat in category_lower:
                return True
        
        return False
    
    @classmethod
    def get_rate(cls, description: str = "", category: str = "") -> Decimal:
        """
        Get the applicable VAT rate for an item
        
        Args:
            description: Item description
            category: Item category
            
        Returns:
            VAT rate as Decimal (0.15 or 0)
        """
        if cls.is_zero_rated(description, category):
            return cls.ZERO_RATE
        return cls.STANDARD_RATE
    
    @classmethod
    def calculate_from_inclusive(cls, amount_incl: Decimal, rate: Decimal = None) -> dict:
        """
        Calculate VAT from VAT-inclusive amount
        
        Args:
            amount_incl: Amount including VAT
            rate: VAT rate (defaults to standard rate)
            
        Returns:
            Dictionary with 'exclusive', 'vat', and 'inclusive' amounts
        """
        if rate is None:
            rate = cls.STANDARD_RATE
        
        amount_incl = Decimal(str(amount_incl))
        
        if rate == cls.ZERO_RATE:
            return {
                'exclusive': amount_incl,
                'vat': Decimal("0"),
                'inclusive': amount_incl,
                'rate': rate
            }
        
        # Formula: exclusive = inclusive / (1 + rate)
        divisor = Decimal("1") + rate
        amount_excl = (amount_incl / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        vat = (amount_incl - amount_excl).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        return {
            'exclusive': amount_excl,
            'vat': vat,
            'inclusive': amount_incl,
            'rate': rate
        }
    
    @classmethod
    def calculate_from_exclusive(cls, amount_excl: Decimal, rate: Decimal = None) -> dict:
        """
        Calculate VAT from VAT-exclusive amount
        
        Args:
            amount_excl: Amount excluding VAT
            rate: VAT rate (defaults to standard rate)
            
        Returns:
            Dictionary with 'exclusive', 'vat', and 'inclusive' amounts
        """
        if rate is None:
            rate = cls.STANDARD_RATE
        
        amount_excl = Decimal(str(amount_excl))
        
        if rate == cls.ZERO_RATE:
            return {
                'exclusive': amount_excl,
                'vat': Decimal("0"),
                'inclusive': amount_excl,
                'rate': rate
            }
        
        vat = (amount_excl * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        amount_incl = amount_excl + vat
        
        return {
            'exclusive': amount_excl,
            'vat': vat,
            'inclusive': amount_incl,
            'rate': rate
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MONEY HANDLING - PRECISION MATTERS
# ═══════════════════════════════════════════════════════════════════════════════

class Money:
    """
    Handle money with proper precision
    All internal calculations use Decimal
    All storage uses cents (integer) to avoid floating point issues
    """
    
    @staticmethod
    def to_cents(rands: Decimal) -> int:
        """Convert Rands to cents for storage"""
        return int((Decimal(str(rands)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    
    @staticmethod
    def from_cents(cents: int) -> Decimal:
        """Convert cents back to Rands"""
        return Decimal(str(cents)) / 100
    
    @staticmethod
    def parse(value) -> Decimal:
        """
        Parse various input formats to Decimal
        
        Handles:
        - "R 1,234.56"
        - "1234.56"
        - 1234.56
        - "R1234,56" (comma as decimal)
        """
        if value is None:
            return Decimal("0")
        
        if isinstance(value, Decimal):
            return value
        
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        
        # String parsing
        s = str(value).strip()
        
        # Remove currency symbol and spaces
        s = s.replace("R", "").replace(" ", "")
        
        # Handle comma as thousands separator or decimal
        if "," in s and "." in s:
            # Both present: comma is thousands separator
            s = s.replace(",", "")
        elif "," in s:
            # Only comma: could be decimal separator
            # Check if it's in the last 3 characters (likely decimal)
            if len(s) - s.rfind(",") <= 3:
                s = s.replace(",", ".")
            else:
                s = s.replace(",", "")
        
        try:
            return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except:
            return Decimal("0")
    
    @staticmethod
    def format(amount: Decimal, symbol: bool = True) -> str:
        """
        Format amount for display
        
        Args:
            amount: Amount to format
            symbol: Include currency symbol
            
        Returns:
            Formatted string like "R 1,234.56"
        """
        amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Format with thousands separator
        formatted = f"{amount:,.2f}"
        
        if symbol:
            return f"R {formatted}"
        return formatted


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE CONNECTION - SUPABASE
# ═══════════════════════════════════════════════════════════════════════════════

class Database:
    """
    Supabase database connection
    
    Handles all CRUD operations with proper error handling
    """
    
    def __init__(self, url: str = None, key: str = None):
        self.url = (url or Config.SUPABASE_URL).rstrip('/')
        self.key = key or Config.SUPABASE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        self.timeout = 30
    
    def _request(self, method: str, endpoint: str, data: dict = None) -> tuple:
        """
        Make HTTP request to Supabase
        
        Returns:
            Tuple of (success: bool, data: dict/list or error: str)
        """
        url = f"{self.url}/rest/v1/{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=self.timeout)
            elif method == "PATCH":
                response = requests.patch(url, headers=self.headers, json=data, timeout=self.timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers, timeout=self.timeout)
            else:
                return False, f"Unknown method: {method}"
            
            if response.status_code in [200, 201, 204]:
                if response.text:
                    return True, response.json()
                return True, []
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            return False, "Database timeout"
        except requests.exceptions.ConnectionError:
            return False, "Database connection error"
        except Exception as e:
            return False, str(e)
    
    def select(self, table: str, filters: dict = None, order: str = None, 
               limit: int = None, columns: str = "*") -> list:
        """
        Select records from table
        
        Args:
            table: Table name
            filters: Dict of column=value filters
            order: Column to order by (prefix with - for descending)
            limit: Maximum records to return
            columns: Columns to select (default all)
            
        Returns:
            List of records
        """
        endpoint = f"{table}?select={columns}"
        
        if filters:
            for key, value in filters.items():
                endpoint += f"&{key}=eq.{value}"
        
        if order:
            if order.startswith("-"):
                endpoint += f"&order={order[1:]}.desc"
            else:
                endpoint += f"&order={order}.asc"
        
        if limit:
            endpoint += f"&limit={limit}"
        
        success, result = self._request("GET", endpoint)
        return result if success and isinstance(result, list) else []
    
    def select_one(self, table: str, id: str) -> dict:
        """Get single record by ID"""
        results = self.select(table, {"id": id}, limit=1)
        return results[0] if results else None
    
    def insert(self, table: str, data: dict) -> tuple:
        """
        Insert record
        
        Returns:
            Tuple of (success: bool, record: dict or error: str)
        """
        return self._request("POST", table, data)
    
    def update(self, table: str, id: str, data: dict) -> tuple:
        """
        Update record by ID
        
        Returns:
            Tuple of (success: bool, record: dict or error: str)
        """
        endpoint = f"{table}?id=eq.{id}"
        return self._request("PATCH", endpoint, data)
    
    def delete(self, table: str, id: str) -> tuple:
        """
        Delete record by ID
        
        Returns:
            Tuple of (success: bool, result or error: str)
        """
        endpoint = f"{table}?id=eq.{id}"
        return self._request("DELETE", endpoint)
    
    def upsert(self, table: str, data: dict, id_field: str = "id") -> tuple:
        """
        Insert or update record
        
        If record with ID exists, update it. Otherwise insert new.
        """
        if data.get(id_field):
            existing = self.select_one(table, data[id_field])
            if existing:
                return self.update(table, data[id_field], data)
        
        return self.insert(table, data)
    
    def count(self, table: str, filters: dict = None) -> int:
        """Count records matching filters"""
        endpoint = f"{table}?select=id"
        
        if filters:
            for key, value in filters.items():
                endpoint += f"&{key}=eq.{value}"
        
        # Use HEAD request with Prefer header for count
        headers = self.headers.copy()
        headers["Prefer"] = "count=exact"
        
        try:
            response = requests.head(
                f"{self.url}/rest/v1/{endpoint}",
                headers=headers,
                timeout=self.timeout
            )
            count_header = response.headers.get("content-range", "")
            if "/" in count_header:
                return int(count_header.split("/")[1])
        except:
            pass
        
        # Fallback: do actual select and count
        results = self.select(table, filters)
        return len(results)
    
    def sum(self, table: str, column: str, filters: dict = None) -> Decimal:
        """Sum a numeric column"""
        records = self.select(table, filters, columns=column)
        total = Decimal("0")
        for record in records:
            value = record.get(column, 0)
            if value:
                total += Decimal(str(value))
        return total


# Initialize database instance
db = Database()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_id() -> str:
    """Generate unique ID for records"""
    return str(uuid.uuid4())


def now() -> str:
    """Current datetime in ISO format"""
    return datetime.now().isoformat()


def today() -> str:
    """Current date as YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def format_date(date_str: str, output_format: str = "%d %b %Y") -> str:
    """
    Format date string for display
    
    Args:
        date_str: Date in ISO format or YYYY-MM-DD
        output_format: Desired output format
        
    Returns:
        Formatted date string
    """
    if not date_str:
        return ""
    
    try:
        # Handle ISO format with time
        if "T" in date_str:
            date_str = date_str.split("T")[0]
        
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime(output_format)
    except:
        return date_str


def safe_string(value, max_length: int = None) -> str:
    """
    Sanitize string for safe output
    Removes potentially dangerous characters
    """
    if value is None:
        return ""
    
    s = str(value)
    
    # Remove control characters and potentially dangerous chars
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    s = s.replace('<', '&lt;').replace('>', '&gt;')
    s = s.replace('"', '&quot;').replace("'", '&#39;')
    
    if max_length:
        s = s[:max_length]
    
    return s.strip()


def safe_json_string(value) -> str:
    """Sanitize string for use in JavaScript"""
    if value is None:
        return ""
    
    s = str(value)
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace("'", "\\'")
    s = s.replace('\n', '\\n')
    s = s.replace('\r', '\\r')
    s = s.replace('\t', '\\t')
    
    # Remove non-printable characters
    s = re.sub(r'[^\x20-\x7E]', '', s)
    
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# USER SESSION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

class UserSession:
    """Handle user authentication and sessions"""
    
    @staticmethod
    def login(username: str, password: str) -> tuple:
        """
        Authenticate user
        
        Returns:
            Tuple of (success: bool, user: dict or error: str)
        """
        users = db.select("users", {"username": username}, limit=1)
        
        if not users:
            return False, "User not found"
        
        user = users[0]
        
        # Simple password check (in production, use proper hashing)
        if user.get("password") != password:
            return False, "Invalid password"
        
        if not user.get("active", True):
            return False, "Account disabled"
        
        # Set session
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user.get("role", "user")
        session["login_time"] = now()
        
        return True, user
    
    @staticmethod
    def logout():
        """Clear user session"""
        session.clear()
    
    @staticmethod
    def get_current_user() -> dict:
        """Get current logged in user"""
        if "user_id" not in session:
            return None
        
        return {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role")
        }
    
    @staticmethod
    def is_logged_in() -> bool:
        """Check if user is logged in"""
        return "user_id" in session
    
    @staticmethod
    def require_login(f):
        """Decorator to require login for a route"""
        @wraps(f)
        def decorated(*args, **kwargs):
            if not UserSession.is_logged_in():
                return redirect("/login")
            return f(*args, **kwargs)
        return decorated
    
    @staticmethod
    def require_role(role: str):
        """Decorator to require specific role"""
        def decorator(f):
            @wraps(f)
            def decorated(*args, **kwargs):
                if not UserSession.is_logged_in():
                    return redirect("/login")
                if session.get("role") != role and session.get("role") != "admin":
                    return redirect("/unauthorized")
                return f(*args, **kwargs)
            return decorated
        return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# OPUS AI INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class OpusAI:
    """
    Claude Opus integration for intelligent features
    
    Opus ADVISES, Flask EXECUTES
    - Receipt reading and data extraction
    - Expense categorization suggestions
    - Anomaly detection
    - Business insights
    """
    
    @staticmethod
    def _call_api(messages: list, model: str = None, max_tokens: int = 1000) -> tuple:
        """
        Call Anthropic API
        
        Returns:
            Tuple of (success: bool, response: str or error: str)
        """
        api_key = Config.ANTHROPIC_API_KEY
        if not api_key:
            return False, "API key not configured"
        
        if model is None:
            model = Config.OPUS_MODEL
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": messages
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get("content", [{}])[0].get("text", "")
                return True, text
            else:
                return False, f"API error: {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "API timeout"
        except Exception as e:
            return False, str(e)
    
    @classmethod
    def read_receipt(cls, image_base64: str) -> dict:
        """
        Extract data from receipt image
        
        Args:
            image_base64: Base64 encoded image
            
        Returns:
            Dict with supplier, description, amount, vat_rate, category
        """
        # Clean base64 string
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        
        prompt = """Analyze this receipt/invoice image and extract the following information.
        
For VAT, note South African rules:
- Standard rate is 15%
- ZERO-RATED (0% VAT): Petrol, diesel, basic foods (brown bread, maize meal, rice, eggs, milk, vegetables, fruit, cooking oil, dried beans, pilchards/sardines)
- Look for "VAT" or "BTW" on the slip to determine the VAT amount

Return ONLY a JSON object in this exact format:
{
    "supplier": "Store/Company name",
    "description": "Brief description of purchase",
    "amount": 123.45,
    "vat_amount": 12.34,
    "is_zero_rated": false,
    "category": "suggested expense category",
    "confidence": 0.95
}

If you cannot read something clearly, use your best judgment based on context.
For category, suggest one of: Fuel, Stock/Inventory, Office Supplies, Repairs & Maintenance, Utilities, Cleaning, Consumables, Transport, Entertainment, Other"""

        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_base64
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
        
        success, response = cls._call_api(messages, max_tokens=500)
        
        if not success:
            return {"error": response}
        
        # Parse JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data
        except:
            pass
        
        return {"error": "Could not parse receipt"}
    
    @classmethod
    def suggest_category(cls, description: str, supplier: str = "") -> str:
        """
        Suggest expense category based on description
        
        Args:
            description: Expense description
            supplier: Supplier name (optional)
            
        Returns:
            Suggested category name
        """
        prompt = f"""Based on this expense:
Supplier: {supplier}
Description: {description}

Suggest the most appropriate expense category from this list:
- Accounting Fees
- Advertising & Marketing
- Bank Charges
- Cleaning
- Computer Expenses
- Consumables
- Electricity & Water
- Entertainment
- Fuel & Oil
- General Expenses
- Insurance
- Internet & Telephone
- Motor Vehicle Expenses
- Office Supplies
- Postage & Courier
- Printing & Stationery
- Rent
- Repairs & Maintenance
- Salaries & Wages
- Security
- Stock/Inventory (if buying items for resale)
- Transport
- Travel & Accommodation

Reply with ONLY the category name, nothing else."""

        messages = [{"role": "user", "content": prompt}]
        
        success, response = cls._call_api(messages, model=Config.SONNET_MODEL, max_tokens=50)
        
        if success:
            return response.strip()
        
        return "General Expenses"


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT NUMBER GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentNumbers:
    """Generate sequential document numbers"""
    
    @staticmethod
    def get_next(prefix: str, table: str, column: str = "number") -> str:
        """
        Get next document number
        
        Args:
            prefix: Document prefix (e.g., "INV", "QUO")
            table: Table to check for existing numbers
            column: Column containing document numbers
            
        Returns:
            Next number like "INV0001"
        """
        # Get all existing numbers with this prefix
        records = db.select(table, columns=column)
        
        max_num = 0
        for record in records:
            num_str = record.get(column, "")
            if num_str.startswith(prefix):
                try:
                    num = int(num_str[len(prefix):])
                    max_num = max(max_num, num)
                except:
                    pass
        
        next_num = max_num + 1
        return f"{prefix}{next_num:04d}"


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCIAL PERIOD HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class FinancialPeriod:
    """Handle financial year and period calculations"""
    
    @staticmethod
    def get_current_year_start() -> str:
        """Get start date of current financial year"""
        now = datetime.now()
        year_end_month = Config.FINANCIAL_YEAR_END_MONTH
        
        if now.month <= year_end_month:
            # We're in the latter part of the financial year
            year_start = datetime(now.year - 1, year_end_month + 1, 1)
        else:
            # We're in the earlier part of the financial year
            year_start = datetime(now.year, year_end_month + 1, 1)
        
        return year_start.strftime("%Y-%m-%d")
    
    @staticmethod
    def get_current_year_end() -> str:
        """Get end date of current financial year"""
        now = datetime.now()
        year_end_month = Config.FINANCIAL_YEAR_END_MONTH
        
        if now.month <= year_end_month:
            year_end = datetime(now.year, year_end_month + 1, 1) - timedelta(days=1)
        else:
            year_end = datetime(now.year + 1, year_end_month + 1, 1) - timedelta(days=1)
        
        return year_end.strftime("%Y-%m-%d")
    
    @staticmethod
    def get_vat_period_start(date: datetime = None) -> str:
        """Get start of current VAT period (bi-monthly)"""
        if date is None:
            date = datetime.now()
        
        # VAT periods: Jan-Feb, Mar-Apr, May-Jun, Jul-Aug, Sep-Oct, Nov-Dec
        month = date.month
        if month % 2 == 0:
            period_start_month = month - 1
        else:
            period_start_month = month
        
        return datetime(date.year, period_start_month, 1).strftime("%Y-%m-%d")
    
    @staticmethod
    def get_vat_period_end(date: datetime = None) -> str:
        """Get end of current VAT period"""
        if date is None:
            date = datetime.now()
        
        month = date.month
        if month % 2 == 0:
            period_end_month = month
        else:
            period_end_month = month + 1
        
        # Get last day of period_end_month
        if period_end_month == 12:
            next_month = datetime(date.year + 1, 1, 1)
        else:
            next_month = datetime(date.year, period_end_month + 1, 1)
        
        period_end = next_month - timedelta(days=1)
        return period_end.strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 1
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 1 COMPLETE - Core Foundation

Contains:
✓ Flask app setup
✓ Configuration class
✓ VAT logic with zero-rated detection
✓ Money handling with Decimal precision
✓ Database class with full CRUD
✓ Helper functions (ID generation, dates, string sanitization)
✓ User session management
✓ Opus AI integration
✓ Document number generation
✓ Financial period helpers

Next: Piece 2 - Chart of Accounts
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 2: Chart of Accounts                                                  ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Complete South African SME Chart of Accounts                              ║
║   - Account types and categories                                              ║
║   - Account class for operations                                              ║
║   - Functions to initialize and manage accounts                               ║
║                                                                               ║
║   Account Numbering Convention:                                               ║
║   1000-1999: Assets                                                           ║
║   2000-2999: Liabilities                                                      ║
║   3000-3999: Equity                                                           ║
║   4000-4999: Revenue/Income                                                   ║
║   5000-5999: Cost of Sales                                                    ║
║   6000-6999: Operating Expenses                                               ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from decimal import Decimal
from enum import Enum
from typing import List, Dict, Optional
from piece1_core import db, generate_id, now, Money


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNT TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class AccountType(Enum):
    """
    Account types determine how the account appears in financial statements
    and how its balance is calculated
    """
    ASSET = "asset"                 # Debit balance, appears on Balance Sheet
    LIABILITY = "liability"         # Credit balance, appears on Balance Sheet
    EQUITY = "equity"               # Credit balance, appears on Balance Sheet
    REVENUE = "revenue"             # Credit balance, appears on Income Statement
    COST_OF_SALES = "cost_of_sales" # Debit balance, appears on Income Statement
    EXPENSE = "expense"             # Debit balance, appears on Income Statement


class AccountCategory(Enum):
    """
    Sub-categories for grouping accounts in reports
    """
    # Asset categories
    CURRENT_ASSET = "current_asset"
    FIXED_ASSET = "fixed_asset"
    
    # Liability categories
    CURRENT_LIABILITY = "current_liability"
    LONG_TERM_LIABILITY = "long_term_liability"
    
    # Equity categories
    CAPITAL = "capital"
    RETAINED_EARNINGS = "retained_earnings"
    
    # Revenue categories
    SALES = "sales"
    OTHER_INCOME = "other_income"
    
    # Cost of Sales categories
    DIRECT_COSTS = "direct_costs"
    
    # Expense categories
    OPERATING_EXPENSE = "operating_expense"
    ADMINISTRATIVE_EXPENSE = "administrative_expense"
    FINANCIAL_EXPENSE = "financial_expense"


# ═══════════════════════════════════════════════════════════════════════════════
# STANDARD CHART OF ACCOUNTS - SOUTH AFRICAN SME
# ═══════════════════════════════════════════════════════════════════════════════

STANDARD_CHART_OF_ACCOUNTS = [
    # ═══════════════════════════════════════════════════════════════════════════
    # ASSETS (1000-1999)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Current Assets (1000-1399)
    {
        "code": "1000",
        "name": "Bank - Current Account",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Main business bank account",
        "vat_applicable": False,
        "system_account": True  # Cannot be deleted
    },
    {
        "code": "1010",
        "name": "Bank - Savings Account",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Business savings account",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1020",
        "name": "Petty Cash",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Cash on hand for small expenses",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "1030",
        "name": "Cash Float",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Till/register cash float",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1100",
        "name": "Debtors Control",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Total amount owed by customers",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "1110",
        "name": "Debtors - Trade",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Amounts owed for goods/services sold",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1120",
        "name": "Debtors - Other",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Other amounts receivable",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1130",
        "name": "Provision for Bad Debts",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Contra account for doubtful debts",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "1200",
        "name": "Stock / Inventory",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Goods held for resale",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "1210",
        "name": "Stock - Raw Materials",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Raw materials for manufacturing",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1220",
        "name": "Stock - Work in Progress",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Partially completed goods",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1230",
        "name": "Stock - Finished Goods",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Completed goods ready for sale",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1300",
        "name": "Prepaid Expenses",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Expenses paid in advance",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1310",
        "name": "Prepaid Rent",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Rent paid in advance",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1320",
        "name": "Prepaid Insurance",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Insurance premiums paid in advance",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "1350",
        "name": "Deposits Paid",
        "type": AccountType.ASSET,
        "category": AccountCategory.CURRENT_ASSET,
        "description": "Refundable deposits paid",
        "vat_applicable": False,
        "system_account": False
    },
    
    # Fixed Assets (1400-1999)
    {
        "code": "1400",
        "name": "Land",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Land owned by business",
        "vat_applicable": False,
        "system_account": False,
        "depreciable": False
    },
    {
        "code": "1410",
        "name": "Buildings",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Buildings at cost",
        "vat_applicable": False,
        "system_account": False,
        "depreciable": True,
        "depreciation_rate": Decimal("0.05")  # 5% per year
    },
    {
        "code": "1411",
        "name": "Buildings - Accumulated Depreciation",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Accumulated depreciation on buildings",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "1500",
        "name": "Equipment at Cost",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Equipment and machinery at cost",
        "vat_applicable": False,
        "system_account": False,
        "depreciable": True,
        "depreciation_rate": Decimal("0.20")  # 20% per year
    },
    {
        "code": "1510",
        "name": "Equipment - Accumulated Depreciation",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Accumulated depreciation on equipment",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "1600",
        "name": "Vehicles at Cost",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Motor vehicles at cost",
        "vat_applicable": False,
        "system_account": False,
        "depreciable": True,
        "depreciation_rate": Decimal("0.20")  # 20% per year
    },
    {
        "code": "1610",
        "name": "Vehicles - Accumulated Depreciation",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Accumulated depreciation on vehicles",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "1700",
        "name": "Furniture & Fittings at Cost",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Office furniture at cost",
        "vat_applicable": False,
        "system_account": False,
        "depreciable": True,
        "depreciation_rate": Decimal("0.1667")  # 16.67% per year (6 years)
    },
    {
        "code": "1710",
        "name": "Furniture - Accumulated Depreciation",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Accumulated depreciation on furniture",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "1800",
        "name": "Computer Equipment at Cost",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Computers and IT equipment at cost",
        "vat_applicable": False,
        "system_account": False,
        "depreciable": True,
        "depreciation_rate": Decimal("0.3333")  # 33.33% per year (3 years)
    },
    {
        "code": "1810",
        "name": "Computer Equipment - Accumulated Depreciation",
        "type": AccountType.ASSET,
        "category": AccountCategory.FIXED_ASSET,
        "description": "Accumulated depreciation on computer equipment",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    # LIABILITIES (2000-2999)
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Current Liabilities (2000-2499)
    {
        "code": "2000",
        "name": "Creditors Control",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Total amount owed to suppliers",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "2010",
        "name": "Creditors - Trade",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Amounts owed for goods/services purchased",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2020",
        "name": "Creditors - Other",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Other amounts payable",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2100",
        "name": "VAT Output",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "VAT collected on sales - payable to SARS",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "2110",
        "name": "VAT Input",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "VAT paid on purchases - claimable from SARS",
        "vat_applicable": False,
        "system_account": True,
        "contra_account": True  # Contra to VAT Output
    },
    {
        "code": "2120",
        "name": "VAT Control",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Net VAT position (Output - Input)",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2200",
        "name": "PAYE Payable",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Employee tax deducted - payable to SARS",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2210",
        "name": "UIF Payable",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "UIF contributions payable",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2220",
        "name": "SDL Payable",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Skills Development Levy payable",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2300",
        "name": "Accrued Expenses",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Expenses incurred but not yet paid",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2310",
        "name": "Salaries Payable",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Salaries earned but not yet paid",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2400",
        "name": "Short-term Loans",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Loans payable within 12 months",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2410",
        "name": "Bank Overdraft",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Bank overdraft facility",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2420",
        "name": "Credit Card",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Business credit card balance",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2450",
        "name": "Income Received in Advance",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.CURRENT_LIABILITY,
        "description": "Payments received for services not yet rendered",
        "vat_applicable": False,
        "system_account": False
    },
    
    # Long-term Liabilities (2500-2999)
    {
        "code": "2500",
        "name": "Long-term Loans",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.LONG_TERM_LIABILITY,
        "description": "Loans payable after 12 months",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2510",
        "name": "Vehicle Finance",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.LONG_TERM_LIABILITY,
        "description": "Finance agreements on vehicles",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2520",
        "name": "Equipment Finance",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.LONG_TERM_LIABILITY,
        "description": "Finance agreements on equipment",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2600",
        "name": "Mortgage Bond",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.LONG_TERM_LIABILITY,
        "description": "Property mortgage",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "2700",
        "name": "Shareholder Loan",
        "type": AccountType.LIABILITY,
        "category": AccountCategory.LONG_TERM_LIABILITY,
        "description": "Loans from shareholders/directors",
        "vat_applicable": False,
        "system_account": False
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EQUITY (3000-3999)
    # ═══════════════════════════════════════════════════════════════════════════
    
    {
        "code": "3000",
        "name": "Share Capital / Owner's Capital",
        "type": AccountType.EQUITY,
        "category": AccountCategory.CAPITAL,
        "description": "Capital invested by owners",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "3010",
        "name": "Share Premium",
        "type": AccountType.EQUITY,
        "category": AccountCategory.CAPITAL,
        "description": "Premium received on share issue",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "3100",
        "name": "Retained Earnings",
        "type": AccountType.EQUITY,
        "category": AccountCategory.RETAINED_EARNINGS,
        "description": "Accumulated profits from prior years",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "3200",
        "name": "Current Year Earnings",
        "type": AccountType.EQUITY,
        "category": AccountCategory.RETAINED_EARNINGS,
        "description": "Profit/loss for current financial year",
        "vat_applicable": False,
        "system_account": True
    },
    {
        "code": "3300",
        "name": "Drawings",
        "type": AccountType.EQUITY,
        "category": AccountCategory.CAPITAL,
        "description": "Amounts withdrawn by owner",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True  # Reduces equity
    },
    {
        "code": "3400",
        "name": "Dividends",
        "type": AccountType.EQUITY,
        "category": AccountCategory.RETAINED_EARNINGS,
        "description": "Dividends declared",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REVENUE / INCOME (4000-4999)
    # ═══════════════════════════════════════════════════════════════════════════
    
    {
        "code": "4000",
        "name": "Sales - Goods",
        "type": AccountType.REVENUE,
        "category": AccountCategory.SALES,
        "description": "Revenue from sale of goods",
        "vat_applicable": True,
        "system_account": True
    },
    {
        "code": "4010",
        "name": "Sales - Services",
        "type": AccountType.REVENUE,
        "category": AccountCategory.SALES,
        "description": "Revenue from services rendered",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "4020",
        "name": "Sales - Other",
        "type": AccountType.REVENUE,
        "category": AccountCategory.SALES,
        "description": "Other sales revenue",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "4050",
        "name": "Sales Returns",
        "type": AccountType.REVENUE,
        "category": AccountCategory.SALES,
        "description": "Goods returned by customers",
        "vat_applicable": True,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "4060",
        "name": "Sales Discounts",
        "type": AccountType.REVENUE,
        "category": AccountCategory.SALES,
        "description": "Discounts given to customers",
        "vat_applicable": True,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "4100",
        "name": "Discount Received",
        "type": AccountType.REVENUE,
        "category": AccountCategory.OTHER_INCOME,
        "description": "Discounts received from suppliers",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "4200",
        "name": "Interest Received",
        "type": AccountType.REVENUE,
        "category": AccountCategory.OTHER_INCOME,
        "description": "Interest earned on bank accounts",
        "vat_applicable": False,  # Interest is exempt from VAT
        "system_account": False
    },
    {
        "code": "4300",
        "name": "Rental Income",
        "type": AccountType.REVENUE,
        "category": AccountCategory.OTHER_INCOME,
        "description": "Income from property rental",
        "vat_applicable": True,  # Commercial rental is VATable
        "system_account": False
    },
    {
        "code": "4400",
        "name": "Commission Received",
        "type": AccountType.REVENUE,
        "category": AccountCategory.OTHER_INCOME,
        "description": "Commission earned",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "4500",
        "name": "Bad Debts Recovered",
        "type": AccountType.REVENUE,
        "category": AccountCategory.OTHER_INCOME,
        "description": "Previously written off debts collected",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "4600",
        "name": "Profit on Sale of Assets",
        "type": AccountType.REVENUE,
        "category": AccountCategory.OTHER_INCOME,
        "description": "Profit from selling fixed assets",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "4900",
        "name": "Other Income",
        "type": AccountType.REVENUE,
        "category": AccountCategory.OTHER_INCOME,
        "description": "Miscellaneous income",
        "vat_applicable": True,
        "system_account": False
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COST OF SALES (5000-5999)
    # ═══════════════════════════════════════════════════════════════════════════
    
    {
        "code": "5000",
        "name": "Cost of Goods Sold",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Cost of goods sold to customers",
        "vat_applicable": False,  # Already accounted for on purchase
        "system_account": True
    },
    {
        "code": "5010",
        "name": "Opening Stock",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Stock at beginning of period",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "5020",
        "name": "Purchases",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Goods purchased for resale",
        "vat_applicable": True,
        "system_account": True
    },
    {
        "code": "5025",
        "name": "Purchase Returns",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Goods returned to suppliers",
        "vat_applicable": True,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "5030",
        "name": "Closing Stock",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Stock at end of period",
        "vat_applicable": False,
        "system_account": False,
        "contra_account": True
    },
    {
        "code": "5040",
        "name": "Carriage Inward",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Freight and delivery costs on purchases",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "5050",
        "name": "Import Duties",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Customs and import duties",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "5100",
        "name": "Direct Labour",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Labour directly involved in production",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "5200",
        "name": "Subcontractors",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Subcontracted work",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "5300",
        "name": "Manufacturing Overheads",
        "type": AccountType.COST_OF_SALES,
        "category": AccountCategory.DIRECT_COSTS,
        "description": "Factory overheads allocated to production",
        "vat_applicable": False,
        "system_account": False
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPERATING EXPENSES (6000-6999)
    # ═══════════════════════════════════════════════════════════════════════════
    
    {
        "code": "6000",
        "name": "Accounting Fees",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.ADMINISTRATIVE_EXPENSE,
        "description": "Fees paid to accountants",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6010",
        "name": "Advertising & Marketing",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Advertising, marketing, promotions",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6020",
        "name": "Bad Debts",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Irrecoverable customer debts written off",
        "vat_applicable": False,  # VAT already claimed on original sale
        "system_account": False
    },
    {
        "code": "6030",
        "name": "Bank Charges",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.FINANCIAL_EXPENSE,
        "description": "Bank fees and charges",
        "vat_applicable": False,  # Bank charges are exempt
        "system_account": True
    },
    {
        "code": "6040",
        "name": "Cleaning",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Cleaning services and supplies",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6050",
        "name": "Computer Expenses",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Software, IT support, computer supplies",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6060",
        "name": "Consulting Fees",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.ADMINISTRATIVE_EXPENSE,
        "description": "Fees paid to consultants",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6070",
        "name": "Consumables",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "General consumable items",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6080",
        "name": "Depreciation",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Depreciation on fixed assets",
        "vat_applicable": False,  # Non-cash expense
        "system_account": True
    },
    {
        "code": "6090",
        "name": "Electricity & Water",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Utilities - electricity and water",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6100",
        "name": "Entertainment",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Client entertainment, meals",
        "vat_applicable": True,  # But only 50% deductible for tax
        "system_account": False
    },
    {
        "code": "6110",
        "name": "Equipment Hire",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Rental of equipment",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6120",
        "name": "Fines & Penalties",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Traffic fines, penalties (non-deductible)",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "6130",
        "name": "Fuel & Oil",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Petrol, diesel for vehicles",
        "vat_applicable": False,  # Zero-rated
        "system_account": True,
        "zero_rated": True
    },
    {
        "code": "6140",
        "name": "General Expenses",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Miscellaneous expenses",
        "vat_applicable": True,
        "system_account": True
    },
    {
        "code": "6150",
        "name": "Insurance",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Business insurance premiums",
        "vat_applicable": False,  # Insurance is exempt
        "system_account": False
    },
    {
        "code": "6160",
        "name": "Interest Paid",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.FINANCIAL_EXPENSE,
        "description": "Interest on loans and overdrafts",
        "vat_applicable": False,  # Interest is exempt
        "system_account": False
    },
    {
        "code": "6170",
        "name": "Internet & Telephone",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Telephone, internet, data costs",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6180",
        "name": "Legal Fees",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.ADMINISTRATIVE_EXPENSE,
        "description": "Fees paid to attorneys",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6190",
        "name": "Licences & Permits",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.ADMINISTRATIVE_EXPENSE,
        "description": "Business licences and permits",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6200",
        "name": "Motor Vehicle Expenses",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Vehicle maintenance, repairs, licence fees",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6210",
        "name": "Office Supplies",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Stationery, office consumables",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6220",
        "name": "Postage & Courier",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Postage, courier services",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6230",
        "name": "Printing & Stationery",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Printing, stationery purchases",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6240",
        "name": "Protective Clothing",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Safety gear, uniforms for staff",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6250",
        "name": "Rent",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Office/premises rental",
        "vat_applicable": True,  # Commercial rent is VATable
        "system_account": False
    },
    {
        "code": "6260",
        "name": "Repairs & Maintenance",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Repairs and maintenance",
        "vat_applicable": True,
        "system_account": True
    },
    {
        "code": "6270",
        "name": "Salaries & Wages",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Staff salaries and wages",
        "vat_applicable": False,  # Salaries are not subject to VAT
        "system_account": True
    },
    {
        "code": "6280",
        "name": "PAYE Expense",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Employer portion of PAYE",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "6290",
        "name": "UIF Expense",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Employer UIF contribution",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "6300",
        "name": "SDL Expense",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Skills Development Levy",
        "vat_applicable": False,
        "system_account": False
    },
    {
        "code": "6310",
        "name": "Staff Welfare",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Staff refreshments, welfare",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6320",
        "name": "Security",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Security services",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6330",
        "name": "Subscriptions",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Magazine, professional subscriptions",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6340",
        "name": "Training",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Staff training and courses",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6350",
        "name": "Travel & Accommodation",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Business travel, accommodation",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6360",
        "name": "Uniforms",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Staff uniforms",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6370",
        "name": "Waste Removal",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Refuse removal, waste disposal",
        "vat_applicable": True,
        "system_account": False
    },
    {
        "code": "6900",
        "name": "Loss on Sale of Assets",
        "type": AccountType.EXPENSE,
        "category": AccountCategory.OPERATING_EXPENSE,
        "description": "Loss from selling fixed assets",
        "vat_applicable": False,
        "system_account": False
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class Account:
    """
    Account class for managing chart of accounts
    """
    
    TABLE = "accounts"
    
    @classmethod
    def get_all(cls, active_only: bool = True) -> List[dict]:
        """Get all accounts"""
        filters = {"active": True} if active_only else None
        return db.select(cls.TABLE, filters, order="code")
    
    @classmethod
    def get_by_code(cls, code: str) -> Optional[dict]:
        """Get account by code"""
        results = db.select(cls.TABLE, {"code": code}, limit=1)
        return results[0] if results else None
    
    @classmethod
    def get_by_type(cls, account_type: AccountType) -> List[dict]:
        """Get all accounts of a specific type"""
        return db.select(cls.TABLE, {"type": account_type.value}, order="code")
    
    @classmethod
    def get_by_category(cls, category: AccountCategory) -> List[dict]:
        """Get all accounts in a specific category"""
        return db.select(cls.TABLE, {"category": category.value}, order="code")
    
    @classmethod
    def get_expense_accounts(cls) -> List[dict]:
        """Get all expense accounts for dropdown"""
        return db.select(cls.TABLE, {"type": AccountType.EXPENSE.value}, order="code")
    
    @classmethod
    def get_income_accounts(cls) -> List[dict]:
        """Get all income accounts"""
        return db.select(cls.TABLE, {"type": AccountType.REVENUE.value}, order="code")
    
    @classmethod
    def create(cls, code: str, name: str, account_type: AccountType, 
               category: AccountCategory, **kwargs) -> tuple:
        """Create a new account"""
        data = {
            "id": generate_id(),
            "code": code,
            "name": name,
            "type": account_type.value,
            "category": category.value,
            "description": kwargs.get("description", ""),
            "vat_applicable": kwargs.get("vat_applicable", True),
            "system_account": kwargs.get("system_account", False),
            "contra_account": kwargs.get("contra_account", False),
            "active": True,
            "created_at": now()
        }
        return db.insert(cls.TABLE, data)
    
    @classmethod
    def deactivate(cls, code: str) -> tuple:
        """Deactivate an account (don't delete, preserve history)"""
        account = cls.get_by_code(code)
        if account:
            if account.get("system_account"):
                return False, "Cannot deactivate system account"
            return db.update(cls.TABLE, account["id"], {"active": False})
        return False, "Account not found"
    
    @classmethod
    def initialize_chart(cls, force: bool = False) -> dict:
        """
        Initialize the standard chart of accounts
        
        Args:
            force: If True, recreate all accounts (use with caution)
            
        Returns:
            Dict with counts of accounts created/skipped
        """
        created = 0
        skipped = 0
        errors = []
        
        for account_def in STANDARD_CHART_OF_ACCOUNTS:
            # Check if account already exists
            existing = cls.get_by_code(account_def["code"])
            
            if existing and not force:
                skipped += 1
                continue
            
            data = {
                "id": generate_id(),
                "code": account_def["code"],
                "name": account_def["name"],
                "type": account_def["type"].value,
                "category": account_def["category"].value,
                "description": account_def.get("description", ""),
                "vat_applicable": account_def.get("vat_applicable", True),
                "system_account": account_def.get("system_account", False),
                "contra_account": account_def.get("contra_account", False),
                "zero_rated": account_def.get("zero_rated", False),
                "depreciable": account_def.get("depreciable", False),
                "depreciation_rate": str(account_def.get("depreciation_rate", 0)),
                "active": True,
                "created_at": now()
            }
            
            if existing and force:
                # Update existing
                success, result = db.update(cls.TABLE, existing["id"], data)
            else:
                # Create new
                success, result = db.insert(cls.TABLE, data)
            
            if success:
                created += 1
            else:
                errors.append(f"{account_def['code']}: {result}")
        
        return {
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "total": len(STANDARD_CHART_OF_ACCOUNTS)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNT LOOKUP HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class AccountCodes:
    """
    Quick lookup for common account codes
    Used throughout the system for journal posting
    """
    
    # Assets
    BANK = "1000"
    PETTY_CASH = "1020"
    DEBTORS = "1100"
    STOCK = "1200"
    
    # Liabilities
    CREDITORS = "2000"
    VAT_OUTPUT = "2100"
    VAT_INPUT = "2110"
    
    # Equity
    CAPITAL = "3000"
    RETAINED_EARNINGS = "3100"
    CURRENT_YEAR_EARNINGS = "3200"
    DRAWINGS = "3300"
    
    # Revenue
    SALES = "4000"
    
    # Cost of Sales
    COGS = "5000"
    PURCHASES = "5020"
    
    # Common Expenses
    BANK_CHARGES = "6030"
    FUEL = "6130"
    GENERAL_EXPENSES = "6140"
    REPAIRS = "6260"
    SALARIES = "6270"


def get_account_code(name_or_code: str) -> str:
    """
    Get account code from name or code
    Useful for flexible input
    """
    # If it looks like a code already, return it
    if name_or_code.isdigit() and len(name_or_code) == 4:
        return name_or_code
    
    # Search by name
    accounts = Account.get_all()
    name_lower = name_or_code.lower()
    
    for acc in accounts:
        if acc["name"].lower() == name_lower:
            return acc["code"]
        if name_lower in acc["name"].lower():
            return acc["code"]
    
    # Default to general expenses if not found
    return AccountCodes.GENERAL_EXPENSES


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 2
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 2 COMPLETE - Chart of Accounts

Contains:
✓ Account types (Asset, Liability, Equity, Revenue, Cost of Sales, Expense)
✓ Account categories for report grouping
✓ Complete SA SME Chart of Accounts (80+ accounts)
✓ Proper VAT flags (standard, zero-rated, exempt)
✓ Depreciation rates for fixed assets
✓ System accounts that cannot be deleted
✓ Contra accounts (accumulated depreciation, drawings, etc.)
✓ Account class with CRUD operations
✓ Chart initialization function
✓ Quick lookup helpers (AccountCodes class)

Account Ranges:
- 1000-1999: Assets
- 2000-2999: Liabilities  
- 3000-3999: Equity
- 4000-4999: Revenue
- 5000-5999: Cost of Sales
- 6000-6999: Operating Expenses

Next: Piece 3 - Journal Engine (double-entry posting)
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 3: Journal Engine                                                     ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Double-entry journal posting                                              ║
║   - Transaction validation                                                    ║
║   - Account balance calculations                                              ║
║   - Transaction templates for common operations                               ║
║   - Audit trail                                                               ║
║                                                                               ║
║   RULE: Every debit must have an equal credit                                 ║
║   Flask does ALL calculations - no JavaScript math                            ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from enum import Enum

from piece1_core import db, generate_id, now, today, Money, VAT, safe_string
from piece2_accounts import Account, AccountCodes, AccountType, get_account_code


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSACTION TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class TransactionType(Enum):
    """Types of transactions for categorization and reporting"""
    SALE = "sale"
    SALE_RETURN = "sale_return"
    PURCHASE = "purchase"
    PURCHASE_RETURN = "purchase_return"
    EXPENSE = "expense"
    RECEIPT = "receipt"
    PAYMENT = "payment"
    TRANSFER = "transfer"
    JOURNAL = "journal"
    OPENING = "opening"
    CLOSING = "closing"
    DEPRECIATION = "depreciation"
    ADJUSTMENT = "adjustment"


# ═══════════════════════════════════════════════════════════════════════════════
# JOURNAL LINE
# ═══════════════════════════════════════════════════════════════════════════════

class JournalLine:
    """Single line in a journal entry"""
    
    def __init__(self, account_code: str, debit: Decimal = None, 
                 credit: Decimal = None, description: str = ""):
        self.account_code = account_code
        self.debit = Decimal(str(debit or 0)).quantize(Decimal("0.01"))
        self.credit = Decimal(str(credit or 0)).quantize(Decimal("0.01"))
        self.description = description
    
    def to_dict(self) -> dict:
        return {
            "account_code": self.account_code,
            "debit": float(self.debit),
            "credit": float(self.credit),
            "description": self.description
        }


# ═══════════════════════════════════════════════════════════════════════════════
# JOURNAL ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

class JournalEntry:
    """
    Complete journal entry with header and lines
    
    Usage:
        entry = JournalEntry(date="2024-01-15", description="Cash sale")
        entry.debit("1000", 1150)  # Bank
        entry.credit("4000", 1000) # Sales
        entry.credit("2100", 150)  # VAT Output
        entry.post()
    """
    
    TABLE = "journal"
    
    def __init__(self, date: str = None, reference: str = "", 
                 description: str = "", trans_type: TransactionType = TransactionType.JOURNAL,
                 source_type: str = "", source_id: str = ""):
        self.id = generate_id()
        self.date = date or today()
        self.reference = reference
        self.description = description
        self.trans_type = trans_type
        self.source_type = source_type  # e.g., "invoice", "expense"
        self.source_id = source_id      # Link back to source document
        self.lines: List[JournalLine] = []
        self.created_at = now()
        self.created_by = None
        self.posted = False
    
    def debit(self, account_code: str, amount, description: str = "") -> 'JournalEntry':
        """Add a debit line"""
        amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount > 0:
            self.lines.append(JournalLine(
                account_code=account_code,
                debit=amount,
                credit=Decimal("0"),
                description=description or self.description
            ))
        return self
    
    def credit(self, account_code: str, amount, description: str = "") -> 'JournalEntry':
        """Add a credit line"""
        amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if amount > 0:
            self.lines.append(JournalLine(
                account_code=account_code,
                debit=Decimal("0"),
                credit=amount,
                description=description or self.description
            ))
        return self
    
    def total_debits(self) -> Decimal:
        """Sum of all debits"""
        return sum(line.debit for line in self.lines)
    
    def total_credits(self) -> Decimal:
        """Sum of all credits"""
        return sum(line.credit for line in self.lines)
    
    def is_balanced(self) -> bool:
        """Check if debits equal credits"""
        diff = abs(self.total_debits() - self.total_credits())
        return diff < Decimal("0.01")
    
    def validate(self) -> Tuple[bool, str]:
        """
        Validate the journal entry
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.lines:
            return False, "Journal entry has no lines"
        
        if not self.date:
            return False, "Journal entry has no date"
        
        if not self.is_balanced():
            diff = self.total_debits() - self.total_credits()
            return False, f"Entry not balanced. Difference: {Money.format(diff)}"
        
        # Validate each line
        for i, line in enumerate(self.lines):
            if line.debit == 0 and line.credit == 0:
                return False, f"Line {i+1} has no amount"
            
            if line.debit > 0 and line.credit > 0:
                return False, f"Line {i+1} has both debit and credit"
            
            # Check account exists
            account = Account.get_by_code(line.account_code)
            if not account:
                return False, f"Account {line.account_code} not found"
            
            if not account.get("active", True):
                return False, f"Account {line.account_code} is inactive"
        
        return True, ""
    
    def post(self, user_id: str = None) -> Tuple[bool, str]:
        """
        Post the journal entry to the database
        
        Returns:
            Tuple of (success, message or entry_id)
        """
        # Validate first
        is_valid, error = self.validate()
        if not is_valid:
            return False, error
        
        self.created_by = user_id
        self.posted = True
        
        # Save each line to the journal table
        for line in self.lines:
            record = {
                "id": generate_id(),
                "entry_id": self.id,
                "date": self.date,
                "account_code": line.account_code,
                "description": safe_string(line.description, 500),
                "reference": safe_string(self.reference, 100),
                "debit": float(line.debit),
                "credit": float(line.credit),
                "trans_type": self.trans_type.value,
                "source_type": self.source_type,
                "source_id": self.source_id,
                "created_at": self.created_at,
                "created_by": self.created_by
            }
            
            success, result = db.insert(self.TABLE, record)
            if not success:
                return False, f"Failed to post line: {result}"
        
        return True, self.id


# ═══════════════════════════════════════════════════════════════════════════════
# JOURNAL QUERIES
# ═══════════════════════════════════════════════════════════════════════════════

class Journal:
    """Query and reporting functions for the journal"""
    
    TABLE = "journal"
    
    @classmethod
    def get_entries(cls, date_from: str = None, date_to: str = None,
                    account_code: str = None, trans_type: str = None,
                    limit: int = 1000) -> List[dict]:
        """
        Get journal entries with optional filters
        """
        # Build query
        entries = db.select(cls.TABLE, order="-date", limit=limit)
        
        # Apply filters (Supabase filtering would be more efficient)
        if date_from:
            entries = [e for e in entries if e.get("date", "") >= date_from]
        if date_to:
            entries = [e for e in entries if e.get("date", "") <= date_to]
        if account_code:
            entries = [e for e in entries if e.get("account_code") == account_code]
        if trans_type:
            entries = [e for e in entries if e.get("trans_type") == trans_type]
        
        return entries
    
    @classmethod
    def get_account_balance(cls, account_code: str, as_at: str = None) -> Decimal:
        """
        Calculate account balance
        
        For Asset/Expense accounts: Debits - Credits
        For Liability/Equity/Revenue accounts: Credits - Debits
        """
        entries = cls.get_entries(account_code=account_code)
        
        if as_at:
            entries = [e for e in entries if e.get("date", "") <= as_at]
        
        total_debits = sum(Decimal(str(e.get("debit", 0))) for e in entries)
        total_credits = sum(Decimal(str(e.get("credit", 0))) for e in entries)
        
        # Get account type to determine balance direction
        account = Account.get_by_code(account_code)
        if account:
            acc_type = account.get("type")
            # Debit-balance accounts: Assets, Expenses, Cost of Sales
            if acc_type in ["asset", "expense", "cost_of_sales"]:
                return total_debits - total_credits
            # Credit-balance accounts: Liabilities, Equity, Revenue
            else:
                return total_credits - total_debits
        
        return total_debits - total_credits
    
    @classmethod
    def get_account_movement(cls, account_code: str, 
                            date_from: str, date_to: str) -> dict:
        """
        Get account movement for a period
        
        Returns dict with opening, debits, credits, closing
        """
        # Opening balance (everything before date_from)
        opening = cls.get_account_balance(account_code, as_at=date_from)
        
        # Period transactions
        entries = cls.get_entries(
            account_code=account_code,
            date_from=date_from,
            date_to=date_to
        )
        
        debits = sum(Decimal(str(e.get("debit", 0))) for e in entries)
        credits = sum(Decimal(str(e.get("credit", 0))) for e in entries)
        
        # Closing balance
        closing = cls.get_account_balance(account_code, as_at=date_to)
        
        return {
            "account_code": account_code,
            "opening": opening,
            "debits": debits,
            "credits": credits,
            "closing": closing
        }
    
    @classmethod
    def get_trial_balance(cls, as_at: str = None) -> List[dict]:
        """
        Generate trial balance
        
        Returns list of accounts with debit and credit balances
        """
        accounts = Account.get_all(active_only=False)
        trial_balance = []
        
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        
        for account in accounts:
            balance = cls.get_account_balance(account["code"], as_at=as_at)
            
            if balance == 0:
                continue  # Skip zero-balance accounts
            
            entry = {
                "code": account["code"],
                "name": account["name"],
                "type": account["type"],
                "category": account["category"],
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "balance": balance
            }
            
            # Determine which column based on account type and balance
            acc_type = account["type"]
            if acc_type in ["asset", "expense", "cost_of_sales"]:
                if balance >= 0:
                    entry["debit"] = balance
                    total_debits += balance
                else:
                    entry["credit"] = abs(balance)
                    total_credits += abs(balance)
            else:  # liability, equity, revenue
                if balance >= 0:
                    entry["credit"] = balance
                    total_credits += balance
                else:
                    entry["debit"] = abs(balance)
                    total_debits += abs(balance)
            
            trial_balance.append(entry)
        
        # Sort by account code
        trial_balance.sort(key=lambda x: x["code"])
        
        # Add totals row
        trial_balance.append({
            "code": "",
            "name": "TOTAL",
            "type": "",
            "category": "",
            "debit": total_debits,
            "credit": total_credits,
            "balance": total_debits - total_credits,
            "is_total": True
        })
        
        return trial_balance
    
    @classmethod
    def get_income_statement(cls, date_from: str, date_to: str) -> dict:
        """
        Generate Income Statement (Profit & Loss)
        
        Revenue - Cost of Sales = Gross Profit
        Gross Profit - Expenses = Net Profit
        """
        result = {
            "period_from": date_from,
            "period_to": date_to,
            "revenue": [],
            "cost_of_sales": [],
            "expenses": [],
            "total_revenue": Decimal("0"),
            "total_cost_of_sales": Decimal("0"),
            "gross_profit": Decimal("0"),
            "total_expenses": Decimal("0"),
            "net_profit": Decimal("0")
        }
        
        accounts = Account.get_all()
        
        for account in accounts:
            movement = cls.get_account_movement(
                account["code"], date_from, date_to
            )
            
            # Calculate period activity (not balance)
            # Revenue: Credits - Debits (income increases with credits)
            # Expenses: Debits - Credits (expenses increase with debits)
            
            acc_type = account["type"]
            
            if acc_type == "revenue":
                amount = movement["credits"] - movement["debits"]
                if amount != 0:
                    result["revenue"].append({
                        "code": account["code"],
                        "name": account["name"],
                        "amount": amount
                    })
                    result["total_revenue"] += amount
            
            elif acc_type == "cost_of_sales":
                amount = movement["debits"] - movement["credits"]
                if amount != 0:
                    result["cost_of_sales"].append({
                        "code": account["code"],
                        "name": account["name"],
                        "amount": amount
                    })
                    result["total_cost_of_sales"] += amount
            
            elif acc_type == "expense":
                amount = movement["debits"] - movement["credits"]
                if amount != 0:
                    result["expenses"].append({
                        "code": account["code"],
                        "name": account["name"],
                        "amount": amount
                    })
                    result["total_expenses"] += amount
        
        # Sort each section by amount (descending)
        result["revenue"].sort(key=lambda x: x["amount"], reverse=True)
        result["cost_of_sales"].sort(key=lambda x: x["amount"], reverse=True)
        result["expenses"].sort(key=lambda x: x["amount"], reverse=True)
        
        # Calculate profits
        result["gross_profit"] = result["total_revenue"] - result["total_cost_of_sales"]
        result["net_profit"] = result["gross_profit"] - result["total_expenses"]
        
        return result
    
    @classmethod
    def get_balance_sheet(cls, as_at: str = None) -> dict:
        """
        Generate Balance Sheet
        
        Assets = Liabilities + Equity
        """
        if not as_at:
            as_at = today()
        
        result = {
            "as_at": as_at,
            "current_assets": [],
            "fixed_assets": [],
            "current_liabilities": [],
            "long_term_liabilities": [],
            "equity": [],
            "total_current_assets": Decimal("0"),
            "total_fixed_assets": Decimal("0"),
            "total_assets": Decimal("0"),
            "total_current_liabilities": Decimal("0"),
            "total_long_term_liabilities": Decimal("0"),
            "total_liabilities": Decimal("0"),
            "total_equity": Decimal("0"),
            "total_liab_equity": Decimal("0")
        }
        
        accounts = Account.get_all()
        
        for account in accounts:
            balance = cls.get_account_balance(account["code"], as_at=as_at)
            
            if balance == 0:
                continue
            
            entry = {
                "code": account["code"],
                "name": account["name"],
                "balance": balance
            }
            
            acc_type = account["type"]
            category = account.get("category", "")
            
            if acc_type == "asset":
                if category == "current_asset":
                    result["current_assets"].append(entry)
                    result["total_current_assets"] += balance
                else:
                    result["fixed_assets"].append(entry)
                    result["total_fixed_assets"] += balance
            
            elif acc_type == "liability":
                if category in ["current_liability"]:
                    result["current_liabilities"].append(entry)
                    result["total_current_liabilities"] += balance
                else:
                    result["long_term_liabilities"].append(entry)
                    result["total_long_term_liabilities"] += balance
            
            elif acc_type == "equity":
                result["equity"].append(entry)
                result["total_equity"] += balance
        
        # Calculate totals
        result["total_assets"] = result["total_current_assets"] + result["total_fixed_assets"]
        result["total_liabilities"] = result["total_current_liabilities"] + result["total_long_term_liabilities"]
        result["total_liab_equity"] = result["total_liabilities"] + result["total_equity"]
        
        return result
    
    @classmethod
    def get_vat_report(cls, date_from: str, date_to: str) -> dict:
        """
        Generate VAT Report
        
        Output VAT (collected on sales) - Input VAT (paid on purchases)
        """
        # Get VAT Output (what we collected)
        vat_output = cls.get_account_movement(
            AccountCodes.VAT_OUTPUT, date_from, date_to
        )
        
        # Get VAT Input (what we paid)
        vat_input = cls.get_account_movement(
            AccountCodes.VAT_INPUT, date_from, date_to
        )
        
        # Output VAT is a liability - credits increase it
        output_amount = vat_output["credits"] - vat_output["debits"]
        
        # Input VAT is contra-liability - debits increase it
        input_amount = vat_input["debits"] - vat_input["credits"]
        
        # Net VAT position
        net_vat = output_amount - input_amount
        
        return {
            "period_from": date_from,
            "period_to": date_to,
            "output_vat": output_amount,
            "input_vat": input_amount,
            "net_vat": net_vat,
            "payable_to_sars": net_vat if net_vat > 0 else Decimal("0"),
            "refund_due": abs(net_vat) if net_vat < 0 else Decimal("0")
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSACTION TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════════

class Transactions:
    """
    Pre-built transaction templates for common operations
    
    These ensure correct double-entry posting for standard transactions.
    All VAT calculations are done by Flask.
    """
    
    @staticmethod
    def cash_sale(amount_incl_vat: Decimal, description: str = "Cash sale",
                  reference: str = "", is_zero_rated: bool = False) -> JournalEntry:
        """
        Record a cash sale
        
        DR Bank (total including VAT)
            CR Sales (excluding VAT)
            CR VAT Output (VAT amount) - unless zero-rated
        """
        amount = Decimal(str(amount_incl_vat))
        
        if is_zero_rated:
            vat_info = VAT.calculate_from_inclusive(amount, VAT.ZERO_RATE)
        else:
            vat_info = VAT.calculate_from_inclusive(amount)
        
        entry = JournalEntry(
            description=description,
            reference=reference,
            trans_type=TransactionType.SALE
        )
        
        entry.debit(AccountCodes.BANK, vat_info["inclusive"])
        entry.credit(AccountCodes.SALES, vat_info["exclusive"])
        
        if vat_info["vat"] > 0:
            entry.credit(AccountCodes.VAT_OUTPUT, vat_info["vat"])
        
        return entry
    
    @staticmethod
    def credit_sale(customer_id: str, amount_incl_vat: Decimal, 
                   description: str = "Credit sale", reference: str = "",
                   is_zero_rated: bool = False) -> JournalEntry:
        """
        Record a sale on account
        
        DR Debtors (total including VAT)
            CR Sales (excluding VAT)
            CR VAT Output (VAT amount)
        """
        amount = Decimal(str(amount_incl_vat))
        
        if is_zero_rated:
            vat_info = VAT.calculate_from_inclusive(amount, VAT.ZERO_RATE)
        else:
            vat_info = VAT.calculate_from_inclusive(amount)
        
        entry = JournalEntry(
            description=description,
            reference=reference,
            trans_type=TransactionType.SALE,
            source_type="customer",
            source_id=customer_id
        )
        
        entry.debit(AccountCodes.DEBTORS, vat_info["inclusive"])
        entry.credit(AccountCodes.SALES, vat_info["exclusive"])
        
        if vat_info["vat"] > 0:
            entry.credit(AccountCodes.VAT_OUTPUT, vat_info["vat"])
        
        return entry
    
    @staticmethod
    def receive_payment(customer_id: str, amount: Decimal,
                       description: str = "Payment received",
                       reference: str = "") -> JournalEntry:
        """
        Record payment received from customer
        
        DR Bank
            CR Debtors
        """
        entry = JournalEntry(
            description=description,
            reference=reference,
            trans_type=TransactionType.RECEIPT,
            source_type="customer",
            source_id=customer_id
        )
        
        entry.debit(AccountCodes.BANK, amount)
        entry.credit(AccountCodes.DEBTORS, amount)
        
        return entry
    
    @staticmethod
    def cash_expense(amount_incl_vat: Decimal, expense_account: str,
                    description: str = "", reference: str = "",
                    vat_type: str = "standard") -> JournalEntry:
        """
        Record a cash expense
        
        DR Expense account (excluding VAT)
        DR VAT Input (VAT amount) - if applicable
            CR Bank (total)
        
        vat_type: "standard", "zero", "exempt"
        """
        amount = Decimal(str(amount_incl_vat))
        
        if vat_type == "zero":
            vat_info = VAT.calculate_from_inclusive(amount, VAT.ZERO_RATE)
        elif vat_type == "exempt":
            # No VAT to claim
            vat_info = {"exclusive": amount, "vat": Decimal("0"), "inclusive": amount}
        else:
            vat_info = VAT.calculate_from_inclusive(amount)
        
        entry = JournalEntry(
            description=description,
            reference=reference,
            trans_type=TransactionType.EXPENSE
        )
        
        entry.debit(expense_account, vat_info["exclusive"])
        
        if vat_info["vat"] > 0:
            entry.debit(AccountCodes.VAT_INPUT, vat_info["vat"])
        
        entry.credit(AccountCodes.BANK, vat_info["inclusive"])
        
        return entry
    
    @staticmethod
    def credit_expense(supplier_id: str, amount_incl_vat: Decimal,
                      expense_account: str, description: str = "",
                      reference: str = "", vat_type: str = "standard") -> JournalEntry:
        """
        Record an expense on credit
        
        DR Expense account (excluding VAT)
        DR VAT Input (VAT amount) - if applicable
            CR Creditors (total)
        """
        amount = Decimal(str(amount_incl_vat))
        
        if vat_type == "zero":
            vat_info = VAT.calculate_from_inclusive(amount, VAT.ZERO_RATE)
        elif vat_type == "exempt":
            vat_info = {"exclusive": amount, "vat": Decimal("0"), "inclusive": amount}
        else:
            vat_info = VAT.calculate_from_inclusive(amount)
        
        entry = JournalEntry(
            description=description,
            reference=reference,
            trans_type=TransactionType.EXPENSE,
            source_type="supplier",
            source_id=supplier_id
        )
        
        entry.debit(expense_account, vat_info["exclusive"])
        
        if vat_info["vat"] > 0:
            entry.debit(AccountCodes.VAT_INPUT, vat_info["vat"])
        
        entry.credit(AccountCodes.CREDITORS, vat_info["inclusive"])
        
        return entry
    
    @staticmethod
    def pay_supplier(supplier_id: str, amount: Decimal,
                    description: str = "Payment to supplier",
                    reference: str = "") -> JournalEntry:
        """
        Record payment to supplier
        
        DR Creditors
            CR Bank
        """
        entry = JournalEntry(
            description=description,
            reference=reference,
            trans_type=TransactionType.PAYMENT,
            source_type="supplier",
            source_id=supplier_id
        )
        
        entry.debit(AccountCodes.CREDITORS, amount)
        entry.credit(AccountCodes.BANK, amount)
        
        return entry
    
    @staticmethod
    def stock_purchase(amount_incl_vat: Decimal, description: str = "Stock purchase",
                      reference: str = "", is_zero_rated: bool = False) -> JournalEntry:
        """
        Record stock/inventory purchase for cash
        
        DR Stock (excluding VAT)
        DR VAT Input (VAT amount)
            CR Bank (total)
        """
        amount = Decimal(str(amount_incl_vat))
        
        if is_zero_rated:
            vat_info = VAT.calculate_from_inclusive(amount, VAT.ZERO_RATE)
        else:
            vat_info = VAT.calculate_from_inclusive(amount)
        
        entry = JournalEntry(
            description=description,
            reference=reference,
            trans_type=TransactionType.PURCHASE
        )
        
        entry.debit(AccountCodes.STOCK, vat_info["exclusive"])
        
        if vat_info["vat"] > 0:
            entry.debit(AccountCodes.VAT_INPUT, vat_info["vat"])
        
        entry.credit(AccountCodes.BANK, vat_info["inclusive"])
        
        return entry
    
    @staticmethod
    def record_cost_of_sale(cost_amount: Decimal, 
                           description: str = "Cost of goods sold") -> JournalEntry:
        """
        Record cost of goods sold (when stock is sold)
        
        DR Cost of Goods Sold
            CR Stock
        """
        entry = JournalEntry(
            description=description,
            trans_type=TransactionType.SALE
        )
        
        entry.debit(AccountCodes.COGS, cost_amount)
        entry.credit(AccountCodes.STOCK, cost_amount)
        
        return entry
    
    @staticmethod
    def bank_transfer(from_account: str, to_account: str, amount: Decimal,
                     description: str = "Bank transfer") -> JournalEntry:
        """
        Transfer between bank accounts
        
        DR To Account
            CR From Account
        """
        entry = JournalEntry(
            description=description,
            trans_type=TransactionType.TRANSFER
        )
        
        entry.debit(to_account, amount)
        entry.credit(from_account, amount)
        
        return entry
    
    @staticmethod
    def owner_drawing(amount: Decimal, 
                     description: str = "Owner drawing") -> JournalEntry:
        """
        Record owner withdrawal
        
        DR Drawings
            CR Bank
        """
        entry = JournalEntry(
            description=description,
            trans_type=TransactionType.JOURNAL
        )
        
        entry.debit(AccountCodes.DRAWINGS, amount)
        entry.credit(AccountCodes.BANK, amount)
        
        return entry
    
    @staticmethod
    def owner_contribution(amount: Decimal,
                          description: str = "Capital contribution") -> JournalEntry:
        """
        Record owner capital contribution
        
        DR Bank
            CR Capital
        """
        entry = JournalEntry(
            description=description,
            trans_type=TransactionType.JOURNAL
        )
        
        entry.debit(AccountCodes.BANK, amount)
        entry.credit(AccountCodes.CAPITAL, amount)
        
        return entry


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def post_sale(amount: Decimal, payment_method: str = "cash",
              customer_id: str = None, invoice_number: str = "",
              is_zero_rated: bool = False, cost_price: Decimal = None) -> Tuple[bool, str]:
    """
    Complete sale posting including cost of goods sold
    
    Args:
        amount: Total sale amount including VAT
        payment_method: "cash" or "account"
        customer_id: Customer ID for credit sales
        invoice_number: Reference number
        is_zero_rated: True for zero-rated items
        cost_price: Cost of goods for COGS entry
        
    Returns:
        Tuple of (success, message)
    """
    # Create sale entry
    if payment_method == "account" and customer_id:
        entry = Transactions.credit_sale(
            customer_id=customer_id,
            amount_incl_vat=amount,
            reference=invoice_number,
            is_zero_rated=is_zero_rated
        )
    else:
        entry = Transactions.cash_sale(
            amount_incl_vat=amount,
            reference=invoice_number,
            is_zero_rated=is_zero_rated
        )
    
    entry.source_type = "invoice"
    entry.source_id = invoice_number
    
    # Post sale
    success, result = entry.post()
    if not success:
        return False, result
    
    # Post COGS if cost price provided
    if cost_price and cost_price > 0:
        cogs_entry = Transactions.record_cost_of_sale(
            cost_amount=cost_price,
            description=f"COGS for {invoice_number}"
        )
        cogs_entry.source_type = "invoice"
        cogs_entry.source_id = invoice_number
        
        success, result = cogs_entry.post()
        if not success:
            return False, f"Sale posted but COGS failed: {result}"
    
    return True, "Sale posted successfully"


def post_expense(amount: Decimal, expense_category: str,
                supplier: str = "", description: str = "",
                reference: str = "", vat_type: str = "standard") -> Tuple[bool, str]:
    """
    Post an expense with automatic account selection
    
    Args:
        amount: Total amount including VAT
        expense_category: Category name or account code
        supplier: Supplier name for description
        description: Expense description
        reference: Reference number
        vat_type: "standard", "zero", or "exempt"
        
    Returns:
        Tuple of (success, message)
    """
    # Get the expense account code
    expense_account = get_account_code(expense_category)
    
    # Build description
    if supplier:
        full_desc = f"{supplier}: {description}" if description else supplier
    else:
        full_desc = description or expense_category
    
    # Create and post entry
    entry = Transactions.cash_expense(
        amount_incl_vat=amount,
        expense_account=expense_account,
        description=full_desc,
        reference=reference,
        vat_type=vat_type
    )
    
    return entry.post()


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 3
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 3 COMPLETE - Journal Engine

Contains:
✓ Transaction types enum
✓ JournalLine class for individual entries
✓ JournalEntry class with validation and posting
✓ Journal query class for:
  - Account balances
  - Account movements
  - Trial Balance generation
  - Income Statement (P&L)
  - Balance Sheet
  - VAT Report
✓ Transaction templates for:
  - Cash and credit sales
  - Payment receipts
  - Cash and credit expenses
  - Supplier payments
  - Stock purchases
  - Cost of goods sold
  - Bank transfers
  - Owner drawings/contributions
✓ Helper functions for common operations

All calculations in Flask using Decimal for precision.
Every entry validates that debits = credits before posting.

Next: Piece 4 - CSS and UI Framework
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 4: CSS & UI Framework                                                 ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Complete CSS with glowing header                                          ║
║   - Responsive design for desktop and mobile                                  ║
║   - UI component templates                                                    ║
║   - Page wrapper functions                                                    ║
║   - Flash messages and alerts                                                 ║
║                                                                               ║
║   Design Principles:                                                          ║
║   - Sticky glowing header - always visible                                    ║
║   - Active page highlighted - no duplicate titles                             ║
║   - Dark theme - easy on the eyes                                             ║
║   - Every pixel counts - especially on mobile                                 ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from piece1_core import Config, Money, safe_string, today


# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLES
# ═══════════════════════════════════════════════════════════════════════════════

CSS = """
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   ROOT VARIABLES
   ═══════════════════════════════════════════════════════════════════════════ */
:root {
    /* Background colors */
    --bg-primary: #050508;
    --bg-secondary: #0a0a10;
    --bg-card: #0f0f18;
    --bg-hover: #15151f;
    
    /* Border colors */
    --border: #1a1a2e;
    --border-hover: #2a2a4e;
    
    /* Text colors */
    --text-primary: #f0f0f0;
    --text-secondary: #a0a0a0;
    --text-muted: #606070;
    
    /* Accent colors */
    --purple: #8b5cf6;
    --purple-glow: rgba(139, 92, 246, 0.5);
    --blue: #3b82f6;
    --blue-glow: rgba(59, 130, 246, 0.3);
    --green: #10b981;
    --green-light: #34d399;
    --red: #ef4444;
    --red-light: #f87171;
    --orange: #f59e0b;
    --yellow: #eab308;
    --cyan: #06b6d4;
    
    /* Gradients */
    --gradient-primary: linear-gradient(135deg, var(--purple), var(--blue));
    --gradient-glow: linear-gradient(135deg, var(--purple-glow), var(--blue-glow));
    
    /* Spacing */
    --header-height: 56px;
    --container-max: 1400px;
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    
    /* Transitions */
    --transition-fast: 0.15s ease;
    --transition-normal: 0.25s ease;
}

/* ═══════════════════════════════════════════════════════════════════════════
   RESET & BASE
   ═══════════════════════════════════════════════════════════════════════════ */
*, *::before, *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html {
    font-size: 14px;
    scroll-behavior: smooth;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}

a {
    color: var(--blue);
    text-decoration: none;
    transition: color var(--transition-fast);
}

a:hover {
    color: var(--purple);
}

/* ═══════════════════════════════════════════════════════════════════════════
   GLOWING HEADER
   ═══════════════════════════════════════════════════════════════════════════ */
.header {
    position: sticky;
    top: 0;
    z-index: 1000;
    height: var(--header-height);
    background: linear-gradient(180deg, var(--bg-card) 0%, rgba(15, 15, 24, 0.97) 100%);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 8px;
    overflow-x: auto;
    overflow-y: hidden;
}

.header::-webkit-scrollbar {
    height: 0;
    display: none;
}

/* Glowing Logo */
.logo {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.5px;
    background: var(--gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-decoration: none;
    margin-right: 20px;
    white-space: nowrap;
    position: relative;
    animation: logo-pulse 3s ease-in-out infinite;
}

.logo::after {
    content: '';
    position: absolute;
    inset: -10px -20px;
    background: var(--gradient-glow);
    filter: blur(20px);
    opacity: 0.4;
    z-index: -1;
    animation: glow-pulse 3s ease-in-out infinite;
}

@keyframes logo-pulse {
    0%, 100% { filter: brightness(1); }
    50% { filter: brightness(1.2); }
}

@keyframes glow-pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(1.1); }
}

/* Navigation Items */
.nav {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1;
}

.nav-item {
    padding: 8px 14px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    text-decoration: none;
    white-space: nowrap;
    transition: all var(--transition-fast);
    border: 1px solid transparent;
    position: relative;
}

.nav-item:hover {
    color: var(--text-primary);
    background: var(--bg-hover);
}

.nav-item.active {
    color: white;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(59, 130, 246, 0.25));
    border-color: rgba(139, 92, 246, 0.4);
    box-shadow: 0 0 20px rgba(139, 92, 246, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.nav-item.active::before {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 20%;
    right: 20%;
    height: 2px;
    background: var(--gradient-primary);
    border-radius: 2px;
}

/* Header User Section */
.header-user {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-left: auto;
    padding-left: 20px;
    border-left: 1px solid var(--border);
}

.header-user-name {
    font-size: 13px;
    color: var(--text-secondary);
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN CONTAINER
   ═══════════════════════════════════════════════════════════════════════════ */
.main {
    min-height: calc(100vh - var(--header-height));
    padding: 24px;
}

.container {
    max-width: var(--container-max);
    margin: 0 auto;
}

/* ═══════════════════════════════════════════════════════════════════════════
   CARDS
   ═══════════════════════════════════════════════════════════════════════════ */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px;
    margin-bottom: 20px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
}

.card-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
}

.card-subtitle {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 4px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   STATS GRID
   ═══════════════════════════════════════════════════════════════════════════ */
.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}

.stat {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 20px;
    text-align: center;
    transition: all var(--transition-normal);
}

.stat:hover {
    border-color: var(--border-hover);
    transform: translateY(-2px);
}

.stat-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--blue);
    line-height: 1.2;
}

.stat-value.green { color: var(--green); }
.stat-value.red { color: var(--red); }
.stat-value.orange { color: var(--orange); }
.stat-value.purple { color: var(--purple); }

.stat-label {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════════════════════════════════════════ */
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    text-decoration: none;
    transition: all var(--transition-fast);
    white-space: nowrap;
}

.btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.btn:active {
    transform: translateY(0);
}

.btn-primary {
    background: var(--gradient-primary);
    color: white;
}

.btn-blue {
    background: var(--blue);
    color: white;
}

.btn-green {
    background: var(--green);
    color: white;
}

.btn-red {
    background: var(--red);
    color: white;
}

.btn-orange {
    background: var(--orange);
    color: black;
}

.btn-purple {
    background: var(--purple);
    color: white;
}

.btn-ghost {
    background: transparent;
    color: var(--text-secondary);
    border: 1px solid var(--border);
}

.btn-ghost:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
    border-color: var(--border-hover);
}

.btn-sm {
    padding: 6px 12px;
    font-size: 12px;
}

.btn-lg {
    padding: 14px 28px;
    font-size: 16px;
}

.btn-block {
    width: 100%;
}

.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
}

/* Button Group */
.btn-group {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

/* ═══════════════════════════════════════════════════════════════════════════
   FORMS
   ═══════════════════════════════════════════════════════════════════════════ */
.form-group {
    margin-bottom: 16px;
}

.form-label {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.form-input,
.form-select,
.form-textarea {
    width: 100%;
    padding: 12px 14px;
    font-size: 14px;
    color: var(--text-primary);
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
    outline: none;
    border-color: var(--purple);
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
}

.form-input::placeholder {
    color: var(--text-muted);
}

.form-textarea {
    min-height: 100px;
    resize: vertical;
}

.form-select {
    cursor: pointer;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%23606070' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 36px;
}

.form-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
}

.form-check {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
}

.form-check input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
    accent-color: var(--purple);
}

/* ═══════════════════════════════════════════════════════════════════════════
   TABLES
   ═══════════════════════════════════════════════════════════════════════════ */
.table-wrapper {
    overflow-x: auto;
    margin: -20px;
    padding: 20px;
}

.table {
    width: 100%;
    border-collapse: collapse;
}

.table th,
.table td {
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid var(--border);
}

.table th {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: var(--bg-secondary);
}

.table tr:hover td {
    background: var(--bg-hover);
}

.table tr:last-child td {
    border-bottom: none;
}

.table td.number,
.table th.number {
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.table-clickable tr {
    cursor: pointer;
}

/* ═══════════════════════════════════════════════════════════════════════════
   PRODUCT GRID (POS)
   ═══════════════════════════════════════════════════════════════════════════ */
.product-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
    max-height: 60vh;
    overflow-y: auto;
    padding: 4px;
}

.product-item {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 14px;
    cursor: pointer;
    transition: all var(--transition-fast);
}

.product-item:hover {
    border-color: var(--purple);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.product-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 6px;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.product-price {
    font-size: 15px;
    font-weight: 700;
    color: var(--green);
}

.product-stock {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
}

.product-stock.low {
    color: var(--orange);
}

.product-stock.out {
    color: var(--red);
}

/* ═══════════════════════════════════════════════════════════════════════════
   CART
   ═══════════════════════════════════════════════════════════════════════════ */
.cart {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px;
    display: flex;
    flex-direction: column;
    height: fit-content;
    position: sticky;
    top: calc(var(--header-height) + 24px);
}

.cart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}

.cart-title {
    font-size: 16px;
    font-weight: 600;
}

.cart-items {
    flex: 1;
    min-height: 150px;
    max-height: 300px;
    overflow-y: auto;
}

.cart-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
}

.cart-item:last-child {
    border-bottom: none;
}

.cart-item-name {
    font-weight: 600;
    font-size: 13px;
}

.cart-item-details {
    font-size: 12px;
    color: var(--text-muted);
}

.cart-item-price {
    font-weight: 600;
    white-space: nowrap;
}

.cart-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 150px;
    color: var(--text-muted);
    font-size: 14px;
}

.cart-total {
    padding: 16px 0;
    border-top: 2px solid var(--border);
    margin-top: 16px;
    text-align: right;
}

.cart-total-label {
    font-size: 14px;
    color: var(--text-secondary);
}

.cart-total-value {
    font-size: 28px;
    font-weight: 800;
    color: var(--green);
}

.cart-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 16px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   MODALS
   ═══════════════════════════════════════════════════════════════════════════ */
.modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(4px);
    z-index: 2000;
    align-items: center;
    justify-content: center;
    padding: 20px;
}

.modal-overlay.show {
    display: flex;
}

.modal {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
}

.modal-header {
    padding: 20px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-title {
    font-size: 18px;
    font-weight: 600;
}

.modal-close {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 24px;
    cursor: pointer;
    padding: 4px;
    line-height: 1;
}

.modal-close:hover {
    color: var(--text-primary);
}

.modal-body {
    padding: 20px;
}

.modal-footer {
    padding: 16px 20px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   ALERTS & MESSAGES
   ═══════════════════════════════════════════════════════════════════════════ */
.alert {
    padding: 14px 18px;
    border-radius: var(--radius-sm);
    margin-bottom: 16px;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.alert-info {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: var(--blue);
}

.alert-success {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: var(--green);
}

.alert-warning {
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid rgba(245, 158, 11, 0.3);
    color: var(--orange);
}

.alert-error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: var(--red);
}

/* ═══════════════════════════════════════════════════════════════════════════
   BADGES
   ═══════════════════════════════════════════════════════════════════════════ */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}

.badge-green {
    background: rgba(16, 185, 129, 0.15);
    color: var(--green);
}

.badge-red {
    background: rgba(239, 68, 68, 0.15);
    color: var(--red);
}

.badge-orange {
    background: rgba(245, 158, 11, 0.15);
    color: var(--orange);
}

.badge-blue {
    background: rgba(59, 130, 246, 0.15);
    color: var(--blue);
}

.badge-purple {
    background: rgba(139, 92, 246, 0.15);
    color: var(--purple);
}

/* ═══════════════════════════════════════════════════════════════════════════
   REPORT CARDS
   ═══════════════════════════════════════════════════════════════════════════ */
.report-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
}

.report-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 24px;
    text-decoration: none;
    color: var(--text-primary);
    transition: all var(--transition-normal);
    display: block;
}

.report-card:hover {
    border-color: var(--purple);
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}

.report-card-icon {
    font-size: 32px;
    margin-bottom: 12px;
}

.report-card-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
}

.report-card-desc {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.5;
}

/* ═══════════════════════════════════════════════════════════════════════════
   EMPTY STATES
   ═══════════════════════════════════════════════════════════════════════════ */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
}

.empty-state-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
}

.empty-state-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.empty-state-desc {
    font-size: 14px;
    max-width: 400px;
    margin: 0 auto;
}

/* ═══════════════════════════════════════════════════════════════════════════
   LOADING STATES
   ═══════════════════════════════════════════════════════════════════════════ */
.loading {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 40px;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border);
    border-top-color: var(--purple);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

/* ═══════════════════════════════════════════════════════════════════════════
   LAYOUT HELPERS
   ═══════════════════════════════════════════════════════════════════════════ */
.flex {
    display: flex;
}

.flex-between {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.flex-center {
    display: flex;
    align-items: center;
    justify-content: center;
}

.flex-wrap {
    flex-wrap: wrap;
}

.gap-sm { gap: 8px; }
.gap-md { gap: 16px; }
.gap-lg { gap: 24px; }

.grid-2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}

.grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}

.mt-sm { margin-top: 8px; }
.mt-md { margin-top: 16px; }
.mt-lg { margin-top: 24px; }
.mb-sm { margin-bottom: 8px; }
.mb-md { margin-bottom: 16px; }
.mb-lg { margin-bottom: 24px; }

.text-center { text-align: center; }
.text-right { text-align: right; }
.text-muted { color: var(--text-muted); }
.text-green { color: var(--green); }
.text-red { color: var(--red); }
.text-orange { color: var(--orange); }

.font-bold { font-weight: 600; }
.font-mono { font-family: 'Monaco', 'Consolas', monospace; }

/* ═══════════════════════════════════════════════════════════════════════════
   POS LAYOUT
   ═══════════════════════════════════════════════════════════════════════════ */
.pos-layout {
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 24px;
    align-items: start;
}

/* ═══════════════════════════════════════════════════════════════════════════
   RESPONSIVE
   ═══════════════════════════════════════════════════════════════════════════ */
@media (max-width: 1024px) {
    .pos-layout {
        grid-template-columns: 1fr 320px;
    }
}

@media (max-width: 768px) {
    html {
        font-size: 13px;
    }
    
    .header {
        padding: 0 12px;
        gap: 4px;
    }
    
    .logo {
        font-size: 18px;
        margin-right: 12px;
    }
    
    .nav-item {
        padding: 6px 10px;
        font-size: 12px;
    }
    
    .main {
        padding: 16px;
    }
    
    .stats {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .pos-layout {
        grid-template-columns: 1fr;
    }
    
    .cart {
        position: relative;
        top: 0;
    }
    
    .form-row {
        grid-template-columns: 1fr;
    }
    
    .grid-2, .grid-3 {
        grid-template-columns: 1fr;
    }
    
    .report-grid {
        grid-template-columns: 1fr;
    }
    
    .cart-actions {
        grid-template-columns: 1fr;
    }
    
    .header-user {
        display: none;
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
   MOBILE SPECIFIC INTERFACE
   ═══════════════════════════════════════════════════════════════════════════ */
.mobile-only {
    display: none;
}

@media (max-width: 480px) {
    .desktop-only {
        display: none;
    }
    
    .mobile-only {
        display: flex;
    }
    
    .mobile-big-buttons {
        display: flex;
        flex-direction: column;
        gap: 20px;
        padding: 40px 20px;
        min-height: calc(100vh - var(--header-height));
        justify-content: center;
    }
    
    .mobile-big-btn {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px;
        border-radius: var(--radius-lg);
        text-decoration: none;
        font-size: 20px;
        font-weight: 700;
        transition: all var(--transition-normal);
    }
    
    .mobile-big-btn-icon {
        font-size: 48px;
        margin-bottom: 12px;
    }
    
    .mobile-big-btn.stock {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(59, 130, 246, 0.2));
        border: 2px solid rgba(139, 92, 246, 0.4);
        color: var(--purple);
    }
    
    .mobile-big-btn.expense {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(245, 158, 11, 0.2));
        border: 2px solid rgba(239, 68, 68, 0.4);
        color: var(--red);
    }
    
    .mobile-big-btn:active {
        transform: scale(0.98);
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
   PRINT STYLES
   ═══════════════════════════════════════════════════════════════════════════ */
@media print {
    .header,
    .btn,
    .modal-overlay {
        display: none !important;
    }
    
    body {
        background: white;
        color: black;
    }
    
    .card {
        border: 1px solid #ccc;
        break-inside: avoid;
    }
    
    .table th,
    .table td {
        border: 1px solid #ccc;
    }
}
</style>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE WRAPPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_header_html(active: str = "", user: dict = None) -> str:
    """
    Generate the glowing header HTML
    
    Args:
        active: Current active page (home, pos, stock, etc.)
        user: Current user dict with name
    """
    nav_items = [
        ("home", "Home", "/"),
        ("pos", "POS", "/pos"),
        ("stock", "Stock", "/stock"),
        ("customers", "Customers", "/customers"),
        ("suppliers", "Suppliers", "/suppliers"),
        ("invoices", "Invoices", "/invoices"),
        ("quotes", "Quotes", "/quotes"),
        ("expenses", "Expenses", "/expenses"),
        ("reports", "Reports", "/reports"),
    ]
    
    nav_html = ""
    for key, label, url in nav_items:
        active_class = " active" if key == active else ""
        nav_html += f'<a href="{url}" class="nav-item{active_class}">{label}</a>'
    
    user_html = ""
    if user:
        user_html = f'''
        <div class="header-user">
            <span class="header-user-name">{safe_string(user.get("username", ""))}</span>
            <a href="/logout" class="btn btn-sm btn-ghost">Logout</a>
        </div>
        '''
    
    return f'''
    <header class="header">
        <a href="/" class="logo">Click AI</a>
        <nav class="nav">
            {nav_html}
        </nav>
        {user_html}
    </header>
    '''


def page_wrapper(title: str, content: str, active: str = "", 
                 user: dict = None, extra_css: str = "", 
                 extra_js: str = "") -> str:
    """
    Wrap page content in full HTML document
    
    Args:
        title: Page title
        content: Main content HTML
        active: Active nav item
        user: Current user
        extra_css: Additional CSS to include
        extra_js: Additional JavaScript to include
    """
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_string(title)} - Click AI</title>
    {CSS}
    {extra_css}
</head>
<body>
    {get_header_html(active, user)}
    <main class="main">
        <div class="container">
            {content}
        </div>
    </main>
    {extra_js}
</body>
</html>'''


def error_page(title: str, message: str, back_url: str = "/") -> str:
    """Generate an error page"""
    content = f'''
    <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h2 class="empty-state-title">{safe_string(title)}</h2>
        <p class="empty-state-desc">{safe_string(message)}</p>
        <a href="{back_url}" class="btn btn-primary mt-lg">Go Back</a>
    </div>
    '''
    return page_wrapper(title, content)


def success_message(message: str) -> str:
    """Generate a success alert HTML"""
    return f'<div class="alert alert-success">✓ {safe_string(message)}</div>'


def error_message(message: str) -> str:
    """Generate an error alert HTML"""
    return f'<div class="alert alert-error">✗ {safe_string(message)}</div>'


def info_message(message: str) -> str:
    """Generate an info alert HTML"""
    return f'<div class="alert alert-info">ℹ {safe_string(message)}</div>'


# ═══════════════════════════════════════════════════════════════════════════════
# COMMON UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def stat_card(value: str, label: str, color: str = "") -> str:
    """Generate a stat card"""
    color_class = f" {color}" if color else ""
    return f'''
    <div class="stat">
        <div class="stat-value{color_class}">{safe_string(value)}</div>
        <div class="stat-label">{safe_string(label)}</div>
    </div>
    '''


def money_stat(amount, label: str, positive_is_green: bool = True) -> str:
    """Generate a money stat card with automatic color"""
    from decimal import Decimal
    amount = Decimal(str(amount))
    color = ""
    if amount > 0:
        color = "green" if positive_is_green else "red"
    elif amount < 0:
        color = "red" if positive_is_green else "green"
    
    return stat_card(Money.format(amount), label, color)


def badge(text: str, color: str = "blue") -> str:
    """Generate a badge"""
    return f'<span class="badge badge-{color}">{safe_string(text)}</span>'


def empty_state(icon: str, title: str, description: str = "") -> str:
    """Generate an empty state placeholder"""
    desc_html = f'<p class="empty-state-desc">{safe_string(description)}</p>' if description else ""
    return f'''
    <div class="empty-state">
        <div class="empty-state-icon">{icon}</div>
        <h3 class="empty-state-title">{safe_string(title)}</h3>
        {desc_html}
    </div>
    '''


def loading_spinner() -> str:
    """Generate a loading spinner"""
    return '<div class="loading"><div class="spinner"></div></div>'


def modal_template(id: str, title: str, body: str, 
                   footer: str = "", size: str = "md") -> str:
    """Generate a modal template"""
    size_style = ""
    if size == "lg":
        size_style = "max-width: 700px;"
    elif size == "sm":
        size_style = "max-width: 400px;"
    
    footer_html = f'<div class="modal-footer">{footer}</div>' if footer else ""
    
    return f'''
    <div class="modal-overlay" id="{id}">
        <div class="modal" style="{size_style}">
            <div class="modal-header">
                <h3 class="modal-title">{safe_string(title)}</h3>
                <button class="modal-close" onclick="closeModal('{id}')">&times;</button>
            </div>
            <div class="modal-body">
                {body}
            </div>
            {footer_html}
        </div>
    </div>
    '''


def table_html(headers: list, rows: list, clickable: bool = False,
               empty_message: str = "No data found") -> str:
    """
    Generate a table
    
    Args:
        headers: List of header strings or dicts with 'label' and 'class'
        rows: List of rows, each row is a list of cell values
        clickable: Add clickable class
        empty_message: Message when no rows
    """
    if not rows:
        return empty_state("📋", empty_message)
    
    # Build headers
    header_html = "<tr>"
    for h in headers:
        if isinstance(h, dict):
            cls = f' class="{h.get("class", "")}"' if h.get("class") else ""
            header_html += f'<th{cls}>{safe_string(h["label"])}</th>'
        else:
            header_html += f'<th>{safe_string(h)}</th>'
    header_html += "</tr>"
    
    # Build rows
    rows_html = ""
    for row in rows:
        rows_html += "<tr>"
        for cell in row:
            if isinstance(cell, dict):
                cls = f' class="{cell.get("class", "")}"' if cell.get("class") else ""
                rows_html += f'<td{cls}>{cell["value"]}</td>'
            else:
                rows_html += f'<td>{cell}</td>'
        rows_html += "</tr>"
    
    clickable_class = " table-clickable" if clickable else ""
    
    return f'''
    <div class="table-wrapper">
        <table class="table{clickable_class}">
            <thead>{header_html}</thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    '''


# ═══════════════════════════════════════════════════════════════════════════════
# FORM HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def form_input(name: str, label: str = "", value: str = "",
               input_type: str = "text", placeholder: str = "",
               required: bool = False) -> str:
    """Generate a form input field"""
    label_html = f'<label class="form-label" for="{name}">{safe_string(label)}</label>' if label else ""
    req = " required" if required else ""
    
    return f'''
    <div class="form-group">
        {label_html}
        <input type="{input_type}" 
               id="{name}" 
               name="{name}" 
               class="form-input"
               value="{safe_string(value)}"
               placeholder="{safe_string(placeholder)}"{req}>
    </div>
    '''


def form_select(name: str, options: list, label: str = "",
                selected: str = "", required: bool = False) -> str:
    """
    Generate a form select field
    
    options: List of tuples (value, label) or dicts with 'value' and 'label'
    """
    label_html = f'<label class="form-label" for="{name}">{safe_string(label)}</label>' if label else ""
    req = " required" if required else ""
    
    options_html = '<option value="">Select...</option>'
    for opt in options:
        if isinstance(opt, dict):
            val, lbl = opt["value"], opt["label"]
        else:
            val, lbl = opt[0], opt[1]
        sel = " selected" if str(val) == str(selected) else ""
        options_html += f'<option value="{safe_string(val)}"{sel}>{safe_string(lbl)}</option>'
    
    return f'''
    <div class="form-group">
        {label_html}
        <select id="{name}" name="{name}" class="form-select"{req}>
            {options_html}
        </select>
    </div>
    '''


def form_textarea(name: str, label: str = "", value: str = "",
                  placeholder: str = "", rows: int = 4) -> str:
    """Generate a form textarea"""
    label_html = f'<label class="form-label" for="{name}">{safe_string(label)}</label>' if label else ""
    
    return f'''
    <div class="form-group">
        {label_html}
        <textarea id="{name}" 
                  name="{name}" 
                  class="form-textarea"
                  rows="{rows}"
                  placeholder="{safe_string(placeholder)}">{safe_string(value)}</textarea>
    </div>
    '''


def form_checkbox(name: str, label: str, checked: bool = False) -> str:
    """Generate a form checkbox"""
    chk = " checked" if checked else ""
    return f'''
    <label class="form-check">
        <input type="checkbox" name="{name}" id="{name}"{chk}>
        <span>{safe_string(label)}</span>
    </label>
    '''


# ═══════════════════════════════════════════════════════════════════════════════
# JAVASCRIPT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

COMMON_JS = """
<script>
// Modal functions
function openModal(id) {
    document.getElementById(id).classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}

// Close modal on overlay click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('show');
    }
});

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.show').forEach(function(m) {
            m.classList.remove('show');
        });
    }
});

// Format currency
function formatMoney(amount) {
    return 'R ' + parseFloat(amount).toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g, ',');
}

// API helper
async function api(url, method, data) {
    const options = {
        method: method || 'GET',
        headers: {'Content-Type': 'application/json'}
    };
    if (data) {
        options.body = JSON.stringify(data);
    }
    const response = await fetch(url, options);
    return response.json();
}
</script>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 4
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 4 COMPLETE - CSS & UI Framework

Contains:
✓ Complete CSS with CSS variables
✓ Glowing animated header with logo
✓ Active navigation highlighting
✓ Responsive design (desktop, tablet, mobile)
✓ Dark theme optimized for long use
✓ Component styles:
  - Cards, Stats, Buttons, Forms
  - Tables, Modals, Alerts, Badges
  - Product grid, Cart, Empty states
  - Loading spinners, Report cards
✓ Page wrapper function
✓ UI component helper functions
✓ Form helper functions
✓ Common JavaScript utilities
✓ Print styles
✓ Mobile-specific big button interface

Design Principles Applied:
- Sticky glowing header - always visible
- Active page highlighted - no duplicate titles
- Every pixel counts - compact but readable
- Dark theme - professional, easy on eyes

Next: Piece 5 - Dashboard
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 5: Dashboard & Landing                                                ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Landing page                                                              ║
║   - Dashboard with real-time stats from ledger                                ║
║   - Quick actions                                                             ║
║   - Recent activity                                                           ║
║   - Login/logout routes                                                       ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import request, redirect, session
from decimal import Decimal

from piece1_core import app, db, Money, today, format_date, UserSession, FinancialPeriod
from piece2_accounts import Account, AccountCodes
from piece3_journal import Journal
from piece4_ui import (
    page_wrapper, CSS, get_header_html, 
    stat_card, money_stat, badge, empty_state,
    success_message, error_message
)


# ═══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE
# ═══════════════════════════════════════════════════════════════════════════════

LANDING_CSS = """
<style>
.landing {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    background: radial-gradient(ellipse at center, #0a0a15 0%, #050508 100%);
}

.landing-logo {
    font-size: 72px;
    font-weight: 900;
    letter-spacing: -2px;
    background: linear-gradient(135deg, #8b5cf6, #3b82f6, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 16px;
    position: relative;
    animation: float 6s ease-in-out infinite;
}

.landing-logo::before {
    content: 'Click AI';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, #8b5cf6, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: blur(30px);
    opacity: 0.6;
    z-index: -1;
    animation: glow-breathe 3s ease-in-out infinite;
}

@keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
}

@keyframes glow-breathe {
    0%, 100% { opacity: 0.4; transform: scale(1); }
    50% { opacity: 0.8; transform: scale(1.1); }
}

.landing-tagline {
    font-size: 20px;
    color: #606070;
    margin-bottom: 48px;
    text-align: center;
}

.landing-tagline span {
    color: #8b5cf6;
}

.landing-buttons {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    justify-content: center;
}

.landing-btn {
    padding: 16px 40px;
    font-size: 18px;
    font-weight: 600;
    border-radius: 12px;
    text-decoration: none;
    transition: all 0.3s ease;
}

.landing-btn-primary {
    background: linear-gradient(135deg, #8b5cf6, #3b82f6);
    color: white;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.4);
}

.landing-btn-primary:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 30px rgba(139, 92, 246, 0.5);
}

.landing-btn-secondary {
    background: transparent;
    color: #a0a0a0;
    border: 1px solid #2a2a3e;
}

.landing-btn-secondary:hover {
    background: #15151f;
    color: white;
    border-color: #3a3a4e;
}

.landing-features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 24px;
    max-width: 800px;
    margin-top: 80px;
}

.landing-feature {
    text-align: center;
    padding: 24px;
}

.landing-feature-icon {
    font-size: 36px;
    margin-bottom: 12px;
}

.landing-feature-title {
    font-size: 16px;
    font-weight: 600;
    color: #f0f0f0;
    margin-bottom: 8px;
}

.landing-feature-desc {
    font-size: 13px;
    color: #606070;
    line-height: 1.5;
}

@media (max-width: 600px) {
    .landing-logo {
        font-size: 48px;
    }
    
    .landing-tagline {
        font-size: 16px;
    }
    
    .landing-btn {
        width: 100%;
        text-align: center;
    }
}
</style>
"""


@app.route("/")
def landing():
    """Landing page - show login or redirect to dashboard if logged in"""
    
    # If already logged in, go to dashboard
    if UserSession.is_logged_in():
        return redirect("/dashboard")
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Click AI - Business Management System</title>
    {CSS}
    {LANDING_CSS}
</head>
<body>
    <div class="landing">
        <div class="landing-logo">Click AI</div>
        <p class="landing-tagline">Complete Business Management.<br><span>Powered by AI.</span></p>
        
        <div class="landing-buttons">
            <a href="/login" class="landing-btn landing-btn-primary">Login</a>
            <a href="/demo" class="landing-btn landing-btn-secondary">Try Demo</a>
        </div>
        
        <div class="landing-features">
            <div class="landing-feature">
                <div class="landing-feature-icon">💰</div>
                <div class="landing-feature-title">Point of Sale</div>
                <div class="landing-feature-desc">Fast, intuitive sales with automatic stock updates</div>
            </div>
            <div class="landing-feature">
                <div class="landing-feature-icon">📊</div>
                <div class="landing-feature-title">Real Accounting</div>
                <div class="landing-feature-desc">Double-entry bookkeeping with proper ledger</div>
            </div>
            <div class="landing-feature">
                <div class="landing-feature-icon">🤖</div>
                <div class="landing-feature-title">AI Powered</div>
                <div class="landing-feature-desc">Smart receipt scanning and categorization</div>
            </div>
            <div class="landing-feature">
                <div class="landing-feature-icon">📱</div>
                <div class="landing-feature-title">Mobile Ready</div>
                <div class="landing-feature-desc">Capture expenses anywhere with your phone</div>
            </div>
        </div>
    </div>
</body>
</html>'''
    
    return html


# ═══════════════════════════════════════════════════════════════════════════════
# LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════════════════════

LOGIN_CSS = """
<style>
.login-container {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background: radial-gradient(ellipse at center, #0a0a15 0%, #050508 100%);
}

.login-box {
    background: #0f0f18;
    border: 1px solid #1a1a2e;
    border-radius: 16px;
    padding: 40px;
    width: 100%;
    max-width: 400px;
}

.login-logo {
    font-size: 32px;
    font-weight: 800;
    background: linear-gradient(135deg, #8b5cf6, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    margin-bottom: 32px;
}

.login-title {
    font-size: 24px;
    font-weight: 600;
    text-align: center;
    margin-bottom: 24px;
    color: #f0f0f0;
}
</style>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page"""
    
    error = ""
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        success, result = UserSession.login(username, password)
        
        if success:
            return redirect("/dashboard")
        else:
            error = result
    
    error_html = f'<div class="alert alert-error">{error}</div>' if error else ""
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Click AI</title>
    {CSS}
    {LOGIN_CSS}
</head>
<body>
    <div class="login-container">
        <div class="login-box">
            <div class="login-logo">Click AI</div>
            <h1 class="login-title">Welcome Back</h1>
            
            {error_html}
            
            <form method="POST">
                <div class="form-group">
                    <label class="form-label" for="username">Username</label>
                    <input type="text" id="username" name="username" class="form-input" 
                           placeholder="Enter username" required autofocus>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="password">Password</label>
                    <input type="password" id="password" name="password" class="form-input" 
                           placeholder="Enter password" required>
                </div>
                
                <button type="submit" class="btn btn-primary btn-block btn-lg mt-md">
                    Login
                </button>
            </form>
            
            <p class="text-center text-muted mt-lg">
                <a href="/">← Back to home</a>
            </p>
        </div>
    </div>
</body>
</html>'''
    
    return html


@app.route("/logout")
def logout():
    """Logout and redirect to landing"""
    UserSession.logout()
    return redirect("/")


@app.route("/demo")
def demo():
    """Demo mode - create demo session"""
    # Set demo user in session
    session["user_id"] = "demo"
    session["username"] = "Demo User"
    session["role"] = "admin"
    session["is_demo"] = True
    
    return redirect("/dashboard")


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/dashboard")
def dashboard():
    """Main dashboard with real-time stats"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    # Get current financial year dates
    year_start = FinancialPeriod.get_current_year_start()
    year_end = FinancialPeriod.get_current_year_end()
    
    # Get real balances from ledger
    bank_balance = Journal.get_account_balance(AccountCodes.BANK)
    debtors_balance = Journal.get_account_balance(AccountCodes.DEBTORS)
    creditors_balance = Journal.get_account_balance(AccountCodes.CREDITORS)
    stock_balance = Journal.get_account_balance(AccountCodes.STOCK)
    
    # Get P&L summary
    income_statement = Journal.get_income_statement(year_start, today())
    total_revenue = income_statement["total_revenue"]
    total_expenses = income_statement["total_expenses"]
    net_profit = income_statement["net_profit"]
    gross_profit = income_statement["gross_profit"]
    
    # Get VAT position
    vat_report = Journal.get_vat_report(year_start, today())
    vat_payable = vat_report["net_vat"]
    
    # Count records
    stock_count = db.count("stock_items")
    customer_count = db.count("customers")
    supplier_count = db.count("suppliers")
    invoice_count = db.count("invoices")
    
    # Get recent transactions
    recent_journal = Journal.get_entries(limit=10)
    
    recent_rows = ""
    for entry in recent_journal[:10]:
        dr = Money.format(Decimal(str(entry.get("debit", 0)))) if entry.get("debit") else "-"
        cr = Money.format(Decimal(str(entry.get("credit", 0)))) if entry.get("credit") else "-"
        recent_rows += f'''
        <tr>
            <td>{format_date(entry.get("date", ""))}</td>
            <td>{entry.get("account_code", "")}</td>
            <td>{entry.get("description", "")[:50]}</td>
            <td class="number">{dr}</td>
            <td class="number">{cr}</td>
        </tr>
        '''
    
    if not recent_rows:
        recent_rows = '<tr><td colspan="5" class="text-center text-muted" style="padding:40px">No transactions yet</td></tr>'
    
    content = f'''
    <div class="flex-between mb-lg">
        <div>
            <h1 style="font-size: 24px; font-weight: 700; margin-bottom: 4px;">Dashboard</h1>
            <p class="text-muted">Welcome back, {user.get("username", "User")}</p>
        </div>
        <div class="btn-group">
            <a href="/pos" class="btn btn-primary">New Sale</a>
            <a href="/expenses/new" class="btn btn-orange">Add Expense</a>
        </div>
    </div>
    
    <!-- Financial Summary -->
    <div class="stats">
        <div class="stat">
            <div class="stat-value{' green' if bank_balance >= 0 else ' red'}">{Money.format(bank_balance)}</div>
            <div class="stat-label">Bank Balance</div>
        </div>
        <div class="stat">
            <div class="stat-value purple">{Money.format(debtors_balance)}</div>
            <div class="stat-label">Debtors Owe You</div>
        </div>
        <div class="stat">
            <div class="stat-value orange">{Money.format(creditors_balance)}</div>
            <div class="stat-label">You Owe Suppliers</div>
        </div>
        <div class="stat">
            <div class="stat-value">{Money.format(stock_balance)}</div>
            <div class="stat-label">Stock Value</div>
        </div>
    </div>
    
    <!-- Profit Summary -->
    <div class="stats">
        <div class="stat">
            <div class="stat-value green">{Money.format(total_revenue)}</div>
            <div class="stat-label">Revenue (YTD)</div>
        </div>
        <div class="stat">
            <div class="stat-value">{Money.format(gross_profit)}</div>
            <div class="stat-label">Gross Profit</div>
        </div>
        <div class="stat">
            <div class="stat-value red">{Money.format(total_expenses)}</div>
            <div class="stat-label">Expenses (YTD)</div>
        </div>
        <div class="stat">
            <div class="stat-value{' green' if net_profit >= 0 else ' red'}">{Money.format(net_profit)}</div>
            <div class="stat-label">Net Profit</div>
        </div>
    </div>
    
    <!-- Quick Stats Row -->
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{stock_count}</div>
            <div class="stat-label">Stock Items</div>
        </div>
        <div class="stat">
            <div class="stat-value">{customer_count}</div>
            <div class="stat-label">Customers</div>
        </div>
        <div class="stat">
            <div class="stat-value">{supplier_count}</div>
            <div class="stat-label">Suppliers</div>
        </div>
        <div class="stat">
            <div class="stat-value{' red' if vat_payable > 0 else ' green'}">{Money.format(abs(vat_payable))}</div>
            <div class="stat-label">{'VAT Payable' if vat_payable > 0 else 'VAT Refund'}</div>
        </div>
    </div>
    
    <!-- Quick Actions -->
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Quick Actions</h2>
        </div>
        <div class="btn-group flex-wrap">
            <a href="/pos" class="btn btn-blue">💰 New Sale</a>
            <a href="/invoices/new" class="btn btn-green">📄 New Invoice</a>
            <a href="/quotes/new" class="btn btn-purple">📝 New Quote</a>
            <a href="/expenses/new" class="btn btn-orange">💸 Add Expense</a>
            <a href="/expenses/scan" class="btn btn-ghost">📷 Scan Receipt</a>
            <a href="/stock" class="btn btn-ghost">📦 Manage Stock</a>
            <a href="/reports" class="btn btn-ghost">📊 Reports</a>
        </div>
    </div>
    
    <!-- Recent Transactions -->
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Recent Transactions</h2>
            <a href="/reports/ledger" class="btn btn-sm btn-ghost">View All</a>
        </div>
        <div class="table-wrapper">
            <table class="table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Account</th>
                        <th>Description</th>
                        <th class="number">Debit</th>
                        <th class="number">Credit</th>
                    </tr>
                </thead>
                <tbody>
                    {recent_rows}
                </tbody>
            </table>
        </div>
    </div>
    '''
    
    return page_wrapper("Dashboard", content, active="home", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# MOBILE INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/mobile")
def mobile_home():
    """Mobile-optimized home with big buttons"""
    
    user = UserSession.get_current_user()
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Click AI Mobile</title>
    {CSS}
    <style>
        body {{
            background: #050508;
        }}
        .mobile-home {{
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 20px;
        }}
        .mobile-header {{
            text-align: center;
            padding: 20px 0;
        }}
        .mobile-logo {{
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #8b5cf6, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .mobile-buttons {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 20px;
            justify-content: center;
            padding: 20px 0;
        }}
        .mobile-btn {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 50px 20px;
            border-radius: 20px;
            text-decoration: none;
            transition: all 0.2s;
        }}
        .mobile-btn:active {{
            transform: scale(0.98);
        }}
        .mobile-btn-icon {{
            font-size: 56px;
            margin-bottom: 16px;
        }}
        .mobile-btn-label {{
            font-size: 22px;
            font-weight: 700;
        }}
        .mobile-btn.stock {{
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(59, 130, 246, 0.15));
            border: 2px solid rgba(139, 92, 246, 0.4);
            color: #8b5cf6;
        }}
        .mobile-btn.expense {{
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(245, 158, 11, 0.15));
            border: 2px solid rgba(239, 68, 68, 0.4);
            color: #ef4444;
        }}
        .mobile-footer {{
            text-align: center;
            padding: 20px;
        }}
        .mobile-footer a {{
            color: #606070;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="mobile-home">
        <div class="mobile-header">
            <div class="mobile-logo">Click AI</div>
            <p style="color: #606070; margin-top: 8px;">Quick Capture</p>
        </div>
        
        <div class="mobile-buttons">
            <a href="/stock/scan" class="mobile-btn stock">
                <div class="mobile-btn-icon">📦</div>
                <div class="mobile-btn-label">Stock In</div>
            </a>
            
            <a href="/expenses/scan" class="mobile-btn expense">
                <div class="mobile-btn-icon">💸</div>
                <div class="mobile-btn-label">Expense</div>
            </a>
        </div>
        
        <div class="mobile-footer">
            <a href="/dashboard">← Back to Full App</a>
        </div>
    </div>
</body>
</html>'''
    
    return html


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR PAGES
# ═══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def page_not_found(e):
    """404 error page"""
    content = '''
    <div class="empty-state">
        <div class="empty-state-icon">🔍</div>
        <h2 class="empty-state-title">Page Not Found</h2>
        <p class="empty-state-desc">The page you're looking for doesn't exist or has been moved.</p>
        <a href="/dashboard" class="btn btn-primary mt-lg">Go to Dashboard</a>
    </div>
    '''
    return page_wrapper("Page Not Found", content), 404


@app.errorhandler(500)
def server_error(e):
    """500 error page"""
    content = '''
    <div class="empty-state">
        <div class="empty-state-icon">⚠️</div>
        <h2 class="empty-state-title">Something Went Wrong</h2>
        <p class="empty-state-desc">We're sorry, something went wrong on our end. Please try again.</p>
        <a href="/dashboard" class="btn btn-primary mt-lg">Go to Dashboard</a>
    </div>
    '''
    return page_wrapper("Server Error", content), 500


@app.route("/unauthorized")
def unauthorized():
    """Unauthorized access page"""
    content = '''
    <div class="empty-state">
        <div class="empty-state-icon">🔒</div>
        <h2 class="empty-state-title">Access Denied</h2>
        <p class="empty-state-desc">You don't have permission to access this page.</p>
        <a href="/dashboard" class="btn btn-primary mt-lg">Go to Dashboard</a>
    </div>
    '''
    return page_wrapper("Unauthorized", content)


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": "2.0",
        "app": "Click AI"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 5
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 5 COMPLETE - Dashboard & Landing

Contains:
✓ Animated landing page with glowing logo
✓ Login/logout system
✓ Demo mode
✓ Dashboard with real-time stats from ledger:
  - Bank balance
  - Debtors/Creditors
  - Stock value
  - Revenue (YTD)
  - Gross profit
  - Expenses (YTD)
  - Net profit
  - VAT position
  - Quick counts
✓ Quick actions
✓ Recent transactions from journal
✓ Mobile-optimized interface with big buttons
✓ Error pages (404, 500, unauthorized)
✓ Health check endpoint

All stats pulled from Journal class - real accounting data!

Next: Piece 6 - POS (Point of Sale)
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 6: Point of Sale (POS)                                                ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - POS interface with product grid                                           ║
║   - Shopping cart functionality                                               ║
║   - Customer selection                                                        ║
║   - Multiple payment methods (cash, card, account)                            ║
║   - Proper GL posting with VAT                                                ║
║   - Stock reduction on sale                                                   ║
║   - Receipt generation                                                        ║
║                                                                               ║
║   All calculations done by Flask - NO JavaScript math                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import request, redirect, jsonify, session
from decimal import Decimal, ROUND_HALF_UP
import json

from piece1_core import (
    app, db, generate_id, now, today, 
    Money, VAT, safe_string, safe_json_string,
    DocumentNumbers
)
from piece2_accounts import AccountCodes
from piece3_journal import JournalEntry, Transactions, TransactionType
from piece4_ui import page_wrapper, COMMON_JS


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_stock_items_for_pos() -> list:
    """Get stock items formatted for POS"""
    items = db.select("stock_items", order="description")
    result = []
    
    for item in items:
        if not item.get("active", True):
            continue
        
        price = Decimal(str(item.get("selling_price", 0) or 0))
        cost = Decimal(str(item.get("cost_price", 0) or 0))
        qty = int(item.get("quantity", 0) or 0)
        
        # Check if zero-rated
        desc = item.get("description", "")
        category = item.get("category", "")
        is_zero_rated = VAT.is_zero_rated(desc, category)
        
        result.append({
            "id": item["id"],
            "code": item.get("code", ""),
            "description": desc,
            "category": category,
            "quantity": qty,
            "price": float(price),
            "price_formatted": Money.format(price),
            "cost": float(cost),
            "is_zero_rated": is_zero_rated
        })
    
    return result


def get_customers_for_pos() -> list:
    """Get customers formatted for POS"""
    customers = db.select("customers", order="name")
    result = []
    
    for cust in customers:
        if not cust.get("active", True):
            continue
        
        result.append({
            "id": cust["id"],
            "name": cust.get("name", ""),
            "code": cust.get("code", ""),
            "balance": float(cust.get("balance", 0) or 0)
        })
    
    return result


def reduce_stock(item_id: str, quantity: int) -> bool:
    """Reduce stock quantity after sale"""
    item = db.select_one("stock_items", item_id)
    if not item:
        return False
    
    current_qty = int(item.get("quantity", 0) or 0)
    new_qty = max(0, current_qty - quantity)
    
    success, _ = db.update("stock_items", item_id, {"quantity": new_qty})
    return success


def update_customer_balance(customer_id: str, amount: Decimal) -> bool:
    """Add to customer balance (for account sales)"""
    customer = db.select_one("customers", customer_id)
    if not customer:
        return False
    
    current_balance = Decimal(str(customer.get("balance", 0) or 0))
    new_balance = current_balance + amount
    
    success, _ = db.update("customers", customer_id, {"balance": float(new_balance)})
    return success


# ═══════════════════════════════════════════════════════════════════════════════
# POS API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/pos/stock")
def api_pos_stock():
    """Get stock items for POS"""
    items = get_stock_items_for_pos()
    return jsonify(items)


@app.route("/api/pos/customers")
def api_pos_customers():
    """Get customers for POS"""
    customers = get_customers_for_pos()
    return jsonify(customers)


@app.route("/api/pos/sale", methods=["POST"])
def api_pos_sale():
    """
    Process a sale - ALL CALCULATIONS DONE HERE IN FLASK
    
    Receives cart items, calculates totals, VAT, posts to GL
    """
    try:
        data = request.get_json()
        items = data.get("items", [])
        customer_id = data.get("customer_id", "")
        payment_method = data.get("payment_method", "cash")
        
        if not items:
            return jsonify({"success": False, "error": "Cart is empty"})
        
        # Calculate totals - ALL IN FLASK
        total_incl = Decimal("0")
        total_excl = Decimal("0")
        total_vat = Decimal("0")
        total_cost = Decimal("0")
        
        line_items = []
        
        for item in items:
            price = Decimal(str(item.get("price", 0)))
            cost = Decimal(str(item.get("cost", 0)))
            qty = int(item.get("quantity", 1))
            is_zero_rated = item.get("is_zero_rated", False)
            
            line_total = price * qty
            
            # Calculate VAT
            if is_zero_rated:
                vat_info = VAT.calculate_from_inclusive(line_total, VAT.ZERO_RATE)
            else:
                vat_info = VAT.calculate_from_inclusive(line_total)
            
            total_incl += vat_info["inclusive"]
            total_excl += vat_info["exclusive"]
            total_vat += vat_info["vat"]
            total_cost += cost * qty
            
            line_items.append({
                "item_id": item.get("id"),
                "code": item.get("code", ""),
                "description": item.get("description", ""),
                "quantity": qty,
                "price": float(price),
                "line_total": float(line_total),
                "vat": float(vat_info["vat"]),
                "cost": float(cost)
            })
        
        # Generate invoice number
        invoice_number = DocumentNumbers.get_next("INV", "invoices", "invoice_number")
        
        # Get customer name
        customer_name = "Walk-in Customer"
        if customer_id:
            cust = db.select_one("customers", customer_id)
            if cust:
                customer_name = cust.get("name", "Customer")
        
        # Create invoice record
        invoice_id = generate_id()
        invoice_record = {
            "id": invoice_id,
            "invoice_number": invoice_number,
            "date": today(),
            "customer_id": customer_id or None,
            "customer_name": customer_name,
            "items": json.dumps(line_items),
            "subtotal": float(total_excl),
            "vat": float(total_vat),
            "total": float(total_incl),
            "payment_method": payment_method,
            "status": "paid" if payment_method != "account" else "outstanding",
            "created_at": now()
        }
        
        success, result = db.insert("invoices", invoice_record)
        if not success:
            return jsonify({"success": False, "error": f"Failed to save invoice: {result}"})
        
        # POST TO GENERAL LEDGER
        description = f"Sale {invoice_number} - {customer_name}"
        
        entry = JournalEntry(
            date=today(),
            reference=invoice_number,
            description=description,
            trans_type=TransactionType.SALE,
            source_type="invoice",
            source_id=invoice_id
        )
        
        # Debit: Cash/Bank or Debtors
        if payment_method == "account":
            entry.debit(AccountCodes.DEBTORS, total_incl)
            # Update customer balance
            update_customer_balance(customer_id, total_incl)
        else:
            entry.debit(AccountCodes.BANK, total_incl)
        
        # Credit: Sales (excl VAT)
        entry.credit(AccountCodes.SALES, total_excl)
        
        # Credit: VAT Output
        if total_vat > 0:
            entry.credit(AccountCodes.VAT_OUTPUT, total_vat)
        
        # Post the sale entry
        success, result = entry.post()
        if not success:
            return jsonify({"success": False, "error": f"Failed to post to ledger: {result}"})
        
        # POST COST OF GOODS SOLD
        if total_cost > 0:
            cogs_entry = JournalEntry(
                date=today(),
                reference=invoice_number,
                description=f"COGS - {invoice_number}",
                trans_type=TransactionType.SALE,
                source_type="invoice",
                source_id=invoice_id
            )
            
            cogs_entry.debit(AccountCodes.COGS, total_cost)
            cogs_entry.credit(AccountCodes.STOCK, total_cost)
            
            cogs_entry.post()
        
        # REDUCE STOCK QUANTITIES
        for item in line_items:
            reduce_stock(item["item_id"], item["quantity"])
        
        # Return success with receipt data
        return jsonify({
            "success": True,
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "total": float(total_incl),
            "total_formatted": Money.format(total_incl),
            "vat": float(total_vat),
            "vat_formatted": Money.format(total_vat),
            "payment_method": payment_method.title(),
            "customer_name": customer_name,
            "date": today(),
            "items_count": len(line_items)
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════════
# POS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/pos")
def pos_page():
    """POS page"""
    
    from piece1_core import UserSession
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    pos_js = '''
<script>
let stockItems = [];
let customers = [];
let cart = [];

document.addEventListener('DOMContentLoaded', loadData);

async function loadData() {
    document.getElementById('loading').style.display = 'flex';
    document.getElementById('products').style.display = 'none';
    
    try {
        const [stockRes, custRes] = await Promise.all([
            fetch('/api/pos/stock'),
            fetch('/api/pos/customers')
        ]);
        
        stockItems = await stockRes.json();
        customers = await custRes.json();
        
        renderProducts();
        renderCustomers();
        
        document.getElementById('loading').style.display = 'none';
        document.getElementById('products').style.display = 'block';
        
    } catch (error) {
        alert('Failed to load: ' + error.message);
    }
}

function renderProducts() {
    const search = document.getElementById('search').value.toLowerCase();
    const container = document.getElementById('product-grid');
    
    let html = '';
    let count = 0;
    
    for (const item of stockItems) {
        if (item.quantity <= 0) continue;
        
        if (search) {
            const m1 = item.description.toLowerCase().includes(search);
            const m2 = (item.code || '').toLowerCase().includes(search);
            if (!m1 && !m2) continue;
        }
        
        if (count >= 100) break;
        count++;
        
        const sc = item.quantity <= 5 ? ' low' : '';
        
        html += '<div class="product-item" onclick="addToCart(\\''+item.id+'\\')">';
        html += '<div class="product-name">'+escHtml(item.description)+'</div>';
        html += '<div class="product-price">'+item.price_formatted+'</div>';
        html += '<div class="product-stock'+sc+'">'+item.quantity+' in stock</div>';
        html += '</div>';
    }
    
    if (!html) {
        html = '<div style="text-align:center;padding:40px;color:#606070;">No products found</div>';
    }
    
    container.innerHTML = html;
}

function renderCustomers() {
    const sel = document.getElementById('customer-select');
    let html = '<option value="">Walk-in Customer</option>';
    
    for (const c of customers) {
        html += '<option value="'+c.id+'">'+escHtml(c.name)+'</option>';
    }
    
    sel.innerHTML = html;
}

function addToCart(itemId) {
    const item = stockItems.find(i => i.id === itemId);
    if (!item) return;
    
    const existing = cart.find(c => c.id === itemId);
    if (existing) {
        existing.quantity++;
    } else {
        cart.push({
            id: item.id,
            code: item.code,
            description: item.description,
            price: item.price,
            price_formatted: item.price_formatted,
            cost: item.cost,
            quantity: 1,
            is_zero_rated: item.is_zero_rated
        });
    }
    
    renderCart();
}

function renderCart() {
    const container = document.getElementById('cart-items');
    const totalEl = document.getElementById('cart-total');
    
    if (cart.length === 0) {
        container.innerHTML = '<div class="cart-empty">Cart is empty</div>';
        totalEl.textContent = 'R 0.00';
        return;
    }
    
    let html = '';
    let total = 0;
    
    for (let i = 0; i < cart.length; i++) {
        const item = cart[i];
        const lineTotal = item.price * item.quantity;
        total += lineTotal;
        
        html += '<div class="cart-item">';
        html += '<div>';
        html += '<div class="cart-item-name">'+escHtml(item.description)+'</div>';
        html += '<div class="cart-item-details">'+item.price_formatted+' × '+item.quantity+'</div>';
        html += '</div>';
        html += '<div style="display:flex;align-items:center;gap:8px;">';
        html += '<span class="cart-item-price">R '+lineTotal.toFixed(2)+'</span>';
        html += '<button class="btn btn-sm btn-red" onclick="removeFromCart('+i+')">×</button>';
        html += '</div></div>';
    }
    
    container.innerHTML = html;
    totalEl.textContent = 'R ' + total.toFixed(2);
}

function removeFromCart(index) {
    cart.splice(index, 1);
    renderCart();
}

function clearCart() {
    cart = [];
    renderCart();
}

async function processSale(method) {
    if (cart.length === 0) {
        alert('Cart is empty');
        return;
    }
    
    const customerId = document.getElementById('customer-select').value;
    
    // Disable buttons
    document.querySelectorAll('.cart-actions .btn').forEach(b => b.disabled = true);
    
    try {
        const response = await fetch('/api/pos/sale', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                items: cart,
                customer_id: customerId,
                payment_method: method
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showReceipt(result);
            cart = [];
            renderCart();
            loadData();
        } else {
            alert('Error: ' + result.error);
        }
        
    } catch (error) {
        alert('Failed: ' + error.message);
    }
    
    document.querySelectorAll('.cart-actions .btn').forEach(b => b.disabled = false);
}

function showReceipt(data) {
    document.getElementById('r-number').textContent = data.invoice_number;
    document.getElementById('r-total').textContent = data.total_formatted;
    document.getElementById('r-vat').textContent = data.vat_formatted;
    document.getElementById('r-method').textContent = data.payment_method;
    document.getElementById('r-customer').textContent = data.customer_name;
    document.getElementById('receipt-modal').classList.add('show');
}

function closeReceipt() {
    document.getElementById('receipt-modal').classList.remove('show');
}

function escHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

document.getElementById('search').addEventListener('input', renderProducts);
</script>
'''
    
    content = '''
    <div class="pos-layout">
        <!-- Products Section -->
        <div class="card">
            <input type="text" id="search" class="form-input" 
                   placeholder="Search products..." style="margin-bottom: 12px;">
            
            <div id="loading" class="loading">
                <div class="spinner"></div>
            </div>
            
            <div id="products" style="display: none;">
                <div id="product-grid" class="product-grid"></div>
            </div>
        </div>
        
        <!-- Cart Section -->
        <div class="cart">
            <div class="cart-header">
                <h3 class="cart-title">Cart</h3>
                <button class="btn btn-sm btn-ghost" onclick="clearCart()">Clear</button>
            </div>
            
            <div style="margin-bottom: 12px;">
                <select id="customer-select" class="form-select">
                    <option value="">Walk-in Customer</option>
                </select>
            </div>
            
            <div id="cart-items" class="cart-items">
                <div class="cart-empty">Cart is empty</div>
            </div>
            
            <div class="cart-total">
                <div class="cart-total-label">Total</div>
                <div class="cart-total-value" id="cart-total">R 0.00</div>
            </div>
            
            <div class="cart-actions">
                <button class="btn btn-green" onclick="processSale('cash')">💵 Cash</button>
                <button class="btn btn-blue" onclick="processSale('card')">💳 Card</button>
            </div>
            <button class="btn btn-purple btn-block mt-sm" onclick="processSale('account')">
                📋 Account
            </button>
        </div>
    </div>
    
    <!-- Receipt Modal -->
    <div class="modal-overlay" id="receipt-modal">
        <div class="modal" style="max-width: 400px;">
            <div class="modal-header">
                <h3 class="modal-title">✓ Sale Complete</h3>
                <button class="modal-close" onclick="closeReceipt()">&times;</button>
            </div>
            <div class="modal-body" style="text-align: center;">
                <div style="font-size: 14px; color: #606070; margin-bottom: 4px;">Invoice</div>
                <div id="r-number" style="font-size: 24px; font-weight: 700; margin-bottom: 20px;"></div>
                
                <div style="font-size: 14px; color: #606070; margin-bottom: 4px;">Total</div>
                <div id="r-total" style="font-size: 36px; font-weight: 800; color: #10b981; margin-bottom: 12px;"></div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 20px; text-align: left;">
                    <div>
                        <div style="font-size: 11px; color: #606070; text-transform: uppercase;">VAT</div>
                        <div id="r-vat" style="font-weight: 600;"></div>
                    </div>
                    <div>
                        <div style="font-size: 11px; color: #606070; text-transform: uppercase;">Payment</div>
                        <div id="r-method" style="font-weight: 600;"></div>
                    </div>
                    <div style="grid-column: 1 / -1;">
                        <div style="font-size: 11px; color: #606070; text-transform: uppercase;">Customer</div>
                        <div id="r-customer" style="font-weight: 600;"></div>
                    </div>
                </div>
            </div>
            <div class="modal-footer" style="justify-content: center;">
                <button class="btn btn-primary" onclick="closeReceipt()">Done</button>
            </div>
        </div>
    </div>
    ''' + pos_js
    
    return page_wrapper("Point of Sale", content, active="pos", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 6
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 6 COMPLETE - Point of Sale

Contains:
✓ POS page with product grid
✓ Real-time product search
✓ Shopping cart management
✓ Customer selection (walk-in or account)
✓ Multiple payment methods:
  - Cash
  - Card
  - Account (adds to customer balance)
✓ All calculations done in Flask:
  - Line totals
  - VAT calculation (15% standard, 0% for zero-rated)
  - Invoice totals
✓ Proper GL posting:
  - DR Bank/Debtors (total incl VAT)
  - CR Sales (excl VAT)
  - CR VAT Output
  - DR Cost of Goods Sold
  - CR Stock
✓ Stock quantity reduction
✓ Customer balance update for account sales
✓ Receipt modal with summary
✓ Invoice record creation

All financial calculations happen on the server.
JavaScript only handles UI interactions.

Next: Piece 7 - Stock Management
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 7: Stock Management                                                   ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Stock item listing with search                                            ║
║   - Add/Edit stock items                                                      ║
║   - Category management                                                       ║
║   - Stock take / adjustment                                                   ║
║   - Low stock alerts                                                          ║
║   - Stock valuation                                                           ║
║   - Import from CSV/JSON                                                      ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import request, redirect, jsonify
from decimal import Decimal
import json
import csv
import io

from piece1_core import (
    app, db, generate_id, now, today,
    Money, VAT, safe_string, UserSession
)
from piece2_accounts import AccountCodes
from piece3_journal import JournalEntry, TransactionType
from piece4_ui import (
    page_wrapper, success_message, error_message, info_message,
    badge, empty_state, table_html, form_input, form_select,
    modal_template
)


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK ITEM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_stock(include_inactive: bool = False) -> list:
    """Get all stock items"""
    items = db.select("stock_items", order="description")
    
    if not include_inactive:
        items = [i for i in items if i.get("active", True)]
    
    return items


def get_stock_item(item_id: str) -> dict:
    """Get single stock item"""
    return db.select_one("stock_items", item_id)


def get_stock_categories() -> list:
    """Get unique categories"""
    items = db.select("stock_items", columns="category")
    categories = set()
    
    for item in items:
        cat = item.get("category", "").strip()
        if cat:
            categories.add(cat)
    
    return sorted(list(categories))


def calculate_stock_valuation() -> dict:
    """Calculate total stock valuation"""
    items = get_all_stock()
    
    total_cost = Decimal("0")
    total_retail = Decimal("0")
    total_items = 0
    total_qty = 0
    
    for item in items:
        qty = int(item.get("quantity", 0) or 0)
        cost = Decimal(str(item.get("cost_price", 0) or 0))
        sell = Decimal(str(item.get("selling_price", 0) or 0))
        
        total_items += 1
        total_qty += qty
        total_cost += cost * qty
        total_retail += sell * qty
    
    return {
        "total_items": total_items,
        "total_quantity": total_qty,
        "total_cost": total_cost,
        "total_retail": total_retail,
        "potential_profit": total_retail - total_cost
    }


def get_low_stock_items(threshold: int = 5) -> list:
    """Get items below reorder level"""
    items = get_all_stock()
    
    low = []
    for item in items:
        qty = int(item.get("quantity", 0) or 0)
        reorder = int(item.get("reorder_level", threshold) or threshold)
        
        if qty <= reorder and qty > 0:
            item["_status"] = "low"
            low.append(item)
        elif qty <= 0:
            item["_status"] = "out"
            low.append(item)
    
    return low


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/stock")
def stock_list():
    """Stock listing page"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    items = get_all_stock()
    valuation = calculate_stock_valuation()
    low_stock = get_low_stock_items()
    
    # Build table rows
    rows = []
    for item in items:
        qty = int(item.get("quantity", 0) or 0)
        cost = Decimal(str(item.get("cost_price", 0) or 0))
        sell = Decimal(str(item.get("selling_price", 0) or 0))
        
        # Stock status badge
        if qty <= 0:
            qty_html = f'<span class="badge badge-red">{qty}</span>'
        elif qty <= 5:
            qty_html = f'<span class="badge badge-orange">{qty}</span>'
        else:
            qty_html = str(qty)
        
        # Zero-rated indicator
        desc = item.get("description", "")
        if VAT.is_zero_rated(desc, item.get("category", "")):
            desc += ' <span class="badge badge-blue">0%</span>'
        
        rows.append([
            item.get("code", "-"),
            desc,
            item.get("category", "-"),
            {"value": qty_html, "class": ""},
            {"value": Money.format(cost), "class": "number"},
            {"value": Money.format(sell), "class": "number"},
            f'<a href="/stock/{item["id"]}/edit" class="btn btn-sm btn-ghost">Edit</a>'
        ])
    
    table = table_html(
        headers=["Code", "Description", "Category", "Qty", 
                {"label": "Cost", "class": "number"}, 
                {"label": "Price", "class": "number"}, ""],
        rows=rows,
        empty_message="No stock items. Add your first item!"
    )
    
    # Low stock alert
    low_alert = ""
    if low_stock:
        low_count = len(low_stock)
        out_count = len([i for i in low_stock if i.get("_status") == "out"])
        low_alert = f'''
        <div class="alert alert-warning">
            ⚠️ {low_count} items need attention: {out_count} out of stock, {low_count - out_count} low stock
            <a href="/stock/low" class="btn btn-sm btn-ghost" style="margin-left: auto;">View</a>
        </div>
        '''
    
    content = f'''
    <div class="flex-between mb-lg">
        <div>
            <p class="text-muted">{valuation["total_items"]} items • {valuation["total_quantity"]} units</p>
        </div>
        <div class="btn-group">
            <a href="/stock/import" class="btn btn-ghost">Import</a>
            <a href="/stock/new" class="btn btn-primary">+ Add Item</a>
        </div>
    </div>
    
    {low_alert}
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{valuation["total_items"]}</div>
            <div class="stat-label">Items</div>
        </div>
        <div class="stat">
            <div class="stat-value">{valuation["total_quantity"]}</div>
            <div class="stat-label">Units</div>
        </div>
        <div class="stat">
            <div class="stat-value">{Money.format(valuation["total_cost"])}</div>
            <div class="stat-label">Cost Value</div>
        </div>
        <div class="stat">
            <div class="stat-value green">{Money.format(valuation["total_retail"])}</div>
            <div class="stat-label">Retail Value</div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Stock Items</h2>
            <input type="text" id="search" class="form-input" 
                   placeholder="Search..." style="width: 250px; margin: 0;"
                   onkeyup="filterTable(this.value)">
        </div>
        <div id="stock-table">
            {table}
        </div>
    </div>
    
    <script>
    function filterTable(q) {{
        q = q.toLowerCase();
        const rows = document.querySelectorAll('#stock-table tbody tr');
        rows.forEach(row => {{
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(q) ? '' : 'none';
        }});
    }}
    </script>
    '''
    
    return page_wrapper("Stock", content, active="stock", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# ADD / EDIT STOCK ITEM
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/stock/new", methods=["GET", "POST"])
def stock_new():
    """Add new stock item"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    message = ""
    
    if request.method == "POST":
        # Get form data
        code = request.form.get("code", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        quantity = int(request.form.get("quantity", 0) or 0)
        cost_price = Money.parse(request.form.get("cost_price", "0"))
        selling_price = Money.parse(request.form.get("selling_price", "0"))
        reorder_level = int(request.form.get("reorder_level", 5) or 5)
        
        if not description:
            message = error_message("Description is required")
        else:
            item = {
                "id": generate_id(),
                "code": code,
                "description": description,
                "category": category or "General",
                "quantity": quantity,
                "cost_price": float(cost_price),
                "selling_price": float(selling_price),
                "reorder_level": reorder_level,
                "active": True,
                "created_at": now()
            }
            
            success, result = db.insert("stock_items", item)
            
            if success:
                return redirect("/stock")
            else:
                message = error_message(f"Failed to save: {result}")
    
    categories = get_stock_categories()
    cat_options = [(c, c) for c in categories]
    cat_options.insert(0, ("General", "General"))
    
    content = f'''
    <a href="/stock" class="btn btn-ghost mb-lg">← Back to Stock</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">Add Stock Item</h2>
        
        {message}
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input" placeholder="SKU or barcode">
                </div>
                <div class="form-group">
                    <label class="form-label">Category</label>
                    <input type="text" name="category" class="form-input" 
                           list="categories" value="General">
                    <datalist id="categories">
                        {"".join([f'<option value="{c}">' for c in categories])}
                    </datalist>
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Description *</label>
                <input type="text" name="description" class="form-input" 
                       placeholder="Item name/description" required>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Quantity</label>
                    <input type="number" name="quantity" class="form-input" value="0" min="0">
                </div>
                <div class="form-group">
                    <label class="form-label">Reorder Level</label>
                    <input type="number" name="reorder_level" class="form-input" value="5" min="0">
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Cost Price</label>
                    <input type="text" name="cost_price" class="form-input" placeholder="0.00">
                </div>
                <div class="form-group">
                    <label class="form-label">Selling Price (incl VAT)</label>
                    <input type="text" name="selling_price" class="form-input" placeholder="0.00">
                </div>
            </div>
            
            <div class="btn-group mt-lg">
                <button type="submit" class="btn btn-primary">Save Item</button>
                <a href="/stock" class="btn btn-ghost">Cancel</a>
            </div>
        </form>
    </div>
    '''
    
    return page_wrapper("Add Stock Item", content, active="stock", user=user)


@app.route("/stock/<item_id>/edit", methods=["GET", "POST"])
def stock_edit(item_id):
    """Edit stock item"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    item = get_stock_item(item_id)
    if not item:
        return redirect("/stock")
    
    message = ""
    
    if request.method == "POST":
        # Check for delete
        if request.form.get("action") == "delete":
            db.update("stock_items", item_id, {"active": False})
            return redirect("/stock")
        
        # Update item
        updates = {
            "code": request.form.get("code", "").strip(),
            "description": request.form.get("description", "").strip(),
            "category": request.form.get("category", "General").strip(),
            "quantity": int(request.form.get("quantity", 0) or 0),
            "cost_price": float(Money.parse(request.form.get("cost_price", "0"))),
            "selling_price": float(Money.parse(request.form.get("selling_price", "0"))),
            "reorder_level": int(request.form.get("reorder_level", 5) or 5)
        }
        
        if not updates["description"]:
            message = error_message("Description is required")
        else:
            success, result = db.update("stock_items", item_id, updates)
            
            if success:
                message = success_message("Item updated")
                item.update(updates)
            else:
                message = error_message(f"Failed: {result}")
    
    categories = get_stock_categories()
    
    content = f'''
    <a href="/stock" class="btn btn-ghost mb-lg">← Back to Stock</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">Edit Stock Item</h2>
        
        {message}
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input" 
                           value="{safe_string(item.get("code", ""))}">
                </div>
                <div class="form-group">
                    <label class="form-label">Category</label>
                    <input type="text" name="category" class="form-input" 
                           list="categories" value="{safe_string(item.get("category", "General"))}">
                    <datalist id="categories">
                        {"".join([f'<option value="{c}">' for c in categories])}
                    </datalist>
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Description *</label>
                <input type="text" name="description" class="form-input" 
                       value="{safe_string(item.get("description", ""))}" required>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Quantity</label>
                    <input type="number" name="quantity" class="form-input" 
                           value="{item.get("quantity", 0)}" min="0">
                </div>
                <div class="form-group">
                    <label class="form-label">Reorder Level</label>
                    <input type="number" name="reorder_level" class="form-input" 
                           value="{item.get("reorder_level", 5)}" min="0">
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Cost Price</label>
                    <input type="text" name="cost_price" class="form-input" 
                           value="{item.get("cost_price", 0)}">
                </div>
                <div class="form-group">
                    <label class="form-label">Selling Price</label>
                    <input type="text" name="selling_price" class="form-input" 
                           value="{item.get("selling_price", 0)}">
                </div>
            </div>
            
            <div class="flex-between mt-lg">
                <button type="submit" class="btn btn-primary">Save Changes</button>
                <button type="submit" name="action" value="delete" class="btn btn-red"
                        onclick="return confirm('Delete this item?')">Delete</button>
            </div>
        </form>
    </div>
    '''
    
    return page_wrapper("Edit Stock Item", content, active="stock", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# LOW STOCK PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/stock/low")
def stock_low():
    """Low stock items page"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    items = get_low_stock_items()
    
    rows = []
    for item in items:
        qty = int(item.get("quantity", 0) or 0)
        
        if item.get("_status") == "out":
            status = '<span class="badge badge-red">OUT</span>'
        else:
            status = '<span class="badge badge-orange">LOW</span>'
        
        rows.append([
            item.get("code", "-"),
            item.get("description", ""),
            item.get("category", "-"),
            qty,
            item.get("reorder_level", 5),
            status,
            f'<a href="/stock/{item["id"]}/edit" class="btn btn-sm btn-ghost">Edit</a>'
        ])
    
    table = table_html(
        headers=["Code", "Description", "Category", "Qty", "Reorder At", "Status", ""],
        rows=rows,
        empty_message="All stock levels are healthy! 🎉"
    )
    
    content = f'''
    <a href="/stock" class="btn btn-ghost mb-lg">← Back to Stock</a>
    
    <div class="alert alert-warning mb-lg">
        ⚠️ These items are below their reorder level and need attention.
    </div>
    
    <div class="card">
        <h2 class="card-title mb-md">Low Stock Items</h2>
        {table}
    </div>
    '''
    
    return page_wrapper("Low Stock", content, active="stock", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/stock/import", methods=["GET", "POST"])
def stock_import():
    """Import stock from JSON"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    message = ""
    
    if request.method == "POST":
        data_str = request.form.get("data", "").strip()
        
        if not data_str:
            message = error_message("No data provided")
        else:
            try:
                data = json.loads(data_str)
                
                # Support different formats
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("stock", data.get("items", data.get("stock_items", [])))
                
                imported = 0
                for item in items:
                    # Map common field names
                    record = {
                        "id": generate_id(),
                        "code": str(item.get("code", item.get("sku", "")))[:50],
                        "description": str(item.get("description", item.get("name", item.get("desc", ""))))[:200],
                        "category": str(item.get("category", "General"))[:50],
                        "quantity": int(item.get("quantity", item.get("qty", 0)) or 0),
                        "cost_price": float(item.get("cost_price", item.get("cost", 0)) or 0),
                        "selling_price": float(item.get("selling_price", item.get("price", item.get("sell", 0))) or 0),
                        "reorder_level": int(item.get("reorder_level", 5) or 5),
                        "active": True,
                        "created_at": now()
                    }
                    
                    if record["description"]:
                        success, _ = db.insert("stock_items", record)
                        if success:
                            imported += 1
                
                message = success_message(f"Imported {imported} items")
                
            except json.JSONDecodeError:
                message = error_message("Invalid JSON format")
            except Exception as e:
                message = error_message(f"Error: {str(e)}")
    
    content = f'''
    <a href="/stock" class="btn btn-ghost mb-lg">← Back to Stock</a>
    
    <div class="card" style="max-width: 700px;">
        <h2 class="card-title mb-md">Import Stock</h2>
        
        {message}
        
        <div class="alert alert-info mb-md">
            Paste JSON data with stock items. Supported formats:
            <ul style="margin-top: 8px; margin-left: 20px;">
                <li>Array of items: [{{...}}, {{...}}]</li>
                <li>Object with "stock" or "items" key</li>
            </ul>
        </div>
        
        <form method="POST">
            <div class="form-group">
                <label class="form-label">JSON Data</label>
                <textarea name="data" class="form-textarea" rows="12" 
                          placeholder='[{{"code": "001", "description": "Item 1", "quantity": 10, "cost": 50, "price": 100}}]'></textarea>
            </div>
            
            <div class="btn-group">
                <button type="submit" class="btn btn-primary">Import</button>
                <a href="/stock" class="btn btn-ghost">Cancel</a>
            </div>
        </form>
    </div>
    '''
    
    return page_wrapper("Import Stock", content, active="stock", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK API
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/stock")
def api_stock_list():
    """API: Get all stock items"""
    items = get_all_stock()
    return jsonify(items)


@app.route("/api/stock/<item_id>")
def api_stock_item(item_id):
    """API: Get single stock item"""
    item = get_stock_item(item_id)
    if item:
        return jsonify(item)
    return jsonify({"error": "Not found"}), 404


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 7
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 7 COMPLETE - Stock Management

Contains:
✓ Stock listing with search
✓ Stock valuation (cost and retail)
✓ Low stock alerts
✓ Add new stock item
✓ Edit stock item
✓ Deactivate (soft delete) items
✓ Category management with datalist
✓ Import from JSON
✓ Low stock page
✓ Zero-rated item detection
✓ Stock API endpoints

Fields tracked:
- Code (SKU/barcode)
- Description
- Category
- Quantity
- Cost price
- Selling price (incl VAT)
- Reorder level
- Active status

Next: Piece 8 - Customers & Suppliers
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 8: Customers & Suppliers                                              ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Customer listing and CRUD                                                 ║
║   - Supplier listing and CRUD                                                 ║
║   - Balance tracking                                                          ║
║   - Transaction history                                                       ║
║   - Receive payments from customers                                           ║
║   - Make payments to suppliers                                                ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import request, redirect, jsonify
from decimal import Decimal

from piece1_core import (
    app, db, generate_id, now, today,
    Money, safe_string, UserSession
)
from piece2_accounts import AccountCodes
from piece3_journal import JournalEntry, Journal, TransactionType
from piece4_ui import (
    page_wrapper, success_message, error_message,
    badge, empty_state, table_html
)


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_customers(include_inactive: bool = False) -> list:
    """Get all customers"""
    customers = db.select("customers", order="name")
    
    if not include_inactive:
        customers = [c for c in customers if c.get("active", True)]
    
    return customers


def get_customer(customer_id: str) -> dict:
    """Get single customer"""
    return db.select_one("customers", customer_id)


def get_customer_invoices(customer_id: str) -> list:
    """Get all invoices for a customer"""
    invoices = db.select("invoices", {"customer_id": customer_id}, order="-date")
    return invoices


def get_customer_transactions(customer_id: str) -> list:
    """Get journal entries related to this customer"""
    entries = Journal.get_entries()
    return [e for e in entries if e.get("source_id") == customer_id or 
            (e.get("source_type") == "customer" and customer_id in str(e.get("description", "")))]


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOMER PAGES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/customers")
def customer_list():
    """Customer listing page"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    customers = get_all_customers()
    
    total_balance = sum(Decimal(str(c.get("balance", 0) or 0)) for c in customers)
    with_balance = len([c for c in customers if Decimal(str(c.get("balance", 0) or 0)) > 0])
    
    rows = []
    for cust in customers:
        balance = Decimal(str(cust.get("balance", 0) or 0))
        
        if balance > 0:
            bal_html = f'<span class="text-red font-bold">{Money.format(balance)}</span>'
        else:
            bal_html = Money.format(balance)
        
        rows.append([
            cust.get("code", "-"),
            f'<a href="/customers/{cust["id"]}">{safe_string(cust.get("name", ""))}</a>',
            cust.get("phone", "-"),
            cust.get("email", "-"),
            {"value": bal_html, "class": "number"},
            f'''<div class="btn-group">
                <a href="/customers/{cust["id"]}" class="btn btn-sm btn-ghost">View</a>
                <a href="/customers/{cust["id"]}/edit" class="btn btn-sm btn-ghost">Edit</a>
            </div>'''
        ])
    
    table = table_html(
        headers=["Code", "Name", "Phone", "Email", {"label": "Balance", "class": "number"}, ""],
        rows=rows,
        empty_message="No customers yet. Add your first customer!"
    )
    
    content = f'''
    <div class="flex-between mb-lg">
        <div>
            <p class="text-muted">{len(customers)} customers</p>
        </div>
        <a href="/customers/new" class="btn btn-primary">+ Add Customer</a>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(customers)}</div>
            <div class="stat-label">Customers</div>
        </div>
        <div class="stat">
            <div class="stat-value red">{Money.format(total_balance)}</div>
            <div class="stat-label">Total Owing</div>
        </div>
        <div class="stat">
            <div class="stat-value orange">{with_balance}</div>
            <div class="stat-label">With Balance</div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Customers</h2>
            <input type="text" id="search" class="form-input" 
                   placeholder="Search..." style="width: 250px; margin: 0;"
                   onkeyup="filterTable(this.value)">
        </div>
        <div id="customer-table">
            {table}
        </div>
    </div>
    
    <script>
    function filterTable(q) {{
        q = q.toLowerCase();
        const rows = document.querySelectorAll('#customer-table tbody tr');
        rows.forEach(row => {{
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(q) ? '' : 'none';
        }});
    }}
    </script>
    '''
    
    return page_wrapper("Customers", content, active="customers", user=user)


@app.route("/customers/new", methods=["GET", "POST"])
def customer_new():
    """Add new customer"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    message = ""
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        
        if not name:
            message = error_message("Name is required")
        else:
            customer = {
                "id": generate_id(),
                "code": request.form.get("code", "").strip(),
                "name": name,
                "phone": request.form.get("phone", "").strip(),
                "email": request.form.get("email", "").strip(),
                "address": request.form.get("address", "").strip(),
                "balance": 0,
                "active": True,
                "created_at": now()
            }
            
            success, result = db.insert("customers", customer)
            
            if success:
                return redirect("/customers")
            else:
                message = error_message(f"Failed: {result}")
    
    content = f'''
    <a href="/customers" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">Add Customer</h2>
        
        {message}
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input" placeholder="Customer code">
                </div>
                <div class="form-group">
                    <label class="form-label">Name *</label>
                    <input type="text" name="name" class="form-input" required>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="text" name="phone" class="form-input">
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Address</label>
                <textarea name="address" class="form-textarea" rows="2"></textarea>
            </div>
            
            <div class="btn-group mt-lg">
                <button type="submit" class="btn btn-primary">Save Customer</button>
                <a href="/customers" class="btn btn-ghost">Cancel</a>
            </div>
        </form>
    </div>
    '''
    
    return page_wrapper("Add Customer", content, active="customers", user=user)


@app.route("/customers/<customer_id>")
def customer_view(customer_id):
    """View customer details and history"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    customer = get_customer(customer_id)
    if not customer:
        return redirect("/customers")
    
    invoices = get_customer_invoices(customer_id)
    balance = Decimal(str(customer.get("balance", 0) or 0))
    
    # Invoice rows
    rows = []
    for inv in invoices[:20]:
        total = Decimal(str(inv.get("total", 0) or 0))
        status = inv.get("status", "draft")
        
        if status == "paid":
            status_badge = badge("Paid", "green")
        elif status == "outstanding":
            status_badge = badge("Outstanding", "orange")
        else:
            status_badge = badge(status.title(), "blue")
        
        rows.append([
            inv.get("invoice_number", "-"),
            inv.get("date", "")[:10],
            {"value": Money.format(total), "class": "number"},
            status_badge
        ])
    
    table = table_html(
        headers=["Invoice", "Date", {"label": "Total", "class": "number"}, "Status"],
        rows=rows,
        empty_message="No invoices yet"
    )
    
    content = f'''
    <a href="/customers" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="flex-between mb-lg">
        <div>
            <h1 style="font-size: 24px; font-weight: 700;">{safe_string(customer.get("name", ""))}</h1>
            <p class="text-muted">{safe_string(customer.get("phone", ""))} • {safe_string(customer.get("email", ""))}</p>
        </div>
        <div class="btn-group">
            <a href="/customers/{customer_id}/receive" class="btn btn-green">Receive Payment</a>
            <a href="/customers/{customer_id}/edit" class="btn btn-ghost">Edit</a>
        </div>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value{' red' if balance > 0 else ''}">{Money.format(balance)}</div>
            <div class="stat-label">Balance Owing</div>
        </div>
        <div class="stat">
            <div class="stat-value">{len(invoices)}</div>
            <div class="stat-label">Invoices</div>
        </div>
    </div>
    
    <div class="card">
        <h3 class="card-title mb-md">Invoices</h3>
        {table}
    </div>
    '''
    
    return page_wrapper(customer.get("name", "Customer"), content, active="customers", user=user)


@app.route("/customers/<customer_id>/edit", methods=["GET", "POST"])
def customer_edit(customer_id):
    """Edit customer"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    customer = get_customer(customer_id)
    if not customer:
        return redirect("/customers")
    
    message = ""
    
    if request.method == "POST":
        if request.form.get("action") == "delete":
            db.update("customers", customer_id, {"active": False})
            return redirect("/customers")
        
        updates = {
            "code": request.form.get("code", "").strip(),
            "name": request.form.get("name", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "address": request.form.get("address", "").strip()
        }
        
        if not updates["name"]:
            message = error_message("Name is required")
        else:
            success, _ = db.update("customers", customer_id, updates)
            if success:
                message = success_message("Updated")
                customer.update(updates)
    
    content = f'''
    <a href="/customers/{customer_id}" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">Edit Customer</h2>
        
        {message}
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input" 
                           value="{safe_string(customer.get("code", ""))}">
                </div>
                <div class="form-group">
                    <label class="form-label">Name *</label>
                    <input type="text" name="name" class="form-input" 
                           value="{safe_string(customer.get("name", ""))}" required>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="text" name="phone" class="form-input" 
                           value="{safe_string(customer.get("phone", ""))}">
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input" 
                           value="{safe_string(customer.get("email", ""))}">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Address</label>
                <textarea name="address" class="form-textarea" rows="2">{safe_string(customer.get("address", ""))}</textarea>
            </div>
            
            <div class="flex-between mt-lg">
                <button type="submit" class="btn btn-primary">Save Changes</button>
                <button type="submit" name="action" value="delete" class="btn btn-red"
                        onclick="return confirm('Delete this customer?')">Delete</button>
            </div>
        </form>
    </div>
    '''
    
    return page_wrapper("Edit Customer", content, active="customers", user=user)


@app.route("/customers/<customer_id>/receive", methods=["GET", "POST"])
def customer_receive_payment(customer_id):
    """Receive payment from customer"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    customer = get_customer(customer_id)
    if not customer:
        return redirect("/customers")
    
    balance = Decimal(str(customer.get("balance", 0) or 0))
    message = ""
    
    if request.method == "POST":
        amount = Money.parse(request.form.get("amount", "0"))
        reference = request.form.get("reference", "").strip()
        
        if amount <= 0:
            message = error_message("Enter a valid amount")
        else:
            # Create journal entry
            entry = JournalEntry(
                date=today(),
                reference=reference,
                description=f"Payment received - {customer.get('name', 'Customer')}",
                trans_type=TransactionType.RECEIPT,
                source_type="customer",
                source_id=customer_id
            )
            
            entry.debit(AccountCodes.BANK, amount)
            entry.credit(AccountCodes.DEBTORS, amount)
            
            success, result = entry.post()
            
            if success:
                # Update customer balance
                new_balance = balance - amount
                db.update("customers", customer_id, {"balance": float(new_balance)})
                
                return redirect(f"/customers/{customer_id}")
            else:
                message = error_message(f"Failed: {result}")
    
    content = f'''
    <a href="/customers/{customer_id}" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 500px;">
        <h2 class="card-title mb-md">Receive Payment</h2>
        <p class="text-muted mb-lg">From: {safe_string(customer.get("name", ""))}</p>
        
        {message}
        
        <div class="alert alert-info mb-lg">
            Current balance owing: <strong>{Money.format(balance)}</strong>
        </div>
        
        <form method="POST">
            <div class="form-group">
                <label class="form-label">Amount Received</label>
                <input type="text" name="amount" class="form-input" 
                       placeholder="0.00" required autofocus
                       style="font-size: 24px; text-align: center;">
            </div>
            
            <div class="form-group">
                <label class="form-label">Reference</label>
                <input type="text" name="reference" class="form-input" 
                       placeholder="Receipt number, bank reference, etc.">
            </div>
            
            <button type="submit" class="btn btn-green btn-block btn-lg">
                Receive Payment
            </button>
        </form>
    </div>
    '''
    
    return page_wrapper("Receive Payment", content, active="customers", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_suppliers(include_inactive: bool = False) -> list:
    """Get all suppliers"""
    suppliers = db.select("suppliers", order="name")
    
    if not include_inactive:
        suppliers = [s for s in suppliers if s.get("active", True)]
    
    return suppliers


def get_supplier(supplier_id: str) -> dict:
    """Get single supplier"""
    return db.select_one("suppliers", supplier_id)


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPLIER PAGES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/suppliers")
def supplier_list():
    """Supplier listing page"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    suppliers = get_all_suppliers()
    
    total_owed = sum(Decimal(str(s.get("balance", 0) or 0)) for s in suppliers)
    
    rows = []
    for supp in suppliers:
        balance = Decimal(str(supp.get("balance", 0) or 0))
        
        if balance > 0:
            bal_html = f'<span class="text-orange font-bold">{Money.format(balance)}</span>'
        else:
            bal_html = Money.format(balance)
        
        rows.append([
            supp.get("code", "-"),
            f'<a href="/suppliers/{supp["id"]}">{safe_string(supp.get("name", ""))}</a>',
            supp.get("phone", "-"),
            supp.get("email", "-"),
            {"value": bal_html, "class": "number"},
            f'''<div class="btn-group">
                <a href="/suppliers/{supp["id"]}" class="btn btn-sm btn-ghost">View</a>
                <a href="/suppliers/{supp["id"]}/edit" class="btn btn-sm btn-ghost">Edit</a>
            </div>'''
        ])
    
    table = table_html(
        headers=["Code", "Name", "Phone", "Email", {"label": "We Owe", "class": "number"}, ""],
        rows=rows,
        empty_message="No suppliers yet. Add your first supplier!"
    )
    
    content = f'''
    <div class="flex-between mb-lg">
        <div>
            <p class="text-muted">{len(suppliers)} suppliers</p>
        </div>
        <a href="/suppliers/new" class="btn btn-primary">+ Add Supplier</a>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(suppliers)}</div>
            <div class="stat-label">Suppliers</div>
        </div>
        <div class="stat">
            <div class="stat-value orange">{Money.format(total_owed)}</div>
            <div class="stat-label">Total We Owe</div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h2 class="card-title">Suppliers</h2>
        </div>
        {table}
    </div>
    '''
    
    return page_wrapper("Suppliers", content, active="suppliers", user=user)


@app.route("/suppliers/new", methods=["GET", "POST"])
def supplier_new():
    """Add new supplier"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    message = ""
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        
        if not name:
            message = error_message("Name is required")
        else:
            supplier = {
                "id": generate_id(),
                "code": request.form.get("code", "").strip(),
                "name": name,
                "phone": request.form.get("phone", "").strip(),
                "email": request.form.get("email", "").strip(),
                "address": request.form.get("address", "").strip(),
                "balance": 0,
                "active": True,
                "created_at": now()
            }
            
            success, _ = db.insert("suppliers", supplier)
            
            if success:
                return redirect("/suppliers")
            else:
                message = error_message("Failed to save")
    
    content = f'''
    <a href="/suppliers" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">Add Supplier</h2>
        
        {message}
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input">
                </div>
                <div class="form-group">
                    <label class="form-label">Name *</label>
                    <input type="text" name="name" class="form-input" required>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="text" name="phone" class="form-input">
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Address</label>
                <textarea name="address" class="form-textarea" rows="2"></textarea>
            </div>
            
            <div class="btn-group mt-lg">
                <button type="submit" class="btn btn-primary">Save Supplier</button>
                <a href="/suppliers" class="btn btn-ghost">Cancel</a>
            </div>
        </form>
    </div>
    '''
    
    return page_wrapper("Add Supplier", content, active="suppliers", user=user)


@app.route("/suppliers/<supplier_id>")
def supplier_view(supplier_id):
    """View supplier details"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    supplier = get_supplier(supplier_id)
    if not supplier:
        return redirect("/suppliers")
    
    balance = Decimal(str(supplier.get("balance", 0) or 0))
    
    content = f'''
    <a href="/suppliers" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="flex-between mb-lg">
        <div>
            <h1 style="font-size: 24px; font-weight: 700;">{safe_string(supplier.get("name", ""))}</h1>
            <p class="text-muted">{safe_string(supplier.get("phone", ""))} • {safe_string(supplier.get("email", ""))}</p>
        </div>
        <div class="btn-group">
            <a href="/suppliers/{supplier_id}/pay" class="btn btn-orange">Make Payment</a>
            <a href="/suppliers/{supplier_id}/edit" class="btn btn-ghost">Edit</a>
        </div>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value orange">{Money.format(balance)}</div>
            <div class="stat-label">We Owe Them</div>
        </div>
    </div>
    '''
    
    return page_wrapper(supplier.get("name", "Supplier"), content, active="suppliers", user=user)


@app.route("/suppliers/<supplier_id>/edit", methods=["GET", "POST"])
def supplier_edit(supplier_id):
    """Edit supplier"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    supplier = get_supplier(supplier_id)
    if not supplier:
        return redirect("/suppliers")
    
    message = ""
    
    if request.method == "POST":
        if request.form.get("action") == "delete":
            db.update("suppliers", supplier_id, {"active": False})
            return redirect("/suppliers")
        
        updates = {
            "code": request.form.get("code", "").strip(),
            "name": request.form.get("name", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "address": request.form.get("address", "").strip()
        }
        
        if not updates["name"]:
            message = error_message("Name is required")
        else:
            db.update("suppliers", supplier_id, updates)
            message = success_message("Updated")
            supplier.update(updates)
    
    content = f'''
    <a href="/suppliers/{supplier_id}" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">Edit Supplier</h2>
        
        {message}
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Code</label>
                    <input type="text" name="code" class="form-input" 
                           value="{safe_string(supplier.get("code", ""))}">
                </div>
                <div class="form-group">
                    <label class="form-label">Name *</label>
                    <input type="text" name="name" class="form-input" 
                           value="{safe_string(supplier.get("name", ""))}" required>
                </div>
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="text" name="phone" class="form-input" 
                           value="{safe_string(supplier.get("phone", ""))}">
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" name="email" class="form-input" 
                           value="{safe_string(supplier.get("email", ""))}">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Address</label>
                <textarea name="address" class="form-textarea" rows="2">{safe_string(supplier.get("address", ""))}</textarea>
            </div>
            
            <div class="flex-between mt-lg">
                <button type="submit" class="btn btn-primary">Save Changes</button>
                <button type="submit" name="action" value="delete" class="btn btn-red"
                        onclick="return confirm('Delete this supplier?')">Delete</button>
            </div>
        </form>
    </div>
    '''
    
    return page_wrapper("Edit Supplier", content, active="suppliers", user=user)


@app.route("/suppliers/<supplier_id>/pay", methods=["GET", "POST"])
def supplier_pay(supplier_id):
    """Make payment to supplier"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    supplier = get_supplier(supplier_id)
    if not supplier:
        return redirect("/suppliers")
    
    balance = Decimal(str(supplier.get("balance", 0) or 0))
    message = ""
    
    if request.method == "POST":
        amount = Money.parse(request.form.get("amount", "0"))
        reference = request.form.get("reference", "").strip()
        
        if amount <= 0:
            message = error_message("Enter a valid amount")
        else:
            # Create journal entry
            entry = JournalEntry(
                date=today(),
                reference=reference,
                description=f"Payment to - {supplier.get('name', 'Supplier')}",
                trans_type=TransactionType.PAYMENT,
                source_type="supplier",
                source_id=supplier_id
            )
            
            entry.debit(AccountCodes.CREDITORS, amount)
            entry.credit(AccountCodes.BANK, amount)
            
            success, result = entry.post()
            
            if success:
                # Update supplier balance
                new_balance = balance - amount
                db.update("suppliers", supplier_id, {"balance": float(new_balance)})
                
                return redirect(f"/suppliers/{supplier_id}")
            else:
                message = error_message(f"Failed: {result}")
    
    content = f'''
    <a href="/suppliers/{supplier_id}" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 500px;">
        <h2 class="card-title mb-md">Make Payment</h2>
        <p class="text-muted mb-lg">To: {safe_string(supplier.get("name", ""))}</p>
        
        {message}
        
        <div class="alert alert-info mb-lg">
            We owe them: <strong>{Money.format(balance)}</strong>
        </div>
        
        <form method="POST">
            <div class="form-group">
                <label class="form-label">Amount Paid</label>
                <input type="text" name="amount" class="form-input" 
                       placeholder="0.00" required autofocus
                       style="font-size: 24px; text-align: center;">
            </div>
            
            <div class="form-group">
                <label class="form-label">Reference</label>
                <input type="text" name="reference" class="form-input" 
                       placeholder="EFT reference, cheque number, etc.">
            </div>
            
            <button type="submit" class="btn btn-orange btn-block btn-lg">
                Make Payment
            </button>
        </form>
    </div>
    '''
    
    return page_wrapper("Make Payment", content, active="suppliers", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/customers")
def api_customers():
    """API: Get all customers"""
    return jsonify(get_all_customers())


@app.route("/api/suppliers")
def api_suppliers():
    """API: Get all suppliers"""
    return jsonify(get_all_suppliers())


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 8
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 8 COMPLETE - Customers & Suppliers

Contains:
✓ Customer listing with search
✓ Customer CRUD (add, edit, deactivate)
✓ Customer balance tracking
✓ Customer invoice history
✓ Receive payment from customer with GL posting:
  - DR Bank
  - CR Debtors
✓ Supplier listing
✓ Supplier CRUD
✓ Supplier balance tracking
✓ Make payment to supplier with GL posting:
  - DR Creditors
  - CR Bank
✓ API endpoints

All payments properly posted to General Ledger!

Next: Piece 9 - Invoices & Quotes
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 9: Invoices & Quotes                                                  ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import request, redirect, jsonify
from decimal import Decimal
import json

from piece1_core import (
    app, db, generate_id, now, today,
    Money, VAT, safe_string, UserSession, DocumentNumbers
)
from piece2_accounts import AccountCodes
from piece3_journal import JournalEntry, TransactionType
from piece4_ui import page_wrapper, success_message, error_message, badge, table_html


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_invoices():
    return db.select("invoices", order="-date")

def get_invoice(invoice_id):
    return db.select_one("invoices", invoice_id)

def get_all_quotes():
    return db.select("quotes", order="-date")

def get_quote(quote_id):
    return db.select_one("quotes", quote_id)

def get_stock_for_selection():
    items = db.select("stock_items", order="description")
    result = []
    for item in items:
        if not item.get("active", True):
            continue
        price = Decimal(str(item.get("selling_price", 0) or 0))
        desc = item.get("description", "")
        is_zero = VAT.is_zero_rated(desc, item.get("category", ""))
        result.append({
            "id": item["id"],
            "code": item.get("code", ""),
            "description": desc,
            "price": float(price),
            "price_formatted": Money.format(price),
            "is_zero_rated": is_zero
        })
    return result

def get_customers_for_selection():
    customers = db.select("customers", order="name")
    return [{"id": c["id"], "name": c.get("name", "")} for c in customers if c.get("active", True)]


# ═══════════════════════════════════════════════════════════════════════════════
# INVOICE PAGES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/invoices")
def invoice_list():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    invoices = get_all_invoices()
    total_value = sum(Decimal(str(i.get("total", 0) or 0)) for i in invoices)
    outstanding = sum(Decimal(str(i.get("total", 0) or 0)) for i in invoices if i.get("status") == "outstanding")
    
    rows = []
    for inv in invoices[:50]:
        status = inv.get("status", "draft")
        if status == "paid":
            sb = badge("Paid", "green")
        elif status == "outstanding":
            sb = badge("Outstanding", "orange")
        else:
            sb = badge(status.title(), "blue")
        
        rows.append([
            f'<a href="/invoices/{inv["id"]}">{inv.get("invoice_number", "-")}</a>',
            inv.get("date", "")[:10],
            safe_string(inv.get("customer_name", "Walk-in")),
            {"value": Money.format(Decimal(str(inv.get("total", 0)))), "class": "number"},
            sb
        ])
    
    table = table_html(
        headers=["Invoice #", "Date", "Customer", {"label": "Total", "class": "number"}, "Status"],
        rows=rows,
        empty_message="No invoices yet"
    )
    
    content = f'''
    <div class="flex-between mb-lg">
        <p class="text-muted">{len(invoices)} invoices</p>
        <a href="/invoices/new" class="btn btn-primary">+ New Invoice</a>
    </div>
    
    <div class="stats">
        <div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div>
        <div class="stat"><div class="stat-value green">{Money.format(total_value)}</div><div class="stat-label">Total Value</div></div>
        <div class="stat"><div class="stat-value orange">{Money.format(outstanding)}</div><div class="stat-label">Outstanding</div></div>
    </div>
    
    <div class="card">{table}</div>
    '''
    
    return page_wrapper("Invoices", content, active="invoices", user=user)


@app.route("/invoices/new", methods=["GET", "POST"])
def invoice_new():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    if request.method == "POST":
        return process_invoice_creation(request)
    
    stock = get_stock_for_selection()
    customers = get_customers_for_selection()
    inv_number = DocumentNumbers.get_next("INV", "invoices", "invoice_number")
    
    js = create_document_js("invoice")
    
    content = f'''
    <a href="/invoices" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card">
        <h2 class="card-title mb-md">New Invoice</h2>
        
        <form method="POST" id="doc-form">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Invoice Number</label>
                    <input type="text" name="doc_number" class="form-input" value="{inv_number}" readonly>
                </div>
                <div class="form-group">
                    <label class="form-label">Date</label>
                    <input type="date" name="date" class="form-input" value="{today()}">
                </div>
                <div class="form-group">
                    <label class="form-label">Customer</label>
                    <select name="customer_id" id="customer_id" class="form-select">
                        <option value="">Walk-in Customer</option>
                        {"".join([f'<option value="{c["id"]}">{safe_string(c["name"])}</option>' for c in customers])}
                    </select>
                </div>
            </div>
            
            <h3 style="margin: 20px 0 10px;">Line Items</h3>
            <input type="text" id="search-stock" class="form-input" placeholder="Search products to add..." onkeyup="searchStock(this.value)">
            <div id="search-results" style="max-height:150px;overflow-y:auto;margin-bottom:10px;"></div>
            
            <table class="table" id="lines-table">
                <thead><tr><th>Description</th><th>Qty</th><th>Price</th><th>Total</th><th></th></tr></thead>
                <tbody id="lines-body"></tbody>
                <tfoot>
                    <tr><td colspan="3" style="text-align:right;font-weight:600;">Subtotal:</td><td id="subtotal" style="text-align:right;">R 0.00</td><td></td></tr>
                    <tr><td colspan="3" style="text-align:right;font-weight:600;">VAT (15%):</td><td id="vat-total" style="text-align:right;">R 0.00</td><td></td></tr>
                    <tr><td colspan="3" style="text-align:right;font-weight:700;font-size:18px;">Total:</td><td id="grand-total" style="text-align:right;font-weight:700;font-size:18px;color:var(--green);">R 0.00</td><td></td></tr>
                </tfoot>
            </table>
            
            <input type="hidden" name="items_json" id="items-json">
            <input type="hidden" name="subtotal" id="subtotal-input">
            <input type="hidden" name="vat" id="vat-input">
            <input type="hidden" name="total" id="total-input">
            
            <div class="btn-group mt-lg">
                <button type="submit" class="btn btn-primary">Save Invoice</button>
                <a href="/invoices" class="btn btn-ghost">Cancel</a>
            </div>
        </form>
    </div>
    
    <script>
    const stockItems = {json.dumps(stock)};
    {js}
    </script>
    '''
    
    return page_wrapper("New Invoice", content, active="invoices", user=user)


def process_invoice_creation(req):
    """Process invoice form submission"""
    try:
        items_json = req.form.get("items_json", "[]")
        items = json.loads(items_json)
        
        if not items:
            return redirect("/invoices/new")
        
        customer_id = req.form.get("customer_id", "")
        customer_name = "Walk-in Customer"
        if customer_id:
            cust = db.select_one("customers", customer_id)
            if cust:
                customer_name = cust.get("name", "Customer")
        
        # Calculate totals in Flask
        subtotal = Decimal("0")
        total_vat = Decimal("0")
        total_cost = Decimal("0")
        
        for item in items:
            price = Decimal(str(item.get("price", 0)))
            qty = int(item.get("quantity", 1))
            is_zero = item.get("is_zero_rated", False)
            
            line_total = price * qty
            
            if is_zero:
                vat_info = VAT.calculate_from_inclusive(line_total, VAT.ZERO_RATE)
            else:
                vat_info = VAT.calculate_from_inclusive(line_total)
            
            subtotal += vat_info["exclusive"]
            total_vat += vat_info["vat"]
            total_cost += Decimal(str(item.get("cost", 0))) * qty
        
        total = subtotal + total_vat
        
        invoice_id = generate_id()
        invoice_number = req.form.get("doc_number", DocumentNumbers.get_next("INV", "invoices", "invoice_number"))
        
        invoice = {
            "id": invoice_id,
            "invoice_number": invoice_number,
            "date": req.form.get("date", today()),
            "customer_id": customer_id or None,
            "customer_name": customer_name,
            "items": items_json,
            "subtotal": float(subtotal),
            "vat": float(total_vat),
            "total": float(total),
            "status": "outstanding",
            "created_at": now()
        }
        
        db.insert("invoices", invoice)
        
        # Post to GL
        entry = JournalEntry(
            date=today(),
            reference=invoice_number,
            description=f"Invoice {invoice_number} - {customer_name}",
            trans_type=TransactionType.SALE,
            source_type="invoice",
            source_id=invoice_id
        )
        
        if customer_id:
            entry.debit(AccountCodes.DEBTORS, total)
            # Update customer balance
            cust = db.select_one("customers", customer_id)
            if cust:
                new_bal = Decimal(str(cust.get("balance", 0) or 0)) + total
                db.update("customers", customer_id, {"balance": float(new_bal)})
        else:
            entry.debit(AccountCodes.BANK, total)
        
        entry.credit(AccountCodes.SALES, subtotal)
        if total_vat > 0:
            entry.credit(AccountCodes.VAT_OUTPUT, total_vat)
        
        entry.post()
        
        # Post COGS
        if total_cost > 0:
            cogs = JournalEntry(
                date=today(),
                reference=invoice_number,
                description=f"COGS - {invoice_number}",
                trans_type=TransactionType.SALE
            )
            cogs.debit(AccountCodes.COGS, total_cost)
            cogs.credit(AccountCodes.STOCK, total_cost)
            cogs.post()
        
        return redirect("/invoices")
        
    except Exception as e:
        return redirect("/invoices/new")


@app.route("/invoices/<invoice_id>")
def invoice_view(invoice_id):
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    inv = get_invoice(invoice_id)
    if not inv:
        return redirect("/invoices")
    
    items = json.loads(inv.get("items", "[]"))
    
    item_rows = ""
    for item in items:
        line_total = Decimal(str(item.get("price", 0))) * int(item.get("quantity", 1))
        item_rows += f'''
        <tr>
            <td>{safe_string(item.get("description", ""))}</td>
            <td class="number">{item.get("quantity", 1)}</td>
            <td class="number">{Money.format(Decimal(str(item.get("price", 0))))}</td>
            <td class="number">{Money.format(line_total)}</td>
        </tr>
        '''
    
    status = inv.get("status", "draft")
    if status == "paid":
        sb = badge("Paid", "green")
    elif status == "outstanding":
        sb = badge("Outstanding", "orange")
    else:
        sb = badge(status.title(), "blue")
    
    content = f'''
    <a href="/invoices" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card">
        <div class="flex-between mb-lg">
            <div>
                <h1 style="font-size:24px;font-weight:700;">Invoice {safe_string(inv.get("invoice_number", ""))}</h1>
                <p class="text-muted">{inv.get("date", "")[:10]} • {safe_string(inv.get("customer_name", "Walk-in"))}</p>
            </div>
            <div>{sb}</div>
        </div>
        
        <table class="table">
            <thead><tr><th>Description</th><th class="number">Qty</th><th class="number">Price</th><th class="number">Total</th></tr></thead>
            <tbody>{item_rows}</tbody>
            <tfoot>
                <tr><td colspan="3" style="text-align:right;">Subtotal:</td><td class="number">{Money.format(Decimal(str(inv.get("subtotal", 0))))}</td></tr>
                <tr><td colspan="3" style="text-align:right;">VAT:</td><td class="number">{Money.format(Decimal(str(inv.get("vat", 0))))}</td></tr>
                <tr><td colspan="3" style="text-align:right;font-weight:700;">Total:</td><td class="number" style="font-weight:700;color:var(--green);">{Money.format(Decimal(str(inv.get("total", 0))))}</td></tr>
            </tfoot>
        </table>
    </div>
    '''
    
    return page_wrapper(f"Invoice {inv.get('invoice_number', '')}", content, active="invoices", user=user)


# ═══════════════════════════════════════════════════════════════════════════════
# QUOTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/quotes")
def quote_list():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    quotes = get_all_quotes()
    
    rows = []
    for q in quotes[:50]:
        rows.append([
            f'<a href="/quotes/{q["id"]}">{q.get("quote_number", "-")}</a>',
            q.get("date", "")[:10],
            safe_string(q.get("customer_name", "")),
            {"value": Money.format(Decimal(str(q.get("total", 0)))), "class": "number"},
            f'<a href="/quotes/{q["id"]}/convert" class="btn btn-sm btn-green">→ Invoice</a>'
        ])
    
    table = table_html(
        headers=["Quote #", "Date", "Customer", {"label": "Total", "class": "number"}, ""],
        rows=rows,
        empty_message="No quotes yet"
    )
    
    content = f'''
    <div class="flex-between mb-lg">
        <p class="text-muted">{len(quotes)} quotes</p>
        <a href="/quotes/new" class="btn btn-primary">+ New Quote</a>
    </div>
    
    <div class="card">{table}</div>
    '''
    
    return page_wrapper("Quotes", content, active="quotes", user=user)


@app.route("/quotes/new", methods=["GET", "POST"])
def quote_new():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    if request.method == "POST":
        return process_quote_creation(request)
    
    stock = get_stock_for_selection()
    customers = get_customers_for_selection()
    quote_number = DocumentNumbers.get_next("QUO", "quotes", "quote_number")
    
    js = create_document_js("quote")
    
    content = f'''
    <a href="/quotes" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card">
        <h2 class="card-title mb-md">New Quote</h2>
        
        <form method="POST" id="doc-form">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Quote Number</label>
                    <input type="text" name="doc_number" class="form-input" value="{quote_number}" readonly>
                </div>
                <div class="form-group">
                    <label class="form-label">Date</label>
                    <input type="date" name="date" class="form-input" value="{today()}">
                </div>
                <div class="form-group">
                    <label class="form-label">Customer</label>
                    <select name="customer_id" id="customer_id" class="form-select">
                        <option value="">Select Customer</option>
                        {"".join([f'<option value="{c["id"]}">{safe_string(c["name"])}</option>' for c in customers])}
                    </select>
                </div>
            </div>
            
            <h3 style="margin: 20px 0 10px;">Line Items</h3>
            <input type="text" id="search-stock" class="form-input" placeholder="Search products..." onkeyup="searchStock(this.value)">
            <div id="search-results" style="max-height:150px;overflow-y:auto;margin-bottom:10px;"></div>
            
            <table class="table" id="lines-table">
                <thead><tr><th>Description</th><th>Qty</th><th>Price</th><th>Total</th><th></th></tr></thead>
                <tbody id="lines-body"></tbody>
                <tfoot>
                    <tr><td colspan="3" style="text-align:right;font-weight:600;">Total:</td><td id="grand-total" style="text-align:right;font-weight:700;font-size:18px;color:var(--green);">R 0.00</td><td></td></tr>
                </tfoot>
            </table>
            
            <input type="hidden" name="items_json" id="items-json">
            <input type="hidden" name="total" id="total-input">
            
            <div class="btn-group mt-lg">
                <button type="submit" class="btn btn-primary">Save Quote</button>
                <a href="/quotes" class="btn btn-ghost">Cancel</a>
            </div>
        </form>
    </div>
    
    <script>
    const stockItems = {json.dumps(stock)};
    {js}
    </script>
    '''
    
    return page_wrapper("New Quote", content, active="quotes", user=user)


def process_quote_creation(req):
    try:
        items = json.loads(req.form.get("items_json", "[]"))
        if not items:
            return redirect("/quotes/new")
        
        customer_id = req.form.get("customer_id", "")
        customer_name = ""
        if customer_id:
            cust = db.select_one("customers", customer_id)
            if cust:
                customer_name = cust.get("name", "")
        
        total = Decimal("0")
        for item in items:
            total += Decimal(str(item.get("price", 0))) * int(item.get("quantity", 1))
        
        quote = {
            "id": generate_id(),
            "quote_number": req.form.get("doc_number", DocumentNumbers.get_next("QUO", "quotes", "quote_number")),
            "date": req.form.get("date", today()),
            "customer_id": customer_id or None,
            "customer_name": customer_name,
            "items": req.form.get("items_json", "[]"),
            "total": float(total),
            "status": "draft",
            "created_at": now()
        }
        
        db.insert("quotes", quote)
        return redirect("/quotes")
        
    except Exception:
        return redirect("/quotes/new")


@app.route("/quotes/<quote_id>")
def quote_view(quote_id):
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    q = get_quote(quote_id)
    if not q:
        return redirect("/quotes")
    
    items = json.loads(q.get("items", "[]"))
    
    item_rows = ""
    for item in items:
        line_total = Decimal(str(item.get("price", 0))) * int(item.get("quantity", 1))
        item_rows += f'''
        <tr>
            <td>{safe_string(item.get("description", ""))}</td>
            <td class="number">{item.get("quantity", 1)}</td>
            <td class="number">{Money.format(Decimal(str(item.get("price", 0))))}</td>
            <td class="number">{Money.format(line_total)}</td>
        </tr>
        '''
    
    content = f'''
    <a href="/quotes" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card">
        <div class="flex-between mb-lg">
            <div>
                <h1 style="font-size:24px;font-weight:700;">Quote {safe_string(q.get("quote_number", ""))}</h1>
                <p class="text-muted">{q.get("date", "")[:10]} • {safe_string(q.get("customer_name", ""))}</p>
            </div>
            <a href="/quotes/{quote_id}/convert" class="btn btn-green">Convert to Invoice</a>
        </div>
        
        <table class="table">
            <thead><tr><th>Description</th><th class="number">Qty</th><th class="number">Price</th><th class="number">Total</th></tr></thead>
            <tbody>{item_rows}</tbody>
            <tfoot>
                <tr><td colspan="3" style="text-align:right;font-weight:700;">Total:</td><td class="number" style="font-weight:700;color:var(--green);">{Money.format(Decimal(str(q.get("total", 0))))}</td></tr>
            </tfoot>
        </table>
    </div>
    '''
    
    return page_wrapper(f"Quote {q.get('quote_number', '')}", content, active="quotes", user=user)


@app.route("/quotes/<quote_id>/convert")
def quote_convert(quote_id):
    """Convert quote to invoice"""
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    q = get_quote(quote_id)
    if not q:
        return redirect("/quotes")
    
    # Create invoice from quote
    items = json.loads(q.get("items", "[]"))
    customer_id = q.get("customer_id", "")
    customer_name = q.get("customer_name", "")
    
    # Calculate with VAT
    subtotal = Decimal("0")
    total_vat = Decimal("0")
    
    for item in items:
        price = Decimal(str(item.get("price", 0)))
        qty = int(item.get("quantity", 1))
        line_total = price * qty
        vat_info = VAT.calculate_from_inclusive(line_total)
        subtotal += vat_info["exclusive"]
        total_vat += vat_info["vat"]
    
    total = subtotal + total_vat
    
    invoice_id = generate_id()
    invoice_number = DocumentNumbers.get_next("INV", "invoices", "invoice_number")
    
    invoice = {
        "id": invoice_id,
        "invoice_number": invoice_number,
        "date": today(),
        "customer_id": customer_id or None,
        "customer_name": customer_name,
        "items": q.get("items", "[]"),
        "subtotal": float(subtotal),
        "vat": float(total_vat),
        "total": float(total),
        "status": "outstanding",
        "from_quote": quote_id,
        "created_at": now()
    }
    
    db.insert("invoices", invoice)
    db.update("quotes", quote_id, {"status": "converted"})
    
    # Post to GL
    entry = JournalEntry(
        date=today(),
        reference=invoice_number,
        description=f"Invoice {invoice_number} - {customer_name}",
        trans_type=TransactionType.SALE,
        source_type="invoice",
        source_id=invoice_id
    )
    
    if customer_id:
        entry.debit(AccountCodes.DEBTORS, total)
        cust = db.select_one("customers", customer_id)
        if cust:
            new_bal = Decimal(str(cust.get("balance", 0) or 0)) + total
            db.update("customers", customer_id, {"balance": float(new_bal)})
    else:
        entry.debit(AccountCodes.BANK, total)
    
    entry.credit(AccountCodes.SALES, subtotal)
    if total_vat > 0:
        entry.credit(AccountCodes.VAT_OUTPUT, total_vat)
    
    entry.post()
    
    return redirect(f"/invoices/{invoice_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED JAVASCRIPT FOR DOCUMENT CREATION
# ═══════════════════════════════════════════════════════════════════════════════

def create_document_js(doc_type):
    return '''
let lines = [];

function searchStock(q) {
    const results = document.getElementById('search-results');
    if (!q || q.length < 2) {
        results.innerHTML = '';
        return;
    }
    q = q.toLowerCase();
    let html = '';
    for (const item of stockItems) {
        if (item.description.toLowerCase().includes(q) || (item.code || '').toLowerCase().includes(q)) {
            html += '<div class="product-item" style="margin-bottom:5px;padding:10px;" onclick=\\'addLine(\"'+item.id+'\")\\'>'+escHtml(item.description)+' - '+item.price_formatted+'</div>';
        }
    }
    results.innerHTML = html || '<div style="padding:10px;color:#606070;">No matches</div>';
}

function addLine(itemId) {
    const item = stockItems.find(i => i.id === itemId);
    if (!item) return;
    
    const existing = lines.find(l => l.id === itemId);
    if (existing) {
        existing.quantity++;
    } else {
        lines.push({
            id: item.id,
            code: item.code,
            description: item.description,
            price: item.price,
            quantity: 1,
            is_zero_rated: item.is_zero_rated,
            cost: item.cost || 0
        });
    }
    
    document.getElementById('search-stock').value = '';
    document.getElementById('search-results').innerHTML = '';
    renderLines();
}

function renderLines() {
    const tbody = document.getElementById('lines-body');
    let html = '';
    let total = 0;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const lineTotal = line.price * line.quantity;
        total += lineTotal;
        
        html += '<tr>';
        html += '<td>'+escHtml(line.description)+'</td>';
        html += '<td><input type="number" value="'+line.quantity+'" min="1" style="width:60px;padding:4px;background:#0a0a10;border:1px solid #1a1a2e;color:#f0f0f0;border-radius:4px;" onchange="updateQty('+i+',this.value)"></td>';
        html += '<td class="number">R '+line.price.toFixed(2)+'</td>';
        html += '<td class="number">R '+lineTotal.toFixed(2)+'</td>';
        html += '<td><button type="button" class="btn btn-sm btn-red" onclick="removeLine('+i+')">×</button></td>';
        html += '</tr>';
    }
    
    tbody.innerHTML = html || '<tr><td colspan="5" style="text-align:center;color:#606070;padding:30px;">Add items above</td></tr>';
    
    document.getElementById('grand-total').textContent = 'R ' + total.toFixed(2);
    document.getElementById('items-json').value = JSON.stringify(lines);
    document.getElementById('total-input').value = total.toFixed(2);
}

function updateQty(index, value) {
    lines[index].quantity = parseInt(value) || 1;
    renderLines();
}

function removeLine(index) {
    lines.splice(index, 1);
    renderLines();
}

function escHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

renderLines();
'''


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 9
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 9 COMPLETE - Invoices & Quotes

Contains:
✓ Invoice listing with totals and status
✓ Create new invoice with line items
✓ View invoice details
✓ Quote listing
✓ Create new quote
✓ View quote details
✓ Convert quote to invoice
✓ Proper GL posting on invoice creation:
  - DR Debtors (or Bank for walk-in)
  - CR Sales
  - CR VAT Output
  - DR COGS / CR Stock
✓ Customer balance update on invoice
✓ Shared JavaScript for document creation

All calculations done in Flask!

Next: Piece 10 - Expenses
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║   CLICK AI - COMPLETE BUSINESS MANAGEMENT SYSTEM                              ║
║   Piece 10: Expenses                                                          ║
║                                                                               ║
║   This piece contains:                                                        ║
║   - Expense listing                                                           ║
║   - Add expense manually                                                      ║
║   - AI receipt scanning with Opus                                             ║
║   - Category selection with proper GL accounts                                ║
║   - VAT handling (standard, zero-rated, exempt)                               ║
║   - Proper GL posting                                                         ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import request, redirect, jsonify
from decimal import Decimal
import json

from piece1_core import (
    app, db, generate_id, now, today,
    Money, VAT, safe_string, UserSession, OpusAI
)
from piece2_accounts import AccountCodes, Account, get_account_code
from piece3_journal import JournalEntry, TransactionType
from piece4_ui import page_wrapper, success_message, error_message, badge, table_html


# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_expenses():
    """Get all expenses"""
    return db.select("expenses", order="-date")


def get_expense(expense_id):
    """Get single expense"""
    return db.select_one("expenses", expense_id)


def get_expense_categories():
    """Get expense account categories for dropdown"""
    accounts = Account.get_expense_accounts()
    categories = []
    
    for acc in accounts:
        # Determine VAT type
        if acc.get("zero_rated"):
            vat_type = "zero"
        elif not acc.get("vat_applicable", True):
            vat_type = "exempt"
        else:
            vat_type = "standard"
        
        categories.append({
            "code": acc["code"],
            "name": acc["name"],
            "vat_type": vat_type
        })
    
    return categories


# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSE PAGES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/expenses")
def expense_list():
    """Expense listing page"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    expenses = get_all_expenses()
    
    total = sum(Decimal(str(e.get("amount", 0) or 0)) for e in expenses)
    total_vat = sum(Decimal(str(e.get("vat", 0) or 0)) for e in expenses)
    
    rows = []
    for exp in expenses[:50]:
        amount = Decimal(str(exp.get("amount", 0)))
        vat = Decimal(str(exp.get("vat", 0)))
        
        rows.append([
            exp.get("date", "")[:10],
            safe_string(exp.get("supplier", "-")),
            safe_string(exp.get("description", "")),
            safe_string(exp.get("category", "-")),
            {"value": Money.format(amount), "class": "number"},
            {"value": Money.format(vat), "class": "number text-muted"}
        ])
    
    table = table_html(
        headers=["Date", "Supplier", "Description", "Category", 
                {"label": "Amount", "class": "number"}, 
                {"label": "VAT", "class": "number"}],
        rows=rows,
        empty_message="No expenses yet"
    )
    
    content = f'''
    <div class="flex-between mb-lg">
        <p class="text-muted">{len(expenses)} expenses</p>
        <div class="btn-group">
            <a href="/expenses/scan" class="btn btn-orange">📷 Scan Receipt</a>
            <a href="/expenses/new" class="btn btn-primary">+ Add Expense</a>
        </div>
    </div>
    
    <div class="stats">
        <div class="stat">
            <div class="stat-value">{len(expenses)}</div>
            <div class="stat-label">Expenses</div>
        </div>
        <div class="stat">
            <div class="stat-value red">{Money.format(total)}</div>
            <div class="stat-label">Total Spent</div>
        </div>
        <div class="stat">
            <div class="stat-value green">{Money.format(total_vat)}</div>
            <div class="stat-label">VAT Claimable</div>
        </div>
    </div>
    
    <div class="card">{table}</div>
    '''
    
    return page_wrapper("Expenses", content, active="expenses", user=user)


@app.route("/expenses/new", methods=["GET", "POST"])
def expense_new():
    """Add new expense manually"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    message = ""
    
    if request.method == "POST":
        result = process_expense(request.form)
        if result["success"]:
            return redirect("/expenses")
        else:
            message = error_message(result["error"])
    
    categories = get_expense_categories()
    cat_options = "".join([
        f'<option value="{c["code"]}" data-vat="{c["vat_type"]}">{c["name"]}</option>' 
        for c in categories
    ])
    
    content = f'''
    <a href="/expenses" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">Add Expense</h2>
        
        {message}
        
        <form method="POST">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Date</label>
                    <input type="date" name="date" class="form-input" value="{today()}">
                </div>
                <div class="form-group">
                    <label class="form-label">Supplier</label>
                    <input type="text" name="supplier" class="form-input" placeholder="Supplier name">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Description</label>
                <input type="text" name="description" class="form-input" placeholder="What was purchased">
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Category</label>
                    <select name="category" id="category" class="form-select" onchange="updateVatType()">
                        <option value="">Select category...</option>
                        {cat_options}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Amount (incl VAT)</label>
                    <input type="text" name="amount" class="form-input" placeholder="0.00" required>
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">VAT Type</label>
                <select name="vat_type" id="vat_type" class="form-select">
                    <option value="standard">Standard Rate (15%)</option>
                    <option value="zero">Zero Rated (0%)</option>
                    <option value="exempt">Exempt (no VAT claim)</option>
                </select>
            </div>
            
            <div class="form-group">
                <label class="form-label">Reference</label>
                <input type="text" name="reference" class="form-input" placeholder="Invoice number, slip number, etc.">
            </div>
            
            <div class="btn-group mt-lg">
                <button type="submit" class="btn btn-primary">Save Expense</button>
                <a href="/expenses" class="btn btn-ghost">Cancel</a>
            </div>
        </form>
    </div>
    
    <script>
    function updateVatType() {{
        const cat = document.getElementById('category');
        const vatType = document.getElementById('vat_type');
        const selected = cat.options[cat.selectedIndex];
        if (selected && selected.dataset.vat) {{
            vatType.value = selected.dataset.vat;
        }}
    }}
    </script>
    '''
    
    return page_wrapper("Add Expense", content, active="expenses", user=user)


def process_expense(form_data, prefilled=None):
    """Process expense form data and post to GL"""
    
    try:
        supplier = form_data.get("supplier", "").strip() if form_data else prefilled.get("supplier", "")
        description = form_data.get("description", "").strip() if form_data else prefilled.get("description", "")
        amount_str = form_data.get("amount", "0") if form_data else str(prefilled.get("amount", 0))
        category_code = form_data.get("category", "") if form_data else prefilled.get("category", "")
        vat_type = form_data.get("vat_type", "standard") if form_data else prefilled.get("vat_type", "standard")
        reference = form_data.get("reference", "") if form_data else prefilled.get("reference", "")
        date = form_data.get("date", today()) if form_data else prefilled.get("date", today())
        
        amount = Money.parse(amount_str)
        
        if amount <= 0:
            return {"success": False, "error": "Enter a valid amount"}
        
        # Get expense account
        if category_code:
            expense_account = category_code
        else:
            expense_account = AccountCodes.GENERAL_EXPENSES
        
        # Calculate VAT based on type
        if vat_type == "zero":
            vat_info = VAT.calculate_from_inclusive(amount, VAT.ZERO_RATE)
        elif vat_type == "exempt":
            vat_info = {"exclusive": amount, "vat": Decimal("0"), "inclusive": amount}
        else:
            vat_info = VAT.calculate_from_inclusive(amount)
        
        # Get category name
        category_name = "General Expenses"
        cat_account = Account.get_by_code(expense_account)
        if cat_account:
            category_name = cat_account.get("name", category_name)
        
        # Create expense record
        expense_id = generate_id()
        expense = {
            "id": expense_id,
            "date": date,
            "supplier": supplier,
            "description": description,
            "category": category_name,
            "category_code": expense_account,
            "amount": float(vat_info["inclusive"]),
            "vat": float(vat_info["vat"]),
            "net": float(vat_info["exclusive"]),
            "vat_type": vat_type,
            "reference": reference,
            "created_at": now()
        }
        
        success, result = db.insert("expenses", expense)
        if not success:
            return {"success": False, "error": f"Failed to save: {result}"}
        
        # Post to GL
        entry_desc = f"{supplier}: {description}" if supplier else description
        
        entry = JournalEntry(
            date=date,
            reference=reference,
            description=entry_desc[:200],
            trans_type=TransactionType.EXPENSE,
            source_type="expense",
            source_id=expense_id
        )
        
        # Debit: Expense account (net amount)
        entry.debit(expense_account, vat_info["exclusive"])
        
        # Debit: VAT Input (if claimable)
        if vat_info["vat"] > 0 and vat_type != "exempt":
            entry.debit(AccountCodes.VAT_INPUT, vat_info["vat"])
        
        # Credit: Bank (total amount)
        entry.credit(AccountCodes.BANK, vat_info["inclusive"])
        
        success, result = entry.post()
        if not success:
            return {"success": False, "error": f"GL posting failed: {result}"}
        
        return {"success": True, "expense_id": expense_id}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# AI RECEIPT SCANNING
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/expenses/scan", methods=["GET"])
def expense_scan_page():
    """Receipt scanning page"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    categories = get_expense_categories()
    cat_options = "".join([
        f'<option value="{c["code"]}" data-vat="{c["vat_type"]}">{c["name"]}</option>' 
        for c in categories
    ])
    
    content = f'''
    <a href="/expenses" class="btn btn-ghost mb-lg">← Back</a>
    
    <div class="card" style="max-width: 600px;">
        <h2 class="card-title mb-md">📷 Scan Receipt</h2>
        <p class="text-muted mb-lg">Take a photo or upload an image. AI will extract the details.</p>
        
        <div class="btn-group mb-lg" style="justify-content: center;">
            <button class="btn btn-orange" onclick="startCamera()">📷 Use Camera</button>
            <label class="btn btn-ghost" style="cursor: pointer;">
                📁 Upload Image
                <input type="file" id="file-input" accept="image/*" style="display: none;" onchange="handleFile(this)">
            </label>
        </div>
        
        <video id="video" autoplay playsinline style="display:none;width:100%;max-width:400px;margin:0 auto;border-radius:12px;background:#000;"></video>
        <button id="capture-btn" class="btn btn-green btn-block mt-md" style="display:none;" onclick="capture()">📸 Capture</button>
        
        <canvas id="canvas" style="display:none;"></canvas>
        <img id="preview" style="display:none;max-width:100%;border-radius:12px;margin-top:16px;">
        
        <div id="processing" class="alert alert-info mt-lg" style="display:none;">
            🔄 AI is reading your receipt...
        </div>
    </div>
    
    <div class="card" id="result-card" style="max-width: 600px; display: none;">
        <h3 class="card-title mb-md">Receipt Details</h3>
        <p class="text-muted mb-md">Review and adjust if needed:</p>
        
        <form method="POST" action="/expenses/save-scanned">
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Date</label>
                    <input type="date" name="date" id="r-date" class="form-input" value="{today()}">
                </div>
                <div class="form-group">
                    <label class="form-label">Supplier</label>
                    <input type="text" name="supplier" id="r-supplier" class="form-input">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">Description</label>
                <input type="text" name="description" id="r-description" class="form-input">
            </div>
            
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Category</label>
                    <select name="category" id="r-category" class="form-select">
                        <option value="">Select...</option>
                        {cat_options}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Amount (incl VAT)</label>
                    <input type="text" name="amount" id="r-amount" class="form-input" 
                           style="font-size: 20px; font-weight: 700;">
                </div>
            </div>
            
            <div class="form-group">
                <label class="form-label">VAT Type</label>
                <select name="vat_type" id="r-vat-type" class="form-select">
                    <option value="standard">Standard Rate (15%)</option>
                    <option value="zero">Zero Rated (0%)</option>
                    <option value="exempt">Exempt (no VAT)</option>
                </select>
            </div>
            
            <button type="submit" class="btn btn-green btn-block btn-lg">
                ✓ Save Expense
            </button>
        </form>
    </div>
    
    <script>
    let stream = null;
    
    function startCamera() {{
        navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: "environment" }} }})
            .then(s => {{
                stream = s;
                const video = document.getElementById('video');
                video.srcObject = s;
                video.style.display = 'block';
                document.getElementById('capture-btn').style.display = 'block';
            }})
            .catch(e => alert('Camera error: ' + e.message));
    }}
    
    function capture() {{
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        
        const imageData = canvas.toDataURL('image/jpeg', 0.8);
        
        if (stream) {{
            stream.getTracks().forEach(t => t.stop());
        }}
        video.style.display = 'none';
        document.getElementById('capture-btn').style.display = 'none';
        
        document.getElementById('preview').src = imageData;
        document.getElementById('preview').style.display = 'block';
        
        processImage(imageData);
    }}
    
    function handleFile(input) {{
        if (input.files && input.files[0]) {{
            const reader = new FileReader();
            reader.onload = e => {{
                document.getElementById('preview').src = e.target.result;
                document.getElementById('preview').style.display = 'block';
                processImage(e.target.result);
            }};
            reader.readAsDataURL(input.files[0]);
        }}
    }}
    
    async function processImage(imageData) {{
        document.getElementById('processing').style.display = 'block';
        document.getElementById('result-card').style.display = 'none';
        
        try {{
            const response = await fetch('/api/expenses/scan', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{ image: imageData }})
            }});
            
            const result = await response.json();
            
            document.getElementById('processing').style.display = 'none';
            document.getElementById('result-card').style.display = 'block';
            
            if (result.supplier) document.getElementById('r-supplier').value = result.supplier;
            if (result.description) document.getElementById('r-description').value = result.description;
            if (result.amount) document.getElementById('r-amount').value = result.amount;
            if (result.category) {{
                // Try to match category
                const catSelect = document.getElementById('r-category');
                for (let i = 0; i < catSelect.options.length; i++) {{
                    if (catSelect.options[i].text.toLowerCase().includes(result.category.toLowerCase())) {{
                        catSelect.selectedIndex = i;
                        break;
                    }}
                }}
            }}
            if (result.is_zero_rated) {{
                document.getElementById('r-vat-type').value = 'zero';
            }}
            
            if (result.error) {{
                console.log('AI note:', result.error);
            }}
            
        }} catch (error) {{
            document.getElementById('processing').style.display = 'none';
            document.getElementById('result-card').style.display = 'block';
            console.error('Scan error:', error);
        }}
    }}
    </script>
    '''
    
    return page_wrapper("Scan Receipt", content, active="expenses", user=user)


@app.route("/api/expenses/scan", methods=["POST"])
def api_scan_receipt():
    """API: Process receipt image with AI"""
    
    try:
        data = request.get_json()
        image_data = data.get("image", "")
        
        if not image_data:
            return jsonify({"error": "No image provided"})
        
        # Clean base64 string
        if "," in image_data:
            image_data = image_data.split(",")[1]
        
        # Call Opus AI to read receipt
        result = OpusAI.read_receipt(image_data)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/expenses/save-scanned", methods=["POST"])
def expense_save_scanned():
    """Save expense from scanned receipt"""
    
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    result = process_expense(request.form)
    
    if result["success"]:
        return redirect("/expenses")
    else:
        # Show error and redirect back
        return redirect("/expenses/scan")


# ═══════════════════════════════════════════════════════════════════════════════
# EXPENSE API
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/expenses")
def api_expenses():
    """API: Get all expenses"""
    return jsonify(get_all_expenses())


# ═══════════════════════════════════════════════════════════════════════════════
# END OF PIECE 10
# ═══════════════════════════════════════════════════════════════════════════════

"""
PIECE 10 COMPLETE - Expenses

Contains:
✓ Expense listing with totals
✓ Add expense manually
✓ Category dropdown from GL expense accounts
✓ VAT type selection (standard/zero/exempt)
✓ AI receipt scanning with Opus:
  - Camera capture
  - Image upload
  - Automatic extraction of supplier, description, amount
  - Category suggestion
  - Zero-rated detection
✓ Proper GL posting:
  - DR Expense account (net)
  - DR VAT Input (if claimable)
  - CR Bank (total)
✓ Expense API

All calculations done in Flask!

Next: Piece 11 - Reports
"""
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║   CLICK AI - Piece 11: Reports                                                ║
║   ALL REPORTS PULL FROM THE JOURNAL - REAL DOUBLE-ENTRY DATA                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from flask import request, redirect
from decimal import Decimal

from piece1_core import app, db, today, format_date, Money, UserSession, FinancialPeriod
from piece2_accounts import Account
from piece3_journal import Journal
from piece4_ui import page_wrapper, table_html, badge


@app.route("/reports")
def reports_menu():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    content = '''
    <h1 style="font-size: 24px; font-weight: 700; margin-bottom: 24px;">Reports</h1>
    <div class="report-grid">
        <a href="/reports/trial-balance" class="report-card"><div class="report-card-icon">⚖️</div><h3 class="report-card-title">Trial Balance</h3><p class="report-card-desc">All accounts with debit/credit balances</p></a>
        <a href="/reports/income-statement" class="report-card"><div class="report-card-icon">📈</div><h3 class="report-card-title">Income Statement</h3><p class="report-card-desc">Profit & Loss report</p></a>
        <a href="/reports/balance-sheet" class="report-card"><div class="report-card-icon">🏦</div><h3 class="report-card-title">Balance Sheet</h3><p class="report-card-desc">Assets, Liabilities, Equity</p></a>
        <a href="/reports/vat" class="report-card"><div class="report-card-icon">🏛️</div><h3 class="report-card-title">VAT Report</h3><p class="report-card-desc">Output minus Input VAT</p></a>
        <a href="/reports/sales" class="report-card"><div class="report-card-icon">💰</div><h3 class="report-card-title">Sales Report</h3><p class="report-card-desc">Invoice summary</p></a>
        <a href="/reports/debtors" class="report-card"><div class="report-card-icon">📋</div><h3 class="report-card-title">Debtors</h3><p class="report-card-desc">Who owes you</p></a>
        <a href="/reports/creditors" class="report-card"><div class="report-card-icon">📑</div><h3 class="report-card-title">Creditors</h3><p class="report-card-desc">Who you owe</p></a>
        <a href="/reports/stock" class="report-card"><div class="report-card-icon">📦</div><h3 class="report-card-title">Stock Report</h3><p class="report-card-desc">Levels and valuation</p></a>
        <a href="/reports/ledger" class="report-card"><div class="report-card-icon">📒</div><h3 class="report-card-title">General Ledger</h3><p class="report-card-desc">All transactions</p></a>
    </div>
    '''
    return page_wrapper("Reports", content, active="reports", user=user)


@app.route("/reports/trial-balance")
def report_trial_balance():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    tb = Journal.get_trial_balance()
    
    rows = []
    for entry in tb:
        if entry.get("is_total"):
            dr = Money.format(entry["debit"]) if entry["debit"] else ""
            cr = Money.format(entry["credit"]) if entry["credit"] else ""
            balanced = abs(entry["balance"]) < Decimal("0.01")
            rows.append([f'<strong>{entry["name"]}</strong>', "", {"value": f'<strong>{dr}</strong>', "class": "number"}, {"value": f'<strong>{cr}</strong>', "class": "number"}, badge("✓ Balanced", "green") if balanced else badge("✗ Unbalanced", "red")])
        else:
            dr = Money.format(entry["debit"]) if entry["debit"] > 0 else "-"
            cr = Money.format(entry["credit"]) if entry["credit"] > 0 else "-"
            rows.append([entry["code"], entry["name"], {"value": dr, "class": "number"}, {"value": cr, "class": "number"}, ""])
    
    table = table_html(headers=["Code", "Account", {"label": "Debit", "class": "number"}, {"label": "Credit", "class": "number"}, ""], rows=rows, empty_message="No transactions")
    
    total_row = next((e for e in tb if e.get("is_total")), None)
    total_dr = total_row["debit"] if total_row else Decimal("0")
    total_cr = total_row["credit"] if total_row else Decimal("0")
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:8px;">Trial Balance</h1>
    <p class="text-muted mb-lg">As at {format_date(today())}</p>
    <div class="stats">
        <div class="stat"><div class="stat-value">{len([e for e in tb if not e.get("is_total")])}</div><div class="stat-label">Accounts</div></div>
        <div class="stat"><div class="stat-value">{Money.format(total_dr)}</div><div class="stat-label">Total Debits</div></div>
        <div class="stat"><div class="stat-value">{Money.format(total_cr)}</div><div class="stat-label">Total Credits</div></div>
    </div>
    <div class="card">{table}</div>
    '''
    return page_wrapper("Trial Balance", content, active="reports", user=user)


@app.route("/reports/income-statement")
def report_income_statement():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    date_from = FinancialPeriod.get_current_year_start()
    date_to = today()
    pnl = Journal.get_income_statement(date_from, date_to)
    
    def make_rows(items):
        return "".join([f'<tr><td style="padding-left:20px;">{i["name"]}</td><td class="number">{Money.format(i["amount"])}</td></tr>' for i in items])
    
    profit_color = "green" if pnl["net_profit"] >= 0 else "red"
    profit_label = "Net Profit" if pnl["net_profit"] >= 0 else "Net Loss"
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:8px;">Income Statement</h1>
    <p class="text-muted mb-lg">{format_date(date_from)} to {format_date(date_to)}</p>
    <div class="stats">
        <div class="stat"><div class="stat-value green">{Money.format(pnl["total_revenue"])}</div><div class="stat-label">Revenue</div></div>
        <div class="stat"><div class="stat-value">{Money.format(pnl["gross_profit"])}</div><div class="stat-label">Gross Profit</div></div>
        <div class="stat"><div class="stat-value red">{Money.format(pnl["total_expenses"])}</div><div class="stat-label">Expenses</div></div>
        <div class="stat"><div class="stat-value {profit_color}">{Money.format(pnl["net_profit"])}</div><div class="stat-label">{profit_label}</div></div>
    </div>
    <div class="card">
        <table class="table"><tbody>
            <tr style="background:var(--bg-secondary);"><td><strong>REVENUE</strong></td><td></td></tr>
            {make_rows(pnl["revenue"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr style="border-top:2px solid var(--border);"><td><strong>Total Revenue</strong></td><td class="number"><strong>{Money.format(pnl["total_revenue"])}</strong></td></tr>
            <tr style="background:var(--bg-secondary);"><td><strong>COST OF SALES</strong></td><td></td></tr>
            {make_rows(pnl["cost_of_sales"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr style="border-top:2px solid var(--border);"><td><strong>Gross Profit</strong></td><td class="number"><strong>{Money.format(pnl["gross_profit"])}</strong></td></tr>
            <tr style="background:var(--bg-secondary);"><td><strong>EXPENSES</strong></td><td></td></tr>
            {make_rows(pnl["expenses"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr style="border-top:2px solid var(--border);"><td><strong>Total Expenses</strong></td><td class="number"><strong>{Money.format(pnl["total_expenses"])}</strong></td></tr>
            <tr style="background:linear-gradient(135deg,rgba(139,92,246,0.1),rgba(59,130,246,0.1));font-size:18px;"><td><strong>{profit_label.upper()}</strong></td><td class="number" style="color:var(--{profit_color});"><strong>{Money.format(abs(pnl["net_profit"]))}</strong></td></tr>
        </tbody></table>
    </div>
    '''
    return page_wrapper("Income Statement", content, active="reports", user=user)


@app.route("/reports/balance-sheet")
def report_balance_sheet():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    bs = Journal.get_balance_sheet()
    
    def make_rows(items):
        return "".join([f'<tr><td style="padding-left:20px;">{i["name"]}</td><td class="number">{Money.format(i["balance"])}</td></tr>' for i in items])
    
    balanced = abs(bs["total_assets"] - bs["total_liab_equity"]) < Decimal("0.01")
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <div class="flex-between mb-lg">
        <div><h1 style="font-size:24px;font-weight:700;">Balance Sheet</h1><p class="text-muted">As at {format_date(today())}</p></div>
        {badge("✓ Balanced", "green") if balanced else badge("✗ Unbalanced", "red")}
    </div>
    <div class="stats">
        <div class="stat"><div class="stat-value">{Money.format(bs["total_assets"])}</div><div class="stat-label">Assets</div></div>
        <div class="stat"><div class="stat-value">{Money.format(bs["total_liabilities"])}</div><div class="stat-label">Liabilities</div></div>
        <div class="stat"><div class="stat-value">{Money.format(bs["total_equity"])}</div><div class="stat-label">Equity</div></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
        <div class="card"><h3 class="card-title mb-md">ASSETS</h3><table class="table"><tbody>
            <tr style="background:var(--bg-secondary);"><td><strong>Current Assets</strong></td><td></td></tr>
            {make_rows(bs["current_assets"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr><td><strong>Sub-total</strong></td><td class="number"><strong>{Money.format(bs["total_current_assets"])}</strong></td></tr>
            <tr style="background:var(--bg-secondary);"><td><strong>Fixed Assets</strong></td><td></td></tr>
            {make_rows(bs["fixed_assets"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr><td><strong>Sub-total</strong></td><td class="number"><strong>{Money.format(bs["total_fixed_assets"])}</strong></td></tr>
            <tr style="background:linear-gradient(135deg,rgba(59,130,246,0.1),rgba(139,92,246,0.1));"><td><strong>TOTAL ASSETS</strong></td><td class="number"><strong>{Money.format(bs["total_assets"])}</strong></td></tr>
        </tbody></table></div>
        <div class="card"><h3 class="card-title mb-md">LIABILITIES & EQUITY</h3><table class="table"><tbody>
            <tr style="background:var(--bg-secondary);"><td><strong>Current Liabilities</strong></td><td></td></tr>
            {make_rows(bs["current_liabilities"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr><td><strong>Sub-total</strong></td><td class="number"><strong>{Money.format(bs["total_current_liabilities"])}</strong></td></tr>
            <tr style="background:var(--bg-secondary);"><td><strong>Long-term Liabilities</strong></td><td></td></tr>
            {make_rows(bs["long_term_liabilities"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr><td><strong>Sub-total</strong></td><td class="number"><strong>{Money.format(bs["total_long_term_liabilities"])}</strong></td></tr>
            <tr style="background:var(--bg-secondary);"><td><strong>Equity</strong></td><td></td></tr>
            {make_rows(bs["equity"]) or '<tr><td colspan="2" class="text-muted" style="padding-left:20px;">None</td></tr>'}
            <tr><td><strong>Sub-total</strong></td><td class="number"><strong>{Money.format(bs["total_equity"])}</strong></td></tr>
            <tr style="background:linear-gradient(135deg,rgba(59,130,246,0.1),rgba(139,92,246,0.1));"><td><strong>TOTAL</strong></td><td class="number"><strong>{Money.format(bs["total_liab_equity"])}</strong></td></tr>
        </tbody></table></div>
    </div>
    '''
    return page_wrapper("Balance Sheet", content, active="reports", user=user)


@app.route("/reports/vat")
def report_vat():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    date_from = FinancialPeriod.get_vat_period_start()
    date_to = FinancialPeriod.get_vat_period_end()
    vat = Journal.get_vat_report(date_from, date_to)
    
    net_color = "red" if vat["net_vat"] > 0 else "green"
    net_label = "VAT Payable" if vat["net_vat"] > 0 else "VAT Refund"
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:8px;">VAT Report</h1>
    <p class="text-muted mb-lg">{format_date(date_from)} to {format_date(date_to)}</p>
    <div class="stats">
        <div class="stat"><div class="stat-value">{Money.format(vat["output_vat"])}</div><div class="stat-label">Output VAT</div></div>
        <div class="stat"><div class="stat-value green">{Money.format(vat["input_vat"])}</div><div class="stat-label">Input VAT</div></div>
        <div class="stat"><div class="stat-value {net_color}">{Money.format(abs(vat["net_vat"]))}</div><div class="stat-label">{net_label}</div></div>
    </div>
    <div class="card" style="max-width:500px;">
        <table class="table"><tbody>
            <tr><td>Output VAT (collected)</td><td class="number">{Money.format(vat["output_vat"])}</td></tr>
            <tr><td>Less: Input VAT (paid)</td><td class="number">({Money.format(vat["input_vat"])})</td></tr>
            <tr style="background:linear-gradient(135deg,rgba(139,92,246,0.1),rgba(59,130,246,0.1));font-size:18px;"><td><strong>{net_label}</strong></td><td class="number" style="color:var(--{net_color});"><strong>{Money.format(abs(vat["net_vat"]))}</strong></td></tr>
        </tbody></table>
    </div>
    '''
    return page_wrapper("VAT Report", content, active="reports", user=user)


@app.route("/reports/sales")
def report_sales():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    invoices = db.select("invoices", order="-date")
    total = sum(Decimal(str(i.get("total", 0) or 0)) for i in invoices)
    paid = sum(Decimal(str(i.get("total", 0) or 0)) for i in invoices if i.get("status") == "paid")
    
    rows = [[i.get("invoice_number", "-"), i.get("date", "")[:10], i.get("customer_name", "-"), {"value": Money.format(Decimal(str(i.get("total", 0)))), "class": "number"}, badge("Paid", "green") if i.get("status") == "paid" else badge("Outstanding", "orange")] for i in invoices[:50]]
    table = table_html(headers=["Invoice", "Date", "Customer", {"label": "Total", "class": "number"}, "Status"], rows=rows, empty_message="No sales")
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:20px;">Sales Report</h1>
    <div class="stats">
        <div class="stat"><div class="stat-value">{len(invoices)}</div><div class="stat-label">Invoices</div></div>
        <div class="stat"><div class="stat-value green">{Money.format(total)}</div><div class="stat-label">Total Sales</div></div>
        <div class="stat"><div class="stat-value orange">{Money.format(total - paid)}</div><div class="stat-label">Outstanding</div></div>
    </div>
    <div class="card">{table}</div>
    '''
    return page_wrapper("Sales Report", content, active="reports", user=user)


@app.route("/reports/debtors")
def report_debtors():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    customers = [c for c in db.select("customers", order="name") if c.get("active", True)]
    with_bal = [c for c in customers if Decimal(str(c.get("balance", 0) or 0)) > 0]
    total = sum(Decimal(str(c.get("balance", 0) or 0)) for c in with_bal)
    
    rows = [[c.get("name", "-"), c.get("phone", "-"), {"value": Money.format(Decimal(str(c.get("balance", 0)))), "class": "number text-red font-bold"}] for c in with_bal]
    table = table_html(headers=["Customer", "Phone", {"label": "Balance", "class": "number"}], rows=rows, empty_message="No debtors 🎉")
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:20px;">Debtors Report</h1>
    <div class="stats">
        <div class="stat"><div class="stat-value">{len(with_bal)}</div><div class="stat-label">Customers Owing</div></div>
        <div class="stat"><div class="stat-value red">{Money.format(total)}</div><div class="stat-label">Total Owing</div></div>
    </div>
    <div class="card">{table}</div>
    '''
    return page_wrapper("Debtors Report", content, active="reports", user=user)


@app.route("/reports/creditors")
def report_creditors():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    suppliers = [s for s in db.select("suppliers", order="name") if s.get("active", True)]
    with_bal = [s for s in suppliers if Decimal(str(s.get("balance", 0) or 0)) > 0]
    total = sum(Decimal(str(s.get("balance", 0) or 0)) for s in with_bal)
    
    rows = [[s.get("name", "-"), s.get("phone", "-"), {"value": Money.format(Decimal(str(s.get("balance", 0)))), "class": "number text-orange font-bold"}] for s in with_bal]
    table = table_html(headers=["Supplier", "Phone", {"label": "We Owe", "class": "number"}], rows=rows, empty_message="No creditors 🎉")
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:20px;">Creditors Report</h1>
    <div class="stats">
        <div class="stat"><div class="stat-value">{len(with_bal)}</div><div class="stat-label">Suppliers Owed</div></div>
        <div class="stat"><div class="stat-value orange">{Money.format(total)}</div><div class="stat-label">Total We Owe</div></div>
    </div>
    <div class="card">{table}</div>
    '''
    return page_wrapper("Creditors Report", content, active="reports", user=user)


@app.route("/reports/stock")
def report_stock():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    items = [i for i in db.select("stock_items", order="description") if i.get("active", True)]
    total_qty = sum(int(i.get("quantity", 0) or 0) for i in items)
    total_cost = sum(Decimal(str(i.get("cost_price", 0) or 0)) * int(i.get("quantity", 0) or 0) for i in items)
    total_retail = sum(Decimal(str(i.get("selling_price", 0) or 0)) * int(i.get("quantity", 0) or 0) for i in items)
    low = len([i for i in items if 0 < int(i.get("quantity", 0) or 0) <= 5])
    out = len([i for i in items if int(i.get("quantity", 0) or 0) <= 0])
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:20px;">Stock Report</h1>
    <div class="stats">
        <div class="stat"><div class="stat-value">{len(items)}</div><div class="stat-label">Items</div></div>
        <div class="stat"><div class="stat-value">{total_qty}</div><div class="stat-label">Units</div></div>
        <div class="stat"><div class="stat-value">{Money.format(total_cost)}</div><div class="stat-label">Cost Value</div></div>
        <div class="stat"><div class="stat-value green">{Money.format(total_retail)}</div><div class="stat-label">Retail Value</div></div>
    </div>
    <div class="stats">
        <div class="stat"><div class="stat-value orange">{low}</div><div class="stat-label">Low Stock</div></div>
        <div class="stat"><div class="stat-value red">{out}</div><div class="stat-label">Out of Stock</div></div>
        <div class="stat"><div class="stat-value green">{Money.format(total_retail - total_cost)}</div><div class="stat-label">Potential Profit</div></div>
    </div>
    <div class="card"><a href="/stock" class="btn btn-primary">Manage Stock</a></div>
    '''
    return page_wrapper("Stock Report", content, active="reports", user=user)


@app.route("/reports/ledger")
def report_ledger():
    user = UserSession.get_current_user()
    if not user:
        return redirect("/login")
    
    entries = Journal.get_entries(limit=200)
    
    rows = []
    for e in entries:
        dr = Money.format(Decimal(str(e.get("debit", 0)))) if e.get("debit") else "-"
        cr = Money.format(Decimal(str(e.get("credit", 0)))) if e.get("credit") else "-"
        rows.append([e.get("date", "")[:10], e.get("account_code", ""), e.get("reference", "-"), e.get("description", "")[:60], {"value": dr, "class": "number"}, {"value": cr, "class": "number"}])
    
    table = table_html(headers=["Date", "Account", "Ref", "Description", {"label": "Debit", "class": "number"}, {"label": "Credit", "class": "number"}], rows=rows, empty_message="No entries")
    
    content = f'''
    <a href="/reports" class="btn btn-ghost mb-lg">← Back</a>
    <h1 style="font-size:24px;font-weight:700;margin-bottom:20px;">General Ledger</h1>
    <div class="card">{table}</div>
    '''
    return page_wrapper("General Ledger", content, active="reports", user=user)


"""
PIECE 11 COMPLETE - Reports

Contains:
✓ Reports menu with 9 report types
✓ Trial Balance - from journal
✓ Income Statement / P&L - from journal  
✓ Balance Sheet - from journal
✓ VAT Report - from journal
✓ Sales Report
✓ Debtors Report
✓ Creditors Report
✓ Stock Report
✓ General Ledger

All financial reports pull from Journal class - real double-entry data!
"""
