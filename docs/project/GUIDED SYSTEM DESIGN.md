# FuelOps Guided System Design

## 1. Real Problem

First-time station owners, managers, and staff must understand operational workflows without training calls or a separate manual. FuelOps contains inventory-changing and finance-changing actions, so unclear onboarding can cause incorrect sales, stock, expense, or approval records.

## 2. Target Users

- Owner: monitors the station, reviews variance, and approves daily operations.
- Manager: encodes or reviews daily operations and controls inventory movements.
- Staff: records pump readings, collections, refills, and expenses.
- Accountant: reviews expenses and reports.

## 3. Best Strategy

Use short contextual tours that start once on the user's first visit to each important workflow. Store progress on the server per user and tour version so guidance is consistent across devices. Keep a help icon on guided pages so users can replay a tour at any time.

The system must skip steps whose target is hidden or unavailable. This prevents staff users from seeing guidance for owner-only approval controls and keeps tours valid when a page has no records yet.

## 4. Core Features

- Automatic first-visit tour for each important workflow.
- Spotlight and focused step dialog with previous, next, skip, and finish actions.
- Responsive positioning for desktop and mobile.
- Keyboard support: Escape dismisses the tour; focus remains in the tour controls.
- Per-user, per-tour, per-version completion or dismissal state.
- Replay button available on every guided page.
- Missing and permission-restricted targets are skipped safely.
- Version increments allow revised tours to appear once after a major workflow change.

## 5. System Design

### Architecture

1. `frontend/guides.py` owns valid tour keys and the current tour version.
2. `frontend/context_processors.py` maps the active Django route to a tour key and checks the current user's progress.
3. `frontend/models.py` stores one progress record per user, tour key, and version.
4. `frontend/views.py` exposes an authenticated POST endpoint for completion and dismissal updates.
5. `static/js/guided-tours.js` owns tour definitions, rendering, positioning, replay, and progress submission.
6. Django templates expose stable `data-guide-target` anchors around real controls and result areas.
7. `templates/base.html` renders the shared tour layer and replay button once.

### Data Model

`GuidedTourProgress`

- `user`: authenticated Django user.
- `guide_key`: stable workflow identifier.
- `version`: positive integer for tour revisions.
- `status`: `completed` or `dismissed`.
- `created_at` and `updated_at`: audit timestamps.
- Unique constraint: `user + guide_key + version`.

### User Flow

1. User opens a guided page.
2. Context processor maps the route to its guide key and version.
3. If no progress exists, the browser starts the tour after the page is ready.
4. The tour resolves visible targets and skips unavailable steps.
5. Finishing saves `completed`; skipping or pressing Escape saves `dismissed`.
6. Future visits do not auto-start the same version.
7. The help icon replays the tour without deleting progress.

### API / Integration Flow

`POST /guides/progress/`

Request JSON:

```json
{
  "guide_key": "daily-operation",
  "version": 1,
  "status": "completed"
}
```

The endpoint requires an authenticated session and CSRF token. It rejects unknown guide keys, unsupported versions, invalid states, malformed JSON, and non-POST requests. A valid request updates or creates the user's progress record.

### Guided Workflow Coverage

- Dashboard: primary actions, operational metrics, alerts, recent sales, and inventory.
- Daily sales list: create action and operation history.
- New daily sale: station/date selection and confirmed creation.
- Daily operation: totals, pump readings, cash collection, and submit/approve/reject controls.
- Fuel refill list: create action and delivery history.
- New fuel refill: delivery fields and confirmed inventory update.
- Expense list: create action and expense history.
- New expense: expense fields and confirmed report impact.
- Reports: filters, profitability metrics, daily results, cash variance, and expense breakdown.

### Deployment Notes

- Apply the new frontend migration during deployment.
- No background service or external onboarding dependency is required.
- Static collection must include `static/js/guided-tours.js` and the updated stylesheet.
- Tour definitions are code-deployed and versioned with the application.

### Security Considerations

- Require authentication and Django CSRF protection for progress updates.
- Use a server-side allowlist for guide keys and versions.
- Never accept a user ID from the client; always use `request.user`.
- Tour content must not reveal controls or permissions absent from the rendered page.
- Guidance never bypasses form validation or transaction confirmation modals.

## 6. Execution Steps

1. Add the progress model and migration.
2. Add route-to-tour context and the progress endpoint.
3. Add the reusable guide markup, CSS, and JavaScript.
4. Add stable target anchors to every completed workflow.
5. Add backend tests and browser checks at desktop and mobile widths.
6. Mark checklist items complete only after verification passes.

## 7. Monetization

Guided onboarding reduces setup and training cost per station, improves activation, and makes a self-serve subscription practical. Advanced role-specific onboarding and onboarding analytics can later support higher-priced multi-station plans.

## 8. Scaling Plan

- Increment a tour version when a workflow materially changes.
- Add role-specific tour variants only when user behavior proves they are needed.
- Add onboarding analytics only after multiple paying stations create enough usage data.
- Move tour definitions to managed content only if non-developers must update them frequently.

## 9. Brutal Feedback

A large help center is premature for the MVP and will become stale. Contextual tours solve the immediate activation problem with lower operating cost. Tours must stay short; if a workflow needs more than five or six steps, the workflow itself is probably too complex and should be simplified.
