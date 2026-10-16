"""Integration tests using PDFs created in temporary directories."""

import json
from pathlib import Path

import pymupdf
import pytest

from pdf_chapters.cli import main
from pdf_chapters.filenames import slugify
from pdf_chapters.outline import derive_chapters


def make_pdf(path: Path, toc: list[list[object]] | None = None, pages: int = 6) -> Path:
    with pymupdf.open() as document:
        for number in range(1, pages + 1):
            page = document.new_page()
            page.insert_text((72, 72), f"Source page {number}")
        if toc:
            document.set_toc(toc)
        document.save(path)
    return path


def test_inspect_and_split_ranges(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "First", 2], [1, "Second", 4]])
    assert main(["inspect", str(source), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["bookmark_level"] == 1
    assert data["excluded_leading_pages"] == 1
    assert [(c["start_page"], c["end_page"], c["page_count"]) for c in data["chapters"]] == [
        (2, 3, 2), (4, 6, 3)
    ]
    destination = tmp_path / "chapters"
    assert main(["split", str(source), "--output-dir", str(destination), "--manifest"]) == 0
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert [item["filename"] for item in manifest["outputs"]] == ["001-first.pdf", "002-second.pdf"]
    for filename, count, first_text in [
        ("001-first.pdf", 2, "Source page 2"),
        ("002-second.pdf", 3, "Source page 4"),
    ]:
        with pymupdf.open(destination / filename) as result:
            assert result.page_count == count
            assert first_text in result[0].get_text()


def test_nested_levels_and_frontmatter(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "Part", 2], [2, "A", 3], [2, "B", 5]])
    destination = tmp_path / "out"
    assert main(["split", str(source), "--level", "2", "--output-dir", str(destination),
                 "--include-frontmatter", "--manifest"]) == 0
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert [(o["start_page"], o["end_page"]) for o in manifest["outputs"]] == [(1, 2), (3, 4), (5, 6)]
    assert (destination / "000-frontmatter.pdf").exists()
    with pymupdf.open(destination / "000-frontmatter.pdf") as frontmatter:
        assert frontmatter.page_count == 2


def test_parent_without_destination_uses_descendant_pages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_pdf(
        tmp_path / "book.pdf",
        [
            [1, "Book", 1],
            [1, "Overview", -1],
            [2, "What is it?", 2],
            [2, "Details", 4],
            [1, "Get started", -1],
            [2, "First steps", 5],
        ],
    )
    assert main(["inspect", str(source), "--json"]) == 0
    inspection = json.loads(capsys.readouterr().out)
    assert [(c["title"], c["start_page"], c["end_page"]) for c in inspection["chapters"]] == [
        ("Book", 1, 1), ("Overview", 2, 4), ("Get started", 5, 6)
    ]
    assert any("earliest descendant page 2" in warning for warning in inspection["warnings"])
    destination = tmp_path / "out"
    assert main(["split", str(source), "--output-dir", str(destination)]) == 0
    with pymupdf.open(destination / "002-overview.pdf") as overview:
        assert overview.page_count == 3
        assert "Source page 2" in overview[0].get_text()
        assert "Source page 4" in overview[-1].get_text()


def test_page_window_filters_bookmarks_and_clips_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = make_pdf(
        tmp_path / "book.pdf",
        [[1, "Before", 1], [1, "Inside", 3], [1, "Last", 5]],
        pages=8,
    )
    window = ["--start-page", "2", "--end-page", "6"]
    assert main(["inspect", str(source), *window, "--json"]) == 0
    inspection = json.loads(capsys.readouterr().out)
    assert inspection["selected_start_page"] == 2
    assert inspection["selected_end_page"] == 6
    assert inspection["excluded_leading_pages"] == 1
    assert [(c["title"], c["start_page"], c["end_page"]) for c in inspection["chapters"]] == [
        ("Inside", 3, 4), ("Last", 5, 6)
    ]
    destination = tmp_path / "out"
    assert main([
        "split", str(source), "--output-dir", str(destination), *window,
        "--include-frontmatter", "--manifest"
    ]) == 0
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert [(o["start_page"], o["end_page"]) for o in manifest["outputs"]] == [
        (2, 2), (3, 4), (5, 6)
    ]
    assert manifest["selected_start_page"] == 2
    assert manifest["selected_end_page"] == 6
    with pymupdf.open(destination / "002-last.pdf") as last:
        assert last.page_count == 2
        assert "Source page 6" in last[-1].get_text()
    assert not (destination / "001-before.pdf").exists()


def test_page_window_validation_and_empty_selection(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "First", 2], [1, "Second", 5]])
    destination = tmp_path / "out"
    for start, end in [(5, 4), (1, 7), (7, 7)]:
        assert main([
            "split", str(source), "--output-dir", str(destination),
            "--start-page", str(start), "--end-page", str(end)
        ]) == 2
        assert not destination.exists()
    assert main([
        "split", str(source), "--output-dir", str(destination),
        "--start-page", "3", "--end-page", "4"
    ]) == 5
    assert not destination.exists()
    assert main([
        "split", str(source), "--output-dir", str(destination),
        "--start-page", "5"
    ]) == 0
    with pymupdf.open(destination / "001-second.pdf") as result:
        assert result.page_count == 2


