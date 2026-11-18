# Playwright Failure Analysis

**Date:** 2026-11-19

## Scope

This document covers the two Playwright failures reported in the comprehensive audit:

1. `queues research and displays its completed status`
2. `cancels and retries background document indexing`

No assertion was weakened or removed. Production code received no new test credentials.

## Original failure 1: queued research completion

### Original result

- Test timed out after 30 seconds.
- The page snapshot showed the research run as `completed`, with 100% progress, histogram rendering, and export buttons visible.

### Root cause

This was a timing/asynchronous test-environment failure, not an API integration or application logic failure:

- The mocked `jobs/job-1` and `research-runs/run-1/status` responses represented completion.
- The page reached the completed state and rendered the histogram/export UI.
- The suite reported an overall test timeout rather than an assertion mismatch.
- The failure did not reproduce across repeated runs.

The exact Playwright waiting step was not preserved in the original error output, so this report does not claim a single locator or assertion was responsible. The snapshot demonstrates that the application and mock API integration had progressed to the completed state.

### Fix

The test itself already had a 10-second completion assertion and did not need a weaker timeout or skipped assertion. The E2E runner was corrected to:

- Wait for the Playwright process to exit naturally.
- Preserve the real Playwright exit code.
- Stop both forcing a success when some tests pass and forcing cleanup after a partial summary.

This removes runner-level masking and ensures future failures are reported honestly.

## Original failure 2: document cancellation/retry

### Original result

- `Cancel` resolved to the correct button.
- Playwright could not click it because the fixed `.sidebar` intercepted pointer input.

### Root cause

This was a genuine application layout/stacking bug:

- The document processing controls were direct child action panels in the application shell.
- The fixed sidebar has `z-index: 3`.
- The document action panel lacked a higher stacking context/positioned container.
- At the viewport used by Playwright, the sidebar overlapped or intercepted the action panel.

This was not an authentication, API, or test expectation issue.

### Fix

Added a targeted CSS stacking and layout rule for `.app-shell > .document-job-actions`:

- `position: relative`
- `z-index: 4`
- Grid layout for label and action rows
- Explicit spacing and button alignment

The existing sidebar remains at `z-index: 3`.

No test assertions were removed or weakened.

## Files changed

- `frontend/src/app/globals.css`
- `frontend/scripts/run-e2e.mjs`
- `documentation/PLAYWRIGHT_FAILURE_ANALYSIS.md`

The Playwright test file was not modified.

## Commands executed

```powershell
npm run test:e2e
npm run typecheck
npm run lint
npm run build
```

Additional repeat run:

```powershell
npm run test:e2e
```

## Actual results

### Playwright

Initial post-fix run:

- Passed: 7
- Failed: 0
- Skipped: 0
- Total: 7
- Duration: 10.5 seconds

Stability rerun:

- Passed: 7
- Failed: 0
- Skipped: 0
- Total: 7
- Duration: 11.4 seconds

### Frontend validation

- `npm run typecheck`: passed
- `npm run lint`: passed
- `npm run build`: passed

The production build compiled and generated all routes successfully.

## Remaining issues

- The first original timeout was not reproduced after the fixes or runner correction.
- A stale Next development server can leave the Next dev lock active. If it does, stop that exact server process before rerunning Playwright; the suite will report server startup failure until the stale server is cleared.
- No live backend, live provider, or live Docker verification was performed as part of this task.
