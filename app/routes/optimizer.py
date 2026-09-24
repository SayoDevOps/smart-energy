# Personalized savings tips and what-if simulator
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Appliance, ConsumptionLog
from app.utils.optimizer import get_optimization_summary
from app.utils.tariff import get_tariff_rate

optimizer_bp = Blueprint('optimizer', __name__)


@optimizer_bp.route('/tips')
@login_required
def tips():
    """Show personalized savings tips based on user's appliances."""
    tariff_rate = get_tariff_rate(current_user.tariff_band)

    summary = get_optimization_summary(
        user_id=current_user.id,
        tariff_rate=tariff_rate,
        db=db,
        Appliance=Appliance,
        ConsumptionLog=ConsumptionLog
    )

    return render_template(
        'optimizer/tips.html',
        tips=summary['tips'],
        total_saving=summary['total_saving'],
        applied_count=summary['applied_count'],
        tariff_rate=tariff_rate
    )


@optimizer_bp.route('/simulator')
@login_required
def simulator():
    """What-if appliance usage simulator."""
    appliances = Appliance.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    tariff_rate = get_tariff_rate(current_user.tariff_band)

    return render_template(
        'optimizer/simulator.html',
        appliances=appliances,
        tariff_rate=tariff_rate
    )