import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import router as api_router
from db.database import (
    close_mongodb,
    close_postgres,
    close_redis,
    init_mongodb,
    init_postgres,
    init_redis,
    get_redis,
)
from services.escalation import run_escalation_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ims.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize connections
    await init_postgres()
    await init_mongodb()
    await init_redis()
    logger.info("Database connections initialized.")

    # Start background tasks
    observability_task = asyncio.create_task(observability_loop())
    escalation_task = asyncio.create_task(run_escalation_loop())
    logger.info("Background tasks started: observability + escalation")

    yield

    # Cleanup
    escalation_task.cancel()
    observability_task.cancel()
    await close_redis()
    await close_mongodb()
    await close_postgres()
    logger.info("Database connections closed.")


async def observability_loop():
    """Prints throughput metrics (Signals/sec) to the console every 5 seconds."""
    while True:
        try:
            await asyncio.sleep(5)
            redis_client = get_redis()

            count_str = await redis_client.get("metric:signals_count")
            count = int(count_str) if count_str else 0

            if count > 0:
                await redis_client.set("metric:signals_count", 0)

            signals_per_sec = count / 5.0
            logger.info(f"THROUGHPUT: {signals_per_sec:.2f} Signals/sec")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Observability loop error: {e}")

app = FastAPI(title="IMS — Incident Management System", lifespan=lifespan)

# CORS configuration
cors_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

import os
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in cors_origins:
    cors_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(api_router, prefix="/api")