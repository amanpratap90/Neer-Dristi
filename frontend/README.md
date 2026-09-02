# ChetakAI Flood Intelligence Frontend

Two-page React/Vite frontend:

- `/` — coordinate input
- dashboard — complete flood intelligence result

The dashboard is already wired for:

`GET /api/v1/risk?lat=<latitude>&lon=<longitude>`

If the backend is unavailable, the UI falls back to the supplied demo structure so frontend development can continue.

## Run

```bash
npm install
npm run dev
```

For the real backend:

```bash
copy .env.example .env
```

Then set `VITE_API_BASE_URL` to the backend URL.
