import bcrypt
import logging
from pydantic import ValidationError
from models.database import connect
from models.schemas import RegisterSchema

class AuthController:
    def register(self, username, email, password, role):
        try:
            data = RegisterSchema(username=username, email=email, password=password, role=role)
        except ValidationError as e:
            logging.warning(f'Registration validation failed for {username}: {e}')
            return False, str(e).split('\n')[-1].replace('Value error, ', '')
        conn = connect()
        try:
            if conn.execute('SELECT 1 FROM users WHERE username=?', (data.username,)).fetchone():
                return False, 'Username already exists.'
            if conn.execute('SELECT 1 FROM users WHERE email=?', (data.email,)).fetchone():
                return False, 'Email address already registered.'
            hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
            conn.execute('INSERT INTO users(username,email,password_hash,role) VALUES(?,?,?,?)',
                         (data.username, data.email, hashed, data.role))
            conn.commit()
            logging.info(f'Registration successful: {data.username} role={data.role}')
            return True, 'Account created successfully.'
        finally:
            conn.close()

    def login(self, username, password):
        conn = connect()
        try:
            user = conn.execute('SELECT * FROM users WHERE username=?', (username.strip(),)).fetchone()
            if not user:
                logging.warning(f'Login failed: unknown username={username}')
                return False, 'Invalid username or password.', None
            if user['is_locked']:
                logging.warning(f'Login blocked: locked account={username}')
                return False, 'Account is locked. Use Reset / Unlock Password.', user
            if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
                attempts = user['failed_attempts'] + 1
                if attempts >= 3:
                    conn.execute('UPDATE users SET failed_attempts=3,is_locked=1 WHERE id=?', (user['id'],))
                    conn.commit()
                    logging.warning(f'ACCOUNT LOCKED after 3 failed attempts: {username}')
                    return False, 'Account locked after 3 unsuccessful attempts. Use Reset / Unlock Password.', user
                conn.execute('UPDATE users SET failed_attempts=? WHERE id=?', (attempts, user['id']))
                conn.commit()
                logging.warning(f'Login failed {attempts}/3: {username}')
                return False, f'Invalid username or password. {3-attempts} attempt(s) remaining.', user
            conn.execute('UPDATE users SET failed_attempts=0 WHERE id=?', (user['id'],))
            conn.commit()
            logging.info(f'Login successful: {username} role={user["role"]}')
            return True, 'Login successful.', user
        finally:
            conn.close()

    def request_reset(self, email):
        conn = connect()
        try:
            user = conn.execute('SELECT * FROM users WHERE email=?', (email.strip().lower(),)).fetchone()
            if not user:
                return False, 'No account is registered with that email.'
            pending = conn.execute("SELECT 1 FROM reset_requests WHERE user_id=? AND status='PENDING'", (user['id'],)).fetchone()
            if pending:
                return False, 'A reset request is already pending.'
            conn.execute('INSERT INTO reset_requests(user_id,email) VALUES(?,?)', (user['id'], user['email']))
            conn.commit()
            logging.info(f'Password reset request submitted: {user["username"]}')
            return True, 'Reset request submitted for ADMIN approval.'
        finally:
            conn.close()

    def change_password(self, user_id, current_password, new_password):
        conn = connect()
        try:
            user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            if not bcrypt.checkpw(current_password.encode(), user['password_hash'].encode()):
                return False, 'Current password is incorrect.'
            try:
                RegisterSchema(username=user['username'], email=user['email'], password=new_password, role=user['role'])
            except ValidationError:
                return False, 'New password does not meet the password requirements.'
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            conn.execute('UPDATE users SET password_hash=? WHERE id=?', (hashed, user_id))
            conn.commit()
            logging.info(f'Password changed directly by user: {user["username"]}')
            return True, 'Password changed successfully.'
        finally:
            conn.close()

    def admin_reset_action(self, request_id, admin_id, approve, new_password=None):
        conn = connect()
        try:
            req = conn.execute('SELECT * FROM reset_requests WHERE id=?', (request_id,)).fetchone()
            if not req or req['status'] != 'PENDING':
                return False, 'Request is not pending.'
            status = 'APPROVED' if approve else 'REJECTED'
            if approve:
                if not new_password:
                    return False, 'Provide a temporary new password.'
                try:
                    user = conn.execute('SELECT * FROM users WHERE id=?', (req['user_id'],)).fetchone()
                    RegisterSchema(username=user['username'], email=user['email'], password=new_password, role=user['role'])
                except ValidationError:
                    return False, 'Temporary password does not meet requirements.'
                hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                conn.execute('UPDATE users SET password_hash=?, is_locked=0, failed_attempts=0 WHERE id=?', (hashed, req['user_id']))
            conn.execute('UPDATE reset_requests SET status=?, reviewed_at=CURRENT_TIMESTAMP, reviewed_by=? WHERE id=?', (status, admin_id, request_id))
            conn.commit()
            logging.info(f'ADMIN reset request {request_id}: {status}')
            return True, f'Request {status.lower()}.'
        finally:
            conn.close()
