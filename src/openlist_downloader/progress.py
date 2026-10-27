"""Lightweight, dependency-free transfer speed and progress reporting."""

import os
import time
import math


def format_size(value):
    """Return a human-readable IEC size or transfer speed component."""
    value = max(0.0, float(value))
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return "{:.1f} {}".format(value, unit)
        value /= 1024


def format_eta(seconds):
    if seconds is None:
        return "--"
    seconds = max(0, int(math.ceil(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    return "{:02d}:{:02d}".format(minutes, seconds)


class TransferProgress:
    """Emit bounded per-file progress messages; safe with concurrent callers.

    An instance belongs to exactly one transfer. The log callback is expected
    to serialize output when several downloads are running concurrently.
    """

    def __init__(self, filename, total, log, interval=2.0, clock=None):
        self.filename = os.path.basename(filename)
        self.total = total if isinstance(total, int) and total >= 0 else None
        self.log = log
        self.interval = max(0.2, float(interval))
        self.clock = clock or time.monotonic
        self.started = self.clock()
        self.last_report = self.started
        self.last_report_bytes = 0
        self.downloaded = 0

    def update(self, size):
        if size <= 0:
            return
        self.downloaded += size
        now = self.clock()
        if now - self.last_report >= self.interval:
            self._report(now, finished=False)

    def finish(self):
        self._report(self.clock(), finished=True)

    def _report(self, now, finished):
        elapsed = max(now - self.last_report, 1e-6)
        current_speed = max(0, self.downloaded - self.last_report_bytes) / elapsed
        if finished:
            duration = max(now - self.started, 1e-6)
            speed = self.downloaded / duration
        else:
            speed = current_speed

        if self.total is None:
            amount = format_size(self.downloaded)
            ratio = "大小未知"
            eta = "--"
        else:
            amount = "{} / {}".format(format_size(self.downloaded), format_size(self.total))
            ratio = "{:.1f}%".format(min(100, self.downloaded * 100 / self.total)) if self.total else "100.0%"
            remaining = max(0, self.total - self.downloaded)
            eta = format_eta(remaining / current_speed) if current_speed > 0 else "--"
        self.log("[PROGRESS] {} | {} | {} | {}/s | ETA {}{}".format(
            self.filename, ratio, amount, format_size(speed), eta,
            " | 完成" if finished else ""
        ))
        self.last_report = now
        self.last_report_bytes = self.downloaded
