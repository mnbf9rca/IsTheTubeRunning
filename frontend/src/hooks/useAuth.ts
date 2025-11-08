import { useAuth0 } from '@auth0/auth0-react'

/**
 * Custom hook that wraps Auth0's useAuth0 hook for cleaner access
 * and easier mocking in tests.
 */
export const useAuth = () => {
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    loginWithRedirect,
    logout: auth0Logout,
    getAccessTokenSilently,
  } = useAuth0()

  const login = async () => {
    // Clear stale OAuth transaction state before starting new login flow
    // This prevents "Invalid state" errors when reopening browser with stale transactions
    // Auth0 stores transaction state (nonce, state, code_verifier) with key: a0.spajs.txs.{clientId}
    try {
      // Clear transaction state (not cleared by logout)
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key?.startsWith('a0.spajs.txs.')) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach((key) => localStorage.removeItem(key))

      // Also clear any token cache (belt and suspenders)
      await auth0Logout({ openUrl: false })
    } catch (error) {
      // If clearing fails, continue anyway - loginWithRedirect will handle it
      console.warn('Could not clear Auth0 state before login:', error)
    }

    await loginWithRedirect()
  }

  const logoutUser = (options?: { logoutParams?: { returnTo?: string } }) => {
    auth0Logout({
      logoutParams: {
        returnTo: options?.logoutParams?.returnTo || window.location.origin,
      },
    })
  }

  const getAccessToken = async () => {
    try {
      return await getAccessTokenSilently()
    } catch (error) {
      console.error('Error getting access token:', error)
      throw error
    }
  }

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    logout: logoutUser,
    getAccessToken,
  }
}
