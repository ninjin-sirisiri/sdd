# SDD Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a skill pack that runs grill-style design, spec/plan/HTML, subagent execution, and stacked PRs on Cursor and Claude Code without calling Superpowers or grill-with-docs at runtime.

**Architecture:** Deterministic Python CLIs under `scripts/` (HTML, task briefs, review packages, stacked PRs) are the testable core. English skills under `skills/` orchestrate those CLIs and encode the pipeline. A local plugin manifest points both hosts at the same `skills/` directory.

**Tech Stack:** Python 3.11+, pytest, vendored mistune 3.3.4, git, `gh` (finish PR paths only).

**Spec:** `docs/superpowers/specs/2026-08-28-sdd-framework-design.md` — read it before starting. The plan argues from that spec.

## Global Constraints

- Runtime: Python 3.11+. Node is not used.
- Codex, named custom agents, and model routing are out of scope. Do not take code from `sdd-model-routed-development` agent routing.
- Do not invoke the Superpowers plugin or grill-with-docs / grilling / domain-modeling at runtime.
- Skill and prompt files are English. Consuming-repo artifacts keep the language of their Markdown.
- Markdown is the source of truth. HTML is generated beside it. Do not make HTML canonical.
- Consuming-repo paths are fixed: `CONTEXT.md`, `CONTEXT.html`, `docs/adr/NNNN-slug.md`, `docs/sdd/specs/`, `docs/sdd/plans/`, `docs/sdd/assets/sdd.css`, `.sdd/` (gitignored scratch).
- Plan task headings in consuming repos are exactly `## Task N: <title>`.
- Install is pack-root only. Do not instruct users to copy a single `SKILL.md`.
- Markdown→HTML uses mistune vendored at `scripts/_vendor/` with no runtime network.
- Automated tests cover scripts only (`pytest`). Do not unit-test skill prose. Do not run subagents in CI.
- License: MIT for this pack. Keep Superpowers MIT text in `LICENSE-superpowers.txt`. Do not copy grill-with-docs skill files.
- Stacked PR branches are `sdd-stack/task-N`. Do not rewrite history. Do not force-push.
- `review-package` requires `-o PATH`. Never use `HEAD~1` as a task range.
- Cursor dispatches via the Task tool. Claude Code dispatches via the Agent tool. Do not pin a model name. If isolated subagents are unavailable, stop with `HOST_SUBAGENT_UNAVAILABLE` and do not implement in the controller session.
- Bounded work: finish options 1–3 only. Option 4 requires a ledger.

---

## File structure

| Path | Responsibility |
|---|---|
| `scripts/sddlib/pack.py` | `pack_root() -> Path` |
| `scripts/sddlib/render.py` | Markdown→HTML, CSS copy |
| `scripts/sddlib/brief.py` | Extract `## Task N:` sections |
| `scripts/sddlib/review.py` | Write BASE..HEAD review package |
| `scripts/sddlib/ledger.py` | Parse `.sdd/progress.md` |
| `scripts/sddlib/stack.py` | Point stack branches and create PRs |
| `scripts/render-docs` | CLI for render |
| `scripts/task-brief` | CLI for briefs |
| `scripts/review-package` | CLI for review packages |
| `scripts/stack-prs` | CLI for stacked PRs |
| `scripts/_vendor/mistune/` | Vendored mistune 3.3.4 |
| `assets/sdd.css` | Stylesheet copied into consuming repos |
| `docs/formats/context.md` | Glossary format |
| `docs/formats/adr.md` | ADR format |
| `skills/sdd/SKILL.md` | Router |
| `skills/sdd-design/SKILL.md` | Classify, grill, glossary, spec |
| `skills/sdd-plan/SKILL.md` | Spec → plan + HTML |
| `skills/sdd-execute/SKILL.md` | Subagent loop + ledger |
| `skills/sdd-execute/*-prompt.md` | Implementer / task reviewer / final reviewer |
| `skills/sdd-finish/SKILL.md` | Four-option finish including stacked PRs |
| `tests/` | pytest for scripts + fixtures |
| `.claude-plugin/plugin.json` | Claude Code local plugin |
| `.cursor-plugin/plugin.json` | Cursor plugin pointing at `./skills/` |
| `pyproject.toml` | pytest config, requires-python `>=3.11` |

Do not add a Node toolchain, a docs site generator, or a Codex agent YAML.

---

### Task 1: Render docs

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `scripts/sddlib/__init__.py`
- Create: `scripts/sddlib/pack.py`
- Create: `scripts/sddlib/render.py`
- Create: `scripts/render-docs`
- Create: `assets/sdd.css`
- Create: `scripts/_vendor/` (mistune 3.3.4 + its BSD license file)
- Create: `tests/test_render_docs.py`
- Create: `tests/fixtures/glossary/CONTEXT.md`
- Create: `tests/fixtures/adr/0001-use-postgres.md`
- Create: `tests/fixtures/spec/2026-01-01-example-design.md`
- Create: `tests/fixtures/plan/2026-01-01-example.md`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `pack_root() -> Path` — directory that contains `scripts/` and `assets/`
  - `render_paths(paths: list[Path], *, cwd: Path, pack_root: Path) -> list[Path]`
  - `render_defaults(*, cwd: Path, pack_root: Path) -> list[Path]`
  - `main(argv: list[str] | None = None) -> int`
  - CLI: `python3 scripts/render-docs [PATH ...]` (cwd = consuming repo)

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/glossary/CONTEXT.md`:

```markdown
# Ordering

Tracks customer orders.

## Terms

**Order**:
A customer's request for goods.

_Avoid_: Purchase, transaction
```

Create `tests/fixtures/adr/0001-use-postgres.md`:

```markdown
# 0001. Use Postgres for the write model

We needed a durable write model. We chose Postgres over a document store because we need transactions across order lines.
```

Create `tests/fixtures/spec/2026-01-01-example-design.md`:

```markdown
# Example design

## Goals

- Keep Markdown canonical.
```

Create `tests/fixtures/plan/2026-01-01-example.md`:

```markdown
# Example Implementation Plan

**Goal:** Build the example.

## Task 1: First thing

First body UNIQUE_TASK_ONE.

## Task 2: Second thing

Second body UNIQUE_TASK_TWO.
```

Create `tests/test_render_docs.py`:

```python
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
RENDER = SCRIPTS / "render-docs"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RENDER), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def test_render_glossary_keeps_terms_and_does_not_touch_source(tmp_path: Path) -> None:
    src = tmp_path / "CONTEXT.md"
    shutil.copy(FIXTURES / "glossary" / "CONTEXT.md", src)
    before = src.read_bytes()
    result = _run(tmp_path, ["CONTEXT.md"])
    assert result.returncode == 0, result.stderr
    html = (tmp_path / "CONTEXT.html").read_text()
    assert "Order" in html
    assert "Purchase" in html
    assert "<h1" in html
    assert src.read_bytes() == before
    css = tmp_path / "docs" / "sdd" / "assets" / "sdd.css"
    assert css.is_file()
    assert 'href="docs/sdd/assets/sdd.css"' in html


