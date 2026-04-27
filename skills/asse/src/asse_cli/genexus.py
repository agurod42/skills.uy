from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GeneXusState:
    """Small state bag for GeneXus web panels.

    GeneXus AJAX responses are incremental: values returned by one event become
    inputs to later events. This class stores those values by frontend field name.
    """

    values: dict[str, Any] = field(default_factory=dict)
    hiddens: dict[str, Any] = field(default_factory=dict)
    props: dict[str, Any] = field(default_factory=dict)

    def apply_response(self, response: dict[str, Any]) -> None:
        self._merge_named_items(self.values, response.get("gxValues") or [])
        self._merge_named_items(self.hiddens, response.get("gxHiddens") or [])
        self._merge_props(response.get("gxProps") or [])

    def get(self, name: str, default: Any = None) -> Any:
        if name in self.values:
            return self.values[name]
        if name in self.hiddens:
            return self.hiddens[name]
        return default

    @staticmethod
    def _merge_named_items(target: dict[str, Any], items: list[Any] | dict[str, Any]) -> None:
        if isinstance(items, dict):
            target.update(items)
            return
        for item in items:
            if isinstance(item, dict):
                target.update(item)
            elif isinstance(item, list) and len(item) >= 2 and isinstance(item[0], str):
                target[item[0]] = item[1]

    def _merge_props(self, items: list[Any]) -> None:
        for item in items:
            if isinstance(item, dict):
                self.props.update(item)


@dataclass(frozen=True)
class GeneXusEvent:
    obj_class: str
    pkg_name: str
    events: tuple[str, ...]
    parms: list[Any] = field(default_factory=list)
    grids: dict[str, Any] = field(default_factory=dict)
    hsh: list[Any] = field(default_factory=list)
    is_master_page: bool = False
    cmp_ctx: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "MPage": self.is_master_page,
            "cmpCtx": self.cmp_ctx,
            "parms": self.parms,
            "hsh": self.hsh,
            "objClass": self.obj_class,
            "pkgName": self.pkg_name,
            "events": list(self.events),
            "grids": self.grids,
        }


def values_dict(response: dict[str, Any]) -> dict[str, Any]:
    state = GeneXusState()
    state.apply_response(response)
    return state.values
