from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt
import secrets
import string
import random
from datetime import datetime, timedelta
import os
import qrcode
from io import BytesIO
import base64
import traceback
import logging
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import socket
import requests
import re

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
bcrypt = Bcrypt(app)

# Logging setup
logging.basicConfig(level=logging.DEBUG)

# ============================================
# DATABASE CONNECTION - SMART URL SELECTOR
# ============================================

# External URL (for local development)
EXTERNAL_DATABASE_URL = 'postgresql://admin_panels_user:kRkEd8Zr8wCqJlXUNsnlNvgBqQOgHthi@dpg-d6ts46juibrs73eo0750-a.oregon-postgres.render.com/admin_panels'

# Internal URL (for Render deployment)
INTERNAL_DATABASE_URL = 'postgresql://admin_panels_user:kRkEd8Zr8wCqJlXUNsnlNvgBqQOgHthi@dpg-d6ts46juibrs73eo0750-a/admin_panels'

def is_running_on_render():
    """Check if we're running on Render.com"""
    return os.getenv('RENDER', False) or os.getenv('RENDER_EXTERNAL_URL', False)

def get_database_url():
    """Smartly choose between internal and external URL"""
    if is_running_on_render():
        logging.info("✅ Running on Render - Using INTERNAL database URL")
        return INTERNAL_DATABASE_URL
    else:
        logging.info("✅ Running locally - Using EXTERNAL database URL")
        return EXTERNAL_DATABASE_URL

def test_database_connection(url):
    """Test if database URL is reachable"""
    try:
        # Extract hostname from URL for testing
        match = re.search(r'@([^:/]+)', url)
        if match:
            hostname = match.group(1)
            # Try to resolve hostname
            socket.gethostbyname(hostname)
            logging.info(f"✅ Hostname {hostname} resolved successfully")
        
        # Try actual connection
        conn = psycopg2.connect(url, connect_timeout=5)
        conn.close()
        logging.info("✅ Database connection successful")
        return True
    except Exception as e:
        logging.error(f"❌ Database connection test failed: {e}")
        return False

