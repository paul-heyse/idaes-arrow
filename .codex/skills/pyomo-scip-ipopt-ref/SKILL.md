---
name: pyomo-scip-ipopt-ref
description: "Reference navigator for Pyomo + SCIP + Ipopt — algebraic-modeling-and-solver-stack optimization. Routes three deep-dives at docs/library_ref/: pyomo.md (AML model, Vars/Constraints/Suffixes, SolverFactory + APPSI, transformations, GDP/MindtPy/PyROS/DAE/MPEC, scaling/infeasibility/QA), SCIP.md (external `SolverFactory(\"scip\")`: install, parameters, presolve/cuts/heuristics, exact MILP), ipopt_standalone.md (external `SolverFactory(\"ipopt\")`: NLP contract, mu/line-search, options incl. `ipopt.opt`, derivatives, linear solvers, warm starts). Use when code touches `import pyomo`, `SolverFactory(\"scip\"|\"ipopt\")`, `ipopt.opt`, or `.nl`/`.sol`; for algebraic modeling, NL-pipeline debugging, infeasibility, MINLP/DAE/MPEC reformulations. For SymPy (symbolic CAS, derivation, lambdify/codegen, exact arithmetic), see the sibling `sympy-ref` skill."
allowed-tools: Read, Grep, Glob, Bash
model-baseline: claude-5 (2026-08)
---

# Pyomo / SCIP / Ipopt Reference Navigator

## Version anchors

All guidance assumes the deployment baseline shared by these three documents:

* **Pyomo 6.10.x** (CPython 3.10–3.14 + PyPy supported), installed via `pip install pyomo` or `conda install -c conda-forge pyomo`. Solvers are **never** installed automatically — `ipopt`, `scip`, and friends are separate conda/pip packages.
* **SCIP 10.0.2** from `conda-forge::scip`, accessed by Pyomo as the external `scip` (≥ 8) or legacy `scipampl` (< 8) executable through Pyomo's `.nl` writer + AMPL/NL reader. SCIP's Pyomo plugin declares LP/MIP/MIQP/MIQCP/MINLP/SOS1/SOS2/indicator capability — narrower than SCIP's native plugin universe.
* **Ipopt 3.14.19** from `conda-forge::ipopt`, accessed by Pyomo as the `ipopt` executable through `.nl`/`.sol` files (and a newer `pyomo.contrib.solver.solvers.ipopt.Ipopt` interface). Linear solvers are build-dependent; conda-forge baseline is **MUMPS** + (Linux) **SPRAL**, with HSL/Pardiso runtime-loadable when builds support `hsllib`/`pardisolib`.
* Stack contract:
  `Pyomo Model → NL writer → external solver executable (.nl) → solver → .sol → Pyomo result loader → Suffix import`

If a doc snippet references a different version, treat it as version-sensitive and verify against the baseline above before adopting.

### Scope

This skill covers Pyomo algebraic modeling (`pyo.Var`, `pyo.Constraint`, `SolverFactory`, NL writer) and SCIP and Ipopt through their **external executables** via `.nl`/`.sol`. In-process bindings, custom SCIP plugins (constraint handlers, separators, branching rules), and solver callbacks are not used in this codebase and are not covered here.

**Symbolic mathematics (SymPy) is covered separately.** SymPy is a derivation aid (exact arithmetic, simplification, calculus, lambdify/codegen) whose output may be transcribed into Pyomo expressions — but Pyomo's expression DAG and SymPy's expression DAG are **different**: never pass SymPy expressions into `Constraint(rule=...)` directly. For symbolic concerns see the **`sympy-ref`** skill.

---

## How the three reference documents are organized

| Doc | Path | Lines | Top-level structure | Authoritative scope |
|-----|------|-------|---------------------|---------------------|
| **pyomo** | `docs/library_ref/pyomo.md` | 55,522 | **Upfront feature-category catalog** (lines 1-563, sections 0-41) + deep-dive expansions for §0-§40. §0-§35 use `# N)` H1 markers; §36-§40 use `## N)` H2 markers — both are deep-dives, only the heading level changes mid-document. §41 is catalog-only ("Documentation architecture for the final Pyomo guide"). Each deep-dive section repeats §N.0-§N.K subsection numbering, recipes, anti-pattern tables, deployment advisories, agent checklists, final checklists. | The full Pyomo algebraic-modeling stack: paradigms, AML object model, indexing/parameters/variables/expressions/objectives/constraints, specialized formulations (Piecewise/SOS/Indicator), suffixes/dual transport, DataPortal, classic + APPSI solver workflows, transformations (Big-M/hull/discretization), GDP/GDPopt/MindtPy/PyROS/DAE/MPEC/Network/Units, sensitivity/parmest/DoE, incidence/community detection, PyNumero, scaling/numerical conditioning, debugging/QA, deployment patterns (notebooks/CLI/HPC/containers/CI/services), and the `pyomo.contrib` ecosystem |
| **SCIP** | `docs/library_ref/SCIP.md` | 20,424 | **Upfront feature-category catalog** (lines 5-647, sections 0-20) + deep-dive expansions for §0-§19. §20 is catalog-only ("Documentation deliverable plan"). Catalog uses `## N)`; deep-dives use `# N) … — Pyomo-focused deep dive` H1 markers. Each deep-dive carries §N.0 invariant, then §N.1-§N.K, ending with anti-pattern tables, decision matrices, and "compact mental model" summaries. | SCIP from a Pyomo-deployment perspective: conda-forge installation/pinning; capability overview (MILP/MIQP/MINLP/CIP/exact MILP/PB); Pyomo↔SCIP integration map (`SolverFactory("scip")` flow, NL writer, options transport via `scip.set`, result loading, declared Pyomo-side capability); model classes that map well; core Pyomo solve syntax targeting SCIP; SCIP parameter system (`limits/time`, `limits/gap`, `display/statistics`); termination + diagnostics; presolve/cuts/heuristics/branching tuning; constraint handlers; file formats (LP/MPS/CIP/standalone shell); SCIP 10 advanced (exact MILP); performance/numerical/infeasibility playbooks; deployment; QA; comparative framing (HiGHS/IPOPT/Couenne/Bonmin/commercial) |
| **ipopt_standalone** | `docs/library_ref/ipopt_standalone.md` | 23,608 | **Upfront feature-category catalog** (lines 1-499, sections 0-23) + deep-dive expansions for §0-§22. §23 is catalog-only ("Documentation artifacts to produce from this map"). Catalog uses `# N)` H1 markers and deep-dives use `# Ipopt Advanced — Section N: …` H1 markers; sub-sections use `## N.M` notation. Each deep-dive ends with anti-pattern catalog, agent checklist, and decision tables. | Ipopt as a **standalone NLP solver invoked through Pyomo**. Coverage: install reality (conda-forge anatomy, `ipopt` vs `cyipopt`, BLAS/LAPACK, MUMPS/SPRAL/HSL/Pardiso build dependence); NLP modeling contract (`x`/`xL`/`xU`, `g(x)` ranged form, smoothness, restoration phase, scaling); algorithmic control (`mu_*`, line search/filter, KKT solve, termination); option deployment channels (Pyomo persistent, solve-local, `ipopt.opt`, `.nl` command-line, new `pyomo.contrib` interface); Pyomo integration front doors (classic + APPSI + new contrib); model-construction patterns; derivatives/Hessians; derivative checker; linear solvers; scaling/initialization/bounds; warm starts via Pyomo suffixes (`ipopt_zL_*`/`ipopt_zU_*`); solver output/log columns/termination interpretation; suffix-based result loading (duals/reduced costs); option bundles; troubleshooting (`Restoration_Failed`, `Infeasible_Problem_Detected`, NaN/Inf); best practices; performance engineering (sparse construction, mutable Param, APPSI repeated solves, BLAS threading, parallel scenarios); advanced workflows (parametric sweeps, sequential solves, homotopy, NLP-in-MINLP, DAE+Ipopt); direct interfaces outside Pyomo (TNLP/C/Fortran/Java/R/`cyipopt`); reproducibility; testing/QA |

**Reading strategy.** Find the right section in the indexes below, then read with `Read(offset=N, limit=M)`. Pyomo deep-dive sections run 700-2,000 lines; SCIP and ipopt_standalone sections run 500-1,500 lines. For cross-cutting concerns, use the unified concern matrix. For agent recipes, every deep-dive in pyomo.md/SCIP.md/ipopt_standalone.md ends with an "agent-ready" or "compact mental model" subsection — load the closing 100-200 lines of a section before drafting code.

---

## pyomo.md — section index

The file opens with a feature-category catalog (lines 1-563). Deep-dives §0-§35 use `# N) …` H1 markers; §36-§40 use `## N) …` H2 markers; §41 is catalog-only. Use the line ranges below to load just the section you need.

