import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Auth0Provider } from '@auth0/auth0-react'
import './index.css'
import App from './App.tsx'
import { config } from './lib/config'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
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
  </StrictMode>
)
