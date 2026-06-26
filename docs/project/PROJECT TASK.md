# FuelOps Station Tracker - Project Task Plan

## 1. Project Goal

Build a responsive web application that helps gasoline station owners monitor fuel sales, pump readings, fuel inventory, expenses, cash collections, shortages/overages, and profitability from one system.

The MVP should replace notebooks and scattered Excel files with a reliable daily operations tracker.

## 2. Finished Project Criteria

The project is considered finished when:

- Staff can log in and encode daily pump readings, sales collections, expenses, and fuel deliveries.
- Owners/managers can review daily operations, approve records, and see discrepancies.
- The system automatically calculates liters sold, expected sales, actual collections, shortages, overages, gross profit, expenses, and net profit.
- Fuel inventory updates from deliveries, sales, and manual adjustments.
- Daily and monthly reports are available on desktop, tablet, and mobile.
- The app has authentication, role-based access, validation, audit-friendly records, and production-ready deployment settings.

## 3. MVP Strategy

Build a Django-first web app using server-rendered pages before adding complex SPA behavior. This keeps development fast, deployment simple, and operating cost low.

Recommended stack:

- Backend: Django
- Frontend: Django templates, HTML, CSS, minimal JavaScript
- Database: SQLite for local development, PostgreSQL for production
- Auth: Django authentication and groups
- Deployment: Render, Railway, Fly.io, VPS, or similar low-cost hosting
- Reports: HTML tables first, CSV/PDF export later

Do not build a full SaaS platform first. Build a single-station MVP with data models that can later support multiple stations.

## 4. Target Users

- Gasoline station owners
- Station managers
- Cashiers or daily encoders
- Accountants/bookkeepers

## 5. Core User Roles

- Owner: full access, reports, approvals, user management
- Manager: operations access, approvals, inventory, reports
- Staff: encode readings, deliveries, expenses, and collections
- Accountant: view/export financial reports

## 6. Phase 1 - Project Foundation

### Tasks

- Confirm Django project runs locally.
- Add environment configuration using `.env`.
- Move secrets out of `settings.py`.
- Configure local and production database settings.
- Create base template layout.
- Add static files structure.
- Add responsive CSS foundation.
- Configure authentication pages:
  - login
  - logout
  - password change
- Create role/group setup command or seed script.
- Add basic navigation by role.

### Acceptance Criteria

- `python manage.py runserver` starts without errors.
- Users can log in and log out.
- App has a usable responsive base layout.
- Secrets are not hardcoded for production.

## 7. Phase 2 - Database Design

### Core Models

Create these models in `api/models.py` or split into a dedicated operations app later if the project grows.

### Station

Fields:

- name
- address
- owner
- timezone
- is_active
- created_at
- updated_at

Purpose:

- Supports the current single-station MVP.
- Keeps the system ready for future multi-station SaaS expansion.

### FuelProduct

Fields:

- station
- name
- code
- current_price_per_liter
- cost_per_liter
- is_active

Examples:

- Premium
- Diesel

### Tank

Fields:

- station
- fuel_product
- name
- capacity_liters
- current_volume_liters
- reorder_level_liters
- is_active

### Pump

Fields:

- station
- fuel_product
- tank
- name
- meter_number
- is_active

### DailyOperation

Fields:

- station
- operation_date
- encoded_by
- approved_by
- status
- notes
- created_at
- updated_at

Status options:

- draft
- submitted
- approved
- rejected

### PumpReading

Fields:

- daily_operation
- pump
- opening_reading
- closing_reading
- liters_sold
- price_per_liter
- expected_sales

Rules:

- closing_reading must be greater than or equal to opening_reading.
- liters_sold = closing_reading - opening_reading.
- expected_sales = liters_sold * price_per_liter.

### CashCollection

Fields:

- daily_operation
- expected_sales
- actual_cash
- gcash_or_bank_transfer
- card_payments
- credit_sales
- shortage
- overage
- notes

Rules:

- total_collection = cash + transfer + card + credit sales.
- variance = total_collection - expected_sales.
- positive variance is overage.
- negative variance is shortage.

### FuelDelivery

Fields:

- station
- fuel_product
- tank
- supplier
- delivery_date
- liters_delivered
- cost_per_liter
- total_cost
- invoice_number
- received_by
- notes

Rules:

- delivery increases tank inventory.
- total_cost = liters_delivered * cost_per_liter.

### Supplier

Fields:

- name
- contact_person
- phone
- email
- address
- is_active

### ExpenseCategory

Fields:

- name
- description
- is_active

Default categories:

