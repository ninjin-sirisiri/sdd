from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

import pytest

from sddlib.html_policy import (
    DigestStatus,
    PathOutsideRepository,
    PolicyInputError,
    _markdown_visible_text,
    check_edit,
    parse_html,
    parse_digest_metadata,
    resolve_target,
    sha256_file,
    validate_html,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def _write_source(root: Path, relative: str = "CONTEXT.md", content: bytes = b"# Context\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _html(digest: str) -> str:
    return f'<meta name="sdd-source-digest" content="{digest}">'


def test_resolves_exact_targets_and_adjacent_companions(tmp_path: Path) -> None:
    cases = (
        ("CONTEXT.md", "CONTEXT.html", "context"),
        ("docs/adr/0001-choice.md", "docs/adr/0001-choice.html", "adr"),
        ("docs/sdd/specs/example.md", "docs/sdd/specs/example.html", "spec"),
        ("docs/sdd/plans/example.md", "docs/sdd/plans/example.html", "plan"),
    )
    for source, companion, kind in cases:
        target = resolve_target(tmp_path, source)
        assert target is not None
        assert target.source_relative == source
        assert target.companion_relative == companion
        assert target.kind == kind
        assert resolve_target(tmp_path, companion) == target

    assert resolve_target(tmp_path, "README.md") is None
    assert resolve_target(tmp_path, "docs/adr/nested/choice.md") is None
    assert resolve_target(tmp_path, "docs/sdd/assets/sdd.css") is None


def test_resolver_accepts_absolute_paths_and_rejects_escape(tmp_path: Path) -> None:
    source = _write_source(tmp_path)
    target = resolve_target(tmp_path, source.resolve())
    assert target is not None
    assert target.source_path == source.resolve()

    with pytest.raises(PathOutsideRepository):
        resolve_target(tmp_path, tmp_path.parent / "CONTEXT.md")


def test_sha256_preserves_crlf_trailing_whitespace_and_final_newline(tmp_path: Path) -> None:
    content = b"# Context\r\nvalue with trailing spaces  \r\nlast line"
    path = _write_source(tmp_path, content=content)
    assert sha256_file(path) == hashlib.sha256(content).hexdigest()

    path.write_bytes(content + b"\n")
    assert sha256_file(path) == hashlib.sha256(content + b"\n").hexdigest()


def test_markdown_visible_text_preserves_inline_code_contents() -> None:
    visible = _markdown_visible_text(
        "An `_Avoid_` path `scripts/_vendor/mistune/` is documented.\n"
    )

    assert visible == "An _Avoid_ path scripts/_vendor/mistune/ is documented."


@pytest.mark.parametrize(
    ("html", "status"),
    (
        ("<html></html>", DigestStatus.MISSING),
        (
            '<meta name="sdd-source-digest" content="sha256:'
            + "a" * 64
            + '"><meta name="sdd-source-digest" content="sha256:'
            + "b" * 64
            + '">',
            DigestStatus.DUPLICATE,
        ),
        ('<meta name="sdd-source-digest">', DigestStatus.MALFORMED),
        (
            '<meta name="sdd-source-digest" content="sha256:'
            + "A" * 64
            + '">',
            DigestStatus.UPPERCASE,
        ),
        (
            '<meta name="sdd-source-digest" content="sha256:'
            + "g" * 64
            + '">',
            DigestStatus.MALFORMED,
        ),
    ),
)
def test_digest_metadata_statuses_are_distinguishable(
    html: str, status: DigestStatus
) -> None:
    parsed = parse_digest_metadata(html)
    assert parsed.status is status
    assert not parsed.is_valid


def test_digest_metadata_requires_one_lowercase_digest() -> None:
    digest = "sha256:" + "a1" * 32
    parsed = parse_digest_metadata(
        f'<meta name="sdd-source-digest" content="{digest}">'
    )
    assert parsed.status is DigestStatus.VALID
    assert parsed.digest == digest
    assert parsed.is_valid


def test_markdown_edit_reports_companion_and_current_digest(tmp_path: Path) -> None:
    content = b"# Context\r\nbody  \n"
    source = _write_source(tmp_path, content=content)
    result = check_edit(tmp_path, [source])
    assert result == {
        "decision": "allow",
        "message": "Markdown changed; author CONTEXT.html separately.",
        "paths": ["CONTEXT.md", "CONTEXT.html"],
        "expected_digests": {"CONTEXT.html": _digest(content)},
    }


def test_mixed_source_and_companion_operation_is_denied(tmp_path: Path) -> None:
    content = b"# Context\n"
    _write_source(tmp_path, content=content)
    result = check_edit(tmp_path, ["CONTEXT.md", "CONTEXT.html"])
    assert result["decision"] == "deny"
    assert "one operation" in result["message"]
    assert result["paths"] == ["CONTEXT.md", "CONTEXT.html"]


def test_stale_companion_is_allowed_and_current_companion_is_html_only_denied(
    tmp_path: Path,
) -> None:
    old = b"# Old\n"
    new = b"# New\n"
    _write_source(tmp_path, content=new)
    (tmp_path / "CONTEXT.html").write_text(_html(_digest(old)), encoding="utf-8")

    allowed = check_edit(tmp_path, ["CONTEXT.html"])
    assert allowed["decision"] == "allow"
    assert allowed["expected_digests"] == {"CONTEXT.html": _digest(new)}

    (tmp_path / "CONTEXT.html").write_text(_html(_digest(new)), encoding="utf-8")
    denied = check_edit(tmp_path, ["CONTEXT.html"])
    assert denied["decision"] == "deny"
    assert "already current" in denied["message"]


def test_multiple_source_edits_use_final_digest_and_stale_again_after_source_edit(
    tmp_path: Path,
) -> None:
    first = b"# First\n"
    second = b"# Second\n"
    third = b"# Third\n"
    _write_source(tmp_path, content=first)
    (tmp_path / "CONTEXT.html").write_text(_html(_digest(first)), encoding="utf-8")

    _write_source(tmp_path, content=second)
    _write_source(tmp_path, content=third)
    result = check_edit(tmp_path, ["CONTEXT.html"])
    assert result["decision"] == "allow"
    assert result["expected_digests"] == {"CONTEXT.html": _digest(third)}

    (tmp_path / "CONTEXT.html").write_text(_html(_digest(third)), encoding="utf-8")
    _write_source(tmp_path, content=b"# Fourth\n")
    assert check_edit(tmp_path, ["CONTEXT.html"])["decision"] == "allow"


def test_new_source_and_explicit_bootstrap_allow_missing_companions(tmp_path: Path) -> None:
    _write_source(tmp_path, content=b"# New\n")
    new_source = check_edit(
        tmp_path,
        ["CONTEXT.html"],
        new_source_paths=["CONTEXT.md"],
    )
    assert new_source["decision"] == "allow"

    other = _write_source(tmp_path, "docs/adr/0001-choice.md", b"# Choice\n")
    bootstrap = check_edit(
        tmp_path,
        [other.with_suffix(".html")],
        bootstrap_paths=[other.with_suffix(".html")],
    )
    assert bootstrap["decision"] == "allow"
    assert bootstrap["expected_digests"] == {
        "docs/adr/0001-choice.html": _digest(b"# Choice\n")
    }


def test_missing_or_invalid_companion_is_denied_in_normal_mode(tmp_path: Path) -> None:
    content = b"# Context\n"
    _write_source(tmp_path, content=content)
    missing = check_edit(tmp_path, ["CONTEXT.html"])
    assert missing["decision"] == "deny"
    assert "no source digest metadata" in missing["message"]

    (tmp_path / "CONTEXT.html").write_text(
        '<meta name="sdd-source-digest" content="sha256:' + "A" * 64 + '">',
        encoding="utf-8",
    )
    uppercase = check_edit(tmp_path, ["CONTEXT.html"])
    assert uppercase["decision"] == "deny"
    assert "uppercase" in uppercase["message"]


def test_unrelated_and_css_only_edits_are_noop_allows(tmp_path: Path) -> None:
    result = check_edit(
        tmp_path,
        ["README.md", "docs/sdd/assets/sdd.css", "notes.txt"],
    )
    assert result == {
        "decision": "allow",
        "message": "No synchronized target documents are affected.",
        "paths": [],
        "expected_digests": {},
    }


def test_unknown_and_malformed_policy_paths_are_structured_input_errors(
    tmp_path: Path,
) -> None:
    with pytest.raises(PolicyInputError) as error:
        check_edit(tmp_path, ["CONTEXT.md"], unexpected=True)
    assert error.value.exit_code == 2
    assert "unexpected" in error.value.message

    with pytest.raises(PolicyInputError) as error:
        check_edit(tmp_path, "CONTEXT.md")
    assert error.value.exit_code == 2
    assert error.value.result["decision"] == "deny"

    with pytest.raises(PolicyInputError):
        check_edit(tmp_path, [b"CONTEXT.md"])

    with pytest.raises(PathOutsideRepository) as error:
        check_edit(tmp_path, [tmp_path.parent / "CONTEXT.md"])
    assert error.value.exit_code == 2


def _copy_fixture(tmp_path: Path, relative_directory: str, stem: str) -> tuple[Path, Path]:
    fixture_source = FIXTURE_ROOT / relative_directory / f"{stem}.md"
    if relative_directory == "glossary":
        target_relative = Path("CONTEXT.md")
    elif relative_directory == "adr":
        target_relative = Path("docs/adr") / f"{stem}.md"
    elif relative_directory == "spec":
        target_relative = Path("docs/sdd/specs") / f"{stem}.md"
    else:
        target_relative = Path("docs/sdd/plans") / f"{stem}.md"
    html_relative = target_relative.with_suffix(".html")
    source = tmp_path / target_relative
    companion = tmp_path / html_relative
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixture_source, source)
    shutil.copyfile(fixture_source.with_suffix(".html"), companion)
    css = tmp_path / "docs/sdd/assets/sdd.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text("/* fixture stylesheet */\n", encoding="utf-8")
    return source, companion


def _violation_codes(result: dict[str, object]) -> set[str]:
    return {item["code"] for item in result["violations"]}  # type: ignore[index]


def test_authored_fixtures_validate_each_document_kind(tmp_path: Path) -> None:
    cases = (
        ("glossary", "CONTEXT"),
        ("adr", "0001-use-postgres"),
        ("spec", "2026-01-01-example-design"),
        ("plan", "2026-01-01-example"),
    )
    for directory, stem in cases:
        source, _companion = _copy_fixture(tmp_path, directory, stem)
        result = validate_html(tmp_path, source)
        assert result["decision"] == "allow", result
        assert result["violations"] == []


def test_glossary_requires_dl_and_keeps_avoid_inside_dd(tmp_path: Path) -> None:
    source, companion = _copy_fixture(tmp_path, "glossary", "CONTEXT")
    result = validate_html(tmp_path, source, companion)
    assert result["decision"] == "allow", result

    companion.write_text(
        companion.read_text(encoding="utf-8").replace("<dl>", "<div>").replace("</dl>", "</div>"),
        encoding="utf-8",
    )
    invalid = validate_html(tmp_path, source, companion)
    assert "glossary-structure" in _violation_codes(invalid)


def test_adr_allows_compact_decision_article_without_invented_headings(tmp_path: Path) -> None:
    source, _companion = _copy_fixture(tmp_path, "adr", "0001-use-postgres")
    result = validate_html(tmp_path, source)
    assert result["decision"] == "allow", result
    assert result["warnings"] == []


def test_spec_and_plan_fixtures_preserve_semantic_sections_and_tasks(tmp_path: Path) -> None:
    spec_source, _spec_companion = _copy_fixture(
        tmp_path, "spec", "2026-01-01-example-design"
    )
    plan_source, _plan_companion = _copy_fixture(
        tmp_path, "plan", "2026-01-01-example"
    )
    spec = validate_html(tmp_path, spec_source)
    plan = validate_html(tmp_path, plan_source)
    assert spec["decision"] == "allow", spec
    assert plan["decision"] == "allow"


def test_duplicate_heading_ids_use_occurrence_suffixes(tmp_path: Path) -> None:
    source, companion = _copy_fixture(tmp_path, "spec", "duplicate-headings")
    result = validate_html(tmp_path, source, companion)
    assert result["decision"] == "allow", result

    companion.write_text(
        companion.read_text(encoding="utf-8").replace(
            'id="repeat-1"', 'id="wrong-repeat"'
        ),
        encoding="utf-8",
    )
    invalid = validate_html(tmp_path, source, companion)
    assert "heading-id" in _violation_codes(invalid)


def test_missing_outline_is_a_violation_when_h2_or_h3_exists(tmp_path: Path) -> None:
    source, companion = _copy_fixture(
        tmp_path, "spec", "2026-01-01-example-design"
    )
    html = companion.read_text(encoding="utf-8")
    start = html.index("<aside")
    end = html.index("</aside>", start) + len("</aside>")
    companion.write_text(html[:start] + html[end:], encoding="utf-8")
    result = validate_html(tmp_path, source, companion)
    assert "outline-missing" in _violation_codes(result)


def test_parser_retains_order_and_rejects_malformed_or_unbalanced_html(
    tmp_path: Path,
) -> None:
    source, companion = _copy_fixture(
        tmp_path, "adr", "0001-use-postgres"
    )
    document = parse_html('<main><p>before <strong>after</strong></p></main>')
    assert [node.tag for node in document.nodes] == ["main", "p", "strong"]
    assert document.root.children[0].content[0].tag == "p"  # type: ignore[union-attr]

    companion.write_text(
        companion.read_text(encoding="utf-8").replace("</main>", ""),
        encoding="utf-8",
    )
    result = validate_html(tmp_path, source, companion)
    assert "malformed-html" in _violation_codes(result)


@pytest.mark.parametrize(
    ("needle", "code"),
    (
        ("<script>alert(1)</script>", "unsafe-tag"),
        (' onmouseover="alert(1)"', "event-attribute"),
        (' style="color:red"', "style-attribute"),
        ('href="https://cdn.example.test/sdd.css"', "stylesheet-resource"),
        ('src="https://example.test/image.png"', "network-resource"),
    ),
)
def test_unsafe_tags_attributes_and_resources_are_rejected(
    tmp_path: Path, needle: str, code: str
) -> None:
    source, companion = _copy_fixture(
        tmp_path, "spec", "2026-01-01-example-design"
    )
    html = companion.read_text(encoding="utf-8")
    if needle.startswith("<script"):
        html = html.replace("<body>", f"<body>{needle}")
    elif "href=" in needle:
        html = html.replace('href="../assets/sdd.css"', needle)
    elif "src=" in needle:
        html = html.replace("</main>", f'<img {needle} alt="diagram"></main>')
    else:
        html = html.replace("<main", f"<main{needle}")
    companion.write_text(html, encoding="utf-8")
    result = validate_html(tmp_path, source, companion)
    assert code in _violation_codes(result)


def test_tables_need_caption_and_scoped_header_cells(tmp_path: Path) -> None:
    source, companion = _copy_fixture(
        tmp_path, "spec", "2026-01-01-example-design"
    )
    html = companion.read_text(encoding="utf-8")
    html = html.replace("<caption>Design rules</caption>\n", "")
    html = html.replace('<th scope="col">Area</th>', "<th>Area</th>")
    companion.write_text(html, encoding="utf-8")
    result = validate_html(tmp_path, source, companion)
    assert {"table-caption", "table-header-scope"} <= _violation_codes(result)


def test_source_omission_reports_first_missing_fragment_with_source_path(
    tmp_path: Path,
) -> None:
    source, companion = _copy_fixture(
        tmp_path, "plan", "2026-01-01-example"
    )
    companion.write_text(
        companion.read_text(encoding="utf-8").replace(
            "UNIQUE_TASK_TWO", "REMOVED_TASK_TWO"
        ),
        encoding="utf-8",
    )
    result = validate_html(tmp_path, source, companion)
    assert "source-text" in _violation_codes(result)
    assert result["violations"][0]["path"] == "docs/sdd/plans/2026-01-01-example.md"  # type: ignore[index]


def test_source_reordering_is_reported_after_digest_is_updated(tmp_path: Path) -> None:
    source, companion = _copy_fixture(
        tmp_path, "plan", "2026-01-01-example"
    )
    original = source.read_bytes()
    reordered = original.replace(
        b"First body UNIQUE_TASK_ONE.\n\n## Task 2: Second thing\n\nSecond body UNIQUE_TASK_TWO.",
        b"Second body UNIQUE_TASK_TWO.\n\n## Task 1: First thing\n\nFirst body UNIQUE_TASK_ONE.",
    )
    source.write_bytes(reordered)
    digest = _digest(reordered)
    companion.write_text(
        companion.read_text(encoding="utf-8").replace(_digest(original), digest),
        encoding="utf-8",
    )
    result = validate_html(tmp_path, source, companion)
    assert "source-text" in _violation_codes(result)
    assert any("reordered" in item["message"] for item in result["violations"])  # type: ignore[index]


def test_invalid_digest_and_language_are_separate_structured_violations(
    tmp_path: Path,
) -> None:
    source, companion = _copy_fixture(
        tmp_path, "spec", "2026-01-01-example-design"
    )
    html = companion.read_text(encoding="utf-8")
    html = html.replace('lang="en"', 'lang="und"').replace(
        _digest(source.read_bytes()), "sha256:" + "0" * 64
    )
    companion.write_text(html, encoding="utf-8")
    result = validate_html(tmp_path, source, companion)
    assert {"digest-mismatch", "language"} <= _violation_codes(result)


def test_irregular_heading_levels_only_emit_warnings(tmp_path: Path) -> None:
    source, _companion = _copy_fixture(tmp_path, "spec", "irregular-headings")
    result = validate_html(tmp_path, source)
    assert result["decision"] == "allow"
    warning_codes = {item["code"] for item in result["warnings"]}  # type: ignore[index]
    assert {"multiple-h1", "skipped-heading-level"} <= warning_codes
