# Lore2MUD V2 Roadmap

The milestone order is fixed by product direction. A milestone starts only after the
prior exit is evidenced and the product owner authorizes the next scope.

## V2-0 Direction Reset

CI green, product definition, architecture RFC, code map, development model.

**Exit:** project entry clear/current state consistent/product owner approves boundaries.

## V2-1 Public Runtime Boundary

`GameSession`/`GameIntent`/`GameEvent`/`GameView`/`TurnResult`.

**Exit:** CLI and Web share one application layer; old content and saves do not regress.

## V2-2 Agent Authoring Interface

`GameBlueprint v1`, `GameProject v1`, static capability catalog, Python SDK,
structured CLI.

**Exit:** Fresh Agent can build/validate/simulate without reading or modifying `src`.

## V2-3 Capability Module Architecture

`CapabilityDescriptor`, state namespaces, predicates/effects/views/migrations.

**Exit:** reference gameplay capability can be added without modifying `World`, save
core, or client routing.

## V2-4 Novel Adaptation V2

prototype/traced/sealed modes, provenance/rights manifest, incremental chapter packages.

**Exit:** one public-safe story arc yields a traceable 30-60 minute game.

## V2-5 Alpha

nontechnical workbench, asset manifest, external playtests, packaging/security audit.

**Exit:** 3-5 external users or Agents independently complete different-genre projects.

## PLAT-1 Platform Thread

A fresh Agent, from public-safe material plus an approved `GameBlueprint`, makes no
core changes and creates a deterministic 20-30 minute game with build, validate,
simulate, Web, and save/load evidence.

The technical first path uses the existing public `urban_investigation` family. The
product sample is a new original investigation. Cultivation is the second genre.

PLAT-1 is developed incrementally across V2-1 through V2-5; no milestone may claim
the platform acceptance before the complete scenario passes independently.
