import asyncio
import os
import socket

from fastapi import FastAPI

app = FastAPI()

NAME = os.getenv("BACKEND_NAME", "backend")
HOSTNAME = socket.gethostname()


def identity() -> dict:
    return {"name": NAME, "hostname": HOSTNAME}


@app.get("/")
def root():
    return identity()


@app.get("/health")
def health():
    return {"status": "ok", **identity()}


@app.get("/slow")
async def slow(seconds: float = 2.0):
    await asyncio.sleep(seconds)
    return {"slept": seconds, **identity()}
