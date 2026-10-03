FROM python:3.12-slim

WORKDIR /app

# libgl1/libglib/libsm6/libxext6/libxrender1: richiesti da opencv-contrib-python
# (dipendenza transitiva di paddleocr) anche in esecuzione headless.
# libgomp1: richiesto da paddlepaddle per l'inferenza CPU multi-thread.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Necessario per evitare un crash verificato empiricamente nel path di inferenza
# oneDNN di paddlepaddle 3.x su CPU (v. app/services/ocr/engine.py).
ENV PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

# Pre-scarica i pesi del modello OCR in build, non al primo avvio in produzione.
RUN python -c "from app.services.ocr.engine import OcrEngine; OcrEngine()"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
