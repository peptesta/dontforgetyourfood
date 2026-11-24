# PROJECT_REPORT — Scadenzario

Report generato in sola lettura dal codice, dai file di config e da `git log` (stato del working tree al 2026-11-17, branch `feature/carica-scontrino`). Dove un dato non è verificabile è scritto "non determinabile".

## 1. Identità

- **Nome**: Scadenzario (nome nel codice, in `RECEIPT_ROADMAP.md`, nel sender email e nel DB `scadenzario`).
- **Scopo**: web app mobile-first per tracciare le scadenze dei prodotti in dispensa. L'utente fotografa titolo e data di scadenza di ogni confezione (o lo scontrino della spesa). Un OCR locale legge i dati e l'app avvisa via email quando un prodotto sta per scadere (1 e 3 giorni prima).
- **Per chi**: persone che fanno la spesa e vogliono evitare sprechi di cibo scaduto. Dal codice e dalla roadmap l'utente tipo è italiano e vive in Spagna: UI in italiano, scontrini spagnoli (Lidl, Mercadona, Alcampo), `TZ=Europe/Madrid`.

## 2. Stack reale

| Area | Tecnologie (da `requirements.txt`, `package.json`, `Dockerfile`) |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, Uvicorn, SQLAlchemy 2.0 async + asyncpg, Alembic, Pydantic v2 / pydantic-settings |
| Auth | JWT (python-jose) con access + refresh token, hashing password con passlib + bcrypt |
| OCR / visione | PaddleOCR 3.7 + PaddlePaddle 3.3 (modelli PP-OCRv5 mobile det + `latin_PP-OCRv5_mobile_rec`, solo CPU), OpenCV (preprocessing, CLAHE), pillow-heif (foto HEIC) |
| Testo / matching | rapidfuzz (fuzzy matching), dateparser (date di scadenza) |
| Async / job | `ProcessPoolExecutor` per i worker OCR, SSE (sse-starlette) per l'avanzamento dei batch, APScheduler per il controllo giornaliero delle scadenze |
| Notifiche | Brevo (API transazionale email, `https://api.brevo.com/v3/smtp/email`) via httpx + template Jinja2 |
| Database | PostgreSQL 16 (immagine `postgres:16-alpine`) |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, react-router-dom 7, TanStack Query 5, date-fns; lint con oxlint |
| Dati esterni | Catalogo prodotti da Open Food Facts (licenza ODbL), scaricato da `backend/scripts/fetch_product_catalog.py` |
| Build/deploy | Docker (`backend/Dockerfile`) + `docker-compose.yml` (db + backend); frontend con dev server Vite in HTTPS (certificati mkcert) |
| Test | pytest (backend). Test frontend: non determinabile (nessuno trovato) |

## 3. Architettura

SPA React che chiama l'API REST di FastAPI (in dev Vite fa da proxy verso `localhost:8000`). Il backend salva utenti, prodotti e batch su Postgres. Le immagini vanno a un pool di processi worker che tengono il modello OCR già caricato in memoria. Un `AsyncIOScheduler` controlla le scadenze e invia le email.

Flussi principali:
- **Aggiungi foto (batch)**: upload foto titolo + data → `POST /batches` (202) → worker OCR in background → avanzamento via SSE (`/batches/{id}/stream`) → revisione → `POST /batches/{id}/confirm` crea i prodotti.
- **Carica scontrino**: più foto della colonna prodotti → `POST /receipts/parse` (stateless, non salva nulla) → OCR → parser righe → merge delle foto sovrapposte → matching col catalogo.

