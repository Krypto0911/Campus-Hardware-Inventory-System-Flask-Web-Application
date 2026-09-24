import csv, logging, os, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from models.database import init_db, connect
from models.schemas import HardwareSchema
from controllers.auth_controller import AuthController
from views.login_view import LoginView

os.makedirs('app_logging', exist_ok=True)
logging.basicConfig(filename='app_logging/app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
init_db()

class App:
    def __init__(self, user):
        self.user=user; self.root=tk.Tk(); self.root.title(f'Campus Hardware Inventory - {user["role"]}'); self.root.geometry('1050x700'); self.auth=AuthController(); self.build(); logging.info(f'Dashboard opened: {user["username"]}')
    def build(self):
        top=ttk.Frame(self.root,padding=10); top.pack(fill='x'); ttk.Label(top,text=f'Welcome, {self.user["username"]} ({self.user["role"]})',font=('Arial',16,'bold')).pack(side='left'); ttk.Button(top,text='My Profile & Security',command=self.profile).pack(side='right',padx=5); ttk.Button(top,text='Logout',command=self.logout).pack(side='right',padx=5)
        if self.user['role']=='ADMIN': ttk.Button(top,text='Admin Approvals',command=self.approvals).pack(side='right',padx=5)
        body=ttk.Frame(self.root,padding=10); body.pack(fill='both',expand=True)
        form=ttk.LabelFrame(body,text='Hardware Catalog',padding=10); form.pack(fill='x')
        self.name=tk.StringVar(); self.cat=tk.StringVar(); self.qty=tk.StringVar(); self.price=tk.StringVar(); self.selected_id=None
        for i,(lab,var) in enumerate([('Item Name',self.name),('Category',self.cat),('Quantity',self.qty),('Unit Price',self.price)]): ttk.Label(form,text=lab).grid(row=0,column=i,sticky='w',padx=5); ttk.Entry(form,textvariable=var,width=22).grid(row=1,column=i,padx=5,pady=5)
        ttk.Button(form,text='Save / Add',command=self.save_item).grid(row=1,column=4,padx=5); ttk.Button(form,text='Delete Selected',command=self.delete_item).grid(row=1,column=5,padx=5); ttk.Button(form,text='Clear',command=self.clear).grid(row=1,column=6,padx=5); ttk.Button(form,text='Export CSV',command=self.export_csv).grid(row=1,column=7,padx=5)
        search=ttk.Frame(body); search.pack(fill='x',pady=8); self.search=tk.StringVar(); ttk.Label(search,text='Search / Filter:').pack(side='left'); ttk.Entry(search,textvariable=self.search,width=40).pack(side='left',padx=5); ttk.Button(search,text='Search',command=self.load).pack(side='left'); ttk.Button(search,text='Show All',command=lambda:(self.search.set(''),self.load())).pack(side='left',padx=5)
        cols=('ID','Name','Category','Qty','Price','Status'); self.tree=ttk.Treeview(body,columns=cols,show='headings');
        for c in cols: self.tree.heading(c,text=c); self.tree.column(c,width=140)
        self.tree.pack(fill='both',expand=True); self.tree.bind('<<TreeviewSelect>>',self.select_item); self.load()
    def status(self,q): return 'In Stock' if q>5 else ('Low Stock' if q>=1 else 'Out of Stock')
    def load(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        q=f'%{self.search.get()}%'; conn=connect(); rows=conn.execute('SELECT * FROM hardware WHERE item_name LIKE ? OR category LIKE ? ORDER BY item_id',(q,q)).fetchall(); conn.close()
        for r in rows: self.tree.insert('', 'end', values=(r['item_id'],r['item_name'],r['category'],r['quantity'],f'{r["unit_price"]:.2f}',r['status']))
    def save_item(self):
        try: d=HardwareSchema(item_name=self.name.get(),category=self.cat.get(),quantity=int(self.qty.get()),unit_price=float(self.price.get()))
        except Exception as e: messagebox.showerror('Validation',str(e)); return
        conn=connect(); st=self.status(d.quantity)
        if self.selected_id: conn.execute('UPDATE hardware SET item_name=?,category=?,quantity=?,unit_price=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE item_id=?',(d.item_name,d.category,d.quantity,d.unit_price,st,self.selected_id)); logging.info(f'Inventory updated: id={self.selected_id}')
        else: cur=conn.execute('INSERT INTO hardware(item_name,category,quantity,unit_price,status) VALUES(?,?,?,?,?)',(d.item_name,d.category,d.quantity,d.unit_price,st)); logging.info(f'Inventory added: id={cur.lastrowid}, item={d.item_name}')
        conn.commit(); conn.close(); self.clear(); self.load()
    def select_item(self,_=None):
        s=self.tree.selection()
        if not s:return
        v=self.tree.item(s[0])['values']; self.selected_id=v[0]; self.name.set(v[1]); self.cat.set(v[2]); self.qty.set(v[3]); self.price.set(v[4])
    def delete_item(self):
        if not self.selected_id:return
        if messagebox.askyesno('Delete','Delete selected hardware item?'):
            conn=connect(); conn.execute('DELETE FROM hardware WHERE item_id=?',(self.selected_id,)); conn.commit(); conn.close(); logging.info(f'Inventory deleted: id={self.selected_id}'); self.clear(); self.load()
    def clear(self): self.selected_id=None; self.name.set(''); self.cat.set(''); self.qty.set(''); self.price.set('')
    def export_csv(self):
        path=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='inventory_report.csv',filetypes=[('CSV','*.csv')]);
        if not path:return
        conn=connect(); rows=conn.execute('SELECT item_id,item_name,category,quantity,unit_price,status FROM hardware ORDER BY item_id').fetchall(); conn.close()
        with open(path,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(['ID','Name','Category','Quantity','Unit Price','Status']); [w.writerow(list(r)) for r in rows]
        logging.info(f'Inventory exported to CSV: {path}'); messagebox.showinfo('Export','Inventory exported successfully.')
    def profile(self):
        win=tk.Toplevel(self.root); win.title('My Profile & Security'); win.geometry('420x350'); f=ttk.Frame(win,padding=20); f.pack(fill='both',expand=True); ttk.Label(f,text=f'Username: {self.user["username"]}').pack(anchor='w',pady=5); ttk.Label(f,text=f'Email: {self.user["email"]}').pack(anchor='w',pady=5); ttk.Label(f,text=f'Role: {self.user["role"]}').pack(anchor='w',pady=5); cur=tk.StringVar(); new=tk.StringVar(); ttk.Label(f,text='Current Password').pack(anchor='w'); ttk.Entry(f,textvariable=cur,show='*').pack(fill='x'); ttk.Label(f,text='New Password').pack(anchor='w',pady=(10,0)); ttk.Entry(f,textvariable=new,show='*').pack(fill='x'); ttk.Button(f,text='Change Password',command=lambda:self.change_pass(win,cur.get(),new.get())).pack(fill='x',pady=15)
    def change_pass(self,win,cur,new):
        ok,msg=self.auth.change_password(self.user['id'],cur,new); (messagebox.showinfo if ok else messagebox.showerror)('Password',msg)
        if ok: win.destroy()
    def approvals(self):
        win=tk.Toplevel(self.root); win.title('Admin Approvals'); win.geometry('800x450'); f=ttk.Frame(win,padding=10); f.pack(fill='both',expand=True); tree=ttk.Treeview(f,columns=('ID','Username','Email','Status','Requested'),show='headings');
        for c in ('ID','Username','Email','Status','Requested'): tree.heading(c,text=c); tree.column(c,width=150)
        tree.pack(fill='both',expand=True); conn=connect(); rows=conn.execute('SELECT rr.id,u.username,rr.email,rr.status,rr.requested_at FROM reset_requests rr JOIN users u ON u.id=rr.user_id ORDER BY rr.id DESC').fetchall(); conn.close();
        for r in rows: tree.insert('', 'end', values=tuple(r))
        def action(approve):
            s=tree.selection()
            if not s:return
            rid=tree.item(s[0])['values'][0]; pw=None
            if approve:
                import tkinter.simpledialog as sd; pw=sd.askstring('Temporary Password','Enter a temporary password:',show='*')
                if not pw:return
            ok,msg=self.auth.admin_reset_action(rid,self.user['id'],approve,pw); (messagebox.showinfo if ok else messagebox.showerror)('Admin Approval',msg); win.destroy(); self.approvals()
        b=ttk.Frame(f); b.pack(fill='x',pady=8); ttk.Button(b,text='Approve Reset / Unlock',command=lambda:action(True)).pack(side='left',padx=5); ttk.Button(b,text='Reject',command=lambda:action(False)).pack(side='left',padx=5)
    def logout(self): logging.info(f'Logout: {self.user["username"]}'); self.root.destroy(); LoginView(start_app)
    def run(self): self.root.mainloop()

def start_app(user): App(user).run()

if __name__=='__main__': LoginView(start_app).mainloop()
