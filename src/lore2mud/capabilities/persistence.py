"""Isolated checkpoint helpers for capability-enabled simulation and replay."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Iterator

from lore2mud._bounded_json import DEFAULT_JSON_READ_LIMITS, read_bounded_json
from lore2mud.application.session import GameSession
from lore2mud.capabilities.contracts import CapabilityCheckpoint
from lore2mud.capabilities.runtime import (
    CapabilityRuntimeHost,
)
from lore2mud.capabilities.serialization import (
    canonical_json_bytes,
    canonical_json_object,
    capability_value_to_document,
    fingerprint_capability_value,
    sha256_bytes,
)
from lore2mud.content.models import ContentPack
from lore2mud.engine.save import SaveLoadError, SaveLoadService


def create_capability_checkpoint(
    session: GameSession,
    pack: ContentPack,
    *,
    slot: str = "capability_checkpoint",
) -> CapabilityCheckpoint:
    """Capture a session into an isolated nested V1 save document."""
    host = session.capability_host
    if not isinstance(host, CapabilityRuntimeHost):
        raise SaveLoadError("capability runtime host is unavailable")
    with session._lock:  # noqa: SLF001 - checkpoint shares the session transaction lock
        plan = host.plan
        with _isolated_save_service(pack) as service:
            try:
                service.save(session.world, slot)
                path = service.slot_path(slot)
                raw_document = read_bounded_json(path, DEFAULT_JSON_READ_LIMITS)
            except (OSError, ValueError, SaveLoadError) as exc:
                raise SaveLoadError("capability checkpoint save failed") from exc
        save_document = canonical_json_object(raw_document)
        states = host.states
        plan_sha256 = fingerprint_capability_value(plan)
        state_sha256 = fingerprint_capability_value(states)
        save_sha256 = sha256_bytes(save_document.canonical_bytes)
        view_sha256 = fingerprint_capability_value(session.view())
        without_fingerprint = {
            "format_version": 1,
            "plan": capability_value_to_document(plan),
            "plan_sha256": plan_sha256,
            "save_document": capability_value_to_document(save_document),
            "save_sha256": save_sha256,
            "states": capability_value_to_document(states),
            "state_sha256": state_sha256,
            "seed": session.determinism.seed,
            "clock": session.determinism.clock,
            "event_sequence": session.event_sequence,
            "view_sha256": view_sha256,
        }
        fingerprint = sha256_bytes(canonical_json_bytes(without_fingerprint))
        return CapabilityCheckpoint(
            format_version=1,
            plan=plan,
            plan_sha256=plan_sha256,
            save_document=save_document,
            save_sha256=save_sha256,
            states=states,
            state_sha256=state_sha256,
            seed=session.determinism.seed,
            clock=session.determinism.clock,
            event_sequence=session.event_sequence,
            view_sha256=view_sha256,
            fingerprint=fingerprint,
        )


def restore_capability_checkpoint(
    session: GameSession,
    pack: ContentPack,
    checkpoint: CapabilityCheckpoint,
) -> None:
    """Restore a checkpoint into a session only after isolated validation."""
    host = session.capability_host
    if not isinstance(host, CapabilityRuntimeHost):
        raise SaveLoadError("capability runtime host is unavailable")
    if type(checkpoint) is not CapabilityCheckpoint or checkpoint.format_version != 1:
        raise SaveLoadError("capability checkpoint is invalid")
    if checkpoint.plan != host.plan:
        raise SaveLoadError("capability checkpoint plan does not match the session")
    if checkpoint.plan_sha256 != fingerprint_capability_value(checkpoint.plan):
        raise SaveLoadError("capability checkpoint plan hash is invalid")
    if checkpoint.state_sha256 != fingerprint_capability_value(checkpoint.states):
        raise SaveLoadError("capability checkpoint state hash is invalid")
    if checkpoint.save_sha256 != sha256_bytes(checkpoint.save_document.canonical_bytes):
        raise SaveLoadError("capability checkpoint save hash is invalid")
    if checkpoint.fingerprint != _checkpoint_fingerprint(checkpoint):
        raise SaveLoadError("capability checkpoint fingerprint is invalid")
    candidate_states = host.prepare_restore(checkpoint.states)

    with _isolated_save_service(pack) as service:
        path = service.slot_path("capability_checkpoint")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(checkpoint.save_document.canonical_bytes)
            candidate_world = service.load("capability_checkpoint")
        except (OSError, ValueError, SaveLoadError) as exc:
            raise SaveLoadError("capability checkpoint load failed") from exc

    with session._lock:  # noqa: SLF001 - checkpoint is an application transaction
        original_world = session._world  # noqa: SLF001
        original_states = host.snapshot()
        original_context = session._determinism  # noqa: SLF001
        original_context_values = (original_context.seed, original_context.clock)
        original_rng_state = session._rng.getstate()  # noqa: SLF001
        original_sequence = session._event_sequence  # noqa: SLF001
        try:
            host.restore(candidate_states)
            session._world = candidate_world  # noqa: SLF001
            object.__setattr__(session._determinism, "seed", checkpoint.seed)  # noqa: SLF001
            object.__setattr__(session._determinism, "clock", checkpoint.clock)  # noqa: SLF001
            session._rng.seed(checkpoint.seed)  # noqa: SLF001
            session._event_sequence = checkpoint.event_sequence  # noqa: SLF001
            if fingerprint_capability_value(session.view()) != checkpoint.view_sha256:
                raise SaveLoadError("capability checkpoint view hash is invalid")
        except Exception:
            session._world = original_world  # noqa: SLF001
            host.restore(original_states)
            object.__setattr__(original_context, "seed", original_context_values[0])
            object.__setattr__(original_context, "clock", original_context_values[1])
            session._determinism = original_context  # noqa: SLF001
            session._rng.setstate(original_rng_state)  # noqa: SLF001
            session._event_sequence = original_sequence  # noqa: SLF001
            raise


@contextmanager
def _isolated_save_service(pack: ContentPack) -> Iterator[SaveLoadService]:
    with tempfile.TemporaryDirectory(prefix="lore2mud-capability-checkpoint-") as root:
        yield SaveLoadService(pack, Path(root))


def _checkpoint_fingerprint(checkpoint: CapabilityCheckpoint) -> str:
    document = {
        "format_version": checkpoint.format_version,
        "plan": capability_value_to_document(checkpoint.plan),
        "plan_sha256": checkpoint.plan_sha256,
        "save_document": capability_value_to_document(checkpoint.save_document),
        "save_sha256": checkpoint.save_sha256,
        "states": capability_value_to_document(checkpoint.states),
        "state_sha256": checkpoint.state_sha256,
        "seed": checkpoint.seed,
        "clock": checkpoint.clock,
        "event_sequence": checkpoint.event_sequence,
        "view_sha256": checkpoint.view_sha256,
    }
    return sha256_bytes(canonical_json_bytes(document))
