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
"""Discovery of the optional ``idaes-accel`` extension.

This module is intentionally stdlib-only and must never import :mod:`idaes` at
module scope: ``idaes/__init__.py`` imports :mod:`idaes.config` and builds the
global config block, so a reverse edge would be an import cycle.

It also never imports the extension at *import* time -- only on first use. The
extension links a substantial native runtime, and making that cost unconditional
on ``import idaes`` would be a visible regression for every user who does not
have acceleration installed.
"""

import contextlib
import importlib
import importlib.metadata
import logging
import os
import sys
import threading
from dataclasses import dataclass
from types import ModuleType
from typing import Optional

from idaes.accel.compat import ACCEL_ABI, ACCEL_DIST, ACCEL_MODULE

_log = logging.getLogger(__name__)

MODE_AUTO = "auto"
MODE_FORCE = "force"
MODE_OFF = "off"
_MODES = frozenset({MODE_AUTO, MODE_FORCE, MODE_OFF})

ENV_MODE = "IDAES_ACCEL"
ENV_DISABLE = "IDAES_ACCEL_DISABLE"


class AccelUnavailableError(RuntimeError):
    """``IDAES_ACCEL=force`` was set but the extension could not be used."""


class AccelNotImplementedError(NotImplementedError):
    """``IDAES_ACCEL=force`` was set but this symbol has no Rust implementation."""


@dataclass(frozen=True)
class Status:
    """Outcome of probing for the extension.

    ``reason`` is always populated, including on success, so that diagnostics can
    report *why* a backend was chosen rather than only *which*.
    """

    mode: str
    available: bool
    reason: str
    version: Optional[str] = None
    abi: Optional[int] = None
    core: Optional[ModuleType] = None


_lock = threading.RLock()
_status: Optional[Status] = None
_generation = 0


def generation() -> int:
    """Monotonic counter bumped by :func:`invalidate`.

    Dispatchers cache their resolved callable against this value, so a single
    integer comparison tells them whether their cache is stale.
    """
    return _generation


def read_mode() -> str:
    """Return the requested mode, raising :class:`ValueError` on a typo.

    A misspelled ``IDAES_ACCEL`` silently falling back to ``auto`` would let a
    CI job believe it had exercised the Rust path when it had not.
    """
    raw = os.environ.get(ENV_MODE, MODE_AUTO).strip().lower()
    if raw not in _MODES:
        raise ValueError(
            f"{ENV_MODE}={raw!r} is not one of {sorted(_MODES)}",
        )
    return raw


def disabled_keys() -> frozenset:
    """Registry keys switched off through ``IDAES_ACCEL_DISABLE``.

    A comma-separated kill switch for one misbehaving kernel, so a single bad
    result does not require uninstalling the whole extension.
    """
    raw = os.environ.get(ENV_DISABLE, "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _probe(mode: str) -> Status:
    if mode == MODE_OFF:
        # Deliberately do not import: this keeps the cost at zero and makes
        # "does the pure-Python path still work" independently testable.
        return Status(mode, False, f"{ENV_MODE}=off")

    gil_enabled = getattr(sys, "_is_gil_enabled", None)
    if gil_enabled is not None and not gil_enabled():
        # abi3 wheels cannot be loaded by a free-threaded interpreter.
        return Status(mode, False, "free-threaded CPython cannot load an abi3 wheel")

    try:
        core = importlib.import_module(ACCEL_MODULE)
    except ImportError as exc:
        return Status(mode, False, f"{ACCEL_MODULE} is not importable: {exc}")

    abi = getattr(core, "__abi_version__", None)
    if abi != ACCEL_ABI:
        return Status(
            mode,
            False,
            f"ABI mismatch: idaes-pse requires {ACCEL_ABI}, "
            f"{ACCEL_DIST} provides {abi!r}; install a matching {ACCEL_DIST}",
            abi=abi,
        )

    try:
        version = importlib.metadata.version(ACCEL_DIST)
    except importlib.metadata.PackageNotFoundError:
        version = getattr(core, "__version__", "unknown")

    return Status(mode, True, "ok", version=version, abi=abi, core=core)


def status() -> Status:
    """Return the current :class:`Status`, probing at most once per mode.

    Raises :class:`AccelUnavailableError` when the mode is ``force`` and the
    extension is unusable. In ``auto`` the failure is logged at DEBUG and the
    caller transparently gets the pure-Python path.
    """
    global _status  # pylint: disable=global-statement
    mode = read_mode()

    cached = _status
    if cached is not None and cached.mode == mode:
        current = cached
    else:
        with _lock:
            if _status is None or _status.mode != mode:
                _status = _probe(mode)
            current = _status
        if current.available:
            _log.info(
                "idaes.accel: using %s %s (abi %s)",
                ACCEL_DIST,
                current.version,
                current.abi,
            )
        elif current.mode == MODE_AUTO:
            _log.debug("idaes.accel: pure-Python backend (%s)", current.reason)

    if current.mode == MODE_FORCE and not current.available:
        raise AccelUnavailableError(current.reason)
    return current


def is_available() -> bool:
    """Whether accelerated implementations will be used."""
    return status().available


def invalidate() -> None:
    """Drop the cached probe and bump :func:`generation`.

    Intended for tests. Production code has no reason to call this: the extension
    cannot appear or disappear inside a running interpreter.
    """
    global _status, _generation  # pylint: disable=global-statement
    with _lock:
        _status = None
        _generation += 1


@contextlib.contextmanager
def override(mode=None, disable=()):
    """Temporarily change the mode and/or disable specific registry keys.

    Test-only. Restores the previous environment and invalidates the cache on the
    way in and the way out, so no state leaks between tests.
    """
    previous_mode = os.environ.get(ENV_MODE)
    previous_disable = os.environ.get(ENV_DISABLE)
    try:
        if mode is not None:
            os.environ[ENV_MODE] = mode
        if disable:
            os.environ[ENV_DISABLE] = ",".join(disable)
        invalidate()
        yield status()
    finally:
        for name, value in ((ENV_MODE, previous_mode), (ENV_DISABLE, previous_disable)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        invalidate()
