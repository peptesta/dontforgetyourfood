# Foto di debug

Metti qui le foto (jpg/png/heic, anche dritte dal telefono) della F. Cad. dubbie da
analizzare, poi lancia dalla cartella `backend/`:

```bash
.venv/bin/python scripts/debug_ocr.py
```

Senza argomenti processa tutte le immagini presenti in questa cartella in modalità
`data`. I risultati (immagini intermedie + box OCR + ragionamento) finiscono in
`scripts/debug_output/<nome_foto>_data/`.

Per una singola foto o la modalità titolo:

```bash
.venv/bin/python scripts/debug_ocr.py debug_input/foto.jpg --mode titolo
```
