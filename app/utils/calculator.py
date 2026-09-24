def appliance_monthly_cost(wattage, daily_hours, tariff_rate):
    """
    Calculate monthly cost for a single appliance.
    Formula: (watts / 1000) * hours * 30 * rate
    """
    if not all([wattage, daily_hours, tariff_rate]):
        return 0.0
    monthly_kwh = (wattage / 1000) * daily_hours * 30
    return round(monthly_kwh * tariff_rate, 2)


def total_monthly_kwh(appliances):
    """
    Sum monthly kWh for a list of appliance dicts/objects.
    """
    total = 0
    for app in appliances:
        if app.is_active:
            total += (app.wattage / 1000) * app.avg_daily_hours * 30
    return round(total, 2)


def generator_cost_per_kwh(fuel_price_per_litre, litres_per_hour, kva_output):
    """
    Calculate generator cost per kWh.
    Formula: (fuel_price * litres_per_hour) / kva_output
    """
    if not all([fuel_price_per_litre, litres_per_hour, kva_output]) or kva_output == 0:
        return 0.0
    return round((fuel_price_per_litre * litres_per_hour) / kva_output, 2)


def calculate_log_cost(kwh, tariff_rate):
    """
    Calculate cost for a consumption log entry.
    """
    if not kwh or not tariff_rate:
        return 0.0
    return round(kwh * tariff_rate, 2)


def format_naira(value):
    """
    Format a value as Nigerian Naira currency.
    """
    if value is None:
        return "—"
    return f"₦{value:,.2f}"


def predict_monthly_bill(total_kwh, tariff_rate):
    """
    Predict monthly bill based on total kWh and tariff rate.
    """
    if not total_kwh or not tariff_rate:
        return 0.0
    return round(total_kwh * tariff_rate, 2)


def detect_anomalies(consumption_logs):
    """
    Detect anomalies in consumption patterns.
    Returns a list of anomalous logs.
    """
    if not consumption_logs or len(consumption_logs) < 3:
        return []
    
    kwh_values = [log.kwh_consumed for log in consumption_logs]
    avg = sum(kwh_values) / len(kwh_values)
    std_dev = (sum((x - avg) ** 2 for x in kwh_values) / len(kwh_values)) ** 0.5
    
    anomalies = []
    for log in consumption_logs:
        if std_dev > 0 and abs(log.kwh_consumed - avg) > 2 * std_dev:
            anomalies.append(log)
    
    return anomalies


def get_daily_kwh_summary(consumption_logs):
    """
    Get daily kWh summary from consumption logs.
    Returns a dictionary with date as key and total kwh as value.
    """
    daily_summary = {}
    for log in consumption_logs:
        date_key = str(log.log_date)
        daily_summary[date_key] = daily_summary.get(date_key, 0) + log.kwh_consumed
    return daily_summary


def get_appliance_cost_breakdown(consumption_logs, tariff_rate):
    """
    Get cost breakdown by appliance.
    Returns a dictionary with appliance_id as key and cost as value.
    """
    breakdown = {}
    for log in consumption_logs:
        if log.appliance_id:
            cost = log.fuel_cost if log.fuel_cost is not None else calculate_log_cost(
                log.kwh_consumed,
                tariff_rate,
            )
            breakdown[log.appliance_id] = breakdown.get(log.appliance_id, 0) + cost
    return breakdown


def get_budget_status(current_spending, budget_limit):
    """
    Get budget status: 'ok', 'warning', or 'exceeded'.
    """
    if budget_limit == 0:
        return 'ok'
    percentage = (current_spending / budget_limit) * 100
    if percentage >= 100:
        return 'exceeded'
    elif percentage >= 80:
        return 'warning'
    return 'ok'