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

`Independent AI review`: requests GitHub Copilot code review without checking out PR code,
then waits for a completed review on the exact PR head commit. The job fails rather than
pretend a review happened when eligibility, quota, permissions or the service are unavailable.
Fork PRs require a maintainer to arrange review; their privileged automatic job is skipped.
Copilot review can consume the account's existing review/AI allowance; this workflow does not
purchase a subscription or enable paid overage. Findings must be read and resolved; a green
completion job alone is not proof of no findings or a substitute for a human approval.

The workflow must be observed running successfully before it is described as operational.
Current live run/reviewer status will be recorded in the PR and docs/STATUS.md.

CodeRabbit CLI availability could not be established from PATH in this environment, so no
CodeRabbit CLI review or configuration was claimed. No fake approval or self-approval is created.
