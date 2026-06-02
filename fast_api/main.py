from fastapi import FastAPI
import logging

from app.db import init_db
from app.routers.items import router as items_router
from app.routers.system import router as system_router
from app.routers.ml import router as ml_router
from app.auth.router import router as auth_router


from app.auth import models as auth_models
from app.db import engine

logger = logging.getLogger(__name__)


app = FastAPI(title="Python Nutshell FastAPI Demo")

print("Starting FastAPI application...")

@app.on_event("startup")
def on_startup():
	# Keep API docs available even when DB is temporarily unavailable.
	try:
		auth_models.User.metadata.create_all(bind=engine)
		init_db()
		pass
	except Exception as exc:
		logger.warning("Database init skipped during startup: %s", exc)

app.include_router(system_router)
app.include_router(items_router)
app.include_router(ml_router)
app.include_router(auth_router)