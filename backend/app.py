import asyncio
import os
import socket

from fastapi import FastAPI

app = FastAPI()

NAME = os.getenv("BACKEND_NAME", "backend")
HOSTNAME = socket.gethostname()
# Makes this backend slower on purpose, to test how the balancer copes with uneven servers.
# Applies to "/" only, so health checks stay fast.
DELAY_SECONDS = float(os.getenv("BACKEND_DELAY_MS", "0")) / 1000


def identity() -> dict:
    return {"name": NAME, "hostname": HOSTNAME}


@app.get("/")
async def root():
    if DELAY_SECONDS:
        await asyncio.sleep(DELAY_SECONDS)
    return identity()


@app.get("/health")
def health():
    return {"status": "ok", **identity()}


@app.get("/slow")
async def slow(seconds: float = 2.0):
    await asyncio.sleep(seconds)
    return {"slept": seconds, **identity()}
