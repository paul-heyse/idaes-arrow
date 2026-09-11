#################################################################################
# The Institute for the Design of Advanced Energy Systems Integrated Platform
# Framework (IDAES IP) was produced under the DOE Institute for the
# Design of Advanced Energy Systems (IDAES).
#
# Copyright (c) 2018-2026 by the software owners: The Regents of the
# University of California, through Lawrence Berkeley National Laboratory,
# National Technology & Engineering Solutions of Sandia, LLC, Carnegie Mellon
# University, West Virginia University Research Corporation, et al.
# All rights reserved.  Please see the files COPYRIGHT.md and LICENSE.md
# for full copyright and license information.
#################################################################################
"""Behaviour of backend selection, independent of any accelerated function."""

import os

import pytest

from idaes.accel import _loader, status
from idaes.accel.compat import ACCEL_ABI


@pytest.mark.unit
def test_off_never_imports_the_extension():
    """``off`` must not pay the import cost, not merely ignore the result."""
    with _loader.override(mode="off") as current:
        assert current.available is False
        assert current.core is None
        assert "off" in current.reason


@pytest.mark.unit
def test_force_raises_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        _loader,
        "_probe",
        lambda mode: _loader.Status(mode, False, "simulated absence"),
    )
    with pytest.raises(_loader.AccelUnavailableError, match="simulated absence"):
        with _loader.override(mode="force"):
            pass


@pytest.mark.unit
def test_auto_falls_back_silently(monkeypatch):
    monkeypatch.setattr(
        _loader,
        "_probe",
        lambda mode: _loader.Status(mode, False, "simulated absence"),
    )
    with _loader.override(mode="auto") as current:
        assert current.available is False


@pytest.mark.unit
def test_unknown_mode_is_an_error_not_a_silent_default():
    """A typo must not masquerade as ``auto``; a CI job would believe a lie."""
    previous = os.environ.get(_loader.ENV_MODE)
    os.environ[_loader.ENV_MODE] = "on"
    try:
        with pytest.raises(ValueError, match="is not one of"):
            _loader.read_mode()
    finally:
        if previous is None:
            os.environ.pop(_loader.ENV_MODE, None)
        else:
            os.environ[_loader.ENV_MODE] = previous


@pytest.mark.unit
def test_abi_mismatch_is_rejected(monkeypatch):
    """An ABI mismatch must degrade, not crash, and must say what to install."""

    class FakeCore:  # pylint: disable=too-few-public-methods
        __abi_version__ = ACCEL_ABI + 1
        __version__ = "9.9.9"

    monkeypatch.setattr(
        _loader.importlib, "import_module", lambda name: FakeCore, raising=True
    )
    with _loader.override(mode="auto") as current:
        assert current.available is False
        assert "ABI mismatch" in current.reason
        assert str(ACCEL_ABI) in current.reason


@pytest.mark.unit
def test_disable_list_is_parsed():
    with _loader.override(mode="auto", disable=("a.b", "c.d")):
        assert _loader.disabled_keys() == frozenset({"a.b", "c.d"})


@pytest.mark.unit
def test_status_is_cached_per_mode(monkeypatch):
    calls = []

    def counting_probe(mode):
        calls.append(mode)
        return _loader.Status(mode, False, "counted")

    monkeypatch.setattr(_loader, "_probe", counting_probe)
    with _loader.override(mode="auto"):
        status()
        status()
        status()
    assert len(calls) == 1, f"probed {len(calls)} times, expected 1"
