import asyncio
import io
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.routers import auth, batches, notifications, ocr, products, receipts
from app.services.scheduler import shutdown_scheduler, start_scheduler
from app.workers.pool import create_pool, process_image_task, shutdown_pool


async def _warmup_pool(pool, workers: int) -> None:
    """Forza l'avvio di ogni processo worker (e il caricamento del modello OCR al suo
    interno) subito, così il primo batch reale dell'utente non paga il cold-start."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (100, 100), color="white").save(buf, format="PNG")
    dummy_bytes = buf.getvalue()

    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(pool, process_image_task, dummy_bytes, "titolo") for _ in range(workers)
    ]
    await asyncio.gather(*tasks)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = create_pool()
    await _warmup_pool(pool, settings.OCR_WORKERS)
    start_scheduler()
    yield
    shutdown_scheduler()
    shutdown_pool()
    await engine.dispose()


app = FastAPI(title="Scadenzario API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(products.router)
app.include_router(batches.router)
app.include_router(ocr.router)
app.include_router(notifications.router)
app.include_router(receipts.router)


@app.get("/health")
async def health():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
