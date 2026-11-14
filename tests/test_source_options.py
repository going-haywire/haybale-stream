"""The Source dropdown lists the senders of the selected backend; Syphon gets its run loop pumped."""

import types

import pytest
from haybale_stream.backends import sources
from haybale_stream.nodes import run_loop, settings


@pytest.fixture
def found(monkeypatch):
    """Discovery results per backend, as the background refresh would have cached them."""
    cache = {"ndi": ["HOST (ndi-out)"], "omt": ["HOST (omt-out)"], "syphon": ["App | Out"]}
    monkeypatch.setattr(sources, "cached_sources", lambda key: list(cache.get(key, [])))
    monkeypatch.setattr(settings, "cached_sources", lambda key: list(cache.get(key, [])))
    monkeypatch.setattr(
        settings, "all_cached_sources", lambda: [n for names in cache.values() for n in names]
    )
    return cache


def test_sources_follow_the_selected_backend(found):
    bag = types.SimpleNamespace(backend="syphon")
    assert settings.source_options(bag) == ["App | Out"]
    bag.backend = "ndi"
    assert settings.source_options(bag) == ["HOST (ndi-out)"]


def test_without_a_bag_every_backend_is_listed(found):
    # A framework that calls options() bare still gets a usable list.
    assert settings.source_options() == ["HOST (ndi-out)", "HOST (omt-out)", "App | Out"]


def test_audio_sources_follow_the_selected_backend(found):
    assert settings.audio_source_options(types.SimpleNamespace(backend="omt")) == ["HOST (omt-out)"]
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
