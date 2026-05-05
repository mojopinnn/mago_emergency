# AGENTS.md

## Cursor Cloud specific instructions

### Overview

MAGO Emergency System — a pnpm workspace monorepo with an Express 5 (TypeScript) API server, a React frontend (Vite), and a UI mockup sandbox (Vite). The primary product is the api-server which serves a PWA for emergency notifications integrated with Autodesk ShotGrid.

### Running services

All Vite-based apps require `PORT` and `BASE_PATH` environment variables.

| Service | Command | Default Port | Notes |
|---------|---------|--------------|-------|
| API Server | `PORT=8080 VAPID_PUBLIC_KEY=<key> VAPID_PRIVATE_KEY=<key> VAPID_EMAIL=mailto:dev@test.com pnpm --filter @workspace/api-server dev` | 8080 | Builds via esbuild then runs. No DB required (in-memory stores). |
| Frontend App | `PORT=5173 BASE_PATH=/ pnpm --filter @workspace/app dev` | 5173 | Just redirects to `/api/app`. |
| Mockup Sandbox | `PORT=5174 BASE_PATH=/ pnpm --filter @workspace/mockup-sandbox dev` | 5174 | Standalone component playground. |

Generate VAPID keys with: `npx web-push generate-vapid-keys --json`

### Key gotchas

- The `@workspace/db` package (PostgreSQL/Drizzle) is scaffolded but **not used** by the api-server at runtime. No `DATABASE_URL` is needed to run the API server.
- The api-server `dev` script builds first (`esbuild`), then starts the server — it does NOT hot-reload. Restart the process after code changes.
- TypeScript has pre-existing errors in `artifacts/api-server/src/lib/shotgrid.ts` (union type access without narrowing). The esbuild-based build ignores these.
- The `preinstall` script in root `package.json` enforces pnpm; using npm/yarn will fail.
- ShotGrid integration requires real credentials for end-to-end webhook testing, but the server starts fine without them (all SG calls are lazy/on-demand).

### Lint & typecheck

```bash
pnpm run typecheck          # TypeScript project references build + per-artifact typecheck
pnpm exec prettier --check . # Prettier formatting check
```

### Build

```bash
pnpm run build              # typecheck + build all artifacts
```
