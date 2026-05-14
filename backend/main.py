import os
import sqlite3

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Prelegal API")

DB_PATH = os.path.join(os.path.dirname(__file__), "prelegal.db")


def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


_frontend_dir = os.path.join(os.path.dirname(__file__), "frontend_out")
if os.path.exists(_frontend_dir):
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
