"""Caps how many conversations the shared in-memory checkpointer keeps."""

import threading
from collections import OrderedDict


class ThreadRegistry:
    """Tracks conversation threads by recent use and deletes the oldest beyond max_threads."""

    def __init__(self, checkpointer, max_threads: int):
        self.checkpointer = checkpointer
        self.max_threads = max_threads
        self._order: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def touch(self, thread_id: str) -> None:
        with self._lock:
            self._order[thread_id] = None
            self._order.move_to_end(thread_id)
            while len(self._order) > self.max_threads:
                oldest, _ = self._order.popitem(last=False)
                self.checkpointer.delete_thread(oldest)

    def forget(self, thread_id: str) -> None:
        with self._lock:
            self._order.pop(thread_id, None)
            self.checkpointer.delete_thread(thread_id)
