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
    logout,
    getAccessTokenSilently,
  } = useAuth0()

  const login = async () => {
    await loginWithRedirect()
  }

  const logoutUser = (options?: { logoutParams?: { returnTo?: string } }) => {
    logout({
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
