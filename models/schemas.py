from pydantic import BaseModel, field_validator
import re

PASSWORD_RE = re.compile(r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[@#$%^&*]).{8,}$')
EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

class RegisterSchema(BaseModel):
    username: str
    email: str
    password: str
    role: str

    @field_validator('username')
    @classmethod
    def username_valid(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Username must be at least 3 characters.')
        return v.strip()

    @field_validator('email')
    @classmethod
    def email_valid(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.fullmatch(v):
            raise ValueError('Enter a valid email address.')
        return v

    @field_validator('password')
    @classmethod
    def password_valid(cls, v):
        if not PASSWORD_RE.fullmatch(v):
            raise ValueError('Password needs 8+ characters, uppercase, number, and one of @#$%^&*.')
        return v

    @field_validator('role')
    @classmethod
    def role_valid(cls, v):
        v = v.upper()
        if v not in ('USER', 'ADMIN'):
            raise ValueError('Role must be USER or ADMIN.')
        return v

class HardwareSchema(BaseModel):
    item_name: str
    category: str
    quantity: int
    unit_price: float

    @field_validator('item_name', 'category')
    @classmethod
    def text_required(cls, v):
        if not v.strip():
            raise ValueError('This field is required.')
        return v.strip()

    @field_validator('quantity')
    @classmethod
    def qty_valid(cls, v):
        if v < 0:
            raise ValueError('Quantity cannot be negative.')
        return v

    @field_validator('unit_price')
    @classmethod
    def price_valid(cls, v):
        if v < 0:
            raise ValueError('Unit price cannot be negative.')
        return v
