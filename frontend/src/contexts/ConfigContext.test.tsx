import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ConfigProvider, useConfig } from './ConfigContext'
import type { AppConfig } from '../lib/config'

const mockConfig: AppConfig = {
  api: {
    baseUrl: 'http://localhost:8000/api/v1',
  },
  auth0: {
    domain: 'test.auth0.com',
    clientId: 'test-client-id',
    audience: 'https://api.test.com',
    callbackUrl: 'http://localhost:5173/callback',
  },
}

describe('ConfigContext', () => {
  describe('ConfigProvider', () => {
    it('should provide config to children', () => {
      function TestComponent() {
        const config = useConfig()
        return <div>API: {config.api.baseUrl}</div>
      }

      render(
        <ConfigProvider config={mockConfig}>
          <TestComponent />
        </ConfigProvider>
      )

      expect(screen.getByText('API: http://localhost:8000/api/v1')).toBeInTheDocument()
    })

    it('should provide full config object', () => {
      function TestComponent() {
        const config = useConfig()
        return (
          <div>
            <div data-testid="api">{config.api.baseUrl}</div>
            <div data-testid="domain">{config.auth0.domain}</div>
            <div data-testid="clientId">{config.auth0.clientId}</div>
            <div data-testid="audience">{config.auth0.audience}</div>
            <div data-testid="callback">{config.auth0.callbackUrl}</div>
          </div>
        )
      }

      render(
        <ConfigProvider config={mockConfig}>
          <TestComponent />
        </ConfigProvider>
      )

      expect(screen.getByTestId('api')).toHaveTextContent('http://localhost:8000/api/v1')
      expect(screen.getByTestId('domain')).toHaveTextContent('test.auth0.com')
      expect(screen.getByTestId('clientId')).toHaveTextContent('test-client-id')
      expect(screen.getByTestId('audience')).toHaveTextContent('https://api.test.com')
      expect(screen.getByTestId('callback')).toHaveTextContent('http://localhost:5173/callback')
    })

    it('should allow multiple nested children to access config', () => {
      function ChildComponent() {
        const config = useConfig()
        return <div>Child: {config.api.baseUrl}</div>
      }

      function ParentComponent() {
        return (
          <div>
            <ChildComponent />
          </div>
        )
      }

      render(
        <ConfigProvider config={mockConfig}>
          <ParentComponent />
        </ConfigProvider>
      )

      expect(screen.getByText('Child: http://localhost:8000/api/v1')).toBeInTheDocument()
    })
  })

  describe('useConfig', () => {
    it('should throw error when used outside ConfigProvider', () => {
      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      function TestComponent() {
        useConfig() // This should throw
        return <div>Should not render</div>
      }

      expect(() => {
        render(<TestComponent />)
      }).toThrow('useConfig must be used within ConfigProvider')

      consoleSpy.mockRestore()
    })

    it('should return config object when used within ConfigProvider', () => {
      function TestComponent() {
        const config = useConfig()
        return <div data-testid="config-test">{JSON.stringify(config)}</div>
      }

      render(
        <ConfigProvider config={mockConfig}>
          <TestComponent />
        </ConfigProvider>
      )

      const element = screen.getByTestId('config-test')
      const receivedConfig = JSON.parse(element.textContent || '{}')
      expect(receivedConfig).toEqual(mockConfig)
    })

    it('should return same config object on re-renders', () => {
      const configs: AppConfig[] = []

      function TestComponent({ counter }: { counter: number }) {
        const config = useConfig()
        configs.push(config)
        return <div>{counter}</div>
      }

      const { rerender } = render(
        <ConfigProvider config={mockConfig}>
          <TestComponent counter={1} />
        </ConfigProvider>
      )

      rerender(
        <ConfigProvider config={mockConfig}>
          <TestComponent counter={2} />
        </ConfigProvider>
      )

      expect(configs).toHaveLength(2)
      expect(configs[0]).toBe(configs[1]) // Same reference
    })
  })
})
