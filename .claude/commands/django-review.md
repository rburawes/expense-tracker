---
description: Review Python/Django changes against the team's style, architecture and workflow standards
argument-hint: "[files | branch | PR number]  (default: uncommitted changes, else current branch vs main)"
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git status:*), Bash(git show:*), Bash(git merge-base:*), Bash(gh pr diff:*), Bash(gh pr view:*), Bash(python manage.py check:*), Bash(python manage.py test:*), Bash(python manage.py makemigrations --check:*), Bash(.venv/bin/python manage.py:*), Bash(ruff:*), Read, Grep, Glob
---

# Django Code Review

You are reviewing code in a Django 5.x / Python 3.12+ project that uses server-rendered templates,
HTMX 2, Alpine.js 3, Tailwind CSS v4 (django-tailwind-cli), django-crispy-forms and django-htmx.
Review like a senior engineer on this team: be specific, cite `file:line`, explain *why* something
matters, and propose a concrete fix. Do not pad the review with praise or restate the diff.

Review target: **$ARGUMENTS**

---

## 1. Workflow

Follow these steps in order.

### Step 1: Determine the scope
- **No arguments:** review uncommitted changes (`git diff HEAD` plus untracked files from
  `git status --porcelain`). If there are none, review the current branch against its merge base
  with `main` (`git diff $(git merge-base HEAD main)...HEAD`).
- **A number:** treat it as a PR. Use `gh pr view <n>` and `gh pr diff <n>`.
- **A branch name:** diff it against `main`.
- **Paths:** review those files in full.

State the scope you chose in one line before the findings.

### Step 2: Build context before you judge
- Read each changed file **in full**, not just the hunks. Read the callers, templates, forms and
  tests that touch the changed code.
- Read `CLAUDE.md` / `README.md` if present. Project-specific rules there override this document.
- Check for existing helpers before you flag "missing" functionality. Grep before claiming
  something is unused or duplicated.

### Step 3: Run the automated gates (when a virtualenv is available)
Run these and report failures as findings:
```bash
python manage.py check
python manage.py makemigrations --check --dry-run   # model changes must ship with migrations
python manage.py test                                # or the affected app(s) only, for speed
ruff check . && ruff format --check .                # if ruff is installed
```
Report each command's result. If a command cannot run, say so; do not assume it passed.

### Step 4: Review against the standards in sections 2–6.

### Step 5: Report using the format in section 7.

---

## 2. Python standards

- **Style:** PEP 8 enforced by `ruff` (line length 120). Use f-strings, `pathlib` and
  modern syntax (`X | None`, `match`, walrus where it clarifies). No wildcard imports. Imports
  go in the order stdlib → third-party → Django → local (ruff/isort).
- **Typing:** type hints on public functions, view signatures (`request: HttpRequest -> HttpResponse`)
  and service-layer functions. Use `dataclass` for structured return values, not loose dicts that
  cross module boundaries.
- **Naming:** names should be descriptive. Booleans read as predicates (`is_filtered`, `has_next`).
  Constants are `UPPER_SNAKE`.
- **Functions:** small and single-purpose. Return early rather than nesting deeply. No mutable
  default arguments. Avoid hidden side effects in properties.
- **Money and numbers:** use `Decimal` for currency end to end. Never use `float` for stored or
  summed amounts. Float is acceptable only at the chart/JSON boundary. Quantize explicitly.
- **Dates and time:** `USE_TZ = True`. Use `timezone.now()` / `timezone.localdate()`, never
  `datetime.now()` / `date.today()`.
- **Errors:** catch specific exceptions. Never write a bare `except:` or swallow errors silently.
  Log with `logging.getLogger(__name__)`, not `print`.
- **Comments:** explain *why*, not *what*. Delete commented-out code. A `TODO` needs an owner
  or ticket.

## 3. Django architecture standards