| § | Line | Title | Key subsections / agent value |
|---|------|-------|-------------------------------|
| **catalog** | 1-563 | All-section feature catalog (sections 0-41) | One-page route map. §41 has no deep-dive. |
| **0** | 566 | Scope, versioning, and the Pyomo mental model | §0.1 canonical definition, §0.2 LLM-agent value cases, §0.3 "supported optimization class" semantics, §0.4 problem-class capability map (LP/QP/NLP/MILP/MIQP/MINLP/SP/GDP/DAE/MPEC/CP), §0.5 version anchors, §0.6 import conventions, §0.7 component declaration standard, §0.8 model lifecycle (declare→data→transform→solve→load→analyze), §0.9 symbolic expression mental model, §0.10 transformation mental model, §0.11 solver selection mental model, §0.12 results/load semantics, §0.13 canonical solve wrapper for generated code, §0.14 component inventory baseline, §0.15 doc syntax standard, §0.16 deployment advisory, §0.17 agent anti-patterns, §0.18 mental-model compression |
| **1** | 1263 | Installation, deployment, and solver environment | §1.0 deployment invariant, §1.1 Python runtime support, §1.2 base install paths, §1.3 Cython-enabled installs, §1.4 solver installation matrix (GLPK/HiGHS/CBC/Ipopt/CPLEX/Gurobi/Xpress/SCIP/KNITRO/MAiNGO), §1.5 interface name taxonomy (legacy/direct/persistent/APPSI), §1.6 runtime solver availability probes, §1.7 minimal smoke-test model, §1.8 solver options + logs, §1.9 deployment patterns (notebook/script/batch/HPC/container/CI/service), §1.10 reproducibility manifest, §1.11 solver selection policy, §1.12 availability-and-solve utility module, §1.13 common deployment failures, §1.14 agent deployment checklist |
| **2** | 2383 | Core modeling paradigms: `ConcreteModel` vs `AbstractModel` | §2.0 paradigm compression, §2.1 decision matrix, §2.2 ConcreteModel deep, §2.3 AbstractModel deep, §2.4 `.dat` files, §2.5 `create_instance(...)` data channels, §2.6 raw dict deep syntax, §2.7 DataPortal deep syntax, §2.8 Python-native vs AMPL-style deployment, §2.9 AbstractModel mutation trap, §2.10 naming conventions, §2.11 component construction timing, §2.12 rule functions (paradigm-neutral), §2.13 data ingestion strategy, §2.14 `pyomo solve` vs `python script.py`, §2.15 safe solve wrapper, §2.16 testing patterns, §2.17 production deployment advisory |
| **3** | 3510 | Project layout and import conventions | recommended import style (`import pyomo.environ as pyo`), separating model/data/orchestration/reporting, reusable model factories, packaging Pyomo models as CLI/notebooks/libraries/services |
| **4** | 5025 | Pyomo AML object model: `Model`/`Block`/component hierarchy | core components (`ConcreteModel`/`AbstractModel`/`Block`/`Set`/`RangeSet`/`Param`/`Var`/`Objective`/`Constraint`/`ExternalFunction`/`Reference`/`SOSConstraint`), `Block` as modular submodel, naming/activation/cloning, traversal (`component_objects`/`component_data_objects`/`descend_into`), large-hierarchy patterns |
| **5** | 6283 | Sets and indexing | `Set`/`RangeSet`, virtual sets, ordered sets, `dimen`, `initialize` (lists/tuples/generators/functions/dicts), `within`/`filter`/`validate`, set algebra, sparse indexing for network/assignment models, performance for indexed constraints |
| **6** | 7507 | Parameters and data contracts | `Param(...)` syntax, indexed/scalar, `initialize`/`default`/`mutable=True`/`within`/`validate`, mutable parameters for repeated solves and parametric studies |
| **7** | 8859 | Variables, domains, bounds, initialization | `Var(...)` syntax, domains (`NonNegativeReals`/`Integers`/`Binary`), bounds (`bounds=`/`bounds=lambda` rule), initialization, `fix`/`unfix`, scaling-aware patterns |
| **8** | 10498 | Expressions and expression construction | symbolic vs numeric, expression construction, `pyo.value`, `pyo.quicksum` vs Python `sum`, `summation`, lazy and named expressions (`Expression(...)`), substitution patterns |
| **9** | 11965 | Objectives | `Objective(rule=...)`, `sense=minimize/maximize`, single active objective rule, multi-objective patterns (lexicographic/weighted/epigraph) |
| **10** | 13365 | Constraints | `Constraint(rule=...)`, equality/inequality/ranged forms, `ConstraintList`, indexed constraints, conditional construction (`Constraint.Skip`), feasibility-tolerance considerations |
| **11** | 14768 | Piecewise, SOS, and special formulation components | §11.2 `Piecewise(...)` constructor, §11.3 `pw_pts` breakpoints, §11.4 `f_rule`, §11.5 `pw_constr_type`, §11.6 `pw_repn` representation matrix, §11.7 representation selection, §11.13 `SOSConstraint`, §11.16 SOS semantics, §11.17 SOS solver compatibility, §11.18 piecewise solver compatibility, §11.21-§11.23 patterns (convex production cost, SOS2 interpolation, SOS1 choose-one) |
| **12** | 16212 | Suffixes, duals, reduced costs, slacks, warm-start metadata | §12.0 mental model, §12.2 `Suffix(...)`, §12.3 direction semantics, §12.4 component-keyed mapping, §12.6 importing constraint duals, §12.7 reduced costs, §12.8 slacks, §12.9 basis info, §12.10-§12.11 warm starts (Ipopt dual/bound multipliers), §12.12 branching priorities, §12.13 CLI suffix request path, §12.14 solver/interface compatibility, §12.15 solve-status gating, §12.16 dual validity rules, §12.17-§12.19 LP/reduced-cost/sensitivity report templates |
| **13** | 17498 | External functions and non-algebraic callbacks | `ExternalFunction`, AMPL `.so` library bridge, when external functions break NL writer derivative generation, alternatives (lookup tables, piecewise approximation, smooth surrogates) |
| **14** | 18790 | Data management and `DataPortal` | `DataPortal(...)`, accepted formats (CSV/JSON/Excel/dict/`.dat`), namespace layers, `load(...)`/`store(...)`, common data-binding pitfalls |
| **15** | 19952 | Solving models: classic `SolverFactory` workflow | `SolverFactory(name)`, `opt.solve(model, tee=True, keepfiles=True, symbolic_solver_labels=True, logfile=...)`, `opt.options[...]`, `opt.solve(..., options={...})` solve-local override, `executable=` path control, `validate=False`/`load_solutions=False` controls |
| **16** | 20997 | Results, interrogation, and reporting | `pyo.value(model.x[i])`, iterating components, accessing duals through suffixes, slacks (`lslack()`/`uslack()`), reporting (tables/pandas/JSON), avoiding stale values |
| **17** | 22517 | Model mutation and repeated solves | `ConstraintList.add(...)`, mutable Param updates, fixing/unfixing variables, bound/objective mutation, re-solving concrete instances vs rebuilding, iterative cuts/no-good/decomposition loops |
| **18** | 23643 | Persistent solvers and APPSI | classic persistent (`gurobi_persistent`/`cplex_persistent`), `set_instance`/`add_constraint`/`remove_constraint`/`update_var`, user notification responsibility, APPSI auto-persistent (Gurobi/Ipopt/CPLEX/CBC/HiGHS/MAiNGO), update-config performance tuning |
| **19** | 25032 | Model transformations and reformulation workflows | `TransformationFactory(...)`, GDP reformulations (Big-M/hull/cutting-plane/logical-to-linear), DAE discretization, network arc expansion, scaling transformation, in-place vs copy semantics, suffix/name/dual implications |
| **20** | 26569 | Generalized Disjunctive Programming: `pyomo.gdp` | `Disjunct`/`Disjunction`, indicator variables, hull vs Big-M, `bigm.use_args`, `convex_hull` transformation, logical propositions (`LogicalConstraint`) |
| **21** | 27795 | GDPopt logic-based solver | `SolverFactory("gdpopt")`, branch-and-bound for GDP, GDP-specific termination, integration with NLP subsolvers |
| **22** | 29153 | MINLP with MindtPy | `SolverFactory("mindtpy")`, OA/ECP/GBD/RegBenders algorithms, master MIP + slave NLP loops, MINLP-specific tolerances |
| **23** | 30612 | Robust optimization with PyROS | `SolverFactory("pyros")`, two-stage robust formulation, uncertainty sets, decision-rule policies, master/separation interaction |
| **24** | 32142 | Dynamic optimization with `pyomo.dae` | `ContinuousSet`, `DerivativeVar`, `Integral`, `discretize` (collocation/finite-difference), initial/boundary conditions, profile reconstruction |
| **25** | 33605 | MPEC and complementarity modeling | `pyomo.mpec`, `Complementarity` constraints, KKT modeling, bilevel-MPEC reformulation, complementarity solvers (PATH-style alternatives) |
| **26** | 35033 | Pyomo Network: `Port`, `Arc`, arc expansion, sequential decomposition | `Port`/`Arc`, `expand_arcs` transformation, sequential modular decomposition for flowsheet-style models |
| **27** | 36399 | Units handling | `pyomo.environ.units`, attaching units to variables/parameters/expressions, unit consistency checks, automatic conversion |
| **28** | 37829 | Stochastic programming and scenario workflows | scenario tree construction, `mpi-sppy`/PySP, two-stage and multi-stage formulations, EF (extensive form) vs decomposition |
| **29** | 39549 | Analysis utilities | `pyomo.contrib.analysis_utilities`, helper inventories, model-shape introspection |
| **30** | 40822 | Alternative solutions and solution pools | `pyomo.contrib.alternative_solutions`, near-optimal enumeration, no-good-cut workflows, pool inspection patterns |
| **31** | 42221 | Infeasibility diagnostics — IIS, MIS, repair explanations, production workflow | §31.4 IIS workflow, §31.5 IIS interpretation, §31.6 MIS workflow, §31.7 MIS interpretation, §31.8 guard constraints in MIS, §31.9 internal MIS mechanics, §31.10 best-practice infeasibility workflow, §31.11 automated diagnostic router, §31.12 constraint/bound relaxation pattern, §31.13 common root causes, §31.14 IIS vs MIS limitations, §31.15 logging strategy, §31.16 production manifest, §31.17 testing/QA, §31.18 deployment advisory, §31.19 anti-pattern table, §31.20 integrated template |
| **32** | 43377 | Sensitivity, parameter estimation, design of experiments | §32.1 Sensitivity Toolbox capability boundary, §32.2 `sensitivity_calculation(...)` syntax, §32.4 sIPOPT route, §32.5 `k_aug` route, §32.6 production wrapper, §32.7 validation, §32.8 `parmest` capability, §32.9-§32.14 `parmest` Experiment skeleton + objective patterns + initialization + scenario creation, §32.15-§32.20 Pyomo.DoE (FIM concepts, Experiment skeleton, DAE integration), §32.21 calibration workflow stages, §32.22 decision matrix |
| **33** | 44768 | Incidence, community detection, and structural analysis | §33.1-§33.4 incidence graph + structural/numeric Jacobian, §33.5-§33.6 adjacent components + maximum matching, §33.7 Dulmage-Mendelsohn partition, §33.8-§33.9 weakly connected components + block triangularization, §33.11 graph plotting, §33.12 community detection, §33.15 decomposition workflow, §33.16-§33.17 structural and numeric singularity debugging, §33.18 visualization workflow |
| **34** | 46050 | PyNumero and advanced nonlinear algorithm development | §34.2 PyNumero architecture, §34.3-§34.5 NLP interfaces (`PyomoNLP`/`AslNLP`/`AmplNLP`), §34.6 PyNumero ↔ Ipopt/CyIpopt, §34.7 `k_aug`/sIPOPT relationship, §34.8 linear solver interfaces, §34.9 KKT system construction, §34.10-§34.12 block vectors/matrices + MPI distribution, §34.13-§34.14 custom-algorithm patterns + interior-point building blocks, §34.15 Pyomo synchronization, §34.16 numerical safety, §34.17 block-structured decomposition |
| **35** | 47295 | Model scaling, numerical conditioning, and performance | §35.1 scaling suffixes, §35.2 `core.scale_model` workflows, §35.3 scaling factor heuristics, §35.4 scaling diagnostics, §35.5 variable bounds + numerical quality, §35.6 Big-M discipline, §35.7 bound tightening, §35.8 expression-building performance, §35.9 sparse indexing + dense cross-product avoidance, §35.10 constraint-generation performance, §35.11 solver tolerances + interpretation, §35.12 post-solve infeasibility/bound diagnostics, §35.13 large-model construction profiling, §35.14 persistent/APPSI performance path, §35.15 solver file generation + labels, §35.16 anti-patterns, §35.17 production scaling+diagnostics wrapper, §35.18 large-model build template |
| **36** | 48763 | Debugging and diagnostics (heading switches to `## N)`) | §36.2 structural inspection (`pprint`/`display`/traversal), §36.3 value safety, §36.4 constraint feasibility diagnostics, §36.5 solver log inspection (`tee`/`logfile`/`keepfiles`/symbolic labels), §36.6 status/termination handling, §36.7 units consistency, §36.8 IIS workflow, §36.9 MIS workflow, §36.10 common warnings/errors reference, §36.11 diagnostic helper module, §36.12 end-to-end harness, §36.13 failure taxonomy, §36.14-§36.15 root causes + anti-patterns, §36.16 deployment policy |
| **37** | 50125 | Testing and QA for Pyomo models | §37.1 project layout, §37.4 unit-test model factories without solving, §37.5 constraint-count + component-shape tests, §37.6 bad-data tests, §37.7 solver availability helpers + optional markers, §37.8 solve wrappers for tests, §37.9 small known-solution tests, §37.10 golden-output report tests, §37.11 infeasibility regression, §37.12 solver-independent report tests, §37.13 fixtures for solved models, §37.14 transformation/mutation QA, §37.15 numeric tolerance policy, §37.16 CI solver matrix, §37.17 `pyproject.toml`/pytest config, §37.18 artifact manifest QA, §37.19 anti-patterns |
| **38** | 51480 | Best-practice modeling patterns | explicit sets + sparse indexes, bounded variables, validate-before-build, mutable Param for repeated solves, persistent/APPSI for high-frequency updates, status-before-load, no Python conditionals on symbolic exprs, separate model/solve/report code, full sparse+bounded+validated+gated template |
| **39** | 52960 | Advanced deployment patterns | §39.1 batch studies + parametric sweeps, §39.2 `mpi4py` parallel solves, §39.3 cloud/HPC, §39.4 solver license management, §39.5 container images with solver binaries, §39.6 long-running services + persistent solvers, §39.7 reproducibility, §39.8 deployment-grade CI matrix, §39.9 anti-patterns, §39.10 deployment checklists, §39.11 implementation skeleton |
| **40** | 54488 | Extension ecosystem and related packages | §40.1-§40.3 `pyomo.contrib` role + inventory + high-value patterns, §40.4 external ecosystem (mpi-sppy/IDAES/WaterTAP), §40.5 contrib vs external decision, §40.6 dependency management for optional packages, §40.7 import design for LLM agents, §40.8 deployment patterns, §40.9 testing/CI, §40.10 citing Pyomo + subpackages |
| 41 | catalog only (line 509) | Documentation architecture for the final Pyomo guide | meta-guidance — no code, no API; skip unless you are authoring Pyomo documentation |

