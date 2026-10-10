import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
from backend.config import Config
from schema import ListingItem, SearchFilter
from backend.db import get_setting

logger = logging.getLogger(__name__)

def send_alert_email(filter_obj: SearchFilter, new_items: List[ListingItem]) -> bool:
    if not new_items:
        return True

    recipient = get_setting("alert_email", Config.DEFAULT_ALERT_EMAIL)
    if not recipient:
        logger.warning("No recipient alert email configured.")
        return False

    smtp_user = Config.SMTP_USER
    smtp_pass = Config.SMTP_PASS

    subject = f"[Marketplace Alert] {len(new_items)} New Matching Item(s) - {filter_obj.name}"

    # Build HTML body
    items_html = ""
    for item in new_items:
        img_tag = f'<img src="{item.image_url}" alt="{item.title}" style="max-width:180px; max-height:140px; object-fit:cover; border-radius:6px; margin-right:15px;" />' if item.image_url else ''
        items_html += f"""
        <div style="display:flex; border:1px solid #e2e8f0; border-radius:8px; padding:12px; margin-bottom:12px; background-color:#ffffff;">
            {img_tag}
            <div>
                <h3 style="margin:0 0 6px 0; font-size:16px;"><a href="{item.url}" target="_blank" style="color:#2563eb; text-decoration:none;">{item.title}</a></h3>
                <p style="margin:0 0 4px 0; font-weight:bold; color:#16a34a; font-size:15px;">{item.price}</p>
                <p style="margin:0 0 8px 0; color:#64748b; font-size:13px;">📍 {item.location}</p>
                <a href="{item.url}" target="_blank" style="display:inline-block; padding:6px 12px; background:#2563eb; color:#fff; text-decoration:none; border-radius:4px; font-size:13px;">View on Facebook</a>
            </div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color:#f8fafc; padding:20px; color:#1e293b;">
        <div style="max-width:650px; margin:0 auto; background-color:#ffffff; padding:24px; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="margin-top:0; color:#1e293b; border-bottom:2px solid #e2e8f0; padding-bottom:10px;">Marketplace Scanner Alert</h2>
            <p style="font-size:14px; color:#475569;">Found <strong>{len(new_items)}</strong> new matching listing(s) for filter: <strong>{filter_obj.name}</strong> (Postcode: {filter_obj.postcode}, Radius: {filter_obj.radius_km}km).</p>
            {items_html}
            <hr style="border:none; border-top:1px solid #e2e8f0; margin:20px 0;" />
            <p style="font-size:12px; color:#94a3b8; text-align:center;">Facebook Marketplace Scanner &bull; Automated local alert</p>
        </div>
    </body>
    </html>
    """

    if not smtp_user or not smtp_pass:
        logger.info(f"[SIMULATED EMAIL] To: {recipient} | Subject: {subject} | {len(new_items)} items. (Configure SMTP_USER and SMTP_PASS in .env to send real emails)")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = recipient

        part = MIMEText(html_content, "html")
        msg.attach(part)

        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipient, msg.as_string())
        logger.info(f"Alert email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False
