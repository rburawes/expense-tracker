from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def currency(value) -> str:
    """Format a number as currency, e.g. 1234.5 -> "$1,234.50" and -3 -> "-$3.00"."""
    try:
        amount = Decimal(str(value if value not in (None, "") else 0))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    sign = "-" if amount < 0 else ""
    return f"{sign}{settings.EXPENSES_CURRENCY_SYMBOL}{abs(amount):,.2f}"


@register.filter
def abs_value(value):
    try:
        return abs(value)
    except TypeError:
        return value