```
scadenzario/
├── backend/
│   ├── app/
│   │   ├── main.py            # app FastAPI, router, lifespan/scheduler
│   │   ├── api/deps.py        # dipendenze (utente corrente, sessione)
│   │   ├── core/              # config (settings) e security (JWT, hash)
│   │   ├── db/                # sessione async + modelli SQLAlchemy
│   │   ├── routers/           # auth, products, batches, ocr, notifications, receipts
│   │   ├── schemas/           # modelli Pydantic
│   │   ├── services/
│   │   │   ├── ocr/           # engine, preprocess, pipeline, date/name extractor, catalogo
│   │   │   ├── receipt/       # parser, merge, matching, foods
│   │   │   ├── batch_processor.py, image_storage.py, notifier.py, scheduler.py
│   │   ├── workers/pool.py    # process pool OCR
│   │   └── data/              # catalogo Open Food Facts, freschi, non-alimentari, abbreviazioni (JSON)
│   ├── alembic/versions/      # 4 migrazioni
│   ├── scripts/               # debug_ocr.py, fetch_product_catalog.py
│   └── tests/                 # 10 file di test
├── frontend/src/
│   ├── pages/                 # 11 pagine
│   ├── components/            # CameraCaptureGrid, ExpiryBadge, ReceiptSourceSheet
│   ├── hooks/, api/, context/, lib/
├── docker-compose.yml
├── start_mobile.sh, MOBILE_TESTING.md
└── RECEIPT_ROADMAP.md
```

## 4. Funzionalità implementate

- Registrazione, login, refresh token, logout, `/auth/me` — `backend/app/routers/auth.py`, `frontend/src/pages/LoginPage.tsx`, `RegisterPage.tsx`, `context/AuthContext.tsx`.
- Dispensa: elenco prodotti, modifica, "consumato", elimina, foto del titolo — `backend/app/routers/products.py`, `frontend/src/pages/PantryListPage.tsx`.
- Badge di scadenza colorato — `frontend/src/components/ExpiryBadge.tsx`.
- Aggiunta prodotti da foto (titolo + data) con OCR in batch e avanzamento in tempo reale (SSE) — `routers/batches.py`, `services/batch_processor.py`, `frontend/src/pages/UploadPage.tsx`, `ProcessingPage.tsx`, `ReviewPage.tsx`, `hooks/useBatchStream.ts`.
- Anteprima OCR della data subito dopo lo scatto — `routers/ocr.py` (`/ocr/date-preview`), `frontend/src/api/ocr.ts`.
- Camera nel browser con riquadro guida e ritaglio — `hooks/useCameraStream.ts`, `components/CameraCaptureGrid.tsx`, `lib/cameraCrop.ts`.
- Estrazione data di scadenza e nome prodotto dall'OCR — `services/ocr/date_extractor.py`, `name_extractor.py`.
- Abbinamento del nome letto al catalogo supermercati — `services/ocr/product_catalog.py`.
- Carica scontrino (Step 1 della roadmap): multi-foto, lettura righe, deduplica per sovrapposizione, esclusione non alimentari, matching catalogo, segnalazione "da verificare" — `routers/receipts.py`, `services/receipt/*`, `frontend/src/pages/ReceiptCapturePage.tsx`, `ReceiptResultPage.tsx`, `ReceiptFlowPage.tsx`, `components/ReceiptSourceSheet.tsx`.
- Notifiche email di scadenza (1 e 3 giorni), idempotenti tramite flag `notificato_1gg/3gg` — `services/scheduler.py`, `services/notifier.py`, `routers/notifications.py` (`/notifications/check`).
- Salvataggio delle foto prodotto su disco — `services/image_storage.py`.
- Avvio per test da telefono in LAN con HTTPS — `start_mobile.sh`, `MOBILE_TESTING.md`.

Non implementato (dichiarato in `RECEIPT_ROADMAP.md`): Step 2 e 3 di "Carica scontrino" (quantità, foto delle scadenze, aggiunta alla dispensa), "Carica immagine"/"Carica documento" (voci disabilitate).

## 5. Parti tecnicamente interessanti