### Layering: where code belongs
| Layer | Responsibility | Must not |
|---|---|---|
| `models.py` | Schema, constraints, field validators, small instance helpers/properties | Do HTTP, request access, or cross-aggregate reporting |
| `forms.py` | Input validation and normalisation (`clean_*`, `clean`), widget config, crispy layout, filter forms that apply themselves to a queryset | Persist unrelated objects, or read `request` except via explicit kwargs |
| `analytics.py` / `services.py` | Aggregations, reporting, multi-model business operations | Return `HttpResponse` or render templates |
| `views.py` | Thin orchestration: auth → load → validate → call service → respond | Hold business logic or raw aggregation math |
| `templates/` | Presentation only | Run queries or contain logic beyond simple conditionals and loops |
| `templatetags/` | Reusable formatting and presentation helpers | Access the database |

- **Views:** function-based views are the house style. Use decorators for cross-cutting concerns:
  `@login_required` plus `@require_safe` / `@require_POST` / `@require_http_methods`. Every view
  declares its allowed methods.
- **Settings:** configure through environment variables (`env_bool`, `env_list`), with safe dev
  defaults and a hard failure in production when secrets are missing. Never hard-code secrets.
  App-level knobs use an `APPNAME_` prefix (e.g. `EXPENSES_PAGE_SIZE`).
- **URLs:** namespaced (`app_name = "expenses"`). Always use `reverse()` / `{% url %}`, never
  hard-coded paths.

### Data access and the ORM
- **Ownership scoping:** every queryset for user data is filtered by `user=request.user`. Use
  `get_object_or_404(Model, pk=pk, user=request.user)`, which returns 404 (not 403) for objects the
  user does not own. **Treat any unscoped lookup of user-owned data as a blocker.**
- **N+1 queries:** use `select_related` / `prefetch_related` for relations rendered in loops.
  Aggregate in the database (`Sum`, `Count`, `TruncMonth`), not in Python loops over rows.
- **Large reads:** `.iterator()` for exports and streams; `.exists()` rather than `len()` / `count()`
  for presence checks; `.only()` / `.values()` when full models are not needed.
- **Writes:** use `transaction.atomic` for multi-step writes. Use `bulk_create` for seeds and imports.
  Use `F()` expressions for concurrent counters.
- **Raw SQL:** avoid it. If it is unavoidable, it must be parameterised. Never interpolate into
  `raw()`, `extra()` or `RawSQL`.

### Models and migrations
- Field-level validators **and** form-level validation for user input. Use
  `DecimalField(max_digits, decimal_places)` for money. Use `TextChoices` for enums.
- Add `Meta.ordering`, `__str__`, and `indexes` for columns used in common filters
  (e.g. `(user, date)`).
- Every model change ships with a migration in the same change. Migrations are reviewed like code:
  no edits to already-applied migrations, data migrations are reversible or explicitly
  `RunPython.noop` on reverse, and there are no long locks on large tables.
- `on_delete` must be an explicit, deliberate choice.

## 4. Frontend standards (templates, HTMX, Alpine, Tailwind)

- **HTMX contract:**
  - Views branch on `request.htmx` (excluding boosted requests) to return a **partial** for HTMX
    and a **full page** otherwise. Every interaction must still work without JavaScript.
  - Partials live in `templates/<app>/partials/_name.html`. Full pages extend `base.html` and
    `{% include %}` the same partial. Do not duplicate markup.
  - A successful HTMX mutation returns `204` with an `HX-Trigger` JSON header (`toast`,
    `<thing>-changed`, `close-modal`). Order matters: emit `toast` before `close-modal`.
  - A failed HTMX form submission returns `200` with the re-rendered form (HTMX does not swap
    4xx responses by default).
  - Regions that need refreshing listen with `hx-trigger="<thing>-changed from:body"` rather than
    the server knowing about the page layout.
  - Use kebab-case for event names (HTML attributes are case-insensitive).
  - Interactive elements provide feedback: `hx-indicator`, `hx-disabled-elt`, spinners.
