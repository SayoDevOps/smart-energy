from datetime import datetime

def get_seasonal_context(month=None):
    """
    Returns seasonal context for Nigeria.
    Dry season: November – March
    Rainy season: April – October
    
    Returns dict:
    {
        'season': 'dry' | 'rainy',
        'level': 'warning' | 'info',
        'icon': str,
        'message': str
    }
    """
    if month is None:
        month = datetime.now().month

    dry_months = [11, 12, 1, 2, 3]

    if month in dry_months:
        return {
            'season': 'dry',
            'level': 'warning',
            'icon': '☀️',
            'message': (
                'Dry season is here (Nov–Mar). AC usage typically rises 30–40%. '
                'Your bill prediction may be conservative if you run cooling longer than usual.'
            )
        }
    else:
        return {
            'season': 'rainy',
            'level': 'info',
            'icon': '🌧',
            'message': (
                'Rainy season (Apr–Oct): Lower AC demand. '
                'Good time to save on cooling costs.'
            )
        }