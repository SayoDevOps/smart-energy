# Consumption optimization engine
# Generates personalized savings tips based on appliances and tariff rates

from app.models import Appliance, ConsumptionLog
from datetime import date, timedelta
from app.models import OptimizationTip

MIN_ACTUAL_LOGS = 3


def _appliance_usage(appliance, user_id, ConsumptionLog, today=None):
    """Return a 30-day actual or explicitly marked fallback usage profile."""
    today = today or date.today()
    start_date = today - timedelta(days=29)
    logs = ConsumptionLog.query.filter(
        ConsumptionLog.user_id == user_id,
        ConsumptionLog.appliance_id == appliance.id,
        ConsumptionLog.log_date >= start_date,
        ConsumptionLog.log_date <= today,
    ).all()

    if len(logs) >= MIN_ACTUAL_LOGS:
        return {
            'monthly_kwh': round(sum(log.kwh_consumed for log in logs), 2),
            'source': 'actual',
            'log_count': len(logs),
            'basis': f'Based on {len(logs)} linked consumption logs',
        }

    estimated_kwh = (appliance.wattage / 1000) * appliance.avg_daily_hours * 30
    return {
        'monthly_kwh': round(estimated_kwh, 2),
        'source': 'fallback_estimate',
        'log_count': len(logs),
        'basis': 'Estimated from appliance profile (insufficient linked logs)',
    }


