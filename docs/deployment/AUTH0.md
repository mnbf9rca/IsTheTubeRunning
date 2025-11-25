# Auth0 Configuration

## Tenant

**Domain**: `tfl-alerts.uk.auth0.com`

## Production Applications

### Frontend (Single Page Application)

**Name**: IsTheTubeRunning Production
**Type**: Single Page Application
**Client ID**: `i14e7UaeWhkXoqHiqK40j8bPyEsl5mm3`

**Required URIs**:
- **Allowed Callback URLs**: `https://isthetube.cynexia.com/callback`
- **Allowed Logout URLs**: `https://isthetube.cynexia.com`
- **Allowed Web Origins**: `https://isthetube.cynexia.com`
- **Allowed Origins (CORS)**: `https://isthetube.cynexia.com`

### Backend (API)

**Name**: IsTheTubeRunning Production
**Type**: Custom API
**Audience**: `https://isthetube.cynexia.com`

## Configuration Files

### Frontend (`frontend/config/config.production.json`)
```json
{
  "auth0": {
    "domain": "tfl-alerts.uk.auth0.com",
    "clientId": "i14e7UaeWhkXoqHiqK40j8bPyEsl5mm3",
    "audience": "https://isthetube.cynexia.com",
    "callbackUrl": "https://isthetube.cynexia.com/callback"
  }
}
```

### Backend (`backend/.env.production`)
```bash
AUTH0_DOMAIN=tfl-alerts.uk.auth0.com
AUTH0_API_AUDIENCE=https://isthetube.cynexia.com
AUTH0_ALGORITHMS=RS256
```

## Authentication Flow

1. User clicks login on frontend
2. React app redirects to Auth0 hosted login page (`tfl-alerts.uk.auth0.com`)
3. User authenticates with Auth0
4. Auth0 redirects back to `https://isthetube.cynexia.com/callback` with authorization code
5. Frontend exchanges code for JWT access token
6. Frontend includes token in API requests (Authorization: Bearer header)
7. Backend validates token signature and claims (audience, issuer, expiry)

## Other Applications (Can Be Ignored)

The following applications exist in the Auth0 tenant but are not used for production deployment:
- **IsTheTubeRunning dev** (dev environment)
- **Custom API Client** (auto-generated, unused)
- **Test Applications** (M2M, testing only)

Only the Production SPA and Production API are required for the application to function.

## Verification

Check Auth0 configuration in dashboard:
1. Login to Auth0 dashboard → `tfl-alerts.uk.auth0.com` tenant
2. Navigate to Applications → "IsTheTubeRunning Production" (SPA)
3. Verify Settings → Application URIs match production domain
4. Navigate to APIs → "IsTheTubeRunning Production"
5. Verify Audience is `https://isthetube.cynexia.com`

## Important Notes

- **No client secret needed**: Backend only validates JWT tokens and doesn't authenticate to Auth0
- **No M2M authentication**: Application uses standard SPA + API pattern
- **Audience must match exactly**: Backend `AUTH0_API_AUDIENCE` must match API audience in Auth0 dashboard
- **Domain includes region**: Use `tfl-alerts.uk.auth0.com`, not `tfl-alerts.auth0.com`
