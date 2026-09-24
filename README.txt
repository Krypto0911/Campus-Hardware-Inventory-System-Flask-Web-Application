LAB 4 - Secure Campus Hardware Inventory System

Features:
1. User registration with username, email, password and role.
2. Password validation and bcrypt hashing.
3. Three failed login attempts permanently lock the account until an approved reset request unlocks it.
4. Reset / Unlock request using registered email; ADMIN approves/rejects it and supplies a temporary password.
5. ADMIN Hardware Catalog: add, update, delete, search/filter and CSV export.
6. Automatic inventory status: >5 In Stock, 1-5 Low Stock, 0 Out of Stock.
7. USER My Profile & Security with direct password change.
8. Audit logging in app_logging/app.log.

Run:
python -m pip install -r requirements.txt
python main.py

For a quick demo, register one ADMIN and one USER account. Password format example: Password1@
