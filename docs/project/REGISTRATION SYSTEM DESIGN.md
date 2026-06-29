# FuelOps Registration System Design

## 1. Real Problem

FuelOps currently requires an administrator to create accounts and station data. A new station owner cannot register, verify ownership of an account, configure a station, or invite staff from the application.

Public registration is not safe with the current station lookup. `frontend/views.py` falls back to the first active station when a user does not own one. If public signup is added before station access is isolated, a new account could see or modify another station's data.

Registration therefore requires two connected systems:

1. Secure account creation and verification.
2. Explicit user membership in a station, enforced by every view, form, and object lookup.

## 2. Target Users

- New station owner creating the first account and station.
- Manager invited by an owner to operate a station.
- Staff member invited to encode daily records.
- Accountant invited for financial records and reports.
- Existing user accepting access to another station in a future multi-station plan.

## 3. Best Strategy

### Public Entry

Allow public registration only for a station owner. Owner registration creates a user, the first station, and an owner membership in one database transaction.

### Team Entry

Manager, staff, and accountant accounts are invite-only. This prevents strangers from choosing privileged roles or attaching themselves to a station.

### Authentication Choice

Keep Django's existing `User` model. Changing `AUTH_USER_MODEL` after migrations and production data exist creates unnecessary migration risk. Normalize the email to lowercase and store it in both `username` and `email` for new self-service accounts. Existing username-based accounts remain valid.

### Authorization Choice

Use a station membership role as the authorization source. Django groups may remain temporarily for admin compatibility, but they must not decide access to tenant data because groups are global rather than station-specific.

## 4. Core Features

### MVP

- Owner registration with name, email, password, station name, and address.
- Unique, normalized email validation.
- Email verification before operational access.
- Atomic creation of user, station, and owner membership.
- First-station setup flow for fuel products, tanks, and pumps.
- Role-based station membership.
- Secure login, logout, and password reset.
- Invite-only manager, staff, and accountant registration.
- Expiring, single-use invitation links.
- Guided first-use flow from registration to the dashboard.
- Audit entries for registration, verification, invitations, and membership changes.

### Not In MVP

- Social login.
- SMS verification.
- Open registration for staff roles.
- Subscription billing during signup.
- Custom organizations, franchises, or complex multi-company hierarchies.

## 5. System Design

### Architecture

Use Django server-rendered forms and session authentication.

```text
Browser
  -> Registration / verification / invitation views
  -> Django forms and password validators
  -> Atomic registration service
  -> User + Station + StationMembership
  -> Verification or invitation email
  -> Station setup wizard
  -> Guided operational dashboard
```

Recommended ownership:

- `frontend/forms.py`: registration, verification resend, invitation, and setup forms.
- `frontend/views.py`: HTML request handling only.
- `frontend/services/registration.py`: registration and invitation transactions.
- `frontend/urls.py`: account, invitation, and setup routes.
- `api/models.py`: station membership and invitation business records.
- `templates/registration/`: register, verification, invitation, and password reset pages.
- `templates/frontend/setup/`: station setup steps.

Business transactions must live in a service module instead of large view functions. This keeps account creation atomic and testable.

### Data Models

#### StationMembership

Path: `api/models.py`

Fields:

- `station`: foreign key to `Station`.
- `user`: foreign key to Django `User`.
- `role`: `owner`, `manager`, `staff`, or `accountant`.
- `status`: `active`, `suspended`, or `revoked`.
- `invited_by`: nullable foreign key to `User`.
- `joined_at`: timestamp.
- `created_at` and `updated_at`: timestamps.

Constraints:

- Unique `station + user` membership.
- Only active memberships grant station access.
- The station owner must always have an active owner membership.

#### StationInvitation

Path: `api/models.py`

Fields:

- `station`: target station.
- `email`: normalized invited email.
- `role`: manager, staff, or accountant.
- `token_hash`: SHA-256 hash of the invitation token.
- `invited_by`: owner or manager.
- `expires_at`: expiration timestamp.
- `accepted_at`: nullable timestamp.
- `revoked_at`: nullable timestamp.
- `created_at`: timestamp.

