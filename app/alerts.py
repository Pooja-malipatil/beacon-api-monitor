from dotenv import load_dotenv
load_dotenv()

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from typing import Optional
import os

# Email config — we'll load these from a .env file
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", ""),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", ""),
    MAIL_FROM=os.getenv("MAIL_FROM", ""),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)

async def send_down_alert(endpoint_name: str, url: str, reason: str, to_email: str):
    """Send an email alert when an endpoint goes down."""
    try:
        message = MessageSchema(
            subject=f"🔴 [{endpoint_name}] is DOWN — Beacon Alert",
            recipients=[to_email],
            body=f"""
            <html><body style="font-family: monospace; background: #0a0a0b; color: #e8e8f0; padding: 32px;">
                <div style="max-width: 500px; margin: 0 auto; background: #111113; border: 1px solid #2a2a2f; border-radius: 12px; padding: 28px;">
                    <h2 style="color: #ff3d71; margin-bottom: 16px;">🔴 Endpoint Down</h2>
                    <p style="color: #8888a0; margin-bottom: 24px;">Watchpost detected an issue with your endpoint.</p>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #2a2a2f;">
                            <td style="padding: 10px 0; color: #55556a; font-size: 12px;">ENDPOINT</td>
                            <td style="padding: 10px 0; color: #e8e8f0;">{endpoint_name}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #2a2a2f;">
                            <td style="padding: 10px 0; color: #55556a; font-size: 12px;">URL</td>
                            <td style="padding: 10px 0; color: #e8e8f0;">{url}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; color: #55556a; font-size: 12px;">REASON</td>
                            <td style="padding: 10px 0; color: #ff3d71;">{reason}</td>
                        </tr>
                    </table>
                    <p style="margin-top: 24px; font-size: 11px; color: #55556a;">Sent by Beacon — API reliability monitoring</p>
                </div>
            </body></html>
            """,
            subtype="html"
        )
        fm = FastMail(conf)
        await fm.send_message(message)
        print(f"📧 Alert sent for {endpoint_name}")
    except Exception as e:
        print(f"❌ Failed to send alert: {e}")

async def send_up_alert(endpoint_name: str, url: str, to_email: str):
    """Send a recovery email when endpoint comes back up."""
    try:
        message = MessageSchema(
            subject=f"🟢 [{endpoint_name}] is back UP — Beacon Alert",
            recipients=[to_email],
            body=f"""
            <html><body style="font-family: monospace; background: #0a0a0b; color: #e8e8f0; padding: 32px;">
                <div style="max-width: 500px; margin: 0 auto; background: #111113; border: 1px solid #2a2a2f; border-radius: 12px; padding: 28px;">
                    <h2 style="color: #00e676; margin-bottom: 16px;">🟢 Endpoint Recovered</h2>
                    <p style="color: #8888a0; margin-bottom: 24px;">Your endpoint is back online.</p>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #2a2a2f;">
                            <td style="padding: 10px 0; color: #55556a; font-size: 12px;">ENDPOINT</td>
                            <td style="padding: 10px 0; color: #e8e8f0;">{endpoint_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; color: #55556a; font-size: 12px;">URL</td>
                            <td style="padding: 10px 0; color: #e8e8f0;">{url}</td>
                        </tr>
                    </table>
                    <p style="margin-top: 24px; font-size: 11px; color: #55556a;">Sent by Beacon — open source API monitoring</p>
                </div>
            </body></html>
            """,
            subtype="html"
        )
        fm = FastMail(conf)
        await fm.send_message(message)
        print(f"📧 Recovery alert sent for {endpoint_name}")
    except Exception as e:
        print(f"❌ Failed to send recovery alert: {e}")