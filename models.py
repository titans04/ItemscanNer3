from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum
import enum

db = SQLAlchemy()

class User(db.Model):
    """
    Represents a user in the system. For this specific requirement,
    we'll focus on the admin role.
    """
    __tablename__ = 'user'
    user_id = db.Column(db.String, primary_key=True)
    full_name = db.Column(db.String, nullable=False)
    email = db.Column(db.String)
    role = db.Column(db.String, default='admin')  # Default to admin
    
    def __repr__(self):
        return f'<User(user_id={self.user_id}, full_name={self.full_name}, role={self.role})>'


class ItemStatus(enum.Enum):
    """
    Enumerates the possible statuses of an item.
    """
    WORKING = 'WORKING'
    Working = 'Working'
    DAMAGED = 'DAMAGED'
    NOT_WORKING = 'NOT_WORKING'
    NOT_SETUP = 'NOT_SETUP'


class Item(db.Model):
    """
    Represents an item in the inventory. Only admins manage items.
    """
    __tablename__ = 'item'
    item_id = db.Column(db.String, primary_key=True)
    item_name = db.Column(db.String, nullable=False)
    location = db.Column(db.String, nullable=False)
    status = db.Column(Enum(ItemStatus), default=ItemStatus.WORKING, nullable=False)
    brand = db.Column(db.String)
    color = db.Column(db.String)
    
    def __repr__(self):
        return f'<Item(item_id={self.item_id}, item_name={self.item_name}, status={self.status})>'