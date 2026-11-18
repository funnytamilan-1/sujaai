import httpx
from app.config import settings

class WhatsAppError(Exception):
    pass

async def send_image_template(phone: str, template_name: str, language: str, image_url: str, body_text: str = "") -> str:
    if not settings.whatsapp_configured:
        raise WhatsAppError("WhatsApp Cloud API is not configured. Add credentials in environment variables.")
    url = f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/{settings.whatsapp_phone_number_id}/messages"
    components = [{"type": "header", "parameters": [{"type": "image", "image": {"link": image_url}}]}]
    if body_text:
        components.append({"type": "body", "parameters": [{"type": "text", "text": body_text[:1024]}]})
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "template",
        "template": {"name": template_name, "language": {"code": language}, "components": components},
    }
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"})
    if response.is_error:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise WhatsAppError(f"WhatsApp API error ({response.status_code}): {detail}")
    data = response.json()
    messages = data.get("messages") or []
    if not messages:
        raise WhatsAppError("WhatsApp API returned no message ID.")
    return messages[0]["id"]
