# Local Web Player

The local Web player is a real single-player interface over the same authoritative
`World` used by the CLI. It is served on loopback by Python's standard library and
adds no runtime dependency.

Start the original public demo with:

```powershell
python -m lore2mud web --content examples/original_demo --save-dir saves
```

The default URL is `http://127.0.0.1:8765/`. `--host` accepts only literal
loopback addresses (`127.0.0.1` or `::1`); the server is intentionally not a LAN or
Internet service. `--port` can select another local port.

## Data flow

```text
browser control
  -> POST /api/action with a typed action object
  -> PlayerSession validates and parses the untrusted action into GameIntent
  -> GameSession submits one turn to the authoritative World / SaveLoadService
  -> TurnResult with status, ordered events, and current player-safe GameView
  -> PlayerSession renders JSON; browser renders projected affordances
```

The browser never derives game state from Chinese response text. Structured actions
cover movement, taking and dropping items, item use, equipment, combat, dialogue,
campaign actions, shops, recovery, and save/load. The command form is a read-only fallback that
delegates to the existing `CommandProcessor`; its text is displayed only in the
journey log. It accepts only the no-argument `look`, `inventory` / `i`, `quests`,
`actions`, `objectives`, `knowledge`, `journal`, `status`, and `help` commands.
Mutating actions and save/load use the structured
controls so their success or failure never depends on parsing rendered Chinese text.

## API

`GET /api/snapshot` returns the current pack, player, room and authoritative exits,
visible room entities, inventory, equipment, accepted quests, active dialogue,
current shop, flags, and a `campaign` object. That object contains active scenes,
visible interactables, currently executable stable actions, non-inactive objectives,
non-unknown player knowledge, the merged journal, and an authoritative
`completion` projection. `completion` contains `completed` plus explicitly authored
`endings` with player-facing `title` and `text`; the browser never infers completion
from an objective, map route, or event message.

`POST /api/action` accepts an `application/json` object. Representative actions:

```json
{"type":"move","direction":"east"}
{"type":"take","target":"item_crystal_blade","quantity":1}
{"type":"equip","target":"item_crystal_blade"}
{"type":"attack","target":"monster_ash_mite"}
{"type":"talk","target":"character_elder_chen"}
{"type":"choose_dialogue","index":1}
{"type":"campaign_action","action_id":"action_align_safe_marks"}
{"type":"save","slot":"trail"}
{"type":"load","slot":"trail"}
{"type":"command","command":"look"}
```

Success responses contain `ok=true`, a typed `event`, the post-action `snapshot`, and
`newly_completed_endings`. The latter is non-empty only on a false-to-true terminal
transition caused by the current non-save/load action; the persistent completion panel
comes from the snapshot. Validation and world-rule failures return HTTP 422 with
`ok=false`, an error event, and an authoritative unchanged snapshot. Malformed HTTP
requests return 4xx JSON without reaching the World.

## Local security boundary

- The default bind address is `127.0.0.1`; wildcard and non-loopback binds are
  rejected.
- Every request requires exactly one numeric loopback `Host` with the active port
  (the standard `:80` suffix may be omitted for HTTP port 80). Browser POSTs must
  use one matching same-origin `Origin`; requests without `Origin` remain supported
  for explicit local clients and tests.
- Only three fixed static paths are served. Request paths are never joined to the
  filesystem.
- Static files are loaded with `importlib.resources.files()` through the package
  `Traversable` API, so the same server code works from a source tree, wheel, or
  zipimport archive. Packaging targets must include `web/static/*.html`, `*.css`,
  and `*.js`.
- Action bodies are limited to 32 KiB, require unambiguous framing, and are validated
  for exact fields and primitive types before dispatch. Socket reads time out after
  five seconds; decoded JSON is
  limited to 32 levels and 2048 nodes, with malformed Unicode and non-standard
  numeric constants rejected as HTTP 400.
- Responses use a restrictive Content Security Policy, `nosniff`, no referrer, and
  no-store headers.
- One process serves exactly one unauthenticated `PlayerSession`, which wraps one
  `GameSession`. The application session owns the authoritative `World`, serializes
  turns with a reentrant lock, and replaces its World only after a successful load;
  `CommandProcessor` reads that current World dynamically. This is a loopback
  single-player boundary, not a multi-user session model.
- A `campaign_action` payload carries only a stable action ID. `PlayerSession` cannot
  execute it through the text-command fallback; `World.execute_campaign_action()`
  recomputes current scene/interactable/condition availability before every mutation.
  Hidden action IDs and stale UI buttons therefore return HTTP 422 with an unchanged
  authoritative snapshot.

The UI uses a responsive three-column game layout on desktop and a single ordered
flow on mobile. Its route canvas is drawn only from structured room/exit snapshot
data, including locked-exit state. Active scene actions render in the main play
column; objectives, player knowledge, and persistent story entries remain in the
journal rail and join the same mobile flow without relying on rendered event text.