1. **Pipeline OCR per scontrini** (`services/ocr/pipeline.py`, `preprocess.py`). Prima del riconoscimento c'è CLAHE con ridimensionamento a 2000 px. Le soglie del detector sono abbassate perché con i default PaddleOCR saltava righe intere. Segue un filtro sul contrasto inchiostro/carta (percentili 5°/95° sui grigi *prima* del CLAHE) che elimina il testo del retro che traspare e i QR. Infine i box con confidenza < 0.6 vengono ritagliati e riletti da soli, e il risultato si accetta solo se ≥ 0.8.
2. **Parser righe con raddrizzamento** (`services/receipt/parser.py`). Stima l'inclinazione dalla mediana dei lati dei box e ruota le coordinate prima di raggruppare in righe. Senza questo il prezzo finiva sulla riga sbagliata in silenzio (bug documentato nella roadmap). Gestisce lettere IVA, codici articolo, prodotti a peso in stile Mercadona e righe senza prezzo, che tiene invece di scartarle.
3. **Merge di foto sovrapposte** (`services/receipt/merge.py`). Cerca "punti di contatto" tra la coda di una foto e la testa della successiva (nome simile + prezzo uguale, catena monotona greedy). Non richiede righe contigue, perché l'OCR sbaglia proprio nella zona comune. Riconosce le righe tagliate dal bordo e segnala le giunture senza sovrapposizione. Poi fonde i duplicati veri contando le `occorrenze`.
4. **Matching col catalogo** (`services/receipt/matching.py`). Usa `token_sort_ratio` più un criterio di contenimento con soglia di copertura, perché `WRatio` dava falsi positivi su nomi brevi (BANANA, KIWI). Espande le abbreviazioni degli scontrini. Cerca su catalogo di marca + lista di freschi generici.
5. **Elaborazione asincrona e robustezza operativa** (`workers/pool.py`, `routers/batches.py`, `services/scheduler.py`). Ogni worker carica il modello OCR una volta sola. I batch partono con 202 e riportano l'avanzamento via SSE. Le notifiche usano soglie `<=` e flag per riga, quindi sono idempotenti anche se il job salta un giorno. Il `Dockerfile` pre-scarica i pesi OCR in build e disattiva oneDNN per un crash di paddlepaddle su CPU (commentato nel codice).

## 6. Numeri verificabili

Fonte: `git ls-files` + `wc -l` (cloc non installato; i conteggi includono righe vuote e commenti).

| Voce | Valore |
|---|---|
| Python (file tracciati) | 4.424 righe |
| TypeScript `.ts` / `.tsx` | 599 / 1.423 righe |
| CSS / HTML | 17 / 13 righe |
| JSON (soprattutto catalogo) | 14.351 righe |
| Endpoint HTTP | 17 route (auth 5, products 5, batches 4, ocr 1, notifications 1, receipts 1) + `/health` citato in `MOBILE_TESTING.md` (non contato) |
| Tabelle DB (modelli) | 6: `households`, `users`, `batches`, `batch_items`, `refresh_tokens`, `products` |
| Migrazioni Alembic | 4 |
| Test | 91 test pytest in 10 file, tutti passati (`pytest tests -q`: 91 passed) |
| Pagine / componenti frontend | 11 pagine, 3 componenti |
| Catalogo prodotti | 3.021 prodotti (Open Food Facts, Spagna, `_stores: 4`, `_complete: false`) |
| Lista non alimentari | 144 parole chiave |
| Lista freschi | 10 categorie (conteggio voci non verificato; la roadmap dice ~320) |
| Abbreviazioni scontrino | 29 |
| Metriche del modello OCR (accuracy ecc.) | non determinabile: nessuna eval nel repo. La roadmap indica che tutto è stato tarato su **un solo** scontrino Lidl (21 righe alimentari lette correttamente) |

## 7. Cronologia

- **Primo commit**: 2026-10-03 (`2b51f62`, "Stato iniziale prima di Carica scontrino")
- **Ultimo commit**: 2026-10-03 (`a56e937`, RECEIPT_ROADMAP.md)
- **Numero di commit**: 5, tutti nello stesso giorno

Il repo è stato inizializzato in git solo il 2026-10-03, quindi la storia reale precedente non è nei commit. Le date dei file più vecchi (22-23 settembre 2026, mtime) indicano che il progetto esisteva già.

