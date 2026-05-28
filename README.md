# IMS - Event-Driven Incident Management System

IMS is an incident management system for DevOps environments. It ingests alerts, classifies incidents, tracks lifecycle state changes, and notifies the right team members.

## Hackathon Problem Statement

This project was built for the Northern Trust hackathon challenge to create an Event-Driven Incident Management System from scratch.

The required goal is to:

- Ingest simulated alerts from monitoring/log/metric sources
- Classify incidents and route them into resolution workflows
- Manage lifecycle stages from detection to post-mortem
- Notify responders and stakeholders through communication channels
- Provide manual controls to acknowledge, escalate, and resolve incidents
- Show incident status and ownership in a real-time dashboard

This implementation prioritizes infrastructure incidents over application incidents and demonstrates different handling paths based on severity and type.

## Requirement Coverage

| Challenge Requirement | Status | Implementation in IMS |
|-----------------------|--------|------------------------|
| Alert ingestion from simulated sources | Implemented | `simulate_alerts.py` sends events to `POST /api/alerts` |
| Event classification and routing | Implemented | Backend classifier maps alerts by type/severity into workflows |
| Incident workflow engine | Implemented | Lifecycle transitions: DETECTED -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED -> CLOSED |
| Notifications to responders/stakeholders | Implemented | Email notifications and escalation reminders |
| Manual intervention controls | Implemented | Dashboard/API actions for acknowledge, investigate, resolve, close |
| Real-time incident visibility | Implemented | Dashboard lists active incidents with severity and status |
| Infrastructure-first response behavior | Implemented | Higher-severity infrastructure incidents are prioritized and escalated sooner |
| SLA or analytics insights (optional) | Partially implemented | Analytics endpoint available (`/api/analytics`) |
| Multi-channel notifications (Slack/SMS) | Not in current scope | Email channel implemented; architecture can be extended |

## Demo Scope for Judges

The demo should walk through two scenarios end-to-end:

1. Infrastructure incident (high severity): immediate notification, workflow progression, and escalation behavior.
2. Application incident (lower severity): lower-priority routing and standard resolution path.

This directly aligns with the judging expectation to show clear priority differences and routing logic.

## Team

- Rutuja Milind Jain
- Sumit Tatyabhau Sonawane
- Aryan Sunil Moon
- Abhay G K
- SADHANA R A
- Chinmay Umesh
- MAHESH M G

## Overview

The platform includes:

- Alert ingestion via API
- Incident classification and workflow management
- Escalation and reminder automation
- Email notifications
- Live dashboard for monitoring and actions

## High-Level Architecture

```
simulate_alerts.py
      |
      v POST /api/alerts
+-----------------------------------------+
|               FastAPI Backend           |
|                                         |
|  Classifier -> State Machine            |
|               (DETECTED, ACKNOWLEDGED,  |
|                INVESTIGATING, RESOLVED, |
|                CLOSED)                  |
|                                         |
|  Escalation Worker                      |
|                                         |
|  PostgreSQL   MongoDB   Redis           |
|  (incidents)  (signals) (cache)         |
+-----------------------------------------+
      |
      v
React Dashboard (http://localhost:3001)
```

## Prerequisites

- Docker Desktop
- Python 3.10+ (for local alert simulation)

## Quick Start

1. Configure environment variables in `.env`.
2. Start the stack:

```bash
docker-compose down -v
docker-compose up --build
```

3. Open the dashboard at `http://localhost:3001`.
4. In a new terminal, run the simulator:

```bash
python simulate_alerts.py
```

Optional:

```bash
python simulate_alerts.py --url http://localhost:8000 --delay 3
```

## Email Configuration (Gmail SMTP)

1. Enable 2FA for your Google account.
2. Generate an app password from Google Account settings.
3. Set these values in `.env`:

```env
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
ONCALL_EMAIL=oncall-recipient@gmail.com
APP_TEAM_EMAIL=app-team-recipient@gmail.com
SENIOR_EMAIL=senior-recipient@gmail.com
```

4. Restart backend service after updating credentials:

```bash
docker-compose restart backend
```

## Typical Demo Flow

1. Start the simulator.
2. Observe new incidents in the dashboard.
3. Move incidents through lifecycle actions:
   DETECTED -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED -> CLOSED.
4. Verify escalation/reminder behavior based on timeout rules.

## API Reference

### Alert Ingestion

```http
POST /api/alerts
```

Example payload:

```json
{
  "type": "infrastructure",
  "severity": "P1",
  "service": "web-server-01",
  "message": "CPU at 98%",
  "source": "prometheus"
}
```

### Incident APIs

```http
GET    /api/incidents
GET    /api/incidents/{id}
PATCH  /api/incidents/{id}/acknowledge
PATCH  /api/incidents/{id}/investigate
PATCH  /api/incidents/{id}/resolve
PATCH  /api/incidents/{id}/close
GET    /api/analytics
GET    /api/health
```

Interactive docs: `http://localhost:8000/docs`

## Severity and Routing

| Severity | Type           | Primary Notification Target |
|----------|----------------|-----------------------------|
| P1       | Infrastructure | On-call engineer            |
| P2       | Infrastructure | On-call engineer            |
| P3       | Application    | Application team            |
| P4       | Application    | Application team            |

## Escalation Rules

| Condition                               | Timeout  | Action                |
|-----------------------------------------|----------|-----------------------|
| P1/P2 infrastructure in DETECTED        | 5 min    | Notify senior engineer |
| Any incident in INVESTIGATING           | 30 min   | Send reminder email    |

Configurable in `.env`:

```env
ESCALATION_TIMEOUT_MINUTES=5
REMINDER_TIMEOUT_MINUTES=30
```

## Data Model

| Table          | Purpose                                |
|----------------|----------------------------------------|
| work_items     | Incident records in PostgreSQL         |
| notifications  | Outbound email log                     |
| audit_log      | Incident state transition history      |
| rca_records    | Post-incident RCA data                 |
| signal_metrics | Time-series metrics (TimescaleDB)      |
| signals        | Raw signal documents (MongoDB)         |

## Project Structure

```
.
|-- simulate_alerts.py
|-- docker-compose.yml
|-- backend
|   |-- main.py
|   |-- config.py
|   |-- api/routers.py
|   |-- db/database.py
|   |-- db/init.sql
|   |-- models/schemas.py
|   `-- services/
|       |-- classifier.py
|       |-- email.py
|       |-- escalation.py
|       |-- ingestion.py
|       `-- workflow.py
`-- frontend
    `-- src
        |-- App.tsx
        |-- api.ts
        `-- components/
            |-- Dashboard.tsx
            |-- IncidentDetail.tsx
            `-- ResolveModal.tsx
```