def get_db_connection():
    """Get database connection with automatic failover"""
    primary_url = get_database_url()
    
    try:
        conn = psycopg2.connect(
            primary_url,
            connect_timeout=10,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        logging.error(f"❌ Primary DB connection failed: {e}")
        
        # Try fallback URL
        if primary_url == INTERNAL_DATABASE_URL:
            fallback_url = EXTERNAL_DATABASE_URL
        else:
            fallback_url = INTERNAL_DATABASE_URL
        
        logging.info(f"🔄 Trying fallback URL: {fallback_url[:50]}...")
        
        try:
            conn = psycopg2.connect(
                fallback_url,
                connect_timeout=10,
                cursor_factory=RealDictCursor
            )
            logging.info("✅ Fallback connection successful!")
            return conn
        except Exception as e2:
            logging.error(f"❌ Fallback also failed: {e2}")
            raise Exception(f"Database connection failed: {e} / {e2}")

def init_db():
    """Initialize database tables"""
    try:
        logging.info("🔄 Initializing database...")
        
        db_url = get_database_url()
        if not test_database_connection(db_url):
            logging.error("❌ Cannot connect to database. Check your URL.")
            return False
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'user',
                credits DECIMAL(10,2) DEFAULT 0,
                total_recharged DECIMAL(10,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Products table with custom_key_pattern
        c.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                credit_cost_per_day DECIMAL(10,2) NOT NULL,
                price_per_day DECIMAL(10,2) NOT NULL,
                key_type VARCHAR(50) DEFAULT 'standard',
                custom_key_pattern TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Licenses table
        c.execute('''
            CREATE TABLE IF NOT EXISTS licenses (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                username VARCHAR(100) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                days INTEGER NOT NULL,
                total_credits DECIMAL(10,2) NOT NULL,
                expiry_date TIMESTAMP NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                last_reset TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Payments table (UPI + Binance)
        c.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                payment_method VARCHAR(20) NOT NULL,
                utr VARCHAR(50) UNIQUE,
                order_id VARCHAR(100) UNIQUE,
                amount DECIMAL(10,2) NOT NULL,
                credits_added DECIMAL(10,2) DEFAULT 0,
                status VARCHAR(50) DEFAULT 'pending',
                date TIMESTAMP NOT NULL,
                approved_date TIMESTAMP,
                approved_by VARCHAR(100),
                binance_data TEXT
            )
        ''')
        
        # Custom key types table
        c.execute('''
            CREATE TABLE IF NOT EXISTS key_types (
                id SERIAL PRIMARY KEY,
                type_name VARCHAR(50) UNIQUE NOT NULL,
                pattern TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default key types
        default_key_types = [
            ('fluorite', 'RANDOM16', '16 characters random'),
            ('gbox', 'RANDOM16', '16 characters random'),
            ('drip', 'DIGITS10', '10 digits'),
            ('hg', 'HG-{RANDOM6}', 'HG-XXXXXX format'),
            ('brmod', 'USER8\\nPASS4', 'Username + Password'),
            ('lkteam', 'LKTEAM-{RANDOM6}', 'LKTEAM-XXXXXX'),
            ('strict', 'STRICT-{DIGITS8}', 'STRICT-8 digits'),
            ('spotify', 'EMAIL8@temp.com\\nPASS12', 'Email + Password'),
            ('standard', 'KEY-{RANDOM4}-{RANDOM4}', 'KEY-XXXX-XXXX')
        ]
        
        for type_name, pattern, desc in default_key_types:
            try:
                c.execute('''
                    INSERT INTO key_types (type_name, pattern, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (type_name) DO NOTHING
                ''', (type_name, pattern, desc))
            except Exception as e:
                logging.warning(f"Key type insert warning: {e}")
        
        # Insert default admin
        hashed = bcrypt.generate_password_hash('620300').decode('utf-8')
        try:
            c.execute('''
                INSERT INTO users (username, password, role, credits)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
            ''', ('thedigamber', hashed, 'admin', 10000))
        except Exception as e:
            logging.warning(f"Admin insert warning: {e}")
        
        # Insert default products
        default_products = [
            ('Fluorite FF IOS', 25, 50, 'fluorite'),
            ('Drip Android ApkMod', 6, 12, 'drip'),
            ('Drip Aimkill PC', 12, 25, 'drip'),
            ('Drip SilentAim PC', 10, 20, 'drip'),
            ('Gbox IOS Signer', 18, 36, 'gbox'),
            ('Hg Cheat ApkMod', 7, 14, 'hg'),
            ('Prime Apkmod', 5, 10, 'standard'),
            ('GlitchShotx 8BP IOS', 15, 30, 'gbox'),
            ('Brmod SilentAim PC', 10, 20, 'brmod'),
            ('Brmod Bypass + Silent', 8, 16, 'brmod'),
            ('Gbox Esign Cert', 20, 40, 'gbox'),
            ('Pato Blue ApkMod', 5, 10, 'standard'),
            ('Drip Root Android', 8, 16, 'drip'),
            ('LKTEAM Root + PC', 12, 25, 'lkteam'),
            ('Pato Orange ApkMod', 7, 14, 'standard'),
            ('Pato Green ApkMod', 5, 10, 'standard'),
            ('Strics Br Root', 10, 20, 'strict'),
            ('Shield Pubg Android', 9, 18, 'standard'),
            ('Haxxcker Pro Root', 12, 25, 'standard'),
            ('Spotify Root', 5, 10, 'spotify')
        ]
        
        for name, credits, price, key_type in default_products:
            try:
                c.execute('''
                    INSERT INTO products (name, credit_cost_per_day, price_per_day, key_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (name) DO NOTHING
                ''', (name, credits, price, key_type))
            except Exception as e:
                logging.warning(f"Product insert warning: {e}")
        
        conn.commit()
        conn.close()
        logging.info("✅ Database initialized successfully!")
        return True
        
    except Exception as e:
        logging.error(f"❌ Database initialization error: {e}")
        traceback.print_exc()
        return False

# Initialize DB on startup with retry
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    logging.info(f"🔄 Database init attempt {attempt + 1}/{MAX_RETRIES}")
    if init_db():
        break
    if attempt < MAX_RETRIES - 1:
        logging.info("⏳ Waiting 5 seconds before retry...")
        time.sleep(5)
    else:
        logging.error("❌ All database initialization attempts failed!")

# ============================================
# CONSTANTS
# ============================================

CREDIT_RATE = float(os.getenv('CREDIT_RATE', 0.5))
MINIMUM_RECHARGE = int(os.getenv('MIN_RECHARGE', 1000))
UPI_ID = os.getenv('UPI_ID', 'prabhu84@ptaxis')
UPI_NAME = os.getenv('UPI_NAME', 'Digamber Raj')
WHATSAPP_LINK = os.getenv('WHATSAPP_LINK', 'https://wa.me/message/IGTHSKO23KP4H1')
TELEGRAM_CHANNEL = os.getenv('TELEGRAM_CHANNEL', 'https://t.me/growmarthq')
BINANCE_API_URL = os.getenv('BINANCE_API_URL', 'https://binance-verifier.onrender.com')

# ============================================
# KEY GENERATOR CLASS
# ============================================

class KeyGenerator:
    """Generate keys in various formats including custom patterns"""
    
    def __init__(self):
        self.generators = {
            'fluorite': self._generate_fluorite,
            'gbox': self._generate_gbox,
            'drip': self._generate_drip,
            'hg': self._generate_hg,
            'brmod': self._generate_brmod,
            'lkteam': self._generate_lkteam,
            'strict': self._generate_strict,
            'spotify': self._generate_spotify,
            'standard': self._generate_standard
        }
    
    def generate_key(self, key_type, custom_pattern=None):
        """Generate key based on type or custom pattern"""
        if custom_pattern:
            return self._generate_from_pattern(custom_pattern)
        
        generator = self.generators.get(key_type, self._generate_standard)
        return generator()
    
    def _generate_from_pattern(self, pattern):
        """Generate key from custom pattern"""
        result = pattern
        
        # Replace placeholders
        placeholders = {
            'RANDOM4': lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)),
            'RANDOM6': lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)),
            'RANDOM8': lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)),
            'RANDOM10': lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10)),
            'RANDOM12': lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12)),
            'RANDOM16': lambda: ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16)),
            'DIGITS4': lambda: ''.join(secrets.choice(string.digits) for _ in range(4)),
            'DIGITS6': lambda: ''.join(secrets.choice(string.digits) for _ in range(6)),
            'DIGITS8': lambda: ''.join(secrets.choice(string.digits) for _ in range(8)),
            'DIGITS10': lambda: ''.join(secrets.choice(string.digits) for _ in range(10)),
            'USER4': lambda: ''.join(secrets.choice(string.ascii_lowercase) for _ in range(4)),
            'USER6': lambda: ''.join(secrets.choice(string.ascii_lowercase) for _ in range(6)),
            'USER8': lambda: ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8)),
            'PASS4': lambda: ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(4)),
            'PASS6': lambda: ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6)),
            'PASS8': lambda: ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8)),
            'PASS12': lambda: ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12)),
            'DATE': lambda: datetime.now().strftime('%Y%m%d'),
            'TIME': lambda: datetime.now().strftime('%H%M%S'),
            'YEAR': lambda: datetime.now().strftime('%Y'),
            'MONTH': lambda: datetime.now().strftime('%m'),
            'DAY': lambda: datetime.now().strftime('%d')
        }
        
        for placeholder in re.findall(r'\{([^}]+)\}', result):
            if placeholder in placeholders:
                result = result.replace(f'{{{placeholder}}}', placeholders[placeholder]())
        
        return result
    
    def _generate_fluorite(self):
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
    
    def _generate_gbox(self):
        return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
    
    def _generate_drip(self):
        return ''.join(secrets.choice(string.digits) for _ in range(10))
    
    def _generate_hg(self):
        rand = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"HG-{rand}"
    
    def _generate_brmod(self):
        username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        password = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        return f"User: {username}\nPass: {password}"
    
    def _generate_lkteam(self):
        rand = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        return f"LKTEAM-{rand}"
    
    def _generate_strict(self):
        digits = ''.join(secrets.choice(string.digits) for _ in range(8))
        return f"STRICT-{digits}"
    
    def _generate_spotify(self):
        username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        return f"Username: {username}@temp.com\nPassword: {password}"
    
    def _generate_standard(self):
        part1 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        part2 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        return f"KEY-{part1}-{part2}"

key_gen = KeyGenerator()

# ============================================
# BINANCE API CLASS
# ============================================

class BinanceAPI:
    def __init__(self):
        self.base_url = BINANCE_API_URL
        self.timeout = 30
    
    def _request(self, endpoint, method='GET', data=None):
        """Make API request to Binance verifier"""
        try:
            url = self.base_url + endpoint
            if method == 'GET':
                response = requests.get(url, timeout=self.timeout)
            else:
                response = requests.post(url, json=data, timeout=self.timeout)
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Binance API error: {response.status_code}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            logging.error(f"Binance API error: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_order(self, amount, email=None):
        """Create new payment order"""
        order_id = f"BNB{int(time.time())}{random.randint(100,999)}"
        return self._request('/api/create-order', 'POST', {
            'orderId': order_id,
            'amount': float(amount),
            'customerEmail': email or 'customer@example.com'
        })
    
    def verify_payment(self, order_id, amount):
        """Verify if payment is complete"""
        return self._request('/api/verify', 'POST', {
            'orderId': order_id,
            'amount': float(amount)
        })
    
    def check_order(self, order_id):
        """Check order status"""
        return self._request(f'/api/check/{order_id}')
    
    def get_qr(self, order_id):
        """Get QR code for order with proper formatting"""
        result = self._request(f'/api/qr/{order_id}')
        if result and result.get('qr'):
            # Ensure QR is properly formatted
            qr_data = result.get('qr')
            if not qr_data.startswith('data:image'):
                qr_data = f"data:image/png;base64,{qr_data}"
            return {'success': True, 'qr': qr_data}
        return {'success': False, 'qr': None}
    
    def get_address(self, order_id):
        """Get crypto address for order"""
        return self._request(f'/api/address/{order_id}')
    
    def check_expired(self, order_id):
        """Check if order expired"""
        return self._request(f'/api/expired/{order_id}')
    
    def cancel_order(self, order_id):
        """Cancel order"""
        return self._request(f'/api/cancel/{order_id}', 'POST')

binance_api = BinanceAPI()

# ============================================
# HELPER FUNCTIONS
# ============================================

def generate_upi_qr(amount):
    """Generate UPI QR code with proper formatting"""
    try:
        upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(upi_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        logging.error(f"QR Generation Error: {e}")
        return None

def format_date(date_obj):
    """Safely format datetime object for templates"""
    if date_obj is None:
        return 'N/A'
    if hasattr(date_obj, 'strftime'):
        return date_obj.strftime('%Y-%m-%d %H:%M')
    if isinstance(date_obj, str):
        return date_obj[:16]
    return str(date_obj)

# ============================================
# ROUTES - AUTHENTICATION
# ============================================

@app.route('/')
def index():
    if 'username' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            if not username or not password:
                return render_template('login.html', error='Username and password required')
            
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = c.fetchone()
            conn.close()
            
            if user and bcrypt.check_password_hash(user['password'], password):
                session.clear()
                session['username'] = user['username']
                session['role'] = user['role']
                session['credits'] = float(user['credits']) if user['credits'] else 0
                session['user_id'] = user['id']
                
                logging.info(f"✅ Login: {username} ({user['role']})")
                
                if user['role'] == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('user_dashboard'))
            
            return render_template('login.html', error='Invalid credentials')
        
        return render_template('login.html')
    except Exception as e:
        logging.error(f"Login Error: {e}")
        traceback.print_exc()
        return render_template('error.html', error=f"Login error: {str(e)}")

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            confirm = request.form.get('confirm_password', '')
            
            if not username or not password:
                return render_template('register.html', error='All fields required')
            if password != confirm:
                return render_template('register.html', error='Passwords do not match')
            if len(password) < 6:
                return render_template('register.html', error='Password must be 6+ characters')
            
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            
            conn = get_db_connection()
            c = conn.cursor()
            try:
                c.execute('''
                    INSERT INTO users (username, password, role, credits)
                    VALUES (%s, %s, %s, %s)
                ''', (username, hashed, 'user', 0))
                conn.commit()
                conn.close()
                return redirect(url_for('login'))
            except Exception as e:
                conn.close()
                return render_template('register.html', error='Username already exists')
        
        return render_template('register.html')
    except Exception as e:
        logging.error(f"Register Error: {e}")
        return render_template('error.html', error=f"Registration error: {str(e)}")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============================================
# ROUTES - USER DASHBOARD
# ============================================

@app.route('/dashboard')
def user_dashboard():
    try:
        if 'username' not in session or session.get('role') != 'user':
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get user
        c.execute("SELECT * FROM users WHERE username = %s", (session['username'],))
        user = c.fetchone()
        
        if not user:
            session.clear()
            conn.close()
            return redirect(url_for('login'))
        
        session['credits'] = float(user['credits'])
        
        # Get active products
        c.execute('''
            SELECT * FROM products 
            WHERE is_active = TRUE 
            ORDER BY name
        ''')
        products = c.fetchall()
        
        # Get user's licenses
        c.execute('''
            SELECT * FROM licenses 
            WHERE username = %s 
            ORDER BY expiry_date DESC 
            LIMIT 50
        ''', (session['username'],))
        licenses = c.fetchall()
        
        conn.close()
        
        return render_template('dashboard.html',
                             user=user,
                             products=products,
                             licenses=licenses,
                             whatsapp_link=WHATSAPP_LINK,
                             telegram_channel=TELEGRAM_CHANNEL)
    
    except Exception as e:
        logging.error(f"Dashboard Error: {e}")
        traceback.print_exc()
        return render_template('error.html', error=f"Dashboard error: {str(e)}")

@app.route('/generate_key', methods=['POST'])
def generate_key_route():
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'error': 'Not logged in'})
        
        data = request.get_json()
        product_id = data.get('product_id')
        days = int(data.get('days', 1))
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get product
        c.execute("SELECT * FROM products WHERE id = %s", (product_id,))
        product = c.fetchone()
        
        if not product:
            conn.close()
            return jsonify({'success': False, 'error': 'Product not found'})
        
        total_credits = float(product['credit_cost_per_day']) * days
        
        # Check user credits
        c.execute("SELECT credits FROM users WHERE username = %s", (session['username'],))
        user_credits = c.fetchone()['credits']
        
        if user_credits < total_credits:
            conn.close()
            return jsonify({'success': False, 'error': f'Need {total_credits} credits'})
        
        # Generate key using pattern
        key = key_gen.generate_key(product['key_type'], product.get('custom_key_pattern'))
        expiry = datetime.now() + timedelta(days=days)
        
        # Deduct credits
        c.execute('''
            UPDATE users SET credits = credits - %s 
            WHERE username = %s
        ''', (total_credits, session['username']))
        
        # Save license
        c.execute('''
            INSERT INTO licenses 
            (key, username, product_name, days, total_credits, expiry_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (key, session['username'], product['name'], days, total_credits,
              expiry.strftime('%Y-%m-%d %H:%M:%S'), 'active'))
        
        conn.commit()
        conn.close()
        
        session['credits'] = user_credits - total_credits
        
        return jsonify({'success': True, 'key': key})
    
    except Exception as e:
        logging.error(f"Generate Key Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/hwid_reset', methods=['POST'])
def hwid_reset():
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'error': 'Not logged in'})
        
        data = request.get_json()
        license_id = data.get('license_id')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE licenses SET last_reset = %s 
            WHERE id = %s AND username = %s
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), license_id, session['username']))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        logging.error(f"HWID Reset Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/hwid_reset_all', methods=['POST'])
def hwid_reset_all():
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'error': 'Not logged in'})
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE licenses SET last_reset = %s 
            WHERE username = %s
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['username']))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        logging.error(f"HWID Reset All Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# ROUTES - PAYMENT (UPI + BINANCE)
# ============================================

@app.route('/payment')
def payment_page():
    """Payment page with method selection"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    return render_template('payment.html',
                         min_recharge=MINIMUM_RECHARGE,
                         credit_rate=CREDIT_RATE,
                         upi_id=UPI_ID,
                         whatsapp_link=WHATSAPP_LINK,
                         telegram_channel=TELEGRAM_CHANNEL)

@app.route('/payment/upi', methods=['GET', 'POST'])
def upi_payment():
    """UPI Manual Payment - FIXED QR"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        utr = request.form.get('utr', '').strip()
        amount = float(request.form.get('amount', 0))
        
        if amount < MINIMUM_RECHARGE:
            qr = generate_upi_qr(MINIMUM_RECHARGE)
            return render_template('upi_payment.html',
                                 error=f'Minimum ₹{MINIMUM_RECHARGE}',
                                 qr_code=qr,
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 upi_id=UPI_ID)
        
        if not utr or len(utr) != 12 or not utr.isdigit():
            qr = generate_upi_qr(amount)
            return render_template('upi_payment.html',
                                 error='Enter valid 12-digit UTR',
                                 qr_code=qr,
                                 amount=amount,
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 upi_id=UPI_ID)
        
        credits = amount * CREDIT_RATE
        
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO payments 
                (username, payment_method, utr, amount, credits_added, status, date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (session['username'], 'upi', utr, amount, credits, 'pending',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            qr = generate_upi_qr(amount)
            return render_template('upi_payment.html',
                                 success=f'Payment submitted! {credits} credits pending approval.',
                                 qr_code=qr,
                                 amount=amount,
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 upi_id=UPI_ID)
        except Exception as e:
            conn.close()
            qr = generate_upi_qr(amount)
            return render_template('upi_payment.html',
                                 error='UTR already exists!',
                                 qr_code=qr,
                                 amount=amount,
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 upi_id=UPI_ID)
    
    # GET request
    qr = generate_upi_qr(MINIMUM_RECHARGE)
    return render_template('upi_payment.html',
                         qr_code=qr,
                         min_recharge=MINIMUM_RECHARGE,
                         credit_rate=CREDIT_RATE,
                         upi_id=UPI_ID)

@app.route('/payment/binance', methods=['GET', 'POST'])
def binance_payment():
    """Binance Crypto Payment - AUTO CREDITS with FIXED QR"""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        
        if amount < MINIMUM_RECHARGE:
            return render_template('binance_payment.html',
                                 error=f'Minimum ₹{MINIMUM_RECHARGE}',
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_channel=TELEGRAM_CHANNEL)
        
        # Create Binance order
        result = binance_api.create_order(amount, f"{session['username']}@user.com")
        
        if result and result.get('success'):
            order_id = result.get('orderId')
            credits = amount * CREDIT_RATE
            
            # Save to database
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('''
                INSERT INTO payments 
                (username, payment_method, order_id, amount, credits_added, status, date, binance_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (session['username'], 'binance', order_id, amount, credits, 'pending',
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  json.dumps(result)))
            conn.commit()
            conn.close()
            
            # Get QR and address
            qr_data = binance_api.get_qr(order_id)
            address_data = binance_api.get_address(order_id)
            
            return render_template('binance_payment.html',
                                 order_id=order_id,
                                 amount=amount,
                                 credits=credits,
                                 qr_code=qr_data.get('qr') if qr_data else None,
                                 address=address_data.get('address') if address_data else None,
                                 binance_data=result,
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_channel=TELEGRAM_CHANNEL)
        else:
            return render_template('binance_payment.html',
                                 error='Binance service unavailable. Please try UPI.',
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_channel=TELEGRAM_CHANNEL)
    
    # GET request
    return render_template('binance_payment.html',
                         min_recharge=MINIMUM_RECHARGE,
                         credit_rate=CREDIT_RATE,
                         whatsapp_link=WHATSAPP_LINK,
                         telegram_channel=TELEGRAM_CHANNEL)

@app.route('/payment/binance/check/<order_id>')
def check_binance_payment(order_id):
    """Check Binance payment status - AUTO CREDIT on success"""
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    try:
        # Check with Binance API
        result = binance_api.check_order(order_id)
        
        if result and result.get('status') == 'completed':
            conn = get_db_connection()
            c = conn.cursor()
            
            # Get payment record
            c.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
            payment = c.fetchone()
            
            if payment and payment['status'] == 'pending':
                # Update payment
                c.execute('''
                    UPDATE payments 
                    SET status = 'approved', approved_date = %s
                    WHERE order_id = %s
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))
                
                # Add credits to user
                c.execute('''
                    UPDATE users 
                    SET credits = credits + %s, total_recharged = total_recharged + %s
                    WHERE username = %s
                ''', (payment['credits_added'], payment['amount'], session['username']))
                
                conn.commit()
                conn.close()
                
                # Update session
                session['credits'] = session.get('credits', 0) + payment['credits_added']
                
                return jsonify({
                    'success': True,
                    'status': 'completed',
                    'credited': True,
                    'credits': float(payment['credits_added'])
                })
            conn.close()
        
        return jsonify({
            'success': True,
            'status': result.get('status', 'pending') if result else 'pending'
        })
        
    except Exception as e:
        logging.error(f"Binance check error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/generate_payment_qr', methods=['POST'])
def generate_payment_qr():
    """Generate UPI QR for amount - FIXED"""
    try:
        if 'username' not in session:
            return jsonify({'success': False, 'error': 'Not logged in'})
        
        data = request.get_json()
        amount = float(data.get('amount', MINIMUM_RECHARGE))
        
        if amount < MINIMUM_RECHARGE:
            return jsonify({'success': False, 'error': f'Minimum amount is ₹{MINIMUM_RECHARGE}'})
        
        qr_code = generate_upi_qr(amount)
        credits_to_add = amount * CREDIT_RATE
        
        return jsonify({
            'success': True,
            'qr_code': qr_code,
            'amount': amount,
            'credits': round(credits_to_add, 1),
            'upi_id': UPI_ID
        })
        
    except Exception as e:
        logging.error(f"Generate QR Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# ROUTES - ADMIN DASHBOARD
# ============================================

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return redirect(url_for('login'))
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Stats
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
        total_users = c.fetchone()['count']
        
        c.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status = 'approved'")
        total_revenue = c.fetchone()['coalesce']
        
        c.execute("SELECT COALESCE(SUM(credits_added), 0) FROM payments WHERE status = 'approved'")
        total_credits_sold = c.fetchone()['coalesce']
        
        c.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
        pending_payments = c.fetchone()['count']
        
        c.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
        active_keys = c.fetchone()['count']
        
        # Users
        c.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY credits DESC")
        users = c.fetchall()
        
        # Payments
        c.execute('''
            SELECT * FROM payments 
            ORDER BY CASE status WHEN 'pending' THEN 1 ELSE 2 END, date DESC
        ''')
        payments = c.fetchall()
        
        # Licenses
        c.execute("SELECT * FROM licenses ORDER BY expiry_date DESC LIMIT 100")
        licenses = c.fetchall()
        
        # Products
        c.execute("SELECT * FROM products ORDER BY name")
        products = c.fetchall()
        
        # Key types
        c.execute("SELECT * FROM key_types ORDER BY type_name")
        key_types = c.fetchall()
        
        conn.close()
        
        return render_template('admin.html',
                             users=users,
                             payments=payments,
                             licenses=licenses,
                             products=products,
                             key_types=key_types,
                             total_users=total_users,
                             total_revenue=total_revenue,
                             total_credits_sold=total_credits_sold,
                             pending_payments=pending_payments,
                             active_keys=active_keys,
                             whatsapp_link=WHATSAPP_LINK,
                             telegram_channel=TELEGRAM_CHANNEL,
                             format_date=format_date)
    
    except Exception as e:
        logging.error(f"Admin Dashboard Error: {e}")
        traceback.print_exc()
        return render_template('error.html', error=f"Admin error: {str(e)}")

@app.route('/admin/track_binance/<order_id>')
def track_binance(order_id):
    """Admin track specific Binance order"""
    if 'username' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Unauthorized'})
    
    result = binance_api.check_order(order_id)
    return jsonify(result)

# ============================================
# ADMIN - PAYMENT MANAGEMENT
# ============================================

@app.route('/admin/approve_payment', methods=['POST'])
def approve_payment():
    """Approve UPI payment (manual)"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        payment_id = data.get('payment_id')
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get payment
        c.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
        payment = c.fetchone()
        
        if not payment:
            conn.close()
            return jsonify({'success': False, 'error': 'Payment not found'})
        
        # Update payment
        c.execute('''
            UPDATE payments 
            SET status = 'approved', approved_date = %s, approved_by = %s
            WHERE id = %s
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['username'], payment_id))
        
        # Add credits to user
        c.execute('''
            UPDATE users 
            SET credits = credits + %s, total_recharged = total_recharged + %s
            WHERE username = %s
        ''', (payment['credits_added'], payment['amount'], payment['username']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Approve Payment Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/reject_payment', methods=['POST'])
def reject_payment():
    """Reject UPI payment"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        payment_id = data.get('payment_id')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE payments SET status = 'rejected' WHERE id = %s
        ''', (payment_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Reject Payment Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# ADMIN - PRODUCT MANAGEMENT
# ============================================

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    """Add product with optional custom key pattern"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        name = data.get('name', '').strip()
        credits = float(data.get('credit_cost_per_day', 0))
        price = float(data.get('price_per_day', 0))
        key_type = data.get('key_type', 'standard')
        custom_pattern = data.get('custom_key_pattern')
        
        if not name or credits <= 0 or price <= 0:
            return jsonify({'success': False, 'error': 'Invalid data'})
        
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO products (name, credit_cost_per_day, price_per_day, key_type, custom_key_pattern)
                VALUES (%s, %s, %s, %s, %s)
            ''', (name, credits, price, key_type, custom_pattern))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'error': 'Product name exists'})
            
    except Exception as e:
        logging.error(f"Add Product Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/edit_product', methods=['POST'])
def edit_product():
    """Edit product"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        product_id = data.get('product_id')
        name = data.get('name')
        credits = float(data.get('credit_cost_per_day', 0))
        price = float(data.get('price_per_day', 0))
        key_type = data.get('key_type')
        custom_pattern = data.get('custom_key_pattern')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE products 
            SET name = %s, credit_cost_per_day = %s, price_per_day = %s, 
                key_type = %s, custom_key_pattern = %s
            WHERE id = %s
        ''', (name, credits, price, key_type, custom_pattern, product_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Edit Product Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/delete_product', methods=['POST'])
def delete_product():
    """Delete product"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        product_id = data.get('product_id')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Delete Product Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/toggle_product', methods=['POST'])
def toggle_product():
    """Enable/disable product"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        product_id = data.get('product_id')
        is_active = data.get('is_active', True)
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE products SET is_active = %s WHERE id = %s", (is_active, product_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Toggle Product Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# ADMIN - KEY TYPE MANAGEMENT
# ============================================

@app.route('/admin/add_key_type', methods=['POST'])
def add_key_type():
    """Add custom key type with pattern"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        type_name = data.get('type_name')
        pattern = data.get('pattern')
        description = data.get('description')
        
        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO key_types (type_name, pattern, description)
                VALUES (%s, %s, %s)
            ''', (type_name, pattern, description))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'error': 'Type name exists'})
            
    except Exception as e:
        logging.error(f"Add Key Type Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/get_key_types')
def get_key_types():
    """Get all key types"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM key_types ORDER BY type_name")
        types = c.fetchall()
        conn.close()
        
        return jsonify({'success': True, 'key_types': types})
        
    except Exception as e:
        logging.error(f"Get Key Types Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# ADMIN - USER MANAGEMENT
# ============================================

@app.route('/admin/add_credits', methods=['POST'])
def add_credits():
    """Admin add credits to user"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        username = data.get('username')
        credits = float(data.get('credits', 0))
        
        if credits <= 0:
            return jsonify({'success': False, 'error': 'Invalid amount'})
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            UPDATE users SET credits = credits + %s WHERE username = %s
        ''', (credits, username))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Add Credits Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    """Delete user and all their data"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        username = data.get('username')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM licenses WHERE username = %s", (username,))
        c.execute("DELETE FROM payments WHERE username = %s", (username,))
        c.execute("DELETE FROM users WHERE username = %s AND role != 'admin'", (username,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Delete User Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/delete_key', methods=['POST'])
def delete_key():
    """Delete a license key"""
    try:
        if 'username' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Unauthorized'})
        
        data = request.get_json()
        license_id = data.get('license_id')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM licenses WHERE id = %s", (license_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logging.error(f"Delete Key Error: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(500)
def internal_error(error):
    logging.error(f"500 Error: {error}")
    db_status = "Unknown"
    try:
        test_database_connection(get_database_url())
        db_status = "Connected"
    except:
        db_status = "Disconnected"
    
    return render_template('error.html', 
                         error=f"Internal Server Error. DB Status: {db_status}"), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error="Page not found"), 404

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
