# Codex Repository Rules

## Repository source of truth

- Treat `hagiwara777/shopee-expansion-tool` and its current clone as the source of truth.
- Do not work in older project or temporary work folders.

## Before making changes

- Identify the files in scope before editing.
- Run these commands at the start of work:

  ```powershell
  git status
  git rev-parse --show-toplevel
  git log -1 --oneline
  ```

- If a task changes behavior or scope, report the proposed differences before editing.

## Git and sensitive data

- Do not commit or push unless the user explicitly authorizes it.
- Never add the following to Git: `.env`, `.env.*`, cache databases, `outputs/`,
  `.venv/`, `__pycache__/`, `.pytest_cache/`, `.pytest_tmp/`, `.agents/`,
  `.codex/`, or `work/`.
- Do not hard-code API keys, tokens, or passwords in source code, README files, or tests.

## Validation

- Run `pytest` after changes whenever practical.
- Use the real Keepa API only when the user explicitly authorizes that verification.

## Component boundaries

- Keep Product Finder, Guardrail, and ASIN Resolver responsibilities separate.
- Do not combine or extend their responsibilities without an approved scope change.
