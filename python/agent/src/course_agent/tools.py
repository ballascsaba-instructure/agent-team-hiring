"""The three tools the agent can call, over the page files in ``_data/``.

Each tool's model-facing text is passed explicitly as ``description=``, which
overrides the docstring. That split is deliberate: the descriptions say only
what the model needs to know, while the docstrings below are free to explain how
the thing actually works.
"""

import json
from dataclasses import asdict
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .course_pages import (
    COURSE,
    find_course_page,
    list_course_pages,
    update_course_page,
)


class ListCoursePagesArgs(BaseModel):
    published_only: bool | None = Field(
        default=None,
        description="Set to true to list only published pages. Omit to list all pages.",
    )


class GetCoursePageArgs(BaseModel):
    page_url: str = Field(description="The url or title of the page to fetch.")


class CoursePageUpdates(BaseModel):
    title: str | None = Field(default=None, description="A new title for the page.")
    body: str | None = Field(
        default=None,
        description="The new page body, as markdown. Replaces the body entirely.",
    )
    published: bool | None = Field(
        default=None, description="Whether the page should be visible to students."
    )


class UpdateCoursePageArgs(BaseModel):
    page_url: str = Field(description="The url or title of the page to update.")
    updates: CoursePageUpdates = Field(
        description="The fields to change. Omit any field you are leaving alone."
    )


def _not_found(page_url: str) -> str:
    return json.dumps(
        {
            "error": (
                f'No page found matching "{page_url}". '
                "Call list_course_pages to see the valid urls."
            )
        }
    )


@tool(
    "list_course_pages",
    args_schema=ListCoursePagesArgs,
    description=(
        "List every page in the course, with its url, title, published state and last "
        "update date. Call this first when you do not already know a page url."
    ),
)
def list_course_pages_tool(published_only: bool | None = None) -> str:
    """List the pages in the course.

    Bedrock rejects a tool whose input schema has no properties, so the schema
    carries one optional filter rather than being empty.
    """
    pages = [page for page in list_course_pages() if not published_only or page["published"]]
    return json.dumps({"course": asdict(COURSE), "pages": pages}, indent=2, ensure_ascii=False)


@tool(
    "get_course_page",
    args_schema=GetCoursePageArgs,
    description=(
        "Get the full content of one course page, including its body. Accepts either the "
        'page url (for example "final-project") or its title (for example "Syllabus").'
    ),
)
def get_course_page_tool(page_url: str) -> str:
    """Fetch the full body of a single course page."""
    page = find_course_page(page_url)
    if page is None:
        return _not_found(page_url)
    return json.dumps({"page": asdict(page)}, indent=2, ensure_ascii=False)


@tool(
    "update_course_page",
    args_schema=UpdateCoursePageArgs,
    description=(
        "Update a page in the course. Pass only the fields you want to change; anything "
        "you leave out keeps its current value."
    ),
)
def update_course_page_tool(page_url: str, updates: CoursePageUpdates) -> str:
    """Write the supplied fields back to the page's markdown file.

    Anything left out of ``updates`` keeps its current value, and the page's
    ``updated_at`` is stamped with today's date. The console output is for
    whoever is watching the demo — the model only sees the returned JSON.
    """
    page = find_course_page(page_url)
    if page is None:
        return _not_found(page_url)

    # LangChain hands us a validated model, but a dict survives a raw invoke too.
    supplied = updates if isinstance(updates, CoursePageUpdates) else CoursePageUpdates(**updates)
    changes: dict[str, Any] = {
        field: value for field, value in supplied.model_dump().items() if value is not None
    }

    if not changes:
        return json.dumps(
            {"error": "No updates were supplied. Provide at least one field to change."}
        )

    updated = update_course_page(page.url, **changes)
    # find_course_page just matched, so the page cannot have vanished.
    assert updated is not None

    print(f'\n[update_course_page] updated "{updated.title}" ({updated.url}):')
    for field, value in changes.items():
        print(f"  - {field}: {json.dumps(value, ensure_ascii=False)}")
    print()

    return json.dumps(
        {
            "page": {
                "url": updated.url,
                "title": updated.title,
                "published": updated.published,
                "updated_at": updated.updated_at,
            },
            "updated": changes,
        }
    )


#: Every tool the agent is allowed to call.
TOOLS: list[BaseTool] = [list_course_pages_tool, get_course_page_tool, update_course_page_tool]
