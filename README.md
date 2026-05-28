# 🛡️ IMS — Event-Driven Incident Management System

A production-grade incident management platform for DevOps environments. Automatically detects, classifies, routes, and tracks incidents from detection through resolution with email notifications and a live dashboard.

## 🏗️ Architecture

```
simulate_alerts.py
      │
      ▼ POST /api/alerts
┌─────────────────────────────────────────┐
│           FastAPI Backend               │
│                                         │
│  ┌──────────┐   ┌────────────────────┐  │
│  │Classifier│──▶│  State Machine     │  │
│  └──────────┘   │  DETECTED          │  │
│                 │  ACKNOWLEDGED      │  │
│  ┌──────────┐   │  INVESTIGATING     │  │
│  │Escalation│   │  RESOLVED          │  │
│  │  Loop    │   │  CLOSED            │  │
│  └──────────┘   └────────────────────┘  │
│                        │                │
│              ┌─────────┴─────────┐      │
│        PostgreSQL    MongoDB   Redis     │
│        (incidents)  (signals) (cache)   │
└─────────────────────────────────────────┘
      │
      ▼
  React Dashboard (http://localhost:3001)
```

## 🚀 Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) running

### 1. Clone and configure

```bash
# Edit .env to add your Gmail credentials (see Email Setup below)
```

### 2. Reset and start (first time or after schema changes)

```bash
# IMPORTANT: Always use -v to reset the database on first run or schema updates
docker-compose down -v
docker-compose up --build
```

### 3. Open the dashboard

Visit: **http://localhost:3001**

### 4. Run the alert simulator

Open a new terminal:
```bash
python simulate_alerts.py
```

Or with custom settings:
```bash
python simulate_alerts.py --url http://localhost:8000 --delay 3
```

---

## 📧 Gmail SMTP Setup (for real emails)

1. **Enable 2-Factor Authentication** on your Google account:
   https://myaccount.google.com/security

2. **Generate an App Password**:
   https://myaccount.google.com/apppasswords
   - Select "Mail" → "Other (custom name)" → "IMS"
   - Copy the 16-character password

3. **Edit `.env`**:
   ```env
   SMTP_USER=your-actual-gmail@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop    # 16-char app password
   ONCALL_EMAIL=your-actual-gmail@gmail.com  # Your inbox for demo
   APP_TEAM_EMAIL=your-actual-gmail@gmail.com
   SENIOR_EMAIL=your-actual-gmail@gmail.com
   ```

4. **Restart the backend**:
   ```bash
   docker-compose restart backend
   ```

---

## 🎬 Demo Flow

1. **Start simulator** → Alerts arrive, dashboard shows new incidents
2. **P1 infrastructure incident** appears at top in red (DETECTED)
3. **Email arrives** in oncall inbox
4. **Click Acknowledge** → Status changes to ACKNOWLEDGED
5. **Click Investigate** → Status changes to INVESTIGATING
6. **Wait 5 min** → Auto-escalation email fires to senior engineer
7. **Click Resolve** → Enter resolution note → Status becomes RESOLVED
8. **Click Close** → Incident archived as CLOSED

---

## 📡 API Reference

### Alert Ingestion
```
POST /api/alerts
{
  "type": "infrastructure",
  "severity": "P1",
  "service": "web-server-01",
  "message": "CPU at 98%",
  "source": "prometheus"
}
```

### Incident Management
```
GET    /api/incidents                    # List all incidents
GET    /api/incidents/{id}               # Full detail + timeline + emails
PATCH  /api/incidents/{id}/acknowledge   # → ACKNOWLEDGED
PATCH  /api/incidents/{id}/investigate   # → INVESTIGATING
PATCH  /api/incidents/{id}/resolve       # → RESOLVED (needs resolution_note)
PATCH  /api/incidents/{id}/close         # → CLOSED
GET    /api/analytics                    # Stats, MTTR, service frequency
GET    /api/health                       # System health check
```

### Interactive API Docs
Visit: **http://localhost:8000/docs**

---

## 🚦 Incident Severity & Routing

| Severity | Type           | Who gets notified      | Action |
|----------|----------------|------------------------|--------|
| P1       | Infrastructure | oncall@company.com     | Page immediately |
| P2       | Infrastructure | oncall@company.com     | Page urgently |
| P3       | Application    | appteam@company.com    | Email, standard |
| P4       | Application    | appteam@company.com    | Email, low priority |

---

## ⚡ Auto-Escalation Rules

| Condition | Timeout | Action |
|-----------|---------|--------|
| P1/P2 Infrastructure in DETECTED | 5 minutes | Email senior-engineer@company.com |
| Any incident in INVESTIGATING | 30 minutes | Send reminder email |

Adjust in `.env`:
```env
ESCALATION_TIMEOUT_MINUTES=5
REMINDER_TIMEOUT_MINUTES=30
```

---

## 🗃️ Database Schema

| Table | Purpose |
|-------|---------|
| `work_items` | All incidents (PostgreSQL) |
| `notifications` | Email log per incident |
| `audit_log` | Every state change with timestamp |
| `rca_records` | Post-mortem analysis |
| `signal_metrics` | Time-series (TimescaleDB) |
| `signals` | Raw signal store (MongoDB) |

---

## 📁 Project Structure

```
IMS/
├── simulate_alerts.py        # Alert simulator script
├── .env                      # Configuration
├── docker-compose.yml
├── backend/
│   ├── main.py               # FastAPI app + background tasks
│   ├── config.py             # Settings
│   ├── api/
│   │   └── routers.py        # All API endpoints
│   ├── models/
│   │   └── schemas.py        # Pydantic models
│   ├── services/
│   │   ├── classifier.py     # Alert → incident classification
│   │   ├── email.py          # Gmail SMTP notifications
│   │   ├── escalation.py     # Auto-escalation background job
│   │   ├── ingestion.py      # Signal ingestion (legacy)
│   │   └── workflow.py       # State machine
│   └── db/
│       ├── database.py       # DB connections
│       └── init.sql          # Schema
└── frontend/
    └── src/
        ├── App.tsx
        ├── api.ts            # API client
        └── components/
            ├── Dashboard.tsx       # Main dashboard
            ├── IncidentDetail.tsx  # Incident detail + timeline
            └── ResolveModal.tsx    # Resolution note modal
```
