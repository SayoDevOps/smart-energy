from datetime import date, datetime

from app import db
from app.models import Appliance, ConsumptionLog
from app.utils.calculator import appliance_monthly_cost
from app.utils.optimizer import get_optimization_summary


def month_window(year, month):
    """Return the inclusive start and exclusive end dates for a calendar month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def previous_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _month_logs(user_id, year, month):
    start, end = month_window(year, month)
    return ConsumptionLog.query.filter(
        ConsumptionLog.user_id == user_id,
        ConsumptionLog.log_date >= start,
        ConsumptionLog.log_date < end,
    ).all()


def _energy_totals(logs, tariff_rate):
    grid_logs = [log for log in logs if log.source == 'grid']
    generator_logs = [log for log in logs if log.source == 'generator']

    total_grid_kwh = sum(log.kwh_consumed or 0 for log in grid_logs)
    total_generator_hours = sum(log.generator_hours or 0 for log in generator_logs)
    total_fuel_cost = sum(log.fuel_cost or 0 for log in generator_logs)

    return {
        'total_grid_kwh': round(total_grid_kwh, 2),
        'total_grid_cost': round(total_grid_kwh * tariff_rate, 2),
        'total_generator_hours': round(total_generator_hours, 2),
        'total_fuel_cost': round(total_fuel_cost, 2),
    }


def _top_appliances(user_id, tariff_rate):
    appliances = Appliance.query.filter_by(user_id=user_id).all()
    top_appliances = [
        {
            'name': appliance.name,
            'category': appliance.category,
            'wattage': int(appliance.wattage),
            'monthly_cost': appliance_monthly_cost(
                appliance.wattage,
                appliance.avg_daily_hours,
                tariff_rate,
            ),
        }
        for appliance in appliances
    ]
    top_appliances.sort(key=lambda appliance: appliance['monthly_cost'], reverse=True)
    return top_appliances[:3]


def _optimization_summary(user_id, year, month, tariff_rate):
    start, end = month_window(year, month)
    start_datetime = datetime.combine(start, datetime.min.time())
    end_datetime = datetime.combine(end, datetime.min.time())
    summary = get_optimization_summary(
        user_id=user_id,
        tariff_rate=tariff_rate,
        db=db,
        Appliance=Appliance,
        ConsumptionLog=ConsumptionLog,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
    )

    return {
        'optimization_applied_count': summary['applied_count'],
        'optimization_total_count': summary['total_count'],
        'optimization_savings': summary['applied_saving'],
    }


def build_monthly_report(user_id, year, month, tariff_rate):
    """Build all calculated values needed by the monthly report."""
    current_logs = _month_logs(user_id, year, month)
    previous_year, previous_month_number = previous_month(year, month)
    previous_logs = _month_logs(user_id, previous_year, previous_month_number)

    current_totals = _energy_totals(current_logs, tariff_rate)
    previous_totals = _energy_totals(previous_logs, tariff_rate)
    combined_total_spend = round(
        current_totals['total_grid_cost'] + current_totals['total_fuel_cost'],
        2,
    )
    last_month_total_spend = round(
        previous_totals['total_grid_cost'] + previous_totals['total_fuel_cost'],
        2,
    )
    percentage_change = None
    if last_month_total_spend > 0:
        percentage_change = round(
            ((combined_total_spend - last_month_total_spend) / last_month_total_spend) * 100,
            1,
        )
    comparison_status = (
        'higher' if percentage_change is not None and percentage_change > 0
        else 'lower' if percentage_change is not None and percentage_change < 0
        else 'none'
    )

    return {
        **current_totals,
        'combined_total_spend': combined_total_spend,
        'top_appliances': _top_appliances(user_id, tariff_rate),
        **_optimization_summary(user_id, year, month, tariff_rate),
        'last_month_total_spend': last_month_total_spend,
        'percentage_change': percentage_change,
        'percentage_change_magnitude': (
            round(abs(percentage_change), 1) if percentage_change is not None else None
        ),
        'comparison_status': comparison_status,
    }