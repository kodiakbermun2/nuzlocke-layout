# Pokemon Nuzlocke OBS Auto-Overlay

A local save-file-driven overlay system for Radical Red / FireRed-based Nuzlocke streams.

Current architecture (with compatibility fallback):
- tracker parses `.sav` -> broadcasts live state via local websocket
- overlay consumes websocket pushes for near-instant updates
- optional fallback remains: tracker writes `tracker/state.json`, overlay polls JSON if websocket is disabled

Provider architecture (optional live mode):
- `SaveFileProvider` (existing stable save-file parser path)
- `EmulatorMemoryProvider` (optional mGBA bridge payload path)
- mode selection is config-driven and can auto-fallback to save mode

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
    "radical_red_mode": "auto",
    "provider_mode": "auto",
    "memory": {
      "enabled": false,
      "backend": "mgba_json_bridge",
      "bridge_path": "tracker/memory_state.json",
      "poll_interval_ms": 150,
      "stale_after_ms": 2000
    },
    "websocket": {
      "enabled": true,
      "host": "127.0.0.1",
      "port": 8765,
      "heartbeat_interval_ms": 10000
    }
  },
  "overlay": {
    "poll_interval_ms": 1000,
    "theme": "default",
    "sprite_style": "auto",
    "overlay_scale": 1.0,
    "websocket": {
      "enabled": true,
      "host": "127.0.0.1",
      "port": 8765,
      "reconnect_interval_ms": 1000
    }
  }
}
```

Notes:
- `radical_red_mode` accepted values: `auto`, `vanilla_firered`, `radical_red`
- `provider_mode` accepted values: `auto`, `save`, `memory`
- CLI args still override config values for tracker runtime
- websocket traffic is local-machine only (`127.0.0.1`)
- set `overlay.websocket.enabled=false` to force JSON polling fallback mode

## Optional Live Memory Mode (mGBA)

This mode is additive: save-based parsing remains available and acts as fallback.

1. Enable in `config.json`:

```json
"tracker": {
  "provider_mode": "auto",
  "memory": {
    "enabled": true,
    "backend": "mgba_json_bridge",
    "bridge_path": "tracker/memory_state.json",
    "poll_interval_ms": 150,
    "stale_after_ms": 2000
  }
}
```

2. Provide bridge payload updates from mGBA scripting to `tracker/memory_state.json`

A concrete bridge script is included:
- `tracker/mgba_memory_bridge_template.lua`

Quick start:
1. Open mGBA Script Console.
2. Load `tracker/mgba_memory_bridge_template.lua`.
3. Keep the script running while tracker is active.

The bridge script now reads FRLG/RR party memory directly and writes atomically:
- source: WRAM party structs
- destination: `tracker/memory_state.json`
- write cadence: ~100ms
- write safety: temp file + rename

Expected mGBA console logs:
- `[mgba_bridge] bridge started`
- `[mgba_bridge] party_count=... party_start=...`
- `[mgba_bridge] write ok #N party_count=... parsed=... failures=...`
- `[mgba_bridge] slot X decode warning: ...` (if slot read fails)
- `[mgba_bridge] write failure: ...` (if path/permissions issue)

Payload contract:

```json
{
  "timestamp_ms": 1716000000000,
  "party": [
    {
      "species": "clauncher",
      "species_id": 800,
      "nickname": "Squirt",
      "level": 16,
      "gender": "unknown",
      "shiny": false,
      "held_item": null,
      "slot": 1,
      "current_hp": 46,
      "max_hp": 46,
      "status": null,
      "types": ["water"]
    }
  ],
  "pc": [],
  "dead": [],
  "meta": {
    "source": "mgba_script"
  }
}
```

3. Tracker behavior:
- If memory bridge is fresh and valid: uses `EmulatorMemoryProvider`
- If memory bridge is stale/unavailable: auto-falls back to `SaveFileProvider`
- websocket/status logs report provider path and fallback events

Provider diagnostics appear in tracker logs as `provider_update` and include `provider=memory` or `provider=save`.

## Bridge Validator

Use the bridge validator to verify schema, timestamp progress, stale writes, and live deltas:

```powershell
python tracker/test_memory_bridge.py --path "tracker/memory_state.json" --poll-ms 100 --stale-ms 1200
```

What it checks:
- JSON is well-formed
- required payload keys exist
- timestamp advances over time
- stale write detection
- live party summaries (HP/status/order)

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
- websocket connected: `Connected to live tracker feed.`
- connected but empty state: `Connected. Waiting for save data...`
- tracker unavailable: `Save disconnected. Waiting for tracker...`
- transient read errors auto-retry
- changed Pokemon cards update without full-grid rerender
- websocket reconnect uses backoff and survives tracker restarts / OBS reloads

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

## Share This With Friends

The easiest way is to share the full `PokemonOverlay` folder via one of these options:
- push to a GitHub repository and send the repo URL
- zip the `PokemonOverlay` folder and send the zip

Recommended package contents:
- `PokemonOverlay/overlay/`
- `PokemonOverlay/tracker/`
- `PokemonOverlay/config.json`
- `PokemonOverlay/requirements.txt`

Per-friend setup checklist (Windows):

1. Install Python 3.11+.
2. Download or clone your shared project folder.
3. Open PowerShell in the `PokemonOverlay` folder.
4. Create and activate a virtual environment:
  - `py -3 -m venv .venv`
  - `.venv\Scripts\Activate.ps1`
5. Install dependencies:
  - `pip install -r requirements.txt`
6. Edit `config.json` for their machine:
  - set `tracker.save_path` to their own `.sav` file path
  - keep websocket host as `127.0.0.1`
  - choose `provider_mode` (`auto`, `save`, or `memory`)
7. Start tracker:
  - from `PokemonOverlay/tracker`, run `python main.py --config ..\config.json`
8. In OBS, add Browser Source:
  - Local file: `PokemonOverlay/overlay/index.html`
  - Width `1920`, Height `1080`

If they use mGBA live memory mode:
- enable `tracker.memory.enabled` in `config.json`
- run the included mGBA Lua bridge script from `tracker/mgba_memory_bridge_template.lua`

Troubleshooting quick hits:
- overlay stuck on waiting: check tracker terminal for errors and verify save path
- no updates in OBS after style/js changes: reload Browser Source cache
- websocket issues: ensure only one tracker instance is bound to port `8765`

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

4. No live memory updates
- ensure mGBA script console is running `tracker/mgba_memory_bridge_template.lua`
- verify `tracker/memory_state.json` file mtime updates every ~100ms
- verify `tracker.memory.enabled=true` in `config.json`

5. Stale bridge warnings
- mGBA script stopped or paused
- incorrect bridge path
- increase `tracker.memory.stale_after_ms` for slower systems

6. Malformed bridge JSON
- ensure script writes atomically (already implemented in template)
- check disk permissions for tracker folder

7. Overlay disconnected / no websocket updates
- ensure only one tracker process is running (port 8765)
- confirm tracker logs show `provider_update` events

8. Wrong paths
- use absolute-style Windows paths in Lua bridge path if needed
- keep tracker and bridge file in the same workspace to simplify relative path resolution

## Extension Readiness

Current structure keeps future additions isolated without changing the core pipeline:
- parser and save diagnostics remain in tracker modules
- UI rendering is state-driven and section-agnostic
- `meta` fields in state support future non-breaking feature metadata
