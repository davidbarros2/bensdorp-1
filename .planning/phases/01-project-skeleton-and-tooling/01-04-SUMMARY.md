---
phase: "01"
plan: "04"
subsystem: ci
tags: [github-actions, ci, branch-protection, workflows]
dependency_graph:
  requires:
    - "01-03"
  provides:
    - REPO-02
    - REPO-03
    - REPO-06
    - REPO-07
    - TEST-06
  affects: []
tech_stack:
  added:
    - "GitHub Actions (ci.yml, close-pr.yml)"
    - "astral-sh/setup-uv@v6"
    - "superbrothers/close-pull-request@v3"
  patterns:
    - "OS matrix (ubuntu-latest + windows-latest) with fail-fast: false"
    - "uv cache keyed on uv.lock via cache-dependency-glob"
    - "pull_request_target for fork-safe PR auto-close"
key_files:
  created:
    - .github/workflows/ci.yml
    - .github/workflows/close-pr.yml
  modified: []
decisions:
  - "Repo changed from private to public to allow GitHub Actions CI to run (billing blocked CI on private repos)"
  - "pull_request_target used in close-pr.yml (not pull_request) to handle fork PRs with write token"
  - "Branch protection ruleset created requiring both test (ubuntu-latest) and test (windows-latest) status checks"
metrics:
  duration: "~30 minutes (includes human checkpoint for repo settings)"
  completed: "2026-05-23"
---

# Phase 1 Plan 4: CI Workflows and Repo Settings Summary

**One-liner:** GitHub Actions CI running pytest + ruff + mypy on ubuntu/windows matrix with branch protection and PR auto-close via pull_request_target.

## What Was Built

Two GitHub Actions workflow files were created and committed (commit 9c2fa6a):

- `.github/workflows/ci.yml` — runs the full quality gate (pytest, ruff check, ruff format --check, mypy --strict) on every push and PR, with an OS matrix covering ubuntu-latest and windows-latest using Python 3.11; uv cache is keyed on uv.lock via cache-dependency-glob for fast installs
- `.github/workflows/close-pr.yml` — auto-closes any incoming PR using pull_request_target (not pull_request) to handle fork PRs correctly, with a no-contributions policy comment

Two manual GitHub repository settings were applied and confirmed via human checkpoint:

- Issues and Discussions disabled (REPO-02)
- Branch protection ruleset "Protect main" requiring test (ubuntu-latest) and test (windows-latest) status checks before merging to main (REPO-06)

CI was triggered via an empty commit (525e62e) after the repository was made public. Both CI jobs passed green: ubuntu-latest in 16 s, windows-latest in 28 s (CI run 26329154567).

## Verification Results

All success criteria met:

1. `.github/workflows/ci.yml` and `.github/workflows/close-pr.yml` exist and are valid YAML
2. GitHub Actions shows two green CI jobs (ubuntu-latest, windows-latest)
3. Issues disabled in repository settings
4. Branch protection ruleset on main requires both CI status checks to pass

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create ci.yml and close-pr.yml | 9c2fa6a | .github/workflows/ci.yml, .github/workflows/close-pr.yml |
| 2 | Human checkpoint: CI green + repo settings applied | — | (manual GitHub settings) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Deviation] Repository changed from private to public**
- **Found during:** Human checkpoint
- **Issue:** GitHub Actions CI would not run on private repos under the account's free billing tier; CI runs were not triggered after pushing the workflow files
- **Fix:** Repository visibility changed from private to public; an empty commit (525e62e) was pushed to trigger CI after the visibility change
- **Impact:** CI ran successfully — both ubuntu-latest and windows-latest jobs passed green (run 26329154567)
- **Commit:** 525e62e

This deviation is expected and correct: the project is a single-user personal tool with no private data in the repository; public visibility is consistent with Phase 14's planned public README and the no-contributions policy enforced by close-pr.yml.

## Phase 1 Completion

All four plans in Phase 1 are now complete:

| Plan | Name | Status |
|------|------|--------|
| 01-01 | pyproject.toml and package skeleton | Done |
| 01-02 | Command modules and help command | Done |
| 01-03 | Test suite, LICENSE, ISSUE_TEMPLATE | Done |
| 01-04 | CI workflows and repo settings | Done |

**Phase 1 success criteria verification:**
1. `uv pip install -e .` completes without errors and `bensdorp1 --help` prints categorized command list — DONE (Plans 01, 02)
2. `bensdorp1 help <command>` returns detailed help for any recognized command — DONE (Plan 02)
3. GitHub Actions ci.yml runs pytest, ruff, and mypy strict on every push and PR; passes on clean repo — DONE (this plan; CI run 26329154567 green)
4. PRs are auto-closed by close-pr.yml; Issues and Discussions disabled — DONE (this plan; settings confirmed)

Phase 1 is complete.

## Known Stubs

None — this plan creates infrastructure files only. No application code with stub patterns was introduced.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

The threat mitigations from the plan's STRIDE register are all in place:
- T-04-01: pull_request_target used (fork-safe)
- T-04-02: no secrets beyond implicit GITHUB_TOKEN; branch protection prevents unauthorized merges
- T-04-03: uv sync --locked enforces uv.lock hash-pinned versions in CI
- T-04-04: Branch protection ruleset applied (confirmed at checkpoint)
- T-04-05: close-pr.yml auto-closes fork PRs via pull_request_target

## Self-Check: PASSED

- `.github/workflows/ci.yml` exists: FOUND
- `.github/workflows/close-pr.yml` exists: FOUND
- Commit 9c2fa6a exists: FOUND
- Commit 525e62e exists: FOUND