---

## SCIP.md — section index

The file opens with a feature-category catalog (lines 5-647). Deep-dives §0-§19 use `# N) … — Pyomo-focused deep dive` H1 markers. §20 is catalog-only. Each deep-dive opens with §N.0 invariant and ends with §N.K compact mental model.

| § | Line | Title | Key subsections / agent value |
|---|------|-------|-------------------------------|
| **catalog** | 5-647 | All-section feature catalog (sections 0-20) | One-page route map. §20 has no deep-dive. |
| **0** | 648 | Scope, versioning, and mental model | §0.1 SCIP terminology (SCIP solver / SCIP Suite / Pyomo SCIP interface), §0.2 Pyomo-deployment value case, §0.3 conda/micromamba install semantics, §0.4 version pinning, §0.5 SCIP mental model (CIP + MIP/MINLP + BCP), §0.6 Pyomo mental model (symbolic → NL → external executable → solution parse), §0.7 modern `scip` vs legacy `scipampl` resolution, §0.8 interface vs native solver capability, §0.9 solver-discovery deployment advisory, §0.10 minimal Pyomo+SCIP harness, §0.11 agent decision procedure, §0.12 compact mental model |
| **1** | 1171 | Installation, environment setup, deployment | §1.1 conda/micromamba install recipes, §1.2 conda-forge-only stack, §1.3 reproducible `environment.yml`, §1.4 locking + pinning, §1.5 shell-level verification, §1.6 Pyomo-level verification, §1.7 actual solve smoke test, §1.8 deployment artifact capture, §1.9 platform notes, §1.10 licensing notes, §1.11 failure-mode diagnostics, §1.12 installation checklist |
| **2** | 1751 | SCIP capability overview | §2.1 problem-class taxonomy (MILP/MIQP/MIQCP/MINLP/CIP/PB), §2.2 solve-process components (presolve/propagation/LP/cuts/branching/heuristics/conflict/Benders/BCP), §2.3 access modes (standalone vs Pyomo), §2.4 SCIP 10 exact mode, §2.5 floating-point vs exact decision table, §2.6 capability-to-interface routing matrix, §2.7 agent feature value cases, §2.8 minimal syntax inventory, §2.9 deployment best-practice |
| **3** | 3069 | Pyomo integration map — SCIP backend semantics | §3.0 interface identity, §3.1 main invocation surface, §3.2 executable resolution, §3.3 what Pyomo writes (`.nl`), §3.4 what SCIP receives, §3.5 options transport (`opt.options` → temporary `scip.set`), §3.6 result processing, §3.7 declared Pyomo SCIP capabilities, §3.8 NL writer controls relevant to SCIP, §3.9 file-based interface limitation (no callbacks/IIS/plugin authoring), §3.10 APPSI limitation (no current SCIP APPSI export), §3.11 interface selection matrix, §3.12 expected debugging artifacts, §3.13 common failure modes, §3.14 canonical wrapper, §3.15 minimal test harness, §3.16 compact mental model |
| **4** | 3937 | Model classes in Pyomo that map well to SCIP | §4.1 MILP / MIP, §4.2 MIQP / quadratic, §4.3 MINLP, §4.4 SOS1/SOS2, §4.5 indicator/logical, §4.6 piecewise-linear (SOS2 vs Big-M vs convex-combination), §4.7 unified model-class decision table, §4.8 agent classification utility, §4.9 SCIP capability probe, §4.10 deployment advice by model class, §4.11 minimal SCIP-friendly Pyomo template |
| **5** | 5008 | Core Pyomo solve syntax — SCIP backend | §5.0 solve-call mental model, §5.1 minimal solve, §5.2 status-checking pattern, §5.3 result loading (default vs controlled), §5.4 `keepfiles=True`, §5.5 `tee=True` + `logfile`, §5.6 persistent vs per-solve options, §5.7 SCIP time limits (`limits/time`, Pyomo `timelimit` mapping), §5.8 how Pyomo transmits SCIP options (temp `scip.set`), §5.9 canonical production wrapper, §5.10 minimal smoke-test, §5.11 solve-call option matrix, §5.12 failure-mode diagnostics |
| **6** | 5680 | SCIP parameter system and Pyomo option syntax | slash-separated keys (`limits/time`, `limits/gap`, `display/statistics`), generating parameter file from SCIP shell (`set save all_params.set`), persistent vs per-solve options, common parameter families (`presolving/`, `propagating/`, `separating/`, `heuristics/`, `branching/`, `display/`, `numerics/`, `conflict/`), SCIP-native explicit option syntax preferred over generic Pyomo kwargs |
| **7** | 6759 | Termination conditions, result interpretation, diagnostics | Pyomo termination-condition mapping from SCIP statuses (optimal/infeasible/unbounded/timeLimit/userInterrupt/etc.), `results.solver.status`, gap/objective extraction, partial-solution handling, conditional load patterns |
| **8** | 7660 | Logging, statistics, reproducibility | `tee=True`/`logfile=` plumbing, SCIP statistics tables (`display/statistics`), structured artifact capture, run reproducibility manifest |
| **9** | 8724 | Presolve, propagation, heuristics, cuts, branching | master presolve controls, aggregation, restart-after-root, implied-integrality presolver, propagation budgets, cut rounds, heuristic frequency tuning, branching rule selection — all via SCIP parameters |
| **10** | 9745 | Constraint handlers and native SCIP expressiveness — Pyomo-facing plugin boundary | what Pyomo can/cannot reach (no plugin authoring through Pyomo), explicit constraint modeling for known handlers, domain-tightening guidance, relaxation insight + cut insertion as model-level patterns |
| **11** | 10772 | File formats and standalone SCIP usage | LP/MPS/CIP/`.nl`, AMPL mode shell entry points (`scip read foo.nl optimize write solution foo.sol`), Pyomo `keepfiles=True` artifact paths, debugging via standalone SCIP shell |
| **12** | 11676 | Limits of the Pyomo SCIP interface | features the file-based `SolverFactory("scip")` path cannot reach: in-process callbacks, custom plugins/event handlers/branching rules, solution pool, fine-grained control — these are not used in this codebase |
| **13** | 12800 | Advanced SCIP 10 capabilities | numerically exact MILP mode, rational arithmetic, exact LP, certificates (`certificate/filename`/`viprcomp`), SCIP 10 implied-integrality presolver, cut-based conflict, flower inequalities, infeasibility-explanation tooling, new nonlinear interface, what's accessible from conda binaries via Pyomo |
| **14** | 13889 | Performance tuning playbook | §14.6 strong proof of optimality, §14.7 memory reduction, §14.8 aggressive presolve, §14.9 numerical stability, §14.10 nonlinear robustness, §14.11 randomization + deterministic benchmarking, §14.12 model-side performance, §14.13-§14.15 benchmark harness + profile library + diagnostics-to-action matrix, §14.16 agent tuning algorithm |
| **15** | 14944 | Numerical stability and modeling best practices | §15.1 scaling, §15.2 finite tight bounds, §15.3 integrality discipline, §15.4 nonlinear domain explicitness, §15.5 GDP-to-MIP/MINLP transformations, §15.6 piecewise transformations, §15.7 nonlinear expression handling + solver routing, §15.8 infeasibility/near-bound diagnostics, §15.9 model-quality audit harness, §15.10 SCIP guardrail options, §15.11 best-practice templates, §15.12 deployment checklist |
| **16** | 15979 | Infeasibility analysis and debugging | §16.0 mental model, §16.1 never load values blindly after infeasible termination, §16.2 Pyomo-level tools (display/`pprint`/IIS/MIS), §16.3 SCIP-level tools, §16.4-§16.9 workflows A-F (immediate Pyomo triage / relaxed solve / slack-penalty feasibility / incremental constraints / bound + Big-M inspection / cross-solver comparison), §16.10 artifacts to preserve, §16.11 standalone SCIP IIS workflow from Pyomo artifact, §16.12 end-to-end playbook, §16.13 common root causes, §16.14 debug profiles, §16.15 orchestration function |
| **17** | 17106 | Deployment patterns — Pyomo + SCIP production layout | §17.1 repository structure, §17.2 conda/micromamba env patterns, §17.3 startup executable checks, §17.4 notebooks, §17.5 CLI scripts, §17.6 batch/HPC, §17.7 containers, §17.8 Streamlit/web, §17.9 CI validation, §17.10 run artifact API, §17.11 config file pattern, §17.12 deployment-specific guidance, §17.13 security + multi-user, §17.14 failure-mode diagnostics by deployment, §17.15-§17.16 production startup + deployment checklists |
| **18** | 18323 | Testing and QA for Pyomo + SCIP | §18.1 test stack, §18.2 shared fixtures, §18.3 solver availability smoke, §18.4-§18.5 tiny MILP + MINLP smoke, §18.6-§18.9 regression tests (objective/termination/feasibility/gap), §18.10 option tests, §18.11-§18.14 failure tests (infeasible/unbounded/missing-executable/bad-parameter), §18.15 golden artifacts, §18.16 expected-termination mapping, §18.17 artifact tests, §18.18 model-output regression, §18.19 CI marker strategy, §18.20 isolation rules, §18.21 reusable solve-assertion harness, §18.22 QA matrix |
| **19** | 19658 | Comparative framing — SCIP vs alternative solvers and interfaces | §19.2 SCIP vs HiGHS, §19.3 SCIP vs IPOPT, §19.4 SCIP vs Couenne/Bonmin, §19.5 SCIP vs Gurobi/CPLEX/Xpress, §19.7 solver-by-model-class matrix, §19.8 install/deploy comparison, §19.9 agent solver-selection procedure, §19.10 multi-solver benchmark harness, §19.12 routing cheat sheet |
| 20 | catalog only (line 604) | Documentation deliverable plan | meta-guidance — no code; skip unless authoring SCIP documentation |

