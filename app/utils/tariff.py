DEFAULT_TARIFF_RATE = 50.00


def get_tariff_rate(tariff_band):
    return tariff_band.rate_per_kwh if tariff_band else DEFAULT_TARIFF_RATE
