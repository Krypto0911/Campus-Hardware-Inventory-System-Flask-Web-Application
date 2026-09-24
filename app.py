from flask import Flask, render_template, request, redirect, url_for, session, flash
from Laboratorysystem import InventoryController, query_db, execute_db
import bcrypt

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Replace with a secure random key for production/Render

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            if user['is_locked'] == 1:
                flash('Your account is locked. Please contact the administrator.', 'danger')
                return render_template('login.html')
            
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email', 'user@campus.edu')
        password = request.form.get('password')
        
        existing = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if existing:
            flash('Username already exists.', 'danger')
        else:
            hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            execute_db(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, 'USER')",
                (username, email, hashed_pw)
            )
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    hardware_list = InventoryController.get_all_hardware()
    
    # Fetch pending borrow and return requests for admin management
    pending_borrows = []
    pending_returns = []
    user_loans = []
    
    if session.get('role') == 'ADMIN':
        pending_borrows = query_db("SELECT * FROM loans WHERE status = 'PENDING_BORROW'")
        pending_returns = query_db("SELECT * FROM loans WHERE status = 'RETURN_PENDING'")
    else:
        user_loans = query_db("SELECT * FROM loans WHERE username = ?", (session['username'],))
        
    return render_template(
        'dashboard.html',
        username=session['username'],
        role=session['role'],
        hardware=hardware_list,
        pending_borrows=pending_borrows,
        pending_returns=pending_returns,
        user_loans=user_loans
    )

@app.route('/admin/process_borrows', methods=['POST'])
def process_borrows():
    if 'username' not in session or session.get('role') != 'ADMIN':
        return redirect(url_for('login'))
        
    loan_ids = request.form.getlist('loan_ids')
    approve = 'approve' in request.form
    
    # Calls the controller method with validation check
    success, message = InventoryController.process_bulk_borrows(loan_ids, approve)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/admin/process_returns', methods=['POST'])
def process_returns():
    if 'username' not in session or session.get('role') != 'ADMIN':
        return redirect(url_for('login'))
        
    loan_ids = request.form.getlist('loan_ids')
    approve = 'approve' in request.form
    
    # Calls the controller method with validation check
    success, message = InventoryController.process_bulk_returns(loan_ids, approve)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/request_borrow', methods=['POST'])
def request_borrow():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    item_id = request.form.get('item_id')
    quantity = int(request.form.get('quantity', 1))
    
    item = query_db("SELECT * FROM hardware WHERE item_id = ?", (item_id,), one=True)
    if item:
        InventoryController.request_borrow(session['username'], item['item_id'], item['item_name'], quantity)
        flash('Borrow request submitted successfully.', 'success')
    else:
        flash('Selected item not found.', 'danger')
        
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)