Fasi viste nei commit:
1. Baseline dell'app esistente (dispensa, batch OCR, auth).
2. "Carica scontrino" Step 1: lettura, dedup e matching catalogo.
3. Raddrizzamento, filtri rumore, matching più severo, merge tollerante.
4. Filtro inchiostro, rilettura box deboli, solo alimentari, freschi, duplicati fusi.
5. Documento di roadmap.

## 8. Deploy e stato

- **URL pubblicato**: non determinabile. Nessun URL di produzione, Procfile, CI o workflow nei file. Esiste solo la configurazione locale: docker-compose (db su porta host 5433, backend su 8000) e Vite in HTTPS.
- **Stato**: in sviluppo, su branch `feature/carica-scontrino`. Il working tree ha **42 voci non committate** (39 file modificati; vedi sotto).
- **Cosa manca** (da `RECEIPT_ROADMAP.md`): Step 2 e 3 di Carica scontrino, `products.data_scadenza` nullable (migrazione non fatta), correzioni manuali nella schermata finale, golden set di valutazione, quadratura col totale, alias imparati, sorgenti "Carica immagine"/"Carica documento", supporto scontrini italiani. Test frontend assenti. `JWT_SECRET` in `.env.example` è un placeholder (`change-me-in-production`).

## 9. Il tuo ruolo

Un solo autore nei commit: **Peppetesta**, 5/5 commit (`git shortlog`). Nessun altro contributor. La roadmap è scritta come passaggio di consegne a una sessione Claude, quindi parte del lavoro recente può essere stato svolto con assistenza AI; il git log non lo indica.

## 10. Link e asset

- **Repository remoto**: nessun `remote` configurato (non determinabile).
- **Demo / sito**: non determinabile.
- **Documentazione**: `RECEIPT_ROADMAP.md`, `MOBILE_TESTING.md`, `frontend/README.md`, `backend/scripts/debug_input/README.md`. Non c'è un README nella root.
- **Immagini**: `backend/scripts/debug_input/IMG_1057.jpeg`, `IMG_1058.jpeg` e `backend/scripts/debug_output/*/*.png` (output intermedi dell'OCR; sono tracciati, `IMG_1126.jpeg` no). Non ci sono screenshot dell'app.
- **Non tracciati**: `Gemini_Generated_Image_h7wib2h7wib2h7wi.jpeg` (foto dello scontrino Lidl di prova, 2,3 MB), `backend/scripts/debug_receipts/`.
- `frontend/public/favicon.svg`, `icons.svg`.

## Dubbi (non verificati)

- **Incoerenza households**: nel working tree `routers/households.py`, `schemas/household.py`, `api/households.ts` e `SettingsPage.tsx` sono cancellati (staged `D`), ma modelli, migrazioni, FK e `scheduler.py` usano ancora `household_id`. Non so se sia una rimozione voluta e incompleta. L'ultima migrazione si chiama "household_settings…". I numeri su endpoint e pagine riflettono il working tree, non i commit.
- **Commit vs working tree**: i commit non contengono le 39 modifiche non committate, quindi il conteggio righe e le funzionalità descritte sono quelli del working tree.
- **Numero di endpoint**: contati con grep sui decoratori `@router.<verbo>`. `/health` e altre route definite direttamente in `main.py` non sono state verificate.
- **Voci della lista freschi**: ~320 secondo la roadmap, non contate (il JSON è per categorie).
- **Tempi di elaborazione OCR e accuratezza**: mai misurati (lo dice anche la roadmap).
- **Deploy in produzione, dominio, hosting**: non determinabile.
- **Pagina di login/registrazione e flusso reale dell'invio email Brevo**: letti nel codice, non eseguiti. Eseguito solo `pytest` (91 passati).
- **Date storiche**: i 5 commit sono tutti del 2026-10-03, quindi non si può ricostruire la durata reale dello sviluppo precedente.
- **Licenza del repo**: non determinabile (nessun file LICENSE). Il catalogo deriva da Open Food Facts (ODbL), quindi comporta obblighi di attribuzione.
