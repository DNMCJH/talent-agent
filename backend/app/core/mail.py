"""Email sending via Resend HTTP API.

We hit `POST https://api.resend.com/emails` directly with httpx instead of pulling
in the resend SDK — it's a single call and the SDK doesn't add value here.

If `settings.resend_api_key` is empty, send_email is a no-op (logs a warning).
This lets the app run in environments without email configured.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"


async def send_email(*, to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Returns True on success, False on failure (logged but not raised)."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set — skipping email to %s (subject=%s)", to, subject)
        return False

    payload: dict[str, object] = {
        "from": settings.resend_from,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                RESEND_ENDPOINT,
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
        if resp.status_code >= 400:
            logger.error("Resend send failed (%s): %s", resp.status_code, resp.text[:300])
            return False
        return True
    except httpx.HTTPError as e:
        logger.error("Resend HTTP error: %s", e)
        return False


def build_verification_email(*, link: str, to_email: str) -> tuple[str, str, str]:
    """Returns (subject, html, text). Bilingual by default — friendlier for our users."""
    subject = "Verify your Talent Agent email / 邮箱验证"
    text = (
        f"Hi,\n\nPlease verify your Talent Agent email by visiting:\n{link}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"你好，\n\n请点击以下链接验证你的 Talent Agent 邮箱：\n{link}\n\n"
        f"链接 24 小时内有效。\n"
    )
    html = f"""
<div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto;">
  <h2>Verify your email / 验证邮箱</h2>
  <p>Hi {to_email},</p>
  <p>Click the button to verify your Talent Agent account email:</p>
  <p style="margin: 24px 0;">
    <a href="{link}" style="background: #111; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 6px;">Verify email</a>
  </p>
  <p style="font-size: 12px; color: #666;">Link expires in 24 hours / 链接 24 小时内有效</p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;" />
  <p style="font-size: 12px; color: #666;">If you did not sign up, just ignore this email.</p>
</div>
""".strip()
    return subject, html, text