---

## ipopt_standalone.md — section index

The file opens with a feature-category catalog (lines 1-499). Deep-dives §0-§22 use `# Ipopt Advanced — Section N: …` H1 markers. §23 is catalog-only. Each section opens with §N.0 invariant and ends with anti-pattern catalog + final checklist.

| § | Line | Title | Key subsections / agent value |
|---|------|-------|-------------------------------|
| **catalog** | 1-499 | All-section feature catalog (sections 0-23) | One-page route map. §23 has no deep-dive. |
| **0** | 518 | Scope, versioning, Ipopt mental model | §0.0 version anchors + installed-build reality, §0.1-§0.4 what Ipopt is/is not, §0.5 local optimality + nonconvexity, §0.6 core algorithm (interior-point line-search filter), §0.7 Pyomo vs Ipopt responsibility split, §0.8 minimal canonical solve, §0.9 deployment-robust solver factory, §0.10 new Pyomo Ipopt interface, §0.11 suffix mental model (Pyomo↔Ipopt metadata channel), §0.12 scope classifier for LLM agents, §0.13 best-practice deployment, §0.14 mental-model checksum |
| **1** | 1090 | Installation and conda/micromamba environment | §1.1-§1.2 micromamba/conda env creation, §1.3 reproducible `environment.yml`, §1.4 verification matrix (shell + executable + Pyomo + options + linear solvers), §1.5 conda package anatomy (`ampl-asl`/BLAS/MUMPS/SPRAL), §1.6 `ipopt` vs `cyipopt`, §1.7 Pyomo solver wiring, §1.8 `ipopt.opt` deployment pattern, §1.9 BLAS/LAPACK considerations, §1.10 linear solver deployment, §1.11 when conda-forge is enough, §1.12 when source/custom builds required (HSL/Pardiso/MKL), §1.13 notebook/kernel failure modes, §1.14-§1.16 Windows/macOS/Linux notes, §1.17 Docker pattern, §1.18 failure-mode map, §1.19 install validator, §1.20 deployment checklist |
| **2** | 2163 | Packaging reality: "installed Ipopt" vs "all Ipopt features" | §2.1 feature-surface taxonomy, §2.2 installed-build vs documented-option universe, §2.3 conda-forge baseline, §2.4 inspecting installed build (`ipopt -=`/`--print-options`), §2.5 solver-log inspection, §2.6 runtime-loadable HSL + Pardiso (`hsllib`/`pardisolib`), §2.7 licensing implications, §2.8 capability-audit script (one-command build fingerprint), §2.9 option-surface parser, §2.10 safe option-selection pattern, §2.11 HSL deployment advisory, §2.12 Pardiso deployment advisory, §2.13 build-dependent defaults, §2.14 packaging smoke-test model, §2.15 feature-selection policy, §2.16 anti-patterns, §2.17 final checklist |
| **3** | 3001 | Core NLP modeling contract | §3.1 canonical mathematical form (`min f(x), xL≤x≤xU, gL≤g(x)≤gU`), §3.2 Pyomo `Var` → `x`/`xL`/`xU`/initial point, §3.3 Pyomo `Constraint` → `g`/`gL`/`gU`, §3.4 infinite bounds (`None` ↔ `nlp_lower_bound_inf`), §3.5 objective contract (single, scalar, smooth), §3.6 C² smoothness contract, §3.7 convex vs nonconvex behavior, §3.8 feasibility contract + infeasible starting points, §3.9 restoration phase + local infeasibility, §3.10 constraint violation output, §3.11 scaling contract (units/magnitudes/derivatives/residuals), §3.12 bound relaxation + fixed variables, §3.13 model-contract validation helper, §3.14 modeling decision table, §3.15 minimal robust Pyomo+Ipopt skeleton |
| **4** | 3913 | Algorithmic control surface | §4.1 option deployment syntax (Pyomo/solve-local/`ipopt.opt`), §4.2 barrier `mu_*` controls (`mu_init`, `mu_strategy`, `mu_oracle`, `mu_max`, `mu_min`), §4.3 line search + filter method (`alpha_min_frac`, `recalc_y`, etc.), §4.4 restoration phase controls (`max_resto_iter`, `resto_penalty_parameter`, etc.), §4.5 step calculation (primal/dual, SOC, KKT solve, multiplier steps), §4.6 desired-convergence termination (`tol`/`dual_inf_tol`/`constr_viol_tol`/`compl_inf_tol`), §4.7 acceptable-convergence secondary stopping, §4.8 time + iteration limits (`max_iter`/`max_cpu_time`/`max_wall_time`), §4.9 algorithm-state output columns (`||d||`/`alpha_pr`/`alpha_du`/`lg(mu)`/`lg(rg)`/`ls`), §4.10 deployment bundles, §4.11 anti-patterns, §4.12 decision table, §4.13 algorithm-control scaffold |
| **5** | 4821 | Option syntax and option deployment | §5.1 core option syntax, §5.2 deployment channels overview, §5.3 Channel A — Pyomo persistent (`opt.options[...]`), §5.4 Channel B — Pyomo solve-local (`opt.solve(..., options={...})`), §5.5 Channel C — `ipopt.opt` file (working-directory dependent), §5.6 option-file-only output controls, §5.7 Channel D — direct `.nl` command-line, §5.8 Channel E — `pyomo.contrib` Ipopt interface, §5.9 AMPL-style option strings, §5.10 option precedence and collision rules, §5.11 option audit + installed-build documentation |
| **6** | 5745 | Pyomo integration front doors | classic `SolverFactory("ipopt")` + `opt.options`/`solve(options=...)`, explicit `executable=`, new `pyomo.contrib.solver.solvers.ipopt.Ipopt` (config: `tee`/`working_dir`/`load_solutions`/`symbolic_solver_labels`/`time_limit`/`solver_options`), APPSI Ipopt (`appsi.solvers.Ipopt`) for repeated solves with model updates |
| **7** | 6666 | Pyomo model construction patterns for Ipopt | bounds + initialization + fixed vars, single active objective, equality/inequality/ranged constraints, mutable Param patterns, expression + derivative generation, domains (`NonNegativeReals` ok, no Integer/Binary), model sanity checks (initialized, bounded, single-objective, no undefined external functions, no nonsmooth operators) |
| **8** | 7594 | Derivatives and Hessian strategy | Pyomo NL writer derivative generation, `hessian_approximation` (`exact` vs `limited-memory` BFGS/SR1), Hessian-update modes, scaling-aware derivatives, when to use exact vs limited-memory, derivative-density vs solve-time trade-offs |
| **9** | 8580 | Derivative checker and model debugging | `derivative_test=first-order|second-order`, `derivative_test_print_all`, reading derivative-checker output, common derivative violations, NaN/Inf checks, decoupling modeling from numerical issues |
| **10** | 9790 | Linear solvers and numerical linear algebra | `linear_solver` (`mumps`/`ma27`/`ma57`/`ma77`/`ma86`/`ma97`/`pardiso`/`pardisomkl`/`spral`/`wsmp`), runtime-loadable HSL via `hsllib=`, Pardiso via `pardisolib=`, MUMPS tuning (`mumps_*`), thread-safety, BLAS/LAPACK layer interaction, runtime introspection |
| **11** | 10883 | Scaling, initialization, bound treatment | `nlp_scaling_method` (`gradient-based`/`none`/`user-scaling`), `linear_system_scaling` (`mc19`/`slack-based`/`none`), gradient-norm scaling for objective, constraint-scaling suffixes, NaN-safe initialization, `bound_push`/`bound_frac` for starting-point projection, `bound_mult_init_method` |
| **12** | 11883 | Warm starts in Pyomo + Ipopt | layer distinction (Pyomo state vs Ipopt warm-start parameters), `warm_start_init_point=yes`, `warm_start_bound_push`/`warm_start_mult_bound_push`, suffix transport (`ipopt_zL_in`/`ipopt_zU_in`/`ipopt_zL_out`/`ipopt_zU_out`/`dual`), partial seeding, file-based seeding, re-solving similar models, candidate-start builder with domain projection |
| **13** | 12785 | Solver output, logs, termination interpretation | `print_level` (0-12), iteration table columns (`iter`/`objective`/`inf_pr`/`inf_du`/`lg(mu)`/`||d||`/`lg(rg)`/`alpha_du`/`alpha_pr`/`ls`), `alpha_pr` diagnostic suffixes, `print_info_string`, status interpretation table (`Solve_Succeeded`/`Solved_To_Acceptable_Level`/`Infeasible_Problem_Detected`/`Search_Direction_Becomes_Too_Small`/`Diverging_Iterates`/`User_Requested_Stop`/`Maximum_Iterations_Exceeded`/`Maximum_CpuTime_Exceeded`/`Restoration_Failed`/`Error_In_Step_Computation`/`Invalid_Number_Detected`/`Insufficient_Memory`/`Internal_Error`), Pyomo termination-condition mapping |
| **14** | 13578 | Result loading, duals, reduced costs, suffix data | §14.2 manual-load wrapper, §14.3 constraint duals via `model.dual`, §14.4 Ipopt bound multipliers (`ipopt_zL_*`/`ipopt_zU_*`), §14.5 bound multipliers vs reduced costs, §14.6 warm-start round-trip, §14.7 suffix mechanics (direction/datatype/component mapping), §14.8 solver/interface compatibility, §14.9 APPSI Ipopt result access (primals/duals/reduced-costs/slacks), §14.10 APPSI result validity, §14.11 sign convention, §14.12-§14.13 classic vs APPSI snapshot comparison, §14.15 suffix lifecycle hazards, §14.16 dual + multiplier audit helpers, §14.17 KKT consistency checks, §14.18 result-loading policy, §14.19 anti-pattern catalog |
| **15** | 14549 | Common Ipopt option bundles | §15.2 Bundle: Debug derivatives, §15.3 Fast quiet solve, §15.4 Relaxed convergence, §15.5 Limited-memory Hessian, §15.6 MUMPS tuning, §15.7 Strict final solve, §15.8 Warm-start resolve, §15.9 Feasibility + restoration diagnostics, §15.10 NaN/Inf derivative diagnostics, §15.11 Output audit, §15.12 bundle composition rules, §15.13 option-profile registry, §15.14 profile factory + termination policy, §15.15 installed-build validation for bundles, §15.16 `ipopt.opt` equivalents, §15.17 bundle decision table |
| **16** | 15629 | Failure modes and troubleshooting | §16.1 global diagnostic preflight, §16.2 `No executable found for solver 'ipopt'`, §16.3 solver in shell but not in notebook/kernel, §16.4 option typo / unsupported option, §16.5 `Restoration_Failed`, §16.6 `Infeasible_Problem_Detected`, §16.7 `Maximum_Iterations_Exceeded`, §16.8 `Maximum_WallTime_Exceeded`/`Maximum_CpuTime_Exceeded`, §16.9 `Search_Direction_Becomes_Too_Small`, §16.10 `Error_In_Step_Computation`, §16.11 NaN/Inf in objective or constraints, §16.12 nonsmooth `abs`/`max`/`min`/conditionals, §16.13 bad scaling, §16.14 missing/poor variable initial values, §16.15 singular Jacobian / dependent equality constraints, §16.16 linear-solver memory failures, §16.17 Windows path/executable issues, §16.18 model constructible but unsolvable due to Pyomo expression logic, §16.19 unified troubleshooting decision tree, §16.20 failure-to-action matrix, §16.21 production-safe solve wrapper, §16.22 anti-patterns, §16.23 final checklist |
| **17** | 16959 | Best practices for Pyomo + Ipopt model quality | §17.1 initialize variables near feasible meaningful values, §17.2 scale objectives + constraints to similar magnitudes, §17.3 use bounds wherever physically meaningful, §17.4 avoid nonsmooth functions (reformulate), §17.5 check degrees of freedom for equality-constrained systems, §17.6 use `tee=True` before tuning, §17.7 start with defaults + tune one option family at a time, §17.8 prefer exact derivatives unless Hessians too dense/expensive, §17.9 `symbolic_solver_labels=True` for debugging, §17.10 version-control `ipopt.opt` files, §17.11 model-quality sanity checker, §17.12 residual audit after solve, §17.13 option tuning order, §17.14 production-ready solve wrapper, §17.15 best-practice matrix, §17.16 anti-pattern catalog |
| **18** | 18035 | Performance engineering | §18.1 sparse expression construction in Pyomo, §18.2 avoid Python-side repeated construction inside solve loops, §18.3 mutable `Param` for parametric studies, §18.4 reusing model instances vs rebuilding, §18.5 APPSI repeated-solve workflows, §18.6 temp file locations + working dirs, §18.7 Ipopt timer columns, §18.8 BLAS threading + conda BLAS variant control (`MKL_NUM_THREADS`/`OMP_NUM_THREADS`/`OPENBLAS_NUM_THREADS`), §18.9 multiprocessing parallel scenarios, §18.10 MPI parallel scenarios, §18.11 linear solver as first serious performance lever, §18.12 NL writer controls, §18.13 avoid expression duplication, §18.14 warm starts + continuation as performance tools, §18.15 profiling model construction time, §18.16 performance benchmark artifact contract, §18.17 anti-patterns |
| **19** | 19096 | Advanced Pyomo workflows | §19.1 parametric sweeps, §19.2 sequential solves, §19.3 homotopy / continuation, §19.4 feasibility restoration workflows, §19.5 manual warm starts, §19.6 bound tightening loops, §19.7 NLP subproblems inside decomposition methods, §19.8 NLP subproblems in GDP/MINLP algorithms, §19.9 DAE discretization + Ipopt, §19.10 external functions and compiled callbacks, §19.11 hybrid use with `cyipopt`, §19.12 advanced workflow selection, §19.13 workflow-safe solve policy, §19.14 reproducibility bundle |
| **20** | 20105 | Direct Ipopt interfaces outside Pyomo | §20.1 interface selection table, §20.2 when direct beats Pyomo, §20.3 AMPL `.nl` command-line usage, §20.4 C++ TNLP, §20.5 C, §20.6 Fortran, §20.7 Java JIpopt, §20.8 R `ipoptr`, §20.9 `cyipopt` Python wrapper, §20.10 Pyomo vs cyipopt vs direct C++ decision matrix, §20.11 derivative contract, §20.12 option deployment, §20.13 build/deployment, §20.14 memory + lifecycle, §20.15 debugging, §20.16 intermediate callback use cases, §20.17 anti-patterns, §20.18 best-practice checklist, §20.19 migration from Pyomo to direct |
| **21** | 21257 | Reproducibility and environment capture | §21.1 required run metadata, §21.2 conda/micromamba env capture, §21.3 ipopt executable + option-surface capture, §21.4 Pyomo + Python version capture, §21.5 BLAS/LAPACK + thread env capture, §21.6 linear solver capture, §21.7 random seed capture, §21.8 solver logs for benchmark cases, §21.9 result metadata capture, §21.10 solve-time capture, §21.11 model + data fingerprinting, §21.12 unified collector, §21.13 CLI capture script, §21.14 benchmark-case directory layout, §21.15 primal/dual solution artifacts, §21.16 reproducible policy with `load_solutions=False`, §21.17 option-profile reproducibility, §21.18 regression + benchmark comparison schema |
| **22** | 22363 | Testing and QA harness | §22.2 minimal availability test, §22.3 small known NLP test, §22.4 infeasible model test, §22.5 bad-derivative / nonsmooth test, §22.6 option propagation test, §22.7 warm-start suffix round-trip test, §22.8 linear solver availability test, §22.9 golden log fragments for termination messages, §22.10 model scaling + initialization regression, §22.11 model-quality helper, §22.12 residual audit utilities, §22.13 expected status/termination policy, §22.14 CI matrix (pinned + latest conda-forge), §22.15 platform-specific assertions, §22.16 slow/nightly tests, §22.17 artifact capture on failure, §22.18 regression suite inventory |
| 23 | catalog only (line 484) | Documentation artifacts to produce from this map | meta-guidance — list of recommended derived docs; skip unless authoring Ipopt documentation |

