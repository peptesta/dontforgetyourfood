# Don't forget your food (Scadenzario)

An app to track food expiry dates: photograph your products or upload a receipt and OCR does the rest.

## Quick start with Docker

You only need [Docker](https://docs.docker.com/get-docker/) with Compose.

```bash
curl -O https://raw.githubusercontent.com/peptesta/dontforgetyourfood/main/docker-compose.prod.yml
JWT_SECRET=$(openssl rand -hex 32) docker compose -f docker-compose.prod.yml up -d
```

Open **http://localhost:8080**, sign up and you're ready to go.

The first start downloads the images (the backend is large because it bundles the OCR model) and creates the database automatically.

Public images:
- `ghcr.io/peptesta/dontforgetyourfood-backend:latest`
- `ghcr.io/peptesta/dontforgetyourfood-frontend:latest`

Useful commands:
- Logs: `docker compose -f docker-compose.prod.yml logs -f backend`
- Update: `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d`
- Stop: `docker compose -f docker-compose.prod.yml down` (data is kept in Docker volumes)

### Notes
- The browser camera only works on `localhost` or over HTTPS. To use it from a phone, put the app behind an HTTPS reverse proxy (e.g. Caddy, Cloudflare Tunnel).
- If you expose the app on a different address, set the backend's `CORS_ORIGINS` accordingly.
- Keep the same `JWT_SECRET` across restarts, otherwise existing sessions are invalidated.
- The backend needs roughly 2 GB of RAM.

## Development
See `docker-compose.yml` (local build) and `MOBILE_TESTING.md`.
