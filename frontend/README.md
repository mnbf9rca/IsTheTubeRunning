# IsTheTubeRunning - Frontend

React + TypeScript + Vite frontend for the TfL Disruption Alert System.

## Configuration

The application uses environment-specific configuration files in `/config`:
- `config.development.json` - Local development
- `config.production.json` - Production deployment
- `config.test.json` - Test environment

Configuration is loaded based on Vite's `MODE` at build time. See `src/lib/config.ts` for details.

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

The Dockerfile supports a `VITE_MODE` build argument to control which config is used:

**Production (default):**
```bash
docker build -t frontend .
```

**Development:**
```bash
docker build --build-arg VITE_MODE=development -t frontend .
```

**Testing:**
```bash
docker build --build-arg VITE_MODE=test -t frontend .
```

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
