from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt
import sqlite3
import secrets
import string
import random
from datetime import datetime, timedelta
import os
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
bcrypt = Bcrypt(app)

# Credit conversion rate (₹1 = 0.5 credits)
CREDIT_RATE = 0.5
MINIMUM_RECHARGE = 1000

# UPI Details
UPI_ID = "thedigamber@fam"
UPI_NAME = "Digamber"

# Support Links
WHATSAPP_LINK = "https://wa.me/message/IGTHSKO23KP4H1"
TELEGRAM_CHANNEL = "https://t.me/growmarthq"
TELEGRAM_SUPPORT = "https://t.me/growmarthq"  # Same channel for support

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  role TEXT DEFAULT 'user',
                  credits REAL DEFAULT 0,
                  total_recharged REAL DEFAULT 0,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL,
                  credit_cost_per_day REAL NOT NULL,
                  price_per_day REAL NOT NULL,
                  key_type TEXT DEFAULT 'standard',
                  is_active BOOLEAN DEFAULT 1,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Licenses table
    c.execute('''CREATE TABLE IF NOT EXISTS licenses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key TEXT UNIQUE NOT NULL,
                  username TEXT NOT NULL,
                  product_name TEXT NOT NULL,
                  days INTEGER NOT NULL,
                  total_credits REAL NOT NULL,
                  expiry_date TEXT NOT NULL,
                  status TEXT DEFAULT 'active',
                  last_reset TEXT,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Manual Payments table (for UTR verification)
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  utr TEXT UNIQUE NOT NULL,
                  amount REAL NOT NULL,
                  credits_added REAL DEFAULT 0,
                  status TEXT DEFAULT 'pending',
                  screenshot TEXT,
                  date TEXT NOT NULL,
                  approved_date TEXT,
                  approved_by TEXT)''')
    
    # Insert default admin
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        c.execute("INSERT INTO users (username, password, role, credits) VALUES (?, ?, ?, ?)",
                  ('admin', hashed_password, 'admin', 10000))
    
    # Insert default products
    default_products = [
        ('Fluorite FF IOS', 10, 20, 'fluorite'),
        ('Drip Android ApkMod', 5, 10, 'drip'),
        ('Drip Aimkill PC', 6, 12, 'drip'),
        ('Drip SilentAim PC', 8, 15, 'drip'),
        ('Gbox IOS Signer', 12, 25, 'gbox'),
        ('Gbox Esign Cert', 20, 40, 'gbox'),
        ('Hg Cheat ApkMod', 7, 14, 'hg'),
        ('Brmod SilentAim PC', 10, 20, 'brmod'),
        ('Brmod Bypass + Silent', 12, 25, 'brmod'),
        ('LKTEAM Root + PC', 12, 25, 'lkteam'),
        ('Strict Br Root', 10, 20, 'strict'),
        ('Spotify Root', 4, 8, 'spotify')
    ]
    
    for product in default_products:
        try:
            c.execute("INSERT INTO products (name, credit_cost_per_day, price_per_day, key_type) VALUES (?, ?, ?, ?)",
                     product)
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()

init_db()

def generate_upi_qr(amount):
    """Generate UPI QR code"""
    upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(upi_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return img_str

# Key generation functions
def generate_fluorite_key():
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(16))

def generate_gbox_key():
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(16))

def generate_drip_key():
    return ''.join(secrets.choice(string.digits) for _ in range(10))

def generate_hg_key():
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
    return f"HG-{random_part}"

def generate_brmod_credentials():
    username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    password = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"User: {username}\nPass: {password}"

def generate_lkteam_key():
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
    return f"LKTEAM-{random_part}"

def generate_strict_key():
    digits = ''.join(secrets.choice(string.digits) for _ in range(8))
    return f"STRICT-{digits}"

def generate_spotify_credentials():
    username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    return f"Username: {username}@temp.com\nPassword: {password}"

def generate_key_by_type(key_type):
    generators = {
        'fluorite': generate_fluorite_key,
        'gbox': generate_gbox_key,
        'drip': generate_drip_key,
        'hg': generate_hg_key,
        'brmod': generate_brmod_credentials,
        'lkteam': generate_lkteam_key,
        'strict': generate_strict_key,
        'spotify': generate_spotify_credentials
    }
    generator = generators.get(key_type, generate_fluorite_key)
    return generator()

