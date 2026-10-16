"""Stage extracted PDFs and commit them with rollback on write failure."""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class Output:
    title: str
    start_page: int
    end_page: int
    filename: str
    index: int

    def as_dict(self) -> dict[str, int | str]:
        return {
            "index": self.index,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "page_count": self.end_page - self.start_page + 1,
            "filename": self.filename,
        }


def _temp_path(directory: Path) -> Path:
    descriptor, name = tempfile.mkstemp(prefix=".pdf-chapters-", suffix=".tmp", dir=directory)
    os.close(descriptor)
    return Path(name)


def write_outputs(
    source: pymupdf.Document,
    output_dir: Path,
    outputs: list[Output],
    manifest_bytes: bytes | None,
    overwrite: bool,
) -> None:
    """Stage all files before publishing; restore existing files on commit failure."""
    targets = [output_dir / output.filename for output in outputs]
    if manifest_bytes is not None:
        targets.append(output_dir / "manifest.json")
    if not overwrite and any(target.exists() for target in targets):
        raise FileExistsError("One or more output files already exist; use --overwrite to replace them.")
    output_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for output in outputs:
            temporary = _temp_path(output_dir)
            staged.append(temporary)
            with pymupdf.open() as chapter_pdf:
                chapter_pdf.insert_pdf(source, from_page=output.start_page - 1, to_page=output.end_page - 1)
                chapter_pdf.save(temporary)
        if manifest_bytes is not None:
            temporary = _temp_path(output_dir)
            staged.append(temporary)
            temporary.write_bytes(manifest_bytes)
        # Move old targets aside so a failed publish can restore them.
        for target in targets:
            if target.exists():
                if not overwrite:
                    raise FileExistsError(f"Output already exists: {target}")
                backup = _temp_path(output_dir)
                os.replace(target, backup)
                backups[target] = backup
        for temporary, target in zip(staged, targets):
            os.replace(temporary, target)
            published.append(target)
    except Exception:
        for target in published:
            target.unlink(missing_ok=True)
        for target, backup in backups.items():
            os.replace(backup, target)
        raise
    finally:
        for temporary in staged:
            temporary.unlink(missing_ok=True)
        # A failed restore must leave its backup available for manual recovery.
        for target, backup in backups.items():
            if target.exists():
                backup.unlink(missing_ok=True)
