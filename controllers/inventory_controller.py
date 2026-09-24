import csv, logging
from pathlib import Path
from models.database import connect

class InventoryController:
    @staticmethod
    def _ensure_loans():
        conn=connect()
        conn.execute("""CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'PENDING_BORROW',
            requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT, reviewed_by INTEGER, returned_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(item_id) REFERENCES hardware(item_id),
            FOREIGN KEY(reviewed_by) REFERENCES users(id))""")
        conn.commit(); conn.close()

    @staticmethod
    def _status(q):
        return "In Stock" if q>5 else ("Low Stock" if q>0 else "Out of Stock")

    @staticmethod
    def get_all_items(search_text="", category="ALL"):
        conn=connect()
        sql="SELECT * FROM hardware WHERE 1=1"; params=[]
        if search_text:
            sql+=" AND (item_name LIKE ? OR category LIKE ?)"; q=f"%{search_text}%"; params += [q,q]
        if category and category!="ALL": sql+=" AND category=?"; params.append(category)
        sql+=" ORDER BY item_id DESC"
        try: return conn.execute(sql,params).fetchall()
        finally: conn.close()

    @staticmethod
    def get_categories():
        conn=connect()
        try: return [r["category"] for r in conn.execute("SELECT DISTINCT category FROM hardware ORDER BY category")]
        finally: conn.close()

    @staticmethod
    def add_item(name,category,quantity,unit_price):
        if not name.strip() or not category.strip(): return False,"Item name and category are required."
        if quantity<0 or unit_price<0: return False,"Quantity and unit price cannot be negative."
        conn=connect()
        try:
            conn.execute("INSERT INTO hardware(item_name,category,quantity,unit_price,status) VALUES(?,?,?,?,?)",
                         (name.strip(),category.strip(),quantity,unit_price,InventoryController._status(quantity)))
            conn.commit(); logging.info("Hardware added: %s",name); return True,"Hardware item added successfully."
        finally: conn.close()

    @staticmethod
    def update_item(item_id,name,category,quantity,unit_price):
        if quantity<0 or unit_price<0: return False,"Quantity and unit price cannot be negative."
        conn=connect()
        try:
            cur=conn.execute("""UPDATE hardware SET item_name=?,category=?,quantity=?,unit_price=?,status=?,
                                updated_at=CURRENT_TIMESTAMP WHERE item_id=?""",
                             (name.strip(),category.strip(),quantity,unit_price,InventoryController._status(quantity),item_id))
            conn.commit()
            return (True,"Hardware item updated successfully.") if cur.rowcount else (False,"Hardware item not found.")
        finally: conn.close()

    @staticmethod
    def delete_bulk_items(ids):
        if not ids: return False,"Select at least one hardware item."
        conn=connect()
        try:
            conn.executemany("DELETE FROM hardware WHERE item_id=?",[(i,) for i in ids]); conn.commit()
            return True,"Selected hardware items deleted."
        finally: conn.close()

    @staticmethod
    def borrow_item(username,item_id,quantity=1):
        InventoryController._ensure_loans()
        if quantity<1: return False,"Borrow quantity must be at least 1."
        conn=connect()
        try:
            item=conn.execute("SELECT * FROM hardware WHERE item_id=?",(item_id,)).fetchone()
            user=conn.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()
            if not item: return False,"Hardware item not found."
            if not user: return False,"User account not found."
            if quantity>item["quantity"]: return False,f"Requested quantity exceeds available stock ({item['quantity']})."
            conn.execute("INSERT INTO loans(user_id,item_id,quantity,status) VALUES(?,?,?,'PENDING_BORROW')",
                         (user["id"],item_id,quantity)); conn.commit()
            return True,"Borrow request submitted for ADMIN approval."
        finally: conn.close()

    @staticmethod
    def get_user_active_loans(username):
        InventoryController._ensure_loans(); conn=connect()
        try: return conn.execute("""SELECT l.*,h.item_name,h.category FROM loans l
            JOIN users u ON u.id=l.user_id JOIN hardware h ON h.item_id=l.item_id
            WHERE u.username=? AND l.status='BORROWED' ORDER BY l.id DESC""",(username,)).fetchall()
        finally: conn.close()

    @staticmethod
    def get_user_pending_borrows(username):
        InventoryController._ensure_loans(); conn=connect()
        try: return conn.execute("""SELECT l.*,h.item_name,h.category FROM loans l
            JOIN users u ON u.id=l.user_id JOIN hardware h ON h.item_id=l.item_id
            WHERE u.username=? AND l.status='PENDING_BORROW' ORDER BY l.id DESC""",(username,)).fetchall()
        finally: conn.close()

    @staticmethod
    def get_user_loan_history(username):
        InventoryController._ensure_loans(); conn=connect()
        try: return conn.execute("""SELECT l.*,h.item_name,h.category FROM loans l
            JOIN users u ON u.id=l.user_id JOIN hardware h ON h.item_id=l.item_id
            WHERE u.username=? ORDER BY l.id DESC""",(username,)).fetchall()
        finally: conn.close()

    @staticmethod
    def get_pending_borrows():
        InventoryController._ensure_loans(); conn=connect()
        try: return conn.execute("""SELECT l.*,u.username,u.email,h.item_name,h.category FROM loans l
            JOIN users u ON u.id=l.user_id JOIN hardware h ON h.item_id=l.item_id
            WHERE l.status='PENDING_BORROW' ORDER BY l.id DESC""").fetchall()
        finally: conn.close()

    @staticmethod
    def get_pending_returns():
        InventoryController._ensure_loans(); conn=connect()
        try: return conn.execute("""SELECT l.*,u.username,u.email,h.item_name,h.category FROM loans l
            JOIN users u ON u.id=l.user_id JOIN hardware h ON h.item_id=l.item_id
            WHERE l.status='RETURN_PENDING' ORDER BY l.id DESC""").fetchall()
        finally: conn.close()

    @staticmethod
    def get_all_loans_history():
        InventoryController._ensure_loans(); conn=connect()
        try: return conn.execute("""SELECT l.*,u.username,h.item_name,h.category FROM loans l
            JOIN users u ON u.id=l.user_id JOIN hardware h ON h.item_id=l.item_id ORDER BY l.id DESC""").fetchall()
        finally: conn.close()

    @staticmethod
    def request_bulk_item_returns(ids):
        InventoryController._ensure_loans()
        if not ids: return False,"Select at least one borrowed item."
        conn=connect()
        try:
            ph=",".join("?"*len(ids))
            cur=conn.execute(f"UPDATE loans SET status='RETURN_PENDING' WHERE id IN ({ph}) AND status='BORROWED'",ids)
            conn.commit()
            return (True,"Return request submitted for ADMIN approval.") if cur.rowcount else (False,"No valid borrowed item was selected.")
        finally: conn.close()

    @staticmethod
    def process_bulk_borrows(ids,approve=True):
        InventoryController._ensure_loans()
        if not ids: return False,"Select at least one borrow request."
        conn=connect(); count=0
        try:
            for lid in ids:
                loan=conn.execute("SELECT * FROM loans WHERE id=? AND status='PENDING_BORROW'",(lid,)).fetchone()
                if not loan: continue
                if approve:
                    item=conn.execute("SELECT * FROM hardware WHERE item_id=?",(loan["item_id"],)).fetchone()
                    if not item or item["quantity"]<loan["quantity"]: continue
                    q=item["quantity"]-loan["quantity"]
                    conn.execute("UPDATE hardware SET quantity=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE item_id=?",(q,InventoryController._status(q),loan["item_id"]))
                    status="BORROWED"
                else: status="REJECTED_BORROW"
                conn.execute("UPDATE loans SET status=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(status,lid)); count+=1
            conn.commit(); return True,f"{count} borrow request(s) processed."
        finally: conn.close()

    @staticmethod
    def process_bulk_returns(ids,approve=True):
        InventoryController._ensure_loans()
        if not ids: return False,"Select at least one return request."
        conn=connect(); count=0
        try:
            for lid in ids:
                loan=conn.execute("SELECT * FROM loans WHERE id=? AND status='RETURN_PENDING'",(lid,)).fetchone()
                if not loan: continue
                if approve:
                    item=conn.execute("SELECT * FROM hardware WHERE item_id=?",(loan["item_id"],)).fetchone()
                    q=item["quantity"]+loan["quantity"]
                    conn.execute("UPDATE hardware SET quantity=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE item_id=?",(q,InventoryController._status(q),loan["item_id"]))
                    conn.execute("UPDATE loans SET status='RETURNED',reviewed_at=CURRENT_TIMESTAMP,returned_at=CURRENT_TIMESTAMP WHERE id=?",(lid,))
                else: conn.execute("UPDATE loans SET status='BORROWED',reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(lid,))
                count+=1
            conn.commit(); return True,f"{count} return request(s) processed."
        finally: conn.close()

    @staticmethod
    def export_to_csv(username):
        path=Path("inventory_report.csv").resolve()
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["Item ID","Item Name","Category","Quantity","Unit Price","Status"])
            for r in InventoryController.get_all_items(): w.writerow([r["item_id"],r["item_name"],r["category"],r["quantity"],r["unit_price"],r["status"]])
        return True,"Inventory report exported."
