from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Delay import to avoid circular dependency
from app import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    household_type = db.Column(db.String(30))
    tariff_band_id = db.Column(db.Integer, db.ForeignKey('tariff_bands.id'))
    tariff_band = db.relationship('TariffBand', backref='users', lazy=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appliances = db.relationship('Appliance', backref='user', lazy=True)
    consumption_logs = db.relationship('ConsumptionLog', backref='user', lazy=True)
    bills = db.relationship('Bill', backref='user', lazy=True)
    tips = db.relationship('OptimizationTip', backref='user', lazy=True)
    monthly_budget = db.Column(db.Float, nullable=True, default=None)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class TariffBand(db.Model):
    __tablename__ = 'tariff_bands'
    id = db.Column(db.Integer, primary_key=True)
    band = db.Column(db.String(1), unique=True, nullable=False)
    rate_per_kwh = db.Column(db.Float, nullable=False)
    service_hours = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

class Appliance(db.Model):
    __tablename__ = 'appliances'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    wattage = db.Column(db.Float, nullable=False)
    avg_daily_hours = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ConsumptionLog(db.Model):
    __tablename__ = 'consumption_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    log_date = db.Column(db.Date, nullable=False)
    kwh_consumed = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(20), nullable=False)
    fuel_cost = db.Column(db.Float, nullable=True)
    generator_hours = db.Column(db.Float, nullable=True)
    appliance_id = db.Column(db.Integer, db.ForeignKey('appliances.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appliance = db.relationship('Appliance', backref='logs')
    
    __table_args__ = (db.UniqueConstraint('user_id', 'log_date', 'source'),)

class Bill(db.Model):
    __tablename__ = 'bills'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    tariff_band_id = db.Column(db.Integer, db.ForeignKey('tariff_bands.id'))
    total_kwh = db.Column(db.Float, nullable=True)
    predicted_amount = db.Column(db.Float, nullable=True)
    actual_amount = db.Column(db.Float, nullable=True)
    is_settled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'month', 'year'),)

class OptimizationTip(db.Model):
    __tablename__ = 'optimization_tips'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    appliance_id = db.Column(db.Integer, db.ForeignKey('appliances.id'), nullable=True)
    tip_text = db.Column(db.Text, nullable=False)
    potential_saving = db.Column(db.Float, nullable=False)
    action_type = db.Column(db.String(20), nullable=False)
    is_applied = db.Column(db.Boolean, default=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    appliance = db.relationship('Appliance', backref='tips')

class Budget(db.Model):
    __tablename__ = 'budgets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False, default=20000.00)
    user = db.relationship('User', backref='budget', uselist=False)