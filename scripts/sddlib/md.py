from __future__ import annotations

from collections.abc import Iterator
import re

TASK_HEADING_RE = re.compile(r"^## Task (\d+):")
_OPEN_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
_CLOSE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*$")


class FenceTracker:
    """CommonMark-style fenced code blocks: 0-3 space indent, 3+ ` or ~."""

    def __init__(self) -> None:
        self._marker: str | None = None
        self._length = 0

    def consume(self, line: str) -> bool:
        """Return True if *line* is a fence marker or fence content."""
        if self._marker is not None:
            close = _CLOSE_RE.match(line)
            if (
                close is not None
                and close.group(2)[0] == self._marker
                and len(close.group(2)) >= self._length
            ):
                self._marker = None
                self._length = 0
            return True
        opened = _OPEN_RE.match(line)
        if opened is None:
            return False
        fence = opened.group(2)
        info = opened.group(3)
        if fence[0] == "`" and "`" in info:
            return False
        self._marker = fence[0]
        self._length = len(fence)
        return True


def iter_unfenced_lines(text: str) -> Iterator[str]:
    tracker = FenceTracker()
    for line in text.splitlines():
        if not tracker.consume(line):
            yield line


def task_headings(plan_text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for line in iter_unfenced_lines(plan_text):
        match = TASK_HEADING_RE.match(line)
        if match:
            found.append((int(match.group(1)), line.strip()))
    return found


def plan_task_numbers(plan_text: str) -> list[int]:
    return [n for n, _ in task_headings(plan_text)]


def extract_task_heading(plan_text: str, n: int) -> str:
    for number, heading in task_headings(plan_text):
        if number == n:
            return heading
    return ""


def extract_task(plan_text: str, n: int) -> str | None:
    tracker = FenceTracker()
    capturing = False
    chunks: list[str] = []
    for line in plan_text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        fenced = tracker.consume(stripped)
        match = None if fenced else TASK_HEADING_RE.match(stripped)
        if match:
            num = int(match.group(1))
            if capturing:
                break
            capturing = num == n
        if capturing:
            chunks.append(line)
    if not chunks:
        return None
    return "".join(chunks)
