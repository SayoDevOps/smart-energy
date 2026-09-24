from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from app import db
from app.models import User, TariffBand

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return render_template('auth/landing.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # If already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        household_type = request.form.get('household_type', 'residential')
        tariff_band_id = request.form.get('tariff_band_id', type=int)

        if not all([full_name, email, password, tariff_band_id]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.register'))

        # Check if email is already registered
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # Check if full name is already registered (case-insensitive)
        name_exists = User.query.filter(
            db.func.lower(User.full_name) == full_name.lower()
        ).first()
        if name_exists:
            flash('That name is already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # Store full_name with title case
        full_name = full_name.title()

        user = User(
            full_name=full_name,
            email=email,
            household_type=household_type,
            tariff_band_id=tariff_band_id
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Log in with your full name.', 'success')
        return redirect(url_for('auth.login'))

    bands = TariffBand.query.filter_by(is_active=True).all()
    return render_template('auth/register.html', bands=bands)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')

        if not full_name or not password:
            flash('Name and password are required.', 'danger')
            return redirect(url_for('auth.login'))

        # Look up user case-insensitively
        user = User.query.filter(
            db.func.lower(User.full_name) == full_name.lower()
        ).first()

        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            parsed_next = urlparse(next_page) if next_page else None
            if parsed_next and not parsed_next.netloc and parsed_next.path.startswith('/') and not parsed_next.path.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))

        flash('Invalid credentials. Please check your name and password.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))