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
"""Fixtures shared by the acceleration tests."""

import pytest

from idaes.accel import _loader, status


@pytest.fixture(name="require_accel")
def require_accel_fixture():
    """Skip unless the Rust backend is actually in use.

    Under ``IDAES_ACCEL=off`` -- or simply without ``idaes-accel`` installed --
    there is nothing to compare against, so parity cases skip rather than fail.
    The reason string names the cause so a CI job cannot quietly skip the entire
    suite it believed it was running.
    """
    current = status()
    if not current.available:
        pytest.skip(f"idaes-accel unavailable: {current.reason}")
    return current


@pytest.fixture(autouse=True)
def reset_accel_state():
    """Drop cached backend selection after each test."""
    yield
    _loader.invalidate()


def pytest_report_header(config):  # pylint: disable=unused-argument
    """Record which backend the run actually used, in the test report."""
    try:
        current = status()
    except Exception as exc:  # pylint: disable=broad-except
        return [f"idaes.accel: probe failed: {exc}"]
    return [
        f"idaes.accel: mode={current.mode} available={current.available} "
        f"version={current.version} abi={current.abi} reason={current.reason}"
    ]
