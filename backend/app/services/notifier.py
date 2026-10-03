import httpx
from jinja2 import BaseLoader, Environment

from app.core.config import settings
from app.db.models import Product

EMAIL_TEMPLATE = """
<html><body style="font-family: sans-serif; color: #0f172a;">
  <h2>Aggiornamento scadenze dispensa</h2>
  {% if scade_1gg %}
  <h3 style="color: #dc2626;">Scadono domani</h3>
  <ul>{% for p in scade_1gg %}<li>{{ p.nome }} — {{ p.data_scadenza.strftime('%d/%m/%Y') }}</li>{% endfor %}</ul>
  {% endif %}
  {% if scade_3gg %}
  <h3 style="color: #d97706;">Scadono tra 3 giorni</h3>
  <ul>{% for p in scade_3gg %}<li>{{ p.nome }} — {{ p.data_scadenza.strftime('%d/%m/%Y') }}</li>{% endfor %}</ul>
  {% endif %}
</body></html>
"""

_template = Environment(loader=BaseLoader()).from_string(EMAIL_TEMPLATE)


async def send_expiry_email(to_email: str, scade_1gg: list[Product], scade_3gg: list[Product]) -> None:
    if not settings.BREVO_API_KEY:
        raise RuntimeError("BREVO_API_KEY non configurata")

    html = _template.render(scade_1gg=scade_1gg, scade_3gg=scade_3gg)
    payload = {
        "sender": {"email": settings.NOTIFY_EMAIL_FROM, "name": "Scadenzario"},
        "to": [{"email": to_email}],
        "subject": "Prodotti in scadenza nella tua dispensa",
        "htmlContent": html,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.BREVO_API_KEY, "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
