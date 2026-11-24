import csv
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .analytics import dashboard_stats
from .forms import ExpenseFilterForm, ExpenseForm
from .models import Expense
from .templatetags.money import currency


def _is_htmx(request: HttpRequest) -> bool:
    # Boosted requests expect full pages, so treat them like normal navigation.
    return bool(request.htmx) and not request.htmx.boosted


def _htmx_success(message: str) -> HttpResponse:
    """204 response that closes the modal, refreshes data on the page and shows a toast."""
    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps(
        {
            # Order matters: fire the toast before the modal (the event source) is removed.
            "toast": {"message": message, "type": "success"},
            "expenses-changed": True,
            "close-modal": True,
        }
    )
    return response


@login_required
@require_safe
def dashboard(request: HttpRequest) -> HttpResponse:
    stats = dashboard_stats(request.user, request.GET.get("period", "month"))
    chart_data = {
        "trend": {"labels": [t["short"] for t in stats["trend"]], "full": [t["label"] for t in stats["trend"]],
                  "values": [t["total"] for t in stats["trend"]]},
        "categories": {
            "labels": [c.label for c in stats["categories"]],
            "values": [float(c.total) for c in stats["categories"]],
            "colors": [c.color for c in stats["categories"]],
        },
        "currency": settings.EXPENSES_CURRENCY_CODE,
    }
    context = {**stats, "chart_data": chart_data}
    template = "expenses/partials/_dashboard_content.html" if _is_htmx(request) else "expenses/dashboard.html"
    return render(request, template, context)


@login_required
@require_safe
def expense_list(request: HttpRequest) -> HttpResponse:
    filter_form = ExpenseFilterForm(request.GET or None)
    expenses = filter_form.filter(Expense.objects.filter(user=request.user))
    summary = expenses.aggregate(total=Sum("amount"))

    page = Paginator(expenses, settings.EXPENSES_PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)

    context = {
        "filter_form": filter_form,
        "page_obj": page,
        "expenses": page.object_list,
        "total_count": page.paginator.count,
        "total_amount": summary["total"] or 0,
        "querystring": query.urlencode(),
        "is_filtered": filter_form.is_filtered,
    }
    template = "expenses/partials/_expense_results.html" if _is_htmx(request) else "expenses/expense_list.html"
    return render(request, template, context)


def _expense_form_view(request: HttpRequest, instance: Expense | None = None) -> HttpResponse:
    form = ExpenseForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        expense = form.save(commit=False)
        expense.user = request.user
        expense.save()
        verb = "updated" if instance else "added"
        message = f"Expense {verb}: {expense.description} ({currency(expense.amount)})"
        if _is_htmx(request):
            return _htmx_success(message)
        messages.success(request, message)
        return redirect("expenses:list")

    context = {"form": form, "expense": instance}
    if _is_htmx(request):
        # A POST with errors re-renders only the <form>; a GET renders the full modal.
        template = "expenses/partials/_expense_form.html" if request.method == "POST" else "expenses/partials/_expense_modal.html"
        return render(request, template, context)
    return render(request, "expenses/expense_form.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def expense_create(request: HttpRequest) -> HttpResponse:
    return _expense_form_view(request)


@login_required
@require_http_methods(["GET", "POST"])
def expense_update(request: HttpRequest, pk: int) -> HttpResponse:
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    return _expense_form_view(request, expense)


@login_required
@require_http_methods(["GET", "POST"])
def expense_delete(request: HttpRequest, pk: int) -> HttpResponse:
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == "POST":
        message = f"Deleted: {expense.description} ({currency(expense.amount)})"
        expense.delete()
        if _is_htmx(request):
            return _htmx_success(message)
        messages.success(request, message)
        return redirect("expenses:list")
    template = "expenses/partials/_delete_modal.html" if _is_htmx(request) else "expenses/expense_confirm_delete.html"
    return render(request, template, {"expense": expense})


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Neutralise spreadsheet formula injection in user-supplied text."""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


@login_required
@require_safe
def export_csv(request: HttpRequest) -> HttpResponse:
    filter_form = ExpenseFilterForm(request.GET or None)
    expenses = filter_form.filter(Expense.objects.filter(user=request.user))

    filename = f"expenses-{timezone.localdate():%Y-%m-%d}.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # BOM so Excel detects UTF-8

    writer = csv.writer(response)
    writer.writerow(["Date", "Category", "Description", f"Amount ({settings.EXPENSES_CURRENCY_CODE})"])
    for e in expenses.iterator():
        writer.writerow([e.date.isoformat(), e.get_category_display(), _csv_safe(e.description), f"{e.amount:.2f}"])
    return response
