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
import re

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
bcrypt = Bcrypt(app)

# Credit conversion rate (₹1 = 0.5 credits)
CREDIT_RATE = 0.5  # 1 rupee = 0.5 credits

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
                  credits REAL DEFAULT 0)''')  # Changed to REAL for decimal credits
    
    # Create products table
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL,
                  credit_cost_per_day REAL NOT NULL,  # Credits per day
                  price_per_day REAL NOT NULL,  # Price per day in rupees
                  key_type TEXT DEFAULT 'standard')''')
    
    # Create licenses table
    c.execute('''CREATE TABLE IF NOT EXISTS licenses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key TEXT UNIQUE NOT NULL,
                  username TEXT NOT NULL,
                  product_name TEXT NOT NULL,
                  days INTEGER NOT NULL,
                  total_credits REAL NOT NULL,
                  expiry_date TEXT NOT NULL,
                  status TEXT DEFAULT 'active',
                  last_reset TEXT)''')
    
    # Create payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  utr TEXT UNIQUE NOT NULL,
                  amount REAL NOT NULL,
                  credits_added REAL DEFAULT 0,
                  status TEXT DEFAULT 'pending',
                  date TEXT NOT NULL,
                  approved_date TEXT)''')
    
    # Insert default admin if not exists
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        c.execute("INSERT INTO users (username, password, role, credits) VALUES (?, ?, ?, ?)",
                  ('admin', hashed_password, 'admin', 1000))
    
    # Insert default products with per-day pricing
    default_products = [
        ('Fluorite FF IOS', 10, 20, 'fluorite'),  # 10 credits per day, ₹20 per day
        ('Drip Android ApkMod', 5, 10, 'drip'),
        ('Drip Aimkill PC', 6, 12, 'drip'),
        ('Drip SilentAim PC', 8, 15, 'drip'),
        ('Gbox IOS Signer', 12, 25, 'gbox'),
        ('Hg Cheat ApkMod', 7, 14, 'hg'),
        ('Prime Apkmod', 9, 18, 'standard'),
        ('GlitchShotx 8BP IOS', 15, 30, 'gbox'),
        ('Brmod SilentAim PC', 10, 20, 'brmod'),
        ('Brmod Bypass + Silent', 12, 25, 'brmod'),
        ('Gbox Esign Cert', 20, 40, 'gbox'),
        ('Pato Blue ApkMod', 5, 10, 'standard'),
        ('Drip Root Android', 8, 16, 'drip'),
        ('LKTEAM Root + PC', 12, 25, 'lkteam'),
        ('Pato Orange ApkMod', 7, 14, 'standard'),
        ('Pato Green ApkMod', 8, 16, 'standard'),
        ('Strict Br Root', 10, 20, 'strict'),
        ('Shield Pubg Android', 9, 18, 'standard'),
        ('Haxxcker Pro Root', 12, 25, 'standard'),
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

# UPI ID for QR Code
UPI_ID = "thedigamber@fam"
UPI_NAME = "Digamber"

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

# Key generation functions for different products
def generate_fluorite_key():
    """Generate Fluorite style key (16 chars alphanumeric)"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(16))

def generate_gbox_key():
    """Generate Gbox style key (same as fluorite)"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(16))

def generate_drip_key():
    """Generate Drip style key (10 digits)"""
    return ''.join(secrets.choice(string.digits) for _ in range(10))

def generate_hg_key():
    """Generate HG Cheat style key"""
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
    return f"HG-{random_part}"

def generate_brmod_credentials():
    """Generate BRMod username and password"""
    username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    password = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"User: {username}\nPass: {password}"

def generate_lkteam_key():
    """Generate LKTEAM style key"""
    alphabet = string.ascii_uppercase + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(6))
    return f"LKTEAM-{random_part}"

def generate_strict_key():
    """Generate Strict Br Root key (STRICT-8 digits)"""
    digits = ''.join(secrets.choice(string.digits) for _ in range(8))
    return f"STRICT-{digits}"

def generate_spotify_credentials():
    """Generate Spotify style credentials"""
    username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    return f"Username: {username}@temp.com\nPassword: {password}"

def generate_key_by_type(key_type):
    """Generate key based on product type"""
    key_types = {
        'fluorite': generate_fluorite_key,
        'gbox': generate_gbox_key,
        'drip': generate_drip_key,
        'hg': generate_hg_key,
        'brmod': generate_brmod_credentials,
        'lkteam': generate_lkteam_key,
        'strict': generate_strict_key,
        'spotify': generate_spotify_credentials
    }
    
    generator = key_types.get(key_type, generate_fluorite_key)
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
    
    # Get products
    c.execute("SELECT * FROM products ORDER BY name")
    products = c.fetchall()
    
    # Get user's licenses
    c.execute("SELECT * FROM licenses WHERE username = ? ORDER BY expiry_date DESC", (session['username'],))
    licenses = c.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', user=user, products=products, licenses=licenses)

@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get all users
    c.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY username")
    users = c.fetchall()
    
    # Get all payments
    c.execute("SELECT * FROM payments ORDER BY date DESC")
    payments = c.fetchall()
    
    # Get all licenses
    c.execute("SELECT * FROM licenses ORDER BY expiry_date DESC")
    licenses = c.fetchall()
    
    # Get all products
    c.execute("SELECT * FROM products ORDER BY name")
    products = c.fetchall()
    
    conn.close()
    
    return render_template('admin.html', users=users, payments=payments, 
                         licenses=licenses, products=products)

@app.route('/calculate_price', methods=['POST'])
def calculate_price():
    """Calculate total price and credits for selected days"""
    product_id = request.json.get('product_id')
    days = int(request.json.get('days'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    
    if not product:
        return jsonify({'success': False})
    
    total_credits = product[2] * days  # credit_cost_per_day * days
    total_price = product[3] * days  # price_per_day * days
    
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
    
    # Get product details
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    
    if not product:
        conn.close()
        return jsonify({'success': False, 'error': 'Product not found'})
    
    # Calculate total credits needed
    total_credits = product[2] * days  # credit_cost_per_day * days
    
    # Get user credits
    c.execute("SELECT credits FROM users WHERE username = ?", (session['username'],))
    credits = c.fetchone()[0]
    
    if credits < total_credits:
        conn.close()
        return jsonify({'success': False, 'error': f'Insufficient credits. Need {total_credits} credits'})
    
    # Generate key based on product type
    key = generate_key_by_type(product[4])  # product[4] is key_type
    
    # Calculate expiry date based on days
    expiry_date = datetime.now() + timedelta(days=days)
    
    # Deduct credits
    c.execute("UPDATE users SET credits = credits - ? WHERE username = ?",
             (total_credits, session['username']))
    
    # Save license
    c.execute("""INSERT INTO licenses (key, username, product_name, days, total_credits, expiry_date, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
             (key, session['username'], product[1], days, total_credits, 
              expiry_date.strftime('%Y-%m-%d %H:%M:%S'), 'active'))
    
    conn.commit()
    conn.close()
    
    # Update session credits
    session['credits'] -= total_credits
    
    return jsonify({'success': True, 'key': key})

@app.route('/hwid_reset', methods=['POST'])
def hwid_reset():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    license_id = request.json.get('license_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Check if license belongs to user
    c.execute("SELECT * FROM licenses WHERE id = ? AND username = ?", 
             (license_id, session['username']))
    license = c.fetchone()
    
    if not license:
        conn.close()
        return jsonify({'success': False, 'error': 'License not found'})
    
    # Update HWID reset timestamp
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
    
    # Update all user's licenses
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

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        utr = request.form['utr']
        amount = float(request.form['amount'])
        
        # Calculate credits to add (₹1 = 0.5 credits)
        credits_to_add = amount * CREDIT_RATE
        
        # Generate QR code for the amount
        qr_code = generate_upi_qr(amount)
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO payments (username, utr, amount, credits_added, status, date)
                         VALUES (?, ?, ?, ?, ?, ?)""",
                     (session['username'], utr, amount, credits_to_add, 'pending', 
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            
            # Auto-approve for testing (remove in production)
            # c.execute("UPDATE payments SET status = 'approved' WHERE utr = ?", (utr,))
            # c.execute("UPDATE users SET credits = credits + ? WHERE username = ?",
            #          (credits_to_add, session['username']))
            # conn.commit()
            
            conn.close()
            return render_template('payment.html', success=f'Payment request submitted! You will get {credits_to_add} credits after approval.', qr_code=qr_code, amount=amount)
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('payment.html', error='UTR already exists')
    
    return render_template('payment.html')

# Admin API Routes
@app.route('/admin/approve_payment', methods=['POST'])
def approve_payment():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    payment_id = request.json.get('payment_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get payment details
    c.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    payment = c.fetchone()
    
    if payment:
        # Update payment status
        c.execute("""UPDATE payments SET status = 'approved', approved_date = ? 
                     WHERE id = ?""", 
                 (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), payment_id))
        
        # Add credits to user
        c.execute("UPDATE users SET credits = credits + ? WHERE username = ?",
                 (payment[4], payment[1]))  # payment[4] is credits_added, payment[1] is username
        
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
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Product management routes
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
    c.execute("SELECT * FROM products ORDER BY name")
    products = c.fetchall()
    conn.close()
    
    return jsonify({'success': True, 'products': products})

if __name__ == '__main__':
    app.run(debug=True)
