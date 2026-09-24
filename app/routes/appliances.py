from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Appliance, TariffBand
from app.utils.calculator import appliance_monthly_cost
from app.utils.tariff import get_tariff_rate

appliances_bp = Blueprint('appliances', __name__)

@appliances_bp.route('/')
@login_required
def list_appliances():
    appliances = Appliance.query.filter_by(user_id=current_user.id).all()
    tariff = TariffBand.query.get(current_user.tariff_band_id)
    rate = get_tariff_rate(tariff)
    
    appliance_data = []
    total_cost = 0
    for app in appliances:
        cost = appliance_monthly_cost(app.wattage, app.avg_daily_hours, rate)
        total_cost += cost
        appliance_data.append({
            'id': app.id,
            'name': app.name,
            'wattage': app.wattage,
            'avg_daily_hours': app.avg_daily_hours,
            'category': app.category,
            'is_active': app.is_active,
            'monthly_cost': cost,
            'monthly_kwh': round((app.wattage / 1000) * app.avg_daily_hours * 30, 2)
        })
    
    return render_template('appliances/list.html', 
                         appliances=appliance_data, 
                         total_cost=round(total_cost, 2),
                         rate=rate)

@appliances_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_appliance():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        wattage = request.form.get('wattage', type=float)
        hours = request.form.get('avg_daily_hours', type=float)
        category = request.form.get('category', 'other')
        
        if not name or wattage is None or hours is None:
            flash('Name, wattage, and daily hours are required.', 'danger')
            return redirect(url_for('appliances.add_appliance'))
        
        if wattage <= 0 or wattage > 20000:
            flash('Wattage must be between 1W and 20,000W.', 'danger')
            return redirect(url_for('appliances.add_appliance'))
        if hours <= 0 or hours > 24:
            flash('Average daily hours must be between 0 and 24.', 'danger')
            return redirect(url_for('appliances.add_appliance'))
        
        appliance = Appliance(
            user_id=current_user.id,
            name=name,
            wattage=wattage,
            avg_daily_hours=hours,
            category=category
        )
        db.session.add(appliance)
        db.session.commit()
        flash(f'{name} added successfully! <a href="{url_for("optimizer.tips")}">Visit the Optimizer</a> to see your savings tips.', 'success')
        return redirect(url_for('appliances.list_appliances'))
    
    return render_template('appliances/add.html')

@appliances_bp.route('/edit/<int:appliance_id>', methods=['GET', 'POST'])
@login_required
def edit_appliance(appliance_id):
    appliance = Appliance.query.get_or_404(appliance_id)
    if appliance.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('appliances.list_appliances'))
    
    if request.method == 'POST':
        wattage = request.form.get('wattage', type=float)
        hours = request.form.get('avg_daily_hours', type=float)
        name = request.form.get('name', '').strip()
        
        if not name or wattage is None or hours is None:
            flash('Name, wattage, and daily hours are required.', 'danger')
            return redirect(url_for('appliances.edit_appliance', appliance_id=appliance_id))
        if wattage <= 0 or wattage > 20000:
            flash('Wattage must be between 1W and 20,000W.', 'danger')
            return redirect(url_for('appliances.edit_appliance', appliance_id=appliance_id))
        if hours <= 0 or hours > 24:
            flash('Average daily hours must be between 0 and 24.', 'danger')
            return redirect(url_for('appliances.edit_appliance', appliance_id=appliance_id))
        
        appliance.name = name
        appliance.wattage = wattage
        appliance.avg_daily_hours = hours
        appliance.category = request.form.get('category', 'other')
        appliance.is_active = bool(request.form.get('is_active'))
        
        db.session.commit()
        flash('Appliance updated.', 'success')
        return redirect(url_for('appliances.list_appliances'))
    
    return render_template('appliances/edit.html', appliance=appliance)

@appliances_bp.route('/delete/<int:appliance_id>', methods=['POST'])
@login_required
def delete_appliance(appliance_id):
    appliance = Appliance.query.get_or_404(appliance_id)
    if appliance.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('appliances.list_appliances'))
    
    db.session.delete(appliance)
    db.session.commit()
    flash(f'{appliance.name} deleted.', 'info')
    return redirect(url_for('appliances.list_appliances'))