# FuelOps Station Tracker — Web Application Theme Guide

## 1. Theme Name

**Industrial Command Center**

This theme is designed for a gasoline station management system that tracks fuel sales, pump readings, inventory, expenses, cash variance, and profit reports.

The design should feel:

* professional
* serious
* industrial
* financial
* trustworthy
* easy to scan
* SaaS-ready

This should not look like a colorful gasoline poster. It should look like a business control dashboard for owners and managers.

---

## 2. Design Direction

The web application should use a clean admin dashboard layout with strong numbers, clear status badges, and simple forms.

Primary design style:

```text
Dark navy header/sidebar
White dashboard cards
Soft gray page background
Amber fuel accent
Green for profit/success
Red for shortage/loss/danger
Blue for informational actions
```

The goal is to make the owner quickly understand:

```text
How much was sold?
How much money was collected?
Is there a cash shortage?
Is there fuel inventory loss?
How much profit was made?
What expenses are due?
```

---

## 3. Color Palette

Use this as the main CSS color system.

```css
:root {
  /* Core Brand Colors */
  --color-primary: #0B1220;        /* Deep navy */
  --color-secondary: #111827;      /* Charcoal */
  --color-accent: #F59E0B;         /* Fuel amber */

  /* Backgrounds */
  --color-background: #F8FAFC;     /* App background */
  --color-surface: #FFFFFF;        /* Cards, tables, panels */
  --color-sidebar: #0B1220;        /* Sidebar background */
  --color-header: #111827;         /* Top header */

  /* Text */
  --color-text: #0F172A;           /* Main text */
  --color-muted: #64748B;          /* Secondary text */
  --color-light-text: #F8FAFC;     /* Text on dark background */

  /* Borders */
  --color-border: #E5E7EB;
  --color-border-dark: #334155;

  /* Status Colors */
  --color-success: #16A34A;        /* Profit, approved, healthy */
  --color-warning: #F59E0B;        /* Warning, pending, due soon */
  --color-danger: #DC2626;         /* Shortage, loss, overdue */
  --color-info: #2563EB;           /* Info, neutral action */

  /* Soft Status Backgrounds */
  --color-success-soft: #DCFCE7;
  --color-warning-soft: #FEF3C7;
  --color-danger-soft: #FEE2E2;
  --color-info-soft: #DBEAFE;
}
```

---

## 4. Typography

Recommended font combination:

```text
Main UI Font: Inter
Numeric / Meter Reading Font: IBM Plex Mono
```

Use `Inter` for general interface text.

Use `IBM Plex Mono` for:

* pump meter readings
* money values
* liters
* invoice numbers
* report totals
* calculated variance

Example:

```css
body {
  font-family: "Inter", system-ui, sans-serif;
  background: var(--color-background);
  color: var(--color-text);
}

.amount,
.liters,
.meter-reading,
.report-number {
  font-family: "IBM Plex Mono", monospace;
}
```

---

## 5. Layout Style

Use a SaaS admin dashboard layout.

Desktop layout:

```text
Left Sidebar
Top Header
Main Content Area
Dashboard Cards
Tables
Forms
Reports
```

Mobile layout:

```text
Top Header
Simplified Content
Bottom Navigation
Large Input Forms
Quick Action Buttons
```

---

## 6. Sidebar Structure

Recommended sidebar menu:

```text
MAIN
- Dashboard
- Daily Sales
- Pump Readings

OPERATIONS
- Fuel Inventory
- Fuel Refill
- Tanks
- Pumps / Nozzles

FINANCE
- Expenses
- Cash Remittance
- Profit Report

REPORTS
- Daily Report
- Monthly Report
- Inventory Variance
- Cash Variance
- Renewal Report

SYSTEM
- Users
- Station Settings
- Audit Logs
```

Sidebar design rules:

* Use dark navy background.
* Use white text for active navigation.
* Use muted gray text for inactive navigation.
* Use amber left border or amber icon for active menu.
* Group menu items clearly by section.
* Keep icons simple and professional.

---

## 7. Header Design

The top header should contain:

```text
Page title
Breadcrumb
Date filter
Station selector
Notification icon
User profile dropdown
```

Example:

```text
Dashboard / ABC Gasoline Station / June 2026
```

Header style:

```css
.app-header {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  height: 64px;
}
```

---

