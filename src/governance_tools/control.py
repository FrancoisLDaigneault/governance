"""The checked Control value, and its per-target override resolution.

`baseline` stays the only module that turns untyped JSON into these values;
this module defines what a validated control is, so the value can carry
behaviour (per-target overrides) without crowding the parser.
"""

from dataclasses import dataclass, field, replace

JsonDict = dict[str, object]

KINDS = ("ruleset", "json", "status204")
APPLICABILITIES = ("public", "all")
SCOPES = ("repo", "org")
PLACEHOLDERS = {"repo": "{repo}", "org": "{org}"}


@dataclass(frozen=True)
class Override:
    """Per-target replacement values for one control.

    Wholesale replacement, never a merge: an override carries the full desired
    value (and corrective payload) for its target, so what governs a repository
    is always readable directly from the baseline instead of computed in
    someone's head.
    """

    desired: JsonDict | None = None
    apply_payload: JsonDict | None = None


@dataclass(frozen=True)
class Control:
    """One governed setting, of a repository (default) or of an organization."""

    id: str
    kind: str
    applicability: str
    desired: JsonDict
    apply_method: str
    apply_endpoint: str
    scope: str = "repo"
    read_endpoint: str | None = None
    projection: str | None = None
    ruleset_name: str | None = None
    apply_payload: JsonDict | None = None
    apply_preserve: str | None = None
    manual_reason: str | None = None
    na_when: str | None = None
    na_reason: str | None = None
    overrides: dict[str, Override] = field(default_factory=dict)

    def applies_to(self, visibility: str) -> bool:
        """Public-only controls need a public repo (private ones need a paid plan)."""
        return self.applicability != "public" or visibility == "public"

    @property
    def is_manual(self) -> bool:
        """True when no API call can correct this control; it audits only."""
        return self.manual_reason is not None

    @property
    def placeholder(self) -> str:
        """The template placeholder this control's endpoints must carry."""
        return PLACEHOLDERS[self.scope]

    def for_target(self, target: str) -> "Control":
        """The control as one target sees it, with any override folded in.

        Only the desired value and the corrective payload can differ per
        target: the projection and the endpoints stay shared, so an override
        can never quietly move a control to a different ruleset or endpoint.
        """
        override = self.overrides.get(target)
        if override is None:
            return self
        return replace(
            self,
            desired=self.desired if override.desired is None else override.desired,
            apply_payload=(
                self.apply_payload if override.apply_payload is None else override.apply_payload
            ),
        )
