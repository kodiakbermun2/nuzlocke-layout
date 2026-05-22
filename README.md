# PokemonOverlay Repository

Save-driven OBS/browser overlay tooling for Pokemon FireRed/Radical Red Nuzlocke tracking.

## Repository Layout

- `PokemonOverlay/tracker`: save parsing, state generation, diagnostics
- `PokemonOverlay/overlay`: browser source UI rendered by OBS
- `PokemonOverlay/config.json`: runtime config for tracker + overlay
- `Front`, `Front shiny`, `Icons`, `Icons shiny`: sprite assets

## Quick Start

1. Create and activate virtual environment.
2. Install dependencies:

```powershell
c:/Users/kodia/nuzlocke/.venv/Scripts/python.exe -m pip install -r PokemonOverlay/requirements.txt
```

3. Set save path in `PokemonOverlay/config.json`.
4. Run tracker:

```powershell
Push-Location "PokemonOverlay/tracker"
c:/Users/kodia/nuzlocke/.venv/Scripts/python.exe main.py
Pop-Location
```

5. In OBS Browser Source, load:

`PokemonOverlay/overlay/index.html`

Recommended OBS dimensions: `1920x1080`.

## Development Workflow

- Primary branch: `main` (stable)
- Integration branch: `dev`
- Feature branches: `feature/<short-topic>`
- Experimental branches: `experimental/<short-topic>`

Detailed workflow, commit grouping, and branch naming are in `docs/DEVELOPMENT_WORKFLOW.md`.

## Safety Notes

- Runtime/generated artifacts are ignored in `.gitignore`.
- Do not commit save files, logs, local dumps, or virtual environments.
- Keep parser and overlay changes in separate commits where practical.
