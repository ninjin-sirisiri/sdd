from __future__ import annotations

from dataclasses import dataclass
import re

from sddlib.md import extract_task_heading, iter_unfenced_lines

LEDGER_RE = re.compile(
    r"^Task (\d+): complete \(commits ([0-9a-f]+)\.\.([0-9a-f]+), review clean\)\s*$"
)
GOAL_RE = re.compile(r"^\*\*Goal:\*\*\s*(.*)$")
BASELINE_RE = re.compile(r"^Branch baseline: ([0-9a-f]+)\s*$")


@dataclass(frozen=True)
class TaskComplete:
    number: int
    base: str
    head: str


def parse_ledger(text: str) -> list[TaskComplete]:
    return [
        TaskComplete(int(m.group(1)), m.group(2), m.group(3))
        for line in text.splitlines()
        if (m := LEDGER_RE.match(line))
    ]


def extract_baseline(text: str) -> str | None:
    for line in text.splitlines():
        match = BASELINE_RE.match(line)
        if match:
            return match.group(1)
    return None


def extract_goal(plan_text: str) -> str:
    for line in iter_unfenced_lines(plan_text):
        match = GOAL_RE.match(line)
        if match:
            return match.group(1).strip()
    return ""


__all__ = [
    "TaskComplete",
    "extract_baseline",
    "extract_goal",
    "extract_task_heading",
    "parse_ledger",
]