---

## Cross-document overlap matrix

This is the routing table when a topic appears in more than one document. **Authoritative source** is the doc that owns the topic; **secondary** documents may have summaries or cross-cuts. When a topic appears in multiple docs, prefer the authoritative source unless your question is specifically about another doc's perspective.

Legend: ✅ authoritative, 🔁 cross-cut/summary, — not covered.

### Pyomo modeling primitives

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| `ConcreteModel` vs `AbstractModel` | §2 ✅ | — | — | **pyomo §2** |
| `Block` and component hierarchy | §4 ✅ | — | — | **pyomo §4** |
| `Set`/`RangeSet` indexing | §5 ✅ | — | — | **pyomo §5** |
| `Param` (mutable, indexed, validated) | §6 ✅ | — | §18.3 (mutable Param for parametric) 🔁 | **pyomo §6** |
| `Var` (domains, bounds, init, fix) | §7 ✅ | §4.1 (model classes) 🔁 | §3.2, §11 (init + bounds for Ipopt) ✅ | **pyomo §7** for general; **ipopt §3 + §11** for NLP-specific bound + init discipline |
| Expressions + `quicksum` | §8 ✅ | — | §18.1 (sparse construction) 🔁 | **pyomo §8** |
| `Objective` + epigraph | §9 ✅ | — | §3.5 (single scalar smooth) ✅ | **pyomo §9** for general; **ipopt §3.5** for NLP-specific |
| `Constraint` + ranged + `ConstraintList` | §10 ✅ | — | §3.3 (ranged g) 🔁 | **pyomo §10** |
| `Piecewise` + `pw_repn` representations | §11 ✅ | §4.6 (model class), §15.6 (piecewise transform) 🔁 | — | **pyomo §11** |
| `SOSConstraint` (SOS1, SOS2) | §11 ✅ | §4.4 (SOS routing for SCIP) ✅ | — | **pyomo §11** for syntax; **SCIP §4.4** for SCIP routing |
| Indicator/logical constraints | §11 (transform) | §4.5 (linearize-or-handle decision) ✅ | — | **SCIP §4.5** for solver routing; **pyomo §11** for syntax |
| `Suffix` (duals, reduced costs, slacks) | §12 ✅ | — | §14 ✅ (Ipopt-specific bound multipliers + KKT audit) | **pyomo §12** for general suffix mechanics; **ipopt §14** for Ipopt-specific multiplier semantics |
| `ExternalFunction` | §13 ✅ | — | §19.10 (compiled callbacks) 🔁 | **pyomo §13** |
| `DataPortal` | §2.7 + §14 ✅ | — | — | **pyomo §14** |

