#!/usr/bin/env bash
# Avvia backend (docker compose) + frontend (vite HTTPS) per testare l'app da telefono
# sulla stessa LAN. Vedi MOBILE_TESTING.md.
#
# Uso:
#   ./start_mobile.sh                 avvia tutto; Ctrl+C ferma frontend e backend
#   ./start_mobile.sh --keep-backend  Ctrl+C ferma solo il frontend, backend resta su
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND="$ROOT/frontend"
CERT="$FRONTEND/.certs/dev-cert.pem"
KEY="$FRONTEND/.certs/dev-key.pem"
KEEP_BACKEND=0
[[ "${1:-}" == "--keep-backend" ]] && KEEP_BACKEND=1

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m!!\033[0m %s\n' "$*" >&2; }

# --- 1. IP LAN: interfaccia della rotta di default (evita i bridge docker 172.17/18/...)
LAN_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
[[ -z "$LAN_IP" ]] && LAN_IP="$(hostname -I | awk '{print $1}')"
if [[ -z "$LAN_IP" ]]; then
  err "Impossibile determinare l'IP LAN: sei connesso a una rete?"
  exit 1
fi
log "IP LAN: $LAN_IP"

# --- 2. Certificati: rigenera se mancano o non coprono l'IP attuale
if [[ ! -f "$CERT" || ! -f "$KEY" ]] \
   || ! openssl x509 -in "$CERT" -noout -ext subjectAltName 2>/dev/null | grep -q "IP Address:$LAN_IP\b"; then
  if ! command -v mkcert >/dev/null; then
    err "mkcert non trovato: installalo o genera i certificati a mano (vedi MOBILE_TESTING.md)"
    exit 1
  fi
  log "Rigenero certificati HTTPS per $LAN_IP"
  mkdir -p "$FRONTEND/.certs"
  mkcert -cert-file "$CERT" -key-file "$KEY" "$LAN_IP" localhost 127.0.0.1
fi

# --- 3. Backend
log "Avvio backend (docker compose up -d)"
cd "$ROOT"
docker compose up -d

log "Attendo che il backend risponda su :8000/health"
for _ in $(seq 1 60); do
  curl -fs http://localhost:8000/health >/dev/null 2>&1 && break
  sleep 1
done
if ! curl -fs http://localhost:8000/health >/dev/null 2>&1; then
  err "Il backend non risponde dopo 60s. Log: docker compose logs backend"
  exit 1
fi
log "Backend su"

# --- 4. Arresto pulito su Ctrl+C
cleanup() {
  echo
  if [[ $KEEP_BACKEND -eq 0 ]]; then
    log "Fermo backend (docker compose down, i dati restano nel volume)"
    (cd "$ROOT" && docker compose down)
  else
    log "Backend lasciato attivo (docker compose down per fermarlo)"
  fi
}
trap cleanup EXIT

# --- 5. Frontend
cd "$FRONTEND"
if [[ ! -d node_modules ]]; then
  log "Installo dipendenze frontend (npm install)"
  npm install
fi

URL="https://$LAN_IP:5173"
echo
log "Apri dal telefono (stessa Wi-Fi): $URL"
command -v qrencode >/dev/null && qrencode -t ANSIUTF8 "$URL"
echo "   (se compare l'avviso sul certificato, accettalo per proseguire)"
echo

npm run dev
