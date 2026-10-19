# Frontend

Next.js app for the CCL platform: public site, student app (`src/app/(app)`), test player (`src/app/attempt`) and
admin (`src/app/admin`). All data comes from the FastAPI backend through the same-origin `/api` rewrite in
`next.config.ts` (`API_URL`, default `http://127.0.0.1:8000`), so the httpOnly session cookie is sent with every call.

```bash
npm install
npm run dev     # http://localhost:3000
npm run lint
npm run build   # standalone output, used by the production Dockerfile
```

See the repository [README](../README.md) for the full setup.
