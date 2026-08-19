"""In-memory stand-in for a course pages API.

The agent is a demo, so this module is the whole "backend": one course with
three fixed pages that never change, even when the update tool is called.
"""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Course:
    id: str
    code: str
    name: str


@dataclass(frozen=True)
class CoursePage:
    url: str
    title: str
    published: bool
    updated_at: str
    body: str


#: The single course these pages belong to.
COURSE = Course(id="course-101", code="ASTR-101", name="Introduction to Astronomy")

_PAGES: tuple[CoursePage, ...] = (
    CoursePage(
        url="syllabus",
        title="Syllabus",
        published=True,
        updated_at="2026-07-14",
        body="\n".join(
            [
                "# Syllabus",
                "",
                "A survey of the night sky, from the solar system out to the large-scale",
                "structure of the universe. No prior physics required.",
                "",
                "## Assessment",
                "",
                "- Weekly quizzes — 30%",
                "- Observation log — 20%",
                "- Final project — 50%",
                "",
                "Office hours are Thursdays 14:00–16:00.",
            ]
        ),
    ),
    CoursePage(
        url="observing-the-night-sky",
        title="Observing the Night Sky",
        published=True,
        updated_at="2026-08-02",
        body="\n".join(
            [
                "# Observing the Night Sky",
                "",
                "You do not need a telescope for this course. Binoculars and a dark field",
                "will show you more than most beginners expect.",
                "",
                "## Before you go out",
                "",
                "1. Check the moon phase — a full moon washes out everything faint.",
                "2. Give your eyes twenty minutes to adapt, and use a red torch.",
                "3. Find north, then work from the bright stars outwards.",
                "",
                "## What to record",
                "",
                "For each session note the date, time, location, seeing conditions, and",
                "anything you could not identify. The unidentified entries are the ones we",
                "discuss in class.",
            ]
        ),
    ),
    CoursePage(
        url="final-project",
        title="Final Project Guidelines",
        published=False,
        updated_at="2026-08-11",
        body="\n".join(
            [
                "# Final Project Guidelines",
                "",
                "Pick one object in the sky and follow it for six weeks.",
                "",
                "## Deliverables",
                "",
                "- An observation log with at least eight entries",
                "- A 2000 word write-up placing your object in its astrophysical context",
                "- One sketch or photograph you made yourself",
                "",
                "## Marking",
                "",
                "Consistency of observation matters more than the equipment you used. A",
                "careful naked-eye log will score higher than a sporadic telescope one.",
            ]
        ),
    ),
)


def list_course_pages() -> list[dict[str, Any]]:
    """Every page in the course, without the body."""
    return [{k: v for k, v in asdict(page).items() if k != "body"} for page in _PAGES]


def find_course_page(page_url: str) -> CoursePage | None:
    """A single page with its full body, or None if nothing matches.

    Accepts the page url or its title, case-insensitively.
    """
    needle = page_url.strip().lower()
    for page in _PAGES:
        if page.url.lower() == needle or page.title.lower() == needle:
            return page
    return None
