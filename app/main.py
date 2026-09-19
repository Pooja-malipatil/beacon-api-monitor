from dotenv import load_dotenv
load_dotenv()
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app import db_models, schemas, auth
from fastapi import FastAPI, HTTPException,Depends
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
from app.models import EndpointCreate
from app import monitor
import asyncio
from app.health_checker import run_service_check
from app.database import SessionLocal
from typing import Optional
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect
from app.ws_manager import manager
from jose import jwt, JWTError

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.start()
    manager.loop = asyncio.get_event_loop() 

    db = SessionLocal()
    try:
        active_services = db.query(db_models.Service).filter(db_models.Service.is_active == True).all()
        for service in active_services:
            schedule_service(service)
    finally:
        db.close()

    yield
    scheduler.shutdown()

# Allow the React frontend to talk to this backend
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "Beacon is running 🟢",
        "author": "Pooja-malipatil",
        "github": "https://github.com/Pooja-malipatil",
        "version": "1.0.0",
    }

@app.get("/endpoints")
async def list_endpoints():
    return list(monitor.endpoints.values())

@app.post("/endpoints")
async def add_endpoint(data: EndpointCreate):
    ep = monitor.add_endpoint(data)

    # Schedule automatic checks for this endpoint
    scheduler.add_job(
        monitor.run_check,
        "interval",
        seconds=ep.interval,
        args=[ep.id],
        id=ep.id,
        replace_existing=True
    )

    # Run first check immediately
    asyncio.create_task(monitor.run_check(ep.id))
    return ep

