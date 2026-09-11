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
"""Runtime selection between pure-Python and Rust implementations.

IDAES runs unchanged without the optional ``idaes-accel`` distribution. When it
is installed and its ABI matches, functions decorated with :func:`accelerate`
dispatch to Rust instead; the original Python implementation is retained, stays
reachable, and is compared against the Rust one by the parity suite.

Controlled by two environment variables:

``IDAES_ACCEL``
    ``auto`` (default) uses Rust when available and falls back silently
    otherwise; ``force`` raises if acceleration is unavailable or a symbol is
    missing; ``off`` never imports the extension.

``IDAES_ACCEL_DISABLE``
    Comma-separated registry keys to force onto the Python path -- a kill switch
    for one kernel that does not require uninstalling anything.

Example::

    from idaes.accel import accelerate


    @accelerate("pysmo.sampling.prime_number_generator")
    def _prime_number_generator(n): ...
"""

from idaes.accel._loader import (
    AccelNotImplementedError,
    AccelUnavailableError,
    Status,
    invalidate,
    is_available,
    override,
    status,
)
from idaes.accel._registry import Accelerated, accelerate, registry
from idaes.accel.compat import ACCEL_ABI

__all__ = [
    "ACCEL_ABI",
    "AccelNotImplementedError",
    "AccelUnavailableError",
    "Accelerated",
    "Status",
    "accelerate",
    "invalidate",
    "is_available",
    "override",
    "registry",
    "status",
]
