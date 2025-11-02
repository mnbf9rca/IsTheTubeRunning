# Auth0 Setup Guide

This guide walks you through setting up Auth0 for the TfL Disruption Alert System.

## Prerequisites

- A free Auth0 account (sign up at https://auth0.com)
- Admin access to your Auth0 tenant

## Step 1: Create Auth0 Account and Tenant

1. Go to https://auth0.com and click "Sign Up"
2. Choose a tenant name (e.g., `tfl-alerts-dev`)
   - This will become part of your domain: `tfl-alerts-dev.auth0.com`
3. Select your region (choose closest to your users)
4. Complete the registration process

## Step 2: Create an API

Auth0 APIs represent your backend and define the audience for JWTs.

1. In the Auth0 Dashboard, navigate to **Applications > APIs**
2. Click **"Create API"**
3. Configure the API:
   - **Name**: `TfL Alerts API`
   - **Identifier**: `https://api.isthetube.com` (or your domain)
     - This becomes your `AUTH0_API_AUDIENCE` value
     - Must be a valid URI (doesn't need to be accessible)
   - **Signing Algorithm**: `RS256`
4. Click **"Create"**

### API Settings

After creation, configure these settings:

1. Go to **Settings** tab
2. **Token Expiration**: Set to `86400` seconds (24 hours)
3. **Allow Offline Access**: Enable if you need refresh tokens
4. **Enable RBAC**: Enable (we'll use this for admin roles later)
5. **Add Permissions in the Access Token**: Enable
6. Click **"Save"**

## Step 3: Create a Single Page Application

This is for your React frontend.

1. Navigate to **Applications > Applications**
2. Click **"Create Application"**
3. Configure the application:
   - **Name**: `TfL Alerts Frontend`
   - **Type**: Select **"Single Page Application"**
4. Click **"Create"**

### Application Settings

Configure the following settings in the **Settings** tab:

#### Application URIs

For **local development**:
- **Allowed Callback URLs**: `http://localhost:5173/callback`
- **Allowed Logout URLs**: `http://localhost:5173`
- **Allowed Web Origins**: `http://localhost:5173`
- **Allowed Origins (CORS)**: `http://localhost:5173`

For **production** (add these when deploying):
- **Allowed Callback URLs**: `https://yourdomain.com/callback`
- **Allowed Logout URLs**: `https://yourdomain.com`
- **Allowed Web Origins**: `https://yourdomain.com`
- **Allowed Origins (CORS)**: `https://yourdomain.com`

#### Advanced Settings

1. Go to **Advanced Settings > OAuth**
2. **JsonWebToken Signature Algorithm**: `RS256`
3. **OIDC Conformant**: Enable
4. Click **"Save Changes"**

### Note Your Credentials

From the application settings page, copy these values:
- **Domain**: (e.g., `tfl-alerts-dev.auth0.com`)
- **Client ID**: (a long alphanumeric string)

You'll need these for your frontend configuration.

## Step 4: Configure Backend Environment Variables

Update your `backend/.env` file with the following values:

```bash
# Auth0 Settings
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_API_AUDIENCE=https://api.isthetube.com
AUTH0_ALGORITHMS=RS256
```

Replace:
- `your-tenant.auth0.com` with your actual Auth0 domain
- `https://api.isthetube.com` with your API identifier from Step 2

## Step 5: Test JWT Validation (Optional)

You can test your Auth0 setup before implementing the frontend:

### Using Auth0 Dashboard

1. Go to **Applications > APIs > TfL Alerts API**
2. Click the **"Test"** tab
3. Copy the test access token
4. Use curl to test your API:

```bash
# Store your token in an environment variable for security
export AUTH0_TEST_TOKEN="your_token_from_auth0_dashboard"
curl -H "Authorization: Bearer $AUTH0_TEST_TOKEN" http://localhost:8000/api/v1/auth/me
```

### Using Auth0 Authentication API Explorer

1. Go to **Applications > Applications > TfL Alerts API (Test Application)**
2. Note: Auth0 automatically creates a test application for your API
3. Use this for testing token generation in development

## Step 6: Set Up Universal Login (Optional Customization)

Auth0 provides a hosted login page by default. You can customize it later.

1. Navigate to **Branding > Universal Login**
2. Choose a template or customize the HTML/CSS
3. Preview and save your changes

## Step 7: Configure Social Connections (Optional)

To allow users to sign in with Google, GitHub, etc.:

1. Navigate to **Authentication > Social**
2. Enable the providers you want (e.g., Google, GitHub)
3. Configure each provider with OAuth credentials
4. Test the connection

## Step 8: Set Up Admin Roles (Phase 9)

For admin functionality (Phase 9), you'll configure roles:

1. Navigate to **User Management > Roles**
2. Create a role named `admin`
3. Add permissions from your API
4. Assign users to the admin role manually or via rules

## Local Development with Mock JWT

For local development without Auth0, the backend supports mock JWT mode:

1. Set `DEBUG=true` in your `.env` file
2. The backend will accept mock JWTs generated locally
3. No Auth0 calls are made in debug mode
4. See `backend/app/core/auth.py` for mock JWT implementation

## Troubleshooting

### "Invalid token" errors

- Verify `AUTH0_DOMAIN` matches your tenant domain exactly
- Ensure `AUTH0_API_AUDIENCE` matches your API identifier
- Check that `AUTH0_ALGORITHMS` is set to `RS256`
- Verify the token hasn't expired

### CORS errors

- Add your frontend URL to **Allowed Origins (CORS)** in application settings
- Ensure the URL exactly matches (including port number)
- Check that your FastAPI CORS middleware includes Auth0 domain

### "Audience claim missing" errors

- Verify you're requesting tokens with the correct audience
- Check that your frontend is passing the audience parameter to Auth0

## Security Best Practices

1. **Never commit Auth0 credentials** to version control
2. **Use different tenants** for development, staging, and production
3. **Rotate secrets regularly** in production
4. **Enable MFA** for your Auth0 dashboard account
5. **Monitor Auth0 logs** for suspicious activity
6. **Set token expiration** appropriately (24 hours is reasonable)

## Production Checklist

Before deploying to production:

- [ ] Create a production Auth0 tenant
- [ ] Configure production callback URLs
- [ ] Set up custom domain (optional but recommended)
- [ ] Enable MFA for all admin accounts
- [ ] Configure rate limiting rules
- [ ] Set up Auth0 anomaly detection
- [ ] Configure email templates for user verification
- [ ] Test the full authentication flow
- [ ] Set up monitoring and alerting
- [ ] Document all Auth0 configuration

## Additional Resources

- [Auth0 React Quickstart](https://auth0.com/docs/quickstart/spa/react)
- [Auth0 FastAPI Integration](https://auth0.com/docs/quickstart/backend/python)
- [Auth0 JWT Validation](https://auth0.com/docs/secure/tokens/json-web-tokens/validate-json-web-tokens)
- [Auth0 Dashboard](https://manage.auth0.com)

## Next Steps

Once Auth0 is configured:

1. Test JWT validation with the backend (`GET /api/v1/auth/me`)
2. Proceed to Phase 10 to implement the frontend authentication flow
3. Test the full signup/login/logout flow
4. Add error handling for auth failures

## Support

If you encounter issues:

1. Check Auth0 logs in the dashboard (**Monitoring > Logs**)
2. Review FastAPI logs for JWT validation errors
3. Use Auth0 Community Forum for Auth0-specific questions
4. Check the project README for backend-specific troubleshooting
