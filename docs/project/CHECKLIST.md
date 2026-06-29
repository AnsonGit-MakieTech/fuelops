DONE - Reviewed project description and build task roadmap.
DONE - Start Phase 1 and Phase 2 MVP foundation.
DONE - Configure Django settings for environment variables.
DONE - Create core database models for station operations.
DONE - Register core models in Django admin.
DONE - Add seed command for default roles, fuel products, and expense categories.
DONE - Create initial database migration.
DONE - Run Django system checks.
DONE - Add core calculation tests.
DONE - Run initial tests.
DONE - Apply database migrations locally.
DONE - Seed local default data.
DONE - Build authentication pages and base layout.
DONE - Build dashboard page.
DONE - Build daily operation encoding workflow.
DONE - Build fuel delivery and expense forms.
DONE - Build daily and monthly reports.
DONE - Run post-frontend Django system check.
DONE - Run post-frontend tests.
DONE - Render smoke test auth, dashboard, operations, fuel refill, expenses, and reports.
DONE - Review first 5 frontend build tasks.
DONE - Replace inline message block with slide notification alerts for success/error feedback.
DONE - Add confirmation modals for important transactions before submit, approve, reject, fuel refill save, expense save, and inventory-changing actions.
DONE - Run notification and confirmation modal verification checks.
DONE - Design the first-use guided workflow system.
DONE - Add versioned per-user guide progress persistence and API.
DONE - Build the reusable responsive guided tour interface and replay control.
DONE - Guide dashboard, daily sales, pump readings, cash collection, review actions, fuel refills, expenses, and reports.
DONE - Add guided workflow tests and run full verification.
DONE - Seed the local Main Station, fuel products, tanks, pumps, roles, suppliers, and expense categories for first use.
DONE - Design secure owner registration, station membership, email verification, onboarding, and team invitations.
DONE - Add station membership models and backfill existing station owners.
DONE - Enforce station membership across all views, forms, reports, approvals, and object lookups.
DONE - Build owner registration with atomic station creation and email verification.
DONE - Build guided station setup for fuel products, tanks, and pumps.
DONE - Build password reset and verification resend flows.
DONE - Build invite-only manager, staff, and accountant registration.
DONE - Add registration rate limits, audit events, and cross-station security tests.
DONE - Improve Dashboard and Reports layouts on phone screens.
DONE - Replace non-field form error blocks with slide notifications.
DONE - Run registration, invitation, tenancy, mobile markup, notification, migration, and Django verification checks.
DONE - Audit implemented routes and workflows against the project requirements.
TODO - Build station settings for adding and editing multiple fuel products, tanks, pumps, and station details.
TODO - Make suppliers station-scoped and add supplier management pages.
TODO - Add a dedicated tank inventory page with delivery and adjustment history.
TODO - Build the inventory adjustment workflow with owner or manager approval.
TODO - Enforce role permissions for owner, manager, staff, and accountant across navigation, views, forms, and reports.
TODO - Enforce valid daily-operation state transitions and require readings and collection before approval.
TODO - Prevent approved-operation changes at the model and admin layers and add a controlled reopen workflow.
TODO - Add rejection notes input and correction workflow.
TODO - Recalculate collection variance when pump readings change.
TODO - Snapshot fuel cost on each pump reading and exclude draft or rejected operations from official profit reports.
TODO - Add edit and controlled archive flows for readings, deliveries, expenses, and other financial records.
TODO - Complete audit logs for approvals, rejections, inventory changes, edits, archives, and access changes.
TODO - Add team member role changes, suspension, reactivation, and last-owner protection.
TODO - Add active-station switching for users assigned to multiple stations.
TODO - Add report date ranges, per-product totals, delivery cost, and inventory movement reporting.
TODO - Add the planned dashboard and reporting API endpoints or remove them from the MVP contract.
TODO - Configure production PostgreSQL, email, static files, HTTPS, backups, and error monitoring.
TODO - Run manual end-to-end QA and validate calculations with one real station.