### Solver invocation and result handling

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| `SolverFactory` mental model | §15 ✅ | §3 ✅ | §6 ✅ | **pyomo §15** for the general API; **SCIP §3** for SCIP-specific `.nl`+`scip.set` flow; **ipopt §6** for Ipopt-specific |
| `tee=True`/`logfile=`/`keepfiles=`/`symbolic_solver_labels=` | §15 ✅ | §5.4-§5.5 ✅ | §5, §13 ✅ | **pyomo §15** + per-solver chapters for solver-specific log columns |
| `opt.options[...]` persistent vs `solve(options=...)` per-call | §15 ✅ | §5.6 ✅ | §5.3-§5.4 ✅ | **pyomo §15** for the contract; per-solver docs for parameter names |
| Time limit (`limits/time` for SCIP, `max_cpu_time` for Ipopt) | §15 (general `timelimit`) | §5.7 ✅ | §4.8 ✅ | **SCIP §5.7** + **ipopt §4.8** |
| Termination + status interpretation | §16 ✅ | §7 ✅ | §13 ✅ (with full status table) | **per-solver chapter**: SCIP §7 for SCIP statuses, ipopt §13 for Ipopt return codes; pyomo §16 only for the generic `TerminationCondition` enum |
| `load_solutions=False` discipline | §16 ✅ | §5.3 🔁 | §21.16 ✅ | **pyomo §16** |
| Persistent / APPSI solvers | §18 ✅ | §3.10 (no SCIP APPSI exposed currently) | §6 (APPSI Ipopt), §18.5 ✅ | **pyomo §18** for the contract; **ipopt §18.5** for APPSI repeated-solve patterns |
| `executable=` path control | §15 🔁 | §1.5 ✅ | §1, §16.2-§16.3 ✅ | **per-solver install chapters** |
| `keepfiles=True` artifact paths (`.nl`/`.sol`/`.row`/`.col`/log) | §15 🔁 | §3.12, §11 ✅ | §16, §21 ✅ | **per-solver debugging chapters** |

### Termination, debugging, infeasibility

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| Generic Pyomo termination handling | §16 ✅ | — | — | **pyomo §16** |
| SCIP-specific termination + log | — | §7, §8 ✅ | — | **SCIP §7-§8** |
| Ipopt-specific iteration table + return statuses | — | — | §13 ✅ | **ipopt §13** |
| IIS workflow | §31 ✅, §36.8 🔁 | §16.11 (standalone SCIP IIS from Pyomo artifact) ✅ | §18 (NLP-specific feasibility) | **pyomo §31** for the workflow; **SCIP §16.11** for solver-side standalone IIS |
| MIS workflow | §31 ✅ | — | — | **pyomo §31** |
| `Restoration_Failed` / NLP infeasibility | — | — | §16.5-§16.6 ✅ | **ipopt §16** |
| Numerical scaling + conditioning | §35 ✅ | §15 ✅ | §11, §17 ✅ | **per-solver chapter** for solver-aware tactics; **pyomo §35** for general Pyomo-level scaling suffixes |
| Big-M discipline | §35.6 ✅ | §15.10 (guardrails) 🔁 | — | **pyomo §35.6** |
| Bound tightening | §35.7 ✅ | §9 (propagation tightens) 🔁 | §19.6 (bound-tightening loops) ✅ | **pyomo §35.7** for general; **ipopt §19.6** for NLP-specific iterative tightening |
| Performance debugging | §35 ✅ | §14 ✅ | §18 ✅ | **per-solver chapter**: SCIP §14, ipopt §18; pyomo §35 for build-time |
| Singular Jacobian / dependent equality | §33 (incidence) ✅ | — | §16.15 ✅ | **pyomo §33** for structural detection; **ipopt §16.15** for Ipopt failure mode |
| Nonsmooth `abs`/`max`/`min`/conditionals | — | — | §16.12, §17.4 ✅ | **ipopt §16.12 + §17.4** for what NLP solvers can't handle. For *symbolic* reformulation tooling, see the `sympy-ref` skill. |
| Common warnings/errors reference | §36.10 ✅ | §3.13 (failure modes) 🔁 | §16 ✅ | **pyomo §36.10** for Pyomo-side; **ipopt §16** for Ipopt-specific |

### Reformulation and transformations

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| `TransformationFactory(...)` | §19 ✅ | §15.5 (GDP-to-MIP through transforms) 🔁 | — | **pyomo §19** |
| GDP (Big-M, hull, logical-to-linear) | §20 ✅ | §15.5 (SCIP-routed transforms) 🔁 | — | **pyomo §20** |
| GDPopt | §21 ✅ | — | — | **pyomo §21** |
| MindtPy (MINLP) | §22 ✅ | §15.7 (nonlinear routing) 🔁 | §19.8 (NLP subproblems in GDP/MINLP) ✅ | **pyomo §22** for the algorithm driver; **ipopt §19.8** for the inner NLP role |
| PyROS (robust) | §23 ✅ | — | — | **pyomo §23** |
| `pyomo.dae` + discretization | §24 ✅ | — | §19.9 (DAE+Ipopt) ✅ | **pyomo §24** for `ContinuousSet`+`DerivativeVar`+`discretize`; **ipopt §19.9** for solver-side concerns |
| MPEC + complementarity | §25 ✅ | — | — | **pyomo §25** |
| Pyomo Network (`Port`/`Arc`) | §26 ✅ | — | — | **pyomo §26** |
| Units handling | §27 ✅ | — | — | **pyomo §27** |

### NLP-specific concerns (Ipopt-centric, with Pyomo-side support)

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| NLP modeling contract (smoothness, bounds, single objective) | §7 (vars) + §9 (obj) | — | **§3** ✅ | **ipopt §3** |
| Algorithmic control (`mu_*`, line search, KKT solve, termination) | — | — | **§4** ✅ | **ipopt §4** |
| Option deployment channels (`opt.options`/solve-local/`ipopt.opt`/`.nl` cmdline/`pyomo.contrib`) | §15 (Pyomo channels) | §5.6 🔁 | **§5** ✅ | **ipopt §5** |
| `ipopt.opt` working-directory pattern | — | — | **§1.8 + §5.5** ✅ | **ipopt §1.8 + §5.5** |
| Linear solver (MUMPS, MA27/57/77/86/97, Pardiso, MKL Pardiso, SPRAL) | — | — | **§10 + §1.10** ✅ | **ipopt §10** |
| HSL + Pardiso runtime loading (`hsllib`/`pardisolib`) | — | — | **§2.6** ✅ | **ipopt §2.6** |
| Derivatives + Hessian strategy (exact vs L-BFGS) | — | — | **§8** ✅ | **ipopt §8** |
| Derivative checker (`derivative_test=...`) | — | — | **§9** ✅ | **ipopt §9** |
| Warm starts (suffix transport, `warm_start_init_point`) | §17 (mutation) 🔁 | — | **§12** ✅ | **ipopt §12** |
| `Solve_Succeeded` / `Solved_To_Acceptable_Level` / restoration | — | — | **§13** ✅ | **ipopt §13** |
| Dual + bound multiplier audit (`ipopt_zL_*`/`ipopt_zU_*` + KKT consistency) | §12 (suffix mechanics) | — | **§14** ✅ | **ipopt §14** |
| Option bundles (debug derivatives / fast quiet / strict final / warm-start resolve / etc.) | — | — | **§15** ✅ | **ipopt §15** |
| Direct interfaces (TNLP/C/Fortran/Java/R/`cyipopt`) | — | — | **§20** ✅ | **ipopt §20** |
| Reproducibility bundle (env + executable + options + seeds + logs + result + fingerprint) | §1.10 + §39.7 | — | **§21** ✅ | **ipopt §21** for the most procedural bundle; **pyomo §1.10 + §39.7** for Pyomo-side |

### MILP/MINLP-specific concerns (SCIP-centric)

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| SCIP capability overview (MILP/MIQP/MINLP/CIP/PB) | §1.4 (matrix) | **§2** ✅ | §0.4 (Ipopt is not MIP) 🔁 | **SCIP §2** |
| Pyomo-side problem-class capability map | **§0.4** ✅ | §4 (SCIP-routed classes) ✅ | — | **pyomo §0.4** for global; **SCIP §4** for SCIP-specific |
| SCIP parameter system (`limits/time`, `display/statistics`, etc.) | — | **§6** ✅ | — | **SCIP §6** |
| Presolve/cuts/heuristics/branching tuning | — | **§9, §14** ✅ | — | **SCIP §9, §14** |
| Constraint handlers (Pyomo-facing boundary) | — | **§10** ✅ | — | **SCIP §10** |
| File formats (LP/MPS/CIP) and standalone shell | — | **§11** ✅ | §20.3 (`.nl` cmdline) 🔁 | **SCIP §11** |
| Exact MILP mode (rational arithmetic, certificates) | — | **§13** ✅ | — | **SCIP §13** |
| SCIP vs HiGHS / IPOPT / Couenne / Bonmin / commercial | §0.11 (general) | **§19** ✅ | — | **SCIP §19** |

### Sensitivity, parameter estimation, design of experiments, advanced workflows

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| Sensitivity Toolbox (sIPOPT, k_aug) | **§32.1-§32.7** ✅ | — | §19.11 (cyipopt) 🔁 | **pyomo §32** |
| `parmest` parameter estimation | **§32.8-§32.14** ✅ | — | — | **pyomo §32** |
| Pyomo.DoE (Fisher Information Matrix design) | **§32.15-§32.20** ✅ | — | — | **pyomo §32** |
| Parametric sweeps + sequential solves + homotopy | §17 (mutation) | — | **§19.1-§19.3** ✅ | **ipopt §19** |
| NLP subproblems in MINLP/GDP | §22 (MindtPy) | — | **§19.7-§19.8** ✅ | **ipopt §19.7-§19.8** |
| Incidence + structural analysis | **§33** ✅ | — | §16.15 (singular Jacobian) 🔁 | **pyomo §33** |
| PyNumero (custom NLP algorithms) | **§34** ✅ | — | §19.11 (cyipopt) 🔁 | **pyomo §34** |
| Stochastic programming (`mpi-sppy`/PySP) | **§28** ✅ | — | §18.10 (MPI parallel scenarios) 🔁 | **pyomo §28** for SP-specific; **ipopt §18.10** for parallel infrastructure |
| Alternative solutions / solution pools | **§30** ✅ | — | — | **pyomo §30** |

### Deployment, testing, observability

| Topic | pyomo | SCIP | ipopt_standalone | Authoritative |
|-------|-------|------|------------------|---------------|
| Notebooks / scripts / batch / HPC / containers / CI / services | §1.9 + §39 ✅ | §17.4-§17.9 ✅ | §1.13-§1.17 + §18.9-§18.10 ✅ | **pyomo §39** for Pyomo-side breadth; per-solver §17/§1 for solver-specific |
| Solver license management | §39.4 ✅ | §1.10 (licensing notes) 🔁 | §1.7 + §2.7 (HSL/Pardiso licenses) ✅ | **pyomo §39.4** |
| `environment.yml` / conda lockfiles | §1 + §39.5 ✅ | §1.3-§1.4 ✅ | §1.3 ✅ | **per-solver chapter** for solver-aware pinning |
| BLAS threading / parallel scenarios | §39.2 (mpi4py) | — | **§18.8-§18.10** ✅ | **ipopt §18.8-§18.10** |
| Reproducibility bundle | §1.10 + §39.7 ✅ | §1.8, §16.10 ✅ | **§21** ✅ | **ipopt §21** for procedural bundle |
| QA / pytest harness | §37 ✅ | §18 ✅ | **§22** ✅ | **per-doc** — each has its own QA chapter; pyomo §37 for Pyomo-wide |
| `pyomo.contrib` ecosystem | §40 ✅ | — | §6 (new contrib Ipopt interface) 🔁 | **pyomo §40** |

