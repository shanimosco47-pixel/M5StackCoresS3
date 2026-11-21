# Independent review and GitHub checks

The implementation is developed on `feature/cloud-voice-relay` and will be submitted as one PR.
It is not merged automatically.

## Actual separate review

A separate read-only reviewer inspected the server and reproduced three bugs while the original
29 tests passed: upload/replay race, ineffective cancellation during upload (including UUID case),
and missing upload deadline. Regression tests reproduced these failures before fixes.
The implementation now reserves the request before any upload await, includes upload in the
deadline, canonicalizes cancellation UUIDs and releases the slot after cancellation/timeout.
The suite now includes 32 cases. A follow-up independent review confirmed those fixes and
independently passed the32tests. It also caught a deployment integration issue: concurrency=1
would block cancellation HTTP requests during a running POST. The recommendation is corrected
to concurrency=4, with one ASGI worker and the existing application one-turn lock.

This separate reviewer is an agent in the development session, not a GitHub human approval.

## Automated GitHub jobs

`Relay checks`: Python 3.11/3.12 behavior tests, Ruff correctness checks, Bandit production-code
security review and pip-audit dependency vulnerability checks. No provider keys or billable AI
calls are used by these jobs. Static checks are not an AI code review.

`Independent AI review`: uses the existing Codex GitHub integration without checking out PR code,
then waits for its authenticated bot summary reporting a completed review on the exact PR head commit.
Codex automatically reviews newly opened PRs in this repository. After further pushes, an authorized
maintainer (or this development agent through the owner's authenticated GitHub CLI) comments `@codex review`.
Live testing showed that a GitHub Actions bot cannot authenticate to Codex, so the gate is strictly
read-only and never posts a misleading bot trigger. The job fails rather than
pretend a review happened when eligibility, quota, permissions or the service are unavailable.
Fork PRs require a maintainer to arrange review; their privileged automatic job is skipped.
Codex review can consume the account's existing review allowance; this workflow does not
purchase a subscription or enable paid overage. Findings must be read and resolved; a green
completion job alone is not proof of no findings or a substitute for a human approval.

The first live run proved that Copilot is ineligible on this account (HTTP422), so the gate was
changed to the already connected Codex service. The actual Codex bot automatically started a
review on PR1, verified through its GitHub comment and exact commit metadata.
The final gate must still be observed passing before it is described as fully operational.

The actual GitHub Codex review of commit68c6751 completed and found oneP2issue: the bounded replay
cache evicted unexpired IDs after enough silent/invalid uploads. A regression test reproduced it;
the fix refuses new IDs when capacity is full, preserving all unexpired IDs. The relay suite now
has33tests. Eight additional tests execute the actual workflow script against controlled GitHub
states, including spoofed authors, wrong commits, incomplete results, running and failed reviews.

CodeRabbit CLI availability could not be established from PATH in this environment, so no
CodeRabbit CLI review or configuration was claimed. No fake approval or self-approval is created.
