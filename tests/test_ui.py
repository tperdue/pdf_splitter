"""UI action tests use generated PDFs and Streamlit's headless runner."""

import io
import json
from pathlib import Path

import pymupdf
import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from pdf_chapters.ui_actions import perform_action


def make_pdf(path: Path) -> Path:
    with pymupdf.open() as document:
        for number in range(1, 5):
            document.new_page().insert_text((72, 72), f"Page {number}")
        document.set_toc([[1, "Overview", 1], [1, "Procedures", 3]])
        document.save(path)
    return path


def test_uploaded_pdf_runs_split_and_keeps_original_name(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "upload.pdf")
    destination = tmp_path / "chapters"
    result = perform_action(
        "split", "", io.BytesIO(source.read_bytes()), "upload.pdf", 1, 1, 3,
        "", str(destination), False, True, False, False,
    )
    assert result["code"] == 0
    assert result["inspection"]["source_file"] == "upload.pdf"
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_file"] == "upload.pdf"
    assert [(item["start_page"], item["end_page"]) for item in manifest["outputs"]] == [
        (1, 2), (3, 3)
    ]


def test_ui_inspects_selected_window(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "book.pdf")
    app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()
    assert not app.exception
    app.text_input("source_path").set_value(str(source))
    app.number_input("start_page").set_value(3)
    app.text_input("end_page").set_value("3")
    app.form_submit_button("inspect").click().run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 1
    assert app.dataframe[0].value.iloc[0]["Section"] == "Procedures"
    assert app.metric[2].value == "3–3"
    destination = tmp_path / "ui-output"
    app.text_input("output_dir").set_value(str(destination))
    app.form_submit_button("dry_run").click().run()
    assert not app.exception
    assert not destination.exists()
    assert "Dry run complete" in app.info[0].value
    app.checkbox("manifest").check()
    app.form_submit_button("split").click().run()
    assert not app.exception
    assert (destination / "001-procedures.pdf").exists()
    assert (destination / "manifest.json").exists()
