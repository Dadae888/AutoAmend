from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 - registers the Device model on Base
from .config import settings
from .db import Base, engine
from .routes import billing, llm, status


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AutoAmend AI backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status.router)
app.include_router(llm.router)
app.include_router(billing.router)


@app.get("/")
def root() -> dict:
    return {"service": "AutoAmend AI backend", "status": "ok"}
