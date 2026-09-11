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
"""Binding of pure-Python implementations to their Rust counterparts."""

import functools
import inspect
from typing import Callable, Dict, Optional

from idaes.accel import _loader

_REGISTRY: Dict[str, "Accelerated"] = {}


def _symbol_for(key: str) -> str:
    """Map a registry key to its exported symbol in ``idaes_accel._core``.

    ``pysmo.sampling.foo`` -> ``pysmo__sampling__foo``. Mechanical, so nothing
    has to maintain a second table mapping one to the other.
    """
    return key.replace(".", "__")


class Accelerated:
    """A callable that prefers a Rust implementation and falls back to Python.

    Both implementations stay reachable -- :attr:`python_impl` and
    :attr:`rust_impl` -- which is what lets a single parity test compare them
    without any per-function test code.

    The resolved callable is cached alongside the loader generation as one tuple,
    so the hot path is a single attribute load and an integer compare, and the
    pair can never be observed half-updated.
    """

    def __init__(self, key: str, python_impl: Callable):
        self.key = key
        self.python_impl = python_impl
        self._cache = (-1, python_impl)
        functools.update_wrapper(self, python_impl)
        # Without this, Sphinx renders every accelerated function as
        # ``(*args, **kwargs)``: docs/conf.py sets autodoc_typehints="description",
        # which needs a resolvable signature.
        self.__signature__ = inspect.signature(python_impl)

    @property
    def rust_impl(self) -> Optional[Callable]:
        """The Rust implementation, or ``None`` if unavailable or not built."""
        current = _loader.status()
        if not current.available:
            return None
        return getattr(current.core, _symbol_for(self.key), None)

    @property
    def backend(self) -> str:
        """``"rust"`` or ``"python"`` -- whichever a call would use right now."""
        return "rust" if self._resolved() is not self.python_impl else "python"

    def _resolved(self) -> Callable:
        generation, cached = self._cache
        if generation == _loader.generation():
            return cached
        return self._resolve()

    def _resolve(self) -> Callable:
        current = _loader.status()
        chosen = None
        if current.available and self.key not in _loader.disabled_keys():
            chosen = self.rust_impl
            if chosen is None and current.mode == _loader.MODE_FORCE:
                raise _loader.AccelNotImplementedError(
                    f"{_loader.ENV_MODE}=force but {self.key!r} has no Rust "
                    f"implementation (expected {_symbol_for(self.key)!r} in "
                    f"{current.version})",
                )
        chosen = chosen or self.python_impl
        self._cache = (_loader.generation(), chosen)
        return chosen

    def __call__(self, *args, **kwargs):
        return self._resolved()(*args, **kwargs)

    def __repr__(self):
        return f"<Accelerated {self.key!r} backend={self.backend}>"


def accelerate(key: str):
    """Decorate a **module-level** pure-Python function as accelerable.

    The decorated object keeps the original function reachable, so the call site
    reads exactly as before and the Python implementation is never deleted.

    Never apply this to a method. ``self`` would be marshalled across the
    boundary as the first positional argument; extract the body to a
    module-level function and have the method delegate to it.
    """

    def decorate(python_impl):
        if inspect.isclass(python_impl):
            raise TypeError(
                f"accelerate({key!r}) wraps functions, not classes: "
                "wrapping a class breaks issubclass() and getattr-by-name lookups",
            )
        if key in _REGISTRY:
            raise KeyError(f"duplicate accel key {key!r}")
        wrapper = Accelerated(key, python_impl)
        _REGISTRY[key] = wrapper
        return wrapper

    return decorate


def registry() -> Dict[str, "Accelerated"]:
    """A copy of the registry, keyed by accel key."""
    return dict(_REGISTRY)
