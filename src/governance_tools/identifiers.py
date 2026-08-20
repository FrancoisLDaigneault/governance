"""Validation for repository and organization identifiers."""

import re

# A repository name is substituted into `repos/{repo}/...` path templates, and
# HTTP clients normalize `..` segments: an unvalidated name such as
# `../../orgs/acme` would aim a corrective write at a different endpoint.
_REPO_RE = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")
# An organization login carries no slash and no dot, so it can never be mistaken
# for OWNER/REPO and can never climb out of an `orgs/{org}/...` template.
_ORG_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?")


def is_valid_repo(repo: str) -> bool:
    """True for a plain OWNER/REPO identifier, with no path traversal."""
    return _REPO_RE.fullmatch(repo) is not None


def is_valid_org(org: str) -> bool:
    """True for a bare organization login, with no slash and no path traversal."""
    return _ORG_RE.fullmatch(org) is not None
