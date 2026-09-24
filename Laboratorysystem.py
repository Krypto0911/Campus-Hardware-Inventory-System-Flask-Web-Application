import os
import bcrypt
import csv

# Make Tkinter Optional for Web/Render Deployment
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
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn, "postgres"
    else:
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
    """Initializes basic database tables if they do not exist."""
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
                status TEXT NOT NULL DEFAULT 'Available'
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
            cur.execute('''CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL,
                new_password_hash TEXT NOT NULL,
                request_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING'
            )''')
            conn.commit()
        else:
            with conn.cursor() as cur:
                cur.execute('''CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT NOT NULL DEFAULT 'user@campus.edu',
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'USER',
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    is_locked INTEGER NOT NULL DEFAULT 0
                )''')
                cur.execute('''CREATE TABLE IF NOT EXISTS hardware (
                    item_id SERIAL PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Available'
                )''')
                cur.execute('''CREATE TABLE IF NOT EXISTS loans (
                    loan_id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    borrow_date TEXT NOT NULL,
                    return_date TEXT,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'PENDING_BORROW'
                )''')
                cur.execute('''CREATE TABLE IF NOT EXISTS password_resets (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    new_password_hash TEXT NOT NULL,
                    request_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
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
            execute_db("UPDATE users SET failed_attempts = 0 WHERE username = ?", (username,))
            return True, "Login successful.", user['role'], 0, user['email']
        else:
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
                "INSERT INTO password_resets (username, email, new_password_hash, request_time, status) VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'PENDING')",
                (username, email, hashed_pw)
            )
        except Exception as e:
            return False, f"Error submitting reset request: {str(e)}"
        return True, "Password reset request submitted successfully."

    @staticmethod
    def get_pending_resets():
        return query_db("SELECT * FROM password_resets WHERE status = 'PENDING'")

    @staticmethod
    def process_bulk_resets(request_ids, approve, new_password, admin_id):
        for req_id in request_ids:
            req = query_db("SELECT * FROM password_resets WHERE id = ?", (req_id,), one=True)
            if not req:
                continue
            if approve:
                if new_password:
                    hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    execute_db("UPDATE users SET password_hash = ?, is_locked = 0, failed_attempts = 0 WHERE username = ?", (hashed_pw, req["username"]))
                else:
                    execute_db("UPDATE users SET password_hash = ?, is_locked = 0, failed_attempts = 0 WHERE username = ?", (req["new_password_hash"], req["username"]))
                execute_db("UPDATE password_resets SET status = 'APPROVED' WHERE id = ?", (req_id,))
            else:
                execute_db("UPDATE password_resets SET status = 'REJECTED' WHERE id = ?", (req_id,))
        return True, "Password reset requests processed successfully."

    @staticmethod
    def change_password_direct(username, email, old_password, new_password):
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if not user or not bcrypt.checkpw(old_password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return False, "Incorrect old password."
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        execute_db("UPDATE users SET password_hash = ? WHERE username = ?", (hashed_pw, username))
        return True, "Password changed successfully."


class InventoryController:
    @staticmethod
    def _ensure_loans():
        pass

    @staticmethod
    def get_all_items(search="", category="ALL"):
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
        return [row["category"] for row in rows if row["category"]]

    @staticmethod
    def add_item(item_name, category, quantity, unit_price):
        if not item_name or not category:
            return False, "Item name and category are required."
        execute_db(
            "INSERT INTO hardware (item_name, category, quantity, unit_price, status) VALUES (?, ?, ?, ?, 'Available')",
            (item_name, category, quantity, unit_price)
        )
        return True, "Item added successfully."

    @staticmethod
    def delete_bulk_items(item_ids):
        for item_id in item_ids:
            execute_db("DELETE FROM hardware WHERE item_id = ?", (item_id,))
        return True, "Selected items deleted successfully."

    @staticmethod
    def borrow_item(username, item_id, quantity):
        item = query_db("SELECT * FROM hardware WHERE item_id = ?", (item_id,), one=True)
        if not item:
            return False, "Hardware item not found."
        if item["quantity"] < quantity:
            return False, "Requested quantity exceeds available stock."
        
        execute_db(
            "INSERT INTO loans (username, item_id, item_name, borrow_date, quantity, status) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 'PENDING_BORROW')",
            (username, item_id, item["item_name"], quantity)
        )
        return True, "Borrow request submitted successfully."

    @staticmethod
    def get_user_active_loans(username):
        return query_db("SELECT * FROM loans WHERE username = ? AND status = 'BORROWED'", (username,))

    @staticmethod
    def get_user_pending_borrows(username):
        return query_db("SELECT * FROM loans WHERE username = ? AND status = 'PENDING_BORROW'", (username,))

    @staticmethod
    def get_user_loan_history(username):
        return query_db("SELECT * FROM loans WHERE username = ? AND status IN ('RETURNED', 'REJECTED')", (username,))

    @staticmethod
    def get_pending_borrows():
        return query_db("SELECT * FROM loans WHERE status = 'PENDING_BORROW'")

    @staticmethod
    def get_pending_returns():
        return query_db("SELECT * FROM loans WHERE status = 'PENDING_RETURN'")

    @staticmethod
    def get_all_loans_history():
        return query_db("SELECT * FROM loans")

    @staticmethod
    def request_bulk_item_returns(loan_ids):
        for loan_id in loan_ids:
            execute_db("UPDATE loans SET status = 'PENDING_RETURN' WHERE loan_id = ?", (loan_id,))
        return True, "Return requests submitted successfully."

    @staticmethod
    def process_bulk_borrows(loan_ids, approve):
        if not loan_ids:
            return False, "No borrow requests selected."
        processed_count = 0
        for loan_id in loan_ids:
            loan = query_db("SELECT * FROM loans WHERE loan_id = ?", (loan_id,), one=True)
            if not loan:
                continue
            if approve:
                item = query_db("SELECT * FROM hardware WHERE item_id = ?", (loan["item_id"],), one=True)
                if item and item["quantity"] >= loan["quantity"]:
                    new_qty = item["quantity"] - loan["quantity"]
                    execute_db("UPDATE hardware SET quantity = ? WHERE item_id = ?", (new_qty, loan["item_id"]))
                    execute_db("UPDATE loans SET status = 'BORROWED' WHERE loan_id = ?", (loan_id,))
                    processed_count += 1
            else:
                execute_db("UPDATE loans SET status = 'REJECTED' WHERE loan_id = ?", (loan_id,))
                processed_count += 1
        return True, f"Successfully processed {processed_count} borrow request(s)."

    @staticmethod
    def process_bulk_returns(loan_ids, approve):
        if not loan_ids:
            return False, "No return requests selected."
        processed_count = 0
        for loan_id in loan_ids:
            loan = query_db("SELECT * FROM loans WHERE loan_id = ?", (loan_id,), one=True)
            if not loan:
                continue
            if approve:
                item = query_db("SELECT * FROM hardware WHERE item_id = ?", (loan["item_id"],), one=True)
                if item:
                    new_qty = item["quantity"] + loan["quantity"]
                    execute_db("UPDATE hardware SET quantity = ? WHERE item_id = ?", (new_qty, loan["item_id"]))
                execute_db("UPDATE loans SET status = 'RETURNED', return_date = CURRENT_TIMESTAMP WHERE loan_id = ?", (loan_id,))
                processed_count += 1
            else:
                execute_db("UPDATE loans SET status = 'REJECTED' WHERE loan_id = ?", (loan_id,))
                processed_count += 1
        return True, f"Successfully processed {processed_count} return request(s)."

    @staticmethod
    def export_to_csv(username):
        try:
            items = query_db("SELECT * FROM hardware")
            with open("inventory_report.csv", mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Item ID", "Item Name", "Category", "Quantity", "Unit Price", "Status"])
                for item in items:
                    writer.writerow([item["item_id"], item["item_name"], item["category"], item["quantity"], item["unit_price"], item["status"]])
            return True, "Export successful."
        except Exception as e:
            return False, str(e)