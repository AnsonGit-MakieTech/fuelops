# Product Description: FuelOps Station Tracker

## Product Overview

FuelOps Station Tracker is a responsive gasoline station operations and profitability management system. It gives station owners and teams one place to record daily fuel activity, monitor tank inventory, control cash collections, track expenses, review discrepancies, and measure business performance.

The product replaces handwritten notebooks and disconnected spreadsheets with structured operational records, automatic calculations, approval controls, and daily and monthly reporting. It is built as a Django web application that works on desktop, tablet, and phone.

## Problem It Solves

Gasoline stations generate important data from pump meters, fuel deliveries, cash remittances, expenses, and inventory movements. When these records are maintained separately, owners cannot quickly confirm whether sales, cash, and fuel stock agree.

FuelOps connects these records so owners can detect:

- Cash shortages and overages.
- Incorrect or missing pump readings.
- Low tank inventory.
- Unexpected operating expenses.
- Differences between expected sales and actual collections.
- Profit changes caused by fuel cost and station expenses.

## Target Users

- Station owners who need operational and financial visibility.
- Managers who review daily records and approve operations.
- Staff who encode readings, collections, refills, and expenses.
- Accountants or bookkeepers who review expenses and reports.

## Implemented Capabilities

### Account Registration and Access

- New owners can create an account and register their first station without Django admin access.
- Registration creates the owner, station, and secure station membership in one transaction.
- Production-ready email verification can be enabled through environment settings.
- Password reset and verification resend flows are available.
- Owners and managers can invite managers, staff, and accountants through expiring, single-use invitation links.
- Invitation tokens are hashed, rate-limited, and bound to the invited email.
- Users can access only stations where they have an active membership.
- Existing station owners are automatically backfilled with owner memberships.

### Guided Station Setup

- A new owner is guided through creating the first fuel product, tank, pump, and supplier.
- Fuel product prices, fuel cost, tank capacity, opening inventory, reorder level, and pump meter details are captured during setup.
- Setup validates that products, tanks, and pumps belong to the same station and fuel line.
- First-time guided tours introduce each important workflow and can be replayed from the help control.

### Dashboard and Operational Monitoring

- Today's expected fuel sales.
- Today's liters sold.
- Cash shortage or overage.
- Month-to-date net profit.
- Low-stock and missing-operation alerts.
- Recent daily sales and approval status.
- Current fuel inventory by tank and product.
- Compact mobile layouts for the Today dashboard.

### Daily Sales and Pump Readings

- Create one daily operation for each station and business date.
- Record opening and closing readings for every pump.
- Automatically calculate liters sold from meter differences.
- Automatically calculate expected sales using the recorded price per liter.
- Prevent invalid closing readings and duplicate pump readings.
- Display calculated liters, expected sales, collections, and variance in real time.

### Cash Collection and Variance

- Record actual cash, bank or e-wallet transfers, card payments, and credit sales.
- Automatically calculate total collection.
- Compare collections with expected pump sales.
- Automatically identify cash shortage or overage.
- Preserve collection notes for operational review.

### Review and Approval Workflow

- Daily operations move through draft, submitted, approved, or rejected states.
- Owners and managers can approve or reject submitted operations.
- Important actions use confirmation dialogs before records are committed.
- Approving a daily operation deducts sold liters from the linked tanks once.
- Approved operations are protected from further encoding changes.
- Inventory-changing and access-related activity is recorded for audit support.

### Fuel Refill and Inventory

- Record supplier fuel deliveries, invoice references, delivered liters, and cost per liter.
- Calculate total delivery cost automatically.
- Increase the selected tank inventory when a refill is saved.
- Correctly apply only the inventory difference when an existing delivery changes.
- Monitor tank capacity, current volume, and reorder levels.
- Protect product, tank, and station relationships through validation.

### Expense Management

- Record salaries, bills, calibration, maintenance, supplies, government fees, renewals, fuel purchases, and other expenses.
- Store expense date, category, amount, vendor, reference number, payer, and notes.
- Include station expenses automatically in monthly net-profit calculations.
- Keep expense records isolated to authorized stations.

### Daily and Monthly Reports

- Filter reports by authorized station, daily date, and monthly period.
- Review daily liters sold, expected sales, collections, shortage, overage, and operation status.
- Review monthly liters, gross sales, fuel cost, gross profit, expenses, and net profit.
- View monthly cash variance and expense totals by category.
- Open source daily operations directly from report results.
- Use stacked, readable report rows on phone screens instead of wide desktop-only tables.

### Notifications and Error Handling

- Success, warning, information, and validation messages appear as slide notifications.
- Non-field form errors no longer render as raw nested error lists.
- Notifications can be dismissed and close automatically.
- Confirmation modals protect daily-sale creation, pump readings, collections, submissions, approvals, rejections, refills, expenses, and other important transactions.

## Core Operational Flow

1. An owner registers and creates a station.
2. The owner configures the first product, tank, pump, and supplier.
3. Staff create the station's daily sales operation.
4. Pump opening and closing readings are encoded.
5. Cash and non-cash collections are recorded.
6. FuelOps calculates expected sales and collection variance.
7. The operation is submitted to an owner or manager.
8. Approval finalizes the operation and deducts sold fuel from inventory.
9. Refills and operating expenses are recorded as they occur.
10. Owners review the Today dashboard and daily or monthly reports.

## System and Security Design

- Backend: Django with server-rendered templates.
- Database: SQLite for local development and PostgreSQL-ready production configuration.
- Authentication: Django sessions, password validation, verification, and password recovery.
- Authorization: station memberships with owner, manager, staff, and accountant roles.
- Tenant isolation: views, forms, reports, approvals, and object lookups are restricted to authorized stations.
- Security: CSRF protection, secure production cookie settings, invitation token hashing, throttled account actions, and environment-based secrets.
- User experience: responsive Industrial Command Center theme, reusable slide notifications, confirmation dialogs, and versioned guided tours.

## Current Product Stage

FuelOps is an implemented MVP ready for manual end-to-end testing with a real gasoline station. Core calculation, registration, invitation, permission, onboarding, notification, and workflow tests are included.

Before production launch, the project still requires deployment configuration for PostgreSQL, transactional email, static file hosting, HTTPS, backups, error monitoring, and validation against real station records.

## Business Value

FuelOps helps owners reduce manual accounting work and identify operational loss earlier. Its main value is not only record keeping; it connects liters, selling price, collections, fuel cost, expenses, and inventory so discrepancies become visible before they grow into larger losses.

The initial commercial model can support:

- Monthly subscription per station.
- One-time setup and historical data import services.
- Paid custom reports and integrations.
- Higher plans for additional users, stations, exports, alerts, and consolidated reporting.

## Future Expansion

Future features should be added only after real-station validation:

- CSV and PDF exports.
- Automated low-stock and discrepancy alerts.
- Multi-station switching and consolidated owner reporting.
- Supplier payment and accounts payable tracking.
- Renewal and compliance reminders.
- Offline-first mobile encoding.
- POS or pump-system integrations.
- Advanced audit history and business analytics.
