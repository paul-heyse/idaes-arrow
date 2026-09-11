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
"""Registration of Python-versus-Rust parity cases.

Deliberately free of any test-framework or array-library import, so it ships in
the wheel and downstream projects can register cases for their own accelerated
functions.

A case declares how to build its arguments rather than holding them, so fixtures
are constructed fresh per test and cannot leak mutation between the two
implementations under comparison.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

TIERS = ("unit", "component", "integration")


@dataclass(frozen=True)
class ParityCase:
    """One comparison of a pure-Python implementation against its Rust twin."""

    key: str
    """Registry key, as passed to :func:`idaes.accel.accelerate`."""

    id: str
    """Unique, stable pytest parameter id."""

    make_args: Callable[[], Tuple[tuple, dict]]
    """Builds ``(args, kwargs)``. Called once per test, never shared."""

    tier: str = "unit"
    """Which required marker the generated test carries."""

    compare: Optional[Callable] = None
    """Override comparator; defaults to type-directed comparison."""

    requires: Tuple[str, ...] = ()
    """Module names that must be importable, else the case skips."""

    rtol: float = 0.0
    atol: float = 0.0
    """Tolerances. Zero means bit-exact, which is the default on purpose."""

    raises: bool = False
    """Expect *both* implementations to raise, and compare the exception types.

    Without this the harness calls the Python implementation unguarded, so a case
    whose Python side raises errors the test rather than comparing anything --
    meaning exception parity could not be expressed at all. Type equality is what
    is compared, not the message: callers write ``except SomeError``, and a port
    that swaps the class silently stops being caught.
    """

    note: str = ""
    """Why a loosened tolerance is acceptable. Required whenever one is set."""


_CASES: List[ParityCase] = []


def register(case: ParityCase) -> ParityCase:
    """Add a case, rejecting silently-loosened tolerances."""
    if case.tier not in TIERS:
        raise ValueError(f"{case.id}: tier must be one of {TIERS}, got {case.tier!r}")
    if (case.rtol or case.atol) and not case.note:
        raise ValueError(
            f"{case.id}: a non-zero tolerance needs a `note` justifying it. "
            "Bit-exact is the default because users baseline these results.",
        )
    if any(existing.id == case.id for existing in _CASES):
        raise KeyError(f"duplicate parity case id {case.id!r}")
    _CASES.append(case)
    return case


def cases(tier: Optional[str] = None) -> List[ParityCase]:
    """Registered cases, optionally filtered to one tier."""
    return [c for c in _CASES if tier is None or c.tier == tier]
