"""Local Streamlit workspace for inspecting and splitting bookmarked PDFs."""

import json

import streamlit as st

from pdf_chapters.filenames import slugify
from pdf_chapters.ui_actions import perform_action


st.set_page_config(
    page_title="Chapter Studio",
    page_icon=":material/auto_stories:",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.session_state.setdefault("result", None)

with st.sidebar:
    st.markdown("### :material/auto_stories: Chapter Studio")
    st.caption("LOCAL DOCUMENT OPERATIONS")
    st.space("medium")
    st.markdown("**Workflow**")
    st.markdown("1. Choose a PDF and bookmark level")
    st.markdown("2. Inspect the planned page ranges")
    st.markdown("3. Export chapter files")
    st.space("medium")
    st.caption("PDF content stays on this machine. Output files are written to a local folder.")

st.caption("PDF OPERATIONS / BOOKMARK SPLITTING")
st.title("Split a PDF by its bookmarks")
st.markdown("Choose a document, review its chapter boundaries, then export the pages you need.")
source_mode = st.segmented_control(
    "Choose source", ["Local path", "Upload PDF"], default="Local path", required=True,
    key="source_mode",
)

with st.form("chapter_options", border=True):
    st.subheader("Source document", anchor=False)
    if source_mode == "Upload PDF":
        uploaded = st.file_uploader("PDF file", type=["pdf"], max_upload_size=1024, key="uploaded_pdf")
        source_path = ""
    else:
        source_path = st.text_input(
            "PDF path", placeholder=r"C:\documents\book.pdf",
            help="Path on the computer running Streamlit.", key="source_path",
        )
        uploaded = None
    password = st.text_input(
        "PDF password", type="password", help="Used only to open this PDF.", key="pdf_password"
    )

    st.subheader("Chapter boundaries", anchor=False)
    level_col, start_col, end_col = st.columns(3)
    with level_col:
        level = st.number_input("Bookmark level", min_value=1, value=1, step=1, key="bookmark_level")
    with start_col:
        start_page = st.number_input("Start page", min_value=1, value=1, step=1, key="start_page")
    with end_col:
        end_page_text = st.text_input(
            "End page", placeholder="Last page", help="Leave blank for the last page.", key="end_page"
        )

    st.subheader("Export", anchor=False)
    output_dir = st.text_input(
        "Output folder", value="chapters", help="Path on the computer running Streamlit.", key="output_dir"
    )
    option_cols = st.columns(3)
    with option_cols[0]:
        include_frontmatter = st.checkbox("Include leading pages", key="include_frontmatter")
        manifest = st.checkbox("Write JSON manifest", key="manifest")
    with option_cols[1]:
        overwrite = st.checkbox("Replace existing files", key="overwrite")
        verbose = st.checkbox("Verbose diagnostics", key="verbose")
    st.caption("Exports use the selected bookmark level. Sections are clipped at the end page.")
    inspect_col, preview_col, split_col = st.columns(3)
    with inspect_col:
        inspect_clicked = st.form_submit_button(
            "Inspect bookmarks", icon=":material/visibility:", width="stretch", key="inspect"
        )
    with preview_col:
        preview_clicked = st.form_submit_button(
            "Dry run", icon=":material/playlist_add_check:", width="stretch", key="dry_run"
        )
    with split_col:
        split_clicked = st.form_submit_button(
            "Split PDF", icon=":material/content_cut:", type="primary", width="stretch", key="split"
        )

if inspect_clicked or preview_clicked or split_clicked:
    if uploaded is None and not source_path.strip():
        st.session_state.result = {"code": 2, "error": "Choose a PDF file or enter its path."}
    elif not output_dir.strip() and (preview_clicked or split_clicked):
        st.session_state.result = {"code": 2, "error": "Enter an output folder."}
    else:
        try:
            end_page = int(end_page_text) if end_page_text.strip() else None
        except ValueError:
            st.session_state.result = {"code": 2, "error": "End page must be a positive whole number."}
        else:
            if end_page is not None and end_page < 1:
                st.session_state.result = {"code": 2, "error": "End page must be a positive whole number."}
            else:
                action = "inspect" if inspect_clicked else "dry_run" if preview_clicked else "split"
                with st.spinner("Reading bookmarks and page ranges…"):
                    st.session_state.result = perform_action(
                        action, source_path, uploaded, uploaded.name if uploaded else None,
                        int(level), int(start_page), end_page, password, output_dir,
                        include_frontmatter, manifest, overwrite, verbose,
                    )

result = st.session_state.result
if result is None:
    st.info("Start by inspecting a PDF. The chapter plan will appear here.", icon=":material/info:")
elif result["code"]:
    st.error(str(result.get("error") or "The operation failed."), title="Could not process PDF")
else:
    inspection = result["inspection"]
    chapters = inspection["chapters"]
    st.subheader("Chapter plan", anchor=False)
    metrics = st.columns(3)
    metrics[0].metric("Source pages", inspection["page_count"])
    metrics[1].metric("Sections selected", len(chapters))
    metrics[2].metric("Selected window", f"{inspection['selected_start_page']}–{inspection['selected_end_page']}")
    rows = [
        {
            "#": chapter["index"],
            "Section": chapter["title"],
            "Start": chapter["start_page"],
            "End": chapter["end_page"],
            "Pages": chapter["page_count"],
            "PDF file": f"{chapter['index']:03d}-{slugify(chapter['title'])}.pdf",
        }
        for chapter in chapters
    ]
    st.dataframe(rows, hide_index=True, width="stretch", alt="Selected bookmark sections and page ranges")
    warnings = inspection.get("warnings", [])
    if warnings:
        with st.expander(f"Outline notes ({len(warnings)})"):
            for warning in warnings:
                st.warning(warning, icon=":material/warning:")
    if result["action"] == "dry_run":
        st.info("Dry run complete. No files were written.", icon=":material/visibility:")
        st.code(str(result["message"]), language="text")
    elif result["action"] == "split":
        st.success(str(result["message"]), title="Export complete", icon=":material/check_circle:")
        st.caption(f"Output folder: {result['output_dir']}")
    report = json.dumps(inspection, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button(
        "Download inspection JSON", report, file_name="chapter-inspection.json",
        mime="application/json", icon=":material/download:", width="content",
    )
