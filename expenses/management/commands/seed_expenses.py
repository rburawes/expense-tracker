import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from expenses.models import Category, Expense

SAMPLES = {
    Category.FOOD: (["Groceries", "Coffee", "Lunch with team", "Pizza night", "Farmers market", "Bakery"], (4, 120)),
    Category.TRANSPORTATION: (["Fuel", "Metro card top-up", "Uber ride", "Parking", "Train ticket"], (3, 90)),
    Category.ENTERTAINMENT: (["Movie tickets", "Concert", "Streaming subscription", "Board game", "Bowling"], (8, 150)),
    Category.SHOPPING: (["New shoes", "Books", "Kitchen gadgets", "Clothing", "Phone case"], (10, 250)),
    Category.BILLS: (["Electricity bill", "Internet", "Phone plan", "Water bill", "Rent share"], (30, 400)),
    Category.OTHER: (["Gift", "Haircut", "Pharmacy", "Charity donation"], (5, 80)),
}
WEIGHTS = [34, 18, 12, 14, 10, 12]


class Command(BaseCommand):
    help = "Create a demo user (if needed) and populate ~12 months of realistic sample expenses."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="demo")
        parser.add_argument("--password", default="demo-pass-123")
        parser.add_argument("--count", type=int, default=260)
        parser.add_argument("--clear", action="store_true", help="Delete the user's existing expenses first.")

    @transaction.atomic
    def handle(self, *args, username, password, count, clear, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(password)
            user.save()
        if clear:
            user.expenses.all().delete()

        rng = random.Random(42)
        today = timezone.localdate()
        categories = list(SAMPLES)
        expenses = []
        for _ in range(count):
            category = rng.choices(categories, WEIGHTS)[0]
            names, (lo, hi) = SAMPLES[category]
            expenses.append(
                Expense(
                    user=user,
                    category=category,
                    description=rng.choice(names),
                    amount=Decimal(str(round(rng.uniform(lo, hi), 2))),
                    date=today - timedelta(days=int(rng.triangular(0, 365, 0))),
                )
            )
        Expense.objects.bulk_create(expenses)
        msg = f"Created {count} expenses for '{username}'."
        if created:
            msg += f" New user created with password '{password}'."
        self.stdout.write(self.style.SUCCESS(msg))
