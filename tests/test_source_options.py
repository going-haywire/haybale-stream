"""The Source dropdown: refresh queries the selected backend, options show what it found; Syphon's run loop."""

import types

import pytest
from haybale_stream.backends import sources
from haybale_stream.nodes import run_loop, settings


@pytest.fixture
def found(monkeypatch):
    """What a query on each backend finds."""
    network = {"ndi": ["HOST (ndi-out)"], "omt": ["HOST (omt-out)"], "syphon": ["App | Out"]}
    monkeypatch.setattr(sources, "_found", {})
    for key, backend in sources.BACKENDS.items():
        monkeypatch.setattr(backend, "is_available", classmethod(lambda cls: True))
        monkeypatch.setattr(backend, "discover", classmethod(lambda cls, wait=0.0, k=key: list(network[k])))
    monkeypatch.setattr(settings, "ensure_main_run_loop", lambda key: None)
    return network


def test_options_never_query_and_refresh_does(found):
    bag = types.SimpleNamespace(backend="syphon")
    assert settings.source_options(bag) == []  # nothing asked for yet
    assert settings.find_source_options(bag) == ["App | Out"]
    assert settings.source_options(bag) == ["App | Out"]  # what the refresh found
    found["syphon"].append("App | Late")
    assert settings.source_options(bag) == ["App | Out"]  # until the next refresh


def test_sources_follow_the_selected_backend(found):
    bag = types.SimpleNamespace(backend="syphon")
    settings.find_source_options(bag)
    bag.backend = "ndi"
    assert settings.source_options(bag) == []
    assert settings.find_source_options(bag) == ["HOST (ndi-out)"]


def test_without_a_bag_every_backend_found_is_listed(found):
    # A framework that calls options() bare still gets a usable list.
    for key in ("ndi", "omt", "syphon"):
        sources.find_sources(key)
    assert settings.source_options() == ["HOST (ndi-out)", "HOST (omt-out)", "App | Out"]


def test_a_failing_query_keeps_the_last_list(found, monkeypatch):
    sources.find_sources("ndi")

    def boom(cls, wait=0.0):
        raise RuntimeError("network down")

    monkeypatch.setattr(sources.BACKENDS["ndi"], "discover", classmethod(boom))
    assert sources.find_sources("ndi") == ["HOST (ndi-out)"]


def test_audio_sources_follow_the_selected_backend(found):
    bag = types.SimpleNamespace(backend="omt")
    assert settings.find_audio_source_options(bag) == ["HOST (omt-out)"]
    assert settings.audio_source_options(bag) == ["HOST (omt-out)"]
    assert settings.audio_source_options() == ["HOST (omt-out)"]


def test_the_run_loop_pump_starts_only_for_syphon(monkeypatch):
    scheduled = []
    loop = types.SimpleNamespace(is_running=lambda: True, call_soon_threadsafe=scheduled.append)
    monkeypatch.setattr("nicegui.core.loop", loop)
    monkeypatch.setattr(run_loop.sys, "platform", "darwin")
    monkeypatch.setattr(run_loop, "_started", False)
    monkeypatch.setattr(
        "haybale_stream.backends.syphon.SyphonBackend.is_available", classmethod(lambda cls: True)
    )

    run_loop.ensure_main_run_loop("ndi")
    assert scheduled == []

    run_loop.ensure_main_run_loop("syphon")
    run_loop.ensure_main_run_loop("syphon")
    assert len(scheduled) == 1  # once per process


def test_the_run_loop_pump_waits_for_the_app_loop(monkeypatch):
    monkeypatch.setattr("nicegui.core.loop", None)
    monkeypatch.setattr(run_loop.sys, "platform", "darwin")
    monkeypatch.setattr(run_loop, "_started", False)
    run_loop.ensure_main_run_loop("syphon")
    assert run_loop._started is False  # tried again on the next call
