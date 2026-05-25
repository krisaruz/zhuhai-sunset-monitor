import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.models.database import init_db
from src.models.sunset import SunsetRecord  # noqa: F401 - ensure table creation
from src.models.location import ShootingLocation, NotificationLog  # noqa: F401
from src.routers import api, dashboard
from src.tasks.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Path("data").mkdir(exist_ok=True)
    await init_db()

    # Seed locations
    from src.seed_locations import seed
    await seed()

    # Start scheduler
    setup_scheduler()

    yield

    # Shutdown
    from src.tasks.scheduler import scheduler
    scheduler.shutdown(wait=False)


app = FastAPI(title="珠海晚霞监控", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
app.include_router(api.router)
app.include_router(dashboard.router)
