"""Policy model (FR-G06, ADR-011)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentic_sdlc.policy.evaluator import PolicyInput


class Outcome(StrEnum):
    PASS = "PASS"  # noqa: S105 - an outcome label, not a credential
    FAIL = "FAIL"
    EXCEPTION_REQUESTED = "EXCEPTION-REQUESTED"
    NOT_APPLICABLE = "NOT-APPLICABLE"


Check = Callable[["PolicyInput"], tuple[Outcome, str]]


@dataclass(frozen=True)
class Policy:
    id: str
    domain: str  # security | compliance | change-control | dependencies | audit
    title: str
    mandatory: bool
    exceptionable: bool
    version: str
    check: Check
    description: str = ""

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "domain": self.domain,
            "title": self.title,
            "mandatory": self.mandatory,
            "exceptionable": self.exceptionable,
            "version": self.version,
            "description": self.description,
        }


@dataclass(frozen=True)
class PolicyEvaluation:
    policy_id: str
    policy_version: str
    outcome: Outcome
    detail: str
    mandatory: bool
    exceptionable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "outcome": self.outcome.value,
            "detail": self.detail,
            "mandatory": self.mandatory,
            "exceptionable": self.exceptionable,
        }
