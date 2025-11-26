# Runtime Config Implementation Progress

## Goal
Convert from build-time environment variables to runtime JSON config loading with **hostname-based auto-detection**.
**Benefit:** ONE Docker image works in ALL environments with ZERO configuration - just works based on hostname.

## Completed ✅

### Phase 1: Core Infrastructure
- [x] `src/lib/configLoader.ts` - Async fetch, hostname detection, and validation
- [x] `src/contexts/ConfigContext.tsx` - React Context + useConfig() hook
- [x] `src/components/ConfigLoader.tsx` - Loading/error UI wrapper
- [x] `src/lib/config.ts` - Updated to export only types and validation

### Phase 2: Update Config Consumers
- [x] `src/main.tsx` - Wrapped in ConfigLoader, uses useConfig
- [x] `src/lib/api.ts` - Added setApiBaseUrl() function, called from ConfigLoader
- [x] `src/contexts/BackendAvailabilityContext.tsx` - Uses useConfig() hook

### Phase 3: Docker Configuration
- [x] `Dockerfile` - Removed all ARG/ENV for config, simplified build
- [x] `public/config.json` - Single file with ALL environments (development + production)
- [x] `deploy/docker-compose.prod.yml` - Removed volume mount (config is baked into image)

### Phase 4: Testing
- [x] Local dev test: Config.json served correctly with both environments ✅
- [x] Docker build test: Image builds successfully ✅
- [x] Docker run test: Config.json in image with all environments ✅
- [x] Grep test: Only 2 "localhost" in React library code, NOT in our config ✅

## Key Implementation Details

### Hostname-Based Auto-Detection
**How it works:**
1. Browser fetches `/config.json` (contains all environments)
2. JavaScript detects hostname using `window.location.hostname`
3. Selects appropriate config:
   - `localhost`, `127.0.0.1`, `192.168.*`, `10.*`, `*.local` → **development**
   - `isthetube.cynexia.com` or anything else → **production**
4. App initializes with selected config

**Benefits:**
- ✅ Zero configuration needed
- ✅ Same Docker image for all environments
- ✅ No volume mounts required
- ✅ No environment variables needed
- ✅ Works in development AND production automatically

### Config Structure
```json
{
  "development": {
    "api": { "baseUrl": "http://localhost:8000/api/v1" },
    "auth0": { /* dev config */ }
  },
  "production": {
    "api": { "baseUrl": "https://isthetube.cynexia.com/api/v1" },
    "auth0": { /* prod config */ }
  }
}
```

### Config Consumer Pattern
**Before:**
```typescript
import { config } from '@/lib/config'
const url = config.api.baseUrl
```

**After:**
```typescript
import { useConfig } from '@/contexts/ConfigContext'
const config = useConfig()
const url = config.api.baseUrl
```

### api.ts Special Case
`src/lib/api.ts` exports utility functions, not React components. Cannot use hooks directly.

**Solution:** Module-level variable with setter function
```typescript
let API_BASE_URL = ''
export function setApiBaseUrl(baseUrl: string): void {
  API_BASE_URL = baseUrl
}
```
Called from ConfigLoader after config loads

## File Change Summary

### New Files (4)
- `src/lib/configLoader.ts` - Fetches config.json and detects environment from hostname
- `src/contexts/ConfigContext.tsx` - React Context provider for global config access
- `src/components/ConfigLoader.tsx` - Loading/error UI wrapper component
- `public/config.json` - Single config file with all environments (dev + prod)

### Modified Files (6)
- `src/lib/config.ts` - Removed env var reading, now only exports types and validation
- `src/main.tsx` - Wrapped app in ConfigLoader
- `src/lib/api.ts` - Added setApiBaseUrl() for runtime config injection
- `src/contexts/BackendAvailabilityContext.tsx` - Uses useConfig() hook
- `Dockerfile` - Removed all ARG/ENV build arguments (simplified)
- `deploy/docker-compose.prod.yml` - Removed volume mount (config is baked into image)

## Testing Results

- [x] `npm run dev` works (development config) ✅
- [x] `npm run build` creates bundle without our hardcoded config ✅
- [x] Docker build succeeds ✅
- [x] Config.json baked into image with all environments ✅
- [x] Only 2 "localhost" occurrences in bundle (React library code, not our config) ✅
- [ ] End-to-end test: Deploy and verify production detection (pending deployment)
- [ ] Auth0 integration works (uses config values) (pending deployment)
- [ ] API calls work (uses config.api.baseUrl) (pending deployment)
- [ ] Backend availability check works (pending deployment)

## Architecture Benefits

1. **Client-side environment detection** - Happens in browser based on hostname
2. **No server-side processing needed** - Busybox httpd just serves static files
3. **Single source of truth** - One config.json with all environments
4. **Zero configuration deployment** - No volume mounts, no env vars, no build args
5. **Instant config changes** - Just rebuild and redeploy (no per-environment builds)

## Issues Resolved

- Issue #263: ✅ Docker compose production configuration fixed
- Issue #265: ✅ Localhost URLs no longer embedded in production builds
- Issue #266: ✅ Frontend configuration properly externalized
