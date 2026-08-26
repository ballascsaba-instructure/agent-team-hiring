/** The example pages a fresh checkout seeds `_data/` with. */
import * as fs from 'node:fs';
import * as path from 'node:path';

const SYLLABUS = `---
title: Syllabus
published: true
updated_at: 2026-07-14
---

# Syllabus

A survey of the night sky, from the solar system out to the large-scale
structure of the universe. No prior physics required.

## Assessment

- Weekly quizzes — 30%
- Observation log — 20%
- Final project — 50%

Office hours are Thursdays 14:00–16:00.
`;

const OBSERVING_THE_NIGHT_SKY = `---
title: Observing the Night Sky
published: true
updated_at: 2026-08-02
---

# Observing the Night Sky

You do not need a telescope for this course. Binoculars and a dark field
will show you more than most beginners expect.

## Before you go out

1. Check the moon phase — a full moon washes out everything faint.
2. Give your eyes twenty minutes to adapt, and use a red torch.
3. Find north, then work from the bright stars outwards.

## What to record

For each session note the date, time, location, seeing conditions, and
anything you could not identify. The unidentified entries are the ones we
discuss in class.
`;

const FINAL_PROJECT = `---
title: Final Project Guidelines
published: false
updated_at: 2026-08-11
---

# Final Project Guidelines

Pick one object in the sky and follow it for six weeks.

## Deliverables

- An observation log with at least eight entries
- A 2000 word write-up placing your object in its astrophysical context
- One sketch or photograph you made yourself

## Marking

Consistency of observation matters more than the equipment you used. A
careful naked-eye log will score higher than a sporadic telescope one.
`;

/** Page url -> file contents. The url is the file name, minus the `.md`. */
export const EXAMPLE_FILES: Record<string, string> = {
  syllabus: SYLLABUS,
  'observing-the-night-sky': OBSERVING_THE_NIGHT_SKY,
  'final-project': FINAL_PROJECT,
};

/**
 * Write every example page into `directory`, overwriting what is there.
 *
 * The caller decides when this is appropriate — `ensureDataDir` only calls it
 * for a directory it has just created, so pages you edit or delete stay edited
 * or deleted.
 */
export function seedExamples(directory: string): string[] {
  for (const [url, text] of Object.entries(EXAMPLE_FILES)) {
    fs.writeFileSync(path.join(directory, `${url}.md`), text, 'utf8');
  }
  return Object.keys(EXAMPLE_FILES);
}
