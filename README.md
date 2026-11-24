# Ledgerly: Expense Tracker

A personal expense tracker built with Django 5, HTMX 2, Alpine.js 3, Tailwind CSS v4 and SQLite.

## Features
- **Accounts:** sign up, sign in and sign out. Each user only sees their own expenses.
- **Expenses:** add, edit and delete expenses in modal dialogs with no full page reloads. Delete asks for confirmation first.
- **Validation:** the amount must be between 0.01 and 1,000,000 with at most 2 decimal places, the date can't be in the future, and the description is required. Errors appear inline.
- **List:** live search, filters for category and period presets (this month, last month, last 30 days, this year), custom date ranges, sorting and pagination. Filter state is kept in the URL.
- **Dashboard:** period selector, total spent, this month compared with the same point last month, daily average, top category, a 12-month bar chart, a category doughnut chart with breakdown bars, and recent expenses.
- **CSV export:** exports whatever the current filters show, or everything from the user menu. Formula injection is neutralised and the file includes a UTF-8 BOM so Excel reads it correctly.
- **UX:** toasts for success and errors, loading spinners and disabled buttons while requests run, HTMX error handling (network, 4xx and 5xx), responsive layout with mobile bottom navigation and bottom-sheet modals, and keyboard support (Esc closes dialogs, focus moves into the modal).
- **No-JS fallback:** every action also works as a normal full-page form.

## Setup
Requires Python 3.12+.

```bash
cd expense_tracker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py tailwind build          # downloads the standalone Tailwind v4 CLI (no Node needed)
python manage.py seed_expenses           # optional: demo user "demo" / "demo-pass-123" with 12 months of data
python manage.py runserver
```
Open http://127.0.0.1:8000 and sign in as `demo` / `demo-pass-123`, or create an account.

While editing templates, run `python manage.py tailwind runserver` instead. It starts Django and the Tailwind watcher together.

> **macOS note:** if `tailwind build` fails with "An unknown error occurred", the downloaded binary
> was killed by the code-signing check. Re-sign it and retry:
> `codesign --force -s - .django_tailwind_cli/tailwindcss-*`

## Tests
```bash
python manage.py test
```

## Production
Set these environment variables: `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY=...`, `DJANGO_ALLOWED_HOSTS=example.com`,
and `DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com`. Then run:
```bash
python manage.py tailwind build && python manage.py collectstatic --noinput && python manage.py migrate
gunicorn config.wsgi   # (pip install gunicorn)
```
WhiteNoise serves the static files. You can change the currency with `EXPENSES_CURRENCY_CODE` / `EXPENSES_CURRENCY_SYMBOL`.

## Project layout
```
config/              settings, urls
accounts/            signup + styled login form
expenses/
  models.py          Expense + Category choices and colours
  forms.py           ExpenseForm (validation, crispy layout), ExpenseFilterForm
  analytics.py       dashboard aggregations
  views.py           dashboard, list, CRUD (HTMX-aware), CSV export
  templatetags/      currency filter, SVG icons
  management/commands/seed_expenses.py
  tests/
templates/           base layout, pages, HTMX partials, crispy field override
assets/css/source.css   Tailwind v4 entry point
static/              vendored htmx / alpine / chart.js, app.js, built CSS
```
