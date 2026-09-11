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
"""Compatibility contract between ``idaes-pse`` and ``idaes-accel``.

The two distributions are versioned and released independently, so the binding
contract between them is a single integer, not a version range:
``idaes_accel._core.__abi_version__`` must compare **exactly equal** to
:data:`ACCEL_ABI`.

Exact equality rather than ``>=`` is deliberate. Breakage is bidirectional: a
newer ``idaes-pse`` calling into an older extension is just as wrong as an older
``idaes-pse`` calling into a newer one. Version *strings* appear only in
diagnostics; they are never used for gating, because ``packaging`` is not a
declared dependency of ``idaes-pse`` and hand-rolled version parsing is a
reliable source of subtle bugs.

Bump :data:`ACCEL_ABI` on any change to argument or return marshalling, to a
kernel's numeric semantics, or to an exported symbol name.
"""

ACCEL_ABI = 1
"""Required value of ``idaes_accel._core.__abi_version__``."""

ACCEL_DIST = "idaes-accel"
"""Distribution name, used for metadata lookup in diagnostics."""

ACCEL_MODULE = "idaes_accel._core"
"""Module imported by name so static analysers do not require it to be present."""
