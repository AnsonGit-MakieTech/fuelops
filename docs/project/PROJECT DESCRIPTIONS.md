# Product Description: FuelOps Station Tracker

## Product Overview

FuelOps Station Tracker is a responsive, multi-station gasoline station operations, inventory, cash-control, and profitability system. It gives station owners and authorized teams one place to configure fuel infrastructure, encode daily sales, reconcile collections, track fuel movement, control expenses, approve sensitive transactions, and generate formal reports.

FuelOps replaces handwritten notebooks and disconnected spreadsheets with structured records, automatic calculations, role-based workflows, audit history, and tenant-isolated reporting. It is implemented as a Django web application designed for repeated use on desktop, tablet, and phone.

## Problem It Solves

Gasoline stations generate connected data from pump meters, tank inventory, supplier deliveries, collections, expenses, and approvals. When these records are maintained separately, owners cannot quickly confirm whether fuel sold, money collected, and inventory remaining agree.

FuelOps connects these records to reveal:

- Cash shortages and overages.
- Missing, duplicate, or incorrect pump readings.
- Low tank inventory and unexplained inventory movement.
- Fuel delivery cost and supplier history.
- Operating expenses by category.
- Gross and net profit changes.
- Unapproved, corrected, archived, or reopened transactions.
- User access and operational changes that require an audit trail.

## Target Users

- Station owners who need operational, inventory, and financial control.
- Managers who supervise configuration, teams, approvals, and corrections.
- Staff who encode daily operations, deliveries, expenses, and inventory requests.
- Accountants or bookkeepers who manage expenses and generate reports.
- Multi-station operators who need secure station switching from one account.

## Implemented Capabilities

### Registration, Authentication, and Onboarding

- Owners can register an account and create their first station without Django admin access.
- Registration creates the owner, station, and owner membership atomically.
- Configurable email verification, verification resend, login, logout, and password reset flows are available.
- Account and invitation actions are rate-limited.
- New owners receive guided station setup for the first fuel product, tank, pump, supplier, and opening inventory.
- Versioned guided tours cover important workflows and can be replayed from the help control.

### Multi-Station Access and Team Management

- Users can belong to multiple stations through active station memberships.
- A session-backed station selector changes the active station without allowing cross-station access.
- Owners and managers can invite managers, staff, and accountants through expiring, single-use links.
- Invitation tokens are hashed and bound to the invited email.
- Authorized administrators can change member roles, suspend access, and reactivate suspended members.
- Last-owner protection prevents a station from losing its final active owner.
- Membership, invitation, and active-station changes are audit logged.

### Role-Based Permissions

- **Owner:** full station, catalog, team, operation, delivery, expense, inventory, approval, and reporting access.
- **Manager:** operational access equivalent to an owner, without implicit ownership of the station.
- **Staff:** daily operations, deliveries, expenses, inventory viewing, and inventory-adjustment requests.
- **Accountant:** expense management and reporting.
- Navigation, views, forms, approvals, object lookups, and APIs enforce the same permission rules.

### Station and Fuel Catalog Management

- Add and edit station details.
- Configure multiple fuel products with selling price and current cost per liter.
- Configure tanks with product, capacity, current volume, and reorder level.
- Configure pumps with product, tank, and meter number.
- Maintain a station-scoped supplier directory.
- Validate product, pump, tank, supplier, and station relationships.
- Seed standard roles, expense categories, and optional starter station data.

### Dashboard and Operational Monitoring

- Today's liters sold and expected sales.
- Today's collections, shortage, and overage.
- Month-to-date expenses and net profit.
- Current inventory by tank and fuel product.
- Low-stock and missing-daily-operation alerts.
- Recent daily operations and approval status.
- Role-aware dashboard actions and responsive phone layouts.

### Daily Sales and Pump Readings

