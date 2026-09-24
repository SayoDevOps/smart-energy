from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from sqlalchemy import func
from app import db
from app.models import ConsumptionLog, Appliance, User
from app.utils.calculator import (
    calculate_log_cost, predict_monthly_bill, detect_anomalies,
    get_daily_kwh_summary, format_naira, get_appliance_cost_breakdown,
    get_budget_status
)
from app.utils.tariff import get_tariff_rate

# Blueprint Registration
consumption_bp = Blueprint('consumption', __name__, url_prefix='/consumption')


@consumption_bp.route('/log', methods=['GET', 'POST'])
@login_required
def log_consumption():
    appliances = Appliance.query.filter_by(user_id=current_user.id).all()
    # Calculate average daily kWh for this user (all time)
    avg_result = db.session.query(
        func.avg(ConsumptionLog.kwh_consumed)
    ).filter(
        ConsumptionLog.user_id == current_user.id
    ).scalar()
    avg_daily_kwh = round(avg_result, 2) if avg_result else 0
    # POST HANDLER — Process the submitted form
    if request.method == 'POST':
        # Extract form fields
        kwh_consumed = request.form.get('kwh_consumed', type=float)
        source = request.form.get('source', 'grid')
        log_date_str = request.form.get('log_date')
        appliance_id = request.form.get('appliance_id') or None
        notes = request.form.get('notes', '').strip()
        
        if kwh_consumed is None or kwh_consumed <= 0 or kwh_consumed > 500:
            flash('Energy used must be between 0 and 500 kWh.', 'danger')
            return redirect(url_for('consumption.log_consumption'))
        if source not in ('grid', 'generator'):
            flash('Select a valid energy source.', 'danger')
            return redirect(url_for('consumption.log_consumption'))

        # Parse and validate date
        try:
            log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            flash('Enter a valid log date.', 'danger')
            return redirect(url_for('consumption.log_consumption'))
        
        if log_date > date.today():
            flash('Cannot log future dates.', 'danger')
            return redirect(url_for('consumption.log_consumption'))
        # Handle optional appliance linkage
        if appliance_id:
            appliance_id = int(appliance_id)
            appliance = Appliance.query.filter_by(
                id=appliance_id,
                user_id=current_user.id,
            ).first()
            if not appliance:
                flash('Select one of your own appliances.', 'danger')
                return redirect(url_for('consumption.log_consumption'))
        
        # Build the ConsumptionLog ORM object
        log = ConsumptionLog(
            user_id=current_user.id,
            log_date=log_date,
            kwh_consumed=kwh_consumed,
            source=source,
            notes=notes if notes else None,
            appliance_id=appliance_id
        )
        
        # Handle generator-specific fields from the form
        if source == 'generator':
            gen_hours = request.form.get('generator_hours', type=float)
            fuel = request.form.get('fuel_cost', type=float)
            if gen_hours is None or gen_hours <= 0 or gen_hours > 24:
                flash('Generator hours must be between 0 and 24.', 'danger')
                return redirect(url_for('consumption.log_consumption'))
            if fuel is None or fuel < 0:
                flash('Fuel cost must be zero or greater.', 'danger')
                return redirect(url_for('consumption.log_consumption'))
            log.generator_hours = gen_hours
            log.fuel_cost = fuel
        
        try:
            db.session.add(log)
            db.session.commit()
            
            # Calculate cost for flash message only
            tariff_rate = get_tariff_rate(current_user.tariff_band)
            display_cost = calculate_log_cost(kwh_consumed, tariff_rate)
            
            flash(f'Logged {kwh_consumed} kWh ({format_naira(display_cost)}) for {log_date.strftime("%d %b, %Y")}.', 'success')
            return redirect(url_for('consumption.history'))
            
        except Exception:
            db.session.rollback()
            flash('Error saving log. You may have already logged this source for today.', 'danger')
            return redirect(url_for('consumption.log_consumption'))
    
    return render_template('consumption/log.html', 
                         appliances=appliances, 
                         today=date.today().isoformat(),
                         avg_daily_kwh=avg_daily_kwh,
                         tariff_rate=get_tariff_rate(current_user.tariff_band))

#Consumption History
@consumption_bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    logs = ConsumptionLog.query.filter_by(user_id=current_user.id)\
        .order_by(ConsumptionLog.log_date.desc()).paginate(
            page=page, per_page=15, error_out=False
        )
    
    # Summary stats using correct field names from your model
    total_kwh_result = db.session.query(func.sum(ConsumptionLog.kwh_consumed))\
        .filter_by(user_id=current_user.id).scalar()
    total_kwh = round(float(total_kwh_result), 2) if total_kwh_result else 0
    
    grid_kwh_result = db.session.query(func.sum(ConsumptionLog.kwh_consumed)).filter(
        ConsumptionLog.user_id == current_user.id,
        ConsumptionLog.source == 'grid',
    ).scalar()
    generator_fuel_result = db.session.query(func.sum(ConsumptionLog.fuel_cost)).filter(
        ConsumptionLog.user_id == current_user.id,
        ConsumptionLog.source == 'generator',
    ).scalar()

    # Calculate true cost on the fly (logs do not store grid cost)
    tariff_rate = get_tariff_rate(current_user.tariff_band)
    total_cost = round(
        (float(grid_kwh_result or 0) * tariff_rate) + float(generator_fuel_result or 0),
        2,
    )
    
    return render_template('consumption/history.html',
                         logs=logs,
                         total_kwh=total_kwh,
                         total_cost=total_cost,
                         tariff_rate=tariff_rate)


@consumption_bp.route('/log/<int:log_id>/delete', methods=['POST'])
@login_required
def delete_log(log_id):
    log = ConsumptionLog.query.get_or_404(log_id)
    if log.user_id != current_user.id:
        flash('Unauthorized.', 'danger')
        return redirect(url_for('consumption.history'))
    
    db.session.delete(log)
    db.session.commit()
    flash('Log entry deleted.', 'info')
    return redirect(url_for('consumption.history'))


# IoT Sensor API (JSON Endpoint)
@consumption_bp.route('/api/log', methods=['POST'])
def api_log():
    """
    Accepts JSON from IoT sensors.
    {
        "user_id": 1,
        "kwh_consumed": 4.2,
        "source": "grid",
        "date": "2026-04-15"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'status': 'error', 'message': 'No JSON received'}), 400
    
    user_id = data.get('user_id')
    kwh_consumed = data.get('kwh_consumed')
    source = data.get('source', 'grid')
    log_date_str = data.get('date')
    
    if not all([user_id, kwh_consumed, log_date_str]):
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400
    
    try:
        log_date = datetime.strptime(log_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    
    try:
        kwh_consumed = float(kwh_consumed)
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid kWh value'}), 400
    if kwh_consumed <= 0 or kwh_consumed > 500:
        return jsonify({'status': 'error', 'message': 'kWh must be between 0 and 500'}), 400
    if source not in ('grid', 'generator') or log_date > date.today():
        return jsonify({'status': 'error', 'message': 'Invalid source or future date'}), 400

    tariff_rate = get_tariff_rate(user.tariff_band)
    cost = calculate_log_cost(kwh_consumed, tariff_rate)
    
    log = ConsumptionLog(
        user_id=user_id,
        kwh_consumed=kwh_consumed,
        source=source,
        log_date=log_date
    )
    
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'status': 'ok',
        'message': 'Consumption log saved',
        'log_id': log.id,
        'cost': cost
    }), 201