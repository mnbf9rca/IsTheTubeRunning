import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { loadConfig } from './configLoader'
import type { MultiEnvConfig } from './configLoader'

// Mock fetch globally
global.fetch = vi.fn()

describe('configLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Restore original location
    vi.unstubAllGlobals()
  })

  describe('detectEnvironment', () => {
    it('should detect development for localhost', async () => {
      vi.stubGlobal('location', { hostname: 'localhost' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
      expect(config.auth0.domain).toBe('dev.auth0.com')
    })

    it('should detect development for 127.0.0.1', async () => {
      vi.stubGlobal('location', { hostname: '127.0.0.1' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
    })

    it('should detect development for 192.168.x.x addresses', async () => {
      vi.stubGlobal('location', { hostname: '192.168.1.100' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
    })

    it('should detect development for 10.x.x.x addresses', async () => {
      vi.stubGlobal('location', { hostname: '10.0.0.5' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
    })

    it('should detect development for .local domains', async () => {
      vi.stubGlobal('location', { hostname: 'mycomputer.local' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
    })

    it('should detect development for 172.16.x.x addresses', async () => {
      vi.stubGlobal('location', { hostname: '172.16.0.1' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
    })

    it('should detect development for IPv6 loopback (::1)', async () => {
      vi.stubGlobal('location', { hostname: '::1' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
    })

    it('should detect development for IPv6 link-local (fe80::)', async () => {
      vi.stubGlobal('location', { hostname: 'fe80::1' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
    })

    it('should detect production for isthetube.cynexia.com', async () => {
      vi.stubGlobal('location', { hostname: 'isthetube.cynexia.com' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://isthetube.cynexia.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.isthetube.com',
            callbackUrl: 'https://isthetube.cynexia.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('https://isthetube.cynexia.com/api/v1')
      expect(config.auth0.domain).toBe('prod.auth0.com')
    })

    it('should detect development for any other domain (safer default)', async () => {
      vi.stubGlobal('location', { hostname: 'example.com' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
      expect(config.auth0.domain).toBe('dev.auth0.com')
    })
  })

  describe('loadConfig', () => {
    it('should fetch config from /config.json', async () => {
      vi.stubGlobal('location', { hostname: 'localhost' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      await loadConfig()

      expect(global.fetch).toHaveBeenCalledWith('/config.json')
    })

    it('should throw error when fetch fails', async () => {
      vi.stubGlobal('location', { hostname: 'localhost' })
      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: false,
        status: 404,
      })

      await expect(loadConfig()).rejects.toThrow()
    })

    it('should validate config has required fields', async () => {
      vi.stubGlobal('location', { hostname: 'localhost' })

      const invalidConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: '' }, // Invalid: empty baseUrl
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => invalidConfig,
      })

      await expect(loadConfig()).rejects.toThrow('Configuration validation failed')
    })

    it('should throw error when environment config is missing', async () => {
      vi.stubGlobal('location', { hostname: 'localhost' })

      const incompleteConfig = {
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
        // Missing development config
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => incompleteConfig,
      })

      await expect(loadConfig()).rejects.toThrow(
        'Configuration for environment "development" not found in config.json'
      )
    })

    it('should return fully populated config object', async () => {
      vi.stubGlobal('location', { hostname: 'localhost' })

      const mockConfig: MultiEnvConfig = {
        development: {
          api: { baseUrl: 'http://localhost:8000/api/v1' },
          auth0: {
            domain: 'dev.auth0.com',
            clientId: 'dev-client-id',
            audience: 'https://api.dev.com',
            callbackUrl: 'http://localhost:5173/callback',
          },
        },
        production: {
          api: { baseUrl: 'https://api.prod.com/api/v1' },
          auth0: {
            domain: 'prod.auth0.com',
            clientId: 'prod-client',
            audience: 'https://api.prod.com',
            callbackUrl: 'https://prod.com/callback',
          },
        },
      }

      ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: async () => mockConfig,
      })

      const config = await loadConfig()

      expect(config).toBeDefined()
      expect(config.api).toBeDefined()
      expect(config.api.baseUrl).toBe('http://localhost:8000/api/v1')
      expect(config.auth0).toBeDefined()
      expect(config.auth0.domain).toBe('dev.auth0.com')
      expect(config.auth0.clientId).toBe('dev-client-id')
      expect(config.auth0.audience).toBe('https://api.dev.com')
      expect(config.auth0.callbackUrl).toBe('http://localhost:5173/callback')
    })
  })
})
