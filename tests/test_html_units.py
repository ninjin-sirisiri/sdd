from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sddlib.html_units import (
    RECEIPT_SCHEMA,
    SEMANTIC_CONTRACT,
    SOURCE_INDEX_SCHEMA,
    SourceScanError,
    UnitSchemaError,
    scan_markdown,
    source_index,
    strict_requirements,
    validate_provenance,
    validate_receipt,
    validate_source_index,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures"
UNIT_FIXTURES = FIXTURE_ROOT / "units"


def _load(name: str) -> dict[str, object]:
    return json.loads((UNIT_FIXTURES / name).read_text(encoding="utf-8"))


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _assert_lossless(scan, data: bytes) -> None:
    for unit in scan.units:
        assert 0 <= unit.start <= unit.end <= len(data)
        assert data[unit.start : unit.end] == unit.text.encode("utf-8")
        assert unit.to_json()["source_digest"] == scan.digest
    for item in scan.unsupported:
        assert 0 <= item.start <= item.end <= len(data)
        assert data[item.start : item.end] == item.text.encode("utf-8")
        assert item.to_json()["source_digest"] == scan.digest


def _unit_by_kind(scan, kind: str):
    return [unit for unit in scan.units if unit.kind == kind]


def test_empty_document_is_complete_and_matches_schema_fixture() -> None:
    scan = scan_markdown(b"")

    assert scan.complete
    assert scan.status == "complete"
    assert scan.units == ()
    assert scan.unsupported == ()
    assert scan.digest == _digest(b"")
    assert scan.byte_length == 0
    assert scan.to_index() == _load("source-index.empty.json")
    assert validate_source_index(scan.to_index()) == scan.to_index()

    with pytest.raises(TypeError):
        scan_markdown(123)  # type: ignore[arg-type]


def test_crlf_and_japanese_text_use_original_utf8_byte_offsets() -> None:
    data = (
        "# 見出し\r\n"
        "\r\n"
        "本文は `コード` と [リンク](https://example.com/path) を含む。\r\n"
    ).encode("utf-8")
    scan = scan_markdown(data)

    assert scan.complete
    assert scan.digest == _digest(data)
    _assert_lossless(scan, data)

    heading = _unit_by_kind(scan, "heading")[0]
    heading_text = "# 見出し".encode("utf-8")
    assert heading.start == 0
    assert heading.end == len(heading_text)
    assert heading.fields == {"level": 1, "slug": "見出し"}

    paragraph = _unit_by_kind(scan, "paragraph")[0]
    assert data.startswith("本文".encode("utf-8"), paragraph.start)
    # CRLF is two bytes; the paragraph starts after heading + two CRLF pairs.
    assert paragraph.start == len(heading_text) + 4
    assert paragraph.end == paragraph.start + len(
        "本文は `コード` と [リンク](https://example.com/path) を含む。".encode("utf-8")
    )

    inline = _unit_by_kind(scan, "inline_code")[0]
    assert inline.fields["value"] == "コード"
    assert data[inline.start : inline.end] == "`コード`".encode("utf-8")
    assert inline.parent == paragraph.id

    link = _unit_by_kind(scan, "link")[0]
    assert link.fields["destination"] == "https://example.com/path"
    assert data[link.start : link.end] == "[リンク](https://example.com/path)".encode(
        "utf-8"
    )


def test_duplicate_headings_keep_unique_ids_and_occurrence_slugs() -> None:
    scan = scan_markdown("# Repeat\n\n## Repeat\n\n## Repeat\n")
    headings = _unit_by_kind(scan, "heading")

    assert [heading.fields["slug"] for heading in headings] == [
        "repeat",
        "repeat-1",
        "repeat-2",
    ]
    assert len({heading.id for heading in headings}) == 3
    validate_source_index(scan.to_index())


def test_nested_lists_have_parent_child_ranges_depths_and_checkboxes() -> None:
    data = b"- a\n  - b\n    1. c\n- [x] d\n"
    scan = scan_markdown(data)

    _assert_lossless(scan, data)
    assert scan.complete
    lists = _unit_by_kind(scan, "list")
    items = _unit_by_kind(scan, "list_item")
    assert [(item["depth"], item["ordered"], item["start"]) for item in (unit.fields for unit in lists)] == [
        (0, False, None),
        (1, False, None),
        (2, True, 1),
    ]
    assert [item.fields["depth"] for item in items] == [0, 1, 2, 0]
    assert items[-1].fields["checkbox"] == "checked"
    assert lists[1].parent == items[0].id
    assert lists[2].parent == items[1].id
    assert items[0].parent == lists[0].id
    assert items[1].parent == lists[1].id
    for unit in scan.units:
        if unit.parent is None:
            continue
        parent = next(candidate for candidate in scan.units if candidate.id == unit.parent)
        assert parent.start <= unit.start
        assert unit.end <= parent.end
    validate_source_index(scan.to_index())


def test_fenced_code_inside_a_list_item_keeps_its_parent_and_code_kind() -> None:
    data = b"- item\n\n  ```sh\n  echo hi\n  ```\n"
    scan = scan_markdown(data)

    _assert_lossless(scan, data)
    item = _unit_by_kind(scan, "list_item")[0]
    code = _unit_by_kind(scan, "code_block")[0]
    assert code.parent == item.id
    assert code.fields["language"] == "sh"
    assert code.fields["content"] == "  echo hi\n"
    assert item.start <= code.start and code.end <= item.end
    validate_source_index(scan.to_index())


def test_table_header_and_body_cells_have_exact_ranges_and_inline_children() -> None:
    data = (
        b"| Area | Rule |\n"
        b"| :--- | ---: |\n"
        b"| `Source` | Markdown |\n"
        b"| Companion | [HTML](https://example.com) |\n"
    )
    scan = scan_markdown(data)

    _assert_lossless(scan, data)
    tables = _unit_by_kind(scan, "table")
    headers = _unit_by_kind(scan, "table_header")
    cells = _unit_by_kind(scan, "table_cell")
    assert len(tables) == 1
    assert tables[0].fields == {
        "columns": 2,
        "alignments": ["left", "right"],
    }
    assert [header.text for header in headers] == ["Area", "Rule"]
    assert [cell.text for cell in cells] == [
        "`Source`",
        "Markdown",
        "Companion",
        "[HTML](https://example.com)",
    ]
    assert [(cell.fields["row"], cell.fields["column"]) for cell in cells] == [
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
    ]
    inline = _unit_by_kind(scan, "inline_code")[0]
    link = _unit_by_kind(scan, "link")[0]
    assert inline.parent == cells[0].id
    assert link.parent == cells[3].id
    assert all(unit.parent == tables[0].id for unit in headers + cells)
    validate_source_index(scan.to_index())


def test_code_blocks_and_inline_units_record_exact_values() -> None:
    data = (
        b"```python\n"
        b"print('hi')\n"
        b"\n"
        b"value = 1\n"
        b"```\n"
        b"\n"
        b"    indented\n"
        b"\n"
        b"`inline` and [link](https://example.com) and ![alt](img.png) and "
        b"<https://example.com/auto>\n"
    )
    scan = scan_markdown(data)

    _assert_lossless(scan, data)
    assert scan.complete
    fenced = _unit_by_kind(scan, "code_block")[0]
    assert fenced.fields == {
        "fenced": True,
        "info": "python",
        "language": "python",
        "closed": True,
        "content": "print('hi')\n\nvalue = 1\n",
    }
    indented = _unit_by_kind(scan, "code_block")[1]
    assert indented.fields["fenced"] is False
    assert indented.fields["language"] is None
    assert indented.fields["content"] == "indented"

    inline = _unit_by_kind(scan, "inline_code")[0]
    link = _unit_by_kind(scan, "link")[0]
    image = _unit_by_kind(scan, "image")[0]
    autolink = _unit_by_kind(scan, "link")[1]
    assert inline.fields["value"] == "inline"
    assert link.fields["destination"] == "https://example.com"
    assert image.fields == {"destination": "img.png", "alt": "alt"}
    assert autolink.fields["autolink"] is True
    assert autolink.fields["destination"] == "https://example.com/auto"

    requirements = strict_requirements(scan)
    assert {"unit": fenced.id, "category": "code", "value": "print('hi')\n\nvalue = 1\n"} in requirements
    assert {"unit": inline.id, "category": "code", "value": "inline"} in requirements
    assert {"unit": link.id, "category": "link", "value": "https://example.com"} in requirements
    validate_source_index(scan.to_index())


def test_glossary_term_and_avoid_entries_are_related_and_strict() -> None:
    data = (FIXTURE_ROOT / "glossary" / "CONTEXT.md").read_bytes()
    scan = scan_markdown(data)

    _assert_lossless(scan, data)
    assert scan.complete
    term = _unit_by_kind(scan, "glossary_term")[0]
    avoid = _unit_by_kind(scan, "glossary_avoid")[0]
    assert term.fields["term"] == "Order"
    assert avoid.fields["avoid"] == ["Purchase", "transaction"]
    assert avoid.parent == term.id
    requirements = strict_requirements(scan)
    assert {"unit": term.id, "category": "glossary_term", "value": "Order"} in requirements
    assert {"unit": avoid.id, "category": "avoid", "value": "Purchase"} in requirements
    assert {"unit": avoid.id, "category": "avoid", "value": "transaction"} in requirements
    validate_source_index(scan.to_index())


def test_unsupported_markdown_is_reported_instead_of_dropped() -> None:
    data = (
        b"Title\n"
        b"=====\n"
        b"\n"
        b"[ref]: https://example.com\n"
        b"\n"
        b"See [link][ref] and [^1].\n"
        b"\n"
        b"[^1]: note\n"
    )
    scan = scan_markdown(data)

    _assert_lossless(scan, data)
    assert scan.status == "incomplete"
    assert {item.kind for item in scan.unsupported} == {
        "setext_heading",
        "reference_definition",
        "reference_link",
        "footnote_reference",
        "footnote_definition",
    }
    assert not any(unit.kind == "heading" for unit in scan.units)
    index = scan.to_index()
    assert index["status"] == "incomplete"
    assert validate_source_index(index) == index


def test_non_utf8_source_is_rejected_with_byte_offset() -> None:
    with pytest.raises(SourceScanError) as error:
        scan_markdown(b"# ok\n\xff\n")
    assert "byte 5" in str(error.value)


def test_every_pack_target_fixture_scans_completely() -> None:
    paths = sorted(
        path
        for path in FIXTURE_ROOT.rglob("*.md")
        if "units" not in path.parts
    )
    assert paths
    for path in paths:
        scan = scan_markdown(path.read_bytes())
        assert scan.complete, (path, [item.kind for item in scan.unsupported])
        validate_source_index(scan.to_index(path.relative_to(FIXTURE_ROOT).as_posix()))


def test_source_index_binds_every_unit_to_the_exact_source_digest() -> None:
    data = b"# Title\n\nBody.\n"
    index = source_index(data, path="docs/sdd/specs/example.md")
    validate_source_index(index)

    assert index["schema"] == SOURCE_INDEX_SCHEMA
    assert index["contract"] == SEMANTIC_CONTRACT
    assert index["source"] == {
        "path": "docs/sdd/specs/example.md",
        "digest": _digest(data),
        "byte_length": len(data),
    }
    for unit in index["units"]:  # type: ignore[union-attr]
        assert unit["source_digest"] == _digest(data)

    broken = json.loads(json.dumps(index))
    broken["units"][0]["source_digest"] = _digest(b"other")
    with pytest.raises(UnitSchemaError) as error:
        validate_source_index(broken)
    assert "must equal the index source digest" in str(error.value)


def test_valid_schema_fixtures_pass_and_are_returned_unchanged() -> None:
    for loader, name in (
        (validate_source_index, "source-index.empty.json"),
        (validate_provenance, "provenance.valid.json"),
        (validate_receipt, "receipt.valid.json"),
    ):
        value = _load(name)
        assert loader(value) is value


@pytest.mark.parametrize(
    ("validator", "fixture", "message"),
    (
        (
            validate_source_index,
            "invalid/source-index-unknown-field.json",
            "unknown field(s): extra",
        ),
        (
            validate_source_index,
            "invalid/source-index-unknown-version.json",
            "unsupported version 2",
        ),
        (
            validate_source_index,
            "invalid/source-index-duplicate-id.json",
            "duplicate id 'paragraph-000000'",
        ),
        (
            validate_provenance,
            "invalid/provenance-unknown-field.json",
            "unknown field(s): extra",
        ),
        (
            validate_provenance,
            "invalid/provenance-unknown-version.json",
            "unsupported version 2",
        ),
        (
            validate_provenance,
            "invalid/provenance-duplicate-unit.json",
            "duplicate id 'heading-000000'",
        ),
        (
            validate_provenance,
            "invalid/provenance-missing-source.json",
            "missing required field(s): source",
        ),
        (
            validate_provenance,
            "invalid/provenance-missing-calculation-field.json",
            "missing required field(s): formula",
        ),
        (
            validate_receipt,
            "invalid/receipt-unknown-version.json",
            "unsupported version 2",
        ),
        (
            validate_receipt,
            "invalid/receipt-missing-verification.json",
            "missing required field(s): verification",
        ),
        (
            validate_receipt,
            "invalid/receipt-missing-condition.json",
            "missing condition(s)",
        ),
    ),
)
def test_schema_fixtures_reject_unknown_versions_fields_duplicates_and_missing_data(
    validator, fixture: str, message: str
) -> None:
    with pytest.raises(UnitSchemaError) as error:
        validator(_load(fixture))
    assert message in str(error.value)


def test_provenance_rejects_unknown_parent_and_duplicate_mapping() -> None:
    provenance = _load("provenance.valid.json")
    broken = json.loads(json.dumps(provenance))
    broken["units"][0]["parent"] = "paragraph-999999"
    with pytest.raises(UnitSchemaError) as error:
        validate_provenance(broken)
    assert "unknown parent id" in str(error.value)

    duplicate = json.loads(json.dumps(provenance))
    duplicate["mappings"].append(dict(duplicate["mappings"][0]))
    with pytest.raises(UnitSchemaError) as error:
        validate_provenance(duplicate)
    assert "duplicate mapping" in str(error.value)

    dangling = json.loads(json.dumps(provenance))
    dangling["mappings"][0]["unit"] = "heading-999999"
    with pytest.raises(UnitSchemaError) as error:
        validate_provenance(dangling)
    assert "unknown unit id" in str(error.value)


def test_provenance_strict_and_calculation_shapes_are_fixed() -> None:
    provenance = _load("provenance.valid.json")

    missing_targets = json.loads(json.dumps(provenance))
    missing_targets["strict"].append(
        {
            "unit": "heading-000000",
            "category": "code",
            "value": "value",
        }
    )
    with pytest.raises(UnitSchemaError) as error:
        validate_provenance(missing_targets)
    assert "missing required field(s): targets" in str(error.value)

    bad_operation = json.loads(json.dumps(provenance))
    bad_operation["calculations"][0]["operation"] = "eval"
    with pytest.raises(UnitSchemaError) as error:
        validate_provenance(bad_operation)
    assert "unsupported value 'eval'" in str(error.value)

    missing_result = json.loads(json.dumps(provenance))
    del missing_result["calculations"][0]["result"]
    with pytest.raises(UnitSchemaError) as error:
        validate_provenance(missing_result)
    assert "missing required field(s): result" in str(error.value)


def test_receipt_requires_h2_purpose_verification_and_condition_evidence() -> None:
    receipt = _load("receipt.valid.json")

    wrong_purpose = json.loads(json.dumps(receipt))
    wrong_purpose["h2"]["purpose"] = "completion"
    with pytest.raises(UnitSchemaError) as error:
        validate_receipt(wrong_purpose)
    assert "h2.purpose" in str(error.value)

    unknown_condition = json.loads(json.dumps(receipt))
    unknown_condition["conditions"][0]["id"] = "other"
    with pytest.raises(UnitSchemaError) as error:
        validate_receipt(unknown_condition)
    assert "unknown condition id" in str(error.value)

    empty_evidence = json.loads(json.dumps(receipt))
    empty_evidence["conditions"][0]["evidence"] = []
    with pytest.raises(UnitSchemaError) as error:
        validate_receipt(empty_evidence)
    assert "must not be empty" in str(error.value)

    unknown_field = json.loads(json.dumps(receipt))
    unknown_field["verification"]["extra"] = True
    with pytest.raises(UnitSchemaError) as error:
        validate_receipt(unknown_field)
    assert "unknown field(s): extra" in str(error.value)


def test_unknown_html_contract_value_is_not_a_semantic_receipt() -> None:
    receipt = _load("receipt.valid.json")
    receipt["contract"] = "semantic-v2"
    with pytest.raises(UnitSchemaError) as error:
        validate_receipt(receipt)
    assert "contract" in str(error.value)

    # The three schemas are intentionally distinct.
    with pytest.raises(UnitSchemaError) as error:
        validate_receipt({"schema": RECEIPT_SCHEMA, "version": 1})
    assert "missing required field(s)" in str(error.value)
