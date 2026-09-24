from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import ConsumptionLog, Bill
from app.utils.predictor import (
    predict_monthly_bill,
    get_bill_history,
    detect_anomaly
)
from app.utils.tariff import get_tariff_rate
from datetime import date

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/predict')
@login_required
def predict():
    """Show this month's bill forecast."""
    tariff_rate = get_tariff_rate(current_user.tariff_band)

    prediction = predict_monthly_bill(
        user_id=current_user.id,
        tariff_rate=tariff_rate,
        db=db,
        ConsumptionLog=ConsumptionLog
    )

    # Auto-save prediction to Bills table
    if not prediction['error']:
        today = date.today()
        existing = Bill.query.filter_by(
            user_id=current_user.id,
            month=today.month,
            year=today.year
        ).first()

        if existing:
            existing.predicted_amount = prediction['predicted_bill']
            existing.total_kwh = prediction['projected_kwh']
            existing.tariff_band_id = current_user.tariff_band_id
        else:
            new_bill = Bill(
                user_id=current_user.id,
                month=today.month,
                year=today.year,
                predicted_amount=prediction['predicted_bill'],
                total_kwh=prediction['projected_kwh'],
                tariff_band_id=current_user.tariff_band_id
            )
            db.session.add(new_bill)

        db.session.commit()

    bill_history = get_bill_history(
        user_id=current_user.id,
        db=db,
        Bill=Bill
    )

    anomaly = detect_anomaly(
        user_id=current_user.id,
        db=db,
        ConsumptionLog=ConsumptionLog
    )

    month_name = date.today().strftime('%B %Y')

    return render_template(
        'billing/predict.html',
        prediction=prediction,
        bill_history=bill_history,
        anomaly=anomaly,
        month_name=month_name,
        tariff_rate=tariff_rate,
        date=date
    )


@billing_bp.route('/save-actual', methods=['POST'])
@login_required
def save_actual_bill():
    """User enters actual NERC bill for accuracy tracking."""
    month = int(request.form['month'])
    year = int(request.form['year'])
    actual_amount = float(request.form['actual_amount'])

    bill = Bill.query.filter_by(
        user_id=current_user.id,
        month=month,
        year=year
    ).first()

    if bill:
        bill.actual_amount = actual_amount
        bill.is_settled = True
    else:
        bill = Bill(
            user_id=current_user.id,
            month=month,
            year=year,
            actual_amount=actual_amount,
            is_settled=True
        )
        db.session.add(bill)

    db.session.commit()
    flash('Actual bill saved! Comparison updated.', 'success')
    return redirect(url_for('billing.predict'))