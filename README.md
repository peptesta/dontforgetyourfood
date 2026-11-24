# Don't forget your food (Scadenzario)

App per tenere traccia delle scadenze degli alimenti: fotografa i prodotti o carica lo scontrino e l'OCR fa il resto.

## Avvio rapido con Docker

Serve solo [Docker](https://docs.docker.com/get-docker/) con Compose.

```bash
curl -O https://raw.githubusercontent.com/peptesta/dontforgetyourfood/main/docker-compose.prod.yml
JWT_SECRET=$(openssl rand -hex 32) docker compose -f docker-compose.prod.yml up -d
```

Apri **http://localhost:8080**, registrati e inizia.

Il primo avvio scarica le immagini (il backend è grande per via del modello OCR) e crea il database da solo.

Immagini pubbliche:
- `ghcr.io/peptesta/dontforgetyourfood-backend:latest`
- `ghcr.io/peptesta/dontforgetyourfood-frontend:latest`

Comandi utili: `docker compose -f docker-compose.prod.yml logs -f backend` · `... pull && ... up -d` per aggiornare · `... down` per fermare (i dati restano nei volumi).

### Note
- La fotocamera del browser funziona solo su `localhost` o in HTTPS. Per usarla da telefono metti l'app dietro un reverse proxy HTTPS (es. Caddy, Cloudflare Tunnel).
- Se esponi l'app su un altro indirizzo, imposta `CORS_ORIGINS` del backend di conseguenza.
- Mantieni lo stesso `JWT_SECRET` tra i riavvii, altrimenti le sessioni decadono.
- Il backend richiede circa 2 GB di RAM.

## Sviluppo
Vedi `docker-compose.yml` (build locale) e `MOBILE_TESTING.md`.
