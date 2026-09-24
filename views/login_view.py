import tkinter as tk
from tkinter import ttk, messagebox
from controllers.auth_controller import AuthController

class LoginView(tk.Tk):
    def __init__(self, on_success):
        super().__init__()
        self.title('Lab 4 - Secure Campus Hardware Inventory')
        self.geometry('520x520')
        self.resizable(False, False)
        self.controller = AuthController()
        self.on_success = on_success
        self.show_login()

    def clear(self):
        for w in self.winfo_children(): w.destroy()

    def show_login(self):
        self.clear()
        frm = ttk.Frame(self, padding=30); frm.pack(fill='both', expand=True)
        ttk.Label(frm, text='SECURE LOGIN', font=('Arial', 20, 'bold')).pack(pady=10)
        self.login_user = tk.StringVar(); self.login_pass = tk.StringVar(); self.show_login_pass = tk.BooleanVar()
        ttk.Label(frm, text='Username').pack(anchor='w'); ttk.Entry(frm, textvariable=self.login_user).pack(fill='x', pady=5)
        ttk.Label(frm, text='Password').pack(anchor='w'); e=ttk.Entry(frm, textvariable=self.login_pass, show='*'); e.pack(fill='x', pady=5); self.login_pass_entry=e
        ttk.Checkbutton(frm, text='Show Password', variable=self.show_login_pass, command=lambda:self.toggle(self.login_pass_entry,self.show_login_pass)).pack(anchor='w')
        ttk.Button(frm, text='LOGIN', command=self.login).pack(fill='x', pady=12)
        ttk.Button(frm, text='REGISTER', command=self.show_register).pack(fill='x', pady=3)
        ttk.Button(frm, text='Reset / Unlock Password', command=self.show_reset).pack(fill='x', pady=3)

    def toggle(self, entry, var): entry.config(show='' if var.get() else '*')

    def login(self):
        ok,msg,user=self.controller.login(self.login_user.get(), self.login_pass.get())
        if ok:
            self.on_success(dict(user)); self.destroy()
        else: messagebox.showwarning('Login', msg)

    def show_register(self):
        self.clear(); frm=ttk.Frame(self,padding=30); frm.pack(fill='both',expand=True)
        ttk.Label(frm,text='CREATE ACCOUNT',font=('Arial',20,'bold')).pack(pady=10)
        self.reg_user=tk.StringVar(); self.reg_email=tk.StringVar(); self.reg_pass=tk.StringVar(); self.reg_role=tk.StringVar(value='USER'); self.show_reg_pass=tk.BooleanVar()
        for label,var in [('Username',self.reg_user),('Email Address',self.reg_email)]:
            ttk.Label(frm,text=label).pack(anchor='w'); ttk.Entry(frm,textvariable=var).pack(fill='x',pady=5)
        ttk.Label(frm,text='Password').pack(anchor='w'); e=ttk.Entry(frm,textvariable=self.reg_pass,show='*'); e.pack(fill='x',pady=5); self.reg_pass_entry=e
        ttk.Checkbutton(frm,text='Show Password',variable=self.show_reg_pass,command=lambda:self.toggle(self.reg_pass_entry,self.show_reg_pass)).pack(anchor='w')
        ttk.Label(frm,text='User Role').pack(anchor='w',pady=(10,0)); ttk.Combobox(frm,textvariable=self.reg_role,values=['USER','ADMIN'],state='readonly').pack(fill='x',pady=5)
        ttk.Button(frm,text='CREATE ACCOUNT',command=self.register).pack(fill='x',pady=12); ttk.Button(frm,text='Back to Login',command=self.show_login).pack(fill='x')

    def register(self):
        ok,msg=self.controller.register(self.reg_user.get(),self.reg_email.get(),self.reg_pass.get(),self.reg_role.get())
        if ok: messagebox.showinfo('Registration',msg); self.show_login()
        else: messagebox.showerror('Registration',msg)

    def show_reset(self):
        self.clear(); frm=ttk.Frame(self,padding=30); frm.pack(fill='both',expand=True)
        ttk.Label(frm,text='RESET / UNLOCK PASSWORD',font=('Arial',18,'bold')).pack(pady=15)
        email=tk.StringVar(); ttk.Label(frm,text='Registered Email').pack(anchor='w'); ttk.Entry(frm,textvariable=email).pack(fill='x',pady=8)
        ttk.Button(frm,text='SUBMIT RESET REQUEST',command=lambda:self.reset(email.get())).pack(fill='x',pady=12); ttk.Button(frm,text='Back to Login',command=self.show_login).pack(fill='x')
    def reset(self,email):
        ok,msg=self.controller.request_reset(email); (messagebox.showinfo if ok else messagebox.showerror)('Reset Request',msg)