def test_render_is_idempotent(tmp_path: Path) -> None:
    shutil.copy(FIXTURES / "glossary" / "CONTEXT.md", tmp_path / "CONTEXT.md")
    assert _run(tmp_path, ["CONTEXT.md"]).returncode == 0
    first = (tmp_path / "CONTEXT.html").read_bytes()
    assert _run(tmp_path, ["CONTEXT.md"]).returncode == 0
    assert (tmp_path / "CONTEXT.html").read_bytes() == first
    assert "datetime" not in first.decode().lower()


def test_render_defaults_and_relative_css(tmp_path: Path) -> None:
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "sdd" / "plans").mkdir(parents=True)
    shutil.copy(FIXTURES / "glossary" / "CONTEXT.md", tmp_path / "CONTEXT.md")
    shutil.copy(FIXTURES / "adr" / "0001-use-postgres.md", tmp_path / "docs" / "adr" / "0001-use-postgres.md")
    shutil.copy(
        FIXTURES / "spec" / "2026-01-01-example-design.md",
        tmp_path / "docs" / "sdd" / "specs" / "2026-01-01-example-design.md",
    )
    shutil.copy(
        FIXTURES / "plan" / "2026-01-01-example.md",
        tmp_path / "docs" / "sdd" / "plans" / "2026-01-01-example.md",
    )
    result = _run(tmp_path, [])
    assert result.returncode == 0, result.stderr
    adr_html = (tmp_path / "docs" / "adr" / "0001-use-postgres.html").read_text()
    spec_html = (tmp_path / "docs" / "sdd" / "specs" / "2026-01-01-example-design.html").read_text()
    plan_html = (tmp_path / "docs" / "sdd" / "plans" / "2026-01-01-example.html").read_text()
    assert "Postgres" in adr_html
    assert 'href="../sdd/assets/sdd.css"' in adr_html
    assert "Keep Markdown canonical" in spec_html
    assert 'href="../assets/sdd.css"' in spec_html
    assert "UNIQUE_TASK_ONE" in plan_html
    assert 'href="../assets/sdd.css"' in plan_html


def test_missing_explicit_path_is_nonzero(tmp_path: Path) -> None:
    result = _run(tmp_path, ["nope.md"])
    assert result.returncode != 0
    assert "nope.md" in result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_render_docs.py -v`

Expected: FAIL (file `scripts/render-docs` missing or import error)

- [ ] **Step 3: Vendor mistune 3.3.4 and write the implementation**

`pyproject.toml`:

```toml
[project]
name = "sdd"
version = "0.1.0"
description = "Spec-driven development skill pack"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["scripts", "tests"]
```

`.gitignore`:

```
__pycache__/
.pytest_cache/
.venv/
.sdd/
*.egg-info/
```

Vendor (no runtime network after this step):

```bash
python3 -m pip download mistune==3.3.4 --no-deps -d /tmp/sdd-mistune
# unpack the wheel; copy the mistune package directory to scripts/_vendor/mistune
# copy the wheel's LICENSE to scripts/_vendor/mistune-LICENSE
```

If 3.3.4 is unavailable, stop with BLOCKED naming the pip error. Do not pick another major.

`assets/sdd.css`:

```css
:root { color-scheme: light dark; }
body {
  font-family: ui-sans-serif, system-ui, sans-serif;
  line-height: 1.55;
  max-width: 48rem;
  margin: 2rem auto;
  padding: 0 1rem;
}
pre, code { font-family: ui-monospace, Menlo, monospace; }
pre { overflow: auto; padding: 1rem; background: #f6f8fa; }
@media (prefers-color-scheme: dark) {
  pre { background: #1f2328; }
}
a { color: inherit; }
```

`scripts/sddlib/__init__.py` empty.

`scripts/sddlib/pack.py`:

```python
from pathlib import Path


def pack_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent
```

`scripts/sddlib/render.py`:

```python
from __future__ import annotations

from pathlib import Path
import sys
import argparse

_VENDOR = Path(__file__).resolve().parent.parent / "_vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))
import mistune  # noqa: E402

from sddlib.pack import pack_root

DEFAULT_GLOBS = (
    "CONTEXT.md",
    "docs/adr/*.md",
    "docs/sdd/specs/*.md",
    "docs/sdd/plans/*.md",
)


def html_path_for(md_path: Path) -> Path:
    return md_path.with_suffix(".html")


def _css_href(html_path: Path, css_path: Path) -> str:
    return Path(os_relpath(css_path, html_path.parent)).as_posix()


def os_relpath(target: Path, start: Path) -> str:
    import os

    return os.path.relpath(target, start=start)


def _ensure_css(cwd: Path, root: Path) -> Path:
    dest = cwd / "docs" / "sdd" / "assets" / "sdd.css"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_bytes((root / "assets" / "sdd.css").read_bytes())
    return dest


def _title(md_text: str, stem: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return stem


def _document(body: str, title: str, css_href: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="und">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f'<link rel="stylesheet" href="{css_href}">\n'
        "</head>\n"
        "<body>\n<main>\n"
        f"{body}\n"
        "</main>\n</body>\n</html>\n"
    )


def render_paths(paths: list[Path], *, cwd: Path, pack_root: Path) -> list[Path]:
    css = _ensure_css(cwd, pack_root)
    written: list[Path] = []
    for md in paths:
        text = md.read_text(encoding="utf-8")
        html = html_path_for(md)
        href = _css_href(html, css)
        html.write_text(
            _document(mistune.html(text), _title(text, md.stem), href),
            encoding="utf-8",
        )
        written.append(html)
    return written


def render_defaults(*, cwd: Path, pack_root: Path) -> list[Path]:
    found: list[Path] = []
    ctx = cwd / "CONTEXT.md"
    if ctx.is_file():
        found.append(ctx)
    for pattern in DEFAULT_GLOBS[1:]:
        found.extend(sorted(cwd.glob(pattern)))
    return render_paths(found, cwd=cwd, pack_root=pack_root) if found else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="render-docs")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)
    cwd = Path.cwd()
    root = pack_root()
    try:
        if args.paths:
            resolved = []
            for p in args.paths:
                candidate = p if p.is_file() else cwd / p
                if not candidate.is_file():
                    print(f"missing file: {p}", file=sys.stderr)
                    return 1
                resolved.append(candidate)
            render_paths(resolved, cwd=cwd, pack_root=root)
        else:
            render_defaults(cwd=cwd, pack_root=root)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"render-docs failed: {exc}", file=sys.stderr)
        return 1
    return 0
