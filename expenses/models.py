from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Category(models.TextChoices):
    FOOD = "food", "Food"
    TRANSPORTATION = "transportation", "Transportation"
    ENTERTAINMENT = "entertainment", "Entertainment"
    SHOPPING = "shopping", "Shopping"
    BILLS = "bills", "Bills"
    OTHER = "other", "Other"


# Presentation metadata per category: chart colour + Tailwind badge classes.
# Class strings are written out in full so Tailwind's scanner picks them up.
CATEGORY_META: dict[str, dict[str, str]] = {
    Category.FOOD: {"color": "#f97316", "badge": "bg-orange-50 text-orange-700 ring-orange-600/20", "dot": "bg-orange-500"},
    Category.TRANSPORTATION: {"color": "#0ea5e9", "badge": "bg-sky-50 text-sky-700 ring-sky-600/20", "dot": "bg-sky-500"},
    Category.ENTERTAINMENT: {"color": "#a855f7", "badge": "bg-purple-50 text-purple-700 ring-purple-600/20", "dot": "bg-purple-500"},
    Category.SHOPPING: {"color": "#ec4899", "badge": "bg-pink-50 text-pink-700 ring-pink-600/20", "dot": "bg-pink-500"},
    Category.BILLS: {"color": "#10b981", "badge": "bg-emerald-50 text-emerald-700 ring-emerald-600/20", "dot": "bg-emerald-500"},
    Category.OTHER: {"color": "#64748b", "badge": "bg-slate-100 text-slate-700 ring-slate-600/20", "dot": "bg-slate-500"},
}

MAX_AMOUNT = Decimal("1000000.00")


class Expense(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    date = models.DateField(db_index=True)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(MAX_AMOUNT)],
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER, db_index=True)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["user", "date"]), models.Index(fields=["user", "category"])]

    def __str__(self) -> str:
        return f"{self.date:%Y-%m-%d} · {self.get_category_display()} · {self.amount}"

    @property
    def category_meta(self) -> dict[str, str]:
        return CATEGORY_META.get(self.category, CATEGORY_META[Category.OTHER])
