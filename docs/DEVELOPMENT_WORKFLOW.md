# Development Workflow

## Branch Model

- `main`: release-quality, recoverable state only
- `dev`: integration branch for tested changes before merge to main
- `feature/*`: scoped feature or bugfix work
- `experimental/*`: risky investigations or reverse-engineering probes

## Recommended Initial Commit Groups

For bootstrapping this repository from current project state, use this commit sequence:

1. `chore(repo): initialize git and ignore generated artifacts`
2. `feat(tracker): initial parser system`
3. `feat(overlay): initial browser overlay system`
4. `chore(parser): Radical Red parser calibration artifacts`
5. `chore(repo): production hardening docs and tooling`

### Scope guidance

- `initial parser system`:
  - `PokemonOverlay/tracker/*`
  - `PokemonOverlay/config.json`
  - `PokemonOverlay/requirements.txt`
- `overlay system`:
  - `PokemonOverlay/overlay/*`
  - sprite folders used by overlay
- `Radical Red parser calibration`:
  - RR-specific parser support and diagnostics files
- `production hardening`:
  - README/docs, lint/format config, workflow docs, `.gitignore`

## Commit Hygiene

- Prefer small commits with one concern.
- Use clear messages and include subsystem prefix (`tracker`, `overlay`, `repo`).
- Run parser smoke checks before merging to `dev` or `main`.

## Merge Guidance

- `feature/*` -> `dev` via PR-style review
- `experimental/*` should not merge directly to `main`
- `dev` -> `main` only after runtime verification in OBS

## Tagging Recommendation

- Tag stable milestones from `main`, for example:
  - `v0.1.0-parser-stable`
  - `v0.2.0-overlay-stable`
