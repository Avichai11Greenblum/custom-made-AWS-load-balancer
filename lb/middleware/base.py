from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence

from aiohttp import web

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class Middleware(ABC):
    """One layer wrapped around the request handler (Decorator pattern).

    A layer can act before the request goes on, after the response comes back,
    or stop the request early by returning its own response without calling
    call_next.
    """

    @abstractmethod
    async def handle(self, request: web.Request, call_next: Handler) -> web.StreamResponse:
        """Process the request. Call `await call_next(request)` to pass it inward."""


def build_chain(handler: Handler, middlewares: Sequence[Middleware]) -> Handler:
    """Wrap handler in the middlewares. The first one in the list is the outermost.

    With [A, B] a request passes A, then B, then the handler, and the response
    travels back through B, then A.
    """
    for middleware in reversed(middlewares):
        handler = _wrap(middleware, handler)
    return handler


def _wrap(middleware: Middleware, next_handler: Handler) -> Handler:
    async def wrapped(request: web.Request) -> web.StreamResponse:
        return await middleware.handle(request, next_handler)

    return wrapped
