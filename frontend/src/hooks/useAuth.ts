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
    // Clear any stale local session state before starting new login flow
    // This prevents "Invalid state" errors when reopening browser with stale OAuth transactions
    // Use Auth0's built-in local logout (openUrl: false) to safely clear state
    try {
      await auth0Logout({ openUrl: false })
    } catch (error) {
      // If logout fails, continue anyway - loginWithRedirect will handle it
      console.warn('Could not clear local session before login:', error)
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
