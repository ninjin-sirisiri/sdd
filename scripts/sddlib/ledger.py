from __future__ import annotations

from dataclasses import dataclass
import re

LEDGER_RE = re.compile(
    r"^Task (\d+): complete \(commits ([0-9a-f]+)\.\.([0-9a-f]+), review clean\)\s*$"
)
GOAL_RE = re.compile(r"^\*\*Goal:\*\*\s*(.*)$")
TASK_HEAD_RE = re.compile(r"^## Task (\d+):")


@dataclass(frozen=True)
class TaskComplete:
    number: int
    base: str
    head: str


def parse_ledger(text: str) -> list[TaskComplete]:
    items = [
        TaskComplete(int(m.group(1)), m.group(2), m.group(3))
        for line in text.splitlines()
        if (m := LEDGER_RE.match(line))
    ]
    return sorted(items, key=lambda t: t.number)


def extract_goal(plan_text: str) -> str:
    for line in plan_text.splitlines():
        m = GOAL_RE.match(line)
        if m:
            return m.group(1).strip()
    return ""


def extract_task_heading(plan_text: str, n: int) -> str:
    for line in plan_text.splitlines():
        m = TASK_HEAD_RE.match(line)
        if m and int(m.group(1)) == n:
            return line.strip()
    return ""
