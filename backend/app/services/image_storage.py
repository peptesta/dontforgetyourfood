"""Storage delle foto persistite (oggi solo il titolo, vedi NEXT_SESSION.md e la
conversazione di progettazione). Interfaccia astratta + un'unica implementazione su
disco locale: il resto del codice parla solo con `ImageStorage`/`get_image_storage()`,
così un domani si può aggiungere un'implementazione S3-compatibile senza toccare
nient'altro (routers/batches.py, routers/products.py) — basta cambiare
IMAGE_STORAGE_BACKEND e implementare la nuova classe qui.

Limiti noti dell'implementazione locale (da tenere a mente prima di usarla in
produzione):
- Un solo nodo: se in futuro il backend gira su più container/macchine dietro un load
  balancer, ognuno vedrebbe solo i file scritti su se stesso, a meno di un filesystem
  di rete condiviso.
- Nessuna ridondanza/backup automatico: un disco perso è un'immagine persa (S3 offre
  durabilità multi-zona out of the box).
- Nessuna pulizia: le chiavi di BatchItem/Product non confermati/eliminati restano
  come file orfani, cresce senza limite finché non si aggiunge un job di pulizia.
- Bind mount di sviluppo: in docker-compose.yml oggi la persistenza avviene perché
  l'intera cartella app/ è montata dall'host (stesso meccanismo che già persiste
  app/data/product_catalog_es.json) — comodo in sviluppo, ma un'immagine Docker
  "pulita" (senza bind mount, es. in un vero deploy) needs un volume esplicito montato
  su IMAGE_STORAGE_DIR per non perdere le foto ad ogni riavvio del container.
"""
import re
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings

_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9/_.-]+$")


class ImageStorage(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def load(self, key: str) -> bytes | None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalDiskImageStorage(ImageStorage):
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # difesa base da path traversal: la key è generata da noi (uuid-based), ma
        # meglio non fidarsi ciecamente se un giorno arrivasse da altrove.
        if not _SAFE_KEY_RE.match(key) or ".." in key.split("/"):
            raise ValueError(f"chiave immagine non valida: {key!r}")
        return self._base_dir / key

    def save(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def load(self, key: str) -> bytes | None:
        path = self._resolve(key)
        if not path.is_file():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)


_storage: ImageStorage | None = None


def get_image_storage() -> ImageStorage:
    global _storage
    if _storage is None:
        if settings.IMAGE_STORAGE_BACKEND != "local":
            raise RuntimeError(
                f"backend di storage immagini non supportato: {settings.IMAGE_STORAGE_BACKEND!r}"
            )
        _storage = LocalDiskImageStorage(Path(settings.IMAGE_STORAGE_DIR))
    return _storage
