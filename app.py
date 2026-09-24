from flask import Flask,render_template,request,redirect,url_for,session,flash,send_file
from functools import wraps
import os
from Laboratorysystem import init_db,AuthController,InventoryController
app=Flask(__name__); app.secret_key=os.environ.get("SECRET_KEY","lab7-development-secret")
def login_required(view):
    @wraps(view)
    def wrapped(*a,**kw):
        if "username" not in session: flash("Please log in first.","warning"); return redirect(url_for("login"))
        return view(*a,**kw)
    return wrapped
def admin_required(view):
    @wraps(view)
    def wrapped(*a,**kw):
        if session.get("role")!="ADMIN": flash("Administrator access required.","danger"); return redirect(url_for("dashboard"))
        return view(*a,**kw)
    return wrapped
@app.route("/")
def index(): return redirect(url_for("dashboard" if "username" in session else "login"))
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form.get("username","").strip(); p=request.form.get("password","")
        if not u or not p: flash("Username and password are required.","danger"); return render_template("login.html")
        ok,msg,role,locked,email=AuthController.login_user(u,p)
        if ok: session.clear(); session.update(username=u,role=role,email=email); flash(msg,"success"); return redirect(url_for("dashboard"))
        flash(msg,"danger"); return render_template("login.html",locked=locked,locked_username=u)
    return render_template("login.html")
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        ok,msg=AuthController.register_user(request.form.get("username",""),request.form.get("email",""),request.form.get("password",""),request.form.get("role","USER"))
        flash(msg,"success" if ok else "danger"); return redirect(url_for("login"))
    return render_template("register.html")
@app.route("/reset-request",methods=["GET","POST"])
def reset_request():
    if request.method=="POST":
        if request.form.get("new_password")!=request.form.get("confirm_password"): flash("New passwords do not match.","danger")
        else:
            ok,msg=AuthController.submit_password_reset_request(request.form.get("username",""),request.form.get("email",""),request.form.get("new_password","")); flash(msg,"success" if ok else "danger")
        return redirect(url_for("login"))
    return render_template("reset.html")
@app.route("/dashboard")
@login_required
def dashboard():
    search=request.args.get("search","").strip(); category=request.args.get("category","ALL") or "ALL"
    items=InventoryController.get_all_items(search,category); categories=InventoryController.get_categories()
    total_stocks=sum(x["quantity"] for x in InventoryController.get_all_items())
    active=[]; history=[]; preturn=[]; pborrow=[]; puser=[]; all_loans=[]; resets=[]
    if session["role"]=="USER":
        active=InventoryController.get_user_active_loans(session["username"]); puser=InventoryController.get_user_pending_borrows(session["username"]); history=InventoryController.get_user_loan_history(session["username"])
    else:
        preturn=InventoryController.get_pending_returns(); pborrow=InventoryController.get_pending_borrows(); all_loans=InventoryController.get_all_loans_history(); resets=AuthController.get_pending_resets()
    return render_template("dashboard.html",items=items,categories=categories,search=search,selected_category=category,total_stocks=total_stocks,active_loans=active,history=history,pending_returns=preturn,pending_borrows=pborrow,pending_borrow_requests=puser,all_loans=all_loans,pending_resets=resets)
@app.post("/borrow")
@login_required
def borrow():
    try:i=int(request.form["item_id"]); q=int(request.form.get("quantity","1"))
    except (KeyError,ValueError): flash("Invalid item or borrow quantity.","danger"); return redirect(url_for("dashboard"))
    ok,msg=InventoryController.borrow_item(session["username"],i,q); flash(msg,"success" if ok else "danger"); return redirect(url_for("dashboard"))
@app.post("/return-request")
@login_required
def return_request():
    try:ids=[int(x) for x in request.form.getlist("loan_ids")]
    except ValueError:ids=[]
    ok,msg=InventoryController.request_bulk_item_returns(ids); flash(msg,"success" if ok else "warning"); return redirect(url_for("dashboard"))
@app.post("/change-password")
@login_required
def change_password():
    ok,msg=AuthController.change_password_direct(session["username"],session.get("email",""),request.form.get("old_password",""),request.form.get("new_password","")); flash(msg,"success" if ok else "danger"); return redirect(url_for("dashboard"))
@app.post("/admin/add")
@admin_required
def admin_add():
    try:q=int(request.form["quantity"]); price=float(request.form["unit_price"])
    except (KeyError,ValueError):flash("Quantity must be an integer and unit price must be numeric.","danger");return redirect(url_for("dashboard"))
    ok,msg=InventoryController.add_item(request.form.get("item_name",""),request.form.get("category",""),q,price);flash(msg,"success" if ok else "danger");return redirect(url_for("dashboard"))
@app.post("/admin/delete")
@admin_required
def admin_delete():
    ids=[int(x) for x in request.form.getlist("item_ids") if x.isdigit()];ok,msg=InventoryController.delete_bulk_items(ids);flash(msg,"success" if ok else "warning");return redirect(url_for("dashboard"))
@app.post("/admin/borrow-action")
@admin_required
def admin_borrow_action():
    ids=[int(x) for x in request.form.getlist("loan_ids") if x.isdigit()];ok,msg=InventoryController.process_bulk_borrows(ids,request.form.get("action")=="approve");flash(msg,"success" if ok else "danger");return redirect(url_for("dashboard"))
@app.post("/admin/return-action")
@admin_required
def admin_return_action():
    ids=[int(x) for x in request.form.getlist("loan_ids") if x.isdigit()];ok,msg=InventoryController.process_bulk_returns(ids,request.form.get("action")=="approve");flash(msg,"success" if ok else "danger");return redirect(url_for("dashboard"))
@app.post("/admin/reset-action")
@admin_required
def admin_reset_action():
    ids=[int(x) for x in request.form.getlist("request_ids") if x.isdigit()]; approve=request.form.get("action")=="approve"; pw=request.form.get("new_password","")
    from models.database import connect
    c=connect(); admin=c.execute("SELECT id FROM users WHERE username=?",(session["username"],)).fetchone(); c.close()
    ok,msg=AuthController.process_bulk_resets(ids,approve,pw,admin["id"] if admin else None);flash(msg,"success" if ok else "danger");return redirect(url_for("dashboard"))
@app.get("/export")
@login_required
def export():
    ok,msg=InventoryController.export_to_csv(session["username"])
    if not ok:flash(msg,"danger");return redirect(url_for("dashboard"))
    return send_file(os.path.abspath("inventory_report.csv"),as_attachment=True,download_name="inventory_report.csv")
@app.get("/logout")
def logout():session.clear();flash("You have been logged out.","success");return redirect(url_for("login"))
if __name__=="__main__":
    init_db();InventoryController._ensure_loans();print("CAMPUS HARDWARE INVENTORY - WEB PORTAL");print("Open Google Chrome: http://127.0.0.1:5000");app.run(debug=True)