def test_duplicate_and_out_of_order_bookmarks() -> None:
    chapters, warnings = derive_chapters(
        [[1, "Later", 5], [1, "Earlier", 2], [1, "Ignored", 2], [1, "Bad", -1]], 6, 1
    )
    assert [(c.title, c.start_page, c.end_page) for c in chapters] == [
        ("Earlier", 2, 4), ("Later", 5, 6)
    ]
    assert any("out of order" in warning for warning in warnings)
    assert any("duplicate" in warning for warning in warnings)
    assert any("invalid destination" in warning for warning in warnings)
    titled, _ = derive_chapters([[1, "", 2], [1, "Usable", 2]], 3, 1)
    assert titled[0].title == "Usable"


def test_missing_outline_level_and_source_errors(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "One", 1]])
    assert main(["inspect", str(source), "--level", "2"]) == 5
    assert main(["inspect", str(tmp_path / "absent.pdf")]) == 3
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"not a pdf")
    assert main(["inspect", str(corrupt)]) == 3
    empty_outline = make_pdf(tmp_path / "empty.pdf")
    assert main(["split", str(empty_outline), "--output-dir", str(tmp_path / "missing-out")]) == 5
    assert not (tmp_path / "missing-out").exists()


def test_invalid_level_returns_argparse_exit(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "One", 1]])
    with pytest.raises(SystemExit) as error:
        main(["inspect", str(source), "--level", "0"])
    assert error.value.code == 2


def test_encrypted_pdf(tmp_path: Path) -> None:
    source = tmp_path / "encrypted.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.set_toc([[1, "Secret", 1]])
        document.save(source, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    assert main(["inspect", str(source)]) == 4
    assert main(["inspect", str(source), "--password", "wrong"]) == 4
    assert main(["inspect", str(source), "--password", "secret"]) == 0


def test_collision_dry_run_and_overwrite(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "One", 1]])
    destination = tmp_path / "out"
    assert main(["split", str(source), "--output-dir", str(destination), "--dry-run"]) == 0
    assert not destination.exists()
    destination.mkdir()
    original = destination / "001-one.pdf"
    original.write_bytes(b"existing")
    assert main(["split", str(source), "--output-dir", str(destination), "--manifest"]) == 6
    assert original.read_bytes() == b"existing"
    assert not (destination / "manifest.json").exists()
    assert main(["split", str(source), "--output-dir", str(destination), "--overwrite"]) == 0
    with pymupdf.open(original) as result:
        assert result.page_count == 6


def test_source_cannot_be_replaced_by_output(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "001-one.pdf", [[1, "One", 1]])
    assert main(["split", str(source), "--output-dir", str(tmp_path), "--overwrite"]) == 6
    with pymupdf.open(source) as result:
        assert result.page_count == 6


def test_unsafe_and_unicode_titles(tmp_path: Path) -> None:
    assert slugify("../../\\CON: ♥") == "con"
    assert slugify("日本語") == "untitled"
    source = make_pdf(tmp_path / "book.pdf", [[1, "../../outside", 1], [1, "日本語", 3]])
    destination = tmp_path / "out"
    assert main(["split", str(source), "--output-dir", str(destination)]) == 0
    assert sorted(path.name for path in destination.iterdir()) == ["001-outside.pdf", "002-untitled.pdf"]
    assert not (tmp_path / "outside.pdf").exists()


def test_failed_extraction_leaves_no_manifest_or_temps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "One", 1], [1, "Two", 3]])
    destination = tmp_path / "out"
    original = pymupdf.Document.insert_pdf
    calls = 0

    def fail_second(self: pymupdf.Document, *args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected extraction failure")
        original(self, *args, **kwargs)

    monkeypatch.setattr(pymupdf.Document, "insert_pdf", fail_second)
    assert main(["split", str(source), "--output-dir", str(destination), "--manifest"]) == 7
    assert list(destination.iterdir()) == []


def test_failed_publish_restores_previous_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = make_pdf(tmp_path / "book.pdf", [[1, "One", 1], [1, "Two", 3]])
    destination = tmp_path / "out"
    destination.mkdir()
    first = destination / "001-one.pdf"
    first.write_bytes(b"old one")
    original_replace = __import__("os").replace
    publishes = 0

    def fail_publish(src: Path, dst: Path) -> None:
        nonlocal publishes
        if str(src).endswith(".tmp") and str(dst).endswith(".pdf"):
            publishes += 1
            if publishes == 2:
                raise OSError("injected publish failure")
        original_replace(src, dst)

    monkeypatch.setattr("pdf_chapters.splitter.os.replace", fail_publish)
    assert main(["split", str(source), "--output-dir", str(destination), "--overwrite", "--manifest"]) == 7
    assert first.read_bytes() == b"old one"
    assert sorted(path.name for path in destination.iterdir()) == ["001-one.pdf"]
