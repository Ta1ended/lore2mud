# lore2mud

Lore2MUD is an **Agent-callable novel-to-text-game engine**. A developer Agent is
the direct tool user; the product owner/creator supplies decisions and rights
authorization; the player is the final user. Lore2MUD is not itself an Agent.

The repository is public and contains generic engine/tooling code plus original
examples only. It does not include third-party novels, proprietary characters,
private adaptations, images, audio, or owner-controlled derived artifacts. The MIT
license covers repository-owned material, not imported or generated content.

## Product And Architecture

- [Product definition](PRODUCT.md) - users, modes, inputs/outputs, PLAT-1, metrics,
  non-goals, and rights boundary.
- [Current code map](CODE_MAP.md) - real V1 symbols, flows, module sizes, risks, and
  ownership for future changes.
- [V2 target architecture](docs/v2/architecture.md) - Authoring Plane, deterministic
  Runtime Plane, contracts, compatibility, and capability safety.
- [V2 development model](docs/v2/development_model.md) - product authority, Codex
  roles, model floor, TECH/PRODUCT/SECURITY passes, and Git gates.
- [V2 roadmap](docs/v2/roadmap.md) - V2-0 through V2-5 and PLAT-1.

## What Exists Today: V1

The current public runtime is a local single-player Python text MUD. It loads strict
multi-file JSON content into `ContentPack`, constructs an authoritative `World`, and
exposes play through a text CLI and local Web client. Current capabilities include:

- rooms, exits and item gates; typed item stacks, inventory, equipment, consumables,
  loot, fixed shops, coins, deterministic combat and defeat recovery;
- typed quests, dialogue and atomic effects, narrative state/conditions, and optional
  runtime `campaign.json` scenes, actions, objectives, knowledge, and journal entries;
- save v9 with constrained named slots and guarded v7/v8 read compatibility;
- content validation, public original examples, deterministic authoring compilers,
  repository safety checks, Windows packaging, and a local Web player.

`World`, `CommandProcessor`, and Web `PlayerSession` are current V1 types.
`GameBlueprint`, `GameProject`, `GamePackage v2`, `CapabilityDescriptor`,
`GameSession`, `GameIntent`, `GameEvent`, `GameView`, and `TurnResult` are V2 targets
and are not implemented by the V2-0 documentation reset.

The pipeline `CampaignSpec v1` is a deterministic authoring IR. It is **not** a
runtime input and is not interchangeable with a content pack's runtime
`campaign.json`.

## Quick Start

Python 3.11 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Play the original public demo:

```powershell
python -m lore2mud play --content examples/original_demo
```

The legacy form remains supported:

```powershell
python -m lore2mud --content examples/original_demo
```

Validate without starting a game:

```powershell
python -m lore2mud validate --content examples/original_demo
```

Run the local Web player:

```powershell
python -m lore2mud web --content examples/original_demo
```

Use `help` in the CLI for the live command registry. The original demo walkthrough
and content notes are in [examples/original_demo/README.md](examples/original_demo/README.md).

## Repository Layout

```text
src/lore2mud/          V1 runtime, content loading, CLI, and Web
pipeline/              deterministic authoring and Forge tools
schemas/               public JSON Schema contracts
examples/              original public content
tests/                 unit, scenario, CLI, Web, and packaging evidence
docs/                  V1 formats/workflows and V2 architecture documents
scripts/               repository safety and delivery helpers
```

The current runtime flow is:

```text
JSON content -> load_content_pack() -> ContentPack -> World
player command/action -> CommandProcessor or PlayerSession -> World -> result/view
World <-> SaveLoadService -> versioned local save
```

The target V2 flow is:

```text
Authoring Plane: source + decisions -> Blueprint -> Project -> Package
Runtime Plane: Package + Intent -> Session -> Events + View -> TurnResult
```

See [CODE_MAP.md](CODE_MAP.md) before changing shared runtime or authoring modules.

## Public And Private Boundary

| Public repository | Owner-controlled external workspace |
|---|---|
| Generic engine, SDK/tooling, schemas and tests | Novel text and split chapters |
| Original examples and public-safe fixtures | Private summaries, canon and traces |
| Product/architecture/format documentation | Proprietary adaptations and assets |
| Generic provenance and rights contracts | Indexes, databases, saves, logs and reports |

Private source directories are read-only inputs. Model output, imported packages,
assets, and player input are untrusted. Validate them before use, preserve provenance,
and never infer that a repository license grants rights to external material.

## Authoring Tools

The current pipeline provides conservative novel splitting and deterministic,
validated compilers for fact candidates/reviews, canon drafts/registries,
registry inspection/adaptation, `NarrativeModel v1`, and `CampaignSpec v1`. Their
format contracts live under `docs/` and `schemas/`.

Forge currently orchestrates only inspection and registry-adaptation stages. It is a
useful V1 workbench, not yet the V2 Authoring Plane or package builder.

## Development

Start with [AGENTS.md](AGENTS.md), then read `PRODUCT.md`, `PROJECT_STATE.md`,
`NEXT_TASK.md`, and only the code/docs relevant to the active task. The exact workflow
is in [docs/production_workflow.md](docs/production_workflow.md).

Core verification includes:

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
python -m ruff check .
python -m pyright
python -m compileall -q src pipeline scripts tests
python -m lore2mud validate --content examples/original_demo
python scripts/check_repo_safety.py --history
git fsck --full --no-dangling
git diff --check
```

Local commits do not authorize push, `main` movement, or release. Implementation
cannot self-declare independent acceptance.
