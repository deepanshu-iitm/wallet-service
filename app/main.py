from fastapi import FastAPI
from app.db.session import engine
from sqlalchemy import text
from app.db.base import Base
from app.db import models

app = FastAPI(title="Internal Wallet Service")

from app.routes.transactions import router as transactions_router

app.include_router(transactions_router)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/db-check")
def db_check():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {"db": result.scalar()}