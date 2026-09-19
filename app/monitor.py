import httpx
import asyncio
import os
from datetime import datetime
from typing import Dict
from app.models import Endpoint, CheckResult, EndpointCreate
from app.alerts import send_down_alert, send_up_alert
import uuid

# In-memory store (we'll upgrade to a DB later)
endpoints: Dict[str, Endpoint] = {}

async def ping_endpoint(endpoint: Endpoint) -> CheckResult:
    """Actually ping a URL and record the result."""
    start = datetime.now()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.request(endpoint.method, endpoint.url)
            latency = (datetime.now() - start).total_seconds() * 1000

            return CheckResult(
                status_code=response.status_code,
                latency_ms=round(latency, 2),
                checked_at=datetime.now(),
                message="OK" if response.status_code < 400 else f"HTTP {response.status_code}"
            )

    except httpx.TimeoutException:
        return CheckResult(
            status_code=None,
            latency_ms=None,
            checked_at=datetime.now(),
            message="Connection timed out"
        )
    except Exception as e:
        return CheckResult(
            status_code=None,
            latency_ms=None,
            checked_at=datetime.now(),
            message=str(e)
        )

async def run_check(endpoint_id: str):
    """Run a check and update the endpoint's history."""
    ep = endpoints.get(endpoint_id)
    if not ep:
        return

    result = await ping_endpoint(ep)

    # Track previous status before updating
    prev_status = ep.status

    # Determine new status
    if result.status_code and result.status_code < 400:
        new_status = "up"
    else:
        new_status = "down"

    # Fire alert only when status CHANGES
    alert_email = os.getenv("ALERT_EMAIL", "")
    if alert_email:
        if new_status == "down" and prev_status != "down":
            print(f"🔴 {ep.name} is DOWN — sending alert to {alert_email}")
            asyncio.create_task(send_down_alert(ep.name, ep.url, result.message, alert_email))
        elif new_status == "up" and prev_status == "down":
            print(f"🟢 {ep.name} recovered — sending alert to {alert_email}")
            asyncio.create_task(send_up_alert(ep.name, ep.url, alert_email))

    ep.status = new_status

    # Keep last 50 checks
    ep.history = (ep.history + [result])[-50:]
    ep.last_check = result

    # Calculate uptime %
    good = sum(1 for h in ep.history if h.status_code and h.status_code < 400)
    ep.uptime_pct = round((good / len(ep.history)) * 100, 1)

def add_endpoint(data: EndpointCreate) -> Endpoint:
    """Add a new endpoint to monitor."""
    ep = Endpoint(id=str(uuid.uuid4()), **data.model_dump())
    endpoints[ep.id] = ep
    return ep

def delete_endpoint(endpoint_id: str) -> bool:
    if endpoint_id in endpoints:
        del endpoints[endpoint_id]
        return True
    return False