```

`scripts/render-docs`:

```python
#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sddlib.render import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m pytest tests/test_render_docs.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore assets/sdd.css scripts tests/test_render_docs.py tests/fixtures
git commit -m "Add Markdown-to-HTML rendering with vendored mistune."
```

---

### Task 2: Task brief

**Files:**
- Create: `scripts/sddlib/brief.py`
- Create: `scripts/task-brief`
- Create: `tests/test_task_brief.py`

**Interfaces:**
- Consumes: consuming-repo cwd; plan file path
- Produces:
  - `extract_task(plan_text: str, n: int) -> str | None`
  - `write_brief(plan_path: Path, n: int, *, cwd: Path) -> Path`
  - CLI: `python3 scripts/task-brief PLAN_FILE N` — writes `cwd/.sdd/briefs/task-N-brief.md`, prints that path on stdout. Exit 2 on usage error. Exit 3 if Task N is missing.

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import subprocess
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BRIEF = SCRIPTS / "task-brief"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _run(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BRIEF), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )


def test_extracts_only_task_two(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text((FIXTURES / "plan" / "2026-01-01-example.md").read_text())
    result = _run(tmp_path, [str(plan), "2"])
    assert result.returncode == 0, result.stderr
    out = Path(result.stdout.strip())
    assert out == tmp_path / ".sdd" / "briefs" / "task-2-brief.md"
    text = out.read_text()
    assert text.startswith("## Task 2: Second thing")
    assert "UNIQUE_TASK_TWO" in text
    assert "UNIQUE_TASK_ONE" not in text
    assert "**Goal:**" not in text


def test_skips_headings_inside_fences(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Plan\n\n"
        "## Task 1: Real one\n\n"
        "alpha\n\n"
        "```markdown\n"
        "## Task 2: Fake inside fence\n"
        "```\n\n"
        "still task one\n\n"
        "## Task 2: Real two\n\n"
        "beta\n"
    )
    result = _run(tmp_path, [str(plan), "1"])
    assert result.returncode == 0, result.stderr
    text = Path(result.stdout.strip()).read_text()
    assert "still task one" in text
    assert "Fake inside fence" in text  # fenced content is still inside Task 1
    assert "## Task 2: Real two" not in text
    result2 = _run(tmp_path, [str(plan), "2"])
    assert result2.returncode == 0
    text2 = Path(result2.stdout.strip()).read_text()
    assert text2.startswith("## Task 2: Real two")
    assert "beta" in text2
    assert "still task one" not in text2


