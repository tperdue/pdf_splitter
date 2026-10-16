# PDF Chapters

Split a PDF into separate files using its embedded bookmarks. The project includes a command-line tool (`pdf-chapters`) and a local Streamlit interface (Chapter Studio). PyMuPDF copies the original PDF pages without rendering them as images.

## Requirements

- Python 3.11 or newer
- A PDF with embedded outline bookmarks that point to pages, or parent bookmarks with descendants that do
- No server account, database, or external processing service

## Run the interface

From the project directory, install the UI dependencies and start Streamlit:

```bash
python -m pip install -e ".[ui]"
python -m streamlit run streamlit_app.py
```

Open the local address printed in the terminal (normally `http://localhost:8501`). On Windows, if `python` is not on your path, use `py -3` in the commands above.

1. Select **Local path** to enter a PDF path on the computer running Streamlit, or **Upload PDF** to choose a file in your browser. Uploaded PDFs are staged temporarily and removed after the operation.
2. Set the bookmark level and optional start and end pages. Leave **End page** blank to use the final PDF page. Enter a password if the PDF is encrypted.
3. Select **Inspect bookmarks** to see the proposed section ranges and download the inspection JSON. **Dry run** shows the planned filenames without writing files. **Split PDF** writes the chapter PDFs.
4. For exports, set **Output folder** to a local path on the computer running Streamlit. Choose whether to include leading pages, write `manifest.json`, replace existing files, or show verbose diagnostics.

The interface uses the same splitting engine and rules as the CLI. The output folder is a server-side filesystem path; the browser download button is for the inspection report.

## Use the CLI

Install the core package:

```bash
python -m pip install -e .
```

Inspect before exporting, or run `split` directly:

```bash
pdf-chapters inspect book.pdf
pdf-chapters inspect book.pdf --level 2 --json
pdf-chapters inspect book.pdf --start-page 100 --end-page 300
pdf-chapters split book.pdf --output-dir chapters --dry-run
pdf-chapters split book.pdf --output-dir chapters --manifest
pdf-chapters split book.pdf --output-dir chapters --start-page 100 --end-page 300
pdf-chapters split book.pdf --output-dir chapters --include-frontmatter --overwrite
pdf-chapters split protected.pdf --output-dir chapters --password YOUR_PASSWORD
```

| Option | Commands | Effect |
|---|---|---|
| `--level N` | Both | Use bookmarks at nesting level `N` (default `1`). |
| `--start-page N`, `--end-page N` | Both | Select an inclusive page window. Defaults to the whole PDF. |
| `--password VALUE` | Both | Open an encrypted PDF. Passwords are not written to reports or manifests. |
| `--verbose` | Both | Show diagnostics on stderr. |
| `--json` | Inspect | Print the inspection report as JSON. |
| `--output-dir PATH` | Split | Required destination for chapter PDFs. |
| `--dry-run` | Split | Show ranges and filenames without creating output files. |
| `--include-frontmatter` | Split | Export pages before the first selected bookmark within the chosen window. |
| `--manifest` | Split | Write `manifest.json` after all PDFs succeed. |
| `--overwrite` | Split | Replace files that have the same planned output names. |

## How ranges are chosen

Each bookmark at the selected level starts a section. A section ends just before the next distinct selected bookmark page; the last one ends at the final page or the requested end page. Page numbers shown in the UI, CLI, and JSON are **1-based and inclusive**. Only bookmarks whose starts fall inside the selected page window are exported. A section that started before `--start-page` is excluded.

Some PDFs use parent bookmarks as headings with no page destination (`-1`). In that case, the first valid page among the parent's descendants becomes its start, and the exported file keeps the parent title. A bookmark with no usable destination beneath it is skipped with a warning. Duplicate starts are collapsed; out-of-order bookmarks are sorted by page.

Filenames are ordered and based on safe bookmark-title slugs, for example `001-overview.pdf`. Leading pages are excluded unless `--include-frontmatter` is selected. Existing output files are protected unless `--overwrite` is selected. Files are staged before publication so a failed operation does not report success or leave a partial manifest.

The tool reads embedded PDF bookmarks only. It does not infer chapters from text, scanned pages, or a printed table of contents. Split PDFs do not retain the source's global outline or every cross-document link.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Invalid arguments, bookmark level, or page window |
| `3` | Missing, unreadable, or invalid source PDF |
| `4` | Password required or incorrect |
| `5` | No usable bookmarks at the selected level or within the page window |
| `6` | Destination collision or unwritable destination |
| `7` | Processing or output write failure |

## Develop and test

```bash
python -m pip install -e ".[test,ui]"
python -m pytest
```

Tests create miniature PDFs at runtime and use Streamlit's headless UI runner. They require no external services. For CLI tests only, install `.[test]`; the UI tests are skipped if Streamlit is not installed.
