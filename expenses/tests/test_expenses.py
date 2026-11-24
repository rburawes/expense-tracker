import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from expenses.analytics import add_months, dashboard_stats
from expenses.forms import ExpenseFilterForm, ExpenseForm
from expenses.models import Category, Expense
from expenses.templatetags.money import currency

HTMX = {"HTTP_HX_REQUEST": "true"}


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user("alice", password="pw-12345-xyz")
        cls.other = User.objects.create_user("bob", password="pw-12345-xyz")
        cls.today = timezone.localdate()

    def setUp(self):
        self.client.force_login(self.user)

    def make(self, user=None, **kw):
        defaults = {"date": self.today, "amount": Decimal("10.00"), "category": Category.FOOD, "description": "Lunch"}
        return Expense.objects.create(user=user or self.user, **{**defaults, **kw})


class CurrencyFilterTests(TestCase):
    def test_formats(self):
        self.assertEqual(currency(Decimal("1234.5")), "$1,234.50")
        self.assertEqual(currency(0), "$0.00")
        self.assertEqual(currency(None), "$0.00")
        self.assertEqual(currency(-3), "-$3.00")

    @override_settings(EXPENSES_CURRENCY_SYMBOL="€")
    def test_symbol_setting(self):
        self.assertEqual(currency(5), "€5.00")


class ExpenseFormTests(TestCase):
    def data(self, **kw):
        return {"date": timezone.localdate().isoformat(), "amount": "12.50", "category": "food", "description": "Tacos", **kw}

    def test_valid(self):
        self.assertTrue(ExpenseForm(self.data()).is_valid())

    def test_rejects_zero_negative_and_huge_amounts(self):
        for amount in ("0", "-5", "1000000.01", "abc", "1.234"):
            with self.subTest(amount=amount):
                self.assertIn("amount", ExpenseForm(self.data(amount=amount)).errors)

    def test_rejects_future_date(self):
        future = (timezone.localdate() + timedelta(days=1)).isoformat()
        form = ExpenseForm(self.data(date=future))
        self.assertIn("future", str(form.errors["date"]))

    def test_rejects_blank_description_and_bad_category(self):
        self.assertIn("description", ExpenseForm(self.data(description="   ")).errors)
        self.assertIn("category", ExpenseForm(self.data(category="crypto")).errors)

    def test_normalises_whitespace(self):
        form = ExpenseForm(self.data(description="  Big   lunch  "))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["description"], "Big lunch")


class AuthTests(TestCase):
    def test_pages_require_login(self):
        for name in ("expenses:dashboard", "expenses:list", "expenses:create", "expenses:export"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("login"), response["Location"])

    def test_signup_logs_in(self):
        response = self.client.post(
            reverse("signup"), {"username": "carol", "password1": "Sup3r-secret-pw", "password2": "Sup3r-secret-pw"}
        )
        self.assertRedirects(response, reverse("expenses:dashboard"))
        self.assertEqual(self.client.get(reverse("expenses:dashboard")).status_code, 200)


class CrudTests(Base):
    def payload(self, **kw):
        return {"date": self.today.isoformat(), "amount": "42.10", "category": "bills", "description": "Internet", **kw}

    def test_create_full_page(self):
        response = self.client.post(reverse("expenses:create"), self.payload())
        self.assertRedirects(response, reverse("expenses:list"))
        self.assertEqual(self.user.expenses.get().amount, Decimal("42.10"))

    def test_create_htmx_returns_204_with_triggers(self):
        response = self.client.post(reverse("expenses:create"), self.payload(), **HTMX)
        self.assertEqual(response.status_code, 204)
        triggers = json.loads(response["HX-Trigger"])
        self.assertEqual(list(triggers), ["toast", "expenses-changed", "close-modal"])
        self.assertIn("$42.10", triggers["toast"]["message"])

    def test_create_htmx_invalid_rerenders_form(self):
        response = self.client.post(reverse("expenses:create"), self.payload(amount="-1"), **HTMX)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "expenses/partials/_expense_form.html")
        self.assertTemplateNotUsed(response, "components/modal.html")
        self.assertContains(response, 'aria-invalid="true"')
        self.assertFalse(Expense.objects.exists())

    def test_get_create_htmx_returns_modal(self):
        response = self.client.get(reverse("expenses:create"), **HTMX)
        self.assertTemplateUsed(response, "components/modal.html")
        self.assertNotContains(response, "<html")

    def test_update(self):
        expense = self.make()
        response = self.client.post(reverse("expenses:update", args=[expense.pk]), self.payload(amount="9.99"), **HTMX)
        self.assertEqual(response.status_code, 204)
        expense.refresh_from_db()
        self.assertEqual(expense.amount, Decimal("9.99"))
        self.assertEqual(expense.user, self.user)

    def test_delete_confirm_then_delete(self):
        expense = self.make()
        url = reverse("expenses:delete", args=[expense.pk])
        self.assertContains(self.client.get(url), "Delete expense?")
        self.assertTrue(Expense.objects.filter(pk=expense.pk).exists())
        self.assertEqual(self.client.post(url, **HTMX).status_code, 204)
        self.assertFalse(Expense.objects.filter(pk=expense.pk).exists())

    def test_cannot_touch_other_users_expenses(self):
        theirs = self.make(user=self.other)
        for name in ("expenses:update", "expenses:delete"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[theirs.pk])).status_code, 404)
                self.assertEqual(self.client.post(reverse(name, args=[theirs.pk]), self.payload()).status_code, 404)
        self.assertTrue(Expense.objects.filter(pk=theirs.pk, amount=Decimal("10.00")).exists())


