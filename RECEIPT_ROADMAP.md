# Carica scontrino — stato, idee e roadmap

Documento per una sessione Claude che continua il lavoro sulla funzione **"Carica scontrino"** di Scadenzario. Leggilo per intero prima di toccare il codice. La lingua del progetto (UI, commenti, nomi di dominio) è l'italiano; gli scontrini da leggere sono spagnoli (Lidl, Mercadona, Alcampo).

## 1. Cos'è e come si inserisce nell'app

Scadenzario traccia le scadenze dei prodotti in dispensa. Il flusso esistente "Aggiungi foto" (`/batch`) fotografa titolo e data di scadenza di ogni confezione. "Carica scontrino" è un secondo ingresso: si fotografa lo scontrino, si leggono i prodotti, si abbinano al catalogo, si chiede la scadenza ai soli prodotti freschi e si aggiungono alla dispensa.

L'utente ha definito tre step:

1. **Step 1 (FATTO, vedi §3)** — caricare lo scontrino (anche più foto, perché è lungo), leggere i soli nomi dei prodotti (non le quantità), eliminare i duplicati dovuti alla sovrapposizione tra foto, applicare l'algoritmo di corrispondenza col catalogo dei supermercati.
2. **Step 2 (DA FARE, vedi §5)** — segnare quali prodotti sono freschi e chiedere la foto della scadenza (stesso meccanismo di "Aggiungi foto"), chiedere le quantità, riepilogo con evidenza dei prodotti dubbi.
3. **Step 3 (DA FARE, vedi §6)** — aggiungere i prodotti alla dispensa.

Decisioni già prese dall'utente (non rimetterle in discussione senza motivo):

- Lettura con **PaddleOCR locale + parser righe**, nessun LLM/API esterna.
- Solo i prodotti **alimentari** restano nel riepilogo; i non alimentari si escludono.
- I prodotti **duplicati** sullo scontrino valgono **una sola riga**: la quantità non si legge dallo scontrino, si chiede all'utente nello Step 2.
- Esiste una **lista di prodotti freschi comuni**; in futuro una colonna `fresco` sì/no nel catalogo decide a chi chiedere la foto della scadenza.
- I prodotti **non freschi** non chiedono la foto della scadenza, ma l'utente può scrivere la data a mano nel riepilogo (opzionale). Conseguenza: in Step 3 `products.data_scadenza` dovrà diventare **nullable** (migrazione Alembic + UI della dispensa che gestisca "nessuna scadenza"). Non è stato ancora toccato.
- Nello Step 2 la foto della scadenza si fa con un **menu a tendina** che indica di quale prodotto si sta fotografando la data; l'ordine dello scontrino è solo il default, l'utente può scegliere in che ordine fare le foto (segue come svuota la spesa).
- "Carica scontrino" apre un menu con *Scatta foto* (attivo), *Carica immagine* e *Carica documento* (disabilitati, "presto disponibile").

## 2. Git, ambiente e come provare

