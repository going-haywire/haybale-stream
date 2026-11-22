"""The Source dropdown on core's MenuWidget: the refresh button runs the query with the field's settings bag."""

import asyncio
from typing import Any, cast

import pytest
from haybale_stream.nodes.settings import ReceiveSettings
from haywire.barn.builtin.widgets import MenuWidget
from haywire.core.settings import SettingsRegistry
from haywire.ui.panel.setting_widget_model import SettingWidgetModel
from nicegui import Client, run

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _rendered(properties: dict[str, Any], bag: Any = None):
    """A MenuWidget on ``bag``'s Source cell, given the bag as the settings panel gives it."""
    bag = bag if bag is not None else ReceiveSettings(registry=SettingsRegistry())
    cell = bag._cell_for(type(bag)._settings_descriptors()["source"])
    model = SettingWidgetModel(
        field_id="source",
        widget_config={"properties": properties},
        cell=cell,
        on_edit=cell.set_value,
        settings=bag,
    )
    widget = MenuWidget(model)
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


def test_refresh_queries_the_backend_of_the_bag(monkeypatch):
    bag = ReceiveSettings(registry=SettingsRegistry())
    bag.backend = "syphon"
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


def test_refresh_keeps_the_current_value_listed(monkeypatch):
    bag = ReceiveSettings(registry=SettingsRegistry())
    bag.source = "App | Gone"
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
    assert get_widget_class(descriptor.widget_key).__name__ == "MenuWidget"
