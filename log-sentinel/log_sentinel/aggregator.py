"""Log file watcher and rolling statistics aggregator."""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable

from .models import LogEntry, RollingStats
from .parsers import ParserFunc, parse_auto


class RollingWindow:
    """Time-bounded sliding window of log entries.

    Thread-safe: all mutations and reads go through a lock.
    """

    def __init__(self, window_seconds: int = 300) -> None:
        self._window_seconds = window_seconds
        self._entries: deque[LogEntry] = deque()
        self._lock = threading.Lock()

    def add(self, entry: LogEntry) -> None:
        with self._lock:
            self._entries.append(entry)
            self._evict()

    def stats(self) -> RollingStats:
        with self._lock:
            self._evict()
            s = RollingStats()
            s.total_entries = len(self._entries)
            if not self._entries:
                return s
            s.window_start = self._entries[0].timestamp
            s.window_end = self._entries[-1].timestamp
            for e in self._entries:
                level = e.level
                if level == "ERROR":
                    s.error_count += 1
                elif level == "CRITICAL":
                    s.critical_count += 1
                elif level == "WARNING":
                    s.warning_count += 1
                elif level == "DEBUG":
                    s.debug_count += 1
                else:
                    s.info_count += 1
            return s

    def _evict(self) -> None:
        cutoff = time.time() - self._window_seconds
        while self._entries and self._entries[0].timestamp < cutoff:
            self._entries.popleft()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)


class LogAggregator:
    """Watches a log file, parses new lines, and maintains rolling statistics.

    Handles partial writes (buffers the trailing incomplete line) and log
    rotation (detects inode changes or file truncation and re-opens from
    the beginning).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        parser: ParserFunc = parse_auto,
        window_seconds: int = 300,
        poll_interval: float = 1.0,
        on_entry: Callable[[LogEntry], None] | None = None,
    ) -> None:
        self._path = Path(path)
        self._parser = parser
        self._poll_interval = poll_interval
        self._window = RollingWindow(window_seconds)
        self._on_entry = on_entry
        self._buffer = ""
        self._inode: int | None = None
        self._position: int = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def stats(self) -> RollingStats:
        return self._window.stats()

    def process_existing(self) -> RollingStats:
        """One-shot: read the entire file and return stats."""
        if not self._path.exists():
            return RollingStats()
        with open(self._path) as f:
            for line in f:
                self._ingest_line(line)
        return self._window.stats()

    def start(self) -> None:
        """Start watching the log file in a background thread."""
        self._stop_event.clear()
        self._seek_to_end()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _seek_to_end(self) -> None:
        if not self._path.exists():
            self._inode = None
            self._position = 0
            return
        stat = os.stat(self._path)
        self._inode = stat.st_ino
        self._position = stat.st_size

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except OSError:
                pass
            self._stop_event.wait(self._poll_interval)

    def _poll_once(self) -> None:
        if not self._path.exists():
            return

        stat = os.stat(self._path)

        # Rotation: inode changed → new file, start from beginning
        if self._inode is not None and stat.st_ino != self._inode:
            self._inode = stat.st_ino
            self._position = 0
            self._buffer = ""

        # Truncation: file got smaller → start from beginning
        if stat.st_size < self._position:
            self._position = 0
            self._buffer = ""

        if stat.st_size == self._position:
            return

        self._inode = stat.st_ino
        with open(self._path) as f:
            f.seek(self._position)
            chunk = f.read()
            self._position = f.tell()

        self._process_chunk(chunk)

    def _process_chunk(self, chunk: str) -> None:
        data = self._buffer + chunk
        lines = data.split("\n")
        self._buffer = lines[-1]
        for line in lines[:-1]:
            self._ingest_line(line)

    def _ingest_line(self, line: str) -> None:
        entry = self._parser(line)
        if entry is None:
            return
        self._window.add(entry)
        if self._on_entry:
            self._on_entry(entry)
