import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = "inventory.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, args=(), one=False):
    db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    db.close()
    return (rv[0] if rv else None) if one else rv

def init_db():
    db = get_db()
    
    # Users table
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'USER',
            is_locked INTEGER DEFAULT 0,
            failed_attempts INTEGER DEFAULT 0
        )
    """)
    
    # Items table
    db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL
        )
    """)
    
    # Loans table
    db.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
    """)
    
    # Password Reset Requests table
    db.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL,
            new_password_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING'
        )
    """)
    
    db.commit()
    
    # Seed default admin if not exists
    admin = query_db("SELECT * FROM users WHERE username = 'admin'", one=True)
    if not admin:
        pw_hash = generate_password_hash("admin123")
        db.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   ("admin", "admin@lab.com", pw_hash, "ADMIN"))
        db.commit()
        
    db.close()

class AuthController:
    @staticmethod
    def register_user(username, email, password, role="USER"):
        if not username or not email or not password:
            return False, "All fields are required for registration."
        existing = query_db("SELECT id FROM users WHERE username = ?", (username,), one=True)
        if existing:
            return False, "Username already exists."
        
        pw_hash = generate_password_hash(password)
        db = get_db()
        db.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   (username, email, pw_hash, role))
        db.commit()
        db.close()
        return True, "Registration successful! Please log in."

    @staticmethod
    def login_user(username, password):
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if not user:
            return False, "Invalid username or password.", "USER", False, ""
        
        if user["is_locked"]:
            return False, "Your account is locked. Contact an administrator or submit a password reset.", user["role"], True, user["email"]
            
        if check_password_hash(user["password_hash"], password):
            # Reset failed attempts on success
            db = get_db()
            db.execute("UPDATE users SET failed_attempts = 0 WHERE username = ?", (username,))
            db.commit()
            db.close()
            return True, "Logged in successfully.", user["role"], False, user["email"]
        else:
            # Increment failed attempts
            attempts = user["failed_attempts"] + 1
            locked = 1 if attempts >= 3 else 0
            db = get_db()
            db.execute("UPDATE users SET failed_attempts = ?, is_locked = ? WHERE username = ?", (attempts, locked, username))
            db.commit()
            db.close()
            if locked:
                return False, "Account locked due to 3 failed login attempts.", user["role"], True, user["email"]
            return False, f"Invalid password. Attempt {attempts} of 3.", user["role"], False, user["email"]

    @staticmethod
    def submit_password_reset_request(username, email, new_password):
        user = query_db("SELECT * FROM users WHERE username = ? AND email = ?", (username, email), one=True)
        if not user:
            return False, "Username and email do not match any account."
        
        pw_hash = generate_password_hash(new_password)
        db = get_db()
        db.execute("INSERT INTO password_resets (username, email, new_password_hash, status) VALUES (?, ?, ?, 'PENDING')",
                   (username, email, pw_hash))
        db.commit()
        db.close()
        return True, "Password reset request submitted to admin for approval."

    @staticmethod
    def get_pending_resets():
        return query_db("SELECT * FROM password_resets WHERE status = 'PENDING'")

    @staticmethod
    def process_bulk_resets(request_ids, approve, new_pw, admin_id):
        if not request_ids:
            return False, "No reset requests selected."
        
        db = get_db()
        for req_id in request_ids:
            req = query_db("SELECT * FROM password_resets WHERE id = ? AND status = 'PENDING'", (req_id,), one=True)
            if not req:
                continue
            if approve:
                # If an admin provided a custom new password override, use it, otherwise use requested hash
                pw_hash = generate_password_hash(new_pw) if new_pw else req["new_password_hash"]
                db.execute("UPDATE users SET password_hash = ?, is_locked = 0, failed_attempts = 0 WHERE username = ?",
                           (pw_hash, req["username"]))
                db.execute("UPDATE password_resets SET status = 'APPROVED' WHERE id = ?", (req_id,))
            else:
                db.execute("UPDATE password_resets SET status = 'REJECTED' WHERE id = ?", (req_id,))
        db.commit()
        db.close()
        return True, "Password reset requests processed successfully."

    @staticmethod
    def change_password_direct(username, email, old_password, new_password):
        user = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
        if not user or not check_password_hash(user["password_hash"], old_password):
            return False, "Incorrect old password."
        
        pw_hash = generate_password_hash(new_password)
        db = get_db()
        db.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pw_hash, username))
        db.commit()
        db.close()
        return True, "Password changed successfully."