- Create one active daily operation per station and business date.
- Record opening and closing meter readings for each pump.
- Calculate liters sold and expected sales automatically.
- Reject closing readings below opening readings.
- Prevent duplicate active readings for the same pump and operation.
- Snapshot fuel cost on every reading so historical profit does not change when catalog cost changes.
- Recalculate collection variance whenever an editable reading changes or is archived.

### Cash Collection and Variance

- Record cash, bank or e-wallet transfers, card payments, and credit sales.
- Calculate total collections automatically.
- Compare collections with expected sales.
- Calculate shortage and overage automatically.
- Preserve collection notes for review and audit support.

### Controlled Review, Correction, and Archive Workflow

- Daily operations move through draft, submitted, approved, or rejected states.
- An operation must contain at least one active reading and a cash collection before submission.
- Owners and managers can approve or reject submitted operations.
- Rejection requires a reason and returns the operation to a controlled correction flow.
- Approval deducts sold liters from linked tanks exactly once.
- Submitted and approved operations are locked against direct changes.
- Approved operations can be reopened with a required reason; reopening reverses the prior inventory deduction.
- Readings, draft or rejected operations, deliveries, and expenses use controlled archive flows instead of destructive removal.
- Archiving a delivery reverses its inventory increase; archived records remain available for audit history and are excluded from official totals.
- Important actions use confirmation dialogs before submission.

### Fuel Deliveries and Inventory Control

- Record delivery date, product, tank, supplier, liters, cost per liter, invoice, receiver, and notes.
- Calculate total delivery cost automatically.
- Increase tank inventory when a delivery is saved.
- Apply only the inventory difference when a delivery is corrected.
- Reverse the inventory increase when a delivery is archived.
- View current tank balances, capacities, reorder levels, and low-stock state.
- Review paginated delivery and adjustment histories.

### Inventory Adjustments

- Staff, managers, and owners can request gain, loss, or correction adjustments with a reason.
- Requests remain pending until an owner or manager approves them.
- Approved adjustments update tank inventory once and become immutable.
- Adjustment requests and approvals are audit logged.

### Expense and Category Management

- Record date, category, amount, vendor, reference number, payer, notes, and encoder.
- Include active expenses in monthly net-profit calculations.
- Use shared system categories or owner/manager-controlled station categories.
- Keep custom categories isolated to their station.
- Edit or deactivate station categories without changing historical expenses.
- Correct or archive expenses while preserving audit history.

### Reports and Report Generation

- Filter approved, non-archived data by authorized station, date range, and monthly period.
- Review liters sold, expected sales, collections, shortage, overage, fuel cost, gross profit, expenses, and net profit.
- View per-product liters, sales, fuel cost, and gross profit.
- Review delivery liters, delivery cost, expense totals by category, and inventory movements.
- Generate seven fixed reports:
  - Comprehensive Operations Report.
  - Daily Sales and Reconciliation.
  - Monthly Performance Report.
  - Inventory Movement Report.
  - Fuel Delivery and Purchase Report.
  - Expense Breakdown Report.
  - Cash Variance Report.
- Export reports as branded PDF or CSV, or open a print-ready report.
- Include station, period, generator, generation time, and report totals in generated output.
- Record report generation in the audit log.

### APIs and Calculation Endpoints

- `GET /api/dashboard/summary/`
- `GET /api/reports/daily/`
- `GET /api/reports/monthly/`
- `POST /api/calculate/pump-reading/`
- `POST /api/calculate/cash-variance/`
- API responses validate inputs and enforce authenticated station permissions.

### Notifications and Guided User Experience

- Success, warning, information, and validation feedback uses slide notifications.
- Raw nested non-field error blocks are converted into readable notifications.
- Notifications can be dismissed and close automatically.
- Confirmation modals protect approvals, rejections, archives, inventory changes, access changes, and other important actions.
- Desktop navigation, mobile navigation, responsive tables, and guided tours follow the FuelOps Industrial Command Center theme.

### Performance and Data Fetching