@app.delete("/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: str):
    # Remove from scheduler too
    if scheduler.get_job(endpoint_id):
        scheduler.remove_job(endpoint_id)

    if not monitor.delete_endpoint(endpoint_id):
        raise HTTPException(status_code=404, detail="Endpoint not found")
    return {"deleted": endpoint_id}

@app.post("/endpoints/{endpoint_id}/check")
async def check_now(endpoint_id: str):
    if endpoint_id not in monitor.endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    await monitor.run_check(endpoint_id)
    return monitor.endpoints[endpoint_id]

@app.post("/auth/register", response_model=schemas.UserOut, status_code=201)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(db_models.User).filter(db_models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = db_models.User(
        email=data.email,
        hashed_password=auth.hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token)
def login(data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(db_models.User).filter(db_models.User.email == data.email).first()
    if not user or not auth.verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = auth.create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.UserOut)
def me(current_user: db_models.User = Depends(auth.get_current_user)):
    return current_user


from typing import List

@app.post("/services", response_model=schemas.ServiceOut, status_code=201)
def create_service(
    data: schemas.ServiceCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = db_models.Service(
        name=data.name,
        url=data.url,
        method=data.method,
        expected_status=data.expected_status,
        interval_seconds=data.interval_seconds,
        timeout_seconds=data.timeout_seconds,
        group_id=data.group_id,
        owner_id=current_user.id,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    if service.is_active:
        schedule_service(service)

    return service


@app.get("/services", response_model=List[schemas.ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    return (
        db.query(db_models.Service)
        .filter(db_models.Service.owner_id == current_user.id)
        .all()
    )


def _get_owned_service(service_id: str, db: Session, current_user: db_models.User) -> db_models.Service:
    """Shared helper: fetch a service and make sure it belongs to the requester."""
    service = db.query(db_models.Service).filter(db_models.Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if service.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this service")
    return service


@app.get("/services/{service_id}", response_model=schemas.ServiceOut)
def get_service(
    service_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    return _get_owned_service(service_id, db, current_user)


@app.put("/services/{service_id}", response_model=schemas.ServiceOut)
def update_service(
    service_id: str,
    data: schemas.ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = _get_owned_service(service_id, db, current_user)

    update_fields = data.model_dump(exclude_unset=True)  # only fields the user actually sent
    for field, value in update_fields.items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    if service.is_active:
        schedule_service(service)   # also handles interval changes, via replace_existing
    else:
        unschedule_service(service.id)

    return service


@app.delete("/services/{service_id}", status_code=204)
def delete_service(
    service_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = _get_owned_service(service_id, db, current_user)
    unschedule_service(service.id)
    db.delete(service)
    db.commit()
    return None


def schedule_service(service: db_models.Service):
    job_id = f"service-{service.id}"
    scheduler.add_job(
        run_service_check,
        "interval",
        seconds=service.interval_seconds,
        args=[service.id],
        id=job_id,
        replace_existing=True,
    )


def unschedule_service(service_id: str):
    job_id = f"service-{service_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
        
@app.get("/services/{service_id}/checks", response_model=schemas.PaginatedHealthChecks)
def list_health_checks(
    service_id: str,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = _get_owned_service(service_id, db, current_user)

    query = (
        db.query(db_models.HealthCheck)
        .filter(db_models.HealthCheck.service_id == service.id)
        .order_by(db_models.HealthCheck.timestamp.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return schemas.PaginatedHealthChecks(total=total, page=page, page_size=page_size, items=items)
@app.get("/incidents", response_model=List[schemas.IncidentOut])
def list_incidents(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    return (
        db.query(db_models.Incident)
        .join(db_models.Service)
        .filter(db_models.Service.owner_id == current_user.id)
        .order_by(db_models.Incident.started_at.desc())
        .all()
    )


@app.get("/incidents/{incident_id}", response_model=schemas.IncidentOut)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    incident = (
        db.query(db_models.Incident)
        .join(db_models.Service)
        .filter(db_models.Incident.id == incident_id, db_models.Service.owner_id == current_user.id)
        .first()
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident

VALID_RULE_TYPES = ("response_time", "consecutive_failures", "uptime")


@app.post("/services/{service_id}/alert-rules", response_model=schemas.AlertRuleOut, status_code=201)
def create_alert_rule(
    service_id: str,
    data: schemas.AlertRuleCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = _get_owned_service(service_id, db, current_user)
    if data.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(status_code=400, detail=f"rule_type must be one of {VALID_RULE_TYPES}")

    rule = db_models.AlertRule(service_id=service.id, rule_type=data.rule_type, threshold=data.threshold)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@app.get("/services/{service_id}/alert-rules", response_model=List[schemas.AlertRuleOut])
def list_alert_rules(
    service_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = _get_owned_service(service_id, db, current_user)
    return service.alert_rules


@app.delete("/alert-rules/{rule_id}", status_code=204)
def delete_alert_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    rule = (
        db.query(db_models.AlertRule)
        .join(db_models.Service)
        .filter(db_models.AlertRule.id == rule_id, db_models.Service.owner_id == current_user.id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    db.delete(rule)
    db.commit()
    return None


@app.get("/alerts", response_model=List[schemas.TriggeredAlertOut])
def get_active_alerts(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    services = db.query(db_models.Service).filter(db_models.Service.owner_id == current_user.id).all()
    triggered: List[schemas.TriggeredAlertOut] = []

    for service in services:
        for rule in service.alert_rules:
            if not rule.is_active:
                continue

            if rule.rule_type == "consecutive_failures":
                if service.consecutive_failures >= rule.threshold:
                    triggered.append(schemas.TriggeredAlertOut(
                        service_id=service.id, service_name=service.name,
                        rule_type=rule.rule_type, threshold=rule.threshold,
                        current_value=service.consecutive_failures,
                        message=f"{service.name} has {service.consecutive_failures} consecutive failures (limit {int(rule.threshold)})",
                    ))

            elif rule.rule_type == "response_time":
                last_check = (
                    db.query(db_models.HealthCheck)
                    .filter(db_models.HealthCheck.service_id == service.id)
                    .order_by(db_models.HealthCheck.timestamp.desc())
                    .first()
                )
                if last_check and last_check.response_time_ms and last_check.response_time_ms >= rule.threshold:
                    triggered.append(schemas.TriggeredAlertOut(
                        service_id=service.id, service_name=service.name,
                        rule_type=rule.rule_type, threshold=rule.threshold,
                        current_value=last_check.response_time_ms,
                        message=f"{service.name} response time is {last_check.response_time_ms:.0f}ms (limit {int(rule.threshold)}ms)",
                    ))

            elif rule.rule_type == "uptime":
                total = db.query(db_models.HealthCheck).filter(db_models.HealthCheck.service_id == service.id).count()
                if total > 0:
                    successful = (
                        db.query(db_models.HealthCheck)
                        .filter(db_models.HealthCheck.service_id == service.id, db_models.HealthCheck.success == True)
                        .count()
                    )
                    uptime_pct = (successful / total) * 100
                    if uptime_pct < rule.threshold:
                        triggered.append(schemas.TriggeredAlertOut(
                            service_id=service.id, service_name=service.name,
                            rule_type=rule.rule_type, threshold=rule.threshold,
                            current_value=uptime_pct,
                            message=f"{service.name} uptime is {uptime_pct:.1f}% (limit {rule.threshold}%)",
                        ))

    return triggered

@app.get("/services/{service_id}/checks", response_model=schemas.PaginatedHealthChecks)
def list_health_checks(
    service_id: str,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = _get_owned_service(service_id, db, current_user)

    query = (
        db.query(db_models.HealthCheck)
        .filter(db_models.HealthCheck.service_id == service.id)
        .order_by(db_models.HealthCheck.timestamp.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return schemas.PaginatedHealthChecks(total=total, page=page, page_size=page_size, items=items)


from datetime import timedelta
from sqlalchemy import func


def calculate_uptime(db: Session, service_id: str, since: datetime) -> Optional[float]:
    total = (
        db.query(db_models.HealthCheck)
        .filter(db_models.HealthCheck.service_id == service_id, db_models.HealthCheck.timestamp >= since)
        .count()
    )
    if total == 0:
        return None  # no data yet for this window
    successful = (
        db.query(db_models.HealthCheck)
        .filter(
            db_models.HealthCheck.service_id == service_id,
            db_models.HealthCheck.timestamp >= since,
            db_models.HealthCheck.success == True,
        )
        .count()
    )
    return round((successful / total) * 100, 2)


@app.get("/services/{service_id}/stats", response_model=schemas.ServiceStatsOut)
def get_service_stats(
    service_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    service = _get_owned_service(service_id, db, current_user)
    now = datetime.utcnow()

    uptime_24h = calculate_uptime(db, service.id, now - timedelta(hours=24))
    uptime_7d = calculate_uptime(db, service.id, now - timedelta(days=7))

    agg = (
        db.query(
            func.avg(db_models.HealthCheck.response_time_ms),
            func.min(db_models.HealthCheck.response_time_ms),
            func.max(db_models.HealthCheck.response_time_ms),
            func.count(db_models.HealthCheck.id),
        )
        .filter(db_models.HealthCheck.service_id == service.id)
        .first()
    )
    avg_rt, min_rt, max_rt, total_checks = agg

    return schemas.ServiceStatsOut(
        service_id=service.id,
        service_name=service.name,
        uptime_24h=uptime_24h,
        uptime_7d=uptime_7d,
        avg_response_time_ms=round(avg_rt, 2) if avg_rt else None,
        min_response_time_ms=round(min_rt, 2) if min_rt else None,
        max_response_time_ms=round(max_rt, 2) if max_rt else None,
        total_checks=total_checks or 0,
    )
    
@app.post("/groups", response_model=schemas.GroupOut, status_code=201)
def create_group(
    data: schemas.GroupCreate,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    group = db_models.ServiceGroup(name=data.name, owner_id=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@app.get("/groups", response_model=List[schemas.GroupSummaryOut])
def list_groups(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    groups = db.query(db_models.ServiceGroup).filter(db_models.ServiceGroup.owner_id == current_user.id).all()

    result = []
    for group in groups:
        services = group.services  # uses the relationship we defined back in Phase 1
        result.append(schemas.GroupSummaryOut(
            id=group.id,
            name=group.name,
            total_services=len(services),
            healthy=sum(1 for s in services if s.status == "healthy"),
            degraded=sum(1 for s in services if s.status == "degraded"),
            down=sum(1 for s in services if s.status == "down"),
        ))
    return result


@app.delete("/groups/{group_id}", status_code=204)
def delete_group(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    group = (
        db.query(db_models.ServiceGroup)
        .filter(db_models.ServiceGroup.id == group_id, db_models.ServiceGroup.owner_id == current_user.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    db.delete(group)
    db.commit()
    return None

@app.get("/dashboard", response_model=schemas.DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(auth.get_current_user),
):
    services = db.query(db_models.Service).filter(db_models.Service.owner_id == current_user.id).all()
    service_ids = [s.id for s in services]

    active_incidents_count = (
        db.query(db_models.Incident)
        .join(db_models.Service)
        .filter(db_models.Service.owner_id == current_user.id, db_models.Incident.status == "open")
        .count()
    )

    recent_incidents = (
        db.query(db_models.Incident)
        .join(db_models.Service)
        .filter(db_models.Service.owner_id == current_user.id)
        .order_by(db_models.Incident.started_at.desc())
        .limit(5)
        .all()
    )

    avg_response_time = None
    overall_uptime_24h = None

    if service_ids:
        avg_result = (
            db.query(func.avg(db_models.HealthCheck.response_time_ms))
            .filter(db_models.HealthCheck.service_id.in_(service_ids))
            .scalar()
        )
        avg_response_time = round(avg_result, 2) if avg_result else None

        since = datetime.utcnow() - timedelta(hours=24)
        total_checks = (
            db.query(db_models.HealthCheck)
            .filter(db_models.HealthCheck.service_id.in_(service_ids), db_models.HealthCheck.timestamp >= since)
            .count()
        )
        if total_checks > 0:
            successful_checks = (
                db.query(db_models.HealthCheck)
                .filter(
                    db_models.HealthCheck.service_id.in_(service_ids),
                    db_models.HealthCheck.timestamp >= since,
                    db_models.HealthCheck.success == True,
                )
                .count()
            )
            overall_uptime_24h = round((successful_checks / total_checks) * 100, 2)

    return schemas.DashboardOut(
        total_services=len(services),
        healthy=sum(1 for s in services if s.status == "healthy"),
        degraded=sum(1 for s in services if s.status == "degraded"),
        down=sum(1 for s in services if s.status == "down"),
        active_incidents=active_incidents_count,
        avg_response_time_ms=avg_response_time,
        overall_uptime_24h=overall_uptime_24h,
        recent_incidents=recent_incidents,
    )
    


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    # WebSockets can't send an Authorization header easily, so the token
    # is passed as a query parameter instead: ws://.../ws?token=xxxxx
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # we don't expect messages FROM the client, just keep the connection open
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)