#!/usr/bin/env python3
"""
Build the file -> owning-document ledger for the authoritative_design set.

Every source module and every shipped asset is assigned to exactly one document.
Assignment is by ordered rules, first match wins, so the mapping is reproducible
and reviewable rather than a hand-maintained list of 600+ rows.

Test modules are owned as a class by document 32 and are not enumerated here;
the ledger covers the 465 source modules and 179 assets that the per-subsystem
documents are accountable for.

Usage:
    python _scripts/ledger.py            # write _generated/ledger.csv, report gaps
    python _scripts/ledger.py --check    # exit non-zero if the mapping is not total
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

# Ordered (regex, doc-id) rules. First match wins.
RULES: list[tuple[str, str]] = [
    # ---- 32: repository engineering (tests owned as a class) --------------
    (r"^idaes/conftest\.py$", "32"),
    (r"^idaes/tests/", "32"),
    (r"/tests/", "32"),

    # ---- 02: runtime platform, configuration, logging, CLI ---------------
    (r"^idaes/(__init__|config|logger|beta)\.py$", "02"),
    (r"^idaes/core/__init__\.py$", "02"),
    (r"^idaes/commands/", "02"),

    # ---- 04: control volume framework (before 03's core/base catch) ------
    (r"^idaes/core/base/(extended_)?control_volume", "04"),

    # ---- 05: property and reaction framework -----------------------------
    (r"^idaes/core/base/(property_base|reaction_base|property_meta|property_set|phases|components)\.py$", "05"),

    # ---- 17: costing (costing_base lives with its implementations) -------
    (r"^idaes/core/base/costing_base\.py$", "17"),
    (r"^idaes/core/base/location_factors\.json$", "17"),
    (r"^idaes/models/costing/", "17"),
    (r"^idaes/models_extra/power_generation/costing/", "17"),
    (r"^idaes/models_extra/temperature_swing_adsorption/costing/", "17"),

    # ---- 03: block hierarchy and construction protocol -------------------
    (r"^idaes/core/base/", "03"),

    # ---- 06: initializers and scalers ------------------------------------
    (r"^idaes/core/initialization/", "06"),
    (r"^idaes/core/scaling/", "06"),
    (r"^idaes/core/util/(scaling|initialization)\.py$", "06"),

    # ---- 30: numerics and solver interface -------------------------------
    (r"^idaes/core/solvers/", "30"),

    # ---- 07: diagnostics and run orchestration ---------------------------
    (r"^idaes/core/util/(diagnostics_tools|convergence|structfs)/", "07"),
    (r"^idaes/core/util/(parameter_sweep|performance|model_diagnostics)\.py$", "07"),

    # ---- 09: surrogate subsystem -----------------------------------------
    (r"^idaes/core/surrogate/", "09"),

    # ---- 08: remaining core utilities, plugins, tombstones ---------------
    (r"^idaes/core/util/", "08"),
    (r"^idaes/core/plugins/", "08"),
    (r"^idaes/core/dmf/", "08"),
    (r"^idaes/core/datasets\.py$", "08"),
    (r"^idaes/core/io/", "08"),

    # ---- 10: control-volume-based unit models ----------------------------
    (r"^idaes/models/unit_models/(heater|heat_exchanger|heat_exchanger_1D|heat_exchanger_ntu|"
     r"heat_exchanger_lc|shell_and_tube_1d|pressure_changer|valve|pipe|cstr|plug_flow_reactor|"
     r"stoichiometric_reactor|equilibrium_reactor|gibbs_reactor|flash|feed|feed_flash|product)\.py$", "10"),

    # ---- 11: network / contactor unit models and control -----------------
    (r"^idaes/models/unit_models/(mixer|separator|translator|statejunction|stream_scaler|"
     r"mscontactor|skeleton_model|__init__)\.py$", "11"),
    (r"^idaes/models/unit_models/solid_liquid/", "11"),
    (r"^idaes/models/unit_models/icons/", "11"),
    (r"^idaes/models/control/", "11"),

    # ---- 12-16: property packages ----------------------------------------
    (r"^idaes/models/properties/modular_properties/base/", "12"),
    (r"^idaes/models/properties/modular_properties/(eos|phase_equil|reactions)/", "13"),
    (r"^idaes/models/properties/modular_properties/(state_definitions|pure|transport_properties)/", "14"),
    (r"^idaes/models/properties/modular_properties/(examples|coolprop)/", "15"),
    (r"^idaes/models/properties/modular_properties/__init__\.py$", "15"),
    (r"^idaes/models/properties/(activity_coeff_models|examples|interrogator)/", "15"),
    (r"^idaes/models/properties/(general_helmholtz|helmholtz)/", "16"),
    (r"^idaes/models/properties/(iapws95|swco2)\.py$", "16"),
    (r"^idaes/models/properties/__init__\.py$", "16"),

    # ---- 24: shipped flowsheets (before family rules) --------------------
    (r"^idaes/models/flowsheets/", "24"),
    (r"^idaes/models_extra/power_generation/flowsheets/", "24"),
    (r"^idaes/models_extra/gas_solid_contactors/flowsheets/", "24"),

    # ---- 20: Helmholtz steam-cycle units and solid oxide cells -----------
    (r"^idaes/models_extra/power_generation/unit_models/(helm|soc_submodels)/", "20"),
    (r"^idaes/models_extra/power_generation/unit_models/soec_design\.py$", "20"),

    # ---- 19: cross-flow / auxiliary heat exchangers and PG properties ----
    (r"^idaes/models_extra/power_generation/unit_models/(cross_flow_heat_exchanger_1D|heater_1D|"
     r"heat_exchanger_common|heat_exchanger_3streams|feedwater_heater_0D|feedwater_heater_0D_dynamic|"
     r"cpu)\.py$", "19"),
    (r"^idaes/models_extra/power_generation/properties/", "19"),

    # ---- 18: boiler island (remaining PG unit models) --------------------
    (r"^idaes/models_extra/power_generation/unit_models/", "18"),
    (r"^idaes/models_extra/power_generation/__init__\.py$", "18"),

    # ---- 21-23: remaining extended libraries -----------------------------
    (r"^idaes/models_extra/column_models/", "21"),
    (r"^idaes/models_extra/gas_solid_contactors/", "22"),
    (r"^idaes/models_extra/temperature_swing_adsorption/", "23"),
    (r"^idaes/models_extra/gas_distribution/", "23"),
    (r"^idaes/models_extra/co2_capture_and_utilization/", "23"),

    # ---- 25-27: applications ---------------------------------------------
    (r"^idaes/apps/grid_integration/", "25"),
    (r"^idaes/apps/matopt/", "26"),
    (r"^idaes/apps/(caprese|nmpc|uncertainty_propagation)/", "27"),

    # ---- namespace package markers ---------------------------------------
    # All three are zero-byte files. Document 02 owns the package namespace
    # story, so the empty top-level markers belong with it.
    (r"^idaes/(apps|models|models_extra)/__init__\.py$", "02"),
]

COMPILED = [(re.compile(pattern), doc) for pattern, doc in RULES]

DOC_TITLES = {
    "01": "01_glossary_and_conventions",
    "02": "02_runtime_platform_and_cli",
    "03": "03_block_hierarchy_and_construction_protocol",
    "04": "04_control_volume_framework",
    "05": "05_property_and_reaction_framework",
    "06": "06_model_preparation_initializers_and_scalers",
    "07": "07_diagnostics_and_run_orchestration",
    # Document 08 exceeded the length cap and took the pre-approved split. The
    # ledger keeps one id per file, so its rows name the first half; both halves
    # are listed in verify.py's PLANNED set and in document 00.
    "08": "08a_model_introspection_and_persistence",
    "09": "09_surrogate_subsystem",
    "10": "10_unit_models_control_volume_based",
    "11": "11_unit_models_network_contactors_and_control",
    "12": "12_modular_properties_generic_framework",
    "13": "13_modular_properties_eos_and_phase_equilibrium",
    "14": "14_modular_properties_state_definitions_and_libraries",
    "15": "15_property_package_catalog",
    "16": "16_general_helmholtz_property_system",
    "17": "17_costing_framework_and_libraries",
    "18": "18_power_generation_boiler_island",
    "19": "19_power_generation_heat_exchangers_and_properties",
    "20": "20_power_generation_helmholtz_units_and_soc",
    "21": "21_column_models_and_solvent_systems",
    "22": "22_gas_solid_contactors",
    "23": "23_tsa_gas_distribution_and_ccu",
    "24": "24_reference_flowsheets_and_demonstrations",
    "25": "25_grid_integration",
    "26": "26_matopt",
    "27": "27_dynamic_optimization_and_uncertainty",
    "30": "30_numerics_and_solver_interface_map",
    "32": "32_repository_engineering",
}


def assign(path: str) -> tuple[str, str]:
    for rx, doc in COMPILED:
        if rx.search(path):
            return doc, rx.pattern
    return "", ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--generated", default=str(Path(__file__).resolve().parents[1] / "_generated"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    gen = Path(args.generated)
    modules = list(csv.DictReader((gen / "modules.csv").open(encoding="utf-8")))
    assets = list(csv.DictReader((gen / "assets.csv").open(encoding="utf-8")))

    rows: list[dict] = []
    unassigned: list[str] = []

    for m in modules:
        doc, rule = assign(m["file"])
        if not doc:
            unassigned.append(m["file"])
            continue
        rows.append({
            "file": m["file"], "kind": "module", "role": m["role"],
            "loc": m["loc"], "bytes": "", "doc": doc,
            "doc_file": DOC_TITLES.get(doc, "") + ".md", "rule": rule,
        })

    for a in assets:
        doc, rule = assign(a["file"])
        if not doc:
            unassigned.append(a["file"])
            continue
        rows.append({
            "file": a["file"], "kind": "asset", "role": "test" if a["in_tests"] == "True" else "source",
            "loc": "", "bytes": a["bytes"], "doc": doc,
            "doc_file": DOC_TITLES.get(doc, "") + ".md", "rule": rule,
        })

    rows.sort(key=lambda r: (r["doc"], r["file"]))
    with (gen / "ledger.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "kind", "role", "loc", "bytes", "doc", "doc_file", "rule"])
        w.writeheader()
        w.writerows(rows)

    src = [r for r in rows if r["role"] == "source"]
    per_doc = Counter(r["doc"] for r in src)
    loc_per_doc = Counter()
    for r in src:
        if r["kind"] == "module":
            loc_per_doc[r["doc"]] += int(r["loc"])

    print(f"ledger rows: {len(rows)}  (source: {len(src)}, test-owned: {len(rows) - len(src)})")
    print(f"unassigned: {len(unassigned)}")
    for f in unassigned:
        print("  UNASSIGNED " + f)
    print()
    print(f"{'doc':<4} {'files':>6} {'LOC':>8}  document")
    for doc in sorted(per_doc):
        print(f"{doc:<4} {per_doc[doc]:>6} {loc_per_doc[doc]:>8}  {DOC_TITLES.get(doc, '?')}")

    if args.check and unassigned:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
