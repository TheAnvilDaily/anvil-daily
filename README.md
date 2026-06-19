# The Anvil Daily

Independent journalism aggregator. Static site, deployed to Cloudflare Pages.

## Structure
- `public/` — the deployed static site
- `content/posts/` — Markdown post files (bot writes here)
- `scripts/` — bot + build scripts (added in next phase)

## Local preview
```bash
cd public && python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy
Connected to Cloudflare Pages. Push to `main` → auto-deploy.
- Build command: (none — pure static)
- Output directory: `public`
