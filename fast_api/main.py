from fastapi import FastAPI

from app.db import init_db
from app.routers.items import router as items_router
from app.routers.system import router as system_router
from app.routers.ml import router as ml_router

app = FastAPI(title="Python Nutshell FastAPI Demo")

print("Starting FastAPI application...")

# @app.on_event("startup")
# def on_startup():
	# init_db()

app.include_router(system_router)
app.include_router(items_router)
app.include_router(ml_router)