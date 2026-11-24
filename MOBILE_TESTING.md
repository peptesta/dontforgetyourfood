# Testing the app from a phone (same LAN)

The project is already set up for this (local HTTPS certificates + Vite listening on all interfaces). You only need to start the two services and connect from your phone.

## Quick start (one command)

```bash
./start_mobile.sh                 # Ctrl+C stops frontend + backend
./start_mobile.sh --keep-backend  # Ctrl+C stops the frontend only
```

The script detects the LAN IP, regenerates the certificates if they don't cover the current IP, starts `docker compose`, waits for `/health`, prints the URL + a QR code and launches `npm run dev`. The steps below describe the manual procedure.

## 1. Prerequisites (one-off, already done in this repo)

- HTTPS certificates generated with `mkcert` in `frontend/.certs/dev-cert.pem` + `dev-key.pem` (not versioned, see `frontend/.gitignore`). They are needed because `getUserMedia` (camera) requires a secure context: `http://<lan-ip>` is not enough.
- If they ever need to be regenerated (e.g. new machine):
  ```bash
  cd frontend
  mkcert -install   # installs the local CA (once per machine)
  mkdir -p .certs
  mkcert -cert-file .certs/dev-cert.pem -key-file .certs/dev-key.pem <LAN-IP> localhost 127.0.0.1
  ```
- Phone and computer must be on the **same Wi-Fi/LAN**.

## 2. Start the backend (Postgres + API)

```bash
cd /home/giuseppe/scadenzario
docker compose up -d
```

Check that it is up, on port `8000`:
```bash
docker ps   # scadenzario-backend-1 and scadenzario-db-1 must be "Up"
```

## 3. Start the frontend (Vite dev server, HTTPS)

```bash
cd /home/giuseppe/scadenzario/frontend
npm run dev
```

Vite starts in HTTPS on `0.0.0.0:5173` (`host: true` in `vite.config.ts`) and forwards `/api/*` to the backend at `localhost:8000`.

## 4. Find the computer's LAN IP

```bash
hostname -I | awk '{print $1}'
```

(on my setup it is typically `192.168.1.38`, but check every time as it can change)

## 5. Connect from the phone

Open on the phone, on the same Wi-Fi:

```
https://<LAN-IP>:5173
```

e.g. `https://192.168.1.38:5173`

- The certificate is self-signed: the phone's browser will show a security warning the first time ("connection not private" or similar) — you have to proceed/accept manually to continue.
- If the phone already has the `mkcert` CA installed as trusted, the warning does not appear.

## 6. Stopping

```bash
# frontend: Ctrl+C in the npm run dev terminal
cd /home/giuseppe/scadenzario
docker compose down   # stops backend + db (data is kept in the db_data volume)
```
