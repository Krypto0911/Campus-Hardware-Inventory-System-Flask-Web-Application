import os
import sqlite3

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

DB_NAME = "hardware_inventory.db"

def get_db_connection():
    """Helper function to get a database connection supporting row factory."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, args=(), one=False):
    """Helper function to execute a read query."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    """Helper function to execute write/update/delete queries."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, args)
    conn.commit()
    conn.close()

class InventoryController:
    @staticmethod
    def get_all_hardware():
        return query_db("SELECT * FROM hardware")

    @staticmethod
    def add_hardware(item_name, category, quantity, unit_price, status):
        execute_db(
            "INSERT INTO hardware (item_name, category, quantity, unit_price, status) VALUES (?, ?, ?, ?, ?)",
            (item_name, category, quantity, unit_price, status)
        )

    @staticmethod
    def update_hardware(item_id, item_name, category, quantity, unit_price, status):
        execute_db(
            "UPDATE hardware SET item_name = ?, category = ?, quantity = ?, unit_price = ?, status = ? WHERE item_id = ?",
            (item_name, category, quantity, unit_price, status, item_id)
        )

    @staticmethod
    def delete_hardware(item_id):
        execute_db("DELETE FROM hardware WHERE item_id = ?", (item_id,))

    @staticmethod
    def request_borrow(username, item_id, item_name, quantity):
        import datetime
        borrow_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execute_db(
            "INSERT INTO loans (username, item_id, item_name, borrow_date, quantity, status) VALUES (?, ?, ?, ?, ?, 'PENDING_BORROW')",
            (username, item_id, item_name, borrow_date, quantity)
        )

    @staticmethod
    def process_bulk_borrows(loan_ids, approve):
        if not loan_ids:
            return False, "No borrow requests selected. Please select at least one item."
        
        for lid in loan_ids:
            loan = query_db("SELECT * FROM loans WHERE loan_id = ?", (lid,), one=True)
            if not loan:
                continue
            if approve:
                item = query_db("SELECT * FROM hardware WHERE item_id = ?", (loan["item_id"],), one=True)
                if item and item["quantity"] >= loan["quantity"]:
                    new_qty = item["quantity"] - loan["quantity"]
                    new_status = "AVAILABLE" if new_qty > 0 else "OUT OF STOCK"
                    execute_db("UPDATE hardware SET quantity = ?, status = ? WHERE item_id = ?", (new_qty, new_status, loan["item_id"]))
                    execute_db("UPDATE loans SET status = 'BORROWED' WHERE loan_id = ?", (lid,))
                else:
                    execute_db("UPDATE loans SET status = 'REJECTED' WHERE loan_id = ?", (lid,))
            else:
                execute_db("UPDATE loans SET status = 'REJECTED' WHERE loan_id = ?", (lid,))
        return True, "Borrow requests processed successfully."

    @staticmethod
    def process_bulk_returns(loan_ids, approve):
        if not loan_ids:
            return False, "No return requests selected. Please select at least one item."
            
        for lid in loan_ids:
            loan = query_db("SELECT * FROM loans WHERE loan_id = ?", (lid,), one=True)
            if not loan:
                continue
            if approve:
                item = query_db("SELECT * FROM hardware WHERE item_id = ?", (loan["item_id"],), one=True)
                if item:
                    new_qty = item["quantity"] + loan["quantity"]
                    execute_db("UPDATE hardware SET quantity = ?, status = 'AVAILABLE' WHERE item_id = ?", (new_qty, loan["item_id"]))
                import datetime
                ret_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                execute_db("UPDATE loans SET status = 'RETURNED', return_date = ? WHERE loan_id = ?", (ret_date, lid))
            else:
                execute_db("UPDATE loans SET status = 'BORROWED' WHERE loan_id = ?", (lid,))
        return True, "Return requests processed successfully."