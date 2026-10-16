"""Convert PDF outline entries into inclusive, one-based page ranges."""

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    start_page: int
    end_page: int

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1

    def as_dict(self) -> dict[str, int | str]:
        return {
            "index": self.index,
            "title": self.title,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "page_count": self.page_count,
        }


class NoUsableBookmarksError(Exception):
    """The chosen outline level has no valid page destinations."""


def derive_chapters(
    toc: Sequence[Sequence[object]], page_count: int, level: int
) -> tuple[list[Chapter], list[str]]:
    """Select a level, using descendants when a parent has no destination."""
    if level < 1:
        raise ValueError("bookmark level must be at least 1")
    warnings: list[str] = []
    selected: list[tuple[int, str]] = []
    for position, entry in enumerate(toc):
        if len(entry) < 3 or entry[0] != level:
            continue
        title = str(entry[1]).strip()
        page = entry[2]
        if isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= page_count:
            descendant_pages: list[int] = []
            for descendant in toc[position + 1:]:
                if not descendant or not isinstance(descendant[0], int) or descendant[0] <= level:
                    break
                if len(descendant) >= 3:
                    descendant_page = descendant[2]
                    if isinstance(descendant_page, int) and not isinstance(descendant_page, bool):
                        if 1 <= descendant_page <= page_count:
                            descendant_pages.append(descendant_page)
            if not descendant_pages:
                warnings.append(
                    f"Skipped bookmark {title!r}: invalid destination page {page!r} "
                    "and no valid descendant destination."
                )
                continue
            page = min(descendant_pages)
            warnings.append(
                f"Bookmark {title!r} has invalid destination page {entry[2]!r}; "
                f"using earliest descendant page {page}."
            )
        selected.append((page, title))
    if not selected:
        raise NoUsableBookmarksError(f"No usable bookmarks at level {level}.")
    if any(left[0] > right[0] for left, right in zip(selected, selected[1:])):
        warnings.append("Bookmark destinations are out of order; sections are sorted by page.")
    starts: dict[int, str] = {}
    for page, title in selected:
        if page in starts:
            if not starts[page] and title:
                discarded = starts[page]
                starts[page] = title
            else:
                discarded = title
            warnings.append(f"Discarded duplicate bookmark {discarded!r} at page {page}.")
        else:
            starts[page] = title
    pages = sorted(starts)
    chapters = [
        Chapter(i + 1, starts[start], start, pages[i + 1] - 1 if i + 1 < len(pages) else page_count)
        for i, start in enumerate(pages)
    ]
    if any(chapter.page_count < 1 or chapter.end_page > page_count for chapter in chapters):
        raise ValueError("Invalid chapter range derived from PDF outline")
    return chapters, warnings


def select_page_window(chapters: list[Chapter], start_page: int, end_page: int) -> list[Chapter]:
    """Keep bookmarks starting in the inclusive window and clip their ranges."""
    selected = [
        Chapter(0, chapter.title, chapter.start_page, min(chapter.end_page, end_page))
        for chapter in chapters
        if start_page <= chapter.start_page <= end_page
    ]
    return [
        Chapter(index, chapter.title, chapter.start_page, chapter.end_page)
        for index, chapter in enumerate(selected, start=1)
    ]
