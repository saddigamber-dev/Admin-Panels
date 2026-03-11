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
app.secret_key = secrets.token_hex(16)
bcrypt = Bcrypt(app)

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
                  credits INTEGER DEFAULT 0)''')
    
    # Create products table with days dropdown
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL,
                  credit_cost INTEGER NOT NULL,
                  days INTEGER NOT NULL,
                  price REAL NOT NULL,
                  key_type TEXT DEFAULT 'standard')''')
    
    # Create licenses table
    c.execute('''CREATE TABLE IF NOT EXISTS licenses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key TEXT UNIQUE NOT NULL,
                  username TEXT NOT NULL,
                  product_name TEXT NOT NULL,
                  hwid TEXT,
                  expiry_date TEXT NOT NULL,
                  status TEXT DEFAULT 'active',
                  last_reset TEXT)''')
    
    # Create payments table
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  utr TEXT UNIQUE NOT NULL,
                  amount REAL NOT NULL,
                  status TEXT DEFAULT 'pending',
                  date TEXT NOT NULL)''')
    
    # Insert default admin if not exists
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        c.execute("INSERT INTO users (username, password, role, credits) VALUES (?, ?, ?, ?)",
                  ('admin', hashed_password, 'admin', 1000))
    
    # Insert default products with days
    default_products = [
        ('Fluorite FF IOS', 50, 7, 5.99, 'fluorite'),
        ('Drip Android ApkMod', 30, 15, 3.99, 'drip'),
        ('Drip Aimkill PC', 40, 30, 4.99, 'drip'),
        ('Drip SilentAim PC', 60, 30, 6.99, 'drip'),
        ('Gbox IOS Signer', 45, 7, 5.49, 'standard'),
        ('Hg Cheat ApkMod', 35, 15, 4.49, 'hg'),
        ('Prime Apkmod', 55, 30, 6.49, 'standard'),
        ('GlitchShotx 8BP IOS', 70, 7, 7.99, 'standard'),
        ('Brmod SilentAim PC', 65, 30, 7.49, 'brmod'),
        ('Brmod Bypass + Silent', 80, 30, 8.99, 'brmod'),
        ('Gbox Esign Cert', 90, 15, 9.99, 'standard'),
        ('Pato Blue ApkMod', 25, 7, 2.99, 'standard'),
        ('Drip Root Android', 50, 30, 5.99, 'drip'),
        ('LKTEAM Root + PC', 75, 30, 8.49, 'lkteam'),
        ('Pato Orange ApkMod', 40, 15, 4.99, 'standard'),
        ('Pato Green ApkMod', 45, 15, 5.49, 'standard'),
        ('Strict Br Root', 60, 30, 6.99, 'standard'),
        ('Shield Pubg Android', 55, 30, 6.49, 'standard'),
        ('Haxxcker Pro Root', 85, 30, 9.49, 'standard'),
        ('Spotify Root', 20, 30, 2.49, 'spotify')
    ]
    
    for product in default_products:
        try:
            c.execute("INSERT INTO products (name, credit_cost, days, price, key_type) VALUES (?, ?, ?, ?, ?)",
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
    # UPI deep link format: upi://pay?pa=user@upi&pn=Receiver&am=amount&cu=INR
    upi_url = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&cu=INR"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(upi_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding in HTML
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return img_str

# Key generation functions for different products
def generate_fluorite_key():
    """Generate Fluorite style key (16 chars alphanumeric)"""
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

def generate_spotify_credentials():
    """Generate Spotify style credentials"""
    username = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    return f"Username: {username}@temp.com\nPassword: {password}"

def generate_key_by_type(key_type):
    """Generate key based on product type"""
    if key_type == 'fluorite':
        return generate_fluorite_key()
    elif key_type == 'drip':
        return generate_drip_key()
    elif key_type == 'hg':
        return generate_hg_key()
    elif key_type == 'brmod':
        return generate_brmod_credentials()
    elif key_type == 'lkteam':
        return generate_lkteam_key()
    elif key_type == 'spotify':
        return generate_spotify_credentials()
    else:
        # Standard key format
        alphabet = string.ascii_uppercase + string.digits
        return 'KEY-' + ''.join(secrets.choice(alphabet) for _ in range(4)) + '-' + \
               ''.join(secrets.choice(alphabet) for _ in range(4)) + '-' + \
               ''.join(secrets.choice(alphabet) for _ in range(4))

# Routes (keep all existing routes and add new ones)

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

@app.route('/generate_key', methods=['POST'])
def generate_key_route():
    if 'username' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
    
    product_id = request.json.get('product_id')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Get product details
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    
    if not product:
        conn.close()
        return jsonify({'success': False, 'error': 'Product not found'})
    
    # Get user credits
    c.execute("SELECT credits FROM users WHERE username = ?", (session['username'],))
    credits = c.fetchone()[0]
    
    if credits < product[2]:  # product[2] is credit_cost
        conn.close()
        return jsonify({'success': False, 'error': 'Insufficient credits'})
    
    # Generate key based on product type
    key = generate_key_by_type(product[5])  # product[5] is key_type
    
    # Calculate expiry date based on days
    expiry_date = datetime.now() + timedelta(days=product[3])  # product[3] is days
    
    # Deduct credits
    c.execute("UPDATE users SET credits = credits - ? WHERE username = ?",
             (product[2], session['username']))
    
    # Save license
    c.execute("""INSERT INTO licenses (key, username, product_name, expiry_date, status)
                 VALUES (?, ?, ?, ?, ?)""",
             (key, session['username'], product[1], expiry_date.strftime('%Y-%m-%d %H:%M:%S'), 'active'))
    
    conn.commit()
    conn.close()
    
    # Update session credits
    session['credits'] -= product[2]
    
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
        
        # Generate QR code for the amount
        qr_code = generate_upi_qr(amount)
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO payments (username, utr, amount, status, date)
                         VALUES (?, ?, ?, ?, ?)""",
                     (session['username'], utr, amount, 'pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            return render_template('payment.html', success='Payment request submitted successfully', qr_code=qr_code, amount=amount)
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
        c.execute("UPDATE payments SET status = 'approved' WHERE id = ?", (payment_id,))
        # Add credits to user
        c.execute("UPDATE users SET credits = credits + ? WHERE username = ?",
                 (payment[3], payment[1]))  # payment[3] is amount, payment[1] is username
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    conn.close()
    return jsonify({'success': False})

@app.route('/admin/add_credits', methods=['POST'])
def add_credits():
    if 'username' not in session or session['role'] != 'admin':
        return jsonify({'success': False})
    
    username = request.json.get('username')
    credits = int(request.json.get('credits'))
    
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
    credit_cost = int(request.json.get('credit_cost'))
    days = int(request.json.get('days'))
    price = float(request.json.get('price'))
    key_type = request.json.get('key_type', 'standard')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        c.execute("""INSERT INTO products (name, credit_cost, days, price, key_type)
                     VALUES (?, ?, ?, ?, ?)""", (name, credit_cost, days, price, key_type))
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
    credit_cost = int(request.json.get('credit_cost'))
    days = int(request.json.get('days'))
    price = float(request.json.get('price'))
    key_type = request.json.get('key_type', 'standard')
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""UPDATE products SET name = ?, credit_cost = ?, days = ?, price = ?, key_type = ?
                 WHERE id = ?""", (name, credit_cost, days, price, key_type, product_id))
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
