import asyncio
import itertools

import aiohttp
from aiohttp import web

BACKENDS = [
    "http://localhost:8001",
    "http://localhost:8002",
    "http://localhost:8003",
]

# Headers that describe a single connection, not the message.
# A proxy must not forward them (RFC 7230 section 6.1).
# HOP_BY_HOP is the standard name for the next machine in line 
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

_round_robin_backend = itertools.cycle(BACKENDS)


def forward_headers_without_irrelevant(request: web.Request) -> dict[str, str]:
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "host"
    }
    client_ip = request.remote or ""
    previous = request.headers.get("X-Forwarded-For")
    headers["X-Forwarded-For"] = f"{previous}, {client_ip}" if previous else client_ip
    return headers


async def proxy(request: web.Request) -> web.StreamResponse:
    server_to_send = next(_round_robin_backend)
    url = server_to_send + request.path_qs
    session: aiohttp.ClientSession = request.app["session"]

    try:
        async with session.request(
            request.method,
            url,
            headers=forward_headers_without_irrelevant(request),
            data=request.content if request.can_read_body else None,
            allow_redirects=False,
        ) as upstream:
            response = web.StreamResponse(status=upstream.status, reason=upstream.reason)
            for key, value in upstream.headers.items():
                if key.lower() not in HOP_BY_HOP:
                    response.headers[key] = value
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(64 * 1024):
                await response.write(chunk)
            await response.write_eof()
            return response
    except aiohttp.ClientConnectionError:
        return web.Response(status=502, text=f"Bad gateway: cannot reach {server_to_send}\n")
    except asyncio.TimeoutError:
        return web.Response(status=504, text=f"Gateway timeout: {server_to_send}\n")


async def client_session(app: web.Application):
    timeout = aiohttp.ClientTimeout(total=30, connect=3)
    # auto_decompress=False keeps bytes identical to what the backend sent,
    # so Content-Encoding and Content-Length stay correct.
    async with aiohttp.ClientSession(timeout=timeout, auto_decompress=False) as session:
        app["session"] = session
        yield


def create_app() -> web.Application:
    app = web.Application()
    app.cleanup_ctx.append(client_session)
    app.router.add_route("*", "/{tail:.*}", proxy)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), port=8080)
