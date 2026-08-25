/**
 * File-backed storage for one course's pages.
 *
 * The agent is a demo, so this module is the whole "backend": a single course
 * whose pages live as markdown files in a git ignored `_data/` directory. Each
 * file holds a small frontmatter block for the metadata and the page body below
 * it:
 *
 *     ---
 *     title: Syllabus
 *     published: true
 *     updated_at: 2026-07-14
 *     ---
 *
 *     # Syllabus
 *     ...
 *
 * The file name is the page url, so `_data/syllabus.md` is the page `syllabus`.
 * There is no index and no cache — every call reads the directory, which is
 * fine at three pages and keeps hand-edits to the files visible immediately.
 *
 * `_data/` is created and seeded with the pages in `seed.ts` the first
 * time anything touches it, so a fresh clone has something to talk about.
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import process from 'node:process';

import { seedExamples } from './seed.ts';

export interface CoursePage {
  url: string;
  title: string;
  published: boolean;
  updatedAt: string;
  body: string;
}

/** A page as it appears in a listing — no body. */
export type CoursePageSummary = Omit<CoursePage, 'body'>;

/** The fields `updateCoursePage` will write. Omitted fields keep their value. */
export type CoursePageUpdates = Partial<Pick<CoursePage, 'title' | 'body' | 'published'>>;

/** The single course these pages belong to. Not stored — there is only one. */
export const COURSE = { id: 'course-101', code: 'ASTR-101', name: 'Introduction to Astronomy' };

/**
 * Where the page files live. `COURSE_DATA_DIR` overrides it; the default sits
 * next to package.json so it is the same directory whatever the cwd is.
 */
export const DATA_DIR =
  process.env.COURSE_DATA_DIR || path.resolve(import.meta.dirname, '..', '_data');

const FENCE = '---';

/** Today, local time, as `YYYY-MM-DD`. */
function today(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

const trimNewlines = (text: string): string => text.replace(/^\n+|\n+$/g, '');

/**
 * Render a page as frontmatter plus body. The url is not written — it is the
 * file name. The `updated_at` key is snake_case so the files stay readable by
 * the Python port, which writes the same format.
 */
function serialise(page: CoursePage): string {
  return [
    FENCE,
    `title: ${page.title}`,
    `published: ${page.published}`,
    `updated_at: ${page.updatedAt}`,
    FENCE,
    '',
    trimNewlines(page.body),
    '',
  ].join('\n');
}

/**
 * Read one page file.
 *
 * The frontmatter parser is deliberately tiny — `key: value` lines, no YAML. A
 * file with no readable frontmatter still loads: it becomes an unpublished page
 * titled after its file name, rather than an error the agent cannot act on.
 */
function deserialise(filePath: string): CoursePage {
  const text = fs.readFileSync(filePath, 'utf8');
  const url = path.basename(filePath, '.md');
  const meta = new Map<string, string>();
  let body = text;

  if (text.startsWith(`${FENCE}\n`)) {
    const rest = text.slice(FENCE.length + 1);
    const end = rest.indexOf(`\n${FENCE}\n`);

    if (end !== -1) {
      body = rest.slice(end + FENCE.length + 2);
      for (const line of rest.slice(0, end).split('\n')) {
        const colon = line.indexOf(':');
        if (colon !== -1) {
          meta.set(line.slice(0, colon).trim(), line.slice(colon + 1).trim());
        }
      }
    }
  }

  return {
    url,
    title: meta.get('title') || url,
    published: meta.get('published')?.toLowerCase() === 'true',
    updatedAt: meta.get('updated_at') ?? '',
    body: trimNewlines(body),
  };
}

/**
 * The file a page url maps to. `path.basename` drops any directory part, so a
 * url like `../secrets` cannot write outside `_data/`.
 */
function pagePath(pageUrl: string): string {
  const name = path.basename(pageUrl.trim());

  if (!name || name.startsWith('.')) {
    throw new Error(`Not a usable page url: "${pageUrl}"`);
  }
  return path.join(DATA_DIR, `${name}.md`);
}

function write(page: CoursePage): void {
  fs.writeFileSync(pagePath(page.url), serialise(page), 'utf8');
}

/**
 * Create `_data/` and seed the example pages if it is not there yet.
 *
 * Idempotent, and called by every read and write below as well as at startup,
 * so no caller has to remember to set the storage up first.
 */
export function ensureDataDir(): string {
  if (fs.existsSync(DATA_DIR)) {
    return DATA_DIR;
  }

  fs.mkdirSync(DATA_DIR, { recursive: true });
  seedExamples(DATA_DIR);
  return DATA_DIR;
}

/** Every page on disk, ordered by url so listings are stable. */
function loadAll(): CoursePage[] {
  ensureDataDir();
  return fs
    .readdirSync(DATA_DIR)
    .filter((name) => name.endsWith('.md'))
    .sort()
    .map((name) => deserialise(path.join(DATA_DIR, name)));
}

/** Every page in the course, without the body. */
export function listCoursePages(): CoursePageSummary[] {
  return loadAll().map(({ url, title, published, updatedAt }) => ({ url, title, published, updatedAt }));
}

/**
 * A single page with its full body, or `undefined` if nothing matches.
 * Accepts the page url or its title, case-insensitively.
 */
export function findCoursePage(pageUrl: string): CoursePage | undefined {
  const needle = pageUrl.trim().toLowerCase();
  return loadAll().find((page) => page.url.toLowerCase() === needle || page.title.toLowerCase() === needle);
}

/**
 * Write changed fields back to the page's file and return the new page, or
 * `undefined` if no page matches.
 *
 * Fields left out of `updates` keep their current value, and `updatedAt` is
 * stamped with today's date on every write. The url never changes, even when
 * the title does — it is the file name, and renaming files would break links
 * the agent may already have handed out.
 */
export function updateCoursePage(pageUrl: string, updates: CoursePageUpdates): CoursePage | undefined {
  const page = findCoursePage(pageUrl);

  if (!page) {
    return undefined;
  }

  const updated: CoursePage = {
    ...page,
    title: updates.title ?? page.title,
    body: updates.body ?? page.body,
    published: updates.published ?? page.published,
    updatedAt: today(),
  };

  write(updated);
  return updated;
}
