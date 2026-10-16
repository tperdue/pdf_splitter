"""Bridge Streamlit actions to the existing CLI command handler."""

import io
import json
import shutil
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import BinaryIO

from .cli import build_parser, run


def invoke_cli(arguments: list[str], source_label: str | None = None) -> tuple[int, str, str]:
    """Run a console command and capture its report for the UI."""
    output = io.StringIO()
    errors = io.StringIO()
    with redirect_stdout(output), redirect_stderr(errors):
        code = run(build_parser().parse_args(arguments), source_label=source_label)
    return code, output.getvalue(), errors.getvalue().strip()


def perform_action(
    action: str,
    source_path: str,
    uploaded_file: BinaryIO | None,
    uploaded_name: str | None,
    level: int,
    start_page: int,
    end_page: int | None,
    password: str,
    output_dir: str,
    include_frontmatter: bool,
    manifest: bool,
    overwrite: bool,
    verbose: bool,
) -> dict[str, object]:
    """Inspect first, then optionally dry-run or split while an upload is staged."""
    with tempfile.TemporaryDirectory(prefix="pdf-chapters-ui-") as temporary_dir:
        label = None
        if uploaded_file is not None:
            label = Path(uploaded_name or "uploaded.pdf").name
            staged_source = Path(temporary_dir) / "source.pdf"
            uploaded_file.seek(0)
            with staged_source.open("wb") as destination:
                shutil.copyfileobj(uploaded_file, destination)
            source = str(staged_source)
        else:
            source = source_path.strip()
        shared = [source, "--level", str(level), "--start-page", str(start_page)]
        if end_page is not None:
            shared += ["--end-page", str(end_page)]
        if password:
            shared += ["--password", password]
        if verbose:
            shared.append("--verbose")
        code, report, error = invoke_cli(["inspect", *shared, "--json"], label)
        if code:
            return {"code": code, "error": error, "action": action}
        inspection = json.loads(report)
        if action == "inspect":
            return {"code": 0, "inspection": inspection, "action": action}
        split_args = ["split", *shared, "--output-dir", output_dir.strip()]
        if include_frontmatter:
            split_args.append("--include-frontmatter")
        if manifest:
            split_args.append("--manifest")
        if overwrite:
            split_args.append("--overwrite")
        if action == "dry_run":
            split_args.append("--dry-run")
        code, message, error = invoke_cli(split_args, label)
        return {
            "code": code,
            "inspection": inspection,
            "message": message.strip(),
            "error": error,
            "action": action,
            "output_dir": str(Path(output_dir).resolve()),
            "include_frontmatter": include_frontmatter,
        }