- **CSRF:** sent globally via `hx-headers` on `<body>`. Never add `@csrf_exempt` to a
  state-changing view.
- **Alpine:** for small, local UI state only (menus, modals, toggles). Business logic and data
  fetching belong on the server. Use `x-cloak` on anything initially hidden.
- **Tailwind v4:**
  - Write class names out in full in templates or Python. Never build them dynamically (`"bg-" + color`),
    because the scanner will miss them.
  - Reusable patterns are `@utility` blocks in `assets/css/source.css`.
  - New source directories need an `@source` entry.
  - The built `static/css/tailwind.css` is a generated artifact.
- **Forms:** render with crispy (`{% crispy form %}` / `|as_crispy_field`). Widget classes come
  from the shared `INPUT_CLASSES`. Invalid fields set `aria-invalid`.
- **Templates:**
  - Never use `|safe` / `mark_safe` on user data.
  - Pass data to JS with `|json_script`, not by interpolating into `<script>`.
  - Use `|escapejs` inside JS strings.
  - Use `{% url %}` everywhere.
- **Accessibility and responsiveness:** labels or `sr-only` text on icon-only controls, `role` /
  `aria-*` on dialogs and tabs, keyboard support (Esc closes modals), and layouts checked at
  phone width (no horizontal scroll).

## 5. Security checklist (blockers if violated)
- Authentication on every non-public view. Object-level ownership checks on every lookup.
- Model state is never changed by a GET request. Destructive actions use POST behind a confirmation step.
- No secrets, credentials or `DEBUG=True` assumptions in committed code.
- Exports neutralise spreadsheet formula injection (`=`, `+`, `-`, `@` prefixes).
- No XSS sinks: `|safe`, `mark_safe`, `format_html` with unescaped user data, `innerHTML` in JS.
- No SQL built from strings. No `eval` / `pickle` on untrusted input. No open redirects
  (validate `next` with `url_has_allowed_host_and_scheme`).
- File uploads, if any, validate type and size and are never served from an executable path.

## 6. Testing standards
- Every behavioural change has tests. Bug fixes include a regression test that fails without the fix.
- Use Django `TestCase` with `setUpTestData` for shared fixtures and `force_login` for auth.
- Cover at least:
  - the happy path
  - validation failures
  - **access control** (anonymous users redirected; another user's object returns 404)
  - **both** HTMX (`HTTP_HX_REQUEST="true"`) and full-page responses, asserting template, status
    and `HX-Trigger`
- Test services and analytics functions directly, with exact `Decimal` assertions.
- Tests must be deterministic. Do not depend on the wall clock in ways that break at month or year
  boundaries; derive dates from `timezone.localdate()`.

---

## 7. Output format

Start with:

**Scope:** what was reviewed (files, commits or PR). **Gates:** the result of each command from
step 3.

Then list the findings grouped by severity. Omit empty groups.

- **🔴 Blocker:** security holes, data loss or corruption, broken behaviour, missing migrations,
  unscoped user-data access. Must be fixed before merge.
- **🟠 Should fix:** correctness risks, N+1 queries, missing tests for new behaviour, layering
  violations, HTMX/no-JS contract breaks.
- **🟡 Suggestion:** readability, naming, simplification, minor style issues not caught by tooling.
- **❓ Question:** intent is unclear. Ask rather than assume.

Write each finding as:
```
[severity] path/to/file.py:LINE: one-line summary
  Why: the concrete failure scenario or cost (inputs → wrong result).
  Fix: the specific change, with a short code snippet when it helps.
```

End with a **Verdict**: `Approve`, `Approve with suggestions` or `Request changes`, plus one
sentence of justification.

Rules for the report:
- Only report issues you verified by reading the code. Do not flag hypotheticals with no plausible trigger.
- Do not report what `ruff` or `manage.py check` already enforce, unless those gates failed.
- Prefer fewer, high-confidence findings over a long speculative list.
- Do not modify files during a review. Offer to apply fixes afterwards.
