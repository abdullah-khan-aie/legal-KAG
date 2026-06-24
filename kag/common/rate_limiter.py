# Minimal stand-in for kag.common.rate_limiter.RATE_LIMITER_MANGER.
#
# RerankModelABC decorates its async call with a rate limiter obtained from the
# manager. Server-free we don't throttle, so the limiter is a pass-through that
# returns the wrapped coroutine function unchanged.


class _NoopLimiter:
    # RerankModelABC uses the limiter as `async with self.limiter:`
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RateLimiterManger:
    def __init__(self, *args, **kwargs):
        self._limiter = _NoopLimiter()

    def get_rate_limiter(self, *args, **kwargs):
        return self._limiter


RATE_LIMITER_MANGER = RateLimiterManger()