class ListAndFilterTests(Base):
    def setUp(self):
        super().setUp()
        self.make(description="Groceries", category=Category.FOOD, amount=Decimal("50"))
        self.make(description="Bus pass", category=Category.TRANSPORTATION, amount=Decimal("30"),
                  date=self.today - timedelta(days=40))
        self.make(description="Netflix", category=Category.ENTERTAINMENT, amount=Decimal("15"),
                  date=self.today - timedelta(days=400))
        self.make(user=self.other, description="Bob's groceries")

    def get(self, **params):
        return self.client.get(reverse("expenses:list"), params)

    def descriptions(self, response):
        return [e.description for e in response.context["expenses"]]

    def test_only_own_expenses(self):
        self.assertNotIn("Bob's groceries", self.descriptions(self.get()))
        self.assertEqual(self.get().context["total_count"], 3)

    def test_search_category_and_dates(self):
        self.assertEqual(self.descriptions(self.get(q="grocer")), ["Groceries"])
        self.assertEqual(self.descriptions(self.get(category="transportation")), ["Bus pass"])
        self.assertEqual(self.descriptions(self.get(preset="last_30")), ["Groceries"])
        start = (self.today - timedelta(days=60)).isoformat()
        end = (self.today - timedelta(days=1)).isoformat()
        self.assertEqual(self.descriptions(self.get(date_from=start, date_to=end)), ["Bus pass"])

    def test_sort_and_total(self):
        response = self.get(sort="-amount")
        self.assertEqual(self.descriptions(response), ["Groceries", "Bus pass", "Netflix"])
        self.assertEqual(response.context["total_amount"], Decimal("95"))

    def test_invalid_range_shows_error(self):
        response = self.get(date_from=self.today.isoformat(), date_to=(self.today - timedelta(days=5)).isoformat())
        self.assertContains(response, "End date must be on or after the start date.")

    def test_htmx_returns_partial(self):
        response = self.client.get(reverse("expenses:list"), {"q": "bus"}, **HTMX)
        self.assertTemplateUsed(response, "expenses/partials/_expense_results.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, "Bus pass")

    def test_empty_state(self):
        self.assertContains(self.get(q="zzz"), "No matching expenses")

    def test_filter_presets(self):
        form = ExpenseFilterForm({"preset": "last_month"})
        self.assertTrue(form.is_valid())
        start, end = form.date_range()
        self.assertEqual(start.day, 1)
        self.assertEqual(end + timedelta(days=1), self.today.replace(day=1))


class ExportTests(Base):
    def test_csv_respects_filters_and_escapes_formulas(self):
        self.make(description="=HYPERLINK(\"evil\")", amount=Decimal("1234.5"))
        self.make(description="Taxi", category=Category.TRANSPORTATION)
        self.make(user=self.other, description="Hidden")
        response = self.client.get(reverse("expenses:export"), {"category": "food"})
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        lines = body.strip().splitlines()
        self.assertEqual(lines[0], "Date,Category,Description,Amount (USD)")
        self.assertEqual(len(lines), 2)
        self.assertIn("'=HYPERLINK", body)
        self.assertIn("1234.50", body)
        self.assertNotIn("Taxi", body)
        self.assertNotIn("Hidden", body)


class DashboardTests(Base):
    def test_add_months(self):
        from datetime import date

        self.assertEqual(add_months(date(2026, 1, 1), -1), date(2025, 12, 1))
        self.assertEqual(add_months(date(2026, 11, 1), 3), date(2027, 2, 1))

    def test_stats(self):
        self.make(amount=Decimal("60"), category=Category.BILLS)
        self.make(amount=Decimal("40"), category=Category.FOOD)
        self.make(amount=Decimal("999"), date=self.today - timedelta(days=500))
        self.make(user=self.other, amount=Decimal("5000"))
        stats = dashboard_stats(self.user, "month")
        self.assertEqual(stats["period_total"], Decimal("100"))
        self.assertEqual(stats["this_month_total"], Decimal("100"))
        self.assertEqual(stats["all_time_total"], Decimal("1099"))
        self.assertEqual(stats["top_category"].key, Category.BILLS)
        self.assertAlmostEqual(stats["top_category"].percent, 60.0)
        self.assertEqual(len(stats["trend"]), 12)
        self.assertEqual(stats["trend"][-1]["total"], 100.0)

    def test_dashboard_renders(self):
        self.make(amount=Decimal("1500.75"))
        response = self.client.get(reverse("expenses:dashboard"), {"period": "year"})
        self.assertContains(response, "$1,500.75")
        self.assertContains(response, 'id="chart-data"')
        self.assertContains(response, "This year")

    def test_dashboard_empty_and_bad_period(self):
        response = self.client.get(reverse("expenses:dashboard"), {"period": "bogus"})
        self.assertContains(response, "Welcome to Ledgerly")

    def test_dashboard_htmx_partial(self):
        response = self.client.get(reverse("expenses:dashboard"), {"period": "30d"}, **HTMX)
        self.assertTemplateUsed(response, "expenses/partials/_dashboard_content.html")
        self.assertTemplateNotUsed(response, "base.html")
