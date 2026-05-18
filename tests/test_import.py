"""Sanity tests: public surface and plugin registration."""

import ovos_messagebus_chat_plugin as pkg


def test_public_class_exported():
    assert hasattr(pkg, "OVOSMessagebusChatAgent")


def test_no_legacy_solver_class_exported():
    """This is a fresh package — no QuestionSolver baggage."""
    assert not hasattr(pkg, "OVOSMessagebusSolver")
    assert not hasattr(pkg, "QuestionSolver")


def test_version_string():
    assert isinstance(pkg.__version__, str)
    assert pkg.__version__.split(".")[0].isdigit()


def test_is_chat_engine_subclass():
    from ovos_plugin_manager.templates.agents import ChatEngine
    assert issubclass(pkg.OVOSMessagebusChatAgent, ChatEngine)


def test_entry_point_registered():
    """Discoverable via opm.agents.chat — not under any solver group."""
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        from importlib_metadata import entry_points  # type: ignore

    eps = entry_points()
    group = eps.select(group="opm.agents.chat") if hasattr(eps, "select") \
        else eps.get("opm.agents.chat", [])
    names = {ep.name for ep in group}
    assert "ovos-messagebus" in names
