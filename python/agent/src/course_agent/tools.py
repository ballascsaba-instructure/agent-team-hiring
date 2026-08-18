import json
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from .course_pages import COURSE, find_course_page, list_course_pages


def _json(payload: Any, *, indent: int | None = None) -> str:
    """``JSON.stringify`` with the same spacing and unescaped non-ASCII."""
    separators = (",", ":") if indent is None else None
    return json.dumps(payload, indent=indent, separators=separators, ensure_ascii=False)


class ListCoursePagesInput(BaseModel):
    # camelCase throughout this module: these names are the model-facing
    # contract, and they match the TypeScript agent's zod schemas exactly.
    publishedOnly: bool | None = Field(
        default=None,
        description="Set to true to list only published pages. Omit to list all pages.",
    )


@tool(
    "list_course_pages",
    description=(
        "List every page in the course, with its url, title, published state and last update date. "
        "Call this first when you do not already know a page url."
    ),
    args_schema=ListCoursePagesInput,
)
def list_course_pages_tool(publishedOnly: bool | None = None) -> str:
    """
    Lists the pages in the course.

    Bedrock rejects a tool whose input schema has no properties, so the schema
    carries one optional filter rather than being empty.
    """
    pages = [page for page in list_course_pages() if not publishedOnly or page["published"]]
    return _json({"course": COURSE, "pages": pages}, indent=2)


class GetCoursePageInput(BaseModel):
    pageUrl: str = Field(description="The url or title of the page to fetch.")


@tool(
    "get_course_page",
    description=(
        "Get the full content of one course page, including its body. "
        'Accepts either the page url (for example "final-project") or its title (for example "Syllabus").'
    ),
    args_schema=GetCoursePageInput,
)
def get_course_page_tool(pageUrl: str) -> str:
    """Fetches the full body of a single course page."""
    page = find_course_page(pageUrl)

    if page is None:
        return _json(
            {
                "error": (
                    f'No page found matching "{pageUrl}". '
                    "Call list_course_pages to see the valid urls."
                )
            }
        )

    return _json({"page": page.as_json()}, indent=2)


class PageUpdates(BaseModel):
    title: str | None = Field(default=None, description="A new title for the page.")
    body: str | None = Field(
        default=None,
        description="The new page body, as markdown. Replaces the body entirely.",
    )
    published: bool | None = Field(
        default=None,
        description="Whether the page should be visible to students.",
    )


class UpdateCoursePageInput(BaseModel):
    pageUrl: str = Field(description="The url or title of the page to update.")
    updates: PageUpdates = Field(
        description="The fields to change. Omit any field you are leaving alone."
    )


@tool(
    "update_course_page",
    description=(
        "Update a page in the course. Pass only the fields you want to change; "
        "anything you leave out keeps its current value."
    ),
    args_schema=UpdateCoursePageInput,
)
def update_course_page_tool(pageUrl: str, updates: PageUpdates) -> str:
    """
    A deliberately inert write tool. It validates the page url, prints the
    changes it *would* have made, and returns without touching the page data.
    The point of the demo is to watch the agent decide on an edit, not to
    maintain a course.

    Note that neither the description above nor the return value admits to this
    — the model is meant to treat it as a real write.
    """
    page = find_course_page(pageUrl)

    if page is None:
        return _json(
            {
                "error": (
                    f'No page found matching "{pageUrl}". '
                    "Call list_course_pages to see the valid urls."
                )
            }
        )

    changes = [(field, value) for field, value in updates if value is not None]

    if len(changes) == 0:
        return _json({"error": "No updates were supplied. Provide at least one field to change."})

    print(f'\n[update_course_page] would update "{page.title}" ({page.url}):')
    for field, value in changes:
        print(f"  - {field}: {_json(value)}")
    print("[update_course_page] dry run only, nothing was written.\n")

    return _json(
        {
            "page": {"url": page.url, "title": page.title},
            "updated": dict(changes),
        }
    )


#: Every tool the agent is allowed to call.
TOOLS: list[BaseTool] = [list_course_pages_tool, get_course_page_tool, update_course_page_tool]
