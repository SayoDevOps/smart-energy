import calendar
from datetime import date
from statistics import mean, pstdev

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required

from app import db
from app.models import Appliance, Budget, ConsumptionLog
from app.utils.calculator import appliance_monthly_cost
from app.utils.seasonal import get_seasonal_context
from app.utils.predictor import detect_anomaly, predict_monthly_bill
from app.utils.tariff import get_tariff_rate

dashboard_bp = Blueprint('dashboard', __name__)


def _build_alerts(monthly_logs):
    if len(monthly_logs) < 3:
        return []

    kwh_values = [log.kwh_consumed for log in monthly_logs]
    std_dev = pstdev(kwh_values)
    if std_dev == 0:
        return []

    average_kwh = mean(kwh_values)
    alerts = []

    for log in sorted(monthly_logs, key=lambda item: item.log_date, reverse=True):
        deviation = log.kwh_consumed - average_kwh
        if abs(deviation) <= 2 * std_dev:
            continue

        if deviation > 0:
            severity = 'warning'
            message = (
                f"Usage spiked on {log.log_date.strftime('%d %b')}: "
                f"{log.kwh_consumed:.2f} kWh vs {average_kwh:.2f} kWh average."
            )
        else:
            severity = 'info'
            message = (
                f"Usage dipped on {log.log_date.strftime('%d %b')}: "
                f"{log.kwh_consumed:.2f} kWh vs {average_kwh:.2f} kWh average."
            )

        alerts.append({
            'severity': severity,
            'message': message,
        })

        if len(alerts) == 3:
            break

    return alerts


def _build_budget_status(user_id, amount):
    if amount is None or amount <= 0:
        return None

    budget = (
        Budget.query.filter_by(user_id=user_id)
        .order_by(Budget.id.desc())
        .first()
    )
    if not budget or budget.monthly_limit <= 0:
        return None

    raw_percentage = round((amount / budget.monthly_limit) * 100, 1)
    if raw_percentage >= 100:
        color = 'danger'
    elif raw_percentage >= 80:
        color = 'warning'
    else:
        color = 'success'

    return {
        'predicted': round(amount, 2),
        'limit': round(budget.monthly_limit, 2),
        'percentage': raw_percentage,
        'progress_width': min(raw_percentage, 100),
        'overage': round(max(amount - budget.monthly_limit, 0), 2),
        'color': color,
    }


def _prediction_confidence(days_logged):
    if days_logged >= 21:
        return 'high'
    if days_logged >= 14:
        return 'medium'
    if days_logged >= 7:
        return 'low'
    return 'building'