## 8. Dashboard Card Design

Dashboard cards should be simple, clear, and numeric.

Recommended cards:

```text
Today’s Gross Sales
Today’s Liters Sold
Cash Shortage / Overage
Monthly Net Profit
Premium Stock
Diesel Stock
Pending Expenses
Upcoming Renewals
```

Card style:

```css
.dashboard-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 20px;
}

.dashboard-card-label {
  color: var(--color-muted);
  font-size: 14px;
  font-weight: 500;
}

.dashboard-card-value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 8px;
}
```

Card behavior:

* Use green for positive profit.
* Use red for shortage or loss.
* Use amber for warnings.
* Use mono font for large values.

---

## 9. Status Badge Design

Use badges heavily because this app needs quick scanning.

Statuses:

```text
Submitted
Approved
Pending
Reopened
Paid
Unpaid
Overdue
Low Stock
Healthy
Variance Detected
Shortage
Overage
```

Badge style:

```css
.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 600;
}

.badge-success {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.badge-warning {
  background: var(--color-warning-soft);
  color: #92400E;
}

.badge-danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.badge-info {
  background: var(--color-info-soft);
  color: var(--color-info);
}
```

---

## 10. Button Design

Primary button:

```css
.btn-primary {
  background: var(--color-primary);
  color: white;
  border-radius: 12px;
  padding: 10px 16px;
  font-weight: 600;
}
```

Accent button:

```css
.btn-accent {
  background: var(--color-accent);
  color: #111827;
  border-radius: 12px;
  padding: 10px 16px;
  font-weight: 700;
}
```

Danger button:

```css
.btn-danger {
  background: var(--color-danger);
  color: white;
  border-radius: 12px;
  padding: 10px 16px;
  font-weight: 600;
}
```

Button usage:

```text
Primary: Save, Submit, Approve
Accent: Generate Report, Add Refill, New Sale
Danger: Delete, Reopen, Mark Shortage
Info: Export PDF, Export Excel, View Details
```

---

## 11. Form Design

Forms must be simple and large enough for mobile use.

Use this style for inputs:

```css
.form-control {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 16px;
  background: white;
}

.form-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: 6px;
}
```

Important form screens:

```text
Daily Sales Encoding
Pump Meter Reading
Cash Remittance
Fuel Refill
Expense Entry
Tank Inventory Check
Permit Renewal Entry
```

Mobile form rule:

```text
One major action per screen.
Avoid too many columns.
Use large inputs.
Use clear labels.
Show calculated results immediately.
```

---

## 12. Table Design

Tables should be clean, readable, and professional.

Table style:

```css
.table-wrapper {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  overflow: hidden;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  background: #F1F5F9;
  color: var(--color-muted);
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  padding: 12px;
}

.table td {
  padding: 14px 12px;
  border-top: 1px solid var(--color-border);
  font-size: 14px;
}
```

Recommended table columns for daily sales:

```text
Date
Shift
Fuel Type
Opening Meter
Closing Meter
Liters Sold
Expected Sales
Collected
Variance
Status
Action
```

---

## 13. Dashboard Visual Hierarchy

Priority order:

```text
1. Critical alerts
2. Today’s sales and collection
3. Fuel inventory status
4. Monthly profit
5. Expenses and renewals
6. Reports and history
```

Dashboard should not show everything at once.

Recommended dashboard sections:

```text
Top Metrics
Owner Alerts
Fuel Movement
Cash Variance
Monthly Performance
Recent Activity
```

---

## 14. Alerts Design

Alerts should be visible but not too noisy.

Alert examples:

```text
Diesel stock is below reorder level.
Cash remittance is short by ₱850.
Premium tank variance detected: -42 liters.
Business permit renewal is due in 24 days.
Daily sales report has not been submitted.
```

Alert style:

```css
.alert {
  border-radius: 14px;
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  background: var(--color-surface);
}

.alert-danger {
  border-color: #FCA5A5;
  background: var(--color-danger-soft);
  color: #991B1B;
}

.alert-warning {
  border-color: #FCD34D;
  background: var(--color-warning-soft);
  color: #92400E;
}
```

---

## 15. Page Design Rules

### Dashboard Page

Must show:

```text
Today’s Sales
Today’s Liters Sold
Cash Variance
Monthly Net Profit
Premium Stock
Diesel Stock
Critical Alerts
Recent Entries
```

