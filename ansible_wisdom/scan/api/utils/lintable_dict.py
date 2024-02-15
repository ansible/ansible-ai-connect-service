"""Defines LintableDict class."""

import typing

from ansiblelint.file_utils import Lintable


class LintableDict(dict[str, typing.Any]):
    """The LintableDict class."""

    def __init__(self, lintable: Lintable) -> None:
        """Initialize LintableDict."""
        self["column"] = lintable.column
        self["fixed"] = bool(lintable.fixed)
        self["ignored"] = bool(lintable.ignored)
        self["level"] = str(lintable.level)
        self["lineNo"] = lintable.lineno
        self["matchType"] = str(lintable.match_type)
        self["message"] = str(lintable.message)
        self["position"] = str(lintable.position)
        self["rule"] = {
            "name": str(lintable.rule),
            "id": str(lintable.rule.id),
            "tags": str(lintable.rule.tags),
            "description": str(lintable.rule.description),
            "severity": str(lintable.rule.severity),
            "link": str(lintable.rule.link),
            "url": str(lintable.rule.url),
        }
        self["tag"] = str(lintable.tag)
