# Pokemon Nuzlocke OBS Auto-Overlay

A local save-file-driven overlay system for Radical Red / FireRed-based Nuzlocke streams.

The validated architecture remains unchanged:
- tracker parses `.sav` -> writes `tracker/state.json`
- overlay reads `tracker/state.json` from an OBS Browser Source local file

## Current Stability Focus

This build is now hardened for longer stream sessions:
- parser mode separation (`vanilla_firered` vs `radical_red`)
- automatic parser mode detection (`auto`)
- stricter parser safeguards (checksum/species/level/corruption validation)
- structured tracker logging events
- config-driven runtime (`config.json`)
- resilient overlay status states (loading / waiting / disconnected)
- reduced overlay flicker via diff-based DOM updates and sprite source caching

## Project Structure

```text
PokemonOverlay/
|-- config.json
|-- tracker/
|   |-- main.py
|   |-- config_loader.py
|   |-- save_parser.py
|   |-- party_parser.py
|   |-- state_manager.py
|   |-- models.py
|   |-- verify_parser.py
|   |-- mock_save_generator.py
|   |-- debug_save_dump.py
|   |-- state.json
|-- overlay/
|   |-- index.html
|   |-- style.css
|   |-- overlay.js
|   |-- sprites/
|       |-- normal/
|       |-- shiny/
|       |-- icons/
|-- assets/
|   |-- backgrounds/
|-- requirements.txt
```

## Configuration

Use `config.json` at project root.

```json
{
  "tracker": {
    "save_path": "C:/path/to/RadicalRed.sav",
    "state_path": "tracker/state.json",
    "poll_interval_ms": 1000,
    "debug": false,
    "party_only": false,
    "simulate_if_missing": false,
    "radical_red_mode": "auto"
  },
  "overlay": {
    "poll_interval_ms": 1000,
    "theme": "default",
    "sprite_style": "auto",
    "overlay_scale": 1.0
  }
}
```

Notes:
- `radical_red_mode` accepted values: `auto`, `vanilla_firered`, `radical_red`
- CLI args still override config values for tracker runtime

## Running Tracker

From `PokemonOverlay/tracker`:

```powershell
python main.py
```

Or with explicit overrides:

```powershell
python main.py --save "C:\Games\mGBA\saves\RadicalRed.sav" --poll-seconds 1 --parser-mode auto --debug
```

## Parser Verification Utility

Validate parser correctness against a real save:

```powershell
python verify_parser.py --save "C:\Games\mGBA\saves\RadicalRed.sav" --mode auto --expect-party 6
```

Optional output dump:

```powershell
python verify_parser.py --save "C:\Games\mGBA\saves\RadicalRed.sav" --out "parsed_state.json"
```

## Mock Saveblock Utility

Generate a parser-targeted mock saveblock for test tooling:

```powershell
python mock_save_generator.py --mode radical_red --party-count 6 --out "mock_saveblock.bin"
```

## Overlay Behavior

The overlay now handles long-running OBS sessions more safely:
- startup: `Loading overlay...`
- connected but empty state: `Connected. Waiting for save data...`
- tracker unavailable: `Save disconnected. Waiting for tracker...`
- transient read errors auto-retry
- changed Pokemon cards update without full-grid rerender

### OBS Source Setup

1. Add Browser Source
2. Enable Local file
3. Select `overlay/index.html`
4. Set Width: `1920`, Height: `1080`
5. Keep source refresh behavior according to stream workflow

## Sprite Requirements

Supported lookup order for party entries:
- `overlay/sprites/normal/<species>.png` or shiny equivalent
- `overlay/sprites/normal/<species_id>.png` or shiny equivalent
- `overlay/sprites/normal/missingno.png`
- built-in SVG fallback

For PC/dead entries:
- `overlay/sprites/icons/<species>.png`
- `overlay/sprites/icons/<species_id>.png`
- icon/normal fallback chain

## Troubleshooting

1. Parser mode seems wrong
- set `radical_red_mode` to `radical_red` in `config.json` and retry

2. Overlay says disconnected
- confirm tracker process is running and writing `tracker/state.json`
- confirm overlay can resolve `../tracker/state.json`

3. Sprites missing
- add species files using current naming conventions
- optionally add `overlay/sprites/normal/missingno.png`

## Extension Readiness

Current structure keeps future additions isolated without changing the core pipeline:
- parser and save diagnostics remain in tracker modules
- UI rendering is state-driven and section-agnostic
- `meta` fields in state support future non-breaking feature metadata