- Il progetto **non era un repo git**: l'ho inizializzato. `main` contiene lo stato di prima (commit `2b51f62`). Tutto il lavoro è nel branch **`feature/carica-scontrino`** così, se non piace, si torna a `main`.
- Backend: FastAPI + SQLAlchemy async + Postgres (docker-compose, porta host **5433**, utente/password/db `scadenzario`). Venv in `backend/.venv`. Test: `cd backend && .venv/bin/pytest tests -q` (83 passano).
- Frontend: Vite + React 19 + TypeScript + Tailwind + react-router + TanStack Query. `cd frontend && npx tsc -b` e `npm run lint` (i warning esistenti in `useAuthedImageUrl.ts` e `AuthContext.tsx` non sono nostri).
- Per provare da telefono: `docker compose up -d`, poi `./start_mobile.sh` (vedi `MOBILE_TESTING.md`).
- Il DB è stato svuotato (tutti gli account cancellati su richiesta dell'utente): serve registrarsi di nuovo.
- File di prova nella root: `Gemini_Generated_Image_h7wib2h7wib2h7wi.jpeg` — foto di uno **scontrino Lidl reale** (26 righe prodotto, 4 non alimentari, `CREMAS DE HORTALIZAS` ripetuta due volte, QR e testo del retro che traspaiono, foto leggermente inclinata). Non è committato; conviene spostarlo in una cartella di fixture (vedi idea 1.4).

### Come riprodurre le prove sull'immagine
Gli script che ho usato stanno nello scratchpad della sessione e non sono nel repo. Per rifarli (da `backend/`, con `.venv/bin/python`):

```python
from app.services.ocr.engine import OcrEngine
from app.services.ocr.pipeline import run_receipt_pipeline
from app.services.receipt.parser import parse_receipt_photo
from app.services.receipt.merge import merge_photos
from app.services.receipt.matching import match_catalog, is_reliable
from app.services.receipt.foods import is_non_food

eng = OcrEngine()
lines = run_receipt_pipeline(eng, open(path, "rb").read())   # righe OCR grezze
parsed = parse_receipt_photo(lines, foto=0)                   # righe prodotto
merged = merge_photos([parsed])                               # più foto: merge_photos([p0, p1, ...])
food = [l for l in merged.lines if not is_non_food(l.nome)]
for l in food: print(l.nome, l.prezzo, l.occorrenze, match_catalog(l.nome)[0])
```

Per provare la sovrapposizione: ritagliare la stessa immagine in due pezzi che si sovrappongono (io usavo `img.crop((280, 380, 1560, 1500))` e `img.crop((280, 1300, 1560, 2250))` sull'immagine 1792×2390) e passare le due liste a `merge_photos`. Risultato atteso: stessa lista della foto intera, nessuna "giuntura senza sovrapposizione".

Note: la prima esecuzione carica i modelli PaddleOCR (qualche secondo). Immagini sintetiche molto piccole (testo < ~40px di altezza) fanno perdere righe all'OCR: per test sintetici usare font grandi e immagini ≥ 1000px.

## 3. Cosa c'è oggi (Step 1)

### Frontend
- `frontend/src/pages/PantryListPage.tsx` — due bottoni fissi affiancati: "+ Aggiungi foto" e "🧾 Carica scontrino" (quest'ultimo apre `ReceiptSourceSheet`).
- `frontend/src/components/ReceiptSourceSheet.tsx` — bottom sheet con le 3 sorgenti.
- `frontend/src/pages/ReceiptFlowPage.tsx` (route `/receipt` in `App.tsx`) — orchestratore Cattura → Risultato. **Qui si agganceranno gli step successivi.**
- `frontend/src/pages/ReceiptCapturePage.tsx` — camera multi-foto: riquadro guida **verticale** (la colonna prodotti, con il box-shadow gigante per scurire il resto), ritaglio sulla colonna, miniature con ✕, bottone "Fine (n)". Dopo il primo scatto mostra in trasparenza in alto la **fascia bassa dell'ultima foto** per aiutare l'utente a ripetere le ultime 2-3 righe (garantisce la sovrapposizione). Gli scatti restano in memoria locale fino a "Fine".
- `frontend/src/pages/ReceiptResultPage.tsx` — elenco righe lette: nome, prezzo, abbinamento catalogo con punteggio, badge "da verificare" / "fresco" / "N righe sullo scontrino", avvisi (giunture senza sovrapposizione, foto senza righe, foto con errore), nota sui non alimentari ignorati. **Sola lettura** salvo "scarta riga".
- `frontend/src/api/receipts.ts` — `parseReceipt(files)`; assegna a ogni riga un `id` stabile lato client (`<timestamp>-<ordine>`) perché lo Step 2 si riferisca alle righe per id e non per posizione.
- `frontend/src/lib/cameraCrop.ts` — `guideToVideoRect`, estratta da `UploadPage.tsx` (che ora la importa). Riusa `useCameraStream` esistente.

### Backend
Endpoint **stateless** `POST /receipts/parse` (multipart `files`, max 12 foto, ordine di scatto): non salva né foto né righe, nessuna migrazione DB. Router `backend/app/routers/receipts.py`, schemi `backend/app/schemas/receipt.py`.

Pipeline per ogni foto (`backend/app/services/ocr/pipeline.py: run_receipt_pipeline`):
1. `preprocess_image(mode="scontrino")` (`preprocess.py`): CLAHE 2.0, lato lungo max 2000px.
2. `OcrEngine.run(..., det_params=...)` con soglie del detector **più basse** (`text_det_thresh=0.2`, `text_det_box_thresh=0.4`) solo per gli scontrini: con i default il detector saltava righe intere (verificato).
3. `_drop_faint_boxes`: scarta i box con **contrasto inchiostro/carta** basso (5° vs 95° percentile dei pixel del box sulla scala di grigi *senza CLAHE*, `receipt_gray()`), soglia `max(25, 0.4 × contrasto mediano della foto)`. Il testo vero ha contrasto 145-199, il testo del retro che traspare e i QR 4-16. L'idea è dell'utente: i prodotti sono stampati in nero, tutto ciò che è grigio chiaro è rumore.
4. `_recheck_weak_boxes`: i box con confidenza < 0.6 e senza cifre (max 8 per foto, i più dubbi per primi) vengono **ritagliati e riletti da soli**; il risultato si accetta solo se la confidenza è ≥ 0.8. Recupera righe che nella foto intera falliscono (es. `KIWI VERDE CESTA` letto `IE EE RR` a 0.38 perché dietro passava un QR; riletto da solo 1.0).

Poi, fuori dal worker OCR (`backend/app/services/receipt/`):
- `parser.py: parse_receipt_photo` — raggruppa i box in righe dopo aver **raddrizzato l'inclinazione** (angolo mediano del lato superiore dei box, `_estimate_skew`): senza questo, in una foto inclinata il prezzo a destra finisce sulla riga sbagliata (bug trovato: `JAMON SERRANO 2,25` invece di 2,75). Scarta frammenti a bassa confidenza non-prezzo, box prevalentemente in minuscolo dopo un primo box in maiuscolo (`_drop_lowercase_ghosts`), prezzi duplicati nella stessa riga (`_keep_best_price_box`: tipico frammento "2,09 D" della riga sopra tagliata dal bordo). Per ogni riga: separa il prezzo a destra (con lettera IVA finale), toglie quantità iniziale, codici articolo (`-0500229`), `EUR`; scarta intestazione, totale, IVA, pagamento, righe quantità/peso, sconti negativi, barcode, date. Gestisce il prodotto a peso Mercadona (nome su una riga, prezzo sulla riga di dettaglio). **Tiene** una riga con nome ma senza prezzo letto (`prezzo=None`, da verificare) dopo il primo prodotto con prezzo; scarta come intestazione le righe senza prezzo prima del primo prodotto (solo foto 0). Dalla riga `TOTAL` in poi è piè di pagina. Fallback: se in una foto non c'è nessun prezzo (utente ha inquadrato solo i nomi) ogni riga con testo è un prodotto.
- `merge.py: merge_photos` — elimina la sovrapposizione tra foto consecutive: cerca **punti di contatto (anchor)** tra la coda della foto k e la testa della k+1 (catena monotona greedy, nome simile + prezzo uguale; **non** richiede righe contigue perché l'OCR salta o legge male righe proprio nella zona comune). Un solo contatto è valido solo se entrambe le righe hanno prezzo; altrimenti ne servono due; il primo contatto deve stare nelle prime 3 righe della foto successiva. Gestisce la **riga tagliata dal bordo** (`DATE DE. CERDO` = `PATE DE CERDO`, senza prezzo, sostituita dalla versione completa). Se non c'è sovrapposizione registra la giuntura (`giunture_senza_sovrapposizione`). Alla fine `_collapse_repeated` fonde i prodotti con nome quasi identico (`token_sort_ratio ≥ 92`, **solo nome, non prezzo**) in una riga sola con `occorrenze` = quante righe erano.
- `foods.py` — `is_non_food(nome)` (parole intere, senza accenti, da `backend/app/data/non_food_es.json`, ~144 voci) e `load_fresh_products()` (da `backend/app/data/fresh_products_es.json`, ~320 nomi generici per categoria, tutti con `fresco: true, generico: true`).
- `matching.py: match_catalog(nome, k=3)` — espande le abbreviazioni da scontrino (`backend/app/data/receipt_abbreviations.json`: `LCHE`→leche, `ENT`→entera…), confronta con **catalogo supermercati + lista freschi**. Scoring: `token_sort_ratio` sul solo nome (peso 1.0) e su "marca nome" (peso 0.95); **contenimento** (tutte le parole della riga sono nel nome del catalogo e ne coprono ≥ metà: `PAN TOSTADO` ⊂ `Pan tostado classic`, ma non `BANANA` ⊂ "yogurt avena, fragola e banana"); **contenimento inverso solo per le voci generiche** (`KIWI` in `KIWI VERDE CESTA`); a parità di punteggio prevale la voce generica. Soglia "affidabile" = 80 (`MATCH_SCORE_THRESHOLD` in `product_catalog.py`). Ritorna fino a 3 `CatalogMatch` (label, brand, name, score, `fresco`).
- `backend/app/services/ocr/product_catalog.py` — `load_catalog_products()` (catalogo da `backend/app/data/product_catalog_es.json`: 3008 prodotti **di marca** da Open Food Facts per Lidl/Mercadona/Alcampo, `_complete: false`, nessun campo `fresco`).

Risposta dell'endpoint (`ReceiptParseResponse`): `righe[]` (`ordine, nome, prezzo, confidence, foto, occorrenze, match, candidati, incerto`), `giunture_senza_sovrapposizione[]`, `foto_senza_righe[]`, `foto_con_errore[]`, `non_alimentari_scartati[]`.

### Risultato verificato sull'immagine Lidl
Foto intera **e** in due foto sovrapposte danno lo stesso risultato: 21 righe alimentari con prezzi corretti, 4 non alimentari scartati (`ARNES PERRO`, `PAPEL HIGIENICO`, `PIJAMA MUJER`, `GEL DE BAÑO`), `CREMAS DE HORTALIZAS` unita (×2), tutte abbinate in modo affidabile. Questo è il **solo** scontrino su cui è stato tarato tutto.

### Lezioni apprese (leggile, ti fanno risparmiare ore)
- **Il testo del retro che traspare e i QR** sono il nemico principale su carta sottile. I filtri su testo/confidenza/minuscolo non bastano (alcuni fantasmi hanno confidenza 0.9); il filtro sul **contrasto d'inchiostro** è risolutivo. Misura sulla scala di grigi **prima del CLAHE**, perché il CLAHE rende scuro anche il fantasma.
- **Foto inclinata ⇒ prezzi sfasati di mezza riga**: raggruppare per y senza raddrizzare assegna il prezzo alla riga sbagliata *in silenzio*, che è peggio che perdere la riga.
- **`WRatio` di rapidfuzz è inadatto** a nomi brevi contro etichette lunghe (contiene un confronto parziale): `BANANA`, `KIWI` risultavano "affidabili" su prodotti sbagliati. Usare `token_sort_ratio` + contenimento con soglia di copertura.
- **Il detector PaddleOCR con soglie di default salta righe intere** negli scontrini; abbassare le soglie recupera righe ma introduce frammenti spuri ai bordi: da qui i filtri a valle (prezzi duplicati, contrasto, seconda lettura).
- **Allineamento tra foto**: pretendere una sovrapposizione contigua fallisce al primo errore OCR nella zona comune. Servono anchor tolleranti.
- **Mai perdere una riga in silenzio**: una riga con nome ma senza prezzo si tiene (`prezzo=None`); una riga di sola sovrapposizione si elimina solo con prove (nome simile + prezzo uguale).
- Su immagini molto piccole l'OCR perde righe; i test sintetici vanno fatti con testo grande.
- I **test unitari** del parser/merge/matching usano OCR "finto" (liste di box con coordinate): vedi `backend/tests/test_receipt_*.py`, `test_receipt_ink.py`, `test_receipt_foods.py`. Il caso "foto inclinata" è in `test_receipt_parser.py`.

### Cose note e non risolte
- `JUDIAS VERDES` (fresche o in barattolo?), `SALMON AL NATURAL` (quasi sempre in scatola; l'ho tolto dai freschi), `PECHUGA DE POLLO` (Realvalle cotta vs fresca): il flag `fresco` per nome è ambiguo, deve essere **correggibile dall'utente**.
- Residuo di rumore dentro un nome: `CHORIZO IBERICO EXT.IpSS-` (un frammento nello stesso box); non impedisce l'abbinamento.
- `LANGOSTINO COCIDO` poteva finire su "Langostino crudo" (85%) col solo catalogo: ora c'è la voce generica "langostino cocido" (100). Resta il rischio cocido/crudo per altri prodotti.
- Il tempo di elaborazione per foto **non è stato misurato**; la seconda lettura dei box deboli lo aumenta. Misurarlo con 6-10 foto prima di pensare alla UX di attesa.
- Lo Step 1 funziona solo con scontrini **spagnoli** (parole di scarto, abbreviazioni, non alimentari). Alcune parole italiane sono già nelle liste di scarto (TOTALE, CONTANTI, RESTO…), ma non è testato.

## 4. Idee per migliorare ancora lo Step 1

Ordinate per valore. Le prime quattro erano state proposte all'utente come "da fare adesso"; l'utente ha chiesto di scrivere tutto qui, **non ha ancora scelto quali implementare**: chiedigli prima.

1. **Quadratura con il totale.** Abbiamo i prezzi e leggiamo la riga `TOTAL` (oggi viene scartata come piè di pagina: va letta il suo importo prima di fermarsi). Sommare i prezzi di *tutte* le righe (anche non alimentari scartate e righe senza nome) e confrontarli con il totale: se manca 3,09 € sappiamo che una riga non è stata letta e quanto vale. Va esposto in `ReceiptParseResponse` (es. `totale_letto`, `somma_righe`, `differenza`). Attenzione: gli sconti (`Desc. 0,50`, righe negative) vanno sottratti; i prodotti a peso hanno il prezzo sulla riga principale. Collegata a 1b.
   - 1b. **Riga non letta**: quando c'è un prezzo senza nome (box del nome illeggibile) o la quadratura non torna, mostrare "riga non letta (3,09 €)" che l'utente può completare a mano. Oggi una riga con solo il prezzo viene ignorata.
2. **Anteprima OCR per foto, come `previewDatePhoto`.** Dopo ogni scatto inviare la foto a un endpoint tipo `POST /receipts/photo-preview` (modello: `backend/app/routers/ocr.py` + `frontend/src/api/ocr.ts`) e mostrare "14 prodotti letti, collegata alla foto precedente" oppure "nessuna riga in comune, rifai la foto più in alto". Serve poter fare il merge incrementale (inviare anche le ultime righe della foto precedente, o tenerle lato client). Evita di scoprire a fine scontrino che una giuntura è saltata.
3. **Correzioni nella schermata finale** (oggi sola lettura): scegliere tra i 3 candidati del catalogo, modificare il nome, aggiungere una riga mancante, attivare/togliere il flag `fresco`, riammettere un prodotto escluso come non alimentare (e viceversa). Importante quanto la lettura, perché `fresco` e `non alimentare` si basano su liste di parole e sbagliano ogni tanto.
4. **Set di valutazione (golden set).** Tarato su un solo scontrino ⇒ rischio overfitting. Creare `backend/tests/fixtures/receipts/` con 5-10 scontrini veri (Mercadona, Alcampo, Lidl, Carrefour…) + JSON dell'output atteso (nome, prezzo), e `backend/scripts/eval_receipts.py` che esegue la pipeline e stampa recall/precisione delle righe e dei prezzi. Servono foto reali dall'utente; **non committare scontrini con dati personali** (carta, nome) — ritagliare o oscurare. Includere anche foto storte, sfocate, con ombra, e scontrini lunghi in 2-3 foto.
5. **Alias imparati** (grande guadagno nel tempo): tabella `receipt_aliases` (testo normalizzato dello scontrino → prodotto/etichetta, per supermercato/famiglia), alimentata dalle correzioni dell'idea 3 e consultata **prima** del fuzzy match. Richiede una migrazione Alembic.
6. **Riconoscere negozio e data dall'intestazione** (prima foto): il negozio (LIDL, MERCADONA, ALCAMPO…) sceglie formato righe (Mercadona ha la quantità a sinistra; Lidl ha le lettere IVA a destra), abbreviazioni e catalogo; la **data dello scontrino** serve a stimare le scadenze (data acquisto + durata tipica) e, con negozio e totale, a riconoscere uno **scontrino già caricato**. Aggiungere i campi alla risposta.
7. **Bozza salvata**: lo Step 2 sarà lungo (decine di foto di scadenze); chiudere l'app a metà non deve perdere tutto. Salvare lo stato dello scontrino (righe, flag, foto fatte) lato server (nuove tabelle, simili a `batches`/`batch_items` in `backend/app/db/models/batch.py`) o nel browser (IndexedDB per le foto). Va deciso prima dello Step 2.
8. **Qualità della foto in tempo reale**: nitidezza (varianza del Laplaciano sul ritaglio), troppo scuro, inclinazione eccessiva, con avviso e blocco dello scatto; torcia con `track.applyConstraints({advanced:[{torch:true}]})` dove supportata; suggerimento "appoggia lo scontrino su una superficie piatta" (la carta termica si arriccia).
9. **Raddrizzamento prospettico lato server**: riconoscere i 4 bordi dello scontrino (OpenCV) e correggere la prospettiva prima dell'OCR. Il raddrizzamento di sola rotazione già c'è (solo sulle coordinate dei box); la prospettiva corregge le foto scattate molto di lato.
10. **Carica immagine / Carica documento**: dalla galleria (stesso `parseReceipt` con più file) e **PDF di scontrini digitali** (Mercadona, Lidl Plus): il PDF ha testo selezionabile ⇒ niente OCR, lettura quasi perfetta (estrarre con PyMuPDF/pdfplumber le righe con le coordinate e riusare `parser.py` e `merge.py`). Probabilmente il modo più preciso di caricare uno scontrino. Le voci sono già nel `ReceiptSourceSheet`, disabilitate.
11. **Multilingua**: scontrini italiani (l'utente è italiano, vive in Spagna): parole di scarto, non alimentari, abbreviazioni e catalogo italiani; `TZ=Europe/Madrid` nell'env.
12. **Sconti, resi e prodotti a peso**: associare `Desc.`/righe negative alla riga sopra (oggi si scartano), riconoscere i resi, e per i prodotti a peso usare peso e prezzo al kg come informazioni extra.
13. **Prestazioni**: misurare il tempo per foto; se serve, SSE con avanzamento per foto (pattern già in `batches` con `useBatchStream` / `sse-starlette`), limitare la seconda lettura ai box davvero rilevanti, oppure scalare l'immagine.
14. **Catalogo e lista freschi più ricchi**: la lista dei freschi (`fresh_products_es.json`) è scritta a mano e va estesa con ciò che compare negli scontrini reali (specie le abbreviazioni dei singoli supermercati: `LONCHAS VACA TIERNO` è una voce Lidl che ho dovuto aggiungere a mano). Un job che, per le righe incerte, segnali al team i nomi più frequenti non abbinati.

## 5. Step 2 — idee di implementazione

Obiettivo: dopo la lettura, segnare quali prodotti sono freschi, chiedere le foto delle scadenze, chiedere le quantità e mostrare un **riepilogo** con evidenza dei dubbi (stile `ReviewPage`).

- **Colonna `fresco` nel catalogo.** Ogni voce di `product_catalog_es.json` potrà avere `fresco: true | false | null` (`null` = sconosciuto ⇒ si ricade sulle parole chiave / lista freschi). Valorizzarla in `backend/scripts/fetch_product_catalog.py` dalle categorie Open Food Facts (carni, latticini freschi, frutta e verdura, pesce, piatti pronti refrigerati…). Il codice di matching già propaga `fresco` in `CatalogMatch`. Le correzioni dell'utente sovrascrivono (e alimentano gli alias, idea 4.5).
- **Flag per riga.** Il default viene da `match.fresco` (lista freschi/catalogo); l'utente lo corregge nel riepilogo. Per le righe incerte senza match: parole chiave sul nome (insalata, carne, pollo, pesce, succo…).
- **Quantità.** Nello Step 2 si chiede la quantità per ogni prodotto. `occorrenze` (quante righe dello scontrino erano quel prodotto) è un buon **valore iniziale suggerito**. Possibile ottimizzazione: se la quantità è N > 1 e il prodotto è fresco, scegliere se serve una foto per ciascuna unità (date diverse) o una sola.
- **Foto delle scadenze con menu a tendina.** Riusare `CameraCaptureGrid`, `useCameraStream` e il flusso di `UploadPage.tsx` (oggi coppia titolo+data; qui basta la **sola data**, il titolo lo conosciamo già dallo scontrino). Un `<select>` in alto indica il prodotto in corso, con spunta sui già fatti e conteggio dei mancanti; si avanza al prossimo prodotto non ancora fotografato, ma l'utente può scegliere l'ordine. Per l'OCR della data riusare `previewDatePhoto` (`POST /ocr/date-preview`) e `run_date_pipeline` (`backend/app/services/ocr/pipeline.py`, `date_extractor.py`).
- **Prodotti non freschi:** nessuna foto; campo data opzionale nel riepilogo (digitazione manuale).
- **Riepilogo.** Elenco di tutti i prodotti con: nome (modificabile, candidati del catalogo), quantità, flag fresco, data (letta o mancante), badge "da verificare" per i dubbi (match incerto, data a bassa confidenza, prodotto fresco senza data). Riusare lo stile e i componenti di `frontend/src/pages/ReviewPage.tsx` e `ExpiryBadge`.
- **Stato da tenere** nel front-end (o salvato come bozza, idea 4.7): righe dello scontrino con `id` stabile, flag, quantità, foto/date per riga.

## 6. Step 3 — idee di implementazione

- **Migrazione Alembic**: `products.data_scadenza` → nullable (e gli indici/query che la usano: `idx_products_household_scadenza`, `backend/app/services/scheduler.py` e `notifier.py` per le notifiche a 3/1 giorni devono ignorare i prodotti senza data). Aggiornare `schemas/product.py`, `PantryListPage`/`ExpiryBadge` ("nessuna scadenza").
- **Endpoint di conferma** simile a `POST /batches/{id}/confirm` (`backend/app/routers/batches.py`) ma per righe di scontrino: crea un `Product` per ogni riga (o N se quantità N con scadenze diverse; oppure un campo `quantita` su `Product` se si vuole un'unica riga con quantità — decisione di prodotto da prendere con l'utente). Salvare la foto del prodotto/della data con `backend/app/services/image_storage.py` (le foto della data si usano per la miniatura come oggi `foto_titolo_key`; per lo scontrino non c'è la foto del titolo: valutare una miniatura generica o nessuna).
- **Duplicati con la dispensa**: avvisare di possibili doppioni con prodotti già presenti (stesso nome entro N giorni, o scontrino già caricato: negozio+data+totale, idea 4.6).
- **Stima della scadenza per i non freschi** (opzionale, rimandata dall'utente): durata tipica per categoria (pasta 12 mesi, scatolame 24…), modificabile — l'utente per ora ha scelto di *non* stimarla ma di lasciare l'inserimento manuale facoltativo.
- **Pulizia**: le foto dello scontrino non vanno conservate (privacy: contengono carta, ora, punto vendita). Se in futuro si salvano, ritagliare la sola colonna prodotti.

## 7. Domande aperte per l'utente

- Quali idee dello §4 includere? (Proposta mia: 1, 3 e 4 insieme, perché la quadratura è molto più utile se l'utente può poi sistemare la riga mancante; la 2 se si vuole uno scatto più guidato.)
- Altri scontrini reali per il golden set (Mercadona, Alcampo, Carrefour, Dia, scontrini italiani)?
- Quantità N > 1 di un prodotto fresco: una foto di scadenza per ciascuna unità o una sola? E in dispensa: N righe o una riga con quantità?
- Bozza dello scontrino: lato server o nel browser?
- Il flag `fresco` deve decidere solo "chiedere la foto della data" o anche altro (es. notifiche più anticipate)?
