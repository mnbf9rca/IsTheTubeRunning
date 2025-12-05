import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [tailwindcss(), react()],
  define: {
    __BUILD_COMMIT__: JSON.stringify(process.env.VITE_BUILD_COMMIT || 'dev'),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/**',
        'src/test/**',
        '**/*.test.{ts,tsx}',
        '**/*.config.{ts,js}',
        'src/main.tsx',
        'src/components/ui/**', // shadcn components - third-party
      ],
      thresholds: {
        lines: 75,
        functions: 80,
        branches: 70,
        statements: 75,
      },
    },
  },
})
