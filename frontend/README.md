# IsTheTubeRunning - Frontend

React + TypeScript + Vite frontend for the TfL Disruption Alert System.

## Configuration

The application uses **runtime configuration loading** from `/public/config.json`. Configuration is auto-detected based on the hostname:
- `localhost` or `127.0.0.1` or private IPs (RFC 1918) → Development
- `isthetube.cynexia.com` → Production

This allows the **same Docker image** to work across all environments with zero configuration - the frontend automatically selects the correct config based on `window.location.hostname`.

See `src/lib/configLoader.ts` for implementation details.

## Local Development

```bash
npm install
npm run dev
```

This uses `config.development.json` and connects to `http://localhost:8000`.

## Building

**Production build (default):**
```bash
npm run build
```

**Development build:**
```bash
npm run build -- --mode development
```

## Docker Build

The Docker image is **environment-agnostic** - no build arguments needed:

```bash
docker build -t frontend .
```

The same image works in development and production. Environment detection happens at runtime based on hostname.

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
