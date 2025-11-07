# Contact Verification & User Management

## Code-based Verification

### Status
Active

### Context
Email and SMS verification could use different mechanisms (email links vs SMS codes), but this creates inconsistent UX and more complex frontend logic.

### Decision
Use numeric verification codes for both email and SMS. Users enter 6-digit code in the same UI flow regardless of contact type.

### Consequences
**Easier:**
- Consistent UX for both email and SMS
- Single verification flow in frontend
- Same backend logic for both contact types
- Mobile-friendly (easy to type 6 digits)

**More Difficult:**
- Email links might be more familiar to some users
- Users must manually copy code from email (vs clicking link)

---

## Simple Verification Codes

### Status
Active

### Context
Could use HOTP/TOTP for verification codes (cryptographically secure), but these are overkill for contact verification and harder to implement. Industry standard for email/SMS verification is simple random codes.

### Decision
Generate random 6-digit numeric codes for verification. 15-minute expiry. Industry standard for contact verification.

### Consequences
**Easier:**
- Simple to implement (no HOTP/TOTP library needed)
- Easy to type (6 digits)
- Industry standard (users are familiar)
- Good enough security with rate limiting

**More Difficult:**
- Not cryptographically secure (but acceptable for contact verification)
- Could theoretically brute force (but rate limiting prevents this)

---

## Separate Verification Flow

### Status
Active

### Context
Could auto-send verification code immediately when contact is added, but this prevents users from adding multiple contacts before verifying. Also, users might want to add a contact but verify it later.

### Decision
Users add contacts first (returns unverified contact), then explicitly request verification code via separate API call. Allows batch contact addition before verification.

### Consequences
**Easier:**
- Better UX (add multiple contacts, then verify in batch)
- Users control when codes are sent (not automatic)
- Clearer separation of "add" vs "verify" actions
- Can re-send verification code without re-adding contact

**More Difficult:**
- Two-step process instead of one
- More API calls (add contact, then verify)
- Need to track verification state per contact

---

## Privacy-Focused User Deletion

### Status
Active

### Context
GDPR and privacy regulations require ability to delete user data. However, hard deletes make analytics impossible. Need balance between privacy and analytics.

### Decision
`DELETE /admin/users/{id}` implements GDPR-style data minimization while preserving analytics. Deletes PII (email_addresses, phone_numbers, verification_codes), anonymizes `external_id` to `"deleted_{user_id}"`, clears `auth_provider`, deactivates all routes (stops alerts), sets `deleted_at` timestamp. Preserves `notification_logs` and route structure for aggregated analytics (user_id becomes anonymous identifier). Transaction-based to ensure atomicity.

### Consequences
**Easier:**
- GDPR compliant (PII is deleted)
- Analytics still possible (aggregated metrics work)
- Audit trail preserved (`deleted_at` timestamp)
- Atomic operation (transaction ensures all-or-nothing)

**More Difficult:**
- More complex deletion logic (multiple tables, specific order)
- Anonymized users remain in database (soft delete)
- Must distinguish "deleted user" from "active user" in queries
- Cannot fully purge user (some records remain for analytics)

---

## Explicit NotificationPreference Deletion on Anonymization

### Status
Active

### Context
When anonymizing users, notification preferences could be preserved (they link to routes), but these preferences are meaningless without active contacts. Could rely on CASCADE DELETE, but this makes deletion implicit and harder to understand.

### Decision
Explicitly delete `NotificationPreference` records during user anonymization instead of relying on implicit CASCADE behavior.

### Consequences
**Easier:**
- Code clarity - deletion is explicit for future maintainers
- KISS/YAGNI - no need for placeholder contacts or schema changes
- Data minimization - preference configurations (intent) without active users are not actionable
- Analytics sufficiency - `NotificationLog` preserves actual behavior data (what was sent, success rates)

**More Difficult:**
- Must remember to delete preferences explicitly (can't rely on CASCADE)
- More lines of code in deletion logic
