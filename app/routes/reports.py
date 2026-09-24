from datetime import date

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.utils.reports import build_monthly_report
from app.utils.tariff import get_tariff_rate


reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/monthly')
@login_required
def monthly():
    today = date.today()
    tariff_band = current_user.tariff_band
    tariff_rate = get_tariff_rate(tariff_band)
    report = build_monthly_report(
        user_id=current_user.id,
        year=today.year,
        month=today.month,
        tariff_rate=tariff_rate,
    )

    return render_template(
        'reports/monthly.html',
        current_user=current_user,
        month_name=today.strftime('%B'),
        year=today.year,
        tariff_band=tariff_band,
        tariff_rate=tariff_rate,
        **report,
    )