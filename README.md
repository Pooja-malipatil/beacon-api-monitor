# ◈ Beacon

> API reliability and incident monitoring platform — automated health checks, incident tracking, alert rules, and real-time updates over WebSockets.

Built with **FastAPI** + **React** + **PostgreSQL**

[![MIT License](https://img.shields.io/badge/License-MIT-7c5cfc.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00e676.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-00b0ff.svg)](https://reactjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org)
[![Python](https://img.shields.io/badge/Python-3.10+-ffea00.svg)](https://python.org)

---

## About

Beacon watches APIs and web services on a schedule, detects outages using consecutive-failure logic (to avoid false alarms from single network blips), and automatically opens and resolves incidents as services go down and recover — with every status change pushed live to the dashboard over WebSockets, no polling required.

This project began from a small open-source starter — a basic endpoint pinger with email alerts — and was substantially extended with a full database layer, JWT authentication, incident lifecycle management, configurable alert rules, uptime/response-time analytics, service groups, and real-time WebSocket updates.

---

## Features

- **JWT Authentication** — each user only sees and manages their own services
- **Service Management** — register any URL with a custom method, expected status code, check interval, and timeout
- **Automated Background Monitoring** — real async HTTP checks on a configurable schedule via APScheduler + HTTPX
- **Three-State Health Model** — Healthy / Degraded / Down, with consecutive-failure detection before anything is marked down
- **Automatic Incident Lifecycle** — incidents open the instant a service goes down and resolve automatically on recovery, with duration tracked
- **Configurable Alert Rules** — response time thresholds, consecutive failure limits, uptime minimums, evaluated live
- **Real-Time Dashboard** — status changes push instantly over WebSockets
- **Uptime & Response-Time Analytics** — 24h/7d uptime %, average/min/max response times
- **Service Groups** — organize related services with aggregated group health
- **Paginated Health-Check History** — full audit trail of every check ever run
- **REST API** — full FastAPI backend with interactive Swagger docs

---

## Tech Stack

| Layer      | Technology                                  |
|------------|----------------------------------------------|
| Backend    | Python, FastAPI, HTTPX                       |
| Database   | PostgreSQL, SQLAlchemy                       |
| Scheduler  | APScheduler                                  |
| Auth       | JWT (python-jose), bcrypt                    |
| Real-time  | WebSockets (native FastAPI)                  |
| Frontend   | React, Vite, Axios                           |

---

## Architecture

```
React (Vite) frontend  <-->  FastAPI backend  <-->  PostgreSQL
                                   |
                          APScheduler (background jobs)
                                   |
                          HTTPX (pings monitored URLs)
```

The frontend talks to the backend over REST for all standard operations, and keeps one WebSocket connection open per logged-in user for real-time status push notifications.

---

## Database Design

| Table            | Purpose                                                  |
|-------------------|-----------------------------------------------------------|
| `users`           | Registered accounts                                       |
| `services`        | Monitored endpoints, owned by a user, optionally grouped  |
| `service_groups`  | Logical grouping of related services                      |
| `health_checks`   | One row per check ever run — the raw history               |
| `incidents`       | Created automatically on outage, resolved on recovery      |
| `alert_rules`     | User-defined thresholds, evaluated live                    |

All relationships use proper foreign keys — a service belongs to one user and optionally one group; a service has many health checks and many incidents.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL (local install or via Docker)



### 1. Set up the database

```bash
docker-compose up db
```
(or point `DATABASE_URL` at any local/hosted PostgreSQL instance instead)

### 2. Set up the backend

```bash
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
copy .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/watchpost
JWT_SECRET=replace-this-with-a-long-random-string
```

### 4. Start the backend

```bash
python -m uvicorn app.main:app --reload
```

Backend runs at: `http://127.0.0.1:8000`
API Docs at: `http://127.0.0.1:8000/docs`

### 5. Set up and start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## Usage

### Registering and logging in

Open the frontend, register an account, and log in — every service you add is scoped to your account only.

### Adding a service to monitor

**From the dashboard:**
- Click **"+ Add Service"**
- Fill in name, URL, method, expected status code, check interval, and timeout
- Click **Save**

**From the API docs:**
- Go to `http://127.0.0.1:8000/docs`, authorize with your JWT token
- Use `POST /services` with a body like:

```json
{
  "name": "My API",
  "url": "https://api.example.com/health",
  "method": "GET",
  "expected_status": 200,
  "interval_seconds": 60,
  "timeout_seconds": 5
}
```

### How monitoring works

1. Every active service is scheduled as a recurring background job.
2. Each run pings the service and records success/failure, status code, response time, and any error.
3. **Healthy** — succeeded, fast. **Degraded** — succeeded, but slower than the configured threshold. **Down** — failed 3 consecutive checks.
4. Going down opens an incident automatically; recovering resolves it automatically, with duration calculated.
5. Every status change is pushed instantly to the dashboard over WebSocket.

---

## API Reference

```
Auth
POST   /auth/register
POST   /auth/login
GET    /auth/me

Services
POST   /services
GET    /services
GET    /services/{id}
PUT    /services/{id}
DELETE /services/{id}
GET    /services/{id}/checks?page=&page_size=
GET    /services/{id}/stats

Incidents
GET    /incidents
GET    /incidents/{id}

Alert Rules
POST   /services/{id}/alert-rules
GET    /services/{id}/alert-rules
DELETE /alert-rules/{id}
GET    /alerts

Groups
POST   /groups
GET    /groups
DELETE /groups/{id}

Dashboard
GET    /dashboard

Real-time
WS     /ws?token=<jwt>
```

Full interactive docs available at `/docs` when the backend is running.

---

## Project Structure

```
beacon/
├── app/
│   ├── main.py          <- FastAPI routes
│   ├── database.py      <- SQLAlchemy engine/session setup
│   ├── db_models.py     <- SQLAlchemy table definitions
│   ├── schemas.py       <- Pydantic request/response schemas
│   ├── auth.py          <- Password hashing + JWT logic
│   ├── health_checker.py<- Background health check + incident logic
│   ├── ws_manager.py    <- WebSocket connection manager
│   └── __init__.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx       <- Login/register + WebSocket connection
│   │   ├── Dashboard.jsx <- Main dashboard UI
│   │   └── api.js        <- Shared Axios client
│   └── package.json
├── .env.example
├── requirements.txt
├── docker-compose.yml
├── LICENSE
└── README.md
```

---

## Known Limitations / Next Steps

- [ ] Cursor-based pagination (offset-based pagination can shift slightly on live-changing data)
- [ ] Automated test suite (currently manually verified during development)
- [ ] Email/SMS alert delivery (alerts currently surface in-dashboard only)
- [ ] p95 latency percentile
- [ ] Deploy to cloud

## Roadmap (completed)

- [x] JWT authentication with per-user data isolation
- [x] Service CRUD with real database persistence
- [x] Automated background health checks
- [x] Consecutive-failure detection and status model
- [x] Automatic incident lifecycle (open/resolve)
- [x] Configurable alert rules
- [x] Real-time WebSocket updates
- [x] Uptime and response-time analytics
- [x] Service groups
- [x] Aggregated dashboard endpoint

---

## Attribution

This project builds on an original open-source endpoint-monitoring starter (basic pinging, in-memory storage, and email alerts). The database layer, authentication, incident management, alerting system, analytics, service groups, real-time updates, and rebuilt frontend were added on top of that foundation.

---

## Author

**YOUR_NAME**

- GitHub: [@Pooja-malipatil](https://github.com/Pooja-malipatil)

---

## License

This project is for learning and educational purpose

---

*If you find this useful, consider giving it a star on GitHub.*