from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt
import sqlite3
import secrets
import string
import random
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
bcrypt = Bcrypt(app)

# Credit conversion rate
CREDIT_RATE = 0.5  # ₹1 = 0.5 credits

# Support Links
WHATSAPP_LINK = "https://wa.me/message/IGTHSKO23KP4H1"
TELEGRAM_LINK = "https://t.me/GrowMarthq"

# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  role TEXT DEFAULT 'user',
                  credits REAL DEFAULT 0,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create products table
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL,
                  credit_cost_per_day REAL NOT NULL,
                  key_type TEXT DEFAULT 'standard',
                  is_active INTEGER DEFAULT 1)''')
    
    # Create licenses table
    c.execute('''CREATE TABLE IF NOT EXISTS licenses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  license_key TEXT UNIQUE NOT NULL,
                  username TEXT NOT NULL,
                  product_name TEXT NOT NULL,
                  days INTEGER NOT NULL,
                  total_credits REAL NOT NULL,
                  expiry_date TEXT NOT NULL,
                  status TEXT DEFAULT 'active',
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  utr TEXT UNIQUE NOT NULL,
                  amount REAL NOT NULL,
                  credits_requested REAL NOT NULL,
                  status TEXT DEFAULT 'pending',
                  payment_date TEXT NOT NULL,
                  approved_date TEXT)''')
    
    # Insert default admin
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        c.execute("INSERT INTO users (username, password, role, credits) VALUES (?, ?, ?, ?)",
                  ('admin', hashed_password, 'admin', 10000))
    
    # Insert default products
    default_products = [
        ('Fluorite FF IOS', 10, 'fluorite'),
        ('Drip Android ApkMod', 5, 'drip'),
        ('Drip Aimkill PC', 6, 'drip'),
        ('Drip SilentAim PC', 8, 'drip'),
        ('Gbox IOS Signer', 12, 'gbox'),
        ('Gbox Esign Cert', 20, 'gbox'),
        ('GlitchShotx 8BP IOS', 15, 'gbox'),
        ('Hg Cheat ApkMod', 7, 'hg'),
        ('Prime Apkmod', 9, 'standard'),
        ('Brmod SilentAim PC', 10, 'brmod'),
        ('Brmod Bypass + Silent', 12, 'brmod'),
        ('Pato Blue ApkMod', 5, 'standard'),
        ('Pato Orange ApkMod', 7, 'standard'),
        ('Pato Green ApkMod', 8, 'standard'),
        ('Drip Root Android', 8, 'drip'),
        ('LKTEAM Root + PC', 12, 'lkteam'),
        ('Strict Br Root', 10, 'strict'),
        ('Shield Pubg Android', 9, 'standard'),
        ('Haxxcker Pro Root', 12, 'standard'),
        ('Spotify Root', 4, 'spotify')
    ]
    
    for product in default_products:
        try:
            c.execute("INSERT INTO products (name, credit_cost_per_day, key_type) VALUES (?, ?, ?)",
                     product)
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()

init_db()

# Key Generation Functions
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
    return f"Username: {username}\nPassword: {password}"

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
    return f"Email: {username}@temp.com\nPassword: {password}"

def generate_standard_key():
    alphabet = string.ascii_uppercase + string.digits
    return 'KEY-' + ''.join(secrets.choice(alphabet) for _ in range(4)) + '-' + \
           ''.join(secrets.choice(alphabet) for _ in range(4)) + '-' + \
           ''.join(secrets.choice(alphabet) for _ in range(4))

def generate_key_by_type(key_type):
    generators = {
        'fluorite': generate_fluorite_key,
        'gbox': generate_gbox_key,
        'drip': generate_drip_key,
        'hg': generate_hg_key,
        'brmod': generate_brmod_credentials,
        'lkteam': generate_lkteam_key,
        'strict': generate_strict_key,
        'spotify': generate_spotify_credentials,
        'standard': generate_standard_key
    }
    generator = generators.get(key_type, generate_standard_key)
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
    
    # Get user data
    c.execute("SELECT * FROM users WHERE username = ?", (session['username'],))
    user = c.fetchone()
    session['credits'] = user[4]
    
    # Get active products
    c.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name")
    products = c.fetchall()
    
    # Get user's licenses
    c.execute("""SELECT * FROM licenses WHERE username = ? 
                 ORDER BY expiry_date DESC""", (session['username'],))
    licenses = c.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         user=user, 
                         products=products, 
                         licenses=licenses,
                         whatsapp_link=WHATSAPP_LINK,
                         telegram_link=TELEGRAM_LINK)

@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get stats
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'user'")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    pending_payments = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
    active_keys = c.fetchone()[0]
    
    c.execute("SELECT IFNULL(SUM(amount), 0) FROM payments WHERE status = 'approved'")
    total_revenue = c.fetchone()[0]
    
    # Get all users
    c.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY credits DESC")
    users = c.fetchall()
    
    # Get all payments
    c.execute("SELECT * FROM payments ORDER BY payment_date DESC")
    payments = c.fetchall()
    
    # Get all licenses
    c.execute("SELECT * FROM licenses ORDER BY expiry_date DESC")
    licenses = c.fetchall()
    
    # Get all products
    c.execute("SELECT * FROM products ORDER BY name")
    products = c.fetchall()
    
    conn.close()
    
    return render_template('admin.html', 
                         users=users, 
                         payments=payments, 
                         licenses=licenses, 
                         products=products,
                         total_users=total_users,
                         pending_payments=pending_payments,
                         active_keys=active_keys,
                         total_revenue=total_revenue)

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
        return jsonify({'success': False, 'error': 'Product not found'})
    
    total_credits = product[2] * days
    total_price = (total_credits / CREDIT_RATE)  # Convert credits to rupees
    
    return jsonify({
        'success': True,
        'total_credits': total_credits,
        'total_price': round(total_price, 2)
    })

@app.route('/generate_key', methods=['POST'])
def generate_key():
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
    user_credits = c.fetchone()[0]
    
    if user_credits < total_credits:
        conn.close()
        return jsonify({'success': False, 'error': f'Insufficient credits. Need {total_credits} credits'})
    
    # Generate key
    license_key = generate_key_by_type(product[3])
    
    # Calculate expiry
    expiry_date = datetime.now() + timedelta(days=days)
    
    # Deduct credits
    c.execute("UPDATE users SET credits = credits - ? WHERE username = ?",
             (total_credits, session['username']))
    
    # Save license
    c.execute("""INSERT INTO licenses (license_key, username, product_name, days, total_credits, expiry_date)
                 VALUES (?, ?, ?, ?, ?, ?)""",
             (license_key, session['username'], product[1], days, total_credits, 
              expiry_date.strftime('%Y-%m-%d %H:%M:%S')))
    
    conn.commit()
    conn.close()
    
    session['credits'] -= total_credits
    
    return jsonify({'success': True, 'key': license_key})

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        utr = request.form['utr']
        amount = float(request.form['amount'])
        
        if amount < 100:
            return render_template('payment.html', 
                                 error='Minimum recharge amount is ₹100',
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_link=TELEGRAM_LINK)
        
        credits_requested = amount * CREDIT_RATE
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO payments (username, utr, amount, credits_requested, payment_date, status)
                         VALUES (?, ?, ?, ?, ?, 'pending')""",
                     (session['username'], utr, amount, credits_requested, 
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            return render_template('payment.html', 
                                 success='Payment request submitted successfully! Admin will verify and add credits.',
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_link=TELEGRAM_LINK)
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('payment.html', 
                                 error='UTR already exists. Please use a different UTR.',
                                 whatsapp_link=WHATSAPP_LINK,
                                 telegram_link=TELEGRAM_LINK)
    
    return render_template('payment.html', 
                         whatsapp_link=WHATSAPP_LINK,
                         telegram_link=TELEGRAM_LINK,
                         credit_rate=CREDIT_RATE)

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
        c.execute("UPDATE payments SET status = 'approved', approved_date = ? WHERE id = ?",
                 (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), payment_id))
        c.execute("UPDATE users SET credits = credits + ? WHERE username = ?",
                 (payment[4], payment[1]))  # payment[4] is credits_requested
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
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

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

@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    name = request.json.get('name')
    credit_cost_per_day = float(request.json.get('credit_cost_per_day'))
    key_type = request.json.get('key_type')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO products (name, credit_cost_per_day, key_type) VALUES (?, ?, ?)",
                 (name, credit_cost_per_day, key_type))
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
    key_type = request.json.get('key_type')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE products SET name = ?, credit_cost_per_day = ?, key_type = ? WHERE id = ?",
             (name, credit_cost_per_day, key_type, product_id))
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

if __name__ == '__main__':
    app.run(debug=True)
