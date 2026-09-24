from models.database import init_db
from controllers.auth_controller import AuthController as _AuthController
from controllers.inventory_controller import InventoryController

class AuthController(_AuthController):
    @classmethod
    def login_user(cls,username,password):
        ok,msg,user=cls().login(username,password)
        return (ok,msg,user["role"],bool(user["is_locked"]),user["email"]) if ok else (ok,msg,user["role"] if user else None,bool(user["is_locked"]) if user else False,user["email"] if user else None)
    @classmethod
    def register_user(cls,username,email,password,role="USER"): return cls().register(username,email,password,role)
    @classmethod
    def submit_password_reset_request(cls,username,email,new_password): return cls().request_reset(email)
    @classmethod
    def change_password_direct(cls,username,email,old_password,new_password):
        from models.database import connect
        c=connect()
        try: u=c.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()
        finally: c.close()
        return cls().change_password(u["id"],old_password,new_password) if u else (False,"User account not found.")
    @classmethod
    def get_pending_resets(cls):
        from models.database import connect
        c=connect()
        try: return c.execute("SELECT rr.*,u.username FROM reset_requests rr JOIN users u ON u.id=rr.user_id ORDER BY rr.id DESC").fetchall()
        finally: c.close()
    @classmethod
    def process_bulk_resets(cls,ids,approve=True,new_password=None,admin_id=None):
        if not ids:return False,"Select at least one reset request."
        if approve and not new_password:return False,"Provide a temporary new password."
        if admin_id is None:return False,"Admin session is required."
        count=0
        for rid in ids:
            ok,_=cls().admin_reset_action(rid,admin_id,approve,new_password)
            count += int(ok)
        return True,f"{count} reset request(s) processed."
