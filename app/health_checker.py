import time
import httpx
from datetime import datetime
from app.database import SessionLocal
from app import db_models
from app.ws_manager import broadcast_update
RESPONSE_TIME_DEGRADED_THRESHOLD_MS = 1000  # simple fixed threshold for now
CONSECUTIVE_FAILURES_FOR_DOWN = 3


def run_service_check(service_id: str):
    db = SessionLocal()


def run_service_check(service_id: str):
    db = SessionLocal()
    try:
        service = db.query(db_models.Service).filter(db_models.Service.id == service_id).first()
        if not service or not service.is_active:
            print(f"[2] Service missing or inactive, skipping")
            return

        print(f"[3] Found service, making request to {service.url}")
        previous_status = service.status

        success = False
        status_code = None
        response_time_ms = None
        error_message = None

        start = time.perf_counter()
        try:
            with httpx.Client(timeout=service.timeout_seconds) as client:
                response = client.request(service.method, service.url)
            response_time_ms = (time.perf_counter() - start) * 1000
            status_code = response.status_code
            success = status_code == service.expected_status
            if not success:
                error_message = f"Expected status {service.expected_status}, got {status_code}"
        except httpx.TimeoutException:
            error_message = "Request timed out"
        except httpx.RequestError as e:
            error_message = f"Connection error: {str(e)}"


        check = db_models.HealthCheck(
            service_id=service.id,
            timestamp=datetime.utcnow(),
            success=success,
            status_code=status_code,
            response_time_ms=response_time_ms,
            error_message=error_message,
        )
        db.add(check)

        if success:
            service.consecutive_failures = 0
            if response_time_ms is not None and response_time_ms > RESPONSE_TIME_DEGRADED_THRESHOLD_MS:
                service.status = "degraded"
            else:
                service.status = "healthy"

            open_incident = (
                db.query(db_models.Incident)
                .filter(db_models.Incident.service_id == service.id, db_models.Incident.status == "open")
                .first()
            )
            if open_incident:
                open_incident.status = "resolved"
                open_incident.resolved_at = datetime.utcnow()
        else:
            service.consecutive_failures += 1
            if service.consecutive_failures >= CONSECUTIVE_FAILURES_FOR_DOWN:
                was_already_down = service.status == "down"
                service.status = "down"
                if not was_already_down:
                    incident = db_models.Incident(
                        service_id=service.id,
                        started_at=datetime.utcnow(),
                        status="open",
                        reason=error_message or f"Failed {CONSECUTIVE_FAILURES_FOR_DOWN} consecutive checks",
                    )
                    db.add(incident)

    
        db.commit()

        if service.status != previous_status:
            broadcast_update(service.owner_id, {
                "type": "status_change",
                "service_id": service.id,
                "service_name": service.name,
                "old_status": previous_status,
                "new_status": service.status,
            })
        
    except Exception as e:
        print(f"Health check failed for service {service_id}: {e}")
    finally:
        db.close()