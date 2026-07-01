import asyncio

from kag.interface.solver.reporter_abc import ReporterABC

# Sentinel enqueued when the reported task finishes, so a consumer draining the
# queue knows to stop.
DONE = object()


class QueueReporter(ReporterABC):
    """Bridge the pipeline's report events onto an ``asyncio.Queue``.

    The solver reports progress (planning, retrieval, and -- via the streaming
    generator -- each answer token) through ``add_report_line``. This reporter
    turns each call into an event on a queue that a streaming consumer (e.g. an
    SSE endpoint) drains.

    Thread-safe: retrieval executors run their sync ``invoke`` in worker threads
    (``asyncio.to_thread``), so events are scheduled back onto the owning event
    loop with ``call_soon_threadsafe`` rather than touched cross-thread.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._loop = asyncio.get_running_loop()
        self.queue: asyncio.Queue = asyncio.Queue()

    def add_report_line(self, segment, tag_name, content, status, **kwargs):
        event = {"segment": segment, "tag": tag_name, "content": content, "status": status}
        self._loop.call_soon_threadsafe(self.queue.put_nowait, event)

    def do_report(self):
        # Events are pushed directly from add_report_line; the periodic
        # cycle-report hook is unused for the streaming bridge.
        return None

    def signal_done(self) -> None:
        """Enqueue the end sentinel via the same ordered path as events.

        Scheduling through ``call_soon_threadsafe`` (rather than a direct
        ``put_nowait``) guarantees the sentinel lands after every event already
        scheduled -- otherwise it could overtake the last deferred token.
        """
        self._loop.call_soon_threadsafe(self.queue.put_nowait, DONE)
