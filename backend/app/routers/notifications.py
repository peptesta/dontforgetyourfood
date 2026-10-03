from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.services.scheduler import check_expirations

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/check")
async def trigger_check(_=Depends(get_current_user)):
    """Forza subito il controllo scadenze/invio email, senza aspettare lo scheduler
    giornaliero — utile per testare la configurazione Brevo prima di affidarcisi."""
    return await check_expirations()
