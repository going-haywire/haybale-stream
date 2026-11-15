"""RefreshSelectWidget: the refresh button runs the query with the field's settings bag."""

import asyncio
from typing import Any, cast

import pytest
from haybale_stream.nodes.settings import ReceiveSettings
from haybale_stream.widgets.refresh_select import RefreshSelectWidget, remember_bag
from haywire.core.settings import SettingsRegistry
from haywire.ui.panel.setting_widget_model import SettingWidgetModel
from nicegui import Client, run

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _rendered(properties: dict[str, Any], bag: Any = None):
    """A RefreshSelectWidget on ``bag``'s Source cell (as the panel and a promoted port build it)."""
    bag = bag if bag is not None else ReceiveSettings(registry=SettingsRegistry())
    cell = bag._cell_for(type(bag)._settings_descriptors()["source"])
    model = SettingWidgetModel(
        field_id="source", widget_config={"properties": properties}, cell=cell, on_edit=cell.set_value
    )
    widget = RefreshSelectWidget(model)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        widget.render()
    return cast(Any, widget), bag, client


def _click_refresh(widget: Any, client: Client, monkeypatch) -> None:
    async def io_bound(fn, *args):
        return fn(*args)

    monkeypatch.setattr(run, "io_bound", io_bound)
    with client:
        asyncio.run(widget._query_options())


def test_refresh_queries_the_backend_of_the_remembered_bag(monkeypatch):
    bag = ReceiveSettings(registry=SettingsRegistry())
    bag.backend = "syphon"
    remember_bag(bag, "source")
    seen: list = []

    def query(b: Any) -> list[str]:
        seen.append(b)
        return [f"{b.backend} | Out"]

    widget, _, client = _rendered({"options": lambda b: [], "refresh": query}, bag)
    assert seen == []  # building never runs the query
    assert widget._refresh_button.props["icon"] == "refresh"

    _click_refresh(widget, client, monkeypatch)

    assert seen == [bag]
    assert widget.ui_element.options == ["syphon | Out"]
    assert "loading" not in widget._refresh_button.props


def test_an_unknown_bag_reaches_the_callables_as_none(monkeypatch):
    seen: list = []
    widget, _, _ = _rendered({"options": lambda b: seen.append(b) or ["a"], "refresh": lambda b: []})
    assert seen == [None]
    assert widget.ui_element.options == ["a"]


def test_refresh_keeps_the_current_value_listed(monkeypatch):
    bag = ReceiveSettings(registry=SettingsRegistry())
    bag.source = "App | Gone"
    remember_bag(bag, "source")
    widget, _, client = _rendered(
        {"options": lambda b: ["App | Gone"], "refresh": lambda b: ["App | New"]}, bag
    )
    _click_refresh(widget, client, monkeypatch)
    assert widget.ui_element.options == ["App | New", "App | Gone"]


def test_a_failing_refresh_keeps_the_options(monkeypatch):
    def query(b: Any) -> list[str]:
        raise RuntimeError("network down")

    widget, _, client = _rendered({"options": lambda b: ["a"], "refresh": query})
    _click_refresh(widget, client, monkeypatch)
    assert widget.ui_element.options == ["a"]


def test_the_source_setting_resolves_to_the_registered_widget(library_system):
    from haywire.ui.widget.globals import get_widget_class

    descriptor = ReceiveSettings._settings_descriptors()["source"]
    assert get_widget_class(descriptor.widget_key).__name__ == "RefreshSelectWidget"