- Salaries
- Bills
- Calibration
- Fuel Purchase
- Maintenance
- Government Fees
- License Renewal
- Supplies
- Other

### Expense

Fields:

- station
- category
- expense_date
- amount
- vendor
- reference_number
- paid_by
- encoded_by
- notes

### InventoryAdjustment

Fields:

- station
- tank
- adjustment_date
- adjustment_type
- liters
- reason
- encoded_by
- approved_by

Adjustment types:

- gain
- loss
- correction

### AuditLog

Fields:

- user
- action
- model_name
- object_id
- old_value
- new_value
- created_at

Purpose:

- Track sensitive changes such as approved reports, inventory adjustments, and deleted records.

### Acceptance Criteria

- Models migrate successfully.
- Django admin can create and manage core records.
- Calculated fields are generated consistently.
- Records are tied to station and user where needed.

## 8. Phase 3 - Business Logic

### Tasks

- Add calculation service functions for:
  - liters sold
  - expected sales
  - total collections
  - shortage
  - overage
  - gross sales
  - fuel cost
  - gross profit
  - total expenses
  - net profit
  - tank inventory movement
- Add model validation for impossible values.
- Prevent editing approved daily operations unless owner/manager reopens them.
- Prevent duplicate daily operation records for the same station and date.
- Add automatic tank deduction from approved pump readings.
- Add automatic tank increase from fuel deliveries.
- Add audit logging for approvals and inventory changes.

### Acceptance Criteria

- Calculations match manual examples.
- Invalid readings cannot be saved.
- Approved records are protected.
- Inventory changes are traceable.

## 9. Phase 4 - Backend Views And APIs

### Recommended MVP Approach

Use Django views and templates first. Add JSON API endpoints only where they reduce friction, such as dynamic calculations or dashboard widgets.

### Pages

- Login page
- Dashboard
- Daily operations list
- Create/edit daily operation
- Pump readings form
- Cash collections form
- Fuel deliveries list and form
- Tank inventory page
- Expenses list and form
- Suppliers page
- Reports page
- User management page
- Settings page

### Optional API Endpoints

- `GET /api/dashboard/summary/`
- `GET /api/reports/daily/?date=YYYY-MM-DD`
- `GET /api/reports/monthly/?month=YYYY-MM`
- `POST /api/calculate/pump-reading/`
- `POST /api/calculate/cash-variance/`

### Acceptance Criteria

- Staff can complete the daily encoding workflow.
- Owners/managers can review and approve records.
- Pages enforce role permissions.
- API endpoints validate input and return predictable JSON.

## 10. Phase 5 - Frontend Experience

### UX Priorities

- Fast daily encoding
- Clear discrepancy visibility
- Mobile-friendly forms
- Owner dashboard that shows business health quickly

### Dashboard Widgets

- Today sales
- Today liters sold
- Today cash shortage/overage
- Current tank inventory
- Low inventory alerts
- Monthly gross sales
- Monthly expenses
- Monthly net profit

### Key Screens

### Daily Operations Screen

Must show:

- date
- status
- total liters sold
- expected sales
- actual collections
- shortage/overage
- approval state

### Daily Encoding Screen

Must include:

- pump opening reading
- pump closing reading
- auto-calculated liters sold
- auto-calculated expected sales
- collection breakdown
- expenses for the day
- notes
- submit for approval button

### Inventory Screen

Must show:

- tank name
- fuel product
- current liters
- capacity
- reorder level
- latest deliveries
- latest adjustments

### Reports Screen

Must show:

- daily report
- monthly report
- fuel sales summary
- expense summary
- profit summary
- variance report

### Acceptance Criteria

- App is usable on desktop, tablet, and mobile.
- Staff can encode a daily operation in under 5 minutes.
- Owners can understand daily profit/loss without opening spreadsheets.

## 11. Phase 6 - Reports

### Daily Report

Include:

- operation date
- liters sold per fuel product
- expected sales
- actual collections
- shortage/overage
- expenses
- gross profit
- net profit
- inventory movement

### Monthly Report

Include:

- total liters sold
- total gross sales
- total fuel cost
- gross profit
- total expenses by category
- net profit
- total shortages
- total overages
- delivery cost summary

### Variance Report

Include:

- cash variance by date
- fuel inventory variance
- suspicious high-loss days
- repeated shortage patterns

### Acceptance Criteria

- Reports can be filtered by date range.
- Reports match database records.
- Reports are clear enough for owner/accountant review.

## 12. Phase 7 - Admin, Permissions, And Security

### Tasks

