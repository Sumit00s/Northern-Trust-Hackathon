#!/usr/bin/env python3
"""
simulate_alerts.py — Alert Simulator for IMS Demo

Sends fake monitoring alerts to the backend API to simulate
a real DevOps environment with infrastructure and application incidents.

Usage:
    python simulate_alerts.py
    python simulate_alerts.py --url http://localhost:8000 --delay 5

Press Ctrl+C to stop.
"""

import json
import random
import sys
import time
import argparse
from urllib import request, error
from datetime import datetime


# ─── Alert Scenarios ──────────────────────────────────────────────

INFRASTRUCTURE_ALERTS = [
    {
        "type": "infrastructure",
        "severity": "P1",
        "service": "db-primary-01",
        "message": "Database server is DOWN — connection refused on port 5432",
        "source": "prometheus",
    },
    {
        "type": "infrastructure",
        "severity": "P1",
        "service": "web-server-01",
        "message": "CPU usage at 98% for 5 minutes — server unresponsive",
        "source": "prometheus",
    },
    {
        "type": "infrastructure",
        "severity": "P2",
        "service": "core-network-switch",
        "message": "Network packet loss at 45% — significant degradation detected",
        "source": "nagios",
    },
    {
        "type": "infrastructure",
        "severity": "P1",
        "service": "auth-server-02",
        "message": "Server out of memory — OOM killer triggered, processes killed",
        "source": "prometheus",
    },
    {
        "type": "infrastructure",
        "severity": "P2",
        "service": "load-balancer-01",
        "message": "Load balancer health check failing — 3 of 5 backends down",
        "source": "cloudwatch",
    },
]

APPLICATION_ALERTS = [
    {
        "type": "application",
        "severity": "P3",
        "service": "checkout-api",
        "message": "Error rate spiked to 12% — above 5% threshold for 3 minutes",
        "source": "datadog",
    },
    {
        "type": "application",
        "severity": "P4",
        "service": "product-search-service",
        "message": "Average response time 4200ms — SLA threshold is 2000ms",
        "source": "newrelic",
    },
    {
        "type": "application",
        "severity": "P3",
        "service": "payment-gateway",
        "message": "Payment service timeout — 23% of transactions failing",
        "source": "datadog",
    },
    {
        "type": "application",
        "severity": "P4",
        "service": "notification-service",
        "message": "Email delivery queue backed up — 15,000 messages pending",
        "source": "cloudwatch",
    },
    {
        "type": "application",
        "severity": "P3",
        "service": "user-auth-api",
        "message": "Login failure rate at 8% — possible authentication service issue",
        "source": "datadog",
    },
]

# All scenarios combined for the demo
ALL_ALERTS = INFRASTRUCTURE_ALERTS + APPLICATION_ALERTS


def send_alert(api_url: str, alert: dict) -> bool:
    """Send a single alert to the backend API."""
    url = f"{api_url}/api/alerts"
    payload = json.dumps(alert).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    try:
        req = request.Request(url, data=payload, headers=headers, method="POST")
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            data = json.loads(body)
            return True, data
    except error.HTTPError as e:
        body = e.read().decode()
        return False, {"error": str(e), "body": body}
    except Exception as e:
        return False, {"error": str(e)}


def print_alert(alert: dict, success: bool, response: dict, index: int):
    """Pretty-print alert status to terminal."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    alert_type = alert["type"].upper()
    severity = alert["severity"]
    service = alert["service"]

    # Color codes
    RED = "\033[91m"
    ORANGE = "\033[93m"
    YELLOW = "\033[33m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    GRAY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    severity_color = {
        "P1": RED,
        "P2": ORANGE,
        "P3": YELLOW,
        "P4": BLUE,
    }.get(severity, GRAY)

    type_color = RED if alert_type == "INFRASTRUCTURE" else BLUE

    status_icon = f"{GREEN}✓{RESET}" if success else f"{RED}✗{RESET}"
    action = response.get("action", "unknown")

    print(f"\n{GRAY}[{timestamp}]{RESET} Alert #{index}")
    print(f"  {severity_color}{BOLD}{severity}{RESET} │ {type_color}{alert_type}{RESET} │ {BOLD}{service}{RESET}")
    print(f"  {GRAY}↳ {alert['message'][:70]}{RESET}")
    print(f"  {status_icon} API response: {action} — ID: {response.get('incident_id', 'N/A')[:8]}...")


def run_demo_sequence(api_url: str, delay: float):
    """
    Run the demo sequence: send a mix of infra and app alerts.
    Prioritizes infrastructure alerts first for demo clarity.
    """
    print(f"\n{'='*60}")
    print(f"  🛡️  IMS Alert Simulator")
    print(f"{'='*60}")
    print(f"  Target: {api_url}/api/alerts")
    print(f"  Delay: {delay}s between alerts")
    print(f"  Alerts: {len(ALL_ALERTS)} scenarios loaded")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    # Wait for backend to be ready
    print("⏳ Waiting for backend to be ready...")
    for attempt in range(30):
        try:
            req = request.Request(f"{api_url}/api/health", method="GET")
            with request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"✅ Backend is ready!\n")
                    break
        except Exception:
            pass
        time.sleep(2)
        print(f"   Attempt {attempt + 1}/30...")
    else:
        print("⚠️  Could not reach backend. Proceeding anyway...\n")

    # Demo sequence: send infra alerts first, then app alerts
    # Interleave for realistic simulation
    sequence = [
        INFRASTRUCTURE_ALERTS[0],   # DB down (P1) - most critical
        APPLICATION_ALERTS[0],       # checkout error rate (P3)
        INFRASTRUCTURE_ALERTS[2],    # Network packet loss (P2)
        APPLICATION_ALERTS[2],       # payment timeout (P3)
        INFRASTRUCTURE_ALERTS[1],    # CPU spike (P1)
        APPLICATION_ALERTS[1],       # slow response (P4)
        INFRASTRUCTURE_ALERTS[3],    # OOM (P1)
        APPLICATION_ALERTS[4],       # auth failure rate (P3)
        INFRASTRUCTURE_ALERTS[4],    # load balancer (P2)
        APPLICATION_ALERTS[3],       # notification queue (P4)
    ]

    count = 0
    alert_index = 0

    while True:
        # Pick alert from sequence then repeat randomly
        if alert_index < len(sequence):
            alert = sequence[alert_index]
            alert_index += 1
        else:
            # After the initial sequence, send random repeats to simulate ongoing issues
            alert = random.choice(ALL_ALERTS)

        count += 1
        success, response = send_alert(api_url, alert)
        print_alert(alert, success, response, count)

        # Vary delay slightly for realism
        jitter = random.uniform(-1, 1)
        sleep_time = max(1, delay + jitter)
        time.sleep(sleep_time)


def main():
    parser = argparse.ArgumentParser(description="IMS Alert Simulator")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend API base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds between alerts (default: 5)"
    )
    args = parser.parse_args()

    try:
        run_demo_sequence(args.url, args.delay)
    except KeyboardInterrupt:
        print(f"\n\n✋ Simulator stopped. Goodbye!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
