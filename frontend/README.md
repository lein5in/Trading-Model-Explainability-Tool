# TME frontend

Single-page React app for the Trading Model Explainability Tool. It submits a model (a bundled demo or an uploaded pickle) and market data parameters to the backend, follows the run, and shows the backtest, market regimes, SHAP explanations and the verified report.

Stack: Vite, React 19, React Router 7, Tailwind CSS 4, lightweight-charts 5, Vitest.

## Commands

Run from `frontend/`:

- `npm install` (or `npm ci`) installs dependencies.
- `npm run dev` starts the dev server on port 5173.
- `npm run build` writes the production bundle to `dist/`.
- `npm run lint` runs ESLint.
- `npm run test` runs the unit tests once with Vitest.

## Configuration

- `VITE_API_BASE_URL`: base URL of the backend API. Defaults to `http://127.0.0.1:8000` when unset. Copy `.env.example` to `.env.local` to set it. The value is read at build time.

Provisional limits, the disclaimer and the point-in-time notice live in `src/config.js`.

## Deployment

`vercel.json` rewrites every path to `index.html` so deep links such as `/analysis/<id>/trades` load the app.
