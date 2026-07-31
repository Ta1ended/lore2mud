# Local Web Player

The local Web player is a real single-player interface over the same authoritative
`World` used by the CLI. It is served on loopback by Python's standard library and
adds no runtime dependency.

Start the original public demo with:

```powershell
python -m lore2mud web --content examples/original_demo --save-dir saves
```

The default URL is `http://127.0.0.1:8765/`. Use `--host` or `--port` only when an
explicitly different local bind is required.

## Data flow

```text
browser control
  -> POST /api/action with a typed action object
  -> PlayerSession validates the untrusted action
  -> World public API / SaveLoadService
  -> typed outcome event + authoritative snapshot
  -> browser renders controls from snapshot fields
```

The browser never derives game state from Chinese response text. Structured actions
cover movement, taking and dropping items, item use, equipment, combat, dialogue,
shops, recovery, and save/load. The command form is a fallback that delegates to the
existing `CommandProcessor`; its text is displayed only in the journey log.

## API

`GET /api/snapshot` returns the current pack, player, room and exits, visible room
entities, inventory, equipment, accepted quests, active dialogue, current shop, and
flags.

`POST /api/action` accepts an `application/json` object. Representative actions:

```json
{"type":"move","direction":"east"}
{"type":"take","target":"item_crystal_blade","quantity":1}
{"type":"equip","target":"item_crystal_blade"}
{"type":"attack","target":"monster_ash_mite"}
{"type":"talk","target":"character_elder_chen"}
{"type":"choose_dialogue","index":1}
{"type":"save","slot":"trail"}
{"type":"load","slot":"trail"}
{"type":"command","command":"look"}
```

Success responses contain `ok=true`, a typed `event`, and the post-action
`snapshot`. Validation and world-rule failures return HTTP 422 with `ok=false`, an
error event, and an authoritative unchanged snapshot. Malformed HTTP requests return
4xx JSON without reaching the World.

## Local security boundary

- The default bind address is `127.0.0.1`; exposing it on another interface is an
  explicit operator choice.
- Only three fixed static paths are served. Request paths are never joined to the
  filesystem.
- Action bodies are limited to 32 KiB and validated for exact fields and primitive
  types before dispatch.
- Responses use a restrictive Content Security Policy, `nosniff`, no referrer, and
  no-store headers.
- One `PlayerSession` owns one World and serializes actions with a reentrant lock.
  A successful load replaces both the session World and its command processor.

The UI uses a responsive three-column game layout on desktop and a single ordered
flow on mobile. Its route canvas is drawn only from structured room/exit snapshot
data, including locked-exit state.