class InventoryController:
    @staticmethod
    def _ensure_loans():
        pass

    @staticmethod
    def get_all_items(search="", category="ALL"):
        db = get_db()
        query = "SELECT * FROM items WHERE 1=1"
        params = []
        if search:
            query += " AND item_name LIKE ?"
            params.append(f"%{search}%")
        if category and category != "ALL":
            query += " AND category = ?"
            params.append(category)
        res = query_db(query, params)
        db.close()
        return res

    @staticmethod
    def get_categories():
        rows = query_db("SELECT DISTINCT category FROM items")
        return [r["category"] for r in rows]

    @staticmethod
    def add_item(name, category, quantity, unit_price):
        if not name or not category:
            return False, "Item name and category are required."
        db = get_db()
        db.execute("INSERT INTO items (item_name, category, quantity, unit_price) VALUES (?, ?, ?, ?)",
                   (name, category, quantity, unit_price))
        db.commit()
        db.close()
        return True, "Item added successfully."

    @staticmethod
    def delete_bulk_items(item_ids):
        if not item_ids:
            return False, "No items selected for deletion."
        db = get_db()
        for iid in item_ids:
            db.execute("DELETE FROM items WHERE id = ?", (iid,))
        db.commit()
        db.close()
        return True, "Selected items deleted successfully."

    @staticmethod
    def borrow_item(username, item_id, quantity):
        item = query_db("SELECT * FROM items WHERE id = ?", (item_id,), one=True)
        if not item or item["quantity"] < quantity:
            return False, "Requested quantity exceeds available stock."
        
        db = get_db()
        db.execute("INSERT INTO loans (username, item_id, quantity, status) VALUES (?, ?, ?, 'PENDING')",
                   (username, item_id, quantity))
        db.commit()
        db.close()
        return True, "Borrow request submitted successfully, pending approval."

    @staticmethod
    def get_user_active_loans(username):
        return query_db("""
            SELECT l.id as loan_id, i.item_name, l.quantity, l.status 
            FROM loans l JOIN items i ON l.item_id = i.id 
            WHERE l.username = ? AND l.status IN ('APPROVED', 'RETURN_PENDING')
        """, (username,))

    @staticmethod
    def get_user_pending_borrows(username):
        return query_db("""
            SELECT l.id as loan_id, i.item_name, l.quantity, l.status 
            FROM loans l JOIN items i ON l.item_id = i.id 
            WHERE l.username = ? AND l.status = 'PENDING'
        """, (username,))

    @staticmethod
    def get_user_loan_history(username):
        return query_db("""
            SELECT l.id as loan_id, i.item_name, l.quantity, l.status 
            FROM loans l JOIN items i ON l.item_id = i.id 
            WHERE l.username = ? AND l.status IN ('RETURNED', 'REJECTED')
        """, (username,))

    @staticmethod
    def get_pending_borrows():
        return query_db("""
            SELECT l.id as loan_id, l.username, i.item_name, l.quantity, l.status 
            FROM loans l JOIN items i ON l.item_id = i.id 
            WHERE l.status = 'PENDING'
        """)

    @staticmethod
    def get_pending_returns():
        return query_db("""
            SELECT l.id as loan_id, l.username, i.item_name, l.quantity, l.status 
            FROM loans l JOIN items i ON l.item_id = i.id 
            WHERE l.status = 'RETURN_PENDING'
        """)

    @staticmethod
    def get_all_loans_history():
        return query_db("""
            SELECT l.id as loan_id, l.username, i.item_name, l.quantity, l.status 
            FROM loans l JOIN items i ON l.item_id = i.id
        """)

    @staticmethod
    def request_bulk_item_returns(loan_ids):
        if not loan_ids:
            return False, "No active loans selected for return."
        db = get_db()
        for lid in loan_ids:
            db.execute("UPDATE loans SET status = 'RETURN_PENDING' WHERE id = ? AND status = 'APPROVED'", (lid,))
        db.commit()
        db.close()
        return True, "Return requests submitted for admin approval."

    @staticmethod
    def process_bulk_borrows(loan_ids, approve):
        if not loan_ids:
            return False, "No borrow requests selected."
        
        clean_ids = []
        for lid in loan_ids:
            try:
                clean_ids.append(int(lid))
            except (ValueError, TypeError):
                continue
                
        if not clean_ids:
            return False, "No borrow requests selected."

        status_to_set = 'APPROVED' if approve else 'REJECTED'
        db = get_db()
        
        for loan_id in clean_ids:
            loan = query_db("SELECT * FROM loans WHERE id = ? AND status = 'PENDING'", (loan_id,), one=True)
            if not loan:
                continue
                
            if approve:
                item = query_db("SELECT quantity FROM items WHERE id = ?", (loan['item_id'],), one=True)
                if not item or item['quantity'] < loan['quantity']:
                    db.close()
                    return False, f"Insufficient stock for item ID {loan['item_id']}."
                db.execute("UPDATE items SET quantity = quantity - ? WHERE id = ?", (loan['quantity'], loan['item_id']))
            
            db.execute("UPDATE loans SET status = ? WHERE id = ?", (status_to_set, loan_id))
            
        db.commit()
        db.close()
        action_word = "approved" if approve else "rejected"
        return True, f"Successfully {action_word} selected borrow requests."

    @staticmethod
    def process_bulk_returns(loan_ids, approve):
        if not loan_ids:
            return False, "No return requests selected."
            
        clean_ids = []
        for lid in loan_ids:
            try:
                clean_ids.append(int(lid))
            except (ValueError, TypeError):
                continue
                
        if not clean_ids:
            return False, "No return requests selected."

        db = get_db()
        for loan_id in clean_ids:
            loan = query_db("SELECT * FROM loans WHERE id = ? AND status = 'RETURN_PENDING'", (loan_id,), one=True)
            if not loan:
                continue
            if approve:
                db.execute("UPDATE items SET quantity = quantity + ? WHERE id = ?", (loan['quantity'], loan['item_id']))
                db.execute("UPDATE loans SET status = 'RETURNED' WHERE id = ?", (loan_id,))
            else:
                db.execute("UPDATE loans SET status = 'APPROVED' WHERE id = ?", (loan_id,))
        db.commit()
        db.close()
        return True, "Return requests processed successfully."

    @staticmethod
    def export_to_csv(username):
        items = query_db("SELECT * FROM items")
        try:
            with open("inventory_report.csv", "w", encoding="utf-8") as f:
                f.write("ID,Item Name,Category,Quantity,Unit Price\n")
                for itm in items:
                    f.write(f"{itm['id']},{itm['item_name']},{itm['category']},{itm['quantity']},{itm['unit_price']}\n")
            return True, "Export successful."
        except Exception as e:
            return False, str(e)