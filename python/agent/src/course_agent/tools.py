"""The three tools the agent can call. All of them are dummies.

Each tool's model-facing text is passed explicitly as ``description=``, which
overrides the docstring. That split is deliberate: the docstrings below say what
these functions really do, while the descriptions say only what the model needs
to believe.
"""

import json
from dataclasses import asdict
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .course_pages import COURSE, find_course_page, list_course_pages


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
    """A deliberately inert write tool.

    It validates the page url, prints the changes it *would* have made, and
    returns without touching the page data. The point of the demo is to watch the
    agent decide on an edit, not to maintain a course.

    Note that neither the description above nor the return value admits to this —
    the model is meant to treat it as a real write. The console output is for
    whoever is watching the demo.
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

    print(f'\n[update_course_page] would update "{page.title}" ({page.url}):')
    for field, value in changes.items():
        print(f"  - {field}: {json.dumps(value, ensure_ascii=False)}")
    print("[update_course_page] dry run only, nothing was written.\n")

    return json.dumps({"page": {"url": page.url, "title": page.title}, "updated": changes})


#: Every tool the agent is allowed to call.
TOOLS: list[BaseTool] = [list_course_pages_tool, get_course_page_tool, update_course_page_tool]
