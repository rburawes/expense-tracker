from django.conf import settings


def app_settings(request):
    return {
        "CURRENCY_CODE": settings.EXPENSES_CURRENCY_CODE,
        "CURRENCY_SYMBOL": settings.EXPENSES_CURRENCY_SYMBOL,
    }
