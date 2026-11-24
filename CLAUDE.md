# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ledgerly is a personal expense tracker: Django 5.2, HTMX 2, Alpine.js 3, Tailwind CSS v4 (via `django-tailwind-cli`,
standalone binary, no Node), django-crispy-forms (`crispy-tailwind` pack), django-htmx, SQLite. Python 3.12+.
It is not a git repository.

## Commands

Always activate the virtualenv first: `source .venv/bin/activate`.

```bash
python manage.py tailwind runserver        # Django + Tailwind watcher together (use while editing templates)
python manage.py runserver                 # Django only (CSS must already be built)
python manage.py tailwind build            # rebuild static/css/tailwind.css (generated; don't hand-edit)
python manage.py seed_expenses             # demo user "demo" / "demo-pass-123" with 12 months of data

python manage.py test                                              # all tests
python manage.py test expenses.tests.test_expenses.CrudTests       # one class
python manage.py test expenses.tests.test_expenses.CrudTests.test_create_full_page   # one test

python manage.py check
python manage.py makemigrations --check --dry-run
```

`ruff` (line length 120) is the house linter but is **not** in `.venv`. Install it before relying on it.

macOS: if `tailwind build` fails with "An unknown error occurred", re-sign the binary:
`codesign --force -s - .django_tailwind_cli/tailwindcss-*`

## Architecture

**Apps.** `accounts` handles signup plus a styled `LoginForm`. It is mounted at `/accounts/` *before*
`django.contrib.auth.urls`, so its `login` overrides the built-in one. Auth URL names are un-namespaced
(`login`, `signup`, `logout`). `expenses` holds everything else and is namespaced `expenses:`.

**Layering in `expenses`:**
- `models.py` defines `Expense` and the `Category` TextChoices. Category colours/icons live with the model
  (`category_meta`).
- `forms.py` has two forms:
  - `ExpenseForm` handles validation and the crispy layout.
  - `ExpenseFilterForm` owns all list filtering through `form.filter(queryset)` and `is_filtered`. The list view
    and the CSV export share it, so the export always matches what the list shows.
- `INPUT_CLASSES` in `expenses/forms.py` is the single source of input styling. `accounts/forms.py` imports it too.
- `analytics.py` returns all dashboard numbers from `dashboard_stats(user, period)`. It uses Decimal end to end,
  and views convert to float only when building chart JSON.
- `views.py` contains thin function-based views. Each one is `@login_required` plus a method decorator.
- Every query of user data is scoped by `user=request.user`. Object lookups use
  `get_object_or_404(..., user=request.user)`.

**HTMX contract.** The patterns are in `expenses/views.py`, `base.html` and `static/js/app.js`:
- `_is_htmx()` ignores boosted requests. HTMX requests get a `templates/expenses/partials/_*.html` partial.
  Normal requests get a full page that extends `base.html` and includes the same partial, so every flow works
  without JS.
- Create, edit and delete all go through modals:
  - A GET returns `_expense_modal.html` / `_delete_modal.html`, which is swapped into `#modal-root` in `base.html`.
  - A POST with errors returns only `_expense_form.html` with status 200.
  - A successful POST returns 204 from `_htmx_success()` with an `HX-Trigger` of `toast`, `expenses-changed` and
    `close-modal`, in that order.
- Regions refresh themselves by listening for `hx-trigger="expenses-changed from:body"`, so the server never
  needs to know the page layout.
- CSRF is sent globally via `hx-headers` on `<body>`.
- `app.js` does three things:
  - holds the Alpine `toasts` store
  - turns HTMX errors (4xx/5xx, network, timeout) into toasts
  - handles login redirects during HTMX requests as a full page navigation
- Charts are rendered from `|json_script` data and re-rendered after `htmx:afterSettle`.
- Django `messages` from non-HTMX flows are shown as the same toasts, via `x-init` in `base.html`.
- The modal component is in `templates/components/modal.html`. It closes on `close-modal`, Esc or a backdrop click.

**Tailwind v4.** The entry point is `assets/css/source.css`. It uses `source(none)` and explicit `@source` dirs
(templates, expenses, accounts, static/js), so a new source directory needs its own `@source` line. Reusable
classes (`btn`, `btn-primary`, …) are `@utility` blocks there. Write class names out in full, because the
scanner misses dynamically built ones.

**Settings.** `config/settings.py` reads environment variables through `env_bool` / `env_list`:
- `DJANGO_DEBUG` defaults to true. When it is false, a missing `DJANGO_SECRET_KEY` raises `ImproperlyConfigured`.
- App settings use the `EXPENSES_` prefix: `EXPENSES_CURRENCY_CODE`, `EXPENSES_CURRENCY_SYMBOL` and
  `EXPENSES_PAGE_SIZE`. They reach templates through `expenses.context_processors.app_settings` and the
  `currency` filter in `templatetags/money.py`.

**CSV export** neutralises formula-injection prefixes (`_csv_safe`) and writes a UTF-8 BOM.

## Conventions

The full team review standard is in `.claude/commands/django-review.md` (run it with `/django-review`).
Key points not obvious from the code:
- Use `timezone.localdate()`/`timezone.now()`, never `date.today()`.
- Tests:
  - Use the `Base` fixture in `expenses/tests/test_expenses.py` (`setUpTestData` + `force_login`, with a
    second user `bob` for ownership checks).
  - Cover both HTMX (`**HTMX` = `HTTP_HX_REQUEST="true"`) and full-page responses.
  - Derive dates from `timezone.localdate()` so tests don't break at month boundaries.
- Model changes ship with their migration.
