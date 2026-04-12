"""Sample FastAPI backend for testing OpenOps."""

import logging
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mock Backend API",
    description="Sample backend for OpenOps testing",
    version="0.1.0",
)

DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database_connected: bool


class Item(BaseModel):
    id: int
    name: str
    description: str | None = None


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    db_connected = DATABASE_URL is not None

    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        database_connected=db_connected,
    )


@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    """Get an item by ID."""
    if item_id < 1:
        raise HTTPException(status_code=404, detail="Item not found")

    return Item(
        id=item_id,
        name=f"Item {item_id}",
        description=f"This is item number {item_id}",
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Mock Backend API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
