from __future__ import annotations

from pathlib import Path
import argparse
import html
import re
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
_HEADING_RE = re.compile(r"<h([1-6])>(.*?)</h\1>", re.S)


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
    dest.write_bytes((root / "assets" / "sdd.css").read_bytes())
    return dest


def _doc_kind(md_path: Path) -> str:
    if md_path.name.lower() == "context.md":
        return "Glossary"
    parts = {part.lower() for part in md_path.parts}
    if "adr" in parts:
        return "ADR"
    if "specs" in parts:
        return "Spec"
    if "plans" in parts:
        return "Plan"
    return "Document"


def _plain_text(inner: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", inner, flags=re.S))


def _slugify(text: str, used: dict[str, int]) -> str:
    slug = re.sub(r"\s+", "-", text.strip())
    slug = re.sub(r"[^\w\-]", "", slug, flags=re.UNICODE)
    slug = slug.strip("-").lower() or "section"
    n = used.get(slug, 0)
    used[slug] = n + 1
    return slug if n == 0 else f"{slug}-{n}"


def _annotate_headings(body: str) -> tuple[str, list[tuple[int, str, str]]]:
    used: dict[str, int] = {}
    outline: list[tuple[int, str, str]] = []

    def repl(match: re.Match[str]) -> str:
        level = int(match.group(1))
        inner = match.group(2)
        text = _plain_text(inner)
        slug = _slugify(text, used)
        outline.append((level, slug, text))
        return f'<h{level} id="{html.escape(slug, quote=True)}">{inner}</h{level}>'

    return _HEADING_RE.sub(repl, body), outline


def _sectionize(body: str) -> str:
    chunks = re.split(r"(?=<h2\b)", body)
    if len(chunks) == 1:
        return body
    out = [chunks[0]]
    for chunk in chunks[1:]:
        out.append("<section>\n" + chunk.rstrip("\n") + "\n</section>\n")
    return "".join(out)


def _header(kind: str, outline: list[tuple[int, str, str]]) -> str:
    items = [
        (
            "<li>"
            f'<a href="#{html.escape(slug, quote=True)}">{html.escape(text)}</a>'
            "</li>"
        )
        for level, slug, text in outline
        if level == 2
    ]
    nav = ""
    if items:
        nav = (
            '\n<nav aria-label="On this page">\n<ul>\n'
            + "\n".join(items)
            + "\n</ul>\n</nav>"
        )
    return f"<header>\n<p>{html.escape(kind)}</p>{nav}\n</header>\n"


def _title(md_text: str, stem: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return stem


def _document(body: str, title: str, css_href: str, *, kind: str) -> str:
    annotated, outline = _annotate_headings(body)
    body = _sectionize(annotated)
    header = _header(kind, outline)
    safe_title = html.escape(title, quote=True)
    safe_href = html.escape(css_href, quote=True)
    safe_csp = html.escape(_CSP, quote=True)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="und">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{safe_csp}">\n'
        f"<title>{safe_title}</title>\n"
        f'<link rel="stylesheet" href="{safe_href}">\n'
        "</head>\n"
        "<body>\n"
        f"{header}"
        "<main>\n"
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
            _document(body, _title(text, md.stem), href, kind=_doc_kind(md)),
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
