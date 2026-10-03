from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Product, User
from app.db.session import async_session
from app.services.notifier import send_expiry_email

scheduler = AsyncIOScheduler(timezone=settings.TZ)


async def check_expirations() -> dict:
    """Controlla i prodotti in scadenza per ogni household e invia un'email a ogni
    utente della household. Idempotente: soglia con `<=` (non `==`) e i flag
    notificato_1gg/notificato_3gg garantiscono che nessun avviso parta due volte,
    anche se il job salta un giorno (container down) o un prodotto viene aggiunto
    quando è già vicino alla scadenza."""
    today = date.today()
    sent_count = 0

    async with async_session() as db:
        result = await db.execute(
            select(Product).where(
                Product.stato == "attivo",
                (
                    (Product.notificato_1gg.is_(False) & (Product.data_scadenza <= today + timedelta(days=1)))
                    | (Product.notificato_3gg.is_(False) & (Product.data_scadenza <= today + timedelta(days=3)))
                ),
            )
        )
        products = list(result.scalars().all())

        by_household: dict = {}
        for product in products:
            by_household.setdefault(product.household_id, []).append(product)

        for household_id, items in by_household.items():
            scade_1gg = [
                p for p in items if not p.notificato_1gg and p.data_scadenza <= today + timedelta(days=1)
            ]
            scade_3gg = [
                p
                for p in items
                if not p.notificato_3gg and p.data_scadenza <= today + timedelta(days=3) and p not in scade_1gg
            ]
            if not scade_1gg and not scade_3gg:
                continue

            users_result = await db.execute(select(User).where(User.household_id == household_id))
            users = users_result.scalars().all()

            any_sent = False
            for user in users:
                try:
                    await send_expiry_email(user.email, scade_1gg, scade_3gg)
                    sent_count += 1
                    any_sent = True
                except Exception:
                    continue  # un invio fallito non deve bloccare gli altri utenti/household

            if not any_sent:
                # Nessun invio riuscito per questa household (es. BREVO_API_KEY mancante
                # o non valida): NON segnare come notificato, altrimenti l'avviso
                # verrebbe silenziato per sempre anche dopo aver corretto la chiave.
                continue

            for product in scade_1gg:
                product.notificato_1gg = True
            for product in scade_3gg:
                product.notificato_3gg = True

        await db.commit()

    return {"prodotti_esaminati": len(products), "email_inviate": sent_count}


def start_scheduler() -> None:
    scheduler.add_job(
        check_expirations,
        CronTrigger(hour=8, minute=0, timezone=settings.TZ),
        id="check_expirations",
        misfire_grace_time=3600,
        replace_existing=True,
    )
    scheduler.start()


def shutdown_scheduler() -> None:
    scheduler.shutdown(wait=False)