def generate_tips(user_id, tariff_rate, db, Appliance, ConsumptionLog):
    """
    Analyzes user's appliances and returns personalized savings tips.
    Uses real 2026 Nigerian energy data:
    - Petrol: ₦1,300/litre (March 2026 Lagos average)
    - LED saves 75% vs incandescent (RPE Ltd 2025)
    - AC = 40-60% of electricity bills (NERC guidance)
    - Grid average: 4 hrs/day, generator 6-8 hrs/day
    """
    appliances = Appliance.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()

    tips = []
    appliance_tip_count = {}
    usage_profiles = {}

    for a in appliances:
        usage_profile = _appliance_usage(a, user_id, ConsumptionLog)
        usage_profiles[a.id] = usage_profile
        monthly_kwh = usage_profile['monthly_kwh']
        monthly_cost = monthly_kwh * tariff_rate

        # RULE 1: AC overuse
        if a.category == 'cooling' and a.avg_daily_hours > 6:
            saved_hours = 2
            saving = monthly_cost * min(saved_hours / a.avg_daily_hours, 1)
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': 'cooling',
                'tip_text': (
                    f'Your {a.name} runs {a.avg_daily_hours} hours/day. '
                    f'Reducing by 2 hours and setting temperature to 24°C '
                    f'instead of 18°C could save you ₦{saving:,.2f}/month. '
                    f'AC cooling accounts for up to 60% of electricity bills '
                    f'in Nigerian homes.'
                ),
                'action_type': 'reduce_hours',
                'potential_saving': round(saving, 2),
                'priority': 'high',
                'icon': 'fa-snowflake'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

        # RULE 2: Old incandescent bulbs
        if a.category == 'lighting' and a.wattage > 40:
            led_wattage = 9
            saving = monthly_cost * ((a.wattage - led_wattage) / a.wattage)
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': 'lighting',
                'tip_text': (
                    f'Switching {a.name} ({int(a.wattage)}W) to a 9W LED bulb '
                    f'saves ₦{saving:,.2f}/month. LED bulbs use 75% less energy '
                    f'and last up to 25x longer. Payback period: under 3 months.'
                ),
                'action_type': 'replace',
                'potential_saving': round(saving, 2),
                'priority': 'high',
                'icon': 'fa-lightbulb'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

        # RULE 3: Refrigerator maintenance
        if a.category == 'refrigeration':
            saving = monthly_cost * 0.15
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': 'refrigeration',
                'tip_text': (
                    f'Your {a.name} runs continuously. Defrosting monthly '
                    f'and keeping it 3/4 full improves efficiency by ~15%, '
                    f'saving approx ₦{saving:,.2f}/month. Also ensure it is '
                    f'not placed next to your cooker or in direct sunlight.'
                ),
                'action_type': 'maintenance',
                'potential_saving': round(saving, 2),
                'priority': 'medium',
                'icon': 'fa-temperature-low'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

        # RULE 4: High wattage cooking
        if a.category == 'cooking' and a.wattage >= 1000 and a.avg_daily_hours > 1:
            saving = monthly_cost * min(0.5 / a.avg_daily_hours, 1)
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': 'cooking',
                'tip_text': (
                    f'Your {a.name} uses {int(a.wattage)}W. Reducing cooking time '
                    f'by 30 mins/day (using lids, pre-soaking beans, pressure '
                    f'cooker) saves ₦{saving:,.2f}/month.'
                ),
                'action_type': 'reduce_hours',
                'potential_saving': round(saving, 2),
                'priority': 'medium',
                'icon': 'fa-fire-burner'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

        # RULE 5: Entertainment devices left on standby
        if a.category == 'entertainment' and a.avg_daily_hours > 8:
            saving = monthly_cost * min(2 / a.avg_daily_hours, 1)
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': 'entertainment',
                'tip_text': (
                    f'{a.name} is on for {a.avg_daily_hours} hours/day. '
                    f'Switching off (not standby) when not watching saves '
                    f'₦{saving:,.2f}/month. Standby mode still consumes 5-10W '
                    f'continuously.'
                ),
                'action_type': 'behaviour',
                'potential_saving': round(saving, 2),
                'priority': 'low',
                'icon': 'fa-tv'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

        # Water pump rule
        if a.category == 'water' and a.wattage > 300 and a.avg_daily_hours > 1:
            saving = monthly_cost * min(0.5 / a.avg_daily_hours, 1)
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': a.category,
                'tip_text': (
                    f'Your {a.name} uses '
                    f'{int(a.wattage)}W. '
                    f'Running it during NERC '
                    f'supply hours instead of '
                    f'generator saves '
                    f'\u20A6{saving:,.2f}/month '
                    f'in fuel costs. Consider '
                    f'an overhead tank to reduce '
                    f'daily pump runtime.'
                ),
                'action_type': 'schedule',
                'potential_saving': round(saving, 2),
                'priority': 'medium',
                'icon': 'fa-faucet'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

        # Laundry/ironing rule
        if a.category == 'laundry' and a.avg_daily_hours > 0.5:
            saving = (a.wattage / 1000) * 0.5 * 30 * tariff_rate
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': a.category,
                'tip_text': (
                    f'Your {a.name} uses '
                    f'{int(a.wattage)}W. '
                    f'Batch your ironing once '
                    f'or twice a week instead '
                    f'of daily to save '
                    f'\u20A6{saving:,.2f}/month. '
                    f'Always iron during NERC '
                    f'supply hours to avoid '
                    f'generator fuel cost.'
                ),
                'action_type': 'schedule',
                'potential_saving': round(saving, 2),
                'priority': 'low',
                'icon': 'fa-shirt'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

        # RULE 7: High monthly cost appliance
        if a.wattage > 1000 and monthly_cost > 2000:
            saving = monthly_cost * 0.15
            tips.append({
                'appliance_name': a.name,
                'appliance_id': a.id,
                'category': 'high_usage',
                'tip_text': (
                    f'{a.name} uses {int(a.wattage)}W for {a.avg_daily_hours} hours/day. '
                    f'At an estimated ₦{monthly_cost:,.2f}/month, it is above the '
                    f'high-usage threshold. Reducing runtime or switching to a more '
                    f'efficient model could save around ₦{saving:,.2f}/month.'
                ),
                'action_type': 'reduce_usage',
                'potential_saving': round(saving, 2),
                'priority': 'high',
                'icon': 'fa-bolt'
            })
            appliance_tip_count[a.id] = appliance_tip_count.get(a.id, 0) + 1
            if appliance_tip_count[a.id] >= 1:
                continue

    for tip in tips:
        usage_profile = usage_profiles[tip['appliance_id']]
        tip['monthly_kwh'] = usage_profile['monthly_kwh']
        tip['usage_source'] = usage_profile['source']
        tip['usage_log_count'] = usage_profile['log_count']
        tip['usage_basis'] = usage_profile['basis']

    # Sort by potential saving descending
    tips.sort(key=lambda x: x['potential_saving'], reverse=True)
    return tips


def get_total_potential_saving(tips):
    """Sum of all tip savings."""
    return round(sum(t['potential_saving'] for t in tips), 2)


def get_optimization_summary(
    user_id,
    tariff_rate,
    db,
    Appliance,
    ConsumptionLog,
    start_datetime=None,
    end_datetime=None,
):
    """Share generated savings while retaining persisted applied state."""
    tips = generate_tips(
        user_id=user_id,
        tariff_rate=tariff_rate,
        db=db,
        Appliance=Appliance,
        ConsumptionLog=ConsumptionLog,
    )
    stored_query = OptimizationTip.query.filter_by(user_id=user_id)
    if start_datetime is not None:
        stored_query = stored_query.filter(OptimizationTip.generated_at >= start_datetime)
    if end_datetime is not None:
        stored_query = stored_query.filter(OptimizationTip.generated_at < end_datetime)
    applied_ids = {
        tip.appliance_id for tip in stored_query.all()
        if tip.is_applied and tip.appliance_id is not None
    }
    applied_tips = [tip for tip in tips if tip['appliance_id'] in applied_ids]

    return {
        'tips': tips,
        'total_saving': get_total_potential_saving(tips),
        'applied_count': len(applied_tips),
        'applied_saving': round(
            sum(tip['potential_saving'] for tip in applied_tips),
            2,
        ),
        'total_count': len(tips),
    }