# Lore2MUD V2 Product Definition

_Status: V2-0 direction accepted and published; V2-1 local implementation candidate,
TECH/PRODUCT/publication gates separate, 2026-08-04_

## Product

Lore2MUD is an **Agent-callable novel-to-text-game engine**. It is not an Agent
and does not choose creative direction, rights policy, or release scope by itself.

The direct user is a developer Agent that calls stable authoring and runtime
interfaces. The product owner/creator supplies product decisions, creative
direction, source authorization, and acceptance. The player is the final user of
the generated text game.

The product turns public-safe or explicitly authorized story material plus an
approved design into a deterministic, inspectable, portable game package. It
supports human review at every boundary instead of treating model output as trusted.

## Operating Modes

| Mode | Purpose | Required guarantees | Typical output |
|---|---|---|---|
| `prototype` | Explore a playable interpretation quickly. | Explicit source boundary, validated structures, deterministic runtime. Not release evidence. | Mutable `GameProject v1` and non-distributable preview build. |
| `traced` | Make adaptation choices reviewable. | Provenance links, rights status, creator decisions, validation and simulation reports. | Traceable project, preview candidate, and evidence reports. |
| `sealed` | Freeze an accepted build. | Canonical inputs, hashes, capability policy, reproducible build, security and product gates. | Immutable `GamePackage v2` plus evidence manifest. |

Promotion is one-way for a particular build record: a sealed package is never
silently regenerated in place. A later change creates a new candidate.

## Inputs And Outputs

Authoring inputs:

- public-safe source material, or owner-authorized private material kept outside
  public Git;
- creator decisions: audience, genre, tone, play length, adaptation boundaries,
  acceptance criteria, and rights status;
- an approved `GameBlueprint v1`, declared capability requirements, and optional asset
  manifest; capability selection and resolution begin only in V2-3;
- validated existing artifacts such as a `NarrativeModel`, used only through an
  explicit authoring adapter.

Authoring outputs:

- `GameBlueprint v1`: portable creator intent and gameplay requirements;
- `GameProject v1`: normalized, validated build inputs and trace records;
- preview build: an unsealed, non-distributable runtime input for isolated validation
  and simulation; before V2-3 it uses only the engine-defined V1 compatibility profile,
  rejects any declared V2 capability requirement, and is never release evidence;
- `GamePackage v2`: sealed runtime data, assets, capability requirements, and hashes;
- structured build, validation, simulation, provenance, rights, and security reports.

Production runtime input is a sealed `GamePackage v2` plus a typed `GameIntent`.
During V2-2 authoring, deterministic simulation may use an isolated preview build
through the same session semantics, but it cannot mutate the caller's project or a
live player session and is not distributable. V2-2 does not ignore or resolve declared
V2 capability requirements: it emits an authoring diagnostic and blocks preview build
and simulation until V2-3. Runtime output is a deterministic `TurnResult` containing
`GameEvent` records and a player-safe `GameView`.
`CampaignSpec v1` is an authoring IR, **not** a runtime input.

The V2-1 local candidate applies these runtime contracts to the existing V1
`ContentPack`/`World` compatibility profile. It does not implement or imply a sealed
`GamePackage v2`, capability resolution, an SDK, or publication.

## Platform Acceptance: PLAT-1

A fresh developer Agent, starting from public-safe material and an approved
`GameBlueprint`, must create a deterministic 20-30 minute game **without core code
changes**, then build, validate, simulate, play it in the Web client, and save/load
the session.

The technical first path reuses the current public `urban_investigation` family.
The product sample is a new original investigation. Cultivation is the second-genre
proof, not the first product sample.

## Success Metrics

- A fresh Agent completes PLAT-1 from published contracts without reading or
  editing `src/`.
- CLI and Web produce equivalent application-layer results for the same package,
  intent sequence, seed, and clock.
- Sealed builds are byte-reproducible from recorded inputs and reject undeclared
  capabilities or invalid references before play.
- A traced build can explain the source, right, creator decision, and transformation
  behind each material story element without exposing private source text.
- By V2-5, 3-5 external users or Agents independently complete different-genre
  projects and their players can finish the resulting games.
- Existing V1 public content and supported saves do not regress during the migration.

## Non-Goals

- Building an autonomous creative Agent, chat persona, or model-hosting platform.
- Making rights decisions or granting rights to imported or generated material.
- Reading, publishing, or embedding private source material without explicit scope.
- Allowing generated code, arbitrary Python, dynamic plugins, shell commands, or
  unrestricted network access in a game package.
- Replacing deterministic rules with free-form model calls during a turn.
- Treating the existing `CampaignSpec` as a deployable game or runtime content pack.
- Breaking V1 content/save compatibility merely to make the V2 API cleaner.

## Rights And Trust Boundary

The public repository contains only generic engine/tooling work and original public
samples. Novel text, derived private adaptation data, images, indexes, saves, logs,
and owner-controlled artifacts remain outside public Git. Imported content, player
input, model output, packages, and assets are untrusted until structurally,
semantically, and rights-policy validated. The product records rights assertions;
the product owner remains responsible for their truth and for release approval.

## V2 References

- [Current code map](CODE_MAP.md)
- [Target architecture](docs/v2/architecture.md)
- [Development model](docs/v2/development_model.md)
- [Roadmap](docs/v2/roadmap.md)
