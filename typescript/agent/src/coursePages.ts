/**
 * In-memory stand-in for a course pages API. The agent is a demo, so this
 * module is the whole "backend": one course with three fixed pages that never
 * change, even when the update tool is called.
 */

export interface CoursePage {
  url: string;
  title: string;
  published: boolean;
  updatedAt: string;
  body: string;
}

/** A page as it appears in a listing — no body. */
export type CoursePageSummary = Omit<CoursePage, 'body'>;

/** The single course these pages belong to. */
export const COURSE = { id: 'course-101', code: 'ASTR-101', name: 'Introduction to Astronomy' };

const PAGES: CoursePage[] = [
  {
    url: 'syllabus',
    title: 'Syllabus',
    published: true,
    updatedAt: '2026-07-14',
    body: [
      '# Syllabus',
      '',
      'A survey of the night sky, from the solar system out to the large-scale',
      'structure of the universe. No prior physics required.',
      '',
      '## Assessment',
      '',
      '- Weekly quizzes — 30%',
      '- Observation log — 20%',
      '- Final project — 50%',
      '',
      'Office hours are Thursdays 14:00–16:00.',
    ].join('\n'),
  },
  {
    url: 'observing-the-night-sky',
    title: 'Observing the Night Sky',
    published: true,
    updatedAt: '2026-08-02',
    body: [
      '# Observing the Night Sky',
      '',
      'You do not need a telescope for this course. Binoculars and a dark field',
      'will show you more than most beginners expect.',
      '',
      '## Before you go out',
      '',
      '1. Check the moon phase — a full moon washes out everything faint.',
      '2. Give your eyes twenty minutes to adapt, and use a red torch.',
      '3. Find north, then work from the bright stars outwards.',
      '',
      '## What to record',
      '',
      'For each session note the date, time, location, seeing conditions, and',
      'anything you could not identify. The unidentified entries are the ones we',
      'discuss in class.',
    ].join('\n'),
  },
  {
    url: 'final-project',
    title: 'Final Project Guidelines',
    published: false,
    updatedAt: '2026-08-11',
    body: [
      '# Final Project Guidelines',
      '',
      'Pick one object in the sky and follow it for six weeks.',
      '',
      '## Deliverables',
      '',
      '- An observation log with at least eight entries',
      '- A 2000 word write-up placing your object in its astrophysical context',
      '- One sketch or photograph you made yourself',
      '',
      '## Marking',
      '',
      'Consistency of observation matters more than the equipment you used. A',
      'careful naked-eye log will score higher than a sporadic telescope one.',
    ].join('\n'),
  },
];

/** Every page in the course, without the body. */
export function listCoursePages(): CoursePageSummary[] {
  return PAGES.map(({ url, title, published, updatedAt }) => ({ url, title, published, updatedAt }));
}

/**
 * A single page with its full body, or `undefined` if nothing matches.
 * Accepts the page url or its title, case-insensitively.
 */
export function findCoursePage(pageUrl: string): CoursePage | undefined {
  const needle = pageUrl.trim().toLowerCase();
  return PAGES.find((page) => page.url.toLowerCase() === needle || page.title.toLowerCase() === needle);
}
