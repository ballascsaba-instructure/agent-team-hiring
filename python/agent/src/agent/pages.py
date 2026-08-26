"""File-backed storage for pages, saved as markdown files with frontmatter under ``_data/``."""

import os
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from .seed import seed_examples


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    published: bool
    updated_at: str
    body: str


#: Where the page files live. ``PAGE_DATA_DIR`` overrides it; the default sits
#: next to pyproject.toml so it is the same directory whatever the cwd is.
DATA_DIR = Path(
    os.environ.get("PAGE_DATA_DIR") or Path(__file__).resolve().parents[2] / "_data"
)

_FENCE = "---"


def _serialise(page: Page) -> str:
    """Render a page as frontmatter plus body. The url is not written — it is
    the file name."""
    published = "true" if page.published else "false"
    return "\n".join(
        [
            _FENCE,
            f"title: {page.title}",
            f"published: {published}",
            f"updated_at: {page.updated_at}",
            _FENCE,
            "",
            page.body.strip("\n"),
            "",
        ]
    )


def _deserialise(path: Path) -> Page:
    """Read one page file.

    The frontmatter parser is deliberately tiny — ``key: value`` lines, no YAML.
    A file with no readable frontmatter still loads: it becomes an unpublished
    page titled after its file name, rather than an error the agent cannot act
    on.
    """
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text

    if text.startswith(f"{_FENCE}\n"):
        header, fence, rest = text[len(_FENCE) + 1 :].partition(f"\n{_FENCE}\n")
        if fence:
            body = rest
            for line in header.splitlines():
                key, sep, value = line.partition(":")
                if sep:
                    meta[key.strip()] = value.strip()

    return Page(
        url=path.stem,
        title=meta.get("title") or path.stem,
        published=meta.get("published", "").lower() == "true",
        updated_at=meta.get("updated_at", ""),
        body=body.strip("\n"),
    )


def _page_path(page_url: str) -> Path:
    """The file a page url maps to.

    ``Path(...).name`` drops any directory part, so a url like ``../secrets``
    cannot write outside ``_data/``.
    """
    name = Path(page_url.strip()).name
    if not name or name.startswith("."):
        raise ValueError(f"Not a usable page url: {page_url!r}")
    return DATA_DIR / f"{name}.md"


def _write(page: Page) -> None:
    _page_path(page.url).write_text(_serialise(page), encoding="utf-8")


def ensure_data_dir() -> Path:
    """Create ``_data/`` and seed the example pages if it is not there yet.

    Idempotent, and called by every read and write below as well as at startup,
    so no caller has to remember to set the storage up first.
    """
    if DATA_DIR.is_dir():
        return DATA_DIR

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    seed_examples(DATA_DIR)
    return DATA_DIR


def _load_all() -> list[Page]:
    """Every page on disk, ordered by url so listings are stable."""
    ensure_data_dir()
    return [_deserialise(path) for path in sorted(DATA_DIR.glob("*.md"))]


def list_pages() -> list[dict[str, Any]]:
    """Every page, without the body."""
    return [
        {k: v for k, v in asdict(page).items() if k != "body"} for page in _load_all()
    ]


def find_page(page_url: str) -> Page | None:
    """A single page with its full body, or None if nothing matches.

    Accepts the page url or its title, case-insensitively.
    """
    needle = page_url.strip().lower()
    for page in _load_all():
        if page.url.lower() == needle or page.title.lower() == needle:
            return page
    return None


def update_page(
    page_url: str,
    *,
    title: str | None = None,
    body: str | None = None,
    published: bool | None = None,
) -> Page | None:
    """Write changed fields back to the page's file and return the new page.

    Returns None if no page matches. Fields left as None keep their current
    value, and ``updated_at`` is stamped with today's date on every write. The
    url never changes, even when the title does — it is the file name, and
    renaming files would break links the agent may already have handed out.
    """
    page = find_page(page_url)
    if page is None:
        return None

    updated = replace(
        page,
        title=page.title if title is None else title,
        body=page.body if body is None else body,
        published=page.published if published is None else published,
        updated_at=date.today().isoformat(),
    )
    _write(updated)
    return updated