Rules:

- Store only the token hash; send the raw token once by email.
- Tokens expire after 48 hours.
- Accepted, expired, or revoked invitations cannot be reused.
- Owners cannot be created by invitation in the MVP.

#### UserProfile

Path: `frontend/models.py`

Fields:

- `user`: one-to-one relation to `User`.
- `email_verified_at`: nullable timestamp.
- `terms_accepted_at`: timestamp.
- `terms_version`: accepted policy version.
- `onboarding_completed_at`: nullable timestamp.

Do not duplicate names, email, or password fields already owned by Django `User`.

### Station Access Contract

Replace the current first-active-station fallback with explicit membership queries.

```python
def stations_for_user(user):
    if user.is_superuser:
        return Station.objects.filter(is_active=True)
    return Station.objects.filter(
        memberships__user=user,
        memberships__status=StationMembership.Status.ACTIVE,
        is_active=True,
    ).distinct()
```

Required enforcement:

- Dashboard and list views query only `stations_for_user(request.user)`.
- Detail views include the allowed station queryset in `get_object_or_404`.
- Forms receive the current user or allowed station queryset.
- Pump, tank, fuel product, delivery, expense, and report choices are station-scoped.
- Approve and reject permissions use the membership role for that operation's station.
- A user with no active membership is redirected to registration/setup or a no-access page.

### Owner Registration Flow

1. User opens `GET /accounts/register/`.
2. User submits name, email, password, station name, address, and terms acceptance.
3. Server normalizes email and validates uniqueness and password strength.
4. In one `transaction.atomic()` block, the service:
   - creates an inactive Django user;
   - creates the station with that user as owner;
   - creates an active owner membership;
   - creates the user profile;
   - writes an audit record.
5. Server sends a verification link.
6. User opens the link and the server validates Django's signed activation token.
7. Server marks the account active and stores `email_verified_at`.
8. User signs in and is redirected to station setup.
9. User creates at least one fuel product, tank, and pump.
10. Setup completes and the existing guided dashboard tour starts.

If email delivery fails, the database remains valid and the user can request another verification message. Do not store raw passwords or verification tokens.

### Team Invitation Flow

1. Owner or manager opens the team page.
2. User submits email and an allowed role.
3. Server verifies that the inviter has permission for the station.
4. Server creates a hashed, expiring invitation and sends the raw link.
5. Invitee opens `GET /accounts/invitations/<token>/accept/`.
6. A new invitee sets their name and password; an existing user signs in.
7. Server verifies the token and email, then creates or activates membership atomically.
8. Invitation is marked accepted and cannot be reused.
9. User enters the station with role-specific navigation and guided tours.

### Routes

```text
GET|POST /accounts/register/
GET      /accounts/verify/<uidb64>/<token>/
GET|POST /accounts/verification/resend/
GET|POST /accounts/password-reset/
GET|POST /accounts/invitations/<token>/accept/
GET|POST /setup/station/
GET|POST /setup/fuel-products/
GET|POST /setup/tanks-pumps/
GET      /team/
POST     /team/invitations/
POST     /team/invitations/<id>/revoke/
POST     /team/members/<id>/role/
POST     /team/members/<id>/suspend/
```

No public JSON API is required for the MVP. Django forms, CSRF protection, redirects, and slide notifications match the current application architecture.

### Email Integration

- Development: Django console email backend.
- Production: Postmark, Amazon SES, Resend, or another transactional provider.
- Configure sender and provider through environment variables.
- Email links use an explicit public base URL from settings.
- Verification responses remain generic to prevent account enumeration.

### Deployment Notes

Required environment variables:

```text
DEFAULT_FROM_EMAIL
PUBLIC_APP_URL
EMAIL_BACKEND
EMAIL_HOST
EMAIL_PORT
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
EMAIL_USE_TLS
REGISTRATION_ENABLED
```

