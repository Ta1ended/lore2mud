# Forge Workbench

Forge turns an already reviewed public `CanonRegistry v1` into inspectable and
playable local artifacts. It is a repository tool, invoked with
`python -m pipeline.forge`; it does not alter the game runtime or accept raw novel
text.

## Data flow

```text
forge-workspace.json
  + inputs/canon_registry.json
  + plans/registry_inspection_plan.json
      -> artifacts/inspection_runs/inspection-<run>-<fingerprint>.json
  + plans/registry_adaptation_plan.json
      -> artifacts/adaptation_runs/content-pack-<run>-<fingerprint>/
  + .forge/state.json
      -> input fingerprints, current outputs, attempts, and failure reasons
```

Forge reuses the existing strict CanonRegistry, registry-inspection, registry-
adaptation, and content-pack validators. It does not infer entity identity, resolve
claim conflicts, search by display name, or author game-facing plan content.

## Create and run

Create a workspace from the public fictional template:

```powershell
python -m pipeline.forge init ..\forge-demo --template examples\forge_workbench
python -m pipeline.forge status ..\forge-demo
python -m pipeline.forge run ..\forge-demo
python -m pipeline.forge check ..\forge-demo
```

`status` is read-only and returns zero for every structurally readable workspace.
`check` prints the same report but returns zero only when both stages are `CURRENT`.
Pass `--json` to either command for machine-readable output.

An ordinary `run` resumes work: it skips a stage when its inputs and last successful
output hashes are unchanged. A forced rerun always creates a new immutable output:

```powershell
python -m pipeline.forge rerun ..\forge-demo --stage adaptation
```

The prior successful directory remains available. If a later attempt fails,
`.forge/state.json` records the reason while retaining the previous success record.

## Status model

- `READY`: valid inputs exist and the stage has not run.
- `CURRENT`: input fingerprints and last successful output hashes match.
- `STALE`: inputs changed or a successful output was removed or modified.
- `FAILED`: the last attempt failed for the current input fingerprint.
- `BLOCKED`: an input is missing, unsafe, malformed, or semantically incompatible.

The state file is tool-owned. Edit plans or registry inputs, then use `run`; do not
hand-edit `.forge/state.json` or generated artifacts.

## Safety boundary

All manifest paths must be normalized, forward-slash, workspace-relative paths.
Forge rejects path traversal, input hardlink aliases, symbolic links in managed
paths, Windows junctions and other reparse points, unsafe template entries, and
concurrent runs of the same workspace. State output records must remain under the
run root for their stage. State publication uses a same-directory temporary file,
`flush`, `fsync`, and atomic replace. Stage outputs use unique run paths, so reruns
never overwrite known-good artifacts. Forge recomputes each stage's input
fingerprint after publishing; if inputs changed during execution, it removes only
that invocation's new output and records the attempt as failed.

The checked-in example is entirely fictional. Private novel text, summaries, canon,
extractions, indexes, databases, model files, and derived private content remain
outside the public repository and outside Forge test inputs.

## V1 boundary

V1 starts at an explicitly reviewed `CanonRegistry`. Upstream chapter splitting,
candidate extraction, human fact review, and draft promotion remain separate tools.
This keeps the first workbench loop real and runnable without pretending automated
review decisions exist. Later Forge work can add upstream adapters while preserving
the workspace and stage-state contracts.
