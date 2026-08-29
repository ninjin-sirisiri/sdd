from __future__ import annotations

from pathlib import Path
import argparse
import html
import sys

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
MARKDOWN_SUFFIXES = {".md", ".markdown"}
_MARKDOWN = mistune.create_markdown(
    escape=True,
    plugins=["strikethrough", "footnotes", "table"],
)
_CSP = (
    "default-src 'none'; img-src 'self' data:; style-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def html_path_for(md_path: Path) -> Path:
    if md_path.suffix.lower() not in MARKDOWN_SUFFIXES:
        raise ValueError(f"not a markdown file: {md_path}")
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
    safe_title = html.escape(title, quote=True)
    safe_href = html.escape(css_href, quote=True)
    safe_csp = html.escape(_CSP, quote=True)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="und">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{safe_csp}">\n'
        f"<title>{safe_title}</title>\n"
        f'<link rel="stylesheet" href="{safe_href}">\n'
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
        out = html_path_for(md)
        if md.resolve() == out.resolve():
            raise ValueError(f"output path would overwrite input: {md}")
        href = _css_href(out, css)
        body = _MARKDOWN(text)
        if not isinstance(body, str):
            raise TypeError(f"expected HTML string from markdown renderer, got {type(body)}")
        out.write_text(
            _document(body, _title(text, md.stem), href),
            encoding="utf-8",
        )
        written.append(out)
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