# Routes
@app.route('/')
def index():
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and bcrypt.check_password_hash(user[2], password):
            session['username'] = user[1]
            session['role'] = user[3]
            session['credits'] = user[4]
            session['user_id'] = user[0]
            
            if user[3] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters')
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role, credits) VALUES (?, ?, ?, ?)",
                     (username, hashed_password, 'user', 0))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Username already exists')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def user_dashboard():
    if 'username' not in session or session['role'] != 'user':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM users WHERE username = ?", (session['username'],))
    user = c.fetchone()
    session['credits'] = user[4]
    
    c.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name")
    products = c.fetchall()
    
    c.execute("""SELECT * FROM licenses WHERE username = ? 
                 ORDER BY expiry_date DESC LIMIT 50""", (session['username'],))
    licenses = c.fetchall()
    
    # Get pending payments
    c.execute("""SELECT * FROM payments WHERE username = ? AND status = 'pending' 
                 ORDER BY date DESC""", (session['username'],))
    pending_payments = c.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', user=user, products=products, 
                         licenses=licenses, pending_payments=pending_payments,
                         min_recharge=MINIMUM_RECHARGE, credit_rate=CREDIT_RATE,
                         whatsapp_link=WHATSAPP_LINK, telegram_channel=TELEGRAM_CHANNEL)

@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Stats
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(amount) FROM payments WHERE status = 'approved'")
    total_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(credits_added) FROM payments WHERE status = 'approved'")
    total_credits_sold = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    pending_payments = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
    active_keys = c.fetchone()[0]
    
    # All users
    c.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY credits DESC")
    users = c.fetchall()
    
    # All payments (pending first)
    c.execute("""SELECT * FROM payments ORDER BY 
                 CASE status WHEN 'pending' THEN 1 ELSE 2 END, date DESC""")
    payments = c.fetchall()
    
    # All licenses
    c.execute("SELECT * FROM licenses ORDER BY expiry_date DESC LIMIT 100")
    licenses = c.fetchall()
    
    # All products
    c.execute("SELECT * FROM products ORDER BY name")
    products = c.fetchall()
    
    conn.close()
    
    return render_template('admin.html', users=users, payments=payments, 
                         licenses=licenses, products=products,
                         total_users=total_users, total_revenue=total_revenue,
                         total_credits_sold=total_credits_sold, 
                         pending_payments=pending_payments, active_keys=active_keys,
                         whatsapp_link=WHATSAPP_LINK, telegram_channel=TELEGRAM_CHANNEL)

