# CLAUDE.md

## Project Context

- Always read `requirements.md` before making product or architecture decisions.
- Also check `docs/superpowers/specs/` for approved design specs before implementation.
- Current MVP design is documented in `docs/superpowers/specs/2026-04-25-knowledgedeck-mvp-design.md`.

## Branching Workflow

- Use `main` as the stable branch.
- Use `dev` as the active development branch.
- Feature work should branch from `dev`.
- Do not commit directly to `main` unless explicitly requested.

## Development Rules

- Use TDD for feature and bugfix work.
- Write or update tests before implementation when behavior changes.
- Keep changes scoped to the requested feature or fix.
- Prefer existing project patterns over introducing new abstractions.
- Do not add unrelated refactors.

## Secret And API Key Safety

- Never commit API keys, tokens, passwords, private keys, `.env`, model credentials, or service secrets.
- Use `.env.example` for documented configuration values.
- Use placeholder values only, such as `local-dev-key` or `change-me`.
- Before committing, check staged changes for secrets or sensitive host-specific paths.
- If a secret is accidentally committed, stop and report it immediately instead of continuing.

## AI Code Review

- Claude Code may be used for code review.
- Treat Claude Code review comments as review feedback, not automatic truth.
- Verify review suggestions against the codebase before applying them.
- Do not blindly implement review feedback that conflicts with project requirements or architecture.

## Verification

- Run relevant tests before claiming work is complete.
- If tests cannot be run, explain why and state what was checked instead.
- For Docker or service changes, include the command used for validation.

## Git Hygiene

- Keep commits focused and descriptive.
- Do not rewrite shared history unless explicitly requested.
- Do not revert user changes unless explicitly asked.