### Daily Sales Page

Must focus on:

```text
Date
Shift
Pump
Nozzle
Fuel Type
Opening Meter
Closing Meter
Price per Liter
Calculated Liters Sold
Calculated Expected Sales
Actual Collection
Variance
Submit Button
```

### Fuel Inventory Page

Must show:

```text
Fuel Type
Tank
Current Stock
Reorder Level
Expected Stock
Actual Dipstick Reading
Variance
Status
```

### Expenses Page

Must show:

```text
Expense Category
Amount
Due Date
Paid Date
Payment Status
Receipt Attachment
Approved By
```

### Reports Page

Must include:

```text
Date range filter
Station filter
Report type filter
Export PDF
Export Excel
Print view
```

---

## 16. Mobile Web Design

Mobile pages should be designed for staff encoding, not full admin work.

Mobile bottom navigation:

```text
Today
Sales
Refill
Expense
Alerts
```

Mobile design rules:

```text
Use large buttons.
Use single-column forms.
Keep dashboard simple.
Avoid complex tables.
Use cards instead of tables.
Show only the staff’s needed actions.
```

Mobile staff dashboard:

```text
Open Today’s Shift
Encode Pump Reading
Encode Cash Collection
Add Expense
View Submission Status
```

---

## 17. Desktop Web Design

Desktop is for owners, managers, and accountants.

Desktop should prioritize:

```text
Reports
Tables
Filters
Approvals
Audit Logs
Exporting
Profit analysis
Inventory variance
```

Desktop layout rules:

```text
Use sidebar navigation.
Use multi-column metric cards.
Use report tables.
Use date range filters.
Use compact but readable spacing.
```

---

## 18. Icons

Use simple line icons.

Recommended icon style:

```text
Lucide Icons
Heroicons
Tabler Icons
```

Recommended icons:

```text
Dashboard: gauge
Daily Sales: receipt
Pump Readings: fuel
Inventory: database
Fuel Refill: truck
Expenses: wallet
Reports: file-text
Cash Remittance: banknote
Users: users
Settings: settings
Audit Logs: shield-check
Alerts: triangle-alert
```

Do not use cartoon gasoline icons.

---

## 19. Spacing and Radius

Use consistent spacing.

```css
:root {
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-2xl: 32px;
}
```

Recommended:

```text
Cards: 16px radius
Buttons: 12px radius
Inputs: 12px radius
Badges: full pill radius
Page padding: 24px desktop, 16px mobile
```

---

## 20. Design Do’s

Do:

```text
Use clean white cards.
Use dark navy for authority.
Use amber as fuel/profit accent.
Use mono font for numbers.
Use badges for statuses.
Use tables for reports.
Use cards for mobile.
Use clear warning colors.
Use simple icons.
Prioritize readability.
```

---

## 21. Design Don’ts

Do not:

```text
Use bright red/yellow as the main background.
Use flame graphics everywhere.
Use cartoon fuel pump illustrations.
Use too many gradients.
Use playful fonts.
Use small inputs on mobile.
Overload staff screens with analytics.
Mix too many colors.
Make the app look like a gas station tarpaulin.
```

The product should look like a serious business tool, not a marketing poster.

---

## 22. Landing Page Theme

Landing page should use the same premium industrial style.

Hero message:

```text
Control fuel, cash, expenses, and profit from one dashboard.
```

Supporting message:

```text
A gasoline station management system for tracking daily sales, pump readings, fuel inventory, expenses, cash variance, and monthly profit reports.
```

Landing page sections:

```text
Hero Section
Problem Section
Dashboard Preview
Core Features
Owner Benefits
Pricing Plans
Call to Action
```

Feature highlights:

```text
Daily Sales Tracking
Pump Meter Reading
Fuel Inventory Control
Cash Shortage Detection
Expense Monitoring
Monthly Profit Reports
Renewal Reminders
Audit Logs
```

---

## 23. Final Theme Summary

Theme name:

```text
Industrial Command Center
```

Best visual identity:

```text
Dark navy
Fuel amber
White cards
Soft gray background
Clean tables
Strong numbers
Professional status badges
Mobile-friendly encoding screens
```

The design should communicate:

```text
This system helps gasoline station owners control fuel, cash, expenses, and profit.
```