- Add role-based access checks.
- Restrict staff from viewing owner-only profit reports.
- Restrict delete actions for financial records.
- Add soft-delete or archive behavior for sensitive records.
- Add CSRF protection on all forms.
- Add server-side validation for all calculations.
- Add login-required protection to all private pages.
- Add audit logs for:
  - approvals
  - rejected daily operations
  - inventory adjustments
  - edited readings
  - deleted expenses
- Add production security settings:
  - `DEBUG=False`
  - secure secret key
  - allowed hosts
  - secure cookies
  - CSRF trusted origins

### Acceptance Criteria

- Unauthorized users cannot access restricted pages.
- Sensitive edits are auditable.
- Production settings pass Django deployment checks.

## 13. Phase 8 - Testing

### Unit Tests

Test:

- pump reading calculations
- cash variance calculations
- fuel delivery inventory increase
- approved sales inventory deduction
- expense totals
- monthly profit calculation
- duplicate daily operation prevention
- permission rules

### Manual QA Checklist

- Create owner account.
- Create staff account.
- Create station.
- Create premium and diesel fuel products.
- Create tanks and pumps.
- Encode daily readings.
- Encode actual collections.
- Add fuel delivery.
- Add expenses.
- Submit daily operation.
- Approve daily operation.
- Check dashboard totals.
- Check daily report.
- Check monthly report.
- Test mobile layout.

### Acceptance Criteria

- Core calculation tests pass.
- Main user workflow works from login to report review.
- No critical broken pages.

## 14. Phase 9 - Deployment

### Tasks

- Add `requirements.txt`.
- Add production environment variables.
- Configure PostgreSQL.
- Configure static file serving with WhiteNoise or platform equivalent.
- Run migrations on production.
- Create first owner account.
- Configure backups.
- Configure error logging.
- Add deployment notes to `README.md`.

### Environment Variables

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DATABASE_URL`
- `CSRF_TRUSTED_ORIGINS`

### Acceptance Criteria

- Production app is accessible through HTTPS.
- Static files load correctly.
- Database persists records.
- Admin account can manage the system.
- Backup path is documented.

## 15. Phase 10 - Launch And Validation

### Tasks

- Test with one real gasoline station.
- Import or manually encode 7 to 30 days of historical data.
- Compare reports against existing notebook/Excel records.
- Identify workflow friction.
- Fix the top 5 issues before adding new features.
- Collect pricing feedback from owner/manager.

### Success Metrics

- Daily encoding takes less than 5 minutes.
- Owner checks dashboard at least 3 times per week.
- Reports reduce manual accounting work.
- Shortage/overage detection is trusted by the owner.
- Owner is willing to pay monthly for continued use.

## 16. Monetization Plan

### MVP Pricing

- Single station: PHP 999 to PHP 2,499 per month
- Setup/import assistance: PHP 3,000 to PHP 10,000 one-time
- Custom reports or integrations: quoted separately

### Future SaaS Pricing

- Basic: daily sales, inventory, expenses, reports
- Pro: approvals, audit logs, exports, alerts
- Multi-Station: branch comparison, owner dashboard, advanced permissions

Do not underprice if the system helps detect losses. A single avoided shortage can justify the subscription.

## 17. Future Features After MVP

Add only after the first station validates the workflow:

- CSV/PDF exports
- Automated low-stock alerts
- License and renewal reminders
- Multi-station support
- Advanced audit trail
- Bookkeeper/accountant access
- AI business insights
- Supplier payment tracking
- Customer credit/accounts receivable
- Offline-first mobile encoding
- POS or pump integration

## 18. Suggested Build Order

1. Foundation and authentication
2. Data models and admin
3. Pump reading calculations
4. Daily operation workflow
5. Cash collection variance
6. Fuel delivery and inventory movement
7. Expense tracking
8. Dashboard
9. Daily and monthly reports
10. Permissions and audit logs
11. Tests
12. Production deployment
13. Real station validation

## 19. Brutal Feedback

- The project becomes valuable only if calculations are trusted. Prioritize correctness over fancy UI.
- Do not build SaaS billing, AI insights, or multi-tenant complexity before one real station uses the MVP.
- The biggest business value is discrepancy detection: cash shortage, fuel loss, unexpected expense spikes, and low inventory.
- The frontend should be simple and fast. Gas station staff need encoding speed, not a complicated dashboard.
- Reports must match how owners already think about the business: liters, cash, expenses, shortages, and profit.

## 20. Immediate Next Task

Start with Phase 1 and Phase 2:

1. Configure environment settings.
2. Create the core database models.
3. Register models in Django admin.
4. Add migrations.
5. Seed default roles, expense categories, and fuel products.
6. Test creating one full daily operation manually through admin.