@app.route('/calculate_price', methods=['POST'])
def calculate_price():
    product_id = request.json.get('product_id')
    days = int(request.json.get('days'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    
    if not product:
        return jsonify({'success': False})
    
    total_credits = product[2] * days
    total_price = product[3] * days
    
    return jsonify({
        'success': True,
        'total_credits': total_credits,
        'total_price': total_price
    })

@app.route('/generate_key', methods=['POST'])
def generate_key_route():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    product_id = request.json.get('product_id')
    days = int(request.json.get('days'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    
    if not product:
        conn.close()
        return jsonify({'success': False, 'error': 'Product not found'})
    
    total_credits = product[2] * days
    
    c.execute("SELECT credits FROM users WHERE username = ?", (session['username'],))
    credits = c.fetchone()[0]
    
    if credits < total_credits:
        conn.close()
        return jsonify({'success': False, 'error': f'Insufficient credits. Need {total_credits} credits'})
    
    key = generate_key_by_type(product[4])
    expiry_date = datetime.now() + timedelta(days=days)
    
    c.execute("UPDATE users SET credits = credits - ? WHERE username = ?",
             (total_credits, session['username']))
    
    c.execute("""INSERT INTO licenses (key, username, product_name, days, total_credits, expiry_date, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
             (key, session['username'], product[1], days, total_credits, 
              expiry_date.strftime('%Y-%m-%d %H:%M:%S'), 'active'))
    
    conn.commit()
    conn.close()
    
    session['credits'] -= total_credits
    
    return jsonify({'success': True, 'key': key})

# MANUAL PAYMENT SYSTEM
@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        utr = request.form['utr']
        amount = float(request.form['amount'])
        screenshot = request.form.get('screenshot', '')  # Optional screenshot link
        
        if amount < MINIMUM_RECHARGE:
            return render_template('payment.html', 
                                 error=f'Minimum recharge amount is ₹{MINIMUM_RECHARGE}',
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 upi_id=UPI_ID,
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_channel=TELEGRAM_CHANNEL)
        
        credits_to_add = amount * CREDIT_RATE
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO payments (username, utr, amount, credits_added, status, date)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                     (session['username'], utr, amount, credits_to_add, 'pending',
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            return render_template('payment.html', 
                                 success=f'Payment request submitted! ₹{amount} = {credits_to_add} credits pending approval.',
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 upi_id=UPI_ID,
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_channel=TELEGRAM_CHANNEL)
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('payment.html', 
                                 error='UTR already exists! Please use a different UTR.',
                                 min_recharge=MINIMUM_RECHARGE,
                                 credit_rate=CREDIT_RATE,
                                 upi_id=UPI_ID,
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_channel=TELEGRAM_CHANNEL)
    
    # Generate QR for default amount
    qr_code = generate_upi_qr(MINIMUM_RECHARGE)
    
    return render_template('payment.html', 
                         qr_code=qr_code,
                         min_recharge=MINIMUM_RECHARGE,
                         credit_rate=CREDIT_RATE,
                         upi_id=UPI_ID,
                         whatsapp_link=WHATSAPP_LINK,
                         telegram_channel=TELEGRAM_CHANNEL)

@app.route('/generate_payment_qr', methods=['POST'])
def generate_payment_qr():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    amount = float(request.json.get('amount'))
    
    if amount < MINIMUM_RECHARGE:
        return jsonify({'success': False, 'error': f'Minimum amount is ₹{MINIMUM_RECHARGE}'})
    
    qr_code = generate_upi_qr(amount)
    credits_to_add = amount * CREDIT_RATE
    
    return jsonify({
        'success': True,
        'qr_code': qr_code,
        'amount': amount,
        'credits': credits_to_add,
        'upi_id': UPI_ID
    })

# ADMIN PAYMENT APPROVAL
@app.route('/admin/approve_payment', methods=['POST'])
def approve_payment():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    payment_id = request.json.get('payment_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    payment = c.fetchone()
    
    if payment:
        c.execute("""UPDATE payments SET status = 'approved', approved_date = ?, approved_by = ? 
                     WHERE id = ?""", 
                 (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session['username'], payment_id))
        
        c.execute("UPDATE users SET credits = credits + ?, total_recharged = total_recharged + ? WHERE username = ?",
                 (payment[4], payment[3], payment[1]))  # credits_added, amount, username
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    conn.close()
    return jsonify({'success': False})

@app.route('/admin/reject_payment', methods=['POST'])
def reject_payment():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    payment_id = request.json.get('payment_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE payments SET status = 'rejected' WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# HWID Routes
@app.route('/hwid_reset', methods=['POST'])
def hwid_reset():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    license_id = request.json.get('license_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM licenses WHERE id = ? AND username = ?", 
             (license_id, session['username']))
    license = c.fetchone()
    
    if not license:
        conn.close()
        return jsonify({'success': False, 'error': 'License not found'})
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("UPDATE licenses SET last_reset = ? WHERE id = ?", 
             (current_time, license_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'HWID reset successful'})

@app.route('/hwid_reset_all', methods=['POST'])
def hwid_reset_all():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute("UPDATE licenses SET last_reset = ? WHERE username = ?", 
             (current_time, session['username']))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'All HWIDs reset successfully'})

@app.route('/admin/delete_key', methods=['POST'])
def delete_key():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    license_id = request.json.get('license_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/add_credits', methods=['POST'])
def add_credits():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    username = request.json.get('username')
    credits = float(request.json.get('credits'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE username = ?", (credits, username))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/delete_user', methods=['POST'])
def delete_user():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    username = request.json.get('username')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ? AND role != 'admin'", (username,))
    c.execute("DELETE FROM licenses WHERE username = ?", (username,))
    c.execute("DELETE FROM payments WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Product management
@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    name = request.json.get('name')
    credit_cost_per_day = float(request.json.get('credit_cost_per_day'))
    price_per_day = float(request.json.get('price_per_day'))
    key_type = request.json.get('key_type', 'standard')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        c.execute("""INSERT INTO products (name, credit_cost_per_day, price_per_day, key_type)
                     VALUES (?, ?, ?, ?)""", (name, credit_cost_per_day, price_per_day, key_type))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Product name already exists'})

@app.route('/admin/edit_product', methods=['POST'])
def edit_product():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    product_id = request.json.get('product_id')
    name = request.json.get('name')
    credit_cost_per_day = float(request.json.get('credit_cost_per_day'))
    price_per_day = float(request.json.get('price_per_day'))
    key_type = request.json.get('key_type', 'standard')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""UPDATE products SET name = ?, credit_cost_per_day = ?, price_per_day = ?, key_type = ?
                 WHERE id = ?""", (name, credit_cost_per_day, price_per_day, key_type, product_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/toggle_product', methods=['POST'])
def toggle_product():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    product_id = request.json.get('product_id')
    is_active = request.json.get('is_active')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE products SET is_active = ? WHERE id = ?", (is_active, product_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/admin/delete_product', methods=['POST'])
def delete_product():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    product_id = request.json.get('product_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/get_products')
def get_products():
    if 'username' not in session:
        return jsonify({'success': False})
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name")
    products = c.fetchall()
    conn.close()
    
    return jsonify({'success': True, 'products': products})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