---

## Operating rules

1. **Domain code must not import `pyomo` directly.** Pyomo lives behind ports/adapters in `smartref` (`OptimizationPort`, etc.). If you see `import pyomo.environ as pyo` outside an adapter, you are crossing an architectural boundary.

2. **Solvers are external, separately installed, and version-pinned.** `pip install pyomo` does **not** install `scip` or `ipopt`. In this repo, the standalone executables come from a project-scoped micromamba env at `/home/paul/micromamba/envs/smartref-solvers` provisioned by `build_support/local_solvers/bootstrap.sh` (auto-invoked from `.envrc`). **Always** read the executable from `$SMARTREF_SCIP_EXECUTABLE` / `$SMARTREF_IPOPT_EXECUTABLE`, or set `PyomoSolverConfiguration.solver_executable_path` directly — **never** rely on bare `scip` / `ipopt` on `PATH` (`/usr/local/bin/scip` is commonly the unrelated Sourcegraph SCIP code-intelligence CLI; the probe `probe_pyomo_external_solvers` rejects it via fingerprint). Verify availability via that probe or `SolverFactory(name, executable=path).available()` before any solve attempt and surface the result in deployment artifacts. The `pyomo_scip_executable` / `pyomo_ipopt_executable` pytest fixtures and `pyomo_scip` / `pyomo_ipopt` markers gate opt-in tests. (pyomo §1.4-§1.6, SCIP §1.5-§1.7, ipopt §1.4)

3. **Always check `results.solver.termination_condition` (or `results.solver.status`) before trusting any variable value or objective.** Pyomo will let you read stale or never-initialized values silently. Use `load_solutions=False` + explicit gate + `model.solutions.load_from(results)` for production code. (pyomo §16, §38.6, SCIP §5.2, §16.1, ipopt §0.12, §13, §16.21)

4. **`SolverFactory("ipopt")` cannot solve integer/binary problems.** Ipopt is a continuous NLP solver. For MINLP, use `SolverFactory("mindtpy")`, `SolverFactory("scip")`, or `SolverFactory("bonmin")`/`couenne`. (ipopt §0.4, §3, pyomo §22)

5. **Native solver option names go through Pyomo unchanged for SCIP and Ipopt — but the *channel* matters.** SCIP: `opt.options["limits/time"] = 300` → temp `scip.set` written before solve. Ipopt: `opt.options["tol"] = 1e-8` → AMPL solver-options string OR `ipopt.opt` file. Use `opt.options[k]` for persistence across solves; use `solve(options={...})` for one-shot overrides. The `ipopt.opt` file is read from the **current working directory** unless routed otherwise. (SCIP §3.5, §5.6, §5.8; ipopt §5)

6. **Nonsmooth `abs`/`max`/`min`/`Piecewise` cannot be sent to Ipopt directly.** Reformulate using auxiliary variables + epigraph/hypograph (smooth approximations like `sqrt(x**2 + eps)`, max-as-LP-via-epigraph, etc.). When you want symbolic-derivation tooling to produce the reformulation, see the `sympy-ref` skill. (ipopt §16.12, §17.4)

7. **`mutable=True` Param + APPSI is the right path for repeated solves; `model.del_component` + rebuild is the wrong path.** APPSI Ipopt and persistent-Gurobi/CPLEX maintain solver-side state across solves — invalidating that state with structural mutations is expensive. (pyomo §6, §17, §18, §38.4-§38.5; ipopt §18.4-§18.5)

8. **`freeze` solver versions in `environment.yml` AND record them in run artifacts.** Ipopt 3.14.x linear-solver defaults vary by build; SCIP 10 introduces exact-mode features absent in 9.x. A run that worked in lab won't necessarily reproduce in prod. (pyomo §1.10 + §39.7, SCIP §1.4, ipopt §21)

9. **Suffix declarations are direction-typed and component-keyed.** `Suffix(direction=Suffix.IMPORT)` for duals/reduced costs reading. `Suffix(direction=Suffix.EXPORT)` for warm-start metadata. Keying is by Pyomo component object, not name. After `optimize()`, suffix maps are populated only if the solver supplied data. (pyomo §12; ipopt §14.7, §14.15)

10. **Pyomo's expression system is not SymPy.** They are different DAG models: Pyomo expressions are designed for NL-file emission and derivative generation by the AMPL solver library; SymPy expressions are general-purpose CAS structures. Do not pass SymPy expressions into `Constraint(rule=...)` directly — `lambdify` to numeric callables, transcribe symbolically, or evaluate-and-substitute. (pyomo §8 + §38.7; for the SymPy side see the `sympy-ref` skill)

11. **`scip` and `ipopt` are file-based interfaces — there are no in-process callbacks.** No solver-side cuts, no event handlers, no branching rules, no warm callbacks are reachable through `SolverFactory("scip"|"ipopt")`. From Pyomo, the only in-loop control is "rebuild model + re-solve." (SCIP §3.9, §10; ipopt §0.7)

12. **Emit a structured run artifact for every solve.** Termination, options used, timing, objective, IIS (if infeasible), gap, iteration count, NLP iteration count, linear solver used, BLAS variant, executable path, conda env hash. `tee=True logfile=path` captures the solver log; `writeStatistics`/`results.solver` capture the structured fields. (pyomo §1.10, §39.7; SCIP §1.8, §17.10; ipopt §21)

---

## Decision trees

### "Which document do I open first?"

```
Question is about Pyomo modeling itself (Var, Constraint, Param, Block, indexing, expressions, transformations)?
  -> pyomo.md §4-§13 for the core AML
  -> pyomo.md §17-§19 for mutation + transformations

Question is about a specific solver invoked via SolverFactory?
  Solver = "scip"     -> SCIP.md (Pyomo-focused throughout)
  Solver = "ipopt"    -> ipopt_standalone.md
  Solver = "mindtpy"  -> pyomo.md §22 (driver) + ipopt_standalone.md §19.8 (inner NLP)
  Solver = "gdpopt"   -> pyomo.md §21
  Solver = "pyros"    -> pyomo.md §23

Question is about Pyomo's higher-level modeling (GDP, MPEC, DAE, Network, Stochastic)?
  -> pyomo.md §20-§28

Question is about model debugging / infeasibility?
  -> pyomo.md §31 (IIS/MIS) + §36 for general
  -> SCIP.md §16 for SCIP-specific routes
  -> ipopt_standalone.md §16 + §18 for NLP-specific (Restoration_Failed, Infeasible_Problem_Detected)

Question is about scaling / numerical conditioning / performance?
  -> pyomo.md §35 for general
  -> SCIP.md §14-§15 for MIP-specific
  -> ipopt_standalone.md §11 + §17 + §18 for NLP-specific

Question is about deployment (notebooks, CLI, batch, HPC, containers, CI)?
  -> pyomo.md §1.9 + §39 for breadth
  -> SCIP.md §17 + ipopt_standalone.md §1 for solver-specific install/deploy

Question is about testing / QA?
  -> pyomo.md §37 for breadth
  -> SCIP.md §18 + ipopt_standalone.md §22 for solver-specific test patterns

Question is about symbolic mathematics (SymPy expressions, calculus, simplification, lambdify, codegen)?
  -> Out of scope here. See the `sympy-ref` skill.

Question is about in-process plugins, callbacks, or native solver control?
  -> Out of scope. The Pyomo external-executable path used here does not support these.
     SCIP.md §12 + ipopt_standalone.md §20 describe what cannot be reached.
```

### "How do I configure SCIP options through Pyomo?"

```
Need a known parameter name?
  -> SCIP.md §6 (parameter system)
  -> Or run `scip` shell: `set save all_params.set` to dump installed-build parameter list

Persistent across solves on the same opt object?
  opt = SolverFactory("scip")
  opt.options["limits/time"] = 300         # SCIP §5.6 + §6
  opt.options["limits/gap"] = 0.01

Per-solve override?
  opt.solve(model, options={"limits/time": 60})        # SCIP §5.6

Need a complete tuned profile?
  -> Persist as `scip.set` file, then load via Pyomo solve options
  -> SCIP.md §11 + §14 (performance bundles)

Need to call a SCIP feature that Pyomo's interface doesn't expose?
  -> Out of scope for this stack. SCIP.md §12 documents the boundary.
```

### "How do I configure Ipopt options through Pyomo?"

```
Persistent on opt object?           opt.options["tol"] = 1e-8       (ipopt §5.3)
Per-solve override?                  opt.solve(m, options={...})    (ipopt §5.4)
Need an option that Pyomo doesn't pass through cleanly?
  -> Write `ipopt.opt` in the working directory                    (ipopt §1.8 + §5.5)

Diagnosing an unsupported option?
  -> ipopt -=                                                       (ipopt §2.4)
  -> Compare against installed-build option universe                (ipopt §2.9)

Restoration_Failed / Infeasible_Problem_Detected?
  -> ipopt §16.5-§16.6 (failure-mode triage)
  -> Apply Bundle "Feasibility + restoration diagnostics"           (ipopt §15.9)

Bad scaling suspected?
  -> ipopt §11 (scaling channels: nlp_scaling_method, linear_system_scaling)
  -> Apply Bundle "Debug derivatives" first, then Bundle "MUMPS tuning"
                                                                    (ipopt §15.2 + §15.6)

Want to swap linear solver?
  -> ipopt §10 (catalog: MUMPS, MA27/57/77/86/97, Pardiso, MKL, SPRAL)
  -> Set linear_solver=ma27 + hsllib=/path/to/libhsl.so            (ipopt §2.6 + §10)
```

### "Which Pyomo solver path for which problem class?"

```
LP (continuous, linear)?                -> HiGHS / GLPK / CBC / Gurobi / CPLEX (pyomo §1.4)
MILP (integer, linear)?                 -> HiGHS / SCIP / CBC / Gurobi / CPLEX (SCIP.md §4.1, §19)
MIQP (quadratic objective + integer)?   -> Gurobi / CPLEX / SCIP                (SCIP.md §4.2)
NLP (continuous, smooth nonlinear)?     -> Ipopt / KNITRO                       (ipopt §0)
MINLP?                                  -> SCIP (global) or BONMIN/Couenne or
                                            MindtPy (Pyomo decomposition)       (SCIP.md §4.3, pyomo §22)
GDP?                                    -> GDPopt or transform → MIP/MINLP      (pyomo §20-§21)
Robust?                                 -> PyROS                                (pyomo §23)
Dynamic / DAE?                          -> pyomo.dae + Ipopt or IPOPT-via-IDAES (pyomo §24)
Bilevel / MPEC?                         -> Pyomo MPEC + manual                  (pyomo §25)
Stochastic?                             -> mpi-sppy / PySP                      (pyomo §28)
```

