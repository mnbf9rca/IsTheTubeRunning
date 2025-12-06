import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Auth0Provider } from '@auth0/auth0-react'
import './index.css'
import App from './App.tsx'
import { ConfigLoader } from './components/ConfigLoader'
import { useConfig } from './contexts/ConfigContext'

/**
 * AppWithAuth - Wraps app in Auth0Provider using runtime config
 * Must be inside ConfigLoader to access config via useConfig hook
 */
// Entry point file - no exports needed
// eslint-disable-next-line react-refresh/only-export-components
function AppWithAuth() {
  const config = useConfig()

  return (
    <Auth0Provider
      domain={config.auth0.domain}
      clientId={config.auth0.clientId}
      authorizationParams={{
        redirect_uri: config.auth0.callbackUrl,
        audience: config.auth0.audience,
      }}
      cacheLocation="localstorage"
      useRefreshTokens={true}
    >
      <App />
    </Auth0Provider>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigLoader>
      <AppWithAuth />
    </ConfigLoader>
  </StrictMode>
)
