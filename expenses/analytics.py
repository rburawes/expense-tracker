"""Aggregations that power the dashboard."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, QuerySet, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import CATEGORY_META, Category, Expense

ZERO = Decimal("0.00")

PERIODS = {
    "month": "This month",
    "30d": "Last 30 days",
    "year": "This year",
    "all": "All time",
}


def add_months(d: date, months: int) -> date:
    month_index = d.year * 12 + (d.month - 1) + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def period_range(period: str, today: date, first_expense: date | None) -> tuple[date, date]:
    match period:
        case "30d":
            return today - timedelta(days=29), today
        case "year":
            return today.replace(month=1, day=1), today
        case "all":
            return (first_expense or today), today
        case _:
            return today.replace(day=1), today


def _total(qs: QuerySet) -> Decimal:
    return qs.aggregate(total=Sum("amount"))["total"] or ZERO


def percent_change(current: Decimal, previous: Decimal) -> float | None:
    if not previous:
        return None
    return float((current - previous) / previous * 100)


@dataclass
class CategoryTotal:
    key: str
    label: str
    total: Decimal
    count: int
    percent: float
    color: str
    dot: str


def category_breakdown(qs: QuerySet) -> list[CategoryTotal]:
    rows = qs.values("category").annotate(total=Sum("amount"), count=Count("id")).order_by("-total")
    grand = sum((r["total"] for r in rows), ZERO)
    labels = dict(Category.choices)
    result = []
    for r in rows:
        meta = CATEGORY_META.get(r["category"], CATEGORY_META[Category.OTHER])
        result.append(
            CategoryTotal(
                key=r["category"],
                label=labels.get(r["category"], r["category"]),
                total=r["total"],
                count=r["count"],
                percent=float(r["total"] / grand * 100) if grand else 0.0,
                color=meta["color"],
                dot=meta["dot"],
            )
        )
    return result


def monthly_trend(qs: QuerySet, today: date, months: int = 12) -> list[dict]:
    start = add_months(today.replace(day=1), -(months - 1))
    rows = (
        qs.filter(date__gte=start)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    totals = {r["month"]: r["total"] for r in rows}
    trend = []
    for i in range(months):
        m = add_months(start, i)
        trend.append({"label": m.strftime("%b %Y"), "short": m.strftime("%b"), "total": float(totals.get(m, ZERO))})
    return trend


def dashboard_stats(user, period: str = "month") -> dict:
    period = period if period in PERIODS else "month"
    today = timezone.localdate()
    base = Expense.objects.filter(user=user)

    first = base.order_by("date").values_list("date", flat=True).first()
    start, end = period_range(period, today, first)
    in_period = base.filter(date__gte=start, date__lte=end)

    month_start = today.replace(day=1)
    last_month_start = add_months(month_start, -1)
    # Compare month-to-date against the same span of last month for a fair comparison.
    last_month_same_day = min(today.day, (month_start - timedelta(days=1)).day)
    this_month_total = _total(base.filter(date__gte=month_start, date__lte=today))
    last_month_mtd = _total(
        base.filter(date__gte=last_month_start, date__lte=last_month_start.replace(day=last_month_same_day))
    )
    last_month_total = _total(base.filter(date__gte=last_month_start, date__lt=month_start))

    period_total = _total(in_period)
    period_count = in_period.count()
    days = max((end - start).days + 1, 1)
    categories = category_breakdown(in_period)

    return {
        "period": period,
        "period_label": PERIODS[period],
        "periods": PERIODS,
        "start": start,
        "end": end,
        "period_total": period_total,
        "period_count": period_count,
        "daily_average": (period_total / days).quantize(Decimal("0.01")),
        "days": days,
        "all_time_total": _total(base),
        "all_time_count": base.count(),
        "this_month_total": this_month_total,
        "last_month_total": last_month_total,
        "month_change": percent_change(this_month_total, last_month_mtd),
        "categories": categories,
        "top_category": categories[0] if categories else None,
        "largest_expense": in_period.order_by("-amount", "-date").first(),
        "trend": monthly_trend(base, today),
        "recent": base.order_by("-date", "-created_at")[:6],
    }
