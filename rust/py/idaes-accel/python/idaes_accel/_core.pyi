# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026 Paul Heyse.
# Part of a fork of the IDAES Integrated Platform (IDAES IP);
# see LICENSE.md and COPYRIGHT.md at the repository root.
"""Type stubs for the compiled ``idaes_accel._core`` module.

Exported symbol names are registry keys with ``.`` replaced by ``__`` so that
``idaes.accel`` can resolve them mechanically from the key alone.
"""

__abi_version__: int
__version__: str

def pysmo__sampling__prime_number_generator(n: int) -> list[int]:
    """Return the first ``n`` primes; empty for ``n <= 0``."""
