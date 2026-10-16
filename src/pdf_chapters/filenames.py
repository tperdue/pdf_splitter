"""Safe and deterministic names for files derived from untrusted titles."""

import re
import unicodedata

from .outline import Chapter


def slugify(title: str, max_length: int = 72) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug[:max_length].rstrip("-") or "untitled"


def chapter_filenames(chapters: list[Chapter]) -> list[str]:
    width = max(3, len(str(len(chapters))))
    return [f"{chapter.index:0{width}d}-{slugify(chapter.title)}.pdf" for chapter in chapters]