@dashboard_bp.route('/')
@login_required
def index():
    uid = current_user.id
    today = date.today()
    first_of_month = date(today.year, today.month, 1)
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    active_appliances = Appliance.query.filter_by(
        user_id=uid,
        is_active=True,
    ).all()
    appliance_count = len(active_appliances)

    monthly_logs = (
        ConsumptionLog.query.filter(
            ConsumptionLog.user_id == uid,
            ConsumptionLog.log_date >= first_of_month,
            ConsumptionLog.log_date <= today,
        )
        .order_by(ConsumptionLog.log_date.desc())
        .all()
    )

    grid_monthly_logs = [log for log in monthly_logs if log.source == 'grid']
    kwh_this_month = round(sum(log.kwh_consumed for log in monthly_logs), 2)
    grid_kwh_this_month = round(sum(log.kwh_consumed for log in grid_monthly_logs), 2)
    days_logged = len({log.log_date for log in grid_monthly_logs})

    # True energy spend: grid cost + generator fuel cost
    from sqlalchemy import func
    gen_cost_this_month = db.session.query(
        func.sum(ConsumptionLog.fuel_cost)
    ).filter(
        ConsumptionLog.user_id == uid,
        ConsumptionLog.log_date >= first_of_month,
        ConsumptionLog.log_date <= today,
        ConsumptionLog.source == 'generator'
    ).scalar() or 0

    tariff_rate = get_tariff_rate(current_user.tariff_band)

    grid_cost_this_month = round(grid_kwh_this_month * tariff_rate, 2)
    prediction_result = predict_monthly_bill(
        user_id=uid,
        tariff_rate=tariff_rate,
        db=db,
        ConsumptionLog=ConsumptionLog,
    )
    predicted_bill = prediction_result['predicted_bill']
    true_total = round(grid_cost_this_month + float(gen_cost_this_month), 2)
    # Budget progress bar
    monthly_budget = current_user.monthly_budget
    budget_status_new = None
    if monthly_budget and monthly_budget > 0:
        budget_pct = 0
        overage = 0
        used = 0
        if predicted_bill:
            budget_pct = min((predicted_bill / monthly_budget) * 100, 100)
            overage = max(predicted_bill - monthly_budget, 0)
            used = predicted_bill
        if budget_pct < 70:
            budget_color = 'green'
        elif budget_pct < 90:
            budget_color = 'amber'
        else:
            budget_color = 'red'
        budget_status_new = {
            'pct': round(budget_pct, 1),
            'color': budget_color,
            'overage': round(overage, 2),
            'limit': monthly_budget,
            'used': used if used > 0 else None
        }

    alerts = _build_alerts(grid_monthly_logs)

    # Anomaly detection (spike or rising trend)
    anomaly = detect_anomaly(
        user_id=uid,
        db=db,
        ConsumptionLog=ConsumptionLog
    )

    recent_logs = []
    for log in monthly_logs[:5]:
        source_label = (log.source or 'grid').replace('_', ' ').title()
        log_cost = (
            log.fuel_cost
            if log.fuel_cost is not None
            else log.kwh_consumed * tariff_rate
            if log.source == 'Grid'
            else None
        )
        recent_logs.append({
            'date': log.log_date,
            'kwh': round(log.kwh_consumed, 2),
            'source': source_label,
            'cost': round(log_cost, 2) if log_cost is not None else None,
        })

    top_appliances = []
    for appliance in active_appliances:
        monthly_cost = appliance_monthly_cost(
            appliance.wattage,
            appliance.avg_daily_hours,
            tariff_rate,
        )
        top_appliances.append({
            'name': appliance.name,
            'monthly_cost': monthly_cost,
        })

    top_appliances.sort(key=lambda appliance: appliance['monthly_cost'], reverse=True)
    top_appliances = top_appliances[:3]
    top_appliance = top_appliances[0] if top_appliances else None

    budget_base_amount = predicted_bill
    if budget_base_amount is None and grid_kwh_this_month > 0:
        budget_base_amount = grid_cost_this_month
    budget_status = _build_budget_status(uid, budget_base_amount)

    seasonal = get_seasonal_context()
    is_new_user = appliance_count == 0 and days_logged == 0

    name_parts = (current_user.full_name or '').split()
    first_name = name_parts[0] if name_parts else 'there'

    prediction = {
        'value': predicted_bill,
        'days_logged': prediction_result['days_logged'],
        'days_in_month': days_in_month,
        'confidence': prediction_result['confidence'],
    }

    return render_template(
        'dashboard/index.html',
        first_name=first_name,
        appliance_count=appliance_count,
        kwh_this_month=kwh_this_month,
        days_logged=days_logged,
        predicted_bill=predicted_bill,
        prediction=prediction,
        top_appliance=top_appliance,
        top_appliances=top_appliances,
        seasonal=seasonal,
        is_new_user=is_new_user,
        alerts=alerts,
        recent_logs=recent_logs,
        budget_status=budget_status,
        budget_status_new=budget_status_new,
        gen_cost_this_month=gen_cost_this_month,
        grid_cost_this_month=grid_cost_this_month,
        true_total=true_total,
        anomaly=anomaly,
    )


@dashboard_bp.route('/set-budget', methods=['POST'])
@login_required
def set_budget():
    try:
        budget = float(request.form['budget'])
        current_user.monthly_budget = budget
        db.session.commit()
        flash('Budget updated!', 'success')
    except Exception:
        flash('Invalid budget amount.', 'danger')
    return redirect(url_for('dashboard.index'))

