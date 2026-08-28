from __future__ import annotations

from pathlib import Path
import re
import sys

TASK_RE = re.compile(r"^## Task (\d+):")


def extract_task(plan_text: str, n: int) -> str | None:
    in_fence = False
    capturing = False
    chunks: list[str] = []
    for line in plan_text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        if stripped.startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else TASK_RE.match(stripped)
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


def write_brief(plan_path: Path, n: int, *, cwd: Path) -> Path:
    text = extract_task(plan_path.read_text(encoding="utf-8"), n)
    if text is None:
        raise FileNotFoundError(n)
    out = cwd / ".sdd" / "briefs" / f"task-{n}-brief.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: task-brief PLAN_FILE N", file=sys.stderr)
        return 2
    plan = Path(args[0])
    if not plan.is_file():
        plan = Path.cwd() / args[0]
    if not plan.is_file():
        print(f"no such plan file: {args[0]}", file=sys.stderr)
        return 2
    try:
        n = int(args[1])
    except ValueError:
        print("usage: task-brief PLAN_FILE N", file=sys.stderr)
        return 2
    try:
        out = write_brief(plan, n, cwd=Path.cwd())
    except FileNotFoundError:
        print(f"task {n} not found in {plan}", file=sys.stderr)
        return 3
    print(out)
    return 0