- Growing tables use database-backed pagination instead of fixed large fetches.
- Pagination covers daily sales, deliveries, expenses, inventory histories, reports, team members, suppliers, and expense categories.
- Independent tables preserve their own page state.
- Daily-operation totals use database annotations to avoid per-row aggregate queries.
- Monthly report totals and per-product performance use grouped database aggregation.
- Delivery and inventory movement reporting uses pageable database queries rather than loading every record into application memory.

## Core Operational Flow

1. An owner registers and creates a station.
2. The owner configures products, tanks, pumps, suppliers, categories, and team access.
3. Staff record deliveries and request inventory corrections when required.
4. Staff create the station's daily operation.
5. Pump readings and cash or non-cash collections are encoded.
6. FuelOps calculates liters, expected sales, collection variance, and historical fuel cost.
7. The operation is submitted to an owner or manager.
8. The reviewer approves it or rejects it with a correction reason.
9. Approval deducts sold fuel from inventory and includes the operation in official reports.
10. Expenses, approved adjustments, and delivery costs feed monthly performance reporting.
11. Owners and accountants review or export reports.
12. Authorized users correct, reopen, or archive records through controlled workflows when necessary.

## System and Security Design

- **Backend:** Django with server-rendered templates and focused JSON endpoints.
- **Database:** SQLite for local development and environment-driven `DATABASE_URL` support for deployment databases.
- **Authentication:** Django sessions, password validation, verification, invitations, and password recovery.
- **Authorization:** station memberships with owner, manager, staff, and accountant roles.
- **Tenant isolation:** forms, queries, reports, exports, APIs, approvals, and object lookups are station scoped.
- **Transaction safety:** inventory-changing approvals, corrections, reopens, deliveries, and archives use database transactions and row locking where required.
- **Historical accuracy:** approved-only reporting, fuel-cost snapshots, immutable applied adjustments, and non-destructive archives protect prior results.
- **Auditability:** approvals, rejections, corrections, archives, inventory changes, report generation, invitations, and access changes create audit events.
- **Web security:** CSRF protection, password validators, secure production cookie defaults, optional SSL redirect, hashed invitation tokens, and environment-based secrets.
- **Static and media support:** configured static collection and media paths with branded FuelOps assets.

## Current Product Stage

FuelOps is a feature-complete MVP with the core station workflow implemented from registration through report export. The current automated suite contains 42 passing tests covering calculations, workflow transitions, tenancy, registration, permissions, archives, inventory reversal, report generation, APIs, and pagination. The project checklist also records the real-station end-to-end validation as completed.

The application can be evaluated locally as a working station operations system. A public production launch still requires operators to provision and verify the actual deployment environment, including the database driver and PostgreSQL service, transactional email provider, production web server, static-file delivery, HTTPS termination, scheduled backups, and error-monitoring service.

## Business Value and Monetization

FuelOps reduces manual reconciliation work and helps station owners identify cash, fuel, inventory, and expense discrepancies earlier. Its advantage is the connection between operational quantities and financial outcomes: liters sold, price, collections, historical fuel cost, expenses, inventory, and approvals are evaluated as one workflow.

Practical commercial options include:

- Monthly subscription per active station.
- Tiered pricing by station count and team size.
- One-time onboarding, configuration, and historical data-import services.
- Higher plans for consolidated multi-station reporting, scheduled reports, alerts, and integrations.
- Paid custom reports, accounting exports, POS integrations, and pump-system integrations.

## Current Boundaries and Future Expansion

Future work should be driven by real-station demand rather than adding a generic feature builder. High-value candidates are:

- Consolidated owner reporting across multiple stations.
- Scheduled email delivery of reports.
- Automated low-stock, shortage, and discrepancy alerts.
- Supplier payments and accounts payable.
- License, calibration, and compliance reminders.
- Offline-capable mobile encoding for unstable connections.
- POS, accounting, and pump-controller integrations.
- Optional two-factor authentication and stronger enterprise access policies.
- Generic report customization only after fixed reports are validated commercially.
