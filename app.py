from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_bcrypt import Bcrypt
import sqlite3
import secrets
import string
from datetime import datetime, timedelta
import os

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
    
    # Create products table
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE NOT NULL,
                  credit_cost INTEGER NOT NULL,
                  duration TEXT NOT NULL,
                  price REAL NOT NULL)''')
    
    # Create licenses table
    c.execute('''CREATE TABLE IF NOT EXISTS licenses
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  key TEXT UNIQUE NOT NULL,
                  username TEXT NOT NULL,
                  product_name TEXT NOT NULL,
                  expiry_date TEXT NOT NULL,
                  status TEXT DEFAULT 'active')''')
    
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
    
    # Insert default products if not exists
    default_products = [
        ('Fluorite FF IOS', 50, '7 days', 5.99),
        ('Drip Android ApkMod', 30, '15 days', 3.99),
        ('Drip Aimkill PC', 40, '30 days', 4.99),
        ('Drip SilentAim PC', 60, '30 days', 6.99),
        ('Gbox IOS Signer', 45, '7 days', 5.49),
        ('Hg Cheat ApkMod', 35, '15 days', 4.49),
        ('Prime Apkmod', 55, '30 days', 6.49),
        ('GlitchShotx 8BP IOS', 70, '7 days', 7.99),
        ('Brmod SilentAim PC', 65, '30 days', 7.49),
        ('Brmod Bypass + Silent', 80, '30 days', 8.99),
        ('Gbox Esign Cert', 90, '15 days', 9.99),
        ('Pato Blue ApkMod', 25, '7 days', 2.99),
        ('Drip Root Android', 50, '30 days', 5.99),
        ('LKTEAM Root + PC', 75, '30 days', 8.49),
        ('Pato Orange ApkMod', 40, '15 days', 4.99),
        ('Pato Green ApkMod', 45, '15 days', 5.49),
        ('Strict Br Root', 60, '30 days', 6.99),
        ('Shield Pubg Android', 55, '30 days', 6.49),
        ('Haxxcker Pro Root', 85, '30 days', 9.49),
        ('Spotify Root', 20, '30 days', 2.49)
    ]
    
    for product in default_products:
        try:
            c.execute("INSERT INTO products (name, credit_cost, duration, price) VALUES (?, ?, ?, ?)",
                     product)
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()

init_db()

# Helper function to generate key
def generate_key():
    alphabet = string.ascii_uppercase + string.digits
    return 'KEY-' + ''.join(secrets.choice(alphabet) for _ in range(4)) + '-' + \
           ''.join(secrets.choice(alphabet) for _ in range(4)) + '-' + \
           ''.join(secrets.choice(alphabet) for _ in range(4))

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
    
    # Generate key
    key = generate_key()
    expiry_date = datetime.now() + timedelta(days=int(product[3].split()[0]))
    
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

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        utr = request.form['utr']
        amount = float(request.form['amount'])
        
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        
        try:
            c.execute("""INSERT INTO payments (username, utr, amount, status, date)
                         VALUES (?, ?, ?, ?, ?)""",
                     (session['username'], utr, amount, 'pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            return render_template('payment.html', success='Payment request submitted successfully')
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
    duration = request.json.get('duration')
    price = float(request.json.get('price'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        c.execute("""INSERT INTO products (name, credit_cost, duration, price)
                     VALUES (?, ?, ?, ?)""", (name, credit_cost, duration, price))
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
    duration = request.json.get('duration')
    price = float(request.json.get('price'))
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""UPDATE products SET name = ?, credit_cost = ?, duration = ?, price = ?
                 WHERE id = ?""", (name, credit_cost, duration, price, product_id))
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
