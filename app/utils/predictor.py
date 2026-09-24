# Weighted Moving Average bill predictor
# Recent days weighted higher — adapts faster to behavior changes

from datetime import date, timedelta
from sqlalchemy import func


def predict_monthly_bill(user_id, tariff_rate, db, ConsumptionLog):
    """
    Weighted moving average forecasting.
    Recent days get higher weight than older days.
    """
    today = date.today()
    first_of_month = date(today.year, today.month, 1)

    # Pull only grid logs for this month, oldest first
    logs = ConsumptionLog.query.filter(
        ConsumptionLog.user_id == user_id,
        ConsumptionLog.log_date >= first_of_month,
        ConsumptionLog.source == 'grid'
    ).order_by(ConsumptionLog.log_date.asc()).all()

    days_logged = len(logs)

    # Need minimum 3 days for prediction
    if days_logged < 3:
        return {
            'projected_kwh': None,
            'predicted_bill': None,
            'predicted_bill_with_vat': None,
            'avg_daily_kwh': None,
            'days_logged': days_logged,
            'confidence': 'insufficient',
            'confidence_level': 0,
            'error': f'Need at least 3 days of data. You have logged {days_logged} day(s) so far.'
        }

    # Weighted moving average — recent days count more
    daily_kwh = [log.kwh_consumed for log in logs]
    n = len(daily_kwh)
    weights = list(range(1, n + 1))  # 1, 2, 3, ... n

    weighted_sum = sum(w * k for w, k in zip(weights, daily_kwh))
    total_weight = sum(weights)
    avg_daily_kwh = weighted_sum / total_weight

    # Project for full 30-day month
    projected_kwh = round(avg_daily_kwh * 30, 2)

    # Bill calculations
    predicted_bill = round(projected_kwh * tariff_rate, 2)
    predicted_bill_with_vat = round(predicted_bill * 1.075, 2)

    # Confidence scoring based on data volume
    if days_logged >= 22:
        confidence, confidence_level = 'Very High', 95
    elif days_logged >= 15:
        confidence, confidence_level = 'High', 80
    elif days_logged >= 7:
        confidence, confidence_level = 'Moderate', 60
    else:
        confidence, confidence_level = 'Low', 30

    return {
        'projected_kwh': projected_kwh,
        'predicted_bill': predicted_bill,
        'predicted_bill_with_vat': predicted_bill_with_vat,
        'avg_daily_kwh': round(avg_daily_kwh, 2),
        'days_logged': days_logged,
        'confidence': confidence,
        'confidence_level': confidence_level,
        'error': None
    }


def get_bill_history(user_id, db, Bill):
    """Last 6 months of bill records with predicted vs actual."""
    return Bill.query.filter_by(user_id=user_id).order_by(
        Bill.year.desc(), Bill.month.desc()
    ).limit(6).all()


def detect_anomaly(user_id, db, ConsumptionLog):
    """
    Two-layer detection:
    Layer 1: 30%+ spike this week vs last week
    Layer 2: 3 consecutive weeks rising
    """
    today = date.today()

    def avg_kwh_period(start, end):
        result = db.session.query(
            func.avg(ConsumptionLog.kwh_consumed)
        ).filter(
            ConsumptionLog.user_id == user_id,
            ConsumptionLog.log_date >= start,
            ConsumptionLog.log_date <= end,
            ConsumptionLog.source == 'grid'
        ).scalar()
        return float(result) if result else 0

    # This week vs last week
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)

    this_week_avg = avg_kwh_period(week_start, today)
    last_week_avg = avg_kwh_period(last_week_start, last_week_end)

    if last_week_avg == 0:
        return {'has_anomaly': False, 'anomaly_type': None, 'message': None, 'percentage': None}

    pct_change = ((this_week_avg - last_week_avg) / last_week_avg) * 100

    #Spike detection
    if pct_change >= 30:
        return {
            'has_anomaly': True,
            'anomaly_type': 'spike',
            'message': f'Your usage jumped {pct_change:.0f}% this week vs last week. Did you add a new appliance?',
            'percentage': round(pct_change, 1)
        }

    #3-week trend creep
    two_weeks_ago_start = last_week_start - timedelta(days=7)
    two_weeks_ago_end = last_week_start - timedelta(days=1)
    two_weeks_avg = avg_kwh_period(two_weeks_ago_start, two_weeks_ago_end)

    if two_weeks_avg > 0 and last_week_avg > two_weeks_avg and this_week_avg > last_week_avg:
        total_increase = ((this_week_avg - two_weeks_avg) / two_weeks_avg) * 100
        return {
            'has_anomaly': True,
            'anomaly_type': 'trend',
            'message': f'Your energy usage has increased 3 weeks in a row. Total rise: +{total_increase:.0f}% over 3 weeks.',
            'percentage': round(total_increase, 1)
        }

    return {'has_anomaly': False, 'anomaly_type': None, 'message': None, 'percentage': None}