# V2-3 Capability Module Architecture

This document records the public boundary for the V2-3 capability-module
workstream. It is a design and implementation guide, not a release or
acceptance record. Capability previews, reports, and checkpoints remain
unsealed authoring evidence until the product and independent technical gates
explicitly close them.

## Data Flow

```text
GameProject v1 capability_requirement_ids
  -> engine-shipped CapabilityCatalog
  -> deterministic dependency/version/safety/namespace resolution
  -> ResolvedCapabilityPlan v1
  -> capability-enabled preview
  -> isolated GameSession + namespaced capability state
  -> typed capability intents, effects, events, and player-safe views
  -> simulation/replay/checkpoint evidence
  -> shared Python SDK, structured CLI, and generic Web transport
```

`World` remains the V1 gameplay authority. `GameSession` remains the single
turn coordinator and transaction boundary. A capability host may observe an
immutable context and apply validated deterministic effects in its own
namespace, but it must not receive a `World` reference or host I/O access.

## Compatibility Lane

An empty `capability_requirement_ids` tuple is the exact V2-2 path. It returns
the existing `PreviewBuild v1`, `SimulationReport v1`, and proofing artifacts
without wrappers or extra fields. Canonical bytes, fingerprints, hashes,
object types, SDK values, structured-CLI envelopes and exit behavior, Web
snapshots/action traces, and save-v9 behavior are compatibility contracts.

Capability serializers omit the capability section when its value is `None`.
They do not emit an empty or `null` section merely because the capability layer
is available.

## Capability Lane

Non-empty requirements resolve against the engine-shipped catalog before any
preview, session, state, or output is materialized. Successful results are
additive wrappers around unchanged V2-2 artifacts and bind the exact resolved
plan, namespaced state evidence, capability event/view hashes, witness replay,
and checkpoint equivalence. They are unsealed, non-distributable authoring
evidence.

Resolution and runtime rejection use the existing `AuthoringDiagnostic v1`
envelope. Stable capability codes include:

`capability_not_found`, `capability_version_unsatisfied`,
`capability_catalog_duplicate`, `capability_dependency_cycle`,
`capability_conflict`, `capability_namespace_overlap`,
`capability_safety_denied`, `capability_state_invalid`,
`capability_implementation_missing`, `capability_migration_unavailable`,
`capability_intent_invalid`, and `capability_intent_inadmissible`.

Mixed simulations execute legacy V1 intents through the existing World rules
and route capability intents through a generic host. The outer witness is
authoritative; any embedded legacy report covers only the filtered legacy-intent
subsequence. Malformed or inadmissible capability intents produce zero
transition events. Any observer, runtime, or checkpoint failure restores World,
capability state, determinism inputs, event sequence, and save-visible output.

## Client Boundary

The SDK and structured CLI call the same authoring service and must be value,
diagnostic, exit, stdout, and output-file equivalent. Web uses one generic
capability intent/view transport. Client code must not special-case
`reference_counter` or expose implementation/module paths, hidden predicates,
private state, or non-public identifiers.

## Ownership

- `src/lore2mud/capabilities/` owns descriptors, SemVer, catalog, resolution,
  runtime protocol, reference implementation, and checkpoint primitives.
- `src/lore2mud/authoring/` owns preview/report/proofing wrappers, canonical
  envelopes, SDK/CLI parity, and authoring diagnostics.
- `src/lore2mud/application/` owns the single session transaction boundary and
  compatibility projection; `World` and save core remain unchanged.
- `src/lore2mud/web/` owns generic transport and legacy-compatible rendering.

No capability-specific route, dynamic plugin loader, arbitrary code execution,
new save format, private source access, package sealing, release, or V2-4/V2-5
scope belongs in this workstream.
