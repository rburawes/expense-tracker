[//]: # (Subagents are lightweight instances of Claude Code running in a task via the Task Tool. )
[//]: # (When a subagent is running, you can actually see that the output says "Task&#40;Performing task X&#41;".)

---
description: Run parallel backend and frontend improvement audits
argument-hint: [optional focus, e.g. "performance" or "apps/orders"]
---

Run two subagents IN PARALLEL (launch both in a single step, don't wait for one to finish first).
Both are read-only: analyze and report, do not modify any files.
Optional focus from the user: $ARGUMENTS

## Subagent 1 — Backend
Scope: Django apps, models, views, serializers, services, Celery tasks, settings, migrations.
Look for:
- Security issues (auth/permission gaps, injection, secrets, unsafe settings)
- ORM performance (N+1 queries, missing indexes, unbounded querysets)
- Architecture (logic in views, duplicated code, oversized modules)
- Error handling, logging, and missing tests

## Subagent 2 — Frontend
Scope: templates, static JS/CSS, or the frontend app (e.g. `frontend/`).
Look for:
- Performance (bundle size, unnecessary re-renders, unoptimized assets)
- Accessibility (labels, alt text, contrast, keyboard navigation)
- Code quality (duplicated components, dead code, inconsistent state handling)
- UX issues (missing loading/error states, form validation)

## Each subagent returns
A list of findings, each with:
- `path/to/file:LINE`
- Issue and why it matters
- Suggested fix
- Priority: High / Medium / Low
- Effort: S / M / L

## After both finish
Combine the results into one report:
1. **Top 5 overall**: highest impact for lowest effort, across both areas
2. **Backend findings**, sorted by priority
3. **Frontend findings**, sorted by priority
4. **Cross-cutting issues**: anything spanning both (API contracts, validation duplicated on both sides)