def test_missing_task_is_exit_3(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text((FIXTURES / "plan" / "2026-01-01-example.md").read_text())
    result = _run(tmp_path, [str(plan), "9"])
    assert result.returncode == 3
    assert not (tmp_path / ".sdd" / "briefs" / "task-9-brief.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_task_brief.py -v`

Expected: FAIL (`scripts/task-brief` missing)

- [ ] **Step 3: Write minimal implementation**

`scripts/sddlib/brief.py`:

```python
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
```

`scripts/task-brief` same shebang pattern as `scripts/render-docs`, calling `sddlib.brief.main`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m pytest tests/test_task_brief.py tests/test_render_docs.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/sddlib/brief.py scripts/task-brief tests/test_task_brief.py
git commit -m "Extract one plan task into a brief file."
```

---

### Task 3: Review package

**Files:**
- Create: `scripts/sddlib/review.py`
- Create: `scripts/review-package`
- Create: `tests/test_review_package.py`
- Create: `tests/gitutil.py`

**Interfaces:**
- Consumes: git repo at cwd
- Produces:
  - `write_review_package(base: str, head: str, out: Path, *, cwd: Path) -> Path`
  - CLI: `python3 scripts/review-package BASE HEAD -o PATH` — `-o` required. Prints `PATH` on stdout. Exit 2 on usage or bad revision.

- [ ] **Step 1: Write the failing test**

`tests/gitutil.py`:

```python
from pathlib import Path
import subprocess


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def init_repo(cwd: Path) -> None:
    git(cwd, "init")
    git(cwd, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "--allow-empty", "-m", "base")
```

Do not run `git config` (no `git config user.*`). Pass `-c` on each commit command.

`tests/test_review_package.py`:

```python
from pathlib import Path
import subprocess
import sys

from gitutil import git, init_repo

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
REVIEW = SCRIPTS / "review-package"


def _commit(cwd: Path, name: str, content: str, message: str) -> str:
    path = cwd / name
    path.write_text(content)
    git(cwd, "add", name)
    git(cwd, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", message)
    return git(cwd, "rev-parse", "HEAD").strip()


def test_package_includes_all_commits_not_only_last(tmp_path: Path) -> None:
    init_repo(tmp_path)
    base = git(tmp_path, "rev-parse", "HEAD").strip()
    _commit(tmp_path, "a.txt", "one\n", "task commit 1")
    head = _commit(tmp_path, "b.txt", "two\n", "task commit 2")
    out = tmp_path / "pkg.diff.md"
    result = subprocess.run(
        [sys.executable, str(REVIEW), base, head, "-o", str(out)],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(out)
    text = out.read_text()
    assert "task commit 1" in text
    assert "task commit 2" in text
    assert "a.txt" in text
    assert "b.txt" in text
    one_parent = git(tmp_path, "rev-parse", "HEAD~1").strip()
    # The package must not be equivalent to HEAD~1..HEAD (which would drop commit 1).
    only_last = subprocess.check_output(
        ["git", "log", "--oneline", f"{one_parent}..{head}"],
        cwd=tmp_path,
        text=True,
    )
    assert "task commit 1" not in only_last
    assert "task commit 1" in text


def test_requires_dash_o(tmp_path: Path) -> None:
    init_repo(tmp_path)
    sha = git(tmp_path, "rev-parse", "HEAD").strip()
    result = subprocess.run(
        [sys.executable, str(REVIEW), sha, sha],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_review_package.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`scripts/sddlib/review.py`:

```python
from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys


def write_review_package(base: str, head: str, out: Path, *, cwd: Path) -> Path:
    subprocess.check_output(["git", "rev-parse", "--verify", base], cwd=cwd)
    subprocess.check_output(["git", "rev-parse", "--verify", head], cwd=cwd)
    log = subprocess.check_output(["git", "log", "--oneline", f"{base}..{head}"], cwd=cwd, text=True)
    stat = subprocess.check_output(["git", "diff", "--stat", f"{base}..{head}"], cwd=cwd, text=True)
    diff = subprocess.check_output(["git", "diff", "-U10", f"{base}..{head}"], cwd=cwd, text=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# Review package: {base}..{head}\n\n"
        f"## Commits\n{log}\n"
        f"## Files changed\n{stat}\n"
        f"## Diff\n{diff}",
        encoding="utf-8",
    )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="review-package")
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("-o", "--output", required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 2)
    try:
        path = write_review_package(args.base, args.head, Path(args.output), cwd=Path.cwd())
    except subprocess.CalledProcessError:
        print("bad BASE or HEAD", file=sys.stderr)
        return 2
    print(path)
    return 0
```

`scripts/review-package` shebang wrapper calling `sddlib.review.main`. Do not default `-o`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m pytest tests/test_review_package.py tests/test_task_brief.py tests/test_render_docs.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/sddlib/review.py scripts/review-package tests/test_review_package.py tests/gitutil.py
git commit -m "Write a BASE..HEAD review package without using HEAD~1."
```

---

### Task 4: Stacked PRs

**Files:**
- Create: `scripts/sddlib/ledger.py`
- Create: `scripts/sddlib/stack.py`
- Create: `scripts/stack-prs`
- Create: `tests/test_stack_prs.py`

**Interfaces:**
- Consumes: `parse_ledger` lines exactly `Task N: complete (commits <base7>..<head7>, review clean)`; ignore other lines (including `Ruling:`)
- Produces:
  - `@dataclass(frozen=True) class TaskComplete: number: int; base: str; head: str`
  - `parse_ledger(text: str) -> list[TaskComplete]` sorted by `number`
  - `extract_goal(plan_text: str) -> str` — text after `**Goal:**` on that line, else `""`
  - `extract_task_heading(plan_text: str, n: int) -> str` — the `## Task N:` line stripped, else `""`
  - CLI: `python3 scripts/stack-prs --base BRANCH --ledger PATH --plan PATH [--dry-run]`
  - Dry-run: no `git branch` / `git push` / `gh`. Print planned `sdd-stack/task-N` and PR bases to stdout. Exit 0 if ledger is valid.
  - Real mode: `git update-ref refs/heads/sdd-stack/task-N <resolved head>` then `git push origin sdd-stack/task-N` (no `--force`) then `gh pr create --base <pr-base> --head sdd-stack/task-N --title <heading> --body <goal + heading>`.
  - PR base for task 1 = `--base`. For task N = `sdd-stack/task-(N-1)`.
  - Missing ledger, no complete lines, or unparsable ranges: exit 1, create no PRs.
  - Mid-loop failure: print created PR URLs and remaining task numbers; exit 1; do not rewrite history.
  - `run_stack(*, cwd, base_branch, ledger_path, plan_path, dry_run, update_ref=None, push=None, gh=None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_stack_prs.py`:

```python
from pathlib import Path
import subprocess
import sys

from gitutil import git, init_repo
from sddlib.ledger import parse_ledger
from sddlib.stack import run_stack

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
STACK = SCRIPTS / "stack-prs"

PLAN = """# Example Implementation Plan

**Goal:** Build the example.

## Task 1: First thing

First body UNIQUE_TASK_ONE.

## Task 2: Second thing

Second body UNIQUE_TASK_TWO.
"""


def _two_task_repo(tmp_path: Path) -> tuple[Path, Path]:
    init_repo(tmp_path)
    git(tmp_path, "checkout", "-b", "main")
    c0 = git(tmp_path, "rev-parse", "--short", "HEAD").strip()
    (tmp_path / "t1.txt").write_text("1")
    git(tmp_path, "add", "t1.txt")
    git(tmp_path, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", "t1")
    c1 = git(tmp_path, "rev-parse", "--short", "HEAD").strip()
    (tmp_path / "t2.txt").write_text("2")
    git(tmp_path, "add", "t2.txt")
    git(tmp_path, "-c", "user.email=sdd@test", "-c", "user.name=sdd", "commit", "-m", "t2")
    c2 = git(tmp_path, "rev-parse", "--short", "HEAD").strip()
    ledger = tmp_path / "progress.md"
    ledger.write_text(
        f"Task 1: complete (commits {c0}..{c1}, review clean)\n"
        f"Task 2: complete (commits {c1}..{c2}, review clean)\n"
    )
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN)
    return ledger, plan


def test_parse_ledger_ignores_rulings() -> None:
    text = (
        "Ruling: picked names — clarity — low\n"
        "Task 1: complete (commits abc1234..def5678, review clean)\n"
        "Task 2: complete (commits def5678..ghi9012, review clean)\n"
    )
    items = parse_ledger(text)
    assert [i.number for i in items] == [1, 2]
    assert items[0].base == "abc1234"
    assert items[1].head == "ghi9012"


def test_dry_run_does_not_create_branches_or_call_hooks(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    before_refs = git(tmp_path, "show-ref")
    called: list[str] = []

    def boom(name: str):
        def _inner(*args, **kwargs):
            called.append(name)
            raise AssertionError(f"{name} called")

        return _inner

    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=True,
        update_ref=boom("update_ref"),
        push=boom("push"),
        gh=boom("gh"),
    )
    assert code == 0
    assert called == []
    assert git(tmp_path, "show-ref") == before_refs
    result = subprocess.run(
        [
            sys.executable,
            str(STACK),
            "--base",
            "main",
            "--ledger",
            str(ledger),
            "--plan",
            str(plan),
            "--dry-run",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert "sdd-stack/task-1" in result.stdout
    assert "sdd-stack/task-2" in result.stdout


def test_missing_ledger_nonzero(tmp_path: Path) -> None:
    empty = tmp_path / "progress.md"
    empty.write_text("")
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN)
    result = subprocess.run(
        [
            sys.executable,
            str(STACK),
            "--base",
            "main",
            "--ledger",
            str(empty),
            "--plan",
            str(plan),
            "--dry-run",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1


def test_real_mode_points_branches(tmp_path: Path) -> None:
    ledger, plan = _two_task_repo(tmp_path)
    refs: list[tuple[str, str]] = []
    pushes: list[str] = []
    gh_calls: list[list[str]] = []

    def update_ref(branch: str, sha: str) -> None:
        refs.append((branch, sha))

    def push(branch: str) -> None:
        pushes.append(branch)

    def gh(args: list[str]) -> str:
        gh_calls.append(args)
        return "https://example.test/pr/" + str(len(gh_calls))

    code = run_stack(
        cwd=tmp_path,
        base_branch="main",
        ledger_path=ledger,
        plan_path=plan,
        dry_run=False,
        update_ref=update_ref,
        push=push,
        gh=gh,
    )
    assert code == 0
    assert [b for b, _ in refs] == ["sdd-stack/task-1", "sdd-stack/task-2"]
    assert pushes == ["sdd-stack/task-1", "sdd-stack/task-2"]
    bases = []
    titles = []
    bodies = []
    for args in gh_calls:
        bases.append(args[args.index("--base") + 1])
        titles.append(args[args.index("--title") + 1])
        bodies.append(args[args.index("--body") + 1])
    assert bases == ["main", "sdd-stack/task-1"]
    assert "First thing" in titles[0]
    assert "Second thing" in titles[1]
    assert "Build the example" in bodies[0]
    assert "Build the example" in bodies[1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_stack_prs.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`scripts/sddlib/ledger.py`:

```python
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
```

`scripts/sddlib/stack.py`:

```python
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from sddlib.ledger import extract_goal, extract_task_heading, parse_ledger


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


def run_stack(
    *,
    cwd: Path,
    base_branch: str,
    ledger_path: Path,
    plan_path: Path,
    dry_run: bool,
    update_ref=None,
    push=None,
    gh=None,
) -> int:
    if not ledger_path.is_file():
        print("missing ledger", file=sys.stderr)
        return 1
    items = parse_ledger(ledger_path.read_text(encoding="utf-8"))
    if not items:
        print("no complete tasks in ledger", file=sys.stderr)
        return 1
    plan_text = plan_path.read_text(encoding="utf-8")
    goal = extract_goal(plan_text)
    created: list[str] = []
    for index, item in enumerate(items):
        branch = f"sdd-stack/task-{item.number}"
        pr_base = base_branch if index == 0 else f"sdd-stack/task-{items[index - 1].number}"
        heading = extract_task_heading(plan_text, item.number) or branch
        if dry_run:
            print(f"{branch} base={pr_base}")
            continue
        try:
            sha = _git(cwd, "rev-parse", "--verify", item.head).strip()
            (update_ref or (_default_update_ref(cwd)))(branch, sha)
            (push or (_default_push(cwd)))(branch)
            url = (gh or (_default_gh(cwd)))(
                [
                    "pr",
                    "create",
                    "--base",
                    pr_base,
                    "--head",
                    branch,
                    "--title",
                    heading,
                    "--body",
                    f"{goal}\n\n{heading}",
                ]
            )
            created.append(url.strip())
            print(url.strip())
        except Exception as exc:  # noqa: BLE001
            remaining = [t.number for t in items[index:]]
            print(f"failed at task {item.number}: {exc}", file=sys.stderr)
            print("created: " + ", ".join(created), file=sys.stderr)
            print("remaining: " + ", ".join(str(n) for n in remaining), file=sys.stderr)
            return 1
    return 0


def _default_update_ref(cwd: Path):
    def _run(branch: str, sha: str) -> None:
        _git(cwd, "update-ref", f"refs/heads/{branch}", sha)

    return _run


def _default_push(cwd: Path):
    def _run(branch: str) -> None:
        subprocess.check_call(["git", "push", "origin", branch], cwd=cwd)

    return _run


def _default_gh(cwd: Path):
    def _run(args: list[str]) -> str:
        return subprocess.check_output(["gh", *args], cwd=cwd, text=True)

    return _run
```

`scripts/stack-prs` argparse (`--base`, `--ledger`, `--plan`, `--dry-run`) calls `run_stack`. Never pass `--force`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `python3 -m pytest tests/ -v`

Expected: PASS (full script suite)

- [ ] **Step 5: Commit**

```bash
git add scripts/sddlib/ledger.py scripts/sddlib/stack.py scripts/stack-prs tests/test_stack_prs.py
git commit -m "Stack task branches from the progress ledger."
```

---

### Task 5: Design skill and formats

**Files:**
- Create: `docs/formats/context.md`
- Create: `docs/formats/adr.md`
- Create: `skills/sdd-design/SKILL.md`

**Interfaces:**
- Consumes: `scripts/render-docs` CLI from Task 1
- Produces: English `sdd-design` skill; format docs identical to the spec examples

This task is prose. Verification is `grep`, not pytest.

- [ ] **Step 1: Write format files**

`docs/formats/context.md`:

````markdown
# CONTEXT.md format

CONTEXT.md is a glossary and nothing else. No implementation details, specs, or scratch notes.

Template:

    # {Context Name}

    {One or two sentences: what this context is}

    ## Terms

    **{Term}**:
    {What it IS, one or two sentences}

    _Avoid_: {rejected synonyms}

Rules:
- Project-specific terms only. General programming concepts do not belong.
- One canonical term per concept. Put rivals under `_Avoid_`.
- Create the file lazily when the first term is resolved.
- In v1 write only a root CONTEXT.md. If CONTEXT-MAP.md exists, ask which single CONTEXT.md to use. Do not route terms automatically.
````

`docs/formats/adr.md`:

```markdown
# ADR format

Write an ADR only when all three are true:

1. Hard to reverse
2. Surprising without context
3. The result of a real trade-off

Path: `docs/adr/NNNN-slug.md` where NNNN is max existing + 1, or 0001.

Body: one to three sentences covering situation, choice, and reason. Nothing else.
```

- [ ] **Step 2: Write `skills/sdd-design/SKILL.md`** with exactly this content:

````markdown
---
name: sdd-design
description: Classify a change, interview until shared understanding, write CONTEXT.md/ADRs inline, then a Markdown spec plus HTML. Use before implementation when the work is new or the words are unsettled.
---

# SDD Design

Do not invoke Superpowers, grill-with-docs, grilling, or domain-modeling. This skill contains those rules.

Announce: "I'm using sdd-design."

## Classify first

Say spike / bounded / architectural out loud. When unsure, take the heavier path. If hidden complexity appears, upgrade and say so. Never downgrade.

## Explore

Read CONTEXT.md (or ask which file if CONTEXT-MAP.md exists), docs/adr/, README, and enough code that the codebase can answer questions instead of the human.

## Interview

- One question per message. Prefer multiple choice. Always give a recommended answer.
- Do not ask what CONTEXT.md, ADRs, README, or the codebase already answer.
- If the human's word conflicts with CONTEXT.md, resolve the collision before any other question.
- Walk dependencies in order.

## CONTEXT.md

When a term resolves, write it immediately using docs/formats/context.md. Then run:

```text
python3 <pack-root>/scripts/render-docs CONTEXT.md
```

If render-docs exits non-zero, warn and continue. Never put implementation detail in CONTEXT.md.

## ADRs

Offer an ADR only when all three gates in docs/formats/adr.md hold. After the human agrees, write `docs/adr/NNNN-slug.md` and render that file. If a gate is missing, put the decision in the spec instead (architectural) or keep it in the short chat design (bounded).

## Endings

**Spike:** Two or three sentences for the probe, get a nod, investigate cheaply, report a recommendation. Label leftover code throwaway. No spec or plan. Glossary/ADR writes still apply if they qualify.

**Bounded:** Short design in chat. Stop until an explicit yes. Then TDD in this session. No spec file, no plan file.

**Architectural:** Propose 2–3 approaches, recommended first. Present the design in sections; wait for approval after each. Then write `docs/sdd/specs/YYYY-MM-DD-<topic>-design.md` and render it. Self-review: no placeholders, no contradictions, one interpretation per requirement, scope that fits one plan. Commit the spec plus this session's CONTEXT.md / ADR / HTML changes. Ask the human to review the spec file. Further spec edits are new commits (do not amend). After they approve, use sdd-plan. Do not use writing-plans.

Spec must record: classification, chosen approach, architecture, components, data flow, error handling, testing, goals/non-goals, consuming paths, and any numeric defaults, negative requirements, or ordering guarantees that did not earn an ADR. Do not end the session with those only in chat.

## Pack root

Resolve `<pack-root>` as the directory that contains `scripts/` and `skills/`. Do not copy this SKILL.md alone into another repo.
````

- [ ] **Step 3: Verify with grep**

Run:

```bash
grep -q "Do not invoke Superpowers" skills/sdd-design/SKILL.md
grep -q "one question per message" skills/sdd-design/SKILL.md
grep -q "render-docs" skills/sdd-design/SKILL.md
grep -q "sdd-plan" skills/sdd-design/SKILL.md
grep -q "CONTEXT-MAP.md" skills/sdd-design/SKILL.md
grep -q "docs/adr/NNNN-slug.md" docs/formats/adr.md
```

Expected: all succeed (exit 0)

- [ ] **Step 4: Commit**

```bash
git add docs/formats/context.md docs/formats/adr.md skills/sdd-design/SKILL.md
git commit -m "Add the design skill with glossary and ADR formats."
```

---

### Task 6: Plan skill

**Files:**
- Create: `skills/sdd-plan/SKILL.md`

**Interfaces:**
- Consumes: architectural spec path; `scripts/render-docs`
- Produces: consuming `docs/sdd/plans/YYYY-MM-DD-<feature>.md` with headers and `## Task N:` headings

- [ ] **Step 1: Write `skills/sdd-plan/SKILL.md`**

````markdown
---
name: sdd-plan
description: Turn an approved architectural spec into a task plan with Markdown and HTML. Use after sdd-design when a spec file exists.
---

# SDD Plan

Announce: "I'm using sdd-plan."

Do not invoke Superpowers writing-plans. Input is the spec path. Do not start from a chat-only bounded design.

## Header (required, in this order)

```markdown
# [Feature] Implementation Plan

**Goal:** [one sentence]

**Architecture:** [two or three sentences]

**Tech Stack:** [key tools]

**Spec:** [path to the spec]

## Global Constraints

[Copy exact values and wording from the spec, one line each]
```

Then file structure, then tasks.

## Tasks

Each task is the smallest unit with its own test cycle and review gate. Fold scaffolding into the task that needs it. Heading format is exactly:

```markdown
## Task N: <title>
```

Example: `## Task 1: Render docs script`

Steps inside a task are not PR units. Task N is the stacked-PR boundary.

Assume the implementer is skilled but does not know this repo. No TBD, no "similar to Task N", no steps without the actual commands or file contents.

## HTML and commit

After writing the plan, run:

```text
python3 <pack-root>/scripts/render-docs docs/sdd/plans/<file>.md
```

If HTML fails, warn and continue. Commit the plan Markdown and its HTML. Then tell the human to run sdd-execute.
````

- [ ] **Step 2: Verify with grep**

```bash
grep -q '## Task N:' skills/sdd-plan/SKILL.md
grep -q 'Global Constraints' skills/sdd-plan/SKILL.md
grep -q 'render-docs' skills/sdd-plan/SKILL.md
grep -q 'sdd-execute' skills/sdd-plan/SKILL.md
```

- [ ] **Step 3: Commit**

```bash
git add skills/sdd-plan/SKILL.md
git commit -m "Add the plan skill with fixed Task heading syntax."
```

---

### Task 7: Execute skill and prompts

**Files:**
- Create: `skills/sdd-execute/SKILL.md`
- Create: `skills/sdd-execute/implementer-prompt.md`
- Create: `skills/sdd-execute/task-reviewer-prompt.md`
- Create: `skills/sdd-execute/final-reviewer-prompt.md`

**Interfaces:**
- Consumes: Task 2 CLI `task-brief PLAN N`; Task 3 CLI `review-package BASE HEAD -o PATH`; plan Global Constraints
- Produces: `.sdd/progress.md` lines `Task N: complete (commits <base7>..<head7>, review clean)`

- [ ] **Step 1: Write `skills/sdd-execute/implementer-prompt.md`**

````markdown
# Implementer Subagent Prompt Template

Use this template when dispatching an implementer subagent.

```
Dispatch a fresh isolated subagent (Cursor Task tool, or Claude Code Agent tool).

Subagent task:
  description: "Implement Task [N]: [TASK_NAME]"
  prompt: |
    You are implementing Task [N]: [TASK_NAME]

    ## Task Description

    Read your task brief first: [BRIEF_FILE]
    It contains the full task text from the plan.

    ## Context

    [CONTEXT]

    ## Before You Begin

    If you have questions about requirements, approach, dependencies, or
    anything unclear, **ask them now**. Do not start work while guessing.

    ## Your Job

    Once you're clear:
    1. Follow TDD: write a failing test, run it and confirm it fails for the
       expected reason, write the minimal code, run the test and confirm it
       passes. Repeat per step in the brief.
    2. Run the focused test while iterating; run the full suite once before
       commit.
    3. Commit.
    4. Self-review (below).
    5. Write the full report to [REPORT_FILE].

    Work from: [WORKDIR]

    If something unexpected appears, ask. Do not invent requirements.

    ## Code Organization

    Follow the file structure in the brief. One responsibility per file.
    If a file grows past the brief's intent, stop and report DONE_WITH_CONCERNS.
    Do not split files the brief did not ask for.

    ## When You're in Over Your Head

    STOP and report BLOCKED or NEEDS_CONTEXT when the task needs an
    architectural choice the brief does not make, you cannot find the code
    you need, or you are unsure the approach is correct.

    ## Before Reporting Back: Self-Review

    Completeness, quality, YAGNI, and tests that verify behavior (not mocks).
    Fix issues before reporting.

    ## After Review Findings

    If you fix reviewer findings, re-run the tests that cover the amended
    code and append command + output to [REPORT_FILE].

    ## Report Format

    Write the full report to [REPORT_FILE]:
    - What you implemented (or attempted, if blocked)
    - What you tested and results
    - **TDD Evidence**:
      - RED: command, failing output, why that failure was expected
      - GREEN: command and passing output
    - Files changed
    - Self-review findings
    - Concerns

    Then report back with ONLY (under 15 lines):
    - **Status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
    - Commits created (short SHA + subject)
    - One-line test summary
    - Concerns, if any
    - The report file path

    If BLOCKED or NEEDS_CONTEXT, put the specifics in the final message.
    Use DONE_WITH_CONCERNS if you finished but doubt correctness or scope.
```
````

- [ ] **Step 2: Write `skills/sdd-execute/task-reviewer-prompt.md`**

````markdown
# Task Reviewer Prompt Template

Use this template when dispatching a task reviewer. One reviewer, two verdicts:
spec compliance and code quality.

```
Dispatch a fresh isolated subagent (Cursor Task tool, or Claude Code Agent tool).

Subagent task:
  description: "Review Task [N] (spec + quality)"
  prompt: |
    You are reviewing one task: first whether it matches its requirements,
    then whether it is well-built. This is a task-scoped gate, not a merge
    review.

    ## What Was Requested

    Read the task brief: [BRIEF_FILE]

    Global constraints that bind this task:
    [GLOBAL_CONSTRAINTS]

    ## What the Implementer Claims

    Read the implementer's report: [REPORT_FILE]

    ## Diff Under Review

    **Base:** [BASE_SHA]
    **Head:** [HEAD_SHA]
    **Diff file:** [DIFF_FILE]

    Read the diff file once. Do not re-run git. Do not crawl the broader
    codebase unless you can name a concrete risk, and then one focused check
    per risk. Read-only: do not mutate the worktree.

    ## Do Not Trust the Report

    Treat the report as claims. Judge the code. A rationale does not
    downgrade severity.

    ## Tests

    The implementer already ran tests and reported TDD evidence. Do not
    re-run the suite to confirm. Run a test only when the code raises a
    specific doubt no existing run answers — focused, never package-wide.

    ## Part 1: Spec Compliance

    Missing / Extra / Misunderstood. If a requirement cannot be verified
    from this diff, report ⚠️ and what the controller should check.

    ## Part 2: Code Quality

    Separation of concerns, error handling, DRY without premature
    abstraction, tests that verify behavior, file responsibilities.

    Cite file:line for every finding. Final message begins with the spec
    verdict. No preamble.

    ## Calibration

    Important means this task cannot be trusted until fixed: incorrect
    behavior, missed requirement, or merge-blocking maintainability
    (verbatim logic duplication, swallowed errors, tests that assert
    nothing). Broader coverage is Minor.
    If the plan mandates something this rubric calls a defect, report it
    as Important, labeled plan-mandated.

    ## Output Format

    ### Spec Compliance

    - ✅ Spec compliant | ❌ Issues found: [with file:line]
    - ⚠️ Cannot verify from diff: [and what to check]

    ### Strengths
    [specific]

    ### Issues

    #### Critical (Must Fix)
    #### Important (Should Fix)
    #### Minor (Nice to Have)

    ### Assessment

    **Task quality:** [Approved | Needs fixes]

    **Reasoning:** [1-2 sentences]
```
````

- [ ] **Step 3: Write `skills/sdd-execute/final-reviewer-prompt.md`**

````markdown
# Final Reviewer Prompt Template

Use after every task has passed its per-task gate.

```
Dispatch a fresh isolated subagent (Cursor Task tool, or Claude Code Agent tool).

Subagent task:
  description: "Review the complete branch"
  prompt: |
    You are reviewing the whole branch against the plan.

    ## Plan

    [PLAN_PATH]

    ## Review Package

    Read [DIFF_FILE] (MERGE_BASE..HEAD). Do not re-derive the diff.
    Read-only.

    ## Deferred Minors

    [MINOR_LEDGER]

    Triage which Minor items must be fixed before merge.

    ## What to Check

    Plan alignment, code quality, architecture, testing, production
    readiness. Categorize Critical / Important / Minor. Cite file:line.

    ## Output Format

    ### Strengths
    ### Issues
    #### Critical (Must Fix)
    #### Important (Should Fix)
    #### Minor (Nice to Have)
    ### Assessment
    **Ready to merge?** [Yes | No | With fixes]
    **Reasoning:** [1-2 sentences]
```
````

- [ ] **Step 4: Write `skills/sdd-execute/SKILL.md`**

````markdown
---
name: sdd-execute
description: Execute an SDD plan with one isolated implementer per task, a spec+quality review, and a progress ledger. Use when a plan file exists and the user wants it implemented.
---

# SDD Execute

Announce: "I'm using sdd-execute."

Do not invoke Superpowers subagent-driven-development. Do not pin a model name.

## Preconditions

- Require a plan file path. If missing, stop.
- If `.gitignore` has no `.sdd/` line, append it and commit only `.gitignore`.
- If the worktree is still dirty after that commit, stop and ask the human to commit or stash.
- Scan the plan once for contradictions or Global Constraints conflicts. Ask them in one batch. If none, say nothing.

## Host

- Cursor: Task tool, fresh subagent, no inherited chat.
- Claude Code: Agent tool, fresh subagent, no inherited chat.
- If the host cannot isolate a subagent, stop with `HOST_SUBAGENT_UNAVAILABLE`. Do not implement in this controller session.

## Loop

Serial tasks only. Never dispatch two implementers at once.

For each Task N not already `complete` in `.sdd/progress.md`:

1. Record current HEAD as BASE (full SHA).
2. `python3 <pack-root>/scripts/task-brief PLAN_FILE N`
3. Dispatch implementer using implementer-prompt.md. Fill `[BRIEF_FILE]`, `[REPORT_FILE]` (`.sdd/reports/task-N-report.md`), `[N]`, `[TASK_NAME]`, `[WORKDIR]`, `[CONTEXT]` (where this task fits + interfaces from earlier tasks + your resolution of brief ambiguity). Do not paste the plan. Do not paste diffs.
4. If the implementer asks questions, answer and resume the same contract.
5. `DONE_WITH_CONCERNS` about correctness or scope: resolve before review. Observations: ledger them and review.
6. `DONE` or observational concerns: `python3 <pack-root>/scripts/review-package BASE HEAD -o .sdd/reviews/task-N.diff.md` (overwrite on re-review).
7. Dispatch task-reviewer-prompt.md with brief, report, diff path, and Global Constraints copied verbatim from the plan.
8. Critical/Important: dispatch a fix implementer (same prompt contract, covering tests named), then re-review with the same reviewer template.
9. A finding that contradicts plan text: do not fix; show the human the finding and the plan sentence once.
10. On spec ✅ and quality Approved, append to `.sdd/progress.md`:
    `Task N: complete (commits <base7>..<head7>, review clean)`
    head7 is HEAD after fixes. base7 is the BASE you recorded.

## Controller stops

Only for destructive ops, security, side effects outside this worktree (push, merge, publish), or a plan so broken the next step is a guess. Otherwise decide from the spec, write `Ruling: <decision> — <why> — <cost if wrong>` to the ledger, and continue.

After compaction, trust the ledger and `git log`. Do not re-dispatch completed tasks. `git clean -fdx` deletes the ledger; recover from `git log`.

`NEEDS_CONTEXT` / `BLOCKED`: add context, split the task, or fix the plan. Never retry the identical prompt.

## Close

After every task is complete, `review-package MERGE_BASE HEAD -o .sdd/reviews/final.diff.md` and dispatch final-reviewer-prompt.md once, including deferred Minors. If findings remain, one fix subagent for the whole list, then re-run final review. Then use sdd-finish.

Pack root is the directory containing `scripts/` and `skills/`.
````

- [ ] **Step 5: Verify with grep**

```bash
grep -q 'HOST_SUBAGENT_UNAVAILABLE' skills/sdd-execute/SKILL.md
grep -q 'task-brief' skills/sdd-execute/SKILL.md
grep -q 'review-package' skills/sdd-execute/SKILL.md
grep -q 'Task N: complete (commits' skills/sdd-execute/SKILL.md
grep -q 'DONE_WITH_CONCERNS' skills/sdd-execute/SKILL.md
grep -q 'sdd-finish' skills/sdd-execute/SKILL.md
grep -q 'TDD Evidence' skills/sdd-execute/implementer-prompt.md
grep -q 'Spec Compliance' skills/sdd-execute/task-reviewer-prompt.md
grep -q 'Ready to merge' skills/sdd-execute/final-reviewer-prompt.md
grep -L 'sdd_implementer\|sdd_task_reviewer\|sdd_final_reviewer\|sdd_simple_implementer' skills/sdd-execute/*
```

The last command must print all four files (no Codex agent names).

- [ ] **Step 6: Commit**

```bash
git add skills/sdd-execute
git commit -m "Add subagent execution with file handoffs and a progress ledger."
```

---

### Task 8: Finish skill

**Files:**
- Create: `skills/sdd-finish/SKILL.md`

**Interfaces:**
- Consumes: Task 4 `stack-prs --base --ledger --plan`; test suite of the consuming repo
- Produces: four-option menu; option 4 only when `.sdd/progress.md` has complete lines

- [ ] **Step 1: Write `skills/sdd-finish/SKILL.md`**

````markdown
---
name: sdd-finish
description: After implementation is green, merge locally, open one PR, keep the branch, or open stacked PRs one per plan task.
---

# SDD Finish

Announce: "I'm using sdd-finish."

Run the consuming repo's full test suite. If it fails, report failures and do not show the menu.

Confirm the base branch (plan, conversation, or upstream). If unsure, ask.

## Menu

Named branch (normal repo or named worktree), present exactly:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Push stacked PRs, one per plan Task

Which option?
```

Detached HEAD: omit 1. Bounded work with no `.sdd/progress.md` complete lines: omit 4.

Wait for the human. Do not add extra options.

## Execute

1. Checkout base, pull, merge the feature branch, re-run tests. On failure, stop and leave the branch. On success, delete the feature branch only after tests pass.
2. `git push -u origin <feature-branch>` then `gh pr create` for that single branch. Needs `gh`.
3. Do nothing.
4. Run:

```text
python3 <pack-root>/scripts/stack-prs --base <base-branch> --ledger .sdd/progress.md --plan <plan-path>
```

If the command exits non-zero, report any PR URLs it printed and which tasks remain. Do not force-push. Do not rebase or amend. Needs `gh`.

Option 4 is unavailable without a ledger. Do not invent task boundaries from `git log` guesswork.
````

Also include in the skill (unfenced in the file): worktree cleanup is out of scope unless this checkout is a git worktree you created in this session — v1 does not require creating worktrees.

- [ ] **Step 2: Verify with grep**

```bash
grep -q 'Push stacked PRs, one per plan Task' skills/sdd-finish/SKILL.md
grep -q 'stack-prs' skills/sdd-finish/SKILL.md
grep -q 'omit 4' skills/sdd-finish/SKILL.md
grep -q 'Do not force-push' skills/sdd-finish/SKILL.md
```

- [ ] **Step 3: Commit**

```bash
git add skills/sdd-finish/SKILL.md
git commit -m "Add finish options including stacked PRs per task."
```

---

### Task 9: Router, plugins, licenses, README

**Files:**
- Create: `skills/sdd/SKILL.md`
- Create: `.claude-plugin/plugin.json`
- Create: `.cursor-plugin/plugin.json`
- Create: `LICENSE`
- Create: `LICENSE-superpowers.txt`
- Modify: `README.md`

**Interfaces:**
- Consumes: all skills from Tasks 5–8
- Produces: pack installable on Cursor and Claude Code from this repo root

- [ ] **Step 1: Write `skills/sdd/SKILL.md`**

````markdown
---
name: sdd
description: Route spec-driven work to sdd-design, sdd-plan, sdd-execute, or sdd-finish. Use when the user wants SDD, a spec, a plan, implementation of a plan, or to finish a branch.
---

# SDD

This directory is the pack root. Install the whole pack. Never copy one SKILL.md.

## Route

| Situation | Skill |
|---|---|
| New idea, fuzzy words, or any architectural change without a spec | sdd-design |
| Approved architectural spec, no plan yet | sdd-plan |
| Plan exists, implement it | sdd-execute |
| Implementation green, integrate | sdd-finish |
| User asks to "just implement" something architectural | sdd-design first |

Do not run sdd-execute without a plan file. Do not run architectural implementation without a spec file.

Do not invoke Superpowers or grill-with-docs.

Pack root = the directory containing `skills/` and `scripts/`.
````

- [ ] **Step 2: Write plugin manifests**

`.claude-plugin/plugin.json`:

```json
{
  "name": "sdd",
  "description": "Spec-driven development: grill-style design, plans, subagent execution, stacked PRs",
  "version": "0.1.0",
  "author": { "name": "sdd" },
  "license": "MIT"
}
```

`.cursor-plugin/plugin.json`:

```json
{
  "name": "sdd",
  "displayName": "SDD",
  "description": "Spec-driven development: grill-style design, plans, subagent execution, stacked PRs",
  "version": "0.1.0",
  "author": { "name": "sdd" },
  "license": "MIT",
  "skills": "./skills/"
}
```

- [ ] **Step 3: Write licenses**

`LICENSE` — MIT, copyright line `Copyright (c) 2026 sdd`. Standard MIT permission paragraphs (same structure as Superpowers MIT).

`LICENSE-superpowers.txt` — the full Superpowers MIT text:

```
MIT License

Copyright (c) 2025 Jesse Vincent
```

followed by the standard MIT paragraphs (copy from obra/superpowers LICENSE). Add a one-line preface: "Portions of the plan, execute, finish, and prompt text are adapted from Superpowers, licensed MIT:"

- [ ] **Step 4: Replace README.md**

English install + checklist:

```markdown
# sdd

Skill pack for spec-driven development on Cursor and Claude Code.

Markdown is canonical. HTML is generated beside it. Install this repository as a whole pack — do not copy a single SKILL.md.

## Install

**Claude Code:** from this repo, install it as a local plugin (the `.claude-plugin/` manifest).

**Cursor:** install this repo as a plugin, or point Cursor at this folder so it loads `./skills/`.

Python 3.11+ is required for `scripts/`. `gh` is required only for finish options 2 and 4.

## Pipeline

sdd-design → sdd-plan → sdd-execute → sdd-finish

## Manual check

1. In a throwaway git repo, invoke sdd-design, answer one glossary question, confirm `CONTEXT.md` and `CONTEXT.html` appear.
2. On Cursor and on Claude Code, confirm the `sdd` skill is visible.
3. `python3 scripts/stack-prs --help` shows `--dry-run`.
```

Do not claim marketplace publication.

- [ ] **Step 5: Verify**

```bash
test -f skills/sdd/SKILL.md
test -f .claude-plugin/plugin.json
test -f .cursor-plugin/plugin.json
test -f LICENSE
test -f LICENSE-superpowers.txt
grep -q 'do not copy a single SKILL.md' README.md
python3 -m pytest tests/ -v
```

Expected: tests PASS, files exist.

- [ ] **Step 6: Commit**

```bash
git add skills/sdd/SKILL.md .claude-plugin/plugin.json .cursor-plugin/plugin.json LICENSE LICENSE-superpowers.txt README.md
git commit -m "Package the skill pack for Cursor and Claude Code."
```

---

## Self-review notes (author)

Spec coverage: render-docs, task-brief, review-package, stack-prs, formats, five skills, prompts, plugin manifests, licenses, README, pytest fixtures, host routing, HOST_SUBAGENT_UNAVAILABLE, bounded omitting option 4, Task heading syntax, no Superpowers/grill runtime, no Codex agents, vendored mistune, CSS copy, ledger line format, no HEAD~1.

Placeholder scan: Task 4 tests are complete (no PATH wipe). Task 7 prompt files are inlined. Task 1 includes full `render.py`.
