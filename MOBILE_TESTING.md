# Testare l'app da telefono (stessa LAN)

Il progetto è già configurato per questo (certificati HTTPS locali + vite in ascolto su tutte le interfacce). Serve solo avviare i due servizi e collegarsi dal telefono.

## Avvio rapido (un solo comando)

```bash
./start_mobile.sh                 # Ctrl+C ferma frontend + backend
./start_mobile.sh --keep-backend  # Ctrl+C ferma solo il frontend
```

Lo script rileva l'IP LAN, rigenera i certificati se non coprono l'IP attuale, avvia `docker compose`, attende `/health`, stampa URL + QR code e lancia `npm run dev`. I passi sotto descrivono la procedura manuale.

## 1. Prerequisiti (una tantum, già fatti in questo repo)

- Certificati HTTPS generati con `mkcert` in `frontend/.certs/dev-cert.pem` + `dev-key.pem` (non versionati, vedi `frontend/.gitignore`). Servono perché `getUserMedia` (fotocamera) richiede un contesto sicuro: `http://<ip-lan>` non basta.
- Se mai andassero rigenerati (es. nuova macchina):
  ```bash
  cd frontend
  mkcert -install   # installa la CA locale (una volta sola per macchina)
  mkdir -p .certs
  mkcert -cert-file .certs/dev-cert.pem -key-file .certs/dev-key.pem <IP-LAN> localhost 127.0.0.1
  ```
- Telefono e computer devono essere sulla **stessa rete Wi-Fi/LAN**.

## 2. Avvio backend (Postgres + API)

```bash
cd /home/giuseppe/scadenzario
docker compose up -d
```

Verifica che sia su, porta `8000`:
```bash
docker ps   # scadenzario-backend-1 e scadenzario-db-1 devono essere "Up"
```

## 3. Avvio frontend (dev server Vite, HTTPS)

```bash
cd /home/giuseppe/scadenzario/frontend
npm run dev
```

Vite parte in HTTPS su `0.0.0.0:5173` (host `true` in `vite.config.ts`) e inoltra `/api/*` al backend su `localhost:8000`.

## 4. Trovare l'IP LAN del computer

```bash
hostname -I | awk '{print $1}'
```

(sul mio setup risulta tipicamente `192.168.1.38`, ma va ricontrollato ogni volta perché può cambiare)

## 5. Collegarsi dal telefono

Aprire sul telefono, nello stesso Wi-Fi:

```
https://<IP-LAN>:5173
```

es. `https://192.168.1.38:5173`

- Il certificato è self-signed: il browser del telefono mostrerà un avviso di sicurezza la prima volta ("connessione non privata" o simile) — bisogna procedere/accettare manualmente per continuare.
- Se il telefono ha già la CA di `mkcert` installata come attendibile, l'avviso non compare.

## 6. Arresto

```bash
# frontend: Ctrl+C nel terminale di npm run dev
cd /home/giuseppe/scadenzario
docker compose down   # ferma backend + db (i dati restano nel volume db_data)
```
