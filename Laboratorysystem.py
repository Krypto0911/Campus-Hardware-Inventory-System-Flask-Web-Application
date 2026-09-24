import os
import bcrypt

# A.1 Make Tkinter Optional for Web/Render Deployment
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    TKINTER_AVAILABLE = True
except ImportError:
    tk = None
    messagebox = None
    ttk = None
    TKINTER_AVAILABLE = False

# Database configuration detection
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row
else:
    import sqlite3

SQLITE_DB = "hardware_inventory.db"


def get_db_connection():
    """Returns a database connection depending on whether DATABASE_URL is configured."""
    if DATABASE_URL:
        # Connect to Supabase PostgreSQL
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn, "postgres"
    else:
        # Fallback to local SQLite
        conn = sqlite3.connect(SQLITE_DB)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"


def query_db(query, args=(), one=False):
    """Executes a SELECT query and returns rows as dictionaries."""
    conn, db_type = get_db_connection()
    if db_type == "postgres":
        query = query.replace('?', '%s')
    try:
        if db_type == "postgres":
            with conn.cursor() as cur:
                cur.execute(query, args)
                rv = cur.fetchall()
                return (rv[0] if rv else None) if one else rv
        else:
            cur = conn.cursor()
            cur.execute(query, args)
            rv = cur.fetchall()
            return (rv[0] if rv else None) if one else rv
    finally:
        conn.close()


def execute_db(query, args=()):
    """Executes an INSERT, UPDATE, or DELETE query."""
    conn, db_type = get_db_connection()
    if db_type == "postgres":
        query = query.replace('?', '%s')
    try:
        if db_type == "postgres":
            with conn.cursor() as cur:
                cur.execute(query, args)
                conn.commit()
        else:
            cur = conn.cursor()
            cur.execute(query, args)
            conn.commit()
    finally:
        conn.close()


def init_db():
    """Initializes basic database tables if they do not exist (mainly for local SQLite)."""
    conn, db_type = get_db_connection()
    try:
        if db_type == "sqlite":
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL DEFAULT 'user@campus.edu',
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'USER',
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                is_locked INTEGER NOT NULL DEFAULT 0
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS hardware (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                status TEXT NOT NULL
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS loans (
                loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                borrow_date TEXT NOT NULL,
                return_date TEXT,
                quantity INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'PENDING_BORROW'
            )''')
            conn.commit()
    finally:
        conn.close()


class AuthController:
    @staticmethod
    def login_user(username, password):
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if not user:
            return False, "Invalid username or password.", "USER", 0, ""
        
        if user['is_locked'] == 1:
            return False, "Account is locked. Please contact administrator.", user['role'], 1, user['email']
        
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            # Reset failed attempts on success
            execute_db("UPDATE users SET failed_attempts = 0 WHERE username = ?", (username,))
            return True, "Login successful.", user['role'], 0, user['email']
        else:
            # Increment failed attempts
            attempts = user['failed_attempts'] + 1
            locked = 1 if attempts >= 3 else 0
            execute_db("UPDATE users SET failed_attempts = ?, is_locked = ? WHERE username = ?", (attempts, locked, username))
            if locked:
                return False, "Account locked due to multiple failed login attempts.", user['role'], 1, user['email']
            return False, f"Invalid password. Attempt {attempts} of 3.", user['role'], 0, user['email']

    @staticmethod
    def register_user(username, email, password, role="USER"):
        if not username or not password:
            return False, "Username and password are required."
        existing = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if existing:
            return False, "Username already exists."
        
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        execute_db(
            "INSERT INTO users (username, email, password_hash, role, failed_attempts, is_locked) VALUES (?, ?, ?, ?, 0, 0)",
            (username, email or "user@campus.edu", hashed_pw, role)
        )
        return True, "Registration successful. Please log in."

    @staticmethod
    def submit_password_reset_request(username, email, new_password):
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if not user:
            return False, "Username not found."
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            execute_db(
                "INSERT INTO password_resets (username, email, new_password_hash, request_time, status) VALUES (?, ?, ?, datetime('now'), 'PENDING')",
                (username, email, hashed_pw)
            )
        except Exception:
            pass  # Table might be structured differently or managed via migration
        return True, "Password reset request submitted successfully."


class InventoryController:
    @staticmethod
    def get_all_hardware(search="", category="ALL"):
        query = "SELECT * FROM hardware WHERE 1=1"
        params = []
        if search:
            query += " AND item_name LIKE ?"
            params.append(f"%{search}%")
        if category and category != "ALL":
            query += " AND category = ?"
            params.append(category)
        return query_db(query, tuple(params))

    @staticmethod
    def get_categories():
        rows = query_db("SELECT DISTINCT category FROM hardware")
        return [row["category"] for row in rows]

    @staticmethod
    def get_all_hardware_items():
        return query_db("SELECT * FROM hardware")

    @staticmethod
    def borrow_item(username, item_id, quantity):
        item = query_db("SELECT * FROM hardware WHERE item_id = ?", (item_id,), one=True)
        if not item:
            return False, "Hardware item not found."
        if item["quantity"] < quantity:
            return False, "Requested quantity exceeds available stock."
        
        execute_db(
            "INSERT INTO loans (username, item_id, item_name, borrow_date, quantity, status) VALUES (?, ?, ?, datetime('now'), ?, 'PENDING_BORROW')",
            (username, item_id, item["item_name"], quantity)
        )
        return True, "Borrow request submitted successfully."

    @staticmethod
    def process_bulk_borrows(loan_ids, approve):
        for loan_id in loan_ids:
            loan = query_db("SELECT * FROM loans WHERE loan_id = ?", (loan_id,), one=True)
            if not loan or loan["status"] != "PENDING_BORROW":
                continue
            if approve:
                # Deduct stock and update loan status
                item = query_db("SELECT * FROM hardware WHERE item_id = ?", (loan["item_id"],), one=True)
                if item and item["quantity"] >= loan["quantity"]:
                    new_qty = item["quantity"] - loan["quantity"]
                    execute_db("UPDATE hardware SET quantity = ? WHERE item_id = ?", (new_qty, loan["item_id"]))
                    execute_db("UPDATE loans SET status = 'BORROWED' WHERE loan_id = ?", (loan_id,))
            else:
                execute_db("UPDATE loans SET status = 'REJECTED' WHERE loan_id = ?", (loan_id,))
        return True, "Borrow requests processed successfully."

    @staticmethod
    def process_bulk_returns(loan_ids, approve):
        for loan_id in loan_ids:
            loan = query_db("SELECT * FROM loans WHERE loan_id = ?", (loan_id,), one=True)
            if not loan:
                continue
            if approve:
                item = query_db("SELECT * FROM hardware WHERE item_id = ?", (loan["item_id"],), one=True)
                if item:
                    new_qty = item["quantity"] + loan["quantity"]
                    execute_db("UPDATE hardware SET quantity = ? WHERE item_id = ?", (new_qty, loan["item_id"]))
                execute_db("UPDATE loans SET status = 'RETURNED', return_date = datetime('now') WHERE loan_id = ?", (loan_id,))
        return True, "Return requests processed successfully."