---

## Known gotchas

| Gotcha | Detail | Reference |
|--------|--------|-----------|
| **Solvers don't auto-install with Pyomo** | `pip install pyomo` and `conda install pyomo` install only the modeling layer. SCIP and Ipopt are separate packages (`conda-forge::scip`, `conda-forge::ipopt`). Always probe `SolverFactory(name).available()` at startup. | pyomo §1.4, SCIP §1.7, ipopt §0.13 |
| **Modern `scip` vs legacy `scipampl`** | SCIP ≥ 8 ships with an integrated AMPL/NL reader registered as `scip`. Older SCIP was wrapped as `scipampl`. Pyomo's plugin tries `scip` first, then falls back. If you have both, Pyomo will pick the modern one — verify via `opt.executable()`. | SCIP §0.7, §3.2 |
| **`ipopt.opt` is working-directory-relative** | Ipopt looks for `ipopt.opt` in the **process current working directory**, not the model file's directory. Tests that change cwd, batch scripts that chdir, and notebooks that don't pin cwd will silently miss your options file. | ipopt §1.8, §5.5 |
| **`opt.options` is a plain dict — no validation** | Typing `opt.options["mu_strategy"] = "adapitve"` (typo) silently uses Ipopt's default value. Validate options against `ipopt -=` parameter dump or, for SCIP, against a `set save` dump. | ipopt §16.4; SCIP §6 |
| **Empty-string Ipopt options mean "use default"** | `opt.options["linear_solver"] = ""` does NOT clear the linear solver — it falls back to the build's default (usually MUMPS). To probe what was actually used, parse the solver log. | ipopt §10, §17 |
| **`load_solutions=True` is the Pyomo default and silently loads stale/invalid values** | When termination is not optimal, `load_solutions=True` may load infeasible or partial values into `model.x.value`. Always gate on `termination_condition` or use `load_solutions=False` + explicit `model.solutions.load_from(results)`. | pyomo §16, ipopt §13, §21.16 |
| **`ConcreteModel` mutation requires no special API** | Pyomo accepts post-solve mutations (bound changes, new constraints) without `freeTransform()` because it rebuilds the NL file on each solve. APPSI/persistent solvers are the exception — they DO require explicit notification of changes. | pyomo §17, §18 |
| **Ipopt return statuses are not the same as Pyomo `TerminationCondition`** | Ipopt has 18+ return codes (Solve_Succeeded, Solved_To_Acceptable_Level, Infeasible_Problem_Detected, Restoration_Failed, etc.). Pyomo maps them into a coarser enum. Read the original Ipopt status from `results.solver.message` or the log for full diagnostic detail. | ipopt §13 |
| **`Restoration_Failed` is not "infeasible"** | It can mean: bad scaling, bad derivatives, bad starting point, OR genuine local infeasibility. Diagnose first (Bundle "Feasibility + restoration diagnostics"); declare infeasibility only after ruling out the others. | ipopt §16.5, §18 |
| **Pyomo `Suffix` doesn't auto-import** | Declaring `model.dual = Suffix(direction=Suffix.IMPORT)` only requests duals — the solver must support and supply them, AND `load_solutions=True` (or explicit `load_from`) must run. After re-solving, the suffix data is replaced, not appended. | pyomo §12.6, ipopt §14 |
| **`ExternalFunction` breaks NL writer derivative generation** | Ipopt requires C² derivatives. `ExternalFunction` provides numeric callbacks that the NL writer cannot symbolically differentiate. Alternatives: piecewise-linear approximation, smooth surrogates, `cyipopt` with manual TNLP derivatives. | pyomo §13, ipopt §19.10 |
| **APPSI doesn't currently expose SCIP** | APPSI Ipopt, Gurobi, CPLEX, CBC, HiGHS, MAiNGO are all available. APPSI SCIP is not currently exported. Use `SolverFactory("scip")` (file-based) for SCIP from Pyomo. | SCIP §3.10 |
| **Pyomo expressions ≠ SymPy expressions** | Pyomo's expression DAG is purpose-built for NL emission and supports `quicksum`, `summation`, `Expression`, etc. SymPy's DAG is general-purpose CAS. Mixing them silently misroutes — use SymPy (see the `sympy-ref` skill) to derive, transcribe to Pyomo. | pyomo §8 |
| **`hessian_approximation="limited-memory"` invalidates exact-Hessian benchmarks** | L-BFGS quasi-Newton is robust but converges differently from exact Hessian. Treat the choice as a deliberate experiment, not a debug toggle in production. | ipopt §8 |
| **HSL/Pardiso runtime-loadable, not always installed** | `linear_solver=ma27` may fail if conda-forge build doesn't bundle HSL. Use `hsllib=/path/to/libhsl.so` to point Ipopt at a separately-licensed copy. Verify with `ipopt -=` or via the solver log. | ipopt §2.6, §10 |
| **Big-M values affect both LP relaxation and numerical stability** | Big-M too tight = infeasible original model; too loose = weak LP relaxation, slow solve. Use bound-derived M, not arbitrary `1e9`. | pyomo §35.6, SCIP §15.1 |
| **`Piecewise` representation choice matters** | `pw_repn="SOS2"` requires solver SOS support; `pw_repn="BIGM_BIN"` linearizes; `pw_repn="CC"` (convex combination) gives a tight LP relaxation but more variables. Choose by solver + tightness needs. | pyomo §11.6-§11.7, SCIP §4.6 |

---

## Glossary (which document defines each term)

| Term | Authoritative definition |
|------|--------------------------|
| **`ConcreteModel` vs `AbstractModel`** | pyomo §2 |
| **`Block`** | pyomo §4 |
| **`Set` / `RangeSet` / `dimen`** | pyomo §5 |
| **`Param(mutable=True)`** | pyomo §6 |
| **`Var` (continuous/integer/binary domain)** | pyomo §7 |
| **`quicksum` vs `sum`** | pyomo §8 |
| **`Expression`** | pyomo §8 |
| **`Constraint.Skip`** | pyomo §10 |
| **`Piecewise` / `pw_repn`** | pyomo §11 |
| **`SOSConstraint` (SOS1, SOS2)** | pyomo §11 |
| **`Suffix(direction=...)`** | pyomo §12 |
| **`ExternalFunction`** | pyomo §13 |
| **`DataPortal`** | pyomo §14 |
| **`SolverFactory(name)`** | pyomo §15 |
| **`tee=True` / `keepfiles=True` / `symbolic_solver_labels=True`** | pyomo §15 (general); SCIP §5, ipopt §13 (per-solver semantics) |
| **`load_solutions` / `model.solutions.load_from`** | pyomo §16 |
| **APPSI** | pyomo §18 |
| **`TransformationFactory`** | pyomo §19 |
| **GDP / Big-M / hull / logical-to-linear** | pyomo §20 |
| **GDPopt** | pyomo §21 |
| **MindtPy / OA / ECP / GBD** | pyomo §22 |
| **PyROS** | pyomo §23 |
| **`ContinuousSet` / `DerivativeVar` / `discretize`** | pyomo §24 |
| **MPEC / Complementarity** | pyomo §25 |
| **`Port` / `Arc` / `expand_arcs`** | pyomo §26 |
| **`pyomo.environ.units`** | pyomo §27 |
| **mpi-sppy / PySP** | pyomo §28 |
| **IIS / MIS** | pyomo §31 |
| **Sensitivity Toolbox / sIPOPT / k_aug** | pyomo §32 |
| **parmest / Pyomo.DoE / Fisher Information Matrix** | pyomo §32 |
| **PyNumero / `PyomoNLP`** | pyomo §34 |
| **CIP (Constraint Integer Programming)** | SCIP §0.5 |
| **SCIP Optimization Suite** | SCIP §0.5 |
| **`SolverFactory("scip")` vs `SolverFactory("scipampl")`** | SCIP §0.7, §3.2 |
| **`scip.set` (parameter file)** | SCIP §3.5, §6 |
| **`limits/time` / `limits/gap` / `display/statistics`** | SCIP §5.7, §6 |
| **Exact MILP (rational arithmetic, certificates)** | SCIP §13 |
| **Implied-integrality presolver / cut-based conflict / flower inequalities** | SCIP §13 |
| **Ipopt as standalone NLP solver** | ipopt §0 |
| **Interior-point line-search filter method** | ipopt §0.6 |
| **Restoration phase** | ipopt §3.9, §16.5 |
| **`mu_strategy` (barrier)** | ipopt §4.2 |
| **`hessian_approximation`: `exact` vs `limited-memory`** | ipopt §8 |
| **`derivative_test=first-order|second-order`** | ipopt §9 |
| **`linear_solver` + `hsllib` + `pardisolib`** | ipopt §2.6, §10 |
| **MUMPS / MA27/57/77/86/97 / Pardiso / MKL Pardiso / SPRAL** | ipopt §10 |
| **`nlp_scaling_method` / `linear_system_scaling`** | ipopt §11 |
| **`warm_start_init_point` / `warm_start_bound_push`** | ipopt §12 |
| **Ipopt iteration columns (`||d||`/`alpha_pr`/`alpha_du`/`lg(mu)`/`lg(rg)`/`ls`)** | ipopt §4.9, §13 |
| **Ipopt return statuses (`Solve_Succeeded` / `Solved_To_Acceptable_Level` / `Restoration_Failed` / `Infeasible_Problem_Detected` / `Diverging_Iterates` / etc.)** | ipopt §13 |
| **`ipopt.opt` (option file, working-directory-relative)** | ipopt §1.8, §5.5 |
| **`ipopt_zL_*` / `ipopt_zU_*` (bound multipliers)** | ipopt §14.4 |
| **`cyipopt`** | ipopt §1.6, §19.11, §20.9 |
| **`pyomo.contrib.solver.solvers.ipopt.Ipopt`** | ipopt §6, pyomo §40 |
| **TNLP (C++ Ipopt interface)** | ipopt §20.4 |

---

## Related skills

* **`sympy-ref`** — for symbolic mathematics (CAS, exact arithmetic, calculus, simplification, solvers, code generation, lambdify). SymPy is used here only as a **derivation aid** that produces formulas later transcribed into Pyomo expressions; the two libraries are **not** the same expression substrate (see operating rule 10 above).
* **`smartref-code-intel-ref`** — for structural code search and refactoring inside this repo.
* **`fastapi-nicegui-ref`** — for the web layer.
* **`attrs-cattrs-ref`** — for declarative class definition + boundary serialization.
