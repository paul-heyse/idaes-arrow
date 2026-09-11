# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Paul Heyse.
# Part of a fork of the IDAES Integrated Platform (IDAES IP);
# see LICENSE.md and COPYRIGHT.md at the repository root.
"""Rust acceleration for the IDAES PSE Framework.

This package is a transport layer. It is not a public API: consumers go through
``idaes.accel``, which owns backend selection, the ABI compatibility check, and
the pure-Python fallback. Import this module directly and you get no fallback.

``__abi_version__`` is the compatibility contract with ``idaes-pse`` and must
compare *exactly* equal to ``idaes.accel.compat.ACCEL_ABI``.
"""

from idaes_accel._core import __abi_version__, __version__

__all__ = ["__abi_version__", "__version__"]
