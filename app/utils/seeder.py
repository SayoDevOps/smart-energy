from app import db
from app.models import TariffBand

def seed_tariff_bands():
    """Seed NERC tariff bands. Safe to run multiple times."""
    bands = [
        {'band': 'A', 'rate_per_kwh': 225.00, 'service_hours': '20+ hours', 'description': 'Premium areas (VI, Ikoyi)'},
        {'band': 'B', 'rate_per_kwh': 63.33, 'service_hours': '16-20 hours', 'description': 'Good urban supply'},
        {'band': 'C', 'rate_per_kwh': 50.00, 'service_hours': '12-16 hours', 'description': 'Average urban'},
        {'band': 'D', 'rate_per_kwh': 46.15, 'service_hours': '8-12 hours', 'description': 'Irregular supply'},
        {'band': 'E', 'rate_per_kwh': 40.61, 'service_hours': '4-8 hours', 'description': 'Rural/poor supply'},
    ]
    
    for b in bands:
        existing = TariffBand.query.filter_by(band=b['band']).first()
        if not existing:
            tb = TariffBand(**b)
            db.session.add(tb)
        else:
            existing.rate_per_kwh = b['rate_per_kwh']
            existing.service_hours = b['service_hours']
            existing.description = b['description']
    
    db.session.commit()
    print("Tariff bands seeded.")