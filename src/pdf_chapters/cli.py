"""Command-line interface and documented exit codes."""

import argparse
import json
import logging
import sys
from pathlib import Path

import pymupdf

from .filenames import chapter_filenames
from .outline import NoUsableBookmarksError, derive_chapters, select_page_window
from .splitter import Output, write_outputs

LOGGER = logging.getLogger("pdf_chapters")


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf-chapters", description="Split PDFs using embedded bookmarks.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "split"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path, help="Input PDF")
        command.add_argument("--level", type=positive_int, default=1, metavar="N")
        command.add_argument("--start-page", type=positive_int, default=1, metavar="N")
        command.add_argument("--end-page", type=positive_int, metavar="N")
        command.add_argument("--password", help="Password for an encrypted PDF")
        command.add_argument("--verbose", action="store_true")
        if name == "inspect":
            command.add_argument("--json", action="store_true", help="Print JSON to stdout")
        else:
            command.add_argument("--output-dir", type=Path, required=True)
            command.add_argument("--dry-run", action="store_true")
            command.add_argument("--manifest", action="store_true")
            command.add_argument("--include-frontmatter", action="store_true")
            command.add_argument("--overwrite", action="store_true")
    return parser


def _error(message: str, code: int) -> int:
    print(f"pdf-chapters: {message}", file=sys.stderr)
    return code


def _open_source(path: Path, password: str | None) -> tuple[pymupdf.Document | None, int]:
    if not path.is_file():
        return None, _error("source PDF is missing or is not a file", 3)
    try:
        document = pymupdf.open(path)
    except (OSError, RuntimeError, ValueError) as exc:
        LOGGER.debug("Could not open source PDF: %s", type(exc).__name__)
        return None, _error("source file is unreadable or is not a valid PDF", 3)
    if document.needs_pass:
        if not password or not document.authenticate(password):
            document.close()
            return None, _error("PDF password is required or incorrect", 4)
    return document, 0


def _print_ranges(
    outputs: list[Output], level: int, start_page: int, end_page: int, warnings: list[str]
) -> None:
    print(f"Bookmark level: {level}")
    print(f"Page range: {start_page}-{end_page}")
    for output in outputs:
        print(
            f"{output.index:03d}  pages {output.start_page}-{output.end_page} "
            f"({output.end_page - output.start_page + 1})  {output.title}  -> {output.filename}"
        )
    for warning in warnings:
        print(f"Warning: {warning}")


def run(args: argparse.Namespace, source_label: str | None = None) -> int:
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, stream=sys.stderr)
    source, error_code = _open_source(args.source, args.password)
    if source is None:
        return error_code
    with source:
        window_end = args.end_page if args.end_page is not None else source.page_count
        if args.start_page > window_end or window_end > source.page_count:
            return _error(
                f"page range must be within 1-{source.page_count} and start at or before end", 2
            )
        try:
            chapters, warnings = derive_chapters(source.get_toc(), source.page_count, args.level)
        except NoUsableBookmarksError as exc:
            return _error(str(exc), 5)
        except (RuntimeError, ValueError) as exc:
            LOGGER.debug("Outline processing failed: %s", type(exc).__name__)
            return _error("could not process PDF outline", 7)
        chapters = select_page_window(chapters, args.start_page, window_end)
        if not chapters:
            return _error(
                f"No usable bookmarks at level {args.level} starting within pages "
                f"{args.start_page}-{window_end}.", 5
            )
        for warning in warnings:
            LOGGER.warning("%s", warning)
        source_file = source_label or str(args.source.resolve())
        if args.command == "inspect":
            if args.json:
                payload = {
                    "source_file": source_file,
                    "page_count": source.page_count,
                    "bookmark_level": args.level,
                    "selected_start_page": args.start_page,
                    "selected_end_page": window_end,
                    "chapters": [chapter.as_dict() for chapter in chapters],
                    "excluded_leading_pages": chapters[0].start_page - args.start_page,
                    "warnings": warnings,
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                filenames = chapter_filenames(chapters)
                outputs = [Output(c.title, c.start_page, c.end_page, filename, c.index)
                           for c, filename in zip(chapters, filenames)]
                _print_ranges(outputs, args.level, args.start_page, window_end, warnings)
                if chapters[0].start_page > args.start_page:
                    print(f"Excluded leading pages in range: {chapters[0].start_page - args.start_page}")
            return 0

        filenames = chapter_filenames(chapters)
        outputs = [Output(c.title, c.start_page, c.end_page, filename, c.index)
                   for c, filename in zip(chapters, filenames)]
        if args.include_frontmatter and chapters[0].start_page > args.start_page:
            outputs.insert(0, Output(
                "Frontmatter", args.start_page, chapters[0].start_page - 1, "000-frontmatter.pdf", 0
            ))
        if args.dry_run:
            _print_ranges(outputs, args.level, args.start_page, window_end, warnings)
            return 0
        source_path = args.source.resolve()
        planned_names = [output.filename for output in outputs]
        if args.manifest:
            planned_names.append("manifest.json")
        if any((args.output_dir / name).resolve() == source_path for name in planned_names):
            return _error("source PDF cannot also be an output file", 6)
        manifest_bytes = None
        if args.manifest:
            manifest = {
                "schema_version": "1.0",
                "source_file": source_file,
                "source_page_count": source.page_count,
                "bookmark_level": args.level,
                "selected_start_page": args.start_page,
                "selected_end_page": window_end,
                "include_frontmatter": args.include_frontmatter,
                "outputs": [output.as_dict() for output in outputs],
                "warnings": warnings,
            }
            manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        try:
            write_outputs(source, args.output_dir, outputs, manifest_bytes, args.overwrite)
        except FileExistsError as exc:
            return _error(str(exc), 6)
        except (PermissionError, NotADirectoryError, IsADirectoryError) as exc:
            LOGGER.debug("Destination error: %s", type(exc).__name__)
            return _error("destination is not writable", 6)
        except OSError as exc:
            LOGGER.debug("Output error: %s", type(exc).__name__)
            return _error("failed to write output files", 7)
        except Exception as exc:
            LOGGER.debug("Extraction error: %s", type(exc).__name__)
            return _error("failed to process PDF pages", 7)
        print(f"Wrote {len(outputs)} PDF file(s) to {args.output_dir}")
        return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
