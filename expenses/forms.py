from datetime import date, timedelta

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Div, Field, Layout
from django import forms
from django.utils import timezone

from .models import Category, Expense

INPUT_CLASSES = (
    "block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-xs "
    "ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 "
    "focus:ring-2 focus:ring-inset focus:ring-indigo-600 focus:outline-none "
    "aria-invalid:ring-rose-500 aria-invalid:focus:ring-rose-500"
)


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["date", "amount", "category", "description"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "amount": forms.NumberInput(
                attrs={"step": "0.01", "min": "0.01", "inputmode": "decimal", "placeholder": "0.00"}
            ),
            "description": forms.TextInput(attrs={"placeholder": "e.g. Groceries at the market", "maxlength": 255}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault("date", today)
        self.fields["date"].widget.attrs["max"] = today.isoformat()
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", INPUT_CLASSES)
            if self.is_bound and name in self.errors:
                field.widget.attrs["aria-invalid"] = "true"

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(Field("date"), Field("amount"), css_class="grid grid-cols-1 gap-x-4 sm:grid-cols-2"),
            Field("category"),
            Field("description"),
        )

    def clean_date(self):
        value = self.cleaned_data["date"]
        today = timezone.localdate()
        if value > today:
            raise forms.ValidationError("The date can't be in the future.")
        if value < date(1970, 1, 1):
            raise forms.ValidationError("Please enter a date after 1970.")
        return value

    def clean_description(self):
        value = " ".join(self.cleaned_data["description"].split())
        if not value:
            raise forms.ValidationError("Please describe this expense.")
        return value


class ExpenseFilterForm(forms.Form):
    """Validates the query-string filters used by the list and CSV export."""

    PRESETS = [
        ("", "All time"),
        ("this_month", "This month"),
        ("last_month", "Last month"),
        ("last_30", "Last 30 days"),
        ("this_year", "This year"),
    ]
    SORTS = [
        ("-date", "Newest first"),
        ("date", "Oldest first"),
        ("-amount", "Highest amount"),
        ("amount", "Lowest amount"),
    ]

    q = forms.CharField(required=False, max_length=100)
    category = forms.ChoiceField(required=False, choices=[("", "All categories"), *Category.choices])
    preset = forms.ChoiceField(required=False, choices=PRESETS)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    sort = forms.ChoiceField(required=False, choices=SORTS)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", INPUT_CLASSES)

    def clean(self):
        cleaned = super().clean()
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "End date must be on or after the start date.")
        return cleaned

    def date_range(self) -> tuple[date | None, date | None]:
        """Resolve the preset (if any) or explicit dates into a (start, end) range."""
        data = self.cleaned_data
        today = timezone.localdate()
        match data.get("preset"):
            case "this_month":
                return today.replace(day=1), today
            case "last_month":
                end = today.replace(day=1) - timedelta(days=1)
                return end.replace(day=1), end
            case "last_30":
                return today - timedelta(days=29), today
            case "this_year":
                return today.replace(month=1, day=1), today
        return data.get("date_from"), data.get("date_to")

    def filter(self, queryset):
        if not self.is_valid():
            return queryset
        data = self.cleaned_data
        if q := data.get("q", "").strip():
            queryset = queryset.filter(description__icontains=q)
        if category := data.get("category"):
            queryset = queryset.filter(category=category)
        start, end = self.date_range()
        if start:
            queryset = queryset.filter(date__gte=start)
        if end:
            queryset = queryset.filter(date__lte=end)
        return queryset.order_by(data.get("sort") or "-date", "-created_at")

    @property
    def is_filtered(self) -> bool:
        if not self.is_valid():
            return False
        return any(self.cleaned_data.get(k) for k in ("q", "category", "preset", "date_from", "date_to"))
