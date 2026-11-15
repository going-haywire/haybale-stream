"""Refresh Select — a dropdown with a refresh button that looks the options up on click.

A stopgap: haywire core's SelectWidget does not yet take a ``refresh`` query or hand
callables the settings bag (going-haywire/haywire#106). Once a released core does, use
``SelectWidget`` instead and drop ``remember_bag``.
"""

from __future__ import annotations

import logging
import weakref
from typing import Any

from haywire.barn.builtin.widgets import SelectWidget
from haywire.ui.widget.decorator import widget
from nicegui import run, ui

log = logging.getLogger(__name__)

_bags: weakref.WeakValueDictionary[int, Any] = weakref.WeakValueDictionary()  # id(cell) -> bag


def remember_bag(bag: Any, field: str) -> None:
    """Let a RefreshSelectWidget on ``bag``'s ``field`` hand ``bag`` to its callables.

    The released core gives a widget only the field's cell, which the settings panel and a
    promoted port share; this maps that cell back to its bag.
    """
    descriptor = type(bag)._settings_descriptors()[field]
    _bags[id(bag._cell_for(descriptor))] = bag


def _bag_for(model: Any) -> Any:
    bag = getattr(model, "settings", None)  # a core that hands widgets the bag
    if bag is not None:
        return bag
    cell = getattr(model, "data", None)  # the field's cell
    return None if cell is None else _bags.get(id(cell))


@widget(description="Dropdown with a refresh button that looks the options up on click")
class RefreshSelectWidget(SelectWidget):
    """
    Dropdown with a refresh button beside it, for lists that are slow to find.

    Config options (via ``RefreshSelectWidget.config(properties={...})``):

    - ``options`` (list, dict, or callable): The list shown when the widget is built.
      A callable gets the field's settings bag (``None`` when unknown) and should be
      fast, e.g. return what the last refresh found.
    - ``refresh`` (callable): The query the refresh button runs, off the UI thread,
      so it may block. Gets the bag like ``options``; its result becomes the list.
      The refresh button is the only update: opening the dropdown re-reads nothing.
    - ``clearable``, ``multiple``, ``new_value_mode``: as for ``SelectWidget``.

    Example::

        RefreshSelectWidget.config(
            properties={'options': known_sources, 'refresh': find_sources, 'new_value_mode': 'add-unique'}
        )
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {"options": self._call(props.get("options", [])), "value": None}
        for prop in ["clearable", "multiple", "new_value_mode"]:
            if prop in props:
                kwargs[prop] = props[prop]
        element = self.bind(ui.select(**kwargs).classes("w-full text-xs"))
        with element.add_slot("append"):
            self._refresh_button = (
                ui.button(icon="refresh").props("flat dense round size=sm").tooltip("Refresh the list")
            )
        # .stop: the click must not also open the dropdown.
        self._refresh_button.on("click.stop", self._query_options)
        return element

    def _call(self, options: Any) -> list | dict:
        if callable(options):
            options = options(_bag_for(self.port))
        # A copy: NiceGUI appends typed values to the list it is given.
        return dict(options) if isinstance(options, dict) else list(options)

    async def _query_options(self) -> None:
        """Run the ``refresh`` query off the UI thread and show what it returns."""
        button = self._refresh_button
        button.props("loading")
        try:
            options = await run.io_bound(self._call, self._config.get("properties", {}).get("refresh", []))
        except Exception:
            log.warning("RefreshSelectWidget refresh failed", exc_info=True)
            return
        finally:
            button.props(remove="loading")
        if options is not None:
            self._show_options(options)

    def _show_options(self, options: list | dict) -> None:
        """Show ``options``, keeping the current value listed (NiceGUI shows a missing one as empty)."""
        element = self.ui_element
        if element is None:
            return
        current = element.value if isinstance(element.value, list) else [element.value]
        for value in current:
            if value is None or value == "" or value in options:
                continue
            if isinstance(options, dict):
                options[value] = value
            else:
                options.append(value)
        element.set_options(options)
