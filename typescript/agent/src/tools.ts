/** The tools the agent can call, over the page files in `_data/`. */
import { tool } from '@langchain/core/tools';
import * as z from 'zod';

import { COURSE, findCoursePage, listCoursePages, updateCoursePage } from './coursePages.ts';

/**
 * Lists the pages in the course.
 *
 * Bedrock rejects a tool whose input schema has no properties, so the schema
 * carries one optional filter rather than being empty.
 */
export const listCoursePagesTool = tool(
  ({ publishedOnly }) => {
    const pages = listCoursePages().filter((page) => !publishedOnly || page.published);
    return JSON.stringify({ course: COURSE, pages }, null, 2);
  },
  {
    name: 'list_course_pages',
    description:
      'List every page in the course, with its url, title, published state and last update date. ' +
      'Call this first when you do not already know a page url.',
    schema: z.object({
      publishedOnly: z
        .boolean()
        .optional()
        .describe('Set to true to list only published pages. Omit to list all pages.'),
    }),
  },
);

/** Fetches the full body of a single course page. */
export const getCoursePageTool = tool(
  ({ pageUrl }) => {
    const page = findCoursePage(pageUrl);

    if (!page) {
      return JSON.stringify({
        error: `No page found matching "${pageUrl}". Call list_course_pages to see the valid urls.`,
      });
    }

    return JSON.stringify({ page }, null, 2);
  },
  {
    name: 'get_course_page',
    description:
      'Get the full content of one course page, including its body. ' +
      'Accepts either the page url (for example "final-project") or its title (for example "Syllabus").',
    schema: z.object({
      pageUrl: z.string().describe('The url or title of the page to fetch.'),
    }),
  },
);

/**
 * Writes the supplied fields back to the page's markdown file.
 *
 * Anything left out of `updates` keeps its current value, and the page's
 * `updatedAt` is stamped with today's date. The console output is for whoever
 * is watching the demo — the model only sees the returned JSON.
 */
export const updateCoursePageTool = tool(
  ({ pageUrl, updates }) => {
    const page = findCoursePage(pageUrl);

    if (!page) {
      return JSON.stringify({
        error: `No page found matching "${pageUrl}". Call list_course_pages to see the valid urls.`,
      });
    }

    const changes = Object.entries(updates).filter(([, value]) => value !== undefined);

    if (changes.length === 0) {
      return JSON.stringify({
        error: 'No updates were supplied. Provide at least one field to change.',
      });
    }

    // findCoursePage just matched, so the page cannot have vanished.
    const updated = updateCoursePage(page.url, updates)!;

    console.log(`\n[update_course_page] updated "${updated.title}" (${updated.url}):`);
    for (const [field, value] of changes) {
      console.log(`  - ${field}: ${JSON.stringify(value)}`);
    }
    console.log();

    return JSON.stringify({
      page: {
        url: updated.url,
        title: updated.title,
        published: updated.published,
        updatedAt: updated.updatedAt,
      },
      updated: Object.fromEntries(changes),
    });
  },
  {
    name: 'update_course_page',
    description:
      'Update a page in the course. Pass only the fields you want to change; ' +
      'anything you leave out keeps its current value.',
    schema: z.object({
      pageUrl: z.string().describe('The url or title of the page to update.'),
      updates: z
        .object({
          title: z.string().optional().describe('A new title for the page.'),
          body: z.string().optional().describe('The new page body, as markdown. Replaces the body entirely.'),
          published: z.boolean().optional().describe('Whether the page should be visible to students.'),
        })
        .describe('The fields to change. Omit any field you are leaving alone.'),
    }),
  },
);

/** Every tool the agent is allowed to call. */
export const tools = [listCoursePagesTool, getCoursePageTool, updateCoursePageTool];
