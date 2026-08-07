"""Generic Web projection for the shared authoring service."""

from __future__ import annotations

from typing import cast

from lore2mud._bounded_json import BoundedJsonError, JsonReadErrorCode
from lore2mud.authoring.contracts import (
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    DiagnosticSeverity,
)
from lore2mud.authoring.sdk import AgentAuthoringSDK
from lore2mud.authoring.serialization import (
    AuthoringDocumentTraversalError,
    InvalidUnicodeScalarError,
    authoring_result_to_document,
    validate_unicode_scalars,
)
from lore2mud.authoring.service import AuthoringService


class AuthoringWebTransport:
    """Dispatch bounded JSON requests without introducing Web-specific rules."""

    def __init__(self, service: AuthoringService | None = None) -> None:
        self._sdk = AgentAuthoringSDK(service if service is not None else AuthoringService())

    def dispatch(self, request: object) -> dict[str, object]:
        try:
            validate_unicode_scalars(request)
            if type(request) is not dict or not all(type(key) is str for key in request):
                raise ValueError("request must be an object")
            data = cast(dict[str, object], request)
            operation = data.get("operation")
            if type(operation) is not str:
                raise ValueError("request.operation is invalid")
            if operation == "validate_provenance":
                _exact_keys(data, {"operation", "manifest"})
                result = self._sdk.validate_provenance_document(data["manifest"])
            elif operation == "validate_anchors":
                _exact_keys(data, {"operation", "request"})
                result = self._sdk.validate_anchor_migrations_document(data["request"])
            elif operation == "seal":
                _exact_keys(data, {"operation", "request"})
                result = self._sdk.seal_document(data["request"])
            else:
                return _document(_rejected("web_transport"))
        except InvalidUnicodeScalarError:
            return _document(_bounded_rejection("web_transport", JsonReadErrorCode.TOO_COMPLEX))
        except AuthoringDocumentTraversalError:
            return _document(_bounded_rejection("web_transport", JsonReadErrorCode.TOO_COMPLEX))
        except BoundedJsonError as exc:
            return _document(_bounded_rejection("web_transport", exc.code))
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _document(_rejected("web_transport"))
        return _document(cast(AuthoringResult[object], result))


def _document(result: AuthoringResult[object]) -> dict[str, object]:
    value = authoring_result_to_document(result)
    if type(value) is not dict:
        raise TypeError("authoring result must be a JSON object")
    return cast(dict[str, object], value)


def _rejected(operation: str) -> AuthoringResult[object]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=(
            AuthoringDiagnostic(
                stage=AuthoringStage.SERIALIZATION,
                code="authoring_input_invalid_json",
                severity=DiagnosticSeverity.ERROR,
                artifact_id="web_request",
                json_pointer="/",
                source_span=None,
                message="The authoring Web request is invalid.",
                remediation="Provide one bounded JSON request for a supported operation.",
            ),
        ),
        exit_code=1,
    )


def _bounded_rejection(
    operation: str,
    code: JsonReadErrorCode,
) -> AuthoringResult[object]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=(
            AuthoringDiagnostic(
                stage=AuthoringStage.SERIALIZATION,
                code=f"authoring_input_{code.value}",
                severity=DiagnosticSeverity.ERROR,
                artifact_id="web_request",
                json_pointer="/",
                source_span=None,
                message="The authoring Web request could not be read safely.",
                remediation="Provide one bounded UTF-8 JSON request within the documented limits.",
            ),
        ),
        exit_code=1,
    )


def _exact_keys(data: dict[str, object], expected: set[str]) -> None:
    if set(data) != expected:
        raise ValueError("request fields are invalid")