Deployment order:

1. Deploy membership models while public registration remains disabled.
2. Backfill an owner membership for every existing `Station.owner`.
3. Update and test all station-scoped views and forms.
4. Configure production email and HTTPS.
5. Enable owner registration.
6. Enable invitations after owner registration is stable.

### Security Considerations

- Never enable public registration before membership scoping is complete.
- Require CSRF protection on every POST form.
- Use Django password validators and session rotation after login.
- Normalize emails with `strip().lower()` and enforce case-insensitive uniqueness in application validation.
- Return generic messages for login, reset, resend, and invitation lookup failures.
- Rate-limit registration, login, password reset, verification resend, and invitation acceptance.
- Use HTTPS, secure cookies, HSTS, and trusted origins in production.
- Hash invitation tokens and make them single-use.
- Prevent users from changing their own role or removing the last station owner.
- Write audit logs for membership and role changes.
- Scope every object lookup to an authorized station; hiding navigation is not authorization.
- Do not auto-create sample financial or inventory transactions during registration.

## 6. Execution Steps

### Phase 1: Tenancy Safety

1. Add `StationMembership` and migration.
2. Backfill owner memberships for existing stations.
3. Replace `get_current_station()` fallback.
4. Scope all views, forms, reports, and object lookups by membership.
5. Replace global group approval checks with station-role checks.
6. Add cross-station access tests.

### Phase 2: Owner Registration

1. Add `UserProfile` and registration service.
2. Add owner registration form and page using the FuelOps theme.
3. Add email verification and resend flow.
4. Add login-by-email compatibility and password reset.
5. Add registration rate limits and audit records.

### Phase 3: Station Onboarding

1. Add station setup forms for products, tanks, and pumps.
2. Require one valid product-to-tank-to-pump chain before completion.
3. Add guided setup steps and progress persistence.
4. Redirect completed users to the dashboard.

### Phase 4: Team Invitations

1. Add invitation model and secure token service.
2. Add team member and invitation screens.
3. Add invitation emails and acceptance flow.
4. Enforce owner/manager invitation permissions.
5. Test expiration, revocation, reuse, and existing-account acceptance.

## 7. Acceptance Criteria

- A new owner can register without Django admin access.
- Registration creates exactly one user, station, and owner membership atomically.
- Duplicate or case-variant emails are rejected.
- Unverified accounts cannot access operational pages.
- A verified owner completes station setup and reaches the dashboard.
- Staff cannot self-select a station or privileged role.
- Invitations expire, are single-use, and are bound to the invited email.
- Every operational query is limited to the user's active station memberships.
- Cross-station list, detail, edit, report, and approval requests are denied.
- Password reset works without revealing whether an account exists.
- Registration, verification, and permission tests pass.

## 8. Monetization

- Start the station's trial when email verification succeeds, not when the form is first submitted.
- Keep payment collection out of the first registration release.
- Capture subscription conversion after the owner completes setup and records real operations.
- Limit team seats by plan later; do not hardcode seat billing into membership models.
- Track activation events: verified account, station configured, first daily sale, first approved operation, and first report viewed.

## 9. Scaling Plan

- MVP tenant boundary: station membership.
- Multi-station plan: one user can hold memberships in multiple stations and select the active station.
- Franchise/company plan: add an `Organization` above stations only after paying customers require consolidated ownership and billing.
- Move email sending to a background queue only when synchronous delivery affects response time or reliability.
- Add SSO and enterprise identity only for contracted customers.

## 10. Brutal Feedback

- The current first-active-station fallback is a data isolation defect, not an onboarding inconvenience. Public registration must remain disabled until it is removed everywhere.
- Global Django groups are insufficient for a multi-station SaaS because a manager role must belong to a specific station.
- Registration without email verification and password reset is not production-ready.
- A long signup form will reduce activation. Collect only account and first-station data, then move inventory configuration into guided setup.
- Billing during signup adds friction before FuelOps has delivered value. Validate activation and usage first.
